"""The executive _REPORT page — Luna COMPOSES it, the code RENDERS and
REFEREES it.

Owner's design lock (2026-08-28, REPORT_REQUIREMENTS.md in studio-native/):
a management page readable in one minute, three blocks —

  1. Key number snapshot  — the mindmap objective list, live formulas
  2. Why it moved         — bridges: P&L keys EVERY time, BS/CF keys only
                            when the move is material (~20%+). Composed by
                            the agent's REASONING, never a word search.
                            Every walk line is a traceable FORMULA; each
                            bridge ends in a self-balancing residual.
  3. Needs your attention — plugs, then red rulings (as questions), then
                            orange derivations. A few words per note.

Division of labour (the referee rule): the LLM decides WHAT the page says
— which rows are the key numbers in THIS model, what actually drove each
change, how each ruling is phrased. The code draws the format and REFUSES
what does not tie: a walk line whose formula does not evaluate to its
claimed value, or a bridge whose lines do not sum to its claimed change.
A wrong story rendered confidently is worse than no story.

Report-only mode regenerates the page on an ALREADY-updated model without
re-running the update:

    python -m pipeline.execreport "<company_dir>" \
        --model=<updated model.xlsx> --pre=<archived pre-update model.xlsx>

--selftest runs the offline museum (no LLM, no files touched).
"""
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- facts

RED_FILLS = {"FFC7CE"}
ORANGE_FILLS = {"FFC000"}
MAX_ROW = 300


def _fill_code(cell):
    try:
        rgb = cell.fill.start_color.rgb
    except AttributeError:
        return ""
    if not isinstance(rgb, str):
        return ""
    return rgb[-6:].upper()


def _label_of(ws, row, max_col=6):
    for c in range(1, max_col + 1):
        v = ws.cell(row=row, column=c).value
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def gather_facts(wb, pre_wb, target_col=21, prior_col=20,
                 pre_est_col=21, pre_next_col=22):
    """Everything Luna needs to compose, as plain data. Deterministic."""
    facts = {"model_rows": [], "raw_rows": [], "estimates": [], "flags": []}
    ws = wb["Model"]
    for r in range(3, min(ws.max_row, MAX_ROW) + 1):
        lab = _label_of(ws, r)
        if not lab:
            continue
        t = ws.cell(row=r, column=prior_col).value
        u = ws.cell(row=r, column=target_col).value
        facts["model_rows"].append(
            [r, lab,
             round(t, 1) if isinstance(t, (int, float)) else None,
             round(u, 1) if isinstance(u, (int, float)) else None])
    rf = wb["Raw financials"]
    for r in range(3, min(rf.max_row, MAX_ROW) + 1):
        lab = _label_of(rf, r, max_col=3)
        t = rf.cell(row=r, column=prior_col).value
        u = rf.cell(row=r, column=target_col).value
        if lab and (isinstance(t, (int, float)) or isinstance(u, (int, float))):
            facts["raw_rows"].append(
                [r, lab,
                 round(t, 1) if isinstance(t, (int, float)) else None,
                 round(u, 1) if isinstance(u, (int, float)) else None])
    if pre_wb is not None and "Model" in pre_wb.sheetnames:
        pm = pre_wb["Model"]
        for r in range(3, min(pm.max_row, MAX_ROW) + 1):
            lab = _label_of(pm, r)
            e = pm.cell(row=r, column=pre_est_col).value
            n = pm.cell(row=r, column=pre_next_col).value
            if lab and isinstance(e, (int, float)):
                facts["estimates"].append(
                    [r, lab, round(e, 1),
                     round(n, 1) if isinstance(n, (int, float)) else None])
    for sheet in wb.sheetnames:
        if sheet.startswith("_"):
            continue
        sws = wb[sheet]
        for row in sws.iter_rows(min_row=1,
                                 max_row=min(sws.max_row, MAX_ROW)):
            for cell in row:
                code = _fill_code(cell)
                if code in RED_FILLS or code in ORANGE_FILLS:
                    note = ""
                    if cell.comment is not None:
                        note = str(cell.comment.text)[:200]
                    facts["flags"].append(
                        [sheet, cell.coordinate,
                         "red" if code in RED_FILLS else "orange", note])
    return facts

# ------------------------------------------------------------- referee

_REF = re.compile(r"'?([A-Za-z_][A-Za-z0-9_ ]*?)'?!([A-Z]{1,3})([0-9]{1,4})")
_SAFE = re.compile(r"^[0-9+\-*/(). ]*$")


