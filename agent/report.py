"""_REPORT tab (first sheet, clickable links + live values) + markdown report."""
from openpyxl.styles import Font, PatternFill


def write_report_tab(wb, cfg, flags, backouts, big_moves, core_rows, reviewer_findings,
                     restatements, title, exceptions=None):
    if "_REPORT" in wb.sheetnames:
        del wb["_REPORT"]
    r = wb.create_sheet("_REPORT", 0)
    r.sheet_view.showGridLines = False
    bold, big = Font(bold=True), Font(bold=True, size=14)
    grey = Font(color="FF666666", size=9)
    red = PatternFill("solid", start_color="FF" + cfg["conventions"]["flag_uncertain_fill"],
                      end_color="FF" + cfg["conventions"]["flag_uncertain_fill"])
    orange = PatternFill("solid", start_color="FF" + cfg["conventions"]["flag_backedout_fill"],
                         end_color="FF" + cfg["conventions"]["flag_backedout_fill"])
    for col, w in (("A", 24), ("B", 14), ("C", 95)):
        r.column_dimensions[col].width = w
    r["A1"], r["A1"].font = title, big
    row = 3
    if exceptions:
        c = r[f"A{row}"]
        c.value = ("⚠ DELIVERED WITH EXCEPTIONS — integrity checks not fully passed; "
                   "resolve the red-flagged cells below, then re-verify:")
        c.font = bold
        c.fill = red
        row += 1
        for e in exceptions:
            r[f"A{row}"], r[f"A{row}"].font = f"  {e}", grey
            row += 1
        row += 1

    def section(header):
        nonlocal row
        r[f"A{row}"], r[f"A{row}"].font = header, bold
        row += 1

    def entry(sheet, coord, note, fill=None):
        nonlocal row
        c = r[f"A{row}"]
        c.value = f"{sheet}!{coord}"
        c.hyperlink = f"#'{sheet}'!{coord}"
        if fill:
            c.fill = fill
        r[f"B{row}"] = f"='{sheet}'!{coord}"
        r[f"C{row}"] = note
        row += 1

    def text(t):
        nonlocal row
        r[f"A{row}"], r[f"A{row}"].font = t, grey
        row += 1

    section("1. FLAGGED RED (uncertain — needs analyst review)")
    for s, coord, note in flags or [("", "", "none")]:
        entry(s, coord, note, red) if s else text("None.")
    row += 1
    section("2. BACKED OUT (orange — derived, awaiting true-up)")
    for s, coord, note in backouts or []:
        entry(s, coord, note, orange)
    if not backouts:
        text("None pending.")
    row += 1
    section(f"3. BIG MOVES (>{int(cfg['conventions']['big_move_threshold']*100)}% YoY) — QC scan")
    for s, coord, note in big_moves or []:
        entry(s, coord, note)
    if not big_moves:
        text("None above threshold.")
    row += 1
    section("4. CORE FIGURES — actual vs model's prior estimate")
    for s, coord, note in core_rows or []:
        entry(s, coord, note)
    row += 1
    if restatements:
        section("Restatements")
        for t in restatements:
            text(t)
        row += 1
    if reviewer_findings is not None:
        section("5. REVIEWER PASS (independent, fresh-context)")
        for f in reviewer_findings.get("findings", []):
            text(f"[{f['severity']}] {f.get('cell','')}: model holds {f.get('model_holds','')} | "
                 f"disclosure: {f.get('disclosure_says','')} (p{f.get('page','?')}) — {f.get('evidence','')[:200]}")
        text(f"Verdict: {reviewer_findings.get('verdict','')}")


def big_moves_scan(ev, wb, spec, cfg):
    """>threshold YoY moves on the primary statements sheet (P&L/BS weighted)."""
    out = []
    thr = cfg["conventions"]["big_move_threshold"]
    for sheet, axis in spec["year_axis"].items():
        role = (spec["sheets"].get(sheet) or {}).get("role")
        if role != "statements":
            continue
        cols = axis.get("columns") or {}
        years = sorted(cols)
        if len(years) < 2:
            continue
        prev_col, cur_col = cols[years[-2]], cols[years[-1]]
        ws = wb[sheet]
        for r in range(1, min(ws.max_row, 200) + 1):
            try:
                a, b = ev.cell(sheet, f"{prev_col}{r}"), ev.cell(sheet, f"{cur_col}{r}")
            except Exception:
                continue
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a) >= 100:
                chg = (b - a) / abs(a)
                if abs(chg) > thr:
                    label = next((ws[f"{lc}{r}"].value for lc in "ABCDEF"
                                  if isinstance(ws[f"{lc}{r}"].value, str)), f"row {r}")
                    out.append((sheet, f"{cur_col}{r}",
                                f"{label}: {a:,.0f} -> {b:,.0f} ({chg*100:+.0f}%)"))
    out.sort(key=lambda x: -abs(float(x[2].split("(")[-1].rstrip("%)").replace('+', ''))))
    return out[:25]
