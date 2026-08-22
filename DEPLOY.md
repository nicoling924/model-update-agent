# Deploying and testing this agent — no special tooling required

The agent is a plain Python application. Anyone with the repo, a Python 3.9+
environment, and one API key can run it. There is no Claude Code, no vendor
runtime, and no hidden service in the loop — the LLM is called through a
standard OpenAI-compatible API (currently `openai/gpt-5.6-luna` via
OpenRouter; any provider exposing that API shape works).

## Option A — GitHub Actions (recommended: zero local setup)

1. Fork or import this repository into your GitHub org (private is fine).
2. In the repo: Settings → Secrets and variables → Actions → add secret
   `LLM_API_KEY` (an OpenRouter key, or set `LLM_BASE_URL`/`LLM_MODEL`
   repo variables to point at your own gateway).
3. Actions tab → workflow **update** → Run workflow →
   `company: CLP`, `period: FY25` (leave `action` at its default
   `updater`).
4. Wait 40–70 minutes. Download the run's artifact: it contains the
   updated Excel model, the pre-update archive, and the full log.
5. Open the model. The **`_REPORT` tab is the first sheet** — the run's
   own review: red flags with citations, derived figures, big moves,
   actual-vs-forecast, and the Police verdict in the header.

## Option B — run locally

```bash
git clone <repo-url> && cd model-update-agent
python3 -m pip install -r requirements.txt
echo "LLM_API_KEY=sk-..." > .env          # never commit this
python3 run.py update companies/CLP FY25
```

The updated model lands in `companies/CLP/model/`, the pre-update copy in
`companies/CLP/model-archive/`.

## Verifying the install without spending tokens

```bash
python3 -m unittest tests.test_updater_museum     # 137 regression exhibits
python3 tools/benchmark.py companies/CLP FY25 2025   # offline gate
```

Both must be green. The benchmark is the dispatch gate: a head that is not
"dispatch-eligible" should never be run against a live model.

## Trying your own company

```
companies/<TICKER>/
├── model/          <- the ONE live Excel model
└── disclosures/<PERIOD>/   <- the period's PDFs (AR, announcement, ppt)
```

Drop the files, then run `python3 run.py update companies/<TICKER> <PERIOD>`.
No per-company code or configuration is required: on a first ("cold") run
the agent discovers the model's anatomy at runtime and writes what it
learned into a hidden `_SPEC` tab inside the workbook, so the next run is
faster and better. Expect the first run on a new company to be a
calibration run — its job is to surface that model's judgment questions as
red flags for the analyst, not to be perfect.

## What the pieces are (for reviewers)

- `updater/` (~11k lines) — the application: PDF extraction with
  arithmetic verification, deterministic mapping, ~15 write-guards, Excel
  writing, balance checks, the report. The LLM is one component it calls
  (~10–15 bounded JSON exchanges per run); the LLM never writes or
  executes code.
- `prompts/` (~1.3k lines) — the instruction templates the application
  fills with per-run data. Not runnable on their own.
- `tests/`, `tools/benchmark.py` — the regression suite and the offline
  gate; every past failure class is frozen here.
- `companies/` — input documents and models (the bulk of the repo's size;
  in production these would live in a document store instead).
- `agent/`, `pipeline/` — retired earlier architectures, kept for
  history; not executed.

Model-agnostic by design: the engine is set by `LLM_MODEL`/`LLM_BASE_URL`
env vars. Swapping providers requires no code changes.
