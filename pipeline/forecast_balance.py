"""Forecast-year balance (the owner's law: balance is for ALL years).

After mark-to-actual, forecast BS lines rebase onto the new actuals
through their drivers — but the BS only ties if every line's year-on-
year movement is captured in the cash-flow construction (cash comes off
the CF). Movements with no CF counterpart open a gap. The owner's
effort ladder (ruling 2026-08-30):

1. AUDIT (here, deterministic): per forecast year, the gap and the
   full BS-movement table — the evidence for attribution.
2. ATTRIBUTE (the loop's real effort): place each uncaptured movement
   into a DESIGNED CF input row (`place_flow`) as a traceable formula
   =-(V56-U56), orange. Placement targets are the model's own typed
   input cells inside the CF block — never a formula, never a driver.
3. LAST-RESORT PLUG (here, deterministic): only the residue that
   genuine attribution could not place — one per year, into the CF's
   designed catch-all input row, orange with the honest note, RED when
   large. A plug is an admission, not a fix; it keeps the model
   deliverable while the analyst rules.
"""
import re

from openpyxl.comments import Comment
from openpyxl.utils import column_index_from_string, get_column_letter

_CF_START = re.compile(r"cash\s*flow", re.IGNORECASE)
_OTHERS = re.compile(r"^(others?|其他|其它)\b", re.IGNORECASE)
PLUG_RED_SHARE = 0.10        # plug > 10% of the year's total assets move


def _label(ws, row, max_col=6):
    for c in range(1, max_col + 1):
        v = ws.cell(row=row, column=c).value
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def cf_input_rows(ws, target_col_letter, max_row=250):
    """Typed input cells inside the CF block (rows after the 'Cash flow'
    banner) — the legal placement targets, with their labels."""
    tci = column_index_from_string(target_col_letter)
    start = None
    for r in range(1, max_row + 1):
        if _CF_START.search(_label(ws, r) or ""):
            start = r
            break
    if start is None:
        return []
    out = []
    for r in range(start + 1, max_row + 1):
        v = ws.cell(row=r, column=tci).value
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append((r, _label(ws, r)))
    return out


def audit(wb, evaluate, sheet, check_row, bs_rows, year_cols):
    """Per forecast year: the gap and the BS movements, as data for the
    loop. `year_cols` = ordered forecast column letters; `bs_rows` =
    (row, label) pairs of BS lines; `evaluate(sheet, coord)` computes."""
    ws = wb[sheet]
    report = []
    for i, col in enumerate(year_cols):
        prev = year_cols[i - 1] if i else None
        try:
            gap = evaluate(sheet, f"{col}{check_row}")
        except Exception:
            continue
        if not isinstance(gap, (int, float)) or abs(gap) <= 1:
            continue
        start = cf_start_row(ws)
        moves = []
        for r, lab in bs_rows:
            if prev is None:
                continue
            fsrc = ws.cell(row=r, column=column_index_from_string(col)).value
            if isinstance(fsrc, str) and start is not None and any(
                    int(m.group(1)) >= start for m in
                    re.finditer(r"\$?[A-Z]{1,3}\$?([0-9]{1,5})", fsrc)):
                lab = lab + "  [RESULT of the CF — never place this]"
            try:
                d = (evaluate(sheet, f"{col}{r}")
                     - evaluate(sheet, f"{prev}{r}"))
            except Exception:
                continue
            if isinstance(d, (int, float)) and abs(d) > 1:
                moves.append({"row": r, "label": lab, "delta": round(d, 1)})
        moves.sort(key=lambda m: -abs(m["delta"]))
        report.append({"col": col, "gap": round(gap, 1), "moves": moves[:25]})
    return report


def cf_start_row(ws, max_row=250):
    for r in range(1, max_row + 1):
        if _CF_START.search(_label(ws, r) or ""):
            return r
    return None


