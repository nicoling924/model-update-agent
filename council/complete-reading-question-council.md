# LLM Council transcript

## Question

# Design question: is "complete-extraction-first" the right fundamental cut?

## Context

We are building a generic, objective-based agent (engine: gpt-5.6-luna) that
marks equity-research Excel models to actual results from PDF disclosures
(Chinese annual reports, often scanned). Hard requirements from the owner:
model balances every year; key numbers (sales + segment breakdown, GP +
breakdown, NP, cash, CA/NCA/CL/NCL, equity, CFO/CFI/CFF) must be CORRECT,
not just flagged; always deliver; never a wrong unflagged number; ≤60 min
per run. The agent must THINK like an analyst — no hardcoded workflows.

## The failure pattern we must escape

25 runs in. The architecture: deterministic evidence extraction feeds an
LLM agent that maps disclosure lines to model rows through guarded write
tools (writes need citations; identity checksums refuse unproven values;
zero wrong writes since guards landed). Balance now passes all years;
8-10/10 headline keys tie print. But EVERY run still fails on some rows
because the EVIDENCE POOL HAS HOLES, and each hole became its own bolt-on
channel across runs:

1. pdfplumber text lines (loses table columns)
2. "table islands" (grid rendering with headers)
3. vision transcription of scanned pages
4. "verified ingest" (whole-page LLM transcription, checksummed: a row is
   believed only if its comparative ties a model prior at identity grade)
5. "recovery mode" (vision-missed lines resurrected by prior-anchor)
6. "section closure" (subtotals as equations: proves single-number column
   placement → absent-line zeros; derives missing rows by difference)
7. "sightings" (note-page lines printing a model prior, surfaced to the
   agent because note pages are banned from machine writes after a junk
   note number once corrupted net profit)
8. "last-year map" (find the row's prior value in the PRIOR-year report,
   then walk to the current report's counterpart section by label overlap
   — handles re-based segment categories)

Each channel was born from one run's miss. The owner has now called this
what it is: a patch spiral. His directive: "if it's a fundamental issue,
fix it fundamentally."

## The proposed fundamental fix

Invert the architecture: the run's FIRST product is one complete,
column-resolved, verified transcription of the statements + relevant notes
(a canonical staging extraction), and mapping runs only against that
complete world. Completeness is PROVEN, not asserted:

- (a) every statement section closes against its printed subtotal
  (both columns);
- (b) every open model row's prior value is either LOCATED in the
  extraction or proven absent (searched pages enumerated);
- (c) pages failing (a) or (b) are re-read (better prompt, higher zoom,
  targeted) inside the run until the proof passes or the gap is
  explicitly recorded.

The existing channels stop being independent evidence sources and become
internal verification/repair steps of the ONE reading stage. Downstream,
the mapping agent gets a complete dataset, so "look elsewhere" becomes a
query over the extraction instead of a hope that the right snippet was
served.

Additionally: a pre-dispatch OFFLINE benchmark (we have the archived
documents + every historical failure class) — a head is dispatched only
when the full benchmark passes, so live runs stop being discovery tools.
Live runs cost the owner an hour each.

## Questions for the council

1. Is complete-extraction-first the right fundamental cut, or is the
   channel accumulation actually fine (convergent, not divergent) and the
   real fundamental issue elsewhere (e.g. in the mapping agent's task
   shape, or the guard design)?
2. What is the cleanest ARCHITECTURE for the one reading stage given a
   weak-ish engine (luna) that misreads scanned CN tables: how do we get
   whole-report completeness within ~30 min of runtime — page selection,
   per-page transcription with closure repair loops, what to do about
   notes (hundreds of pages, only some relevant)?
3. Completeness proof design: are (a)+(b) sufficient? What completeness
   claims can NOT be proven deterministically, and how should the run
   treat them honestly?
4. What are the failure modes of extraction-first (e.g. a wrong-but-
   internally-consistent extraction poisoning everything downstream), and
   what invariants prevent them?
5. Is the offline benchmark gate sound, or does it risk overfitting the
   agent to DFE's document quirks (the generic-agent requirement)?

Answer concretely. The measure of a good answer is a design we can build
once and stop patching.


## Stage 1 — answers

### Response A — openai/gpt-5.6-terra

## Short answer

**Yes: the fundamental cut should be “canonical, coverage-proven evidence world before mapping.”**  
But I would slightly refine the proposal:

> Do not require a literal complete transcription of the entire annual report. Require a **complete, column-resolved, provenance-preserving extraction of the disclosure universe relevant to the model**, with an explicit coverage contract.

That distinction matters. “Transcribe every relevant note” is right in principle, but “relevant” must be discovered and proven through a structured coverage plan—not guessed page by page and not expanded into hundreds of pages by default.

The current architecture is not bad because it has multiple extraction methods. It is bad because those methods have become **peer evidence channels with different semantics and different failure behavior**. They should be demoted into repair/verification mechanisms beneath one canonical evidence layer.

The desired architecture is:

```text
Document intake
  -> document map / report manifest
  -> coverage planner
  -> canonical evidence extraction
       -> structural reconstruction
       -> OCR / vision / text alternatives
       -> page-level repair loops
       -> reconciliation and validation
  -> coverage proof / unresolved-gap register
  -> semantic mapping to model rows
  -> guarded writes
  -> model-wide accounting validation
  -> delivery with explicit exceptions, if any
```

The mapping agent should never be asked to “find the number somewhere in the report.” It should be asked:

> “Given this bounded, typed evidence world, identify the appropriate accounting concept, scope, period, unit, and column for this model row.”

That is a much better task shape for a weak model.

---

# 1. Is complete-extraction-first the right fundamental cut?

## Yes, with one important correction: make it “coverage-first canonical evidence,” not “whole-report transcription first”

Your current failure mode is fundamentally an **evidence coverage problem**, not primarily a mapping or guard problem.

The evidence channels were individually reasonable:

- text extraction catches born-digital text;
- table islands restore table geometry;
- vision handles scans;
- comparative/prior matching helps repair OCR;
- subtotal closure detects omissions;
- note sightings provide alternate evidence;
- last-year maps handle category changes.

The patch spiral appeared because each channel became an independent route by which an agent could discover evidence. That means the system has no single answer to:

- What pages have been searched?
- Which sections are complete?
- Which rows are represented?
- Which columns are resolved?
- Which values are primary disclosure versus note-only support?
- Which missing values are truly absent versus merely not yet found?

Without those answers, every future miss creates another “search elsewhere” mechanism.

So the right fundamental change is:

> Convert all extraction methods into components of one evidence compiler whose output is a canonical disclosure graph plus a coverage certificate.

The canonical layer should not be “a pile of transcribed rows.” It should be a typed graph of disclosure facts.

For example:

```json
{
  "fact_id": "CNAR2024:consolidated:is:revenue:2024",
  "concept": "Revenue",
  "statement": "Consolidated Income Statement",
  "scope": "Consolidated",
  "period_end": "2024-12-31",
  "period_type": "FY",
  "value": 1523400,
  "unit": "RMB thousand",
  "column_role": "current_year",
  "row_label_raw": "营业收入",
  "row_label_normalized": "revenue",
  "page": 87,
  "bbox": [x1, y1, x2, y2],
  "source_crop": "sha256:...",
  "extraction_methods": ["table-layout", "vision-ocr"],
  "verification": {
    "cross_method_agreement": true,
    "statement_equation_participation": true,
    "comparative_match": true
  },
  "status": "verified"
}
```

The mapping layer should consume facts such as this, not raw snippets and not independently discovered note text.

## The guard design is still necessary, but it is not sufficient

Your guarded writes have done exactly what guards should do: prevent silent corruption.

They do not solve the main problem because guards answer:

> “May I write this proposed number?”

They do not answer:

> “Have we found all the evidence necessary to produce the model?”

