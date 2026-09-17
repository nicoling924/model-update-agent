"""THE STRUCTURE TURN (owner 2026-09-17, the CX cold model: no spec, no
labelled check, so objective 1 — balance — could not be measured AT ALL and
the report still said "balance and cash checks closed, every year").

What a row IS is a reading, not a pattern. When the spec is absent or thin,
ONE brain turn happens BEFORE the card queue: the brain reads the sheets as
the model prints them — names, labels, the target-year formulas, what the
history holds — and names the statement sheets and their roles, the model's
own CHECK rows, its KEY rows, its input sites, and any row definitions the
formulas or the history let it read ("minority interests here historically
includes the perpetuals").

Code is the referee, never the reader: each named check row must be a row the
model works out and that reads ~0 in the periods it already holds; each named
key row must be a row the model computes. What verifies goes into the spec the
run measures itself against, and what is dropped is said. With no brain the
deterministic discovery stands, and if it found no check row the report says
balance was NOT MEASURED — never that it holds.
"""
import re

from .checks import year_columns
from .evaluator import Evaluator

CHECK_TOL = 1.0

SYSTEM = """You are an equity research analyst opening a valuation model you
have never seen, to update it to a new reporting period. Read the sheets as
they are printed below — every sheet's labels, and for each row the formula
that sits in the year being updated — and say what this model's rows ARE.

Name:
- statements: which sheets carry the financial statements and what each is
  (profit and loss, balance sheet, cash flow, segments, drivers, valuation).
- checks: the model's OWN check rows — a row the model works out and expects
  to be ZERO (assets less liabilities and equity; cash less the cash-flow
  roll; a units total less its components). These are how the update proves
  it did not break the model, so find them if they exist.
- keys: the headline rows — revenue, operating profit, net profit, EPS, DPS,
  total assets, total liabilities and equity, current liabilities,
  non-current liabilities, current assets, non-current assets, total equity,
  cash, the cash flows — whatever THIS model has. Name "total assets" and "total
  liabilities and equity" whenever the model computes them, even if it has no
  check row: those two are how a balance sheet is proved, and if this model
  declares no check of its own, their difference becomes the balance objective. Name the balance sheet's four halves whenever the model computes
  them: a balance check that closes proves the two SIDES agree, not that either
  side is right, and a figure plugged into the wrong half hides there. A key is
  a row the MODEL computes from its own inputs, never a place where the printed
  statement is retyped.
- inputs: rows that are typed in (hardcoded actuals), not computed — where an
  update lands its figures.
- definitions: anything the formulas or the history tell you about what a row
  means, that its label does not say.

Only name rows you can actually see. A row you are unsure of is better left
out than guessed.

Answer with ONE JSON object and nothing else:
{"statements":[{"sheet":"<name>","role":"<pl|bs|cf|segments|drivers|valuation|other>"}],
 "checks":["Sheet!<row>", ...],
 "keys":[{"name":"revenue","ref":"Sheet!<row>"}, ...],
 "inputs":["Sheet!<row>", ...],
 "definitions":["<one short sentence each>", ...],
 "because":"<one short sentence>"}"""


def wanted(spec):
    """Is this model's anatomy still unknown? A model from another team has no
    spec: code reads the year axes from the headers, but which rows are the
    checks and which are the keys is a reading of the model."""
    return not (spec.get("check_rows") or []) or not (spec.get("key_rows") or [])


def _validate(obj):
    if not isinstance(obj, dict):
        return ["the answer must be one JSON object"]
    errs = []
    for k in ("checks", "keys", "statements"):
        if k in obj and not isinstance(obj[k], list):
            errs.append(f"'{k}' must be a list")
    for k in (obj.get("keys") or []):
        if not isinstance(k, dict) or not k.get("ref") or not k.get("name"):
            errs.append("each key needs a name and a ref")
            break
    return errs


def _parse(ref, wb):
    """'Sheet!118' or 'Sheet!AO118' -> (sheet, row) or (None, why)."""
    m = re.match(r"^\s*'?([^'!]+)'?!\$?[A-Z]{0,3}\$?(\d+)\s*$", str(ref))
    if not m:
        return None, f"'{ref}' is not a Sheet!row reference"
    sh, row = m.group(1).strip(), int(m.group(2))
    if sh not in wb.sheetnames:
        return None, f"this model has no sheet '{sh}'"
    return (sh, row), None


