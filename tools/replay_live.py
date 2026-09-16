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
  --live-shape: a client is PRESENT but answers nothing (run 34925710395:
                OpenRouter 402 four minutes in). Every branch keyed on a
                live brain runs — the key tie proposes instead of
                absorbing, the ending deals key cards, the reader and the
                name judgment fail the way they fail live — so the live
                path is exercised offline, never only in the hour.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def reviews_from_log(path):
    """The review's own turns, recorded verbatim by the loop ('[review] turn N
    reply {json}') and replayed in order — a floor must be able to drive the
    review exactly as the live run did."""
    out = []
    if not path:
        return out
    import json
    for ln in Path(path).read_text(errors="ignore").splitlines():
        m = re.search(r"\[review\] turn \d+ reply (\{.*)$", ln)
        if not m:
            continue
        try:
            out.append(json.loads(m.group(1)))
        except ValueError as e:
            print(f"[replay] a recorded review turn is not readable JSON and is NOT replayed: {e}")
    return out


def maps_from_log(path):
    """The mapping's own turns, recorded verbatim by the loop ('[map] turn N
    reply {json}') and replayed in order — a floor drives the mapping exactly
    as the live run did. Empty until a live run has recorded some: a floor with
    no mapping turns tests extraction and the ending only, and says so."""
    out = []
    if not path:
        return out
    import json
    for ln in Path(path).read_text(errors="ignore").splitlines():
        m = re.search(r"\[map\] turn \d+ reply (\{.*)$", ln)
        if not m:
            continue
        try:
            out.append(json.loads(m.group(1)))
        except ValueError as e:
            print(f"[replay] a recorded mapping turn is not readable JSON and is NOT replayed: {e}")
    return out


def picks_from_log(path):
    picks = {}
    if not path:
        return picks
    # sheet names may carry spaces ('SOC Accounts!7') — match lazily to ' -> ';
    # every card kind and every answer token the live log can carry (a family
    # the replay cannot read defaults silently and the floor diverges)
    pat = re.compile(r"\[queue\] (SERVE|LABEL|SENSE|COMPONENT|ROLLOVER|TRIPWIRE|PLUG|CONSEQUENCE|RUNG) (.+?) -> "
                     r"([A-Za-z_]+(?::[A-Za-z0-9]+)?)(?:\s+((?:'[^']+'|[A-Za-z0-9_ ]+?)!\$?[A-Z]{1,3}\$?\d+))?")   # rewrite:1 included
    for ln in Path(path).read_text(errors="ignore").splitlines():
        if " refused (" in ln or " REFUSED " in ln:
            continue                                  # a refusal line is not an answer
        m = pat.search(ln)
        if m:
            kind = "SERVE" if m.group(1) in ("LABEL", "SENSE") else m.group(1)   # rendered under the SERVE head
            ans = m.group(3)
            if ans == "derive:via" and m.group(4):
                ans = (ans, f"use {m.group(4)}")       # the cell the brain named rides along as the why
            picks.setdefault((kind, m.group(2)), []).append(ans)
    return picks


def make_answerer(picks):
    def _norm(ref):
        return re.sub(r"!([A-Z]{1,3})(\d+)$", r"!\2", ref)

    def _take(key, options, default):
        c = picks[key].pop(0)
        if isinstance(c, tuple):
            return (c[0], c[1]) if c[0] in options else default
        return c if c in options else default

    def answer(text, options, default):
        head = text.splitlines()[0]
        mm = re.match(r"CARD (SERVE|COMPONENT|ROLLOVER|PLUG|TRIPWIRE|CONSEQUENCE|RUNG)\s+(?:check\s+)?"
                      r"(.+?!\S+)", head)
        if not mm:
            mk = re.match(r"CARD (TRIPWIRE)", head)
            if not mk:
                return default
            kind, ref = "TRIPWIRE", ""
        else:
            kind, ref = mm.group(1), mm.group(2)
        for key in ((kind, _norm(ref)), (kind, ref)):
            if key in picks and picks[key]:
                return _take(key, options, default)
        if kind == "TRIPWIRE":
            for key in list(picks):
                if key[0] == "TRIPWIRE" and picks[key]:
                    return _take(key, options, default)
        return default
    return answer


class DeadBrain:
    """Present, never answers: the live shape with no brain."""
    def __init__(self):
        self.deadline = None
        self.model, self.base_url, self.api_key, self.max_output_tokens = "dead-brain", "", "", 14000
        self.usage = {"model": "dead-brain", "calls": 0, "prompt_tokens": 0, "completion_tokens": 0}

    def json(self, *a, **k):
        from pipeline.llm import LLMError
        raise LLMError("live-shape floor: the brain answers nothing")

    chat = json


def main(argv):
    live_shape = "--live-shape" in argv
    argv = [a for a in argv if a != "--live-shape"]
    if len(argv) < 4:
        print(__doc__)
        return 2
    company, period, year, art = argv[0], argv[1], int(argv[2]), Path(argv[3])
    log_path = argv[4] if len(argv) > 4 else None
    from pipeline.run import update
    answerer = make_answerer(picks_from_log(log_path))
    answerer.reviews = reviews_from_log(log_path) or None
    answerer.maps = maps_from_log(log_path) or None
    if answerer.maps:
        print(f"[replay] {len(answerer.maps)} recorded mapping turn(s) will be replayed")
    else:
        print("[replay] no mapping turns are recorded in this log: the mapping runs with no brain, "
              "every input row lands red 'not reached' — this floor tests extraction and the ending only")
    res = update(company, period, year, client=DeadBrain() if live_shape else None, stage4_mode="queue-only",
                 stage4_answerer=answerer,
                 pinned_ledger=str(art / "replay" / period / "ledger.json"),
                 pinned_served=str(art / "replay" / period / "provenance.json"),
                 log=print)
    print(f"\nFAITHFUL REPLAY -> {'DELIVERED' if res['ok'] else 'GATE REFUSED'}: "
          f"{res['out']}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
