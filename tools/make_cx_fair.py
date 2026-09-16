"""Blank every FY2025 actual left in the CX test model (owner's ruling 2026-09-17).

Rule, per cell in an FY2025 column:
  * a period mark / label in the header block is kept;
  * a cell that HOLDS AN ACTUAL (a constant, or a formula that is only literals
    e.g. '=2583+3403') is replaced by what the analyst would have had before the
    update:  the prior-year (FY2024) equivalent cell's formula rolled forward if
    that cell is a real formula, otherwise EMPTY (never 0);
  * a cell that COMPUTES from other cells is left alone - it carries no actual.
Everything else in the workbook (formulas, styles, names, other sheets) is untouched.
"""
import re, shutil, sys
import openpyxl
from openpyxl.utils import get_column_letter as gl, column_index_from_string as ci

SRC = sys.argv[1]
DST = sys.argv[2]

HAS_REF = re.compile(r'(?<![A-Za-z0-9_$!])\$?[A-Za-z]{1,3}\$?\d+(?![\w(])')
YEAR = re.compile(r'(19|20)\d{2}')
# a same-sheet A1 reference not preceded by a sheet qualifier
REF = re.compile(r'(?<![A-Za-z0-9_.!])(\$?)([A-Za-z]{1,3})(\$?)(\d+)(?![\w(])')

def is_formula(v):
    return isinstance(v, str) and v.startswith('=')

def holds_actual(v):
    """A constant, or a formula made only of literals - both are hardcoded data."""
    if v is None:
        return False
    if is_formula(v):
        return not HAS_REF.search(v[1:])
    return not isinstance(v, str) or not v.strip() == ''

def shift(formula, ncols):
    """Shift every UNQUALIFIED A1 ref by ncols. Refs carrying a sheet name are
    left alone (another sheet has its own period axis) and reported."""
    foreign = []
    for m in re.finditer(r"(?:'[^']+'|[A-Za-z_][A-Za-z0-9_. ]*)!", formula):
        foreign.append(m.group()[:-1])
    out, last = [], 0
    for m in REF.finditer(formula):
        s, e = m.span()
        # skip refs that follow a '!' (qualified) - REF's lookbehind covers '!'
        out.append(formula[last:s])
        d1, col, d2, row = m.groups()
        try:
            newcol = gl(ci(col) + ncols)
        except Exception:
            newcol = col
        out.append(f'{d1}{newcol}{d2}{row}')
        last = e
    out.append(formula[last:])
    return ''.join(out), foreign

def year_mark(ws, r, c, header_rows):
    v = ws.cell(r, c).value
    if r > header_rows:
        return False
    if isinstance(v, str) and YEAR.search(v):
        return True
    return False

def clean(ws, col, prev_col, header_rows, rows=None, only_rows_matching=None,
          label_cols='ABCDEF', log=None):
    c, pc = ci(col), ci(prev_col)
    n_blank = n_roll = 0
    for r in (rows or range(1, ws.max_row + 1)):
        cell = ws.cell(r, c)
        if type(cell).__name__ == 'MergedCell':
            continue
        v = cell.value
        if v is None or not holds_actual(v):
            continue
        if year_mark(ws, r, c, header_rows):
            continue
        lab = ''
        for lc in label_cols:
            x = ws[f'{lc}{r}'].value
            if isinstance(x, str) and x.strip():
                lab = x.strip()[:40]; break
        if only_rows_matching and not only_rows_matching(lab):
            continue
        prev = ws.cell(r, pc).value
        if is_formula(prev) and HAS_REF.search(prev[1:]):
            new, foreign = shift(prev, c - pc)
            cell.value = new
            n_roll += 1
            log.append(f'  ROLL  {ws.title}!{col}{r} {str(v)[:18]!r} -> {new[:70]!r}'
                       + (f'  [cross-sheet refs left as-is: {foreign}]' if foreign else '')
                       + f'   | {lab}')
        else:
            cell.value = None
            n_blank += 1
            log.append(f'  BLANK {ws.title}!{col}{r} {str(v)[:24]!r}   | {lab}')
    return n_blank, n_roll

def main():
    shutil.copy(SRC, DST)
    wb = openpyxl.load_workbook(DST)
    log = []
    tally = {}

    # ---- CXMODEL 1H2025 (FI) and 2H2025 (FJ); prior-year equivalents FE / FF
    ws = wb['CXMODEL']
    for col, prev in (('FI', 'FE'), ('FJ', 'FF')):
        b, ro = clean(ws, col, prev, header_rows=14, label_cols='ABCDE', log=log)
        tally[f'CXMODEL!{col} (interim 2025)'] = (b, ro)

    # ---- CXMODEL FY2025 annual (AO) and its annual-split twin (FK) are NOT
    #      swept: the prep already rebuilt them from the FY2026 forecast column,
    #      and every constant left in them is that column's own assumption
    #      (checked cell by cell against AP/FO) - a forecast, not an actual.

    # ---- Monthly: the twelve 2025 month columns LB..LM (prior year = -12 cols)
    ws = wb['Monthly']
    tb = tr = 0
    for c in range(ci('LB'), ci('LM') + 1):
        b, ro = clean(ws, gl(c), gl(c - 12), header_rows=8, log=log)
        tb += b; tr += ro
    tally['Monthly!LB:LM (2025 months)'] = (tb, tr)

    # ---- Monthly 2026 columns: a hardcoded YoY / YTD % is FY2025 arithmetic
    #      in disguise (2026 value / 2025 value - 1), so it goes too.
    yo = lambda lab: ('yoy' in lab.lower() or 'ytd' in lab.lower())
    tb = tr = 0
    for c in range(ci('LN'), ws.max_column + 1):
        b, ro = clean(ws, gl(c), gl(c - 12), header_rows=8,
                      only_rows_matching=yo, log=log)
        tb += b; tr += ro
    tally['Monthly!LN.. (2026 YoY/YTD hardcodes derived from 2025)'] = (tb, tr)

    wb.save(DST)
    print('\n'.join(log))
    print('\n=== tally (blanked, rolled-forward) ===')
    for k, v in tally.items():
        print(f'  {k}: blanked={v[0]} rolled={v[1]}')

main()
