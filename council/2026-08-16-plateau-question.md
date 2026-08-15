# Council question: a model-update agent has met its hard objectives but plateaued at 75-79% whole-model — where is the remaining 15% and is the target even right?

## System (one paragraph)

Deterministic Python harness drives gpt-5.6-luna (text+vision) to mark an
equity-research Excel model to actual results from a Chinese annual report.
Retrieval by prior-year value -> holistic block mapping -> code audit ->
objective convergence (sibling-first corrections, learned bridges) -> bounded
agent loop -> integrity gate. A learner calibrates on the PRIOR year (where
the model holds answers) and stores verified row identities in a memory tab.
Overnight arc (5 runs): scanned-statement vision with prior-column checksum,
document+page unit scales, CN glossary, parent-company scope gate, input-site
write redirection — each fix measured and verified offline before dispatch.

## Where it stands (Dongfang Electric, 600875 CN, FY25)

Hard objectives (owner's priority order) TRANSFORMED overnight:
- 2025 balance: PASS (runs 100, 102; never before).
- Forecast-year balance gaps: -27,743 -> -528 -> **-10** (one propagating item left; plus one CF-tie check at -585).
- Key numbers: 3/13 -> 10-11/14. Remaining: operating profit flagged not
  plugged (model 5,046 vs CN 营业利润 4,778 — a genuine definitional scope
  difference; the reference model itself computes ~5,046, so flagging is
  CORRECT behavior); CFI/CFF wobble ±1-4% between runs (served by learned
  1-term bridges whose FY25 replay sometimes lands on a slightly different
  line instance).
- Runtime 37-55 min. A parallel CLP (HK, English, text PDFs) run on the
  identical stack scored 75.0% = its historical band — no regression, the
  generic claim holds.

But WHOLE-MODEL completion oscillates: 79.1% -> 77.3% -> 75.1% (273 evaluated
cells vs a reference). Owner's target: >=90%.

## The reference problem

The scoring reference is itself a prior Claude Fable 5 run, NOT an
analyst-verified model. Adjudicating every disagreement against the filing:
the RUN beats the reference 10-8 (run 100). Examples: run wrote 58,005.4
(printed verbatim in the segment note); reference has 35,779.1 (not printed
anywhere — a different segment basis, possibly external-revenue vs total).
~31 of 62 disagreements are "neither printed" (computed/derived rows).

## The remaining wrongness (51 Driver-page cells, fully classified)

1. ~17 cells: product-segment splits (Wind/Thermal/...). The FY25 MD&A
   分产品 table prints FY25-only values in 万元 (10^4) with % changes — NO
   comparative column. Prior-value triangulation is impossible on the new
   document. The model's own prior-year values ARE printed in the FY24
   filing's equivalent table.
2. ~18 cells: operating statistics (production/sales/inventory triplets in
   raw MW units, one table, FY25-only + % changes). Same single-year problem.
   The values the reference used are printed verbatim on that page.
3. ~12 cells: PPE/intangible roll-forward details from note tables
   (addition/disposal/transfer) — moderate misses.
4. ~4 cells: narrative order-book numbers printed as 亿 (e.g. 734.76亿元 ->
   model 73,476) in prose, not tables.

Attempted fix that failed silently: the learner was given a SINGLE-YEAR
identification fallback (match the row's known FY24 value in the FY24 doc's
own tables at per-page unit scale, store label+page as a hint). Result:
0 stored — in fact the learner's identification stage has stored 0 verified
rows in 4 consecutive runs (was 19 before vision was added), with 0 rejected
too, meaning every LLM identification answer fails the first filter
(status != OK or no line text returned). A diagnostic print ships next run.

## Constraints

Pure gpt-5.6-luna; widely available Python libs only; generic across
companies (no per-company code; a learned per-company memory tab is fine);
~2 more runs (~$2, 40-55 min each) before the owner's morning deadline
(management presentation of a WORKING GENERIC agent).

## Questions

Q1 — The 90% question. Given the reference is provably wrong on ~8-10 cells
and ~31 disagreements are analyst-derived values printed nowhere, what is the
HONEST framing of "completion rate" for the morning presentation, and what
raw-% is realistically reachable in 2 runs? Should scoring exclude or
separately report analyst-derived rows (values not printed in the filing)?

Q2 — Single-year tables. For MD&A tables that print ONLY the current year
(segments in 万元, operating stats in MW): what is the most reliable generic
mechanism for a weak LLM to fill those model rows correctly? Options we see:
(a) learner identifies rows on the PRIOR-year document (values known there)
and hands (page, label, table-position) hints to the update mapper;
(b) update-time label+structure table reading with per-page unit scale told
to the reader; (c) both. What verification gates a single-year read when no
comparative exists — % change columns? cross-footing? Anything better?

Q3 — Bridge replay wobble. Learned 1-term CF bridges (statement line ->
model row) sometimes replay onto a slightly different line instance in the
new document (CFI off 1.3%, CFF off 8% in one run but fine in another).
What replay verification pins the RIGHT instance (the statement page? the
value that ties to the balance-sheet cash delta?)?

Q4 — Priorities. Rank what to do with the last 2 runs before morning, and
what to SAY at the presentation about the gap between hard-objective success
(balance/keys) and whole-model %.

Answer concretely; flag anything you think the other members will get wrong.
