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

    verdict = "all checks PASS"
    fails = [k for k, v in ((police or {}).get("laws") or {}).items()
             if v not in ("PASS", "n/a")]
    if fails:
        verdict = "REVIEW: " + ", ".join(sorted(fails))
    head(f"RESULTS UPDATE — FY{target_year}   ({verdict})", big=True)
    reds = book.by_grade("C")
    oranges = book.by_grade("D")
    ws[f"A{r}"] = _clean(f"{len(reds)} cells need review (red) · "
                         f"{len(oranges)} backed out (orange) · detail on "
                         f"the _REPORT_DETAIL tab")
    r += 2

    # ---- 1. KEY FIGURES ----------------------------------------------
    head("KEY FIGURES — actual vs last year and vs our estimate")
    keys = key_panel_rows(wb, spec, target_year, snapshot)
    moves = big_moves(wb, spec, target_year)
    why = commentary(client, keys, moves, wb)
    hdr = ("", "Actual", "Prior yr", "YoY", "Our est.", "vs est.")
    for j, h in enumerate(hdr):
        c = ws.cell(row=r, column=1 + j, value=h)
        c.font = _BOLD
    r += 1
    for name, ref, act, pri, est in keys:
        sheet, coord = ref.split("!", 1)
        ws[f"A{r}"] = _clean(name)
        ws[f"A{r}"].hyperlink = f"#{_syn(sheet)}!{coord}"
        ws[f"A{r}"].font = _LINK
        ws[f"B{r}"] = act
        ws[f"C{r}"] = pri
        if isinstance(act, (int, float)) and isinstance(pri, (int, float)) \
                and pri:
            ws[f"D{r}"] = (act - pri) / abs(pri)
            ws[f"D{r}"].number_format = "+0.0%;-0.0%"
        ws[f"E{r}"] = est if isinstance(est, (int, float)) else None
        if isinstance(act, (int, float)) and isinstance(est, (int, float)) \
                and est:
            ws[f"F{r}"] = (act - est) / abs(est)
            ws[f"F{r}"].number_format = "+0.0%;-0.0%"
        for cc in ("B", "C", "E"):
            ws[f"{cc}{r}"].number_format = "#,##0.0"
        r += 1
        line = why.get(name)
        if line:
            ws[f"B{r}"] = _clean(f"— {line}")
            ws[f"B{r}"].font = Font(italic=True, color="FF666666")
            r += 1
    blank()

    # ---- 2. WHAT TO REVIEW (red) -------------------------------------
    head(f"REVIEW — the agent could not prove these ({len(reds)})")
    for p in reds[:40]:
        sheet, coord = p.ref.split("!", 1)
        row_n = int(re.sub(r"[A-Z]", "", coord))
        lab = _label(wb, sheet, row_n) or p.ref
        ws[f"A{r}"] = _clean(f"{lab}  ({sheet})")[:60]
        ws[f"A{r}"].hyperlink = f"#{_syn(sheet)}!{coord}"
        ws[f"A{r}"].font = _LINK
        ws[f"B{r}"] = f"={_syn(sheet)}!{coord}"
        ws[f"C{r}"] = _first_sentence(p.note or p.method)
        r += 1
    if len(reds) > 40:
        ws[f"A{r}"] = _clean(f"…and {len(reds) - 40} more — see "
                             f"_REPORT_DETAIL")
        r += 1
    if not reds:
        ws[f"A{r}"] = "(none)"
        r += 1
    blank()

    # ---- 3. BACKED OUT (orange) --------------------------------------
    head(f"BACKED OUT — derived, will true-up from the detailed report "
         f"({len(oranges)})")
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
        head("OTHER BIG MOVES (>50% YoY — check mapping before news)")
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
