# Boss mindmap — model update agent (2026-08-17, verbatim from owner)

**Status: GOVERNING OBJECTIVES DOCUMENT. Supersedes prior acceptance-criteria
framings where they conflict. Recorded verbatim; clarifications from the
grilling session are appended at the bottom, never edited into the original.**

---

## Why do we need the agent? → forecasting

Analyst will use the model to do the following task:
- Compare with previous forecast of that year of key numbers
- Analyse growth trend of key numbers
- Project the expected growth rate of the key numbers

## Task of the agent

### A: First need to understand the model structure (modelling is an Art)
- Forecast time (Quarterly / Half yearly / annually?)
- Forecast sheet (P&L? Balance Sheet? CF Statement)
- Which year to update? (based on the model, e.g. if 2024 has the most
  hardcode inputted, then it's likely 2024 is updated and we are updating
  2025) → the agent has to be able to figure which year to update → some
  models work by Q1-Q2-Q3-Q4-FY, so the agent needs to figure out by itself
  which one to update
- P&L items of Quarterly/Half yearly → see if they are for forecast or if
  they are only for reference → e.g. some analyst's sales breakdown has to
  be done each quarter, while some only need to be updated annually

### B: Identify if there are any special condition — Restatement
- When the agent identifies any restatement in the financial doc, it will
  STOP COMPLETELY and ask the analyst to provide the previous financial
  report → in order to identify where the numbers come from so that it can
  map the numbers in the current period
- It also has to ask the analyst whether he wants to restate the numbers in
  the model → it has to warn the analyst that restating data could impact
  the model → as operational data are not restated and if the financial
  data is restated, then they may not reconcile → only restate the previous
  data if the analyst agrees

## Key required output from an updated model

### 1. Model balanced → the 3 statements have to reconcile; no accounting errors
- Make sure ALL years and all quarterly/half-yearly/annual balance sheets
  are balanced
- If numbers are not found or unable to do so, BACK OUT the numbers and
  MARK them for the analyst to check

### 2. Key numbers have to be updated correctly
- Key numbers include: Sales, sales segmental breakdown, gross profit,
  gross profit breakdown, net profit, cash balance, current-and-non-current
  assets and liabilities, equities, operating, investing and financing
  cash flow
- The agent has to be able to identify the KEY DRIVERS of the model and
  make sure they are updated correctly → key drivers are hardcodes /
  embedded hardcodes that affect the key numbers

## There has to be a [Police] in the agent

To make sure of the following:
1. Company announced data have been updated correctly based on the
   company-released financial statement
2. Analyst adjusted numbers have been updated according to previous
   adjustments → have to find out the LOGIC of the adjustments
3. The model has to be balanced
4. The key numbers have to be checked to be correct

---

## Clarifications from grilling (appended, dated)

- **2026-08-17 · Delivery semantics:** the agent ALWAYS delivers — refusal is
  dead (only exception: the restatement full-stop). No flag budget, no
  quarantine. Core rule: never a wrong unflagged number. On any issue (e.g.
  unbalanced BS) the agent must REASON and FIX it itself — trace the
  statements, find the cause, solve it — not refuse. True for all inputs and
  issues. If truly unsolvable: back out, mark, still deliver.
- **2026-08-17 · Forecast years:** never re-forecast — analyst's forecast
  drivers stay untouched; obsolete driver → flag, don't change. EXCEPTION:
  if forecast years break (e.g. 2026 BS unbalanced after updating 2025, from
  a roll-forward error or an error in the 2025 column), the agent must
  reason, find the error, and fix it — which MAY include editing the
  forecast column. Not a hard no-touch rule; touch only to fix integrity
  (balance etc.), never to change the forecast view.
- **2026-08-17 · Analyst adjustments:** agent infers the adjustment logic
  from the model itself (how the prior actual column adjusts the reported
  figure), replicates it on the new actuals, flags if uncertain. No need to
  ask the analyst.
- **2026-08-17 · Restatement pause = RESUME, not rerun.** Detect early via
  comparatives-vs-model scan; pause; ask (a) for the prior-year report,
  (b) restate yes/no. YES → restate history, continue. NO → the analyst
  method: use the UNRESTATED prior report (e.g. FY24 AR) to locate which
  section/table each model line was sourced from, then find the matching
  section in the new (restated) report and take the current-period value
  from there — cross-checking restated vs unrestated statements — and flag
  the mismatched comparatives. Work done before the pause is kept.
- **2026-08-17 · Police loop:** structure (deterministic vs LLM review) left
  open — owner unsure. Confirmed behavior: Police flags an issue → agent
  goes back, reasons, finds the cause, fixes with the correct number. After
  a FEW ITERATIONS without a fix → resort to backing out: a plug to balance,
  or a back-out so a =SUM matches the disclosed figure — always flagged for
  the analyst. Escalation ladder: correct number > reasoned fix > flagged
  back-out/plug. Never endless looping, never refusal.
- **2026-08-17 · Measurement:** completion rate is OMITTED as a metric — not
  all cells are equally important; key numbers + segment breakdowns deserve
  the attention. A run/champion is measured on: (1) pass/fail on the 4
  Police rules (all must pass), (2) tiebreaker = fewer backed-out/flagged
  cells, (3) time ≤60 min as ceiling only.
- **2026-08-17 · Stale non-key cells:** disclosed → update. Genuinely not
  disclosed this period → leave stale, NO cell flag, one line in _REPORT
  ("not updated this period"). Flags reserved for uncertain/derived numbers.
  GUARD: "not disclosed" must be PROVEN, not asserted — past agents lazily
  labeled "unable to find" as "not disclosed" when the figure WAS in the
  document. The agent must show where it searched (cascade exhausted) before
  claiming non-disclosure.
- **2026-08-17 · Forecast comparison in _REPORT:** agent snapshots the
  pre-update model. For an FY25 update the _REPORT shows BOTH: (a) FY25
  previous projection vs FY25 actual, and (b) old FY26 projection vs new
  FY26 projection (how the forecast moved after actuals flowed through).
  Re-projection itself remains the analyst's job.
- **2026-08-17 · Rollout:** NO per-model onboarding. First run self-discovers
  the model structure (Task A) and persists learnings to the hidden _SPEC
  tab. The analyst only ever answers restatement pauses and reviews flags
  after delivery.
- **2026-08-17 · Engine:** prefer pure gpt-5.6-luna for BOTH updater and
  Police/reviewer. Fallback: if Luna-as-reviewer doesn't perform, Luna
  updates + Tera reviews.
- **2026-08-17 (evening) · Keys clarification (owner, reviewing run 7):**
  the key-number list in "Key required output" is to be read with SPECIAL
  ATTENTION on: operating / investing / financing cash flow, and the
  segment breakdowns of sales AND gross profit. For KEY numbers a flag
  does not excuse a wrong or stale value — "correct-or-flagged" is the
  standard for lesser rows; keys must be CORRECT (updated and tying the
  disclosure). Segment breakdowns must be UPDATED from the MD&A/segment
  disclosures (implied-prior identity for single-year tables), not left
  stale-flagged.
- **2026-08-17 · Fresh start:** NO champion re-scoring — the old champion
  agent (stable-run105) is retired; "the agent of the champion is not good
  at all." We start new. Purpose of this mindmap: Fable 5 understands the
  owner's objective, communicates it to the agent (Luna), then decides what
  TOOLS to give the agent to support its work. Objectives first, tools
  second.
