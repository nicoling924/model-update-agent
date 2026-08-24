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

# dashboard palette (owner: "easier to read finance dashboard")
from openpyxl.styles import Alignment, Border, PatternFill, Side
_NAVY = PatternFill("solid", start_color="FF1F3864")
_BAND = PatternFill("solid", start_color="FF2E5496")
_RED_BAND = PatternFill("solid", start_color="FFC00000")
_AMBER_BAND = PatternFill("solid", start_color="FFBF6000")
_ZEBRA = PatternFill("solid", start_color="FFF2F5FA")
_CHIP_OK = PatternFill("solid", start_color="FFC6E0B4")
_CHIP_WARN = PatternFill("solid", start_color="FFFFD6D6")
_WHITE_B = Font(bold=True, color="FFFFFFFF")
_WHITE_B14 = Font(bold=True, color="FFFFFFFF", size=14)
_GOOD = Font(color="FF107C41")
_BAD = Font(color="FFC00000")
_MUTED_I = Font(italic=True, color="FF7F7F7F")
_THIN = Border(bottom=Side(style="thin", color="FFD0D7E5"))

# the mindmap's OWN key-item list (BOSS_MINDMAP "Key numbers include") —
# the report's top table shows THESE, not every discovered key
HEADLINE_RE = re.compile(
    r"revenue|sales|gross profit|net profit|eps|dps|dividend|cash year|"
    r"cash balance|total assets|total equity|"
    r"operating cash|investing cash|financing cash", re.I)


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




def _clean(text):
    """openpyxl refuses control characters — PDF-extracted text carries
    them (run 6 died at the finish line writing a search trail)."""
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    return ILLEGAL_CHARACTERS_RE.sub(" ", text)


def _label(wb, sheet, row):
    """The row's own label from the sheet's text columns."""
    if sheet not in wb.sheetnames:
        return ""
    for lc in ("A", "B", "C", "D"):
        v = wb[sheet][f"{lc}{row}"].value
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _first_sentence(text, cap=110):
    t = _clean(str(text or "")).strip()
    for stop in (". ", "; ", " — ", " -> "):
        i = t.find(stop)
        if 0 < i < cap:
            return t[:i + 1]
    return t[:cap]


def key_panel_rows(wb, spec, ty, snapshot):
    """[(name, ref, actual, prior, est)] for the model's key rows —
    evaluated live, prior from the prior column, estimate from the
    pre-write snapshot."""
    ev = Evaluator(wb)
    est_by_ref = {ref: est for _n, ref, est in snapshot.get("target", [])}
    out = []
    for k in spec.get("key_rows") or []:
        sheet, row = k["sheet"], int(k["row"])
        if sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(ty))
        pcol = prior_column(spec, sheet, ty)
        if not tcol:
            continue
        ref = f"{sheet}!{tcol}{row}"
        try:
            actual = ev.cell(sheet, f"{tcol}{row}")
        except Exception:
            actual = None
        try:
            prior = ev.cell(sheet, f"{pcol}{row}") if pcol else None
        except Exception:
            prior = None
        out.append((k.get("name", f"{sheet}!{row}"), ref,
                    actual if isinstance(actual, (int, float)) else None,
                    prior if isinstance(prior, (int, float)) else None,
                    est_by_ref.get(ref)))
    return out


def commentary(client, keys, moves, wb):
    """One engine call -> {key name: one-line why}. Empty on any failure
    — the report never blocks on commentary."""
    if client is None or not keys:
        return {}
    try:
        from pathlib import Path
        prompt = (Path(__file__).resolve().parent.parent / "prompts"
                  / "commentary.md").read_text()
        lines = []
        for name, _ref, act, pri, est in keys:
            if act is None:
                continue
            bits = [f"{name}: actual {act:,.1f}"]
            if isinstance(pri, (int, float)) and pri:
                bits.append(f"prior {pri:,.1f} ({(act - pri) / abs(pri):+.1%} YoY)")
            if isinstance(est, (int, float)) and est:
                bits.append(f"our estimate was {est:,.1f} ({(act - est) / abs(est):+.1%} vs est)")
            lines.append("; ".join(bits))
        ctx = ["KEY FIGURES:"] + lines + ["", "LARGEST MOVES THIS PERIOD "
                                             "(context for causes):"]
        for ref, pv, tv, pct in moves[:12]:
            sheet, coord = ref.split("!", 1)
            row = int(re.sub(r"[A-Z]", "", coord))
            lab = _label(wb, sheet, row) or ref
            ctx.append(f"{lab} ({sheet}): {pv:,.1f} -> {tv:,.1f} ({pct:+.0%})")
        out = client.json(prompt, "\n".join(ctx),
                          lambda o: [] if isinstance(o, dict)
                          else ["one JSON object required"])
        return {str(k): _clean(str(v))[:130] for k, v in out.items()
                if isinstance(v, str)}
    except Exception:
        return {}


