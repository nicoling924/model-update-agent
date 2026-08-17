# LLM Council transcript

## Question

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


## Stage 1 — answers

### Response A — openai/gpt-5.6-terra

The problem is not that Luna cannot “reason.” It is that the current loop gives it the wrong unit of work:

- one primitive tool call at a time,
- against a large global state,
- without a durable reconciliation objective,
- where exploration and completion are equally easy,
- and where the only memory of a plan is prose it must reconstruct every turn.

That produces a competent diagnostician with no case ownership. It can inspect a formula tree forever because nothing makes an inspection become a disposition.

The redesign should make the unit of work a **reconciliation case**, not a tool call or a cell.

---

# 1. Replace the global one-action loop with objective-scoped reconciliation sessions

Do not give Luna unrestricted free-form autonomy over the full workbook. It will lose the thread.

Also do not keep the current “one JSON action against the whole world” loop. That is too atomized.

Use a three-level loop.

## A. Global controller: owns the workboard

The deterministic substrate maintains a durable **Reconciliation Board**. Every meaningful issue is a case:

```text
Case ID: CF_2024_investing_cash_flow
Type: statement-gap / failed-check / stale-input / missing-disclosure
Section: Cash flow statement
Years: FY23, FY24
Priority: high
Residual impact: 514
Status: open | investigating | ready-to-write | resolved | flagged
Source facts: [evidence IDs]
Known fixed cells: [...]
Editable candidate leaves: [...]
Affected checks: [...]
Previous attempts: [...]
Disposition: empty
```

Cases are created deterministically from:

- stale-input detection,
- failed balance checks,
- missing rows in a statement section,
- unexplained prior/current diffs,
- unmatched disclosed evidence,
- Police findings.

The board, not the LLM’s prose, is the durable plan.

The global state shown to Luna should be small:

```text
Run scorecard
Current phase
Top open cases by impact/value of information
Cases resolved today
Remaining evidence coverage / residuals
Active case summary
Last action result
```

Not the entire workbook state and action history every turn.

## B. Focused case session: Luna owns one discrepancy until disposition

When Luna chooses or is assigned a case, create a short-lived focused session containing only:

- the relevant statement section and adjacent rows;
- all affected years;
- source evidence candidates;
- prior-year values and differences;
- compact formula/dependency paths;
- affected check residuals;
- candidate editable leaves and their impact on all residuals;
- already attempted actions;
- the case’s required possible dispositions.

A case ends in one of these outcomes:

1. **Actual updated** — cited disclosed value written.
2. **Derived correctly** — formula/model logic produces the value.
3. **Existing analyst assumption retained** — explicitly recognized as intentional.
4. **Flagged unresolved** — source not disclosed, ambiguity remains, or model structure is unclear.
5. **Flagged plug** — only a legal non-disclosed model-completion plug, clearly labeled.

The critical rule is architectural:

> An investigation is not complete when more information has been read. It is complete when the case has a recorded disposition.

Luna may suspend a case if new evidence is needed elsewhere, but it cannot silently drift from case to case.

## C. Tool action loop inside the case

Keep sequential feedback for writes; it is valuable because workbook state changes after every commit.

But make each tool action more meaningful than `trace_cell`.

Replace primitive actions with richer case-level operations:

```text
open_case(case_id)

inspect_case(
  question="Which editable leaf can explain the 514 residual without changing disclosed values?",
  targets=[...]
)

survey_statement_section(
  section="cash_flow",
  year="FY24",
  include=["reported rows", "unmatched evidence", "prior-year diffs"]
)

resolve_candidate(
  candidate_cell="Other investing cash flow",
  proposed_value=...,
  evidence_ids=[...],
  expected_effect={
    "cash_flow_balance": 0,
    "other_checks": "unchanged"
  }
)

flag_case(
  reason="No separately disclosed amount; two plausible classifications remain",
  evidence_ids=[...]
)
```

A single `inspect_case` should perform what currently requires many traces:

- trace formula paths to editable leaves;
- identify shared components across residuals;
- show which leaves are disclosed-tied;
- show the sign/magnitude each candidate would contribute;
- show all checks affected by changing that leaf;
- retrieve relevant evidence snippets;
- compare prior-year model treatment.

This avoids the Run 8 failure structurally. Before changing a shared cell, Luna sees that it affects multiple residuals and is not a private plug for one of them.

## Multi-action turns: use them selectively

Do **not** let a mid-tier model emit unrestricted multi-step programs that can mutate the workbook. That increases silent incoherence.

Use this split instead:

- **Read-only bundles may be multi-action.**  
  Example: inspect all rows in an income-statement section, retrieve all FY24 evidence hits, compare against FY23 and formula links.

- **Writes remain serial and transactional.**  
  One resolution proposal or one small independent write-set at a time, followed by deterministic validation and updated checks.

- **A write-set may include multiple independent cells** if all have separate citations and the validator can prove they do not conflict. This is useful for filling a whole reported statement row/column, but it should still be one atomic transaction.

Thus the agent gets coherent arcs without giving it a dangerous unrestricted scripting language.

---

# 2. Teach a method, not a list of prohibitions

The prompt should teach the mental model of an analyst closing an update.

The current 15 laws are mostly fossilized incident reports. They are useful as guard requirements and test cases, but harmful as the main cognitive interface.

A model under a long rulebook optimizes for avoiding violations. An analyst optimizes for forming and closing a correct view of the statements.

## The core method to teach

This is the kind of prompt text I would use.

---

### Role and objective

You are closing an equity-research model to newly reported annual results.

Your job is to make the workbook tell one coherent story about the reported period while preserving the analyst’s existing judgments. A completed model is not merely balanced: reported facts are correct, assumptions remain intentional, derived values follow from the model, and anything uncertain is visible.

Work statement-by-statement and year-by-year. Do not chase isolated cells without knowing the statement section they belong to.

### How to think

Treat each open item as a reconciliation question:

1. **What is the economic item?**  
   Identify the statement, period, line-item meaning, and whether it is reported, derived, or an analyst assumption.

2. **What should determine it?**  
   Prefer the disclosed statement value. If it is not separately disclosed, determine whether it should be derived by formula, retained as an analyst assumption, or marked unavailable.

3. **What evidence would settle it?**  
   Read the relevant statement section and notes in context. Prior-year model values are clues for locating and classifying an item; they are not evidence that a current-period amount is true.

4. **What is the smallest truthful resolution?**  
   Write cited reported values where available. Repair a derivation when model logic determines the amount. Preserve intentional analyst adjustments. If the source does not settle the question, flag it rather than inventing certainty.

