# Council pack — "the code is hindering the brain" (2026-09-16)

## The owner's question (verbatim, condensed)
"Why can't the brain be taught to make sure the key numbers are correct as well? Why rely on code to make it
right? If the brain knows a number is wrong it could find the reason, plug it, or correct it. Now the code and
the brain are fighting each other to fill the gap. I want the brain to think and the code as only a tool for the
brain. Before you build, make sure this is the best solution — we have made a lot of changes in the past few days
and they don't work out that well. It is doing okay now; some things in the rule book / the agent need fixing.
Too many rules make the agent rigid; the brain is able to think but is forced not to because the code takes over.
Find the balance: help the brain, guide it, provide tools — without taking away its ability to think."

Constraints: the owner is out of time and money for many more iterations (each live run ≈ 1 hour, ≈ 350 brain
calls, 2M tokens). The next change must be the right one. The governing philosophy is in
/Users/lingling/Project M/CLAUDE.md ("The philosophy" and "The change law" sections — read them).

## The agent in one paragraph
Repo: /Users/lingling/Project M/model-update-agent (branch rebuild, head ff8aa81). pipeline/run.py update():
stage-1 read of the PDFs → table reader → name judgment (brain) → stage-2 join (number ties) → schedules → reader
(brain) → stage-3 → constants law (composites) → checkpoint sense → CARD QUEUE (pipeline/workqueue.py: SERVE /
LABEL / ROLLOVER / RUNG / COMPONENT / PLUG / SENSE / TRIPWIRE cards, the brain answers, code applies) → key tie
(pipeline/keytie.py) → THE ENDING (pipeline/consequence.py run_ending: objectives = actual-year balance checks >
keys > cash/assets sanity > forecast checks > sense lines; each broken objective becomes a CONSEQUENCE card; the
brain picks revert/backout/derive/plug/question; code applies with snapshot/restore) → report page.
Brain = openai/gpt-5.6-luna via OpenRouter (pipeline/llm.py). Every card is one shot: text in, one answer out.

## The laws in code that can override or pre-empt the brain (candidates for the audit)
- Evidence law "proven cell": a cell whose evidence ties the model's prior is PROVEN; the brain's later pick on it
  is REFUSED (rollover.input_is_proven, orchestrator.held_proven, workqueue/investigate refusals).
- "One row, one claim": a printed line already serving another cell cannot serve a second (keytie/workqueue).
- Collapse guard (run.py collapse_guard): reverts a cell when a forecast row collapses vs the analyst's baseline,
  unless the brain ruled on that cell.
- Roll-base back-out (run.py): when a roll (schedule) misses its typed actual, code moves the "least confident
  input" by the gap — no card.
- Terminal ladder (orchestrator.terminal_ladder): plugs a still-failing balance check into the largest
  unproven residual — after the loop, no card (the "last resort").
- Forecast plugs (orchestrator): forecast-year residual rows re-solved by code every round.
- Key tie absorbers (keytie.key_tie): with a live brain, absorbers="none" (propose only, the ending's card
  decides); on floors absorbers="any" (code absorbs the key gap into the least-proven input).
- derive:1 / derive:via (investigate.t_derive): code solves a cell so a proven consumer ties; refuses proven cells.
- The ending's exit: "question" or a silent brain ends a KEY break (red, open). Only balance checks go to a last
  resort. There is no key last resort.

## What happened in run 34993405014 (CLP FY25, head c7c4fde, 58 min, delivered)
Log (timestamps stripped): /private/tmp/claude-501/-Users-lingling-Project-M/e6314157-1ae6-4357-a397-f672d87a0a2c/scratchpad/r.log
Score: docs/scores/CLP_FY25_run34993405014_vs_analyst.txt. Analyst's answer key:
"/Users/lingling/Project M/companies/CLP Holdings/model/CLP Model FY25 (Updated).xlsx".
Outcome: balance 0 every year 2018–2030E; keys 8/10 equal the analyst; operating profit 11,957 vs print 14,272
and net profit 8,153 vs print 10,468 — both off by −2,315; 2026E cash −966 (analyst 5,355); mapping 62%.

