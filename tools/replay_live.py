"""THE FAITHFUL REPLAY (owner discipline 2026-09-02: a live failure is
never debugged by re-dispatching — it is reproduced offline first).

Rebuilds a live run's state on this machine from its own artifact:
  - the live evidence ledger (stage 1, vision included)
  - the live provenance serves (stage 2 + the LLM's stage-3 gap reads)
  - the live card answers, replayed in order from the Actions log
and runs the same pipeline with no LLM. When the offline gate reproduces
the live verdict, every diagnostic tool works on the exact live state.

Usage:
  python tools/replay_live.py <company_dir> <PERIOD> <YEAR> <artifact_dir> [actions_log]

  artifact_dir: the unzipped run artifact (holds replay/<PERIOD>/ledger.json
                and provenance.json)
  actions_log : the run's 0_update.txt (for the [queue] card answers);
                optional — without it every card defaults (the floor)
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def picks_from_log(path):
    picks = {}
    if not path:
        return picks
    pat = re.compile(r"\[queue\] (SERVE|COMPONENT|TRIPWIRE|PLUG) (\S+) -> "
                     r"(serve:[A-D]|fix:\d|plug:\d|error_fixed|justified|"
                     r"suspicious|refuse_flag|not_disclosed)")
    for ln in Path(path).read_text(errors="ignore").splitlines():
        m = pat.search(ln)
        if m:
            picks.setdefault((m.group(1), m.group(2)), []).append(m.group(3))
    return picks


def make_answerer(picks):
    def _norm(ref):
        return re.sub(r"!([A-Z]{1,3})(\d+)$", r"!\2", ref)

    def answer(text, options, default):
        head = text.splitlines()[0]
        mm = re.match(r"CARD (SERVE|COMPONENT|PLUG|TRIPWIRE)\s+(?:check\s+)?(\S+)",
                      head)
        if not mm:
            return default
        kind, ref = mm.group(1), mm.group(2)
        for key in ((kind, _norm(ref)), (kind, ref)):
            if key in picks and picks[key]:
                c = picks[key].pop(0)
                return c if c in options else default
        if kind == "TRIPWIRE":
            for key in list(picks):
                if key[0] == "TRIPWIRE" and picks[key]:
                    c = picks[key].pop(0)
                    return c if c in options else default
        return default
    return answer


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    company, period, year, art = argv[0], argv[1], int(argv[2]), Path(argv[3])
    log_path = argv[4] if len(argv) > 4 else None
    from pipeline.run import update
    res = update(company, period, year, client=None, stage4_mode="queue-only",
                 stage4_answerer=make_answerer(picks_from_log(log_path)),
                 pinned_ledger=str(art / "replay" / period / "ledger.json"),
                 pinned_served=str(art / "replay" / period / "provenance.json"),
                 log=print)
    print(f"\nFAITHFUL REPLAY -> {'DELIVERED' if res['ok'] else 'GATE REFUSED'}: "
          f"{res['out']}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
