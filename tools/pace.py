"""THE PACE TEST (owner 2026-09-17, before any live run).

Can the mapping loop mark a model inside its budget? This drives the real
pipeline on a pinned ledger with a SYNTHETIC brain: each turn it reads the
context exactly as the brain would, takes the leads it is shown (the printed
line whose comparative ties the row's prior) and answers with one `sets` batch.
It measures what code costs (the context, the gate, the writes) and adds a
stated think-time per turn, so the answer is honest about which half is which.

  python3 tools/pace.py <company_dir> <PERIOD> <YEAR> <artifact_dir> [batch] [think_s]

It writes no live call and needs no brain.
"""
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_SKIP_SCOPE = (os.environ.get("PACE_SKIP_SCOPE") or "disclosure").strip().lower()
_ROW = re.compile(r"^\s{2}([^\s!]+(?: [^\s!]+)*)!([A-Z]{1,3}\d+)\s")
_LEAD = re.compile(r"lead: p(\d+) '(.+?)' → this year ([-\d,\.]+)")


def _turn_from_context(user, batch):
    """What a brain with no judgment would do: take every lead it is shown."""
    sets, sheet_of, cur = [], None, None
    for line in user.splitlines():
        m = _ROW.match(line)
        if m and "|" in line:
            cur = f"{m.group(1)}!{m.group(2)}"
            sheet_of = "unfilled" in line
            continue
        if not cur or not sheet_of:
            continue
        lm = _LEAD.search(line)
        if lm:
            nums = re.findall(r"[-+]?\d[\d,]*\.?\d*", lm.group(2))
            if nums:
                sets.append({"ref": cur, "printed": float(nums[0].replace(",", "")),
                             "page": int(lm.group(1)), "line": lm.group(2),
                             "because": "the lead's own line"})
            cur = None
            if len(sets) >= batch:
                break
    if not sets:
        # nothing left that a lead can answer: say so row by row, as the brain
        # must — an unmapped row is a judgment with a reason, never a silence.
        # THIS BRAIN'S REASON IS ABOUT THE WHOLE DISCLOSURE ("no printed line ON
        # FILE carries this row's prior"), so its skip carries that scope: a
        # bare skip is about the page it was shown, and this brain was never
        # reading one. PACE_SKIP_SCOPE=page drives the other path instead — the
        # row comes back against a print it has not refused, and a brain that
        # only refuses is ended by the stuck guard.
        skips = []
        for line in user.splitlines():
            m = _ROW.match(line)
            if m and "unfilled" in line:
                skips.append({"tool": "skip", "ref": f"{m.group(1)}!{m.group(2)}",
                              "because": "no printed line on file carries this row's prior"})
                if _SKIP_SCOPE != "page":
                    skips[-1]["scope"] = _SKIP_SCOPE
            if len(skips) >= batch * 4:
                break
        if skips:
            return {"thinking": f"{len(skips)} rows I cannot map from this disclosure", "calls": skips}
        return {"thinking": "every row is filled or skipped", "calls": [{"tool": "done"}]}
    return {"thinking": f"marking {len(sets)} rows of this face", "calls": [{"tool": "sets", "sets": sets}]}


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    company, period, year, art = argv[0], argv[1], int(argv[2]), Path(argv[3])
    batch = int(argv[4]) if len(argv) > 4 else 30
    think_s = float(argv[5]) if len(argv) > 5 else 20.0
    state = {"turns": 0, "code_s": 0.0, "t_last": time.monotonic(), "said": []}

    def maps(system, user):
        state["code_s"] += time.monotonic() - state["t_last"]
        state["turns"] += 1
        reply = _turn_from_context(user, batch)
        state["t_last"] = time.monotonic()
        return reply
    answerer = (lambda *a, **k: None)
    answerer.maps = maps
    answerer.reviews = None
    from pipeline.run import update
    t0 = time.monotonic()
    _res = update(company, period, year, client=None, stage4_answerer=answerer,
                 pinned_ledger=str(art / "replay" / period / "ledger.json"),
                 pinned_served=str(art / "replay" / period / "provenance.json"),
                 log=(lambda *a: [state["said"].append(str(x)) for x in a]))
    wall = time.monotonic() - t0
    summary = [ln for ln in state["said"] if ln.startswith("[map] mapping:")]
    print("\n".join(summary) or "(no mapping line in the log)")
    head = summary[0] if summary else ""
    filled = int(re.search(r"(\d+) plain", head).group(1)) if re.search(r"(\d+) plain", head) else 0
    red = int(re.search(r"(\d+) red", head).group(1)) if re.search(r"(\d+) red", head) else 0
    skipped = int(re.search(r"(\d+) skipped", head).group(1)) if re.search(r"(\d+) skipped", head) else 0
    rows = int(re.search(r"of (\d+) input rows", head).group(1)) if re.search(r"of (\d+) input rows", head) else 0
    sim_min = (state["code_s"] + state["turns"] * think_s) / 60.0
    print(f"turns {state['turns']} | code {state['code_s']:.0f}s | think {think_s:.0f}s/turn assumed "
          f"| simulated mapping time {sim_min:.1f} min | whole run wall {wall/60:.1f} min")
    print(f"PACE: {rows} input rows resolved in {sim_min:.1f} simulated minutes "
          f"({(rows / sim_min if sim_min else 0):.0f} rows/min): {filled} plain, {red} red, {skipped} skipped "
          f"with a reason — the bar is 257 cells inside 36 min.")
    print("NOTE: this brain has no judgment — it takes every lead it is shown and skips every row that has "
          "none. The PLAIN count is what leads alone can answer; the pace is what the loop costs.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
