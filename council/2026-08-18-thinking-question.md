# Question: teach a mid-tier LLM agent to THINK like an analyst — not obey a rulebook

## The system

An agent updates equity-research valuation models (Excel) to new annual
results from PDF disclosures — "mark to actual, roll forward". It must be
GENERIC across an organization's analysts (every model differs: language,
layout, sheets, drivers), run on a fixed mid-tier engine (gpt-5.6-luna —
weaker than frontier models, weak at long coherent execution, decent at
diagnosis), finish in <60 min, and ALWAYS deliver (never refuse), with
everything unproven flagged for the analyst.

Measured architecture that works (keep): deterministic substrate — PDF
extraction ledger, prior-value-anchored joins, checksummed page reads,
scale/unit doctrine — serves ~220 of ~590 rows with headline keys exact
every run (revenue/EPS/total-assets/net-profit). One write chokepoint:
every write is cited, transactional (auto-reverts if it breaks a passing
check or moves any value off its disclosed tie), world-band guarded. A
deterministic "Police" measures four laws at the end: announced data
correct, analyst adjustments honored, balanced all years, key numbers
correct. Structural honesty: stale inputs auto-flagged, failing checks
auto-marked. These guards are SAFETY and stay.

The agent layer on top: an LLM loop that owns the run — sees a rendered
state block (scorecard, tool health, its notes/todos, action history,
last tool result) and answers ONE action per turn as JSON from a toolbox:
bulk ops (rollover, deterministic join, checksummed gap reads), queries
(trace a cell's formula chain, search evidence lines, diff statements,
diagnose a failing check into guilty/suspect leaf components, implied-
prior candidates for single-year tables), writes (set_input with citation,
apply_diff, plug_residual as flagged last resort, flag, not_disclosed),
control (note, todo, finish). Budget ~120 actions + two Police feedback
cycles of ~20.

## The measured failure (why we stopped)

Across 9 live runs the deterministic layer is constant; the AGENT'S
ENDGAME is a lottery:
- Run 7: agent landed 4 legal flagged plugs -> ALL years balanced,
  announced-data law PASS. The contract essentially met.
- Run 8: (after we added a key-diagnosis feature) agent misused the plug
  tool on KEY cells (drove investing-cash-flow itself toward zero),
  ping-ponged one shared component 35,262 -> 5,089 -> -25,073 as two
  residuals fought. Guards have since made this impossible.
- Run 9: all guards held, zero corruption — but the agent spent 83 of
  ~160 actions on trace_cell (formula-chain inspection), landed only 3
  writes, exhausted its budget, and left small residuals open
  (90 / -425 / 514 / -95) that run 7 had closed.

Pattern over 9 runs: whenever the agent misbehaved we added a guard, a
refusal message, or a prompt rule (walk-away law, third-look-is-a-plug,
plug-rules, keys-law, steering nudges after 5 non-writes...). The prompt
is now ~15 laws born of specific failures. The owner (correctly) called
this the same patch spiral that killed the previous 100-run generation:
compliance engineering, not thinking. The agent obeys or evades each
rule; it does not UNDERSTAND why plugging a key is absurd.

Reference point: a frontier model (Claude/Fable) doing the same update
free-form in a clean room scored 96% with a simple coherent METHOD —
"read the statements completely, fill the column in order at full
precision, self-verify at the end" — no rulebook, no guards needed.

## The question

How do we get a MID-TIER model to genuinely think like an analyst closing
a model — hold a plan, reconcile section by section, treat residuals as
information, decide plug-vs-flag like an owner — GENERICALLY (no
per-company logic), within the engine/time constraints? Specifically:

1. Is the one-action-per-turn JSON loop itself the thinking-killer?
   Should the agent instead write free-text reasoning + a plan and pursue
   self-chosen objectives in coherent arcs (multi-action turns, or a
   focused sub-session per objective carrying only relevant state)? What
   loop shape best converts a mid-tier model's diagnosis into action?
2. What should the PROMPT teach? A working method (the analyst's mental
   model of closing a model) vs enumerated rules — what does that method
   text actually look like for this job, and what happens to the 15 laws?
3. How do we stop the trace-spam / non-conversion failure mode
   structurally WITHOUT behavior-steering patches (we tried steering
   nudges and hard caps — the owner rejects the cap-and-nudge direction)?
4. Budget realities: ~250 LLM calls, 40 min, mid-tier context quality.
   What allocation of those calls (planning vs acting vs reflecting)
   maximizes a weak model's effective intelligence?
5. What is the MINIMAL set of standing rules that should survive in the
   prompt (if any), given guards already make mistakes safe?

Constraints: pure gpt-5.6-luna (no frontier model in the loop; a stronger
reviewer is allowed only as blind Police), <60 min, always deliver,
truth-outranks-balance (never move a disclosed value to force an
identity), four Police laws are the measure, generic across models.
Answer with a concrete redesign, not principles alone: loop shape, prompt
architecture, call budget, and what to DELETE from the current design.
