"""The _REPORT page, owner's revamp of 2026-09-13 — one fixed table for
every model, rendered by code from the model itself. No prose.

  1. Verdict strip     — delivered / checks per year / keys tied / counts
  2. The table         — a FIXED list of lines (P&L, balance sheet, cash
                         flow) in a fixed order, the same on every
                         model: what changed (new vs old) with the
                         >10-point check, NEW with the printed figure
                         and YoY, OLD. A line this model has no row for
                         says so and keeps its place.
  3. Key numbers       — the model's own key rows: prior actual, actual,
                         YoY, the analyst's estimate, actual vs estimate.
  4. Look here         — the sense check's verdicts with the cell each
                         trail ended at, open checks, plugs, and the
                         flagged cells that sit on the page's own rows;
                         everything else as a count per sheet. The
                         complete list stays on _FLAGS.

THE PERIOD FOLLOWS THE RUN (owner 2026-09-13): the columns are the
model's own axis for the period updated — the annual columns on an
annual run, the half-year or quarterly panel on an interim run. Headers
are explicit (FY24A, 1H25A, FY26E). A panel with no forecast columns
says "no half-year forecast found in this model" where they would be.

HOW A LINE FINDS ITS ROW (generic, the model's own evidence): the spec's
key rows first (the run already proved which row each key is), then the
model's own label — an exact name, a whole-phrase name, or word kinship,
never a label that carries a word of another meaning (a 'tax' line is
not 'deferred tax assets'); among equals the statement's own order
decides (the row at or after the previous line of the same statement).
"""
import re

from openpyxl.styles import Border, Font, PatternFill, Side
from openpyxl.utils import column_index_from_string, get_column_letter

from .numerics import norm_label

SENSE_GAP = 0.10                     # the owner's ten points
NUM, PCT = '#,##0.0', '0.0%'
_ROLE_CTX = {}

