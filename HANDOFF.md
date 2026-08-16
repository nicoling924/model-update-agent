# HANDOFF — read this first

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

## Next session

1. Read the live run result (`pipeline_live_run1.log`, `_REPORT` tab in
   the delivered/quarantined workbook, run summary at the end of the
   conversation log). Score it against the champion (stable-run105:
   80.6% / balance / keys 11-14 / 38 min) + the delivery gate — the
   champion/challenger law decides.
2. Not yet built (known gaps): restatement scan (prior-period comparatives
   vs model history — surface via loop statement_diff for now), true-up
   pass for FFC000 backouts, reviewer pass wiring (prompts/reviewer.md),
   _UPDATE_MAP migration into _SPEC.
3. Owner directives stand: pure gpt-5.6-luna, museum green always, dry
   runs before dispatch, one dispatch = one challenger evaluation, council
   on major decisions.

History and autopsies: RUNLOG.md. Presentation: PRESENTATION.md.
