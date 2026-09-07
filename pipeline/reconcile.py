"""THE RECONCILIATION STAGE (owner ruling 2026-09-01, after run 208:
"the agent plugged 2025 and called it a day").

The by-hand method AS the serve engine. An analyst does not serve
scattered rows — they lay a whole printed statement beside the model
and reconcile line by line. This stage walks EVERY table of every
current-document face page:

  - each printed line's (current, prior) pair is matched to model rows
    by the PRIOR (the map), giving a complete, auditable mapping table;
  - a printed line whose current EQUALS its prior CONFIRMS the model's
    unchanged value — served clean, red cleared (the owner's
    "mappable: the number didn't change vs last year");
  - the ACCEPTANCE TEST is the statement's own arithmetic: where a
    table prints a total that ties a model total-row, the served
    children must sum to it — a serve set that breaks its own printed
    total is rejected WHOLESALE (an India-taking-Australia's-number
    cannot survive, because it breaks the total it sits inside);
  - every printed line with no model home and every model row with no
    line are listed — the leftovers that name missing lines.

Generic: tables, priors, totals all come from the run's own ledger and
workbook. Runs BEFORE the scattered joins; whatever reconciliation
serves is authoritative (conf 5); the joins fill only what remains.
"""
import re
from collections import defaultdict

from .checks import prior_column, year_columns
from .evaluator import Evaluator
from .numerics import norm_label, row_tol, to_model_units
from .ledger import vintage_ban as _vintage_ban

CONF_RECON = 4   # trusted, NOT locked — a new stage earns locks later
UNCHANGED_CONF = 4


def _model_prior_index(wb, spec, target_year, max_row=100000):
    """Evaluated prior for every target row -> {round(pv,1): [(sheet,
    row)]}, plus per-row lookup {(sheet,row): pv}. Formula priors are
    evaluated (the no-cached-values discipline)."""
    ev = Evaluator(wb)
    homes = defaultdict(list)
    by_row = {}
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        pcol = prior_column(spec, sheet, target_year)
        if not pcol:
            continue
        hdr = (spec.get("year_axis") or {}).get(sheet, {}).get("header_row")
        ws = wb[sheet]
        for r in range(1, min(ws.max_row, max_row) + 1):
            if hdr and r == int(hdr):
                # the year-header row: its prior IS a year (2024), which a
                # printed date line ("31 December 2024") would fake-match
                continue
            v = ws[f"{pcol}{r}"].value
            if isinstance(v, str) and v.startswith("="):
                try:
                    v = ev.cell(sheet, f"{pcol}{r}")
                except Exception:
                    v = None
            if isinstance(v, (int, float)) and abs(v) >= 0.5:
                homes[round(v, 1)].append((sheet, r))
                by_row[(sheet, r)] = float(v)
    # THE INTERIM COMPARATIVE (DFE run 236): in a half-year / quarterly
    # run the balance sheet compares to the last YEAR-END, not to the
    # interim prior — the model's last annual column is a second home
    # for a printed comparative (total assets 156,365 | 142,009 ties the
    # FY column, not the 1H column). Rows already homed by their interim
    # prior keep that as their tolerance base.
    for sheet, acol in (spec.get("annual_prior_axis") or {}).items():
        if sheet not in wb.sheetnames or not acol:
            continue
        hdr = (spec.get("year_axis") or {}).get(sheet, {}).get("header_row")
        ws = wb[sheet]
        for r in range(1, min(ws.max_row, max_row) + 1):
            if hdr and r == int(hdr):
                continue
            v = ws[f"{acol}{r}"].value
            if isinstance(v, str) and v.startswith("="):
                try:
                    v = ev.cell(sheet, f"{acol}{r}")
                except Exception:
                    v = None
            if isinstance(v, (int, float)) and abs(v) >= 0.5:
                key = round(v, 1)
                if (sheet, r) not in homes[key]:
                    homes[key].append((sheet, r))
                by_row.setdefault((sheet, r), float(v))
    return homes, by_row