def build_report(wb, spec, target_year, book, snapshot, adjustments=None,
                 police=None, loop_summary="", reading=None, client=None):
    """The analyst's page (owner ruling 2026-08-24): key figures with
    estimate-vs-actual and a one-line why; what to review below; the
    machine detail on a second tab. Reads like a results summary, not a
    log file."""
    for sn in (REPORT_SHEET, "_REPORT_DETAIL"):
        if sn in wb.sheetnames:
            del wb[sn]
    ws = wb.create_sheet(REPORT_SHEET, 0)
    r = 1

    def head(text, big=False):
        nonlocal r
        ws[f"A{r}"] = _clean(text)
        ws[f"A{r}"].font = Font(bold=True, size=13 if big else 11)
        r += 1

    def blank():
        nonlocal r
        r += 1

    fails = [k for k, v in ((police or {}).get("laws") or {}).items()
             if v not in ("PASS", "n/a")]
    reds = book.by_grade("C")
    oranges = book.by_grade("D")
    # title bar
    ws.merge_cells(f"A{r}:F{r}")
    ws[f"A{r}"] = _clean(f"RESULTS UPDATE — FY{target_year}")
    ws[f"A{r}"].font = _WHITE_B14
    ws[f"A{r}"].fill = _NAVY
    ws.row_dimensions[r].height = 26
    ws[f"A{r}"].alignment = Alignment(vertical="center")
    r += 1
    # status chips
    ws[f"A{r}"] = ("✓ all checks PASS" if not fails
                   else "⚠ review: " + ", ".join(sorted(fails)))
    ws[f"A{r}"].fill = _CHIP_OK if not fails else _CHIP_WARN
    ws[f"A{r}"].font = Font(bold=True)
    ws[f"B{r}"] = f"{len(reds)} to review"
    ws[f"B{r}"].fill = _CHIP_WARN if reds else _CHIP_OK
    ws[f"C{r}"] = f"{len(oranges)} backed out"
    ws[f"D{r}"] = "detail → _REPORT_DETAIL"
    ws[f"D{r}"].font = _MUTED_I
    r += 2

    # ---- 1. KEY FIGURES ----------------------------------------------
    def band(text, fill=_BAND):
        nonlocal r
        ws.merge_cells(f"A{r}:F{r}")
        ws[f"A{r}"] = _clean(text)
        ws[f"A{r}"].font = _WHITE_B
        ws[f"A{r}"].fill = fill
        r += 1

    band("KEY FIGURES — actual vs last year and vs our estimate")
    all_keys = key_panel_rows(wb, spec, target_year, snapshot)
    keys = [k for k in all_keys if HEADLINE_RE.search(k[0])][:12] \
        or all_keys[:10]
    moves = big_moves(wb, spec, target_year)
    why = commentary(client, keys, moves, wb)
    hdr = ("", "Actual", "Prior yr", "YoY", "Our est.", "vs est.")
    for j, h in enumerate(hdr):
        c = ws.cell(row=r, column=1 + j, value=h)
        c.font = _BOLD
        c.border = _THIN
    r += 1
    zebra = False
    for name, ref, act, pri, est in keys:
        sheet, coord = ref.split("!", 1)
        ws[f"A{r}"] = _clean(name).title()
        ws[f"A{r}"].hyperlink = f"#{_syn(sheet)}!{coord}"
        ws[f"A{r}"].font = Font(bold=True, color="FF1F3864")
        ws[f"B{r}"] = act
        ws[f"C{r}"] = pri
        if isinstance(act, (int, float)) and isinstance(pri, (int, float)) \
                and pri:
            pct = (act - pri) / abs(pri)
            ws[f"D{r}"] = pct
            ws[f"D{r}"].number_format = "+0.0%;-0.0%"
            ws[f"D{r}"].font = _GOOD if pct >= 0 else _BAD
        ws[f"E{r}"] = est if isinstance(est, (int, float)) else None
        if isinstance(act, (int, float)) and isinstance(est, (int, float)) \
                and est:
            pe = (act - est) / abs(est)
            ws[f"F{r}"] = pe
            ws[f"F{r}"].number_format = "+0.0%;-0.0%"
            ws[f"F{r}"].font = _GOOD if abs(pe) <= 0.02 \
                else (_BAD if pe < 0 else _GOOD)
        for cc in ("B", "C", "E"):
            ws[f"{cc}{r}"].number_format = "#,##0.0"
        if zebra:
            for cc in "ABCDEF":
                ws[f"{cc}{r}"].fill = _ZEBRA
        r += 1
        line = why.get(name)
        if line:
            ws[f"B{r}"] = _clean(f"— {line}")
            ws.merge_cells(f"B{r}:F{r}")
            ws[f"B{r}"].font = _MUTED_I
            if zebra:
                for cc in "ABCDEF":
                    ws[f"{cc}{r}"].fill = _ZEBRA
            r += 1
        zebra = not zebra
    blank()

    # ---- 2. WHAT TO REVIEW (red) -------------------------------------
    # de-cluttered (owner): grouped by sheet, one line per item, note as
    # a HOVER comment not a text column, biggest first, capped at 20
    band(f"REVIEW — the agent could not prove these ({len(reds)})",
         _RED_BAND)
    ws[f"A{r}"] = "hover a name for the agent's note · full list on _REPORT_DETAIL"
    ws[f"A{r}"].font = _MUTED_I
    r += 1
    ev_r = Evaluator(wb)

    def _live(p):
        sheet, coord = p.ref.split("!", 1)
        try:
            v = ev_r.cell(sheet, coord)
            return v if isinstance(v, (int, float)) else None
        except Exception:
            return None
    reds_sized = sorted(((p, _live(p)) for p in reds),
                        key=lambda x: -(abs(x[1]) if x[1] else 0))[:20]
    by_sheet = {}
    for p, v in reds_sized:
        by_sheet.setdefault(p.ref.split("!", 1)[0], []).append((p, v))
    from openpyxl.comments import Comment as _C
    for sheet in sorted(by_sheet):
        ws[f"A{r}"] = _clean(sheet)
        ws[f"A{r}"].font = Font(bold=True, color="FF7F7F7F")
        r += 1
        for p, v in by_sheet[sheet]:
            _sh, coord = p.ref.split("!", 1)
            row_n = int(re.sub(r"[A-Z]", "", coord))
            lab = _label(wb, _sh, row_n) or p.ref
            ws[f"B{r}"] = _clean(str(lab))[:44]
            ws[f"B{r}"].hyperlink = f"#{_syn(_sh)}!{coord}"
            ws[f"B{r}"].font = _LINK
            note = _clean(str(p.note or p.method))[:250]
            if note:
                ws[f"B{r}"].comment = _C(note, "Model Update Agent")
            ws[f"C{r}"] = f"={_syn(_sh)}!{coord}"
            ws[f"C{r}"].number_format = "#,##0.0"
            r += 1
    if len(reds) > 20:
        ws[f"B{r}"] = _clean(f"…{len(reds) - 20} smaller items on "
                             f"_REPORT_DETAIL")
        ws[f"B{r}"].font = _MUTED_I
        r += 1
    if not reds:
        ws[f"A{r}"] = "(none)"
        r += 1
    blank()

    # ---- 3. BACKED OUT (orange) --------------------------------------
    band(f"BACKED OUT — derived, will true-up from the detailed report "
         f"({len(oranges)})", _AMBER_BAND)
    for p in oranges[:25]:
        sheet, coord = p.ref.split("!", 1)
        row_n = int(re.sub(r"[A-Z]", "", coord))
        lab = _label(wb, sheet, row_n) or p.ref
        ws[f"A{r}"] = _clean(f"{lab}  ({sheet})")[:60]
        ws[f"A{r}"].hyperlink = f"#{_syn(sheet)}!{coord}"
        ws[f"A{r}"].font = _LINK
        ws[f"B{r}"] = f"={_syn(sheet)}!{coord}"
        ws[f"C{r}"] = _first_sentence(p.note or p.method)
        r += 1
    if not oranges:
        ws[f"A{r}"] = "(none)"
        r += 1
    blank()

    # ---- 4. OTHER BIG MOVES (non-key, top 10, labels not refs) -------
    key_refs = {ref for _n, ref, _a, _p, _e in keys}
    other = [(ref, pv, tv, pct) for ref, pv, tv, pct in moves
             if ref not in key_refs][:10]
    if other:
        band("OTHER BIG MOVES (>50% YoY — check mapping before news)")
        for ref, pv, tv, pct in other:
            sheet, coord = ref.split("!", 1)
            row_n = int(re.sub(r"[A-Z]", "", coord))
            lab = _label(wb, sheet, row_n) or ref
            ws[f"A{r}"] = _clean(f"{lab}  ({sheet})")[:60]
            ws[f"A{r}"].hyperlink = f"#{_syn(sheet)}!{coord}"
            ws[f"A{r}"].font = _LINK
            ws[f"B{r}"] = _clean(f"{pv:,.1f} -> {tv:,.1f} ({pct:+.0%})")
            r += 1
        blank()

    ws.column_dimensions["A"].width = 46
    for cc in "BCEF":
        ws.column_dimensions[cc].width = 13
    ws.column_dimensions["C"].width = 46
    ws.column_dimensions["D"].width = 9

    # ---- machine detail tab ------------------------------------------
    _build_detail(wb, spec, target_year, book, snapshot, adjustments,
                  police, loop_summary, reading)
    return ws


