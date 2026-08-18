"""Stage 2 — JOIN: pure code binds ledger evidence to model rows.

The inversion's core: no model row is written because a mechanism thinks a
number is plausible. A row is served only because a specific ledger item,
on a ratified statement-face page, tied the row's own prior-year actual
under every hard gate below. No LLM is imported anywhere in this module —
if code cannot prove the bind, the row falls through to Stage 3's
checksummed reader, and an empty row is a legal state.

The gates, in order (all must pass; the legacy prototype measured 130/130
against the DFE filing under these rules):

  BACKOUT EXCLUSION  spec-declared composition rows never join — one
                     component line is not a composition.
  FACE AUTHORITY     candidates live on pl/bs/cf statement-caption pages
                     only; 母公司 / company-only pages were evicted at
                     ledger build and eviction blocks caption propagation.
  BLOCK-SCALE        a page serves only at a scale RATIFIED by >= 2 of its
  RATIFICATION       items tying >= 2 distinct model priors (run-116 law:
                     the checksum was secretly the scale anchor — here the
                     anchor is explicit, and scale is a block property,
                     never one number's magnitude). Hinted scales are tried
                     first; ambiguity ratifies nothing.
  PRIOR IDENTITY     signed, slot-by-tie: the adjacent pair (ns[i], ns[i+1])
                     whose SECOND element ties the row's prior serves the
                     first (faces print note-ref columns, so fixed-position
                     pairing starves). Tolerance is the ROW'S OWN WORLD
                     (run-112 law): aggregates 0.6 absolute, small-world
                     rows (|pv| < 100) 0.5% / a cent — base 0.6 on pv=15
                     accepted anything (the 税率 poison). Multi-pair lines
                     and elimination lines (adjacent exact negations —
                     direction unknowable from one line) are refused.
  KINSHIP            non-vacuous: label or memory-hint overlap must be
                     POSITIVE evidence; an empty content-word set confirms
                     nothing. Kinship corroborates — it never creates a
                     match on its own.
  AGREEMENT          all surviving candidates must agree within the world
                     tolerance; ambiguity joins NOTHING (no scoring
                     contest, no best-effort pick).
  TWINS              two model rows tying ONE item cannot both be that
                     line (合计 totals must not flatten onto components):
                     conservative — neither joins.

Then ONE sibling-position pass (measured 13/13): an unjoined row lying
between two joined rows binds to the sole tying item positioned between
its neighbours' items on the same page.

Joined cells are conf 4 — never locked; Stage 4's verification web still
owns acceptance.
"""
import bisect
from collections import defaultdict
from dataclasses import dataclass, asdict, field

from .numerics import (CJK_STRUCTURAL, STOPWORDS, norm_label, row_tol,
                       to_model_units, SCALES)


def _words(norm):
    return {w for w in norm.split() if w not in STOPWORDS and len(w) > 2}


def _kin_pre(norm):
    """Precomputed kinship key for one label: (norm, words, squashed)."""
    return (norm, _words(norm), norm.replace(" ", ""))


def _kin_fast(a, b):
    """kinship() over precomputed keys — identical semantics, no regex."""
    na, wa, sa = a
    nb, wb, sb = b
    if not na or not nb:
        return False
    if wa and wb:
        return bool(wa & wb)
    if len(sa) < 2 or len(sb) < 2:
        return False
    if sa in CJK_STRUCTURAL or sb in CJK_STRUCTURAL:
        return False
    return sa in sb or sb in sa

MAX_CANDS = 6          # more agreeing printings than this is noise, not proof
RATIFY_MIN_PRIORS = 2  # distinct model priors a page must tie to ratify a scale
CONF_JOINED = 4


@dataclass
class JoinDecision:
    sheet: str
    row: int
    status: str                 # accepted | accepted_sibling | ambiguous | twin_dropped | excluded_backout
    value: float = None         # model units (accepted only)
    item_id: str = ""
    doc: str = ""
    page: int = None
    scale: float = None
    note: str = ""
    gates: list = field(default_factory=list)


