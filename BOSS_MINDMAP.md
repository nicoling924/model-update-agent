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

## Special situation: RECLASSIFICATION (owner addition, 2026-08-24)

Distinct from restatement. A RECLASSIFICATION is when the current period's
PRESENTATION changes — segment/breakdown categories are cut differently
in 2025 vs 2024 (e.g. Dongfang's sales breakdown) — while the prior-year
numbers in the model are NOT contradicted.

- The agent does NOT stop for a reclassification (owner ruling
  2026-08-26, final): map the segments the reclassification left
  UNCHANGED (the bridge-proven survivors); for changed segments that
  cannot be mapped, BACK OUT the number (= total − mapped members, as a
  visible formula) and flag it for the analyst. NEVER write the
  company's re-based category value into the model's narrower row —
  the model's classification is never changed, in any case.
- The agent must NOT alter the model structure — no new rows, no changed
  row/column headers, no re-basing of the model's categories. Structural
  changes are the ANALYST'S work.
- If it cannot map an item by meaning, it simply backs the number out
  (orange) or leaves it flagged (red) — it never stalls the run and never
  invents structure.

Rule of thumb: restatement = the PAST changed → full stop, ask.
Reclassification = the PRESENTATION changed → map by meaning or back out,
flag, keep moving, never touch structure.

## Balance-first placement (owner ruling 2026-08-26)

When a PROVEN printed amount has no exact home in the model (a NEW line
the model never carried, e.g. perpetual capital securities inside the
equity section), it is MORE important that the model balances than that
the amount waits homeless: put it in the BEST-FITTED existing row (the
row whose section the printed line sits in), flag it RED with a note
naming what was folded in, and the analyst decides its final home.
A balanced model with a flagged best-fit beats an unbalanced model with
a homeless number.

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
- **2026-08-18 · The look-elsewhere skill (owner, reviewing the segment
  design):** one table (e.g. the p13 分产品 grid) will not carry all the
  segment answers. The agent must have the ANALYST'S SKILL of searching
  other places when the first place lacks the figure — segment note,
  statement notes, five-year summary, other MD&A tables — as its own
  reasoning ability (it can ASK for more places), not as a fixed
  retrieval list. "If we can't find our specific data in one place, we
  will find another place."
- **2026-08-18 · Same-page completeness (owner, run 23):** if the agent
  can map total assets it must map total liabilities — same statement,
  same page. Stale rows inside a statement whose neighbors mapped are an
  ingestion/mapping failure, never acceptable.
- **2026-08-18 · Last-year report as the location map (owner, run 23):**
  use last year's financials to learn WHERE segment (and other) numbers
  live — keywords, tables, sections. Current-year reports usually print
  only current-year segment breakdowns, so the prior report is the map
  to where the numbers are found.
- **2026-08-18 · BACKOUT rules (owner):** for most situations the KEY
  NUMBERS should NOT be backed out — they are announced and provided.
  Back out a key only under a special condition. ADDED CONDITION #1:
  INCOMPLETE FINANCIAL DATA — companies sometimes provide incomplete
  data in results announcements / quarterly statements; in those cases
  key numbers may be backed out.
- **2026-08-18 · Backout clarification (grilling):** full annual report →
  key numbers are NEVER backed out (all are available in the statements;
  find them or leave the key failing loudly). Backout of keys is allowed
  only for reports CONFIRMED incomplete (e.g. an announcement with no
  cash-flow statement) — the agent may confirm incompleteness
  deterministically (a whole statement absent from the document set),
  states it in _REPORT, and backs out flagged orange.
- **2026-08-18 · Understanding model structure — adjustments (owner):**
  the model sometimes classifies key numbers differently from company
  management (e.g. interest expense in operating vs financing cash
  flow). The agent must understand HOW these numbers are derived while
  understanding the model. A correctly-inputted model can still show
  CFO/CFF that do not match the annual report BECAUSE of the model's own
  adjustments — the agent must understand what the adjustment is, and
  whether the number is correct even without the adjustment.
- **2026-08-18 · Adjustments clarification (grilling):** the agent
  reasons out WHY a total doesn't match by TRACKING PRECEDENT CELLS
  (follow the formula chain to the classified components). If the prior
  year's figure matches the company-announced figure, it is HIGHLY
  LIKELY there is no UBS adjustment — the deviation is then an error to
  find and fix, not a design to preserve. When a deviation equals one
  nameable item, name it, quantify it, and present the classification
  question in _REPORT rather than forcing or ignoring.
- **2026-08-18 · Segment breakdowns — multi-table persistence (owner):**
  the segment breakdowns exist in MULTIPLE tables scattered across the
  report. Failing to find in one table must never end in a stale figure
  — look for multiple datapoints across the report for the breakdown and
  the other key numbers. If a number is in the model as a HARDCODE, it
  is highly likely findable in the disclosures.
- **2026-08-18 · Segment terminal state (grilling):** when a segment row
  is genuinely unfound after exhausting multiple tables in all documents,
  the terminal state is STALE + RED FLAG — never an estimate. (This
  supersedes the earlier prior-structure-estimate teaching: the owner
  wants no estimated segment writes.)
- **2026-08-18 · Ingestion ability (owner):** the agent misses numbers
  that are easily found in the report — the ingestion layer must read
  the statements at Fable-5 grade (whole pages, complete, verified), not
  as scattered retrieval.
- **2026-08-17 · Fresh start:** NO champion re-scoring — the old champion
  agent (stable-run105) is retired; "the agent of the champion is not good
  at all." We start new. Purpose of this mindmap: Fable 5 understands the
  owner's objective, communicates it to the agent (Luna), then decides what
  TOOLS to give the agent to support its work. Objectives first, tools
  second.

- **2026-08-30 · Reclassification back-out recipe (owner ruling, final):**
  Reclassification = the TOTAL is unchanged but the item classification
  changed. (1) Map a segment ONLY if both its name (trivia-normalized:
  spacing/full-width/furniture ignored, any word change fails) AND its
  prior-year comparative match the model — i.e. only segments the
  reclassification did not touch. (2) Everything else is backed out:
  non-plug segments = prior year × the disclosed TOTAL's growth rate
  (formula, orange); the SMALLEST backed-out segment is the plug
  = total − all other segments (formula, orange) so the table always
  sums to the disclosed actual total. (3) A plug that turns negative or
  swings wildly vs its prior year is still delivered (the total must
  tie) but escalated RED with the question — a weird plug usually means
  a mapped segment is wrong. (4) The company's re-cut category figures
  are IGNORED except their total — the model is never re-based. 
  (5) Applies to every segment table that sums to a disclosed total
  (sales split, gross profit split, segment profit), each using its own
  total's growth rate.

- **2026-08-30 · Assumption-freeze law (owner ruling, roll-forward):**
  Forecast growth/ratio ASSUMPTIONS must never rebase onto the new
  actual through the model's wiring (2026E growth =U5 silently becoming
  70% because 2025 came in at 70%). At roll-forward, FREEZE to a
  hardcode at its PRE-UPDATE value every forecast cell that is
  (a) percentage-formatted AND (b) a formula referencing the newly
  actual column or earlier. A % cell computed within its own column
  (=V7/V4, a margin output) is wiring — never frozen. Chains inherit
  the freeze (W5=V5 stays a formula and correctly reads the frozen
  30%). Every frozen cell: orange fill + listed in _REPORT with its
  old formula and frozen value, so restoring the live link is one
  paste. Freeze all qualifiers by default; the analyst restores the
  ones they deliberately want live.

