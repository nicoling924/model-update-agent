"""The write layer — one chokepoint, every guard, nothing else writes.

The write monopoly (council ruling): a cell may be written by Stage 2's
join, Stage 3's checksummed read, or a Stage-4 repair that cites a failed
check and a source item. Whatever the writer, the write itself passes
through Writer.write below, which enforces:

- WORLD-BAND GUARD (run-112b/115 law): a mechanical write may never leave
  the row's order of magnitude vs its prior actual (>100x or <1% refused).
  Checksum-proven writes pass trusted=True — their magnitude is proven by
  the tie, not assumed.
- NUMERIC PREVIEW (run-114 law): a pure-arithmetic formula string is a
  number wearing an '='. It is evaluated and the NUMBER is guarded —
  formula-writing paths do not bypass the band.
- READ-BACK: every write is re-read; a mismatch raises. Success codes are
  never trusted.
- FLAGS: two-tier house colors — FFC7CE uncertain/needs-review, FFC000
  backed-out/derived — with methodology notes.
- LOCKS: cells the run has proven (checksummed) may be locked against
  later, lower-confidence writers.

Plus the OWNER'S COLUMN CONVENTION as the primary conversion move:
rollover_column copies the ENTIRE prior actual column — formulas
(Excel-shifted one column right), values, cell types, number formats —
so the new column is the prior column carried forward, and only the
hardcoded inputs are then overwritten with disclosed actuals. The analyst
finds everything exactly where they left it.

And the honesty instruments: formula_map + clobber_diff prove no formula
outside the allowed columns changed (non-empty diff = delivery blocked).

Generic by construction: nothing in here knows a company, a language, or
a layout — only cells, priors, and magnitudes.
"""
import copy
import re

import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill

AUTHOR = "Model Update Agent"
FLAG_UNCERTAIN = "FFC7CE"    # light red: uncertain / needs analyst review
FLAG_BACKEDOUT = "FFC000"    # orange: backed-out / derived, awaiting true-up
FLAG_FROZEN = "BDD7EE"       # light blue: a FORECAST cell the agent froze,
                             # held or plugged (owner 2026-09-07: forecast
                             # years carry only this colour — error and
                             # back-out flags live in the actual column)
BAND_RATIO = 100.0           # world-band guard: refuse >100x or <1% of prior

_ARITH_FORMULA = re.compile(r"^=[\d+\-*/(). eE]+$")


class WriteError(RuntimeError):
    pass


def load(path, data_only=False):
    return openpyxl.load_workbook(path, data_only=data_only)


def save(wb, path):
    wb.calculation.fullCalcOnLoad = True   # Excel fully recalcs on open
    wb.save(path)


# -- column arithmetic --------------------------------------------------------

def col_to_num(col):
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def num_to_col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def shift_formula_excel(formula, offset=1):
    """Shift ALL relative column references by `offset`, exactly like Excel's
    copy-paste one column right: AG20*AH21 -> AH20*AI21. $-absolute columns
    and row numbers stay put; sheet-qualified relative refs shift too (Excel
    does); quoted sheet names are protected from the column pattern."""
    pat = re.compile(r"(\$?)([A-Z]{1,3})(\$?\d+)")

    def sub(m):
        if m.group(1) == "$":
            return m.group(0)
        return num_to_col(col_to_num(m.group(2)) + offset) + m.group(3)

    parts = re.split(r"('[^']*')", formula)
    return "".join(p if p.startswith("'") else pat.sub(sub, p) for p in parts)


def _shape(formula):
    """A formula's structure with every column letter blanked: '=EY152+EX152'
    and '=EU152+ET152' share a shape; '=T4*(1+V22)' does not share it with
    a hardcode or with '=U4'. Rows, operators and functions stay."""
    import re as _re
    return _re.sub(r"(?<![A-Za-z_])\$?[A-Z]{1,3}\$?(\d+)", r"C\1", str(formula).replace("$", ""))