def ratify_page_scales(items, priors, log=None):
    """{(doc, page): scale} for pages whose scale is PROVEN.

    A page ratifies at scale s when >= RATIFY_MIN_PRIORS distinct model
    priors are tied by >= as many distinct items (each item vouches for at
    most ONE prior), through numbers that actually CONVERT at s. Only
    aggregate-world priors (|pv| > 100) may ratify: small values (EPS,
    rates) pass through to_model_units unchanged, tie at EVERY scale, and
    therefore prove nothing about the scale — scale is a property proven
    by aggregates. Hinted scales (printed unit headers, vision checksum
    locks) are tried first and win outright when they ratify. Otherwise
    every legal scale competes; the best hit-count wins, and a TIE between
    different scales ratifies nothing — an ambiguous scale is an unproven
    scale.
    """
    priors = [pv for pv in priors
              if isinstance(pv, (int, float)) and abs(pv) > 100]
    sorted_priors = sorted({abs(pv) for pv in priors})
    by_page = defaultdict(list)
    for it in items:
        by_page[(it.doc, it.page)].append(it)
    out = {}
    for key, page_items in by_page.items():
        hints = []
        for it in page_items:
            if it.scale_hint and it.scale_hint not in hints:
                hints.append(it.scale_hint)

        def hits_at(s):
            # A tie ratifies scale s only through a number that actually
            # CONVERTED at s (small pass-through values tie at every scale
            # and prove nothing), and each item vouches for at most ONE
            # prior — >= 2 distinct priors therefore means >= 2 distinct
            # corroborating lines, never one line counted twice.
            # Sorted priors + bisect: the page x prior cross-product was a
            # measured multi-minute hang on a 600-row model.
            tied = set()
            for it in page_items:
                hit = None
                for n in it.nums[1:]:
                    if s > 1 and abs(n) < s / 1000:
                        continue
                    a = abs(to_model_units(n, s))
                    i = bisect.bisect_left(sorted_priors, a * 0.99)
                    while i < len(sorted_priors) and sorted_priors[i] <= a * 1.01 + 1.0:
                        pv = sorted_priors[i]
                        if abs(a - pv) <= row_tol(pv, base=0.6):
                            hit = round(pv, 2)
                            break
                        i += 1
                    if hit is not None:
                        break
                if hit is not None:
                    tied.add(hit)
            return tied

        chosen = None
        for s in hints:
            if len(hits_at(s)) >= RATIFY_MIN_PRIORS:
                chosen = s
                break
        if chosen is None:
            scored = sorted(((len(hits_at(s)), s) for s in SCALES), reverse=True)
            best_n, best_s = scored[0]
            if best_n >= RATIFY_MIN_PRIORS and best_n != scored[1][0]:
                chosen = best_s
        if chosen is not None:
            out[key] = chosen
    if log is not None:
        log.append(f"stage-2: {len(out)}/{len(by_page)} face pages ratified "
                   f"a block scale")
    return out


def _tying_pairs(ns, pv, tol):
    """Signed slot-by-tie: [(served_value, index)] for adjacent pairs whose
    SECOND element ties ±pv. The sign of the tie propagates to the served
    value (a row the face prints negated serves negated)."""
    out = []
    for i in range(len(ns) - 1):
        if abs(ns[i + 1] - pv) <= tol:
            out.append((ns[i], i))
        elif abs(ns[i + 1] + pv) <= tol:
            out.append((-ns[i], i))
    return out


def _is_elimination_line(ns, tol):
    """Elimination/reallocation lines print exact adjacent negations — the
    direction is unknowable from one line, so the line proves nothing."""
    return any(abs(a + b) <= tol and a != 0 for a, b in zip(ns, ns[1:]))


def _world_tol(pv):
    """The row's own world (run-112 law): small-world rows (|pv| < 100) tie
    at 0.5% / a cent; aggregates absorb statement rounding at 0.6."""
    return row_tol(pv, base=0.6 if abs(pv) >= 100 else 0.01)


def _proven_zero(sv, it):
    """The absence-as-evidence exception (run-24 twin): a served value of
    ZERO is legal ONLY from a closure item — the section subtotal proved
    the printed number belongs entirely to the comparative column, so the
    current-year line is absent and its value is zero. Everything else
    keeps the zero-refusal (a zero from any other channel is a non-read)."""
    return sv == 0 and getattr(it, "channel", "") == "closure"


def _in_world(sv, pv):
    """The world-band law AT JOIN TIME (the CLP dividend poison): a line can
    print a per-share figure adjacent to the total ('Fourth interim dividend
    declared 1.26 ... 3,183'), so slot-by-tie can pair (per-share, prior-
    total) and serve the per-share number into a totals row with every gate
    passing. A served value that leaves the prior's order of magnitude is
    not a join — it is Stage 3's row now."""
    return abs(sv) <= 100 * abs(pv) and abs(sv) * 100 >= abs(pv)