- **2026-08-30 · The sense-check stage (owner ruling, final feedback):**
  A built-in review step for agent AND analyst. After the update, code
  computes the what's-changed table and its flags (sign flips, big
  gaps, >20% moves). The agent must then go back once more and review
  each flag adversarially — is the change justified by the disclosure,
  or a mistake? One verdict per flag: JUSTIFIED (reason) / SUSPICIOUS
  (analyst should look) / ERROR FOUND (cells named, red). Verdicts are
  printed on the _REPORT beside the flags — never silently fixed. The
  walk-away rule applies: one investigation pass per flag.

- **2026-08-31 · Every run is the FINAL run (owner ruling, session brief):**
  No run is a test. Each run aims to be the final, deliverable run —
  mistakes and errors are not expected or budgeted for. We run multiple
  times on different models ONLY to (1) surface issues we didn't expect,
  (2) prove the agent is generic enough to adapt to different models,
  (3) measure accuracy and time required. The agent launches to the
  whole department; the mission is replicating what Fable 5 can do on a
  less sophisticated brain. LARGE changes to the agent are welcome when
  they serve the fundamental objective — but NEVER just patch the
  issue: every fix must be generic and fix the underlying fundamental
  cause before it is pushed.

- **2026-08-31 · The tier law (owner ruling, CLP campaign):** effort
  follows the WIRING. A deterministic trace from the key rows through
  the forecast column's formulas marks every upstream row the model
  actually consumes (LOAD-BEARING: segment revenue, segment earnings —
  what IFRS 8 guarantees is published). Load-bearing staleness is
  neglect and must be adjudicated. Everything outside the trace is
  tier-3: NEVER searched, held at the group's growth as an orange
  traceable formula (the reclass recipe's cousin), trued up when
  detail appears. Companion guard: a forecast driver computing
  sign-absurd (negative where both actual years are positive) freezes
  at its pre-update value, orange — upstream noise never becomes a
  forecast.
