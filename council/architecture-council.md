# LLM Council transcript

## Question

# Council question: the harness has hit its architectural ceiling — design the rebuild

## The uncomfortable evidence (measured, today)
- Five cold runs today: 72.9 -> 75.5 -> 76.9 -> regression (serve collapse +
  a scale-poisoned write). Weeks of runs oscillate 73-84. Every individual
  fix validated and worked; the score barely moves.
- Run 116's failure was CAUSED by run 115's fix (complete-coverage expansion
  + no-prior reads): the checksum was secretly the scale anchor; removing it
  for no-prior rows let a raw-scale number through; bigger chunks degraded
  the reader's serving 104 -> 67. The marginal mechanism now has NEGATIVE
  expected value.
- Where errors come from, all week: NEVER from a checksummed LLM read
  (104/104, 103/103, 0 wrong across runs). ALWAYS from the machinery between
  reads and cells: closing-loop swap (112), allocation scaling over printed
  values (114), mapper writing a MEGAWATT figure into a P&L row (115), my
  own coverage expansion (116). ~20 cooperating mechanisms; each fix adds one.
- Clean-room proof: a strong model, free-form, single coherent context, NO
  harness: 96.0%, Model tab 100%. Historic: plain ChatGPT chat beat the
  then-pipeline. The harness subtracts value from the reading.
- What DOES work, proven: (a) whole-page reads with per-row prior checksum
  (zero wrong ever); (b) the multi-pass consensus EXTRACTION (staging: ~2,300
  items with {value, prior, page, stmt-tag}, column-bound by the extractor);
  (c) the deterministic TRIPLE-LOCK join (prior ties + stmt-face + label
  kinship) — surgical in replay: exactly the true repairs, zero false
  positives; (d) balance/cash/keys deterministic verification; (e) the
  post-eval residual chase (playbooks) — by hand it takes 76.9 raw to 83.9
  with Model tab 99.1 in ~40 min.
- Owner's mandate: the AGENT must complete the whole thing itself — no
  hand-finishing. Model tab 2025 = 100%-or-flagged is the bar. Pure
  gpt-5.6-luna. Generic across companies. Broadly-available Python only.

## The proposed rebuild (invert the architecture)
Today the model rows drive: ~20 mechanisms each try to fill rows (mapper
blocks, rescues, bridges, allocation, closing, coverage passes...). The
inversion — closer to how the clean-room run and a human analyst work:

STAGE 1 — READ the documents, once, completely: the existing multi-pass
  consensus extraction (plus vision for scans) produces the item table.
  The LLM's only job here is transcription with both years per line.
STAGE 2 — JOIN deterministically: fill model rows FROM the item table via
  the proven triple-lock join (prior identity + face authority + label
  kinship + page-scale). Code, not LLM. Complete coverage falls out of the
  extraction being complete, not from per-row quizzes. No-prior rows join
  by label+position within their block WITH the block's page scale.
STAGE 3 — READ AGAIN, narrowly: rows the join cannot serve uniquely become
  ONE fable-mode-style call per statement region (whole page + priors +
  checksum contract) — the proven zero-wrong reader as the gap-filler, not
  the primary.
STAGE 4 — VERIFY & REPAIR: the deterministic web (balance, cash tie, EPS x
  shares, segment sums, statement line-for-line identity) + the orchestrator
  with the taught playbooks for residual chase. Flags for what cannot be
  proven. NOTHING else writes: delete/disarm allocation scaling, closing
  swaps, breadth auto-applies, mechanical rescues.

## Questions
Q1: Is the inversion the right call, or is there a smaller change with the
    same effect? Judge against: every failure this week was machinery; every
    success was the reader or a deterministic join/check.
Q2: Specify Stage 2 precisely enough to build: join keys, ambiguity rules,
    no-prior handling WITH scale anchoring (the run-116 lesson), what the
    extraction must add (block/section ids? row order?) so the join can bind
    non-statement Driver/MD&A tables safely (the left-neighbour and
    five-year-table traps are documented).
Q3: The validation protocol that would have caught runs 112-116 BEFORE
    dispatch, given the local environment cannot reproduce the run's vision
    cache. What is the minimum honest pre-flight (golden fixtures? a pinned
    transcription snapshot? a staged canary run?) — design it so "validated
    locally" can never again mean "blind on the main region".
Q4: Sequencing and risk: owner presents Monday (hours away; the presentation
    will use existing results and the honest architecture story). The rebuild
    lands next week. What is the order of work that gets Model-tab
    100%-or-flagged on a cold run FASTEST, and what do we explicitly NOT do?
Be concrete. Flag what other members will get wrong.


## Stage 1 — answers

### Response A — openai/gpt-5.6-terra

## Recommendation

### Q1 — Invert it. The smaller safe change is only a bridge to the rebuild.

The evidence is unusually clear:

- The reader is not the dominant error source.
- The deterministic join/checks are not the dominant error source.
- The write-side “helpful” machinery is the error source.
- Adding another row-driven mechanism has negative expected value because it creates another writer with incomplete context.

So the architectural decision should be:

> **Documents produce a normalized evidence ledger; deterministic code binds evidence to model cells; narrow reading resolves only explicitly unbound evidence; validators decide acceptance.**

That is the right rebuild.

A smaller change can reduce immediate risk, but it does not achieve the same effect. The emergency containment change is:

1. Disable all autonomous writers except:
   - existing checksum-protected page reader;
   - triple-lock join;
   - deterministic formula/identity-derived values where the formula is explicit and verified.
2. Make every other mechanism advisory-only: it may create a candidate or a flag, but cannot write.
3. Require provenance for every write.

That would likely stop repeats of 112–116. But it leaves the old architecture alive: rows still solicit many mechanisms, and future “small fixes” will reintroduce unsafe writers. It is not the final design.

The proposed four-stage inversion is the final design.

The principle to adopt is:

> **No model row may be written because a mechanism thinks it is plausible. It may be written only because a specific document item, in a known table/block, was uniquely bound to that row under explicit scale and column rules.**

---

# Q2 — Stage 2 specification

## 1. Make the extraction output an evidence ledger, not loose `{value, prior, page, stmt-tag}` items

The current extraction is close, but Stage 2 needs enough structural metadata to bind items without inventing table geometry.

Each extracted item should retain immutable source evidence and normalized fields.

```python
ExtractedItem = {
    # Identity / provenance
    "document_id": ...,
    "page_number": ...,
    "image_or_text_hash": ...,
    "extraction_run_id": ...,
    "source_span": ...,              # text offsets or bounding box
    "crop_id": ...,                  # optional, for vision-derived evidence

    # Table and block structure
    "section_id": ...,               # e.g. Consolidated Income Statement
    "block_id": ...,                 # one contiguous table / statement block
    "table_id": ...,                 # stable table identifier within page/section
    "row_id": ...,                   # stable extracted row identity
    "row_order": ...,                # visual/top-to-bottom order within table
    "column_id": ...,
    "column_order": ...,             # left-to-right physical order
    "header_path": [...],            # all applicable headers, not just nearest header
    "year_or_period": ...,           # FY2025, FY2024, Q4, LTM, etc.
    "unit_header": ...,              # "$ in millions", "$ in thousands", MW, %, etc.
    "scale": ...,                    # numeric multiplier only if evidenced
    "currency": ...,
    "sign_convention": ...,          # reported, parentheses-negative, percent, basis points
    "table_kind": ...,               # statement, note, driver, MD&A, KPI, five_year_summary
    "statement_tag": ...,            # income_statement, balance_sheet, cash_flow, etc.

    # Row semantics
    "raw_label": ...,
    "normalized_label": ...,
    "label_tokens": [...],
    "indent_level": ...,
    "row_role": ...,                 # line_item, subtotal, total, header, footnote, ratio
    "parent_label_path": [...],      # hierarchy: Revenue > Generation > MW
    "column_measure": ...,           # dollars, units, MW, %, shares, per-share, etc.

    # Values
    "raw_display_value": ...,
    "parsed_value": ...,
    "normalized_value": ...,         # only populated if scale is evidenced
    "prior_value": ...,              # if the source line contains it
    "prior_normalized_value": ...,
    "current_value": ...,
    "confidence": ...,

    # Extraction consensus
    "consensus_count": ...,
    "candidate_values": [...],
    "is_consensus_stable": ...,
    "reader_checksum": ...,          # checksum / line identity evidence
}
```

