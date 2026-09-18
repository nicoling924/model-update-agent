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
                 pre_formulas_wb=None, check_rows=(), forecast_col=None):
    """Plan first-forecast holds from the pre-update snapshot.

    A backward-linked percentage assumption is frozen at the first forecast
    period's pre-update value.  Explicit one-off zero holds are handled by
    hold_oneoff_forecasts(); later forecast formulas remain live.  Read-only —
    apply_freezes() writes.
    pre_formulas_wb: the archived pre-update workbook (formulas) —
    manual-calc models cache NO values, so the pre-update value is
    COMPUTED when the cache is empty (the fourth appearance of the
    no-cached-values disease; without it a CLP-style model silently
    froze nothing and every growth assumption rebased)."""
    plans = []
    protected = set()
    for item in check_rows or ():
        if isinstance(item, dict):
            sh, row = item.get("sheet"), item.get("row")
            if sh is not None and isinstance(row, int):
                protected.add((sh, row))
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            protected.add((item[0], item[1]))
        elif isinstance(item, str) and "!" in item:
            sh, row = item.rsplit("!", 1)
            if row.isdigit():
                protected.add((sh, int(row)))
    pre_ev = [None]

    def _pre_value(sn, coord):
        v = pre_wb[sn][coord].value if sn in pre_wb.sheetnames else None
        if isinstance(v, (int, float)):
            return v
        if pre_formulas_wb is not None:
            # A missing cached value is not evidence of zero.  Only evaluate
            # when the authoritative pre-update formula workbook actually
            # contains a formula or hardcoded value at this coordinate.
            raw = (pre_formulas_wb[sn][coord].value
                   if sn in pre_formulas_wb.sheetnames else None)
            if raw in (None, ""):
                return None
            if pre_ev[0] is None:
                from .evaluator import Evaluator
                pre_ev[0] = Evaluator(pre_formulas_wb)
            try:
                v = pre_ev[0].cell(sn, coord)
                if pre_ev[0].cycles:
                    return None
            except Exception:
                return None
            if isinstance(v, (int, float)):
                return v
        return None

    for sn in sheets:
        if sn not in wb.sheetnames or sn not in pre_wb.sheetnames:
            continue
        ws = wb[sn]
        for row in range(1, ws.max_row + 1):
            if (sn, row) in protected:
                continue
            col = forecast_col if forecast_col is not None else target_col + 1
            c = ws.cell(row=row, column=col)
            f = c.value
            # Do not ask the evaluator about later forecast columns: the
            # owner exception is deliberately limited to the next period.
            pre = _pre_value(sn, c.coordinate)
            if not isinstance(pre, (int, float)):
                continue                # absent, unresolved, or circular
            if not (isinstance(f, str) and f.startswith("=")):
                continue
            if "%" not in (c.number_format or ""):
                continue
            if not _refs_backward(f, target_col, row):
                continue
            plans.append({"sheet": sn, "coord": c.coordinate,
                          "oldFormula": f, "value": round(pre, 6),
                          "reason": "assumption_freeze"})
    return plans


