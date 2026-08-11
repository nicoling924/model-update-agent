"""Cold-start anatomy discovery: workbook -> draft spec.yaml (analyst reviews it).

Generic across industries and layouts: nothing here assumes a sector — the LLM
reads the workbook's own structure (labels, formulas, year headers) and proposes
the anatomy, with a cell citation for every claim and nulls where unsure.
"""
import json
from pathlib import Path

import yaml

from . import workbook


def structural_dump(wb, max_rows=250, sample_cols=14):
    """Compact, generic view of each sheet: labels + a sample of values/formulas."""
    dump = {}
    for ws in wb.worksheets:
        rows = []
        for r in range(1, min(ws.max_row, max_rows) + 1):
            cells = {}
            for c in ws.iter_rows(min_row=r, max_row=r, max_col=min(ws.max_column, 60)):
                for cell in c:
                    if cell.value is not None and len(cells) < sample_cols:
                        v = cell.value
                        cells[cell.coordinate] = v if isinstance(v, (int, float)) else str(v)[:80]
            if cells:
                rows.append(cells)
        dump[ws.title] = {"max_row": ws.max_row, "max_col": ws.max_column, "rows": rows[:max_rows]}
    return dump


def discover(client, system, discover_prompt, company_dir, model_path, cfg):
    wb = workbook.load(model_path)
    dump = structural_dump(wb)
    user = (f"{discover_prompt}\n\nWorkbook structural dump (truncated):\n"
            f"{json.dumps(dump)[:350000]}\n\n"
            "Return JSON with keys: sheets, year_axis, statement_rows, check_rows, "
            "input_vs_formula, roll_forward_bases, calc_mode, quirks, draft.")

    def validate(obj):
        errs = []
        for k in ("sheets", "year_axis", "statement_rows", "check_rows"):
            if k not in obj:
                errs.append(f"missing {k}")
        for sheet, ax in (obj.get("year_axis") or {}).items():
            if sheet not in wb.sheetnames:
                errs.append(f"year_axis names unknown sheet {sheet}")
            elif not (ax.get("columns") or {}):
                errs.append(f"year_axis[{sheet}] has no columns")
        for c in obj.get("check_rows", []):
            if c.get("sheet") not in wb.sheetnames:
                errs.append(f"check_row names unknown sheet {c.get('sheet')}")
        return errs

    obj = client.json(system, user, validate, repair_retries=cfg["budgets"]["json_repair_retries"])
    obj["draft"] = True
    obj["model_file"] = Path(model_path).name
    # deterministic facts read from the file, not the LLM
    obj["calc_mode"] = wb.calculation.calcMode
    spec_path = Path(company_dir) / "spec.yaml"
    existing = {}
    if spec_path.exists():
        existing = yaml.safe_load(spec_path.read_text()) or {}
    for keep in ("aliases", "backout_rules", "analyst_rulings", "carried_flags", "tie_out_anchors"):
        obj.setdefault(keep, existing.get(keep) or [])
    spec_path.write_text(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True))
    return spec_path
