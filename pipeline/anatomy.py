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
  total assets, equity, cash, the cash flows — whatever THIS model has. A key
  is a row the MODEL computes from its own inputs, never a place where the
  printed statement is retyped.
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
    """The cells this row actually holds, left to right."""
    ws = wb[sheet]
    out = []
    for c in range(1, min(ws.max_column, 80) + 1):
        cell = ws.cell(row, c)
        if isinstance(cell.value, (int, float)) or \
                (isinstance(cell.value, str) and cell.value.startswith("=")):
            out.append(cell.coordinate)
    return out


def _reads_zero(wb, ev, spec, sheet, row, target_year):
    """A CHECK IS A ROW THAT READS ZERO WHERE THE MODEL ALREADY CLOSED IT: the
    periods it already holds. -> (True, how_many) or (False, why). The target
    year and anything right of it are excluded — the run is about to change
    them, and a check that is currently broken is still a check."""
    cols = year_columns(spec, sheet) or {}
    past = {c for y, c in cols.items() if str(y).isdigit() and int(y) < int(target_year)}
    seen = bad = 0
    for coord in _row_cells(wb, sheet, row):
        col = "".join(ch for ch in coord if ch.isalpha())
        if cols and col not in past:
            continue                 # the target year, a forecast, or off the axis
        try:
            v = ev.cell(sheet, coord)
        except Exception:            # noqa: BLE001 — an unevaluable cell proves nothing either way
            continue
        if not isinstance(v, (int, float)):
            continue
        seen += 1
        if abs(v) > CHECK_TOL:
            bad += 1
    if seen < 2:
        return False, "the model closes this row in fewer than two periods — nothing to verify a check against"
    if bad:
        return False, f"it reads non-zero in {bad} of the {seen} periods the model already closed — not a check"
    return True, seen


def sheet_reading(wb, spec, target_year, cap=24000):
    """What code can show the brain: every sheet on the year axis (and every
    other sheet that holds labels), its year columns, and each row's label
    beside the formula the target year holds."""
    L = ["The sheets, their year columns, and their rows:"]
    axis = spec.get("year_axis") or {}
    order = [s for s in list(axis) + list(wb.sheetnames) if s in wb.sheetnames]
    order = list(dict.fromkeys(order))
    # EVERY SHEET GETS ITS SHARE OF THE BUDGET (the check row may live on the
    # sheet code found no year axis for — CX's Fleet!5 'Total Check'): a budget
    # spent first-come shows the brain one big sheet and hides the rest.
    share = max(400, cap // max(1, len(order)))
    for sh in order:
        room = share
        if sh not in wb.sheetnames:
            continue
        cols = year_columns(spec, sh) or {}
        tcol = cols.get(str(target_year))
        L.append(f"--- {sh}: {len(cols)} year column(s)"
                 + (f"; {target_year} is column {tcol}" if tcol else "; no year columns found") + " ---")
        ws = wb[sh]
        for r in range(1, min(ws.max_row, 400) + 1):
            lab = ""
            for c in range(1, 6):
                v = ws.cell(r, c).value
                if isinstance(v, str) and v.strip() and not v.startswith("="):
                    lab = v.strip()
                    break
            f = ws[f"{tcol}{r}"].value if tcol else None
            if not lab and not (isinstance(f, str) and f.startswith("=")):
                continue
            ln = f"  {r}: {lab[:46]}" + (f"   {str(f)[:44]}" if isinstance(f, str) and f.startswith("=") else "")
            if room - len(ln) < 0:
                L.append(f"  (… more rows of {sh}, not shown)")
                break
            room -= len(ln)
            L.append(ln)
    return "\n".join(L)


def read(wb, spec, client, target_year, log, period="FY"):
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
    took_c = took_k = 0
    dropped = []
    have_c = {(c.get("sheet"), int(c.get("row"))) for c in (spec.get("check_rows") or [])}
    for ref in (obj.get("checks") or []):
        site, why = _parse(ref, wb)
        if site is None:
            dropped.append(f"check {ref}: {why}")
            continue
        sh, r = site
        if (sh, r) in have_c:
            continue
        ok, detail = _reads_zero(wb, ev, spec, sh, r, target_year)
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
        if tcol and wb[sh][f"{tcol}{r}"].value not in (None, ""):
            try:
                v = ev.cell(sh, f"{tcol}{r}")
            except Exception:    # noqa: BLE001
                v = None
        if not isinstance(v, (int, float)):
            dropped.append(f"key {sh}!{r} as '{k.get('name')}': the model works out no "
                           "number there — a key is a row the model computes")
            continue
        if (sh, r) in have_k:
            continue
        spec.setdefault("key_rows", []).append(
            {"name": str(k.get("name"))[:40], "sheet": sh, "row": r, "source": "the brain's anatomy"})
        have_k.add((sh, r))
        took_k += 1
        log(f"[anatomy] key '{str(k.get('name'))[:32]}' at {sh}!{r} reads {v:,.2f}")
    notes = spec.setdefault("anatomy_notes", [])
    for s_ in (obj.get("statements") or []):
        if isinstance(s_, dict) and s_.get("sheet"):
            notes.append(f"sheet '{s_['sheet']}' is {str(s_.get('role') or 'unnamed')}")
    for d in (obj.get("definitions") or [])[:20]:
        notes.append(f"definition: {str(d)[:160]}")
    for i_ in (obj.get("inputs") or [])[:60]:
        site, _w = _parse(i_, wb)
        if site:
            spec.setdefault("input_sites", []).append({"sheet": site[0], "row": site[1]})
    for d in dropped:
        log(f"[anatomy] dropped {d}")
    log(f"[anatomy] the brain read this model: {took_c} check row(s) and {took_k} key row(s) taken, "
        f"{len(dropped)} dropped — {str(obj.get('because') or '')[:120]}")
    return took_c, took_k, dropped