# (key, label, group, kind, names, excluded words, spec key names)
# names: whole phrases that mean this line; a label carrying an
# excluded word is a different line (a ratio, a sub-line, a balance)
_RATIO = ("margin", "yoy", "growth", "rate", "ratio", "%", "per cent", "percent", "as of")
ROLES = [
    ("revenue", "Revenue", "P&L", "value",
     ["revenue", "total revenue", "revenues", "turnover", "sales", "net sales", "营业收入", "营业总收入"],
     _RATIO + ("cost", "segment", "other", "deferred", "unearned"), ["revenue", "sales"]),
    ("gross_profit", "Gross profit", "P&L", "value",
     ["gross profit", "gross margin amount", "毛利"], _RATIO + ("gpm",), ["gross profit"]),
    ("ebitda", "EBITDA", "P&L", "value", ["ebitda", "ebitdaf"], _RATIO, ["ebitda"]),
    ("ebit", "Operating profit / EBIT", "P&L", "value",
     ["ebit", "operating profit", "operating income", "operating earnings", "profit from operations", "营业利润"],
     _RATIO + ("before", "ebitda", "non", "segment"), ["operating profit", "ebit"]),
    ("finance", "Net finance costs", "P&L", "value",
     ["net finance costs", "net finance cost", "finance costs", "finance cost", "net interest",
      "interest expense", "finance gain cost", "financial expenses", "财务费用"],
     _RATIO + ("capitalised", "capitalized", "paid", "received", "payable", "cash"), ["finance costs"]),
    ("associates", "Associates and JVs", "P&L", "value",
     ["share of associates", "associates and joint ventures", "share of profits of associates",
      "jointly controlled entities", "investment income", "associates", "joint ventures", "投资收益"],
     _RATIO + ("dividend", "balance", "carrying", "less"), ["associates"]),
    ("pretax", "Pre-tax profit", "P&L", "value",
     ["profit before tax", "pretax profit", "pretax profits", "pre tax profit", "pbt", "利润总额"],
     _RATIO + ("cash", "adjust"), ["pre-tax profit", "profit before tax"]),
    ("tax", "Tax", "P&L", "value",
     ["tax", "income tax", "taxation", "income tax expense", "所得税"],
     _RATIO + ("before", "pre", "after", "deferred", "payable", "paid", "asset", "liabilit", "recoverable",
               "business", "other", "profit", "rate", "cash"), ["tax"]),
    ("net_profit", "Net profit attributable", "P&L", "value",
     ["net profit", "reported net profit", "net profits reported", "net profit attributable",
      "profit attributable to shareholders", "profit attributable to owners", "net income", "归母净利润"],
     _RATIO + ("recurring", "underlying", "core", "adjusted", "before", "minority", "before minority",
               "operating", "cash", "1h", "h1"), ["net profit", "net profit attributable"]),
    ("recurring", "Recurring / core net profit", "P&L", "value",
     ["recurring net profit", "net profits recurring", "core net profit", "underlying profit",
      "adjusted net profit", "operating earnings", "扣非净利润"],
     _RATIO + ("cash", "1h", "h1", "per share", "eps", "dps"), ["recurring net profit"]),
    ("eps", "EPS", "P&L", "pershare",
     ["eps", "eps reported", "eps basic", "basic eps", "earnings per share", "每股收益"],
     _RATIO + ("recurring", "diluted", "adjusted", "core", "underlying", "1h", "h1"), ["eps"]),
    ("dps", "DPS", "P&L", "pershare",
     ["dps", "total dps", "dividend per share", "每股股利", "每股派息"],
     _RATIO + ("interim", "final", "special", "recurring", "payout"), ["dps"]),
    ("cash", "Cash", "Balance sheet", "value",
     ["cash", "cash and equivalents", "cash and cash equivalents", "cash and bank balances",
      "cash year end", "货币资金"],
     _RATIO + ("flow", "restricted", "beginning", "change", "changes", "net", "pledged", "per share",
               "operating", "investing", "financing", "diff"), ["cash", "cash year end"]),
    ("net_debt", "Net debt", "Balance sheet", "value",
     ["net debt", "net debt cash", "净负债"],
     _RATIO + ("ebitda", "equity", "gearing", "to"), ["net debt"]),
    ("equity", "Total equity", "Balance sheet", "value",
     ["total equity", "total shareholders equity", "shareholders equity", "total shareholder s equity",
      "equity attributable to shareholders", "股东权益合计", "所有者权益合计"],
     _RATIO + ("liabilities", "liabilities and", "return", "minority", "per share", "debt"),
     ["total equity"]),
    ("bvps", "Book value per share", "Balance sheet", "pershare",
     ["book value per share", "bvps", "bps", "bps ye", "nav per share", "每股净资产"],
     _RATIO + ("tangible",), ["book value per share"]),
    ("cfo", "Operating cash flow", "Cash flow", "value",
     ["operating cash flow", "net cash flow from operations", "net cash from operating activities",
      "cash flow from operations", "cash from operations", "cfo", "经营活动产生的现金流量净额"],
     _RATIO + ("before", "other", "per share"), ["operating cash flow"]),
    ("capex", "Capex", "Cash flow", "value",
     ["capex", "capital expenditure", "capital expenditures", "purchase of fixed assets",
      "purchase of property plant and equipment", "资本开支"],
     _RATIO + ("maintenance", "growth", "sales", "per"), ["capex"]),
    ("cfi", "Investing cash flow", "Cash flow", "value",
     ["investing cash flow", "net cash flow from investing", "net cash used in investing activities",
      "cash flow from investing", "cash from investing", "cfi", "投资活动产生的现金流量净额"],
     _RATIO + ("other", "before"), ["investing cash flow"]),
    ("cff", "Financing cash flow", "Cash flow", "value",
     ["financing cash flow", "net cash flow from financing", "net cash used in financing activities",
      "cash flow from financing", "cash from financing", "cff", "筹资活动产生的现金流量净额"],
     _RATIO + ("other", "before"), ["financing cash flow"]),
    ("fcf", "Free cash flow", "Cash flow", "value",
     ["free cash flow", "free cash flow to firm", "fcf", "fcff", "自由现金流"],
     _RATIO + ("equity", "per share", "yield"), ["free cash flow"]),
    ("div_paid", "Dividends paid", "Cash flow", "value",
     ["dividends paid", "dividend paid", "dividend payment", "dividends paid to shareholders", "less dividends",
      "dividends", "分配股利"],
     _RATIO + ("minority", "received", "per share", "non controlling", "interim", "final", "special", "total",
               "payout", "proposed", "declared", "payable"), ["dividends paid"]),
]


# ---------------------------------------------------------------- period