def _row_cells(wb, sheet, row):
    """The cells this row actually holds, left to right — the SHEET's own extent
    decides how far that is (reviewer 2026-09-17: a cap of 80 columns hid the
    check on any wider book, which is the failure this module exists to fix)."""
    ws = wb[sheet]
    out = []
    for c in range(1, ws.max_column + 1):
        cell = ws.cell(row, c)
        if isinstance(cell.value, (int, float)) or \
                (isinstance(cell.value, str) and cell.value.startswith("=")):
            out.append(cell.coordinate)
    return out


def _reads_zero(wb, ev, spec, sheet, row, target_year, unread=None, cached=None):
    """A CHECK IS A ROW THAT READS ZERO WHERE THE MODEL ALREADY CLOSED IT: the
    periods it already holds. -> (True, how_many) or (False, why). The target
    year and anything right of it are excluded — the run is about to change
    them, and a check that is currently broken is still a check."""
    if unread is None:
        unread = []
    cols = year_columns(spec, sheet) or {}
    past = {c for y, c in cols.items() if str(y).isdigit() and int(y) < int(target_year)}
    cells = _row_cells(wb, sheet, row)
    if not cols and cells:
        # THE SHEET DECLARES NO YEARS (CX's Fleet, where the check actually is):
        # a left-to-right sheet's newest period is its rightmost figure, and that
        # is the one the run may be about to change — so it is not held to zero,
        # exactly as the target year is not on a sheet that does name its years.
        # evidence: the model's own column order is the only period order such a sheet gives.
        cells = cells[:-1]
    seen = bad = 0
    for coord in cells:
        col = "".join(ch for ch in coord if ch.isalpha())
        if cols and col not in past:
            continue                 # the target year, a forecast, or off the axis
        try:
            v = ev.cell(sheet, coord)
        except Exception as e:       # noqa: BLE001
            # CODE'S LIMITATION IS NOT THE MODEL'S FAULT (reviewer 2026-09-17):
            # this evaluator cannot do AVERAGEIFS or a full-column reference, so
            # the workbook's own cached result stands. Only when there is none
            # does the cell prove nothing — and the run says which one and why.
            v = cached(sheet, coord) if cached else None
            if v is None:
                unread.append(f"{sheet}!{coord} ({type(e).__name__})")
                continue
        if not isinstance(v, (int, float)):
            continue
        seen += 1
        if abs(v) > CHECK_TOL:
            bad += 1
    if seen < 2:
        return False, ("the model closes this row in fewer than two periods — nothing to verify a check "
                       "against" + (f" ({len(unread)} cell(s) would not evaluate: {', '.join(unread[:3])})" if unread else ""))
    if bad:
        return False, f"it reads non-zero in {bad} of the {seen} periods the model already closed — not a check"
    return True, seen


def _sheet_lines(wb, spec, sh, target_year):
    """One sheet's reading: each row's label beside the formula the target year
    holds. -> (lines, n_axis_rows) — the second is how much of this sheet is
    statement-shaped (rows the year axis actually carries a formula or figure
    for), which is what makes a sheet worth the brain's attention."""
    cols = year_columns(spec, sh) or {}
    tcol = cols.get(str(target_year))
    ws = wb[sh]
    lines, n_axis = [], 0
    for r in range(1, ws.max_row + 1):        # the sheet's own extent, not a cap
        lab = ""
        for c in range(1, 6):
            v = ws.cell(r, c).value
            if isinstance(v, str) and v.strip() and not v.startswith("="):
                lab = v.strip()
                break
        f = ws[f"{tcol}{r}"].value if tcol else None
        if isinstance(f, (int, float)) or (isinstance(f, str) and f.startswith("=")):
            n_axis += 1
        if not lab and not (isinstance(f, str) and f.startswith("=")):
            continue
        lines.append(f"  {r}: {lab[:46]}" + (f"   {str(f)[:44]}" if isinstance(f, str) and f.startswith("=") else ""))
    return lines, n_axis


