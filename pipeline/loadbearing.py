"""The load-bearing trace (owner ruling, CLP campaign 2026-08-31).

"What affects the main statement" is not a judgment call — the model
declares it. Starting from the spec's key rows and check rows, walk the
target-column formulas backward: every (sheet, row) the walk reaches is
LOAD-BEARING — it must be served or adjudicated, and staleness there is
neglect. Everything OUTSIDE the trace is tier-3 decoration: never
searched, backed out at the group's growth, orange, awaiting true-up.

This is what stops a three-storey model (segments -> drivers -> model)
from starving: effort follows the wiring, and the wiring is read, not
guessed. Deterministic; no LLM anywhere.
"""
import re

_QREF = re.compile(r"'([^']{1,60})'!\$?([A-Z]{1,3})\$?([0-9]{1,5})"
                   r"(?::\$?([A-Z]{1,3})\$?([0-9]{1,5}))?")
_BREF = re.compile(r"(?<![A-Za-z0-9_'!])([A-Za-z_][A-Za-z0-9_.]{0,30})!"
                   r"\$?([A-Z]{1,3})\$?([0-9]{1,5})"
                   r"(?::\$?([A-Z]{1,3})\$?([0-9]{1,5}))?")
_LREF = re.compile(r"(?<![A-Za-z0-9_!$])\$?([A-Z]{1,3})\$?([0-9]{1,5})"
                   r"(?::\$?([A-Z]{1,3})\$?([0-9]{1,5}))?")
RANGE_CAP = 200


def _rows_of(r1, r2):
    a, b = int(r1), int(r2 or r1)
    if b < a:
        a, b = b, a
    if b - a > RANGE_CAP:
        b = a + RANGE_CAP
    return range(a, b + 1)


def _refs(formula, own_sheet):
    """Yield (sheet, row) for every reference in the formula, ranges
    expanded row-wise."""
    out = []
    rest = formula

    def eat(m, sheet):
        out.extend((sheet, r) for r in _rows_of(m.group(3) if sheet != own_sheet or True else 0, 0))

    for m in _QREF.finditer(rest):
        for r in _rows_of(m.group(3), m.group(5)):
            out.append((m.group(1), r))
    rest = _QREF.sub(" ", rest)
    for m in _BREF.finditer(rest):
        for r in _rows_of(m.group(3), m.group(5)):
            out.append((m.group(1), r))
    rest = _BREF.sub(" ", rest)
    for m in _LREF.finditer(rest):
        for r in _rows_of(m.group(2), m.group(4)):
            out.append((own_sheet, r))
    return out


def trace(wb, spec, target_year, max_depth=15, max_cells=20000):
    """-> {(sheet, row), ...} reachable from key_rows + check_rows."""
    from .checks import forecast_columns, year_columns
    # walk the FIRST FORECAST column: the target column holds typed
    # actuals after mark-to-actual (no formulas to walk), but the
    # forecast column keeps the model's wiring intact — and wiring is
    # row-wise: the rows a forecast formula consumes are the rows whose
    # actuals matter
    tcol_by = {}
    for sheet in (spec.get("year_axis") or {}):
        fc = forecast_columns(spec, sheet, target_year)
        c = (fc[0] if fc
             else year_columns(spec, sheet).get(str(target_year)))
        if c and sheet in wb.sheetnames:
            tcol_by[sheet] = c
    seeds = [(k["sheet"], int(k["row"]))
             for k in (spec.get("key_rows") or []) +
                      (spec.get("check_rows") or [])
             if k.get("sheet") in tcol_by]
    seen = set(seeds)
    frontier = list(seeds)
    for _ in range(max_depth):
        if not frontier or len(seen) > max_cells:
            break
        nxt = []
        for sheet, row in frontier:
            tcol = tcol_by.get(sheet)
            if not tcol:
                continue
            v = wb[sheet][f"{tcol}{row}"].value
            if not (isinstance(v, str) and v.startswith("=")):
                continue
            for ref in _refs(v, sheet):
                sh = ref[0]
                # tolerate quoted names the workbook spells with spaces
                if sh not in tcol_by:
                    match = next((s for s in tcol_by
                                  if s.strip().lower() == sh.strip().lower()),
                                 None)
                    if match is None:
                        continue
                    ref = (match, ref[1])
                if ref not in seen:
                    seen.add(ref)
                    nxt.append(ref)
        frontier = nxt
    return seen