Important distinction:

- `parsed_value` is what the document printed.
- `normalized_value` is what it means after applying a **proven page/block/table scale**.
- A row without a prior value must never be allowed to establish its own scale from a naked printed number.

That directly prevents run 116.

## 2. The model row needs a similarly explicit target schema

Do not join to vague labels alone. Each target row needs a canonical target specification.

```python
TargetRow = {
    "workbook_id": ...,
    "sheet": ...,
    "cell_current": ...,
    "cell_prior": ...,

    "model_section": ...,
    "model_block": ...,
    "statement_tag_expected": ...,
    "table_kind_expected": ...,      # statement / note / driver / KPI
    "expected_measure": ...,         # dollars, MW, %, shares, etc.
    "expected_currency": ...,
    "expected_unit_family": ...,     # monetary, physical, ratio, per_share
    "expected_period": ...,

    "canonical_label": ...,
    "acceptable_label_aliases": [...],
    "label_hierarchy": [...],
    "row_order_hint": ...,           # only within an identified model block
    "prior_model_value": ...,
    "current_model_value": ...,

    "is_formula_row": ...,
    "is_input_row": ...,
    "is_no_prior_row": ...,
    "required_or_optional": ...,
}
```

The model should have an explicit row dictionary/configuration, not scattered mapper assumptions. This is where company-specific aliases can live without creating company-specific write logic.

## 3. Stage 2 is a gated deterministic join, not a scoring contest

The triple lock should be implemented as a sequence of hard eligibility gates, followed by uniqueness resolution.

### Gate A: structural domain

An item is eligible only if all are compatible:

- expected statement tag / table kind;
- expected measure family;
- expected currency where applicable;
- expected period/year;
- expected row role is `line_item`, `subtotal`, or explicitly permitted `total`;
- item belongs to a table/block with an evidenced scale;
- item has stable extraction consensus.

A megawatt item is therefore ineligible for a P&L dollar row before label similarity is even considered. This would have prevented run 115.

### Gate B: face authority

“Face authority” should be explicit and ranked:

1. Primary face of the relevant financial statement.
2. Relevant note table explicitly tied to the model row.
3. Management table / MD&A table only when the target row is designated as a driver/KPI row.
4. Never cross this hierarchy merely because a label matches.

For example, a Revenue row should not be sourced from an MD&A chart, and a Capacity MW driver should not be sourced from a financial-statement dollar line.

### Gate C: prior identity, where prior exists

For rows with a model prior:

- Compare the target prior against the item’s source prior after applying the **item’s evidenced block scale**.
- Require exact equality after appropriate display rounding, or a narrowly specified tolerance for known rounding cases.
- Match sign and unit family.
- Require compatible period/column identity.

The prior is an identity key, not merely a similarity feature.

If several source items share the same prior, do not choose based on nearest label alone. Continue to the remaining locks and demand uniqueness.

### Gate D: label kinship

Use deterministic normalized label matching:

- canonicalized labels;
- approved aliases;
- token overlap;
- hierarchy/path compatibility;
- segment/geography qualifiers;
- exclusion tokens;
- subtotal/total distinction;
- measure/unit tokens.

“Net income” must not casually match “net income attributable to noncontrolling interests.” “Capacity” must not casually match “generation.” The label matcher should return an explanation, not just a score.

Label kinship may rank eligible candidates. It must not override a failed structural, face-authority, or prior-identity gate.

### Gate E: unique binding

Write only if exactly one candidate survives the gates.

If zero candidates survive: send to Stage 3.

If multiple candidates survive: send to Stage 3. Do not choose the top score unless the separation is encoded as a deterministic rule and has regression evidence.

The resulting join record should look like:

```python
JoinDecision = {
    "target_cell": "Model!F42",
    "status": "accepted" | "ambiguous" | "unbound" | "rejected",
    "source_item_ids": [...],
    "source_value_raw": ...,
    "source_value_normalized": ...,
    "scale_source": ...,
    "accepted_by": [
        "structural_domain",
        "face_authority",
        "prior_identity",
        "label_kinship",
        "unique_candidate"
    ],
    "rejection_reasons": [...],
}
```

Every cell must be auditable from workbook cell back to page, source span, row label, header path, raw printed value, and scale source.

---

## 4. No-prior handling: more restrictive, never less restrictive

No-prior rows are exactly where the old harness became unsafe. The rule should be:

> **A no-prior row may borrow identity from a bound block; it may not invent its own block, scale, or column semantics.**

A no-prior item is joinable only if all of the following hold:

1. **The table/block is already identified.**  
   At least two neighboring or sibling rows in the same source block have been independently triple-lock bound to the corresponding model block, preferably with prior-based matches.

2. **The scale is evidenced at table/block level.**  
   The scale must come from:
   - the table header (“$ in millions”);
   - statement caption;
   - an inherited page/block scale explicitly attached to the table;
   - or a verified statement-wide scale rule.

   It may not come from the no-prior cell’s magnitude.

3. **Column identity is explicit.**  
   The target period must map to a source column through headers, not “the value to the left/right.” This is essential for five-year tables and comparative tables.

4. **Label and hierarchy match uniquely.**  
   The target’s canonical label and parent path must identify one line item in that already-bound source block.

5. **Measure family matches.**  
   MW, MWh, dollars, shares, percentages, and per-share values are distinct types, even if labels overlap.

6. **Position is a tie-breaker only within the same proven block.**  
   Row order may disambiguate two otherwise compatible labels inside an identified table. It must never be used as a cross-table locator.

7. **No cross-section borrowing.**  
   A no-prior Driver/MD&A item cannot be joined because a similarly named statement item exists elsewhere.

If any condition fails, Stage 3 reads the entire relevant statement/table region with the checksum contract.

### Scale anchoring rule

Make this an invariant:

```text
No normalized numeric write without a source scale provenance record.
```

A source scale provenance record must identify:

- the table/block;
- the source header/caption span;
- the scale multiplier;
- the measure/currency context;
- whether the scale is inherited and from where.

If the source says `1,250` and the scale cannot be proven, Stage 2 must produce `UNBOUND_SCALE`, not `$1,250`, `$1.25bn`, or any other guess.

---

## 5. Non-statement Driver and MD&A tables: bind tables before rows

This is where teams will be tempted to reintroduce dangerous “left-neighbor” logic. Do not do that.

For non-statement tables, use a two-level join:

### First join: model block to source table/block

A model Driver/MD&A block may bind to a source table only using:

- section/table title similarity;
- table kind;
- measure family;
- header schema;
- period-column schema;
- known block-specific row labels;
- optional anchored rows with prior values.

For example, a five-year operating-statistics table should be recognized as a five-year table before any cell is joined.

### Then join: row and column within that bound table

Only after table binding:

- identify the source row by label hierarchy and row role;
- identify the source column from the full header path and period;
- apply the table’s evidenced unit and scale;
- require a unique cell.

Never use “the left neighbor,” “the next numeric value,” or “same x-position” as a global rule. Those fail on:

- five-year summaries;
- multi-level headers;
- columns for percentage change;
- trailing CAGR columns;
- actual vs adjusted columns;
- repeated year labels;
- side-by-side tables;
- footnote columns.

The extraction must preserve complete header paths and physical column order precisely so this can be deterministic.

---

# Q3 — Honest validation protocol

The important conclusion is:

> A local validation that does not exercise the same document-transcription artifact is not validation of the production path.

If the local environment cannot reproduce the vision cache, “validated locally” must mean only “unit-tested against fixtures,” not “validated end-to-end.”

Use three layers.

## A. Immutable golden fixtures: required for merge

Create a small but adversarial corpus from real, permissioned filings and model tabs. It must include the exact classes of failure seen this week:

| Regression | Fixture requirement |
|---|---|
| Run 112 closing-loop swap | Similar adjacent closing/ending balance rows; verify no cross-row swap |
| Run 114 allocation scaling | Monetary values with different scales and allocation-like labels; verify units cannot cross |
| Run 115 MW into P&L | Same/similar label appearing as MW driver and dollar financial line |
| Run 116 no-prior raw scale | No-prior row in a scaled table; assert no write without inherited scale provenance |
| Five-year trap | Multi-year table with CAGR / percentages / multiple period columns |
| Left-neighbor trap | Adjacent numbers with different semantic columns |
| Duplicate prior values | Multiple statement lines with equal priors |
| Negative / parentheses | Sign parsing and normalized value tests |
| Statement vs MD&A duplicate labels | Face authority test |

