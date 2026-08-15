"""Score a run's workbook against a reference model, cell by cell.

    python tools/score_run.py "<run>/model/CLP Model.xlsx"
    python tools/score_run.py "<run>/model/DFE Model.xlsx" --company DFE

Both models are evaluated (formulas computed), so a formula cell is judged on
its VALUE — the analyst's number is what matters, not how it was written.

ADJUDICATION. A reference that is itself an agent's output cannot simply be
declared right. With --docs, every disagreement is put to the filing: does the
document print the candidate's number, the reference's, both, or neither? That
converts an opinion into evidence, and it is the only honest way to score DFE,
whose reference (Dongfang Electric Claude Fable 5.xlsx) is a prior agent run,
not an analyst-verified model.
"""
import argparse
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from agent import workbook, mapper  # noqa: E402
from agent.evaluator import Evaluator  # noqa: E402
from agent import lookup as L  # noqa: E402

PROJECT = REPO.parent
REFS = {
    "CLP": PROJECT / "companies/CLP Holdings/model/CLP Model FY25 (Updated).xlsx",
    "DFE": PROJECT / "companies/Dongfang Electric/model/Dongfang Electric Claude Fable 5.xlsx",
}
# CLP's reference is the analyst's finished model; DFE's is a prior agent run.
TRUSTED = {"CLP"}
FLAGS = {"FFC7CE", "00FFC7CE", "FFC000", "00FFC000", "FFFFC7CE", "FFFFC000"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--company", default="CLP")
    ap.add_argument("--ref", default=None)
    ap.add_argument("--year", default="2025")
    ap.add_argument("--docs", default=None,
                    help="disclosure dir; disagreements are put to the filing")
    a = ap.parse_args()

    ref_path = Path(a.ref) if a.ref else REFS[a.company]
    spec = yaml.safe_load((REPO / "companies" / a.company / "spec.yaml").read_text())
    gt_wb, ca_wb = workbook.load(ref_path), workbook.load(Path(a.candidate))
    gt_ev, ca_ev = Evaluator(gt_wb), Evaluator(ca_wb)

    raw = []
    if a.docs:
        raw = L.raw_lines(sorted(Path(a.docs).glob("*.pdf")))

    total = correct = wrong_fl = wrong_unfl = 0
    worst, rows_seen = [], []
    for sheet, ax in spec["year_axis"].items():
        col = (ax.get("columns") or {}).get(a.year)
        if not col or sheet not in gt_wb.sheetnames or sheet not in ca_wb.sheetnames:
            continue
        for r in range(1, 401):
            if r == ax.get("header_row", 1):
                continue
            try:
                gv = gt_ev.cell(sheet, f"{col}{r}")
            except Exception:
                continue
            if not isinstance(gv, (int, float)) or gt_wb[sheet][f"{col}{r}"].value is None:
                continue
            total += 1
            rows_seen.append((sheet, r, gv))
            try:
                cv = ca_ev.cell(sheet, f"{col}{r}")
            except Exception:
                cv = None
            tol = max(1.0, abs(gv) * 0.005)
            ok = isinstance(cv, (int, float)) and abs(cv - gv) <= tol
            cell = ca_wb[sheet][f"{col}{r}"]
            fill = (str(cell.fill.fgColor.rgb)
                    if cell.fill and cell.fill.patternType and cell.fill.fgColor else "")
            flagged = fill in FLAGS
            if ok:
                correct += 1
            else:
                worst.append((abs((cv or 0) - gv), f"{sheet}!{col}{r}", gv, cv, flagged))
                if flagged:
                    wrong_fl += 1
                else:
                    wrong_unfl += 1

    if not total:
        sys.exit(f"no comparable cells in the {a.year} column — check --year/spec")
    print(f"reference: {ref_path.name}"
          f"{'' if a.company in TRUSTED else '  [prior agent run — not analyst-verified]'}")
    print(f"cells={total} correct={correct} ({correct / total * 100:.1f}%) "
          f"wrong_flagged={wrong_fl} wrong_unflagged={wrong_unfl}")

    if raw:
        mapper.set_doc_scale(mapper.detect_scale([g for _s, _r, g in rows_seen], raw))
        print(f"\nadjudicating disagreements against the filing "
              f"(doc scale {mapper.DOC_SCALE:,.0f}x):")
        tally = {"candidate": 0, "reference": 0, "both": 0, "neither": 0}
        for d, ref, gv, cv, fl in sorted(worst, reverse=True):
            in_doc_gt = any(mapper.line_has_value(ln, gv) for _p, _s, ln in raw)
            in_doc_cv = (isinstance(cv, (int, float))
                         and any(mapper.line_has_value(ln, cv) for _p, _s, ln in raw))
            verdict = ("both" if in_doc_gt and in_doc_cv else
                       "candidate" if in_doc_cv else
                       "reference" if in_doc_gt else "neither")
            tally[verdict] += 1
            if len(worst) <= 40 or verdict in ("candidate", "both"):
                print(f"  {ref}: ref={gv:,.1f} got="
                      f"{cv if cv is None else format(cv, ',.1f')} "
                      f"{'[flagged]' if fl else '[UNFLAGGED]'} -> filing supports {verdict}")
        print(f"\n  filing supports: candidate {tally['candidate']}, "
              f"reference {tally['reference']}, both {tally['both']}, "
              f"neither {tally['neither']}")
        print("  (\"candidate\" = the run is right and the reference is wrong; "
              "\"neither\" = a computed subtotal, judge by its components)")
    else:
        for d, ref, gv, cv, fl in sorted(worst, reverse=True)[:15]:
            print(f"  {ref}: ref={gv:,.1f} got="
                  f"{cv if cv is None else format(cv, ',.1f')} "
                  f"{'[flagged]' if fl else '[UNFLAGGED]'}")


if __name__ == "__main__":
    main()