def hold_oneoff_forecasts(wb, pre_wb, spec, target_year, sheet, row,
                          writer, because):
    """Hold explicitly classified one-off zero forecasts at zero.

    ``because`` is the brain's one-off classification; code supplies only
    structural proof.  A zero is eligible when its original forecast cell is
    a known zero and is either a constant/hardcode or an event-carry formula
    whose references stay on this row and sheet.  The original prior actual
    must itself be a numeric/constant input, which excludes aggregate/output
    rows and accounting wiring.  Missing, cyclic, nonzero, and cross-row
    formulas remain live.
    """
    if not isinstance(because, str) or not because.strip():
        return []
    if sheet not in wb.sheetnames or sheet not in pre_wb.sheetnames:
        return []
    axis = (spec.get("year_axis") or {}).get(sheet) or {}
    columns = axis.get("columns") or axis.get("cols") or {}
    if not columns:
        return []
    from .checks import prior_column
    from .evaluator import Evaluator

    def original_value(coord):
        raw = pre_wb[sheet][coord].value
        if raw in (None, ""):
            return None, False
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw), True
        if not (isinstance(raw, str) and raw.startswith("=")):
            return None, False
        try:
            # A fresh evaluator keeps a cycle found in one candidate from
            # poisoning the known-value check for later candidates.
            pre_ev = Evaluator(pre_wb)
            value = pre_ev.cell(sheet, coord)
        except Exception:
            return None, False
        if getattr(pre_ev, "cycles", None):
            return None, False
        return (float(value), True) if isinstance(value, (int, float)) \
            and not isinstance(value, bool) else (None, False)

    def constant_or_event_formula(raw, own_row):
        if not (isinstance(raw, str) and raw.startswith("=")):
            return False
        # Reuse the mapping contract for reference-free arithmetic.  A bare
        # ``refs == []`` test would incorrectly bless names, functions, and
        # external references as constants.
        from openpyxl.formula.tokenizer import Tokenizer
        from .mapping import is_constant_expression
        try:
            tokens = Tokenizer(raw).items
        except Exception:
            return False
        ranges = [t.value for t in tokens
                  if t.type == "OPERAND" and t.subtype == "RANGE"]
        if not ranges:
            return is_constant_expression(raw)
        # Every non-numeric operand must be a complete A1 cell on this sheet
        # and on the event row.  Functions are allowed when all their cell
        # operands satisfy that proof; names/external references are rejected
        # by the full match and sheet check.
        full = re.compile(_A1.pattern + r"$")
        for value in ranges:
            m = full.fullmatch(value)
            qualifier = (m.group(1) or "").strip("'").replace("''", "'") if m else None
            if (m is None or (qualifier and qualifier != sheet)
                    or int(m.group(3)) != own_row):
                return False
        return True

    pcol = prior_column(spec, sheet, target_year)
    if not pcol:
        return []
    prior_raw = pre_wb[sheet][f"{pcol}{row}"].value
    prior_value, prior_known = original_value(f"{pcol}{row}")
    if not prior_known or not (
            isinstance(prior_raw, (int, float)) and not isinstance(prior_raw, bool)
            or constant_or_event_formula(prior_raw, row) and not list(_A1.finditer(prior_raw))):
        return []

    plans = []
    for year, col in sorted(columns.items(), key=lambda item: str(item[0])):
        if not str(year).isdigit() or int(year) <= int(target_year):
            continue
        coord = f"{col}{row}"
        raw = pre_wb[sheet][coord].value
        ref = f"{sheet}!{coord}"
        if writer is not None and ref in getattr(writer, "forecast_holds", {}):
            continue
        value, known = original_value(coord)
        if not known or abs(value) > 1e-9:
            continue
        if not (isinstance(raw, (int, float)) and not isinstance(raw, bool)
                or constant_or_event_formula(raw, row)):
            continue
        # The live workbook may have been rewritten by mapping/roll-forward
        # since the snapshot.  Never overwrite a now-different output formula
        # merely because the archived value was zero.
        live_raw = wb[sheet][coord].value
        if not (isinstance(live_raw, (int, float)) and not isinstance(live_raw, bool)
                or constant_or_event_formula(live_raw, row)):
            continue
        plans.append({
            "sheet": sheet,
            "coord": coord,
            "oldFormula": raw,
            "value": 0.0,
            "reason": "zero_forecast_hold",
            "proof": (f"explicit one-off classification: {because.strip()}; "
                      "original forecast evaluates to zero and is an independent "
                      "constant/event-carry input; prior actual is constant-only"),
        })
    lines = apply_freezes(wb, plans, writer=writer)
    if writer is not None and lines:
        writer.log.setdefault("frozen", []).extend(lines)
    return lines


def apply_freezes(wb, plans, writer=None):
    """Hardcode each planned cell at its pre-update value, orange fill.
    Returns report lines: 'Sheet!C5: frozen at 0.30 — was =U5'."""
    from openpyxl.styles import PatternFill
    fill = PatternFill("solid", fgColor=ORANGE)
    lines = []
    authorized = {"assumption_freeze", "zero_forecast_hold"}
    for p in plans:
        if p.get("reason") not in authorized:
            continue
        c = wb[p["sheet"]][p["coord"]]
        if writer is not None:
            # through the writer, so every law of the run applies (2026-09-14)
            note = p.get("proof") if p.get("reason") == "zero_forecast_hold" else None
            if not writer.write(p["sheet"], p["coord"], p["value"], trusted=True,
                                force_lock=True, over_formula=True, flag="blue",
                                note=note):
                continue
        else:
            c.value = p["value"]
        if c.value != p["value"]:
            raise RuntimeError("freeze read-back mismatch %s!%s" %
                               (p["sheet"], p["coord"]))
        if writer is not None:
            if not hasattr(writer, "forecast_holds"):
                writer.forecast_holds = {}
            writer.forecast_holds[f"{p['sheet']}!{p['coord']}"] = p["value"]
        c.fill = fill
        lines.append("%s!%s: frozen at %s — was %s"
                     % (p["sheet"], p["coord"], p["value"], p["oldFormula"]))
    return lines


# freeze_sign_absurd RETIRED (owner 2026-09-01, run-204 autopsy):
# hardcoding forecast formulas at pre-update values broke the model's
# self-balancing wiring in every forecast year. Sign-flips are now
# INVESTIGATION items; unresolved ones stay LIVE, red, reported.
