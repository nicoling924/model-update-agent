# HANDOFF — read this first

**REDESIGN NIGHT (2026-08-18): the packetized thinking agent is LIVE.**
Read MORNING_REPORT.md for the full story. Short version: owner halted
the patch spiral; council session #1 redesigned the unit of work
(packets, L0/L1, compile+surgeon, method-not-laws — REDESIGN.md);
council session #2 solved the three walls as representation problems
(Table Islands / Closing Bell / Atomic Reclass). Five runs in: half the
cost, zero trace-spam, balance at one 1.0 residual with all forecast
years passing, segments writing 15/33 reproducibly with island
citations. Open: CFI/CFF ~594 twin (reclass trigger needs data-driven
diagnosis), the last 1.0 (bell aims at proven cells), CLP genericity
run, EPS-class proof. Governing docs: BOSS_MINDMAP.md (objectives),
REBUILD.md (constitution), REDESIGN.md (architecture), OVERNIGHT.md
(run cards). Museum: 63 exhibits. Engine: pure gpt-5.6-luna.
Owner protocol: report card -> problems -> proposal after every run; no
symptom patches — rethink design-level, council when stuck.

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

## RUNBOOK — dispatching a live run (canonical, AUDIT 2026-08-18)

ONE way to fly a run — never a hand-built curl:

    tools/dispatch.sh <COMPANY> <PERIOD>       # e.g. tools/dispatch.sh DFE FY25

It verifies local==origin on rebuild, dispatches with action=updater
EXPLICIT, resolves the run by created-after (no newest-run race), asserts
the run's head_sha, waits, and only reports success after the UPDATER
FINGERPRINT is found in the run's own log. Exit 2 = wrong chain / crash —
never score that run. Run it inside a Monitor so completion notifies.

Preconditions for ANY dispatch (owner law, one-run-one-hour):
  1. python3 -m unittest tests.test_updater_museum   -> all green
  2. python3 tools/benchmark.py companies/<T> <P> <Y> -> ALL layers green
  3. nothing else about to land within minutes

The legacy stack is RETIRED: the workflow fails loudly (exit 64) for any
action except `updater`, and the old chain only runs behind the explicit
value `legacy-chain-i-am-sure`.

## RESUME POINT — 2026-08-19 (owner took the machine; local work stopped cleanly)

State: DFE bar MET (run 33: balance PASS all years, keys law PASS 27
proven, 12/12 mistakes). CLP first flight flown (diagnostic: generic ✓,
quality shallow). Owner's post-review rulings ALL IMPLEMENTED and
committed (museum 111 green):
- DFE rebased ruling live (updates/rebased_ruling.json): 2024 untouched,
  structure kept, 2025 WRITTEN from new partition + mandatory red.
- Subheader law (no numbers any year + nothing sums it = not work).
- Pattern rows (prior cell's formula = the input logic; constants anchor
  the last-year map; pattern_formula write with printed-constant law).
- Flag discipline (red only when the filing demonstrably carries the
  figure; else quietly stale + _REPORT line).

TO RESUME (in order):
1. `python3 tools/minirun.py companies/DFE FY25 2025 "Raw financials,Driver" companies/DFE/replay/FY25/mini_expect.json`
   (expect: rebased rows now WRITTEN+red per ruling; caches warm, ~10 min)
2. `python3 tools/minirun.py companies/CLP FY25 2025 "Final" companies/CLP/replay/FY25/mini_expect.json`
   (expect: no subheader writes; Final!57 pattern resolved-or-flagged)
3. CLP BALANCE AUDIT (owner's point 3, not yet done): why did the
   residual/surgeon/bell machinery barely engage on CLP's 8 failing
   checks? Inspect the CLP first-flight artifact (scratchpad/clp1) run
   log for residual packets; suspect check-row discovery or the queue.
4. Then: benchmarks (DFE + CLP) → dispatch DFE + CLP via
   tools/dispatch.sh per the runbook (gates green first).
Open owner ruling still pending: CLP cash +23 (bind with adjustment
inference, or leave unbound).

## RESUME POINT — CLP campaign (after CLP run 2)

Run 2 delivered: Aus revenue exact via the 2D matrix join; all
consolidated keys converging with coverage (NP 10,115→11,546 target);
zero wrong values. NEXT, in order:
1. CN sheet confined test: `python3 tools/minirun.py companies/CLP FY25 2025 "CN" companies/CLP/replay/FY25/mini_expect.json`
   — grow expectations from the segment matrix (p177/178) CN column.
2. HK Sales / SOC sheets (operating stats — sources are the business
   review + stats appendices, likely matrix-shaped too).
3. The ±1,765 CFO/CFF reclassification: law-2 adjustment binding
   (model CFO = filing CFO − adj; the adjustment's FY25 magnitude must
   be inferred from the model's own structure — Final rows 101-140).
4. EBITDAF definitional fork (EBITDAF vs operating earnings tables):
   agent judgment via label kinship — teach if it recurs.
Owner rulings pending: DFE J6 scope, rollover design-formula question.

## CLP campaign — after run 3 + refinements (committed)

Fable-diff verdicts: class 2 (group-total pastes) FIXED; class 3 (JV
blocks) mostly fixed; class 1 half (Aus exact, CN dashed-row lead fixed
post-run — dashed matrix rows now leave the 1D pool); cross-sheet guard
re-scoped to key rows (mirror rows are legal). NEXT: CLP run 4 verifies
both refinements; then remaining classes 4-5 (allocation judgment, SoC
machinery) per owner appetite. Agreement 71-73% vs Fable; zero
wrong-with-confidence classes remain.
