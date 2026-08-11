"""Stage 1: disclosure -> validated staging JSON.

The LLM extracts; code validates the arithmetic. Extraction that doesn't tie is
rejected with the failures quoted back (one retry), then the run hard-stops:
nothing downstream may consume unvalidated numbers.
"""
from pathlib import Path

from . import pdfs

SCHEMA_HINT = """
Schema:
{
 "units": "...", "currency": "...", "sign_convention": {"pl": "...", "cf": "..."},
 "items": [
   {"id": "pl_1", "stmt": "pl|bs|cf|segment|soc|kpi|other", "label": "<exact>",
    "value": 0, "prior": 0, "page": 0, "segment": null, "units": null}
 ],
 "ties": [
   {"desc": "total assets = liabilities + equity",
    "lhs": ["bs_12"], "rhs": ["bs_30", "bs_44"], "tolerance": 1.0}
 ],
 "missing": ["cash_flow_statement"],
 "bridge": [{"label": "...", "value": 0, "page": 0}]
}
Each tie: sum(values of lhs ids) must equal sum(values of rhs ids) within tolerance.
STRICT: every object in "items" must contain ALL SIX keys id, stmt, label, value,
prior, page ("prior" may be null; the other five may never be null or omitted).
Do not group items under sub-objects; "items" is one flat list.
"""


def extract(client, system, disclosure_paths, extraction_prompt, cfg):
    all_items, all_ties, meta = [], [], {}
    window_chars = cfg["budgets"].get("extraction_window_chars", 35000)
    for path in disclosure_paths:
        page_texts = pdfs.pages(path)
        for win in pdfs.windows(page_texts, chars_per_window=window_chars):
            doc = pdfs.render(win)
            user = (f"{extraction_prompt}\n{SCHEMA_HINT}\n"
                    f"Document: {Path(path).name} (window pages "
                    f"{win[0][0]}-{win[-1][0]} of the full document)\n\n{doc}")
            obj = client.json(system, user, _validator,
                              repair_retries=cfg["budgets"]["extraction_retries"])
            # drop incomplete stragglers the validator tolerated (few, not tie-referenced)
            dropped = [it.get("id") for it in obj.get("items", []) if not _complete(it)]
            if dropped:
                obj["items"] = [it for it in obj["items"] if _complete(it)]
                meta.setdefault(Path(path).name, {}).setdefault("dropped_items", []).extend(dropped)
            offset = len(all_items)
            remap = {}
            for it in obj.get("items", []):
                new_id = f"{it['id']}_{offset}"
                remap[it["id"]] = new_id
                it["id"] = new_id
                it["doc"] = Path(path).name
                all_items.append(it)
            for tie in obj.get("ties", []):
                tie["lhs"] = [remap.get(i, i) for i in tie["lhs"]]
                tie["rhs"] = [remap.get(i, i) for i in tie["rhs"]]
                all_ties.append(tie)
            meta.setdefault(Path(path).name, {}).update(
                {k: obj.get(k) for k in ("units", "currency", "sign_convention", "missing")})
    return {"items": all_items, "ties": all_ties, "meta": meta}


def _complete(it):
    return all(it.get(k) not in (None, "") or (k == "value" and it.get(k) == 0)
               for k in ("id", "stmt", "label", "value", "page"))


def _validator(obj):
    errs = []
    items = {it.get("id"): it for it in obj.get("items", [])}
    if not items:
        errs.append("no items extracted")
    incomplete = [i for i, it in items.items() if not _complete(it)]
    # tolerate a few incomplete items (weak models drop fields) UNLESS a tie needs them
    if len(incomplete) > max(3, len(items) // 10):
        errs.append(f"{len(incomplete)} items missing required fields "
                    f"(id/stmt/label/value/page), e.g. {incomplete[:5]} — every item "
                    "MUST carry all five fields")
    tie_refs = {i for tie in obj.get("ties", []) for i in tie.get("lhs", []) + tie.get("rhs", [])}
    for i in sorted(set(incomplete) & tie_refs):
        missing = [k for k in ("id", "stmt", "label", "value", "page")
                   if items[i].get(k) in (None, "") and not (k == "value" and items[i].get(k) == 0)]
        errs.append(f"item {i} is used in a tie but is missing {missing} — "
                    f"add the missing key(s) to this exact item")
    for tie in obj.get("ties", []):
        try:
            lhs = sum(items[i]["value"] for i in tie["lhs"])
            rhs = sum(items[i]["value"] for i in tie["rhs"])
        except KeyError as e:
            errs.append(f"tie '{tie.get('desc')}' references unknown item {e}")
            continue
        tol = tie.get("tolerance", 1.0)
        if abs(lhs - rhs) > tol:
            errs.append(f"tie FAILED '{tie.get('desc')}': lhs {lhs} vs rhs {rhs} (tol {tol}) — "
                        "re-check the extracted values on the cited pages")
    if not obj.get("ties"):
        errs.append("no ties provided — emit the arithmetic relations that validate your extraction")
    return errs


def find_by_prior(staging, prior_value, tolerance=0.6):
    """Triangulation: locate items whose comparative equals the model's stored
    prior-year value. Number-based, so immune to labels/synonyms/translation."""
    if prior_value is None or not isinstance(prior_value, (int, float)):
        return []
    return [it for it in staging["items"]
            if isinstance(it.get("prior"), (int, float))
            and abs(it["prior"] - prior_value) <= tolerance]