def _eval_formula(wb, formula):
    """Evaluate the +-*/() cell-reference grammar the bridges use, from
    TYPED values only. Returns (value, verifiable). A reference landing on
    a formula cell (no cached value) makes the line unverifiable — the sum
    law still binds it."""
    from openpyxl.utils import column_index_from_string
    expr = formula.lstrip("=")
    verifiable = True

    def sub(m):
        nonlocal verifiable
        sheet, col, row = m.group(1), m.group(2), int(m.group(3))
        if sheet not in wb.sheetnames:
            verifiable = False
            return "0"
        v = wb[sheet].cell(row=row,
                           column=column_index_from_string(col)).value
        if v is None:
            return "0"                      # blank reads as 0, like Excel
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return repr(float(v))
        verifiable = False                  # formula cell without a cache
        return "0"
    expr = _REF.sub(sub, expr)
    if not verifiable or not _SAFE.match(expr):
        return None, False
    try:
        return float(eval(expr, {"__builtins__": {}})), True
    except Exception:
        return None, False



def _is_circular(bridge, formula):
    """A pure +/- walk line that references the bridge's own anchor row."""
    if "*" in formula or "/" in formula:
        return False
    bs = str(bridge.get("sheet", "Model")).strip().lower()
    try:
        brow = int(bridge.get("row", 0))
    except (TypeError, ValueError):
        return False
    for m in _REF.finditer(formula):
        if m.group(1).strip().lower() == bs and int(m.group(3)) == brow:
            return True
    return False


def referee(summary, wb):
    """Refuse what does not tie. Returns (kept_bridges, refusals)."""
    kept, refusals = [], []
    for b in summary.get("bridges", []):
        why = []
        total = b.get("total")
        if not isinstance(total, (int, float)):
            why.append("bridge '%s': no claimed total" % b.get("title"))
        lines = b.get("lines", [])
        ssum = 0.0
        for ln in lines:
            lab = str(ln.get("label", "")).strip().lower()
            f = str(ln.get("formula", ""))
            if re.match(r"^(other|residual)", lab):
                why.append("line '%s': never write your own Other/Residual "
                           "line — the renderer adds it" % ln.get("label"))
                continue
            # circular: a pure +/- line that references the very row it is
            # supposed to explain is a tautology (total minus the other
            # lines), not a driver. Multiplicative forms are exempt — the
            # sanctioned volume/margin split references its own row.
            if _is_circular(b, f):
                why.append("line '%s': circular — a plus/minus line may "
                           "not reference the bridge's own total row; "
                           "derive the driver from the underlying rows "
                           "instead" % ln.get("label"))
                continue
            val = ln.get("value")
            if not isinstance(val, (int, float)):
                why.append("line '%s': no value" % ln.get("label"))
                continue
            ssum += val
            got, ok = _eval_formula(wb, str(ln.get("formula", "")))
            if ok and abs(got - val) > max(0.5, abs(val) * 0.01):
                why.append(
                    "line '%s': formula evaluates to %.1f but claims %.1f"
                    % (ln.get("label"), got, val))
        if isinstance(total, (int, float)):
            if abs(ssum - total) > max(1.0, abs(total) * 0.02):
                why.append(
                    "bridge '%s': lines sum to %.1f but claims a change of "
                    "%.1f — the walk must add up (use the residual for the "
                    "remainder)" % (b.get("title"), ssum, total))
        if why:
            refusals.append({"bridge": b.get("title"), "why": why})
        else:
            kept.append(b)
    return kept, refusals

# ------------------------------------------------------------- renderer

NUM, SGN, PCT = '#,##0.0', '+#,##0.0;-#,##0.0', '0.0%'


