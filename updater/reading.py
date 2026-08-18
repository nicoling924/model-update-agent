"""THE ONE READING STAGE — extraction-first (council ruling, 2026-08-18).

The patch spiral's root: the agent mapped against an evidence pool with
holes, and every hole became a bolt-on channel. The council's cut, owner-
approved: the run's FIRST product is one complete, verified reading of
the filing, with completeness PROVEN — and mapping only ever works
against that world. The old channels survive as internal repair tactics
of this stage, not as independent products.

Four phases (bounded clock):

A. MANIFEST + ENTITY — deterministic. CN filings print consolidated and
   parent-company statements side by side; a parent page in the pool
   poisons the join and the oracle (run-24: police cited a parent-CF
   page as "print"). Two language-free classifiers:
   - banner scan: a page whose lines carry a 母公司-statement banner and
     no 合并 banner is parent;
   - anchor arbitration: among same-kind face blocks, the model's own
     priors tie the CONSOLIDATED block at identity grade — the block
     with anchors is the spine, twins without anchors are parent.
   Parent pages lose face authority and their items leave the pool.

B. SPINE — the consolidated statements read whole and PROVEN:
   verified page reads (cache replay offline, live calls on CI), then
   section closure, then the ARTICULATION GATE: the balance sheet
   balances from the extraction's own numbers, and CF ending cash ties
   BS cash. Pages whose sections stay unresolved get a bounded live
   REPAIR re-read with the failing equation in the prompt ("the section
   above X must sum to Y — transcribe every row"). Articulation proves
   the extracted columns belong to the same reality — an internally
   closed table can still be the wrong entity or a swapped year.

C. DEMAND-DRIVEN NOTES — pages selected by what the MODEL still needs
   (open-row priors not yet located), never by page count.

D. SUFFICIENCY + FREEZE — the inventory: every open-row prior located
   (page recorded) or listed unlocated with the searched trail. The
   report rides to _REPORT; nothing downstream may claim the document
   lacks a figure the inventory locates.
"""
import re

from .closure import _sections, _solve, closure_sweep
from .ingest import MAX_PAGES, _select_pages, read_pages
from .ledger import JOIN_FACES
from .numerics import SCALES, to_model_units

PARENT_RE = re.compile(r"母公司[^，。]{0,12}(资产负债表|利润表|现金流量表|"
                       r"所有者权益变动表|财务报表[^，。]{0,6}注释)")
CONS_RE = re.compile(r"合并[^，。]{0,8}(资产负债表|利润表|现金流量表|"
                     r"所有者权益变动表|财务报表[^，。]{0,6}注释)")
REPAIR_CAP = 6


def _page_lines(ledger, doc, page):
    return [it.source_line or "" for it in ledger.items
            if it.doc == doc and it.page == page]


def _anchor_count(ledger, doc, page, priors):
    n = 0
    for it in ledger.items:
        if it.doc != doc or it.page != page:
            continue
        for pv in priors:
            tol = max(0.6, abs(pv) * 5e-4)
            if any(abs(abs(to_model_units(v, s)) - abs(pv)) <= tol
                   for v in it.nums for s in SCALES):
                n += 1
                break
    return n