A golden fixture should include:

1. source pages or legal redacted equivalents;
2. a pinned extraction ledger snapshot;
3. expected joins;
4. expected non-joins/flags;
5. expected scale provenance;
6. expected final model-cell results;
7. expected validation outcomes.

The fixtures must assert **negative behavior**, not just successful fills:

- “This MW item must never be eligible for this P&L row.”
- “This no-prior row must remain flagged if the scale header is removed.”
- “This ambiguous duplicate must not write.”

## B. Pinned transcription snapshots: required for deterministic Stage 2–4 testing

Store the exact extraction ledger generated in a known-good run as an immutable artifact. Stage 2–4 must be runnable entirely from that snapshot.

This isolates join and write logic from LLM/vision variability and lets the team prove that a code change cannot alter:

- accepted cell set;
- source-to-cell mapping;
- scale multipliers;
- ambiguity decisions;
- validation outcomes.

Every PR that changes join/write/validation code should produce a differential report:

```text
accepted writes: old 842, new 842
changed source bindings: 0
new flags: 0
removed flags: 0
scale provenance changes: 0
```

Any unexpected binding difference is a release blocker, not a “looks reasonable” review item.

## C. Production-like staged canary: required before dispatch

Because vision/cache behavior is part of reality, there must be a canary in the actual execution environment.

The canary should:

1. Run on one representative company/document set using the same production vision/transcription path.
2. Produce a full evidence ledger.
3. Run Stage 2–4.
4. Compare against a pinned baseline or known reviewed output.
5. Stop before final dispatch/write promotion unless all gates pass.

The canary report must include:

- extraction coverage by page/table;
- consensus disagreement count;
- accepted writes, flags, and ambiguity count;
- changed source bindings vs baseline;
- scale provenance coverage;
- statement balance/cash/EPS/key checks;
- Model-tab score if an evaluator is available;
- list of all values written without a prior, with their block-scale anchors.

A release should require:

- no forbidden writer invoked;
- no unexplained binding drift;
- no unproven scale write;
- no new validation failure;
- no degradation in golden fixtures;
- canary passes on the actual transcription stack.

## Release terminology should be corrected

Use these terms precisely:

- **Unit-tested:** code passed synthetic and golden fixture tests.
- **Snapshot-tested:** code passed against pinned real extraction artifacts.
- **Canary-validated:** code passed production-like transcription and join path.
- **Dispatch-approved:**

### Response B — google/gemini-3.1-pro-preview

This is a classic "local maxima" trap. You have climbed as high as the current architecture allows. The ~20 cooperating mechanisms are a symptom of a system fighting its own fundamental design. The harness is no longer facilitating the LLM; it is actively sabotaging it. 

Here is the blueprint for the rebuild.

### Q1: Is the inversion the right call?
**Yes. Emphatically.** There is no smaller change. 

You have proven that the LLM is flawless at reading and extracting (0 errors) and that deterministic Python is flawless at matching known quantities. You have also proven that bridging the two with heuristic Python "machinery" (scaling over printed values, closing-loop swaps, rescues) produces a negative expected value. 

The current architecture is a **pull** system: *Model rows ask the documents for data.* This forces the machinery to guess *where* and *how* to look, creating infinite edge cases. 
The inverted architecture is a **push** (ETL) system: *Extract all facts from the documents, then map them to the model.* This restricts the LLM to its core competency (transcription/extraction) and Python to its core competency (relational joins/math). 

**Burn the ~20 mechanisms.** Delete allocation scaling, closing swaps, breadth auto-applies, and mechanical rescues. They are dead code.

---

### Q2: Specification for Stage 2 (Deterministic Join)
To build this, Stage 1 (Extraction) must be enriched, and Stage 2 must be radically strict.

**1. Required Enhancements to Stage 1 (The Staging Table):**
To prevent the Left-Neighbor and 5-Year-Table traps, the extractor must append structural metadata to every extracted row:
*   `page_num`: For scoping Stage 3.
*   `section_type`: [Face_Income, Face_Balance, Face_Cash, MDA, Footnote].
*   `table_id`: A UUID or index for the contiguous block the row came from.
*   `row_index`: The integer order of the row within the `table_id`.
*   `stated_scale`: The scale explicitly printed at the top of the `table_id` (e.g., 1_000_000 for "in millions"). **This is the Run 116 fix.** Scale belongs to the *table*, never the row.

**2. The Join Logic (Strict Python, No LLM):**
*   **Pass A (The Golden Join - Prior + Face + Label):** 
    For a target model row, search Stage 1 items where:
    `item.value_prior == model.prior` AND 
    `item.section_type == target_section` AND 
    `fuzzy_match(item.label, model.label) > 0.85`.
    *Action:* Bind current year value. Multiply by `item.stated_scale`.
*   **Pass B (No-Prior / Gap Join):** 
    If a model row lacks a prior (causing the Run 116 failure), we cannot anchor by value. We anchor by *structure*.
    Find the `table_id` where the *rest* of this section's rows successfully bound in Pass A. Search *only* within that `table_id` for a `fuzzy_match` on the label. 
    *Action:* Bind current year value. Multiply by that table's `stated_scale`. (This prevents a raw mega-watt figure from a random page sneaking into a financial column).
*   **Pass C (Driver / MD&A Safe Binding):**
    Only permit joins where `item.table_id` has exactly the expected column structure (e.g., reject tables with 5 columns of years if looking for standard 2-year comparables).

**3. Ambiguity Rules (The Golden Rule of Stage 2):**
If a join rule yields 0 matches, or >1 match, **DO NOTHING**. Leave the row blank. Do not write heuristic tie-breakers. A blank row safely falls through to Stage 3.

---

### Q3: The Validation Protocol (No More Blind Dispatches)
You cannot ship code to production without local CI, and you cannot run local CI if it requires 500 vision-cache hits per run. 

**The Minimum Honest Pre-flight:**
1.  **The Staging Snapshot (Golden Fixtures):** In production, run Stage 1 on three highly volatile companies (e.g., a bank, a conglomerate, a weird software company). Save the output—the ~2,300 rows of JSON with metadata—as static files in your repo.
2.  **The Local Replay Harness:** Stages 2, 3, and 4 must be executable locally, taking the static Stage 1 JSON files as their input. **No vision API required.** 
3.  **The CI Contract:** Before pushing *any* fix to the python join logic or the verification math, you run the replay harness. The rule is: *Score must go up, and zero previously bound rows are allowed to change state.* 
4.  **The Canary Dispatch:** The orchestrator must support running a single, complex ticker in the cloud environment before doing a 100-run batch. If the canary's math verification fails catastrophically, the batch auto-aborts.

Never again will "validated locally" mean "we didn't test the actual data payload."

---

### Q4: Sequencing and Risk (The Next 7 Days)
*The Monday Narrative for the Owner:* "We proved the AI can read perfectly (0 errors). We proved our math checks work. We identified that the middle-layer software is causing 100% of the volatility. Next week, we are deleting that software and wiring the perfect reader directly to the math checks. We expect a permanent stabilization of the score, culminating in 100% or flagged."

**The Sequence (Fastest path to 100%-or-flagged):**

*   **Day 1: Demolition & Stage 1 Staging.** Delete all ~20 legacy mechanisms. Update the existing multi-pass extractor prompt to enforce the `table_id`, `row_index`, and `stated_scale` metadata schema. Generate and download the Golden Fixtures.
*   **Day 2: The Stage 2 Joiner.** Build Pass A, B, and C (from Q2) in pure Python. Test against the fixtures. Accept that many rows will be blank. 
*   **Day 3: Verification (Stage 4) & Stage 3 Gap Filler.** Hook up the existing deterministic math verification. For anything blank or failing math, wire up the existing, proven 0-error whole-page reader (Stage 3).
*   **Day 4: The Residual Chase & Flagging.** Wire up the playbook orchestrator for anything still failing math. **Crucial:** Implement the final abort. If a row is still broken after the playbooks, the Agent writes a standard `FLAGGED: [Reason]` to the cell.
*   **Day 5: Cold Run.**

