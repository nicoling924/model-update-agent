# WIP — forecast-year balance build (2026-08-30, owner-approved)

Owner ruling: balance is for ALL years (my run-15 year-scoping was a
mistake — reverted). Plug allowed ONLY as last resort after genuine
attribution effort. Effort ladder: audit -> loop attributes each BS
movement into a designed CF input row (place_flow) -> deterministic
last-resort plug (orange, red if >10% of asset move).

DONE:
- gate.py: check failures refuse for ALL years again
- checks.py: loop state shows forecast fails as YOURS + ladder hint
- pipeline/forecast_balance.py: audit(), place_flow(), cf_input_rows(),
  last_resort_plug() — written, NOT yet wired or tested

TODO (in order):
1. orchestrator: new tool t_place_flow calling forecast_balance.place_flow
   (args {"bs_row": int, "cf_row": int}; sheet=Model; cols from spec);
   register in TOOLS; audit report exposed to the loop (a t_audit tool or
   inject into _state_block when forecast checks fail).
2. run.py: after the loop, last_resort_plug() over forecast columns
   (forecast_columns(spec, sheet, ty)), check_row/assets/bs rows for
   Model (check row from spec checks; bs rows = rows 47..93 discovery or
   from targets), BEFORE the gate.
3. prompts/stage4_objective.md: REWRITE the run-13 'priority ladder'
   section (it still says forecast checks are the analyst's — WRONG now):
   ladder = 1) target-year checks, 2) forecast balance by attribution
   (place_flow; plug is last resort and automatic), 3) adjudicate reds.
4. Museum: exhibits for place_flow legality (input-cell-only, formula
   shape), last_resort_plug (residue only, red-if-large, no catch-all ->
   left failing), audit attribution table.
5. Dry run (loop skipped -> last-resort plugs fire deterministically ->
   forecast years must tie in dry); audit the plugs; then ask owner go
   for run 16.

Context: delivered run 15 file = "model/Dongfang Electric FY25 (run 15
DELIVERED).xlsx" (owner rejects: forecast years unbalanced, +10,679 in
2026-2030; pre-model already -539). Run history in RUNLOG.md.
