"""Direct mapping: the brain reads, the hands verify.

The side test proved a mid-tier LLM mapping a whole statement against the whole
row list beats the extract-then-match pipeline by ~10pp. This module makes that
the architecture:

1. RETRIEVE (code, free): every model row's "home pages" are found by searching
   the raw document text for the row's PRIOR-year value (the user's Ctrl+F
   method) and its label. Works identically for statements, segment notes,
   five-year tables — scattered info is not a special case.
2. CLUSTER (code): rows sharing home pages form blocks.
3. MAP (LLM, one call per block): the block's pages + the block's rows (labels,
   prior values, memory hints) in ONE context -> value/status/page per row.
   The model reads holistically, the way a person does.
4. The audit layer (tie-web, objectives, sibling-first, guards) then verifies
   every mapped value before it survives.
"""
import json
import re

from . import lookup

MAX_BLOCK_ROWS = 40
MAX_BLOCK_PAGES = 10
NEIGHBOR = 1  # pages either side of a hit are part of the home


def _num_variants(v):
    """Printed forms of a number: 1,234 / 1234 / (1,234) / 1,234.0"""
    out = set()
    for scale in (1,):
        x = abs(v * scale)
        if x == int(x):
            s = f"{int(x):,}"
            out.add(s)
            out.add(str(int(x)))
        out.add(f"{x:,.1f}")
    return out


def find_homes(rows, raw_lines):
    """rows: [{sheet,row,label,prior_value,...}] -> same rows + 'pages' (home
    candidates, best-first). Prior-value hits are the strong signal; label hits
    back them up; section repetition is the tiebreak."""
    page_text = {}
    for pn, _sec, ln in raw_lines:
        page_text.setdefault(pn, []).append(ln)
    for r in rows:
        votes = {}
        pv = r.get("prior_value")
        if isinstance(pv, (int, float)) and abs(pv) > 1:
            variants = _num_variants(pv)
            for pn, lines in page_text.items():
                for ln in lines:
                    if any(v in ln for v in variants):
                        votes[pn] = votes.get(pn, 0) + 3
                        break
        lab = lookup.norm(str(r.get("label") or ""))
        if len(lab) >= 6:
            for pn, lines in page_text.items():
                if any(lab in lookup.norm(ln) for ln in lines):
                    votes[pn] = votes.get(pn, 0) + 1
        hint = r.get("memory_page")
        if hint:
            votes[hint] = votes.get(hint, 0) + 2
        ranked = sorted(votes, key=lambda p: -votes[p])
        home = []
        for p in ranked[:4]:
            for q in range(p - NEIGHBOR, p + NEIGHBOR + 1):
                if q > 0 and q in page_text and q not in home:
                    home.append(q)
        r["pages"] = home[:MAX_BLOCK_PAGES]
    return rows


def cluster(rows):
    """Group rows into blocks that share home pages (and sheet), so each LLM
    call reads one coherent area of the document against one slab of the model."""
    blocks = []
    for r in rows:
        placed = False
        for b in blocks:
            if b["sheet"] == r["sheet"] and len(b["rows"]) < MAX_BLOCK_ROWS \
                    and (set(r["pages"]) & set(b["pages"]) or not r["pages"]):
                b["rows"].append(r)
                for p in r["pages"]:
                    if p not in b["pages"] and len(b["pages"]) < MAX_BLOCK_PAGES:
                        b["pages"].append(p)
                placed = True
                break
        if not placed:
            blocks.append({"sheet": r["sheet"], "pages": list(r["pages"]),
                           "rows": [r]})
    return blocks


def map_block(client, system, prompt_tpl, block, raw_lines, cfg):
    """One holistic call: block pages' text + row list -> per-row mapping."""
    page_set = set(block["pages"])
    text = []
    for pn, sec, ln in raw_lines:
        if pn in page_set and ln.strip():
            text.append(f"p{pn}: {ln.strip()}")
    rows_desc = []
    for r in block["rows"]:
        hint = f" [last year this row mapped to: {r['memory_hint']}]" \
            if r.get("memory_hint") else ""
        rows_desc.append(f"- id {r['sheet']}!{r['row']}: '{r['label']}' "
                         f"(prior year: {r['prior_value']}){hint}")
    user = (prompt_tpl
            .replace("{PAGES}", "\n".join(text[:600]))
            .replace("{ROWS}", "\n".join(rows_desc)))

    def _validate(o):
        errs = []
        if not isinstance(o.get("mappings"), list):
            return ["missing mappings list"]
        for m in o["mappings"]:
            if not isinstance(m, dict) or "id" not in m or "status" not in m:
                errs.append(f"bad mapping entry {str(m)[:60]}")
        return errs

    resp = client.json(system, user, _validate,
                       repair_retries=cfg["budgets"].get("json_repair_retries", 2))
    out = {}
    for m in resp.get("mappings", []):
        mm = re.match(r"^([^!]+)!(\d+)$", str(m.get("id", "")))
        if not mm:
            continue
        val = m.get("value")
        if isinstance(val, str):
            try:
                val = float(val.replace(",", ""))
            except ValueError:
                val = None
        out[(mm.group(1), int(mm.group(2)))] = {
            "value": val if isinstance(val, (int, float)) else None,
            "status": str(m.get("status", "")).upper(),
            "page": m.get("page"),
            "line": str(m.get("line", ""))[:80],
            "hint": str(m.get("hint", ""))[:80]}
    return out


