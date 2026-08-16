"""Stage 2 — the deterministic joiner (the council's architecture ruling).

The inversion: the documents are read ONCE into items; CODE joins items to
model cells through hard gates; the LLM reader only fills gaps. Scoped to
the statement faces + CF-supplement/variance tables (measured 31/32 correct
on those pages — they print 本期|上年 like the faces). Measured on DFE FY25:
132 joins at 97.7% precision baseline; the run-B hardening below closes
every wrong join the three verification agents found.

Gates, in order (all must pass):
  A. PRIOR IDENTITY, signed, slot-by-tie: the pair (ns[i], ns[i+1]) whose
     SECOND element ties the row's prior serves the first (English faces
     print a note-ref column, so position-0 pairing starves; ambiguous
     multi-pair lines are refused). Small-world rows (|pv| < 100) tie at
     0.5%/a cent — base 0.6 on pv=15 accepted anything (the 税率 poison).
  B. FACE AUTHORITY: statement-caption pages only; 母公司 and 'of the
     Company' parent-entity pages evicted, and eviction blocks caption
     propagation onto them.
  C. BLOCK-SCALE RATIFICATION: a page joins only if >= 2 of its items tie
     >= 2 distinct row priors (checks the CONVERSION; run-116 law).
  D. KINSHIP, non-vacuous: label or memory-hint overlap must be POSITIVE —
     an empty content-word set confirms nothing (the vacuous-truth clause
     produced every hint-path poison measured); short CJK labels compare by
     substring after norm.
  E. AGREEMENT: all candidates must agree; ambiguity joins nothing.
  F. COMPOSITION rows (spec backout_rules) never join — one component line
     is not a composition.
  G. TWINS: when two rows tie one item, the exact-prior row wins only if
     clearly better; otherwise neither joins (合计 rows must not flatten
     onto components).
Then one SIBLING-POSITION pass: an unjoined row lying between two joined
rows binds to the sole tying item between its neighbours' items on the
same page (measured 13/13 correct). Joined cells are conf 4 — never locked.
"""
import re
from collections import defaultdict

from . import lookup, mapper
from .mapping import _STOP, norm
from .workbook import row_tol

MAX_CANDS = 6
_ENUM = re.compile(r"^\s*\d{1,2}[．、]\s*")
_EN_FACE = ("consolidated statement of financial position",
            "consolidated statement of profit or loss",
            "consolidated statement of cash flows",
            "consolidated income statement", "consolidated balance sheet")
_EN_PARENT = ("statement of financial position of the company",
              "company statement of financial position",
              "balance sheet of the company")


def _kin(a, b):
    """Non-vacuous kinship: POSITIVE evidence required. Word overlap for
    languages with spaces; normalized-substring containment for short CJK
    labels. An empty content-word set confirms nothing."""
    na, nb = norm(str(a or "")), norm(str(b or ""))
    if not na or not nb:
        return False
    wa = {w for w in na.split() if w not in _STOP and len(w) > 2}
    wb = {w for w in nb.split() if w not in _STOP and len(w) > 2}
    if wa and wb:
        return bool(wa & wb)
    sa, sb = na.replace(" ", ""), nb.replace(" ", "")
    if len(sa) < 2 or len(sb) < 2:
        return False
    return sa in sb or sb in sa


def _page_stmt(raw_all):
    tags, parent = {}, set()
    for pn, _sec, ln in raw_all:
        low = ln.lower()
        if ("母公司" in ln and ("资产负债表" in ln or "利润表" in ln or "现金流量表" in ln)) \
                or any(p in low for p in _EN_PARENT):
            parent.add(pn)
            continue
        if pn in tags:
            continue
        if "资产负债表" in ln or "balance sheet" in low \
                or "financial position" in low:
            tags[pn] = "bs"
        elif "现金流量表" in ln or "cash flow" in low:
            tags[pn] = "cf"
        elif "利润表" in ln or "income statement" in low or "profit or loss" in low:
            tags[pn] = "pl"
    for pn in parent:
        tags.pop(pn, None)
    # caption governs continuation pages, but propagation STOPS at parent pages
    out = {pn: t for pn, t in tags.items() if pn not in parent}
    for pn in list(tags):
        for k in (1, 2, 3):
            if pn + k in parent:
                break
            out.setdefault(pn + k, tags[pn])
    return out