def render(wb, summary, target_col_letter="U", prior_col_letter="T",
           next_col_letter="V"):
    """The owner's v3 layout, exactly. Deterministic."""
    from openpyxl.styles import Border, Font, PatternFill, Side
    BANNER = PatternFill("solid", fgColor="FFF2CC")
    SECT = PatternFill("solid", fgColor="F2F2F2")
    TINT_O = PatternFill("solid", fgColor="FDEBD0")
    TINT_R = PatternFill("solid", fgColor="FADBD8")
    GREY = Font(color="7F7F7F", size=10)
    GREYI = Font(color="7F7F7F", size=10, italic=True)
    BOLD = Font(bold=True, size=11)
    SECTF = Font(bold=True, size=12)
    BANF = Font(bold=True, size=13)
    BODY = Font(size=11)
    SMALL = Font(size=10)
    THIN = Border(bottom=Side(style="thin", color="BFBFBF"))
    T, U, V = prior_col_letter, target_col_letter, next_col_letter

    if "_REPORT" in wb.sheetnames:
        del wb["_REPORT"]
    ws = wb.create_sheet("_REPORT", 0)
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 46
    for col in "BCDEFGH":
        ws.column_dimensions[col].width = 13
    r = 1

    def cell(row, col, val, font=None, fill=None, fmt=None, border=None):
        c = ws.cell(row=row, column=col, value=val)
        c.font = font if font else BODY
        if fill:
            c.fill = fill
        if fmt:
            c.number_format = fmt
        if border:
            c.border = border
        return c

    def band(row, fill, h=None):
        for c in range(1, 9):
            ws.cell(row=row, column=c).fill = fill
        if h:
            ws.row_dimensions[row].height = h

    def gap(h=8):
        nonlocal r
        ws.row_dimensions[r].height = h
        r += 1

    def sect(title):
        nonlocal r
        cell(r, 1, title, SECTF, SECT)
        band(r, SECT, 22)
        r += 1
        gap(6)

    cell(r, 1, str(summary.get("banner", ""))[:140], BANF, BANNER)
    cell(r, 6, str(summary.get("coverage", ""))[:90], GREY, BANNER)
    band(r, BANNER, 30)
    r += 1
    gap(14)

    sect("1 · Key number snapshot   (RMB mn)")
    hdr = ["", "FY prior A", "FY actual A", "YoY", "Your estimate",
           "A vs E", "Next yr before", "Next yr after"]
    for i, h in enumerate(hdr):
        cell(r, i + 1, h, GREY, None, None, THIN)
    r += 1
    for grp in summary.get("snapshot", []):
        cell(r, 1, str(grp.get("group", ""))[:30], GREYI)
        r += 1
        for it in grp.get("rows", []):
            mr = int(it["row"])
            sheet = it.get("sheet", "Model")
            q = "'%s'" % sheet if re.search(r"[^A-Za-z0-9]", sheet) else sheet
            cell(r, 1, '=HYPERLINK("#%s!%s%d","%s")'
                 % (sheet.replace("'", ""), U, mr,
                    str(it.get("label", ""))[:40]))
            cell(r, 2, "=%s!%s%d" % (q, T, mr), None, None, NUM)
            cell(r, 3, "=%s!%s%d" % (q, U, mr), None, None, NUM)
            cell(r, 4, '=IFERROR(IF(B%d<=0,"n/m",C%d/B%d-1),"")'
                 % (r, r, r), None, None, PCT)
            est = it.get("est")
            cell(r, 5, est if isinstance(est, (int, float)) else "",
                 None, None, NUM)
            cell(r, 6, '=IFERROR(IF(E%d<=0,"n/m",C%d/E%d-1),"")'
                 % (r, r, r), None, None, PCT)
            nb = it.get("next_before")
            cell(r, 7, nb if isinstance(nb, (int, float)) else "",
                 None, None, NUM)
            cell(r, 8, "=%s!%s%d" % (q, V, mr), None, None, NUM)
            r += 1
    gap(14)

    sect("2 · Why it moved   (actual vs prior year · P&L always · "
         "BS/CF when the move is material, ~20%+)")
    for b in summary.get("bridges", []):
        mr = int(b["row"])
        sheet = b.get("sheet", "Model")
        q = "'%s'" % sheet if re.search(r"[^A-Za-z0-9]", sheet) else sheet
        trow = r
        cell(r, 1, '=HYPERLINK("#%s!%s%d","%s")'
             % (sheet.replace("'", ""), U, mr, str(b.get("title", ""))[:60]),
             BOLD)
        cell(r, 2, "=%s!%s%d-%s!%s%d" % (q, U, mr, q, T, mr),
             BOLD, None, SGN)
        r += 1
        first = r
        for ln in b.get("lines", []):
            f = str(ln.get("formula", "")).strip()
            if f and not f.startswith("="):
                f = "=" + f          # Luna often omits it; text is useless
            cell(r, 1, "      " + str(ln.get("label", ""))[:60], SMALL)
            cell(r, 2, f, SMALL, None, SGN)
            r += 1
        cell(r, 1, "      Other / residual", GREYI)
        cell(r, 2, "=B%d-SUM(B%d:B%d)" % (trow, first, r - 1),
             GREY, None, SGN)
        r += 1
        gap(10)
    for note in (summary.get("skipped_note"), summary.get("company_note")):
        if note:
            cell(r, 1, str(note)[:200], GREYI)
            r += 1
    gap(14)

    sect("3 · Needs your attention")
    tiers = [("plugs", "Plugs — inserted to make the model tie; "
              "resolve properly", TINT_O),
             ("red", "Red — unsure, your ruling", TINT_R),
             ("orange", "Orange — derived, not read", TINT_O)]
    attention = summary.get("attention", {})
    for key, header, fill in tiers:
        items = attention.get(key, [])
        if not items:
            continue
        cell(r, 1, header, BOLD, fill)
        band(r, fill, 20)
        r += 1
        for it in items:
            if not isinstance(it, dict):
                continue
            sheet, addr = str(it.get("sheet", "")), str(it.get("cell", ""))
            if sheet not in wb.sheetnames or not re.match(
                    r"^[A-Z]{1,3}[0-9]{1,4}$", addr):
                continue
            q = ("'%s'" % sheet if re.search(r"[^A-Za-z0-9]", sheet)
                 else sheet)
            cell(r, 1, '=HYPERLINK("#\'%s\'!%s","%s!%s")'
                 % (sheet, addr, sheet, addr), SMALL)
            cell(r, 2, "=%s!%s" % (q, addr), SMALL, None, NUM)
            cell(r, 3, str(it.get("note", ""))[:90], SMALL)
            r += 1
        gap(8)
    if summary.get("other_note"):
        cell(r, 1, str(summary["other_note"])[:200], GREYI)
        r += 1
    wb.active = 0
    return r

