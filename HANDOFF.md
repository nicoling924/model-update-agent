# HANDOFF — read this first

**OBJECTIVES REWORKED + NEW AGENT BUILT (2026-08-17 evening).** The mindmap
session happened: **BOSS_MINDMAP.md** is the governing objectives document
(always deliver, no refusal/flag-budget/completion-%; restatement = the one
pause; 4 Police laws; keys+segments over completion; champion retired).
REBUILD.md rewritten as the constitution; TOOLSET_AUDIT.md holds
evidence-graded keep/kill rulings on all legacy tooling; BUILD_PLAN.md the
approved design. **`updater/` is the new package**: one agent loop owns the
whole run (bulk stages are its TOOLS), evidence-graded writes (A-D ->
flags automatic), self-announcing toolbox, restatement pause/resume with
agent judging, adjustment-logic inference, Police (findings loop back,
never auto-apply), new _REPORT (proj-vs-actual + old-vs-new forecast).
Museums: 24 updater + 50 pipeline + 6 legacy, all green. Dry runs DELIVER
on DFE and CLP with honest Police verdicts. Next: first live Luna run
(`python -m updater.cli companies/DFE FY25 2025`). Everything below is the
PRE-REWORK technical state, kept for reference.

**Day-2 state:** 10 live runs total (5 local, 5 cloud). Latest cloud run
(v10): balance residual 67 (from 4,042), 141 deterministic joins at 175/176
measured precision, honest refusal on Driver flag budget 24% vs 15% and the
cash-tie -11,193. Three named residuals: CF-face rows not joining despite
evidence (autopsy next), Driver flag budget (needs an owner ruling on
whether driver sheets share the statement sheets' 15% bar), loop budget
exhaustion on multi-check runs. Museum: 50 exhibits green.

**State (2026-08-17 overnight):** the clean rebuild is BUILT. `pipeline/`
now holds the complete four-stage agent (fresh code, zero copied from
`agent/`), the 40-exhibit pipeline museum is green, dry runs pass on DFE
AND CLP with zero company-specific code, and the first live pure-Luna
challenger run is in flight. REBUILD.md remains the constitution — it now
also carries the **owner objectives** (2026-08-17 mandate): balance-or-
flagged, keys correct-or-flagged, 80-90% completion (95% = Fable parity),
the column convention, objective-based not workflow-machine, generic
across the whole department.

## The pipeline (all in `pipeline/`, all stdlib-importable; heavy deps lazy)

- `numerics.py` — tolerance doctrine (row worlds), year-token filter,
  non-vacuous kinship, scale set, unit conversion.
- `ledger.py` + `stage1_read.py` — STAGE 1 READ ONCE: evidence ledger
  (items with table_id/row_ord/face/unit_dim/scale_hint; JSON snapshots);
  text channel deterministic, vision channel = multi-vote consensus +
  prior-column checksum (parent-twin defense), 3-wide parallel calls.
- `targets.py` + `stage2_join.py` — STAGE 2 deterministic triple-lock
  join: face authority, block-scale ratification (>=2 items, >=2 distinct
  aggregate priors, scale-invariant ties refused), signed slot-by-tie
  prior identity at row_tol, kinship corroboration, agreement-or-nothing,
  twins dropped, sibling-position pass, world-band at join time (the CLP
  dividend poison). Pure code, JoinDecision provenance.
- `stage3_read.py` — STAGE 3 checksummed gap reader: whole regions, signed
  per-row comparative checksum; no-prior rows ONLY with a ratified block
  anchor (run-116 law re-armed), conf 5 lockable / conf 3 flagged.
- `writer.py` — the ONE write chokepoint: world band, numeric preview,
  read-back; column rollover (owner's convention) + year-header roll;
  clobber diff; flags.
- `checks.py` + `orchestrator.py` + `prompts/stage4_objective.md` — STAGE
  4: deterministic scorecard + the OBJECTIVE LOOP (Luna owns the update;
  tools: rescore/trace_cell/find_line/statement_diff/set_input/flag/notes;
  set_input needs a page citation, refuses subtotals, and is TRANSACTIONAL
  — auto-revert if a passing check breaks).
- `gate.py` — delivery gate: year headers rolled (type-preserving),
  magnitude sweep, 15% flag budget, driver-roll sanity, checks/clobber/
  errors/cycles. Refusal = quarantine filename, never a delivery.
- `discover.py` — anatomy DISCOVERY (genericity): year axis (with the
  1H-panel trap solved by period-kind), check rows, key rows — the agent
  reasons the model out; no spec needed to run; draft persists to _SPEC.
- `spec.py`, `report.py` (the _REPORT first sheet), `replay.py` (offline
  precision gate: bindings diff vs pinned baseline), `run.py` (end to
  end), `cli.py` (`python -m pipeline.cli <dir> FY25 2025 [--dry]`),
  `llm.py` (the ONE legacy import: transport only).

## Validation state

- `tests/test_pipeline_museum.py` — 40 exhibits green (112/115/116 on the
  new line, CLP dividend poison, transactional writes, gate laws, ...).
  `tests/test_museum.py` (legacy) still green.
- Pinned snapshots: `companies/Dongfang Electric/replay/FY25/` (Project M
  tree): ledger.json, targets.json, decisions.json, baseline.json (74
  deterministic bindings). Replay contract: ANY changed binding is a
  release blocker (`python -m pipeline.replay ... --baseline=...`).
- Dry runs (no LLM): DFE 7s warm / gate correctly refuses on the unread
  scans; CLP end-to-end via AUTO-DISCOVERY (8 sheets, 57 joins, honest
  refusal). The gate caught two real poisons in dry runs alone.
- Actions: `update.yml` gained action `pipeline` (runs `pipeline.cli` on
  the repo's companies/DFE|CLP data; auto-discovery covers their legacy
  spec format).

## Overnight live-iteration results (5 Luna runs, 2026-08-17 ~01-06 HKT)

Full story: MORNING_REPORT.md. Headline: **challenger scored 70.3% whole /
82.5% Model tab, balance gap 59 (0.04%), GATE REFUSED (its own honest
verdict) — the champion (80.6% / 90.4% / PASS / delivered) KEEPS the
title.** Trajectory across the night's iterations: balance 645 -> 446 ->
59; six real diseases found live, fixed, and pinned as museum exhibits
(FY24-doc checksum coincidence + early abort; cropped-caption faces;
redirect sign law; CLP dividend per-share poison; year-axis census rows;
doc-vintage classifier). Luna diagnoses excellently in the loop; its
remaining weakness is CONVERTING findings to writes — apply_diff (the
find-to-act bridge) landed in the final run and fired 5 times.

## Next session (ranked)

1. **The Driver/MD&A serving path** — 55.8% on Driver is the whole gap
   (as it was for the champion). Driver rows live in MD&A tables the
   join's face-authority correctly refuses; they need either a bound-table
   Stage-2 extension (council's two-level table binding) or loop-driven
   apply_diff over an MD&A-scoped diff.
2. **The loop's endgame authority** — the 59 residual needs the analyst's
   documented plug/re-anchor move (orange-flagged); decide (owner/council)
   whether the loop gets that move with proof requirements, as legacy
   plug_key had.
3. **Flag-budget clearing** — 80 stale inputs remain the delivery blocker;
   apply_diff works on them but Luna prioritizes balance; consider a
   pre-loop deterministic apply_diff sweep over STALE rows that have
   unique face evidence (it is stage-2-grade evidence; zero LLM).
4. Not yet built: restatement scan, true-up pass for FFC000 backouts,
   reviewer pass wiring, _UPDATE_MAP -> _SPEC migration.
5. Owner directives stand: pure gpt-5.6-luna, museum green always (43
   exhibits), dry runs before dispatch, one dispatch = one challenger
   evaluation, council on major decisions.

History and autopsies: RUNLOG.md. Presentation: PRESENTATION.md.
