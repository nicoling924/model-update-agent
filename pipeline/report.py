"""The _REPORT tab — the analyst reviews the update inside Excel.

Visible, FIRST sheet (it opens on top). Every listed cell is a clickable
hyperlink next to its LIVE value (a formula, so it tracks any later edit).
Four sections, house format:

1. Flagged RED (FFC7CE)  — uncertain, needs analyst review (+ method note)
2. Backed out (FFC000)   — derived, awaiting true-up (+ method note)
3. Big moves             — >50% YoY on P&L/BS lines (QC scan; a surprise
                           move is usually a mapping error, not news)
4. Core figures          — actual vs the model's own pre-update estimate
                           (snapshot taken BEFORE mark-to-actual)

Text and references only — size discipline as _SPEC.
"""
import re

from openpyxl.styles import Font

REPORT_SHEET = "_REPORT"
BIG_MOVE = 0.5
BIG_MOVE_CAP = 30

_BOLD = Font(bold=True)
_LINK = Font(color="FF0563C1", underline="single")


def _syn(sheet):
    return f"'{sheet}'" if re.search(r"[^A-Za-z0-9]", sheet) else sheet


def build_report(wb, spec, target_year, writer_log, served, pre_estimates,
                 gate_failures, loop_summary="", documents=None,
                 rollover=None):
    if REPORT_SHEET in wb.sheetnames:
        del wb[REPORT_SHEET]
    ws = wb.create_sheet(REPORT_SHEET, 0)
    r = 1

    def head(text):
        nonlocal r
        ws[f"A{r}"] = text
        ws[f"A{r}"].font = _BOLD
        r += 1

    def link_row(ref, note):
        nonlocal r
        sheet, coord = ref.split("!", 1)
        ws[f"A{r}"] = ref
        ws[f"A{r}"].hyperlink = f"#{_syn(sheet)}!{coord}"
        ws[f"A{r}"].font = _LINK
        ws[f"B{r}"] = f"={_syn(sheet)}!{coord}"
        ws[f"C{r}"] = str(note)[:250]
        r += 1

    head(f"MODEL UPDATE REPORT — {target_year} "
         f"({'DELIVERED' if not gate_failures else 'GATE REFUSED'})")
    if gate_failures:
        for f in gate_failures[:15]:
            ws[f"A{r}"] = f"GATE: {f}"[:250]
            r += 1
    if loop_summary:
        ws[f"A{r}"] = f"Objective loop: {loop_summary}"[:250]
        r += 1
    r += 1

    if documents:
        head("DOCUMENTS RECEIVED — what the agent identified, and how each was used")
        for line in documents:
            ws[f"A{r}"] = str(line)[:250]
            r += 1
        r += 1

    if rollover:
        head("ROLLOVER CHECK — did the update move the forecast in proportion "
             "to the actual surprise? (owner teaching 2026-09-03)")
        for col, txt in zip("ABCDEFGH", ("row", "line", "estimate (target yr)",
                                         "actual", "old forecast (yr+1)",
                                         "new forecast (yr+1)", "test", "verdict")):
            ws[f"{col}{r}"] = txt
            ws[f"{col}{r}"].font = _BOLD
        r += 1
        for ref, name, est_t, act_t, old_f, new_f, test, verdict in rollover:
            sheet, coord = ref.split("!", 1)
            ws[f"A{r}"] = ref
            ws[f"A{r}"].hyperlink = f"#{_syn(sheet)}!{coord}"
            ws[f"A{r}"].font = _LINK
            ws[f"B{r}"] = str(name)[:40]
            for col, v in zip("CDEF", (est_t, act_t, old_f, new_f)):
                ws[f"{col}{r}"] = v if isinstance(v, (int, float)) else None
            ws[f"G{r}"] = str(test)[:120]
            ws[f"H{r}"] = str(verdict)[:80]
            r += 1
        r += 1

    notes = _cell_notes(wb, writer_log)
    head("1. FLAGGED RED (FFC7CE) — uncertain, review each")
    reds = [f for f in writer_log.get("flags", [])]
    for ref in dict.fromkeys(reds):
        link_row(ref, notes.get(ref, ""))
    if not reds:
        ws[f"A{r}"] = "(none)"
        r += 1
    r += 1

    head("2. BACKED OUT (FFC000) — derived, awaiting true-up")
    oranges = [ref for ref in dict.fromkeys(writer_log.get("flags", []))
               if "backed out" in notes.get(ref, "").lower()
               or "back-out" in notes.get(ref, "").lower()]
    for ref in oranges:
        link_row(ref, notes.get(ref, ""))
    if not oranges:
        ws[f"A{r}"] = "(none)"
        r += 1
    r += 1

    head(f"3. BIG MOVES — >{BIG_MOVE:.0%} YoY (QC scan; verify mapping first)")
    moves = big_moves(wb, spec, target_year)
    for ref, pv, tv, pct in moves[:BIG_MOVE_CAP]:
        link_row(ref, f"{pv:,.1f} -> {tv:,.1f} ({pct:+.0%} YoY)")
    if len(moves) > BIG_MOVE_CAP:
        ws[f"A{r}"] = f"({len(moves) - BIG_MOVE_CAP} more capped)"
        r += 1
    if not moves:
        ws[f"A{r}"] = "(none)"
        r += 1
    r += 1

    verdicts = writer_log.get("verdicts", [])
    if verdicts:
        head("SENSE-CHECK VERDICTS — tripwires adjudicated by the agent "
             "(owner ruling 2026-08-31)")
        for v in verdicts[:40]:
            ref, _, rest = v.partition(": ")
            if "!" in ref and ref.split("!", 1)[0] in wb.sheetnames:
                link_row(ref, rest)
            else:
                ws[f"A{r}"] = v[:250]
                r += 1
        r += 1

    sense = writer_log.get("sense_check", [])
    if sense:
        head("SENSE CHECK — headline lines, updated model vs your pre-update model "
             "(owner ruling 2026-09-09: a forecast out of line with the actual by >10 points is reviewed)")
        for s_ in sense[:20]:
            ws[f"A{r}"] = str(s_)[:400]
            r += 1
        r += 1

    head("4. CORE FIGURES — actual vs the model's own pre-update estimate")
    for name, ref, est in pre_estimates:
        sheet, coord = ref.split("!", 1)
        ws[f"A{r}"] = name
        ws[f"B{r}"] = f"={_syn(sheet)}!{coord}"
        ws[f"C{r}"] = est if isinstance(est, (int, float)) else None
        ws[f"D{r}"] = (f"=IFERROR((B{r}-C{r})/ABS(C{r}),\"\")"
                       if isinstance(est, (int, float)) and est else "")
        ws[f"E{r}"] = ref
        ws[f"E{r}"].hyperlink = f"#{_syn(sheet)}!{coord}"
        ws[f"E{r}"].font = _LINK
        r += 1
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 10
    return ws


