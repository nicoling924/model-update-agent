"""The canonical run-artifact loader — diagnostics must see what the run saw.

Two measured diagnostic disasters (2026-08-18) came from ad-hoc
reconstruction of run state:
- VINTAGE BLINDNESS: re-loaded ledgers had no doc-period classification,
  so prior-year documents looked citable and phantom "poisoned" findings
  were reported to the owner.
- PRIORLESS CENSUS: building targets from the DELIVERED workbook (openpyxl
  formulas carry no cached values) yielded prior_value=None everywhere,
  so the evidence oracle proved nothing and phantom "unverified keys"
  were reported to the owner.

Rule: every offline analysis of a run loads through HERE, nothing else.
"""
from pathlib import Path

from . import targets as targets_mod
from .ledger import Ledger
from .spec import read_spec_tab
from .writer import load


def load_run(artifact_dir, period="FY25", target_year=2025):
    """-> dict(wb, spec, targets, ledger) — the run's exact view.

    - wb: the DELIVERED workbook (openpyxl, formulas).
    - targets: census from the ARCHIVED PRE-UPDATE model (Excel-cached
      values — exactly what the run's census read).
    - ledger: replay snapshot with vintage restored (serialized since the
      run-19 fix) or re-derived from the census when absent.
    """
    a = Path(artifact_dir)
    out_wb = next(iter(sorted((a / "model").glob("*updater*.xls[xm]"))), None)
    if out_wb is None:
        raise FileNotFoundError(f"no delivered workbook under {a}/model")
    wb = load(out_wb)
    spec = read_spec_tab(wb)

    pre = sorted((a / "model-archive").glob(f"*_{period}_pre.xls[xm]"))
    if not pre:
        raise FileNotFoundError(
            f"no archived pre-update model under {a}/model-archive — the "
            "census cannot be reconstructed faithfully without it")
    wb_pre_values = load(pre[-1], data_only=True)
    wb_pre = load(pre[-1])
    targets = list(targets_mod.from_workbook(wb_pre_values, spec,
                                             target_year,
                                             wb_formulas=wb_pre))

    ledger = Ledger.load(a / "replay" / period / "ledger.json")
    if getattr(ledger, "_doc_periods", None) is None:
        priors = [t.prior_value for t in targets
                  if isinstance(t.prior_value, (int, float))]
        deep = [t.prior2_value for t in targets
                if isinstance(getattr(t, "prior2_value", None),
                              (int, float))]
        ledger.ensure_vintage(priors, deep, log=lambda s: None)
    return {"wb": wb, "spec": spec, "targets": targets, "ledger": ledger}