def period_kind(period):
    """'FY' | '1H' | '2H' | '1Q'..'4Q' from the run's period string."""
    p = str(period or "").upper().replace(" ", "")
    m = re.match(r"^([12])H|^H([12])", p)
    if m:
        return (m.group(1) or m.group(2)) + "H"
    m = re.match(r"^([1-4])Q|^Q([1-4])", p)
    if m:
        return (m.group(1) or m.group(2)) + "Q"
    return "FY"


def period_axis(spec, sheet, target_year, period):
    """The sheet's columns for this run's period, labelled explicitly:
    [(label, column, 'prior'|'actual'|'forecast')]. The forecast columns
    are the ones the SAME panel carries after the target year (an
    interim panel without forecasts has none — the page says so)."""
    from .checks import year_columns
    cols = year_columns(spec, sheet)
    ty = int(target_year)
    kind = period_kind(period)
    pre = "FY" if kind == "FY" else kind

    def lab(y, suffix):
        return f"{pre}{str(y)[-2:]}{suffix}"
    out = []
    if str(ty - 1) in cols:
        out.append((lab(ty - 1, "A"), cols[str(ty - 1)], "prior"))
    if str(ty) in cols:
        out.append((lab(ty, "A"), cols[str(ty)], "actual"))
    for y in (ty + 1, ty + 2, ty + 3):
        if str(y) in cols:
            out.append((lab(y, "E"), cols[str(y)], "forecast"))
    return out


def no_forecast_text(period):
    kind = period_kind(period)
    return ("no half-year forecast found in this model" if kind.endswith("H")
            else "no quarterly forecast found in this model" if kind.endswith("Q")
            else "no forecast columns found in this model")


# ------------------------------------------------------------ resolving

def _label_of(ws, row, max_col=6):
    for c in range(1, max_col + 1):
        v = ws.cell(row=row, column=c).value
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _phrase_in(phrase, label):
    return re.search(r"(?:^| )" + re.escape(phrase) + r"(?: |$)", label) is not None


def _score(role, label):
    """3 exact name · 2 whole-phrase name · 1 every word of a name is in
    the label · 0 none; a label carrying an excluded word is another
    line entirely (a shared word alone is no evidence — 'gross profit'
    is not 'profit after tax')."""
    _k, _l, _g, _kind, names, excl, _keys = role
    nl = norm_label(label)
    if not nl:
        return 0
    bare = re.sub(r"\s+", " ", nl).strip()
    if any(norm_label(n) == bare for n in names):
        return 3
    words = set(bare.split())
    for w in excl:
        wn = norm_label(w)
        if wn and (_phrase_in(wn, bare) if " " in wn or len(wn) > 2 else wn in words):
            return 0
    if any(_phrase_in(norm_label(n), bare) for n in names if norm_label(n)):
        return 2
    cjk = re.search(r"[一-鿿]", bare) is not None
    for n in names:
        nn = norm_label(n)
        nw = [w for w in nn.split() if len(w) > 1]
        if not nw or re.search(r"[一-鿿]", nn):
            if nn and cjk and nn in bare.replace(" ", ""):
                return 1
            continue
        if all((w in words) or (w + "s") in words or (w.endswith("s") and w[:-1] in words) for w in nw):
            return 1
    return 0


def _numeric_rows(ws, cols):
    """Rows that hold a number in any of the period's columns."""
    out = []
    idx = [column_index_from_string(c) for _l, c, _k in cols]
    for r in range(1, min(ws.max_row, 400) + 1):
        lab = _label_of(ws, r)
        if not lab:
            continue
        vals = [ws.cell(row=r, column=i).value for i in idx]
        if any(isinstance(v, (int, float)) or (isinstance(v, str) and v.startswith("=")) for v in vals):
            out.append((r, lab))
    return out