Cards: 244 dealt (SERVE 81, LABEL 95, ROLLOVER 27, RUNG 28, CONSEQUENCE 8, PLUG 2, COMPONENT 2, SENSE 1).
Answers: not_disclosed 99 (LABEL 60, SERVE 39); ROLLOVER not_sure 12; CONSEQUENCE question 3, plug 1, derive 1,
revert 3 (2 taken back by code as "did not close / made worse").
Brain picks REFUSED by code laws: ~30 ("already holds a PROVEN value" ×14, "one row one claim" ×12, others).
Code acting alone (no card): roll-base back-outs ×11, terminal-ladder plugs ×2, forecast plug ×7 rounds,
collapse guard ×5 passes.

### Case A — the −2,315 key gap (the owner's complaint)
Gap = opex Final!AI14 −76,061 vs analyst −74,206 (+1,855) + other income Final!AI16 0 vs 460.
- Final!AI14: the roll formula was REVERTED to a red hardcode by the brain's own ROLLOVER pick (r913:
  "ROLLOVER Final!118 -> revert:C: REVERTED Final!AI14: =AH14*(…) -> -76061"). The card offered that revert as
  option C with "recovers 3% of the swing (unproven — may be reverted)".
- Final!AI16: never written. r391 reader suggestion "'Operating profit' is not named like 'Other Income, net'";
  r816 the SERVE card offered ONE candidate, prose about a battery (250MW BESS); brain: not_disclosed. The P&L
  face's other-income line never reached the card.
- Ending rounds 3–5 (r1237–1292): CONSEQUENCE cards for net profit / operating profit listed movers = revenue
  and net finance costs, both "PROVEN — not a place to absorb a gap". Neither AI14 (a revert, not a "move") nor
  AI16 (never written) appeared as a mover. Brain: revert:2 (taken back), then question, question. Keys stayed red.
- Meanwhile r760/r1213: derive:1 moved one-offs Final!AI30 to −2,756 (analyst −441) so recurring NP ties 10,909:
  the wrong line absorbed the gap by code derivation; then r1471–1472 the brain's RUNG pick printed:A on AI30
  was REFUSED "already holds a PROVEN value" — a DERIVED (orange) cell counted as proven against the brain.

### Case B — Aus!AI11 EBITDAF (recurring): agent 2,655 red, analyst 3,475
r422 read stage wrote 2,655 "no prior tie — RED". r689 SERVE card offered C: 3,475 (annual report — the
analyst's number). r690–691 the brain picked it twice; both REFUSED "this cell already holds a PROVEN value".
The proven lock protected an unproven wrong number against the right pick.

### Case C — SOC!AI6 fuel costs: the brain's printed pick refused three times (r589, r618, r661, r671)
"the only evidence row whose comparative ties this prior already serves another cell — one row, one claim".

### Case D — Driver!AI37 (JCE earnings): code roll-base back-out moved it −1,060 (r533) then +4,416 (r1151)
with no card; the sense check later called the line stale and kept the analyst's estimate.

### Case E — Final!AI87 fuel clause account: code plugged 3,872 to close the 2025 balance (terminal ladder,
r1183) after the brain had reverted it; the card had said the gap equals a printed figure "excluded perpetual
capital securities 3,883 (p25)" but offered no way to put it there (the real home is minority interests, agent
5,943 vs analyst 9,815, unflagged). The plug then drove 2026E cash negative; the brain answered question.

## The developer's (Fable's) current proposal — attack it
Replace the one-shot CONSEQUENCE card on keys with a multi-turn investigation: the brain owns the objective
("this key must tie the print; question only with an account of what you looked at"), and can call tools as
often as it needs — show the line tree under the key (each input: value, analyst's estimate, flag, whether the
run wrote / reverted / skipped it), find printed figures near the gap, preview a value (snapshot/restore), then
act (set with evidence, derive, back out, plug). Code only computes, previews, verifies arithmetic, refuses a
write on a proven cell without evidence, and reports. Remove the key back-out logic rather than add to it.
Estimated: about a day under the change law. Risk: another large change after a week of large changes.

## Questions for the council
1. Is that proposal the best solution, or is there a smaller change that fixes the cause? Name it.
2. Which code laws above genuinely protect the model (keep as referee) and which take the decision away from the
   brain (convert to a card the brain answers, or remove)? Judge each with the cases above.
3. Would the brain (Luna) actually do better with tools and a mandate, given it answered not_disclosed 99 times
   and question 3 times on one-shot cards? What does it need most: better evidence on the card, tools, or the
   mandate? Time budget: the whole run must stay within 60 minutes and ~350 calls.
4. What is the minimal, root-cause change set for the next run, in priority order, with the risk of each?
