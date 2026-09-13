# Morning report — 2026-09-14 (night of the 13th)

## What ran
Both full-year runs on head 70bb04b (the four fixes from your DFE findings + the new report page), on the
pipeline chain. Nothing dispatched after these.

| Run | Time | Delivery | Checks | Keys tied | Red / orange / plugs | Sense check |
|---|---|---|---|---|---|---|
| DFE FY25 · 34771914611 | 23 min | clean | closed, every year | 8/11 | 20 / 33 / 0 | 14 lines watched; net finance costs FIXED from the printed 长期借款; capex, investing, FCF, CFO, tax, DPS, EPS, net profit genuine; operating profit, EBITDA, financing red with trails |
| CLP FY25 · 34772986687 | 30 min | clean | closed, every year | 8/10 | 46 red* / 22 orange* / 0 | 4 lines out of line; FCF and CFO traced to the fuel clause (genuine but unusual); financing (final dividend) and investing (China capex) genuine; one review write taken back (it widened CFO); 3 written up |
\* counts from the scoring below (wrong cells only); the page counts every coloured cell.

An hour was lost first: I dispatched DFE with `tools/dispatch.sh`, which runs the previous-generation
agent (action "updater"). The correct command is the root `sh dispatch.sh <CO> <PERIOD> <PRIOR> rebuild pipeline`;
recorded in memory and RUNLOG so it does not recur.

## Your three findings, on the live DFE file
- Driver!J10 `=16602.97-J11`: **red, with its note** (the constants law's flag now survives the investigator's undo).
- Header rows Driver J4 / J171 / J175 / J179 / J187, Raw financials U80, Model U142 "New orders": **all empty**
  (the never-filled row law is the writer's; zero refusals needed because no card was dealt for them).
- DPS and every cash-flow line **in the sense check** (14 lines watched on DFE, 4 on CLP).
- The PP&E schedule intact (J104 disposal 434.56 kept; the rolled-into-zero rule fires only when a forecast moved).

## Score against the answer workbook (tools/score_inputs.py)
Judged = every cell the agent filled in the actual column (a typed number, or a formula carrying an embedded
hardcode as the constants law defines it) where the reference holds a number. Correct = within 0.5% or 0.5.

**CLP FY25 vs your finished model (CLP Model FY25 (Updated).xlsx)**
1. Filled input cells judged: **282; correct 191 (68%)**
2. Wrong 91: **red 46, orange 22**
3. Wrong and not highlighted: **23** — the list, by sheet (agent → yours):
   - Aus: amortisation 386 → −476; customer retail −294 → −462; finance income 14 → 24; solar 257 → 294;
     Cathedral Rocks 189 → 74; implied wholesale price 103.9 → 109.3; YoY line
   - CN: solar 163 → 148; share of associates 0 → 1,607
   - Final: investment in JCEs −11 → −123; minority interests 5,943 → 9,815
   - HK Sales: gross electricity revenue 34,258 → 35,045; rate reductions 85 → 0
   - India: coal −85 → 112; renewable 6 → 140; grid 77 → −50; one-off 150 → 0
   - SEA: Ho-Ping 181 → 231 (twice) and 1,320 → 264; NED solar 63 → 7 and 2 → 21
   - SOC Accounts: payable 20 → 0; charge/rebate −15,842 → −16,557
   Per sheet (judged / correct): Final 67/48 · Driver 22/19 · SOC 20/19 · HK Sales 19/14 · SOC Accounts 23/12 ·
   ROAFNA 23/18 · CN 42/26 · Aus 38/23 · India 16/9 · SEA 12/3. Full cell list: docs/scores/CLP_FY25_run34772986687_vs_analyst.txt

**DFE FY25 vs the prior agent run (Dongfang Electric Claude Fable 5.xlsx — NOT hand-filled; there is no
hand-filled FY25 DFE workbook, only the 1H25 answer sheet)**
1. Judged **214; correct 207 (97%)**
2. Wrong 7: **red 6, orange 0**
3. Wrong and not highlighted: **1** — Raw financials!U266 间接法差额 (a difference row the agent filled with 152.71;
   the reference has 0). The six red are the Driver segment reads (Wind, New Energy, two segment totals) and a
   non-current disposal loss line — the reference's own numbers there are a prior agent's, not proven.

## What the scores say
- CLP's unhighlighted wrong cells are segment inputs (Aus, India, SEA, CN) read from segment tables without a
  prior tie, and two Final lines (minority interests, investment in JCEs). Those are the next causes to chase;
  each needs its trail read from the run log before any rule.
- DFE's one unhighlighted miss is a difference row: the check-label rule (差额 / 平衡) already keeps cards off
  such rows; a stage-2 serve reached it. To trace.