**What we explicitly DO NOT do:**
*   Do not write "smart" Python heuristics to guess missing data in Stage 2. (If others on the team try to add a "quick regex fallback" to the join, reject the PR immediately. Let Stage 3 handle it).
*   Do not touch the prompt of the Stage 3 reader. It works perfectly.
*   Do not attempt to optimize for LLM cost or speed right now. Optimize entirely for structural stability. 

**Watch out for your team:** Engineers hate leaving things blank. They will be tempted to make Stage 2 "smarter" to save LLM calls in Stage 3. Remind them that every time they tried to make the machinery "smart" this week, they caused a regression. Stage 2 is dumb, rigid, and safe. Stage 3 is smart.

### Response C — x-ai/grok-4.6

**Inversion is the right call. The smaller change with the same effect is not a new idea — it is the inversion done as a write-path amputation, not a greenfield rewrite.**

Every failure this week was a writer. Every success was a checksummed read, a deterministic join, or a deterministic check. That is not a streak; it is a type error. The harness treats “fill the grid” as the objective. The bar is “Model tab 2025 = 100% or flagged.” Those two objectives produce opposite systems.

---

## Q1 — Inversion vs smaller change

**Call: invert write authority. Do not invert the codebase.**

Keep Stage 1 (consensus extraction) and the triple-lock and the checksummed reader and the verify web. Delete the right to invent numbers.

A “smaller change” that people will propose — one more mapper guard, a scale heuristic, freeze coverage expansion, add a checksum to no-prior reads — is how you got run 116. Run 115’s complete-coverage expansion *was* a locally validated fix. It removed the secret scale anchor. The marginal mechanism has negative EV because the system is past the point where local correctness implies global correctness. ~20 cooperating writers means every fix is a new coupling.

The clean-room proof is the control: same model, no harness, 96% / Model 100%. The harness is not failing to extract. It is overwriting good reads.

**What other members will get wrong:** treating inversion as “rebuild the extractor.” The extractor is the part that works. Treating inversion as “add a Stage 3 router and keep allocation as fallback.” Fallback is how scale-poisoned writes land. The inversion is a *monopoly on writes*:

| May write a cell | May not write a cell |
|---|---|
| Triple-lock join (code) | Allocation / scaling |
| Stage-3 checksummed region read | Closing-loop swap |
| Stage-4 repair that cites a check + a source item | Breadth auto-apply, mechanical rescues, mapper blocks, bridges |

If a cell cannot be produced by those three, it stays empty and flagged. Empty is a legal state. A plausible number is not.

---

## Q2 — Stage 2 specified to build

### Item table (Stage 1 must emit; join must refuse items that lack these)

Already proven: `{value, prior, page, stmt_tag}` plus column binding.

**Add, or the join cannot be safe:**

```
item:
  item_id
  value_raw          # as printed, unscaled
  prior_raw          # as printed on the same line, or null
  years              # explicit column→year map, e.g. {2025: v, 2024: p}
  page
  table_id           # REQUIRED. Adjacent tables are different tables.
  block_id           # section within table (current assets, operating CF, …)
  row_ord            # stable order in table_id (PDF y-rank, not array index)
  label_raw
  label_norm         # after the existing kinship normalizer
  stmt_face          # {IS, BS, CF, EQUITY, SEGMENT, MDA, DRIVER, OTHER}
  col_bind           # which printed column supplied value_raw
  scale_hint         # token on this row if any (“000s”, “MW”, “%”) — hint only
  block_scale        # see scale rules; may be null at extract time
  unit_dim           # {currency, shares, ratio, energy, count, unknown}
  neighbors          # {left_label, right_label, above_label} for MD&A traps
```

If `table_id` or `row_ord` is missing, the item is non-joinable except via Stage 3. Do not infer table boundaries at join time.

### Scale is a block property, never a number property (run 116)

Compute `block_scale` *before* any write.

1. Explicit header on the table/block (“$ in millions”, “thousands”, “except per share”).
2. Else **ratio lock**: for every item in the block that has `prior_raw` and a model prior on a uniquely triple-locked sibling, `model_prior / prior_raw`. Require ≥2 siblings agreeing within a tight tolerance (e.g. all in {1, 1e3, 1e6, 1e9} and identical). That consensus *is* the block scale.
3. Else `block_scale = unknown`. The entire block is ineligible for Stage 2 writes, including rows that look obvious.

**Invariant:** a write is `value_raw * block_scale`, never `value_raw * guess(value_raw, model_magnitude)`. Checksums were secretly doing (2). Removing checksums for no-prior rows removed the anchor. That is the whole bug.

`unit_dim` is a hard gate: an item with `unit_dim=energy` cannot join a P&L currency row even if the label is “Power” and the number is the right magnitude. Run 115 is this gate’s absence.

### Join keys, in order

Work **per model row**, but the candidate set is first partitioned by `stmt_face` × `table_id`. Cross-table candidates do not exist.

**Lock A — prior identity (statement rows with a model prior)**  
Candidate if `item.prior_raw * block_scale == model.prior` (exact after scale; allow a one-cent / rounding envelope only for per-share).  
This is the strongest key. It is why checksummed reads never fail: the prior is a content-addressable pointer.

**Lock B — face authority**  
`item.stmt_face` must equal the model row’s statement. Segment/MD&A/Driver faces cannot satisfy an IS/BS/CF row. Printed face wins over filename or page heuristics.

**Lock C — label kinship**  
Existing kinship function. Use it to *rank*, not to *create* a match when A failed. Kinship-only matches are Stage 3, not Stage 2.

**Lock D — page/block scale**  
Already applied in A. Re-check: written value must be dimensionally consistent with the row’s unit (currency vs shares vs EPS vs %).

A Stage 2 write requires **A ∧ B ∧ D**, with C used only to break a remaining tie when two items share the same prior (rare; usually two printings of the same line). If C cannot break the tie **and the values differ**, write nothing.

### Ambiguity rules (surgical, like the replay you already trust)

| Situation | Action |
|---|---|
| Exactly one candidate, A∧B∧D | Write. Provenance = `item_id` + `block_scale` source |
| N candidates, same scaled value, same table | Write once. Provenance lists all `item_id`s |
| N candidates, disagreeing values | Write nothing. Escalate region to Stage 3 |
| A matches a candidate on the wrong face | Not a candidate. (Do not “rescue.”) |
| No A match | No Stage 2 write, even if C is perfect |
| `block_scale` unknown | No Stage 2 write for that block |

Replay contract you already have: *exactly the true repairs, zero false positives.* Encode that as a test, not a hope. If a change increases Stage 2 fill rate and changes any previously locked cell, it is a regression even if the new value looks better.

### No-prior rows (the run-116 surface)

No-prior means Lock A is unavailable. **Do not substitute magnitude matching.** That is allocation scaling under another name.

Join no-prior **only inside a block that already has a lock-A scale anchor** (rule 2 above produced a scale from *other* rows in the same `block_id`):

1. Restrict to that `table_id` + `block_id` + `stmt_face`.
2. Match by `label_norm` kinship **and** `row_ord` position relative to locked siblings (e.g. “the line between Gross Profit and Operating Income”, or “first line of the block”, or “label equals model label after kinship”).
3. Apply **the block’s** scale, never a per-row scale.
4. If two labels in the block kinship-match (common in MD&A restatements), write nothing → Stage 3.
5. If the block has no lock-A sibling, write nothing → Stage 3. Stage 3 is allowed to read no-prior rows *because it carries the checksum contract on the whole region*, which reintroduces an anchor. That is the only legal way to fill no-prior cells.

Position without scale is how a raw-scale number lands in the grid. Scale without position is how a left-neighbour lands in the grid. Require both.

### Non-statement Driver / MD&A / five-year tables

These are where left-neighbour and five-year traps live. Stage 2 is *stricter*, not looser:

