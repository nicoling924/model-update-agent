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

ORANGE = "FFC000"
# A1 refs, optionally sheet-qualified; group(1)=sheet or None
_A1 = re.compile(r"(?:('?[^'!=,()*/+\-]{1,40}'?)!)?\$?([A-Z]{1,3})\$?"
                 r"([0-9]{1,5})")


def _refs_backward(formula, target_col, own_row):
    """True if any SAME-SHEET reference points at target_col or earlier.
    Cross-sheet refs are ignored (their column letters live on another
    axis). A reference to the cell's own row in an earlier column is the
    classic chain; any earlier-column ref qualifies."""
    for m in _A1.finditer(formula):
        if m.group(1):                      # sheet-qualified: another axis
            continue
        if column_index_from_string(m.group(2)) <= target_col:
            return True
    return False


def plan_freezes(wb, pre_wb, sheets, target_col, horizon=8, max_row=300):
    """Scan forecast columns (target_col+1 .. +horizon) of the given
    sheets; return [{sheet, coord, oldFormula, value}] for every cell
    the law freezes. Read-only — apply_freezes() writes."""
    plans = []
    for sn in sheets:
        if sn not in wb.sheetnames or sn not in pre_wb.sheetnames:
            continue
        ws, pw = wb[sn], pre_wb[sn]
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
                pre = pw.cell(row=row, column=col).value
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


def freeze_sign_absurd(wb, spec, target_year, pre_values_wb, writer,
                       pre_formulas_path=None):
    """TERMINAL state of the sign-flip tripwire (owner ruling 2026-08-31:
    the sign change is a mistake DETECTOR — the loop investigates each
    hit first and verdicts it on _REPORT; only what remains unresolved
    lands here, so nonsense never ships as a live forecast). Consumes
    gate.sign_absurd_rows — the ONE detection — so the freezer and the
    gate can never disagree (run-197 exhibit: as two implementations,
    the freezer held 0 of the gate's 6 rows).
    - JUSTIFIED rows stand as the analyst's view: never frozen.
    - Unresolved rows with a pre-update cached value: held there,
      orange, in writer.log["frozen"] (the gate's authorized
      replacement), verdict UNRESOLVED recorded.
    - Unresolved rows with NO cached value (manual-calc models never
      cache — proven on CLP, where every forecast cache is None): the
      pre-update value is COMPUTED by evaluating the archived pre-update
      workbook's own formulas (pre_formulas_path). Only when that too
      fails is the honest terminal red + a SUSPICIOUS verdict —
      reported, never silently passed."""
    from .gate import sign_absurd_rows
    from openpyxl.styles import PatternFill
    from openpyxl.comments import Comment
    fill = PatternFill("solid", fgColor=ORANGE)
    red = PatternFill("solid", fgColor="FFC7CE")
    verdicts = writer.log.setdefault("verdicts", [])
    pre_ev = [None]          # lazy: load the archive only on cache miss

    def _pre_value(sheet, coord):
        v = (pre_values_wb[sheet][coord].value
             if sheet in pre_values_wb.sheetnames else None)
        if isinstance(v, (int, float)):
            return v
        if pre_formulas_path:
            if pre_ev[0] is None:
                import openpyxl
                from .evaluator import Evaluator
                pre_ev[0] = Evaluator(
                    openpyxl.load_workbook(pre_formulas_path))
            try:
                v = pre_ev[0].cell(sheet, coord)
            except Exception:
                return None
            if isinstance(v, (int, float)):
                return v
        return None

    n = 0
    for (sheet, f1, r, fv, pv, tv) in sign_absurd_rows(wb, spec, target_year):
        key = f"{sheet}!{f1}{r}"
        if any(v.startswith(key + ":") and "JUSTIFIED" in v
               for v in verdicts):
            continue
        c = wb[sheet][f"{f1}{r}"]
        hold = _pre_value(sheet, f"{f1}{r}")
        if not isinstance(hold, (int, float)):
            c.fill = red
            c.comment = Comment(
                "SIGN-ABSURD, UNRESOLVED: this forecast computes %.1f "
                "where both actual years are positive (%.1f -> %.1f) — "
                "usually a mis-rolled upstream input. No pre-update "
                "cached value exists to hold it at (manual-calc model). "
                "ANALYST MUST REVIEW." % (fv, pv, tv),
                "Model Update Agent")
            writer.log["flags"].append(key)
            verdicts.append(
                f"{key}: SUSPICIOUS — sign-absurd {fv:,.1f} unresolved by "
                f"the loop and no pre-update cached value to hold; "
                f"analyst review")
            n += 1
            continue
        old_f = c.value
        c.value = round(hold, 6)
        c.fill = fill
        c.comment = Comment(
            "SIGN-ABSURD FREEZE (terminal): this forecast computed %.1f "
            "where both actual years are positive — upstream inputs are "
            "incomplete. Held at the pre-update value; restore the "
            "formula (%s) once the inputs are trued up."
            % (fv, old_f), "Model Update Agent")
        writer.log.setdefault("frozen", []).append(
            "%s!%s%d: frozen at %s — was %s (sign-absurd %.1f)"
            % (sheet, f1, r, round(hold, 4), old_f, fv))
        verdicts.append(
            f"{key}: UNRESOLVED — held at pre-update {round(hold, 4)} "
            f"(computed {fv:,.1f}); restore the formula once inputs are "
            f"trued up")
        n += 1
    return n