# ------------------------------------------------------------- compose

SYSTEM = """You are an equity research analyst writing the one-page
executive report of a model update, as JSON. You are given the model's
own data; you COMPOSE the page by reasoning about it — never by matching
words. The renderer draws the format; a referee will REFUSE any bridge
whose lines do not tie. Respond with ONE JSON object, nothing else.

THE PAGE (owner's locked design):
1. "snapshot": the KEY NUMBERS, fixed by the objective: sales/revenue,
   gross profit, net profit, cash, current assets, non-current assets,
   current liabilities, non-current liabilities, total equity, and
   operating / investing / financing cash flow. FIND each one's row in
   the model_rows list (labels differ per model — reason it out). Group
   as P&L / Balance sheet / Cash flow. For each row attach the
   analyst's pre-update estimate and next-year forecast from the
   estimates list (same row numbers) when present.
2. "bridges": WHY each key number moved, year on year. P&L key numbers
   get a bridge EVERY time. Balance-sheet and cash-flow key numbers get
   one ONLY when the move is material (roughly 20%+ change). THINK about
   what actually drove each change by comparing the raw_rows year on
   year — name the few drivers that explain it (2-6 lines), biggest
   first. Every line carries:
   - "label": a short English driver name (your judgment, not the raw
     Chinese label),
   - "formula": an Excel formula deriving the amount from the workbook,
     using ONLY refs like 'Raw financials'!U18-'Raw financials'!T18 or
     Model!U7-Model!T7 (U = actual year, T = prior year; +,-,*,/ and
     parentheses allowed),
   - "value": the number the formula evaluates to (RMB mn, 1dp).
   Also give the bridge's "total" = the key number's actual change.
   Lines must sum close to total; a residual line is added for you —
   NEVER add your own "Other"/"Residual" line (it will be refused).
   A bridge explains WHAT DROVE the change, not the statement's own
   structure: for net profit, name the operating drivers (gross profit,
   investment income, impairments, operating expenses, tax, minorities)
   — "pre-tax profit + tax" explains nothing. A plus/minus line that
   references the bridge's own total row is circular and will be
   refused. Prefer typed 'Raw financials' rows, which the referee can
   verify; a working-capital or funding story usually lives there.
   For gross profit use the volume/margin split:
     volume = (Model!U<rev>-Model!T<rev>)*Model!T<gp>/Model!T<rev>
     margin = Model!U<rev>*(Model!U<gp>/Model!U<rev>-Model!T<gp>/Model!T<rev>)
3. "attention": from the flags list, the items the analyst must rule on,
   most important first — "plugs" (numbers inserted to make the model
   tie; say in a few words what each ties), "red" (uncertain KEY numbers,
   phrased as the question the analyst must answer), "orange" (derived
   key numbers, show the derivation in words). KEY numbers only; keep
   each note under 12 words. Skip minor cells.

RULES THAT NEVER BEND:
- Every number you state must come from the data given. Never invent.
- "banner": one line, honest verdict + the biggest caveat.
- "coverage": counts line, e.g. "key numbers proven X/14 · N plugs · N rulings".
- "skipped_note": name the key numbers you judged too small to bridge,
  with their % moves, so the omission reads as deliberate.
- "company_note": ONLY a company-stated reason with a page reference
  from disclosure text given to you; if none was given, say the stated
  reasons are not in the provided documents.
- "other_note": one line pointing to the colour-marked cells in the
  model tabs.

OUTPUT SHAPE:
{"banner": str, "coverage": str,
 "snapshot": [{"group": "P&L", "rows": [{"label": str, "sheet": "Model",
   "row": int, "est": num|null, "next_before": num|null}, ...]}, ...],
 "bridges": [{"title": str, "sheet": "Model", "row": int, "total": num,
   "lines": [{"label": str, "formula": str, "value": num}, ...]}, ...],
 "skipped_note": str, "company_note": str,
 "attention": {"plugs": [{"sheet": str, "cell": str, "note": str}, ...],
   "red": [...], "orange": [...]},
 "other_note": str}"""