5. **What did the resolution change?**  
   Check the affected statement identity, linked years, and dependent checks. A residual is information: use its sign, size, and dependency path to identify the missing or misclassified component.

### Order of work

1. Establish the reporting period, scale, units, and statement scope.
2. Complete reported statement sections in order at full precision:
   - income statement,
   - balance sheet,
   - cash flow,
   - supporting schedules and notes.
3. Reconcile each completed section before moving to unrelated residuals.
4. Investigate remaining failed checks as named reconciliation cases.
5. Use a flagged plug only as model completion for an otherwise isolated, non-disclosed, eligible leaf. A plug is an explicit assumption, not evidence and not a way to alter reported facts.
6. Finish by ensuring every remaining uncertainty has an owner-visible flag and reason.

### Good completion behavior

For every case, leave one of these records: cited actual, correct derivation, retained adjustment, flagged uncertainty, or flagged eligible plug. Do not leave an unexplained open discrepancy merely because time is short.

---

That is a method. It tells the model why a key-cell plug is absurd: it confuses a disclosed fact with a balancing device, rather than merely violating “law 11.”

## What happens to the 15 laws

Classify each current law into one of three destinations.

| Current law type | Destination |
|---|---|
| “Never alter a disclosed tied value,” key-cell protections, transaction rollback, world-band checks | Deterministic guard/tool eligibility |
| “A plug cannot affect multiple residuals,” no key plugs, no disclosed-line plugs | Plug eligibility engine and candidate packet |
| “After five traces, write something,” “third look is a plug,” walk-away nudges | Delete |
|

### Response B — google/gemini-3.1-pro-preview

The owner is exactly right: compliance engineering (the patch spiral) kills mid-tier models. You have inadvertently built a system that forces the agent to play a game of "guess the rule" one micro-step at a time, rather than doing a job. 

Mid-tier models like gpt-5.6-luna have weak *contextual momentum*. In a single-action JSON loop, by turn 40, the model has forgotten its macro-strategy and is merely reacting to the immediate state block. It spams `trace_cell` because it is lost and looking for a breadcrumb, not because it is executing a plan.

Here is the concrete redesign to make the model think like an analyst.

---

### 1. The Loop Shape: Kill the "Goldfish" JSON Turn
**Delete:** The one-action-per-turn pure JSON loop. It forces the model to act without thinking, leading to reactive spasms (ping-ponging residuals). 
**Implement:** A **Phase-Gated, CoT-to-JSON Arc**.

To get frontier-level coherence from a mid-tier model, you must force it to generate its own contextual momentum using its context window. 
*   **The Turn Structure:** Every turn must require a `<thinking>` block *before* the JSON block. In `<thinking>`, the model states: 1) What the current state means, 2) The section it is currently working on, 3) The hypothesis for the current discrepancy, 4) The next steps. 
*   **Multi-Action Output:** The JSON block should accept an *array* of actions (e.g., 3-5 writes/queries at once). Mid-tier models can handle this if they just wrote the plan in text. This slashes your turn count and stops micro-stuttering.
*   **Phase Gating (The biggest change):** Do not give the agent the whole model at once. Break the loop into three distinct sub-sessions, passing only relevant state:
    *   *Phase 1: Sweep IS (Income Statement)* -> Police Check -> Freeze.
    *   *Phase 2: Sweep BS (Balance Sheet)* -> Police Check -> Freeze.
    *   *Phase 3: Sweep CF (Cash Flow) & Reconciliation (hunting residuals).*

### 2. The Prompt: The Analyst's Method
**Delete:** The 15 reactive laws (walk-away law, third-look-is-a-plug, etc.). 
**Implement:** The **Analyst's Method**. A mid-tier model cannot easily invert negative constraints ("don't plug keys") into positive action. You must tell it *how to move*. 

Replace the rules with this exact operational narrative:

> "You are an equity analyst rolling forward a financial model. The deterministic engine has already anchored the exact key metrics. Your job is to fill in the missing components so the model reflects the new disclosure.
> 
> **Your Method:**
> 1. **Top-Down:** Complete the Income Statement, then Balance Sheet, then Cash Flow. 
> 2. **Precision:** Search the PDF for exact matches to historical line items. Write them exactly as disclosed.
> 3. **The Hierarchy:** Sub-components sum to Keys (e.g., Revenue, Total Assets). Keys are absolute truth. If a check fails, the error is in a sub-component, never the Key.
> 4. **The Residual:** If a formula does not balance after all PDF values are entered, the difference is the 'Residual'. 
>    - *Do not force it.* Treat the residual as information.
>    - Trace the failing check to find stale (unupdated) components.
>    - If all components are updated and it still fails, the company grouped an item differently this year. Use `plug_residual` on the most likely un-disclosed sub-component and FLAG it for the human."

### 3. Structural Fix for Trace-Spam (Without Steering)
**The structural cause of Run 9's failure:** You gave a weak model a shovel (`trace_cell`) and told it to find a buried wire in a massive Excel sheet. It dug 83 holes. 
**The Fix:** Change the information architecture. Deprecate `trace_cell` as an exploratory tool and upgrade the `diagnose` tool into the environment itself.

When a check fails (e.g., `Assets != Liabilities + Equity`), the deterministic layer should *automatically* append the **Diagnostic Leaf Tree** to the state block. 
*   *Instead of the agent seeing:* `Check Failed: BS_Bal (Diff: 425)`.
*   *The agent sees:* `Check Failed: BS_Bal (Diff: 425). Sub-components of this check currently holding stale (prior-year) inputs: [Inventory, Accrued_Liabilities, CapEx].`

By automatically surfacing the un-updated leaf components that feed a broken check, you eliminate the model's need to blindly trace. It immediately knows *where* to look in the PDF. If it still wants to `trace_cell`, require it to pass a `hypothesis` string in the JSON payload to force intentionality.

### 4. Budget Allocation (Maximizing Mid-Tier Intelligence)
With a limit of ~250 LLM calls and 40 minutes, you must spend tokens on *reasoning*, not *loop overhead*. 

**Budget blueprint:**
*   **Phase 1: Deterministic Recon (0 calls).** Engine fills the 220 exact rows.
*   **Phase 2: The Section Sweeps (Max 60 calls - 20 per section).**
    *   Because the agent can output an array of actions (e.g., `[{"action": "set_input", "target": "SG&A"...}, {"action": "set_input", "target": "R&D"...}]`), it can clear a section in 5-10 CoT-driven turns.
*   **Phase 3: The Reconciliation (Max 40 calls).**
    *   The agent focuses purely on the `Diagnostic Leaf Trees` of failing checks. 