def sheet_reading(wb, spec, target_year, cap=52000):
    """What code can show the brain: every sheet, its year columns, and each
    row's label beside the formula the target year holds.

    THE BUDGET FOLLOWS THE CONTENT, NOT THE SHEET COUNT (reviewer 2026-09-17:
    an equal share over CX's eight sheets cut CXMODEL at row 83 and the brain
    never saw revenue at 118 or operating profit at 133 — the twelve rows the
    turn exists to find). A sheet takes what it NEEDS; the statement-shaped
    sheets — the ones the year axis actually carries — are served first, so if
    anything is ever cut it is the small sheet at the back, and the cut is said.
    Six of CX's eight sheets are a few hundred characters; CXMODEL's whole
    reading is 17.6k and fits several times over."""
    L = ["The sheets, their year columns, and their rows:"]
    order = list(dict.fromkeys([s for s in list(spec.get("year_axis") or {}) + list(wb.sheetnames)
                                if s in wb.sheetnames]))
    read = {sh: _sheet_lines(wb, spec, sh, target_year) for sh in order}
    # most year-axis rows first: that is what a statement sheet looks like
    order.sort(key=lambda sh: -read[sh][1])
    room, cut = cap, []
    for sh in order:
        lines, _n = read[sh]
        cols = year_columns(spec, sh) or {}
        tcol = cols.get(str(target_year))
        head = (f"--- {sh}: {len(cols)} year column(s)"
                + (f"; {target_year} is column {tcol}" if tcol else "; no year columns found") + " ---")
        body = "\n".join(lines)
        if room - len(head) - len(body) < 0:
            cut.append(f"{sh} ({len(lines)} rows)")
            continue
        room -= len(head) + len(body)
        L.append(head)
        L += lines
    if cut:
        # said, never silently dropped
        L.append(f"  (these sheets did not fit this turn and are NOT shown: {', '.join(cut)})")
    return "\n".join(L)


