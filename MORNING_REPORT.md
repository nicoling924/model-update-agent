# Morning report — overnight 2026-08-20 (SoC sub-model session)

## The one-line summary

The Scheme-of-Control sub-model — the last structural CLP gap — is
closed: the four SoC sheets went from 57 wrong cells (run 7) to a
stable ~90-93% agreement with your hand-completed model in confined
tests, the SoC core panel scores 6/6 deterministically, and **CLP run 8
is in flight** on the new head (all gates green, fingerprint-verified
dispatch). Fable-diff runs when it lands.

## What the night found (and why it was generic, not SoC-specific)

Run 7's ~57 SoC diffs collapsed to **8 stale input cells** — everything
else was formula fallout. The 8 stales shared four *generic* root causes:

1. **Evidence ranking was first-come, not statement-anchored.** A prior
   like 80 ties dozens of junk lines in a 300-page report; the 2-slot
   evidence cap filled in page order and the real line (p236, the SoC
   statement) never reached the agent. → **Home-page discovery**: pages
   that mass-print a sheet's prior column ARE that sheet's own statement
   (found by number mass — no captions, no language, works for any
   company's supplementary schedules and five-year tables). The card now
   carries the sheet's own statement as a transcript; evidence from home
   pages outranks everything; a unique cent-exact [current, prior] pair
   on a home page serves deterministically (red).
2. **Note references offered as values.** "Fuel clause account 20
   (1,043)" — the oracle called 20 the row's "agreeing print". Closure's
   note-column law now strips note-ref leads at the join pool, one choke
   point for every consumer.
3. **Model design the guards didn't know.** Design-mirror rows (two rows
   holding the same figure by design — local peak / system demand) are
   now exempt from the duplicate-print guard when priors are identical;
   conversely a zero-prior row may no longer take an abs-value a sibling
   already owns (the provision 90 was being double-counted 11 rows away).
4. **Event rows** (capacity retirements, one-off rebates) now taught:
   stale is an assertion the event repeated; no same-kind event this
   year = write 0 with a note. (Your CAPCO −1,050 retirement no longer
   haunts 2025.)

Plus two referee-precision fixes both companies inherit: the oracle's
identity floor tightened 0.6 → 0.05 (cent-exact; it was manufacturing
false "agreeing prints" against small priors) and the home-statement
seatbelt (a write contradicting the sheet's own statement is refused
with the line quoted).

## Confined-test scoreboard (6 iterations, zero cloud runs burned)

| Iteration | SoC core panel | Note |
|---|---|---|
| run-7 baseline | 0/6 | all 8 inputs stale |
| 2 (home pages + blocks) | 3/6 | tariffs + event-row landed |
| 4 (note-strip + home join + mirror) | **6/6** | fuel-clause −1,043, SOC −90, mirror 7,455 |
| 5-6 (zero-prior guard, swap coercion) | 6-7/10 extended panel | SOC sheet perfect (0 diffs) |

Remaining knowingly-open (honest red flags, all listed in _REPORT):
- HK Sales tariff cells (98.0 / 46.3): the model's year-end priors print
  NOWHERE in the FY25 docs (the five-year table prints *averages* with
  different priors) — irreducibly the counterpart-law judgment; Luna
  writes-with-red or flags-stale run to run. Both honest.
- ROAFNA "Other assets" (both pattern constants moved) and the fuel-mix
  allocation splits — analyst-judgment territory, red-flagged.
- DFE benchmark caught home_serves touching a printed key (net profit)
  before dispatch — keys are now out of grade-C jurisdiction entirely.
  Both companies' full benchmarks green after the fix.

## Open questions for you (unchanged from last night, plus none new)

