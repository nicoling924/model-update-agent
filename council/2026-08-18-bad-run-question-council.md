# LLM Council transcript

## Question

# Question: run 22 missed every requirement — assess and rank the actions

The owner has stopped the line. Before ANY change is made, assess this
state strategically. Do not assume the next fix is a rule — the owner
explicitly suspects patch-reflex, and has been right twice before.

## The requirements (the owner's mindmap, condensed)

1. Model balances, all periods (or the residual named and marked).
2. Key numbers correct: sales + segment breakdown, GP + breakdown, NP,
   cash, CA/NCA/CL/NCL, equity, CFO/CFI/CFF. Full annual report =>
   NEVER back out keys; they are all printed.
3. Analyst adjustments honored (prior-year tie => likely no adjustment).
4. Segment rows: search multiple tables in all documents; terminal state
   stale+red-flag, never estimates.
5. Always deliver; wrong-unflagged is the one unforgivable output.

## Where 4 consecutive runs landed (same head lineage, ~40-46 min each)

| Run | Balance | Keys | Notes |
|---|---|---|---|
| 19 | PASS all years | NP exact; CFI/CFF twin open | best card |
| 20 | FAIL — truth-write exposed an inherited 12,116 BS reclass hole | NP 3,834 (slightly off) | honest but unbalanced |
| 21 | FAIL(6) | **NP corrupted to 3,969 (print 3,831) by MY new fixed-point writer** | first fixed-point run |
| 22 | FAIL(7) | NP still wrong; CFI/CFF still open; segments 16/33 | ingestion pass live |

## The self-inflicted disease (fully diagnosed)

I added deterministic "fixed-point reconciliation": any row where the
evidence oracle held a UNIQUE prior-anchored tie got auto-written to
print. The flaw: UNIQUE-IN-POOL != IDENTIFIED. Coincidental ties passed:
an interest row was written from a receivables-by-company junk table; the
net-profit chain took a +134 MI-sized hit. The verification oracle
(designed to SUSPECT on one source) was given WRITE authority, which the
deterministic join only ever earned with corroboration gates (kinship,
block ratification, twin-dropping, locality). The whole-page ingestion
pass (owner-approved, checksummed) then enriched the pool and amplified
the coincidence surface. The police caught every wrong write as findings
(nothing silent; runs restart from the clean base model) — but wrong
machine writes happened, violating requirement 5's spirit.

## Also structurally relevant

- The LEGACY stack had a pre-dispatch REGRESSION GATE: offline replay of
  bindings against a pinned baseline; ANY changed binding blocked
  release. The redesign LOST this. Run 21's NP corruption shipped
  undetected because nothing diffs a new head's writes against the last
  known-good run before spending an owner-hour.
- Remaining genuine model gaps: the 12,116 BS reclass hole (inherited,
  needs the destination row — no unique evidence anywhere); the CFI/CFF
  ±593 twin (item NAMED: bond issuance cash — agent flags rather than
  moves; model-side rows are formulas, so the fix must land in Raw
  detail rows which are printed land); segments 16/33 written, rest
  honestly flagged after multi-table search.
- 22 runs total; the packet architecture halved cost and killed
  trace-spam; behavior is honest; convergence QUALITY is the failure.

## The question

Rank the actions. Candidates (challenge or replace them):
A. Withdraw write authority from the oracle entirely (verification-only;
   fixed point becomes a findings generator for the agent) — accept
   slower convergence.
B. Keep machine writes with join-grade corroboration (e.g. >=2
   independent agreeing sources) — the owner suspects this is another
   patch.
C. Rebuild the pre-dispatch REGRESSION GATE (offline scoring of every
   head against pinned artifacts + headline-key panel) so no owner-hour
   is ever spent on a regressed head again.
D. Declare the remaining DFE gaps analyst-decision items, ship the
   flags, and move to CLP genericity.
E. Something structurally different we are not seeing (state it).

Constraints: pure gpt-5.6-luna; <60 min; generic across models; teach
thinking not compliance; no patches — design-level only; every
dispatched run costs the owner one hour, so the plan must minimize live
runs. Answer with a ranked action plan and what NOT to do.


## Stage 1 — answers

### Response A — openai/gpt-5.6-terra

## Bottom line

The failure is not primarily “insufficient corroboration.” It is an **authority-boundary failure**:

- discovery evidence was allowed to become a model mutation;
- a verifier’s “unique match” signal was treated as identity;
- there was no release gate to catch changed bindings before an owner-hour was spent.

So the answer is not “tune the fixed point.” It is to restore a system in which **inference, adjudication, application, and release are distinct capabilities**.

---

# Ranked action plan

## 1. **E — Rebuild the authority model around explicit binding state and provenance**
**Rank: 1. This is the structural correction.**

Implement a generic evidence-to-model state machine:

| State | Meaning | May alter model? |
|---|---|---|
| Discovered | Candidate evidence found in a source | No |
| Verified | Evidence passes local checks / is non-suspicious | No |
| Proposed | Candidate binding to a target row | No |
| Adjudicated | Identity, period, units, sign, dimensions, locality, and source lineage established | Yes, through controlled application |
| Applied | Binding written to Raw/detail row | Only by a deterministic executor |
| Reconciled | Model and headline checks pass | No new authority |
| Stale / unresolved | No defensible binding | No; emit named flag |

The crucial design rule:

> **No evidence oracle, verifier, search process, or fixed-point process may directly write financial values.**

They can produce findings and ranked proposals. They cannot mutate the model.

A write should occur only when an **adjudicated binding object** exists. That object must carry, at minimum:

- exact target row and period;
- source document/table/block/row identity;
- source hash and extraction location;
- period, units, sign, currency, and dimension mapping;
- semantic row identity, not merely numerical agreement;
- lineage showing whether sources are genuinely independent;
- expected model-side effect, including key-number impact;
- reason and confidence/status;
- whether it is a new binding, changed binding, or replay of a prior approved binding.

This is generic across models. It does not depend on adding a new “two-source” rule for every future failure.

### What this means for the fixed point

Keep the fixed-point mechanism only as a **candidate and contradiction generator**:

- “This value coincides with a prior-year anchor” becomes a finding.
- “This candidate conflicts with the existing NP chain” becomes a finding.
- “This candidate has no row identity / locality / kinship” becomes a rejection.
- It never becomes a write merely because it is unique in the pool.

The run-21 error was not bad arithmetic. It was treating a numerical coincidence as a semantic identification.

---

## 2. **C — Restore and strengthen the pre-dispatch regression gate**
**Rank: 2. Highest immediate return on owner-hours.**

This should be a hard release gate before any owner-visible run. It is the mechanism that prevents a regressed head from consuming an hour.

The gate should replay a candidate head offline against:

1. a **pinned clean baseline**, and  
2. a **pinned release manifest** of known unresolved items.

Do not use the latest head as the baseline; it contains contaminated writes. Use the last clean lineage with explicitly recorded deficiencies. Run 19 may be a useful starting artifact, but it must be re-qualified rather than assumed correct.

### The regression gate must compare more than final values

It should diff:

- every applied binding;
- every changed source-to-target mapping;
- source lineage and provenance;
- all headline keys;
- all balance states;
- segment coverage and stale/red-flag status;
- every named residual;
- all new or removed findings;
- changes to Raw/detail rows versus formulas;
- expected versus actual downstream impacts.

A changed binding is not automatically forbidden. But it must be accompanied by a release-manifest entry saying:

- why it changed;
- what exact headline keys are expected to move;
- what prior defect it resolves;
- which evidence/adjudication supports it.

Then the gate can distinguish:

- **intentional correction:** an approved NP correction moves NP exactly as declared;
- **unexplained regression:** NP changes by +134 due to an interest-row binding, with no approved manifest and no legitimate chain.

### Release criteria

A candidate should be blocked if it:

- worsens any previously passed balance or key;
- changes a protected binding without an approved change record;
- introduces a new wrong or unresolved key;
- converts a red-flag/stale item into an unflagged estimate;
- removes evidence lineage;
- makes a formula-side “repair” when the correct landing zone is Raw detail;
- changes a headline key without a declared expected effect.

The gate cannot prove that a baseline is economically correct. But it can stop exactly what happened in runs 21–22: a known-good behavior regressing silently before the owner sees it.

---

## 3. **A — Withdraw write authority from the oracle immediately**
**Rank: 3 as a standalone action; mandatory as immediate containment.**

Do this now, before any other change or replay:

- revoke all oracle/fixed-point write capability;
- invalidate all machine-written bindings derived from the faulty authority path;
- return to the clean base model;
- retain the oracle output only as findings/proposals.

This is not the final architecture by itself. If adopted alone, it may simply trade corruption for slow manual convergence.

But it is the right emergency action because the current system has demonstrated that it can write wrong values under a false theory of identification.

The permanent version of A is embedded in action E:

> The verifier never writes.  
> The application executor may write only a previously adjudicated binding.

That distinction matters. “No machine writes ever” is unnecessary; “no inference engine may mutate the model” is the durable rule.

---

## 4. **D — Split genuine analyst decisions from solvable execution defects**
**Rank: 4, but modify it substantially.**

Do not declare all remaining gaps “analyst decisions” merely to move on. That would be another form of patch-reflex: changing the label instead of resolving the system’s actual state.

Classify the remaining gaps correctly.

### A. The 12,116 BS reclass hole
This appears to be a real underdetermination:

- the model has a known reclass amount;
- no unique destination row exists in evidence;
- forcing a destination would create an invented answer.

This should become a named analyst-decision item, with:

- source evidence;
- candidate destinations, if any;
- statement of why none is identified;
- balance impact;
- explicit residual treatment;
- visible red flag until decided.

That satisfies “balances, or the residual named and marked.” Do not plug it.

### B. The CFI/CFF ±593 bond issuance cash twin
This should **not** be prematurely classified as an analyst decision if the item is named and printed.

It sounds like a mapping/application defect:

- the evidence identifies the transaction;
- the model-side rows are formulas;
- the correct landing zone is Raw/detail input, not a formula row.

Solve this as a controlled Raw binding and validate it offline through the cash-flow formulas. The agent should flag the twin, but the system should be capable of routing an adjudicated named item to the appropriate Raw detail row.

### C. Segments: 16/33 written; remainder stale/red-flagged
This is acceptable only if the unfilled 17 are truly unresolved after the required multi-table, all-document search.

Keep them visibly:

- stale;
- red-flagged;
- non-estimated;
- with search coverage/provenance recorded.

Do not convert incomplete coverage into silent zeros, copied priors, or inferred estimates.

### D. NP corruption
Do not “correct 3,969” in place with another inference. Remove/rebuild the contaminated binding path from the clean base and replay only adjudicated bindings.

---

## 5. **B — Do not adopt “two independent agreeing sources” as the new write rule**
**Rank: 5 / reject in its proposed form.**

This is the tempting patch, and the owner is right to suspect it.

Two agreeing sources do not establish identity if they are:

- the same disclosure repeated in two tables;
- two extracts from the same page;
- two tables with shared upstream data;
- a correct number attached to the wrong business unit;
- the same number in a receivables table and a P&L row;
- two coincidental historical ties.

“Two sources” can be one useful component of adjudication, but not the authority criterion.

The correct criterion is not a source count. It is an **identified semantic binding**:

- right statement and row type;
- right entity/segment;
- right period;
- right units and sign;
- right source block and table locality;
- right accounting kinship;
- right destination row;
- no contradictory chain effects;
- lineage independence where corroboration is required.

If machine execution is retained, it should execute **adjudicated bindings**, not “matches with score ≥ threshold.”

---

# Recommended execution sequence

## Before the next live run

1. **Freeze run-22 lineage.**
   - Do not repair it incrementally.
   - Preserve it as an adversarial regression fixture.

2. **Revoke direct write authority from discovery, verification, and fixed-point components.**

3. **Select and pin a clean baseline.**
   - Include explicit known unresolved items rather than pretending the baseline is complete.
   - Baseline correctness and baseline non-regression are separate concepts.

4. **Build the release manifest and regression gate offline.**
   - Replay all candidate bindings.
   - Produce a headline-key panel.
   - Require declared impact for every binding change.

5. **Rebuild the NP path from the clean base.**
   - No inherited fixed-point writes.
   - Re-adjudicate all changed inputs affecting NP.

6. **Treat CFI/CFF as a Raw-detail routing problem.**
   - Resolve only if the named printed evidence identifies the Raw destination.
   - Otherwise retain a named twin finding.

7. **Retain the 12,116 as an explicit residual until analyst decision.**

8. **Prepare one release candidate only when the offline gate passes.**

The next owner-hour should be spent on a candidate that has already passed:

- balance/non-regression checks;
- full headline key panel;
- binding-level diff;
- segment-state panel;
- named residual panel;
- source-provenance audit.

That is how to minimize live runs.

---

# What not to do

1. **Do not tune the fixed-point threshold.**  
   “Unique,” “higher confidence,” “two sources,” and “better score” are all variants of the same mistaken authority model unless identity and provenance are established.

2. **Do not allow whole-page ingestion to write or upgrade binding status.**  
   Ingestion expands discovery coverage; it also expands the coincidence surface. Checksums prove artifact integrity, not semantic correctness.

3. **Do not repair formula rows directly when the economic input belongs in Raw detail.**  
   That creates brittle local balance while breaking generic model behavior.

4. **Do not use balancing as evidence of correctness.**  
   A balanced model with misclassified cash flow, corrupt NP, or invented reclass destination still fails the owner’s requirements.

5. **Do not silently back out printed keys to make the model work.**  
   If a printed key cannot be reconciled, preserve it, name the residual/conflict, and flag it.

6. **Do not declare all unresolved items analyst decisions.**  
   Reserve that state for genuine underdetermination. Routing defects, stale searches, and missing provenance are system work, not analyst judgment

### Response B — google/gemini-3.1-pro-preview

The owner was right to stop the line. Runs 21 and 22 failed because of a fundamental architectural violation, not a simple bug. You conflated **numerical uniqueness** with **semantic identity**, and you bypassed your own strict write-gates by granting a downstream verification tool (the oracle) upstream mutation rights. 

The owner's suspicion of a "patch-reflex" is dead-on. Action B is a patch. We must solve this at the design layer.

Here is the strategic assessment and the ranked action plan to restore convergence without wasting another 1-hour live run.

### The Ranked Action Plan

#### 1. Action C: Rebuild the Pre-Dispatch REGRESSION GATE (Highest Priority)
* **The Strategy:** Stop the bleeding of owner-hours.
* **Why:** You cannot iterate a complex, multi-layered financial extraction engine on a live, 1-hour loop. Run 21’s NP corruption should never have seen the light of day. By diffing the new head’s proposed bindings against the pinned, known-good baseline (Run 19), regressions are caught in seconds offline. 
* **Design Rule:** **No live run without a passing offline regression diff.** If a core key (like NP or GP) changes from a previously verified state, the build fails locally. 

#### 2. Action A: Withdraw write authority from the oracle entirely
* **The Strategy:** Restore architectural boundaries (Separation of Concerns).
* **Why:** The oracle is designed to verify, suspect, and flag. By giving it write authority based on "unique ties," you created a rogue mutation path that bypassed the agent's structural logic (kinship, block ratification). A mathematical match (e.g., an interest row matching a receivables junk table) is not a financial reality. 
* **Design Rule:** **Oracles observe; Agents mutate.** The fixed-point system must revert to being a high-signal *findings generator* for the agent to evaluate, never a direct writer to the model.

#### 3. Action E: Establish "Topological Boundaries" (The structural fix you are missing)
* **The Strategy:** Constrain the search surface by financial physics, not just numerical pools.
* **Why:** The "disease" occurred because an Income Statement item (Net Profit chain) pulled from a Balance Sheet/Off-balance sheet context (receivables junk table). In financial modeling, a number's identity is defined by its coordinates (Statement -> Section -> Line Item), not just its value. The ingestion pass amplified the pool, destroying local context.
* **Design Rule:** **Numerical matches cannot cross topological boundaries without explicit bridging logic.** A unique tie is invalid if an Income Statement target is anchored to a Balance Sheet table. Contextual kinship must precede numerical matching.

