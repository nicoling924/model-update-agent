# LLM Council transcript

## Question

# Question: the last-mile plateau — and where the next hour of the owner's time should go

## State (after 8 runs of the packetized redesign, all measured)

The architecture from your two prior sessions is live and stable:
packet queue, L0/L1, compile (write-arrays through a guarded chokepoint),
surgeon (decisions[] schema gate), Table Islands (grid-intact evidence),
Closing Bell, Atomic Reclass. Results reproducible across runs (~95 LLM
calls, ~40 min, flags falling: 67 -> 45): headline keys exact, CFO and
cash tie the statement, all forecast years balance, 15/33 segment rows
write with island citations, zero corruption ever, everything unproven
carries a written reason.

Three residues repeat identically across the last four runs:
1. ONE 1.0 rounding residual on the 2025 balance sheet (model in
   millions vs statement in yuan-2dp). The bell has vetted plug sites and
   rounding guidance — the agent still chooses a reasoned flag over the
   absorption every run.
2. CFI/CFF twin (~594, opposite signs). Breakthrough: the agent now NAMES
   the item ("发行债券收到的现金 593.5 — company books it under
   financing") — then flags instead of MOVING it between the model's own
   presentation rows. Its "from" pointed at the proven statement cell
   (untouchable), not the model's Others row; the card has now been
   clarified, untested.
3. Segments: newly discovered ROOT CAUSE — the FY25 report RE-BASED its
   product categories; the model's segment basis (清洁高效能源装备 etc.)
   is printed only in the FY24 annual report, which was NEVER IN THE RUN
   FOLDER until today. The owner's own cross-report method (locate the
   row in the prior report -> map to the current report's corresponding
   category) requires both documents; the FY24 AR is now added, islands
   tag CURRENT vs PRIOR-YEAR, and the method text explains prior-year
   islands are the map, current report is the only citable source.

## The pattern the owner flagged (correctly): plateau

The owner: "results are plateauing — think more before implementing."
Honest read: the recent iterations were card sentences and site lists —
fine-tuning, not design. And the three residues share ONE shape: the
agent reasons correctly to the answer and then UNDER-ACTS at the finish
(flag instead of the final move). Truth-outranks-balance teaching may
have overweighted caution at exactly the last mile.

## Questions

1. **The last mile.** Is the right design the "SIGNED ORDER" pattern: the
   agent's terminal output names the disposition with full evidence ("the
   residual is rounding; absorb 1.0 into X" / "move 593.5 from model
   investing-Others to financing-Others; evidence p12") and the
   DETERMINISTIC layer executes and verifies the named order (revert if
   the promised effect fails)? Agent decides, code executes-and-verifies.
   Or is under-action a prompt-balance issue (caution overweight) better
   fixed in the method text? Or should these two named residues simply
   ship as flags for the ANALYST (they are 30-second reviews) and the
   agent's job is done?
2. **The FY24 document.** With prior-year docs now present: what is the
   correct ARCHITECTURAL use — per-run cross-report mapping in compile
   cards (as now built), or a one-time BRIDGE LEARNED INTO _SPEC (the
   workbook's memory tab) so future runs inherit the segment mapping
   without re-deriving it? What guards keep prior-year data from
   poisoning current-year writes beyond the existing vintage classifier
   (prior docs uncitable)?
3. **Where the next owner-hour goes.** Each live run costs the owner one
   hour. Options: (a) run DFE again with today's additions (FY24 doc +
   clarified cards) to close the three residues; (b) run CLP instead —
   the redesign has NEVER flown on the second company, and
   organization-wide genericity is the stated goal; (c) both, in one
   dispatch each. Rank by information value per owner-hour.
