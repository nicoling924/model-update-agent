"""Deterministic table lookup — numbers never pass through an LLM.

The pdfs renderer already reconstructs every table into machine lines:
    Investment property | 2025: 754 | 2024: 817
Memory says WHICH label feeds a model row (interpretation done once, by the
learner). So the per-update read is pure code: find the line by NAME, verify
the prior-year figure against the model (mismatch = restatement, not rejection),
and copy the current figure. Renaming rare -> name is the key; restating common
-> the number is the check, never the key.
"""
import re

from . import pdfs
from .mapping import norm

_CELL = re.compile(r"([^|]+?):\s*([^|]+)")


def _coerce(x):
    t = str(x).strip().replace(",", "").replace("–", "-").replace("—", "-")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").rstrip("%")
    try:
        v = float(t)
        return -v if neg else v
    except ValueError:
        return None


def index_tables(disclosure_paths):
    """[(page, section, label, {header: value})] from every structured line."""
    out = []
    for path in disclosure_paths:
        pt = pdfs.pages(path)
        secs = pdfs.sections(pt)
        for pnum, text in pt:
            if "[STRUCTURED TABLES" not in text:
                continue
            block = text[text.index("[STRUCTURED TABLES"):]
            for line in block.splitlines()[1:]:
                if " | " not in line:
                    continue
                parts = line.split(" | ")
                label = parts[0].strip()
                cells = {}
                for seg in parts[1:]:
                    m = _CELL.match(seg.strip())
                    if m:
                        cells[m.group(1).strip()] = m.group(2).strip()
                if label and cells:
                    out.append((pnum, secs.get(pnum), label, cells))
    return out


def _year_value(cells, year):
    """Value under the header containing the year string (e.g. '2025', '2025 HK$M')."""
    ys = str(year)
    for h, v in cells.items():
        if ys in h:
            return _coerce(v)
    return None


def lookup_rows(table_index, memory, rows_ctx, target_year, prior_year, tol=1.0):
    """rows_ctx: {(sheet,row): {label, prior_value}} for rows with memory entries.
    Returns {(sheet,row): {value, prior_found, page, line_label, status}}
    status: clean | restated | sign_flip | ambiguous | miss"""
    results = {}
    for key, ctx in rows_ctx.items():
        mem = memory.get(key)
        if not mem or mem.get("kind") != "input" or not mem.get("label"):
            continue
        want = norm(mem["label"])
        sec = norm(mem.get("section") or "")
        pv = ctx.get("prior_value")
        cands = []
        for pnum, section, label, cells in table_index:
            if norm(label) != want:
                continue
            cur = _year_value(cells, target_year)
            pri = _year_value(cells, prior_year)
            if cur is None:
                continue
            cands.append({"page": pnum, "section": norm(section or ""),
                          "label": label, "cur": cur, "pri": pri})
        if not cands:
            results[key] = {"status": "miss"}
            continue
        # rank: prior corroboration first, then section match
        def score(c):
            s = 0
            if isinstance(pv, (int, float)) and isinstance(c["pri"], (int, float)) \
                    and abs(abs(c["pri"]) - abs(pv)) <= tol:
                s += 10
            if sec and sec in (c["section"] or ""):
                s += 3
            return s
        cands.sort(key=score, reverse=True)
        best = cands[0]
        distinct_vals = {round(c["cur"], 1) for c in cands}
        if score(best) == 0 and len(distinct_vals) > 1:
            results[key] = {"status": "ambiguous", "n": len(cands)}
            continue
        v, pri = best["cur"], best["pri"]
        status = "clean"
        if isinstance(pv, (int, float)) and pv:
            if isinstance(pri, (int, float)) and abs(abs(pri) - abs(pv)) > tol:
                ratio = abs(pri) / abs(pv) if pv else 0
                if 0.05 <= ratio <= 20:
                    status = "restated"       # same line, history moved
                else:
                    results[key] = {"status": "ambiguous", "n": len(cands)}
                    continue                   # magnitude absurd -> likely wrong line
            if v != 0 and (v < 0) != (pv < 0):
                v = -v                         # model sign convention wins
                status = status if status == "restated" else "sign_flip"
        results[key] = {"status": status, "value": v, "prior_found": pri,
                        "page": best["page"], "line_label": best["label"]}
    return results
