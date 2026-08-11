"""Workbook operations: the guardrail layer around openpyxl.

Everything that touches a cell goes through here, enforcing:
- mark-to-actual recipe (copy prior actual column's formula pattern, TYPE, format)
- read-back verification of every write
- two-tier flags with methodology notes
- format rollover
- formula-map snapshot + clobber diff
"""
import copy
import json
import re
from pathlib import Path

import openpyxl
from openpyxl.comments import Comment
from openpyxl.styles import PatternFill

AUTHOR = "Model Update Agent"


class WriteError(RuntimeError):
    pass


def load(path, data_only=False):
    return openpyxl.load_workbook(path, data_only=data_only)


def formula_map(wb):
    """{sheet: {coord: value-or-formula-string}} for every populated cell."""
    out = {}
    for ws in wb.worksheets:
        m = {}
        for row in ws.iter_rows():
            for c in row:
                if c.value is not None:
                    m[c.coordinate] = c.value if isinstance(c.value, (int, float)) else str(c.value)
        out[ws.title] = m
    return out


def snapshot_column(wb_values, sheet, col, max_row=400):
    """Cached values of one column (call on a data_only load BEFORE updating)."""
    ws = wb_values[sheet]
    return {r: ws[f"{col}{r}"].value for r in range(1, min(ws.max_row, max_row) + 1)}


def shift_formula(formula, from_col, to_col):
    """Re-point a prior-column formula pattern to the target column (AH7 -> AI7).
    Only unqualified/current-sheet refs to from_col are shifted; absolute $ kept."""
    pat = re.compile(rf"(?<![A-Z$])({from_col})(\$?\d+)")
    return pat.sub(lambda m: to_col + m.group(2), formula)


class Writer:
    def __init__(self, wb, cfg):
        self.wb = wb
        self.red = PatternFill("solid", start_color="FF" + cfg["conventions"]["flag_uncertain_fill"],
                               end_color="FF" + cfg["conventions"]["flag_uncertain_fill"])
        self.orange = PatternFill("solid", start_color="FF" + cfg["conventions"]["flag_backedout_fill"],
                                  end_color="FF" + cfg["conventions"]["flag_backedout_fill"])
        self.log = {"written": [], "flags": [], "restatements": [], "skipped_merged": []}

    def write(self, sheet, coord, value, prior_coord=None, note=None, flag=None):
        """Write one cell per the mark-to-actual recipe, then read it back."""
        ws = self.wb[sheet]
        cell = ws[coord]
        if type(cell).__name__ == "MergedCell":
            self.log["skipped_merged"].append(f"{sheet}!{coord}")
            return False
        cell.value = value
        if prior_coord is not None:  # inherit prior actual column's format
            prior = ws[prior_coord]
            cell._style = copy.copy(prior._style)
            cell.number_format = prior.number_format
        if flag == "red":
            cell.fill = self.red
            self.log["flags"].append(f"{sheet}!{coord}")
        elif flag == "orange":
            cell.fill = self.orange
            self.log["flags"].append(f"{sheet}!{coord}")
        if note:
            cell.comment = Comment(note, AUTHOR)
        got = ws[coord].value  # read-back: never trust write success
        if got != value:
            raise WriteError(f"read-back mismatch {sheet}!{coord}: wrote {value!r} got {got!r}")
        self.log["written"].append(f"{sheet}!{coord}")
        return True

    def restate(self, sheet, coord, new_value, why):
        ws = self.wb[sheet]
        old = ws[coord].value
        ws[coord].value = new_value
        ws[coord].comment = Comment(f"RESTATED: was {old!r}. {why}", AUTHOR)
        self.log["restatements"].append(f"{sheet}!{coord}: {old!r} -> {new_value!r} ({why})")

    def format_rollover(self, sheet, from_col, to_col):
        """Copy formats (only) from the prior actual column onto every populated
        target-column cell, preserving flag fills."""
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


def clobber_diff(pre_map, post_wb, allowed_cols, allowed_cells, skip_sheets=()):
    """Cells changed outside the target column(s) + explicitly allowed cells.
    Non-empty result = formulas were clobbered = delivery must be blocked."""
    post = formula_map(post_wb)
    bad = []
    col_pat = re.compile(rf"^(?:{'|'.join(allowed_cols)})\d+$") if allowed_cols else None
    for sheet, cells in {**pre_map, **{k: {} for k in post}}.items():
        if sheet in skip_sheets:
            continue
        keys = set(pre_map.get(sheet, {})) | set(post.get(sheet, {}))
        for k in keys:
            a, b = pre_map.get(sheet, {}).get(k), post.get(sheet, {}).get(k)
            if a == b:
                continue
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) < 1e-9:
                continue
            if col_pat and col_pat.match(k):
                continue
            if (sheet, k) in allowed_cells:
                continue
            bad.append((sheet, k, a, b))
    return bad


def save(wb, path):
    wb.calculation.fullCalcOnLoad = True  # Excel fully recalcs on open
    wb.save(path)


def dump_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, default=str))