1. DFE Driver J6 scope (58,005 new-category total vs 35,779 sub-row sum).
2. The rollover design-formula question (HK Sales!7 '=AH7' carry is the
   same class: should the actual column inherit the prior ACTUAL column's
   formula pattern instead of the forecast's carry?).
3. CLP ±1,765 CFO/CFF interest reclassification binding.

## Run 8 result (landed 2026-08-20 morning)

**82% whole-book agreement with the hand version (1073/1305) — campaign
best, up from 75%.** SOC sheet perfect 49/49; HK Sales 70/71 (the tariff
judgment cells landed as red-flagged writes); fuel clause −1,043 correct.
Remaining weak sheets: Aus/SEA/India (65-67% — allocation-split judgment
rows) and Driver (68%). Run id 32313308199, fingerprint verified. A
duplicate dispatch (retry after a sandbox keychain failure masked the
first dispatcher's output) was caught and cancelled before it scored.

---

# Morning report — overnight 2026-08-19 → 20 (extraction-first campaign)

## Where things stand (as of run 32, in flight)

**DFE progress across the night's runs (all fingerprint-verified):**

| Run | Keys at print | Previous-mistakes set | Balance | Note |
|-----|---------------|----------------------|---------|------|
| 29 | **10/10** (first ever) | 9/12 | 1 fail (segment sum −9) | segment estimates leaked under residual pressure |
| 30 | 7/10 | 11/12 | twin re-entered via stage-3 | the 其中 sub-line's last door |
| 31 | **10/10** | **12/12** | NEW: one line written into two sibling rows | the campaign target met, minus one new class |
| 32 | 10/10 | 9/12 | off by 23 (FX-into-RE write) | double-count guard held; guards get re-phrased around |
| **33** | **10/10** | **12/12** | **ALL YEARS PASS** | **keys law PASS (27 proven) — THE BAR. Rebased block = state** |

Every failure was closed at its fundamental, teaching-first, referees for
what the engine drops (owner-ratified boundary: code proves/refuses,
never maps). New laws since the mandate: segment-estimate refusal at the
key leaves, swapped constants must be printed numbers, never-silent
blank/embedded rows, lazy-ND fact-check, stage-3 consensus filter
(pool's agreeing print overrides a lone reader), duplicate-print guard
(one printed line lives in ONE row), per-column closure, note-column
detection + cumulative-subtotal carry (P&L anatomy), bilingual closure
grammar. Museum: 110 exhibits green.

**The confined-run harness (tools/minirun.py)** — same engine, same
code, restricted packet list — took the previous-mistakes set from 4/12
to 12/12 across 9 cheap iterations (~5-20 engine calls each, zero cloud
dispatches) before any full run flew.

## CLP (genericity leg) — self-onboarded, benchmark GREEN, not yet flown

- **Council #6** (transcript in council/): key discovery = LLM nominates
  by meaning, code certifies by prior-identity + constellation +
  uniqueness. Built as updater/onboard.py (generic, zero CLP code).
- CLP self-onboarded **5 certified keys** (revenue, operating profit,
  net profit, EPS, total equity — all on 'Final', constellation 5).
  Cash correctly UNBOUND: the model holds `=4976+23` — an analyst
  adjustment riding the printed 4,976 (the UBS-adjustment class working
  as designed).
- Genericity gaps found and fixed OFFLINE (no run-hours spent): English
  closure grammar (net-cash rows ARE the section equations), note-ref
  columns ([note, cur, prior] detected per table and shed), cumulative
  P&L subtotals (carry-in), FY24 AR provisioned as the last-year map
  (57/67 open rows now hinted).
- **CLP benchmark: ALL LAYERS GREEN.** Ready to fly on your word — or I
  fly it once run 32 confirms DFE holds (the mandate's sequence).

## Open items for your ruling
1. DFE segment block: correctly stale + RED awaiting your re-basing
   decision (DFE merged its categories; the new partition is recorded in
   _REPORT — the restatement-class question).
2. CLP cash: bind with the +23 adjustment inference, or leave unbound?
3. Run 31 took ~3h (engine latency spikes; runs 29/30 were ~50 min) —
   the 30-60 min target holds normally but not under provider latency;
   if this recurs, options are parallel chunk calls or a latency-aware
   budget.

## Cost discipline
Zero legacy-chain incidents since the canonical dispatcher; every run
sha-asserted and fingerprint-verified; all iteration between runs was
confined tests and offline benchmarks.


## CLP first flight (post-run-33, fingerprint-verified, ~75 min, 244 calls)

**Genericity: the machinery ran end-to-end on a completely different
anatomy with zero CLP-specific code** — English filing, multi-sheet
country/segment workbook, 157/163 priors located, compile packets across
10 sheets, honest flags everywhere, revenue bound+written EXACT (88,018).
Zero key mismatches (nothing wrong was written).

**The CLP gaps list (the diagnostic's product):**
1. CLP's consolidated keys are SUMS OF THE COUNTRY SHEETS — NP/OP/EPS
   understate because the country sheets are only partially updated
   (41 rows written; many honest not-disclosed on CN/SEA/HK Sales).
   The next campaign: mapping the AR's regional business-review sections
   into the country sheets (the multi-sheet anatomy challenge).
2. CFO/CFI/CFF unbound at onboarding — the nominate round missed the
   Final sheet's CF rows; needs a second nomination pass scoped to CF.
3. Balance: Final!99 off 560 (2025) and ~33k in forecast years — partial
   segment updates disturb the roll-forward; same class DFE had before
   its campaign.
4. Cash binding awaits the owner's ruling (+23 analyst adjustment).

DFE took a 33-run campaign to reach its bar; CLP starts from "runs
end-to-end, honest, shallow" — the campaign infrastructure (confined
runs, benchmark, museum) is ready to iterate it the same way.

## CLP campaign day 1 (post-DFE-close)

Laws built, all generic, museum-pinned:
- **The 2D matrix join**: segment notes printing regions ACROSS columns
  are re-read as position-true grids (text-strategy keeps empty cells);
  a row's prior anchors row+column, the sibling matrix serves the same
  column; multiple anchors must AGREE. Verified live: Australia revenue
  34,191 exact.
- **The row-shape law**: rows with >=5 numbers refuse the 1D slot-by-tie
  (matrix neighbours are regions, not [cur, prior]) — this was writing
  Mainland's number into Australia with grade-A confidence.
- CFI key certified; CFO/CFF correctly refused: the model reclassifies
  ±1,765 between operating and financing (the mindmap's interest
  example, live) — law-2 adjustment work queued.
- EBITDAF class: two tables disagree (EBITDAF vs operating earnings) —
  the machine refuses definitional forks and leaves them red for
  judgment, as designed.

CLP run 2 in flight with all of it. DFE closed at run 36 (delivered);
owner review pending on J6 scope + the rollover-design-formula question.
