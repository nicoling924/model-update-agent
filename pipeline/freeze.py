"""The assumption freeze (owner ruling 2026-08-30).

A forecast ASSUMPTION wired to the past silently rebases when the past
becomes actual: 2026E growth `=U5` meant "hold my 30%" while U5 was an
estimate — the moment 2025 is marked to actual it becomes "copy the 70%
that actually happened", destroying the analyst's view without any 2026
cell being touched.

The law, both signatures required:
  (a) the cell is percentage-formatted (assumption rows carry % format;
      levels in RMB mn do not), AND
  (b) its formula references the newly actual column or EARLIER on the
      same sheet (it inherits from the past).
A % cell computed within its own column (=V7/V4 — a margin OUTPUT) is
wiring and is never frozen. Chains inherit the freeze: W5=V5 stays a
formula and correctly reads the frozen value.

Frozen = hardcoded at its PRE-UPDATE value, orange fill, and listed with
its old formula so restoring the live link is one paste. Freeze every
qualifier by default; the analyst restores the ones they deliberately
want live.
"""
import re

from openpyxl.utils import column_index_from_string

ORANGE = "BDD7EE"   # frozen forecast inputs are BLUE (owner 2026-09-07):
                    # the one forecast-year colour, distinct from red
                    # (unsure) and orange (backed out) in the actual column
# A1 refs, optionally sheet-qualified; group(1)=sheet or None
_A1 = re.compile(r"(?:('?[^'!=,()*/+\-]{1,40}'?)!)?\$?([A-Z]{1,3})\$?"
                 r"([0-9]{1,5})")


def _refs_backward(formula, target_col, own_row):
    """True only when the formula inherits PURELY from the past: every
    same-sheet reference points at target_col or earlier, and at least
    one exists. A ratio touching its own column (=AJ31/AI31-1, a growth
    DISPLAY) is wiring, never an assumption — the owner's law: only
    cells that would silently rebase onto the new actual are frozen."""
    saw_back = False
    for m in _A1.finditer(formula):
        if m.group(1):                      # sheet-qualified: another axis
            continue
        if column_index_from_string(m.group(2)) <= target_col:
            saw_back = True
        else:
            return False                    # touches its own/later column
    return saw_back


def plan_freezes(wb, pre_wb, sheets, target_col, horizon=8, max_row=300,
                 pre_formulas_wb=None):
    """Scan forecast columns (target_col+1 .. +horizon) of the given
    sheets; return [{sheet, coord, oldFormula, value}] for every cell
    the law freezes. Read-only — apply_freezes() writes.
    pre_formulas_wb: the archived pre-update workbook (formulas) —
    manual-calc models cache NO values, so the pre-update value is
    COMPUTED when the cache is empty (the fourth appearance of the
    no-cached-values disease; without it a CLP-style model silently
    froze nothing and every growth assumption rebased)."""
    plans = []
    pre_ev = [None]

    def _pre_value(sn, coord):
        v = pre_wb[sn][coord].value if sn in pre_wb.sheetnames else None
        if isinstance(v, (int, float)):
            return v
        if pre_formulas_wb is not None:
            if pre_ev[0] is None:
                from .evaluator import Evaluator
                pre_ev[0] = Evaluator(pre_formulas_wb)
            try:
                v = pre_ev[0].cell(sn, coord)
            except Exception:
                return None
            if isinstance(v, (int, float)):
                return v
        return None

    for sn in sheets:
        if sn not in wb.sheetnames or sn not in pre_wb.sheetnames:
            continue
        ws = wb[sn]
        for row in range(1, min(ws.max_row, max_row) + 1):
            for col in range(target_col + 1, target_col + 1 + horizon):
                c = ws.cell(row=row, column=col)
                f = c.value
                if not (isinstance(f, str) and f.startswith("=")):
                    continue
                if "%" not in (c.number_format or ""):
                    continue
                if not _refs_backward(f, target_col, row):
                    continue
                pre = _pre_value(sn, c.coordinate)
                if not isinstance(pre, (int, float)):
                    continue                # no pre-update value to hold
                plans.append({"sheet": sn, "coord": c.coordinate,
                              "oldFormula": f, "value": round(pre, 6)})
    return plans


def apply_freezes(wb, plans):
    """Hardcode each planned cell at its pre-update value, orange fill.
    Returns report lines: 'Sheet!C5: frozen at 0.30 — was =U5'."""
    from openpyxl.styles import PatternFill
    fill = PatternFill("solid", fgColor=ORANGE)
    lines = []
    for p in plans:
        c = wb[p["sheet"]][p["coord"]]
        c.value = p["value"]
        c.fill = fill
        lines.append("%s!%s: frozen at %s — was %s"
                     % (p["sheet"], p["coord"], p["value"], p["oldFormula"]))
    return lines


# freeze_sign_absurd RETIRED (owner 2026-09-01, run-204 autopsy):
# hardcoding forecast formulas at pre-update values broke the model's
# self-balancing wiring in every forecast year. Sign-flips are now
# INVESTIGATION items; unresolved ones stay LIVE, red, reported.