def _validate(d):
    if not isinstance(d, dict):
        return "not an object"
    for k in ("banner", "snapshot", "bridges", "attention"):
        if k not in d:
            return "missing key: " + k
    if not isinstance(d["snapshot"], list) or not d["snapshot"]:
        return "snapshot empty"
    for grp in d["snapshot"]:
        for it in grp.get("rows", []):
            if not isinstance(it.get("row"), int):
                return "snapshot row without an integer row number"
    for b in d["bridges"]:
        if not isinstance(b.get("row"), int):
            return "bridge without an integer row"
        if not b.get("lines"):
            return "bridge '%s' has no lines" % b.get("title")
    att = d["attention"]
    if not isinstance(att, dict):
        return "attention must be an object with plugs/red/orange lists"
    for k in ("plugs", "red", "orange"):
        for it in att.get(k, []):
            if not isinstance(it, dict) or not it.get("sheet") \
                    or not it.get("cell"):
                return ("attention.%s items must be objects "
                        '{"sheet","cell","note"}' % k)
    return None


def compose(client, facts, feedback=""):
    user = json.dumps(facts, ensure_ascii=False)
    if feedback:
        user += ("\n\nTHE REFEREE REFUSED PART OF YOUR LAST ANSWER — fix "
                 "exactly these and resend the FULL object:\n" + feedback)
    return client.json(SYSTEM, user, _validate, repair_retries=2)

# ------------------------------------------------------------ the run


def report_only(company_dir, model_path, pre_path, client, out_path=None):
    import openpyxl
    wb = openpyxl.load_workbook(model_path)
    pre_wb = (openpyxl.load_workbook(pre_path, data_only=True)
              if pre_path else None)
    facts = gather_facts(wb, pre_wb)
    summary = compose(client, facts)
    kept, refusals = referee(summary, wb)
    if refusals:
        summary = compose(client, facts, feedback=json.dumps(refusals))
        kept, refusals = referee(summary, wb)
    summary["bridges"] = kept
    if refusals:                       # surviving refusals: honest note
        summary["skipped_note"] = (
            (summary.get("skipped_note", "") + "  ·  REFUSED bridges: "
             + "; ".join(r["bridge"] or "?" for r in refusals)).strip())
    render(wb, summary)
    out = Path(out_path) if out_path else Path(model_path).with_name(
        Path(model_path).stem + " (Luna REPORT).xlsx")
    wb.save(out)
    return {"ok": True, "out": str(out), "bridges": len(kept),
            "refused": len(refusals),
            "refusals": refusals, "summary": summary}

# ------------------------------------------------------------ selftest