- `table_id` is mandatory. A five-year table is one `table_id` with `years` of length 5. The join binds **year column**, not “the number nearest 2025.” If `years` does not contain the model year as a header (printed year, not inferred), the table cannot serve that year.
- Prior identity is weak here (five-year tables often reprint restated priors, or omit the model’s prior year). Prefer **year-header + label + row_ord + block_scale**. If prior is present and conflicts with the year-header binding, write nothing.
- Left-neighbour: an item’s `neighbors.left_label` must not be a stronger kinship match to the model row than `label_norm`. If it is, the extractor probably column-shifted; drop the item.
- Driver tables often mix MW, %, currency, headcount. `unit_dim` mismatch is an automatic reject, no kinship override.
- Do not let MD&A items satisfy statement-face model rows. If the statement face is missing a line that MD&A prints, that is a Stage 3 region read of the *statement*, not a cross-face borrow. Cross-face borrows are how you get “a true number in the wrong cell.”

**What other members will get wrong in Stage 2:**
- Fuzzy label join as primary key (“the extractor already column-bound, kinship is enough”). Kinship without prior is how MEGAWATT hits P&L.
- Per-row scale inference from “what would make this look like a P&L number.”
- Reusing one global `scale=millions` because the 10-K cover said millions. Per-share, share counts, basis points, segment MW, and “thousands of barrels” coexist in the same filing.
- Treating `row_ord` as list index after filtering — it must be the pre-filter geometric order or you reintroduce left-neighbour.
- Letting Stage 2 write on a single ratio-lock sibling. One sibling is a coincidence; two is a scale.

---

## Q3 — Validation that would have caught 112–116 without the vision cache

Local cannot reproduce vision. Therefore **vision is not in the pre-flight path.** Anything that requires a live read to “validate a writer” is how you shipped 112–116.

Split the system at the item table. That cut is the product.

### Three artifacts, pinned, committed

**1. Transcription snapshot (the real golden).**  
From a run whose Stage 1 you trust (or from the clean-room / best consensus extract): the full item table, bytes on disk, hash in the test manifest. This replaces the vision cache. Stage 2–4 must be runnable as:

```
python -m harness join_verify --items fixtures/acme_2025.items.json --model empty_grid.json
```

No network, no vision, no LLM. If this command is not the default fast path, you will not run it.

**2. Write-trace fixture.**  
Same snapshot plus the expected set of cell writes: `(cell_id, value, provenance_kind, item_id|reader_id, scale, scale_source)`. Expected empties / flags are first-class, not omissions. Replay must match the *set*, not a score.

**3. Adversarial canaries (the 112–116 museum).**  
Tiny synthetic item tables, not full filings. Each is one lie:

| Canary | Planted fault | Must happen |
|---|---|---|
| `112_closing_swap` | Closing cash appears in two faces with kinship-able labels | No swap writer fires; at most one cell filled; the other flagged |
| `114_alloc_scale` | Printed thousands next to a millions-anchored block | No write, or write only at block scale; never “fit to model” |
| `115_mw_into_pnl` | Driver MW number, label “Power”, magnitude looks like revenue | Reject on `unit_dim` / `stmt_face` |
| `116_noprior_rawscale` | No-prior row in a block whose checksum/prior siblings were stripped | No Stage 2 write; scale does not come from the raw magnitude |
| `left_neighbour` | Correct label in column 2, bigger number in column 1 | No write from col 1 |
| `five_year_misbind` | 2021–2025 headers, 2024 value sitting under a 2025-shaped magnitude | Bind by header or write nothing |

If a canary is not in CI, that bug class is unowned.

### Minimum honest pre-flight (the new meaning of “validated locally”)

A change is validated only if **all** of these pass:

1. **Writer allowlist AST/lint.** Tests walk the call graph from `write_cell` / grid mutate. Callees must be in `{triple_lock_join, stage3_reader_apply, stage4_repair}`. Allocation, closing swap, breadth auto-apply, mechanical rescue, mapper-apply must be unreferenced or behind a hard `assert False`. This would have made 112 and 114 unmergable.

2. **Provenance required at the type level.** `write_cell` rejects writes without `(source, scale, scale_source)`. No default scale. This would have made 116 unmergable.

3. **Snapshot replay + canaries** as above. Diff is on cells and flags, not on a 0–100 score. A score can rise while a Model-tab key is poisoned.

4. **Invariant suite, model-free:**
   - No write whose `unit_dim` ≠ cell dim.
   - No write from `table_id` A onto a cell already bound to statement table B.
   - No no-prior write from a block with `block_scale=unknown`.
   - Stage 4 may change a cell only if a named check fails *and* a named source item (or Stage 3 read) justifies the new value.
   - Balance / cash / EPS×shares / segment sums / line-for-line identity either pass or the offending cells are flagged, never silently coerced.

5. **Mutation of the snapshot, not of the code.** Take the golden item table, drop all `prior_raw` in one block (the 116 transform), rerun. Expected: those cells empty/flagged, *every other cell identical*. Take the golden, inject a MW item with a P&L-like label (the 115 transform). Expected: zero new P&L writes. This is the test that “validated locally” never meant, and it does not need vision.

6. **Staged canary if and only if a live read changed.** If Stage 1 prompts or vision change, you may not “validate join locally and ship.” You cut a new snapshot on the main region (one paid run, items only, no writers armed), hash it, then run 1–5. Until that snapshot exists, the change is not validated. Main-region blindness is a process bug, not an environment bug.

**What other members will get wrong in Q3:**
- Unit-testing the kinship function and calling it validation. 112–116 were integration writers.
- A pinned *model output* without a pinned *item table*. That golden-izes the machinery’s mistakes.
- Re-enabling live vision in CI “just for confidence.” It will be flaky, skipped, and then bypassed.
- Score thresholds (“must stay ≥76”). Scores hide single-cell poison.

---

## Q4 — Sequencing: fastest path to Model-tab 100%-or-flagged

Owner presents Monday with existing numbers and this architecture story. **Do not touch the live pipeline before that presentation.** A hero rewrite tonight is how you get another 115→116.

Target is not a higher raw score. Target is: every Model-tab 2025 cell is either proven or flagged, on a cold run, agent-only, luna only.

### Do, in this order

**Day 0 (hours, before any “rebuild”):**  
Arm a write firewall. One function mutates the grid. All other writers become no-ops behind a flag defaulted off. Ship that flag into the existing tree. This is reversible and is the highest EV change in the document. Residual chase by hand already showed 76.9 → 83.9 with Model 99.1; the missing piece is *stopping the unproven 16%*, not inventing new fills.

**Day 1:**  
Export item-table snapshots from the best existing runs (you already have ~2,300-item staging extracts). Commit them. Wire `join_verify` so it runs without vision. Port the canary museum. Nothing new joins yet — prove the old triple-lock is replay-stable on snapshots.

**Day 2:**  
Implement Stage 2 exactly as specified: block scale, no-prior rules, face/unit gates, ambiguity → empty. Delete (do not comment out) allocation scaling, closing swaps, breadth auto-applies, mechanical rescues. CI fail if they reappear on the write graph.

**Day 3:**  
Stage 3: *one* fable-mode call per unfilled statement region, existing whole-page + priors + checksum contract. Gap-filler only. Cap: N region calls, no per-row quizzes, no coverage expansion. If the reader returns a value that fails checksum, flag, do not retry with a different prompt.

**Day 4:**  
Stage 4 verify web + existing playbooks, but playbooks may only (a) replace a cell


## Stage 2 — peer reviews

### Review by openai/gpt-5.6-terra

### Response A

**What it does well**

- It correctly identifies the central architectural conclusion: the system should become an evidence-ledger pipeline with tightly controlled write authority, rather than a collection of row-driven fill mechanisms.
- Its Q1 answer is appropriately nuanced. It distinguishes:
  - the necessary final architecture: inversion; and
  - a near-term containment measure: disable all writers except trusted readers, triple-lock joins, and explicit verified formula-derived writes.
  
  That is stronger than simply saying “delete everything,” because it recognizes the immediate need to prevent another harmful run before the full rebuild lands.
- Its Stage 2 design is highly implementable. In particular, it specifies:
  - immutable extraction provenance;
  - table, block, row, and column identifiers;
  - header paths and physical column order;
  - unit, currency, sign, period, and scale metadata;
  - source spans and extraction-consensus fields;
  - explicit target-row schemas rather than vague mapper assumptions.
