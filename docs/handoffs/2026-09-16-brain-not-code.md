# Handoff 2026-09-16 — "the brain thinks, code is its tool" (build on Opus)

Owner's ruling (2026-09-16): the brain must own the numbers; code helps, guides, provides tools, and never takes
the decision away. Run 34993405014 (CLP FY25, head c7c4fde) proved the brain got the numbers right and code
threw them away. Fable 5 diagnosed with a three-member fresh-context council (reports at the end of this file).
Build the change set below on Opus. Do NOT build the multi-turn "investigator" — the council rejected it.

Evidence: log `/private/tmp/claude-501/-Users-lingling-Project-M/e6314157-1ae6-4357-a397-f672d87a0a2c/scratchpad/r.log`
(timestamps stripped; may be gone after reboot — regenerate with `gh run view 34993405014 --log`), artifact
`gh run download 34993405014`, score `docs/scores/CLP_FY25_run34993405014_vs_analyst.txt`, analyst answer key
`companies/CLP Holdings/model/CLP Model FY25 (Updated).xlsx` (column AI = 2025).

## The change set, in priority order (1–3 first; hours, not a day)

1. **Accept the brain's reconciliation as proof** (reader.py `verify()` / `_printed_match`; the compile path in run.py).
   Root cause: `verify()` accepts only a ledger line carrying the digits; the table extractor dropped the
   opex total line, so the reader's correct `Final!14 = −74,206` (reader.json line 2815, "(74,206) (76,061)",
   comparative ties) and `Final!16 = 460` (decisions.json: "88,018 − 28,950 − 5,987 − 29,551 − 9,718 + 460 =
   14,272 = printed Operating profit") were refused (log r390 "no printed line on p23 carries -74206", r391).
   Rule (evidence, not a fence): a reading whose stated check closes the printed subtotal at full precision from
   ledger items on that page IS proof. Write it — plain when the quoted comparative ties the model's prior, red
   otherwise — with the reconciliation in the note. This alone closes both keys (−2,315) in this run.
   ⚠ This is a new evidence law: one Fable pass over the function before the floors.

2. **The brain's reading goes on the card first** (workqueue.py card build; reader.py suggestions).
   Root cause: a reader answer without a prior tie is dropped ("a suggestion", r391) and the SERVE card re-mines
   candidates by digits — Final!16's card (r816) offered a 250 MW battery and nothing from the P&L face.
   Change: the reader's value, quoted line and its check become option A on the card.

3. **Fix the false "proven" lock** (writegate.py:314-317 `was_served` branch; orchestrator.py:1410).
   Root cause: the refusal fires on `(sheet,row) in served` — any earlier write, red or orange included — while
   the message says "already holds a PROVEN value". `held_proven` (orchestrator.py:1412) is computed but only
   consulted in the tied branch (writegate.py:299). ~20 brain picks refused this run (r690–919, r1472, r1529,
   r1611), including the brain's correct COMPONENT pick fix:0 putting the 3,883 perpetuals into minority
   interests Final!AI97 (r914–915) — AI97 was never written by the run. Change: refuse only when `held_proven`
   is true; a red / orange / never-written holder yields to the brain's pick, which lands red unless it ties.

4. **CONSEQUENCE cards list the key's whole input tree** (consequence.py build_card ~396 `swing_leaves`).
   Root cause: movers = cells moved vs pre_wb, so AI14 (reverted to the same value, Δ=0) and AI16 (never
   written) could not appear; the brain was asked to choose among PROVEN movers only (r1238, r1291) and
   answered question. Change: every actual-column input under the key with status written / proven / reverted /
   untouched-estimate and the analyst's estimate; on the AI31 card say that AI27 is also off by the same gap.

5. **Code-alone moves become cards** — roll-base back-out (teachings.py:788-815, 14 firings, overrode the
   brain's rulings on Driver!AI37 r1151 and Final!AI87 r1153/1300/1378) and the terminal ladder's landing
   site (orchestrator.py:2033; the brain chose plug at r1177, code chose Final!AI87 over the brain's two
   refusals r866/r1116, then 2026E cash went to −966). Keep the rung; ask the brain WHERE.

6. **Drop the "label unrelated — a numeric coincidence" warning when the prior tie is EXACT** (workqueue.py).
   It talked the brain out of two analyst-correct answers (ROAFNA!29 r679, Aus!70 r849).

Also: derive:1 must not solve a cell for a consumer whose upstream key is itself off the print (r760, r1213
pushed Final!AI30 to −2,756; analyst −441 was option C on the r759 card). Forecast plug AJ108 re-plugged 10
rounds and opened AN99 (+86, r1343) — plug once, verify downstream.

KEEP as referee: objective measures (balance, keys, cash), snapshot/restore, arithmetic verification, the
collapse guard (0 overrides this run), "one row one claim" but SHOW the holder on the card so the brain can
move it (8 refusals, r695 Driver!37's JV line among them), key-tie absorbers="none" with a live brain.

## Process (the change law + the independent-review law, CLAUDE.md item 6)
Root cause → evidence rule → museum exhibit with real-shaped data → `sh tools/bench.sh` → four floors
(CLP FY25, DFE FY25, DFE 1H25, CLP live-shape `tools/replay_live.py … --live-shape`) → fresh-context
adversarial reviewer on the diff → every CONFIRMED finding fixed → compact → owner's explicit go → ONE run
`sh dispatch.sh CLP FY25 FY24 rebuild pipeline`. Never dispatch without the go. Usage discipline: one reviewer
per dispatch, grep summaries only.

## Council pack (what the council was given)
See `docs/handoffs/2026-09-16-council-pack.md`.


## Council report — RULE AUDITOR

## Rule audit — run 34993405014 (CLP FY25)

### Laws table

| Law | Where | Fired | Overrode brain | Verdict | Why |
|---|---|---|---|---|---|
| Proven-cell lock | `writegate.py:314-317` (`was_served` REFUSE branch) — NOT `rollover.input_is_proven:145` nor `orchestrator.py:1412 held_proven` | 23 log lines: ~14 cells, ~20 brain picks (r690–919), 3 RUNG (r1472/1529/1611), 5 ladder refusals (r1178–82) | ~20 (every one was a brain pick) | **SPLIT**: KEEP the real proven test (`is_proven` conf≥4 + tie); CONVERT the `was_served` branch | In both verified cases the held cell was NOT proven (see below). The branch fires on mere presence in `served`; the message lies. The "two readings → land red" path already exists at `writegate.py:296` for proven holders — the unproven-holder case should go there, not to REFUSE. |
| One row, one claim | `writegate.py:310-314, 323-326` | 8 (r671, 695, 705, 808, 829, 947, 958, 977) | 8 | CONVERT | Code decides which cell owns a row; the brain never sees who holds it. r695 Driver!37 option A (1,595 'Share of results of JVs', tie EXACT) refused — that is the JCE line. EVICT (`writegate.py:305`) only serves proven writes. Show the holder on the card; brain picks the home. |
| Collapse guard | `run.py:335` | 13 passes (r504–1235) | 0 (no "REVERTED" line; only zero-writes revert, rulings exempt) | KEEP | Watch-lists, respects rulings. Pure referee. |
| Roll-base back-out | `teachings.py:788-815` | 14 (11 cells; Driver!AI37 ×3, Final!AI87 ×3) | ≥4: r1151 after brain's serve r696; r1589 after brain's "estimate" r1585; r1153/1300/1378 after brain's revert r866 / estimate r1373 | CONVERT to a card | Picks "least confident input" by rank — a WHERE fence. Overwrote the brain's explicit rulings on Driver!AI37 and Final!AI87. Dealt as a ROLLOVER-style card it costs ~11 calls. 200 "roll-base mismatch" log lines = noise. |
| Terminal ladder | `orchestrator.py:2033` | 2 plugs (r1183 AI87 3,872; r1184 ROAFNA!AI18), 5 refusals | 1 direct: r1183 overrode the brain's r866 revert AND r1116 `refuse_flag` on the PLUG card; but the brain itself answered "plug" at r1177 | KEEP the rung, CONVERT the site | The brain chose to plug; code chose where ("largest unproven residual"), into a cell the brain had twice said no to. The card at r1176 already named 3,883 = perpetual securities; ask the brain for the home. |
| Forecast plugs | `forecast_balance.py:150-275` | 10 rounds AJ108 −86 (r1206–1637), 4 withheld | 0 directly; the −86 plug coincides with AN99 +86 break (r1343) that the brain then had to revert (r1345) | KEEP, but plug once and verify downstream checks | Designed catch-all row, blue. Re-plugging every round and opening a 2030 check is code creating brain work. |
| Key-tie absorbers | `keytie.py:421` (`absorbers="none"` with client, `run.py:1199/1271`); `"any"` only on floors (`consequence.py:689`) | 0 absorptions; 3 "gap named, red" (r1144, 1244, 1298) | 0 | KEEP | Already proposes only. Correct. |
| derive | `orchestrator.py:1650 t_derive`, `investigate.derive_via` | 6 (r682, 760, 788, 819, 821 brain's `derive:1` on SERVE; r1213 on CONSEQUENCE) + 1 refusal (r672) | 0 — all brain-chosen | KEEP as tool; fix registration | Its `served` entry (`orchestrator.py:~1690`, conf 3, orange) then trips the `was_served` lock (Case A). An orange cell is by definition awaiting replacement. |
| Ending exit on "question" | `consequence.py:691-696` | 3 (r1289, 1292, 1342) | 0 — it is the brain's exit | KEEP exit; CONVERT the mover list | The card's movers = "inputs the run moved" (`consequence.py:~310`), so AI14 (a revert) and AI16 (never written) were invisible; the brain was asked to choose among PROVEN movers only (r1238). That list is the fence, not the exit. |

Pack discrepancy: log shows one-row-one-claim ×8, not ×12; proven refusals ~20 picks on ~14 cells.

### Case A — Final!AI30 (derived, orange)
`input_is_proven` and `held_proven` both return False: `t_derive` registers `conf: 3, flag: "orange"` (`orchestrator.py:~1690`); `writegate.is_proven:238-249` needs conf≥4 → False. The refusal at r1472 came from `judge_write`'s `was_served` branch (`writegate.py:314-317`): `(sheet,row) in self.served` is True, and the brain's printed:A value 250 (r1470: line "the", p18 — the BESS MW prose) cannot tie a prior of 0 (`ties_prior:91` returns False for |prior|<1) → `tied` empty → REFUSE with the "PROVEN" text. So: the derived cell was never treated as proven; the law misreports "served" as "proven". The refusal was accidentally right (250 MW into one-offs would be worse); the card offering it as printed:A is the real fault.

### Case B — Aus!AI11
r422 registered `{conf: 3, flag: "red", why: "no prior tie"}` (`reader.py:375-379`) → `is_proven` False → `held_proven` False. The brain did NOT pick C (3,475): r690 answered "k" (not an option), r691 picked **D = 2,856 'Recurring EBITDAF'**. D's line is a "wide row… may be a SEGMENT row", i.e. `table_kind == "matrix"`, so `ties_prior:97` returns False in the gate although the card printed "✔ prior tie EXACT" — two tie engines disagree — and the `was_served` branch fired with the wrong message. The pack's account (C picked twice) is inaccurate; the lock was mis-named, not mis-applied to the analyst's number.

### not_disclosed — the cards' candidates, not the brain's judgment
Sample of 8 vs analyst AI column:
- ROAFNA!29 Capital: analyst 58,405 = option A (r679), tie EXACT, warned "label unrelated — numeric coincidence" → brain declined. **Talked out of the right answer.**
- Aus!70 Mount Piper: analyst 6,314 = option A (r849), same warning → declined. **Same.**
- Aus!38 (8,500), SOC Accounts!76 (−1,788), Final!16 (460): candidates were prose junk ("747 million −%", BESS, "the"); the face/segment line never reached the card. **Extraction failure, not brain.**
- India!5 (0), CN!46 (blank), Final!40 (blank): not_disclosed correct.

So 3/8 correct, 3/8 the figure was in the print but not on the card, 2/8 the card's "numeric coincidence" warning overrode a tie the analyst accepted. The brain answered honestly on what it was shown; the 99 reflect candidate quality and the warning text.

## Council report — BRAIN SKEPTIC

**Council seat: BRAIN SKEPTIC — question 3**

**1. Were Luna's answers reasonable given the card? Mostly yes. The failures were card evidence, card options, and the proven-lock — not judgment.**

*CONSEQUENCE cards (8):*
- r1176 (balance −3,883): card names the gap ("Excluded perpetual capital securities 3,883 p25") but every mover is "PROVEN — not a place to absorb"; only `revert/derive:via/plug/question` remain. Brain: `plug`. Rational given the menu. The right home (Minority interests AI97 → 9,788, residual −3,872 → −27) had already been OFFERED on the COMPONENT card at r914, the brain PICKED it (fix:0), and code REFUSED it as "already holds a PROVEN value" (r915). AI97 was never written by the run — it held the analyst's forecast. Code failure, brain right.
- r1212 (recurring NP −2,463): movers = AI30 one-offs (unproven, derive offered) and proven lines. Brain: `derive:1`. The only closing option on the card. The card omitted the decisive fact — reported NP AI27 is ALSO off −2,315, so the gap sits above the one-off line. Evidence failure; an analyst shown both gaps would not have picked it.
- r1238/r1288/r1291 (NP/OP −2,315): movers are all PROVEN (AI21, AI7…). Neither AI14 (reverted to a hardcode at the pre-run VALUE, so Δ=0 vs pre_wb, invisible to `swing_leaves`) nor AI16 (never written, Δ=0) can appear — the census measures "what moved vs pre", not "what is short vs print". `revert:2` on proven revenue (r1239) was a bad pick that the preview should have shown as catastrophic (revenue → 0, r1240); I cannot verify the preview text (log truncates at 900 chars). Then `question` ×2 — the correct answer to a card with no valid mover. `derive:via` was available, but its instruction says "derive a *mover*" and AI14 was not listed. Evidence + option-framing failure.
- r1294/r1341 (cash negative): mover [1] is the code's own terminal-ladder plug AI87 3,872 (r1183). Brain: `revert:1` (correct diagnosis), taken back because it reopens the balance (r1339); then `question`. Reasonable both times — the card gave no way to move 3,872 to AI97.
- r1344: `revert:3`, closed the break. Fine.

*ROLLOVER not_sure (12):* r857, r863: candidates are all "PROVEN — never reverted" plus one absurd unproven ("recovers 12418% of the swing"). `not_sure` is the only defensible answer. r912: option C (revert AI14 formula to −76,061, "recovers 3%") was taken (r913) — mediocre judgment, but the card offered a formula revert as a cure for a 3% share; that option should not have existed.

*SERVE/LABEL not_disclosed:* r816 (Other income): candidates are a 250 MW battery, income-tax expense, "1.00 net finance costs". r922 (CN!46 recurring NP): 251 MW wind farm and 3,560 capex prose. `not_disclosed` is correct every time I sampled. Retrieval never put the P&L face line on the card — evidence failure.

*Case B (Aus!AI11):* the pack misstates it. The brain did NOT pick C (3,475); it picked `k` (invalid) then D = 2,856 "Recurring EBITDAF" (r690–691), the best label match for a row called "EBITDAF (recurring)". The card marked the analyst's answer C as "label unrelated — a numeric coincidence". So the card steered away from C, the brain followed the label, and the proven-lock refused both — protecting 2,655, which the read stage itself had marked "no prior tie — RED" (r422). Two code faults (a red cell counted proven; a warning on the right candidate); the brain's judgment was ordinary, not wrong.

**2. Would multi-turn tools help Luna?** Marginally, and at real risk. Luna's mandate says "when unsure, abstain — a wrong number is the one unforgivable failure". Given tools, that persona will call `show_tree`, see AI14 red and AI16 blank, and still answer `question` unless the mandate changes. Tools fix the *evidence* problem (AI14/AI16 invisibility) at ~4–8 calls per key; they do nothing about the proven-lock refusing right picks (r691, r915, r1472) — the biggest single cause of wrong numbers in this run. Cost: 3 keys × ~6 turns ≈ 18–25 calls, 4–7 min if turns are capped; uncapped, Luna's abstention style plus "re-asking" (24 re-asks already, r690 etc.) could burn 15 min.

**3. Cheapest fix per case:**
- −2,315: better evidence. List on the key card every input under the key that is red, blank, or a run-time revert (not just Δ-movers), with the analyst's estimate, and say "AI27 also off −2,315" on the AI31 card. Then `derive:via AI14 via AI15` works with zero new calls. Also let the key's print figure be a valid derive target.
- Aus!AI11 / AI97 / AI30: not evidence, not tools — the proven-lock. A cell the run wrote RED, DERIVED, or never wrote is not proven; a brain pick with an EXACT prior tie must be accepted. Zero calls.
- Mandate: add one line — "a key that misses the print is itself a wrong number; an orange derivation that ties the print beats a red question".

**Estimate:** evidence + lock + mandate = 0 extra calls, <1 min runtime; it would have closed both keys and the −3,883 in this run. Tools: +20–40 calls, +5–15 min, and no effect on the three refused correct picks.

## Council report — ARCHITECT

I have what I need; no further requests. Report follows.

COUNCIL REPORT — ARCHITECT (Q1 and Q4)

Verified facts (log r####, code file:line)

1. The −2,315 gap was in the brain's hands at the READ stage and code dropped it. reader.json:2815-2818 — the reader returned Final!14 = −74,206 quoting the line "(74,206) (76,061)" with "the comparative 76,061 matches". decisions.json:1-12 records action "write" −74,206 with the check "88,018 + 460 … = Operating profit"; decisions.json:14-22 records Final!16 = 460 with the full face reconciliation "88,018 − 28,950 − 5,987 − 29,551 − 9,718 + 460 = 14,272 = printed Operating profit". Both numbers are the analyst's. reader.py:241 refused Final!14 ("no printed line on p23 carries −74206") because verify() accepts only a ledger item carrying the digits (_printed_match, reader.py); ledger.json has zero hits for 74206/76061 — the table extractor dropped the total line. Final!16 was demoted to "a suggestion" (r391) and the SERVE card at r816 showed five junk candidates (a 250 MW battery), never the reader's 460 with its reconciliation; brain: not_disclosed (r817). Neither cell ever got a card again (grep: no SERVE/RUNG for Final!14).

2. The CONSEQUENCE card structurally cannot show the culprit. consequence.py:396-397 movers = swing_leaves(wb, pre_wb…) — leaves ranked by their move vs the analyst's baseline. AI14 was reverted formula→hardcode at the same value −76,061 (r913; that is 2024's actual, Final!AH14 in the pre model) so it moved 0; AI16 was never written. So r1238/r1291 listed revenue and net finance costs, both "PROVEN — not a place to absorb a gap"; the brain answered revert/question because nothing on the card could be the answer.

3. derive:1 mis-attributed the gap. investigate.py derive_via/proven_figure solves one cell so a consumer equals its print with no test that the consumer's other inputs are settled. r760 and r1213 pushed Final!AI30 to −2,756 (analyst −441) to make recurring NP = 10,909 while reported NP was itself off −2,315. The correct −441 was on the r759 card as option C.

4. Aus!AI11: writegate.py:315 refuses on `was_served` (any entry, including a RED no-prior-tie read) while the message says "PROVEN"; orchestrator.py:1410 passes `(sheet,row) in self.served`, and the correctly computed held_proven (orchestrator.py:1412) is consulted only in the tied branch (writegate.py:299). Correction to the pack: the brain's picks were serve:k (invalid) then serve:D = 2,856 (r690-691), not C = 3,475 — lifting the lock would have landed a red 2,856, not the analyst's number. Same wrong condition refused the AI30 printed picks (r1472, r1529, r1611) — but those picks were "250" (battery prose), also wrong.

Q1 — Is the multi-turn investigation the best solution? No.

What it would NOT have fixed: it works at the ending, on cells; the gap was lost at reader.py:241 and r391, before any card. An investigator with a line-tree tool would have found AI14/AI16 only if it re-read p23 — a second read of what the reader already read correctly. Case B is a wrong refusal condition; Case A(iii) is derive attribution; neither needs tools.

What it risks: a new agent loop with its own tool surface, call budget (~350 calls already spent), and snapshot/restore semantics, shipped a day after a week of large changes with two floors and one live run as evidence; and it re-introduces "the code takes over" one level up (the tool set decides what the brain can see).

The smaller change: make code accept the brain's reconciled reading as evidence.

Q4 — Minimal root-cause change set, priority order

1. Reader verify accepts subtotal reconciliation as proof. Root cause: verify() treats "a ledger line carries the digits" as the only proof, so a figure the extractor dropped is unwritable even when it reconciles the printed statement. Change: when the reader's answer names a check whose other terms are ledger items on that page and the arithmetic closes to the printed subtotal at full precision, write it — plain if the quoted comparative ties the model's prior, red otherwise, with the reconciliation in the note. Files: reader.py verify()/_printed_match; the compile decision path in run.py. Risk: low (only fills cells currently left as forecast/prior; every write still red unless prior-tied). Change law: yes — subtotal reconciliation and prior tie are named evidence rules. This alone closes −2,315 (both cells) in this run.

2. Reader's own suggestion goes on the card. Root cause: a reader answer without a prior tie is discarded (r391) and the SERVE card re-mines candidates by digits. Change: carry the reader's value, quoted line and check onto the card as the first option. Files: workqueue.py card build; reader.py. Risk: low. Law: yes (evidence shown, brain decides).

3. Fix writegate.py:315 to use held_proven. Root cause: the refusal fires on "was served" not "is proven". Change: replace `if was_served` with the held_proven argument already computed at orchestrator.py:1412; a red/derived holder yields to a brain pick, landing red. Files: writegate.py:315, orchestrator.py:1410. Risk: low. Law: yes.

4. derive only when the residual is attributable. Root cause: derive_via solves against a proven consumer ignoring that another key upstream is off the print. Change: when a key feeding the consumer is broken, the derive option shows "absorbs the net-profit gap of −2,315" or is withheld. Files: investigate.py derivations/derive_via; consequence.py:341. Risk: medium (fewer derives). Law: yes.

5. CONSEQUENCE card lists the key's input tree, not movers. Root cause: consequence.py:396 movers = cells the run moved; unmoved/unwritten inputs cannot appear. Change: list every actual-column input of the broken key with status (written/proven/reverted/untouched estimate). Files: consequence.py build_card, investigate.swing_leaves. Risk: medium (longer cards). Law: yes (the model's own structure).

Do 1-3 first; they are hours, not a day. Defer the investigator.