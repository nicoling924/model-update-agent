"""Pipeline entry point.

    python -m pipeline.cli "<company_dir>" <PERIOD> <TARGET_YEAR> [--dry]
                           [--budget N]

--dry runs every deterministic stage with no LLM (the pre-flight path);
a live run requires LLM_BASE_URL / LLM_API_KEY / LLM_MODEL in the
environment (a repo-root .env is honored, matching the legacy runner).
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
        from .llm import env_ready, make_client
        if not env_ready():
            print("live run needs LLM_BASE_URL / LLM_API_KEY / LLM_MODEL "
                  "(or pass --dry)")
            return 2
        client = make_client()
    from .run import update
    res = update(company_dir, period, int(target_year), client=client,
                 loop_budget=int(kv.get("--budget", 60)))
    print(f"\n{'DELIVERED' if res['ok'] else 'GATE REFUSED'}: {res['out']}")
    if client is not None:
        u = getattr(client, "usage", None)
        if u:
            print(f"engine: {u.get('model')} calls={u.get('calls')} "
                  f"tokens={u.get('prompt_tokens')}+{u.get('completion_tokens')}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
