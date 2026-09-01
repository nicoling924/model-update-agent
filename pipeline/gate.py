"""The delivery gate — a run REFUSES to deliver unless every check passes.

The owner's usability bar, from the run-A/B failure autopsy, all
deterministic, no LLM (REBUILD.md is the authority):

1. YEAR HEADERS ROLLED: every year header cell in the target column carries
   the new period in the SAME data type as the prior column's header (a
   numeric 2024 rolls to numeric 2025; a text date stays text; no stale
   "2024-12-31" and no leftover "2025E" heads).
2. ORDER-OF-MAGNITUDE SWEEP: no written cell sits >100x or <1% of its
   prior actual (catches every raw-yuan/unconverted cell ever shipped —
   including trusted writes that bypassed the writer's band).
3. FLAG BUDGET: >15% of a sheet's filled target-column cells flagged means
   the run FAILED that sheet — flags are "look here" markers, not a
   liability waiver.
4. DRIVER ROLL INTEGRITY: forecast columns keep their formulas, and no
   sign-absurd forecast (negative where both actual years are positive
   aggregates — the negative-revenue class).
5. CHECKS AS BEFORE: target-year check rows pass, no clobbered formulas,
   no new error literals, no unresolved cycles.

Refusal is a RESULT: the workbook is saved to a quarantine name with the
failure list, never delivered as the model.
"""
import re

from .checks import (forecast_columns, prior_column, scorecard, year_columns)
from .writer import clobber_diff

FLAG_BUDGET = 0.15
BAND_RATIO = 100.0
_ERROR_LITERALS = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?")
_HEADER_SCAN_ROWS = 12
AGGREGATE_MIN = 10.0     # sign-absurd test applies to aggregate-world rows


def _mentions_year(v, year):
    y = str(year)
    if isinstance(v, (int, float)):
        return abs(v - int(y)) < 0.5
    if hasattr(v, "year"):          # datetime/date
        return v.year == int(y)
    return y in str(v)


def _type_class(v):
    if isinstance(v, (int, float)):
        return "number"
    if hasattr(v, "year"):
        return "date"
    return "text"


def check_year_headers(wb, spec, target_year):
    """Gate 1. For each year_axis sheet: every top-of-sheet row where the
    prior column mentions the prior year, the target column must mention
    the TARGET year in the same type class."""
    fails = []
    ty = str(target_year)
    for sheet, axis in (spec.get("year_axis") or {}).items():
        cols = axis.get("columns") or {}
        tcol = cols.get(ty)
        pcol = prior_column(spec, sheet, target_year)
        if not tcol or not pcol or sheet not in wb.sheetnames:
            continue
        years = sorted(cols)
        prior_year = years[years.index(ty) - 1]
        ws = wb[sheet]
        for r in range(1, min(ws.max_row, _HEADER_SCAN_ROWS) + 1):
            pv = ws[f"{pcol}{r}"].value
            if pv is None or not _mentions_year(pv, prior_year):
                continue
            tv = ws[f"{tcol}{r}"].value
            if tv is None or not _mentions_year(tv, ty):
                fails.append(f"HEADER {sheet}!{tcol}{r}: prior header "
                             f"{pv!r} not rolled to {ty} (holds {tv!r})")
            elif _type_class(tv) != _type_class(pv):
                fails.append(f"HEADER {sheet}!{tcol}{r}: type changed "
                             f"{_type_class(pv)} -> {_type_class(tv)} "
                             f"({pv!r} -> {tv!r}) — never change a header's type")
            elif isinstance(tv, str) and re.search(rf"{ty}\s*E\b", tv):
                fails.append(f"HEADER {sheet}!{tcol}{r}: {tv!r} still marked "
                             f"estimate in an actual column")
    return fails


def magnitude_sweep(wb, spec, target_year, written, served=None):
    """Gate 2. Every written target-column cell vs its prior actual.

    Rows served at conf 5 are exempt: their SAME-LINE comparative tied the
    model's prior at a proven scale, so a huge ratio there is real news
    (tiny-prior investing lines legitimately explode 10,000x), not the
    raw-scale disease. Everything else — joins, loop writes, rollover
    leftovers — stays swept."""
    served = served or {}
    fails = []
    by_sheet = {}
    for ref in written:
        sh, coord = ref.split("!", 1)
        by_sheet.setdefault(sh, []).append(coord)
    for sheet, coords in by_sheet.items():
        pcol = prior_column(spec, sheet, target_year)
        tcol = year_columns(spec, sheet).get(str(target_year))
        if not pcol or sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        for coord in coords:
            m = re.match(rf"^{tcol}(\d+)$", coord) if tcol else None
            if not m:
                continue
            if int((served.get((sheet, int(m.group(1)))) or {})
                   .get("conf") or 0) >= 5:
                continue
            v = ws[coord].value
            pv = ws[f"{pcol}{m.group(1)}"].value
            if not isinstance(v, (int, float)) or not isinstance(pv, (int, float)):
                continue
            if v != 0 and pv != 0 and (abs(v) > BAND_RATIO * abs(pv)
                                       or abs(v) * BAND_RATIO < abs(pv)):
                fails.append(f"MAGNITUDE {sheet}!{coord}: {v:,.2f} vs prior "
                             f"{pv:,.2f} — unconverted/raw-scale class")
    return fails


