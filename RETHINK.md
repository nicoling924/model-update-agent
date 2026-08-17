# RETHINK — stepping back after runs 1-9 (2026-08-18, owner-ordered halt)

The owner stopped the loop: it felt like the hundred failed runs again.
This document is the honest self-diagnosis BEFORE the council session and
before any further change. Nothing here is implemented.

## What the nine runs actually showed

Constant across all runs (the substrate works):
- deterministic join + checksummed/vision reads serve ~220 rows with the
  headline keys correct (revenue/EPS/TA/NP exact, every run);
- runtime ~41 min, ~$2-3/run; always delivers; structural honesty flags.

The variable is the AGENT'S ENDGAME, and it is a lottery:
- run 7: landed 4 legal plugs -> balance PASS all years, announced PASS;
- run 8: same harness + my key-mode addition -> agent misused plug on key
  cells, ping-ponged components, corrupted CF (guards then closed it);
- run 9: guards all held, no corruption — but 83 trace_cell calls, 3
  landed writes, budget exhausted, residuals 90/-425/514/-95 left open.

## The self-diagnosis (what I did wrong)

1. **I taught compliance, not thinking.** The prompt grew into ~15 laws,
   each born of one run's symptom (third-look, plug rules, keys law,
   walk-away, steering...). A rulebook of refusals is the workflow
   machine reborn — the agent obeys or evades, it does not UNDERSTAND
   why a plug on a key is absurd.
2. **I used guards to steer.** Guards exist to make mistakes SAFE (the
   truth-guard is right). Using refusal messages as behavior control is
   patching — each new rule reshapes next run's behavior unpredictably,
   which is exactly the measured oscillation.
3. **The harness may be thinking-hostile.** One action per turn, JSON
   only, a re-rendered global state block every turn, ~250 disconnected
   micro-decisions. Compare the 96% clean-room Fable run: ONE coherent
   method — read the statements completely, fill in order at full
   precision, self-verify at the end. Luna is never given the space to
   hold a plan, work one objective to completion, or reason in arcs.
4. **Patch cadence outran understanding.** Six dispatches in one day,
   each with a purposeful change — but purposeful ≠ designed. The
   champion/challenger law existed precisely to prevent this tempo.

## What must be preserved (measured, not opinion)

- The write chokepoint + truth-guard + transactional writes (mistake
  SAFETY — these never steered, they prevented corruption).
- The deterministic reading substrate (join/readers/scales) as TOOLS.
- Always-deliver + structural honesty (stale flags, failing-check marks).
- The Police as independent measurement.

## The question for the council

How do we make a mid-tier LLM (gpt-5.6-luna) THINK like an analyst
closing a model — plan, reconcile section by section, treat residuals as
information, decide plug-vs-flag like an owner — GENERICALLY across
different models, instead of complying with an ever-growing rulebook?
Candidate directions (not decided):
A. Teach a working METHOD in the prompt (the analyst's mental model:
   understand -> statements -> keys/segments -> reconcile -> close),
   deleting all symptom-born rules; keep guards silent.
B. Restructure the harness for coherent reasoning: let the agent WRITE
   ITS PLAN and pursue one self-chosen objective at a time with free-text
   thinking before each action (or multi-action turns), instead of
   one-shot global JSON decisions.
C. Objective-scoped focus: the agent opens a focused sub-session per
   objective it names (e.g. "close the cash tie") carrying only relevant
   state; findings compound in its notes.
D. Something else the council sees that we do not.

Constraint reminders: generic across the organization's models (no
company patches); pure gpt-5.6-luna engine; 60-min ceiling; always
deliver; truth outranks balance; the four Police laws are the measure.
