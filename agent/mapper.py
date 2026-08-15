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


# -- document unit scale ----------------------------------------------------
# The model's units and the filing's units need not agree: a Chinese annual
# report prints yuan (69,695,135,723.47) where the model holds millions
# (69,695.14). Retrieval-by-prior-value then finds NOTHING, and every
# arithmetic proof fails — not because the number is absent but because it is
# printed 1,000,000x larger. The scale is a property of the DOCUMENT, decided
# once per run by reconciliation (below), never guessed per number.
DOC_SCALES = (1, 1e3, 1e4, 1e6, 1e8)  # units, thousands, 万, millions, 亿
DOC_SCALE = 1.0
PAGE_SCALES = {}  # page -> scale, where a PAGE reconciles at its own scale


def set_doc_scale(scale):
    global DOC_SCALE
    DOC_SCALE = float(scale or 1.0)
    PAGE_SCALES.clear()
    return DOC_SCALE


def detect_page_scales(values, raw_lines, min_hits=3):
    """Scale is a property of the PAGE, defaulting to the document's.

    The statements print yuan (doc scale 1e6 to a millions model), but MD&A
    tables print 万元 (1e4) — the product-segment splits the model's Driver
    page needs live THERE and were invisible to every value test (run 100:
    the whole class wrong). A page earns its own scale only by reconciling
    >= min_hits known model values at it; everything else inherits DOC_SCALE.
    """
    vals = sorted({abs(v) for v in values
                   if isinstance(v, (int, float)) and abs(v) > 100}, reverse=True)[:80]
    if not vals:
        return {}
    by_page = {}
    for pn, _sec, ln in raw_lines:
        by_page.setdefault(pn, []).extend(abs(n) for n in lookup.line_nums(ln))
    out = {}
    for pn, nums in by_page.items():
        nums.sort()
        best, best_n = None, 0
        for s in DOC_SCALES:
            n = sum(1 for v in vals if _has_num(nums, v, s))
            if n > best_n:
                best, best_n = s, n
        if best is not None and best != DOC_SCALE and best_n >= min_hits:
            # only a DIFFERENT scale is worth recording, and only if the page
            # ALSO fails to reconcile at the document scale (mixed pages keep
            # the doc default rather than flipping wholesale)
            doc_n = sum(1 for v in vals if _has_num(nums, v, DOC_SCALE))
            if best_n > doc_n:
                out[pn] = float(best)
    PAGE_SCALES.update(out)
    return out


def page_scale(page):
    if page is None:
        return DOC_SCALE
    return PAGE_SCALES.get(page, DOC_SCALE)


def detect_scale(values, raw_lines, sample=60):
    """How many document units to one model unit — decided by RECONCILIATION.

    For each candidate scale, count how many of the model's known prior-year
    values actually appear in the document's printed numbers at that scale.
    The scale that explains the most values wins; ties go to 1 (unchanged
    behaviour), so a same-units filing never takes the scaled path.
    """
    vals = sorted({abs(v) for v in values
                   if isinstance(v, (int, float)) and abs(v) > 100}, reverse=True)[:sample]
    if not vals:
        return 1.0
    nums = []
    for _pn, _sec, ln in raw_lines:
        nums.extend(abs(n) for n in lookup.line_nums(ln))
    nums.sort()
    best, best_n = 1.0, -1
    for s in DOC_SCALES:
        n = sum(1 for v in vals if _has_num(nums, v, s))
        if n > best_n:
            best, best_n = float(s), n
    return best


def _has_num(sorted_nums, v, scale):
    """Is v (model units) present among these printed numbers at `scale`?"""
    import bisect
    target = abs(v) * scale
    tol = max(0.6 * scale, target * 5e-4)
    i = bisect.bisect_left(sorted_nums, target - tol)
    return i < len(sorted_nums) and sorted_nums[i] <= target + tol


def to_model_units(n, page=None):
    """A printed number in the MODEL's units. At scale 1 this is identity.

    At other scales, only page-scale financial values convert: CN statements
    print yuan with cents, so any real aggregate is >= S/1000, while per-share
    figures, ratios and FX rates print small and stay as-is — the model holds
    those in their printed units too (EPS 0.62 is 0.62 in both worlds).
    The scale is the PAGE's where one is proven, else the document's.
    """
    s = page_scale(page)
    if not isinstance(n, (int, float)) or s == 1:
        return n
    return n / s if abs(n) >= s / 1000 else n


def num_matches(nums, v, scale=None, page=None):
    """Does any of these parsed numbers equal v (model units) at the scale?"""
    s = page_scale(page) if scale is None else scale
    target = abs(v) * s
    tol = max(0.6 * s, target * 5e-4)
    return any(abs(abs(n) - target) <= tol for n in nums)


def line_has_value(line, v, scale=None, page=None):
    """Does this printed line carry v (model units)?

    At scale 1 this is the original printed-form string test, kept exactly so
    same-units models behave as before. At any other scale the printed digits
    cannot match (the model's value is rounded at its own precision), so the
    test becomes numeric with a scale-proportional tolerance.
    """
    s = page_scale(page) if scale is None else scale
    if not isinstance(v, (int, float)):
        return False
    if s == 1:
        return any(t in line for t in _num_variants(v))
    return num_matches(lookup.line_nums(line), v, s)


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
            for pn, lines in page_text.items():
                for ln in lines:
                    if line_has_value(ln, pv, page=pn):
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
        for cl in (r.get("candidate_lines") or [])[:4]:
            rows_desc.append(f"    prior-year value found here: {cl}")
    user = (prompt_tpl
            .replace("{PAGES}", "\n".join(text[:600]))
            .replace("{ROWS}", "\n".join(rows_desc)))
    if DOC_SCALE != 1 or PAGE_SCALES:
        user = ("UNITS: these pages MIX unit scales — statements in full units "
                "(元), MD&A tables in 万元 or 千元, volume tables in raw units. "
                "The MODEL's units are whatever each row's prior-year value "
                "uses: convert every figure you read into the same units as "
                "that row's prior before returning it, and sanity-check the "
                "magnitude against that prior.\n\n") + user

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
        return any(line_has_value(ln, v, page=q)
                   for q in (pg - 1, pg, pg + 1)
                   for ln in raw_by_page.get(q, []))

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
        # DOCUMENT UNITS: the reader quotes the page, so on a filing printed in
        # other units it hands back a document-unit number. Convert it to the
        # model's units whenever the prior year says that is what happened —
        # this fires at every magnitude, including priors too small for the
        # ratio guard below.
        if (DOC_SCALE != 1 and v not in (None, 0)
                and isinstance(pv, (int, float)) and abs(pv) > 0):
            if 0.2 * DOC_SCALE <= abs(v) / abs(pv) <= 5 * DOC_SCALE:
                v = m["value"] = v / DOC_SCALE
                m["note"] = ((m.get("note") or "") +
                             f" [document units /{DOC_SCALE:,.0f} -> model units]").strip()
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
            try:  # "p46" and 46 both mean page 46
                pg = int(re.sub(r"[^0-9]", "", str(m["page"])) or "x")
            except ValueError:
                continue
            window = []
            for q in (pg - 1, pg, pg + 1):
                window += raw_by_page.get(q, [])
            if window and not any(line_has_value(ln, v, page=q)
                                  for q in (pg - 1, pg, pg + 1)
                                  for ln in raw_by_page.get(q, [])):
                m["status"] = "UNCITED"
                m["note"] = "claimed value not found on cited page — verify"
    return mapped
