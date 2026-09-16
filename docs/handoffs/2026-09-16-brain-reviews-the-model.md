# Design 2026-09-16 — the brain reviews the model; code applies and measures

Owner's ruling (2026-09-16, after run 35066977462): "the card is an issue — there is no thinking in preparing
the cards, so the brain thinks from wrong choices or choices without enough context." Teach the brain to do the
checking instead of adding rules. This REPLACES the ending's card mechanics (consequence.run_ending's ranked
CONSEQUENCE cards, the checkpoint-only sense check, the judged/tried/clock exit). Nothing is added to the rule
book; `pipeline/consequence.py` shrinks.

## Evidence this is the right fix (audits of run 35066977462, in this folder's council/audit reports)
- Every wrong brain decision was made on a card that fed it a wrong number: the cash card said HK Sales!AI16
  explained 8% of the 2027 cash break (true: 103%); the serve card printed "prior tie EXACT" on a footnote
  superscript (1.00) via a hard-coded placeholder score; a warning was rendered as a tick.
- The sense check ran once, before the writes it should police; its closing re-measure was report text only.
- The loop has six exits, none conditioned on the objectives; "question" disarms the last resort; a
  compensating pair (RE +3,875 / MI −3,872) cannot be resolved one cell at a time.

## The design

### What the brain sees (one context, refreshed every turn; target ≤ 10k tokens)
1. **Objectives, measured by code**: balance check per year (value), each key vs the print (model / print /
   gap), cash and total assets for the next two periods, the pre-update forecast vs now for the headline lines.
2. **The headline lines** (the report table's P&L/CF/BS roles): history (4 years), the analyst's pre-update
   estimate for the actual year, the value now, next year's forecast before and now.
3. **Every cell the run wrote in the actual column**: sheet!cell, label, section path, was → now, the move
   against its own history (min/max of the last 4 years), evidence (doc, page, quoted line, comparative tie or
   not), flag colour. Sorted by the size of the move against history, largest first. No shares, no ranks, no
   "carries N% of the move" — the brain reads the list.
4. **Tools the brain may call, any number of times** (code answers each within the same turn budget):
   - `show sheet!row` — the row's inputs, formulas that use it, history, and the printed candidates on file.
   - `find <number or label>` — printed lines matching, with page and comparative.
   - `try sheet!cell = value [and sheet!cell2 = value2]` — preview: code applies on a snapshot, re-measures the
     objectives (1), reports the deltas, restores. Pairs allowed.
   - `set sheet!cell = value because <evidence>` — apply; lands plain only when the evidence ties (quote on the
     page and comparative ties the prior, or arithmetic the brain states that code verifies); red otherwise;
     a pair applies as one write and is measured as one.
   - `restore sheet!cell` — put back the analyst's pre-update content (red note: "reverted by the brain: <why>").
   - `plug <check> into sheet!cell because <why>` — orange, reported.
   - `done` with a statement per objective: holds / cannot be closed because <reason the analyst will read>.
5. **The mandate** (the prompt): you are the analyst reviewing your own update before delivery. The model must
   balance every year, every key must tie the print, the roll-forward must be sane (no negative cash or
   assets, no headline line moving out of its history without a printed reason). A wrong number is a failure;
   so is a number you could have fixed and left. When something is off, find the input that caused it — look
   at what moved against its history first — and fix it with evidence. Say `done` only when every objective
   holds or you have named why it cannot.

### What code does
- Measures (objectives, deltas, previews), applies, verifies evidence, writes flags and notes, keeps the
  snapshot/restore for every `try`, logs every turn verbatim, and stops the loop at the time budget (default
  12 minutes) or at `done`. On timeout: whatever the brain has not resolved is red with the brain's last
  statement; the terminal ladder then plugs any actual-year check still ≠ 0 (objective 1 is guaranteed by
  code as the very last act, orange, reported) — this is the ONLY code decision in the ending.
- Refuses nothing except a `set` with no evidence at all (lands red instead of refused) and a write to a cell
  outside the actual column / designated inputs.

### What is removed
- `build_card`/CONSEQUENCE cards, the movers census on consequence cards, `judged`/`tried`, the objective
  ranking, the sense `RUNG` cards at the ending, the workqueue PLUG card's `refuse_flag` path, the placeholder
  `tie_off` at workqueue.py:283. The checkpoint sense check stays as an early look (it costs little) but its
  findings are just lines in the brain's context, not cards.

### Verification
- Museum exhibits driven with the run-35066977462 shape: the context lists HK Sales!AI16 first (44.3 → 1.00,
  history 30.2–46.1); `try` on it reports 2027 cash −20,153 → +600; a pair `set` (RE 84,367 + MI 9,815) closes
  Final!99 in one measure; `done` before objectives hold is refused with the objective table.
- The four floors: the replay answerer must be able to drive this loop (record/replay the brain's turns).
- Live-shape floor: a dead brain → timeout → terminal ladder → balanced delivery.
- Cost: one CLP run ≈ 20–40 brain turns × ≤ 12k tokens ≈ 0.3–0.5M tokens — inside today's 2M.

Build on Opus from this brief; a fresh reviewer on the diff; floors; owner's go; one CLP run and one DFE run.