4. **Plateau discipline.** What should the STOP criterion be for DFE
   polishing — when is this model DONE and the remaining deltas
   explicitly analyst-decision items (the _REPORT's job), so effort moves
   to genericity and the department rollout?

Constraints unchanged: pure gpt-5.6-luna, <60 min, always deliver, truth
outranks balance, four Police laws, teach thinking not compliance, no
symptom patches.


## Stage 1 — answers

### Response A — openai/gpt-5.6-terra

## 1. The last mile: use a bounded “SIGNED ORDER” executor, not a stronger prompt alone

The pattern is real: the agent is no longer failing to reason; it is failing to convert a supported conclusion into the permitted model-side action.

That is an architecture problem, not primarily a wording problem.

A better method sentence may help, but it cannot reliably solve the central ambiguity:

> “I know what should happen, but am I allowed to alter a model row after being taught to preserve source truth?”

The answer should be encoded in capabilities and state transitions, not inferred from prose every run.

### Recommended design: evidence-backed, capability-bounded execution orders

Have the agent emit one of three terminal dispositions:

1. **EXECUTE_ORDER**
   - A permitted model-side action with current-report evidence and explicit expected effects.
2. **ESCALATE_ANALYST**
   - A genuine policy, materiality, or semantic judgment remains.
3. **NO_ACTION**
   - The item is not an error, or no authorized action exists.

An `EXECUTE_ORDER` should be structured, not merely narrative. For example:

```json
{
  "disposition": "EXECUTE_ORDER",
  "action_type": "MODEL_PRESENTATION_RECLASS",
  "from_model_cell": "CashFlow.Investing.Others",
  "to_model_cell": "CashFlow.Financing.Others",
  "amount": 593.5,
  "unit": "CNY_millions",
  "direction": "decrease_from_increase_to",
  "evidence": [
    {
      "document_vintage": "CURRENT",
      "page": 12,
      "table": "Cash Flow Statement",
      "statement_cell": "发行债券收到的现金",
      "assertion": "classified as financing cash flow"
    }
  ],
  "preconditions": [
    "source_statement_cells_unchanged",
    "from_row_contains_the_same_amount",
    "cash_total_unchanged"
  ],
  "expected_postconditions": [
    "CFI_CFF_twin_resolved",
    "CFO_unchanged",
    "ending_cash_unchanged",
    "all_cash_flow_invariants_pass"
  ],
  "reason": "The source classification is financing; only the model presentation row is being reclassified."
}
```

The deterministic layer then does all of the following:

- accepts only whitelisted action types;
- permits writes only to explicitly eligible model cells;
- prohibits statement/source/evidence cells as targets;
- verifies the evidence reference is current-vintage and structurally valid;
- checks units, signs, row identities, and amount availability;
- applies the change atomically;
- verifies the promised postconditions;
- rolls back if any postcondition fails;
- logs the order, before/after values, checks, and outcome.

That preserves the core division of labor:

- **Agent:** accounting interpretation and evidence-linked disposition.
- **Code:** constrained execution, invariant checking, rollback, and audit trail.

### Do not make the executor an unrestricted “obey the agent” mechanism

The executor should not let the agent invent edits. It should be a small capability system.

For example, permitted action families could be:

| Action family | Permitted when | Forbidden |
|---|---|---|
| `ROUNDING_ABSORPTION` | residual is within a predefined presentation-rounding tolerance; approved plug rows exist | changing source values; masking material imbalance |
| `MODEL_PRESENTATION_RECLASS` | same amount exists in a model presentation row; current evidence supports classification | moving or editing statement cells |
| `MODEL_LINK_REPOINT` | target/source row identity and evidence conditions pass | substituting prior-year numeric data |
| `SEGMENT_MAPPING_WRITE` | current-year source value exists and bridge maps taxonomy with sufficient support | writing prior-year values into current-year columns |

This is importantly not a hard-coded “move 593.5” patch or “absorb 1.0” patch. It is a generalized action grammar.

### The two current residues

#### A. The 1.0 balance-sheet rounding residual

This should normally be executable, not an analyst flag, if policy establishes:

- a materiality/tolerance rule appropriate to the model’s units;
- an ordered, whitelisted list of rounding plug rows;
- a rule that the plug is presentation-only and cannot overwrite a source-tied line;
- postconditions that all statement ties remain within permitted source-rounding tolerance.

The agent’s order identifies the eligible plug row and explains why it is the correct one. The executor checks that the residual is genuinely a rounding residual and that the chosen row is permitted.

If the organization has not decided the plug hierarchy, that is a **one-time policy decision**, not a recurring analyst review. Put the hierarchy in `_SPEC` and automate thereafter.

#### B. The CFI/CFF 593.5 twin

This is the clearest case for a signed order.

The model has identified the source item, its amount, its financing classification, and the true error: the model’s presentation row is wrong. The needed action is a reclass inside model-owned rows, not a statement edit.

It should no longer be acceptable for the agent to conclude “financing” and then emit only a flag if the action is within its allowed reclass capability. That is an execution defect.

### What belongs with the analyst instead

Keep analyst escalation for cases such as:

- the current report does not support the claimed classification;
- a classification choice materially changes a KPI and the organization has no policy;
- a segment mapping is many-to-many and requires an allocation assumption;
- the appropriate rounding plug itself is economically meaningful or policy-sensitive;
- source evidence conflicts across current-report disclosures.

So: do not ship these two named items as routine analyst flags merely because they are easy reviews. That would institutionalize the plateau. Ship them as flags only if they fail the generalized eligibility rules above.

### Prompt/method text still matters, but as a secondary control

Add one explicit terminal rule:

> Once the agent has established an eligible, evidence-supported model-side correction, it must emit either an executable order or a specific reason that no authorized action class applies. A flag is not an allowed substitute for an authorized correction.

That teaches the correct decision boundary. But the durable fix is the executor and its permitted action classes.

---

## 2. FY24: build a governed temporal bridge, not a globally “learned” mapping

The correct answer is a hybrid:

1. **Derive the cross-report mapping from the report pair when needed.**
2. **Persist the result as a versioned, entity-specific temporal bridge.**
3. **Have future runs consume that bridge when its source fingerprints and applicability conditions match.**
4. **Never let it become a generic, timeless `_SPEC` fact.**

The mapping is not merely a compile-card convenience. It is a reusable, auditable interpretation of a company-specific reporting-basis change. Re-deriving it from scratch every run wastes time and creates avoidable nondeterminism.

But it is also not a universal model rule. Product taxonomies can rebase again, corporate structures change, and terms that look similar can acquire different scope.

### Recommended artifact: an entity/report-basis bridge

Store a dedicated governed artifact, potentially on the workbook memory tab but logically separate from global specification:

```text
Bridge ID: DFE_SEGMENT_2024_BASIS_TO_2025_BASIS_v1
Entity: DFE
Prior report: FY24 AR, document hash/version
Current report: FY25 AR, document hash/version
Prior taxonomy: 清洁高效能源装备 / ...
Current taxonomy: FY25 disclosed categories / ...
Status: validated / provisional / analyst-approved
```

Each mapping row should include at least:

- entity and legal/reporting perimeter;
- prior and current report identities, year, and document hashes;
- prior model taxonomy member;
- current-report category/member;
- mapping relationship: one-to-one, many-to-one, split, discontinued, renamed, unclear;
- current-year source location for the value ultimately written;
- prior-year source location used only for semantic

### Response B — google/gemini-3.1-pro-preview

The owner’s instinct is dead-on: you have hit the **Pareto boundary**. 

The agent is behaving exactly as trained. You drilled "truth outranks balance" and "do not corrupt the grid" so deeply into its core that when it reaches the final inch of an ambiguous accounting reclass or a rounding plug, it chooses to hand you a perfectly diagnosed, perfectly sourced "ticket" rather than risk an unproven write. 

This is not a failure. It is the definition of a stable system. Here is the architectural read on the final mile, the new document, and where your time goes next.

### 1. The Last Mile: Ship the Flags (The Analyst Handoff Boundary)
Do not build the "Signed Order" deterministic layer, and do not tweak the prompt to force the agent to act. **The agent's job is done.**

*   **The Rounding (1.0):** The agent found the 1.0 difference, traced it, proved it was rounding, and named the plug site. Fixing it takes you 10 seconds. Automating the execution of this plug takes hours of coding a deterministic "Resolution Engine." 
*   **The CFI/CFF Twin (594):** Moving a cash flow item from Investing to Financing is an **accounting opinion**. The agent found the offset, named the item (*发行债券收到的现金*), found the page, and flagged it. *This is exactly what a junior analyst should do.* If it moves it silently, it assumes a mandate it shouldn't have.

**Verdict:** Declare victory on these. Ship them as flags in the `_REPORT`. The goal of the system is not a 0-flag model; the goal is a 0-corruption, 100%-traced model with a 5-minute human punch-list. You have achieved this.

### 2. The FY24 Document: One-Time Bridge into `_SPEC`
Do **not** include the FY24 report in the run folder for future runs. Using runtime compute to cross-reference a 300-page prior-year document just to figure out what a company renamed its segments is an expensive, hallucination-prone architectural anti-pattern. 

*   **The Concept:** A segment rebasing is a *structural definition change* by the company, not a runtime data point. 
*   **The Implementation:** This belongs in `_SPEC`. You do a one-time translation (mapping FY25's new segment names to the model's legacy segment rows) and bake that mapping into the `_SPEC` memory tab. 
*   **The Guardrail:** By removing the FY24 document from the run folder entirely, you guarantee zero risk of prior-year data poisoning the current-year writes. The `_SPEC` simply tells the agent: *"The current document calls it X; write that data to model row Y."*

### 3. Where the Next Owner-Hour Goes: Option B (Run CLP)
**Run CLP immediately. Do not run DFE again.**

Ranked by information value per owner-hour:
1.  **Run CLP (Company 2):** *Massive ROI.* You have built a beautifully tight architecture (Islands, Surgeons, Chokepoints, Atomic Reclass) heavily optimized around DFE's eccentricities. You need to know *immediately* if this architecture shatters when it hits CLP's completely different reporting style. 
2.  **Both:** Only if the dispatch requires zero babysitting. If you have to review two outputs, your brain will get dragged back into DFE's minutiae.
3.  **Run DFE again:** *Zero ROI.* You are polishing a cannonball.

### 4. Plateau Discipline: The STOP Criterion
A financial modeling agent is **DONE** when it meets this specific Stop Criterion:

1.  **Zero Silent Failures:** No math is forced; no grid is corrupted.
2.  **Zero Hallucinated Citations:** Every written number has an exact Table Island coordinate.
3.  **The Remaining Flags are Accounting Judgments:** The unresolved items require an analyst's opinion (e.g., M&A adjustments, reclassifying capitalized R&D, moving CFI to CFF) or are simple rounding plugs. 
4.  **Human Resolution Time < 15 Minutes:** The time required for a human to read the agent's flagged reasons and clear the `_REPORT` is a fraction of the time it would take to build the model from scratch.

DFE has met this criterion. The baseline is established. Close the DFE folder, leave the three flags as intentional human hand-offs, update the `_SPEC` with the segment map, and **deploy the architecture against CLP.**

### Response C — anthropic/claude-sonnet-5

# Analysis: last-mile execution, document architecture, and where the hour goes

## 1. The last mile: SIGNED ORDER is the right fix — and it's architectural, not a prompt-balance bug

Look at what's actually happening in all three residues: the agent gets to the *specific, named, evidenced* answer every time. "Absorb 1.0." "Move 593.5 from investing-Others to financing-Others, evidence p12." It is not confused. It stops one step short of acting on its own correct conclusion.

That is not miscalibrated caution from the truth-outranks-balance teaching — it's the agent correctly recognizing that **it has no safe way to act on its own conclusion**. Right now, "decide" and "write" live in the same untrusted pass. Given the hard-won zero-corruption invariant, an agent that treats "self-executed irreversible write" as higher-risk than "flag and let a human write it" is reasoning *correctly under the current architecture*. Fixing this with prompt language ("be more decisive") would just trade this failure mode for corruption risk — exactly the kind of symptom patch the constraints rule out.

The actual gap is a missing primitive: **decide and execute are not separated, and there is no deterministic verification of a promised effect.**

**Design: SIGNED ORDER.**
- Agent's terminal output is a structured order: `{disposition, from, to, amount, evidence, promised effect}` — e.g. "move 593.5 from model investing-Others to model financing-Others; CFI Δ −593.5, CFF Δ +593.5; evidence p12."
- A deterministic layer (not the LLM) parses the order, applies it *only* through the existing guarded chokepoint, checks the promised effect actually happened (residual → 0.0, CFI/CFF deltas match), and **reverts + flags** if the check fails.
- The agent never writes directly; it only signs orders. Zero-corruption is preserved because the trust boundary moves to deterministic verification, not agent self-restraint.

This is strictly better than "loosen the caution" because it doesn't touch the agent's epistemic behavior at all — it still must name evidence and disposition exactly as it does now. It just gives that correct output somewhere safe to land.

**For the two residues in hand right now:** ship them as analyst flags today — they're genuinely 30-second reviews and the architecture fix isn't built yet, so don't block on it. But don't mistake that for the design answer. If SIGNED ORDER isn't

### Response D — x-ai/grok-4.6

**The three residues are one missing verb, not three tuneables.** The agent already reaches the answer; the runtime has no first-class *disposition* that is allowed to finish. Do not loosen caution. Do not ship a new mega-pattern this hour. Measure the two interventions already built, then stop polishing DFE.

---

### 1. The last mile

**Signed Order is the right *shape*, and you mostly have it.** Surgeon `decisions[]` + Atomic Reclass + the compile chokepoint *are* “agent decides, code mutates-and-verifies.” What you lack is a **typed terminal Decision** that covers the leftover class of act: *dispose of an understood residual on model-owned presentation cells*. That is design. Card-boldness is not.

Do **not** implement a new SIGNED ORDER stack before the next measurement run. Do **not** fix under-action by rebalancing “truth vs. finish” in prose. Truth-outranks-balance is not the bug; **FLAG is being used as the only legal last mile** because the other verbs do not fit.

Split the three residues — they are not the same act:

| Residue | What it actually is | Right verb | Wrong response |
|---|---|---|---|
| 1.0 BS | Unit/scale remainder (millions vs yuan-2dp) after identities already hold | `ABSORB_ROUNDING` into a **bell-vetted model site**, with promised identity, or **FLAG_FOR_ANALYST** if no site is legal | “If residual==1.0 plug X”; “be braver” |
| CFI/CFF 593.5 | Model presentation reclass the agent already *named* | Existing **Atomic Reclass**, `from` = model investing-Others, `to` = model financing-Others. Statement cell is evidence, never a write target | New order type; moving the proven statement cell |
| Segments | Missing prior-year *map*, now supplied | Compile from **current** islands, prior-year as correspondence only | Memorizing FY24 values into `_SPEC` |

**Signed Order, if/when you add it, is a schema extension, not a personality change:**

```text
Decision {
  verb: FLAG | ABSORB_ROUNDING | RECLASS_MODEL | WRITE_FROM_ISLAND
  targets: model_cells[]          // statement cells illegal
  evidence: citations[]
  promised_effect: {identities, deltas}
}
```

Deterministic layer applies → verifies promised effect → revert + FLAG on miss. Agent still writes the reason. **FLAG is correct iff the agent cannot name a model-owned target and a promised effect.** If it can name them, FLAG is a failed terminal act, not prudence.

Prompt-balance (“caution overweight”) is a symptom patch. It will trade last-mile under-act for Police-law violations. Teach the **decision boundary**, not compliance with “finish more often.”

**Ship-as-flags is honest only for policy.** The 1.0 *site* can be an analyst item (materiality / presentation policy) if identities already tie and the bell’s plug list is what the agent refuses to pick among. The 593.5 move is **not** policy once the agent has named `发行债券收到的现金` and the company booking. Leaving that as a forever-flag is declaring a system bug “analyst work.” Segments were an input hole, not a judgment call.

---

### 2. FY24 document

**Architectural use: prior-year is a MAP, never a SOURCE.** The FY25 re-base is the proof. A bridge frozen into `_SPEC` as write authority will go stale the next time they re-base — and they just did.

Correct split:

- **Per-run (compile):** build a `SegmentBridge` packet. Prior-year islands supply *name correspondence*. Current-year islands supply *the only writable values and the only citations*. If the map is ambiguous, FLAG the row. Do not invent a current category.
- **Persisted `_SPEC` (optional, later):** store the bridge as a **lockfile / expected mapping**, a hint the next run must *confirm or invalidate*. Not a write key. Not a memory of amounts. If current categories ≠ last-run categories, drop the lockfile and re-derive. That is how you get cheap inheritance without teaching the workbook a lie.

**Guards (beyond vintage = uncitable):**

1. Write-set = current-year model cells only.
2. Value conduit = current-year islands only. Prior-year numbers never enter write-arrays.
3. Bridge carries names/ids, not amounts.
4. Every written segment row’s citation vintage must be CURRENT. Prior-year islands may appear only in the mapping reason.
5. If the current report already prints the category, prior is not consulted.
6. Re-base detector: category-set change invalidates any stored bridge before compile.

Do not “learn the mapping into `_SPEC` so we don’t re-derive.” Re-derivation is the feature that survived FY25. Caching is an optimization *after* CLP shows the cost is real.

---

### 3. Next owner-hour (information per hour)

Pre-commit the reading of the next run. Do not implement more cards first.

| Rank | Option | Why |
|---|---|---|
| 1 | **(a) one DFE run**, today’s folder as-is (FY24 + clarified CFI `from`) | Two causal interventions sit **untested**. This hour distinguishes *missing input / bad target* from *structural under-act*. That bit decides whether DFE is done. ~40 min already fits the box. |
| 2 | **(b) CLP** | Highest *new* design information (genericity is the actual goal; DFE residues are already named). Right **second** hour, or the first hour only if you refuse to spend another DFE cycle on principle. |
| 3 | **(c) both** | Two owner-hours. Splits attention before you know whether DFE even still has a residue. Cannot honestly fit two ~40 min runs in one `<60 min` deliver. |

**How to read (a) — write this down before the run:**

- CFI/CFF closes → targeting bug, Atomic Reclass is sufficient. No new pattern.
- Segments write with **current** cites → input hole, bridge-as-map is sufficient. Do not freeze into `_SPEC` yet.
- 1.0 remains, reasoned FLAG → classify as analyst policy **or** add only `ABSORB_ROUNDING` (bell sites, verify-and-revert). No more site lists.
- Same under-act shape on CFI and/or segments **after** these inputs → **STOP DFE polish.** The next change is the typed Decision, and it must be specified against a second company so you do not fit DFE.

If you skip (a) and go (b) now, you learn genericity but you still do not know whether DFE is allowed to stop. That is why (a) wins **this** hour, not because DFE still deserves a program of work.

---

### 4. Plateau discipline — STOP criterion

**DFE is DONE when every remaining delta is either closed or a written human policy choice that the method cannot make without inventing a rule.** Effort then moves to CLP / department rollout. The `_REPORT` lists those items as analyst-owned, with the agent’s evidence attached.

**Done (you are already close):**

- Identities hold: CFO/cash, statements, all forecast years balance.
- Headline keys exact; Table Islands intact; zero corruption; reproducible.
- Unproven items carry a written reason.
- After **one** measurement run on the last *causal* input change (FY24 + CFI target), residues do not change shape.

**Analyst-decision (legal leftovers):**

- Where a sub-material scale/rounding residual is absorbed, if several bell sites are equally legal.
- Segment rows with **no defensible current-year cite** after the bridge ran.
- Presentation policy the template and the company filing genuinely disagree on *and* the method refuses to lie.

**Not done (do not launder these into `_REPORT`):**

- Agent names the move, points at evidence, then FLAGs — that is a missing/broken verb.
- Wrong `from` (statement vs model) — targeting bug.
- Missing prior-year map — input bug, now testable.
- Another card sentence, site list, or “please absorb” line — fine-tuning, which is what plateaued.

**Hard stop rule:** no further DFE-only design after the next run unless a residue **changes kind**. Same three leftovers again means the model is done as a *system* and unfinished only as *policy*, or the Decision verb is the next design and it is built for the department, not for DFE.

**Next hour of owner time:** dispatch DFE once, no new implementation. Interpret against the table above. Then CLP. Do not spend the hour inventing Signed Order; spend it finding out whether you still need one.


## Stage 2 — peer reviews

### Review by openai/gpt-5.6-terra

## Response A

### What it does well
- Correctly identifies the central issue as an **architecture/capability gap**, not primarily a prompt-tone problem. The agent has reached an evidence-supported conclusion but lacks a safe, authorized way to convert that conclusion into a model-side action.
- Gives a strong version of Signed Order: structured dispositions, whitelisted action types, explicit preconditions and postconditions, model-cell-only targets, atomic application, verification, rollback, and audit logging.
- Properly distinguishes source evidence from model-owned presentation rows. Its handling of the 593.5 item is especially sound: the filing cell is evidence, while the model’s investing/financing “Others” rows are the permissible reclass targets.
- Avoids a residue-specific patch by proposing generalized action families such as `ROUNDING_ABSORPTION` and `MODEL_PRESENTATION_RECLASS`.
- Gives a thoughtful hybrid answer on FY24: derive the bridge from the report pair, persist it as an entity- and version-specific governed artifact, and do not treat it as a timeless global `_SPEC` fact.

### What it does poorly
- As provided, it is incomplete: it cuts off during the FY24 bridge discussion and does not visibly answer the owner-hour ranking or define a DFE stop criterion.
- It moves fairly quickly to implementation of a substantial executor without sufficiently emphasizing the value of first testing the newly added FY24 document and clarified CFI/CFF target. That risks adding architecture before determining whether the remaining behavior is simply caused by the previously missing input and malformed target.
- Its bridge recommendation is good in principle, but it needs the sharper distinction that persisted mappings should be treated as a validated, invalidatable lockfile or hint—not as autonomous write authority.

## Response B

### What it does well
- It clearly recognizes the plateau and appropriately values the achieved invariants: reproducibility, zero corruption, traceability, and a bounded human review queue.
- It gives a clean and practical stop criterion around zero silent failures, valid citations, and short human resolution time.
- It correctly emphasizes that cross-company testing matters and that CLP is highly valuable for assessing genericity.
- It usefully warns against investing large implementation effort merely to eliminate a trivial residual if that capability will not generalize.

### What it does poorly
- Its main conclusion is too conservative. The 593.5 CFI/CFF issue is not inherently an unresolved “accounting opinion” once the company’s current-report classification is proven and the required edit is strictly a model-presentation reclass between model-owned rows. Treating this as permanent analyst work institutionalizes a known missing execution capability.
- It incorrectly frames Signed Order as an unnecessary “Resolution Engine.” A small, bounded, deterministic disposition executor is not equivalent to granting the agent broad authority. It is exactly the mechanism that can preserve the Police laws while allowing a proven correction to finish safely.
- Its FY24 recommendation is too absolute. Freezing a one-time mapping into `_SPEC` and removing FY24 from future runs reduces auditability and leaves the mapping vulnerable to the next rebase, perimeter change, or taxonomy change. Prior-year material should remain available as a governed semantic bridge, even though its values remain uncitable and unwritable.
- “Run CLP immediately” undervalues the information from one DFE measurement run after two concrete causal changes: the added FY24 report and the clarified model-side `from` target. Calling that run “zero ROI” is not justified.
- Its stop criterion wrongly includes items such as a proven model reclass among ordinary analyst judgment items. A repeated proven-but-unexecuted action is not necessarily a legitimate handoff; it can be evidence of a missing verb.

## Response C

### What it does well
- Its visible portion gives an excellent diagnosis of the last-mile problem. It clearly explains why “be more decisive” would be a symptom patch that could trade under-action for corruption.
- It correctly identifies the missing primitive as separation of judgment from execution: the agent should issue an evidence-backed order, while deterministic code applies, verifies, and rolls it back if necessary.
- It preserves the intended trust boundary: the agent interprets evidence; code enforces allowed targets, invariants, and reversibility.
- It makes the useful transitional distinction that the two current items can be analyst-cleared now while the architecture is improved for future runs.

### What it does poorly
- As supplied, it is materially incomplete. It stops mid-sentence in the first question and does not answer the FY24 architecture, rank the next owner-hour options, or provide a plateau stop criterion.
- The visible argument is strongly correct, but it does not yet address an important sequencing issue: whether to build Signed Order immediately or first run the already-improved DFE packet to determine how much of the plateau remains after the causal input and targeting fixes.

## Response D

### What it does well
- It gives the most nuanced overall answer. It sees the three residues as related by a missing terminal disposition capability while still distinguishing their different actual actions: rounding absorption, model presentation reclass, and cross-report taxonomy mapping.
- It correctly rejects prompt rebalancing as the primary remedy. “Truth outranks balance” is not the defect; the agent lacks a legal terminal verb for a supported correction.
- It makes excellent use of the architecture already present. Rather than proposing an entirely new uncontrolled subsystem, it frames Signed Order as a typed extension to `decisions[]`, Atomic Reclass, and the guarded chokepoint.
- Its proposed decision schema is compact and well-governed: typed verbs, model-cell targets only, citations, and promised effects followed by deterministic verification and rollback.
- Its FY24 approach is particularly strong: prior-year data is a semantic map, never a value source; current-year islands are the sole value conduit and citation source; an optional persisted bridge is a confirm-or-invalidate lockfile rather than permanent write authority.
- It gives concrete additional guards beyond vintage classification: current-only write set, current-only value conduit, bridge without amounts, current citations for every write, and taxonomy-change invalidation.
- Its owner-hour recommendation is disciplined. One DFE run tests two already-made causal interventions and yields a clear decision tree; then CLP tests genericity. It correctly treats “both” as two owner-hours rather than pretending it is free.
- Its stop criterion sharply distinguishes legitimate analyst policy decisions from defects that must not be laundered into `_REPORT`, especially “the agent names the move and evidence, then flags.”

### What it does poorly
- The claim that the system “mostly has” Signed Order may slightly overstate what is currently implemented. Existing components may provide some pieces, but a typed terminal disposition plus promised-effect verification is still a real extension.
- Its hard-stop language is slightly compressed: if a proven reclass continues to be flagged, that should not simply become “DFE done”; it should be explicitly classified as a department-level missing capability to design and validate across companies. The response implies this, but could state it more directly.
- Its preference for a DFE run first is well defended, though reasonable operators could choose CLP first if genericity is overwhelmingly more urgent. The response properly acknowledges that alternative but could quantify the tradeoff more explicitly.

FINAL RANKING:
1. Response D
2. Response A
3. Response B
4. Response C

### Review by google/gemini-3.1-pro-preview

**Evaluation of Responses**

**Response A:**
- **What it does well:** The response provides a very strong, well-structured answer to Question 1. The proposal for an `EXECUTE_ORDER` schema is concrete, and the table breaking down permitted action families perfectly grasps the architectural need for a bounded deterministic capability. It correctly identifies that prompt engineering is a "symptom patch" here. 
- **What it does poorly:** The response cuts off midway through Question 2 and completely fails to answer Questions 3 and 4. Because it is highly incomplete, it cannot be ranked highly despite the quality of its initial arguments.

**Response B:**
- **What it does well:** This is a complete response that answers all four questions clearly. It takes a definitive stance on the analyst handoff boundary (Q1) and provides a highly pragmatic, actionable STOP criterion (Q4). 
- **What it does poorly:** Its advice for Q2 (removing the FY24 document and hardcoding the map into `_SPEC`) goes against the systemic goal of generic architecture. If the model is expected to handle *any* company (like CLP next), hardcoding segment mappings into a global memory tab creates brittle, company-specific technical debt. Furthermore, its recommendation for Q3 (abandon DFE immediately) misses a crucial engineering step: testing the variables that were *just* changed before pivoting to a new environment. 

**Response C:**
- **What it does well:** It accurately diagnoses the root cause of the last-mile plateau as an architectural missing verb rather than an LLM prompt issue. 
- **What it does poorly:** The response cuts off at the very end of Question 1. It provides zero insight into Questions 2, 3, and 4. It is the most incomplete response of the batch.

**Response D:**
- **What it does well:** This response is exceptional. It perfectly mirrors the highly specific, technical tone of the prompt and understands the existing architecture deeply. For Q1, it correctly partitions the residues into their respective right verbs (rounding vs. atomic reclass) and refuses to implement a massive new pattern before measuring the current state. For Q2, it provides brilliant, airtight guardrails to ensure prior-year data acts only as a map and never poisons current-year writes. For Q3, it provides the most logically sound engineering advice: run DFE *once* to test the causal interventions you literally just built, read the exact results, and *then* move to CLP. The STOP criteria (Q4) are rigorously defined.
- **What it does poorly:** There are no significant flaws in this response. It is a masterclass in architectural discipline and debug methodology.

FINAL RANKING:
1. Response D
2. Response B
3. Response A
4. Response C

### Review by anthropic/claude-sonnet-5

# Individual Evaluations

**Response A:** Provides a genuinely strong, detailed architectural answer to Q1 — the three-way disposition schema (EXECUTE_ORDER / ESCALATE_ANALYST / NO_ACTION), the JSON order structure, and the table of permitted action families are concrete and well-reasoned. It correctly distinguishes a "generalized action grammar" from a hardcoded patch. However, the response is **critically incomplete**: it trails off mid-sentence partway through Q2 ("prior-year source location used only for semantic...") and never addresses Q3 or Q4 at all. Given the question explicitly asks four distinct questions, leaving half unanswered is a severe deliverable failure regardless of the quality of what is present.

**Response B:** Coherent, decisive, and well-written, taking a clear contrarian stance: ship the flags, don't build new machinery, don't cache the bridge in the run folder, go straight to CLP. This is a legitimate reading of the plateau ("declare victory"). However, it mischaracterizes the CFI/CFF residue as requiring "an accounting opinion" when the move is confined to the model's own presentation rows (not the proven statement cell) — the question's framing suggests this is closer to mechanical execution than judgment, which undercuts B's core argument for that item. Its FY24 answer (remove the document from the run folder) also doesn't engage with the question's explicit ask for guards "beyond the existing vintage classifier" — it just discards the input rather than layering additional guardrails. Answers all four questions, but with less nuance and some logical friction versus D.

**Response C:** Contains a sharp, original insight for Q1 — that the agent's under-action is not miscalibrated caution but *correct reasoning under the current architecture* where decide-and-write share the same untrusted pass, and that prompt tuning would trade under-action for corruption risk. This is arguably the single best paragraph across all four responses. But the response is **severely truncated**, cutting off mid-sentence before even finishing Q1's discussion, and entirely omitting Q2, Q3, and Q4. This is a more severe completeness failure than A's.

**Response D:** The only response that fully and carefully answers all four questions. It offers a nuanced Q1 take (the existing architecture already implements most of "Signed Order"; the gap is a specific missing verb for absorption), correctly separates the three residues into different categories with different correct dispositions, and pushes back on treating the named CFI/CFF move as permanent analyst policy. Its Q2 answer directly engages the "beyond vintage classifier" framing with a concrete numbered list of guards, and proposes a nicely balanced "lockfile, not memory" compromise between per-run and _SPEC-baked mapping. Its Q3 ranking is thoughtful, arguing for testing the untested interventions before dispatching to CLP, with explicit interpretive criteria for the run's outcome. Its Q4 stop criteria differentiate "done," "analyst-decision," and "not done" categories precisely. This is the most complete, most internally consistent, and most directly responsive answer.

# FINAL RANKING:
1. Response D
2. Response B
3. Response A
4. Response C

### Review by x-ai/grok-4.6

## Response A
**Does well:** Strongest standalone *design* of the last-mile mechanism. It correctly treats under-action as a missing capability/state-transition, not a wording problem; proposes a typed `EXECUTE_ORDER` / escalate / no-action grammar; bounds the executor (whitelist, model-only writes, evidence vintage, atomic apply, postcondition rollback); and refuses to institutionalize the two named residues as forever-flags. The FY24 section starts in the right place: a versioned, entity-specific temporal bridge, not a timeless `_SPEC` fact.

**Does poorly:** It does not finish the brief. Q2 is cut off mid-sentence; Q3 (next owner-hour) and Q4 (STOP criterion) are absent. That is a hard miss against “always deliver” and against the owner’s actual decision this hour. The executor spec is also heavier than the constraint set allows *now*—a full action grammar before measuring two already-built, untested interventions. High architectural quality, incomplete product.

## Response B
**Does well:** Complete, readable, and decisive on all four questions. The Pareto / “0-corruption + short punch-list” framing is useful. The STOP criterion (no silent failures, no fake cites, leftover items are judgments, human clear time bounded) is operational. Ranking CLP high for *genericity* matches the stated department goal.

**Does poorly:** Several load-bearing calls are wrong. The CFI/CFF 593.5 item is not an “accounting opinion” once the agent has named the company’s own financing booking; leaving that as a junior-analyst ticket launders a targeting/execution bug. Baking the segment rebase into `_SPEC` as write authority, and deleting the prior-year doc, is the stale-bridge / lost-map failure mode the FY25 rebase just demonstrated. “Zero ROI” on one more DFE run ignores that FY24 + the clarified CFI `from` are **untested causal changes**. Declaring victory on flags is exactly the plateau the owner asked not to fine-tune into.

## Response C
**Does well:** Clean diagnosis of the real gap: decide and write share one untrusted pass, so flagging is rational under the current zero-corruption invariant. “Be more decisive” is correctly rejected as a symptom patch. SIGNED ORDER + deterministic verify-and-revert is the right primitive, and shipping today’s two residues as 30-second flags *until that exists* is honest.

**Does poorly:** It barely starts the exam. Only Q1 is substantially answered; the draft dies mid-sentence. No FY24 architecture, no hour ranking, no STOP rule. Thinner than A even on the part it covers (no capability table, no residue split). Incomplete relative to the four explicit questions.

## Response D
**Does well:** Best fit to the actual decision and the constraints. It keeps SIGNED ORDER as the *shape* but notices the runtime already has surgeon `decisions[]`, Atomic Reclass, and a compile chokepoint—so the hole is a typed terminal verb, not a new mega-stack this hour. It splits the three residues (rounding absorb vs model reclass vs missing map) instead of one slogan. FY24 is correctly “map, never source,” with write-set / citation-vintage / rebase-invalidation guards, and `_SPEC` only as a confirm-or-drop lockfile. Next hour ranks **one DFE measurement** first because two interventions are untested, with a pre-committed readout that decides whether DFE is done; CLP is the right *second* hour. STOP criterion is precise: leftover policy is analyst-owned; named-then-FLAG is not.

**Does poorly:** Denser and more hedged than B; it does not ship a full executor schema the way A does. Someone who wanted the Signed Order spec *written now* will find it thinner. The “a first, then CLP” call could be wrong if the owner’s only scarce resource is attention and they refuse another DFE cycle on principle—but it is the information-theoretically correct call given untested cards/docs.

FINAL RANKING:
1. Response D
2. Response A
3. Response B
4. Response C


## Ranking tally (Borda)

- Response D (x-ai/grok-4.6): 16 pts
- Response A (openai/gpt-5.6-terra): 10 pts
- Response B (google/gemini-3.1-pro-preview): 10 pts
- Response C (anthropic/claude-sonnet-5): 4 pts

## Stage 3 — chairman synthesis (google/gemini-3.1-pro-preview)

The council is in unanimous agreement: the last-mile plateau is an architectural state, not a prompt-tuning problem. Your system is exhibiting a rational response to its own constraints. You have drilled "truth outranks balance" and "zero corruption" so effectively that when the agent reaches the final inch of an ambiguous reclass, it recognizes it lacks a safe, authorized verb to finish the job. It chooses to hand you a perfectly diagnosed ticket rather than risk an unproven write.

Here is the collective architectural synthesis for the last mile, the FY24 document, your next hour, and the definitive stop criteria.

### 1. The Last Mile: Extend the Verbs, Do Not Tweak the Prompt

**Do not loosen the agent's caution.** Altering the prompt's balance of "truth vs. finish" is a symptom patch. It will simply trade your current under-action for Police-law violations (corruption). 

The "Signed Order" pattern is the correct design, but you do not need to build a massive new runtime engine. Your existing architecture (Surgeon `decisions[]`, Atomic Reclass, guarded chokepoint) already implements the core of "agent decides, code mutates-and-verifies." What you are missing is a **typed terminal Decision verb** for disposing of an understood residual on model-owned presentation cells.

Split the remaining residues—they are not the same act, and should not be painted with one brush:

*   **1.0 BS Rounding (Scale/Unit mismatch):** The correct verb is `ABSORB_ROUNDING`. The agent names a bell-vetted model site and promises an identity. The deterministic layer applies it, checks the math, and reverts + flags if it fails. If no site is legal, *then* it is an analyst flag.
*   **593.5 CFI/CFF Twin:** This is not an "accounting opinion" if the agent has already found the item, named the company's booking (*发行债券收到的现金*), and proven the classification. The correct verb is your existing `RECLASS_MODEL`. The statement cell is the *evidence*; the model's investing/financing "Others" rows are the *targets*. Flagging here is a targeting/execution bug, not a policy handoff.

**Verdict:** Implement a structured Decision schema extension (e.g., `verb: FLAG | ABSORB_ROUNDING | RECLASS_MODEL`). The deterministic layer applies, verifies the promised effect, and reverts on a miss. **FLAG is correct if and only if the agent cannot name a model-owned target and a promised effect.** If it can name them, a flag is a system failure.

### 2. The FY24 Document: A Map, Never a Source

The recent FY25 rebasing proves exactly why you **cannot** permanently learn this bridge into `_SPEC`. A one-time map frozen into memory as "write authority" will go stale and silently poison the model the next time the company changes its reporting perimeter or taxonomy. 

**Architectural Use:** 
Prior-year documents must act purely as a semantic map. 
*   **Per-run compile:** The agent builds a `SegmentBridge`. Prior-year islands supply *name correspondence* only. Current-year islands supply the *only writable values* and the *only citations*. 
*   **Optional caching (`_SPEC`):** Store the bridge as a "lockfile" or expected mapping hint that the next run must confirm or invalidate. If the current categories do not match the last-run categories, the lockfile is dropped and the agent re-derives. 

**Strict Guards (Beyond Vintage Classifier):**
1.  **Write-set:** Current-year model cells only.
2.  **Value conduit:** Current-year islands only. Prior-year numbers never enter write-arrays.
3.  **Bridge payload:** Carries taxonomy names/IDs, never amounts.
4.  **Citation requirement:** Every written segment row’s citation vintage must be CURRENT. Prior-year islands may appear only in the written reasoning/mapping evidence.
5.  **Re-base detector:** Any change in the category-set invalidates any stored bridge before the compile step.

### 3. Where the Next Owner-Hour Goes (Ranked by ROI)

Do not spend your next hour building the Signed Order extension. Spend it reading the measurements of what you just built.

**Rank 1: (a) Run DFE again, exactly as-is.** 
You have two causal interventions sitting *untested* in the folder (the FY24 doc and the clarified CFI `from` card). You must run this to distinguish between *missing input/bad target* and *structural under-act*. If the segments now write and the CFI twin closes, you don't need a massive new architectural pattern. ~40 minutes fits your constraints.

**Rank 2: (b) Run CLP.** 
Highest *new* design information. Genericity is the actual goal. This is the right *second* hour. (Or the first hour only if you stubbornly refuse to spend another cycle on DFE on principle).

**Rank 3: (c) Both.** 
Splits your attention before you know whether DFE even still has a residue. Guaranteed to blow past your `<60 min` constraint. 

### 4. Plateau Discipline: The STOP Criterion

A financial modeling agent is **DONE** when every remaining delta is a genuine, written human policy choice that the method cannot make without hallucinating a rule. Once DFE hits this criterion, the model is done as a system, effort shifts to CLP/genericity, and remaining items become the `_REPORT`'s job.

**Done:**
*   Identities hold (CFO/cash, statements, forecast years).
*   Zero silent failures; zero corrupted grids.
*   Every unproven item carries a written, cited reason.
*   After your next measurement run (testing the new inputs), the residues *do not change shape*.

**Legitimate Analyst-Decision (Ship as Flags):**
*   Choosing between multiple legally valid bell sites for a rounding absorption (if company policy isn't codified).
*   Segment rows that genuinely have *no defensible current-year cite* even after the bridge has run.
*   True presentation policy disagreements between the template and the filing where the agent correctly refuses to lie.

**Not Done (Do Not Launder into `_REPORT`):**
*   The agent names the move, points at the exact evidence, and then flags. (This requires the new verb).
*   Wrong `from` targets (statement vs. model). 

**Immediate Action:** Pre-commit to reading the next DFE run. Dispatch it. If the residues remain identically shaped despite the new inputs, *stop DFE polishing*. Your architecture is sound; build the `Decision` verb specifically against CLP to ensure cross-company genericity.