def unforecast_rows(wb, sheet, target_col, forecast_cols, evaluate=None):
    """THE ZERO-FORECAST ROW (owner 2026-09-14, CLP ROAFNA!AI71 'Coal-fired
    (CAPCO)': 2025 typed 0 and every forecast year linked to it — the
    rollover carried last year's −1,050 in and the forecasts followed):
    the rows whose target-year cell and every forecast cell all evaluate
    to zero or blank BEFORE the update — the analyst's own decision that
    the item is nil from here on. -> set of row numbers."""
    ws = wb[sheet]
    out = set()
    if not forecast_cols:
        return out
    def _val(coord):
        v = ws[coord].value
        if isinstance(v, str) and v.startswith("=") and evaluate is not None:
            try:
                v = evaluate(sheet, coord)
            except Exception:
                return None
        return v
    for r in range(1, ws.max_row + 1):
        lab = ws.cell(r, 1).value
        if not (isinstance(lab, str) and lab.strip()):
            continue
        vals = [_val(f"{target_col}{r}")] + [_val(f"{c}{r}") for c in forecast_cols]
        if all(v in (None, "", 0, 0.0) or (isinstance(v, float) and abs(v) < 1e-9) for v in vals) \
                and any(v is not None for v in vals):
            out.add(r)
    return out


def rollover_column(wb, sheet, from_col, to_col, skip_rows=(), zero_rows=()):
    """The owner's convention: the new actual column IS the prior actual
    column carried forward. Copies every cell — formulas Excel-shifted one
    column, hardcodes as-is, styles and number formats — and returns the
    rows that arrived as HARDCODES: the input census the disclosed actuals
    must then overwrite. A row in `zero_rows` (the analyst had it at zero
    this year and every forecast year) rolls in as 0, the analyst's own
    figure — still an input a proven read may overwrite, never a stale one."""
    ws = wb[sheet]
    offset = col_to_num(to_col) - col_to_num(from_col)
    hardcode_rows = []
    for r in range(1, ws.max_row + 1):
        if r in skip_rows:
            continue
        src, dst = ws[f"{from_col}{r}"], ws[f"{to_col}{r}"]
        if type(src).__name__ == "MergedCell" or type(dst).__name__ == "MergedCell":
            continue
        v = src.value
        if v is None:
            dst.value = None
            continue
        if r in zero_rows and isinstance(v, (int, float)) and not isinstance(v, bool):
            dst.value = 0                      # the analyst's own figure this year
            dst._style = copy.copy(src._style)
            dst.number_format = src.number_format
            hardcode_rows.append(r)            # still an input: a PROVEN printed figure may land
            continue
        # THE ANALYST'S OWN PERIOD MARK IS KEPT (half-year replay 2026-09-09:
        # the roll copied 'H124' over the analyst's 'H125' header and the
        # workbook left with two H124 columns): a target header cell that
        # already marks a period other than the source's is the author's,
        # not a stale copy
        if r <= 12:
            from .discover import _year_of as _yo
            ys, yd = _yo(v)[0], _yo(dst.value)[0]
            if ys is not None and yd is not None and yd != ys:
                continue
        if isinstance(v, str) and v.startswith("="):
            # THE ANALYST'S OWN CARRIED-FORWARD FORMULA IS KEPT (half-year
            # replay 2026-09-09: the H125 column already held '=EY152+EX152'
            # — the prior's '=EU152+ET152' one period on, at the QUARTERLY
            # stride — and the two-column shift wrote '=EW152+EV152', the
            # wrong half, breaking 31 cells). A target formula of the same
            # SHAPE as the prior's (same rows and operators, columns moved)
            # is the same structure already rolled by its author: keep it.
            tv = dst.value
            if isinstance(tv, str) and tv.startswith("=") and _shape(tv) == _shape(v):
                dst._style = copy.copy(src._style)
                dst.number_format = src.number_format
                continue
            dst.value = shift_formula_excel(v, offset)
        else:
            dst.value = v
            if isinstance(v, (int, float)):
                hardcode_rows.append(r)
        dst._style = copy.copy(src._style)
        dst.number_format = src.number_format
    return hardcode_rows


