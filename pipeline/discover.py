"""Anatomy discovery — the agent works out the model's shape by itself.

The owner's genericity mandate: the agent must REASON which column holds
which year, where the checks are, which rows are the keys — never be told
to "remember column U". This module is the deterministic first pass: it
reads the workbook the way an analyst skims one, and emits a draft spec
the run (and the analyst, via the _SPEC tab) can review. Ambiguity is left
OUT of the draft — the objective loop and the analyst resolve what code
cannot prove.

Signals used (all language- and layout-agnostic):
- YEAR AXIS: the top-of-sheet row holding the longest run of consecutive
  year marks. A year mark is a number 1990-2100, a date, or text containing
  one ('FY2024', '2024A', '2024-12-31', '2024年'). Longest run wins; the
  topmost row breaks ties.
- CHECK ROWS: rows labelled like a check (check / 差额 / 平衡 / balance
  test) OR formula rows whose cached value is ~0 across >= 3 year columns
  while their formula subtracts (a designed identity, not an empty row).
- KEY ROWS: the analyst's headline lines, matched by a multilingual
  pattern table on the row labels, first hit per (sheet, key).
"""
import re

YEAR_MIN, YEAR_MAX = 1990, 2100
_SCAN_ROWS = 12
_MIN_RUN = 4
_LABEL_COLS = ("A", "B", "C", "D")

_CHECK_LABEL = re.compile(r"check|差额|平衡|balance test|检验|校验", re.IGNORECASE)

KEY_PATTERNS = (
    ("revenue", r"^\s*(?:total\s+)?(?:revenue|turnover|sales)\b|营业总收入|营业收入|收入合计"),
    ("gross profit", r"gross\s+profit|毛利(?!率)"),
    ("operating profit", r"operating\s+profit|^\s*ebit\b|营业利润"),
    ("net profit", r"net\s+profit|profit\s+attributable|归属于母公司(?:股东|所有者)的净利润|净利润"),
    ("eps", r"^\s*eps\b|earnings\s+per\s+share|每股收益"),
    ("total non-current assets", r"total\s+non-?current\s+assets|非流动资产(?:总计|合计)"),
    ("total current assets", r"total\s+current\s+assets|(?<!非)流动资产(?:总计|合计)"),
    ("total assets", r"^\s*total\s+assets\b|资产(?:总计|合计)"),
    # THE HALVES OF THE BALANCE SHEET ARE KEYS (owner 2026-09-17: perpetuals
    # plugged into a liability row leave 'non-current liabilities' off the print
    # while total liabilities and equity still ties — the balance check cannot
    # see it, the halves can). The label's own '非' / 'non-' decides which half.
    ("total non-current liabilities", r"total\s+non-?current\s+liabilities|非流动负债(?:总计|合计)"),
    ("total current liabilities", r"total\s+current\s+liabilities|(?<!非)流动负债(?:总计|合计)"),
    ("total liabilities", r"^\s*total\s+liabilities\b(?!\s+and)|负债(?:总计|合计)"),
    ("total equity", r"total\s+(?:shareholders'?\s+)?equity|所有者权益(?:总计|合计)|股东权益(?:总计|合计)"),
    ("operating cash flow", r"operating\s+cash\s*flow|cash\s+(?:generated\s+)?from\s+operat|经营活动产生的现金流量净额"),
    ("investing cash flow", r"investing\s+cash\s*flow|cash\s+.*investing|投资活动产生的现金流量净额"),
    ("financing cash flow", r"financing\s+cash\s*flow|cash\s+.*financing|筹资活动产生的现金流量净额"),
    ("cash year end", r"cash\s*-?\s*(?:at\s+)?year\s*end|期末现金及现金等价物余额|cash\s+and\s+cash\s+equivalents\s+at\s+end"),
)


_INTERIM_TEXT = re.compile(r"\b[1-4]Q|Q[1-4]\b|\b[12]H|H[12]\b|半年|中期|interim",
                           re.IGNORECASE)