*   **Phase 4: Police Cycles (Max 20 calls).** 
    *   Police gives feedback; agent gets max 10 turns to address explicit failures.
*   **Total:** ~120 calls. You have comfortably cut your turn count in half while doubling the agent's contextual depth.

### 5. The Minimal Surviving Rules
Since the deterministic layer is a vault (transactional, world-band guarded, auto-reverting), you do not need behavioral rules to prevent corruption. You only need rules that define **Epistemology** (what constitutes truth). 

Keep only these three standing rules in the system prompt:

1. **Truth Outranks Balance:** A disclosed value from the PDF is ground truth. Never alter a disclosed value to force an identity or check to clear.
2. **Silence is Disclosed Data:** If a historical line item is missing from the current PDF, do not guess it. Leave it blank, allow the check to fail, and use `plug_residual` with a flag.
3. **No Historical Revisionism:** Never alter a prior year's column unless the new PDF explicitly states a prior-period adjustment.

### Summary of what to DELETE today:
1. Delete the 1 action/turn constraint (switch to array of actions).
2. Delete the pure JSON output (require `<thinking>` block first).
3. Delete `trace_cell` as an open-ended tool (replace with auto-surfaced diagnostic trees on failed checks).
4. Delete the 15 behavioral patch-laws from the prompt. 

By making these structural changes, gpt-5.6-luna will stop acting like a roomba bumping into walls (rules) and will start moving sequentially through the document like an analyst.

### Response C — x-ai/grok-4.6

**The one-action JSON loop is a thinking-killer**, but it is not the only one. Mid-tier models fail this job when every turn is “pick a legal tool under 15 laws.” That is compliance classification, not closing a model. A frontier model succeeds with one method: read the statements, fill a column in order, self-check. The redesign below makes *that* the primitive, and uses the mid-tier for what it can actually do: **compile a statement column, then decide residuals**.

Guards, write chokepoint, ledger, joins, checksums, Police stay. Almost everything else in the agent layer is replaced.

---

## 1. Loop shape

**Two levels. Packetized. Batched. Compile-first. Decision-gated.**  
Not free-roam objectives. Not 120 independent tool picks.

### Substrate publishes a work queue (generic, no per-company logic)

Every turn the deterministic layer already knows what is open. Expose it as **packets**, derived from inventory + checks + ledger, not from the model’s vibes:

- `ground` — roll/join/headlines
- `compile:P&L:2024` (and BS, CF, other statements the model has)
- `seam:NI→RE`, `seam:cash-roll`, `seam:WC`, …
- `residual:<check_id>`
- `repair:<police_law>`
- `deliver`

L0 may **reorder or skip** packets. It may not invent “explore the formula graph.”

### L0 — Owner (rare)

Sees: global scorecard, packet queue, last packet report, Police, its own last plan.  
Emits: situation (≤8 lines), next packet, success criteria, packet budget, stop condition.

~10–12 calls / run. This is the only place a plan is allowed to live.

### L1 — Closer (focused sub-session)

Sees **only** the packet card + a state slice (that statement/year, open cells, prior-year anchors, ledger hits already joined, last 8 actions in *this* packet, last result, the five standing rules).  
Does **not** see: 15 laws, full run history, other statements, tool-health novels.

Each L1 turn is:

```json
{
  "see": "≤40 words",
  "intent": "≤20 words, must name this packet",
  "actions": [ /* 1–8, see verb sets below */ ]
}
```

Packet ends on success criteria, `blocked`, or packet budget. Then L0.

### Two worker modes (this is the conversion engine)

**A. Column compiler** (fill packets) — the analogue of the frontier method.

Do **not** walk cells. One (or two) LLM calls emit the whole open column:

```json
{
  "writes": [{"cell": "...", "value": "...", "cite": "ledger:..."}],
  "flags":  [{"cell": "...", "reason": "not_disclosed|stale_driver|unproven"}],
  "plugs":  [],
  "unknowns": ["..."]
}
```

Runtime runs every write through the existing chokepoint (cite, transactional revert, world-band, no off-tie). Returns an **apply report**: accepted / reverted / still-open. A second compile pass is allowed on the remainder. Then the packet closes. Residual identity failures become `residual:*` packets — they are not hunted inside the compile.

**B. Surgeon** (seam / residual / repair) — diagnosis is a form, not a hobby.

`diagnose_check` returns guilty / suspect **leaves** (depth-1: value, one formula, inputs, disclosed|computed|assumption).  
**The next model output is invalid unless it is `decisions[]`:**

```json
{
  "decisions": [
    {"leaf": "X", "do": "write", "value": 108.4, "cite": "ledger:..."},
    {"leaf": "Y", "do": "flag", "reason": "not_disclosed"},
    {"leaf": "plug_line", "do": "plug", "value": 90, "flag": true}
  ]
}
```

Runtime applies. No second diagnose on the same check unless the apply report introduced a **new** fact. No ping-pong: a leaf written or flagged this packet is frozen for the packet.

### Multi-action turns

Yes, for **gathers and write batches**. No for tourism.

Allowed in one turn: up to 8 ops, of which at most **one** inspect (`diagnose_check` or depth-1 `inspect_leaf`). Parallel checksummed reads + one join are encouraged. A compile is itself one action that proposes many writes.

### Is free-text + self-chosen arcs better?

Free-text reasoning **yes**, but only short, and only L0 + compile preambles.  
Self-chosen objectives **no**. Mid-tier will choose “understand the model” and recreate Run 9. Objectives come from the packet queue. That is how you get coherent arcs without a frontier-length working memory.

---

## 2. What the prompt teaches

One **method**. Not a lawbook. The method is the analyst’s close, written as a work order. Paste this (trimmed to your voice); delete the 15 laws.

---

**METHOD — Closing a model to new annuals**

You own the close. The deterministic layer already locked what it can. You fill what remains, then leave an honest book.

A model is identities plus facts plus the analyst’s choices.  
- **Facts** are disclosed numbers in the ledger. They are not levers.  
- **Analyst adjustments** stay unless the new disclosure explicitly replaces them.  
- **Computed cells** move only because an input moved.  
- **Residuals** are messages: a leaf is missing or wrong. They are not permission to edit a total.

Work the packet in front of you. Finish it. Do not wander.

**Ground.** Confirm the new column exists. Lock headlines from the ledger (revenue, NI, EPS, total assets, equity, cash, CFO/CFI/CFF). If a headline has no cite, flag it. Do not invent it.