def roll_year_headers(writer, sheet, pcol, tcol, prior_year, target_year,
                      scan_rows=12):
    """Roll every year header cell in the target column to the new period,
    PRESERVING the prior header's data type (delivery-gate law: numeric 2024
    -> numeric 2025; a date stays a date; text 'FY2024' -> 'FY2025'; never
    change a header's type — downstream math may read it)."""
    ws = writer.wb[sheet]
    py, ty = str(prior_year), str(target_year)
    n = 0
    for r in range(1, min(ws.max_row, scan_rows) + 1):
        pv = ws[f"{pcol}{r}"].value
        if pv is None:
            continue
        nv = None
        if isinstance(pv, (int, float)) and not isinstance(pv, bool) \
                and abs(pv - int(py)) < 0.5:
            nv = int(ty) if float(pv).is_integer() else float(ty)
        elif hasattr(pv, "year") and pv.year == int(py):
            try:
                nv = pv.replace(year=int(ty))
            except ValueError:          # Feb 29 in a non-leap target year
                nv = pv.replace(year=int(ty), day=28)
        elif isinstance(pv, str) and py in pv:
            nv = pv.replace(py, ty)
        elif isinstance(pv, str):
            # two-digit period marks ('H124' -> 'H125', '1H24' -> '1H25',
            # 'FY24' -> 'FY25'): the mark's own year moves one on
            import re as _re
            m_ = _re.fullmatch(r"\s*((?:H[12]|[12]H|Q[1-4]|[1-4]Q|FY)\s*'?)(\d{2})(\s*[AEae]?\s*)", pv)
            if m_ and int(m_.group(2)) == int(py) % 100:
                nv = f"{m_.group(1)}{int(ty) % 100:02d}{m_.group(3)}"
        if nv is None or ws[f"{tcol}{r}"].value == nv:
            continue
        if writer.write(sheet, f"{tcol}{r}", nv, prior_coord=f"{pcol}{r}",
                        trusted=True):
            n += 1
    return n


# -- the chokepoint -----------------------------------------------------------