def _year_of(v):
    """(year, interim) for a cell's year mark, or (None, False).

    interim marks a half/quarter-period column ('1H2024', '2024-06-30',
    'Q3'): a sheet can hold an annual panel AND an interim panel side by
    side (measured on a live model), and an FY update writing into the 1H
    column is a real shipped disease class. Dates flag interim when they
    are not a year-end month (a consistent 06-30 panel is a half-year
    panel; Dec-end and Jan/Mar fiscal ends stay annual-plausible)."""
    if isinstance(v, bool):
        return None, False
    if isinstance(v, (int, float)):
        y = int(v)
        if YEAR_MIN <= y <= YEAR_MAX and abs(v - y) < 0.5:
            return y, False
        return None, False
    if hasattr(v, "year"):
        if YEAR_MIN <= v.year <= YEAR_MAX:
            return v.year, v.month in (6, 9)
        return None, False
    if isinstance(v, str):
        m = re.search(r"(19\d{2}|20\d{2})", v)
        if m:
            interim = bool(_INTERIM_TEXT.search(v)
                           or re.search(r"[-/](?:06|6)[-/]30|[-/](?:09|9)[-/]30", v))
            return int(m.group(1)), interim
        # TWO-DIGIT PERIOD MARKS (run 256: the Model sheet's half-year
        # panel is headed 'H120 … H125', the Driver's 'H124 H224 H125
        # H225E' — the sheet was 'left out of this run' and its check row
        # never gated the unbalanced column): H1yy / 1Hyy / H2yy / Q3yy /
        # FYyy, an optional trailing A/E
        m2 = re.fullmatch(r"\s*(?:(H[12]|[12]H|Q[1-4]|[1-4]Q|FY)\s*'?(\d{2}))\s*[AEae]?\s*", str(v))
        if m2:
            tag, yy = m2.group(1).upper(), int(m2.group(2))
            return 2000 + yy, tag != "FY"
    return None, False


def period_tag(v):
    """'FY' | 'H1' | 'H2' | 'Q1'..'Q4' for a header mark, from its text or
    date; annual marks are 'FY'. The axis groups runs by tag so H1 and H2
    columns that alternate on one row form two panels, not a broken one."""
    if hasattr(v, "year") and not isinstance(v, (int, float, bool)):
        return {3: "Q1", 6: "H1", 9: "Q3"}.get(getattr(v, "month", 12), "FY")
    t = str(v).upper()
    m = re.search(r"(?:^|[^A-Z0-9])(H[12]|[12]H|Q[1-4]|[1-4]Q)(?![A-Z])", t)
    if m:
        g = m.group(1)
        return {"1H": "H1", "2H": "H2", "1Q": "Q1", "2Q": "Q2", "3Q": "Q3", "4Q": "Q4"}.get(g, g)
    if re.search(r"[-/](?:06|6)[-/]30", t):
        return "H1"
    if re.search(r"[-/](?:09|9)[-/]30", t):
        return "Q3"
    if re.search(r"[-/](?:03|3)[-/]31", t):
        return "Q1"
    return "FY"


def header_resolver(workbook):
    """Read header expressions without depending on saved Excel caches.

    A direct reference preserves its text/date type. Numeric header formulas
    use the existing evaluator. Unknown or circular expressions prove no year.
    This is a read-only view; the workbook's cells and formatting stay intact.
    """
    from .evaluator import Evaluator
    evaluator, memo, visiting = Evaluator(workbook), {}, set()
    direct = re.compile(r"^=\s*\+?\s*(?:(?:'((?:[^']|'')+)'|([^!]+))!)?"
                        r"(\$?[A-Za-z]{1,3}\$?\d+)\s*$")

    def value(sheet, coord):
        key = (sheet, coord)
        if key in memo:
            return memo[key]
        if key in visiting:
            return None
        visiting.add(key)
        try:
            raw = workbook[sheet][coord].value
            if isinstance(raw, str) and raw.startswith("="):
                match = direct.fullmatch(raw)
                if match:
                    target = (match.group(1) or match.group(2) or sheet).strip().replace("''", "'")
                    result = value(target, match.group(3).replace("$", "").upper())
                else:
                    result = evaluator.cell(sheet, coord)
                    if evaluator.cycles:
                        result = None
            else:
                result = raw
        except Exception:
            result = None
        finally:
            visiting.remove(key)
        memo[key] = result
        return result
    return value