- The hard-gate framing is very good. Structural domain, face authority, prior identity, label kinship, and uniqueness are treated as eligibility constraints rather than a fuzzy score competition. This directly addresses the MW-to-P&L failure and the duplicate-prior problem.
- Its no-prior rules are especially strong:
  - source block must already be established;
  - scale must come from an evidenced table/block/header context;
  - period must bind through headers rather than adjacency;
  - row order is only a within-proven-block tie-breaker;
  - ambiguous cases route to Stage 3.
  
  This is a faithful treatment of the run-116 lesson.
- It handles non-statement Driver/MD&A and five-year-table risk sensibly by requiring table-level binding before row/cell binding. Its explicit rejection of global “left neighbor,” “next numeric value,” and same-x-position rules is well targeted.
- Its validation design is strong and honest about the vision-cache limitation. The three-layer approach—golden fixtures, pinned extraction snapshots, and a production-like canary—is appropriate. The emphasis on negative tests and diffing source bindings, scale provenance, and flags rather than only scores is particularly good.

**What it does poorly**

- The response does not answer Q4. It ends during the release-terminology section of Q3 and never provides the requested sequencing, risk management, fastest path to a cold run, or explicit “what not to do” plan.
- Because Q4 is a major part of the prompt and time-to-Monday is central to the scenario, this omission is substantial. The response provides strong architecture but not the requested execution plan.
- It is slightly too expansive in the extraction schema. Much of the proposed metadata is valuable, but some fields could be staged rather than required for the first rebuild iteration. A practical plan should distinguish:
  - mandatory minimum metadata for safe joins next week; from
  - desirable future audit/debug metadata.
- The allowance for “deterministic formula/identity-derived values where the formula is explicit and verified” is reasonable, but it needs a more explicit write-authority contract. Otherwise, legacy repair mechanisms could be relabeled as “formula-derived” and regain unsafe write authority.
- Its production canary section is strong, but it should explicitly say that Stage 1 changes require a new production-region transcription snapshot before promotion, rather than merely recommending a representative canary.

---

### Response B

**What it does well**

- It gets the top-level diagnosis right: the harness’s write-side machinery is causing the observed regressions, while the checksummed reader and deterministic checks have been reliable.
- It clearly advocates the right broad architecture: extract facts first, then deterministically bind them to the model rather than repeatedly querying documents from individual model rows.
- It correctly recommends removing or disabling allocation scaling, closing swaps, breadth auto-applies, and mechanical rescues.
- It gives a useful simple rule for ambiguity: zero or multiple matches should not write and should fall through to Stage 3.
- It correctly identifies table-level scale as the essential run-116 protection and suggests preserving `table_id`, `row_index`, and stated scale.
- Its recommendation to use pinned Stage 1 snapshots for local replay and a cloud canary before a broad batch is directionally correct.
- Its Q4 sequencing is concise and operationally useful at a high level: staging extraction, joiner, verifier and gap reader, residual/flagging, cold run.

**What it does poorly**

- It is materially less rigorous than the other responses on Stage 2. The proposed primary join condition is:

  `prior match AND section type match AND fuzzy label > 0.85`

  That is not sufficient for the documented failure modes. It lacks robust hard gates for:
  - unit dimension;
  - currency;
  - period/header binding;
  - statement-face authority;
  - source table/block identity;
  - row role;
  - duplicate-prior ambiguity;
  - scale provenance;
  - source-column identity.
- The statement that there is “no smaller change” is too absolute. A write firewall/disarming legacy writers is a smaller immediate change that can substantially reduce risk while the rebuild is underway. It is not the final architecture, but it is important given the Monday deadline.
- “The LLM is flawless at reading and extracting” overstates the evidence. The prompt supports the claim that checksummed whole-page reads have been error-free in observed runs, not that all extraction paths or all vision behavior are universally flawless.
- Its no-prior logic is under-specified. “Find the table_id where the rest of this section’s rows successfully bound” does not define:
  - how many anchors are required;
  - how scale is proven;
  - how columns are bound;
  - how repeated labels are resolved;
  - how to distinguish multiple similar tables in a section;
  - what happens when table boundaries or headers are uncertain.
- Its Driver/MD&A treatment is too weak. Rejecting tables with five columns when looking for two-year comparables is not a general solution; many legitimate driver tables are five-year tables and must bind by explicit year-header paths, not be categorically rejected.
- The CI rule that “score must go up, and zero previously bound rows are allowed to change state” is too rigid. A justified correction may need to change a previously bound but incorrect cell. The real requirement should be that all changes are expected, reviewed, provenance-backed, and fixture-approved—not that no old binding may ever change.
- It proposes writing a `FLAGGED: [Reason]` string “to the cell.” Depending on the workbook/evaluator semantics, that may corrupt a numeric model cell. Flags should generally be represented through a separate status/provenance layer, comments, a flag sheet, or a defined permissible model convention.
- It does not adequately explain how Stage 4 repairs can write safely or how their write authority is constrained.

---

### Response C

**What it does well**

- It has the sharpest conceptual framing: the inversion should be implemented as an inversion of **write authority**, not necessarily as a greenfield rewrite. That is exactly the practical distinction needed under time pressure.
- Its “monopoly on writes” model is excellent. It clearly separates allowed writers from prohibited writers and treats blanks/flags as legal outcomes rather than failures requiring a plausible-number fallback.
- It directly addresses the major organizational risk: people will try to retain old mechanisms as “fallbacks,” add another mapper guard, or make Stage 2 “smarter” with heuristics. The response correctly explains why those are the path back to runs 112–116.
- Its Stage 2 scale design is particularly strong:
  - scale is a block property, not a number property;
  - explicit table/header scale is preferred;
  - otherwise use multiple independently locked sibling rows to infer one of a controlled set of scale multipliers;
  - if scale cannot be proven, the block is ineligible for Stage 2 writes.
  
  This is the clearest direct defense against run 116 among the responses.
- Its unit-dimension gate directly handles run 115. Prohibiting energy/MW items from serving currency/P&L rows is a necessary structural constraint that B lacks.
- Its ambiguity table is concrete and conservative. Especially good is the distinction between multiple identical source renderings of the same value versus multiple candidates with disagreeing values.
- Its no-prior protocol is strong:
  - require a prior-based scale anchor in the same block;
  - bind only within the identified table/block/statement face;
  - require label plus positional relation to locked siblings;
  - use block scale only;
  - send ambiguity to Stage 3.
  
  The phrase “scale without position is how a left-neighbour lands in the grid; position without scale is how a raw-scale number lands in the grid” is an effective summary of the combined risk.
- Its treatment of five-year and MD&A tables is more complete than B’s. It requires explicit year-header binding and refuses to treat physical adjacency as semantic column identity.
- Its validation proposal is exceptionally strong:
  - pinned transcription snapshots;
  - expected write traces, including expected flags and empties;
  - synthetic regression canaries for each known failure mode;
  - a writer allowlist enforced through the write graph;
  - type-level provenance requirements;
  - mutation tests that remove priors or inject MW-like distractors;
  - a main-region snapshot process whenever live Stage 1 behavior changes.
  
  This directly answers the prompt’s concern that “validated locally” must never again mean “blind on the main region.”
- It also gives a valuable operational distinction: vision should not be required for ordinary local writer validation, but Stage 1 prompt/vision changes must still produce a new production-region, writers-disarmed snapshot before release.

**What it does poorly**

- The supplied response is incomplete. It is cut off during Q4, after beginning Stage 4. It therefore does not fully provide:
  - the complete sequencing plan;
  - the complete explicit “do not do” list;
  - the final cold-run release plan;
  - the full stage-4 write/flagging rules.
- Its Stage 2 statement-row rule may be overly restrictive if applied literally: it says label kinship should not create a match when prior identity failed and routes all such cases to Stage 3. That is defensible for safety, but could reduce useful deterministic coverage unless the model distinguishes statements, driver tables, formula rows, and source structures more explicitly. A conservative initial release can accept this, but it should be framed as an intentional coverage-vs-safety tradeoff.
- The proposed ratio-lock scale inference is strong but should be carefully constrained in implementation:
  - it needs period consistency;
  - it needs explicit rounding behavior;
  - it should ensure the sibling matches are themselves independently trustworthy;
  - it should not infer scale across blocks merely because they share a statement face.
  
  The response implies much of this, but a build specification should make it explicit.
