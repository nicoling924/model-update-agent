# Build plan — the new agent (proposal, 2026-08-17)

Governed by BOSS_MINDMAP.md + REBUILD.md; tool rulings in TOOLSET_AUDIT.md.
Principle (owner directive): any legacy component with a whiff of
unreliability is NOT reused — rebuilt fresh. Creativity welcome; the novel
mechanisms below are proposals for owner review.

## 1. Scar tissue — every past disease becomes a structural guard

Not prose, not prompts: each is enforced in code or a museum exhibit.

| Disease (run) | Guard in the new agent |
|---|---|
| Silent stale-constant carry (r51 — 4 runs of invisible wrongness) | Rewrite failure → ALWAYS flag; no silent carries, ever |
| Units disease in 9 places (r95–98) | ONE conversion boundary; page-scale detected once, threaded everywhere; no tool compares raw digits |
| Right number, wrong row broke siblings (r37) | All writes transactional: full rescore, auto-revert on any check regression |
| Plug displacement (r37–41 regression) | Plugs only by AGENT decision, sibling-checked first, key cells never plug sites (r38), always flagged |
| Reviewer auto-apply wrote into zero-prior row (r33) | No machine auto-apply exists; Police findings go back to the agent |
| Phase-order clobbering (r33: later stage undid a correct fix) | No phases — one loop owns every write from minute zero |
| Extraction lottery ±5pp (phase 4 verdict) | Digest-once: frozen, validated per-document artifacts |
| Budget burned on one figure (r21, r31; the GPT-5.6 stall mode) | Walk-away discipline: bounded attempts per figure, then the flagged-back-out exit |
| Learner served ZERO for 5 runs on an int(page) bug (r99–103) | Self-announcing tools: every tool reports attempted/served; a zero-serve is surfaced to the loop, never silent |
| Prior-year document poisoning (v10) | Doc-vintage classifier stays; prior docs open only on the restatement path |
| Per-share/twin adjacency poison (CLP dividend) | World-band identity at every join and write |
| Label-first mismatch (r14, r31) | Number-anchored matching only; labels are hints, priors are proof |
| "Not disclosed" laziness (owner-reported) | Non-disclosure claims require a recorded exhausted-search log |

## 2. The shape (what gets built)

ONE thinking loop (Luna) holds the objective from minute zero and calls
tools; no orchestrating state machine. Directory: fresh `agent2/` (name
TBD), museum-covered from day one. Legacy `agent/` and `pipeline/` stay
read-only reference.

**The toolbox** (each self-announcing, unit-converting, citation-carrying):
- `digest(doc)` — one-time frozen extraction artifact per disclosure
- `discover_anatomy(workbook)` — Task A: periodicity, target column,
  forecast-vs-reference sections; reads/writes `_SPEC`
- `auto_join()` — deterministic bulk binding (the 130/130 join, rebuilt on
  digest artifacts)
- `read_page(page)` / `read_scanned_page(page)` — checksummed, signed
- `match_by_implied_prior(row)` — single-year MD&A tables
- `trace(cell)` / `statement_diff()` / `find_value(number)` — investigation
- `set_input(cell, value, citation)` — THE write chokepoint (transactional,
  read-back, world-band, key-protected)
- `plug(check, citation, reason)` — the flagged last resort, agent-invoked
- `flag(cell, kind, note)` / `log_not_disclosed(row, search_trail)`
- `snapshot_forecast()` / `write_report()` — the two comparison tables
- `pause_for_analyst(question)` — restatement stop; resumable state

**The Police** — separate fresh-context pass, 4 laws (announced data,
adjustment logic, balance, keys). Re-derives keys independently from the
digest artifacts and diffs. Findings return to the loop as objectives;
after N unfixed iterations the loop takes the flagged back-out exit.
Engine: Luna (Tera fallback if weak).

## 3. Proposed novel mechanisms (the creative bits — owner to approve)

1. **Evidence-graded writes.** Every number written carries a grade:
   A checksummed-read/joined · B implied-prior/derived-with-tie ·
   C inferred · D plugged. Flags fall out automatically (C/D flagged, B
   noted in _REPORT). Replaces flag-budget arithmetic with provenance
   bookkeeping — a flag can never be forgotten because it is not a
   separate act.
2. **The agent writes its own update plan.** After Task A discovery it
   drafts a short plan (target column, key rows, expected hard spots,
   adjustment sites) and logs it in `_REPORT`. Transparency for the
   analyst + a reviewable record of the agent's judgment. Plans differ per
   model — that is the genericity working, not a workflow returning.
3. **Adjustment-logic inference as diff-of-columns.** The prior actual
   column vs the disclosure's prior figures: every systematic difference
   IS an analyst adjustment; the loop characterizes each (formula, sign,
   scope), replicates it on the new actuals, grades it B, and lists all
   inferred adjustments in `_REPORT` for the analyst to confirm once.
4. **Fingerprint-first repair.** The residual-attribution playbook (2× =
   sign, exact-delta = missing line, ratio = scale) runs as the loop's
   FIRST move on any failed check — the measured fastest route from
   residual to root cause (r115 post-eval: 76.9% → Model 99.1%).
5. **Museum-as-contract.** Every disease in §1 lands as an exhibit BEFORE
   the code that could reintroduce it; the suite is the regression law.

## 4. Build order (each step museum-green + dry-run before the next)

1. **Loop core + toolbox API + write chokepoint** (the spine: always-
   deliver ladder, walk-away budgets, evidence grades)
2. **Digest-once + auto_join + readers** (the proven reading stack,
   rebuilt on the ledger contract)
3. **The Police** (4 laws, fresh context, findings loop-back)
4. **New capabilities**: restatement pause/resume + cross-report section
   mapper; adjustment-logic inference; forecast-comparison tables;
   non-disclosure logging
5. **_SPEC learning** (lean hard-set discovery, guarded serving —
   statement always wins)
6. **Live trials**: DFE + CLP, judged ONLY on the new scorecard (4 Police
   laws / fewest flags / ≤60 min)

## 5. Open items for the owner

- Name/location of the fresh package (`agent2/`? replace `pipeline/`?)
- Police engine trial order (Luna first, agreed; when to judge "not
  going well" → Tera)
- Approve/adjust the novel mechanisms in §3
