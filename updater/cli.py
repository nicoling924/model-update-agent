"""Updater entry point.

    python -m updater.cli <company_dir> <period> <target_year> [--dry] [--budget=80]
    python -m updater.cli companies/DFE FY25 2025 --dry

Exit codes: 0 delivered, 2 usage/env error, 3 PAUSED for the analyst
(restatement question written — answer the JSON file and re-run).
"""
import os
import sys
from pathlib import Path


def _load_env():
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                if v and k not in os.environ:
                    os.environ[k] = v


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    flags = {a for a in argv if a.startswith("--") and "=" not in a}
    kv = dict(a.split("=", 1) for a in argv if a.startswith("--") and "=" in a)
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 3:
        print(__doc__)
        return 2
    company_dir, period, target_year = args
    client = None
    if "--dry" not in flags:
        _load_env()
        if not all(os.environ.get(k) for k in
                   ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL")):
            print("live run needs LLM_BASE_URL / LLM_API_KEY / LLM_MODEL "
                  "(or pass --dry)")
            return 2
        from .llm import Client
        client = Client(temperature=0.1, max_output_tokens=14000)
    from .restate import RestatementPause
    from .run import update
    try:
        res = update(company_dir, period, int(target_year), client=client,
                     loop_budget=int(kv.get("--budget", 120)))
    except RestatementPause as e:
        print(f"\nPAUSED (not a failure): {e}")
        return 3
    print(f"\nDELIVERED: {res['out']}")
    print(f"police: {res['police']}  flags: {res['flags']}  "
          f"served: {res['served']}")
    if client is not None:
        u = getattr(client, "usage", None)
        if u:
            print(f"engine: {u.get('model')} calls={u.get('calls')} "
                  f"tokens={u.get('prompt_tokens')}+{u.get('completion_tokens')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