def _cell_notes(wb, writer_log):
    out = {}
    for ref in writer_log.get("flags", []):
        sheet, coord = ref.split("!", 1)
        if sheet in wb.sheetnames:
            cm = wb[sheet][coord].comment
            if cm is not None:
                out[ref] = str(cm.text)[:250]
    return out


def big_moves(wb, spec, target_year):
    """[(ref, prior, target, pct)] for filled aggregate rows moving >50% YoY.
    CF lines swing naturally — the spec may list cf sheets to de-weight, but
    the scan itself is generic."""
    from .checks import prior_column, year_columns
    from .evaluator import Evaluator
    ev = Evaluator(wb)
    out = []
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        pcol = prior_column(spec, sheet, target_year)
        if not tcol or not pcol:
            continue
        ws = wb[sheet]
        for row in range(1, ws.max_row + 1):
            pv = ws[f"{pcol}{row}"].value
            if not isinstance(pv, (int, float)) or abs(pv) < 10:
                continue
            try:
                tv = ev.cell(sheet, f"{tcol}{row}")
            except Exception:
                continue
            if not isinstance(tv, (int, float)) or tv == 0:
                continue
            pct = (tv - pv) / abs(pv)
            if abs(pct) > BIG_MOVE:
                out.append((f"{sheet}!{tcol}{row}", pv, tv, pct))
    out.sort(key=lambda x: -abs(x[3]))
    return out


def snapshot_estimates(wb_values, spec, target_year):
    """The model's own forecast for the soon-to-be-actual period, per key
    row — captured BEFORE mark-to-actual (once overwritten it is gone)."""
    from .checks import year_columns
    out = []
    for k in spec.get("key_rows") or []:
        sheet = k["sheet"]
        tcol = year_columns(spec, sheet).get(str(target_year))
        if not tcol or sheet not in wb_values.sheetnames:
            continue
        v = wb_values[sheet][f"{tcol}{int(k['row'])}"].value
        if isinstance(v, str) and v.startswith("="):
            # a manual-calc model caches nothing: the pre-update
            # estimate lives behind its formula — evaluate it (the
            # snapshot is taken BEFORE any write, so this IS the old
            # estimate)
            try:
                from .evaluator import Evaluator
                ev = _SNAP_EV.get(id(wb_values))
                if ev is None:
                    ev = _SNAP_EV[id(wb_values)] = Evaluator(wb_values)
                v = ev.cell(sheet, f"{tcol}{int(k['row'])}")
            except Exception:
                v = None
        out.append((k.get("name", f"{sheet}!{k['row']}"),
                    f"{sheet}!{tcol}{k['row']}",
                    v if isinstance(v, (int, float)) else None))
    return out


_SNAP_EV = {}