class Writer:
    def __init__(self, wb):
        self.wb = wb
        self.fills = {
            "red": PatternFill("solid", start_color="FF" + FLAG_UNCERTAIN,
                               end_color="FF" + FLAG_UNCERTAIN),
            "orange": PatternFill("solid", start_color="FF" + FLAG_BACKEDOUT,
                                  end_color="FF" + FLAG_BACKEDOUT),
            "blue": PatternFill("solid", start_color="FF" + FLAG_FROZEN,
                                end_color="FF" + FLAG_FROZEN),
        }
        self.log = {"written": [], "flags": [], "restatements": [],
                    "skipped_merged": [], "band_refused": [], "lock_refused": []}
        self.locked = set()          # "Sheet!C7" cells proven by checksum
        self.prior_lookup = None     # optional (sheet, coord) -> prior actual

    def lock(self, sheet, coord):
        self.locked.add(f"{sheet}!{coord}")

    def _prior_for(self, ws, sheet, coord, prior_coord):
        if prior_coord is not None:
            v = ws[prior_coord].value
            if isinstance(v, (int, float)):
                return v
        if self.prior_lookup is not None:
            try:
                v = self.prior_lookup(sheet, coord)
            except Exception:
                return None
            if isinstance(v, (int, float)):
                return v
        return None

    # -- FORECAST YEARS CARRY NO ERROR FLAG (owner 2026-09-07): the agent
    # makes the model's own arithmetic and the typed actual agree, so a
    # forecast cell has nothing to be red about. What a law finds strange
    # in a forecast row goes on the WATCH LIST (reported, never painted);
    # the cause it identifies is flagged where it lives — the actual
    # column. Blue is the only forecast-year colour: frozen / held /
    # plugged forecast inputs.
    forecast_cols = {}          # {sheet: set(column letters)} set by the run

    def in_forecast(self, sheet, coord):
        cols = self.forecast_cols.get(sheet) or ()
        col = "".join(ch for ch in str(coord) if ch.isalpha())
        return col in cols

    def watch(self, sheet, coord, why):
        ref = f"{sheet}!{coord}"
        lst = self.log.setdefault("forecast_watch", [])
        if not any(x[0] == ref for x in lst):
            lst.append((ref, str(why)[:200]))
        return ref

    def write(self, sheet, coord, value, prior_coord=None, note=None,
              flag=None, trusted=False, force_lock=False, allow_empty=False,
              kind=None):
        """Write one cell through every guard, then read it back.

        trusted=True is for values whose magnitude is PROVEN (a checksummed
        or ratified-scale tie) — they bypass the band, nothing else does.
        kind="plug" declares a plug: THE PLUG LAW (owner 2026-09-14, "a plug
        should only be used as the last resort — analysts hate plugs")
        refuses it until the run has opened the last-resort stage
        (plugs_allowed), i.e. after every evidence stage had its turn on
        the checks; a plug that lands is recorded in log["plugs"].
        Returns True on write, False on a guarded refusal."""
        ref = f"{sheet}!{coord}"
        if kind == "plug" and not getattr(self, "plugs_allowed", False):
            self.log.setdefault("plug_refused", []).append(ref)
            return False
        if ref in self.locked and not force_lock:
            self.log["lock_refused"].append(ref)
            return False
        ws = self.wb[sheet]
        cell = ws[coord]
        if type(cell).__name__ == "MergedCell":
            self.log["skipped_merged"].append(ref)
            return False
        # numeric preview (run-114): judge the NUMBER inside '=a*b' strings
        guard_v = value
        if isinstance(value, str) and _ARITH_FORMULA.match(value):
            try:
                guard_v = float(eval(value[1:], {"__builtins__": {}}, {}))
            except Exception:
                guard_v = None
        # world-band guard (run-112b/115)
        if not trusted and isinstance(guard_v, (int, float)) and guard_v != 0:
            pv = self._prior_for(ws, sheet, coord, prior_coord)
            if isinstance(pv, (int, float)) and pv != 0 and (
                    abs(guard_v) > BAND_RATIO * abs(pv)
                    or abs(guard_v) * BAND_RATIO < abs(pv)):
                self.log["band_refused"].append(
                    f"{ref}: {value!r} (≈{guard_v:,.1f}) vs prior {pv!r}")
                return False
        # THE NEVER-FILLED ROW LAW (owner 2026-09-14, "an overall check for
        # the whole run"): a row that holds no number and no formula in ANY
        # other cell — nothing in the past, nothing in the future — is a
        # caption or a line the analyst never tracked; no step of the run
        # writes into it (DFE live 2026-09-10: label cards filled 'Revenue'
        # over the segment lines and MW headings with fractions). Trusted
        # writes are refused too: the law is the writer's, not a step's.
        if (isinstance(value, (int, float)) or (isinstance(value, str) and value.startswith("="))) \
                and row_never_filled(ws, coord):
            self.log.setdefault("never_filled_refused", []).append(ref)
            return False
        # THE UNFORECAST ROW LAW (owner 2026-09-14, CLP Aus!AI71 'Tallawarra
        # (gas)': last year typed, this year and every forecast year empty —
        # a row the analyst stopped carrying; the tier-3 sweep held it at
        # the group's growth): an ESTIMATE of the agent's own (a hold, a
        # back-out — the orange writes) never lands in a row whose forecast
        # cells are all empty or zero. A proven printed figure still may.
        if flag == "orange" and self._row_unforecast(sheet, coord):
            self.log.setdefault("unforecast_refused", []).append(ref)
            return False
        # the empty-row law (owner ruling 2026-08-31): a row whose prior
        # actual is EMPTY is furniture — machine writes stay out of it
        # (trusted writes may proceed: folds and proven serves carry
        # their own evidence)
        # (allow_empty: the brain filled a row the model names but never
        # held — a label-only card, owner 2026-09-08 — it lands red)
        if not trusted and not allow_empty and prior_coord is not None \
                and ws[prior_coord].value in (None, ""):
            self.log.setdefault("empty_row_refused", []).append(ref)
            return False
        # undo journal (error-baseline law): every write is reversible
        self.log.setdefault("undo", []).append((sheet, coord, cell.value))
        # append-only write ledger (gate loop, 2026-09-02): the guards
        # POP the undo journal while unwinding, so a take-back that
        # reads it after the guards sees nothing — this one is never
        # consumed
        self.log.setdefault("writes_all", []).append(
            (sheet, coord, cell.value, value))
        # the style journal, parallel to writes_all: what the cell LOOKED
        # like before this write, so a take-back restores the colour and
        # the note with the value (DFE live 2026-09-10: the investigator's
        # restore of Driver!J10 wiped the constants law's red)
        self.log.setdefault("style_journal", []).append(
            (sheet, coord, _fill_rgb(cell),
             str(cell.comment.text) if cell.comment is not None else None,
             ref in self.log["flags"]))
        cell.value = value
        if prior_coord is not None:      # inherit the prior actual's look
            prior = ws[prior_coord]
            cell._style = copy.copy(prior._style)
            cell.number_format = prior.number_format
        if flag in self.fills:
            cell.fill = self.fills[flag]
            self.log["flags"].append(ref)
        # notes only on highlighted cells (owner ruling, run 233): a plain
        # updated input carries no note — its provenance lives in the run
        # log and provenance.json, not in the analyst's face
        if note and flag in self.fills:
            cell.comment = Comment(str(note)[:700], AUTHOR)
        got = ws[coord].value
        if got != value:
            raise WriteError(f"read-back mismatch {ref}: wrote {value!r} got {got!r}")
        self.log["written"].append(ref)
        # a successful write REPLACES the cell's standing flag state: a
        # proven rewrite clears it, a flagged write records exactly one
        # entry (the stale fill/style was replaced above either way)
        if ref in self.log["flags"]:
            self.log["flags"] = [f for f in self.log["flags"] if f != ref]
        if flag in self.fills:
            self.log["flags"].append(ref)
        if kind == "plug":
            self.log.setdefault("plugs", []).append(ref)
        return True

    # -- the flag, the revert: journaled like every write -------------------

    def flag(self, sheet, coord, colour, note=None):
        """Paint a cell's flag through the gate: journaled (a take-back
        restores the look), logged once, note only with a flag (owner:
        notes only on flagged cells). colour None clears the flag."""
        ws = self.wb[sheet]
        cell = ws[coord]
        ref = f"{sheet}!{coord}"
        self.log.setdefault("style_journal", []).append(
            (sheet, coord, _fill_rgb(cell),
             str(cell.comment.text) if cell.comment is not None else None,
             ref in self.log["flags"]))
        self.log.setdefault("writes_all", []).append((sheet, coord, cell.value, cell.value))
        self.log["flags"] = [f for f in self.log["flags"] if f != ref]
        if colour in self.fills:
            cell.fill = copy.copy(self.fills[colour])
            if note:
                cell.comment = Comment(str(note)[:700], AUTHOR)
            self.log["flags"].append(ref)
        else:
            cell.fill = PatternFill()
            cell.comment = None
        return True

    def revert(self, sheet, coord, old, colour=None, note=None):
        """A write taken back by a guard: the old value lands through the
        gate, the cell is unlocked and un-served (it is no longer proven —
        run 2026-09-14 audit: reverted serves stayed locked and 'proven'),
        and it wears the colour the guard gives it (red: unconfirmed)."""
        ref = f"{sheet}!{coord}"
        ok = self.write(sheet, coord, old, trusted=True, force_lock=True)
        if not ok:
            return False
        self.locked.discard(ref)
        served = getattr(self, "served", None)
        if isinstance(served, dict):
            served.pop((sheet, int(re.sub(r"[A-Z]+", "", coord))), None)
        if colour:
            self.flag(sheet, coord, colour, note)
        return True

    def _row_unforecast(self, sheet, coord):
        """True when the analyst does not forecast this row: it is in the
        run's zero-forecast set (measured on the pre-update model), or —
        without that set — every forecast cell of the row is empty or zero."""
        row = int(re.sub(r"[A-Z]+", "", coord))
        zset = getattr(self, "unforecast_rows", None)
        if zset is not None:
            return (sheet, row) in zset
        fcols = (getattr(self, "forecast_cols", None) or {}).get(sheet) or []
        if not fcols:
            return False
        ws = self.wb[sheet]
        for c in fcols:
            v = ws[f"{c}{row}"].value
            if isinstance(v, str) and v.startswith("="):
                return False
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v != 0:
                return False
        return True

    def restore_style(self, sheet, coord, style):
        """Put a cell's colour, note and flag standing back as the journal
        recorded them before a write that is now taken back."""
        _sh, _co, rgb, note, flagged = style
        cell = self.wb[sheet][coord]
        ref = f"{sheet}!{coord}"
        by_rgb = {v.fgColor.rgb[-6:]: v for v in self.fills.values()}
        cell.fill = copy.copy(by_rgb[rgb]) if rgb in by_rgb else PatternFill()
        cell.comment = Comment(note[:700], AUTHOR) if note else None
        self.log["flags"] = [f for f in self.log["flags"] if f != ref]
        if flagged:
            self.log["flags"].append(ref)

    def take_back(self, sheet, coord, old, style):
        """A write undone: the old value AND the old look; the cell is
        unlocked and un-served (what the run believed about it goes too)."""
        ok = self.write(sheet, coord, old, trusted=True, force_lock=True)
        if ok:
            self.restore_style(sheet, coord, style)
            self.locked.discard(f"{sheet}!{coord}")
            served = getattr(self, "served", None)
            if isinstance(served, dict):
                served.pop((sheet, int(re.sub(r"[A-Z]+", "", coord))), None)
        return ok

    def restate(self, sheet, coord, new_value, why):
        """Restatement write: prior-period history corrected to the new
        disclosure's comparatives, always annotated, always logged."""
        ws = self.wb[sheet]
        old = ws[coord].value
        ws[coord].value = new_value
        ws[coord].comment = Comment(f"RESTATED: was {old!r}. {why}"[:700], AUTHOR)
        self.log["restatements"].append(f"{sheet}!{coord}: {old!r} -> {new_value!r} ({why})")

    def format_rollover(self, sheet, from_col, to_col):
        """Formats only, prior column -> target column, every populated cell;
        flag fills survive (they are the run's 'look here' markers)."""
        ws = self.wb[sheet]
        flagged = set(self.log["flags"])
        for r in range(1, ws.max_row + 1):
            cell = ws[f"{to_col}{r}"]
            if type(cell).__name__ == "MergedCell" or cell.value is None:
                continue
            src = ws[f"{from_col}{r}"]
            keep = f"{sheet}!{to_col}{r}" in flagged
            fill = copy.copy(cell.fill) if keep else None
            cell._style = copy.copy(src._style)
            cell.number_format = src.number_format
            if keep:
                cell.fill = fill