def flag_budget(wb, spec, target_year, flags, load_bearing=None):
    """Gate 3. RED flags per sheet vs filled target-column cells.

    Owner doctrine (2026-08-30): red = unresolved uncertainty and counts
    against the budget; ORANGE = a figure resolved by a lawful recipe
    (back-out, plug, freeze) awaiting true-up — it is the deliver-with-
    flags mechanism working, not a failure, so it does not spend budget.
    Colour is read from the cell itself, the one source of truth."""
    fails = []
    per_sheet = {}
    for ref in set(flags):
        sh, _, coord = ref.partition("!")
        if sh not in wb.sheetnames or not coord:
            continue
        try:
            cell = wb[sh][coord]
            rgb = cell.fill.start_color.rgb
        except Exception:
            continue
        if not (isinstance(rgb, str) and rgb.upper().endswith("FFC7CE")):
            continue                      # orange or unpainted: no cost
        # the budget measures NEGLECT, not disclosure coverage (run-14
        # ruling, the owner's walk-away doctrine): a red the agent
        # INVESTIGATED and documented — where it looked, why the figure
        # is not disclosed — is a delivered finding. Only an UNEXAMINED
        # red (the stale sweep's marker, or no explanation at all)
        # spends budget.
        note = str(cell.comment.text) if cell.comment else ""
        if note and "STALE INPUT" not in note:
            continue                      # adjudicated: a finding
        # tier law (owner ruling): only LOAD-BEARING staleness is
        # neglect — decoration outside the wiring trace is the tier-3
        # sweep's job, not the loop's
        if load_bearing is not None:
            row_m = __import__("re").match(r"^[A-Z]+([0-9]+)$", coord)
            if row_m and (sh, int(row_m.group(1))) not in load_bearing:
                continue
        per_sheet[sh] = per_sheet.get(sh, 0) + 1
    for sheet, nflags in per_sheet.items():
        tcol = year_columns(spec, sheet).get(str(target_year))
        if not tcol or sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        filled = sum(1 for r in range(1, ws.max_row + 1)
                     if ws[f"{tcol}{r}"].value is not None)
        if filled and nflags / filled > FLAG_BUDGET:
            fails.append(f"FLAG BUDGET {sheet}: {nflags}/{filled} "
                         f"({nflags / filled:.0%}) of filled cells hold "
                         f"UNEXAMINED red staleness — investigate each "
                         f"(serve it, or record where you looked and why "
                         f"it is not disclosed); an unexamined red is "
                         f"neglect, not a finding")
    return fails


def sign_absurd_rows(wb, spec, target_year):
    """THE ONE sign-flip detection (owner ruling 2026-08-31: the sign
    change is a mistake TRIPWIRE — the loop investigates each hit and
    verdicts it; freezing is only the terminal state). This single
    predicate feeds the loop's tripwire list, the terminal freeze, and
    the gate, so they can never disagree (run-197 exhibit: the freezer
    and the gate were two implementations and the freezer held 0 of the
    gate's 6 rows). Both actual years are evaluated — a formula-valued
    prior is as real as a hardcoded one.
    -> [(sheet, first_forecast_col, row, fv, pv, tv), ...]"""
    from .evaluator import Evaluator
    ev = Evaluator(wb)
    out = []
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        fcols = forecast_columns(spec, sheet, target_year)
        tcol = year_columns(spec, sheet).get(str(target_year))
        pcol = prior_column(spec, sheet, target_year)
        if not fcols or not tcol or not pcol:
            continue
        f1 = fcols[0]
        ws = wb[sheet]
        for r in range(1, ws.max_row + 1):
            now_v = ws[f"{f1}{r}"].value
            if not (isinstance(now_v, str) and now_v.startswith("=")):
                continue
            tv, pv = ws[f"{tcol}{r}"].value, ws[f"{pcol}{r}"].value
            if isinstance(tv, str) and tv.startswith("="):
                try:
                    tv = ev.cell(sheet, f"{tcol}{r}")
                except Exception:
                    tv = None
            if isinstance(pv, str) and pv.startswith("="):
                try:
                    pv = ev.cell(sheet, f"{pcol}{r}")
                except Exception:
                    pv = None
            if not isinstance(tv, (int, float)) or not isinstance(pv, (int, float)):
                continue
            if tv > AGGREGATE_MIN and pv > AGGREGATE_MIN:
                try:
                    fv = ev.cell(sheet, f"{f1}{r}")
                except Exception:
                    continue
                if isinstance(fv, (int, float)) and fv < 0:
                    out.append((sheet, f1, r, fv, pv, tv))
    return out