def join(ledger, targets, log=None):
    """-> (served, decisions).

    served: {(sheet, row): {value, status, doc, page, line, conf, note}} in
    the shape the write layer consumes. decisions: JoinDecision provenance
    for every row the joiner touched (the replay diff runs on these).
    Pure code — no LLM call anywhere, no workbook access, no writes.
    """
    log = log if log is not None else []
    priors = [t.prior_value for t in targets
              if isinstance(t.prior_value, (int, float))]
    deep = [t.prior2_value for t in targets
            if isinstance(t.prior2_value, (int, float))]
    periods = ledger.classify_doc_periods(priors, deep)
    log.append("stage-2: doc periods " + ", ".join(
        f"{d}={k}" for d, k in sorted(periods.items())))
    pool = ledger.join_pool()
    page_scales = ratify_page_scales(pool, priors, log)
    pool = [it for it in pool if (it.doc, it.page) in page_scales]
    log.append(f"stage-2: {len(pool)} face items on {len(page_scales)} "
               f"ratified pages")
    # precompute per item: converted numbers (scale is fixed per page) and
    # kinship keys — the target x pool loop must not re-derive them
    pool_pre = []
    for it in pool:
        s = page_scales[(it.doc, it.page)]
        ns = [to_model_units(n, s) for n in it.nums]
        pool_pre.append((it, s, ns, _kin_pre(norm_label(it.label))))

    decisions = []
    served, prov = {}, {}
    twins = defaultdict(list)
    for t in targets:
        pv = t.prior_value
        if not isinstance(pv, (int, float)) or pv == 0:
            continue                       # no identity key -> Stage 3
        if t.is_backout:
            decisions.append(JoinDecision(
                t.sheet, t.row, "excluded_backout",
                note="composition row: spec backout rule serves it, never a join"))
            continue
        tol = _world_tol(pv)
        k_label = _kin_pre(norm_label(t.label))
        k_hint = _kin_pre(norm_label(t.memory_hint)) if t.memory_hint else None
        cands = []
        for it, s, ns, k_item in pool_pre:
            if not (_kin_fast(k_label, k_item)
                    or (k_hint and _kin_fast(k_hint, k_item))):
                continue
            prs = _tying_pairs(ns, pv, tol)
            if len(prs) != 1:
                continue                   # no tie, or ambiguous line — refuse
            if _is_elimination_line(ns, tol):
                continue
            if not _in_world(prs[0][0], pv) and not _proven_zero(prs[0][0], it):
                continue                   # per-share-next-to-total class
            cands.append((prs[0][0], it, s))
        if not cands:
            continue                       # unbound -> Stage 3 (or tier 2)
        if len(cands) > MAX_CANDS:
            decisions.append(JoinDecision(
                t.sheet, t.row, "ambiguous",
                note=f"{len(cands)} tying items (> {MAX_CANDS}) — noise, not proof"))
            continue
        vals = [v for v, _it, _s in cands]
        if max(vals) - min(vals) > row_tol(max(vals, key=abs), base=1.0):
            decisions.append(JoinDecision(
                t.sheet, t.row, "ambiguous",
                note="candidates disagree: " + ", ".join(
                    f"{v:,.2f}@{it.doc}p{it.page}" for v, it, _ in cands[:4])))
            continue
        sv, it, s = cands[0]
        if sv == 0 and not _proven_zero(sv, it):
            continue
        served[t.key] = {
            "value": sv, "status": "OK", "doc": it.doc, "page": it.page,
            "line": it.label[:60], "conf": CONF_JOINED,
            "note": (f"stage-2 join: '{it.label[:40]}' prior ties {pv:,.2f} "
                     f"on ratified face {it.doc} p{it.page} at scale {s:g} "
                     f"({len(cands)} agreeing instance(s))"
                     + (" — CURRENT-YEAR LINE ABSENT from the statement; "
                        "zero proven by section closure" if sv == 0 else ""))}
        prov[t.key] = (it.doc, it.page, (it.table_id, it.row_ord), pv)
        twins[(it.doc, it.page, it.label, round(sv, 2))].append(t.key)
        decisions.append(JoinDecision(
            t.sheet, t.row, "accepted", value=sv, item_id=it.item_id,
            doc=it.doc, page=it.page, scale=s,
            gates=["face_authority", "block_scale", "prior_identity",
                   "kinship", "agreement"],
            note=f"prior {pv:,.2f} tied by '{it.label[:40]}'"))

    # TWINS: two rows tying one item identity cannot both be that line —
    # conservative: neither joins; Stage 3 or the orchestrator decides.
    dropped = set()
    for _ident, keys in twins.items():
        if len(keys) < 2:
            continue
        for k in keys:
            if served.pop(k, None) is not None:
                prov.pop(k, None)
                dropped.add(k)
    for d in decisions:
        if (d.sheet, d.row) in dropped and d.status == "accepted":
            d.status, d.value = "twin_dropped", None
            d.note += " — twin: another row tied the same item; neither joins"
    n_main = len(served)

    # TIER 2 — identity without a name, WITH page affinity: the model's
    # labels are routinely in another language than the filing, so kinship
    # starves whole sheets. An identity-grade tie (0.6 / 0.05%) may serve a
    # row ONLY from a page that already tier-1-serves >= 2 rows of the SAME
    # model sheet (the statement's own page vouches for its sheet — the
    # bound-table law on faces). Lone singletons anywhere measured 4 wrong
    # writes; a mass world-tolerance oracle measured 15. Aggregates only,
    # one agreeing value, twins dropped.
    page_sheet_serves = defaultdict(int)
    for (sh, _rw), (doc, pg, _pos, _pv) in prov.items():
        page_sheet_serves[(doc, pg, sh)] += 1
    twins2 = defaultdict(list)
    for t in targets:
        pv = t.prior_value
        if (t.key in served or t.is_backout
                or not isinstance(pv, (int, float)) or abs(pv) < 100):
            continue
        tol_id = max(0.6, abs(pv) * 5e-4)
        cands = []
        for it, s, ns, _k in pool_pre:
            if page_sheet_serves[(it.doc, it.page, t.sheet)] < 2:
                continue
            if norm_label(it.label).replace(" ", "") in CJK_STRUCTURAL:
                continue    # a bare structural word is a position, not a line
            prs = _tying_pairs(ns, pv, tol_id)
            if len(prs) != 1 or _is_elimination_line(ns, tol_id):
                continue
            if not _in_world(prs[0][0], pv) and not _proven_zero(prs[0][0], it):
                continue
            cands.append((prs[0][0], it, s))
        if not cands or len(cands) > MAX_CANDS:
            continue
        if len({round(v, 2) for v, _i, _s in cands}) != 1:
            continue
        sv, it, s = cands[0]
        if sv == 0 and not _proven_zero(sv, it):
            continue
        served[t.key] = {
            "value": sv, "status": "OK", "doc": it.doc, "page": it.page,
            "line": it.label[:60], "conf": CONF_JOINED,
            "note": (f"stage-2 tier-2 join: identity-grade prior tie "
                     f"{pv:,.2f} by '{it.label[:36]}' on a page serving "
                     f"{page_sheet_serves[(it.doc, it.page, t.sheet)]} rows "
                     f"of this sheet ({it.doc} p{it.page})"
                     + (" — CURRENT-YEAR LINE ABSENT from the statement; "
                        "zero proven by section closure" if sv == 0 else ""))}
        prov[t.key] = (it.doc, it.page, (it.table_id, it.row_ord), pv)
        twins2[(it.doc, it.page, it.label, round(sv, 2))].append(t.key)
        decisions.append(JoinDecision(
            t.sheet, t.row, "accepted", value=sv, item_id=it.item_id,
            doc=it.doc, page=it.page, scale=s,
            gates=["face_authority", "block_scale", "prior_identity_exact",
                   "page_affinity", "agreement"],
            note=f"tier-2: prior {pv:,.2f} tied by '{it.label[:36]}'"))
    for _ident, keys in twins2.items():
        if len(keys) > 1:
            for k in keys:
                if served.pop(k, None) is not None:
                    prov.pop(k, None)
                    dropped.add(k)
    n_tier2 = len(served) - n_main

    # SIBLING-POSITION pass (measured 13/13): an unjoined row strictly
    # between two joined rows binds to the SOLE tying item positioned
    # between its neighbours' items on the same page.
    targets_by_key = {t.key: t for t in targets}
    items_by_page = defaultdict(list)
    for it in pool:
        items_by_page[(it.doc, it.page)].append(it)
    by_sheet = defaultdict(list)
    for (sh, rw) in sorted(prov):
        by_sheet[sh].append(rw)
    for sh, rows in by_sheet.items():
        for a, b in zip(rows, rows[1:]):
            if b - a < 2:
                continue
            doc_a, pg_a, pos_a, _ = prov[(sh, a)]
            doc_b, pg_b, pos_b, _ = prov[(sh, b)]
            if (doc_a, pg_a) != (doc_b, pg_b) or pos_b <= pos_a:
                continue
            s = page_scales[(doc_a, pg_a)]
            for mid in range(a + 1, b):
                key = (sh, mid)
                t = targets_by_key.get(key)
                if key in served or t is None or t.is_backout:
                    continue
                pv = t.prior_value
                if not isinstance(pv, (int, float)) or pv == 0:
                    continue
                tol = _world_tol(pv)
                hits = []
                for it in items_by_page[(doc_a, pg_a)]:
                    if not (pos_a < (it.table_id, it.row_ord) < pos_b):
                        continue
                    ns = [to_model_units(n, s) for n in it.nums]
                    prs = _tying_pairs(ns, pv, tol)
                    if len(prs) == 1 and not _is_elimination_line(ns, tol) \
                            and _in_world(prs[0][0], pv):
                        hits.append((prs[0][0], it))
                if len(hits) == 1 and hits[0][0] != 0:
                    sv, it = hits[0]
                    served[key] = {
                        "value": sv, "status": "OK", "doc": it.doc,
                        "page": it.page, "line": it.label[:60],
                        "conf": CONF_JOINED,
                        "note": (f"stage-2 join (sibling-position): "
                                 f"'{it.label[:36]}' between joined "
                                 f"neighbours, prior ties {pv:,.2f} "
                                 f"{it.doc} p{it.page}")}
                    decisions.append(JoinDecision(
                        sh, mid, "accepted_sibling", value=sv,
                        item_id=it.item_id, doc=it.doc, page=it.page, scale=s,
                        gates=["face_authority", "block_scale",
                               "prior_identity", "sibling_position"],
                        note=f"prior {pv:,.2f} tied between joined neighbours"))

    log.append(f"stage-2: {n_main} rows joined deterministically, "
               f"+{n_tier2} tier-2, "
               f"+{len(served) - n_main - n_tier2} by sibling position, "
               f"{len(dropped)} twin-dropped")
    return served, decisions