A model can balance, have correct headline rows, and still be materially incomplete. Accounting identities constrain arithmetic; they do not prove semantic coverage.

## The mapping task shape should change too

There is a secondary architectural issue: mapping should be separated into two tasks.

### Task A: evidence compilation

Produce structured facts with:

- page and bounding-box provenance;
- statement/note identity;
- row and column geometry;
- entity scope;
- current/prior/recast/restated column role;
- units;
- sign convention;
- source confidence;
- validation links.

### Task B: accounting-semantic mapping

For each model row, select or derive from canonical facts:

- accounting concept;
- scope;
- reporting period;
- line-item definition;
- statement versus note hierarchy;
- whether a value is direct, aggregated, derived, or absent.

Do not make the same agent solve OCR/layout recovery, page retrieval, concept mapping, accounting interpretation, and workbook mutation in one loop. Luna may be adequate at the second task if the first produces good structure. It is much less likely to be reliable when asked to do all five.

---

# 2. Clean architecture for the reading stage

## Design principle: compile a report-specific disclosure graph, not a full text corpus

The reading stage should have five products:

1. **Report manifest**
2. **Coverage plan**
3. **Canonical fact store**
4. **Validation graph**
5. **Gap register**

The gap register is essential. It turns “we could not find it” into a typed, auditable state rather than an implicit failure or an invented zero.

---

## A. Report manifest: cheap, broad, deterministic first pass

Build a document map before interpreting accounting values.

For every page, retain:

- physical page number and printed page number;
- text-layer density;
- image/scanned classification;
- language/script density;
- likely table density;
- detected headings;
- detected note number;
- section classification;
- entity/scope indicators;
- page dimensions and render quality;
- OCR index;
- thumbnails / low-resolution images.

Classify pages into at least:

```text
front matter
audit report
financial statement index
primary statements
statement continuation
notes index
note pages
segment information
cash-flow note
equity note
appendices / ESG / governance / irrelevant
```

This should be largely deterministic or cheap-model assisted. It need not read values correctly yet.

### Important: identify the authoritative financial statements

Chinese annual reports often contain multiple financial statement sets:

- consolidated;
- parent/company-only;
- annual report highlights;
- five-year summaries;
- management discussion;
- audited statements in a separate section;
- restated comparatives;
- notes with repeated statement values.

The manifest must identify the **authoritative set** before extraction begins. A large fraction of dangerous errors are correct numbers from the wrong scope or document section.

---

## B. Coverage planner: derive the minimum necessary disclosure universe

The coverage planner should use three inputs:

1. **Workbook demand graph**
2. **Report manifest**
3. **Prior-year extraction/model map**

### Workbook demand graph

Represent every open model row as a requirement, not merely a spreadsheet coordinate:

```text
Requirement:
  concept: Revenue
  scope: Consolidated
  period: FY 2024
  expected source class: Income Statement or Revenue Note
  expected unit: model unit
  accepts: direct / sum of components / derivation
  criticality: headline / balance-sheet / support
  must_have: yes
```

For segment rows, the requirement includes dimensions:

```text
Revenue by:
  segment = business/geography/channel
  measure = external revenue / total revenue / intersegment revenue
  scope = consolidated
```

This prevents the common mistake of mapping the right label but wrong dimension.

### Coverage expansion rules

The planner should always include:

- all primary financial statements;
- statement continuation pages;
- statement of changes in equity;
- cash flow statement;
- note index;
- notes explicitly referenced by statements;
- notes needed by open model requirements;
- segment, revenue, GP/cost, tax, cash flow, debt, equity, and balance-sheet-detail notes where demanded;
- pages needed to resolve restatements, units, scope, and accounting-policy changes.

It should not initially transcribe all 300 note pages at high fidelity.

Instead, it should discover notes through multiple independent routes:

1. note references from primary statements;
2. note table of contents;
3. note headings;
4. model-row concept dictionary;
5. prior-year note mapping;
6. statement label to note-number anchors;
7. search of OCR/text index;
8. segment/revenue disclosure keywords.

For example, if the model requires business-segment revenue, the planner should include candidate pages from:

- “分部信息”;
- “经营分部”;
- “按产品/业务划分”;
- “客户合同收入”;
- “主营业务收入”;
- “收入构成”;
- segment note references;
- prior-year corresponding note pages.

This is not a hardcoded workflow in the bad sense. It is a reusable coverage-planning ontology.

---

## C. Canonical page extraction: geometry first, language second

For scanned Chinese tables, do not trust a whole-page LLM transcription as the primary record.

The primitive should be a **page evidence packet**:

```text
Page evidence packet:
  page image(s), multiple resolutions
  OCR tokens with coordinates
  table regions
  row boundaries
  column boundaries
  headers and column roles
  footnotes and unit labels
  transcription candidates
  page-level validation results
  source crops for every accepted fact
```

### Recommended extraction stack

For each selected page:

1. **Render at two or more resolutions**
   - Normal resolution for page context.
   - High resolution for table cells and small Chinese characters.

2. **Obtain multiple readings**
   - PDF text layer if usable.
   - Traditional OCR/layout engine.
   - Vision model/table transcription.
   - Targeted crop transcription for disputed rows or cells.

3. **Recover table geometry**
   - Detect horizontal and vertical structure where possible.
   - Infer columns from numeric alignment even where grid lines are absent.
   - Explicitly identify headers, current year, comparative year, recast/restated indicators, and units.

4. **Create cell/row hypotheses**
   - Never directly emit only “row label -> number.”
   - Emit row label, current column, prior column, unit, sign, and table context.

5. **Validate locally**
   - subtotal closure;
   - sum-of-components closure;
   - comparative consistency;
   - row ordering;
   - unit consistency;
   - expected sign patterns;
   - repeated header consistency across continuation pages.

6. **Repair only failed regions**
   - Crop the specific ambiguous row;
   - use a higher-resolution render;
   - ask a focused transcription prompt;
   - compare alternate OCR;
   - use neighboring rows and subtotal arithmetic as constraints.

This means “recovery mode,” “vision resurrection,” “table islands,” and “verified ingest” become repair operators beneath one output contract.

---

## D. Closure repair loops

Your proposed closure loop is correct, but it needs to distinguish the type of failure.

For each page/section, create explicit validation obligations:

```text
Structural:
  - row labels and columns parsed
  - headers identified
  - units identified
  - page continuation correctly linked

Arithmetic:
  - subtotals close
  - statement identities close
  - sum-of-segment tables close where applicable

Cross-period:
  - comparative column matches prior disclosure, adjusted for restatement if stated
  - current/prior columns not swapped

Cross-source:
  - statement values match note values when they should
  - values repeated in summary pages are non-contradictory

Demand coverage:
  - each required model concept has a direct fact, valid derivation path, or explicit unresolved status
```

Then run targeted repair loops, not general retries:

| Failure | Repair action |
|---|---|
| Numeric OCR ambiguity | high-resolution cell crop; alternate OCR; digit-specific prompt |
| Column ambiguity | header/column crop; inspect neighboring pages; compare prior year |
| Missing line between subtotal and heading | row-band crop; detect y-coordinate gaps; use source image |
| Wrong entity scope | inspect statement title and audit section; reject non-authoritative table |
| Unit ambiguity | inspect title/footnote/header; compare order of magnitude to prior year |
| Note candidate missing | expand retrieval through note index, references, synonyms, prior-year note map |
| Segment taxonomy changed | extract all current taxonomy rows first, then perform cross-year semantic mapping |

### Runtime budget

Within 30 minutes, use a tiered budget:

```text
0–3 min: intake, manifest, page classification, workbook demand graph
3–10 min: exhaustive primary-statement extraction in parallel
8–18 min: targeted high-priority notes and segment/revenue notes
15–24 min: validation, repair loops, prior-year comparison
22–28 min: mapping and guarded writes
28–30 min: full workbook checks, gap report, delivery package
```