def driver_roll(wb, spec, target_year, pre_map, writer_log=None):
    """Gate 4. Forecast columns keep formulas where they had them, and no
    UNADJUDICATED sign-absurd first-forecast value. The assumption freeze
    and the agent's probe-proven holds are the authorized
    formula->hardcode replacements — every freeze is in
    writer_log["frozen"]. A sign-absurd row carrying a loop verdict
    (writer_log["verdicts"]) is adjudicated: reported on _REPORT, not
    refused — an unexamined sign flip is neglect, an examined one is a
    finding (same law as the flag budget)."""
    fails = []
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        fcols = forecast_columns(spec, sheet, target_year)
        tcol = year_columns(spec, sheet).get(str(target_year))
        pcol = prior_column(spec, sheet, target_year)
        if not fcols or not tcol or not pcol:
            continue
        f1 = fcols[0]
        ws = wb[sheet]
        pre = pre_map.get(sheet, {})
        for r in range(1, ws.max_row + 1):
            pre_v = pre.get(f"{f1}{r}")
            now_v = ws[f"{f1}{r}"].value
            if isinstance(pre_v, str) and pre_v.startswith("=") \
                    and not (isinstance(now_v, str) and now_v.startswith("=")):
                # freezes (assumption or terminal sign-absurd) are the
                # authorized replacements; each is in the writer log,
                # orange, and reported
                if any(ln.startswith(f"{sheet}!{f1}{r}:")
                       for ln in (writer_log or {}).get("frozen", [])):
                    continue
                fails.append(f"DRIVER ROLL {sheet}!{f1}{r}: forecast formula "
                             f"replaced by {now_v!r}")
    verdicted = {v.split(":", 1)[0]
                 for v in (writer_log or {}).get("verdicts", [])}
    for (sheet, f1, r, fv, pv, tv) in sign_absurd_rows(wb, spec, target_year):
        if f"{sheet}!{f1}{r}" in verdicted:
            continue
        fails.append(f"DRIVER ROLL {sheet}!{f1}{r}: forecast "
                     f"{fv:,.2f} negative where actuals are "
                     f"positive ({pv:,.2f} -> {tv:,.2f}) — "
                     f"sign-absurd class, UNEXAMINED (the loop "
                     f"must trace it and verdict)")
    return fails


def error_scan(wb, pre_map):
    """New error literals introduced by the run."""
    pre_err = {(s, k) for s, m in pre_map.items() for k, v in m.items()
               if isinstance(v, str) and any(e in v for e in _ERROR_LITERALS)}
    fails = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) \
                        and any(e in c.value for e in _ERROR_LITERALS) \
                        and (ws.title, c.coordinate) not in pre_err:
                    fails.append(f"NEW ERROR {ws.title}!{c.coordinate}: "
                                 f"{c.value[:40]}")
    return fails


