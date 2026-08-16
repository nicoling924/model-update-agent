# REBUILD — the clean main (owner ruling, 2026-08-17 ~01:30)

Patching the legacy pipeline is over. Measured verdict of 100+ runs: the
legacy stack peaked at run 105 (80.6% / balance / keys 11-14 / 38 min) and
every patch cycle since oscillated 58-80 — each fix moved the bug, not the
ceiling. The owner's ruling, which matches the council's architecture
verdict (council/architecture-council.md): keep the peak frozen and
showable, and rebuild clean.

## Branch map (do not blur these)

- **stable-run105** — FROZEN champion. The showable agent (80.6%, balance,
  keys, 38 min). Never commit to it. Reproduce: `sh dispatch.sh DFE FY25
  FY24 stable-run105`.
- **run105-line** — parked experiment (validated guard ports on the
  champion). Reference only.
- **rebuild** — THE new main. All new work here, ONLY inside `pipeline/`.
  `agent/` on this branch is read-only legacy reference — import from it,
  never edit it. Its diseases and their fixes are documented in RUNLOG and
  encoded in tests/test_museum.py.
- **objective-driven** — the legacy line, closed.

## Owner objectives (standing mandate, 2026-08-17 overnight ruling)

The benchmark: **Fable 5 completed ~95% of the DFE model in one clean run.**
That is what the agent chases, on pure gpt-5.6-luna. In priority order:

1. **The model balances — or is flagged. No exception.** Every period,
   historical and forecast.
2. **The key numbers are present and correct-or-flagged**: revenue, profit,
   current and non-current assets, liabilities, equity, and operating /
   investing / financing cash flows. These are what the analyst reads
   first; they must never be silently wrong.
3. **Completion: 80-90% of the entire model filled, minimum**; 95% is the
   Fable-5 parity target.
4. **The column convention**: the new actual column is the prior actual
   column carried forward — same formulas (Excel-shifted), same formats,
   same cell types — with ONLY the hardcoded inputs, and numeric constants
   embedded inside formulas, updated to the new financials. The analyst
   must find everything exactly where they left it.

**Objective-based, not a workflow machine.** Luna runs the way Fable 5
works free-form: one objective loop, tools as hands, state external. The
deterministic stages are the ASSISTANCE handed to that loop — they gather
evidence, bind what is provable, check what is checkable, and constrain
what may be written — but the LLM pursues the objective; a fixed call-graph
of scripted steps is the failed legacy design. Deterministic machinery
never invents a number.

**Generic across the whole department.** The agent will be deployed to
every analyst; every analyst's model is different — language, format,
style, company, industry. Therefore: NO company-specific logic in code, no
remembered formulas, no template assumptions. Per-company knowledge lives
in the workbook's own `_SPEC` tab and travels with the file. Mechanisms
must be NUMBER-ANCHORED (prior-identity triangulation, block-scale
ratification, checksums) rather than label- or layout-bound — labels vary
across languages and house styles; last year's numbers do not.

## The champion/challenger law

The champion (stable-run105) is only ever replaced by a challenger that
BEATS it in a real dispatched run on the owner's four criteria:
1. the model balances itself;
2. the key numbers are found and accurate;
3. completion > 80%;
4. under one hour.
PLUS the delivery gate below. No exceptions, no "this fix is obviously
good" — the whole legacy line died of obviously-good fixes.

## The delivery gate (owner's usability bar — run A/B failure autopsy)

A run REFUSES to deliver unless all pass (deterministic checks, no LLM):
1. every year header/date cell rolled to the new period's convention
   (no "2025E", no stale "2024-12-31" date heads);
2. order-of-magnitude sweep: no written cell >100x/<1% of its prior
   actual (catches every raw-yuan/unconverted cell ever shipped);
3. flag budget: >15% of a sheet's filled cells flagged = the run FAILED
   (flags are "look here" markers, not a liability waiver);
4. Driver roll integrity: every forecast formula rolled, no sign-absurd
   values (negative revenue class);
5. balance/cash-tie/keys checks as before.

## The architecture to build (council blueprint, validated pieces first)

- Stage 1 READ ONCE: multi-pass consensus extraction into an evidence
  ledger (items with value, prior, page, stmt-face tag, table id, row
  order, column binding, unit dimension).
- Stage 2 JOIN (pure code): the triple-lock deterministic join — measured
  130/130 vs the filing on DFE (legacy agent/join.py is the validated
  prototype; port, don't re-invent). Hard gates: signed prior identity at
  row_tol, block-scale ratification, face authority, non-vacuous kinship,
  agreement-or-nothing, parent-entity exclusion, composition/backout rows
  excluded, twins dropped.
- Stage 3 READ GAPS: whole-page reader with the per-row comparative
  checksum (legacy agent/fablemode.py at stable-run105+sign-rule is the
  validated prototype; zero wrong reads ever measured). Serves ONLY rows
  Stage 2 left; no-prior rows only with a block-scale anchor.
- Stage 4 VERIFY & CHASE: deterministic checks + the orchestrator with the
  two playbooks (prompts/orchestrator.md), which demonstrably reasons well.
  Machine heuristics NEVER write: no allocation scaling, no closing swaps,
  no label-matched rescues. Unproven = flagged hole.

## Validation protocol (what would have caught runs 112-116 pre-dispatch)

- tests/test_museum.py green, always — extend with every new disease.
- Pinned extraction snapshots: Stage 2-4 run locally from committed JSON
  ledgers in seconds; no vision, no LLM in the pre-flight path.
- Offline precision gate: the joiner replayed against the verified DFE
  workbook must stay >= its committed baseline before any dispatch.
- Dry run (stubbed LLM) end to end for DFE AND CLP.
- One dispatch = one challenger evaluation. Never dispatch to "see".

## Reference results (keep honest)

- stable-run105 cold: 80.6% / Model 90.4% / 2025 balance PASS / keys 11/14 / 38 min.
- Clean-room strong-model ceiling: 96.0% (Model 100%).
- Verified deliverables in companies/Dongfang Electric/model/.
- Joiner prototype: 130/130 vs filing offline. Reader: 0 wrong reads, all runs.
