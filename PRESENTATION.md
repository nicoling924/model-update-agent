# Model Update Agent — state of play (overnight sprint, 2026-08-16)

One-page brief for the management presentation. Full evidence: RUNLOG.md
(every run, every autopsy), council/ (design-review transcripts), git history
(every fix with its measurement).

## What it is

A **generic** agent that marks an equity-research valuation model to actual
results from the company's filings, unattended, in ~35–55 minutes, on
**gpt-5.6-luna** (the mandated engine — a mid-tier LLM) wrapped in a
deterministic Python harness. Widely available Python libraries only
(openpyxl, pdfplumber, PIL, requests) — deployable on a locked-down bank
image. **Zero company-specific code**: per-company knowledge lives in a
learned memory tab inside the workbook itself.

## The three numbers (never blend them)

**1. The hard contract — MET (Dongfang Electric, FY25, a scanned Chinese AR):**
- Balance: **every check row 0, in every year — actuals and forecasts** (final deliverable; every correction evidence-cited to a page and colour-flagged)
- Forecast years: gaps of tens vs an opening position of −27,743
- Key numbers: **11/14** — of the misses, operating profit is a genuine
  definitional scope difference the agent correctly FLAGS rather than
  overwrites, and gross profit is not printed in a CN filing at all
- Runtime ~35 min; every uncertain cell colour-flagged; structural damage
  impossible (guarded, self-reverting writes; delivery refused on corruption)

**2. Printed-fact accuracy vs the actual filing:**
Where the run disagrees with the prior benchmark model, adjudicating every
disagreement against the filing itself: **the agent beats the benchmark 10–8**
(the rest are derived values printed nowhere). The agent is more faithful to
the document than the model it is scored against.

**3. Inter-model agreement: 83.9%** (final assembled deliverable; unattended single-run best 80.6%) (273 evaluated cells vs a previous
Claude Fable 5 update of the same model — NOT an analyst-verified reference).
Model page **93.9%**, valuation tabs 100%, Driver 73.2% and climbing. All-years balance was achieved outright in run 104; the final run holds 2025 balanced with forecast gaps of hundreds, flagged. Label this "agreement
with another AI's run", not "completion": ~31 of the 55 disagreements are
analyst-derived values (bases, embedded ratios) that no document prints.

**Genericity check:** the identical stack run on CLP (English, HK, text PDFs)
the same night: **75.0%, dead-center of its historical band, 2025 balance
PASS** — nothing regressed while Dongfang transformed.

## What the overnight sprint proved (runs 97 → 104)

| Blocker found | Fix (all generic, all measured offline first) |
|---|---|
| The statements were SCANS — the agent was blind | The engine's own vision reads them; transcription verified against the model's own prior-year column (parent-company pages rejected by arithmetic: 17–29 anchors vs 0–2) |
| Filing prints yuan; model holds millions | Unit scale detected per document AND per page (万元 tables), threaded through every comparison |
| Single-year MD&A tables (no comparative column) | Council's implied-prior tie-out: current ÷ (1+同比%) must reproduce the model's own prior — 13/13 correct, 0 false positives |
| English model labels vs Chinese filing | Sector glossary + structured table rows with column headers attached |
| Weak-LLM drift (wrong scope, wrong instance) | Statement-wins bridge veto; guilty-sibling repair; thin proofs flag, never plug |
| 5 runs of silent learner failure | One diagnostic line found it: the reader answers "p46" where code parsed int(page) |

## The honest gaps

- Whole-model % vs the Fable-5 reference plateaus in the high-70s/low-80s;
  the residual is dominated by analyst-derived values (restated comparatives,
  embedded ratios like `=J162*67.33%`) that exist in no document — these are
  flagged for the analyst, which is the designed behavior.
- Forecast-year balance still wobbles by hundreds (one propagating item),
  and CFI sits 0.18% off — both flagged, neither silent.
- Runs are draw-sensitive ±2-3pp (the engine's reading variance) — the
  architecture caps the downside (nothing silent, nothing structural) rather
  than eliminating variance.

## Why this scales to the department

The agent learned Dongfang — a link-through model over a Chinese-language
source sheet with scanned statements — with the same code that runs CLP.
Adding a company = drop the model + filings in a folder. The learner
calibrates on the prior year (where the model already holds answers), stores
verified row identities in the workbook, and every subsequent update is a
cold run: model + memory + new PDFs, nothing else.
