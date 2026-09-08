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

## 6. Live run 260 (DFE annual, the reader stage's first live run) — DELIVERED, 33 min

| | 246 (last good annual) | 254 | 260 |
|---|---|---|---|
| Key numbers (code's count) | not counted by code | 10/10 tied (recomputed) | 8/8 tied |
| Plugs | 3 | 2 | 3 |
| Bond line | 0 by an old law | 0 (card) | 0, plain, from the printed comparative (reader) |
| New orders | empty | 117,251 red | 117,251 red |
| Dividend | held at prior | held at prior, "not found" | 1,832.93 red, cited p45 (reader) |
| Proceeds from investments | plugged 14,601 | plugged 14,601 | 25,155.70 plain (walk, p20) |

The reader asked 182 rows in one call and wrote 16 (7 proven, 9 red with citations); it rejected every fabricated and parent-page answer. It also exposed three gaps in its own verifier, fixed and pinned the same night: a parameter printed alone is never a nil (the tax rate had gone to 0 — a memo cell, nothing references it); a lone number equal to ANY model prior is last year's (the bond figure had landed on "other financing receipts" and was then plugged); a no-tie read must be within the row's own world (10,820 had been read as interest income). With those, the dry re-verify of the reading-test answers gives 21 verdicts: 17 proven, 4 red, no wrong number.

## 7. What the half-year replay taught after run 260 (all fixed and pinned, museum 149)
- **The plug ladder could not see inside SUM ranges.** Its leaf walker took only the two end rows of a range, so the stale dividends-payable inside the current-liabilities block was invisible and the Model's H125 balance stayed open by exactly that amount, with no plug even attempted. Every row of a range is an input now (this also widens the annual ladder's sites).
- **The column roll overwrote the analyst's header.** 'H124' was copied over 'H125', leaving two H124 columns; the header roll only knew four-digit years. A target header marking another period is the author's and stays; two-digit marks move one period on.
- **Note pages without anchors were never walked.** The dividends-payable note (p153) tied the model's year-end prior exactly but could not ratify its own scale. A page without anchors now takes the scale most of its document's ratified pages carry (81 pages on the half-year, 93 on the annual joined the walk).
- Result on the half-year ledger: the Model's balance check closes (only the cash-difference row is off by 1, a rounding), dividends payable 1,371.19 and fixed assets 5,472.69 served from the notes, headers intact. Annual ledger: delivered, 134 rows served.

## 8. Live run 261 (DFE half-year, head 08f5ba2) — DELIVERED, 23 min, the Model column balances

| | 256 (last half-year) | 261 |
|---|---|---|
| Model H125 balance check | −1,389 (never gated: panel unrecognised) | 0 |
| Cash difference row | 8,188 | 0 |
| Investing cash flow (Model) | −9,064 (parent cash mis-served) | −876.58 (print −876.50) |
| Attributable profit | 947 (wrong column) | 1,909.80 (print) |
| Dividends payable | stale 1,485 | 1,371.19 from the note (p153) |
| Key numbers (code's count) | 7/8 | 6/6 |
| Plugs | 0 | 1 (3m, a receivables line) |
| Red cells in the half-year columns | 13 | 51 |

The reader answered 227 rows and wrote 41 (3 proven, 38 red with citations). Most of the reds are Driver-sheet rows that were empty in the prior half-year too (segment revenues from the segment note, balance-sheet lines): they land red with a page reference, exactly as the no-prior rule says, but they are probably reference rows the analyst never fills. One ruling for you: should the agent read rows that were never filled in the interim panel, or leave them empty? (Boss doc §A: some interim breakdowns are reference only.)

## 9. Live run 262 (CLP annual, head 08f5ba2) — DELIVERED WITH OPEN CHECKS at the hour, and what it taught

| | 234 (last CLP annual) | 262 | 262 replayed on the fixed head (no brain) |
|---|---|---|---|
| Time | ~40 min | 60 min (reader 37 min) | — |
| Balance / ROAFNA checks | 0 / 0 | 0 / −184 open | 0 / 0 |
| Keys (code's count) | — | 8/9 | 8/8 |
| Against the by-hand key (11 lines) | 10/11 | 7/11 | intangibles, JVs, total assets back on the face values |
| Red / orange in the actual columns | — | 117 / 45 | 7 / 14 |

What went wrong, in order of damage: the reader re-sent the three documents four times (37 minutes, the queue
starved); it wrote printed totals into rows you never fill and every sum above them moved; a balance card was
allowed to replace the face's intangibles figure with a segment's goodwill because the segment row happened to
contain last year's total; the fuel clause's sign was dropped; the key tie stacked three different back-outs on
total assets across gate rounds; and the report counted a key that had no print at all. All fixed as evidence
rules (RUNLOG 2026-09-10, museum 163, commits 7e4d383 and 20eae3b); the fixed head replays run 262 with checks
closed, 8/8 keys and 7 red cells.

**Rulings needed from you (not fixed, by design):**
- Operating profit: the print (14,272, its comparative = your 14,903) vs the by-hand's 13,812 with other income
  460 split out. The agent follows the print by the prior tie. Which is your definition?
- Minority interests: 5,943 (other NCI, the prior tie) vs the by-hand 9,815 (NCI + perpetual capital securities).
- One-offs (185 disposal, 608 write-down): read from the announcement's bridge, red; the by-hand left them 0.
- Never-filled rows (also the 39 Driver rows in run 261): the agent now leaves them empty. Say if any should be read.
- Fuel clause (Final!61/81): the live card now offers −1,043 (closing balance moved to a liability); confirm.

Next: CLP annual and DFE annual dispatched together on the fixed head (20eae3b) as the regression pair.

## 10. The two live runs on the fixed head (both delivered) and the morning's fixes

| | CLP annual (run 262, before) | CLP annual (fixed head) | DFE annual (run 260) | DFE annual (fixed head) |
|---|---|---|---|---|
| Time | 60 min, open check | 62 min, checks closed | 33 min | 36 min |
| Keys (code's honest count) | 8/9 | 8/10 | 8/8 | 8/11 (three roles have no print) |
| Red / orange (actual column) | 117 / 45 | 8 / 15 | — | same as 260 |
| Reader time | 37 min | 71 s | — | 41 s |

CLP is no longer a regression: checks closed, the intangibles and joint-venture figures on their face values,
red cells down by more than ninety percent. Two mis-maps remained and are fixed this morning with exhibits: the
fuel clause sign (the reader forced last year's sign although the comparative printed negated) and the associates
line (a note's components-and-total row was read as a period pair). Both are evidence rules, not company rules.
Your two rulings from this morning are in: interim balance-sheet keys take the model's year-end column as the
prior, and a comparative the model has no column for becomes a question to you, never an estimate.

Time is the open item on CLP: about forty minutes pass before the card queue starts (document reading with vision
votes, document classification, the walk). The workflow now logs with real timestamps so the next run shows where
those minutes go; no rule changed for time.
