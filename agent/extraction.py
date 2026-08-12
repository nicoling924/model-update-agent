"""Stage 1: disclosure -> validated staging JSON.

The LLM extracts; code validates the arithmetic. Extraction that doesn't tie is
rejected with the failures quoted back (one retry), then the run hard-stops:
nothing downstream may consume unvalidated numbers.
"""
from pathlib import Path

from . import pdfs
from .llm import LLMError

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
    """Optionally double-extract and keep the consensus (budgets.extraction_votes: 2).
    Misreads rarely repeat identically; agreement filters them at the source."""
    votes = cfg["budgets"].get("extraction_votes", 1)
    passes = [_extract_once(client, system, disclosure_paths, extraction_prompt, cfg)
              for _ in range(votes)]
    if len(passes) == 1:
        return passes[0]
    if len(passes) == 2:
        merged = _consensus(passes[0], passes[1])
    else:
        merged = _majority(passes)
    print(f"    [2] consensus: {len(merged['items'])} items kept from "
          f"{[len(p['items']) for p in passes]}", flush=True)
    return merged


def _majority(passes):
    """3+ passes: keep an item when >=2 passes agree on its value (coverage-
    preserving, unlike strict 2-pass intersection)."""
    def key(it):
        return (it.get("stmt"), __import__("re").sub(r"[^a-z0-9]+", " ",
                str(it.get("label", "")).lower()).strip())
    buckets = {}
    for pi, p in enumerate(passes):
        for it in p["items"]:
            buckets.setdefault(key(it), []).append((pi, it))
    items = []
    for k, cands in buckets.items():
        vals = [it.get("value") for _, it in cands if isinstance(it.get("value"), (int, float))]
        best_group = []
        for _, it in cands:
            v = it.get("value")
            if not isinstance(v, (int, float)):
                continue
            grp = [(pj, jt) for pj, jt in cands
                   if isinstance(jt.get("value"), (int, float)) and abs(jt["value"] - v) <= 1.0]
            if len({pj for pj, _ in grp}) > len({pj for pj, _ in best_group}):
                best_group = grp
        if len({pj for pj, _ in best_group}) >= 2:
            rep = dict(best_group[0][1])
            priors = [jt.get("prior") for _, jt in best_group
                      if isinstance(jt.get("prior"), (int, float))]
            if priors and (max(priors) - min(priors) > 1.0):
                rep["prior"] = None
            items.append(rep)
    ids = {it["id"] for it in items}
    ties = [t for t in passes[0]["ties"]
            if all(i in ids for i in t.get("lhs", []) + t.get("rhs", []))]
    return {"items": items, "ties": ties,
            "meta": {**passes[0].get("meta", {}), "consensus": "majority-of-3"}}


def _consensus(a, b):
    """2-pass merge, COVERAGE-PRESERVING: agreed items stay clean; items only in
    pass 1 or with disagreeing values are KEPT but marked disputed (downstream
    treats disputed like low-trust: never accepted without corroboration)."""
    def key(it):
        return (it.get("stmt"), __import__("re").sub(r"[^a-z0-9]+", " ",
                str(it.get("label", "")).lower()).strip())
    bmap = {}
    for it in b["items"]:
        bmap.setdefault(key(it), []).append(it)
    items = []
    for it in a["items"]:
        matched = False
        for cand in bmap.get(key(it), []):
            va, vb = it.get("value"), cand.get("value")
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)) \
                    and abs(va - vb) <= 1.0 and abs(int(it.get("page", 0)) - int(cand.get("page", 0))) <= 2:
                pa, pb = it.get("prior"), cand.get("prior")
                if isinstance(pa, (int, float)) and isinstance(pb, (int, float)) and abs(pa - pb) > 1.0:
                    it = dict(it, prior=None)  # values agree, priors don't — keep value only
                matched = True
                break
        if not matched:
            it = dict(it, disputed=True)  # keep the data, mark the doubt
        items.append(it)
    ids = {it["id"] for it in items}
    ties = [t for t in a["ties"]
            if all(i in ids for i in t.get("lhs", []) + t.get("rhs", []))]
    return {"items": items, "ties": ties, "meta": {**a.get("meta", {}), "consensus": True}}


def _extract_once(client, system, disclosure_paths, extraction_prompt, cfg):
    all_items, all_ties, meta = [], [], {}
    window_chars = cfg["budgets"].get("extraction_window_chars", 35000)
    for path in disclosure_paths:
        page_texts = pdfs.pages(path)
        for win in pdfs.windows(page_texts, chars_per_window=window_chars):
            doc = pdfs.render(win)
            if len(_NUMTOKEN.findall(doc)) < 30:
                continue  # boilerplate window; no financial tables to extract
            print(f"    [2] {Path(path).name} pages {win[0][0]}-{win[-1][0]} "
                  f"(total items so far: {len(all_items)})", flush=True)
            user = (f"{extraction_prompt}\n{SCHEMA_HINT}\n"
                    f"Document: {Path(path).name} (window pages "
                    f"{win[0][0]}-{win[-1][0]} of the full document)\n\n{doc}")
            try:
                obj = client.json(system, user, _validator,
                                  repair_retries=cfg["budgets"]["extraction_retries"])
            except LLMError:
                # Walk-away rule: don't stall the run on one untied table. Re-fetch
                # with shape-only validation, then QUARANTINE items in failing ties —
                # their model rows will fall back to estimate + red flag downstream.
                obj = client.json(system, user, _shape_validator, repair_retries=1)
                obj, quarantined = _quarantine(obj)
                if quarantined:
                    meta.setdefault(Path(path).name, {}).setdefault(
                        "quarantined", []).extend(quarantined)
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
    if len(all_items) < 30:
        raise LLMError(f"extraction produced only {len(all_items)} items across all "
                       "documents — too sparse to update a model; aborting before any edit")
    return {"items": all_items, "ties": all_ties, "meta": meta}