#### 4. Action D: Declare remaining genuine gaps as Analyst-Decision Items (Ship the Flags)
* **The Strategy:** Honor Requirement 5 (Wrong-unflagged is unforgivable; honest flags are acceptable).
* **Why:** The 12,116 BS reclass hole has *no unique evidence*. The CFI/CFF twin is structurally formulaic. If the machine cannot resolve these through rigorous topological binding, forcing it to guess will inevitably corrupt the model. 
* **Design Rule:** If the model balances (even via a named residual per Req 1), keys are intact, and gaps are perfectly isolated and flagged for human review, the machine has done its job. Push to CLP genericity. 

---

### What NOT to Do (The Anti-Patterns)

* **DO NOT execute Action B (Keep machine writes with join-grade corroboration).** 
  This is the exact patch-reflex the owner warned about. Requiring ">=2 agreeing sources" is just applying a heavier band-aid to a broken bone. It treats the symptom (bad writes) while ignoring the disease (giving an oracle mutation rights). Eventually, a junk table will have two copied columns, and Action B will fail silently.
* **DO NOT run another live test (Run 23) until the Regression Gate (C) is active.** 
  Every dispatched run without offline scoring is gambling the owner’s time.
* **DO NOT attempt to formulaically "back out" the keys to force a balance.** 
  Requirement 2 is absolute. Keys are printed; they are the bedrock. If the model must absorb a discrepancy (like the inherited 12,116 BS hole), it absorbs it in a clearly marked residual row, never by altering printed keys.

### Summary State
Roll back the mutation state to the logic of **Run 19** (your best card). Implement the **Regression Gate (C)** immediately. Strip the **Oracle of its write authority (A)**, using it only to feed topological candidates (E) to the agent. Flag the remaining unsolvable gaps **(D)**. You will lose the false speed of auto-writes, but you will guarantee the convergence quality required to trust the output.

### Response C — x-ai/grok-4.6

**Stop the line. Do not dispatch a run 23.** Run 19 already had the only thing that earns an owner-hour: print-faithful keys and named residuals. Runs 20–22 were residual-chasing. That is the patch-reflex.

## Strategic state (before any change)

Two different problems are being treated as one.

**Disease (self-inflicted, new):** a verification oracle was given write authority. `UNIQUE-IN-POOL` was treated as identification. Ingestion then enlarged the coincidence surface. NP became a machine write (`3,969` vs print `3,831`). That is a requirement-2 / requirement-5 failure even though the police later shouted. Findings after a wrong write are not a design. The write should have been impossible.

**Gaps (old, already diagnosed):**
- `12,116` BS reclass — no unique destination evidence. A hole, not a missing rule.
- CFI/CFF `±593` — item is *named* (bond issuance cash). Flag, do not move. Model-side rows are formulas; inventing a Raw landing is a second writer.
- Segments `16/33` — rest correctly stale/red-flag after multi-table search.

Run 19 is the high-water mark on *keys*, not a sacred binding set. Its “PASS” may still hide the reclass (run 20’s truth-write unmasked it). Pin **print keys**, not run-19 cells.

The lost object is not “a better join.” It is the split the legacy stack had and the redesign collapsed:

| Function | Earns | Must not do |
|---|---|---|
| Identification | a write | fire on pool uniqueness |
| Verification | a suspicion | mutate the model |
| Reconciliation | a *named* residual | close the residual to look converged |

Ingestion makes uniqueness *weaker*. A larger pool requires stricter identification, not auto-write.

**False objective that produced 20–22:** minimize open items.  
**Actual objective:** print-key fidelity + every residual named and marked.

---

## Ranked actions

### 1. E — Change the control point (zero live runs)

Do not “fix 22.” Abandon this head lineage as a ship candidate.

- Revert the working model to **pre-writer semantics** (run 19 key posture: NP/sales/GP/cash/BS totals/CFO print-faithful).
- Keep the honest holes as a **residual ledger**, not as jobs for a writer: `12,116` reclass (destination unknown), CFI/CFF bond-issuance twin (named), segments unread after search.
- Freeze success as a **headline-key panel from the print**, plus “no unflagged wrong.” Open twins are allowed. Silent key drift is not.
- Treat the fixed-point writer as a failed experiment, not as something to harden.

This is the move that actually respects “every dispatch costs an hour.” You already bought the answer.

### 2. A — Withdraw write authority entirely

Verification-only. Fixed-point becomes a findings generator for the agent (or for you). No machine write path, including “obvious” unique prior-anchored ties.

Challenge to the framing “accept slower convergence”: **convergence on keys already happened in 19.** What got slower was *counterfeit* closure. A is disease removal, not a performance concession.

Do this in the artifact, not as a prompt incantation. If the writer still exists, it will fire again.

### 3. C — Rebuild the pre-dispatch regression gate *before* any future live run

Offline, cheap, mandatory:

- Score every head against a **pinned print-key panel** (sales + segments that exist, GP, NP, cash, CA/NCA/CL/NCL, equity, CFO; CFI/CFF only as a named pair).
- Also score against last known-good *behavior* (did any printed key move? did a new write land on an interest/NP/MI chain?).
- Any changed printed-key binding → block. No owner-hour.

Challenge: C is a filter, not a cure. Built against run-19 *bindings* it can fossilize a compensating reclass. Built *without* A it only tells you the writer failed after the fact (or misses a coincidental key match). C then A, never C instead of A.

This is the one legacy loss that explains why run 21 shipped. Restore it as infrastructure, not as a checklist item in the run notes.

### 4. D — Only from a clean head, ship the three residuals as analyst decisions

After A+C, do **not** spend an hour on gaps that already have no unique evidence. That is requirement 1 (“residual named and marked”), 4 (never estimates), and 5 (deliver). Then move to CLP genericity.