**Fill by statement, top to bottom, one statement per packet.**  
Read that statement from the extract. Write the open column in order, full precision, each value cited or flagged.  
- Disclosed line → write it.  
- Model driver that is still valid → leave it; do not “refresh” it from vibes.  
- Line with no disclosure and no valid driver → flag `not_disclosed`.  
Do not use an identity to back-solve a disclosed total. If the identity fails after a clean fill, that is the next packet, not a reason to overwrite what you just tied.

**Seams after both sides exist.** NI→RE, cash roll, WC, tax, D&A. A broken seam points at a leaf. Write the leaf or flag it. Do not adjust both sides toward each other.

**Residuals are information.**  
Read the diagnosis. Decide each named leaf once:

1. Empty + evidence → write, cite.  
2. Empty + no evidence → flag `not_disclosed`.  
3. Leaves full, remainder remains, model has a **designated non-key plug line** → plug that line, flag it as unproven.  
4. No designated plug → leave the residual, flag the check. Stop.  

A plug is a confession that the close is incomplete. Never plug a headline, a disclosed total, or a cell other identities treat as source of truth. Never split a residual across innocent components. Never move a number that already ties to disclosure to force a balance. **Truth outranks balance.** Unbalanced and honest beats balanced and fictional.

**Deliver.** Keys cited or flagged. Adjustments untouched. Remaining holes flagged. Then finish. The book must ship.

---

That text replaces “third look is a plug,” “walk-away,” “keys-law,” and the nudge stack. The *behavior* those laws were chasing is now either a sentence in the method or a **rejected write** from the chokepoint (`rejected: key without ledger cite`, `rejected: would move tied value`, `rejected: plug target is a key`). Mid-tier learns from the apply report in *this* run, not from a cemetery of past failures.

### What happens to the 15 laws

| Fate | Items |
|---|---|
| **DELETE from prompt** | walk-away, third-look-is-a-plug, steering after N non-writes, refusal templates, plug casuistry, “don’t over-trace,” any score-maximizing hint |
| **Become method sentences** | truth > balance; keys need cites; adjustments honored; plug = flagged last resort on a plug line |
| **Stay as substrate (silent)** | transactional revert, world-band, tie-lock, stale auto-flag, Police, plug-on-key impossible, residual ping-pong freeze |

---

## 3. Kill trace-spam structurally (no nudges, no “max 12 traces” rule)

Owner is right to reject cap-and-nudge. Do this instead:

1. **Remove free `trace_cell` from the default toolbox.** Replace with `inspect_leaf(cell)` → **depth 1 only** (formula, input values, tags). Full chains are what turned Run 9 into a formula tourist.
2. **`inspect_leaf` exists only in surgeon packets**, and **once per cell per packet** (tool-enforced). Compile packets have **zero** inspect tools — only ledger slice + open-cell inventory + `compile_column`.
3. **Diagnosis returns a form that requires `decisions[]` next.** A trace that does not change the decision form is not a legal next action; the runtime rejects the turn as schema-invalid. That is an interface contract, not a sermon.
4. **Compile / decide are the progress verbs.** A fill packet cannot end in “I looked” — the only legal exits are an apply report or flags on every remaining open cell. If the model emits only inspects, the turn is invalid.
5. **Pre-finish is deterministic:** any still-unproven input is auto-flagged. The agent does not need a walk-away law. L0 is told: “you may `deliver`; these will flag.”

Conversion becomes the only well-typed way out of a packet.

---

## 4. Call budget (~250 calls, ~40 min)

Mid-tier intelligence dies in long, homogeneous loops. Spend calls on **fat compiles and short repairs**, not on orientation.

| Role | Calls | Why |
|---|---|---|
| L0 owner | 10–12 | Start, after each packet, after each Police |
| Compile packets | ~30–40 (2 passes × ~15 statements/years) | Where almost all writes happen |
| Surgeon packets | ~50–70 | Seams + residuals, decision-gated |
| Police repair (×2) | ~25–30 | Touch only guilty/suspect leaves |
| Slack / deliver | ~20 | Always ship |
| **Act : plan : reflect** | **~80% : 12% : 8%** | Reflection only inside L0, structured: closed / open / proved vs believed / next packet. No L1 monologues. |

Each compile turn should produce tens of attempted writes. That is how you beat Run 7’s endgame without Run 9’s 83 traces: **fewer decisions, larger strokes.**

Keep `see`/`intent` tiny so the mid-tier cannot substitute prose for a compile. If you need a longer reasoning slot, put it only on L0.

Context: L1 target ≤8k tokens of *relevant* state. Full-history state blocks are why a decent diagnostic model becomes a lost clerk.

---

## 5. Minimal standing rules in the prompt

Five. Everything else is method or a guard.

1. Do not move a disclosed or tied value to satisfy an identity.  
2. Do not write a key without a ledger citation; otherwise flag it.  
3. Analyst-adjustment cells are read-only unless the new disclosure replaces them.  
4. Plug only a designated non-key plug line, and always flag it.  
5. Always deliver; anything unproven must be flagged.

No other standing rules.

---

## Concrete redesign (what to build / delete)

**Keep.** PDF ledger, prior-anchored joins, checksummed reads, scale/unit doctrine, single write chokepoint, Police, stale auto-flag, failing-check marks, plug-on-key impossible, residual freeze.

**Add.**
- Packet queue as the only source of objectives  
- `compile_column` as the main LLM verb  
- L0/L1 split with sliced state  
- Multi-action turns with inspect ≤1  
- `diagnose → decisions[]` schema gate  
- Depth-1 inspect only  
- Deterministic pre-finish auto-flag  
- Apply reports as the teacher (replace law appendix)

**Delete.**
- One-action-per-turn as the only loop  
- The 15-law prompt and all steering/refusal text  
- Unbounded `trace_cell` and full formula-chain dumps  
- Full action history on every turn  
- Walk-away / third-look / non-write nudges  
- Agent-invented objectives  
- Asking the worker to “be careful” about things the chokepoint already rejects  

**Do not add.** A frontier model in the loop. A reviewer that is not blind Police. Per-issuer recipes. Hard behavior caps dressed up as ethics.

---

## What “thinking like an analyst” means here

You cannot make gpt-5.6-luna hold a 60-minute close in latent state. You **can** make each generation be the same cognitive move an analyst makes: *fill this statement; then explain this residual as a leaf decision.*  

Run 7’s legal flagged plugs were the right endgame. Run 8 was a missing guard (done). Run 9 was a microscope with no compiler. Give the mid-tier a compiler, a residual decision form, and a packet that ends when the column is written — and the rulebook spiral has nothing left to patch.


## Stage 2 — peer reviews