This assumes parallel workers/pages. If processing is sequential, the requirement is unlikely to be robustly achievable for difficult scanned reports.

A useful scheduling policy is:

1. First secure all headline and balancing requirements.
2. Then secure all model-open rows.
3. Spend remaining budget on ambiguity reduction and noncritical detail.
4. Never spend five minutes improving a low-materiality note while revenue, debt, or segment sales remain unresolved.

---

## E. Notes: do not ban them; classify their authority

The prior “note pages are banned from machine writes” rule is understandable but too blunt.

Notes are often the only authoritative source for:

- segment revenue;
- revenue split;
- cost of sales split;
- debt maturity;
- capex;
- cash-flow detail;
- intangible asset additions;
- provisions;
- equity movements;
- tax reconciliation;
- receivables/payables detail.

The correct policy is:

> Notes may write only when their fact type is expected for the requested model row, their scope/period/unit are resolved, and they pass the same provenance and validation contract as statement facts.

Instead of banning notes, use source classes:

```text
Tier 1: audited primary statements
Tier 2: audited notes directly tied to a statement line
Tier 3: audited segment/revenue/detail notes
Tier 4: narrative discussion, highlights, investor-relations summary
Tier 5: unaudited or ambiguous narrative material
```

Tier 4 and 5 can generate search candidates or corroboration, but not automatic writes for core rows.

---

# 3. Completeness proof: are (a) + (b) sufficient?

## No. They are necessary but not sufficient.

Your proposed proofs are valuable:

### (a) Section closure against printed subtotals

This detects:

- missed rows;
- malformed digits;
- column shifts;
- OCR omissions;
- wrong signs;
- broken table boundaries.

### (b) Every open model row’s prior value is located or proven absent

This detects:

- missing expected prior-year line items;
- category disappearance;
- unsearched note sections;
- reclassified segment categories;
- evidence holes relative to the model.

But neither proves semantic completeness.

A table can close while being wrong. For example:

- two rows are swapped;
- current and prior columns are swapped consistently;
- a digit error is offset by another digit error;
- a subtotal itself is misread;
- a line is assigned to the wrong entity/scope;
- a reported subtotal is not the subtotal relevant to the model;
- a new current-year category has no prior-year anchor;
- the model expects external segment sales but the extracted table contains total segment sales including intersegment revenue.

## Add at least five more completeness/validity obligations

### 1. Scope proof

Every accepted fact must be assigned one of:

```text
consolidated
parent company
subsidiary
segment
continuing operations
discontinued operations
total group
other explicitly named scope
```

No core-model write without a resolved scope.

This prevents a correct parent-company cash balance from entering a consolidated model.

### 2. Period and column-role proof

Every value must have:

```text
current year
prior year
recast comparative
restated comparative
opening balance

### Response B — google/gemini-3.1-pro-preview

Here is the unvarnished architectural assessment of your system. 

### 1. Is "complete-extraction-first" the right fundamental cut?

**Yes. It is the absolute correct cut.** Your owner’s intuition is spot on: the "patch spiral" you are experiencing is the classic symptom of conflating **data gathering** with **data mapping (logic)**.

Right now, your mapping agent is acting as an investigator, poking in the dark. Every time it fails, you build it a new flashlight (a new extraction channel). But a human analyst doesn't update a model by reading a PDF line-by-line to find matches. They establish a "trusted universe" of numbers first—they footprint the statements, verify the math, find the relevant notes—and *only then* do they put pen to paper. 

Moving to an extraction-first architecture transitions your system from a fragile, non-deterministic search process into a classic ETL (Extract, Transform, Load) pipeline. 
*   **Extract/Verify:** Creates the canonical, mathematically sound JSON representation of the financials.
*   **Map/Load:** Pure logic. It operates *only* on the verified JSON.

If a number is missing, you now have a single, isolated domain to debug: Did the extraction stage fail to find it, or did the mapping stage fail to place it? 

***

### 2. The Cleanest Architecture for the Reading Stage (Solving for Luna + 30 min limit)

You cannot transcribe a 300-page scanned Chinese annual report in 30 minutes with a weak model using brute force. Furthermore, transcribing 250 pages of boilerplate notes is a waste of compute. You need a **Demand-Driven, Mathematically Bounded Funnel.**

**Phase 1: Orientation (Minutes 0-3)**
*   Do not read page by page. Use heuristics or a fast LLM pass to map the document: find the Table of Contents, locate the Core Statements (usually a contiguous 4-10 page block), and locate the Index of Notes.

**Phase 2: Core Statement Extraction (Minutes 3-12)**
*   Send *only* the pages containing the IS, BS, CF, and Equity statements to Luna.
*   **The Luna Grid-Repair Loop:** Because Luna misreads scanned grids, do not ask it to "read the page." Use a traditional vision model/library to identify the table bounding box. Crop it. Ask Luna to transcribe *just the grid*.
*   Run your math closure proofs immediately on the JSON output. If it fails, send the crop back to Luna with the explicit error: *"Row 4 + Row 5 = 100, but you extracted Subtotal as 90. Re-read the image and correct the hallucination."*

**Phase 3: Demand-Driven Note Extraction (Minutes 12-25)**
*   Do not extract all notes. The Excel model defines the universe of what you need (e.g., segment breakdown, PPE breakdown). 
*   Look up those specific keywords in the extracted Notes Index.
*   Jump to those specific pages. Apply the same Grid-Repair Loop (extract, math-check, repair).

This restricts the heavy lifting to ~15-20 pages of the PDF, easily fitting your 30-minute budget while guaranteeing the data you actually need is canonicalized.

***

### 3. Completeness Proof Design: Are (a) + (b) sufficient?

They are necessary, but **not sufficient**. You are missing two critical structural proofs and one contextual proof.

**The Complete Proof Suite:**
*   **(a) Vertical Math Closure:** Subtotals tie.
*   **(b) Prior-Year Anchor:** Every open model row's prior year value is found (proves you haven't missed a line item).
*   **(c) Cross-Statement Articulation (New):** Net Income on the IS must identically match Net Income on the Cash Flow statement. Ending Cash on the CF must match Cash on the Balance Sheet. *This proves your extracted tables belong to the same reality and you didn't accidentally extract a Q3 table for one and Q4 for another.*
*   **(d) Entity/Column Binding (New - Critical for CN Reports):** Chinese reports famously put "Consolidated" and "Parent Company" columns side-by-side. Vertical math works for both. You must cryptographically tie the column data to the correct header, or you will update the model with Parent data.

**What CANNOT be proven deterministically?**
*   **Semantic Label Shifts:** If "Cloud Revenue" (Prior: 100) is renamed to "Intelligent Computing" (Prior: 100), math and anchors prove the *number* is correct, but deterministic code cannot prove the *concept* is identical.
*   **Missing Zero-Value Rows:** If a segment shuts down and is omitted from the table, vertical math still closes perfectly. The model row is left hanging.
*   **Honest Handling:** The extraction payload must include an `unmapped_priors` array and a `semantic_confidence` score for label changes. The mapping agent must be allowed to leave a row blank and flag it for human review if a prior anchor is missing and math closes without it.

***

### 4. Failure Modes of Extraction-First & Required Invariants

The primary danger of extraction-first is **Poisoning the Well**: creating a mathematically perfect but hallucinated dataset.

**Failure Mode 1: The "Forced-Math Hallucination"**
If Luna knows the subtotal must equal 100, and it extracts 40 and 50, it might hallucinate a missing "10" or change the 50 to a 60 just to make the math pass the prompt's requirements.
*   **The Invariant (The Regex Anchor):** The LLM is allowed to format numbers, but **every digit sequence in the final JSON must have a direct regex/substring match in the raw OCR/pdfplumber text of that page**. Luna cannot invent a number; it can only select them. 

**Failure Mode 2: Column Shearing (The offset error)**
Luna shifts all 2022 numbers into the 2023 column. The vertical math perfectly closes, so your proof passes, but the model is updated with last year's data.
*   **The Invariant:** Cross-column math validation. You must require Luna to extract the "YoY % Change" column if it exists in the print, and prove `(Current - Prior) / Prior = % Change`. If this passes, column shearing is mathematically impossible.

***

### 5. Is the offline benchmark gate sound?

**Yes. It is imperative.** Running live discoveries that cost an hour and burn the owner's trust is unsustainable. Building a benchmark gate is standard regression testing.

**Does it risk overfitting to document quirks?**
Only if you test *instances* instead of *capabilities*. 
*   *Bad test:* "Can the agent extract Tencent's 2022 Q4 segments?" (Overfits to Tencent).
*   *Good test:* "Capability: Merged Column Headers. Here are 15 isolated pages from 15 different companies where a single year spans two sub-columns. Extract them."

Create a **Capabilities Matrix** from your 25 historical failures (e.g., Parent/Consolidated split, re-based segment categories, negative numbers in parentheses, blurry scanned grid). Ensure your offline benchmark tests these specific capabilities across a diverse holdout set of documents. 

If the agent passes the benchmark, you deploy. If it encounters a new failure in the wild, you isolate the failure, add it to the Capabilities Matrix, and never fail on it again. This is how you stop patching and start engineering.

### Response C — x-ai/grok-4.6

**Yes — complete-extraction-first is the right cut.** Channel accumulation is not “convergent.” It is a second, implicit mapper: the live agent is reconciling *several incomplete worlds*. That is why every hole becomes a product feature.

The cut to lock is not “transcribe the whole PDF.” It is:

> **Build one closed, column-resolved FilingLedger that is *sufficient for this model*, prove sufficiency, then map only against that ledger.**

Analyst judgment belongs in *classification / restatement / lumping*. Evidence gathering is a contract, like “the books balance.” Hardcoding that contract is not a hardcoded workflow; it is the condition that makes an agentic mapper safe.

---

## 1. Verdict on the cut

**Keep:** one reading stage; channels become internal repair; mapping queries a store; live runs are not the lab.

**Reject:** “complete notes,” “no re-read after mapping starts,” and “drop the write guards because the ledger is complete.”

**The other fundamental issue *is* the mapper’s task shape.** “Think like an analyst and hunt” will always invent channel 9. After the ledger exists, the mapper’s job is:

- bind ledger rows → model rows
- apply only *ledger-justified* derivations (section residual = 0 ⇒ absent-as-zero; roll-forwards; minority/OCI bridges)
- emit residuals with search inventory
- **never** invent a number that is not a ledger cell or a cited derivation

If you invert extraction but leave the mapper as an open-world hunter, the patch spiral moves downstream.

---

## 2. Architecture of the one reading stage (~30 min)

One store, four phases, one clock. No parallel “evidence products.”

### Canonical object: `FilingLedger`

Every number the mapper may use is a cell:

- `entity` (consolidated vs parent — required)
- `statement_or_note`, `section`, `note_id`
- `unit`, `currency`, `scale` (元 / 千元 / 万元)
- `columns[]` with `{role: current|comparative|restated_comparative, year}`
- `rows[]` with `{label, cells, bbox, page, raw_text, status}`
- `proofs[]` and `gaps[]`

Statuses: `proven` | `derived` | `absent_proven` | `unproven` | `contradicted`.  
Mapper write tools accept only `proven` / `derived` / `absent_proven`.

### Phase A — Index (1–2 min, cheap)

Do **not** vision the book.

- Page catalog: digital text vs scan, header/footer, TOC / 目录, “合并资产负债表 / 利润表 / 现金流量表 / 股东权益”, note-number banners, auditor vs MD&A vs statements.
- Table-region proposals (layout / ruling lines / whitespace), not full transcription.
- Entity detector: 合并 vs 母公司. If both exist, **two ledgers**; default mapping entity is the model’s entity (almost always consolidated).
- Output: `PageIndex` + candidate statement pages (usually < 20) + notes TOC.

### Phase B — Spine: face statements to closure (10–15 min)

This is the run’s real product. Notes are secondary.

**Page selection:** only classified statement pages + immediate continuations. If a section does not close, *then* adjacent pages are in-scope. Never “maybe also page 87.”

**Per table, not per page.** Luna will mangle a full scanned CN sheet. Fixed reader loop:

1. Crop one table region.
2. Transcribe in **stripes** (8–15 body rows), headers and column roles repeated every stripe.
3. Emit a grid (JSON), not prose.
4. **Local proofs before accept:**
   - each printed subtotal equals sum of children (both columns)
   - comparative column identity-ties last year’s *accepted* current (or model prior) at the same label/section
   - scale vs a magnitude anchor (NP, equity, revenue) — reject 100× / 1000×
5. On fail: repair *inside the same table object* — higher zoom, column-isolated crop, digit-only pass, alternate splitter. Do not open a new channel.

**Two independent reads for headline families only** (sales, GP, NP, cash, CA/NCA/CL/NCL, equity, CFO/CFI/CFF). Accept on agreement; on disagreement, third cropped read. Everything else: one read + closure.

**Articulation gates (spine acceptance, not later flags):**

- BS balances both years
- IS articulates to NP
- CF articulates to cash (and cash ties BS)
- equity roll-forward ties BS equity

A spine that closes locally but fails articulation is **not** accepted. That is how you catch column swaps, 母公司/合并 mixups, and restated comparatives mislabeled as originally presented.

**Runtime control:** statement tables are few. Stripe vision + closure is the budget you spend first. If spine is not accepted by T=18 min, stop expanding notes and keep repairing spine. A pretty note extract on an unclosed BS is how you miss the hour.

### Phase C — Sufficiency set, then notes (8–12 min)

Notes are retrieved against an **open set**, not “relevant notes” as a vibe.

Open set =

- model rows still unbound after spine labels
- required breakdowns not on the face (segments, GP by cost/tax, cash composition, debt schedule, etc.)
- spine lines that cite a note number
- last-year ledger pointers: “this model row lived in note 6 / 分部 / 营业收入明细”

**Retrieval (deterministic, capped):**

- note-number pages from TOC + page banners
- label overlap (normalized CN tokens, not raw string)
- last-year page/note map
- hard cap: e.g. 30 note pages, priority queue. Unretrieved pages are listed on the gap, not silently skipped.

**Same reader as spine** for note *tables*. Narrative note lines become label sightings + pointers, not writeable amounts, unless they sit in a closed table or match a model prior at identity grade *and* the surrounding table closes.

Banned: machine writes from free-floating note prose. That is the junk-NP incident, encoded as an invariant, not a folklore rule.

### Phase D — Sufficiency proof, then freeze (2–4 min)

Freeze a ledger version. Mapping starts. The mapper may enqueue **at most N targeted re-reads** (say 5), each of which writes a new ledger version with a reason. No ad-hoc snippets that bypass the ledger.

---

## 3. Completeness proofs: (a)+(b) are necessary, not sufficient

**Require all of these before mapping:**

| ID | Claim | Deterministic? |
|----|--------|----------------|
| A | Every ingested **section** closes to its printed subtotal, both columns | Yes |
| A2 | Spine **articulates** (BS / IS→NP / CF→cash / equity roll) | Yes |
| B | Every still-open **model row prior** is located in the ledger **or** `absent_proven` with enumerated searched pages/regions | Yes (search is finite) |
| C | Every **required key family** has a home (face, closed note table, or explicit gap) | Yes given a key list |
| D | Column roles + years + entity + scale are bound on every accepted table | Yes against anchors |
| E | Headline keys dual-read agree | Yes |

**Cannot prove deterministically — treat honestly:**

- **Semantic identity** after rebase/reclass (segments, “other”, restated comparatives). You can prove a number exists and closes; you cannot prove it *means* last year’s row. Mapper + last-year map propose; human-flag if label overlap < threshold or category cardinality changed.
- **Lumped vs zero.** Residual 0 after a closed parent **does** prove absent-as-zero *inside that parent*. It does **not** prove the economic item is zero if it may live in “其他” or another note. Those stay `unproven` unless the note schedule is closed and named.
- **Note-set completeness.** You cannot prove “no other note mentions X” without reading every page. Record `search_inventory`. If the open row is a hard key, status = `unproven` (deliver, flagged), never a silent number.
- **Compensating OCR errors** that still sum. Dual-read headlines + prior-column identity + cross-statement articulation are the mitigation, not a proof.
- **Which table is authoritative** (face vs note vs MD&A vs 经营情况讨论). Rule: face > closed note schedule > nowhere. MD&A is never writeable.

**Honest run outcomes (only these):**

1. `accepted` — proven/derived cells, model writes cited
2. `accepted_with_gaps` — delivered; unbound rows flagged with inventory; **no unflagged invented fills**
3. `rejected_spine` — do not map; return the failed proofs (this is still “always deliver”: a structured failure beats a wrong model)

“Always deliver” means always a marked workbook **or** a spine-failure package. It does not mean “guess to hit 60 minutes.”

---

## 4. Extraction-first failure modes and the invariants that kill them

| Failure | Invariant |
|---------|-----------|
| Wrong-but-closed grid (column shift, 母公司 sheet, unit) | Articulation + entity field + scale-vs-anchor; reject table, don’t patch cells |
| Dual-year consistent misread | Comparative must identity-tie *last year’s accepted current*, not only close internally |
| Restated comparative extracted as originally presented | Restatement note / “经重述” header is a first-class column role; mismatch vs last year’s published current ⇒ `contradicted`, not overwrite |
| MD&A / junk note poisons NP | Write allowlist: spine + closed note tables only |
| Premature freeze, mapper starved | Bounded targeted re-read queue **into the same ledger** |
| Over-extract, mapper picks the pretty wrong number | Authority order + one cell per (entity, concept, year); duplicates ⇒ `contradicted` |
| Silent zeros | Zeros only via `absent_proven` from a closed parent residual |
| Ledger poison spreads | Immutable versions; guards stay on writes (citation + identity checksum). Extraction-first *feeds* guards; it does not replace them |

**Compensating-error residual:** accept that a non-headline line can be wrong-but-closed. Contain it: non-headlines cannot be written without either (parent closure + residual) or (prior identity + label match). That is how you stop “never a wrong unflagged number” from requiring perfect OCR.

---

## 5. Offline benchmark gate

**Sound as a *capability gate*, fatal as a *company-fit gate*.**

Build `bench/` as failure **classes**, each a (pdf slice, model stub, expected ledger proofs, expected binds/flags):

- digital vs scan, 万元 vs 元
- 合并 vs 母公司 adjacent
- restated comparatives
- segment rebase
- continuation tables / headerless page 2
- note-only breakdown
- closed parent with true zero child
- junk note number near NP
- CF articulation / restricted cash
- two-year column swap

**Dispatch rule:** a reader/mapper head ships only if the suite passes. A live miss may add a **class** (fixture + invariant). It may not add a channel.

**Anti-overfit (generic-agent requirement):**

- ≥1 holdout issuer never used in prompts or repair heuristics
- no DFE-specific labels in the reader; company-specific knowledge lives in the *model*, not the extractor
- score the **proofs** (closure, articulation, absence inventories), not only “matches last human mark”
- if you only have one issuer today, add public CN 年报 scans as extraction-only fixtures (no need for their Excel models)

Live runs stop being discovery. The suite becomes the only place new pathology is legalized.

---

## What to build once (and stop)

```
PageIndex
    → Statement tables (stripe vision + closure + articulation)
    → FilingLedger v1
    → OpenSet = (model rows ∪ required keys) \ ledger
    → Note retrieve ≤ cap
    → Note tables (same reader)
    → Sufficiency proof → Ledger vN freeze
    → Mapper (binds + cited derivations + flags)
    → Write guards (unchanged)