def place_flow(wb, writer, sheet, bs_row, cf_row, target_col, prior_col):
    """The loop's attribution write: the movement of ONE BS row lands in
    ONE designed CF input row as a traceable formula. Verifies the
    target is a typed input inside the CF block, and that the SOURCE is
    a real balance-sheet line — run-16 pin: the loop placed the movement
    of CASH itself (=V133, the CF's own output) back into the CF,
    creating a circular reference. Cash and anything wired through the
    CF block is the RESULT of the statement, never an input to it."""
    ws = wb[sheet]
    start = cf_start_row(ws)
    if start is not None:
        if bs_row >= start:
            return None, ("REFUSED: r%d is inside the cash-flow block — "
                          "only a BALANCE-SHEET line's movement can be "
                          "placed" % bs_row)
        f_src = ws.cell(row=bs_row,
                        column=column_index_from_string(target_col)).value
        if isinstance(f_src, str) and f_src.startswith("="):
            for m in re.finditer(r"\$?[A-Z]{1,3}\$?([0-9]{1,5})", f_src):
                if int(m.group(1)) >= start:
                    return None, (
                        "REFUSED: r%d resolves THROUGH the cash-flow "
                        "block (its formula references r%s) — it is the "
                        "RESULT of the CF, not a movement to place. "
                        "Attribute the underlying balance-sheet lines "
                        "instead" % (bs_row, m.group(1)))
    tc = ws.cell(row=cf_row,
                 column=column_index_from_string(target_col)).value
    if not isinstance(tc, (int, float)) or isinstance(tc, bool):
        return None, ("REFUSED: %s!%s%d is not a typed CF input cell — "
                      "flows may only land in the model's own input slots"
                      % (sheet, target_col, cf_row))
    base = ("" if tc == 0 else "%r" % float(tc))
    f = "=%s-(%s%d-%s%d)" % (base, target_col, bs_row, prior_col, bs_row) \
        if base else "=-(%s%d-%s%d)" % (target_col, bs_row,
                                        prior_col, bs_row)
    lab = _label(ws, bs_row)
    ok = writer.write(sheet, f"{target_col}{cf_row}", f,
                      prior_coord=f"{prior_col}{cf_row}", flag="orange",
                      note=("forecast integrity: carries the movement of "
                            f"'{lab[:40]}' (r{bs_row}) so the {target_col} "
                            "balance sheet ties — review placement"))
    if not ok:
        return None, "REFUSED by the write guard"
    return f, None


def last_resort_plug(wb, writer, make_eval, sheet, check_row, year_cols,
                     assets_row, log):
    """The residue only. One literal per year (a formula would be
    circular through cash), orange + honest note, red when large.
    `make_eval()` returns a FRESH evaluator — each year's plug flows
    through the cash chain into the next year's opening balance, so the
    gap must be re-measured after every write."""
    ws = wb[sheet]
    plugged = []
    targets = None
    from .checks import scorecard  # noqa: F401  (cycle probe below)
    for col in year_cols:
        evaluate = make_eval()
        if year_cols and col == year_cols[0]:
            # plugging a forecast on a broken ACTUAL base masks the real
            # error — the actual year must tie first
            try:
                base_col = get_column_letter(
                    column_index_from_string(col) - 1)
                base_gap = evaluate(sheet, f"{base_col}{check_row}")
                if isinstance(base_gap, (int, float)) and abs(base_gap) > 1:
                    log(f"[run] forecast plugs WITHHELD: the actual year "
                        f"({base_col}) check is off {base_gap:+,.1f} — "
                        "tie the actuals first")
                    return plugged
            except Exception:
                pass
        try:
            gap = evaluate(sheet, f"{col}{check_row}")
        except Exception:
            continue
        if not isinstance(gap, (int, float)) or abs(gap) <= 1:
            continue
        if targets is None:
            targets = cf_input_rows(ws, col)
        others = [r for r, lab in targets if _OTHERS.match(lab or "")]
        if not others:
            log(f"[run] forecast plug: no designed catch-all input row "
                f"in the CF block — {col} left failing for the analyst")
            continue
        # a plug bigger than half the asset base is not a plug, it is
        # a structural break — leave the year failing for the analyst
        if assets_row:
            try:
                ta = abs(evaluate(sheet, f"{col}{assets_row}")) or 1.0
                if abs(gap) > 0.5 * ta:
                    log(f"[run] forecast plug WITHHELD on {col}: gap "
                        f"{gap:+,.1f} exceeds half the asset base — "
                        "structural break, analyst ruling needed")
                    continue
            except Exception:
                pass
        row = others[0]
        held = ws.cell(row=row,
                       column=column_index_from_string(col)).value
        held = float(held) if isinstance(held, (int, float)) else 0.0
        value = round(held - gap, 4)
        big = False
        if assets_row:
            try:
                ta = abs(evaluate(sheet, f"{col}{assets_row}")) or 1.0
                big = abs(gap) > PLUG_RED_SHARE * ta
            except Exception:
                pass
        if writer.write(sheet, f"{col}{row}", value,
                        prior_coord=None, trusted=True, flag="orange",
                        note=(f"LAST-RESORT PLUG: {-gap:+,.1f} could not "
                              "be attributed to any balance-sheet "
                              "movement — analyst ruling needed; unwind "
                              "when re-forecasting")):
            if big:
                cell = ws.cell(row=row,
                               column=column_index_from_string(col))
                cell.fill = writer.fills["red"]
                cell.comment = Comment(
                    f"LAST-RESORT PLUG {-gap:+,.1f} is LARGE (>10% of "
                    "the year's asset base move) — a big plug usually "
                    "means a mis-wired forecast line. Analyst ruling "
                    "needed.", "Model Update Agent")
            plugged.append((col, row, round(-gap, 1), big))
            log(f"[run] forecast plug {sheet}!{col}{row}: {-gap:+,.1f}"
                + ("  (RED — large)" if big else ""))
    return plugged