### Review by openai/gpt-5.6-terra

## Response A

### What it does well

Response A identifies the central design problem very well: the current unit of work is too small and too contextless. Its diagnosis that the model is “a competent diagnostician with no case ownership” is highly aligned with the observed trace-spam failure. It correctly distinguishes between:

- preserving sequential validation for writes;
- allowing richer read/diagnostic operations;
- giving the agent a durable objective outside its transient prose memory.

The proposed **Reconciliation Board** is particularly strong. Turning stale inputs, failed checks, evidence gaps, and Police findings into persistent, named cases is a sound way to externalize planning for a weaker model. The cases have useful fields: economic section, years, residual impact, evidence, editable leaves, affected checks, attempts, and disposition. This is generic across issuers and workbook layouts because it is derived from the model graph, ledger, and checks rather than issuer-specific rules.

The case disposition taxonomy is also excellent:

1. actual updated;
2. derived correctly;
3. analyst assumption retained;
4. unresolved and flagged;
5. flagged legal plug.

That directly attacks the failure mode where inspection does not turn into a conclusion. The core architectural idea—an investigation must end in a disposition, not merely additional reading—is strong and analyst-like.

Its tool redesign is similarly good. Replacing repeated low-level `trace_cell` calls with a richer `inspect_case` operation is the right direction. The suggested diagnostic packet includes exactly the information needed to prevent shared-component ping-pong:

- formula/dependency paths;
- candidate editable leaves;
- disclosure-tied status;
- all affected checks;
- sign and magnitude contribution;
- prior-year handling;
- relevant evidence.

The write policy is sensible: batch read-only work, retain serial transactional writes, and permit atomic write-sets only where the validator can establish independence.

The proposed prompt method is also high quality. It teaches an analyst’s epistemology and workflow rather than merely prohibitions. In particular, it correctly frames residuals as information, prior-year values as clues rather than evidence, and plugs as explicit completion assumptions rather than evidence.

### What it does poorly

The main weakness is incompleteness. The response cuts off while classifying the 15 laws and does not fully answer all five requested areas. In particular, it does not provide:

- a concrete call allocation for the roughly 250-call / 40-minute budget;
- a final minimal set of standing rules;
- a complete “keep / add / delete” implementation checklist;
- a complete treatment of the 15 laws;
- an explicit recommendation on whether free-text reasoning should be retained, how much, and where.

Because the user explicitly requested a concrete redesign including loop shape, prompt architecture, call budget, and what to delete, this omission is material even though the ideas supplied are strong.

There is also some potential ambiguity in the case controller. It says Luna may choose or be assigned a case, but does not specify enough about how cases are prioritized and scheduled under a hard budget. A weak model may still pick intellectually interesting but low-value cases unless the deterministic board ranks them aggressively by materiality, expected closure probability, and relationship to Police failures.

The response’s session model is conceptually good, but it is somewhat more elaborate than necessary. A “global controller,” case sessions, and enriched case-level tools could work, but the answer does not specify the exact schemas or enforceable transitions that prevent an agent from remaining in “investigating” state indefinitely. It states the desired behavior but does not completely convert it into an interface contract.

Overall, A has very good architectural judgment and a particularly strong reconciliation-case concept, but it is not a fully delivered answer.

---

## Response B

### What it does well

Response B correctly recognizes that the system has become a compliance game rather than a coherent closing workflow. Its explanation of “weak contextual momentum” is a plausible description of the observed behavior: under a long rulebook and one-action turns, the model reacts locally instead of pursuing a stable objective.

Several recommendations are directionally right:

- Replace the long behavior-law prompt with an analyst method.
- Break work into statement-oriented phases rather than presenting the whole workbook continuously.
- Surface diagnostic leaf information automatically when checks fail.
- Reduce unrestricted exploratory use of `trace_cell`.
- Keep only a small number of epistemic principles in the prompt.
- Use the deterministic substrate to provide the relevant candidates rather than requiring the model to discover the entire dependency graph itself.

The suggested analyst method has some useful elements, especially its top-down order, key-versus-component hierarchy, and framing of residuals as things to investigate rather than erase.

The recommendation to turn a failed check into a deterministic diagnostic tree is also valuable. It directly addresses Run 9: rather than asking the agent to infer the relevant model graph through 83 traces, show it the stale or suspicious leaf inputs associated with the check.

### What it does poorly

The biggest technical problem is the recommendation to require an exposed `<thinking>` block before every JSON action. That is not necessary to create coherence, consumes budget and context, and risks making the model substitute verbose explanation for progress. The user’s challenge is not merely that the model lacks visible chain-of-thought; it is that the environment has no durable, bounded objective and no structural requirement to convert investigation into a resolution. Structured plans, packet state, dispositions, and apply reports are more reliable than mandatory free-text reasoning on every turn.

The proposal for broad 3–5 action arrays is also under-specified and potentially unsafe. The answer says multi-action output can include multiple writes, but does not distinguish sufficiently between:

- batched evidence gathering;
- a batch of independent cited writes;
- dependent writes whose validity changes after the first write;
- residual repairs that affect several checks.

For a workbook with shared components and transactional validation, allowing routine multi-write plans can recreate incoherence and hidden interaction problems. The better design is to allow batched reads and atomic independent write-sets while keeping dependent mutations serial.

Its phase gating is too rigid: Income Statement, then Balance Sheet, then Cash Flow. That is a useful default workflow, but model structures vary and many schedules or cross-statement seams must be addressed before a section is truly ready. A generic architecture should use dynamically generated statement, schedule, seam, and residual packets, rather than only three fixed statement phases.

The prompt’s second standing rule is problematic:

> “Silence is Disclosed Data: If a historical line item is missing from the current PDF, do not guess it. Leave it blank, allow the check to fail, and use `plug_residual` with a flag.”

This is internally muddled. If a value is not disclosed, the correct outcome is not automatically a plug. It may be a retained analyst assumption, a derivable amount, a classification issue, an unavailable value that should be flagged, or an eligible non-key plug. The response makes plugging sound like a normal automatic response to absence of disclosure, which conflicts with truth outranking balance and risks recreating the exact plug misuse problem.

The call budget is also not convincingly grounded in the stated constraint. It proposes roughly 120 calls despite a stated capacity of around 250, but does not explain why the unused budget should remain unused, how retries and repair cycles fit, or how much work each call can safely perform. It provides a rough allocation but lacks the operational detail needed for implementation.

Finally, the recommendation to “delete `trace_cell` as an open-ended tool” is directionally good, but the answer does not replace it with a sufficiently precise packet-scoped diagnostic and decision mechanism. Requiring a hypothesis string is merely another behavior-steering patch, which the owner has rejected.

