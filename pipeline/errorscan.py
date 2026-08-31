"""The error-baseline law (owner ruling 2026-08-31, first CLP delivery).

Original models can carry hidden errors that are not the agent's doing
— so the agent counts the model's evaluation errors BEFORE it starts.
If the count INCREASED after the update, the agent made mistakes: every
NEW erroring cell is a refusal item, traced to its cause. Pre-existing
errors are the analyst's standing items — reported, never refused.

The run-203 lesson this mechanizes: the dash-nil sweep zeroed two
nuclear-capacity inputs UNFLAGGED, every forecast year from 2026 became
#DIV/0!, and the gate — which only refused on FAIL, never on
EVAL_ERROR — called the model balanced. Errors must refuse loudest,
relative to the baseline.
"""
from .checks import year_columns
from .evaluator import Evaluator


def error_cells(wb, spec, max_row=300):
    """Evaluate every formula cell in every year column of every axis
    sheet. -> {(sheet, coord): first line of the error}. Deterministic;
    one Evaluator instance so the walk is cached."""
    ev = Evaluator(wb)
    out = {}
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        for col in year_columns(spec, sheet).values():
            for r in range(1, min(ws.max_row, max_row) + 1):
                v = ws[f"{col}{r}"].value
                if not (isinstance(v, str) and v.startswith("=")):
                    continue
                try:
                    ev.cell(sheet, f"{col}{r}")
                except Exception as e:
                    out[(sheet, f"{col}{r}")] = str(e).splitlines()[0][:80]
    return out


def new_errors(baseline, current):
    """Errors the update INTRODUCED (the agent's fault, refusal items).
    -> [(sheet, coord, why)] sorted."""
    return sorted((s, c, why) for (s, c), why in current.items()
                  if (s, c) not in baseline)