def join_bound_tables(ledger, targets, served, log=None):
    """Stage 2.5 — the Driver/MD&A path: TWO-LEVEL binding (council law:
    bind tables before rows; never a left-neighbour, never a loose label).

    LEVEL 1 — TABLE BINDING: a non-statement table (doc, page, table_id)
    qualifies only when >= BIND_MIN_PRIORS DISTINCT unserved-row priors are
    tied by DISTINCT items at ONE scale. That consensus proves both the
    table's identity ("this is the model block's own table") and its scale
    — the same ratio-lock law as page ratification, scoped to the table.

    LEVEL 2 — ROW BINDING, inside bound tables only: signed slot-by-tie
    prior identity at the row's world tolerance, in-world value, exactly
    one agreeing candidate across all bound tables, twins dropped. Label
    kinship is NOT required here — the model's driver labels are routinely
    in a different language than the filing's tables, and the binding of
    the TABLE is the block-level kinship; the per-row anchor is the prior.
    Served conf 4, never locked. No-prior rows are NOT served (Stage 3 /
    the loop own them).
    """
    log = log if log is not None else []
    prior_docs = ledger.prior_period_docs()
    face_pages = {k for k, f in ledger.faces.items() if f in ("pl", "bs", "cf")}
    by_table = defaultdict(list)
    for it in ledger.items:
        if (it.joinable() and it.doc not in prior_docs
                and (it.doc, it.page) not in face_pages):
            by_table[(it.doc, it.page, it.table_id)].append(it)

    unserved = [t for t in targets
                if t.key not in served and not t.is_backout
                and isinstance(t.prior_value, (int, float))
                and abs(t.prior_value) >= 100.0  # small MD&A values tie by
                                                 # coincidence even identity-
                                                 # grade (tax-row class,
                                                 # measured at floors 1-25)
                and t.input_kind != "derived"]   # computed rows (deltas,
                                                 # ratios) are never inputs
    by_sheet_t = defaultdict(list)
    for t in unserved:
        by_sheet_t[t.sheet].append(t)

    BIND_MIN_PRIORS = 3     # two ties is chance; three distinct rows of ONE
                            # model block at one scale is a table identity

    def _tie_grade(nm, pv):
        # identity-grade anchor (0.6 abs / 0.05% rel) — same law as every
        # other anchor; world tolerance measured coincidence-prone here
        return abs(nm - abs(pv)) <= max(0.6, abs(pv) * 5e-4)

    # LEVEL 1, PER MODEL BLOCK: a table binds FOR one model sheet only when
    # >= 3 of THAT sheet's priors tie (the council's block<->table binding;
    # binding against the whole census measured related-party tables bound
    # by coincidence)
    # The binding also LEARNS the table's column geometry: the minimal
    # tying slot is where the prior-year block begins, and the current
    # block mirrors it from slot 0 — segment tables interleave measures
    # ((2025rev, 2025cost, 2024rev, 2024cost)); adjacent-pair mechanics
    # served the WRONG MEASURE there (measured live: 2025 cost into a
    # revenue row).
    bound = defaultdict(dict)    # sheet -> {table key: (scale, offset)}
    for key, items in by_table.items():
        if len(items) < BIND_MIN_PRIORS:
            continue
        for sheet, ts in by_sheet_t.items():
            best, best_n, best_slots = None, 0, []
            for s in SCALES:
                tied = set()
                slots = []
                for it in items:
                    # a multi-measure line (rev AND cost priors printed on
                    # one segment row) legitimately vouches for several
                    # DISTINCT priors — the set collapses duplicates
                    for k, n in enumerate(it.nums):
                        if k == 0:
                            continue    # slot 0 is the current block's start
                        if s > 1 and abs(n) < s / 1000:
                            continue
                        nm = abs(to_model_units(n, s))
                        for t in ts:
                            if _tie_grade(nm, t.prior_value):
                                if round(abs(t.prior_value), 2) not in tied:
                                    slots.append(k)
                                tied.add(round(abs(t.prior_value), 2))
                                break
                if len(tied) > best_n:
                    best_n, best, best_slots = len(tied), s, slots
            if best_n >= BIND_MIN_PRIORS:
                k0 = min(best_slots)
                if best_slots.count(k0) < 2:
                    k0 = 1      # offset needs >= 2 corroborating rows,
                                # else classic adjacency
                bound[sheet][key] = (best, k0)
    if not bound:
        log.append("stage-2.5: no non-statement table bound")
        return {}, []

    out, decisions = {}, []
    twins = defaultdict(list)
    for t in unserved:
        pv = t.prior_value
        tol = max(0.6, abs(pv) * 5e-4)       # identity-grade rows only
        cands = []
        for key, (s, k0) in bound.get(t.sheet, {}).items():
            for it in by_table[key]:
                if norm_label(it.label).replace(" ", "") in CJK_STRUCTURAL:
                    continue
                ns = [to_model_units(n, s) for n in it.nums]
                # the prior must tie at exactly ONE slot in the prior
                # block; the current is the mirrored slot (k - k0)
                ties = [(k, 1 if abs(n - pv) <= tol else -1)
                        for k, n in enumerate(ns)
                        if k >= k0 and (abs(n - pv) <= tol
                                        or abs(n + pv) <= tol)]
                if len(ties) != 1 or _is_elimination_line(ns, tol):
                    continue
                k, sign = ties[0]
                j = k - k0
                if not (0 <= j < min(k0, len(ns))):
                    continue    # current slot must sit in the current block
                sv0 = sign * ns[j]
                # stricter world band than statements (30x): an 84x MW
                # coincidence measured through the 100x band here
                if abs(sv0) > 30 * abs(pv) or abs(sv0) * 30 < abs(pv):
                    continue
                cands.append((sv0, it, s))
        if not cands or len(cands) > MAX_CANDS:
            continue
        vals = [v for v, _i, _s in cands]
        if max(vals) - min(vals) > row_tol(max(vals, key=abs), base=1.0):
            continue
        sv, it, s = cands[0]
        if sv == 0:
            continue
        out[t.key] = {
            "value": sv, "status": "OK", "doc": it.doc, "page": it.page,
            "line": it.label[:60], "conf": CONF_JOINED,
            "note": (f"stage-2.5 bound-table join: table proven by "
                     f">=3 sibling prior ties at scale {s:g}; this row's "
                     f"prior {pv:,.2f} tied by '{it.label[:36]}' "
                     f"({it.doc} p{it.page})")}
        twins[(it.doc, it.page, it.table_id, it.label, round(sv, 2))].append(t.key)
        decisions.append(JoinDecision(
            t.sheet, t.row, "accepted", value=sv, item_id=it.item_id,
            doc=it.doc, page=it.page, scale=s,
            gates=["bound_table", "prior_identity", "agreement"],
            note=f"bound-table: prior {pv:,.2f} tied by '{it.label[:36]}'"))
    dropped = 0
    for _k, keys in twins.items():
        if len(keys) > 1:
            for k in keys:
                out.pop(k, None)
                dropped += 1
    for d in decisions:
        if (d.sheet, d.row) not in out and d.status == "accepted":
            d.status = "twin_dropped"
    log.append(f"stage-2.5: {len(bound)} tables bound, {len(out)} rows "
               f"joined, {dropped} twin-dropped")
    return out, decisions