def read(wb, spec, client, target_year, log, period="FY", values_wb=None):
    """The structure turn. Mutates `spec` with what verifies.
    -> (n_checks_taken, n_keys_taken, dropped)."""
    if client is None:
        n = len(spec.get("check_rows") or [])
        log("[anatomy] no brain to read this model's structure — the deterministic "
            f"discovery stands ({n} check row(s), {len(spec.get('key_rows') or [])} key row(s))")
        return 0, 0, []
    user = (f"This model is being updated to {period} {target_year}.\n\n"
            + sheet_reading(wb, spec, target_year))
    try:
        obj = client.json(SYSTEM, user[:60000], _validate, repair_retries=1)
    except Exception as ex:      # noqa: BLE001
        log(f"[anatomy] the brain could not read this model's structure ({ex}) — "
            "the deterministic discovery stands")
        return 0, 0, []
    ev = Evaluator(wb)
    wv = values_wb if values_wb is not None else wb

    def cached(sh_, co_):
        """The workbook's own cached result — what Excel last computed."""
        try:
            v_ = wv[sh_][co_].value
        except Exception:      # noqa: BLE001
            return None
        return v_ if isinstance(v_, (int, float)) and not isinstance(v_, bool) else None
    took_c = took_k = 0
    dropped, notes_off = [], []
    have_c = {(c.get("sheet"), int(c.get("row"))) for c in (spec.get("check_rows") or [])}
    for ref in (obj.get("checks") or []):
        site, why = _parse(ref, wb)
        if site is None:
            dropped.append(f"check {ref}: {why}")
            continue
        sh, r = site
        if (sh, r) in have_c:
            continue
        unread = []
        ok, detail = _reads_zero(wb, ev, spec, sh, r, target_year, unread, cached)
        if unread:
            # said, never swallowed: the analyst sees which cells the model could not work out
            log(f"[anatomy] {sh}!{r}: {len(unread)} cell(s) would not evaluate — {', '.join(unread[:4])}")
            dropped.append(f"check {sh}!{r}: {len(unread)} cell(s) would not evaluate ({', '.join(unread[:3])})")
        if not ok:
            dropped.append(f"check {sh}!{r}: {detail}")
            continue
        spec.setdefault("check_rows", []).append({"sheet": sh, "row": r, "expect": 0})
        have_c.add((sh, r))
        took_c += 1
        log(f"[anatomy] check {sh}!{r} verified — the model closes it to zero in "
            f"{detail} period(s); balance is measured on it from here on")
    have_k = {(k.get("sheet"), int(k.get("row"))) for k in (spec.get("key_rows") or [])}
    for k in (obj.get("keys") or []):
        if not isinstance(k, dict):
            continue
        site, why = _parse(k.get("ref", ""), wb)
        if site is None:
            dropped.append(f"key {k.get('ref')}: {why}")
            continue
        sh, r = site
        cols = year_columns(spec, sh) or {}
        tcol = cols.get(str(target_year))
        v = None
        # an EMPTY cell evaluates to zero and is not a computed row: the model
        # must actually hold something there
        # A KEY IS VERIFIED BY EXISTING (reviewer 2026-09-17: the CX referee threw
        # out 10 of 12 correct keys because this evaluator cannot compute
        # AVERAGEIFS, a full-column FX!B:B or '&' — code rejecting the analyst's
        # own rows for ITS OWN limitation). The model must hold something the row
        # computes in the target column; when code cannot work it out, the
        # workbook's CACHED value stands, and if there is none the key is still
        # taken and marked "not evaluable offline".
        why_k, held, offline = "", None, False
        if not tcol:
            why_k = f"sheet '{sh}' has no column for {target_year} in this model's year axis"
        else:
            held = wb[sh][f"{tcol}{r}"].value
            if held in (None, ""):
                why_k = f"{tcol}{r} is empty — the model holds nothing on that row this year"
            else:
                try:
                    v = ev.cell(sh, f"{tcol}{r}")
                except Exception as e_k:    # noqa: BLE001 — said, not swallowed
                    v = None
                    log(f"[anatomy] {sh}!{tcol}{r} will not evaluate here "
                        f"({type(e_k).__name__}: {str(e_k)[:70]}) — reading the workbook's cached value")
                if not isinstance(v, (int, float)):
                    v = cached(sh, f"{tcol}{r}")
                    offline = v is None
        if why_k:
            dropped.append(f"key {sh}!{r} as '{k.get('name')}': {why_k}")
            continue
        if (sh, r) in have_k:
            continue
        spec.setdefault("key_rows", []).append(
            {"name": str(k.get("name"))[:40], "sheet": sh, "row": r, "source": "the brain's anatomy"})
        have_k.add((sh, r))
        took_k += 1
        log(f"[anatomy] key '{str(k.get('name'))[:32]}' at {sh}!{r} reads "
            + (f"{v:,.2f}" if isinstance(v, (int, float)) else "— not evaluable offline; the row stands as the model's own"))
        if offline:
            notes_off.append(f"{sh}!{tcol}{r} '{str(k.get('name'))[:30]}' is not evaluable offline "
                             f"({str(held)[:40]}) — its tie is measured in Excel, not here")
    notes = spec.setdefault("anatomy_notes", [])
    notes += notes_off
    for s_ in (obj.get("statements") or []):
        if isinstance(s_, dict) and s_.get("sheet"):
            notes.append(f"sheet '{s_['sheet']}' is {str(s_.get('role') or 'unnamed')}")
    for d in (obj.get("definitions") or [])[:20]:
        notes.append(f"definition: {str(d)[:160]}")
    for i_ in (obj.get("inputs") or [])[:60]:
        site, _w = _parse(i_, wb)
        if site:
            spec.setdefault("input_sites", []).append({"sheet": site[0], "row": site[1]})
    # OBJECTIVE 1 MUST EXIST ON EVERY MODEL (reviewer 2026-09-17: CX shipped
    # 1,787 out of balance with nothing measuring it). If the book declares no
    # check row of its own, the two total rows the brain just named ARE the
    # balance test, and code measures their difference from here on.
    if not (spec.get("check_rows") or []):
        by_name = {str(k.get("name") or "").lower(): k for k in (spec.get("key_rows") or [])}
        a = by_name.get("total assets")
        b = (by_name.get("total liabilities and equity")
             or by_name.get("total liabilities & equity"))
        if a and b:
            spec.setdefault("check_pairs", []).append(
                {"name": "balance", "sheet": a["sheet"], "a_row": int(a["row"]),
                 "b_sheet": b["sheet"], "b_row": int(b["row"])})
            log(f"[anatomy] this model declares NO check row — the balance objective is the run's own: "
                f"{a['sheet']}!{a['row']} (total assets) less {b['sheet']}!{b['row']} "
                "(total liabilities and equity); measured every year from here on")
            notes.append(f"balance measured by the RUN, not the model: {a['sheet']}!{a['row']} − "
                         f"{b['sheet']}!{b['row']} (this book declares no check row)")
        else:
            log("[anatomy] this model declares no check row, and the two total rows were not both "
                "named — BALANCE IS NOT MEASURED on this run")
            notes.append("balance NOT measured: no check row, and total assets / total liabilities "
                         "and equity were not both named")
    for d in dropped:
        log(f"[anatomy] dropped {d}")
    log(f"[anatomy] the brain read this model: {took_c} check row(s) and {took_k} key row(s) taken, "
        f"{len(dropped)} dropped — {str(obj.get('because') or '')[:120]}")
    return took_c, took_k, dropped