Challenge: D from run 22 is a dump of a corrupted NP. D is an exit ramp, not an absolution. “Move to genericity” is legitimate only once printed keys are untouchable.

### 5. B — Do not do this now (and probably not later)

`>=2` agreeing sources is UNIQUE-IN-POOL with extra steps. The junk-table interest row can agree with another junk row. The old write-earning stack (kinship, block ratification, twin-dropping, locality) is what *historically* earned writes; a new numeric quorum is exactly the patch you have been right to kill twice.

If machine writes ever return, they return as a **reinstatement of that full identification stack**, sitting *behind* C, never as a one-line corroboration rule. Not in this stop-the-line.

---

## What NOT to do

- Do not run 23 (or any live head) until C exists and A is gone from the code path.
- Do not harden the writer (more gates, more sources, more “only if prior-year tie”).
- Do not close `12,116` or the CFI/CFF twin with a Raw-row invention. No unique evidence → flag.
- Do not use “segments still 16/33” or “twin still open” as a reason to touch NP, interest, or MI.
- Do not pin the regression baseline to a model’s writes; pin it to the **printed** keys.
- Do not confuse “police caught it” with “requirement 5 held.” Wrong machine writes happened.
- Do not add another deterministic reconciler. The next rule is the thing you asked me not to assume.

**If only one thing happens in the next hour:** delete write authority, pin the print-key panel, and ship run-19-class keys with the three named residuals. That is delivery. Another 40-minute head is not.


## Stage 2 — peer reviews

### Review by openai/gpt-5.6-terra

## Response A

### What it does well

Response A gives the strongest diagnosis and the most complete design-level remedy. It correctly identifies the central failure as an **authority-boundary failure**, not merely insufficient matching confidence. Its distinction between discovery, verification, adjudication, application, and release is exactly responsive to the stated disease: a verifier’s suspicion signal was promoted into write authority.

Its proposed binding-state model is especially strong because it replaces an informal confidence rule with a generic, auditable lifecycle:

- evidence discovery cannot mutate;
- verification cannot mutate;
- proposed bindings cannot mutate;
- only a semantically adjudicated binding can be executed;
- unresolved evidence remains visibly unresolved.

That is a structural solution rather than a threshold patch. It also preserves an important nuance: “withdraw write authority from the oracle” should not necessarily mean “ban all machine writes forever.” Rather, a deterministic executor may write only an already-adjudicated binding. That is materially better than treating A as permanent manual-only operation.

Response A also handles the regression gate well. It correctly says that C is not merely a final-number comparison: it must compare bindings, provenance, key panels, residuals, segment states, and expected downstream effects. This is important because a model can retain some headline values while introducing unsafe or unexplained binding changes. Its point that the baseline should be a clean, explicitly qualified baseline—not simply “the latest head”—is sound.

The treatment of the remaining issues is also nuanced:

- The 12,116 reclass is properly characterized as genuine underdetermination and therefore an analyst-decision residual.
- The CFI/CFF ±593 issue is correctly distinguished from the reclass: it is named and printed, and therefore likely a routing/application issue rather than something to dismiss as unknowable.
- The segment shortfall is accepted only if the required all-document, multi-table search is demonstrably complete and the remaining rows stay stale and red-flagged.

Its rejection of B as stated is persuasive. “Two sources” is not semantic identity, nor does it guarantee source independence. Response A correctly reframes corroboration as one possible input to adjudication rather than the authority criterion itself.

Finally, it gives a highly practical offline sequence that minimizes live runs: freeze the bad lineage, revoke unsafe authority, pin a baseline and release manifest, run replay and regression checks offline, and dispatch only a candidate that has passed the full panel.

### What it does poorly

The main weakness is that it is somewhat more elaborate than necessary for the immediate owner decision. The explicit multi-state architecture and detailed release criteria are excellent, but they could make the response feel like a broad redesign specification rather than a sharply prioritized under-60-minute plan.

Its ranking also puts E first and C second, which is defensible architecturally but slightly less directly aligned with the owner-hour constraint. C is the immediate mechanism that prevents another owner-hour from being wasted, while A/E prevents recurrence at the source. Response A does call A “mandatory immediate containment,” but the ranking could more explicitly distinguish:

- immediate containment: A;
- immediate owner-hour protection: C;
- permanent architecture: E.

There is also a small ambiguity around the phrase “adjudicated bindings may alter the model.” The response resolves this later by requiring a controlled deterministic executor, but it could have been clearer that adjudication itself is not an autonomous inference write path; it is a governed artifact with auditable evidence and explicit authority.

Overall, these are presentation and prioritization issues rather than substantive defects.

---

## Response B

### What it does well

Response B correctly recognizes the core conceptual mistake: **numerical uniqueness is not semantic identity**. It also clearly rejects action B’s proposed “two agreeing sources” rule as patch-reflex rather than a durable solution. That is one of the most important judgments in the problem.

It correctly emphasizes two urgent actions:

- restore a pre-dispatch regression gate so regressions do not cost owner-hours;
- remove the oracle’s mutation authority so verification returns to a verification role.

Its “topological boundaries” idea under E is useful. The response rightly notes that statement context, table role, line-item identity, and financial relationship matter. A P&L/NP-chain item should not be sourced from an unrelated receivables-by-company table just because a number matches. This is a valuable articulation of locality and kinship constraints.

The “what not to do” section is concise and mostly sound: no live run before regression testing, no formulaic backing-out of printed keys, and no two-source patch.