def _fill_rgb(cell):
    try:
        f = cell.fill
        return (f.fgColor.rgb or "")[-6:] if f is not None and f.fill_type == "solid" else ""
    except Exception:
        return ""


def row_never_filled(ws, coord):
    """True when no cell of the row but the one addressed holds a number
    (a typed zero counts: the analyst typed it) or a formula: the analyst
    never tracked this line, in any period, past or future."""
    row = int(re.sub(r"[A-Z]+", "", coord))
    for c in range(2, ws.max_column + 1):
        cell = ws.cell(row, c)
        if cell.coordinate == coord:
            continue
        v = cell.value
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.startswith("=")):
            return False
    return True


# -- honesty instruments ------------------------------------------------------

def formula_map(wb):
    """{sheet: {coord: value-or-formula}} for every populated cell. Array/
    data-table formula objects render as stable tokens (their reprs carry
    memory addresses that differ every load — comparing those makes every
    diff a false clobber)."""
    out = {}
    for ws in wb.worksheets:
        m = {}
        for row in ws.iter_rows():
            for c in row:
                if c.value is None:
                    continue
                v = c.value
                if isinstance(v, (int, float, str)):
                    m[c.coordinate] = v
                else:
                    m[c.coordinate] = (f"<{type(v).__name__}:"
                                       f"{getattr(v, 'ref', '')}:"
                                       f"{getattr(v, 'text', '')}>")
        out[ws.title] = m
    return out