def _resolve(rows, wb, spec, target_year, line_label=None):
    """Multi-home priors (a D&A figure living on Driver AND SOC as
    linked twins) are resolvable when exactly ONE home is an INPUT cell
    in the target column — the formula twins just read it. Serving the
    input home serves them all.

    Two INPUT homes with the same prior (DFE run 235: 'cash received from
    investors' 110.0 and its 'of which: from minority investors' sub-line
    110.0 — the parent and the child printed the same last year) are
    told apart by the LABEL the disclosure line carries: the home whose
    label equals the line's wins; failing that, the only home whose
    label is kin to it. No label evidence -> unresolved, as before."""
    if len(rows) <= 1:
        return rows
    inputs = []
    for sheet, r in rows:
        col = year_columns(spec, sheet).get(str(target_year))
        if not col:
            continue
        v = wb[sheet][f"{col}{r}"].value
        if not (isinstance(v, str) and v.startswith("=")):
            inputs.append((sheet, r))
    if len(inputs) == 1:
        return inputs
    if len(inputs) > 1 and line_label:
        from .numerics import kinship, norm_label

        def _lab(sheet, r):
            for c in range(1, 7):
                v = wb[sheet].cell(r, c).value
                if isinstance(v, str) and v.strip():
                    return v
            return ""
        want = norm_label(str(line_label)).replace(" ", "")
        exact = [h for h in inputs
                 if want and norm_label(_lab(*h)).replace(" ", "") == want]
        if len(exact) == 1:
            return exact
        kin = [h for h in inputs if kinship(str(line_label), _lab(*h))]
        if len(kin) == 1:
            return kin
    return rows


WIDE_ROW = 4        # numbers on a line at/above which it is not a statement line


def is_statement_line(item):
    """current | prior, optionally a note reference: at most 3 numbers."""
    nums = item.nums if hasattr(item, "nums") else item.get("nums", [])
    return len([n for n in nums if isinstance(n, (int, float))]) < WIDE_ROW


SMALL_PRIOR = 50.0   # below this a prior ties by coincidence (the one-home bar)


def small_prior_needs_kinship(pv, line_label, row_label):
    """THE SMALL-PRIOR LAW for reconciliation (run-229 autopsy: with the
    wide rows gone, priors of -23, 105, -12, -10 found 'homes' on
    'Short-term deposits', 'India', 'Joint ventures', 'Meters' — label-
    unrelated coincidences, all wrong). A material prior (>= 50) is its
    own identity; a small one needs the line's label to be kin to the
    model row's. Returns True when the pair is acceptable."""
    from .numerics import kinship
    if not isinstance(pv, (int, float)) or abs(pv) >= SMALL_PRIOR:
        return True
    return bool(kinship(str(line_label or ""), str(row_label or "")))


def _pairs(ns, scale):
    """(current, prior) pairs from a printed line, positionally: the
    classic two-column statement puts current first. Note-column
    numbers (small leading ints) are skipped by trying every adjacent
    pair."""
    out = []
    vals = [to_model_units(n, scale) for n in ns]
    for i in range(len(vals) - 1):
        out.append((vals[i], vals[i + 1]))
    return out