def _build_detail(wb, spec, target_year, book, snapshot, adjustments,
                  police, loop_summary, reading):
    """The full audit dump the old report page was — everything the
    machinery knows, for the reviewer who wants it."""
    ws = wb.create_sheet("_REPORT_DETAIL")
    ws.sheet_state = "visible"
    r = 1

    def head(text):
        nonlocal r
        ws[f"A{r}"] = _clean(text)
        ws[f"A{r}"].font = _BOLD
        r += 1

    def plain(text):
        nonlocal r
        ws[f"A{r}"] = _clean(str(text)[:250])
        r += 1

    def link_row(ref, note):
        nonlocal r
        sheet, coord = ref.split("!", 1)
        ws[f"A{r}"] = ref
        ws[f"A{r}"].hyperlink = f"#{_syn(sheet)}!{coord}"
        ws[f"A{r}"].font = _LINK
        ws[f"B{r}"] = f"={_syn(sheet)}!{coord}"
        ws[f"C{r}"] = _clean(str(note)[:250])
        r += 1

    head(f"MODEL UPDATE DETAIL — {target_year}")
    if loop_summary:
        plain(f"Agent: {loop_summary}")
    if reading:
        art = reading.get("articulation") or {}
        plain(f"Reading: {reading.get('located', '?')}/"
              f"{reading.get('inventory', '?')} row priors located; "
              + (", ".join(f"{k}={'OK' if v else 'FAIL'}"
                           for k, v in art.items()) or "not provable")
              + f"; {reading.get('repairs', 0)} page repairs")
        for g in (reading.get("unlocated") or [])[:12]:
            plain(f"  not located in filing: {g}")
    r += 1
    head("ALL RED FLAGS")
    for p in book.by_grade("C"):
        link_row(p.ref, p.note or p.method)
    r += 1
    head("ALL BACK-OUTS / PLUGS")
    for p in book.by_grade("D"):
        link_row(p.ref, p.note or p.method)
    r += 1
    head("DERIVED CLEAN (grade B)")
    for p in book.by_grade("B")[:40]:
        link_row(p.ref, f"{p.method}: {p.citation}"[:250])
    r += 1
    head("INFERRED ANALYST ADJUSTMENTS")
    for a in (adjustments or []):
        plain(f"{a['row']} '{a['label']}': model = disclosed "
              f"{'x' if a['kind'] == 'ratio' else '+'} {a['constant']} "
              f"({a['cite']})")
    r += 1
    head("FORECAST SHIFT (old vs new projection)")
    for year in sorted(snapshot.get("forecast", {})):
        plain(f"— {year} —")
        for name, ref, old in snapshot["forecast"][year]:
            sheet, coord = ref.split("!", 1)
            ws[f"A{r}"] = _clean(name)
            ws[f"B{r}"] = f"={_syn(sheet)}!{coord}"
            ws[f"C{r}"] = old if isinstance(old, (int, float)) else None
            r += 1
    r += 1
    head("NOT UPDATED THIS PERIOD — proven non-disclosures")
    for t in book.non_disclosure:
        plain(f"{t.row}: searched {'; '.join(t.looked[:4])}")
    r += 1
    head("POLICE — four laws")
    for law, v in ((police or {}).get("laws") or {}).items():
        plain(f"{law}: {v}")
    for f in ((police or {}).get("findings") or [])[:20]:
        plain(f"finding: {f}")
    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 60
    return ws
