# Handoff brief — Model Update Agent (read this first)

Fresh-session brief. Everything below is current as of the last commit on branch
`objective-driven`. Repo: `/Users/lingling/Project M/model-update-agent`,
GitHub `nicoling924/model-update-agent`.

## 1. What this is

An agent that marks an equity-research valuation model to actual results from
the company's disclosures, in one pass. Two commands:

- `learn <company_dir> <prior_period>` — the **practice year**. Calibrates on the
  PRIOR year (where the model already holds the answers), writing a hidden
  `_UPDATE_MAP` memory tab: verified row->line identities, component recipes,
  definitional bridges, and reasoned "quirks".
- `update <company_dir> <period>` — the **cold run**. Uses only the model +
  memory tab + the new period's PDFs. Never reads prior-year documents.

The pitch structure the user needs: **one calibration pass, then one-click cold
updates.** Do not add cross-run memory of the target period — that would be
cheating and invalidates the claim.

## 2. The acceptance contract (the user's words, strict cascade)

1. **Balance — all six years** (actual + forecasts). Non-negotiable.
2. **All key numbers correct** — sales, gross/operating profit, net profit,
   cash, current/non-current assets & liabilities, equity, CFO/CFI/CFF,
   sales & gross-profit breakdowns. Formulas must be **derived by the agent per
   company**, never hardcoded methods.
3. **Completion rate** — 80% floor to hit reliably, 90% stretch.
4. **Time** — 60 min per leg is a limit, not a goal. Accuracy always wins.

Engine: **pure gpt-5.6-luna**. Terra allowed only as blind reviewer, only at a
proven plateau, and must be logged. Every trial needs an investigated root
cause and a purposeful change — never a blind re-run. Revert anything that
regresses (git history is the rope).

## 3. Where it stands (CLP, scored vs the analyst's finished model)

Best run: **75.9% whole-model, keys 9/12, 2025 balance PASS, 46 min**
(record-low 44 wrong-flagged). Recent band: 74–76%, keys 8–9/12.
Session arc: started at 66% with nothing balanced.

**Four named residuals** (each precise, none mysterious):
1. **Forecast drift** ~+352/year — one propagating item the agent hasn't yet
   traced. Its constant per-year signature is the clue.
2. **CFO** — the learned bridge serves the right value (22,613) but the final
   model lands ~100-250 off; some stage still nudges it.
3. **NCL** — the model-equation solve inherits error from a weak member.
4. **CFF** — no double-locked construction found yet (needs a wider search).

Ground truth for scoring: `companies/CLP Holdings/model/CLP Model FY25
(Updated).xlsx` (outside the repo, in Project M). **Never let the agent see it.**

## 4. Dongfang (DFE) — the genericity test, in progress

A structurally different model: the `Model` tab is a **view** whose actual
columns are formulas into a Chinese-language `Raw financials` source sheet.
Four failures were fixed in sequence, each a real generic gap:
- partial rollover -> circular refs. Fixed: **universal rollover** — every
  year-axis sheet gets the target column, created if absent.
- false clobber alarms from Excel data-table objects. Fixed: stable tokens in
  `formula_map`.
- reviewer JSON crash on those objects. Fixed: stringify in `column_dump`.
- no structural self-awareness. Fixed: `workbook.resolve_input_site()` follows
  last year's formula to where the number is actually **typed**, and carries the
  view sheet's English label to the source row.

Then two more, found by executing rather than reading (run 95 + the dry run):
- `site_labels` was read above where it was assigned — the update leg crashed
  4 min in, every time. A compile check cannot see this; the dry run can.
- **document units**: the CN annual report prints yuan (69,695,135,723.47)
  where the model holds millions (69,695.14), so retrieval-by-prior-value
  found 19/75 known values and the learner verified **0 of 210** — the numbers
  were present, printed 1,000,000x larger. Scale is now detected once per run
  by reconciliation (the scale that explains the most known model values),
  threaded through every "does this line carry this value" test, told to the
  reader, and used to convert document-unit answers back. Scale 1 keeps the
  original string path byte-for-byte, so CLP is provably untouched.

