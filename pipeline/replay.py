"""Offline replay — the pre-flight gate that would have caught runs 112-116.

Runs Stage 2 entirely from pinned JSON snapshots (a committed evidence
ledger + target census) in seconds: no vision, no LLM, no workbook. The
contract, from the council's validation protocol:

    A change to join logic is a REGRESSION if it changes any previously
    accepted binding, whatever it does to the fill count. Diff the
    bindings, never a score — scores hide single-cell poison.

Usage:
    python -m pipeline.replay LEDGER.json TARGETS.json
        [--baseline BASELINE.json]        # diff against the committed baseline
        [--write-baseline BASELINE.json]  # pin the current bindings

Exit codes: 0 = clean (or baseline written), 1 = bindings changed vs
baseline (release blocker), 2 = usage/load error.
"""
import json
import sys
from pathlib import Path

from .ledger import Ledger
from . import targets as targets_mod
from .stage2_join import join


def bindings_of(served):
    """The diffable fingerprint: cell -> (value, source line, page)."""
    return {f"{sh}!{rw}": {"value": round(e["value"], 2),
                           "line": e["line"], "doc": e["doc"], "page": e["page"]}
            for (sh, rw), e in served.items()}


def diff_bindings(old, new):
    """(added, removed, changed) between two binding maps."""
    added = sorted(k for k in new if k not in old)
    removed = sorted(k for k in old if k not in new)
    changed = sorted(k for k in new if k in old and new[k] != old[k])
    return added, removed, changed


def replay(ledger_path, targets_path, baseline_path=None, write_baseline=None,
           out=print):
    led = Ledger.load(ledger_path)
    targets = targets_mod.load(targets_path)
    log = []
    served, decisions = join(led, targets, log)
    for ln in log:
        out(ln)
    by_status = {}
    for d in decisions:
        by_status[d.status] = by_status.get(d.status, 0) + 1
    out(f"replay: {len(targets)} targets, {len(led.items)} ledger items -> "
        + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
    bindings = bindings_of(served)

    if write_baseline:
        Path(write_baseline).parent.mkdir(parents=True, exist_ok=True)
        Path(write_baseline).write_text(
            json.dumps({"version": 1, "bindings": bindings},
                       ensure_ascii=False, indent=1, sort_keys=True),
            encoding="utf-8")
        out(f"baseline pinned: {len(bindings)} bindings -> {write_baseline}")
        return 0

    if baseline_path:
        base = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
        added, removed, changed = diff_bindings(base.get("bindings") or {},
                                                bindings)
        out(f"vs baseline: +{len(added)} added, -{len(removed)} removed, "
            f"~{len(changed)} changed")
        for k in changed:
            out(f"  CHANGED {k}: {base['bindings'][k]} -> {bindings[k]}")
        for k in removed:
            out(f"  REMOVED {k}: {base['bindings'][k]}")
        for k in added:
            out(f"  added   {k}: {bindings[k]}")
        if removed or changed:
            out("RELEASE BLOCKER: previously accepted bindings changed — "
                "a fill-rate gain does not excuse this")
            return 1
    return 0


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    opts = {a.split("=", 1)[0]: (a.split("=", 1) + [""])[1]
            for a in argv if a.startswith("--")}
    if len(args) != 2:
        print(__doc__)
        return 2
    try:
        return replay(args[0], args[1],
                      baseline_path=opts.get("--baseline") or None,
                      write_baseline=opts.get("--write-baseline") or None)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"replay: cannot load snapshots: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