def entity_quarantine(ledger, targets, log):
    """Phase A: strip face authority from parent-entity pages and drop
    their items from the pool (disputed). Deterministic; caption
    eviction from stage 1 stays senior — this adds the bannerless
    continuation pages and the parent NOTES range."""
    prior_docs = ledger.prior_period_docs()
    priors = [t.prior_value for t in targets
              if isinstance(t.prior_value, (int, float))
              and abs(t.prior_value) > 100]
    quarantined = []
    for doc in {d for (d, _p) in ledger.faces}:
        if doc in prior_docs:
            continue
        pages = sorted(p for (d, p) in ledger.faces if d == doc)
        for page in pages:
            lines = " ".join(_page_lines(ledger, doc, page))
            is_parent = bool(PARENT_RE.search(lines)) \
                and not CONS_RE.search(lines)
            if not is_parent and ledger.faces.get((doc, page)):
                # anchor arbitration: a face page tying NO model prior,
                # while some same-kind face page ties several, is the
                # parent twin (or junk) — spine pages anchor hard. A
                # CONTINUATION page (the EPS tail of an income statement
                # holds only small numbers) is spared: parent twins sit
                # pages away, continuations sit adjacent to an anchored
                # sibling.
                mine = _anchor_count(ledger, doc, page, priors)
                if mine == 0:
                    kind = ledger.faces[(doc, page)]
                    anchored = [p2 for p2 in pages
                                if ledger.faces.get((doc, p2)) == kind
                                and p2 != page
                                and _anchor_count(ledger, doc, p2,
                                                  priors) >= 3]
                    is_parent = bool(anchored) and min(
                        abs(page - p2) for p2 in anchored) > 2
            if is_parent:
                ledger.faces.pop((doc, page), None)
                ledger.parent_pages |= {(doc, page)}
                for it in ledger.items:
                    if it.doc == doc and it.page == page:
                        it.disputed = True
                quarantined.append(page)
        if quarantined:
            log(f"[reading] entity quarantine: {len(quarantined)} "
                f"parent/anchorless face pages evicted "
                f"({', '.join('p' + str(p) for p in quarantined[:8])})")
    try:
        ledger._oracle_cache = None
    except Exception:
        pass
    return quarantined


def _spine_health(ledger):
    """Per face page: sections closed / gap-derived / unresolved."""
    prior_docs = ledger.prior_period_docs()
    health = {}
    for (doc, page), face in sorted(ledger.faces.items()):
        if doc in prior_docs or face not in JOIN_FACES:
            continue
        groups = {}
        for it in ledger.items:
            if (it.doc != doc or it.page != page or it.table_id is None
                    or getattr(it, "channel", "") in ("closure",
                                                      "closure-gap")):
                continue
            groups.setdefault(it.table_id, []).append(it)
        closed = gapped = unresolved = 0
        bad = []
        for _tid, rows in groups.items():
            rows.sort(key=lambda x: x.row_ord)
            for s_row, sec in _sections(rows):
                solved, _ones = _solve(s_row, sec)
                if solved is None:
                    unresolved += 1
                    bad.append((s_row.label[:24],
                                s_row.nums[0] if s_row.nums else None,
                                s_row.nums[1] if len(s_row.nums) > 1
                                else None))
                elif solved[0] == "closed":
                    closed += 1
                else:
                    gapped += 1
        health[(doc, page)] = {"face": face, "closed": closed,
                               "gapped": gapped, "unresolved": unresolved,
                               "bad": bad}
    return health


def _locate(ledger, pv, prior_docs):
    """First current-doc page printing this prior at identity grade."""
    tol = max(0.6, abs(pv) * 5e-4)
    for it in ledger.items:
        if it.doc in prior_docs or getattr(it, "disputed", False):
            continue
        if any(abs(abs(to_model_units(v, s)) - abs(pv)) <= tol
               for v in it.nums for s in SCALES):
            return it.page
    return None


def _articulation(ledger, targets, spec_key_rows):
    """The spine gate, from the extraction's own numbers: locate each
    balance-family key's prior; articulate CA+NCA = CL+NCL+equity and
    CF-end-cash = BS-cash on the CURRENT values the oracle serves."""
    from .stage2_join import unique_evidence_value
    tl = list(targets)
    tmap = {t.key: t for t in tl}
    vals = {}
    for k in spec_key_rows or []:
        name = str(k.get("name", "")).lower()
        t = tmap.get((k["sheet"], int(k["row"])))
        if t is None:
            continue
        got = unique_evidence_value(ledger, tl, t)
        if got is not None and name not in vals:
            vals[name] = got[0]
    checks = {}
    need = ("total current assets", "total non-current assets",
            "total current liabilities", "total non-current liabilities",
            "total equity")
    if all(n in vals for n in need):
        lhs = vals[need[0]] + vals[need[1]]
        rhs = vals[need[2]] + vals[need[3]] + vals[need[4]]
        checks["bs_articulates"] = abs(lhs - rhs) <= max(1.0, lhs * 1e-5)
    cash = next((vals[n] for n in vals if "cash" in n and "flow" not in n),
                None)
    end = next((vals[n] for n in vals if "year end" in n or "ending" in n),
               None)
    if cash is not None and end is not None:
        checks["cash_ties"] = abs(abs(cash) - abs(end)) <= 1.0
    return checks, vals


