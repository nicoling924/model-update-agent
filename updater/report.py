"""The _REPORT tab — the analyst's at-a-glance review, new-objectives shape.

Visible FIRST sheet. Every listed cell is a clickable hyperlink next to its
LIVE value. The run ALWAYS delivers (BOSS_MINDMAP law) — the header carries
the Police verdict, never a refusal.

Sections (text and references only; _SPEC size discipline):
1. FLAGGED RED (grade C)    — uncertain, review each
2. BACKED OUT (grade D)     — plugs/back-outs, awaiting true-up
3. DERIVED CLEAN (grade B)  — tied derivations, listed for transparency
4. INFERRED ADJUSTMENTS     — analyst logic replicated; confirm once
5. BIG MOVES                — >50% YoY (QC scan: often a mapping error)
6. CORE FIGURES             — previous projection vs ACTUAL (target year)
7. FORECAST SHIFT           — old vs new projection for forecast years
8. NOT UPDATED THIS PERIOD  — proven non-disclosures, with search trails
9. POLICE                   — the four laws' verdicts + open findings
"""
import re

from openpyxl.styles import Font

from .checks import prior_column, year_columns
from .evaluator import Evaluator

REPORT_SHEET = "_REPORT"
BIG_MOVE = 0.5
BIG_MOVE_CAP = 30

_BOLD = Font(bold=True)
_LINK = Font(color="FF0563C1", underline="single")


def _syn(sheet):
    return f"'{sheet}'" if re.search(r"[^A-Za-z0-9]", sheet) else sheet


def snapshot_projections(wb_values, spec, target_year):
    """BEFORE any write: the model's own projections, target year AND every
    forecast year, per key row (once overwritten they are gone).
    -> {"target": [(name, ref, value)], "forecast": {year: [(name, ref, v)]}}
    """
    out = {"target": [], "forecast": {}}
    for k in spec.get("key_rows") or []:
        sheet, row = k["sheet"], int(k["row"])
        if sheet not in wb_values.sheetnames:
            continue
        cols = year_columns(spec, sheet)
        for year, col in sorted(cols.items()):
            if year < str(target_year):
                continue
            v = wb_values[sheet][f"{col}{row}"].value
            entry = (k.get("name", f"{sheet}!{row}"), f"{sheet}!{col}{row}",
                     v if isinstance(v, (int, float)) else None)
            if year == str(target_year):
                out["target"].append(entry)
            else:
                out["forecast"].setdefault(year, []).append(entry)
    return out


def big_moves(wb, spec, target_year):
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


def build_report(wb, spec, target_year, book, snapshot, adjustments=None,
                 police=None, loop_summary=""):
    """book = EvidenceBook; snapshot = snapshot_projections() taken pre-write;
    adjustments = adjust.infer() candidates the loop acted on; police = the
    police verdict dict."""
    if REPORT_SHEET in wb.sheetnames:
        del wb[REPORT_SHEET]
    ws = wb.create_sheet(REPORT_SHEET, 0)
    r = 1

    def head(text):
        nonlocal r
        ws[f"A{r}"] = text
        ws[f"A{r}"].font = _BOLD
        r += 1

    def blank():
        nonlocal r
        r += 1

    def plain(text):
        nonlocal r
        ws[f"A{r}"] = str(text)[:250]
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

    verdict = "DELIVERED"
    if police:
        fails = [k for k, v in (police.get("laws") or {}).items()
                 if v not in ("PASS", "n/a")]
        verdict += (" — POLICE: all four laws PASS" if not fails
                    else f" — POLICE: review {', '.join(fails)}")
    head(f"MODEL UPDATE REPORT — {target_year} ({verdict})")
    if loop_summary:
        plain(f"Agent: {loop_summary}")
    blank()

    head("1. FLAGGED RED (FFC7CE) — uncertain, review each")
    reds = book.by_grade("C")
    for p in reds:
        link_row(p.ref, p.note or p.method)
    if not reds:
        plain("(none)")
    blank()

    head("2. BACKED OUT / PLUGS (FFC000) — derived, awaiting true-up")
    oranges = book.by_grade("D")
    for p in oranges:
        link_row(p.ref, p.note or p.method)
    if not oranges:
        plain("(none)")
    blank()

    head("3. DERIVED CLEAN (grade B) — tied derivations, for transparency")
    bs = book.by_grade("B")
    for p in bs[:40]:
        link_row(p.ref, f"{p.method}: {p.citation}"[:250])
    if len(bs) > 40:
        plain(f"({len(bs) - 40} more, all tied)")
    if not bs:
        plain("(none)")
    blank()

    head("4. INFERRED ANALYST ADJUSTMENTS — confirm the logic once")
    for a in (adjustments or []):
        plain(f"{a['row']} '{a['label']}': model = disclosed "
              f"{'x' if a['kind'] == 'ratio' else '+'} {a['constant']} "
              f"(prior: {a['model_prior']:,.1f} vs disclosed "
              f"{a['disclosed_prior']:,.1f}; {a['cite']})")
    if not adjustments:
        plain("(none inferred)")
    blank()

    head(f"5. BIG MOVES — >{BIG_MOVE:.0%} YoY (verify mapping before news)")
    moves = big_moves(wb, spec, target_year)
    for ref, pv, tv, pct in moves[:BIG_MOVE_CAP]:
        link_row(ref, f"{pv:,.1f} -> {tv:,.1f} ({pct:+.0%} YoY)")
    if len(moves) > BIG_MOVE_CAP:
        plain(f"({len(moves) - BIG_MOVE_CAP} more capped)")
    if not moves:
        plain("(none)")
    blank()

    head(f"6. CORE FIGURES — previous {target_year} projection vs ACTUAL")
    for name, ref, est in snapshot.get("target", []):
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
    blank()

    head("7. FORECAST SHIFT — old projection vs new (post-actuals flow-through)")
    for year in sorted(snapshot.get("forecast", {})):
        plain(f"— {year} —")
        for name, ref, old in snapshot["forecast"][year]:
            sheet, coord = ref.split("!", 1)
            ws[f"A{r}"] = name
            ws[f"B{r}"] = f"={_syn(sheet)}!{coord}"
            ws[f"C{r}"] = old if isinstance(old, (int, float)) else None
            ws[f"D{r}"] = (f"=IFERROR((B{r}-C{r})/ABS(C{r}),\"\")"
                           if isinstance(old, (int, float)) and old else "")
            r += 1
    if not snapshot.get("forecast"):
        plain("(no forecast years in axis)")
    blank()

    head("8. NOT UPDATED THIS PERIOD — proven non-disclosures")
    for t in book.non_disclosure:
        plain(f"{t.row}: searched {'; '.join(t.looked[:4])}")
    if not book.non_disclosure:
        plain("(none claimed)")
    blank()

    head("9. POLICE — four laws")
    for law, v in ((police or {}).get("laws") or {}).items():
        plain(f"{law}: {v}")
    for f in ((police or {}).get("findings") or [])[:20]:
        plain(f"finding: {f}")
    if not police:
        plain("(police did not run)")

    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 10
    return ws