There is **no ground-truth DFE model** — judge it by its own integrity checks
(balance rows, tie-outs) and flag inventory.

**The live model must be pristine at dispatch.** A run output had been
committed over `companies/DFE/model/DFE Model.xlsx` (column U already rolled,
`_REPORT` tab present); CI checks out what is committed, so the next benchmark
would have started half-updated. Restored from `abe3232`. Check the live model
has no `_REPORT` tab before dispatching.

## 5. How to operate

Runs happen **on GitHub Actions only** (the user's rule). Dispatch:

```bash
sh dispatch.sh CLP FY25 FY24        # or: sh dispatch.sh DFE FY25 FY24
```

`dispatch.sh` reads the token from the **git credential helper**, which
persists across sessions — no device-flow re-auth was needed on 08-15. If it
ever prints "no stored GitHub credential found", fall back to the device flow
(request a code, user approves at github.com/login/device, exchange at
`https://github.com/login/oauth/access_token` — the `/login/oauth/` path).

**Dry-run first — it is committed now** (`tools/dry_run.py`, previously lost
with its session's temp dir). It stubs every LLM call and executes the real
command against the real workbook on a throwaway copy:

```bash
python tools/dry_run.py DFE FY25 FY24
```

It proves the code PATHS execute, not that answers are right. It caught the
run-95 crash and 80 false clobbers before either cost a dispatch.

**One writer per repo.** On 08-15 two sessions worked this repo at once: the
other committed mid-flight (sweeping in the first session's uncommitted edits)
and dispatched a run against the contaminated model. Commit promptly, and check
`git log` before assuming the tree is yours.

Scoring a finished run: download the artifact, then

```bash
python tools/score_run.py "<path>/model/CLP Model.xlsx"
```

Also check keys directly against the GT list in section 3 and read the run log
for `Objective 1/2`, `[6z]`, `FINISH REFUSED`, `[ALLOC]`, `bridge`.

## 6. Hard-won lessons — do not relearn these

- **Dry-run before dispatching.** Stub the LLM and execute the whole command
  locally; it catches binding-order bugs a compile check cannot. Two paid runs
  died before this existed.
- **Analyze results, not mechanisms.** After every run, inventory the wrong
  cells by cause (carried / mapped-wrong / composite / formula-amplified) and
  attack the biggest group. ~48% of wrong cells are formulas amplifying a
  smaller set of wrong inputs.
- **Never let a later stage overwrite objective work.** Objective-written cells
  are hard-locked; the coverage pass runs before the objective phase, not after.
- **Silence is the enemy.** Every unresolved value must be flagged; a silently
  carried prior-year number was the single worst bug of the project.
- **The harness must hold the goal.** `finish` is refused by code while balance
  or keys are unmet and time remains — a weak model takes any exit it's offered.

## 7. Architecture in one paragraph

Retrieval (code, free) finds each row's home pages by Ctrl+F on its known
prior-year value; the LLM reads whole blocks holistically (3 votes, reconciled)
with candidate evidence lines delivered to it; code audits every answer (page
citation, magnitude, unit scale, year-token filter). Then the audit web —
tie-web subtotal anchors, sibling-first corrections, allocation to proven
totals, learned bridges and identity solves — converges the objectives. Finally
the **agent loop** (150 decisions, full hour, scorecard re-shown every turn,
todo ledger, trace/diagnose/remap/statement_diff/read_bridge/request_review
tools, transactional self-verifying writes that auto-revert on regression) owns
the run to the end. Nothing writes after it except the integrity gate and report.

## 8. Budget

OpenRouter ~$20 (≈10 runs at ~$1.50–2). GitHub Actions budget $10 set with a
hard stop. Runs take 25–50 min per leg.
