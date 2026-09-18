"""The _REPORT page, owner's revamp of 2026-09-13 — one fixed table for
every model, rendered by code from the model itself. No prose.

  1. Verdict strip     — delivered / checks per year / keys tied / counts
  2. The table         — a FIXED list of lines (P&L, balance sheet, cash
                         flow) in a fixed order, the same on every
                         model: what changed (new vs old) with the
                         >10-point check, NEW with the printed figure
                         and YoY, OLD. A line this model has no row for
                         says so and keeps its place.
  3. Look here         — the sense check's verdicts with the cell each
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
    # THE FOUR HALVES OF THE BALANCE SHEET (owner 2026-09-17): each is the
    # MODEL's own total row against the printed total, so a figure landing in
    # the wrong half is seen even when total liabilities and equity ties
    ("current_assets", "Total current assets", "Balance sheet", "value",
     ["total current assets", "current assets", "流动资产合计", "流动资产总计"],
     _RATIO + ("non", "net", "other", "liabilit"), ["total current assets"]),
    ("noncurrent_assets", "Total non-current assets", "Balance sheet", "value",
     ["total non-current assets", "total noncurrent assets", "non-current assets", "noncurrent assets",
      "非流动资产合计", "非流动资产总计"],
     _RATIO + ("other", "liabilit"), ["total non-current assets"]),
    ("current_liabilities", "Total current liabilities", "Balance sheet", "value",
     ["total current liabilities", "current liabilities", "流动负债合计", "流动负债总计"],
     _RATIO + ("non", "net", "other", "asset"), ["total current liabilities"]),
    ("noncurrent_liabilities", "Total non-current liabilities", "Balance sheet", "value",
     ["total non-current liabilities", "total noncurrent liabilities", "non-current liabilities",
      "noncurrent liabilities", "非流动负债合计", "非流动负债总计"],
     _RATIO + ("other", "asset"), ["total non-current liabilities"]),
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
    for r in range(1, ws.max_row + 1):
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
        # the primary sheet must carry a period axis (an interim run keeps only the
        # sheets with an interim panel; a key-row sheet without one crashed the page)
        counts = {sh: n for sh, n in counts.items() if sh in axis_sheets} or counts
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
        for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
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
    if isinstance(v, (int, float)) and int(e.get("conf") or 0) >= 4 and e.get("page"):
        pg = f" · p{e['page']}"
        return (f"{v:,.2f}" if abs(v) < 100 else f"{v:,.0f}") + pg, False
    if isinstance(v, (int, float)) and "COMPOSITE" in str(e.get("line") or ""):
        return "composite of printed lines", False
    return "", False


# ---------------------------------------------------------------- render

def _build_changed_only(wb, pre_wb, spec, target_year, period, extra, log):
    """Render the production report's single old/new delta block.

    Row selection still comes from the model/spec via ``resolve_rows``.  The
    discarded banner, look-here, verdict, and flag sections are never built.
    Cell links and NEW formulas remain live against the workbook.
    """
    extra = extra or {}
    GREY = Font(color="7F7F7F", size=10)
    GREYI = Font(color="7F7F7F", size=10, italic=True)
    SMALL = Font(size=10)
    WARNF = Font(color="9C5700", size=10)
    HEAD = PatternFill("solid", fgColor="E7E6E6")
    THIN = Border(bottom=Side(style="thin", color="BFBFBF"))

    if "_REPORT" in wb.sheetnames:
        del wb["_REPORT"]
    ws = wb.create_sheet("_REPORT", 0)
    ws.sheet_view.showGridLines = False
    rows, primary = resolve_rows(wb, spec, target_year, period)
    axis = period_axis(spec, primary, target_year, period)
    fcols = [a for a in axis if a[2] == "forecast"]
    hist = [a for a in axis if a[2] != "forecast"]
    labels = [a[0] for a in hist] + [a[0] for a in fcols]
    nper = len(labels)
    D0 = 2
    CHK = D0 + nper
    NEW0 = CHK + 2
    PRN = NEW0 + nper
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

    ws.cell(row=1, column=D0, value="WHAT'S CHANGED — new vs old").font = Font(bold=True, size=12)
    ws.cell(row=1, column=NEW0, value="NEW — after the update").font = Font(bold=True, size=11)
    ws.cell(row=1, column=OLD0, value="OLD — before the update").font = Font(bold=True, size=11)
    r = 2
    for block in (D0, NEW0, OLD0):
        for i, label in enumerate(labels):
            c = ws.cell(row=r, column=block + i, value=label)
            c.font, c.fill, c.border = GREY, HEAD, THIN
        if not fcols:
            c = ws.cell(row=r, column=block + len(labels), value=no_forecast_text(period))
            c.font, c.fill, c.border = GREYI, HEAD, THIN
    for col, val in ((CHK, "check"), (PRN, f"{labels[-len(fcols)-1] if fcols else labels[-1]} printed"), (YOY, "YoY")):
        c = ws.cell(row=r, column=col, value=val)
        c.font, c.fill, c.border = GREY, HEAD, THIN

    drawn = {}
    key_ties = [k for k in extra.get("key_ties", []) if isinstance(k, dict)]
    ties_by_ref = {k.get("ref"): k for k in key_ties}
    r += 1
    group_now = None
    for role in ROLES:
        key, label, group, kind, *_ = role
        if group != group_now:
            if group_now is not None:
                r += 1
            ws.cell(row=r, column=1, value=group).font = GREYI
            r += 1
            group_now = group
        hit = rows.get(key)
        if not hit:
            ws.cell(row=r, column=1, value=label).font = SMALL
            ws.cell(row=r, column=D0, value="not in this model").font = GREYI
            r += 1
            continue
        sh, mr, mlab = hit
        ax = period_axis(spec, sh, target_year, period)
        ah = [a for a in ax if a[2] != "forecast"]
        af = [a for a in ax if a[2] == "forecast"]
        cols = [a[1] for a in ah] + [a[1] for a in af][:len(fcols)]
        tcol = next((a[1] for a in ax if a[2] == "actual"), None)
        printed, uncertain = _print_text(extra.get("provenance", {}), sh, mr, tcol,
                                         ties_by_ref.get(f"{sh}!{tcol}{mr}"))
        ws.cell(row=r, column=PRN, value=printed).font = WARNF if uncertain else GREYI
        ws.cell(row=r, column=1, value=_link(sh, f"{tcol or cols[0]}{mr}", f"{label}  ({mlab[:24]})")).font = SMALL
        vfmt = "0.00" if kind == "pershare" else NUM
        for i, cl in enumerate(cols):
            ov = pre_value(pre_wb, sh, mr, cl)
            old = ws.cell(row=r, column=OLD0 + i, value=round(ov, 4) if isinstance(ov, (int, float)) else "")
            old.font, old.number_format = SMALL, vfmt
            new = ws.cell(row=r, column=NEW0 + i, value=f"={_q(sh)}!{cl}{mr}")
            new.font, new.number_format = SMALL, vfmt
            oc, nc = get_column_letter(OLD0 + i), get_column_letter(NEW0 + i)
            delta = ws.cell(row=r, column=D0 + i,
                            value=f'=IFERROR(IF({oc}{r}=0,"",({nc}{r}-{oc}{r})/ABS({oc}{r})),"")')
            delta.font, delta.number_format = SMALL, PCT
        if fcols and len(cols) >= len(ah) + 1:
            c0 = get_column_letter(D0 + len(ah) - 1)
            c1 = get_column_letter(D0 + len(ah))
            ws.cell(row=r, column=CHK,
                    value=f'=IF(COUNT({c0}{r},{c1}{r})<2,"",IF(ABS({c1}{r}-{c0}{r})>{SENSE_GAP},"⚠ "&TEXT(ABS({c1}{r}-{c0}{r})*100,"0")&" pts",""))').font = WARNF
        if len(ah) == 2:
            pc, ac = get_column_letter(NEW0), get_column_letter(NEW0 + 1)
            ws.cell(row=r, column=YOY,
                    value=f'=IFERROR(IF({pc}{r}<=0,"n/m",{ac}{r}/{pc}{r}-1),"")').number_format = PCT
        drawn[key] = (sh, mr)
        r += 1
    if nper:
        from openpyxl.formatting.rule import CellIsRule
        rng = f"{get_column_letter(D0)}3:{get_column_letter(D0 + nper - 1)}{r - 1}"
        for op, value in (("greaterThan", "0.2"), ("lessThan", "-0.2")):
            ws.conditional_formatting.add(rng, CellIsRule(operator=op, formula=[value], fill=PatternFill("solid", fgColor="FFF2CC")))
    ws.freeze_panes = "B3"
    wb.active = 0
    log(f"[report] compact page: {len(drawn)}/{len(ROLES)} table lines found, period {period}")
    flags = flags_of(wb)
    return {"rows": drawn, "primary": primary, "keys": len(spec.get("key_rows", [])), "look_here": 0,
            "tied": sum(bool(k.get("tied")) for k in key_ties), "panel": len(key_ties),
            "red": sum(f[2] == "red" for f in flags), "orange": sum(f[2] == "orange" for f in flags),
            "plugs": sum("PLUG" in f[3].upper() and "PLUG METER" not in f[3].upper() for f in flags)}

def build(wb, pre_wb, spec, target_year, period, extra=None, log=print):
    """Render the page. extra: key_ties, open_checks, sense_rows,
    provenance, elapsed_min, units. -> dict of what was drawn."""
    return _build_changed_only(wb, pre_wb, spec, target_year, period, extra or {}, log)