def deliver_or_refuse(wb, spec, target_year, pre_map, writer_log,
                      served=None, skip_sheets=("_REPORT", "_SPEC"),
                      pre_values_wb=None, load_bearing=None,
                      pre_formulas_path=None, error_baseline=None):
    """The gate. -> (ok, failures, card). ok=False means the run must NOT
    deliver the workbook as the model — quarantine it with this list.
    pre_formulas_path: the archived pre-update file, loaded lazily to
    EVALUATE pre-update check rows when the values workbook caches
    nothing (manual-calc models cache no values — the run-201 lesson:
    the inherited-break law could never prove ROAFNA's 2024 break was
    the analyst's own, because a data_only load holds neither value nor
    formula)."""
    failures = []
    failures += check_year_headers(wb, spec, target_year)
    failures += magnitude_sweep(wb, spec, target_year,
                                writer_log.get("written", ()), served=served)
    failures += flag_budget(wb, spec, target_year, writer_log.get("flags", ()),
                            load_bearing=load_bearing)
    failures += driver_roll(wb, spec, target_year, pre_map, writer_log)
    failures += error_scan(wb, pre_map)
    tcols = sorted({c for sh in (spec.get("year_axis") or {})
                    for y, c in year_columns(spec, sh).items()
                    if y >= str(target_year)})
    allowed = {(r.split("!")[0], r.split("!")[1]) for r in
               list(writer_log.get("written", ())) +
               [x.split(":")[0] for x in writer_log.get("restatements", ())] +
               [x.split(":")[0] for x in writer_log.get("frozen", ())]}
    bad = clobber_diff(pre_map, wb, tcols, allowed, skip_sheets=skip_sheets)
    failures += [f"CLOBBER {s}!{k}: {a!r} -> {b!r}" for s, k, a, b in bad[:20]]
    card = scorecard(wb, spec, target_year, served=served,
                     flags=writer_log.get("flags", ()))
    # THE OWNER'S LAW (re-instated 2026-08-30 after the run-15 mistake:
    # scoping checks to the target year redefined success instead of
    # achieving it): balance is required for ALL years, actual and
    # forecast alike.
    _pre_fwb = [None]        # archived pre-update formulas, loaded lazily
    for c in card["checks"]:
        if c["status"] != "FAIL":
            continue
        # THE INHERITED-BREAK LAW (CLP-1: ROAFNA 2024 was broken in the
        # analyst's own pre-update model): a check that ALREADY failed
        # the same way before the run is the analyst's standing item —
        # reported, never refused. Making it WORSE is ours and refuses.
        inherited = False
        if pre_values_wb is not None:
            m = __import__("re").match(r"^(.*)!r(\d+) \((\d{4})\)$",
                                       c["name"])
            if m:
                sh, row, yr = m.group(1), int(m.group(2)), m.group(3)
                col = year_columns(spec, sh).get(yr)
                if col and sh in pre_values_wb.sheetnames:
                    pv = pre_values_wb[sh][f"{col}{row}"].value
                    if not isinstance(pv, (int, float)):
                        # no cached value — a data_only load holds no
                        # formulas either, so evaluate the ARCHIVED
                        # pre-update file (lazy, once) instead
                        if pre_formulas_path and _pre_fwb[0] is None:
                            try:
                                import openpyxl
                                _pre_fwb[0] = openpyxl.load_workbook(
                                    pre_formulas_path)
                            except Exception:
                                _pre_fwb[0] = False
                        if _pre_fwb[0]:
                            try:
                                from .evaluator import Evaluator
                                pv = Evaluator(_pre_fwb[0]).cell(
                                    sh, f"{col}{row}")
                            except Exception:
                                pv = None
                    if isinstance(pv, (int, float)) and abs(pv) > 1 \
                            and isinstance(c["got"], (int, float)) \
                            and abs(c["got"]) <= abs(pv) + 1:
                        inherited = True
        if inherited:
            card.setdefault("inherited_breaks", []).append(
                f"{c['name']}: {c['got']} (pre-update already "
                f"failed — the analyst's standing item)")
        else:
            failures.append(f"CHECK {c['name']}: {c['got']} vs {c['expect']}")
    if card["cycles"]:
        failures.append(f"CYCLES: {len(card['cycles'])} circular references "
                        f"{card['cycles'][:5]}")
    # THE ERROR-BASELINE LAW (owner ruling 2026-08-31): errors refuse
    # LOUDEST — but only the errors the update INTRODUCED. Pre-existing
    # ones are the analyst's standing items (run-203: two unflagged
    # zeros made every forecast year #DIV/0! and this gate, blind to
    # EVAL_ERROR, called the model balanced).
    if error_baseline is not None:
        from .errorscan import error_cells, new_errors
        cur = error_cells(wb, spec)
        for s, c, why in new_errors(error_baseline, cur):
            failures.append(f"NEW ERROR {s}!{c}: {why} — this cell "
                            "computed before the update; the update "
                            "broke it (trace_error names the cause)")
        if error_baseline:
            card.setdefault("preexisting_errors", []).extend(
                sorted(f"{s}!{c}" for (s, c) in error_baseline)[:20])
    # THE MOVE-ON LAW (owner ruling 2026-08-31): with every check
    # passing and nothing structural broken, remaining unexamined
    # staleness is the analyst's FINDINGS LIST on _REPORT — reported,
    # never refusing. Neglect still refuses while balance is unmet:
    # moving on is earned by the objectives, never a shortcut past them.
    fb = [f for f in failures if f.startswith("FLAG BUDGET")]
    if fb and len(fb) == len(failures):
        card.setdefault("moveon_reported", []).extend(fb)
        failures = []
    return not failures, failures, card
