"""Targeted second-pass extraction — the rescue path for unresolved rows.

For each row the cascade could not resolve, we know one hard fact: the model's
stored prior-year value. That number is a LANDMARK — we search the cached page
text for it, find the exact table it lives in, and ask the LLM to read just that
table with the landmark as an anchor. Acceptance is corroboration: the answer
must quote back a prior matching the model's, or it is discarded.

This turns "extract a 234-page report" (hard for a weak model) into "read one
table containing the number 4,976" (easy), and it is fully generic — no company
or industry assumptions, only numbers the model already holds.
"""
import json
import re

from . import pdfs


def _formats(v):
    """Ways a value may be printed: 4976 / 4,976 / (4,976) / -4,976 / 4976.0"""
    out = set()
    for a in {abs(v), round(abs(v))}:
        s_plain = f"{a:,.0f}" if a == int(a) else f"{a:,.1f}"
        out |= {s_plain, s_plain.replace(",", "")}
    return out


def candidate_pages(page_texts, prior_value, max_pages=4):
    if not isinstance(prior_value, (int, float)) or abs(prior_value) < 10:
        return []
    pats = _formats(prior_value)
    hits = []
    for p, t in page_texts:
        if any(s in t for s in pats):
            hits.append(p)
    return hits[:max_pages]


def rescue(client, system, disclosure_paths, unresolved, cfg, log):
    """unresolved: [{sheet,row,label,prior_value}] -> {(sheet,row): {value,page,label}}"""
    pages_by_doc = {str(p): pdfs.pages(p) for p in disclosure_paths}
    # locate landmark pages per row, group rows sharing pages into batches
    batches = {}
    for u in unresolved:
        placed = False
        if u.get("pages"):  # memory-guided: read the remembered page area directly
            doc = u.get("doc") or next(iter(pages_by_doc))
            key = (doc, tuple(u["pages"]))
            batches.setdefault(key, []).append(u)
            continue
        for doc, pt in pages_by_doc.items():
            cp = candidate_pages(pt, u.get("prior_value"))
            if cp:
                key = (doc, tuple(cp))
                batches.setdefault(key, []).append(u)
                break
    accepted = {}
    calls = 0
    for (doc, pageset), rows in sorted(batches.items(), key=lambda kv: -len(kv[1])):
        if calls >= cfg["budgets"].get("targeted_max_calls", 15):
            log.append(f"targeted: call budget reached, {len(rows)} rows left unrescued")
            break
        calls += 1
        pt = dict(pages_by_doc[doc])
        text = "\n\n".join(f"=== PAGE {p} ===\n{pt.get(p, '')}" for p in pageset)
        asks = [{"sheet": u["sheet"], "row": u["row"], "label": u["label"],
                 "prior": u["prior_value"]} for u in rows]
        user = (
            "From the report pages below, find each requested line item. For each, "
            "locate the table row whose PRIOR-year (comparative) column equals the "
            "given 'prior' anchor (sign may be printed positive where the anchor is "
            "negative). Return the CURRENT-year value from the same row.\n"
            'Return JSON: {"results": [{"sheet": ..., "row": ..., '
            '"current": <number or null>, "prior_seen": <number>, "page": <int>, '
            '"label_seen": "<exact row label>"}]}\n'
            "Use null when the line is genuinely absent — never guess.\n\n"
            f"Requested lines: {json.dumps(asks)}\n\nPages:\n{text}")

        def validate(obj):
            return [] if isinstance(obj.get("results"), list) else ["missing results list"]

        try:
            obj = client.json(system, user, validate,
                              repair_retries=cfg["budgets"]["json_repair_retries"])
        except Exception as e:
            log.append(f"targeted batch failed ({doc} p{pageset}): {e}")
            continue
        by_key = {(u["sheet"], u["row"]): u for u in rows}
        for res in obj["results"]:
            u = by_key.get((res.get("sheet"), res.get("row")))
            if not u or not isinstance(res.get("current"), (int, float)):
                continue
            ps, pv = res.get("prior_seen"), u.get("prior_value")
            if not isinstance(ps, (int, float)) or not isinstance(pv, (int, float)):
                continue
            if abs(abs(ps) - abs(pv)) > 1.0:
                log.append(f"targeted: {u['sheet']}!r{u['row']} prior mismatch "
                           f"({ps} vs {pv}) — rejected")
                continue
            cur = res["current"]
            if (ps < 0) != (pv < 0) and pv != 0:
                cur = -cur  # disclosure prints positive where model stores negative
            flipped = False
            if pv != 0 and cur != 0 and (cur < 0) != (pv < 0):
                # model's stored sign convention wins over the LLM's transcription;
                # genuine year-over-year sign changes surface as flagged cells
                cur, flipped = -cur, True
            accepted[(u["sheet"], u["row"])] = {
                "value": cur, "page": res.get("page"), "flag": "red" if flipped else None,
                "note": ("SIGN HARMONIZED to model convention — verify. " if flipped else "")
                        + f"targeted re-read: '{res.get('label_seen', '?')}' p{res.get('page')}"
                        f" (prior corroborated {ps})"}
    return accepted