def reconcile(wb, spec, target_year, ledger, log, max_lines_per_table=80):
    """-> (serves, mapping) where serves is the standard serve dict and
    mapping = {"tables": n, "lines": n, "matched": n, "confirmed": n,
    "rejected_tables": [...], "unmatched_lines": [...],
    "unserved_rows_hint": n}."""
    homes, by_row = _model_prior_index(wb, spec, target_year)
    prior_docs = _vintage_ban(ledger)
    from .stage2_join import ratify_page_scales
    try:
        pool = ledger.join_pool(all_pages=True)     # the whole report, faces first
    except TypeError:                               # a face-only stub ledger (museum)
        pool = ledger.join_pool()
    priors = list(by_row.values())
    page_scales = ratify_page_scales(pool, priors, [])
    tables = defaultdict(list)
    face_rank = {}
    for it in pool:
        if it.doc in prior_docs or (it.doc, it.page) not in page_scales:
            continue
        tables[(it.doc, it.page, it.table_id)].append(it)
        face_rank[(it.doc, it.page, it.table_id)] = \
            0 if getattr(ledger, "faces", {}).get((it.doc, it.page)) in ("pl", "bs", "cf") else 1

    serves, mapping = {}, {
        "tables": 0, "lines": 0, "matched": 0, "confirmed": 0,
        "rejected_tables": [], "unmatched_lines": []}
    claimed = {}          # (sheet,row) -> (value, src) the FIRST claim wins

    for key in sorted(tables, key=lambda k: (face_rank.get(k, 1), k)):   # statements claim first
        doc, page, tid = key
        items = sorted(tables[key], key=lambda i: i.row_ord or 0)
        # no table-length fence (deduction 2026-09-08): time is the budget
        s = page_scales[(doc, page)]
        mapping["tables"] += 1
        table_serves = {}      # (sheet,row) -> (value, item, kind)
        big_moves = set()      # served, but worth a second look
        exact_rows = set()     # the line's label IS the row's label
        # A PERIOD TABLE has a header line of consecutive years (2025 2024
        # 2023 …); its wide rows are periods side by side and may pair. A
        # table without one is a MATRIX (segments, ageing, roll-forwards):
        # its columns are not periods, so a wide row there never pairs —
        # run 257's 57 false 'two readings' and 182 refused ties all came
        # from segment matrices paired as if they were year tables.
        period_table = False
        for it_ in items:
            yrs = [int(n) for n in it_.nums if isinstance(n, (int, float))
                   and float(n).is_integer() and 1990 <= n <= 2100]
            # distinct years across the header = periods side by side; the
            # same years REPEATED (2025 2024 | 2025 2024 | …) = a segment ×
            # year grid, whose wide rows never pair (CLP run 257 floor: 35
            # false readings from the announcement's segment tables)
            if len(yrs) >= 2 and len(set(yrs)) == len(yrs):
                period_table = True
                break
            if len(yrs) >= 2 and len(set(yrs)) < len(yrs):
                period_table = False
                break
        for it in items:
            mapping["lines"] += 1
            # NO WIDE-ROW FENCE (deduction 2026-09-08): a summary table
            # prints current | prior | growth, a five-year table prints
            # five columns — any adjacent pair whose prior ties is
            # evidence. What run 229 actually taught ('6,608 | 471 | 914 |
            # 7,993' served finance costs because 471 sat mid-row): in a
            # wide row the pair's POSITION is uncertain, so the LABEL must
            # confirm the tie — number first, then the name.
            wide = len([n for n in it.nums if isinstance(n, (int, float))]) >= 4
            if wide and not period_table:
                mapping["matrix_rows"] = mapping.get("matrix_rows", 0) + 1
                continue          # evidence: a wide row in a table with no year header is a matrix row — its columns are not periods
            hit = None
            # THE PAIR IN A WIDE ROW (deduction 2026-09-08, fence-free floor):
            # 'accounts receivable 15,193.79 | 9.34% | 12,000 | 8.1% | +26%'
            # — the number before the tying prior is a percentage; the
            # current is the nearest EARLIER number of the prior's own
            # magnitude. Narrow lines keep the classic adjacent pair.
            pairs = _pairs(it.nums, s)
            if wide:
                vals_w = [to_model_units(n, s) for n in it.nums]
                pairs = []
                for j in range(1, len(vals_w)):
                    pv_w = vals_w[j]
                    for i in range(j - 1, -1, -1):
                        cw = vals_w[i]
                        if abs(pv_w) >= 0.5 and abs(cw) <= 30 * abs(pv_w) and abs(cw) * 30 >= abs(pv_w):
                            pairs.append((cw, pv_w))
                            break
            for cur, pv in pairs:
                rows = _resolve(homes.get(round(pv, 1), []), wb, spec,
                                target_year, line_label=it.label)
                if len(rows) != 1:
                    # sign-flipped storage: model may hold the negative
                    rows = _resolve(homes.get(round(-pv, 1), []), wb, spec,
                                    target_year, line_label=it.label)
                    if len(rows) != 1:
                        continue
                    cur = -cur
                    pv = -pv
                (sheet, r) = rows[0]
                if not small_prior_needs_kinship(
                        pv, it.label, wb[sheet].cell(r, 1).value):
                    mapping["small_unkin"] = mapping.get("small_unkin", 0) + 1
                    continue
                if wide:
                    from .numerics import kinship as _kin_w
                    if not _kin_w(str(it.label or ""), str(wb[sheet].cell(r, 1).value or "")):
                        mapping["wide_unkin"] = mapping.get("wide_unkin", 0) + 1
                        continue
                tol = row_tol(by_row[(sheet, r)])
                # THE OUT-OF-WORLD GUARD FIRES ONLY ON A WEAK MAP (owner
                # 2026-09-08): on a ratified face where the line's label
                # IS the model row's label, a 47x move is the disclosure
                # (DFE's A+H share placement: 110 -> 5,236). The guard
                # stays for prior-only ties, which can be coincidences.
                _rl = norm_label(str(wb[sheet].cell(r, 1).value or "")).replace(" ", "")
                _ll = norm_label(str(it.label or "")).replace(" ", "")
                exact = bool(_rl) and _rl == _ll
                big = (abs(cur) > 30 * max(abs(pv), 1)
                       or (abs(pv) > 30 and abs(cur) * 30 < abs(pv)))
                if cur == 0:
                    big = False            # a printed 0 is nil, not a 30x move
                # ... on a KIN map it is a SUGGESTION, not a gate (owner
                # 2026-09-08: "this input moved 30x — double check before
                # you input it"): served and flagged for review; on a
                # prior-only tie with no label kinship a 30x move is a
                # coincidence and is dropped, as before
                if big and not exact:
                    from .numerics import kinship as _kin
                    if not _kin(str(wb[sheet].cell(r, 1).value or ""), str(it.label or "")):
                        continue
                    big_moves.add((sheet, r))
                hit = (sheet, r, cur, pv)
                if exact:
                    exact_rows.add((sheet, r))
                break
            if hit is None:
                money = [n for n in it.nums if abs(n) >= 50]
                if money and len(money) <= 4:
                    mapping["unmatched_lines"].append(
                        (doc, page, str(it.label)[:48], money[:3]))
                continue
            sheet, r, cur, pv = hit
            kind = ("confirmed" if abs(cur - pv)
                    <= row_tol(pv, base=0.01) else "served")
            if (sheet, r) not in table_serves:
                table_serves[(sheet, r)] = (cur, it, kind)
        # THE ACCEPTANCE TEST: if this table serves a model TOTAL row
        # whose model children are also served here, the children must
        # sum to the total — else the whole table's serves are refused
        ok_table = True
        for (sheet, r), (cur, it, kind) in table_serves.items():
            f = wb[sheet][
                f"{year_columns(spec, sheet)[str(target_year)]}{r}"].value
            m = re.match(r"^=\s*SUM\(([A-Z]{1,3})(\d+):[A-Z]{1,3}(\d+)\)\s*$",
                         str(f).replace("$", "")) \
                if isinstance(f, str) else None
            if not m:
                continue
            kids = [(sheet, rr) for rr in range(int(m.group(2)),
                                                int(m.group(3)) + 1)]
            kid_vals = [table_serves[k][0] for k in kids
                        if k in table_serves]
            if len(kid_vals) >= 2:
                # partial coverage allowed; full coverage must tie
                if len(kid_vals) == len([k for k in kids
                                         if k in by_row]) \
                        and abs(sum(kid_vals) - cur) > row_tol(cur,
                                                              base=2.0):
                    ok_table = False
                    mapping["rejected_tables"].append(
                        (doc, page, tid,
                         f"children sum {sum(kid_vals):,.1f} != printed "
                         f"total {cur:,.1f}"))
                    break
        if not ok_table:
            continue
        for (sheet, r), (cur, it, kind) in table_serves.items():
            if (sheet, r) in claimed:
                prev_v, _src = claimed[(sheet, r)]
                # two printings agree within the COARSER printing's own
                # granularity (a 亿元 summary with two decimals prints to
                # the nearest 1m; the statement prints to the cent)
                _raw = next((n for n in it.nums if isinstance(n, (int, float))), None)
                _dec = len(repr(round(abs(_raw), 8)).split(".")[1].rstrip("0")) if _raw is not None and "." in repr(round(abs(_raw), 8)) else 0
                _gran = abs(to_model_units(10.0 ** (-_dec), s)) if _raw is not None else 0.0
                _parent = (doc, page) in getattr(ledger, "parent_pages", set())  # evidence: docid proved this page is the PARENT company's statement — a different entity, not a second reading of the consolidated row
                # a second READING is a line that names the item — kin to the
                # model row's label or to the first reading's line; a line
                # whose comparative merely equals the prior by coincidence
                # (a solar farm's balance, a tax item) is no reading at all
                from .numerics import kinship as _kin_r
                _first = serves.get((sheet, r), {}).get("line", "") if (sheet, r) in serves else ""
                _named = _kin_r(str(it.label or ""), str(wb[sheet].cell(r, 1).value or "")) \
                    or (_first and _kin_r(str(it.label or ""), str(_first)))
                if abs(prev_v - cur) > max(row_tol(cur, base=1.0), 0.51 * _gran) and (sheet, r) in serves \
                        and not _parent and _named:
                    # TWO PRINTED READINGS (deduction 2026-09-08, F2): the
                    # statement claimed first; a later page prints a
                    # different current for the same tying prior — never
                    # dropped silently, never picked silently: red, both
                    # readings in the note, the brain's card decides
                    serves[(sheet, r)].update({
                        "flag": "red", "conf": 3,
                        "note": (f"Two printed readings: {prev_v:,.2f} ({_src}) vs "
                                 f"{cur:,.2f} ({doc} p{page} {str(it.label)[:24]!r}). "
                                 "Kept the statement's — please confirm.")})
                    mapping["two_readings"] = mapping.get("two_readings", 0) + 1
                    # (a PARENT-company statement's line is not a second reading
                    # of the consolidated row — docid knows those pages; they
                    # rank below the consolidated face and never flag it)
                    mapping.setdefault("two_readings_rows", []).append(
                        (sheet, r, round(prev_v, 2), _src, round(cur, 2), f"{doc} p{page} {str(it.label)[:24]}"))
                continue
            claimed[(sheet, r)] = (cur, f"{doc} p{page}")
            mapping["matched"] += 1
            if kind == "confirmed":
                mapping["confirmed"] += 1
            serves[(sheet, r)] = {
                "value": cur, "status": "OK", "doc": doc, "page": page,
                "line": str(it.label)[:60],
                "conf": UNCHANGED_CONF if kind == "confirmed"
                else CONF_RECON,
                "note": (f"reconciliation: '{str(it.label)[:40]}' — "
                         f"prior {by_row[(sheet, r)]:,.2f} maps the line "
                         f"({doc} p{page}); "
                         + ("value CONFIRMED unchanged vs last year"
                            if kind == "confirmed" else
                            "current read from the same line"))}
            if (sheet, r) in exact_rows:
                serves[(sheet, r)]["exact_label"] = True
            if (sheet, r) in big_moves:
                # served, with the owner's 'double check' note — red
                # (unsure), conf 3 so the value is not proven-locked
                _pv = by_row[(sheet, r)]
                _x = abs(cur) / max(abs(_pv), 1e-9)
                serves[(sheet, r)].update({
                    "flag": "red", "conf": 3,
                    "note": (f"Read from the disclosure ({doc} p{page}) but "
                             f"moved {_x:,.0f}x vs last year ({_pv:,.1f} -> "
                             f"{cur:,.1f}) — please double check.")})
    for _tr in mapping.get("two_readings_rows", [])[:12]:
        log(f"[run]   two readings: {_tr[0]}!{_tr[1]} {_tr[2]:,} ({_tr[3]}) vs {_tr[4]:,} ({_tr[5]})")
    log(f"[run] reconciliation: {mapping.get('two_readings', 0)} rows with two printed "
        f"readings (red), {mapping.get('wide_unkin', 0)} wide-row ties refused (no label "
        f"kinship), {mapping.get('small_unkin', 0)} "
        "small-prior coincidences refused (no label kinship); "
        f"{mapping['tables']} tables walked, "
        f"{mapping['matched']} rows served ({mapping['confirmed']} "
        f"confirmed unchanged), {len(mapping['rejected_tables'])} tables "
        f"rejected by their own sums, "
        f"{len(mapping['unmatched_lines'])} printed lines with no model "
        "home")
    return serves, mapping
