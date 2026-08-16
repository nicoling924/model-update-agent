"""The target census — the model side of the join, as data.

A TargetRow is one model row Stage 2 may serve: its address, its printed
label, its PRIOR-YEAR ACTUAL (the identity key the whole join hangs on),
any learned alias from the workbook's _SPEC memory, and whether the spec
declares it a composition/backout row (which must NEVER join — one
component line is not a composition).

Like the ledger, the census serializes to JSON so Stage 2 replays locally
from pinned files in seconds — workbook access happens once, here, and
nothing downstream needs openpyxl (lazy import; the local museum runs on
stdlib).
"""
import json
import re
from dataclasses import dataclass, asdict

_CELL_REF = re.compile(r"^\s*'?([^'!]+)'?!\D*(\d+)")


def _is_year_mark(v):
    """A year-axis cell: a 1990-2100 number, a date, or text carrying one
    ('FY2024', '2024-12-31', '1H2025')."""
    if isinstance(v, bool) or v is None:
        return False
    if isinstance(v, (int, float)):
        return 1990 <= v <= 2100 and abs(v - int(v)) < 0.5
    if hasattr(v, "year"):
        return 1990 <= v.year <= 2100
    return bool(re.search(r"(19\d{2}|20\d{2})", str(v)))


@dataclass
class TargetRow:
    sheet: str
    row: int
    label: str = ""
    prior_value: float = None    # prior-year ACTUAL, model units (None = no-prior row)
    prior2_value: float = None   # the year BEFORE prior — the doc-vintage negative key
    memory_hint: str = ""        # learned alias from the workbook _SPEC tab
    is_backout: bool = False     # spec-declared composition row: never joins

    @property
    def key(self):
        return (self.sheet, self.row)


def backout_addresses(spec):
    """{(sheet, row)} referenced by the spec's backout rules."""
    out = set()
    for br in (spec.get("backout_rules") or []):
        ref = str(br.get("row") or br.get("cell") or "")
        m = _CELL_REF.match(ref)
        if m:
            out.add((m.group(1), int(m.group(2))))
    return out


def from_workbook(wb_values, spec, target_year, hints=None, max_row=400,
                  label_cols=("A", "B", "C", "D")):
    """Build the census from a data_only workbook load + the run spec.

    For every sheet in spec.year_axis that maps both the target year and the
    year before it: each row's label is the first string in the label
    columns, the prior value is the prior actual column's cached value.
    Rows with neither label nor prior are not targets.
    """
    hints = hints or {}
    backouts = backout_addresses(spec)
    targets = []
    for sheet, axis in (spec.get("year_axis") or {}).items():
        cols = axis.get("columns") or {}
        years = sorted(cols)
        if str(target_year) not in years:
            continue
        i = years.index(str(target_year))
        if i == 0:
            continue
        pcol = cols[years[i - 1]]
        p2col = cols[years[i - 2]] if i >= 2 else None
        if sheet not in wb_values.sheetnames:
            continue
        ws = wb_values[sheet]
        for r in range(1, min(ws.max_row, max_row) + 1):
            label = ""
            for lc in label_cols:
                v = ws[f"{lc}{r}"].value
                if isinstance(v, str) and v.strip():
                    label = v.strip()
                    break
            pv = ws[f"{pcol}{r}"].value
            # a top-of-sheet row whose prior cell is a YEAR MARK is the year
            # axis, not data — serving it wrote 2,025/1e6 = 0.002025 into a
            # header (measured live, run 5)
            if r <= 12 and _is_year_mark(pv):
                continue
            prior = float(pv) if isinstance(pv, (int, float)) else None
            p2 = ws[f"{p2col}{r}"].value if p2col else None
            prior2 = float(p2) if isinstance(p2, (int, float)) else None
            if not label and prior is None:
                continue
            targets.append(TargetRow(
                sheet=sheet, row=r, label=label, prior_value=prior,
                prior2_value=prior2,
                memory_hint=str(hints.get((sheet, r)) or ""),
                is_backout=(sheet, r) in backouts))
    return targets


def known_prior_values(targets):
    """The model's prior-year actuals — Stage 1's vision-checksum anchor set."""
    return [t.prior_value for t in targets
            if isinstance(t.prior_value, (int, float))]


# -- pinned-snapshot serialization -------------------------------------------

def to_json(targets):
    return json.dumps({"version": 1, "targets": [asdict(t) for t in targets]},
                      ensure_ascii=False, indent=1)


def from_json(text):
    obj = json.loads(text)
    return [TargetRow(**d) for d in obj.get("targets") or []]


def save(targets, path):
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(to_json(targets), encoding="utf-8")


def load(path):
    from pathlib import Path
    return from_json(Path(path).read_text(encoding="utf-8"))
