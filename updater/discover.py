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
    ("total current assets", r"total\s+current\s+assets|流动资产(?:总计|合计)"),
    ("total non-current assets", r"total\s+non-?current\s+assets|非流动资产(?:总计|合计)"),
    ("total assets", r"^\s*total\s+assets\b|资产(?:总计|合计)"),
    ("total current liabilities", r"total\s+current\s+liabilities|流动负债(?:总计|合计)"),
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
        return None, None
    if isinstance(v, (int, float)):
        y = int(v)
        if YEAR_MIN <= y <= YEAR_MAX and abs(v - y) < 0.5:
            return y, None
        return None, None
    if hasattr(v, "year"):
        if YEAR_MIN <= v.year <= YEAR_MAX:
            return v.year, ("1H" if v.month in (6, 9) else None)
        return None, None
    if isinstance(v, str):
        t = v.strip().upper()
        # compact interim forms measured on live models: H125 = 1H-2025,
        # H225E = 2H-2025 estimate, Q106 = Q1-2006, 1H2025, 2025H1
        m = re.match(r"^H([12])(\d{2})E?$", t)
        if m:
            return 2000 + int(m.group(2)), f"{m.group(1)}H"
        m = re.match(r"^Q([1-4])(\d{2})E?$", t)
        if m:
            return 2000 + int(m.group(2)), f"{m.group(1)}Q"
        m = re.match(r"^([12])H(19\d{2}|20\d{2})$", t) \
            or re.match(r"^(?:(19\d{2}|20\d{2})H([12]))$", t)
        if m:
            g = m.groups()
            return (int(g[1]), f"{g[0]}H") if len(g[0]) == 1 \
                else (int(g[0]), f"{g[1]}H")
        m = re.match(r"^([1-4])Q(19\d{2}|20\d{2})$", t) \
            or re.match(r"^(19\d{2}|20\d{2})Q([1-4])$", t)
        if m:
            g = m.groups()
            return (int(g[1]), f"{g[0]}Q") if len(g[0]) == 1 \
                else (int(g[0]), f"{g[1]}Q")
        m = re.search(r"(19\d{2}|20\d{2})", t)
        if m:
            interim = bool(_INTERIM_TEXT.search(v)
                           or re.search(r"[-/](?:06|6)[-/]30|[-/](?:09|9)[-/]30", v))
            return int(m.group(1)), ("1H" if interim else None)
    return None, None


def find_year_axis(ws, period_kind="FY"):
    """{year(str): column} from the top rows, or None.

    Candidate = a consecutive ascending run of year marks (>= _MIN_RUN).
    Scoring: match the PERIOD KIND first (an FY update must bind the annual
    panel, an interim update the interim panel — the 1H-panel trap), then
    run length, then topmost row."""
    from .evaluator import n2col
    pk = period_kind.upper()
    want_tag = None if pk == "FY" else pk       # '1H','2H','1Q'..'4Q'
    if want_tag in ("H1", "H2"):
        want_tag = want_tag[1] + "H"
    want_interim = want_tag is not None
    cands = []
    for row in ws.iter_rows(min_row=1, max_row=min(_SCAN_ROWS, ws.max_row)):
        marks = []
        for c in row:
            y, tag = _year_of(getattr(c, "value", None))
            if y is None or not getattr(c, "column", None):
                continue
            if want_interim:
                if tag != want_tag:
                    continue                     # H1 runs see H1 columns only
                marks.append((c.column, y, True))
            else:
                if tag is not None:
                    continue                     # FY runs never see interim cols
                marks.append((c.column, y, False))
        min_run = 2 if want_interim else _MIN_RUN
        if len(marks) < min_run:
            continue
        run = [marks[0]]
        runs = []
        for prev, cur in zip(marks, marks[1:]):
            if cur[1] == prev[1] + 1 and cur[0] > prev[0]:
                run.append(cur)
            else:
                if len(run) >= min_run:
                    runs.append(run)
                run = [cur]
        if len(run) >= min_run:
            runs.append(run)
        rowno = next((c.row for c in row if hasattr(c, "row")), 99)
        for rn in runs:
            interim_frac = sum(1 for _c, _y, i in rn if i) / len(rn)
            kind_match = (interim_frac >= 0.5) == want_interim
            cands.append((kind_match, len(rn), -rowno, rn))
    if not cands:
        return None
    cands.sort(reverse=True)
    best = cands[0][3]
    return {str(y): n2col(col) for col, y, _i in best}


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
    for ws in wb_v.worksheets:
        sheet = ws.title
        if sheet in skip_sheets or ws.sheet_state != "visible":
            continue
        axis = find_year_axis(ws, period_kind)
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
        for r in find_check_rows(ws_f, ws, axis):
            spec["check_rows"].append({"sheet": sheet, "row": r, "expect": 0})
        spec["key_rows"] += find_key_rows(ws, axis, sheet)
    return spec