Overall, B has the right broad diagnosis and some useful structural ideas, but it relies too much on visible reasoning and insufficiently constrained batch autonomy, while offering a less robust resolution architecture than the stronger responses.

---

## Response C

### What it does well

Response C is the strongest answer because it directly translates the observed failures into a concrete, implementable system redesign. It answers all requested dimensions:

- loop shape;
- prompt architecture;
- trace-spam prevention;
- call budget;
- minimal standing rules;
- explicit keep/add/delete lists.

Its central framing is excellent: use the mid-tier model as a **statement-column compiler and residual decision-maker**, not as a free-roaming analyst attempting to hold the whole model in working memory. This is a realistic way to increase effective intelligence without pretending the engine can sustain a 60-minute internal plan.

The proposed packet queue is especially strong. Packets such as:

- `compile:P&L:2024`;
- `compile:BS:2024`;
- `compile:CF:2024`;
- `seam:NI→RE`;
- `seam:cash-roll`;
- `residual:<check_id>`;
- `repair:<police_law>`;

create coherent but bounded units of work. This is more flexible than a fixed three-phase workflow because it supports supporting schedules, cross-statement seams, and Police-derived repair work. It remains generic because the packets are generated from inventory, ledger coverage, checks, model topology, and Police results.

The L0/L1 separation is also well designed:

- L0 is a sparse owner/planner with a small number of calls and durable high-level plan.
- L1 is a focused closer that sees only the packet card and relevant state slice.

This appropriately compensates for weak long-horizon coherence. Importantly, C does not simply give the model unrestricted self-chosen objectives; it recognizes that a weak model would choose “understand the model” and recreate Run 9. Objectives come from the deterministic packet queue, while the model retains discretion over dispositions within the packet.

The two worker modes are a major strength.

The **Column Compiler** mode creates a high-throughput analogue of the frontier model’s successful behavior: read the statement, fill the open column in order, cite or flag every value, then let residuals become explicit later packets. This is exactly the missing “compiler” capability that would have prevented the trace-only Run 9 behavior.

The **Surgeon** mode correctly makes diagnosis serve a decision. Requiring `decisions[]` after a diagnosis is a strong interface design. It prevents open-ended inspection without relying on a soft nudge such as “do not over-trace.” It also supports appropriate outcomes beyond writing: flagging, retaining, and legal plugging.

The trace-spam solution is particularly good because it is structural rather than moralistic:

- no free `trace_cell` in the default toolbox;
- depth-1 leaf inspection only;
- inspections available only in residual/surgeon packets;
- diagnosis must be followed by decisions;
- fill packets have no inspect path and cannot complete with “I looked”;
- unresolved cells are deterministically auto-flagged before delivery.

That is a direct answer to the user’s request to avoid caps and steering patches. It changes the type system and workflow rather than pleading with the model to behave.

The prompt itself is strong. It is concise enough for a mid-tier model, but it explains the epistemology of the work:

- facts are not levers;
- adjustments are distinct from facts;
- computed cells should move through inputs;
- residuals identify missing or misclassified leaves;
- plugs are explicit admissions of incomplete disclosure, not evidence;
- unbalanced but honest is preferable to balanced but fictional.

It also appropriately turns many former rules into either method sentences or deterministic guardrails.

The budget allocation is concrete and plausible: roughly 10–12 owner calls, 30–40 compile calls, 50–70 surgeon calls, 25–30 Police repair calls, and slack. The recommended 80/12/8 acting/planning/reflection split fits the stated model limitations and recognizes that frequent reflection is not necessarily helpful for a weaker model.

Finally, C’s minimal standing rules are sensible and aligned with the existing safeguards. It retains only the rules that define epistemic priorities and delivery behavior, while moving enforcement details into the substrate.

### What it does poorly

C’s main weakness is that some of its structural restrictions may be perceived as a new form of hard cap-and-nudge, despite its argument that they are interface contracts. For example:

- “at most one inspect” per multi-action turn;
- “once per cell per packet” inspection;
- “no second diagnose on the same check unless a new fact exists”;
- freezing a written or flagged leaf for the packet.

These are much better than arbitrary “after five traces, write” nudges because they encode a workflow and prevent repeated unproductive state queries. Still, they need careful implementation so they do not block legitimate situations where a write rejection, new evidence extraction, or cross-check conflict genuinely changes the diagnosis. The answer partially handles this with “unless the apply report introduced a new fact,” but a production design should define “new fact” deterministically.

The recommendation that L0 may reorder or skip packets but “may not invent ‘explore the formula graph’” is broadly correct, but perhaps overly strict. There will be legitimate cases where a model-specific relationship is not covered by a standard seam packet. The better implementation detail would be to allow L0 to request a deterministic “generate topology packet” or “expand suspect neighborhood” packet, rather than forbidding exploration categorically. This preserves bounded exploration while avoiding blind spots.

The method says “one statement per packet,” which is useful, but some models have integrated note schedules or unusual layouts where a statement line is only resolvable through a note. The rest of the response does support ledger slices and supporting schedules, so this is more a wording issue than a conceptual flaw. A production system should permit a compile packet to include designated supporting note evidence without expanding into the whole workbook.

The five standing rules include “Do not write a key without a ledger citation; otherwise flag it.” Since the deterministic layer already anchors headline keys exactly every run and has a write chokepoint, this rule may be somewhat redundant. However, redundancy here is relatively harmless because it is an epistemic principle rather than a long behavioral patch.

Despite these caveats, C is materially more complete, operational, and structurally aligned with the stated constraints than the other responses.

FINAL RANKING:
1. Response C
2. Response A
3. Response B

### Review by google/gemini-3.1-pro-preview

An evaluation of the different responses based on how well they address the user's complex system-design questions and constraints:

### Response A
**What it does well:**
- **Architecture (Q1):** The "Reconciliation Board" is a fantastic structural abstraction. By shifting the state management from the LLM's working memory to a deterministic global board, it perfectly addresses the mid-tier model's tendency to lose the thread. 
- **The Prompt (Q2):** The proposed "Core Method" text is excellent. It successfully translates negative constraints into a positive operational workflow (e.g., "What is the smallest truthful resolution?").
- **Classification of Laws:** Elegantly maps the 15 current patch-laws into deterministic guards, plug logic, or the trash bin.

