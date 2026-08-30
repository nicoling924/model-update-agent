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


def flag_budget(wb, spec, target_year, flags):
    """Gate 3. Flags per sheet vs filled target-column cells."""
    fails = []
    per_sheet = {}
    for ref in flags:
        sh = ref.split("!", 1)[0]
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
                         f"({nflags / filled:.0%}) of filled cells flagged — "
                         f"the run failed this sheet, flags are not a waiver")
    return fails


def driver_roll(wb, spec, target_year, pre_map, writer_log=None):
    """Gate 4. Forecast columns keep formulas where they had them, and no
    sign-absurd first-forecast value (negative where prior and target
    actuals are both positive aggregates). The assumption freeze (owner
    ruling 2026-08-30) is the one authorized formula->hardcode
    replacement — every freeze is in writer_log["frozen"]."""
    from .evaluator import Evaluator
    fails = []
    ev = Evaluator(wb)
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
                # the assumption freeze (owner ruling 2026-08-30) is the
                # ONE authorized formula->hardcode replacement; every
                # freeze is in the writer log, orange, and reported
                if any(ln.startswith(f"{sheet}!{f1}{r}:")
                       for ln in (writer_log or {}).get("frozen", [])):
                    continue
                fails.append(f"DRIVER ROLL {sheet}!{f1}{r}: forecast formula "
                             f"replaced by {now_v!r}")
                continue
            if not (isinstance(now_v, str) and now_v.startswith("=")):
                continue
            tv, pv = ws[f"{tcol}{r}"].value, ws[f"{pcol}{r}"].value
            if isinstance(tv, str) and tv.startswith("="):
                try:
                    tv = ev.cell(sheet, f"{tcol}{r}")
                except Exception:
                    tv = None
            if not isinstance(tv, (int, float)) or not isinstance(pv, (int, float)):
                continue
            if tv > AGGREGATE_MIN and pv > AGGREGATE_MIN:
                try:
                    fv = ev.cell(sheet, f"{f1}{r}")
                except Exception:
                    continue
                if isinstance(fv, (int, float)) and fv < 0:
                    fails.append(f"DRIVER ROLL {sheet}!{f1}{r}: forecast "
                                 f"{fv:,.2f} negative where actuals are "
                                 f"positive ({pv:,.2f} -> {tv:,.2f}) — "
                                 f"sign-absurd class")
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
                      served=None, skip_sheets=("_REPORT", "_SPEC")):
    """The gate. -> (ok, failures, card). ok=False means the run must NOT
    deliver the workbook as the model — quarantine it with this list."""
    failures = []
    failures += check_year_headers(wb, spec, target_year)
    failures += magnitude_sweep(wb, spec, target_year,
                                writer_log.get("written", ()), served=served)
    failures += flag_budget(wb, spec, target_year, writer_log.get("flags", ()))
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
    ty = str(target_year)
    for c in card["checks"]:
        if c["status"] == "FAIL" and c["year"] == ty:
            failures.append(f"CHECK {c['name']}: {c['got']} vs {c['expect']}")
    if card["cycles"]:
        failures.append(f"CYCLES: {len(card['cycles'])} circular references "
                        f"{card['cycles'][:5]}")
    return not failures, failures, card
