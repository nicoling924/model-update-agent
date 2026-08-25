"""Label resolution — a model row's label cell may be a REFERENCE
(='A6', ='Driver'!A6): the analyst writes the block once and points at
it. Kinship, joins, and cards need the TEXT the reference lands on
(overnight 2026-08-25: the whole new-orders block had '=A6'-style labels,
so every row looked nameless and the block stayed stale)."""
import re

_REF = re.compile(r"^=\+?\s*(?:'([^']+)'|([A-Za-z0-9 _]+))?!?"
                  r"\$?([A-Z]{1,3})\$?(\d+)\s*$")


def resolve_label(wb, sheet, row, cols=("A", "B", "C", "D"), hops=3):
    """The row's label text, following simple reference formulas."""
    ws = wb[sheet] if sheet in wb.sheetnames else None
    if ws is None:
        return ""
    for lc in cols:
        v = ws[f"{lc}{row}"].value
        for _ in range(hops):
            if not (isinstance(v, str) and v.startswith("=")):
                break
            m = _REF.match(v.replace("$", ""))
            if not m:
                break
            sh2 = (m.group(1) or m.group(2) or sheet).strip()
            if sh2 not in wb.sheetnames:
                v = None
                break
            v = wb[sh2][f"{m.group(3)}{m.group(4)}"].value
        if isinstance(v, str) and v.strip() and not v.startswith("="):
            return v.strip()
    return ""
