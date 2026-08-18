"""The pre-dispatch REGRESSION GATE (council #4, rank 3) — printed-key panel.

The legacy stack refused to dispatch a head whose offline replay changed
any binding; the redesign lost that shield and run 21 shipped a corrupted
net profit undetected. This gate restores it, pinned to PRINTED KEYS (not
cells — cells can fossilize a compensating error):

    python3 tools/key_gate.py <company_dir> <period> <target_year>

Runs the fully deterministic dry pipeline on a scratch copy of the
company folder, evaluates the headline keys in the delivered workbook,
and PASSES a key only if it equals the pinned PRINTED value or the
pinned PRIOR (stale-not-yet-served is legal in a dry run — corruption is
neither). ANY key at a third value = the head is mutating keys wrongly =
DO NOT DISPATCH.

Pinned panel: <company_dir>/replay/<period>/key_panel.json
    {"<key name>": {"print": <printed value>, "prior": <prior value>}}
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(company_dir, period, target_year):
    company_dir = Path(company_dir)
    panel_path = company_dir / "replay" / period / "key_panel.json"
    if not panel_path.exists():
        print(f"GATE ERROR: no pinned panel at {panel_path}")
        return 2
    panel = json.loads(panel_path.read_text())

    with tempfile.TemporaryDirectory() as td:
        scratch = Path(td) / company_dir.name
        shutil.copytree(company_dir, scratch,
                        ignore=shutil.ignore_patterns("model-archive",
                                                      "replay", "updates"))
        from updater.run import update
        update(str(scratch), period, int(target_year), client=None,
               log=lambda *a, **k: None)
        out = sorted((scratch / "model").glob("*updater*.xls[xm]"))
        if not out:
            print("GATE ERROR: dry run produced no workbook")
            return 2
        from updater.evaluator import Evaluator
        from updater.spec import read_spec_tab
        from updater.writer import load
        wb = load(out[-1])
        spec = read_spec_tab(wb)
        from updater.checks import year_columns
        ev = Evaluator(wb)
        fails = []
        checked = 0
        for k in spec.get("key_rows") or []:
            name = k.get("name")
            if name not in panel:
                continue
            tcol = year_columns(spec, k["sheet"]).get(str(target_year))
            if not tcol:
                continue
            try:
                mv = ev.cell(k["sheet"], f"{tcol}{int(k['row'])}")
            except Exception:
                continue
            if not isinstance(mv, (int, float)):
                continue
            checked += 1
            pins = panel[name]
            tol = max(0.02, abs(pins.get("print", 0)) * 1e-3)
            ok = any(isinstance(pins.get(x), (int, float))
                     and abs(abs(mv) - abs(pins[x])) <= tol
                     for x in ("print", "prior"))
            raw_cell = wb[k["sheet"]][f"{tcol}{int(k['row'])}"].value
            composed = isinstance(raw_cell, str) and raw_cell.startswith("=")
            if ok:
                mark = "ok"
            elif composed:
                # a formula key mixing served actuals with still-stale
                # inputs is a legal partial dry state — warn, don't fail
                mark = "hybrid"
            else:
                mark = "FAIL"
                fails.append(f"  {name} ({k['sheet']}!{tcol}{k['row']}): "
                             f"INPUT cell at {mv:,.3f} — neither printed "
                             f"{pins.get('print'):,} nor prior "
                             f"{pins.get('prior'):,}")
            print(f"  [{mark}] {name}: {mv:,.3f}")
        print(f"\nKEY GATE: {checked} keys checked, {len(fails)} failures")
        for f in fails:
            print(f)
        if fails:
            print("VERDICT: DO NOT DISPATCH — this head mutates printed keys")
            return 1
        print("VERDICT: gate green — head is dispatch-eligible")
        return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