**What it does poorly:**
- **Budget (Q4):** It completely fails to answer the fourth question. There is no numerical breakdown or allocation of the 250-call budget. 
- **Tool Bloat (Q3):** Replacing `trace_cell` with a mega-tool like `inspect_case` shifts too much cognitive load to the tool itself. If the tool returns formula paths, shared components, evidence snippets, and prior-year comparisons all at once, it risks blowing up the context window and overwhelming a mid-tier model.

### Response B
**What it does well:**
- **Loop Shape (Q1):** Accurately identifies that single-action JSON loops kill "contextual momentum" and proposes a phase-gated CoT-to-JSON arc. 
- **Trace-Spam Fix (Q3):** Upgrading the deterministic layer to automatically surface the "Diagnostic Leaf Tree" on a failed check is a very smart, passive way to guide the agent without requiring it to actively use a trace tool.
- **Budget (Q4):** Provides a clear, logical breakdown of the 120-call budget across the different phases.
- **Directness:** Explicitly answers every question, including a succinct "What to DELETE" summary.

**What it does poorly:**
- **Mid-Tier Reality:** Relying heavily on a `<thinking>` block followed by a large JSON array of actions is a frontier-model strategy. Mid-tier models often struggle to perfectly map long CoT reasoning into complex, multi-item JSON arrays without syntax errors or hallucinating targets. 
- **Rigidity:** Forcing a strict "Sweep IS, Sweep BS, Sweep CF" phase gate might violate the "GENERIC across an organization's analysts" constraint, as different models have highly idiosyncratic sheet layouts and non-standard schedules.

### Response C
**What it does well:**
- **Exceptional System Design (Q1):** The L0 (Owner) / L1 (Closer) packetized architecture is brilliant. It uses the mid-tier model exactly as it should be used: highly focused, stateless sub-sessions ("packets") constrained by strict success criteria.
- **Compile vs. Surgeon Modes:** Separating the "fill the column" task from the "diagnose the residual" task prevents the model from conflating data-entry with problem-solving.
- **Structural Trace-Spam Fix (Q3):** The concept of a schema gate (e.g., `diagnose` strictly requires `decisions[]` as the next output) is a masterclass in prompt engineering and system design. It physically prevents the model from infinitely exploring by forcing a well-typed disposition.
- **Budget Allocation (Q4):** Provides a highly detailed and realistic budget breakdown (Act:Plan:Reflect ratio of 80:12:8), proving the viability of the design within the 40-minute/250-call constraint.
- **Prompt Text (Q2 & Q5):** The "Method" prompt is perfectly calibrated, and the 5 minimal standing rules distill the epistemology of the task flawlessly.

**What it does poorly:**
- There are no meaningful flaws in this response. It is highly technical, perfectly aligned with the constraints, and demonstrates deep expertise in both LLM agent architectures and financial modeling workflows. 

***

FINAL RANKING:
1. Response C
2. Response A
3. Response B

### Review by x-ai/grok-4.6

**Response A** is the most complete architectural answer. It correctly identifies the unit-of-work problem (one primitive tool call vs a reconciliation case) and proposes a three-level loop: a deterministic Reconciliation Board as durable plan, focused case sessions with only relevant state, and richer case-level tools that collapse many traces into one inspect. The method text is genuinely analyst-like (economic item → what should determine it → evidence → smallest truthful resolution → what changed), not a restated rulebook. Residuals-as-information, legal plug dispositions, and the classification of the 15 laws into guards vs delete vs eligibility engine are exactly what the owner asked for. Multi-action is handled carefully: read-only bundles yes, writes serial/transactional. Weaknesses: the call-budget section is missing or incomplete (the excerpt ends mid-table), `inspect_case` is powerful but underspecified as an implementation, and the case ontology could sprawl if every discrepancy becomes a first-class object. Still the strongest synthesis of loop, method, structural anti-tourism, and deletion list.

**Response B** is the clearest and most immediately buildable. Phase-gated IS→BS→CF sweeps, required `<thinking>` then action arrays, auto-surfaced Diagnostic Leaf Trees instead of free `trace_cell`, and a short operational method are concrete and well-aimed at Run 9. Budget numbers are explicit (~120 calls, 20 per section). Three epistemology rules are a clean minimal set. Weaknesses: phase gates assume a standard three-statement close and can fight models that are not laid out that way; multi-action write arrays on a mid-tier model risk silent incoherence (A and C are more cautious); “Silence is Disclosed Data / leave blank then plug” is slightly sloppy vs truth-outranks-balance; the method text is thinner than A/C; requiring CoT every turn can waste context on a weak model. Strong practical redesign, less generic and less careful on write atomicity.

**Response C** is the sharpest on conversion and typing. Packet queue as the only source of objectives, L0 owner vs L1 closer, `compile_column` as the main verb, and `diagnose → decisions[]` as a schema gate are the best structural answer to “diagnosis that never becomes a write.” Trace-spam is killed by interface contract (depth-1 inspect, once per cell, compile packets have zero inspect tools), not nudges. Budget table, five standing rules, and an explicit keep/add/delete list match the question’s format. Weaknesses: more machinery (L0/L1, packet types, two worker modes) to implement and tune; compile-the-whole-column may be optimistic for a mid-tier model on messy layouts; the method is more work-order than analyst mental model; L0 “rare owner” can become a new failure mode if it mis-orders packets. Highest structural honesty, slightly more brittle than A.

Overall: A best balances analyst method + durable plan + safe loop; C is the best anti-lottery conversion design; B is the fastest to ship but the least generic and the loosest on writes.

FINAL RANKING:
1. Response A
2. Response C
3. Response B


## Ranking tally (Borda)

- Response C (x-ai/grok-4.6): 8 pts
- Response A (openai/gpt-5.6-terra): 7 pts
- Response B (google/gemini-3.1-pro-preview): 3 pts

## Stage 3 — chairman synthesis (google/gemini-3.1-pro-preview)

The council is in unanimous agreement: the current patch spiral of compliance engineering is exactly what kills mid-tier models. By forcing a mid-tier engine (like gpt-5.6-luna) to act in a single-action, unrestricted global loop against 15 negative laws, you have built a system that optimizes for rule-avoidance and local reactions, not a coherent financial close. 

To achieve frontier-level coherence from a mid-tier model, you must change the **unit of work**. The model must stop acting as a free-roaming tourist searching a massive global state, and instead act as a **statement compiler** and a **residual decision-maker**.

Here is the concrete redesign to make the model genuinely think like an analyst, directly addressing your five questions.

---

### 1. The Loop Shape: Packetized L0/L1 Architecture
**Delete the one-action global loop.** It destroys contextual momentum. A mid-tier model cannot hold a 60-minute macro-plan in its transient memory. Free-text reasoning alone will just result in the model writing long essays before spamming `trace_cell` anyway. 

