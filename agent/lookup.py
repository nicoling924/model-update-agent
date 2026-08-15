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


NUMTOK = re.compile(r"\(?-?[\d,]+(?:\.\d+)?\)?")


def line_nums(line, skip_years=True):
    """Numbers on a line. Format-aware year filter: a financial value >=1000 is
    printed WITH a thousands comma ('2,025'); a bare 4-digit 19xx/20xx token
    ('2025') is a YEAR — column header or date — and poisons every downstream
    prior-triangulation if treated as data."""
    out = []
    for m in NUMTOK.finditer(line):
        t = m.group(0)
        if not any(ch.isdigit() for ch in t):
            continue
        raw = t.strip("()")
        if skip_years and "," not in raw and "." not in raw \
                and raw.isdigit() and 1990 <= int(raw) <= 2100:
            continue
        v = raw.replace(",", "")
        try:
            f = float(v)
        except ValueError:
            continue
        if t.startswith("("):
            f = -f
        out.append(f)
    return out


def label_of(line):
    m = NUMTOK.search(line)
    return (line[:m.start()] if m else line).strip(" .|\u2013\u2014-")


def fmt_variants(c):
    a = abs(c)
    s_ = f"{a:,.0f}" if a == int(a) else f"{a:,.1f}"
    return {s_, s_.replace(",", ""), f"({s_})", f"({s_.replace(',', '')})"}


def raw_lines(disclosure_paths):
    """(page, section, line) for every digit-bearing line: flowed text (the
    analyst's Ctrl+F view) PLUS the structural table re-renders.

    The table renders carry the column header attached to every cell
    ("风电 | 营业收入(本期): 18,224,186,613.44 | ..."), which is exactly what a
    weak reader needs on header-less multi-column note tables — the p14
    production/sales/inventory triplets and the p207 four-column segment
    splits were misread or skipped as bare number soup without them (the
    direct-map rewrite had dropped these; run 102's Driver page paid)."""
    lines = []
    for p in disclosure_paths:
        pt = pdfs.pages(p)
        secs = pdfs.sections(pt)
        for pnum, text in pt:
            body, _, tables = text.partition("[STRUCTURED TABLES")
            for ln in body.splitlines():
                if any(ch.isdigit() for ch in ln):
                    lines.append((pnum, secs.get(pnum) or "", ln.strip()))
            for ln in tables.splitlines()[1:]:
                if " | " in ln and any(ch.isdigit() for ch in ln):
                    lines.append((pnum, "table", ln.strip()))
    return lines


def raw_lookup_rows(rawlines, memory, rows_ctx, tol=1.0):
    """Unified serving for SIMPLE hardcodes, same method as embedded values:
    find the remembered line NAME in raw text, prove it with the prior-year
    number adjacent, copy its left neighbour. Statuses: clean | miss."""
    by_lab = {}
    for pn, sec, ln in rawlines:
        by_lab.setdefault(norm(label_of(ln)), []).append((pn, sec, ln))
    results = {}
    for key, ctx in rows_ctx.items():
        mem = memory.get(key)
        if not mem or mem.get("kind") != "input" or not mem.get("label"):
            continue
        pv = ctx.get("prior_value")
        if not isinstance(pv, (int, float)) or pv == 0:
            continue
        founds = []
        for pn, sec, ln in by_lab.get(norm(mem["label"]), []):
            ns = line_nums(ln)
            for i in range(1, len(ns)):
                if abs(abs(ns[i]) - abs(pv)) <= tol:
                    founds.append((abs(ns[i - 1]), pn, ln))
        changed = [f for f in founds if abs(f[0] - abs(pv)) > tol]
        pick = (changed or founds or [None])[0]
        if pick is None:
            results[key] = {"status": "miss"}
            continue
        v = pick[0] * (1 if pv > 0 else -1)  # model sign convention
        results[key] = {"status": "clean", "value": v, "page": pick[1],
                        "line_label": mem["label"]}
    return results
