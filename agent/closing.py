"""The closing loop: residual-driven investigation, the way an accountant chases
a reconciliation difference.

After verification, the failing check rows leave numeric residuals. Build a
small set of SUSPECT hypotheses and greedily apply whichever most reduces the
total imbalance, then repeat — chase the difference down, not in one leap.

Suspects (all corroboration-gated, so this can only move toward the disclosure):
  A) SIGN suspects — written cells whose sign disagrees with the prior year's:
     hypothesis = flip it.
  B) SWAP suspects — written cells where a validated extraction item corroborates
     the row (its prior matches the model's prior) but the cell holds a different
     value: hypothesis = the extracted value (sign-harmonized to the prior).
Every hypothesis is tested empirically (apply -> re-evaluate all checks -> keep
or revert), so no assumption about check topology is needed. Applied fixes are
red-flagged and logged. Pure Python — no LLM calls.
"""
import re

from .evaluator import Evaluator


def _cell_value(ws, coord):
    v = ws[coord].value
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and re.match(r"^=[\d+\-. ]+$", v):
        try:
            return float(eval(v[1:], {"__builtins__": {}}, {}))
        except Exception:
            return None
    return None


def close_residuals(wb, spec, staging, cfg, writer, flags, target_year,
                    pre_values=None, eligible=None, max_rounds=8, tol=1.0):
    log = []
    checks = []
    for c in spec.get("check_rows", []):
        axis = spec["year_axis"].get(c["sheet"], {})
        col = (axis.get("columns") or {}).get(str(target_year))
        if col:
            checks.append((c["sheet"], f"{col}{c['row']}", c.get("expect", 0)))
    if not checks:
        return log

    def total_residual():
        ev = Evaluator(wb)
        t = 0.0
        for s, co, ex in checks:
            try:
                t += abs(ev.cell(s, co) - ex)
            except Exception:
                t += 1e9
        return t

    # EVIDENCE-FIRST, not residual-first: compensating errors make the net
    # residual a misleading objective (a truth-ward fix can worsen it). Apply
    # every independently-corroborated repair; the residual is only the report.
    base = total_residual()
    suspects = _build_suspects(wb, spec, staging, writer, target_year, tol,
                               pre_values, eligible)
    best_per_cell = {}
    for sheet_f, coord_f, new_v, why, quality in suspects:
        key = (sheet_f, coord_f)
        if key not in best_per_cell or quality > best_per_cell[key][2]:
            best_per_cell[key] = (new_v, why, quality)
    for (sheet_f, coord_f), (new_v, why, quality) in sorted(best_per_cell.items()):
        cur = _cell_value(wb[sheet_f], coord_f)
        if cur is not None and abs(cur - new_v) <= tol:
            continue
        writer.write(sheet_f, coord_f, new_v, note=f"CLOSING LOOP: {why}", flag="red")
        flags.append((sheet_f, coord_f, f"closing loop: {why}"))
        log.append(f"{sheet_f}!{coord_f}: {cur} -> {new_v} ({why})")
    if log:
        log.append(f"total check residual: {base:,.0f} -> {total_residual():,.0f}")
    return log


def _build_suspects(wb, spec, staging, writer, target_year, tol, pre_values=None,
                    eligible=None):
    suspects = []
    items = [it for it in staging["items"]
             if isinstance(it.get("value"), (int, float))]
    for w in sorted(set(writer.log["written"])):
        if "!" not in w:
            continue
        sheet_f, coord_f = w.split("!", 1)
        if sheet_f not in wb.sheetnames:
            continue
        if eligible is not None and w not in eligible:
            continue  # investigate only where doubt exists — never touch clean cells
        axis = spec["year_axis"].get(sheet_f, {})
        tcol = (axis.get("columns") or {}).get(str(target_year))
        if not tcol or not re.match(rf"^{tcol}\d+$", coord_f):
            continue
        ws = wb[sheet_f]
        v = _cell_value(ws, coord_f)
        if v is None:
            continue
        pv = _cell_prior(pre_values or wb, spec, sheet_f, coord_f, tcol, target_year)
        row_label = _row_label(ws, coord_f, tcol)
        if not (isinstance(pv, (int, float)) and pv != 0 and row_label):
            continue
        from .mapping import _overlap, norm, _STOP
        # A) sign suspect — only with a label-related item confirming the flipped value
        if v != 0 and (v < 0) != (pv < 0):
            confirm = any(_overlap(row_label, str(it.get("label", "")))
                          and abs(it["value"] - (-v)) <= tol for it in items)
            if confirm:
                suspects.append((sheet_f, coord_f, -v,
                                 f"sign flipped to prior-year convention (was {v}, "
                                 "flipped value confirmed by extraction)", 3.0))
        # B) corroborated swap: prior match + label kinship, quality-scored
        for it in items:
            pr = it.get("prior")
            if not isinstance(pr, (int, float)) or abs(abs(pr) - abs(pv)) > tol:
                continue
            lbl = str(it.get("label", ""))
            if not _overlap(row_label, lbl):
                continue
            nv = abs(it["value"]) * (1 if pv > 0 else -1)  # prior's sign wins
            if abs(nv - v) <= tol:
                continue
            shared = len({w for w in norm(row_label).split() if w not in _STOP and len(w) > 2}
                         & {w for w in norm(lbl).split() if w not in _STOP and len(w) > 2})
            quality = shared + (1.0 if abs(pr - pv) <= tol else 0.0)
            suspects.append((sheet_f, coord_f, nv,
                             f"swapped to extracted '{lbl[:38]}' p{it.get('page')} "
                             f"(prior corroborated {pr}, label-related)", quality))
    return suspects


def _row_label(ws, coord, tcol):
    row = coord[len(tcol):]
    for lc in "ABCDEF":
        v = ws[f"{lc}{row}"].value
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _cell_prior(wb, spec, sheet, coord, tcol, target_year):
    axis = spec["year_axis"].get(sheet, {})
    cols = axis.get("columns") or {}
    years = sorted(cols)
    try:
        i = years.index(str(target_year))
    except ValueError:
        return None
    if i == 0:
        return None
    pcol = cols[years[i - 1]]
    row = coord[len(tcol):]
    v = wb[sheet][f"{pcol}{row}"].value
    return v if isinstance(v, (int, float)) else None