### What it does poorly

Response B is materially less complete and less precise than Response A. It frames the solution too strongly as “oracles observe; agents mutate,” which risks preserving an unsafe distinction if “agent” means an unstructured inference process. The real design requirement is not merely that one component writes instead of another; it is that **no evidence-discovery or verification component can directly mutate**, and that any write requires a governed, semantically adjudicated binding plus deterministic execution.

Its regression-gate formulation is also too simplistic in saying that any change to a core key from a previously verified state should fail locally. Some legitimate corrections must change a key. The stronger rule is that any protected-key or binding change must be declared, evidence-supported, and have an expected impact; unexplained changes fail. Response A captures this much better.

The biggest substantive problem is its treatment of D and the CFI/CFF twin. It groups the named bond-issuance cash issue with unresolved items that should simply be flagged. But the prompt explicitly says the item is named and printed and that the repair must land in Raw detail because model-side rows are formulas. That is not inherently an analyst-decision gap. It is a known routing/application problem that should be solved offline if the Raw destination is identifiable. Declaring it an analyst item too early weakens requirement 2 and leaves a solvable printed-key issue open.

It also recommends rolling back to Run 19 more straightforwardly than is warranted. Run 19 was the best card, but run 20 exposed an inherited reclass problem. A baseline should preserve Run 19’s good key behavior while explicitly carrying known deficiencies and residuals; it should not be treated as unquestionably correct.

Finally, its proposed E—“topological boundaries”—is valuable but narrower than the required structural fix. Context constraints alone do not solve the authority problem, the provenance requirement, the change-control requirement, or the lost regression gate.

---

## Response C

### What it does well

Response C is strong in identifying the difference between the self-inflicted disease and the pre-existing model gaps. Its framing is clear:

- the disease is unsafe write authority based on pool uniqueness;
- the genuine gaps are underdetermination, named routing/twin issues, and incomplete segment evidence;
- the wrong objective was minimizing open items instead of maintaining print fidelity and explicit residuals.

It makes several excellent points:

- findings after a wrong write are not a valid safety design;
- a larger ingestion pool makes uniqueness less trustworthy, not more trustworthy;
- Run 19 should not automatically be pinned as a correct cell-level/binding-level baseline;
- the regression gate should pin to printed keys and declared residuals, not blindly fossilize prior writes;
- C is a release filter, not a cure for a bad authority model;
- B is not an adequate answer because numeric corroboration does not establish identity.

The warning not to treat “police caught it” as satisfying requirement 5 is particularly good. The owner’s concern is not just whether errors are detectable after the fact, but whether the system is permitted to make wrong, ungoverned model writes at all.

Response C is also very attentive to minimizing live runs. Its insistence that no new dispatch occur until unsafe write authority is removed and the regression gate exists is fully aligned with the one-owner-hour cost.

### What it does poorly

The central substantive weakness is that Response C overstates the case for declaring the CFI/CFF ±593 bond-issuance item unresolved and merely flagged. The prompt says this is a named, printed item and explicitly states that the fix must land in Raw detail rows because the model-side rows are formulas. Response C calls finding a Raw landing “a second writer” and says not to move it. That is too rigid and conflicts with the given diagnosis.

A controlled write to the correct Raw/detail landing zone is not the same as restoring the unsafe fixed-point writer. If semantic identity, transaction classification, and destination row are adjudicated, a deterministic application layer should be able to route the printed bond-issuance cash item into Raw detail and let formulas calculate CFI/CFF. Treating all model changes as forbidden collapses the useful distinction between unsafe inference writes and governed execution of an identified binding.

Response C also says “convergence on keys already happened in 19,” which is too confident. Run 19 had NP exact but still had the CFI/CFF twin open, and run 20 exposed an inherited balance-sheet reclass hole. Run 19 is a valuable baseline artifact, but it is not equivalent to completed convergence or full compliance with all requirements.

Its recommendation to “ship run-19-class keys with the three named residuals” may therefore be premature. The 12,116 residual can be shipped as a named analyst decision, and unresolved segments can be flagged; however, the named printed CFI/CFF item should first be evaluated as a solvable Raw-detail routing defect. Shipping it as an analyst decision without attempting the known correct application layer would give up too early.

Finally, although its E is framed as a control-point change, it is less fully specified than Response A’s authority model. It has the right instinct but does not articulate the durable binding/provenance/adjudication artifact that would permit safe generic automation later.

FINAL RANKING:
1. Response A
2. Response C
3. Response B

### Review by google/gemini-3.1-pro-preview

**Evaluation of Response A**
- **What it does well:** This response provides a highly rigorous, structural breakdown of the problem. It correctly identifies the core issue as an "authority-boundary failure" rather than a simple logic bug. Its proposal for "Action E" (a generic evidence-to-model state machine) is an excellent, durable architectural fix that ensures verifiers only propose and adjudicate, while executors write. The breakdown of how to rebuild the regression gate (Action C) is exceptionally detailed and actionable.
- **What it does poorly:** While the state machine is a great long-term design, it might be slightly over-engineered for the immediate `<60 min` / "minimize live runs" constraint. It puts the regression gate (C) ahead of withdrawing write authority (A) in terms of structural importance, which risks focusing on the filter rather than the cure, though it does note A is mandatory for containment. 