def pages_for_hint(hint, raw_lines, limit=6):
    """Turn a mapper's 'where it lives' hint into candidate pages: score pages
    by hint-keyword hits in their text/section headers."""
    words = [w for w in re.findall(r"[a-z]{4,}", str(hint).lower())
             if w not in ("note", "notes", "page", "section", "statement",
                          "statements", "table")]
    if not words:
        return []
    votes = {}
    for pn, sec, ln in raw_lines:
        blob = (str(sec) + " " + ln).lower()
        hits = sum(1 for w in words if w in blob)
        if hits:
            votes[pn] = votes.get(pn, 0) + hits
    return sorted(votes, key=lambda p: -votes[p])[:limit]


def map_block_voted(client, system, prompt_tpl, block, raw_lines, cfg, votes=2):
    """Accuracy over speed: map the block N times and reconcile per row.
    Agreement -> confident. Disagreement -> the value corroborated by the raw
    text of its cited page wins; no corroboration -> UNCERTAIN with both values
    shown. Union semantics: a row any draw resolved is never dropped."""
    draws = []
    for _ in range(max(1, votes)):
        draws.append(map_block(client, system, prompt_tpl, block, raw_lines, cfg))
    raw_by_page = {}
    for pn, _s, ln in raw_lines:
        raw_by_page.setdefault(pn, []).append(ln)

    def _cited(v, page):
        try:
            pg = int(page)
        except (TypeError, ValueError):
            return False
        window = sum((raw_by_page.get(q, []) for q in (pg - 1, pg, pg + 1)), [])
        return any(any(s in ln for s in _num_variants(v)) for ln in window)

    prior_by_key = {(r["sheet"], r["row"]): r.get("prior_value")
                    for r in block["rows"]}
    out = {}
    keys = {k for d in draws for k in d}
    for k in keys:
        cands = [d[k] for d in draws if k in d and d[k].get("value") is not None]
        if not cands:
            e = next(d[k] for d in draws if k in d)
            e["conf"] = 0
            out[k] = e
            continue
        vals = [c["value"] for c in cands]
        # confidence 0-5: agreement + page-cited + prior-beside-it (the
        # "found at last year's position" signal). >=4 = solid, skippable later.
        if len(cands) >= 2 and max(vals) - min(vals) <= 1.0:
            best = max(cands, key=lambda c: c.get("status") == "OK")
            best["note"] = f"agreed across {len(cands)} independent reads"
            conf = 2
        elif len(cands) == 1:
            best = cands[0]
            conf = 1
        else:
            cited = [c for c in cands if _cited(c["value"], c.get("page"))]
            if len({round(c["value"], 1) for c in cited}) == 1:
                best = cited[0]
                best["note"] = "reads disagreed; this value verified on cited page"
                conf = 1
            else:
                best = cands[0]
                best["status"] = "UNCERTAIN"
                best["note"] = ("reads disagreed: "
                                + " vs ".join(f"{c['value']}" for c in cands[:3]))
                best["conf"] = 0
                out[k] = best
                continue
        if _cited(best["value"], best.get("page")):
            conf += 1
        pv_k = prior_by_key.get(k)
        if isinstance(pv_k, (int, float)) and abs(pv_k) > 1 \
                and _cited(pv_k, best.get("page")):
            conf += 2  # this year's value sits beside last year's — position match
        best["conf"] = min(conf, 5)
        out[k] = best
    return out


def audit(mapped, rows, raw_lines, tol=1.0):
    """Code-side cross-check of every mapped value before anything is written:
    (a) the claimed value must exist in the raw text of the cited page area;
    (b) magnitude vs prior. Failures downgrade status -> UNCERTAIN."""
    raw_by_page = {}
    for pn, _sec, ln in raw_lines:
        raw_by_page.setdefault(pn, []).append(ln)
    ctx = {(r["sheet"], r["row"]): r for r in rows}
    for key, m in mapped.items():
        v = m.get("value")
        if v is None or m.get("status") not in ("OK", "DERIVED"):
            continue
        r = ctx.get(key) or {}
        pv = r.get("prior_value")
        if isinstance(pv, (int, float)) and abs(pv) >= 100 and v != 0:
            ratio = abs(v) / abs(pv)
            if ratio > 20 or ratio < 0.05:
                # unit-scale hypothesis before giving up: thousands tables
                for scale in (1000, 0.001):
                    if 0.2 <= abs(v * scale) / abs(pv) <= 5:
                        m["value"] = v * scale
                        m["status"] = "RESCALED"
                        m["note"] = f"unit-scale corrected x{scale}"
                        break
                else:
                    m["status"] = "UNCERTAIN"
                    m["note"] = f"magnitude {ratio:.0f}x vs prior — verify"
                continue
        if m["status"] == "OK" and m.get("page"):
            try:
                pg = int(m["page"])
            except (TypeError, ValueError):
                continue
            window = []
            for q in (pg - 1, pg, pg + 1):
                window += raw_by_page.get(q, [])
            variants = _num_variants(v)
            if window and not any(any(s in ln for s in variants) for ln in window):
                m["status"] = "UNCITED"
                m["note"] = "claimed value not found on cited page — verify"
    return mapped
