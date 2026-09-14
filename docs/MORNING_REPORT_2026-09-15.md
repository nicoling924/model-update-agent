# Morning report — 2026-09-15 (night of the 14th)

## The deliverable: CLP FY25, run 34892926478 (head 7a733f1, 49 min)
Model: the artifact of run 34892926478, `CLP Model FY25 (pipeline).xlsx` (sent in chat).

| Test | Result |
|---|---|
| 1. Balanced every year | Balance sheet closed in 2025 and every forecast year. One open check: ROAFNA!31, your own schedule check, already off −1,264 before the update (now −968); the brain judged it a question for you rather than plug it. |
| 2. 2025 key numbers | 9/10 tie the print and equal your workbook: net profit 10,468, recurring 10,909, revenue 88,018, EPS 4.14, DPS 3.20, total assets and total liabilities & equity 238,644, total equity 107,610, investing −14,328. Operating profit ties the print (14,272) where your model computes 13,812 — a definition difference, reported. |
| 3. Rollover swings sense-checked | The ending loop ran 8 rounds; every headline line out of line has a verdict on the report page: tax FIXED (CN thermal read from the print, gap 261 → 10 points), pre-tax and operating profit GENUINE, EBITDA genuine but unusual, free cash flow and operating cash flow RED for your ruling (receivables), financing genuine, net profit / EPS spread. Next year's forecasts are sane: net profit +7% vs your old forecast, no explosions. |

Other cells: 255 judged, 151 correct (59%); wrong 104 = red 73 / orange 17 / unhighlighted 14. Not the 90%
aimed at. The unhighlighted are the same classes as before (your own derivations and definitions: retail
EBIT in AUD, minority interests incl. perpetual securities, dividends line, JCE investment, India one-off,
SEA renewables/opex, CLP Power capex).

## What changed tonight (all offline-green before each run; 4 CLP runs + 1 DFE)
- **One ending loop** (`consequence.run_ending`) replaced nine stacked mechanisms: measure the objectives
  (balance every year, keys, swing lines) → the brain decides the biggest break with the movers and the ways
  → code verifies → repeat; stops itself. Every round verified the same way; balance > keys > swing lines.
- **The brain judges every name-mismatched tie** in one call (a doubt lands red, never deleted).
- **The reader sees each row's place in the model** (sheet, section headers).
- **The rung card** offers your estimate AND last year's actual as fallbacks; a proven figure is never traded
  for a guess.
- **Prose money in the model's units** (HK$390 million → 390, not 390,000,000).
- Tolerance and verification fixes found by the runs themselves (CHECK_TOL 0.5; a half-done fix is taken
  back; a widened swing line vetoes a sense pick only; the share-of-total rung needs a typed total).

## Run by run
| Run | Delivery | Keys | Score | Lesson |
|---|---|---|---|---|
| 34874944306 (51 min) | clean | 9/10 | 59% | the name judgment deleted 11 right numbers → a doubt is a flag |
| 34880517810 (50 min) | 2 open | 9/10 | 61% | a 0.03 residue counted as a new failure → tolerance 0.5; verify against the objectives |
| 34887799324 (47 min) | 1 open (ROAFNA!31) | 9/10 | 61% | HK$390 million landed as 390,000,000 → prose in the model's units |
| 34892926478 (49 min) | 1 open (ROAFNA!31) | 9/10 | 59% | the deliverable |

## DFE FY25 proof run 34897890192 (34 min): nothing broke
Delivered; keys 8/11 (as every floor); 0 plugs; score vs the prior agent file 192 judged, 180 correct (94%),
wrong 12 all red, unhighlighted 0. One open check: Driver!J139 off −19, which the brain left as a question
rather than plug. The table reader read 1,879 tables; the name judgment ran (2 of 27 ties doubted).

## Honest gaps
- Correctness on the segment sheets is flat at ~60%: what is left is your own derivations and definitions,
  which need one line each in the model spec, plus a residue of reads the brain still gets wrong.
- Runs take ~50 min; the ending loop is ~8 of them.
- The CLP floor is now pinned from run 4 (with the brain's table readings) so replays exercise the reader.
