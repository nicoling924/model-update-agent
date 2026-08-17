# LLM Council transcript

## Question

# Question: three specific walls after the packetized redesign proved itself

## What changed since the last council (your redesign was implemented)

Your packetized architecture is live and measurably transformed behavior
across 3 runs (all pure gpt-5.6-luna, ~40 min, ~90 LLM calls — HALF the
old cost; zero trace-spam; every packet ends in dispositions; honest
flags; no corruption; guards silent):

- run 10: balance FAIL(8) -> after two method edits (what the column IS;
  how a close ends) ->
- run 11: balance FAIL(1) — only the 2025 BS at 1.0; forecasts, Driver
  checks, cash tie all PASS via honest flagged plugs.
- run 12 (same code as 11 plus two information edits): balance FAIL(6) —
  but it is ONE 24.0 residual propagating into five forecast years; the
  Driver checks passed this time instead.

The redesign works. Three specific walls remain, and the owner's law is:
no symptom patches — design-level answers only.

## Wall 1 — segment rows never get WRITTEN (3 runs: skipped -> flagged -> flagged)

The owner's hard requirement: sales and gross-profit SEGMENT BREAKDOWNS
are key numbers and must be UPDATED, not flagged. The model's segment
rows (sheet "Driver") have ENGLISH labels ("Gas Turbine", "Hydro",
"Domestic/Overseas"); the disclosure is CHINESE, and the segment data
lives in MD&A tables that print ONLY the current year plus a 同比 %
change (no comparative column). Evidence architecture: a text-extraction
ledger of flat lines (line = label + numbers); table HEADERS are lost
(each cell's column meaning is gone). Consequences, all measured:
- label kinship dies cross-language -> evidence slices for segment rows
  are empty -> the compile packet honestly flags 30/33 rows;
- the implied-prior identity (current/(1+pct) == model prior; 13/0
  precision in an older stack that had structured table rendering) finds
  almost nothing through flat lines, and un-guarded it serves prose
  coincidences (measured: associate-stake 2.41%, FX-sensitivity 5%).
Options we see (choose/design): (a) port structured-table extraction
(pdfplumber tables -> "header: value | header: value" lines with per-cell
headers) into the ledger so number-anchored implied-prior regains its
precision; (b) give the compile packet the RAW TEXT of the few
segment-relevant pages and let the agent read the table directly and
write with citations (brains read, hands verify — an earlier side test
showed a raw-reading model beat the pipeline 82.5 vs 73.3 on identical
rows); (c) vision reads of those pages; (d) something better. Which, and
what guards keep precision without becoming a rulebook?

## Wall 2 — the endgame is still a draw: 1.0 vs 24.0 residuals across identical code

Runs 11 and 12 ran the SAME harness; one closed to 1.0, the other left
24.0 unplugged (the surgeon chose flag over plug that draw). The close's
QUALITY floor should not depend on the draw. Owner rejects behavior caps.
Candidate directions: L0 may not pick "deliver" while a residual has a
legal plug line open (is that a method fact or a forbidden steer?); a
final deterministic "closing bell" packet that re-runs the surgeon once
on every still-failing check with the method's ending paragraph; more
surgeon rounds; something else?

## Wall 3 — the CFI/CFF twin (~594 booked in the wrong section) survives everything

Both cash-flow section keys are off by the same ~594 with opposite signs
— one item sits in the wrong section. The repair context now auto-states
this insight. But the agent (two runs) flags both rather than finding and
moving the item. The component-level evidence exists (statement pages
were vision-read). Is this an information problem (give the surgeon the
two sections' component lists side by side in one packet), a packet
problem (a dedicated "misplaced item" packet type), or a capability limit
of the mid-tier model we should route to the Police/analyst honestly?

Constraints unchanged: pure gpt-5.6-luna; <60 min; generic across
organizations' models (no per-company logic; the cross-language case is
the NORM, not an edge); truth outranks balance; always deliver; teach
thinking, never compliance. Answer concretely: which option per wall,
the design, and what NOT to build.


## Stage 1 — answers

### Response A — openai/gpt-5.6-terra

## Wall 1 — Build a **dual-representation segment evidence path**: structured tables plus page reading

Choose **(a) and (b)** together. Use vision only as a targeted recovery layer, not as the default pipeline.

The problem is not primarily that the model cannot understand Chinese segment disclosure. It is that the evidence system destroys the structure needed to make that understanding actionable and verifiable.

### Design

Create a new evidence object: a **Table Evidence Packet**.

For each likely segment page, retain all of the following:

1. **Rendered source**
   - Page image or PDF crop.
   - Original text in reading order.
   - Page and bounding-box citations.

2. **Reconstructed table**
   - Every cell retains:
     - row label,
     - column header,
     - super-header if present,
     - period,
     - unit/currency,
     - page and cell location.
   - Render it to the ledger as meaningful facts, for example:

   ```text
   Page 84 | MD&A segment table
   Segment: 燃气轮机 / Gas Turbine
   Metric: revenue
   Current period: 2025
   Current value: RMB 1,240m
   YoY change: +12.4%
   ```

   Not:

   ```text
   燃气轮机 1240 12.4%
   ```

3. **Task-local raw reading window**
   - The compile packet for a segment row receives the relevant table image/text, not merely retrieved ledger snippets.
   - The agent can read the Chinese table directly, translate/align its meaning, and cite the source cell.

4. **Computed-but-not-trusted candidates**
   - If the table has current value and YoY %, compute:

   \[
   prior = \frac{current}{1 + yoy}
   \]

   But treat this as a candidate fact requiring table-context validation, not as evidence by itself.

### The right role for the model

Use the model for the semantic work:

- Is `燃气轮机` the same business concept as “Gas Turbine”?
- Is the disclosed measure sales, external revenue, gross profit, margin, or something else?
- Does the year, unit, entity scope, and segment definition match the model row?
- Is the YoY percentage associated with that specific current-value cell?

Use deterministic machinery only for:

- preserving table geometry and header inheritance;
- calculating implied priors;
- checking arithmetic;
- maintaining citation provenance;
- verifying that a write came from a cited source cell.

That is “brains read, hands verify” in a form that remains auditable.

### Guards that preserve precision without becoming a rulebook

Do not globally search for numeric identities in prose. An implied-prior candidate is admissible only when all of these are present in the same table evidence object:

1. A row label and a current value;
2. A visible period/current-year context;
3. A visible YoY/change header or row association;
4. Unit and sign interpretation;
5. A model target whose prior-period value agrees within the method’s normal rounding tolerance.

The key guard is **table-local semantic binding**, not a list of prohibited words or company-specific patterns.

Then require a separate verifier to answer:

> Does this citation support this exact metric, segment, period, and value?

If not, the candidate is rejected before writing.

### When to use vision

Use vision only when text/table reconstruction has low structural confidence, for example:

- merged headers cannot be recovered;
- OCR loses Chinese characters;
- columns are interleaved;
- the extracted table is visibly inconsistent with the page rendering.

Do not send all annual-report pages through vision. Route only pages selected as likely segment/MD&A disclosure pages and only when structured extraction is inadequate.

### What not to build

- A permanent English-to-Chinese segment-label dictionary.
- Per-company segment mappings.
- A global regex system for “current plus YoY implies prior.”
- Flat ledger lines with numbers detached from headers.
- A policy that lets raw-reading agents write without cell/page provenance.
- Full-document vision by default.

The generic architecture is: **table-aware evidence objects, raw-page semantic reading, and arithmetic verification.**

---

## Wall 2 — Make closure a terminal-state invariant, not a model preference

The problem is not that the surgeon needs “more encouragement.” The problem is that the current system allows a stochastic agent to decide whether a legal completion action is worth taking.

If a residual has a method-authorized, evidence-supported plug or repair available, delivery is not yet a valid terminal state.

That is not a behavior cap. It is an orchestration fact.

### Design: a deterministic Closing Bell state machine

At the beginning of the run, the Method packet should produce a compact **repair affordance registry**:

```text
Check: balance sheet balance
Legal repair action: permitted balance-sheet plug
Preconditions:
  - residual remains after source-based repair attempts
  - designated plug line exists
  - plug is method-authorized for this period/category
Formula:
  - plug = residual required to close
Required disclosure:
  - state it is a plug
  - preserve cited/source values
Verification:
  - rerun balance and cash checks
```

This is not a static rulebook. It is a run-specific extraction of the owner’s/model’s own method.

Then the Closing Bell operates deterministically:

1. Collect every failing check and residual.
2. For each one, identify method-authorized repair affordances whose preconditions are satisfied.
3. If no legal action exists:
   - flag honestly;
   - include the unmet condition and the evidence gap.
4. If one or more legal actions exist:
   - dispatch the corresponding repair packet;
   - require the surgeon to either execute it or prove which precondition is actually false.
5. Verify the resulting workbook/check state.
6. Repeat only while a newly executed legal action changes the state.

The controller, not L0, decides whether work remains. L0 can determine facts; it cannot declare completion while an eligible repair action is still pending.

### Is “L0 may not deliver while a legal plug is open” a forbidden steer?

No, if “legal plug is open” has a precise meaning:

> The method authorizes the action, all stated preconditions are satisfied, the amount is mechanically determined from the residual, and the action can be transparently disclosed and verified.

That is a method-completion condition, not an instruction to fabricate or optimize outcomes.

The prohibited version would be:

> Keep plugging until all checks pass.

The acceptable version is:

> Execute every method-authorized closing action whose preconditions are demonstrably met; otherwise explain why it is unavailable.

Truth still outranks balance. A plug is only used when the method explicitly makes it a truthful, disclosed repair instrument.

### Why not just add more surgeon rounds?

More rounds leave the terminal decision stochastic. Run 11 and Run 12 already demonstrate that.

A mandatory final packet is useful, but it must be a real state transition, not “please reconsider.” The Closing Bell should receive:

- failing check;
- residual;
- all remaining legal repair affordances;
- required preconditions;
- source/provenance state;
- the method’s ending paragraph;
- the exact workbook cells it may change;
- post-action checks it must rerun.

Then it must return one of only two dispositions:

```text
EXECUTED: [legal action], [cells changed], [verification results]
```

or

```text
UNAVAILABLE: [specific unmet method precondition], [evidence]
```

A bare `FLAG` is not a valid disposition if a legal repair affordance remains available.

### What not to build

- A residual-size threshold such as “always plug below 25.”
- A fixed number of “try harder” surgeon loops.
- A global instruction to force balance.
- A hidden controller that writes plugs itself without method authorization.
- A prompt that treats every mismatch as a plug opportunity.

Reserve a small, guaranteed time budget for Closing Bell rather than allowing earlier exploration to consume the entire run.

---

## Wall 3 — Build a dedicated **cash-flow reclassification reconciliation packet**

This is neither merely an information problem nor necessarily a capability limit. The current packet asks the model to infer a classification move from two disconnected failures. It needs to be presented as one constrained reconciliation problem.

The equal-and-opposite CFI/CFF residual is not proof of the item, but it is a powerful candidate-generation signal:

\[
\Delta CFI = -\Delta CFF
\]

with unchanged total cash flow strongly suggests a reclassification rather than a missing amount.

### Design: the Misplaced Item Packet

Create a dedicated packet whenever two cash-flow sections exhibit equal-and-opposite residuals within tolerance.

The packet should contain one coherent reconciliation ledger:

```text
Observed check state
- CFI discrepancy: +594
- CFF discrepancy: -594
- Net cash-flow discrepancy: 0
- CFO discrepancy: 0

CFI model components
- component, sign, amount, source classification, model classification, citation

CFF model components
- component, sign, amount, source classification, model classification, citation

Statement / note source components
- original label
- normalized English meaning
- reported amount
- statement section if disclosed
- note context
- page/cell/image citation

Candidate reclassifications
- Item A: 594; currently modeled in CFI; source evidence suggests CFF
- Item B: 594; currently modeled in CFF; source evidence suggests CFI
```

The model’s job is then narrow:

1. Identify which component, if any, accounts for the opposing residuals.
2. Determine its source-supported cash-flow classification.
3. Move the same item between sections.
4. Re-run CFI, CFF, total cash flow, and cash balance checks.
5. Cite why the classification is correct.

The operation is a **move**, not a plug:

```text
remove 594 from wrong section
add 594 to correct section
preserve total cash flow
```

### Candidate generation should be deterministic; classification should be semantic

A deterministic reconciler may nominate candidates based on:

- equal or rounded-equal amounts;
- sign relationship;
- opposite residual pattern;
- component/group membership from statement pages;
- matching source amount or a small explicitly disclosed aggregate.

But it must only generate candidates. It must not decide classification based on a keyword taxonomy.

The semantic agent decides whether, in the source context, the item is investing or financing. The verifier checks:

- the source citation really supports the item and amount;
- the proposed move preserves total cash;
- both section discrepancies close;
- the same amount was not duplicated or deleted.

### Should this go to Police/analyst?

Not as the default answer.

This is exactly the kind of bounded, evidence-rich reconciliation that the mid-tier model should handle if it is given the right packet. The present failure is consistent with packet shape, not proven inability.

Use Police/analyst as an honest escalation path only when:

- no source component matches the residual;
- several candidate moves fit arithmetically but classification evidence is ambiguous;
- the source classification is itself genuinely unclear;
- a possible explanation requires accounting-policy judgment not supported by the provided disclosure.

Police should adjudicate ambiguity, not substitute for a missing reconciliation packet.

### What not to build

- Independent CFI and CFF repair packets that never see each other.
- A universal “594 match means move it” rule.
- A hard-coded investing-versus-financing keyword list.
- Automatic section plugs that make the section totals pass.
- Broad subset-sum search over every cash-flow line in the filing.
- Escalation to a stronger role before presenting the relevant component evidence together.

### Response B — google/gemini-3.1-pro-preview

The packetized redesign is working exactly as intended: it localized errors, forced honesty, and dropped costs by containing the LLM’s blast radius. The three walls you are hitting are not model failures; they are architectural blind spots where the current packet boundaries artificially limit the agent's context or mandate. 

Here are the design-level answers for each wall, adhering strictly to the owner's laws.

### Wall 1: Segment Rows (The Cross-Language & Flat-Text Gap)
**The Diagnosis:** Flat-text extraction destroys the spatial relationship of table columns (Current Year vs. 同比 % Change). Without column headers, the LLM cannot confidently execute the implied-prior math (`current / (1+pct)`), and deterministic scripts fail because cross-language label matching ("Hydro" to "水电") requires semantic reasoning, not string-matching.
**The Design:** **Structured-Table Ledger + Raw-Read Sub-Packet (Combine A & B)**
1. **The Tooling Upgrade (A):** Port `pdfplumber` into the ledger to output structured lines (e.g., `[Label] | [Header 1]: Value | [Header 2]: Value`). This restores the absolute identity of the numbers without adding LLM cost. 
2. **The Packet Upgrade (B):** Create a dedicated "Segment Compile Packet." Instead of feeding this packet a few extracted lines based on keyword hits, feed it the structured raw text of the segment MD&A pages. 
3. **The Guard (Teach Thinking):** Instruct the model to perform the cross-lingual match and the implied-prior math explicitly in its reasoning trace before writing. 
   * *Format requirement:* `1. Semantic match: [English Row] = [Chinese Label]. 2. Data: Current = X, YoY = Y%. 3. Prior Math: X / (1 + Y) = Z. 4. Write Z.`
**What NOT to build:** Do not write a rulebook for English-to-Chinese dictionary mappings (violates "generic"). Do not use vision (Option C) — pure Luna can read structured markdown/text perfectly and much faster, keeping you under the 60-minute constraint.

### Wall 2: The Endgame Draw (1.0 vs 24.0 Residuals)
**The Diagnosis:** The L0 "Surgeon" is a generalist designed to hunt for broken data, misalignments, and missing evidence. When faced with a pure accounting residual at the very end of a run, its probabilistic nature means sometimes it confidently applies the "plug" method, and sometimes it gets spooked by the gap and conservatively flags it. 
**The Design:** **The "Closing Bell" Packet**
You do not change the Surgeon; you change the *State*. Introduce a final, distinct packet type that triggers only if: (1) The general Surgeon has finished its rounds, (2) Balance FAILs remain, and (3) The remaining gaps correspond to legally pluggable lines.
* **The Context Shift:** The "Closing Bell" packet strips away all the investigative noise. It receives only the remaining variance, the exact ending paragraph of the method (defining the plug), and the allowed plug lines.
* **The Prompt:** *"The general audit is complete. A systemic residual of [24.0] remains in [Line]. Review the method's closing rules. Does this residual meet the legal criteria to be plugged into [Allowed Line]? If yes, execute the write. If no, state the violation and flag."*
**What NOT to build:** Do not forbid L0 from picking "deliver" while a plug is open. That is a behavior cap/symptom patch. The general Surgeon must be allowed to give up.

### Response C — anthropic/claude-sonnet-5

# Three Walls — Design Answers

Before the picks: all three walls share a root cause. Something upstream lost structure (table headers, section membership, closing legality) and downstream the agent is being asked to recover structure it was never given. The fix in each case is: **restore the structure at the point it was lost, don't compensate for its absence with smarter reading or more rounds.** Keep that filter running through all three.

---

## Wall 1 — segment rows: choose (a) + (b) together, not (c)

**Design:** Port structured-table extraction (pdfplumber tables → `header: value | header: value` per-cell lines) into the ledger — this is the actual fix, because it's the thing that was lost. The implied-prior identity had 13/0 precision when tables were structured; it lost precision when tables became flat lines. That's not a reasoning failure, it's a data-loss failure. Fix the data.

But (a) alone doesn't solve the cross-language kinship death — English labels vs Chinese disclosure, current-year-only MD&A tables. So pair it with (b): for the *specific* rows that survive (a) still empty (kinship dead, no comparative column to imply a prior from), hand the compile packet raw text of those segment pages and let it read+cite directly. The 82.5 vs 73.3 result says raw reading beats pipeline-on-flat-lines on identical rows — but that was likely measuring pipeline-on-*flat*-lines, not pipeline-on-*structured*-lines. Use (b) as the fallback for the residual gap after (a), not as the primary strategy — because (b) has no cross-report memory and no auditable number-anchor; it's a citation-backed guess, (a) is a derivation.

**Why not (c) vision alone:** vision re-derives table structure from pixels every time, at cost, with no persistent artifact other people's packets can reuse. (a) produces a ledger asset that every other check (Driver rows, MD&A cross-refs) benefits from. Vision is the tool for pages where extraction genuinely fails (scanned images, rotated tables) — not the default for "tables that lost headers."

**Guard (not a rulebook):** the implied-prior identity only fires on ledger lines that carry a `header:` tag (i.e., number-anchored, per (a)). If a row has no header-tagged evidence and (b)'s raw-read is used instead, the write must carry a citation to source text, and the packet must record *which mode wrote this row* (derived-from-header vs read-from-raw) as a permanent provenance field — not a hidden implementation detail. That provenance field is itself an audit surface, not a policy toggle. No company-specific label maps, no hardcoded segment name translations — the header-tagging is generic (it works because pdfplumber emits headers, not because we taught it "Gas Turbine = 燃气轮机").

**What NOT to build:** a bilingual label-matching dictionary, a segment-name ontology, or any per-report translation table. That's the rulebook trap — it works for this filer and breaks for the next.

---

## Wall 2 — draw between 1.0 and 24.0: it's a method fact, not a behavior cap

The owner rejects behavior caps ("don't allow X"). But "L0 may not pick deliver while a legal plug line sits open on a residual" isn't a cap on behavior — it's a **completeness criterion for the close**, exactly analogous to "every packet ends in dispositions." It doesn't tell the surgeon what number to pick; it tells L0 what "done" means before it stops running rounds.

**Design — the closing bell packet:** add one deterministic final packet, after normal rounds end, that:
1. Enumerates every still-open FAIL that has a *legal plug line available* (a plug isn't invented here — it's a line that already exists as an option in that check's method).
2. Re-runs the surgeon exactly once per such check, handing it the method's own ending paragraph (the same text that already defines "how a close ends" from the Wall-0 edit) as the only new context — no new instructions, no new heuristics.
3. If the surgeon still declines to plug (chooses flag), that's now a *recorded, deliberate* choice with reasoning attached — not an accident of which round the harness stopped on. The draw disappears not because we force 1.0, but because we force the *decision* to happen once, deterministically, instead of being a coin-flip of "did the harness have one more round left."

This preserves "truth outranks balance" (flag-over-plug remains legal) while removing the arbitrary variance: quality floor = "every open residual got one forced, final, informed decision," not "every residual got plugged."

**What NOT to build:** a hard rule "residuals under $X must be plugged," a round-count increase (masks the problem, doesn't fix it — more rounds is just more chances to get lucky), or a cap that forbids "deliver" outright (that's the forbidden steer the owner is naming).

---

## Wall 3 — CFI/CFF twin: packet problem, not (yet) a capability referral

The evidence exists (vision-read component lists), the insight exists (repair context auto-states it), and the agent still flags both instead of moving one item. That's the signature of an **underspecified task shape**, not a missing capability: "flag any residual" is a different cognitive act than "find the specific line whose removal from A and insertion into B eliminates both residuals simultaneously." The model has never been asked the second question in a form that makes it answerable in one pass.

**Design — dedicated "misplaced item" packet type:** when the repair context detects the twin signature (two section residuals, equal magnitude, opposite sign — this is a generic numeric pattern, no company logic), route to a packet that:
- Presents both sections' component lists side by side, not as two separate checks.
- Asks one question: "which single component's value, moved from section X to section Y, closes both residuals?" — a search-and-verify task, not two independent flags.
- Requires the answer cite the specific line item and show both sections re-summed with the move applied, before disposition.

This is a packet problem because the *same* underlying model, given the *same* evidence, failed a task framed as "evaluate two sections" and would plausibly succeed at a task framed as "find the transposition." The fix is giving the shape of the question that matches the shape of the answer — that's packet design, not a model upgrade.

**Why not route to Police/analyst yet:** we haven't tried the right-shaped packet. Routing to a bigger model on a task the mid-tier model was never correctly asked is premature — it would hide a design gap behind a cost increase. If the misplaced-item packet is built with the side-by-side framing and *still* fails across runs, that's the honest trigger to route: "gpt-5.6-luna cannot resolve twin-residual transpositions even when explicitly framed" is then a measured capability fact, not a guess.

**Guard:** the packet only fires on the *generic* twin signature (equal magnitude, opposite sign, both in cash-flow sections) — not "CFI/CFF specifically." Works the same if the twin shows up between other statement sections next time.

**What NOT to build:** a CFI/CFF-specific rule, a hardcoded "check if item X belongs in section Y" heuristic, or an automatic silent move (the packet must produce a citation and disposition — an auditable claim — not a silent correction, per "guards silent" already meaning *the guard doesn't narrate*, not *the fix is unaudited*).

---

## Cross-cutting: what NOT to build, restated

- No bilingual dictionaries, no per-filer label maps, no company-specific section rules — all three fixes are shape-generic (header-tagged provenance, forced-decision closing packet, twin-signature detection).
- No behavior caps disguised as method facts, and no method facts disguised as behavior caps — Wall 2's fix is legitimate exactly because it changes what "done" means, not what answer is allowed.
- No silent capability-routing before the right-shaped packet has been tried once — Wall 3's escalation must be earned by evidence, not assumed from two failed runs of a mis-framed task.
- No vision-as-default — vision is for extraction failure, not for structure recovery that pdfplumber already does deterministically and cheaply.

### Response D — x-ai/grok-4.6

**The redesign is sound. All three walls are representation problems, not “try harder” problems.** Kinship, extra surgeon rounds, and residual-size vetoes are the symptom patches. Below is one design per wall, the guards that stay method-facts, and the things that must not be built.

---

## Wall 1 — segments: restore geometry, stop retrieving

**Choose (a)+(b), with (c) only as last-mile.** Not a menu pick. They fix different broken layers.

The empty slices are not a translation failure. A segment fact is a **grid fact**: row label × header-path × number. The ledger flattened that to `label + numbers`, so (i) column meaning died, (ii) English↔Chinese kinship had nothing left to bind, (iii) implied-prior was turned into a **global search key** and therefore harvested 2.41% / 5% prose. Porting structured tables into the *same* flat ledger, then searching it, will reproduce (iii).

**Design: table-islands, not a smarter slice.**

1. **Island extract (generic, few pages).** For MD&A/segment pages only, keep a first-class evidence type: a small matrix with header-path preserved (`pdfplumber` → `header/header: value` *inside the island*, never melted into the flat ledger). Attach the raw page text to the same island. If the matrix is ragged (merged cells, two-column Chinese layouts, scanned), keep the island and mark geometry `weak`; do not discard the page.

2. **Compile for segment rows receives islands, not kinship hits.** Packet payload: the model rows (English labels + the already-written “what this column IS”), plus the two or three segment islands (grid + raw text). The agent’s job is bind-then-write: read the grid, bind “Gas Turbine” to whatever the disclosure calls it, write **current** with a citation to `island / row-label-as-printed / header-path`. Brains read, hands verify. This is the 82.5-vs-73.3 result, made into the main path instead of a side test.

3. **Implied-prior is a write-time identity, never a retrieval query.** After a candidate `(current, yoy%)` is taken from the *same island row*, check `current/(1+yoy) ?≈ model prior`. Pass → write. Fail → do not write that pair; say so. This recovers the old 13/0 precision because the pair is co-located, not because a scanner hunted `≈ prior` across the book.

4. **Vision (c)** only when island geometry is `weak` *and* raw text does not show a usable grid. Same packet contract (cite row + header-path). Not a parallel pipeline.

**Guards (method facts, not a rulebook)**

- A segment write must cite an island header-path compatible with the column’s meaning (sales vs GP vs % vs yoy). No header-path → no write.
- Implied-prior runs only on a cited same-row pair. It is never executed against the flat ledger.
- Flag remains legal when bind or identity fails. What is illegal is the current path: empty slice → honest flag of a **key number**. Owner requirement is “update, not flag,” which this packet makes *possible*; it does not force a number.

**Do not build**

- Bilingual segment ontologies, issuer maps, or embedding kinship on flat lines.
- A global implied-prior scanner (measured coincidence magnet).
- Dumping `header: value` lines into the flat ledger and hoping compile stays the same.
- Vision-for-everything (cost + still needs the same write contract).
- “If flagged, force a write” — that is a behavior cap wearing a segment hat.

Cross-language is the normal case; binding belongs to a reader looking at a grid, not to retrieval.

---

## Wall 2 — close quality must not be a draw: one close object, one bell

**Choose a single deterministic closing-bell packet. Reject more surgeon rounds. Reframe the L0 idea so it is a completeness fact, not a steer.**

Runs 11 and 12 prove the harness already has a legal plug path; the last call sometimes dispositions the generator and sometimes flags the symptoms. Extra rounds amplify that draw and the bill. A floor that depends on “the surgeon felt like plugging” is not a method.

**Design**

Treat the residual **as one object**. Run 12’s “24.0 into five forecast years” is one unclosed generator, not six FAILs. Balance, forecast-balance, and cash-tie that share a residual are one close, one disposition.

**Closing bell** (different job from mid-run surgeon):

- **Trigger (deterministic):** any still-FAIL check after the normal packet sequence. Always fires at most once. Then deliver. (“Always deliver” stays.)
- **Input:** residual *vector* + which checks fail + every still-open plug line + the method’s ending paragraph (how a close ends, what a column is) + the already-booked honest flags. No new research corpus.
- **Job:** disposition the *generators*, not the symptom years. One coordinated write/plug/flag per generator. A plug is allowed only on a line the method already treats as a plug line; a flag is allowed only when no such line is open. That is the ending paragraph applied when all information is in, not a night-shift “make it zero.”

**L0 and “don’t deliver while a legal plug is open”**

- **Forbidden steer:** residual magnitude, “prefer plug,” “don’t deliver on FAIL,” retry-until-green. Those invert “truth outranks balance” and are behavior caps.
- **Method fact:** deliver means every close-*obligation* has a *terminal* disposition (write | plug | flag) issued **after** the residual vector is known. An open plug line is an undischarged close step, the same way an uncompiled segment row is unfinished work. L0 does not judge the number; it refuses to call an unfinished close a close.

That is why the bell is not “surgeon again.” Mid-run surgeon is local. The bell is the tie-out, once, with the vector in view.

**Do not build**

- More surgeon rounds or residual-size thresholds (`|r|<24` must plug).
- L0 veto on FAIL / on deliver.
- Per-year nagging of a single residual.
- Any loop that withholds deliver until balance PASSes.

---

## Wall 3 — CFI/CFF twin: paired reclass packet, not a smarter flag

**This is an information + packet problem. It is not yet a capability limit.** Do not route to Police/analyst until a paired packet has been shown both component lists and still cannot *name* the item.

Two independent section repairs make “flag both” the locally honest act. The insight “equal-and-opposite ~594” is already in prose; prose is not an action space. A move is an **atomic reclass** (drop from A, add to B), which no current packet treats as one write.

**Design: one `reclass` packet type**

Payload, side by side, one call:

- CFI booked total + component list  
- CFF booked total + component list  
- the residual pair (same magnitude, opposite sign) as a *single* claim: “one item may be in the wrong section”  
- the vision-read statement components (already extracted)

Required output shape: either

- **named move:** item label as printed, amount, from-section → to-section, citation on the statement; both legs written together or not at all, or  
- **honest flag:** “twin residual remains; no statement item identified.”

No third option of plugging both sides to zero.

**Guards**

- Magnitude rhyme is a *reason to look*, never a license to swap untitled 594s.
- Both legs or neither (a one-legged “fix” is a symptom patch).
- Truth still outranks balance: if the named item is not on the statement, do not invent it to cancel 594.

**When to call it a mid-tier limit.** Only if this packet, with both component lists visible, still cannot point at the printed line. Then escalate honestly: “suspected misclassification, item not identified.” Escalating *now* teaches the system that paired facts are un-actable, which is false.

**Do not build**

- `if CFI_err ≈ −CFF_err then shift amount` (untitled swap).
- Per-issuer “this group books X in CFI” rules.
- Two more single-section surgeon passes with the insight restated.
- Immediate model-tier change before the paired packet exists.

---

## What this is not

| Wall | Build | Do not build |
|---|---|---|
| 1 | Table-islands + compile-from-islands; implied-prior as write-time identity; vision only if geometry is weak | Kinship, flat-ledger header soup, global prior-scan, force-write |
| 2 | One closing-bell on residual *generators*; L0 vetoes unfinished close procedure only | More rounds, residual caps, deliver-blocked-on-FAIL |
| 3 | One atomic `reclass` packet with both section lists | Untitled 594 swap, per-company maps, escalate-first |

Nothing here is per-company. Grids, residual generators, and paired sections are the normal shape of the work. The packetized system already knows how to end a packet in a disposition; these three packets give it the objects those dispositions were missing.


## Stage 2 — peer reviews

### Review by openai/gpt-5.6-terra

### Response A

**What it does well**

Response A is highly complete and directly answers all three walls with concrete architecture, guards, and “what not to build” lists.

- **Wall 1:** Its strongest contribution is identifying the real failure as lost table semantics rather than merely failed label matching. The proposed **dual-representation evidence object**—structured cells plus rendered/raw source—is robust:
  - retains row labels, header paths, period, units, and bounding-box/page provenance;
  - makes current value and YoY change explicitly associated;
  - restores the conditions under which implied-prior arithmetic can be safely used;
  - gives the model a task-local raw-page window for cross-language semantic binding.
  
  The distinction between model work (“Is this Chinese segment equivalent to Gas Turbine?”) and deterministic work (geometry, arithmetic, provenance, citation checking) is excellent. This fits the stated principle: brains read, hands verify.

- **Wall 2:** The “Closing Bell” state machine is a strong answer to the stochastic endgame. It correctly distinguishes:
  - a prohibited policy such as “keep plugging until green,” from
  - a valid completion condition: execute a method-authorized, fully eligible repair action or explicitly establish why it is unavailable.
  
  The proposed repair-affordance registry is especially useful because it derives available actions from the method rather than embedding global policy. Requiring `EXECUTED` or `UNAVAILABLE`, rather than allowing an unexplained `FLAG`, creates a meaningful terminal protocol.

- **Wall 3:** The dedicated cash-flow reclassification packet is very well designed. It makes the twin residuals a candidate-generation signal, not proof. The side-by-side component lists, source classifications, citations, and explicit atomic move operation are exactly the missing action space. The response correctly says that deterministic logic should nominate candidates while semantic judgment determines classification.

- The response consistently avoids prohibited symptom patches: fixed residual caps, automatic plugs, company-specific dictionaries, keyword taxonomies, blind subset-sum searches, and escalation before trying a properly shaped packet.

**What it does poorly**

- It occasionally presents more machinery than may be needed initially. For example, the full “repair affordance registry” and state-machine formalization are sound, but could be implemented incrementally. The answer might have more clearly separated the minimum viable Closing Bell from the longer-term generalized framework.

- On **Wall 1**, it does not fully emphasize the danger of merely serializing structured tables into ordinary ledger text. If later retrieval treats the reconstructed records as independent flat lines, the architecture can still lose table-local binding. Response D improves on this by insisting that table structure remain a first-class “island” rather than merely better-formatted ledger text.

- The answer says a bare `FLAG` is invalid when a legal action remains available. That is generally right, but it needs a very careful definition of “available.” A line being nominally designated as a plug line is insufficient; all method, scope, accounting, and disclosure preconditions must be demonstrably satisfied. A largely says this, but the controller must not overrule a valid semantic objection merely because an affordance appears mechanically open.

- It could have more explicitly addressed the stated hard requirement that segment rows must be updated rather than flagged. The architecture clearly improves the odds of supported updates, but no truthful system can guarantee writing every row if disclosure is absent or genuinely non-comparable. The answer should distinguish “design to make key-number writing the default successful path” from “force a write despite unavailable evidence.”

---

### Response B

**What it does well**

- The diagnosis of **Wall 1** is directionally correct: flat text destroys the relationship between values and headers, while cross-language segment matching requires semantic reasoning rather than string similarity.

- It correctly recommends combining structured extraction with a dedicated raw-read segment packet. It also correctly rejects company-specific bilingual dictionaries.

- For **Wall 2**, the Closing Bell concept is a sensible improvement over simply running more surgeon rounds. Separating the final close from broad investigation is a good packet-design decision.

- It recognizes that a residual-cap policy would be a symptom patch and should not be used.

**What it does poorly**

- The largest flaw is that it does **not answer Wall 3 at all**. The question explicitly requires a design choice and concrete answer for the CFI/CFF twin residual. Omitting an entire wall is disqualifying relative to the other responses.

- Its Wall 1 guard is weak and contrary to the packetized design goals. It proposes requiring the model to perform matching and arithmetic “explicitly in its reasoning trace.” Internal reasoning traces are not a reliable, auditable control surface. The proper guard is structured provenance and independently verifiable outputs, not a mandated chain-of-thought-like format.

- It rejects vision too strongly: “Do not use vision.” That is not justified by the facts given. Vision should not be the default, but it is a legitimate targeted fallback when PDF extraction cannot preserve merged headers, Chinese text, or table geometry. The question specifically identifies statement pages that have already been vision-read, so a categorical dismissal is architecturally inflexible.

- Its proposed structured extraction is too shallow. Emitting `[Label] | [Header]: Value` lines is better than flat text, but it does not describe preservation of superheaders, row-column associations, units, cell-level citation, merged-cell handling, or table-local context. Without those, it risks reintroducing the same ambiguity in a cleaner-looking format.

- On Wall 2, it says the general surgeon “must be allowed to give up,” and rejects preventing delivery with an open legal plug as a behavior cap. This misses the distinction the prompt is testing: the controller need not force a plug, but it can require that every method-authorized, eligible closing action receive a terminal determination before the run is considered complete. The response’s Closing Bell is useful, but its conceptual framing is weaker than A and D.

- It does not sufficiently explain what makes a plug legally eligible or how the system verifies that the final action preserves truth and disclosure.

---

### Response C

**What it does well**

- Response C has a strong unifying diagnosis: structure was lost upstream and downstream agents are being asked to recover it. That is an effective design lens for all three walls.

- **Wall 1** is good:
  - correctly selects structured extraction plus raw reading;
  - correctly treats structured extraction as the primary repair and raw reading as fallback;
  - correctly limits vision to extraction-failure cases rather than using it by default;
  - proposes provenance showing whether a value was derived from header-preserved data or directly read from raw source;
  - rejects bilingual dictionaries and per-report mapping tables.

- **Wall 3** is also strong:
  - it recognizes the equal-and-opposite residual as a generic signature, not a CFI/CFF-specific company rule;
  - it proposes a dedicated misplaced-item packet with both sections visible;
  - it requires a cited item and post-move recalculation;
  - it defers escalation until the model has been tested with the correct packet shape.

- It is concise without being vague, and it avoids many obvious anti-patterns: automatic moves, hard-coded classifications, fixed retry counts, and escalation-first architecture.

**What it does poorly**

- Its **Wall 2** answer is the principal weakness. It argues that the final surgeon may still choose to flag a residual after the Closing Bell, and describes the desired quality floor as “every residual got one forced, final, informed decision.” That improves process consistency, but it does not fully solve the stated problem: the quality floor should not depend on a stochastic draw when a legal plug is genuinely available.

- The response calls “L0 may not deliver while a legal plug line sits open” a forbidden behavior cap. This is too categorical. If “open” is rigorously defined as method-authorized, all preconditions met, amount mechanically determined, transparent disclosure possible, and post-action verification available, then it is a method-completion condition rather than a behavior cap. Response A handles this distinction more accurately.

- The proposed final packet “re-runs the surgeon exactly once.” If the same stochastic model can still decline an eligible method action without proving that a precondition failed, the system can reproduce the 24.0 outcome. A final informed decision alone is not enough; the disposition protocol should require either:
  - execution of the eligible action, or
  - a cited, checkable explanation of why eligibility is false.
  
  This should be enforced by orchestration and verification, not merely requested in a prompt.

- The Wall 1 discussion slightly overstates the audit weakness of raw reading. Raw reading can be fully auditable when it produces page/cell/table citations and is independently verified. It is not merely a “citation-backed guess”; it is the semantic binding layer that structured extraction cannot replace in cross-language contexts.

---

### Response D

**What it does well**

Response D is the strongest overall because it gives the most precise representation-level designs while avoiding overgeneralized controls.

- **Wall 1:** The “table-islands” concept is particularly strong. It improves on simply restoring headers in ledger lines by insisting that the table remain a first-class structured evidence object:
  - row label × header path × number remains intact;
  - the raw page is attached to the same evidence object;
  - weak geometry is explicitly represented rather than silently discarded;
  - the segment compile packet receives a small number of relevant table islands rather than retrieval hits;
  - implied-prior arithmetic is a write-time validation against a same-row current/YoY pair, not a global retrieval mechanism.
  
  This directly addresses the measured 2.41% and 5% false-positive behavior from global numeric matching. It is also very clear that cross-language binding belongs in a semantic reader with table context, not in an English-Chinese dictionary or flat-line retrieval layer.

- **Wall 2:** The response’s “residual generator” framing is insightful. Treating a 24.0 residual propagated into five years as one underlying close object rather than six independent failures prevents repetitive, symptom-level repair behavior. The proposed Closing Bell is constrained, one-shot, and based on the residual vector and open method-authorized repair paths.
  
  Its distinction between:
  - a forbidden “retry until green” policy, and
  - a valid terminal-state requirement that every close obligation receive a final disposition,
  
  is well aligned with the owner’s “truth outranks balance” principle.

- **Wall 3:** The paired atomic reclassification packet is strong and concrete:
  - both CFI and CFF lists are shown together;
  - the equal-and-opposite residual is only a reason to investigate;
  - both legs of a move must occur together or not at all;
  - a cited source line and a recomputation are required;
  - escalation is delayed until the mid-tier model fails with the right-shaped evidence and task.
  
  This is a clean packet-design answer rather than a hidden accounting rule.

- The “what not to build” sections are excellent. They directly reject flat-ledger header soup, global implied-prior scanning, automatic untitled swaps, per-issuer mappings, residual thresholds, and more undirected surgeon rounds.

**What it does poorly**

- The Wall 2 wording has a potential tension: it says “a flag is allowed only when no such [legal plug] line is open.” This is defensible only if “open” means not merely present in the workbook or method, but fully eligible after all factual, accounting, scope, and disclosure preconditions are checked. Otherwise, it could turn into an implicit balance-forcing rule. The answer gestures toward this distinction but should define it as explicitly as Response A does.

- The claim that Wall 1’s hard requirement makes the current empty-slice-to-flag path “illegal” needs care. It is right that the architecture must be redesigned so key segment rows are not routinely abandoned due to evidence-pipeline failure. But the system must still retain an honest no-write disposition when the filing truly lacks support or comparability. The owner’s requirement should drive evidence acquisition and workflow priority, not authorize unsupported updates.

- The response is very assertive in declaring Wall 3 “not yet a capability limit.” That is likely correct, but it could specify clearer escalation criteria beyond “cannot name the item”: for example, multiple candidates fit the amount and signs, source classification is ambiguous, or the matter depends on accounting-policy interpretation not contained in the source evidence.

- The “always fires at most once, then deliver” design is cost- and time-disciplined, but it may need a provision for one deterministic verification/reconciliation pass after an executed move or plug. The response implies coordinated verification but does not spell out whether a changed state can create a new, distinct repair obligation. A carefully bounded one-pass post-action verification rule would make it more operationally complete.

FINAL RANKING:
1. Response D
2. Response A
3. Response C
4. Response B

### Review by google/gemini-3.1-pro-preview

An evaluation of the different responses based on your specific constraints and architectural philosophy:

### Response A
**What it does well:** 
This response provides very concrete, actionable data structures. The "Table Evidence Packet" in Wall 1 is a well-thought-out implementation that correctly blends structured extraction with raw semantic reading. For Wall 2, the "repair affordance registry" is a clever way to formalize the method rules into a state machine, making the closing bell truly deterministic. It also gives a great format for Wall 3's reconciliation packet.
**What it does poorly:** 
It misses a crucial clue in Wall 2: the prompt mentions *“ONE 24.0 residual propagating into five forecast years.”* Response A treats the endgame as a loop over failing checks, missing the opportunity to redesign the architecture to target the root *generator* rather than the symptoms. 

### Response B
**What it does well:** 
It provides punchy, direct answers for the first two walls and correctly identifies that Wall 1 requires combining structured extraction with raw semantic reading.
**What it does poorly:** 
It completely fails to answer Wall 3. It stops abruptly after Wall 2, ignoring a third of the prompt. Furthermore, its answer to Wall 2 ("Do not forbid L0 from picking 'deliver'... That is a behavior cap") misunderstands the owner's philosophy, as the other models correctly identify that forbidding delivery with an open method-authorized plug is a *completeness/method fact*, not a behavior cap.

### Response C
**What it does well:** 
This response perfectly captures the underlying architectural philosophy. The opening thesis ("restore the structure at the point it was lost, don't compensate for its absence") is a brilliant unifying framework. For Wall 2, its explanation of why the L0 rule is a "completeness criterion for the close" rather than a behavior cap is the most eloquent and philosophically aligned defense of the design choice. 
**What it does poorly:** 
Like Response A, it misses the specific insight regarding the 24.0 residual propagating into five forecast years, offering a fix that still runs "per check" rather than addressing the multi-year ripple as a single entity. It also relies slightly too much on fallback logic for Wall 1 rather than co-locating the data.

### Response D
**What it does well:** 
Response D is exceptional. It demonstrates the deepest reading comprehension by catching the "propagating into five forecast years" clue in Wall 2 and redesigning the process around "generators" vs "symptom years." This is a massive architectural insight. For Wall 1, it correctly identifies a flaw in the prompt's own option (a): dumping structured data into a flat ledger will still cause global search collisions. Its solution ("table-islands") fixes the root data-geometry issue flawlessly. For Wall 3, the "atomic reclass" concept perfectly matches the requirement for auditable, two-legged writes. It explicitly addresses all constraints, method facts, and what *not* to build.
**What it does poorly:** 
There are no significant flaws in this response. It is highly technical, deeply aligned with the prompt's unique jargon, and perfectly structured.

FINAL RANKING:
1. Response D
2. Response C
3. Response A
4. Response B

### Review by x-ai/grok-4.6

## Response A
**What it does well.** Comprehensive, implementable designs for all three walls. Wall 1 correctly pairs structured tables with task-local raw reading, keeps vision as recovery-only, and states strong “what not to build” (no bilingual dictionaries, no global implied-prior scan). Wall 2 turns closure into an orchestration invariant and distinguishes a method-authorized plug from “keep plugging until green.” Wall 3 frames the twin residual as a reclassification problem, with deterministic candidate generation and semantic classification, and defers Police escalation until the right packet has been tried.

**What it does poorly.** Slightly overbuilt: a full “Table Evidence Packet,” repair-affordance registry, and state machine add machinery the owner did not ask for. On Wall 2 it is more coercive than the owner’s laws allow—“FLAG is not valid if a legal affordance remains” can invert “truth outranks balance” if the surgeon has a real reason not to plug. It also never quite names the measured failure mode of implied-prior as a *global retrieval key*, so it is weaker than D on how structured cells must stay isolated from the flat ledger.

## Response B
**What it does well.** Wall 1 diagnosis is sound (flat text kills column meaning; cross-language needs a reader, not a dictionary). Combining (a)+(b) and rejecting a translation rulebook is correct. The Closing Bell idea—strip investigative noise, apply the method’s ending paragraph once—is directionally right.

**What it does poorly.** **Wall 3 is missing entirely**, so it fails the asked deliverable. Wall 1’s numbered “format requirement” is closer to a compliance script than “teach thinking.” Blanket rejection of vision is too absolute. Wall 2 explicitly *allows* L0 to deliver while a legal plug is open, which leaves the 1.0-vs-24.0 draw unfixed. Thin on guards and on residual-as-one-generator.

## Response C
**What it does well.** Sharp unifying thesis: restore structure where it was lost; do not compensate with more rounds or smarter reading. Wall 1 is well sequenced—(a) as the real fix, (b) as residual fallback, (c) not default—plus a provenance field for derived-vs-raw writes. Wall 2 is the best calibration of owner law: forcing a *decision* once is a completeness criterion, not a behavior cap; flag-over-plug stays legal. Wall 3 correctly treats the twin as a task-shape / packet problem and refuses premature model-tier escalation. Cross-cutting “what not to build” is disciplined and generic.

**What it does poorly.** Less original than D on two measured facts: it still talks about putting `header: value` *into the ledger* (risking the same global implied-prior coincidences), and it does not treat the 24.0-into-five-years pattern as one residual generator. Closing Bell as “re-run the surgeon once per check” is a bit more local and less vector-aware than D’s single close object.

## Response D
**What it does well.** Most precise architectural diagnosis. Wall 1: table-islands as a first-class type that must **not** be melted into the flat ledger; implied-prior only as a same-row write-time identity (directly explains the 2.41%/5% prose hits); compile receives islands, not kinship slices; vision only if geometry is weak. Wall 2: residual as one *generator* (the actual run-12 fact), one closing-bell on the residual vector, L0 as unfinished-procedure veto rather than a FAIL/size cap. Wall 3: atomic reclass (both legs or neither), magnitude rhyme as a reason to look not a license to swap, escalate only after the paired packet fails to *name* the line. Tight “do not build” table. Fully generic.

**What it does poorly.** Slightly less operational detail than A (no explicit affordance schema or verifier checklist). On Wall 2, “flag only when no plug line is open” still leans toward requiring the plug when a line exists—less explicit than C that a *reasoned* flag remains legal. A bit denser / more compressed, so some packet contracts are sketched rather than specified.

FINAL RANKING:
1. Response D
2. Response C
3. Response A
4. Response B


## Ranking tally (Borda)

- Response D (x-ai/grok-4.6): 12 pts
- Response C (anthropic/claude-sonnet-5): 8 pts
- Response A (openai/gpt-5.6-terra): 7 pts
- Response B (google/gemini-3.1-pro-preview): 3 pts

## Stage 3 — chairman synthesis (google/gemini-3.1-pro-preview)

The Council has convened, reviewed the models' responses, and reached a unanimous architectural consensus. The peer evaluations highlight a crucial unifying insight: **All three walls are representation and task-shape problems, not reasoning failures.** Upstream data pipelines lost structural context, and the downstream agent is being forced to compensate through global searches, stochastic guessing, or fragmented logic. 

The cure for all three walls is to restore structure exactly where it was lost. We do not compensate with extra rounds, smarter retrieval, or behavioral caps. 

Here are the design-level answers, guards, and prohibitions for each wall, adhering strictly to the owner’s laws.

---

### Wall 1: Segment Rows (The Cross-Language & Flat-Text Gap)

**The Root Cause:** Flat-text extraction destroys grid geometry (row × column). By dumping structured text into a flat ledger, cross-language label binding ("Gas Turbine" to "燃气轮机") lost its semantic context. Worse, the implied-prior math (`current / (1+pct) == prior`) was turned into a *global retrieval key*, which is exactly why it is harvesting prose coincidences (2.41% / 5%). 

**The Design: Table-Islands + Task-Local Reading (Combine A and B)**
Do not dump structured tables into the flat ledger. Instead, establish a first-class evidence object for MD&A and segment pages: the **Table Island**.
1. **Island Extraction:** Use `pdfplumber` to extract tables on these specific pages into an isolated grid (`row-label × header-path : value`), attaching the raw text of the page directly to this island.
2. **Compile Packet:** The compile packet receives these intact islands, not keyword-retrieved ledger slices. The agent acts as a reader: it reviews the English model requirements, reads the Chinese table in its native grid context, establishes the semantic kinship, and writes the current value with a hard citation to the `island / row-label / header-path`. *(Brains read, hands verify).*
3. **Implied-Prior as Write-Time Validation:** The implied prior is no longer a retrieval query. It is a write-time identity. Once the agent binds a current value and a YoY% from the *same island row*, it checks the math. If it matches the model prior, it writes.

**The Guards (Method Facts):** 
A segment write is only valid if it carries an island header-path citation. Vision (Option C) is reserved strictly as a last-mile fallback for pages where the PDF extraction yields mathematically weak or merged/broken geometry; it is never the default pipeline. 

**What NOT to build:** 
No bilingual dictionaries, no per-filer segment maps, and no global implied-prior scanners. Do not force the model to write if the disclosure is genuinely absent—an honest flag remains the correct action for missing data.

---

### Wall 2: The Endgame Draw (1.0 vs 24.0 Residuals)

**The Root Cause:** The current harness treats the endgame as just another round of localized, stochastic symptom patching. A 24.0 residual propagating into five forecast years is *one unclosed residual generator*, not six independent check failures. Furthermore, prohibiting the system from delivering while a legal plug remains open is **not** a forbidden behavior cap; it is a *completeness criterion for the close*.

**The Design: The Deterministic Closing Bell**
Treat the endgame as a distinct state machine.
1. **The Packet:** Introduce a single, deterministic "Closing Bell" packet that runs exactly once after the general surgeon has finished its normal rounds. 
2. **The Payload:** It receives the residual *vector* (treating propagated years as one generator object), every still-open method-authorized plug line, and the method's ending paragraph ("how a close ends"). It receives no new research corpus.
3. **The Disposition:** The packet must issue one terminal disposition per generator: either an executed plug (if all mechanical and accounting preconditions are met) or a reasoned, cited flag explaining exactly why the plug is unavailable or violates truth. 

**The Guards (Method Facts):**
Truth outranks balance. A flag remains a completely legal outcome of the Closing Bell, but the draw disappears because we force an informed, deterministic *decision* on the whole vector, rather than flipping a coin on whether the general surgeon had one more round left in its budget.

**What NOT to build:** 
Do not increase the number of general surgeon rounds. Do not implement residual-size thresholds (e.g., "always plug if under 25"). Do not create a retry-until-green loop that indefinitely blocks delivery. 

---

### Wall 3: The CFI/CFF Twin (~594 booked in the wrong section)

**The Root Cause:** This is a packet problem, not yet a capability limit. The evidence exists, but the task shape is underspecified. Asking a model to independently evaluate two separate sections and expecting it to spontaneously perform a coordinated swap is an architectural failure. The agent flags both because "flag" is the locally honest act when an action space for a two-legged move does not exist.

**The Design: The Atomic Reclassification Packet**
1. **The Trigger:** The generic twin-residual signature (equal magnitude, opposite sign) deterministically triggers this packet. It is a reason to look, not a license to swap.
2. **The Payload:** The packet presents both the CFI and CFF component lists, their booked totals, and the vision-read statement components side-by-side in a single prompt.
3. **The Task:** The agent is asked a single, bound question: *"Which specific source component's value, moved from section X to section Y, closes both residuals?"* 
4. **The Disposition:** The output must be an **atomic move**: drop from A and add to B executed simultaneously, backed by a citation to the printed line item. If the item cannot be explicitly named from the source, it must flag.

**The Guards (Method Facts):**
Both legs of the move must be written together, or not at all. You may only route this to the Police/analyst tier if this newly shaped packet runs and the mid-tier model *still* cannot confidently name the source item. Escalating before fixing the packet shape hides a design gap behind an LLM cost increase.

**What NOT to build:** 
No untitled, silent 594 swaps just to make the math work. No hardcoded, per-issuer "this group books X in CFI" keyword lists. 

---

### Summary of Chairman's Directives

| Wall | Architectural Fix | Prohibited Symptom Patches |
| :--- | :--- | :--- |
| **1 (Segments)** | **Table-Islands + Task-Local Read.** Extract grid geometry intact. Implied prior is write-time validation, not retrieval. | No bilingual dictionaries. No flat-ledger header soup. No vision-by-default. |
| **2 (Endgame)** | **Deterministic Closing Bell.** Target residual *generators* (vectors) in a single, final pass. Enforce completion criteria. | No extra surgeon rounds. No residual-size caps (e.g. plug if <25). |
| **3 (CFI/CFF)** | **Atomic Reclass Packet.** Present both sections side-by-side to allow a coordinated, two-legged move. | No silent/untitled swaps. No capability escalation until the packet is tested. |