Instead, implement a **Packetized Two-Level Loop**. The deterministic layer translates the workbook state (missing rows, failed checks, Police findings) into a durable queue of named "Packets" (e.g., `compile:IS:2024`, `seam:NI->RE`, `residual:BS_Bal`). 

*   **L0 — The Planner (Rare):** Runs ~10–15 times per job. It sees the global scorecard, the deterministic packet queue, and the Police results. It outputs a short text plan (≤8 lines) and selects the next Packet. It does *not* execute writes. 
*   **L1 — The Closer (Focused):** Operates in a highly constrained sub-session. It sees **only** the active Packet state (e.g., a single statement section, prior-year anchors, unmapped ledger facts, and the specific failing check). It does not see the 15 laws, the global history, or unrelated statements.

**Multi-action turns:** Yes, but strictly for **batched reads** and **independent write arrays**. L1 should be able to output an array of writes (a "compile") to fill out an entire statement column in one turn. The deterministic chokepoint will apply them transactionally, rejecting any that conflict or break ties, and return an "Apply Report." Dependent mutations (chasing a cascading residual) remain serial.

### 2. The Prompt: The Analyst's Method
**Delete the 15 behavioral laws.** (e.g., walk-away, third-look-is-a-plug). A mid-tier model cannot easily invert negative constraints into a positive workflow. 

Replace the rulebook with a positive **Method** that teaches the epistemology of a close. Paste this exact operational narrative (or similar in your voice) into the L1 prompt:

> **METHOD — Closing a model to new annuals**
> You own the close. The deterministic layer has anchored the exact key metrics. Your job is to fill what remains, then leave an honest book. A completed model is not merely balanced: reported facts are correct, assumptions remain intentional, and uncertainty is visible.
> 
> *   **Facts** are disclosed numbers in the ledger. They are not levers. Write them exactly as disclosed.
> *   **Analyst Adjustments** stay unless the new disclosure explicitly replaces them. Do not refresh them based on vibes.
> *   **Residuals are Information.** If an identity fails after a clean fill, a leaf component is missing, misclassified, or stale. Residuals are not permission to edit a total or force a balance.
> 
> **Order of Work:**
> 1. **Compile:** Fill the packet's statement top-to-bottom. If a historical line has no disclosure and no valid driver, flag it `not_disclosed`. 
> 2. **Reconcile:** For remaining broken seams or residuals, identify the un-updated leaf. 
> 3. **The Plug:** A plug is a confession that the close is incomplete. You may only use `plug_residual` on a designated non-key plug line, and it MUST be flagged for the analyst. Never plug a key or split a residual across innocent components.
> 4. **Deliver:** Unbalanced and honest beats balanced and fictional. Truth outranks balance.

### 3. Structural Fix for Trace-Spam (Without Steering/Caps)
Run 9 failed because you gave a weak model a shovel (`trace_cell`) and told it to find a buried wire in a massive Excel sheet. You must kill trace-spam through **Information Architecture** and **Schema Gating**, not nudges.

*   **Remove open-ended `trace_cell` from the default toolbox.** 
*   **Auto-surface the Leaves:** When L1 receives a `residual` packet, the deterministic layer must automatically append a **Diagnostic Leaf Tree** (depth-1 components, formula paths, and which are stale/un-updated). The agent immediately knows *where* to look without digging.
*   **The Schema Gate:** If the agent still needs to use a new `inspect_leaf` tool, enforce an interface contract: **The diagnosis must return a form that strictly requires `decisions[]` as the next JSON payload.** 
   ```json
   {
     "decisions": [
       {"leaf": "X", "do": "write", "value": 108.4, "cite": "ledger:..."},
       {"leaf": "Y", "do": "flag", "reason": "not_disclosed"}
     ]
   }
   ```
   If a turn ends with just "I looked," the runtime rejects it as schema-invalid. Investigation is not complete when more information is read; it is complete when a disposition is recorded.

### 4. Call Budget Allocation
With ~250 LLM calls and 40 minutes, you must spend tokens on *compiling* and *deciding*, not orientation overhead. The budget allocation (roughly 80% acting, 12% planning, 8% reflecting) should be:

*   **L0 Owner (10–15 calls):** Runs only at the start, between packets, and after Police feedback.
*   **L1 Compile Packets (30–40 calls):** The bulk of the actual writing. The model drafts whole statement sections at once via write-arrays.
*   **L1 Surgeon Packets (50–70 calls):** Fixing cross-statement seams and deciding auto-surfaced residuals. Schema-gated.
*   **Police Repair Cycles (25–30 calls):** Touching only guilty/suspect leaves flagged by the end-stage deterministic Police.
*   **Slack / Deliver (20 calls):** Deterministic pre-finish auto-flags any remaining unproven inputs. The agent guarantees delivery.

### 5. Minimal Set of Standing Rules
Because the deterministic substrate (transactional reverts, world-band guards, tie-locks, Police) is a vault, you only need rules that define **what constitutes truth**. The 15 laws vanish. Keep only these five:

1. **Truth Outranks Balance:** Never move a disclosed or tied value to satisfy an identity.
2. **Key Citation:** Do not write a Key metric without a direct ledger citation; otherwise flag it.
3. **Historical Intent:** Analyst-adjustment cells are read-only unless explicitly replaced by new disclosure.
4. **Plug Doctrine:** Plug only a designated non-key plug line, and always flag it as unproven. 
5. **Always Deliver:** Ensure every remaining uncertainty has an owner-visible flag and reason. The book must ship.

### Summary: What to Build and What to Delete Today

**KEEP:** 
PDF ledger extraction, prior-anchored joins, checksummed reads, single write chokepoint (reverts on broken ties), the 4 deterministic Police laws. 

**ADD (The Redesign):**
*   L0 / L1 architecture with state-sliced sub-sessions.
*   Deterministic Packet Queue (the only source of objectives).
*   Multi-action write arrays for "Compiling" statements.
*   Auto-surfaced Diagnostic Leaf Trees for failed checks.
*   Schema-gated `decisions[]` payload requirement to exit a diagnostic state.
*   Deterministic auto-flagging of stale/unproven items right before delivery.

**DELETE:**
*   The one-action-per-turn JSON loop.
*   Unbounded `trace_cell` and full formula-chain dumps.
*   The 15-law prompt (including all steering/refusal text, walk-away nudges, "third look is a plug").
*   Passing the full action history/global state on every turn. 

By upgrading the model from a lost formula-tourist to a bounded compiler and surgeon, gpt-5.6-luna will stop reacting to rules and start methodically closing the model.