def clobber_diff(pre_map, post_wb, allowed_cols, allowed_cells=(), skip_sheets=()):
    """Cells changed outside the allowed target column(s) and explicitly
    allowed cells. Non-empty = formulas were clobbered = delivery blocked."""
    post = formula_map(post_wb)
    col_pat = (re.compile(rf"^(?:{'|'.join(allowed_cols)})\d+$")
               if allowed_cols else None)
    bad = []
    for sheet in set(pre_map) | set(post):
        if sheet in skip_sheets:
            continue
        pre_cells = pre_map.get(sheet, {})
        post_cells = post.get(sheet, {})
        for k in set(pre_cells) | set(post_cells):
            a, b = pre_cells.get(k), post_cells.get(k)
            if a == b:
                continue
            if (a is None or a == "") and (b is None or b == ""):
                continue    # openpyxl normalizes empty strings on save/load
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
                    and abs(a - b) < 1e-9:
                continue
            if col_pat and col_pat.match(k):
                continue
            if (sheet, k) in allowed_cells:
                continue
            bad.append((sheet, k, a, b))
    return bad


_SINGLE_REF = re.compile(
    r"^=\s*-?\s*(?:'([^']+)'|([A-Za-z][A-Za-z0-9 _]*))!([A-Z]{1,3})(\d+)\s*$")


def resolve_input_site(wb, sheet, row, prior_col, depth=0):
    """Where is this row's number ACTUALLY typed? The analyst's own prior
    column answers: a hardcode -> here; a single cross-sheet reference ->
    follow it; anything composite -> a derived row, not an input site."""
    if depth > 4 or sheet not in wb.sheetnames:
        return None
    try:
        v = wb[sheet][f"{prior_col}{row}"].value
    except Exception:
        return None
    if isinstance(v, (int, float)):
        return (sheet, row)
    if not isinstance(v, str) or not v.startswith("="):
        return None
    m = _SINGLE_REF.match(v.replace("$", "").strip())
    if not m:
        return None
    tgt_sheet = (m.group(1) or m.group(2) or "").strip()
    return resolve_input_site(wb, tgt_sheet, int(m.group(4)), m.group(3), depth + 1)
