"""THE LIVE PACE TEST (owner 2026-09-17: "a 15-min test of sorts, so the time cost is lower").

Runs the v3 mapping loop with the REAL brain on a pinned extraction (no PDF
reading), with the run's clock set to N minutes instead of 60. It answers two
questions before any full run: how many seconds a brain turn costs, and how
many rows the loop maps in the minutes it is given.

  python3 tools/pace_live.py <company_dir> <PERIOD> <YEAR> <artifact_dir> [minutes]

Prints the mapping summary, the per-turn cost, and copies the delivered model to
drytest_out/ for scoring.
"""
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    company, period, year, art = argv[0], argv[1], int(argv[2]), Path(argv[3])
    minutes = float(argv[4]) if len(argv) > 4 else 15.0
    import pipeline.run as R
    R.RUN_TARGET_S = minutes * 60
    R.review_budget_s.__defaults__ = (R.RUN_TARGET_S, R.FINISH_MARGIN_S)
    from pipeline.llm import make_client, handshake
    client = make_client()
    print(f"brain handshake: {handshake(client)}")
    calls = []                      # (stage, seconds, chars_in, chars_out)
    stage = {"name": "pre"}
    _json = client.json

    def timed_json(system, user, *a, **k):
        t = time.monotonic()
        out = _json(system, user, *a, **k)
        calls.append((stage["name"], time.monotonic() - t, len(system or "") + len(user or ""),
                      len(str(out))))
        return out
    client.json = timed_json
    said = []

    def log(*a):
        line = " ".join(str(x) for x in a)
        said.append(line)
        if line.startswith("[map] routing"):
            stage["name"] = "routing"          # the brain saying which page each open row is read against
        elif (line.startswith("[map] the face round") or "[map] face" in line
              or "face(s) to map" in line):     # the face round starts here, after the routing batches
            stage["name"] = "faces"
        elif line.startswith("[map] turn") and stage["name"] != "sequential":
            stage["name"] = ("sequential" if stage["name"] in ("faces", "routing")
                             or "the face round took" in "\n".join(said[-3:]) else stage["name"])
        elif line.startswith("[review]"):
            stage["name"] = "review"
        elif line.startswith("[anatomy]"):
            stage["name"] = "anatomy"
        print(line, flush=True)
    t0 = time.monotonic()
    res = R.update(company, period, year, client=client,
                   pinned_ledger=str(art / "replay" / period / "ledger.json"),
                   pinned_served=str(art / "replay" / period / "provenance.json"),
                   log=log)
    wall = time.monotonic() - t0
    print("\n===== PACE (live brain) =====")
    for ln in said:
        if ln.startswith(("[map] mapping:", "[map] the face round", "[run] budget", "[run] key count",
                          "[run] executive report coverage", "[review] ended", "[run] DELIVERED")):
            print(ln)
    by = {}
    for st, s, ci, co in calls:
        d = by.setdefault(st, [0, 0.0, 0, 0]); d[0] += 1; d[1] += s; d[2] += ci; d[3] += co
    print(f"wall {wall/60:.1f} min for a {minutes:.0f}-min clock · brain calls {len(calls)} · "
          f"brain time {sum(c[1] for c in calls)/60:.1f} min")
    for st, (n, s, ci, co) in by.items():
        print(f"  {st:11} {n:4} calls · {s/n:5.1f} s/call · {ci//max(n,1):7} chars in/call · {co//max(n,1):6} chars out/call")
    head = next((ln for ln in said if ln.startswith("[map] mapping:")), "")
    m = re.search(r"of (\d+) input rows", head)
    if m:
        rows = int(m.group(1))
        map_s = sum(c[1] for c in calls if c[0] in ("faces", "routing", "sequential")) or 1
        print(f"rows/min of brain time in the mapping: {rows / (map_s/60):.1f}")
    out = Path("drytest_out"); out.mkdir(exist_ok=True)
    for p in Path(company).glob("model/*pipeline*.xlsx"):
        shutil.copy(p, out / p.name); print(f"copied {p} -> {out / p.name}")
    for p in (Path(company) / "replay").rglob("*.json"):
        dst = out / "replay" / p.relative_to(Path(company) / "replay"); dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(p, dst)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