def unique_evidence_value(ledger, targets, t):
    """The disclosed value for one target row by prior identity on a
    ratified current-doc face page — the loop's and the sweep's shared
    evidence oracle. -> (value, item, scale) or None: single agreeing
    in-world candidate, or nothing.

    The pool/scale cache lives ON THE LEDGER (a module dict keyed by
    id(ledger) let a freed ledger's id be reused by a fresh object — a
    measured stale-cache poison, the same artifact class as the vintage
    and census diagnostic disasters)."""
    _cache = getattr(ledger, "_oracle_cache", None)
    if _cache is None:
        priors = [x.prior_value for x in targets
                  if isinstance(x.prior_value, (int, float))]
        pool = ledger.join_pool()
        _cache = {"pool": pool,
                  "scales": ratify_page_scales(pool, priors)}
        try:
            ledger._oracle_cache = _cache
        except Exception:
            pass
    pv = t.prior_value
    if not isinstance(pv, (int, float)) or pv == 0:
        return None
    # EXACT identity only (run-24 false positive: 5e-4 relative gave a
    # 14-unit window on a 28k prior, wide enough for a wrong-scale junk
    # line to tie and "prove" 66,532 for a segment row; disclosures
    # reprint the comparative to the cent, so the oracle demands it —
    # analyst-rounded priors simply stay outside oracle jurisdiction)
    tol = max(0.6, abs(pv) * 2e-5)
    cands = []
    for it in _cache["pool"]:
        s = _cache["scales"].get((it.doc, it.page))
        if s is None:
            continue
        ns = [to_model_units(n, s) for n in it.nums]
        prs = _tying_pairs(ns, pv, tol)
        if len(prs) == 1 and (_in_world(prs[0][0], pv)
                              or _proven_zero(prs[0][0], it)):
            cands.append((prs[0][0], it, s))
    if not cands:
        return None
    vals = [v for v, _i, _s in cands]
    if max(vals) - min(vals) > row_tol(max(vals, key=abs), base=1.0):
        return None
    return cands[0]


def infer_composition(wb, sheet, row, pcol, tcol, max_terms=8):
    """A stale COMBINED row (应收票据及应收账款-class) whose prior equals the
    SUM of the priors of the rows directly beneath it is a composition the
    analyst designed — its current is the same sum, written as a FORMULA
    (house law: back-outs are formulas, never hardcodes) and flagged
    orange. -> '=SUM(Uj:Uk)' or None. Identity-grade prior match only."""
    ws = wb[sheet]
    base = ws[f"{pcol}{row}"].value
    if not isinstance(base, (int, float)) or base == 0:
        return None
    acc = 0.0
    for k in range(row + 1, row + 1 + max_terms):
        v = ws[f"{pcol}{k}"].value
        if not isinstance(v, (int, float)):
            break
        acc += v
        if k > row + 1 and abs(acc - base) <= max(0.6, abs(base) * 5e-4):
            return f"=SUM({tcol}{row + 1}:{tcol}{k})"
    return None


def decisions_to_json(decisions):
    import json
    return json.dumps({"version": 1, "decisions": [asdict(d) for d in decisions]},
                      ensure_ascii=False, indent=1)