def read_complete(ledger, targets, client, docs, spec_d, log):
    """The one reading stage. Returns the sufficiency report."""
    prior_docs = ledger.prior_period_docs()

    # A. manifest + entity
    entity_quarantine(ledger, targets, log)

    # B. spine: read the faces whole, close, repair, articulate
    faces = [(d, p) for (d, p), f in sorted(ledger.faces.items())
             if f in JOIN_FACES and d not in prior_docs]
    read_pages(ledger, targets, client, log, faces)
    closure_sweep(ledger, log)
    health = _spine_health(ledger)
    repairs = 0
    for (doc, page), h in sorted(health.items()):
        if not h["unresolved"] or repairs >= REPAIR_CAP or client is None:
            continue
        demand = "; ".join(
            f"the section above '{lab}' must sum to {sc:,.2f} (current) "
            f"and {sp:,.2f} (prior) — transcribe EVERY row of it"
            for lab, sc, sp in h["bad"][:3] if sc is not None)
        if not demand:
            continue
        read_pages(ledger, targets, client, log, [(doc, page)],
                   extra_prompt=("REPAIR DEMAND — this page failed its "
                                 "own arithmetic: " + demand),
                   fresh=True)
        repairs += 1
    if repairs:
        closure_sweep(ledger, log)
        health = _spine_health(ledger)
    n_unres = sum(h["unresolved"] for h in health.values())
    checks, key_vals = _articulation(ledger, targets,
                                     spec_d.get("key_rows"))
    log(f"[reading] spine: {len(faces)} face pages, "
        f"{sum(h['closed'] for h in health.values())} sections closed, "
        f"{sum(h['gapped'] for h in health.values())} gap-derived, "
        f"{n_unres} unresolved after {repairs} repairs; "
        f"articulation: " + (", ".join(
            f"{k}={'OK' if v else 'FAIL'}" for k, v in checks.items())
            or "insufficient keys located"))

    # C. demand-driven notes: pages ranked by still-unlocated priors
    unlocated = [t for t in targets
                 if isinstance(t.prior_value, (int, float))
                 and abs(t.prior_value) >= 1.0
                 and _locate(ledger, t.prior_value, prior_docs) is None]
    if unlocated:
        pages = [pg for pg in _select_pages(
                     ledger, [t.prior_value for t in unlocated],
                     cap=MAX_PAGES)
                 if pg not in faces and pg not in ledger.parent_pages]
        n_p, n_r = read_pages(ledger, targets, client, log, pages)
        closure_sweep(ledger, log)
        log(f"[reading] demand notes: {n_p} pages read for "
            f"{len(unlocated)} unlocated priors, {n_r} verified rows")

    # D. sufficiency inventory + freeze
    located = inventory = 0
    gaps = []
    for t in targets:
        pv = t.prior_value
        if not isinstance(pv, (int, float)) or abs(pv) < 1.0:
            continue
        inventory += 1
        pg = _locate(ledger, pv, prior_docs)
        if pg is not None:
            located += 1
        else:
            gaps.append(f"{t.sheet}!{t.row} '{str(t.label)[:24]}' "
                        f"(prior {pv:,.2f})")
    try:
        ledger._oracle_cache = None
    except Exception:
        pass
    report = {"spine": {k[1]: v for k, v in health.items()},
              "articulation": checks, "key_values": key_vals,
              "located": located, "inventory": inventory,
              "unlocated": gaps, "repairs": repairs}
    log(f"[reading] sufficiency: {located}/{inventory} open-row priors "
        f"located in the filing; {len(gaps)} unlocated (listed in "
        f"_REPORT)")
    return report
