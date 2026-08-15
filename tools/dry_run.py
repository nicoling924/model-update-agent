"""Stubbed dry run — execute a whole command locally with the LLM replaced.

The mandatory pre-flight before any paid dispatch. A compile check cannot catch
binding-order bugs (a name read above where it is assigned runs fine until the
branch is taken); executing the real command against the real workbook does.

Every LLM call returns an EMPTY answer, so the harness walks its own control
flow end to end with nothing found: retrieval, mapping, audit, objectives,
integrity gate, report. What this proves is that the code PATHS execute — not
that the answers are right. Accuracy is measured only on a real run.

    python tools/dry_run.py DFE FY25 FY24      # both legs
    python tools/dry_run.py CLP FY25 --update  # update leg only

Work happens on a throwaway copy of the company directory; the real model and
the real archive are never touched.
"""
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# credentials must exist before agent.llm imports; they are never used
os.environ.setdefault("LLM_BASE_URL", "http://dry-run.invalid/v1")
os.environ.setdefault("LLM_API_KEY", "dry-run")
os.environ.setdefault("LLM_MODEL", "dry-run/stub")


class Empty(dict):
    """An answer with nothing in it — any key reads as an empty list.

    Real answers are schema-validated, so a missing key is not a real failure
    mode; making it one would fill the dry run with false alarms.
    """

    def __missing__(self, key):
        return []


def install_stub():
    from agent import llm

    calls = {"n": 0}

    def chat(self, system, user, force_json=True, **kw):
        calls["n"] += 1
        self.usage["calls"] += 1
        return "{}"

    def json_(self, system, user, validate, repair_retries=2, **kw):
        calls["n"] += 1
        self.usage["calls"] += 1
        return Empty()

    llm.Client.chat = chat
    llm.Client.json = json_
    return calls


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if not args:
        sys.exit("usage: python tools/dry_run.py <COMPANY> [PERIOD] [PRIOR] "
                 "[--learn|--update]")
    company = args[0]
    period = args[1] if len(args) > 1 else "FY25"
    prior = args[2] if len(args) > 2 else "FY24"
    src = REPO / "companies" / company
    if not src.is_dir():
        sys.exit(f"no such company directory: {src}")

    calls = install_stub()
    from agent import cli

    tmp = Path(tempfile.mkdtemp(prefix=f"dryrun_{company}_"))
    work = tmp / company
    shutil.copytree(src, work)
    print(f"[dry-run] working copy: {work}", flush=True)

    legs = []
    if "--update" not in flags:
        legs.append(("learn", lambda: cli.cmd_learn(str(work), prior)))
    if "--learn" not in flags:
        legs.append(("update", lambda: cli.cmd_update(str(work), period)))

    failed = []
    for name, fn in legs:
        print(f"\n{'=' * 60}\n[dry-run] {name} leg\n{'=' * 60}", flush=True)
        try:
            fn()
            print(f"[dry-run] {name}: COMPLETED", flush=True)
        except Exception:
            failed.append(name)
            print(f"[dry-run] {name}: CRASHED", flush=True)
            traceback.print_exc()

    print(f"\n[dry-run] stubbed LLM calls: {calls['n']}")
    if failed:
        print(f"[dry-run] FAILED legs: {', '.join(failed)} — do NOT dispatch")
        sys.exit(1)
    print("[dry-run] all legs executed end to end — safe to dispatch")


if __name__ == "__main__":
    main()
