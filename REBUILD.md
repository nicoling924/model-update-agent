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
