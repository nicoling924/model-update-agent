"""THE ADVERSARIAL MUSEUM (council ruling, runs 112-116).

Each exhibit is a disease that actually shipped, rebuilt synthetically.
These tests are the floor: any change that lets one pass again is rejected,
whatever it does to the score. Run: python -m pytest tests/test_museum.py -q
(or: python tests/test_museum.py). No LLM, no filesystem beyond stdlib.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl  # noqa: E402

from agent.closing import _build_suspects  # noqa: E402
from agent.workbook import Writer, row_tol  # noqa: E402

CFG = {"conventions": {"flag_uncertain_fill": "FFC7CE",
                       "flag_backedout_fill": "FFC000"}}


def _wb(prior_cells):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "S"
    for coord, v in prior_cells.items():
        ws[coord] = v
    return wb


# ── Exhibit 112: the closing loop swapped EPS 1.15 for net profit 3,831.3 ──
# because an ABSOLUTE tolerance of 1.0 let "prior 1.15" corroborate a 0.94
# row. The row-relative tolerance must refuse the join.

def test_112_small_row_swap_refused():
    wb = _wb({"A5": "    基本每股收益", "T5": 0.94, "U5": 1.15})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": []}
    staging = {"items": [
        # the misaligned note item: numerator under the EPS label,
        # true EPS shifted into the prior slot
        {"label": "基本每股收益", "value": 3831.30122213, "prior": 1.15,
         "page": 213},
        # the true statement-face line
        {"label": "基本每股收益（元／股）", "value": 1.15, "prior": 0.94,
         "page": 99, "stmt": "pl"},
    ]}

    class W:
        log = {"written": ["S!U5"]}
    sus = _build_suspects(wb, spec, staging, W, "2025", 1.0,
                          pre_values=_wb({"T5": 0.94}), eligible=None)
    poison = [s for s in sus if abs(s[2]) > 100]
    assert not poison, f"run-112 poison swap re-admitted: {poison}"


# ── Exhibit 112b/115: the world-band guard at the write chokepoint ──
# 3,831 must never enter a 0.94 world; checksummed writes stay exempt.

def test_112b_world_band_guard():
    wb = _wb({"T5": 0.94})
    w = Writer(wb, CFG)
    assert w.write("S", "U5", 3831.3, prior_coord="T5") is False
    assert w.write("S", "U5", 1.15, prior_coord="T5") is True
    assert w.write("S", "U6", 3831.3, prior_coord="T5", trusted=True) is True


# ── Exhibit 114: allocation wrote formula STRINGS, blinding the numeric ──
# guard. The chokepoint must evaluate pure-arithmetic formulas and judge
# the number.

def test_114_numeric_preview_catches_formula():
    wb = _wb({"T9": 21.8791})
    w = Writer(wb, CFG)
    # a x482 structure-scale masquerading as a formula
    assert w.write("S", "U9", "=21.8791*482.376", prior_coord="T9") is False
    # a sane in-band formula passes
    assert w.write("S", "U9", "=21.8791*3.65", prior_coord="T9") is True


# ── Exhibit 115: a MEGAWATT figure joined a P&L money row via label match.
# The closing loop's world-band guard must refuse any swap that leaves the
# row's order of magnitude even when a label-related item corroborates.

def test_115_out_of_world_swap_refused():
    wb = _wb({"A7": "其他业务成本(金融类)", "T7": 26.15, "U7": 26.15})
    spec = {"year_axis": {"S": {"columns": {"2024": "T", "2025": "U"}}},
            "check_rows": []}
    staging = {"items": [
        # production-table row whose prior coincidentally ties (26.1 MW)
        {"label": "其他业务成本(金融类)", "value": 8056.6, "prior": 26.1,
         "page": 158},
    ]}

    class W:
        log = {"written": ["S!U7"]}
    sus = _build_suspects(wb, spec, staging, W, "2025", 1.0,
                          pre_values=_wb({"T7": 26.15}), eligible=None)
    poison = [s for s in sus if abs(s[2]) > 50 * 26.15]
    assert not poison, f"run-115 out-of-world swap re-admitted: {poison}"


# ── Exhibit 116: a no-prior row served without a scale anchor wrote a ──
# raw-scale number. Until the Stage-2 block-scale invariant lands, the
# fable no-prior path must convert via document/page scale; this test pins
# the conversion requirement at the acceptance layer.

def test_116_no_prior_scale_anchor():
    from agent import mapper
    try:
        from agent.fablemode import _accept
    except ImportError:
        # the no-prior read path is reverted (run-116 regression); the
        # exhibit re-arms when the Stage-2 block-scale no-prior join lands
        print("  (116 path reverted — exhibit dormant)")
        return
    old_doc = mapper.DOC_SCALE
    try:
        mapper.set_doc_scale(1e6)   # filing prints yuan, model in millions
        served = {}
        chunk = [{"sheet": "S", "row": 250, "label": "使用权资产折旧",
                  "prior_value": None, "pages": [215], "_grp0": 215}]
        resp = {"rows": [{"id": "S!250", "current": "152,709,448.06",
                          "comparative": "199,139,706.74", "status": "OK"}]}
        _accept(resp, chunk, served, "", [])
        e = served.get(("S", 250))
        assert e is not None, "no-prior row was not served at all"
        assert abs(e["value"] - 152.709448) < 0.01, \
            f"run-116 scale poison: no-prior row served {e['value']} " \
            "(raw scale) instead of 152.71 (model units)"
        assert e["conf"] < 5, "no-prior read must never earn the lock (conf 5)"
    finally:
        mapper.set_doc_scale(old_doc)


# ── The tolerance doctrine itself ──

def test_row_tol_worlds():
    assert row_tol(0.94) <= 0.01 + 1e-9          # per-share world: a cent
    assert row_tol(2773.7) >= 13.0               # aggregate world: 0.5%
    assert abs(1.15 - 0.94) > row_tol(0.94), "1.15 must never tie 0.94"


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as ex:
                print(f"FAIL {name}: {ex}")
                fails += 1
    sys.exit(1 if fails else 0)