def resolve_rows(wb, spec, target_year, period, primary=None):
    """{role key: (sheet, row, label)} for every ROLES entry this model
    has a row for. Candidates are the run's proven key rows and the
    sheets' own labels; among them the sheet carrying the fuller period
    axis (the forecast path) wins, then the stronger name, then the
    primary sheet, then the row nearest the lines of the same statement
    already placed (the model's own order)."""
    from .checks import year_columns
    axis_sheets = [sh for sh in (spec.get("year_axis") or {}) if sh in wb.sheetnames]
    keys = spec.get("key_rows") or []
    if primary is None:
        counts = {}
        for k in keys:
            counts[k.get("sheet")] = counts.get(k.get("sheet"), 0) + 1
        primary = (max(counts, key=counts.get) if counts else
                   (axis_sheets[0] if axis_sheets else wb.sheetnames[0]))
    sheets = [primary] + [s for s in axis_sheets if s != primary]
    axes = {sh: period_axis(spec, sh, target_year, period) for sh in sheets}
    cands = {sh: _numeric_rows(wb[sh], ax) for sh, ax in axes.items() if ax}
    out, taken, placed = {}, set(), {}
    for role in ROLES:
        key, _l, group, _kind, _names, _excl, keynames = role
        best = None
        pool = []
        for k in keys:
            if norm_label(k.get("name")) in {norm_label(x) for x in keynames} and k.get("sheet") in cands \
                    and isinstance(k.get("row"), int):
                pool.append((k["sheet"], int(k["row"]), _label_of(wb[k["sheet"]], int(k["row"])) or str(k.get("name")), 4))
        for sh, rows in cands.items():
            for r, lab in rows:
                s = _score(role, lab)
                if s:
                    pool.append((sh, r, lab, s))
        for sh, r, lab, s in pool:
            if (sh, r) in taken:
                continue
            near = placed.get((group, sh))
            dist = abs(r - near) if near is not None else 0
            rank = (len(axes[sh]), 1 if s >= 2 else 0, 1 if sh == primary else 0, -dist, s, -r)
            if best is None or rank > best[0]:
                best = (rank, sh, r, lab)
        if best is not None:
            _rank, sh, r, lab = best
            out[key] = (sh, r, lab)
            taken.add((sh, r))
            placed[(group, sh)] = r
    return out, primary


# ---------------------------------------------------------------- facts

_PRE_EV = {}


def pre_value(pre_wb, sheet, row, col_letter):
    """The pre-update model's VALUE at a cell, formulas evaluated."""
    if pre_wb is None or sheet not in pre_wb.sheetnames:
        return None
    try:
        v = pre_wb[sheet][f"{col_letter}{row}"].value
    except Exception:
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str) and v.startswith("="):
        key = id(pre_wb)
        if key not in _PRE_EV:
            try:
                from .evaluator import Evaluator
                _PRE_EV[key] = Evaluator(pre_wb)
            except Exception:
                return None
        try:
            got = _PRE_EV[key].cell(sheet, f"{col_letter}{row}")
        except Exception:
            return None
        return got if isinstance(got, (int, float)) else None
    return None


def flags_of(wb):
    """[(sheet, coord, 'red'|'orange'|'blue', note)] from the fills."""
    out = []
    for sheet in wb.sheetnames:
        if sheet.startswith("_"):
            continue
        ws = wb[sheet]
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 400)):
            for cell in row:
                f = cell.fill
                code = ""
                try:
                    if f is not None and f.fill_type == "solid":
                        code = str(f.fgColor.rgb or "")[-6:].upper()
                except Exception:
                    code = ""
                if code in ("FFC7CE", "FFC000", "BDD7EE"):
                    note = str(cell.comment.text)[:200] if cell.comment is not None else ""
                    out.append((sheet, cell.coordinate,
                                "red" if code == "FFC7CE" else "orange" if code == "FFC000" else "blue",
                                note))
    return out


_ACRONYMS = {"eps", "dps", "ebit", "ebitda", "ebitdaf", "cfo", "cfi", "cff", "fcf", "fcff", "bvps", "bps",
             "capex", "ppe", "pp&e", "roe", "roic", "nav", "jv", "jvs", "jce", "jces", "sg&a", "d&a", "ar", "ap"}


def proper_name(name):
    """A key name in sentence case, acronyms upper: 'eps' -> 'EPS',
    'total liabilities and equity' -> 'Total liabilities and equity'."""
    words = str(name or "").strip().split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if lw in _ACRONYMS or re.match(r"^[a-z]&[a-z]$", lw):
            out.append(lw.upper())
        elif i == 0:
            out.append(w[:1].upper() + w[1:])
        else:
            out.append(w if w.isupper() and len(w) > 1 else lw)
    return " ".join(out)


def _q(sheet):
    return "'%s'" % sheet if re.search(r"[^A-Za-z0-9]", sheet) else sheet


def _link(sheet, coord, text):
    return '=HYPERLINK("#\'%s\'!%s","%s")' % (sheet, coord, str(text).replace('"', "'")[:60])


