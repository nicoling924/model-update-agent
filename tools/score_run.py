import sys, yaml
sys.path.insert(0, "/Users/lingling/Project M/model-update-agent")
from pathlib import Path
from agent import workbook
from agent.evaluator import Evaluator

GT = Path("/Users/lingling/Project M/companies/CLP Holdings/model/CLP Model FY25 (Updated).xlsx")
CAND = Path(sys.argv[1])
spec = yaml.safe_load(Path("/Users/lingling/Project M/model-update-agent/companies/CLP/spec.yaml").read_text())

gt_wb, ca_wb = workbook.load(GT), workbook.load(CAND)
gt_ev, ca_ev = Evaluator(gt_wb), Evaluator(ca_wb)
FLAGS = {"FFC7CE", "00FFC7CE", "FFC000", "00FFC000", "FFFFC7CE", "FFFFC000"}
total = correct = wrong_fl = wrong_unfl = 0
worst = []
for sheet, ax in spec["year_axis"].items():
    col = ax["columns"].get("2025")
    if not col or sheet not in gt_wb.sheetnames or sheet not in ca_wb.sheetnames:
        continue
    for r in range(1, 401):
        if r == ax.get("header_row", 1):
            continue
        try:
            gv = gt_ev.cell(sheet, f"{col}{r}")
        except Exception:
            continue
        if not isinstance(gv, (int, float)) or (gt_wb[sheet][f"{col}{r}"].value is None):
            continue
        total += 1
        try:
            cv = ca_ev.cell(sheet, f"{col}{r}")
        except Exception:
            cv = None
        tol = max(1.0, abs(gv) * 0.005)
        ok = isinstance(cv, (int, float)) and abs(cv - gv) <= tol
        cell = ca_wb[sheet][f"{col}{r}"]
        fill = str(cell.fill.fgColor.rgb) if cell.fill and cell.fill.patternType and cell.fill.fgColor else ""
        flagged = fill in FLAGS
        if ok:
            correct += 1
        else:
            (worst.append((abs((cv or 0) - gv), f"{sheet}!{col}{r}", gv, cv, flagged)))
            if flagged: wrong_fl += 1
            else: wrong_unfl += 1
print(f"cells={total} correct={correct} ({correct/total*100:.1f}%) "
      f"wrong_flagged={wrong_fl} wrong_unflagged={wrong_unfl}")
for d, ref, gv, cv, fl in sorted(worst, reverse=True)[:15]:
    print(f"  {ref}: gt={gv:,.1f} got={cv if cv is None else format(cv, ',.1f')} {'[flagged]' if fl else '[UNFLAGGED]'}")