**Evaluation of Response B**
- **What it does well:** Response B accurately identifies that Action B is a "patch-reflex" and correctly diagnoses the root cause (giving an oracle mutation rights). It prioritizes stopping the bleeding of owner-hours by rebuilding the regression gate first. 
- **What it does poorly:** The tone feels slightly forced and buzzword-heavy (e.g., "financial physics," "Topological Boundaries"). While contextual boundaries are important, making them the entirety of "Action E" misses the deeper operational issue. Additionally, it fails to follow the instructions to rank *all* candidates in the list, choosing instead to leave Action B out of the ranking and relegate it solely to the "What NOT to do" section.

**Evaluation of Response C**
- **What it does well:** This response perfectly captures the requested analytical, zero-fluff, strategic persona. It makes a brilliant deduction: *Run 19 already achieved the success criteria* (print-faithful keys and named residuals), meaning runs 20–22 were a fool's errand of "residual-chasing." The insight that "Ingestion makes uniqueness weaker" is profound and perfectly diagnoses why the failure cascaded. Its ranking logic is flawless, particularly the realization that Action C is a "filter, not a cure" and must sit behind Action A. It offers the best possible answer to the constraint of minimizing owner-hours: zero live runs, revert to the Run 19 baseline semantics, apply the gate, and ship the flags.
- **What it does poorly:** There is very little to critique here. It handles the complex constraints, diagnoses the systemic failure flawlessly, and provides a highly practical, immediate action plan that respects the user's operational costs.

FINAL RANKING:
1. Response C
2. Response A
3. Response B

### Review by x-ai/grok-4.6

## Response A

**What it does well.**  
This is the most complete design-level answer. It correctly names the failure as an *authority-boundary* problem (discovery/verification mutating the model; uniqueness treated as identity; no release gate), not a missing corroboration threshold. The proposed E is actually structural: a binding state machine that separates Discovered → Verified → Proposed → Adjudicated → Applied, with a hard rule that oracles never write. That is generic, teachable, and not a new numeric rule. C is specified as a real release gate (bindings, provenance, headline keys, residuals, segment state), not a vague “diff NP.” D is *challenged* rather than rubber-stamped: the 12,116 hole is genuine underdetermination; CFI/CFF may be a Raw-routing defect; segments may stay stale; NP corruption must be rebuilt from a clean base, not patched in place. B is rejected for the right reason (source-count ≠ identity). The pre-dispatch sequence and “what not to do” list are operationally useful and aligned with minimizing owner-hours.

**What it does poorly.**  
It overbuilds for a stop-the-line moment. A seven-state binding architecture is design-level, but it is also a large next system—the thing the owner asked not to assume. That risks another cycle of implementation before any honest ship. It is slightly too willing to keep solving CFI/CFF as an execution defect; the brief already says the agent flags rather than moves, and inventing a Raw destination without unique evidence is residual-chasing. The answer is long enough that the strategic freeze (“do not repair 22 incrementally”) can get lost inside the new machinery. It also treats A as rank 3 / containment rather than as the disease-removal that must happen in the artifact *now*.

## Response B

**What it does well.**  
Clear diagnosis and readable plan. It agrees the owner’s patch-reflex suspicion is correct, rejects B firmly, and states useful anti-patterns (no live run 23 without a gate; do not back out printed keys). “Oracles observe; agents mutate” is the right slogan. Ranking C first is at least responsive to the one-hour cost. The topological-boundary observation (IS item pulled from a receivables junk table) is a real description of *this* failure.

**What it does poorly.**  
It is the shallowest and the most compliance-shaped. E as “numerical matches cannot cross topological boundaries” is a new matching rule—exactly the class of fix the owner said not to assume. Two junk tables on the same statement would still pass. C is treated as the cure rather than a filter; without first removing write authority, the gate only tells you the writer failed (or misses a coincidental key match). D is too blunt: all remaining gaps are dumped as analyst decisions and “move to CLP,” including a *named, printed* cash item. Rollback to run 19 is recommended without the crucial distinction that run 19 may have hidden the 12,116 reclass and that the pin must be *print keys*, not that head’s cells. Candidates are mostly accepted in their given form rather than challenged. Design rules read like slogans, not an authority model.

## Response C

**What it does well.**  
Best match to the actual question: assess *before any change*, do not assume the next fix is a rule, minimize live runs, teach thinking. It separates two problems the other answers sometimes fuse: the self-inflicted writer (new, must be impossible) versus the old named gaps (already diagnosed). The false-vs-actual objective (“minimize open items” vs “print-key fidelity + named residuals”) is the clearest teaching move in the set. E is the structural move the list was missing: abandon this lineage as a ship candidate, revert to pre-writer *semantics*, freeze success as a print-key panel, keep holes as a residual ledger. A is correctly framed as disease removal, not a speed concession—key convergence already existed in 19. C is ranked and *challenged* (filter, not cure; pin print keys, not run-19 bindings, or you fossilize a compensating reclass). D is allowed only from a clean head. B is rejected as UNIQUE-IN-POOL with extra steps. The “what not to do” list is the sharpest, including the requirement-5 point that police-after-the-fact is not a design.

**What it does poorly.**  
E is more a control-point / ship decision than a reusable generic mechanism; if machine writes must ever return, this answer only points back at the old kinship stack rather than specifying an adjudication object. It is slightly too absolute on CFI/CFF (“inventing a Raw landing is a second writer”)—the brief itself says any real fix must land in printed Raw detail, so a *named* item with an identified destination is not the same as plugging 12,116. Less concrete than A on what the regression gate should actually diff. A reader who needs a durable architecture for CLP genericity gets a better blueprint from A.

---

FINAL RANKING:
1. Response C
2. Response A
3. Response B


## Ranking tally (Borda)