def find_year_axis(ws, period_kind="FY", resolve_header=None):
    """{year(str): column} from the top rows, or None.

    Candidate = a consecutive ascending run of year marks (>= _MIN_RUN).
    Scoring: match the PERIOD KIND first (an FY update must bind the annual
    panel, an interim update the interim panel — the 1H-panel trap), then
    run length, then topmost row."""
    from .evaluator import n2col
    resolve_header = resolve_header or header_resolver(ws.parent)
    want_interim = period_kind.upper() != "FY"
    want_tag = {"1H": "H1", "H1": "H1", "2H": "H2", "H2": "H2"}.get(period_kind.upper())
    # ONE MARK PER COLUMN, THE TEXT MARK WINS (run 256 autopsy): a column's
    # header rows usually carry a date AND a text mark ('2024-06-30' over
    # '1H2024'; '2024-06-30' over '2Q2024'). A date is ambiguous — June 30
    # is a half-year end AND a quarter end — the text says which. Runs
    # are then built WITHIN a period tag, so H1 | H2 | H1 | H2 alternating
    # on one row holds two panels and a quarterly block never outvotes
    # the half-year panel.
    percol = {}                       # col -> (year, tag, from_text, row)
    for row in ws.iter_rows(min_row=1, max_row=min(_SCAN_ROWS, ws.max_row)):
        for c in row:
            v = getattr(c, "value", None)
            if v is None or (isinstance(v, str) and v.startswith("=")):
                v = resolve_header(ws.title, c.coordinate)
            y, _interim = _year_of(v)
            if y is None or not getattr(c, "column", None):
                continue
            is_text = isinstance(v, str)
            cur = percol.get(c.column)
            if cur is None or (is_text and not cur[2]):
                percol[c.column] = (y, period_tag(v), is_text, c.row)
    marks = sorted((col, y, tag, r, t) for col, (y, tag, t, r) in percol.items())
    runs = []
    for tag in sorted({m_[2] for m_ in marks}):
        if want_interim and want_tag and tag != want_tag:
            continue
        if want_interim and not want_tag and not tag.startswith("Q"):
            continue
        if not want_interim and tag != "FY":
            continue
        tm = [m_ for m_ in marks if m_[2] == tag]

        def _keep(run):
            # an interim panel named in TEXT (H124 | H125) is a panel at two
            # marks — the tag is the evidence; date-only runs keep the bar
            need = 2 if (want_interim and all(m_[4] for m_ in run)) else _MIN_RUN
            return len(run) >= need
        run = [tm[0]]
        for prev, cur in zip(tm, tm[1:]):
            if cur[1] == prev[1] + 1 and cur[0] > prev[0]:
                run.append(cur)
            else:
                if _keep(run):
                    runs.append(run)
                run = [cur]
        if _keep(run):
            runs.append(run)
    if not runs:
        return None
    best = max(runs, key=lambda rn: (len(rn), -min(m_[3] for m_ in rn)))
    return {str(y): n2col(col) for col, y, _t, _r, _x in best}


def _label(ws, r):
    for lc in _LABEL_COLS:
        v = ws[f"{lc}{r}"].value
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def find_check_rows(ws_f, ws_v, axis):
    """Rows that ARE the model's own integrity checks."""
    out = []
    cols = list(axis.values())
    for r in range(1, min(ws_f.max_row, 400) + 1):
        lab = _label(ws_f, r)
        labelled = bool(lab and _CHECK_LABEL.search(lab))
        zeroish = 0
        has_minus_formula = False
        for col in cols:
            f = ws_f[f"{col}{r}"].value
            v = ws_v[f"{col}{r}"].value
            if isinstance(f, str) and f.startswith("=") and "-" in f:
                has_minus_formula = True
                if isinstance(v, (int, float)) and abs(v) <= 0.01:
                    zeroish += 1
        if labelled and has_minus_formula and zeroish >= 2:
            out.append(r)
        elif not labelled and has_minus_formula and zeroish >= max(3, len(cols) - 2) \
                and zeroish == sum(1 for col in cols
                                   if isinstance(ws_f[f"{col}{r}"].value, str)
                                   and ws_f[f"{col}{r}"].value.startswith("=")):
            out.append(r)
    return out


