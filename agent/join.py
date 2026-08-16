"""Stage 2 — the deterministic joiner (the council's architecture ruling).

The inversion: the documents are read ONCE into items; CODE joins items to
model cells through hard gates; the LLM reader only fills gaps. This module
is the join, scoped tonight to where the replay ledger proved it surgical —
the STATEMENT FACES (bs/pl/cf pages), which are exactly the Model tab's
world. Driver/MD&A matrix tables wait for the enriched extraction schema
(row order + column binding); joining them positionally is the documented
left-neighbour trap.

Gates, in order (all must pass — run-115/116 laws):
  A. PRIOR IDENTITY, signed, at the row's own tolerance: the item's prior
     column must tie the model row's prior actual (item ~ +pv -> serve as
     printed; ~ -pv -> serve flipped; never force last year's sign).
  B. FACE AUTHORITY: only items from statement-caption pages join.
  C. BLOCK-SCALE RATIFICATION: a page's items are eligible only if >= 2
     distinct items on that page tie >= 2 distinct row priors — a page
     whose scale conversion is wrong ratifies nothing and joins nothing
     (the run-116 lesson: scale is a property of the block, and an
     unratified block is ineligible, never guessed).
  D. LABEL KINSHIP: required confirmation (replay round 4: without it, a
     Driver row whose prior collided with a face line's joined operating
     profit).
  E. AGREEMENT: every candidate that passes A-D must agree at the row's
     tolerance; ambiguity joins nothing.
Downstream the write chokepoint still applies its world-band guard, and
the checks/orchestrator remain the arbiter. Joined cells are conf 4 —
solid, but never locked (only checksummed reads earn the lock).
"""
from collections import defaultdict

from . import lookup, mapper
from .mapping import _overlap
from .workbook import row_tol

MAX_CANDS = 6


def _page_stmt(raw_all):
    tags, parent = {}, set()
    for pn, _sec, ln in raw_all:
        # scope discipline: 母公司 (parent-company) statements are faces too,
        # but the WRONG entity — their values enter candidate pools and the
        # agreement gate then refuses everything (coverage collapse, not
        # poison — the gate held; the tagger was the leak)
        if "母公司" in ln and ("资产负债表" in ln or "利润表" in ln or "现金流量表" in ln):
            parent.add(pn)
            continue
        if pn in tags:
            continue
        low = ln.lower()
        if "资产负债表" in ln or "balance sheet" in low:
            tags[pn] = "bs"
        elif "现金流量表" in ln or "cash flow" in low:
            tags[pn] = "cf"
        elif "利润表" in ln or "income statement" in low:
            tags[pn] = "pl"
    for pn in parent:                     # parent caption evicts the page
        tags.pop(pn, None)
    # a statement caption governs its continuation pages too (the BS spans
    # 2-3 pages and only the first carries the caption) — but propagation
    # STOPS at a parent-company page
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
    items = []
    for pn, _sec, ln in raw_all:
        if pn not in page_stmt:
            continue
        ns = lookup.line_nums(ln)
        if len(ns) < 2:
            continue
        lab = lookup.label_of(ln)
        if not lab or len(lab) < 4:
            continue
        # label hygiene: vision column markers ('| col') and other transcript
        # artifacts are not labels — one such junk label made the only wrong
        # join in offline validation (16/17)
        if "|" in lab or sum(c.isalpha() for c in lab) < 3:
            continue
        items.append((lab,
                      mapper.to_model_units(ns[0], page=pn),
                      mapper.to_model_units(ns[1], page=pn),
                      pn))
    # C. BLOCK-SCALE RATIFICATION: a page joins only if >=2 of its items tie
    # >=2 distinct census priors (already in model units — so this checks the
    # CONVERSION, not just the layout)
    priors = [r["prior_value"] for r in all_rows
              if isinstance(r.get("prior_value"), (int, float))
              and abs(r["prior_value"]) > 1]
    hits_per_page = defaultdict(set)
    for lab, cur, pri, pn in items:
        for pv in priors:
            if abs(abs(pri) - abs(pv)) <= row_tol(pv, base=0.6):
                hits_per_page[pn].add(round(pv, 2))
                break
    ratified = {pn for pn, hs in hits_per_page.items() if len(hs) >= 2}
    items = [it for it in items if it[3] in ratified]
    log.append(f"stage-2 join: {len(items)} face items on {len(ratified)} "
               f"ratified statement pages")
    served = {}
    for r in all_rows:
        pv = r.get("prior_value")
        if not isinstance(pv, (int, float)) or pv == 0:
            continue
        row_label = str(r.get("label") or "")
        hint = str(r.get("memory_hint") or "")
        if not row_label:
            continue
        tol_a = row_tol(pv, base=0.6)
        cands = []
        for lab, cur, pri, pn in items:
            if not (_overlap(row_label, lab) or (hint and _overlap(hint, lab))):
                continue
            if abs(pri - pv) <= tol_a:
                cands.append((cur, pn, lab))
            elif abs(pri + pv) <= tol_a:
                cands.append((-cur, pn, lab))
        if not cands or len(cands) > MAX_CANDS:
            continue
        vals = [v for v, _p, _l in cands]
        if max(vals) - min(vals) > row_tol(max(vals, key=abs), base=1.0):
            continue                      # E. disagreement -> join nothing
        sv, pg, lab = cands[0]
        if sv == 0:
            continue
        served[(r["sheet"], r["row"])] = {
            "value": sv, "status": "OK", "page": pg % 1000,
            "line": lab[:60], "conf": 4,
            "note": f"stage-2 join: '{lab[:40]}' prior ties "
                    f"{pv:,.2f} on ratified face p{pg % 1000} "
                    f"({len(cands)} agreeing instance(s))"}
    log.append(f"stage-2 join: {len(served)} rows joined deterministically")
    return served