- Response C (x-ai/grok-4.6): 8 pts
- Response A (openai/gpt-5.6-terra): 7 pts
- Response B (google/gemini-3.1-pro-preview): 3 pts

## Stage 3 — chairman synthesis (google/gemini-3.1-pro-preview)

**Stop the line. Do not dispatch a Run 23.**

The owner’s suspicion of a patch-reflex is dead-on. You are treating two different problems—a new self-inflicted disease and pre-existing known gaps—as a single convergence issue. In doing so, you substituted a false objective (*minimize open items*) for the actual objective (*print-key fidelity + every residual named and marked*). 

## Strategic Assessment (Before Any Change)

The failure in runs 20–22 is an **authority-boundary failure**, not a missing matching threshold. 

You conflated *numerical uniqueness in a pool* with *semantic identity*. By granting a verification oracle (designed to suspect/flag) direct write authority, you bypassed the structural logic (kinship, block ratification, locality) that previously earned a model mutation. Ingestion then enlarged the coincidence surface, making uniqueness mathematically weaker, not stronger. 

Run 19 was the high-water mark on *keys*. The NP corruption (`3,969` vs print `3,831`) in Run 21 is a catastrophic Requirement 2 and Requirement 5 failure. Relying on the "police" to catch it after the fact is not a design; wrong machine writes happened. The write should have been structurally impossible.

Here is the ranked action plan to restore architectural boundaries without spending another 1-hour live run.

---

## Ranked Action Plan

### 1. E — Change the Control Point & Authority Architecture
**Rank: 1 (The structural correction; zero live runs required)**

Abandon the Run 20–22 head lineage as a ship candidate. Revert the working model to the pre-writer semantics (Run 19 key posture). 

To ensure this never happens again across any model, establish a strict, generic evidence-to-model state machine. The fundamental design rule must be: **Oracles observe; Executors mutate.**
* **Discovered/Verified:** Candidate evidence found. *May not mutate the model.*
* **Adjudicated:** Identity, period, units, sign, locality, and source lineage established. *May not mutate the model.*
* **Applied:** Binding written to a Raw/detail row. *Only executed by a deterministic executor applying a previously adjudicated binding.*

The fixed-point system must revert to being a high-signal *findings generator* for the agent to evaluate. 

### 2. A — Withdraw write authority from the oracle entirely
**Rank: 2 (Immediate disease removal)**

Execute this in the artifact immediately. Strip all fixed-point and verification components of mutation rights. 

Challenge to your framing: You are not "accepting slower convergence." **Convergence on keys already happened in Run 19.** What got slower in runs 20-22 was *counterfeit closure*. Action A is not a performance concession; it is the removal of a rogue writer. 

### 3. C — Rebuild the pre-dispatch REGRESSION GATE
**Rank: 3 (The operational shield)**

This is the exact legacy loss that allowed Run 21 to ship undetected. It must be a hard, offline release gate before any owner-hour is spent.

* **Crucial constraint:** Do not pin the baseline to Run 19's *cells* (which might fossilize a compensating reclass). Pin it to a **printed-key panel** (sales + segments, GP, NP, cash, CA/NCA/CL/NCL, equity, CFO).
* The gate must diff every applied binding, provenance change, and expected downstream impact. Any changed printed-key binding without a declared, evidence-supported manifest entry fails the build locally.
* *Note: C is a filter, not a cure. Built without A, it only tells you the writer failed after the fact. It must sit behind A.*

### 4. D — Ship the remaining gaps as Explicit Analyst Decisions
**Rank: 4 (Delivery)**

Do not spend an hour trying to force the machine to close genuine underdetermination. That violates Requirement 1 (residuals must be named/marked). 
* **The 12,116 BS reclass hole:** There is no unique destination evidence. Forcing a destination invents an answer. Name it, mark the balance impact, and flag it.
* **Segments (16/33):** If the required all-document, multi-table search is demonstrably complete, leave the rest visibly stale and red-flagged.
* **CFI/CFF ±593 twin:** Because the item is *named* and *printed* (bond issuance cash), treat it as a Raw-detail routing defect offline. If rigorous adjudication cannot identify the correct Raw destination without inventing data, leave it as an open twin. Open twins are allowed; silent key drift is not.

### 5. B — Do not adopt ">=2 independent agreeing sources"
**Rank: 5 / Reject completely**

The owner is right to suspect this patch. Source count does not equal identity. Two agreeing sources can simply be the same junk table repeated, or a coincidental tie across different statements. "Two sources" is just UNIQUE-IN-POOL with extra steps. If machine writes ever return, they must reinstate the full legacy identification stack (kinship, locality, block ratification), never a single-line numeric quorum rule.

---

## What NOT to do (Anti-Patterns)

1. **Do not dispatch Run 23** (or any live head) until the Regression Gate (C) exists and write authority (A) is completely revoked.
2. **Do not tune or harden the fixed-point writer** (e.g., adding "topological boundaries" or new confidence thresholds). A bad authority model cannot be fixed with better matching rules.
3. **Do not use balancing as proof of correctness.** A balanced model with misclassified cash flow or an invented reclass destination still fails the requirements.
4. **Do not attempt to formulaically "back out" printed keys** to force a balance. Keys are printed; they are the bedrock.
5. **Do not confuse "the police caught it" with "Requirement 5 held."** The objective is not post-write detection. The objective is governed, mathematically sound mutation boundaries. 

**Summary Execution:** Delete the oracle's write authority, build the offline print-key regression panel, roll back to Run 19's key semantics, and ship the three honest gaps as flagged residuals. That is a delivery. Chasing another 40-minute live run is not.