def zero_difference_rows(ws_f, ws_v, axis, min_years=3, target_year=None, wb_f=None):
    """THE MODEL'S OWN CHECKS WHEN NOTHING IS LABELLED (owner 2026-09-17, the CX
    cold model: a wide single sheet, no 'check' anywhere, and objective 1 could
    not be measured at all). A row whose formula SUBTRACTS and comes out at zero
    in every HISTORY year it computes, over operands that are not themselves
    zero, IS a check — the model testing itself, whatever it is called. A
    measurement of the model's own arithmetic, not a judgment about meaning.
    -> [row]"""
    years = sorted(y for y in axis if str(y).isdigit()
                   and (target_year is None or int(y) < int(target_year)))
    cols = [axis[y] for y in years[-6:]] or list(axis.values())[:6]
    ev = None
    if wb_f is not None:
        try:
            from .evaluator import Evaluator
            ev = Evaluator(wb_f)
        except Exception:  # noqa: BLE001
            ev = None
    sheet = ws_f.title

    def _value(col, r):
        v = ws_v[f"{col}{r}"].value
        if isinstance(v, (int, float)):
            return v
        if ev is None:
            return None
        try:                       # a workbook saved with no cached values
            return ev.cell(sheet, f"{col}{r}")
        except Exception:  # noqa: BLE001
            return None
    out = []
    for r in range(1, min(ws_f.max_row, 400) + 1):
        zeros = nonzero = alive = 0
        for col in cols:
            f = ws_f[f"{col}{r}"].value
            if not (isinstance(f, str) and f.startswith("=") and "-" in f):
                continue
            v = _value(col, r)
            if not isinstance(v, (int, float)):
                continue
            if abs(v) > 0.01:
                nonzero += 1
                continue
            zeros += 1
            # A ZERO OVER NOTHING IS NOT A CHECK (CX 2026-09-17: '=B27/B40-1'
            # reads 0 because both cells are empty). Something the row
            # subtracts must itself be a real number.
            for m in re.finditer(r"(?<![A-Z0-9])([A-Z]{1,3})\$?(\d+)", str(f)):
                ov = _value(m.group(1), int(m.group(2)))
                if isinstance(ov, (int, float)) and abs(ov) >= 1:
                    alive += 1
                    break
        if zeros >= min_years and nonzero == 0 and alive >= min_years:
            out.append(r)
    return out


def find_key_rows(ws, axis, sheet):
    """First label hit per key pattern, provided the row holds numbers."""
    cols = list(axis.values())
    out, seen = [], set()
    for r in range(1, min(ws.max_row, 400) + 1):
        lab = _label(ws, r)
        if not lab:
            continue
        has_num = any(isinstance(ws[f"{c}{r}"].value, (int, float))
                      for c in cols[:6])
        if not has_num:
            continue
        for name, pat in KEY_PATTERNS:
            if name in seen:
                continue
            if re.search(pat, lab, re.IGNORECASE):
                out.append({"name": name, "sheet": sheet, "row": r})
                seen.add(name)
                break
    return out


def discover(wb_f, wb_v, target_year=None, period_kind="FY",
             skip_sheets=("_REPORT", "_SPEC")):
    """-> draft spec dict {year_axis, check_rows, key_rows, auto_discovered}.

    Sheets whose axis does not reach the target year (pure history dumps
    with no forecast need) still enter the axis — the runner only rolls
    sheets that map both the target and prior years.
    """
    spec = {"year_axis": {}, "check_rows": [], "key_rows": [],
            "auto_discovered": True}
    resolve_header = header_resolver(wb_f)
    for ws in wb_v.worksheets:
        sheet = ws.title
        if sheet in skip_sheets:
            continue
        axis = find_year_axis(ws, period_kind, resolve_header=resolve_header)
        if not axis:
            continue
        if target_year is not None and str(target_year) not in axis:
            # extend one year past the last mark: analysts add the new
            # column at roll-forward; discovery must offer it
            from .evaluator import col2n, n2col
            years = sorted(axis)
            last_y, last_c = years[-1], axis[years[-1]]
            if int(last_y) + 1 == int(target_year):
                axis[str(target_year)] = n2col(col2n(last_c) + 1)
        spec["year_axis"][sheet] = {"columns": axis}
        ws_f = wb_f[sheet]
        found = find_check_rows(ws_f, ws, axis)
        if not found:
            found = zero_difference_rows(ws_f, ws, axis, target_year=target_year, wb_f=wb_f)
            if found:
                spec.setdefault("check_notes", []).append(
                    f"{sheet}: {len(found)} check row(s) found by the model's own arithmetic — rows whose "
                    f"formula subtracts and comes out at zero in every year it computes (rows "
                    f"{', '.join(str(x) for x in found[:8])}); nothing on this sheet is labelled a check")
        for r in found:
            spec["check_rows"].append({"sheet": sheet, "row": r, "expect": 0})
        spec["key_rows"] += find_key_rows(ws, axis, sheet)
    if not spec["check_rows"]:
        spec.setdefault("check_notes", []).append(
            "NO CHECK ROW IN THIS MODEL: no row subtracts two live totals to zero in its history, on any "
            "sheet with a year axis. Objective 1 (balance) cannot be measured from the model's own "
            "arithmetic — the anatomy turn must name the identity, or the analyst must.")
    return spec
