"""Stage 4: the integrity gate. All checks must pass or delivery is blocked."""
from .evaluator import Evaluator


def run_checks(wb, spec, staging, cfg, pre_map, allowed_cells):
    from . import workbook
    ev = Evaluator(wb)
    results, failures = [], []

    def chk(name, sheet, coord, expect, tol=None):
        tol = cfg["conventions"]["rounding_tolerance"] if tol is None else tol
        try:
            got = ev.cell(sheet, coord)
        except Exception as e:
            failures.append(f"{name}: EVAL ERROR {e} (needs Excel recalc)")
            results.append((name, None, expect, "EVAL_ERROR"))
            return
        ok = isinstance(got, (int, float)) and abs(got - expect) <= tol
        results.append((name, got, expect, "PASS" if ok else "FAIL"))
        if not ok:
            failures.append(f"{name} [{sheet}!{coord}]: got {got} expect {expect}")

    # 1. built-in check rows (balance checks etc.) for EVERY year column
    for c in spec.get("check_rows", []):
        axis = spec["year_axis"].get(c["sheet"], {})
        for year, col in (axis.get("columns") or {}).items():
            chk(f"check row {c['sheet']}!r{c['row']} ({year})", c["sheet"],
                f"{col}{c['row']}", c.get("expect", 0), tol=0.01 if c.get("expect", 0) == 0 else None)

    # 2. tie-out anchors: model cell must equal the disclosed figure exactly
    for a in spec.get("tie_out_anchors", []):
        if a.get("expected") is not None:
            chk(f"anchor {a['name']}", a["sheet"], a["cell"], a["expected"])

    # 3. no formula clobbering outside the target column
    bad = workbook.clobber_diff(pre_map, wb, spec.get("_target_cols", []),
                                allowed_cells, skip_sheets=spec.get("_report_sheets", ["_REPORT"]))
    if bad:
        failures.append(f"CLOBBER: {len(bad)} cells changed outside target column: {bad[:10]}")

    # 4. no error literals introduced
    pre_errors = {(s, k) for s, m in pre_map.items() for k, v in m.items()
                  if isinstance(v, str) and any(e in v for e in ("#REF!", "#DIV/0!", "#VALUE!"))}
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and any(e in c.value for e in ("#REF!", "#DIV/0!", "#VALUE!")):
                    if (ws.title, c.coordinate) not in pre_errors:
                        failures.append(f"NEW ERROR CELL {ws.title}!{c.coordinate}: {c.value[:50]}")
    return results, failures