- The “writer allowlist AST/lint” idea is excellent as defense in depth, but static call-graph enforcement alone may miss indirect mutation paths, reflection, workbook utility methods, or external side effects. It should be paired with runtime enforcement through a single write API and an immutable workbook/input state.
- Its Q4 recommendation to ship a write firewall immediately is good, but because the response is truncated, it never fully reconciles that emergency containment change with the owner’s expectation of an agent-complete cold run next week.

FINAL RANKING:
1. Response C
2. Response A
3. Response B

### Review by google/gemini-3.1-pro-preview

### Evaluation of Responses

**Response A**
* **What it does well:** Response A provides a highly rigorous, schema-centric approach to the architectural rebuild. Its proposed `ExtractedItem` and `TargetRow` dictionaries in Q2 are excellent, forcing strict metadata requirements that would prevent the exact traps (like the 5-year table or left-neighbor traps) mentioned in the prompt. The gating system (Structural Domain -> Face Authority -> Prior Identity -> Label Kinship -> Unique Binding) is a brilliant translation of the "triple-lock" concept into deterministic code. For Q3, the three-layered validation protocol effectively solves the vision-cache bottleneck by isolating the transcription artifact.
* **What it does poorly:** The response completely fails to answer Q4. It ends abruptly after Q3, completely omitting the sequencing, the strategy for the Monday presentation, and the explicit list of what *not* to do. 

**Response B**
* **What it does well:** This response is structurally complete, addressing all four questions clearly. It provides a solid, easy-to-follow day-by-day plan for Q4, and correctly identifies that the current architecture is failing because it operates as a "pull" rather than a "push" system. 
* **What it does poorly:** It lacks the deep technical and domain rigor required by the prompt. For example, in Q2, it suggests using `fuzzy_match(item.label, model.label) > 0.85`. In financial statements, relying on basic fuzzy matching is catastrophic (e.g., "Net Income" and "Net Income Attributable to Noncontrolling Interests" are highly similar textually but financially distinct). Furthermore, for Q3 CI validation, it dictates "Score must go up"—completely missing the prompt's evidence that top-level scores are masking critical, scale-poisoned single-cell regressions. 

**Response C**
* **What it does well:** Response C is a masterclass in software architecture and displays profound domain expertise. It deeply understands the mechanics of the failures—for instance, its realization in Q2 that the previous checksums were secretly functioning as a "ratio lock" to anchor block scale is a brilliant diagnosis of the run-116 bug. The constraints placed on Stage 2 (especially regarding `block_scale` and no-prior rows) are ironclad. Its Q3 validation protocol is the strongest of the three, specifically designing adversarial canaries for every single failing run mentioned in the prompt. It also smartly distributes the requested "what others will get wrong" warnings contextually throughout each section.
* **What it does poorly:** The response truncates slightly at the very end of Q4 (cutting off mid-sentence during Day 4). However, it still manages to cover the Monday presentation strategy, the Day 0-4 sequencing, and the immediate risks before the cutoff. The sheer depth and accuracy of the engineering plan make it the best response despite the truncation.

FINAL RANKING:
1. Response C
2. Response A
3. Response B

### Review by x-ai/grok-4.6

## Response A

**What it does well**
- Q1 is correctly framed: inversion is the destination; a write-containment bridge is useful but not equivalent. The governing rule (“write only from a uniquely bound document item under explicit scale/column rules”) is the right invariant.
- Q2 is the most complete *schema* of the three. Provenance fields, header paths, measure families, face-authority ranking, and two-level table-then-cell binding for MD&A/drivers would actually prevent 115 and the five-year / left-neighbour traps if implemented.
- Scale vs parsed value is handled correctly: no-prior rows cannot establish scale from magnitude. Unique-binding-or-escalate is the right ambiguity rule.
- Q3’s three layers (adversarial goldens, pinned ledgers, production canary) and the insistence on *negative* assertions are honest. The terminology split (unit-tested vs snapshot-tested vs canary-validated) would stop “validated locally” from meaning “blind on main.”

**What it does poorly**
- Q4 is missing. The answer stops at “Dispatch-approved:”. For a Monday presentation and a next-week landing, sequencing *is* the decision. That is a hard miss against the brief.
- The item/target schemas are build-spec heavy for a one-week rebuild. Teams will spend days on `header_path` / `sign_convention` instead of a write monopoly and block-scale.
- “What other members will get wrong” is mostly implicit. It does not name the specific regressions (kinship-as-primary-key, per-row scale, score-as-gate) as sharply as C.
- Gate language sometimes still sounds like a scoring contest (“label kinship may rank”) without C’s hard “no Lock A ⇒ no Stage 2 write.”

## Response B

**What it does well**
- Clearest narrative: pull vs push, burn the ~20 writers, blank is safe. Easy for an owner slide on Monday.
- Q2’s core insight is right: `stated_scale` belongs to the *table*, not the row; Pass B must stay inside a table already bound by priors.
- Ambiguity rule is simple and correct: 0 or >1 matches → do nothing → Stage 3.
- Q3’s staging snapshot + local replay without vision is the minimum honest cut.
- Q4 exists and is usable: demolition, joiner, gap-filler, flag, cold run. “Do not make Stage 2 smarter to save Stage 3 calls” is the right team warning.

**What it does poorly**
- Pass A’s `fuzzy_match > 0.85` is exactly the class of machinery that caused 115. Label similarity as a *join key* (not a tie-break after prior + face + unit) will reintroduce MW-into-P&L.
- Pass C is thin: “expected column structure” does not specify year-header binding, `unit_dim`, neighbour checks, or “one agreeing sibling is not a scale.”
- CI contract “score must go up” is a trap the brief already falsified. Scores rose while cells were poisoned.
- Day-1 “delete all ~20 mechanisms” before a write firewall and pinned snapshots is how you get another 115→116 the night before the owner talk.
- Less concrete on no-prior scale *computation* (ratio lock from ≥2 siblings). “Multiply by `stated_scale`” assumes extraction always printed a header; run 116 was the case where that anchor vanished.
- Does not systematically flag wrong turns the way the prompt asked.

## Response C

**What it does well**
- Best Q1: invert *write authority*, not the codebase. The monopoly table (triple-lock / checksummed region read / cited Stage-4 repair vs everything else) is the smaller change with the same effect, and it matches the evidence (every failure was a writer).
- Best Q2 for *building this week*: block_scale as a pre-write property (header → ≥2 sibling ratio-lock → else unknown); `unit_dim` hard gate; A∧B∧D required; kinship ranks only; no-prior only inside an already-anchored block with label *and* `row_ord`; year-header binding for five-year tables; left-neighbour drop rule. This is the run-116 lesson stated as an invariant, not a hope.
- Explicit “what others will get wrong” on each stage (fuzzy label as primary key, global millions, `row_ord` after filter, single-sibling scale).
- Best Q3: split at the item table; writer-allowlist on the call graph; provenance required at the type; canary *museum* for 112–116; mutate the snapshot (strip priors, inject MW) and demand other cells unchanged. That protocol would have made 112–116 unmergeable without vision.
- Best Q4 start: do not touch the live pipeline before Monday; Day 0 write firewall; target is 100%-or-flagged, not a higher raw score; playbooks may only replace a cell under a named check + source.

**What it does poorly**
- Q4 is truncated mid-sentence at Day 4, so the last mile (playbook limits, cold-run gate, explicit NOT-do list) is incomplete—though still more decision-ready than A.
- Slightly less encyclopedic than A on extraction schema (header paths, crop ids). A builder might still need A’s field list when implementing Stage 1.
- Denser and more legalistic; a Monday verbal story is easier from B’s first page. That is a presentation issue, not a technical one.

---

C is the only answer that is simultaneously architecturally right, specified tightly enough to implement Stage 2 without reintroducing writers, and honest about validation and Monday risk. A is the strongest reference design but fails the sequencing question. B is the best memo and the weakest spec (fuzzy thresholds, score CI, demolition-first).

FINAL RANKING:
1. Response C
2. Response A
3. Response B


## Ranking tally (Borda)

- Response C (x-ai/grok-4.6): 9 pts
- Response A (openai/gpt-5.6-terra): 6 pts
- Response B (google/gemini-3.1-pro-preview): 3 pts

## Stage 3 — chairman synthesis (google/gemini-3.1-pro-preview)