def _print_text(prov, sheet, row, col, key_tie):
    """'88,018.0 · p3' for a proven figure, 'not tied' for a key whose
    print no line reached, '' otherwise."""
    if key_tie is not None:
        if key_tie.get("tied"):
            pv = key_tie.get("print")
            e = prov.get(f"{sheet}!{row}") or {}
            pg = f" · p{e['page']}" if e.get("page") else ""
            return (f"{pv:,.2f}" if abs(pv) < 100 else f"{pv:,.0f}") + pg, False
        return "not tied", True
    e = prov.get(f"{sheet}!{row}") or {}
    v = e.get("value")
    if isinstance(v, (int, float)) and int(e.get("conf") or 0) >= 4:
        pg = f" · p{e['page']}" if e.get("page") else ""
        return (f"{v:,.2f}" if abs(v) < 100 else f"{v:,.0f}") + pg, False
    return "", False


# ---------------------------------------------------------------- render

def build(wb, pre_wb, spec, target_year, period, extra=None, log=print):
    """Render the page. extra: key_ties, open_checks, sense_rows,
    provenance, elapsed_min, units. -> dict of what was drawn."""
    from .checks import scorecard
    extra = extra or {}
    BANNER = PatternFill("solid", fgColor="FFF2CC")
    OPEN = PatternFill("solid", fgColor="FADBD8")
    SECT = PatternFill("solid", fgColor="F2F2F2")
    HEAD = PatternFill("solid", fgColor="E7E6E6")
    GREY = Font(color="7F7F7F", size=10)
    GREYI = Font(color="7F7F7F", size=10, italic=True)
    BOLD = Font(bold=True, size=11)
    SECTF = Font(bold=True, size=12)
    BANF = Font(bold=True, size=12)
    BODY = Font(size=11)
    SMALL = Font(size=10)
    REDF = Font(color="C00000", size=10)
    WARNF = Font(color="9C5700", size=10)
    THIN = Border(bottom=Side(style="thin", color="BFBFBF"))

    if "_REPORT" in wb.sheetnames:
        del wb["_REPORT"]
    ws = wb.create_sheet("_REPORT", 0)
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B4"
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

    def band(row, fill, h=None, upto=22):
        for c in range(1, upto):
            ws.cell(row=row, column=c).fill = fill
        if h:
            ws.row_dimensions[row].height = h

    def sect(title):
        nonlocal r
        cell(r, 1, title, SECTF, SECT)
        band(r, SECT, 22)
        r += 1

    rows, primary = resolve_rows(wb, spec, target_year, period)
    prov = extra.get("provenance") or {}
    key_ties = {k.get("name"): k for k in (extra.get("key_ties") or []) if isinstance(k, dict)}
    flags = flags_of(wb)
    n_red = sum(1 for f in flags if f[2] == "red")
    n_orange = sum(1 for f in flags if f[2] == "orange")
    plugs = [f for f in flags if "PLUG" in f[3].upper()]
    open_checks = [str(x) for x in (extra.get("open_checks") or [])]

    # ---- 1. verdict strip ----------------------------------------
    try:
        card = scorecard(wb, spec, target_year)
        # the run's objective is the years it wrote: the target and the forecasts
        fails = [c for c in card["checks"] if c["status"] != "PASS" and str(c["year"]) >= str(target_year)]
    except Exception:
        fails = []
    kt = extra.get("key_ties") or []
    n_tied = sum(1 for k in kt if isinstance(k, dict) and k.get("tied"))
    kind = period_kind(period)
    plabel = (f"FY{str(target_year)[-2:]}" if kind == "FY" else f"{kind}{str(target_year)[-2:]}")
    el = extra.get("elapsed_min")
    parts = [f"Updated to {plabel}" + (f" in {el:.0f} min" if isinstance(el, (int, float)) else "")]
    if fails or open_checks:
        yrs = sorted({str(c["year"]) for c in fails})
        parts.append(f"CHECKS OPEN: {len(fails)} ({', '.join(yrs[:6])})" if fails
                     else f"CHECKS OPEN: {len(open_checks)}")
    else:
        parts.append("balance and cash checks closed, every year")
    parts.append(f"key numbers tied to the print {n_tied}/{len(kt)}" if kt else "key numbers: no panel")
    parts.append(f"red {n_red} · orange {n_orange} · plugs {len(plugs)}")
    cell(r, 1, "   ·   ".join(parts), BANF, BANNER)
    band(r, OPEN if (fails or open_checks) else BANNER, 30)
    r += 1
    ws.row_dimensions[r].height = 8
    r += 1

    # ---- 2. the table -------------------------------------------
    units = str(extra.get("units") or spec.get("units") or "model units")
    axis = period_axis(spec, primary, target_year, period)
    fcols = [a for a in axis if a[2] == "forecast"]
    hist = [a for a in axis if a[2] != "forecast"]
    nper = len(hist) + len(fcols)
    D0 = 2                                   # change block
    CHK = D0 + nper                          # check column
    NEW0 = CHK + 2
    PRN = NEW0 + nper                        # print
    YOY = PRN + 1
    OLD0 = YOY + 2
    LAST = OLD0 + nper
    ws.column_dimensions["A"].width = 30
    for c in range(2, LAST + 1):
        ws.column_dimensions[get_column_letter(c)].width = 10.5
    ws.column_dimensions[get_column_letter(CHK)].width = 13
    ws.column_dimensions[get_column_letter(PRN)].width = 17
    for c in (CHK + 1, YOY + 1):
        ws.column_dimensions[get_column_letter(c)].width = 2
    sect(f"1 · What changed, new model vs your model   ({units}; change = new ÷ old − 1; "
         f"check = next period's change more than {SENSE_GAP*100:.0f} points from the actual's)")
    cell(r, D0, "WHAT CHANGED — new vs old", GREY)
    cell(r, NEW0, "NEW — after the update", GREY)
    cell(r, OLD0, "OLD — before the update", GREY)
    r += 1
    labels = [a[0] for a in hist] + [a[0] for a in fcols]
    for blk in (D0, NEW0, OLD0):
        for i, lab in enumerate(labels):
            cell(r, blk + i, lab, GREY, HEAD, None, THIN)
        if not fcols:
            cell(r, blk + len(labels), no_forecast_text(period), GREYI, HEAD, None, THIN)
    cell(r, CHK, "check", GREY, HEAD, None, THIN)
    cell(r, PRN, f"{labels[-len(fcols) - 1] if fcols else labels[-1]} printed", GREY, HEAD, None, THIN)
    cell(r, YOY, "YoY", GREY, HEAD, None, THIN)
    r += 1
    first_table = r
    drawn = {}
    group_now = None
    for role in ROLES:
        key, label, group, kindr, *_ = role
        if group != group_now:
            if group_now is not None:
                r += 1                       # one empty row between statements (owner 2026-09-14)
            cell(r, 1, group, GREYI)
            r += 1
            group_now = group
        hit = rows.get(key)
        if not hit:
            cell(r, 1, label, SMALL)
            cell(r, D0, "not in this model", GREYI)
            r += 1
            continue
        sh, mr, mlab = hit
        ax = period_axis(spec, sh, target_year, period)
        ah = [a for a in ax if a[2] != "forecast"]
        af = [a for a in ax if a[2] == "forecast"]
        cols = [a[1] for a in ah] + [a[1] for a in af][:len(fcols)]
        tcol = next((a[1] for a in ax if a[2] == "actual"), None)
        q = _q(sh)
        cell(r, 1, _link(sh, f"{tcol or cols[0]}{mr}", f"{label}  ({mlab[:24]})"), SMALL)
        vfmt = "0.00" if kindr == "pershare" else NUM
        for i, cl in enumerate(cols):
            ov = pre_value(pre_wb, sh, mr, cl)
            cell(r, OLD0 + i, round(ov, 4) if isinstance(ov, (int, float)) else "", SMALL, None, vfmt)
            cell(r, NEW0 + i, f"={q}!{cl}{mr}", SMALL, None, vfmt)
            oc, nc = get_column_letter(OLD0 + i), get_column_letter(NEW0 + i)
            cell(r, D0 + i, f'=IFERROR(IF({oc}{r}=0,"",({nc}{r}-{oc}{r})/ABS({oc}{r})),"")', SMALL, None, PCT)
        # the check: the owner's ten points between the actual's change and the next period's
        if fcols and len(cols) >= len(ah) + 1:
            c0 = get_column_letter(D0 + len(ah) - 1)
            c1 = get_column_letter(D0 + len(ah))
            cell(r, CHK,
                 f'=IF(COUNT({c0}{r},{c1}{r})<2,"",IF({c0}{r}*{c1}{r}<0,"⚠ sign flip",'
                 f'IF(ABS({c1}{r}-{c0}{r})>{SENSE_GAP},"⚠ "&TEXT(ABS({c1}{r}-{c0}{r})*100,"0")&" pts","")))',
                 WARNF)
        # the printed figure: the key panel's print for a key row, a proven serve otherwise
        kname = next((k.get("name") for k in (spec.get("key_rows") or [])
                      if k.get("sheet") == sh and int(k.get("row", -1)) == mr), None)
        ptxt, bad = _print_text(prov, sh, mr, tcol, key_ties.get(kname) if kname else None)
        cell(r, PRN, ptxt, REDF if bad else SMALL)
        if len(ah) == 2:
            pc, ac = get_column_letter(NEW0), get_column_letter(NEW0 + 1)
            cell(r, YOY, f'=IFERROR(IF({pc}{r}<=0,"n/m",{ac}{r}/{pc}{r}-1),"")', SMALL, None, PCT)
        drawn[key] = (sh, mr)
        r += 1
    from openpyxl.formatting.rule import CellIsRule
    rng = f"{get_column_letter(D0)}{first_table}:{get_column_letter(D0 + nper - 1)}{r - 1}"
    for op, v in (("greaterThan", "0.2"), ("lessThan", "-0.2")):
        ws.conditional_formatting.add(rng, CellIsRule(operator=op, formula=[v],
                                                      fill=PatternFill("solid", fgColor="FFF2CC")))
    ws.row_dimensions[r].height = 10
    r += 1

    # ---- 3. key numbers -----------------------------------------
    keys = sorted([k for k in (spec.get("key_rows") or [])
                   if k.get("sheet") in wb.sheetnames and isinstance(k.get("row"), int)],
                  key=lambda k: (0 if k.get("sheet") == primary else 1, str(k.get("sheet")), int(k["row"])))
    if keys:
        sect(f"2 · Key numbers   ({plabel} actual vs the prior period and vs your estimate)")
        hdr = ["", "Prior actual", f"{plabel} actual", "YoY", "Your estimate", "Actual vs estimate"]
        for i, h in enumerate(hdr):
            cell(r, i + 1, h, GREY, HEAD, None, THIN)
        r += 1
        for k in keys:
            sh, mr = k["sheet"], int(k["row"])
            ax = period_axis(spec, sh, target_year, period)
            pcol = next((a[1] for a in ax if a[2] == "prior"), None)
            tcol = next((a[1] for a in ax if a[2] == "actual"), None)
            if not tcol:
                continue
            # an interim balance sheet compares to the last year end (owner 2026-09-10)
            apx = (spec.get("annual_prior_axis") or {}).get(sh)
            nm = str(k.get("name") or "")
            if apx and any(w in nm.lower() for w in ("asset", "liabilit", "equity", "debt", "cash year end")):
                pcol = apx
            q = _q(sh)
            cell(r, 1, _link(sh, f"{tcol}{mr}", proper_name(nm)), SMALL)
            cell(r, 2, f"={q}!{pcol}{mr}" if pcol else "", SMALL, None, NUM)
            cell(r, 3, f"={q}!{tcol}{mr}", SMALL, None, NUM)
            cell(r, 4, f'=IFERROR(IF(B{r}<=0,"n/m",C{r}/B{r}-1),"")', SMALL, None, PCT)
            est = pre_value(pre_wb, sh, mr, tcol)
            cell(r, 5, round(est, 4) if isinstance(est, (int, float)) else "", SMALL, None, NUM)
            cell(r, 6, f'=IFERROR(IF(E{r}<=0,"n/m",C{r}/E{r}-1),"")', SMALL, None, PCT)
            r += 1
        ws.row_dimensions[r].height = 10
        r += 1

    # ---- 4. look here -------------------------------------------
    sect("3 · Look here")
    n_items = 0
    sense = [s for s in (extra.get("sense_rows") or []) if isinstance(s, dict)]
    final = [s for s in sense if s.get("stage") == "final"]
    shown = final if final else sense
    seen = set()
    for s in shown:
        if s.get("name") in seen:
            continue
        seen.add(s.get("name"))
        v = str(s.get("verdict") or "")
        word = {"fixed": "fixed", "genuine": "genuine", "unusual": "genuine but unusual",
                "red": "red, your ruling"}.get(v, v or "reviewed")
        leaf = s.get("leaf")
        cell(r, 1, str(s.get("name") or "")[:30], BOLD)
        cell(r, 2, (f"actual {s.get('d0', 0)*100:+.1f}% vs your estimate; next period "
                    f"{s.get('d1', 0)*100:+.1f}% vs old ({abs(s.get('d1', 0)-s.get('d0', 0))*100:.0f} pts) → {word}"),
             SMALL)
        if leaf and "!" in str(leaf):
            lsh, lco = str(leaf).split("!", 1)
            if lsh in wb.sheetnames:
                cell(r, PRN, _link(lsh, lco, leaf), SMALL)
        r += 1
        if s.get("text"):
            cell(r, 2, "      " + str(s["text"])[:300], GREYI)
            r += 1
        n_items += 1
    for oc in open_checks[:12]:
        cell(r, 1, "OPEN CHECK", REDF)
        cell(r, 2, oc[:200], SMALL)
        r += 1
        n_items += 1
    for sh, co, _c, note in plugs[:12]:
        cell(r, 1, _link(sh, co, f"PLUG {sh}!{co}"), SMALL)
        cell(r, 2, f"={_q(sh)}!{co}", SMALL, None, NUM)
        cell(r, 3, note[:160], SMALL)
        r += 1
        n_items += 1
    # flagged cells that sit on the page's own rows
    page_rows = {(sh, mr) for sh, mr in drawn.values()} | {(k["sheet"], int(k["row"])) for k in keys}
    on_page = [f for f in flags if f[2] in ("red", "orange") and "PLUG" not in f[3].upper()
               and (f[0], int(re.sub(r"[A-Z]+", "", f[1]) or 0)) in page_rows]
    for sh, co, colour, note in on_page[:20]:
        cell(r, 1, _link(sh, co, f"{colour.upper()} {sh}!{co}"), REDF if colour == "red" else WARNF)
        cell(r, 2, f"={_q(sh)}!{co}", SMALL, None, NUM)
        cell(r, 3, note[:160], SMALL)
        r += 1
        n_items += 1
    rest = [f for f in flags if f[2] in ("red", "orange") and f not in on_page and f not in plugs]
    by_sheet = {}
    for f in rest:
        by_sheet.setdefault(f[0], []).append(f)
    if by_sheet:
        cell(r, 1, "Elsewhere (every flagged cell is listed on _FLAGS, with its note):", GREYI)
        r += 1
        for sh in sorted(by_sheet):
            fs = by_sheet[sh]
            nr = sum(1 for f in fs if f[2] == "red")
            no = len(fs) - nr
            cell(r, 1, _link(sh, fs[0][1], f"{sh}: {nr} red, {no} orange"), SMALL)
            r += 1
    if n_items == 0 and not by_sheet:
        cell(r, 1, "Nothing to look at: no line out of line, no check open, no plug.", SMALL)
        r += 1

    # ---- the complete list on _FLAGS -----------------------------
    fws = wb.create_sheet("_FLAGS") if "_FLAGS" not in wb.sheetnames else wb["_FLAGS"]
    for row_ in fws.iter_rows():
        for c_ in row_:
            c_.value = None
    fws.cell(row=1, column=1, value="Every flagged cell (plugs, red rulings, orange derivations)").font = BOLD
    fr = 3
    for tier, title in (("plug", "Plugs"), ("red", "Red — unsure, your ruling"),
                        ("orange", "Orange — derived, not read"), ("blue", "Blue — forecast inputs frozen or held")):
        items = [f for f in flags if (("PLUG" in f[3].upper()) if tier == "plug"
                                      else (f[2] == tier and "PLUG" not in f[3].upper()))]
        if not items:
            continue
        fws.cell(row=fr, column=1, value=title).font = BOLD
        fr += 1
        for sh, co, _c, note in items:
            fws.cell(row=fr, column=1, value=_link(sh, co, f"{sh}!{co}")).font = SMALL
            fws.cell(row=fr, column=2, value=f"={_q(sh)}!{co}").number_format = NUM
            fws.cell(row=fr, column=3, value=note[:200]).font = SMALL
            fr += 1
        fr += 1
    fws.column_dimensions["A"].width = 26
    fws.column_dimensions["C"].width = 110
    wb.active = 0
    log(f"[report] page: {len(drawn)}/{len(ROLES)} table lines found, {len(keys)} key rows, "
        f"{n_items} look-here items, period {plabel}" + ("" if fcols else " (no forecast columns)"))
    return {"rows": drawn, "primary": primary, "keys": len(keys), "look_here": n_items,
            "tied": n_tied, "panel": len(kt), "red": n_red, "orange": n_orange, "plugs": len(plugs)}