def _selftest():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Model"
    rf = wb.create_sheet("Raw financials")
    ws["A4"], ws["T4"], ws["U4"] = "Revenue", 100.0, 120.0
    ws["A7"], ws["T7"], ws["U7"] = "Gross profit", 20.0, 30.0
    rf["A5"], rf["T5"], rf["U5"] = "core", 90.0, 108.0
    rf["A6"], rf["T6"], rf["U6"] = "fin", 10.0, 12.0
    good = {"banner": "b", "coverage": "c",
            "snapshot": [{"group": "P&L", "rows": [
                {"label": "Revenue", "sheet": "Model", "row": 4,
                 "est": 110.0, "next_before": 130.0}]}],
            "bridges": [
                {"title": "Revenue", "sheet": "Model", "row": 4,
                 "total": 20.0, "lines": [
                     {"label": "Core",
                      "formula": "='Raw financials'!U5-'Raw financials'!T5",
                      "value": 18.0},
                     {"label": "Fin",
                      "formula": "='Raw financials'!U6-'Raw financials'!T6",
                      "value": 2.0}]},
                {"title": "Bad sum", "sheet": "Model", "row": 7,
                 "total": 10.0, "lines": [
                     {"label": "x",
                      "formula": "='Raw financials'!U6-'Raw financials'!T6",
                      "value": 2.0}]},
                {"title": "Bad line", "sheet": "Model", "row": 7,
                 "total": 10.0, "lines": [
                     {"label": "lie",
                      "formula": "='Raw financials'!U5-'Raw financials'!T5",
                      "value": 10.0}]}],
            "attention": {"plugs": [], "red": [
                {"sheet": "Model", "cell": "U7", "note": "why?"}],
                "orange": []},
            "skipped_note": "s", "company_note": "n", "other_note": "o"}
    good["bridges"] += [
        {"title": "Circular", "sheet": "Model", "row": 7, "total": 10.0,
         "lines": [{"label": "tautology",
                    "formula": "=Model!U7-Model!T7", "value": 10.0}]},
        {"title": "Own residual", "sheet": "Model", "row": 7, "total": 10.0,
         "lines": [{"label": "Residual x",
                    "formula": "='Raw financials'!U6-'Raw financials'!T6",
                    "value": 10.0}]},
        {"title": "Volume-margin ok", "sheet": "Model", "row": 7,
         "total": 10.0, "lines": [
             {"label": "Volume",
              "formula": "=(Model!U4-Model!T4)*Model!T7/Model!T4",
              "value": 4.0},
             {"label": "Margin",
              "formula": "=Model!U4*(Model!U7/Model!U4-Model!T7/Model!T4)",
              "value": 6.0}]}]
    kept, refusals = referee(good, wb)
    assert len(kept) == 2, refusals
    assert {k["title"] for k in kept} == {"Revenue", "Volume-margin ok"}
    assert len(refusals) == 4
    assert any("sum to" in w for r in refusals for w in r["why"])
    assert any("evaluates to" in w for r in refusals for w in r["why"])
    assert any("circular" in w for r in refusals for w in r["why"])
    assert any("Other/Residual" in w for r in refusals for w in r["why"])
    kept[1]["lines"][0]["formula"] = kept[1]["lines"][0]["formula"][1:]
    good["bridges"] = kept
    rows = render(wb, good)
    assert wb.sheetnames[0] == "_REPORT" and rows > 15
    rpt = wb["_REPORT"]
    flat = "|".join(str(c.value) for row in rpt.iter_rows()
                    for c in row if c.value is not None)
    assert "Key number snapshot" in flat and "Why it moved" in flat
    assert "residual" in flat and "Needs your attention" in flat
    assert "=HYPERLINK" in flat and "'Raw financials'!U5" in flat
    assert "=(Model!U4-Model!T4)*Model!T7/Model!T4" in flat  # '=' restored
    assert _validate(good) is None
    assert _validate({"banner": "x"}) is not None
    print("execreport selftest: ALL PASS")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        _selftest()
        return 0
    kv = dict(a.split("=", 1) for a in argv if a.startswith("--") and "=" in a)
    args = [a for a in argv if not a.startswith("--")]
    if not args or "--model" not in "".join(argv):
        print(__doc__)
        return 2
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from pipeline.cli import _load_env
    _load_env()
    from pipeline.llm import env_ready, make_client
    if not env_ready():
        print("needs LLM_BASE_URL / LLM_API_KEY / LLM_MODEL in env or .env")
        return 2
    client = make_client()
    res = report_only(args[0], kv["--model"], kv.get("--pre"), client,
                      kv.get("--out"))
    print("DELIVERED:", res["out"])
    print("bridges kept:", res["bridges"], "refused:", res["refused"])
    for rr in res["refusals"]:
        print("  refused:", rr)
    u = getattr(client, "usage", None)
    if u:
        print("engine:", u.get("model"), "calls:", u.get("calls"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
