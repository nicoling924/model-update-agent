# Design 2026-09-17 — the brain maps the model; code indexes, verifies, measures

Owner's ruling (2026-09-16/17): the card queue, the number-tie join, the composites law and phase0 all decide
meaning by number coincidence, one shot, no memory, and can overrule the brain. "There is no thinking in
preparing the cards." Rebuild the MAPPING stage the way the ending was rebuilt: the brain reads and decides,
code indexes, verifies and measures. A deduction: the stages below are removed, not wrapped.

## Evidence (runs 35089032559 / 35107985779 CLP, 35089036223 / 35107991176 DFE)
- Same mapping code, different one-shot draws: other income 460 mapped in one run, "not disclosed" in the
  next; one-offs derived in one, sign-flipped by a composite rewrite in the next.
- The brain's correct minority-interests pick (perpetuals) refused as "proven" in both CLP runs — a
  definition judgment overruled by a number tie.
- DFE Raw financials!U16: the name judge refused a 合计 total line; a serve card re-offered it with a tick and
  no memory; the brain took it; net profit −1,076.
- phase0 wrote SOC Accounts!AI7 = 20 from a coincidental tie, cleared two earlier red doubts, no note.
- The "net profit" key pinned to the statement copy (Raw financials!U40), not the model's own row (Model!U28).

## What is removed (the deduction)
- `stage2_join` as a WRITER (number-tie join that fills cells). It survives only as an INDEX: for each
  model row, the printed lines whose comparative ties the prior — candidates shown to the brain, never written.
- `composites` as a writer (the constants law rewriting formulas by literal matching). Composition is the
  brain's statement, verified by code arithmetic.
- `phase0` (code applying "guilty" diffs and rewrites with no brain).
- The work-queue cards for mapping: SERVE, LABEL, COMPONENT, PLUG-for-mapping, their candidate scoring,
  ticks, warnings, defaults, the "proven"/"was served"/"one row one claim" refusals, `rewrite:1`, `derive:1`.
  ROLLOVER/RUNG cards go too — the review loop already owns roll-forward.
- The reader's one-shot per-row answers as a separate stage (`brain_read`) — folded into the mapping loop.
- Key rows pinned to statement copies: keys are the model's own lines.

## What stays (code as index, verifier, measurer)
- Extraction as an index: page text, numbers per page, page scale, statement faces (stage1_read, demoted).
- Name judgment of the statements (which page is which statement) — a brain call, kept.
- The write gate: a `set` lands PLAIN only when the quoted line is on the page and its comparative ties the
  model's prior at full precision, or the brain states arithmetic over printed figures that code re-computes;
  RED otherwise; never refused; NEVER over a formula cell (the house rule; the ending needs the same guard).
- Objectives measured by code (balance, keys on the model's own rows, cash/assets, headline lines vs history).
- The review loop at the end (unchanged), the terminal ladder, the report page, restatement scan.

## The mapping loop (mirrors pipeline/review.py)
Context the brain sees, refreshed every turn (≤ ~12k tokens):
1. The model's input rows for the actual column, by sheet and section: label, history (4 years), the
   analyst's pre-update estimate, status (unfilled / filled by the brain / red), and for each row the
   INDEX: printed lines whose comparative ties the prior (page, quoted line, figure) — shown as candidates,
   never as ticks or ranks.
2. The statement faces as text (P&L, BS, CF, segment tables) with page numbers — the brain reads them.
3. Coverage: how many input rows are still unfilled, by sheet.
4. Its own prior turns, one line each (what it mapped, what it refused and why).
Tools: `page N` (the page text), `find <number|label>` (index lookup across pages), `show sheet!row`
(row, history, formulas that use it), `set` / `sets` (batch writes with a quoted line or stated arithmetic
per cell; pairs/batches measured as one), `skip sheet!row because <why>` (lands red with the reason —
"not disclosed" is the brain's judgment, recorded), `restate` (a comparative that disagrees with the model's
prior — the restatement path, verified), `done` (accepted only when every input row is filled or skipped
with a reason).
Mandate: you are the analyst mapping the disclosure into your own model. A number match is a lead, not a
mapping: read the line and the row and say what the line IS before you write it. Composition is yours to
state; code checks the arithmetic. Definitions follow the MODEL (your minority interests include perpetuals;
your operating profit excludes other income): reconcile against the company's bridge, never the bare label.
Every model is different — reason your own way. Never type over the model's own arithmetic.
Budget: the run's time minus the review's and the finish margin; the clock is the only end; on the clock
every unfilled row lands red "not reached" (never a silent estimate).

## Verification before any run
- Museum exhibits on the real shapes: CLP p23 (opex from four printed lines by the brain's arithmetic; other
  gain 460; the perpetuals into minority interests as a definition), DFE p207 (the 合计 total refused once
  stays refused — the memory line), SOC Accounts!AI7 (a coincidental tie is a candidate, never a write),
  a `set` over a formula cell refused, `done` before coverage refused.
- Replay: record/replay of the mapping turns (as for the review) so the four floors run offline.
- Coverage on the floors: input rows filled + skipped-with-reason = 100%; plain writes only with ties.
- Two live runs on the same documents compared cell by cell: the mapping must agree on every plain cell.
- Independent fresh-context review of the diff, findings fixed and re-verified; diff must remove more than it
  adds (`git diff --stat`).

## Estimate
Build 1.5–2 days on Opus (loop + tools + context, removals, replay, exhibits), review + floors 0.5 day,
two runs. Token cost per run ≈ 0.5–1M for mapping (replacing the card queue's ~1M), inside the hour.

## Risks, said plainly
Coverage (the brain skipping rows) — measured, red on the clock. Formula trap — guarded. Variance — the
two-run comparison is the acceptance test. Time — the clock bounds it; if the brain cannot map a model
inside the budget the run says so rather than guessing.