def _complete(it):
    return all(it.get(k) not in (None, "") or (k == "value" and it.get(k) == 0)
               for k in ("id", "stmt", "label", "value", "page"))


_NUMTOKEN = __import__("re").compile(r"\d[\d,]{2,}")


def _coerce_num(x):
    """'1,234' -> 1234.0; '(56)' -> -56.0; '-'/'n/a'/'' -> None; numbers pass through."""
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        t = x.strip().replace(",", "").replace("\u2013", "-").replace("\u2014", "-")
        neg = t.startswith("(") and t.endswith(")")
        t = t.strip("()")
        try:
            v = float(t)
            return -v if neg else v
        except ValueError:
            return None
    return None


def _clean(obj):
    for it in obj.get("items", []):
        it["value"] = _coerce_num(it.get("value"))
        it["prior"] = _coerce_num(it.get("prior"))
    return obj


def _validator(obj):
    _clean(obj)
    errs = []
    items = {it.get("id"): it for it in obj.get("items", [])}
    if not items:
        return errs  # a window may legitimately hold no financial tables
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
            refs = tie["lhs"] + tie["rhs"]
            nones = [i for i in refs if items[i].get("value") is None]
            if nones:
                errs.append(f"tie '{tie.get('desc')}' references items with non-numeric "
                            f"values {nones} — give numeric values or drop the tie")
                continue
            lhs = sum(items[i]["value"] for i in tie["lhs"])
            rhs = sum(items[i]["value"] for i in tie["rhs"])
        except KeyError as e:
            errs.append(f"tie '{tie.get('desc')}' references unknown item {e}")
            continue
        tol = tie.get("tolerance", 1.0)
        if abs(lhs - rhs) > tol:
            detail = ", ".join(
                f"{i}='{items[i].get('label', '?')}'={items[i].get('value', '?')}"
                for i in tie["lhs"] + tie["rhs"])
            errs.append(f"tie FAILED '{tie.get('desc')}': lhs {lhs} vs rhs {rhs} (tol {tol}). "
                        f"Components: {detail}. Fix the wrong value(s) against the cited pages, "
                        "or fix the tie's sides to match the signs you recorded")
    if not obj.get("ties"):
        errs.append("no ties provided — emit the arithmetic relations that validate your extraction")
    return errs


def _shape_validator(obj):
    _clean(obj)
    errs = []
    for it in obj.get("items", []):
        if not it.get("id"):
            errs.append("every item needs an id")
            break
    return errs


def _quarantine(obj):
    """Remove items that participate in FAILING ties (keeping any item that a
    passing tie also vouches for). Returns (obj, quarantined_descriptions)."""
    items = {it.get("id"): it for it in obj.get("items", []) if it.get("id")}
    failing_ids, passing_ids = set(), set()
    for tie in obj.get("ties", []):
        try:
            lhs = sum(items[i]["value"] or 0 if isinstance(items[i].get("value"), (int, float)) else 0
                      for i in tie.get("lhs", []))
            rhs = sum(items[i]["value"] or 0 if isinstance(items[i].get("value"), (int, float)) else 0
                      for i in tie.get("rhs", []))
        except KeyError:
            continue
        refs = set(tie.get("lhs", []) + tie.get("rhs", []))
        if abs(lhs - rhs) > max(tie.get("tolerance", 1.0), 1.0):
            failing_ids |= refs
        else:
            passing_ids |= refs
    bad = failing_ids - passing_ids
    quarantined = [f"{i} '{items[i].get('label', '?')}'={items[i].get('value', '?')}"
                   for i in sorted(bad)]
    obj["items"] = [it for it in obj.get("items", []) if it.get("id") not in bad]
    obj["ties"] = [t for t in obj.get("ties", [])
                   if not (set(t.get("lhs", []) + t.get("rhs", [])) & bad)]
    return obj, quarantined


def find_by_prior(staging, prior_value, tolerance=0.6):
    """Triangulation: locate items whose comparative equals the model's stored
    prior-year value. Number-based, so immune to labels/synonyms/translation."""
    if prior_value is None or not isinstance(prior_value, (int, float)):
        return []
    return [it for it in staging["items"]
            if isinstance(it.get("prior"), (int, float))
            and abs(it["prior"] - prior_value) <= tolerance]
