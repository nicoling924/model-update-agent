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
                     assets_row, log, only=None):
    """The residue only. One literal per year (a formula would be
    circular through cash), orange + honest note, red when large.
    `make_eval()` returns a FRESH evaluator — each year's plug flows
    through the cash chain into the next year's opening balance, so the
    gap must be re-measured after every write.

    `only`: the periods to plug (a break in period t is plugged in period
    t — see plug_period). The whole series is still walked, so a plug
    stays measured against the years before it."""
    ws = wb[sheet]
    plugged = []
    targets = None
    from .checks import scorecard  # noqa: F401  (cycle probe below)
    if year_cols:
        # plugging a forecast on a broken ACTUAL base masks the real
        # error — the actual year must tie first
        try:
            base_col = get_column_letter(
                column_index_from_string(year_cols[0]) - 1)
            base_gap = make_eval()(sheet, f"{base_col}{check_row}")
            if isinstance(base_gap, (int, float)) and abs(base_gap) > 1:
                log(f"[run] forecast plugs WITHHELD: the actual year "
                    f"({base_col}) check is off {base_gap:+,.1f} — "
                    "tie the actuals first")
                return plugged
        except Exception:
            pass
    for col in year_cols:
        evaluate = make_eval()
        try:
            gap = evaluate(sheet, f"{col}{check_row}")
        except Exception:
            continue
        if not isinstance(gap, (int, float)) or abs(gap) <= 1:
            continue
        if only is not None and col not in only:
            continue                 # this break belongs to another period
        # THE CASCADE BREAKER (run-205: plugs doubled year over year,
        # -2,327 -> -42,512 — each plug flows through cash into the next
        # year's gap and the series feeds itself). An ESCALATING plug
        # series is a structural symptom, not a residue: stop plugging,
        # leave the years failing with their collapse-flag causes for
        # the analyst/loop — forecast inviolability over cosmetics.
        if plugged and abs(gap) > 1.6 * abs(plugged[-1][2]) \
                and abs(gap) > 500:
            log(f"[run] forecast plugs STOPPED at {col}: the series is "
                f"escalating ({plugged[-1][2]:+,.1f} -> {-gap:+,.1f}) — "
                "a cascade means an unresolved actual-column cause, "
                "never a residue; plugs unwound, years left failing "
                "with their collapse-flag causes")
            for pcol, prow, _pval, _big, pdelta in plugged:
                c2 = ws.cell(row=prow,
                             column=column_index_from_string(pcol))
                if isinstance(c2.value, (int, float)):
                    writer.write(ws.title, f"{pcol}{prow}", round(c2.value - pdelta, 6),
                                 trusted=True, force_lock=True)          # through the writer (2026-09-14)
                    c2.comment = Comment(
                        "forecast plug UNWOUND: the plug series was "
                        "escalating (cascade) — see collapse flags for "
                        "the actual-column causes.", "Model Update Agent")
            return []
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
        # THE COEFFICIENT PROBE (2026-09-02: a plug sized on the +1
        # assumption DOUBLED the residual it aimed to close — the row's
        # true coefficient on the check was -2. Measure, never assume:
        # bump the row 1.0, read the check's response, size by it.)
        cell_p = ws.cell(row=row, column=column_index_from_string(col))
        old_p = cell_p.value
        cell_p.value = held + 1.0
        try:
            probe = make_eval()(sheet, f"{col}{check_row}")
        except Exception:
            probe = None
        cell_p.value = old_p
        coeff = (probe - gap) if isinstance(probe, (int, float)) else None
        if not isinstance(coeff, (int, float)) or abs(coeff) < 0.1:
            log(f"[run] forecast plug WITHHELD on {col}: the designed "
                f"catch-all row does not move this check (coeff "
                f"{coeff if coeff is None else round(coeff, 3)}) — left "
                "failing for the analyst")
            continue
        value = round(held - gap / coeff, 4)
        big = False
        if assets_row:
            try:
                ta = abs(evaluate(sheet, f"{col}{assets_row}")) or 1.0
                big = abs(gap) > PLUG_RED_SHARE * ta
            except Exception:
                pass
        # a forecast plug is BLUE (the one forecast-year colour, owner
        # 2026-09-07); a large one is also put on the watch list
        if writer.write(sheet, f"{col}{row}", value,
                        prior_coord=None, trusted=True, flag="blue", kind="plug",
                        note=(f"Plug: {-gap:+,.1f} inserted so the forecast "
                              "balances; not attributable to any balance-"
                              "sheet movement. Unwind when re-forecasting.")):
            if big:
                cell = ws.cell(row=row,
                               column=column_index_from_string(col))
                cell.comment = Comment(
                    f"Plug: {-gap:+,.1f} inserted so the forecast balances "
                    "— LARGE (over 10% of the year's asset move); a big "
                    "plug usually means a mis-wired forecast line. Your "
                    "ruling.", "Model Update Agent")
                writer.watch(sheet, f"{col}{row}",
                             f"large forecast plug {-gap:+,.0f}")
            plugged.append((col, row, round(-gap, 1), big,
                            round(value - held, 6)))
            log(f"[run] forecast plug {sheet}!{col}{row}: {-gap:+,.1f}"
                + ("  (RED — large)" if big else ""))
    return plugged


def plug_period(loop, sheet, coord, log):
    """A BREAK IN PERIOD t IS PLUGGED IN PERIOD t (run 35043265913: a
    forecast-year break was answered with "plug", the terminal ladder was
    called — it only ever looks at the ACTUAL period's checks — and the
    forecast repair then plugged the FIRST broken forecast year instead,
    so the break stayed open and the pick was judged on another year's
    plug). -> the plugs written."""
    import re as _re
    from .checks import forecast_columns, year_columns
    from .evaluator import Evaluator
    m = _re.match(r"([A-Z]{1,3})(\d+)$", str(coord))
    if not m or sheet not in loop.wb.sheetnames:
        return []
    col, row = m.group(1), int(m.group(2))
    cols = forecast_columns(loop.spec, sheet, int(loop.ty)) or []
    if col not in cols:
        return []
    assets_row = None
    tcol = year_columns(loop.spec, sheet).get(str(int(loop.ty)))
    f = loop.wb[sheet][f"{tcol}{row}"].value if tcol else None
    if isinstance(f, str):
        m2 = _re.search(r"[A-Z]{1,3}(\d+)", f)
        if m2:
            assets_row = int(m2.group(1))
    return last_resort_plug(loop.wb, loop.writer,
                            (lambda: (lambda s_, c_, e=Evaluator(loop.wb): e.cell(s_, c_))),
                            sheet, row, cols, assets_row, log, only=[col])