def stage2_join(all_rows, raw_all, spec, target_year, log):
    """-> {(sheet,row): mapped-entry} for rows the face items decide
    unambiguously. Pure code — no LLM call anywhere."""
    page_stmt = _page_stmt(raw_all)
    # F. composition rows never join
    backout = set()
    for br in (spec.get("backout_rules") or []):
        m = re.match(r"^\s*'?([^'!]+)'?!\D*(\d+)", str(br.get("row") or br.get("cell") or ""))
        if m:
            backout.add((m.group(1), int(m.group(2))))
    items = []   # (label, [nums in model units], page, order-index)
    for idx, (pn, _sec, ln) in enumerate(raw_all):
        if pn not in page_stmt:
            continue
        ln = _ENUM.sub("", ln)   # '2．少数股东损益 ...' — enumerator is not a value
        ns = [mapper.to_model_units(n, page=pn) for n in lookup.line_nums(ln)]
        if len(ns) < 2:
            continue
        lab = lookup.label_of(ln)
        if not lab or len(lab) < 4:
            continue
        if "|" in lab or sum(c.isalpha() for c in lab) < 3:
            continue     # transcript artifacts are not labels
        items.append((lab, ns, pn, idx))
    # C. block-scale ratification
    priors = [r["prior_value"] for r in all_rows
              if isinstance(r.get("prior_value"), (int, float))
              and abs(r["prior_value"]) > 1]
    hits_per_page = defaultdict(set)
    for lab, ns, pn, _i in items:
        for pv in priors:
            if any(abs(abs(n) - abs(pv)) <= row_tol(pv, base=0.6) for n in ns[1:]):
                hits_per_page[pn].add(round(pv, 2))
                break
    ratified = {pn for pn, hs in hits_per_page.items() if len(hs) >= 2}
    items = [it for it in items if it[2] in ratified]
    log.append(f"stage-2 join: {len(items)} face items on {len(ratified)} "
               f"ratified statement pages")

    def _pairs(ns, pv, tol):
        """Slot-by-tie: adjacent pairs whose SECOND element ties pv (signed).
        Returns list of (served_value, matched_i). Refuses multi-pair lines
        that disagree."""
        out = []
        for i in range(len(ns) - 1):
            if abs(ns[i + 1] - pv) <= tol:
                out.append((ns[i], i))
            elif abs(ns[i + 1] + pv) <= tol:
                out.append((-ns[i], i))
        return out

    served, prov = {}, {}
    twins = defaultdict(list)     # item identity -> rows that tied it
    for r in all_rows:
        pv = r.get("prior_value")
        if not isinstance(pv, (int, float)) or pv == 0:
            continue
        if (r["sheet"], r["row"]) in backout:
            continue
        row_label = str(r.get("label") or "")
        hint = str(r.get("memory_hint") or "")
        # A. small-world rows tie in their own world (the 税率 lesson)
        tol_a = row_tol(pv, base=0.6 if abs(pv) >= 100 else 0.01)
        cands = []
        for lab, ns, pn, idx in items:
            if not (_kin(row_label, lab) or (hint and _kin(hint, lab))):
                continue
            prs = _pairs(ns, pv, tol_a)
            if len(prs) != 1:
                continue          # no tie, or ambiguous line — refuse
            sv = prs[0][0]
            # elimination/reallocation lines print exact negations — the
            # direction is unknowable from one line
            if any(abs(a + b) < tol_a and a != 0
                   for a, b in zip(ns, ns[1:])):
                continue
            cands.append((sv, pn, lab, idx))
        if not cands or len(cands) > MAX_CANDS:
            continue
        vals = [v for v, _p, _l, _i in cands]
        if max(vals) - min(vals) > row_tol(max(vals, key=abs), base=1.0):
            continue              # E. disagreement -> join nothing
        sv, pg, lab, idx = cands[0]
        if sv == 0:
            continue
        key = (r["sheet"], r["row"])
        served[key] = {
            "value": sv, "status": "OK", "page": pg,
            "line": lab[:60], "conf": 4,
            "note": f"stage-2 join: '{lab[:40]}' prior ties "
                    f"{pv:,.2f} on ratified face p{pg % 1000} "
                    f"({len(cands)} agreeing instance(s))"}
        prov[key] = (pg, idx, pv)
        twins[(pg, lab, round(sv, 2))].append((key, abs(pv)))
    # G. twins: two rows tying ONE item cannot both be that line (合计 rows
    # must not flatten onto components) — conservative: neither joins;
    # the reader or the orchestrator decides those rows instead
    for _it, rows_t in twins.items():
        if len(rows_t) < 2:
            continue
        for k, _ in rows_t:
            served.pop(k, None)
            prov.pop(k, None)
    n_main = len(served)
    # SIBLING-POSITION pass (measured 13/13): an unjoined row between two
    # joined neighbours binds to the SOLE tying item between their items.
    by_sheet = defaultdict(list)
    for (sh, rw) in sorted(prov):
        by_sheet[sh].append(rw)
    items_by_page = defaultdict(list)
    for lab, ns, pn, idx in items:
        items_by_page[pn].append((idx, lab, ns))
    rows_ctx = {(r["sheet"], r["row"]): r for r in all_rows}
    for sh, rws in by_sheet.items():
        for a, b in zip(rws, rws[1:]):
            if b - a < 2:
                continue
            pg_a, ix_a, _ = prov[(sh, a)]
            pg_b, ix_b, _ = prov[(sh, b)]
            if pg_a != pg_b or ix_b <= ix_a:
                continue
            for mid in range(a + 1, b):
                key = (sh, mid)
                r = rows_ctx.get(key)
                if key in served or r is None or key in backout:
                    continue
                pv = r.get("prior_value")
                if not isinstance(pv, (int, float)) or pv == 0:
                    continue
                tol_m = row_tol(pv, base=0.6 if abs(pv) >= 100 else 0.01)
                hits = []
                for idx, lab, ns in items_by_page[pg_a]:
                    if not (ix_a < idx < ix_b):
                        continue
                    prs = _pairs(ns, pv, tol_m)
                    if len(prs) == 1:
                        hits.append((prs[0][0], lab))
                if len(hits) == 1 and hits[0][0] != 0:
                    sv, lab = hits[0]
                    served[key] = {
                        "value": sv, "status": "OK", "page": pg_a,
                        "line": lab[:60], "conf": 4,
                        "note": f"stage-2 join (sibling-position): '{lab[:36]}' "
                                f"between joined neighbours, prior ties "
                                f"{pv:,.2f} p{pg_a % 1000}"}
    log.append(f"stage-2 join: {n_main} rows joined deterministically, "
               f"+{len(served) - n_main} by sibling position")
    return served
