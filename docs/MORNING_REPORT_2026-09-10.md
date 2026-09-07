# Morning report — 2026-09-10 (overnight work after runs 255/256/257)

## 1. The reading test (your priority): Luna CAN read a report like an analyst — with one trap

One call per company, the whole disclosure page-marked (scanned pages as images):

| | CLP FY25 | DFE FY25 |
|---|---|---|
| Prompt tokens / time | 392k / 40 s | 368k / 66 s |
| Rows asked / answered with a page | 28 / 24 | 42 / 41 |
| Right vs the by-hand key (where both numeric) | 18 / 24 | text-page rows right (revenue, PBT, EPS, dividend 1,832.93, the three cash flows, cash, NP, new orders 117,251, two blank→0) |
| The misses | model conventions: payout % vs fraction, dividends sign, a segment sheet given the group total, an analyst's own definition | the bond line's comparative read as this year's; a units slip (19,078 for 19.08); dividend paid vs declared; the group order figure on a segment row; and a FABRICATED balance sheet on the scanned page (97,563 / 65,111 / 96,628 / 54,449 — balances to the true total, not what the page prints) |

Verdict: Luna reads text like an analyst and fabricates consistent numbers on a scan it cannot read exactly. Both facts point to one design:

**The reader stage** (`pipeline/reader.py`, wired before the tier-3 hold): Luna reads whole and answers every row the deterministic stages left unproven; code recomputes each value from the PRINTED digits at the page's scale, ties the cited line's comparative to the model's prior, applies the model's sign, treats a lone number equal to the prior as 0, finds a page slip by the printed name, refuses any number no printed line carries. Proven → plain; printed but untied → red with citation; unverifiable → never written. On the DFE reading answers: 20 verdicts, 17 proven, 3 red, the fabricated block rejected, the units slip corrected. Cards remain for genuine conflicts.

## 2. Why 255 and 257 failed (and 256 was unbalanced) — all found, all fixed

| Run | Cause | Fix |
|---|---|---|
| 255 DFE annual, refused | the plug ladder reverted every site of the fixed-asset check for "forecast damage" | forecast damage → watch list, never a veto |
| 255 | the bond card offered 23 "Total" lines because my "last year's report names the item" rule took the word Total as a name; Luna served last year's number | a name must be specific; identity needs a current AND a comparative; a lone number equal to the prior is never a candidate |
| 255 | the order-intake sentence landed on a Driver segment row, blocking the group row | label cards state the row's scope and list competing homes |
| 256 DFE half-year, unbalanced Model column | headers "H120…H125" not recognised, so the Model and Driver panels were "left out" and never gated; a label card put the parent's cash into a subsidiary row; label cards served the model's own balancing rows | per-column period tags (text beats a date), tag-grouped runs, two-digit marks; label cards never on check rows |
| 257 CLP, refused after 63 min | segment matrices paired as year tables (57 false readings); a group debt figure on the India row; the one-off law and the gate contradicted each other; the hour went to vision reads of last year's report | wide rows pair only in period tables (distinct-year header); the one-off law registers frozen; prior-vintage documents read as text only; per-stage timing |
| all | the gate quarantined instead of delivering | the run always delivers: an unclosable check is marked red on its cell and listed; only a restatement pauses |
| found by the half-year replay | the roll copied prior formulas into the H125 column with a two-column shift, breaking 31 cells | a target formula of the prior's shape is the analyst's own carried-forward structure — kept |

## 3. Guards on me (the change law)
`tools/change_guard.py` as a Claude Code hook, a git pre-commit hook and a bench check: a pipeline edit that adds a where-to-look or how-many rule is refused; evidence lines carry `# evidence:`. The law is in CLAUDE.md. It fired once tonight — correctly — on the reader stage's use of the prior-vintage ban (kept as "never a source", marked as evidence).

## 4. Proof state (filled in below as the night ends)
- Museum: 146 exhibits green. Bench green.
- Three replays on the final head: (see the end of this file)
- Live runs: (see the end of this file)

## 5. Rules added / removed tonight
Removed: wide-row fence, table-length fence, candidate caps, serve/call caps, statement-pages-only in the walk and the nil check, the prior-year "never read" ban, the ladder's forecast veto, the gate's refusal.
Added (evidence only): matrix rows never pair; identity needs a specific name and two numbers; lone prior-equal numbers are comparatives; scope words and competing homes on label cards; per-column period tags; the roll's shape rule; the reader stage's verification.