The council has reviewed the evidence, the proposed architectural inversion, and the peer evaluations. The consensus is unanimous: you are caught in a classic local maxima trap. The harness is no longer facilitating the LLM; it is actively sabotaging it. Your ~20 cooperating mechanisms are a symptom of a system fighting its own fundamental design.

Here is the synthesized blueprint for the rebuild, combining the structural rigor of Response A, the narrative clarity of Response B, and the surgical invariants of Response C.

---

### Q1: Is the inversion the right call?

**Yes. Invert the write authority.**

The evidence is conclusive: every success this week was a checksummed read, a deterministic join, or a deterministic check. Every regression was a write-side heuristic ("machinery"). The current architecture is a **pull** system—individual model rows solicit data, forcing heuristics to guess where and how to look. The inverted architecture is a **push** system—extract all facts, bind them strictly, and read narrowly only for gaps.

The "smaller change with the same effect" is not a new idea; it is the inversion implemented as a **monopoly on writes**. 

Keep Stage 1 (consensus extraction), the triple-lock, the checksummed reader, and the verify web. **Delete the right to invent numbers.** 

| May Write a Cell | May NOT Write a Cell |
| :--- | :--- |
| Stage 2: Triple-lock join (deterministic code) | Allocation / scaling heuristics |
| Stage 3: Checksummed region read (LLM gap-filler) | Closing-loop swaps |
| Stage 4: Repair (must cite a failed check + source item) | Breadth auto-applies, mechanical rescues, bridges |

If a cell cannot be produced by those three authorized paths, it stays empty and gets flagged. A blank cell is a safe, legal state. A heuristically guessed number is a systemic poison.

---

### Q2: Stage 2 Specification (The Deterministic Join)

Stage 2 must be a sequence of hard eligibility gates, not a scoring contest. 

#### 1. Enriched Extraction Schema (Stage 1 Output)
Loose `{value, prior, page, stmt-tag}` items are insufficient. Stage 1 must emit an evidence ledger. If an item lacks these, it is ineligible for Stage 2:
*   `table_id` & `block_id`: Adjacent tables are different tables.
*   `row_ord`: Stable geometric order in the table (PDF y-rank, not list index).
*   `col_bind`: Explicit column-to-year mapping via header paths.
*   `stmt_face`: Primary face authority (IS, BS, CF, MDA, DRIVER, etc.).
*   `unit_dim`: Measure family (currency, shares, energy, %, ratio).

#### 2. The Scale Invariant (The Run-116 Fix)
**Scale is a property of the block, never of the row.** Do not infer per-row scale to make a number "fit" a model cell. Compute `block_scale` before any join:
1.  **Explicit:** Read from the table/block header ("$ in millions").
2.  **Ratio Lock:** If no header exists, find $\ge 2$ uniquely triple-locked siblings in that block that possess priors. If `model_prior / prior_raw` yields the exact same multiplier (e.g., 1e6) for all siblings, that consensus is the `block_scale`.
3.  **Unknown:** If neither applies, `block_scale = unknown`. The entire block is ineligible for Stage 2. Send to Stage 3.

#### 3. The Joining Gates (In Order)
A Stage 2 write requires **A ∧ B ∧ C**. Label kinship is a tie-breaker, not a primary key. (Relying on fuzzy label matching is what caused the Run-115 MW-to-P&L regression).
*   **Gate A: Prior Identity.** `item.prior_raw * block_scale == model.prior` (exact match after scale). 
*   **Gate B: Face Authority.** `item.stmt_face` must exactly match the model row’s expected statement.
*   **Gate C: Unit Dimension.** A megawatt item (`unit_dim=energy`) cannot join a P&L currency row, even if the label is a 100% match.
*   **Gate D: Label Kinship.** Used only to rank or break ties if multiple candidates share the exact same prior value.

**Ambiguity Rule:** If 0 matches, or >1 match with disagreeing values, **write nothing**. Send the region to Stage 3. 

#### 4. Handling Traps: No-Priors, 5-Year Tables, & MD&A
*   **No-Prior Rows:** A no-prior row may only join if it is inside a block that *already* has a lock-A scale anchor. It binds by `label_norm` + `row_ord` relative to those locked siblings. Apply the `block_scale`. No independent scale guessing.
*   **5-Year Tables:** Stage 2 must bind to the table and year-headers first. Do not use adjacency ("left neighbor") as column identity. If the specific year header is missing, write nothing.

---

### Q3: Minimum Honest Pre-flight (Validation)

Local CI cannot reproduce the vision cache. Therefore, **vision is not in the pre-flight path.** Anything that requires a live LLM read to "validate a writer" is how you shipped 112–116 blindly.

1.  **Pinned Extraction Snapshots:** Cut the system at the item table. Store the exact JSON extraction ledgers from known-good runs. Stage 2–4 must be runnable locally from these static files in seconds. 
2.  **Type-Level Provenance & AST Linting:** `write_cell` must statically reject writes without `(source_id, scale, scale_source)`. Tests must walk the call graph to ensure allocation/swaps are completely disconnected.
3.  **The Adversarial Museum (Negative Tests):** Create synthetic JSON item tables with planted faults to test boundaries:
    *   *112 closing swap:* Plant identical closing cash rows in two faces. Assert no cross-swap occurs.
    *   *114 alloc scale:* Plant "thousands" printed next to a "millions" block. Assert no scale bleeding.
    *   *115 MW into P&L:* Plant `unit_dim=energy` with the label "Power Revenue". Assert rejection.
    *   *116 no-prior scale:* Strip prior siblings from a block. Assert the no-prior row drops to Stage 3.
4.  **Mutation Testing:** Take a golden snapshot. Delete all priors in a block (simulating 116). Run locally. Expectation: those cells flag, *every other cell remains perfectly identical*.
5.  **The Production Canary Contract:** If you change Stage 1 (prompts/vision), you cannot validate locally. You must generate a new production-region snapshot (extract only, no writers armed), pin it, and run the CI suite against it before promoting code.

---

### Q4: Sequencing, Risk, and the Next 7 Days

**The Monday Narrative for the Owner:** "We have proven the AI can read perfectly and our math checks work. The middle-layer heuristic software is causing 100% of the volatility. This week, we are amputating that middle layer and wiring the deterministic reader directly to the math checks. We expect a temporary drop in raw fill rate, culminating in our goal: 100% verified or cleanly flagged."

**The Fastest Path to a Cold Run (Sequence):**

*   **Day 0 (Pre-Presentation): Arm the Write Firewall.** Do not execute a hero rewrite before the presentation. Create a single `write_cell` function. Put all heuristic writers (allocation, rescues, swaps) behind a feature flag defaulted to OFF. Stop the bleeding.
*   **Day 1: Snapshots & Mocks.** Export existing high-quality item tables. Commit them. Wire the CI harness to run without vision. Build the 112-116 Adversarial Museum in CI.
*   **Day 2: The Stage 2 Joiner.** Implement the strict gates, the block-scale ratio lock, and the ambiguity->empty rules in pure Python. Delete (do not comment out) the legacy heuristic writers. Accept that many rows will now sit blank.
*   **Day 3: Stage 3 Gap Filler.** Hook up the proven 0-error whole-page reader, restricted to *one* fable-mode call per unfilled statement region. No per-row quizzes. If it fails a checksum, flag it.
*   **Day 4: Verify & Chase (Stage 4).** Hook up the deterministic math checks. Playbooks may only execute if they explicitly cite a failed check and point to a specific source item. 
*   **Day 5: The Final Abort.** If a row fails Stage 4, the agent writes `FLAGGED: [Reason]` to the cell's provenance/comment layer. Execute the cold run. 

**What you explicitly MUST NOT DO (Watch your team for these):**
*   **Do not make Stage 2 "smarter".** Engineers hate blank rows. They will try to add a "quick regex fallback" or use fuzzy label matching as a primary key to save Stage 3 LLM calls. Reject the PR immediately. 
*   **Do not use a global fallback scale.** Assuming "millions" because it was on the 10-K cover will poison per-share, MW, and headcount rows.
*   **Do not touch the Stage 3 prompt.** It works perfectly. Only change its routing.
*   **Do not use top-level score thresholds for CI.** Scores hide single-cell poison. A score can go up while a critical P&L cell is overwritten with a Megawatt figure. Diff the source bindings and flags, not the score.
