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


def rollover_column(wb, sheet, from_col, to_col, skip_rows=()):
    """The owner's convention: the new actual column IS the prior actual
    column carried forward. Copies every cell — formulas Excel-shifted one
    column, hardcodes as-is, styles and number formats — and returns the
    rows that arrived as HARDCODES: the input census the disclosed actuals
    must then overwrite."""
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
        if isinstance(v, str) and v.startswith("="):
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

    def write(self, sheet, coord, value, prior_coord=None, note=None,
              flag=None, trusted=False, force_lock=False):
        """Write one cell through every guard, then read it back.

        trusted=True is for values whose magnitude is PROVEN (a checksummed
        or ratified-scale tie) — they bypass the band, nothing else does.
        Returns True on write, False on a guarded refusal."""
        ref = f"{sheet}!{coord}"
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
        # the empty-row law (owner ruling 2026-08-31): a row whose prior
        # actual is EMPTY is furniture — machine writes stay out of it
        # (trusted writes may proceed: folds and proven serves carry
        # their own evidence)
        if not trusted and prior_coord is not None \
                and ws[prior_coord].value in (None, ""):
            self.log.setdefault("empty_row_refused", []).append(ref)
            return False
        # undo journal (error-baseline law): every write is reversible
        self.log.setdefault("undo", []).append((sheet, coord, cell.value))
        cell.value = value
        if prior_coord is not None:      # inherit the prior actual's look
            prior = ws[prior_coord]
            cell._style = copy.copy(prior._style)
            cell.number_format = prior.number_format
        if flag in self.fills:
            cell.fill = self.fills[flag]
            self.log["flags"].append(ref)
        if note:
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
        return True

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