```

Delete the eight channels as *products*. Keep their *algorithms* as repair tactics inside the table loop (grid, vision stripe, prior-anchor reread, section residual, last-year note pointer).

**Owner-facing contract, one sentence:**  
*We do not mark against a PDF. We mark against a ledger that has closed and articulated; anything we cannot prove is a flag, not a number.*

That is the fundamental cut. Mapping intelligence stays; evidence stops being a hunt.


## Stage 2 — peer reviews

### Review by openai/gpt-5.6-terra

## Response A

### What it does well

Response A correctly identifies the core architectural issue: the problem is not that the individual extraction methods are inherently bad, but that they have become **peer evidence channels** with inconsistent semantics and no unified coverage contract. Its reframing to a “coverage-first canonical evidence” layer is strong and directly addresses the patch spiral.

Particularly good elements include:

- **Refines “complete extraction” appropriately.** It warns against literally transcribing every page of a 300-page report and instead proposes “complete, column-resolved, provenance-preserving extraction of the disclosure universe relevant to the model.” This is an important practical distinction.
- **Separates extraction from mapping cleanly.** The distinction between:
  - evidence compilation: facts, geometry, headers, scope, periods, units, provenance; and
  - semantic mapping: selecting/deriving model values from those facts  
  is exactly the right decomposition for a weak model.
- **Treats the canonical layer as typed facts rather than text snippets.** The proposed fact schema includes concept, scope, period, units, column role, page/bounding box, source crop, extraction methods, and verification state. That is much more buildable and auditable than an unstructured “evidence pool.”
- **Provides a strong manifest and coverage-planning concept.** The report manifest, workbook demand graph, note-selection mechanisms, and coverage-expansion rules are all sensible.
- **Correctly avoids a blanket ban on notes.** Its source-tier approach is better than a hard prohibition. Many essential model values genuinely reside only in notes.
- **Recognizes that closure is insufficient by itself.** It explicitly notes that internally closed tables can still have swapped rows, wrong scope, wrong columns, wrong units, or incorrect economic meaning.
- **Provides useful targeted repair taxonomy.** The table matching failure types to repair actions is concrete and operationally useful.
- **Addresses runtime with prioritization.** It proposes manifest first, statements first, targeted notes next, repair and mapping last. This is directionally correct.

### What it does poorly

The most serious issue is that Response A is **incomplete**. It ends during its proposed completeness obligations, before it fully answers questions 3–5. Therefore it does not deliver a fully usable council answer despite a strong start.

Other weaknesses:

- **Too broad and somewhat over-engineered.** It introduces a large number of artifacts—manifest, graph, planner, fact store, validation graph, gap register, page evidence packets, multiple extraction methods, extensive metadata—without sharply distinguishing the minimum viable architecture from the ideal end-state. For a system constrained to 30 minutes and a weak engine, the answer would benefit from a smaller “build this first” implementation plan.
- **Does not sufficiently define acceptance states.** It talks about verified facts and gaps, but does not clearly specify whether a live run may produce:
  - a fully accepted marked workbook,
  - a marked workbook with explicit unresolved rows,
  - or a failed/no-write delivery package.  
  This matters because the stated requirements “always deliver” and “never a wrong unflagged number” are in tension.
- **Does not put enough emphasis on immutable versions and conflict handling.** A canonical store needs explicit behavior for duplicate facts, contradictory facts, restated comparatives, and alternate authorities. Response A mentions some of these but does not define a crisp conflict policy such as “duplicates become contradictions until resolved.”
- **Its runtime plan assumes parallelism without adequately qualifying operational requirements.** It says the 30-minute target assumes parallel workers/pages, but it does not translate that into a concrete concurrency and time-budget design.
- **The answer is more descriptive than decisive on hard trade-offs.** For example, it correctly says not to extract all notes, but it does not give a hard cap, escalation rule, or stopping rule for note retrieval.
- **The benchmark discussion is absent due to truncation.** That is a major omission because question 5 explicitly asks about overfitting and generic-agent requirements.

Overall, Response A contains many excellent design components, but it is incomplete and insufficiently distilled into a crisp operational contract.

---

## Response B

### What it does well

Response B is concise, clear, and generally aligned with the correct architectural direction.

Strong points include:

- **Correctly endorses extraction-first.** It recognizes that the system is conflating data gathering and mapping, and that a canonical verified representation makes failures diagnosable as extraction failures versus mapping failures.
- **Offers a practical demand-driven funnel.** The three-phase plan—orientation, core statements, then demand-driven notes—is a reasonable way to fit the process into a 30-minute budget.
- **Correctly advises table-region crops rather than full-page reading.** For a weak vision-capable engine reading scanned Chinese tables, crop-based grid extraction and repair is more reliable than whole-page transcription.
- **Adds useful proof obligations beyond subtotal closure.** Cross-statement articulation and entity/column binding are essential additions. The warning that Chinese reports can contain consolidated and parent-company statements with equally valid arithmetic is particularly important.
- **Identifies unprovable semantic issues.** It correctly notes that renames/reclassifications and missing zero-value categories cannot be established merely through deterministic closure checks.
- **Makes a good benchmark distinction.** Testing capability classes rather than specific companies/documents is the right anti-overfitting framing.

### What it does poorly

Response B is materially weaker than the other two because it is too simplified and contains a few dangerous technical recommendations.

Most importantly:

- **The “every digit sequence must directly match raw OCR/pdf text” invariant is unsound.** OCR is precisely one of the unreliable components in scanned Chinese reports. A correct value may fail to appear correctly in the raw OCR text, while an incorrect OCR sequence may appear. Direct regex matching is not a reliable proof of visual truth. The relevant provenance should be the source image crop plus an auditable transcription/verification process, not a raw-OCR substring requirement.
- **The YoY-column invariant is not generally applicable.** Many audited financial statement tables do not print YoY percentage columns. Even where a percentage exists, it may be calculated with a different denominator, affected by restatements, or rounded. It cannot be a universal required check for preventing column shearing.
- **It under-specifies the canonical data model.** It says “verified JSON representation,” but does not explain the fields required to prevent the most dangerous mistakes: authority tier, scope, column role, restatement state, page/bounding-box provenance, row/table hierarchy, unit/scale, and contradiction status.
- **It does not adequately address notes as authoritative sources.** It advises demand-driven note extraction, but it does not define when a note may safely write to the model versus merely corroborate a statement.
- **It does not fully address “always deliver” versus “never wrong unflagged.”** It says rows can be blank and flagged, but does not propose a formal run-state contract or a delivery policy for a failed core statement extraction.
- **It understates the difficulty of “guaranteeing” canonicalization from 15–20 pages.** Many models need a nontrivial set of note pages, especially for segments, gross-profit detail, debt, tax, PPE, working capital, or cash-flow detail. The answer should frame the 15–20-page target as a typical budget, not a guarantee.
- **It does not clearly preserve the existing guarded-write architecture.** It implies ETL separation, but does not explicitly state that extraction-first should feed—not replace—citation, checksum, and identity guards.
- **The benchmark advice is good but too generic.** It lacks split design, hidden holdouts, regression rules, and the principle that new production failures should become generalized pathology classes rather than issuer-specific special cases.

Response B is useful as a high-level recommendation, but not sufficiently rigorous to be the architecture that “can be built once and stop patching.”

---

## Response C

### What it does well

Response C is the strongest response because it turns the right conceptual answer into a concrete operating design with explicit artifacts, invariants, failure states, and stopping rules.

Its central formulation is excellent:

> Build one closed, column-resolved FilingLedger sufficient for the model, prove sufficiency, then map only against that ledger.

That captures the necessary correction to “complete-extraction-first”: completeness must be defined relative to a **coverage contract**, not as indiscriminate full-PDF transcription.

Specific strengths:

- **Correct diagnosis of the patch spiral.** It explains that multiple channels have become “a second, implicit mapper,” leaving the live agent to reconcile incomplete evidence worlds. That is a sharp explanation of why each miss becomes another channel.
- **Retains useful existing work while changing its role.** It does not propose throwing away table islands, vision recovery, priors, closure, or last-year maps. Instead, it demotes them from independent products to repair mechanisms inside the one reading stage. That is precisely the right organizational cut.
- **Defines a practical canonical object.** The `FilingLedger` structure is concrete: entity, statement/note, section, note ID, units/currency/scale, column roles, row cells, bounding boxes, page, raw text, proofs, and gaps.
- **Defines explicit statuses.** `proven`, `derived`, `absent_proven`, `unproven`, and `contradicted` are useful operational states. Restricting write tools to proven/derived/absent-proven states creates a clear safety boundary.
- **Provides a realistic staged runtime plan.** The four phases—index, statement spine, open-set notes, sufficiency proof/freeze—are clear, ordered, and time-aware.
- **Prioritizes the financial-statement spine correctly.** The answer explicitly says not to spend time on notes while the balance sheet is unclosed. This is an important operational priority rule.
- **Uses table/stripe-level reading rather than vague page reading.** Cropping table regions, extracting in row stripes, repeating headers, and applying local proofs is a more reliable design for scanned Chinese tables than general whole-page LLM transcription.
- **Uses stronger validation than (a)+(b).** It adds:
  - statement articulation;
  - required-key-family coverage;
  - column role/year/entity/scale binding;
  - dual-read agreement for headline rows.  
  These are meaningful additions.
- **Is honest about what cannot be deterministically proven.** It clearly distinguishes deterministic evidence sufficiency from semantic identity. It correctly calls out segment rebasing, lumped-versus-zero interpretation, note-set completeness, and compensating OCR errors.
- **Handles “always deliver” correctly.** Its three run outcomes—accepted, accepted with gaps, rejected spine—are a strong answer to the owner’s constraints. “Always deliver” means always provide a marked result or structured failure package, not fabricate a completed model.
- **Provides a robust failure-mode table.** The invariants are generally sensible: articulation, entity field, scale anchor, column-role handling for restatements, authority ordering, immutable ledger versions, no silent zeros, and retained write guards.
- **Has the best benchmark design.** The distinction between capability gate and company-fit gate is exactly right. The proposed benchmark fixtures, holdout issuers, proof-based scoring, and rule that new live failures may add a class but not a new production channel are all strong.

### What it does poorly

Despite being the best response, Response C has some areas that need refinement.

- **It is slightly too prescriptive in a few implementation details.** For example, “stripes of 8–15 rows,” “at most N targeted re-reads,” and “cap 30 note pages” are useful defaults but should be presented as tunable policy parameters based on latency and report complexity, not universal truths.
- **The statement “narrative note lines become label sightings + pointers, not writeable amounts” may be too restrictive.** Some audited note disclosures are presented as text or semi-structured prose and can be authoritative. The correct rule is not “table only,” but rather “audited source with resolved scope, period, unit, and bounded textual provenance; machine write eligibility depends on source type and validation.” Free-floating narrative should be restricted, but a blanket table bias can miss legitimate disclosures.
- **“Comparative must identity-tie last year’s accepted current” requires restatement-aware nuance.** The answer does mention restated comparatives elsewhere, but the local proof should explicitly allow expected divergence when the current report says comparative amounts have been restated/reclassified. Otherwise it risks falsely rejecting valid reports.
- **The concept-to-model mapping layer could be more fully specified.** It says the mapper binds ledger rows to model rows and performs ledger-justified derivations, but it could better describe:
  - mapping confidence;
  - authority precedence between statement and note facts;
  - one-to-many and many-to-one mappings;
  - taxonomy-change handling;
  - explicit human-review thresholds.
- **The claim that non-headline lines can be safely contained with parent closure plus residual or prior identity plus label match may still be optimistic.** A wrong row can satisfy both in rare cases, especially if taxonomy is changed or OCR errors are compensating. The answer acknowledges compensating errors, but the write policy could be stricter for rows that materially affect model outputs.
- **It could distinguish extraction confidence from semantic confidence more explicitly.** A row can be perfectly transcribed but ambiguously mapped; conversely, a concept may be clear but the OCR uncertain. Separate fields would improve routing and review decisions.
- **It does not fully explain how the “generic-agent” requirement interacts with reusable ontology.** It properly avoids DFE-specific labels, but a production system will still need a generic financial disclosure ontology and multilingual synonym system. That is not bad hardcoding; it is a reusable domain schema. Making that distinction explicit would strengthen the answer.

These are refinements rather than foundational problems. Response C is the most complete and directly buildable answer.

FINAL RANKING:
1. Response C
2. Response A
3. Response B

### Review by google/gemini-3.1-pro-preview

An evaluation of the models' responses based on the specific constraints of the prompt (gpt-5.6-luna weak engine, 30-60 min runtime, 100% correct-or-flagged requirement, Chinese scanned annual reports):

### Response A
**What it does well:** 
Response A provides a great conceptual reframing of the problem. Distinguishing between a "literal complete transcription" and a "canonical, coverage-proven evidence world" is the exact right mindset. Its breakdown of the reading stage into specific products (manifest, coverage plan, fact store, validation graph, gap register) is clean. It also correctly identifies the need to find the "authoritative" set of financials, which is a notorious issue in Chinese annual reports.

**What it does poorly:** 
The response fails because it completely cuts off in the middle of answering Question 3. It leaves the completeness proofs hanging and completely ignores Question 4 (failure modes/invariants) and Question 5 (offline benchmark gate). 

### Response B
**What it does well:** 
Response B is highly structured, punchy, and practical. It correctly identifies the architectural shift as moving to a classic ETL (Extract, Transform, Load) pipeline. To handle the 30-minute budget with a weak model, it proposes a "Demand-Driven Funnel," which is a highly effective way to limit compute. It correctly identifies the critical Chinese reporting quirk of "Consolidated" and "Parent Company" columns sitting side-by-side. Furthermore, its proposed invariants to prevent failure modes are brilliant: the "Regex Anchor" (forcing the LLM's JSON digits to substring-match the raw OCR) directly prevents the forced-math hallucinations that weak models often generate. 

**What it does poorly:** 
Its reliance on a keyword search against the Notes Index (Phase 3) might be slightly brittle. If the Excel model asks for a specific breakdown, the exact keyword might not perfectly align with the document's localized index phrasing, potentially leading to missed notes.

### Response C
**What it does well:** 
Response C is a masterclass in system design tailored to a highly specific, constrained domain. It reads like it was written by a senior architect who has built this exact system. 
- It perfectly addresses the weak `gpt-5.6-luna` engine constraint by introducing "stripe vision" (chunking tables into 8-15 row bands), which is exactly how you stop weak vision models from hallucinating large scanned grids. 
- It introduces "Articulation gates" (BS balancing, IS tying to NP, CF tying to cash) as an absolute spine-acceptance criteria, which is the gold standard for financial data integrity.
- It exhibits deep knowledge of Chinese financial statements (`合并` vs `母公司`, `万元` vs `元`). 
- It directly integrates the user's specific past failures (the "junk NP" incident) into concrete invariants (allowlists for where numbers can be pulled from).
- It answers all five questions with exceptional depth, providing a blueprint that can be immediately built.

**What it does poorly:** 
There are no notable flaws in this response. It is an outstanding technical answer that balances accounting realities with LLM architectural constraints.

FINAL RANKING:
1. Response C
2. Response B
3. Response A

### Review by x-ai/grok-4.6

## Response A

**What it does well.** The strongest conceptual move in A is the refinement from “transcribe the whole report” to a *coverage-proven, typed evidence world*. That is the right correction: completeness is a contract over the model’s demand graph, not a page-count. The split between evidence compilation and accounting-semantic mapping is also right, and it names the real secondary bug: Luna is being asked to do OCR, retrieval, concept mapping, and workbook mutation in one loop. The proposed fact schema (scope, column role, unit, bbox, verification links) and the authority-tier treatment of notes are more careful than a blunt “ban notes” rule. The diagnosis of the patch spiral—peer channels with different semantics, no single answer to “what was searched / what is complete”—is accurate.

**What it does poorly.** The response is unfinished. It dies mid-list in Q3 and never answers Q4 (poisoning / invariants) or Q5 (benchmark overfitting) at all. Against a brief whose success criterion is “a design we can build once,” that is fatal: there is no freeze/version story, no honest delivery states, no failure-mode table, no dispatch rule. Even the finished parts lean essay-architecture (manifest → planner → graph) more than a single object and a stop rule. Coverage-expansion “routes” risk becoming Channel 9–16 under a nicer name. Runtime is a Gantt sketch, not a spine-first budget with a hard halt. High conceptual quality; not a closable build spec.

## Response B

**What it does well.** B answers all five questions and is easy to act on. The ETL cut (extract/verify a canonical JSON, then map only against it) is the right inversion, and “if missing, is it extract or map?” is the debug split the current system lacks. The demand-driven funnel (orient → face statements → only notes the model actually needs) is the only sketch that is obviously compatible with ~30 minutes. Completeness extras are the right ones: cross-statement articulation and CN parent/consolidated column binding. The benchmark advice is the best of the three on anti-overfit: test *capabilities* (merged headers, parent/consol, parentheses negatives), not “Tencent 2022 Q4,” and promote wild failures into a matrix rather than a new live channel.

**What it does poorly.** Several “invariants” are weaker than they sound. A regex/substring match against raw OCR/pdfplumber is a bad primary lock on *scanned* CN tables—the existing failure mode is that the text layer is exactly what is missing or wrong; it also forbids legitimate vision-only recoveries. “Cryptographically tie” columns is rhetoric, not a design. The reader is underspecified for Luna: one crop + “re-read because 4+5≠100” invites the forced-math hallucination B itself warns about, and there is no stripe/grid protocol, dual-read of headlines, scale/entity anchors, or ledger versioning. Notes policy, restatements, silent zeros, and “always deliver vs guess” are thin. Write guards are not explicitly retained. Buildable, but still a sketch that would grow patches.

## Response C

**What it does well.** C is the only response that is both the right cut *and* a spec you could implement without inventing the missing half. The locked object is a `FilingLedger` of cells with statuses (`proven` / `derived` / `absent_proven` / `unproven` / `contradicted`) and a mapper that may write only the first three—that single rule kills both the hunt and silent fills. Phases are ordered by what must not fail: cheap index → spine tables to *articulation* (not just local subtotals) → open-set note retrieval with a hard cap and search inventory → freeze + bounded re-reads into the same store. Stripe transcription, dual-read only on headline families, scale-vs-anchor, entity as a required field, restated comparatives as a first-class column role, and “face > closed note table > nowhere” are concrete Luna/CN tactics, not another channel. Failure modes are paired with invariants (including keeping write guards: extraction *feeds* guards, does not replace them). Honest outcomes (`accepted` / `accepted_with_gaps` / `rejected_spine`) reconcile “always deliver” with “never a wrong unflagged number.” The benchmark is a *capability* suite; live misses add a fixture + invariant, never a product channel. The closer—“we mark against a ledger that has closed and articulated”—is the owner-facing contract.

**What it does poorly.** A 30-page note cap and “at most 5 re-reads” are reasonable but arbitrary; they need a priority rule tied to key-family criticality, not just a number. Dual-read is underspecified (two methods vs two samples). Compensating OCR that still closes is acknowledged rather than fully contained for non-headlines. Parallelism is implicit. These are calibration gaps inside a complete design, not holes in the cut.

---

FINAL RANKING:
1. Response C
2. Response B
3. Response A


## Ranking tally (Borda)

- Response C (x-ai/grok-4.6): 9 pts
- Response B (google/gemini-3.1-pro-preview): 5 pts
- Response A (openai/gpt-5.6-terra): 4 pts

## Stage 3 — chairman synthesis (google/gemini-3.1-pro-preview)

As Chairman of the Council, I have reviewed the assessments from our constituent AI models. The consensus is absolute: **Yes, "complete-extraction-first" is the exact correct fundamental cut.** 

Your current architecture suffers from conflating **evidence gathering** with **mapping logic**. Every time the mapper fails to find a number, it treats it as a search problem and opens a new channel. You have built a system that attempts to reconcile multiple incomplete worlds at runtime. 

To stop the patch spiral, you must transition from a "hunter-gatherer" agent to a strict ETL (Extract, Transform, Load) pipeline. The extraction stage must produce a single, canonical, mathematically sound object—a **FilingLedger**—and the mapping agent must be restricted to querying only that ledger.

Here is the finalized blueprint for the architecture you can build once and stop patching.

---

### 1. The Fundamental Cut & Task Shape
The fundamental cut is right, but we must refine the definition of "complete." Do not attempt to transcribe all 300 pages of an annual report. Completeness is a contract over the model's demand graph, not a page count.

The new architecture operates on a unified `FilingLedger` comprised of typed, proven cells:
*   **Attributes:** Entity (Consolidated vs. Parent), concept, unit/scale (`万元` vs `元`), column role (Current, Prior, Restated), bounding box, source text, and status.
*   **Statuses:** `proven`, `derived`, `absent_proven`, `unproven`, `contradicted`.

The mapping agent’s task shape completely changes. It no longer "hunts." Its sole job is to:
1. Bind model rows to `FilingLedger` cells.
2. Apply only *ledger-justified* derivations (e.g., section residual = 0).
3. If a number is not in the ledger with a `proven` or `derived` status, it **cannot be written**. It is flagged for human review.

### 2. Architecture for the Reading Stage (~30 min limit)
To overcome the constraints of a weak vision engine (`luna`) and scanned Chinese reports, you cannot process whole pages or brute-force the entire document. Use a bounded, four-phase clock:

**Phase A: Index & Manifest (Minutes 0-3)**
*   Perform a cheap, deterministic pass to map the document: find the TOC, core statement pages (usually 4-10 pages), note index, and note-number banners.
*   **Critical:** Detect Entity (`合并` vs `母公司`). If both exist side-by-side, explicitly prepare to bind columns to the correct entity to avoid poisoning the consolidated model with parent data.

**Phase B: The Statement Spine (Minutes 3-18)**
*   Process *only* the classified core statements and immediate continuations.
*   **The "Stripe Vision" Loop:** Luna will mangle a full scanned sheet. Crop the table region and ask Luna to transcribe it in **stripes** (8-15 body rows at a time), repeating column headers for each stripe. 
*   **Local Repair:** If a stripe fails local math closure, repair *inside that stripe* (higher zoom, alternate OCR, digit-only pass) before moving on. Do not open a new extraction channel.
*   *Rule: Do not move to Phase C if the balance sheet is unclosed. A pretty note extract on an unclosed BS is how you miss the runtime target.*

**Phase C: Demand-Driven Notes (Minutes 18-26)**
*   Retrieve notes against an **open set**, not randomly. Pull only what is still required by the Excel model (e.g., segment breakdowns, required keys not on the face statements, or lines explicitly pointing to a note number).
*   Apply a hard cap (e.g., 20 priority note pages). Unretrieved pages are listed in a "gap inventory," not silently skipped. Apply the same Stripe Vision reader to note tables.

**Phase D: Sufficiency Proof & Freeze (Minutes 26-30)**
*   Execute global proofs (see below). Freeze the `FilingLedger` as an immutable version. The mapping agent begins work.

### 3. Completeness Proofs: Beyond (a) + (b)
Your proposed proofs—(a) sections close to subtotals and (b) priors are located/proven absent—are necessary but **not sufficient**. An internally closed table can still have swapped years, shifted columns, or represent the wrong entity. 

You must enforce the following absolute gates before the ledger is accepted:

*   **Cross-Statement Articulation (The Spine Gate):** The Balance Sheet must balance for both years. Income Statement net profit *must* tie to the Cash Flow starting net profit. Cash Flow ending cash *must* tie to the Balance Sheet cash. *This proves your extracted columns belong to the same reality and prevents column-swapping or restatement-mixing.*
*   **Entity/Column Binding:** Every accepted column must be deterministically bound to `合并` (Consolidated) or `母公司` (Parent), and its scale (`元` vs `万元`) anchored against a known magnitude.
*   **Dual-Read for Headlines:** For critical key families (Sales, GP, NP, Cash, Equity), run two independent read passes. Accept only on agreement.

**What cannot be proven deterministically?**
*   **Semantic Reclassification:** If a segment was rebased, the math will close, but deterministic code cannot prove the *economic concept* is identical to last year. 
*   **Honest Handling:** The run must output explicit statuses. "Always deliver" means delivering a completed model **OR** a `rejected_spine` failure package. It does not mean "guess to hit 60 minutes." If an item cannot be proven, the status is `unproven`, the cell is left blank, and it is flagged with a search inventory.

### 4. Failure Modes & Invariants
The primary danger of an extraction-first architecture is a mathematically perfect but hallucinated/sheared dataset poisoning everything downstream. 

*   **Failure Mode 1: The Forced-Math Hallucination.** Luna realizes 40 + X = 100 and hallucinates a 60.
    *   *Invariant:* Dual-read headline families. For non-headlines, ensure every ledger cell retains its source crop and bbox. Furthermore, **keep your existing write guards** (citations and identity checksums). Extraction-first *feeds* the guards; it does not replace them.
*   **Failure Mode 2: The Restatement Shearing.** The company restated 2022's numbers in the 2023 report. Luna reads them as current.
    *   *Invariant:* Restatement notes / "经重述" headers are treated as a first-class column role. If the comparative does not identically tie to the model's prior (due to restatement), it is flagged `contradicted` rather than silently overwriting the model's history.
*   **Failure Mode 3: Junk Note Poisoning.** 
    *   *Invariant:* Strict authority ordering. Primary face statements > Closed note schedules > Free-floating text. Unstructured MD&A narrative is never writeable for core financial integers.

### 5. The Offline Benchmark Gate
**Your offline benchmark gate is sound as a *capability gate*, but dangerous if used as a *company-fit gate*.**

To ensure you are building a generic agent (and not just overfitting to DFE's quirks), your benchmark suite must test **pathology classes**, not specific companies. 
*   *Bad test:* "Extract Tencent 2022 Q4."
*   *Good test:* "Capability: Restated Comparatives. Capability: Merged Column Headers. Capability: Parent/Consolidated Adjacent Columns."

Set a strict dispatch rule: A new agent head is deployed only if the capability suite passes completely. If a live run fails in production, you do not add a new "bolt-on channel." You isolate the failure, add it as a new capability class to the benchmark suite, write an invariant for it in the reader loop, and clear the benchmark.

### Summary Contract
Delete your 8 channels as independent products, but keep their logic as internal repair tactics during Phase B and C. 

Adopt this single contract with your owner:
*"We no longer hunt through PDFs. We extract a ledger, prove it closes, prove it articulates across statements, and bind the model only to that ledger. Anything we cannot prove is flagged, never invented."*
