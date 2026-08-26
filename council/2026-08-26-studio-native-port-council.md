# LLM Council transcript

## Question

# Question: porting a proven model-update engine to Copilot Studio native (Office Scripts + agent flows)

## Context

We have a production agent that marks equity-research Excel valuation models to
actual results from PDF disclosures and rolls them forward. Current
architecture, proven over ~100 calibration runs (DFE 85%+ key accuracy, CLP
balanced with locked analyst rulings):

- **Python engine (~15k lines)** — deterministic laws: complete PDF reading
  (pdfplumber text + vision fallback, position-true grids, completeness checks
  tied to known prior-year values), restatement scan, mark-to-actual recipe
  (copy prior actual column's formulas+formats, overwrite inputs only),
  back-outs as formulas with orange flags, roll-forward with per-panel column
  translation (interim H1=Q1+Q2 panels roll within their own panel), balance
  Police (delivery refused if BS doesn't balance / cash doesn't tie / formulas
  clobbered), _REPORT tab, decision ledger (analyst rulings replay
  deterministically), k=2 second opinion on first-round judgments.
- **LLM (gpt-5.6-luna)** answers ~50 bounded judgment questions per run
  (mapping/definition/adjustment calls); code referees every answer by
  arithmetic ties (a mapping is accepted because it RECONCILES, not because
  the label matched).

## The forced move

The analyst's company allows ONLY Copilot Studio (Personal Productivity
environment) + SharePoint + Excel Online. No Python anywhere, no GitHub, no
Azure, no external APIs, no third-party connectors. Verified available:

- **Office Scripts** ("Run script" action on Excel Online (Business)): real
  TypeScript against the workbook — read/write values, formulas, formats,
  colors. Constraints: single self-contained file (NO imports/modules), ~120s
  per execution when flow-invoked (chainable — a flow can call scripts
  repeatedly), JSON string in/out parameters with payload caps (~5MB),
  fetch/external calls blocked when invoked from flows. Excel Online's real
  recalc engine is available (an upgrade over our openpyxl evaluator).
- **Agent node in flows** (Microsoft renamed "AI Builder prompt" → "Agent"):
  built-in GPT-5.6 Reasoning callable as a flow step, can take instructions +
  file/knowledge inputs. Copilot chat demonstrably OCRs scanned PDFs.
- Flow control: Loop, If/Else, Human review (approval) nodes, SharePoint
  file triggers/actions, Classify node.
- NOT available: AI Builder OCR as a standalone action, connected agents,
  any code outside Office Scripts.

## Design so far (challenge it)

Port the deterministic laws to TypeScript: a shared pure-logic core
(axis discovery, tie checks, mark-to-actual planner, panel translation,
balance checks) concatenated into 4-6 self-contained scripts
(snapshot / write_actuals / check_balance / report), each JSON-in/JSON-out,
tested locally in Node against fixture workbooks before paste-in. Flows
orchestrate: SharePoint trigger → Agent extracts staging tables from the PDF
→ snapshot script reads model anatomy → Agent maps staging→model rows
(cascade: direct label / triangulate on prior-year value / back-out rule /
estimate+flag) → write script ENFORCES ties before accepting any write
(refuses non-reconciling entries → red flag) → balance script → report
script. Analyst rulings via Human review nodes, persisted in a hidden _SPEC
sheet. Phases: 1) end-to-end plumbing on key lines, 2) full statements +
restatement + true-up, 3) roll-forward + report + ledger parity.

## Questions for the council

1. What breaks first in this decomposition at real scale (300-page PDF,
   ~1,000 written cells, 10-sheet workbook) — payload caps, script timeouts,
   flow quotas, Agent-node context limits — and what's the mitigation?
2. Is the script split (snapshot/write/check/report) the right cut, or is
   there a better decomposition (per-sheet? per-law? one mega-script called
   with a mode parameter)?
3. PDF reading without our pipeline: how to structure Agent-node extraction
   so completeness is provable (we can no longer walk pages in code)?
   Chunking strategy, page budgets, and how to detect "the Agent skipped a
   table" using only tie-checks and known prior-year values?
4. The mark-to-actual recipe requires copying the prior column's formulas AND
   formats cell-by-cell, then overwriting inputs — is Office Scripts
   getCellProperties/setCellProperties viable for whole-column recipe copy
   within 120s, and what's the fallback if a sheet is too big?
5. Where does this architecture silently lose determinism, and what's the
   cheapest ledger design inside a hidden sheet that survives concurrent
   flow runs?
6. What should Phase 1 explicitly NOT attempt (so the first paste-in kit is
   assemblable by a non-technical intern in under an hour)?


## Stage 1 — answers

### Response A — openai/gpt-5.6-terra

The proposed direction is viable, but the main risk is not TypeScript translation. It is losing the current system’s **controlled evidence acquisition and transactional discipline** once PDF reading and orchestration become Agent/Flow driven.

The right target is a fail-closed, batch-oriented system in which the Agent proposes evidence and mappings, while Office Scripts own all model state changes and acceptance decisions.

## 1. What breaks first at real scale

### A. Payload size will break before 1,000 writes do

A thousand write instructions are small if represented compactly:

```json
{
  "runId": "2025-02-15-ABC-Q4",
  "sheet": "Model",
  "writes": [
    {
      "address": "H125",
      "value": 123.4,
      "sourcePage": 87,
      "sourceLabel": "Revenue",
      "mappingId": "REV_TOTAL",
      "evidenceId": "E-087-014"
    }
  ]
}
```

But a workbook anatomy snapshot containing every formula, format, used cell, row label, and column header across ten sheets can easily exceed a practical JSON payload limit. Formula strings and format objects are particularly expensive.

**Mitigation: return indexes and fingerprints, not workbook dumps.**

The snapshot script should return only information needed for planning:

- sheet name and used range dimensions;
- relevant panel boundaries;
- header rows and period-axis definitions;
- normalized row labels and row IDs;
- named ranges / key anchors;
- prior actual column addresses;
- hashes/fingerprints of protected formula regions;
- balance check locations;
- model/template version signature;
- a compact list of writable input cells or writable row intervals.

Do not send full formulas or formats to the flow unless a specific exception needs them.

Persist larger operational state in the workbook itself, ideally in `_SPEC` tables, not in flow variables.

---

### B. Office Script timeouts will break on chatty Excel API usage

The likely 120-second issue is not copying 1,000 cells. It is doing any of these:

- `getCell()` / `getRange()` calls inside loops;
- cell-by-cell format reads/writes;
- reading full worksheet grids;
- recalculating after every write;
- scanning formulas one cell at a time;
- writing `_SPEC` one row at a time.

**Mitigation: work in rectangular blocks.**

A script should generally:

1. Read each relevant used range once.
2. Build in-memory indexes in TypeScript.
3. Calculate planned changes in memory.
4. Write contiguous ranges in batches.
5. Recalculate once.
6. Read only the check cells and protected-region fingerprints needed for audit.

For example, avoid 1,000 flow calls or 1,000 `setValue()` calls. Instead, group writes by:

- worksheet;
- target column;
- contiguous row interval;
- semantic panel.

A practical batch might be 50–250 changes, depending on workbook complexity and formula recalculation cost.

For a workbook with expensive formulas, consider:

- setting calculation mode to manual during the write phase;
- applying all planned writes;
- restoring automatic calculation;
- invoking a controlled full recalculation;
- running checks in a subsequent script invocation if necessary.

Test this carefully: calculation mode must always be restored, including on error paths.

---

### C. Flow orchestration will break if it becomes “one action per fact”

A loop of 1,000 Agent calls, approvals, or Office Script executions is the wrong architecture. It will be slow, fragile, quota-sensitive, hard to retry, and nearly impossible to audit.

**Use coarse flow steps and fine-grained script batches.**

A reasonable run shape is closer to:

1. Create run record and acquire model lock.
2. Snapshot/preflight script.
3. PDF inventory/extraction passes.
4. One Agent mapping pass per financial-statement section or evidence package.
5. One Human review gate for unresolved/high-risk items.
6. One or several write batches by sheet/panel.
7. One audit/reconciliation script.
8. One report/ledger finalization script.

The flow should coordinate phases. It should not be the cell-level execution engine.

---

### D. Agent context and PDF grounding are likely the most serious operational limitation

A 300-page PDF is not safely equivalent to “a 300-page input to an LLM.” Even if the Agent can OCR and answer questions about the document, that does not prove:

- every page was inspected;
- every table was seen;
- page numbering was interpreted correctly;
- footnotes and restatement notes were captured;
- a long table was not silently truncated;
- the response covers every relevant disclosure.

A model can be excellent at extracting a requested table and still miss that the same table has a continuation page, a revised comparative, or a note-specific definition.

Treat Agent PDF extraction as **evidence proposal**, not complete document ingestion.

---

## 2. Better decomposition than `snapshot / write / check / report`

Your split is directionally right, but I would use transactional boundaries rather than purely functional names.

A good Office Script set is usually five scripts.

### Script 1: `preflightSnapshot`

Purpose:

- verify expected workbook/template identity;
- discover axes, period columns, panels, row IDs, and protected regions;
- identify prior actual and target actual columns;
- calculate a compact model fingerprint;
- verify the workbook is in a writable and expected state;
- produce the run plan skeleton.

Output should be compact and deterministic.

It should fail if:

- expected sheets are missing;
- headers have changed unexpectedly;
- the source period already exists;
- protected formulas differ from approved template expectations;
- balance-check cells are unavailable;
- a conflicting run is active.

---

### Script 2: `validateAndPlan`

This script should receive the Agent/Human-produced evidence package and do no model writes.

It should:

- validate JSON schema;
- normalize units, signs, dates, and currencies;
- verify model row IDs and target addresses;
- check source current/prior-year values against model prior actuals;
- apply known back-out rules;
- calculate arithmetic reconciliation tests;
- classify each proposed item as:
  - accepted;
  - accepted with flag;
  - needs analyst ruling;
  - rejected;
  - impossible due to model/source inconsistency;
- return a write plan plus a rejection queue.

This is where “the code accepts because it reconciles, not because the label matched” should live.

Separating planning from writing is valuable because it means an Agent response can be challenged, reviewed, and replayed without touching the workbook.

---

### Script 3: `applyBatch`

This is the only script allowed to change operational model cells.

It should:

- verify `runId`, workbook fingerprint, and plan version;
- verify the run lock;
- copy prior-actual recipe blocks into target actual columns where required;
- apply only approved input writes;
- add flags/comments/formatting;
- append an immutable batch record;
- return the resulting check-cell values and a new model fingerprint.

Use one invocation per sheet/panel or per bounded batch, not per individual cell.

The write plan must be idempotent. Re-running the same batch should either:

- detect that it was already applied and return success, or
- safely reapply exactly the same result.

Do not rely on “the flow probably will not retry.”

---

### Script 4: `auditAndBalance`

This should independently perform:

- balance-sheet balance check;
- cash-flow-to-cash check;
- formula-error checks;
- protected formula fingerprint comparison;
- expected target-column existence checks;
- accounting identity checks;
- source-to-model reconciliation group checks;
- stale/blank/unmapped required-field checks;
- formula clobber check outside approved write cells;
- panel-specific roll-forward checks when that phase is enabled.

It should return a structured failures table, not prose.

For example:

```json
{
  "status": "FAILED",
  "failures": [
    {
      "type": "FORMULA_CLOBBER",
      "sheet": "IS",
      "address": "H215",
      "expectedFormula": "=H201+H203",
      "actualValue": 0
    },
    {
      "type": "BALANCE_SHEET_OUT_OF_BALANCE",
      "sheet": "BS",
      "address": "H480",
      "difference": 12.3
    }
  ]
}
```

---

### Script 5: `finalizeReportAndLedger`

This should:

- write/update `_REPORT`;
- append final decisions and evidence records;
- mark the run as completed, failed, or awaiting review;
- release the model lock only if appropriate;
- emit a short operational summary for the flow.

---

### Avoid a mega-script

A single mega-script with a `mode` parameter appears simpler but tends to become difficult to test, retry, and diagnose. It also makes timeout recovery worse.

The right compromise is:

- one shared pure TypeScript logic core, pasted into each script during development/build;
- five small operational entry points;
- a common version identifier embedded in every script and ledger record.

The cut should not be “per sheet” by default. Per-sheet splitting is useful for large workbooks and retry isolation, but the principal boundary should be:

> preflight → plan →

### Response B — google/gemini-3.1-pro-preview

This is a fascinating architectural puzzle. You are moving from a highly deterministic, code-heavy, unconstrained environment into a low-code, strictly sandboxed, deeply constrained Microsoft 365 ecosystem. 

The good news: **Excel Online’s Office Scripts (TypeScript) engine is blisteringly fast if you respect its memory model**, and Power Automate (PA) flows can act as a robust state machine. The bad news: your Python pipeline relied heavily on absolute control over PDF parsing and unlimited compute time, both of which are gone.

Here is the architectural review and answers to your six questions from "the council."

---

### 1. What breaks first at scale, and what’s the mitigation?
**First to break: The Agent-node context limit on 300-page PDFs.**
A Copilot/AI Builder Agent node will hallucinate, skip tables, or simply time out if fed a 300-page PDF and asked to "find the financials." It lacks the deterministic grid-mapping of `pdfplumber`. 
*   **Mitigation:** You cannot process the whole PDF in one prompt. You must use a **Flow Loop**. In Excel, store a configuration table of "Target Tables" (e.g., Income Statement, Balance Sheet). The Flow loops over this table, and for each, sends the PDF to the Agent with a highly scoped prompt: *"Locate the Income Statement. You will know you found it because the prior year (2023) Revenue was exactly $4,521. Extract only this table."* 

**Second to break: Office Script 120s timeouts.**
If you loop cell-by-cell to check ties or apply formats, Office Scripts will time out in ~15 seconds, let alone 120s. Every call across the Excel API boundary (e.g., `range.getValue()`) is costly.
*   **Mitigation:** **100% In-Memory Array Processing.** You must read the entire target range into a TypeScript 2D array (`range.getValues()`, `range.getFormulas()`), do all logic (axis discovery, tie checks) in standard TypeScript in-memory, and write back in a single `range.setValues()` call.

**Third to break: Flow Concurrency.**
If two analysts trigger the Flow on the same model, or PA tries to parallelize a loop, the Excel file will corrupt or lock.
*   **Mitigation:** Go into the Flow Settings for your trigger and any "Apply to each" loops, and explicitly set **Concurrency Control to 1**.

### 2. Is the script decomposition (snapshot/write/check/report) the right cut?
**No. It relies too heavily on passing JSON through Power Automate.**
Passing massive "snapshot" JSONs out of Excel, into PA, and back into Excel will hit the ~5MB payload cap and slow the flow to a crawl. **Treat Excel as the database.** Do not pass state to the Flow; pass *instructions*.

A better decomposition (called sequentially by Flow):
*   **Script A (Prep & Anchor):** Finds the axes, executes the Mark-to-Actual recipe (copies columns), and returns to PA *only* a JSON list of target row names and expected Prior Year anchor values.
*   **Script B (Map & Write - called in a loop per statement):** PA passes the Agent-extracted JSON table to this script. The script maps rows, writes inputs, triggers Excel recalc, and checks ties. If it fails the tie, it rolls back the write and returns a `{"status": "fail", "reason": "Net Income diverged by $40"}` payload back to PA.
*   **Script C (Roll-forward & Translation):** Executes the panel translations.
*   **Script D (Police & Report):** Does the final balance sheet ties, generates the orange flags, and outputs the final report.

### 3. PDF Completeness: How to detect skipped tables without code?
Since you can no longer walk pages in Python, you must rely on **Anchor-Triangulation** driven by the Excel model.

1.  **The Prior-Year Anchor:** Before asking the Agent to extract a table, Script A looks at the Excel model's *Prior Year Actuals*. It passes 3-5 of these key values (e.g., PY Revenue, PY Net Income, PY Total Assets) to the Agent node's prompt. 
2.  **The Extraction Rule:** The prompt mandates: *"Extract the table containing these specific values in the 2023 column. You must include all rows between [Revenue] and [Net Income]."*
3.  **The Mathematical Enforcer:** When the Agent returns the JSON table, Script B writes it to a hidden staging sheet in Excel. The script sums the extracted parts (e.g., summing extracted operating expenses). If the extracted parts do not mathematically tie to the extracted subtotal, **the Agent skipped a row**. The script rejects the extraction, triggering a Flow loop to retry with a higher temperature or prompt variation. 

### 4. The mark-to-actual recipe: Copying formulas/formats cell-by-cell in 120s?
Cell-by-cell `getCellProperties` is dead on arrival. However, Office Scripts wraps the native Excel C++ engine, which gives you access to bulk operations that are actually *faster* than Python's `openpyxl`.

**The Viable Recipe:**
1.  **Bulk Copy:** Use `range.copyFrom(sourceRange, ExcelScript.RangeCopyType.all)`. This duplicates formats, formulas, and values instantly.
2.  **The "Overwrite Inputs Only" Magic:** You do not need to check formulas one by one. Office Scripts has a native method for this. Once the column is copied, call:
    `newColumnRange.getSpecialCells(ExcelScript.SpecialCellType.constants)`
    This instantly isolates all hardcoded inputs (ignoring formulas). 
3.  **Clear:** Call `clear(ExcelScript.ClearApplyTo.contents)` on that special range.
Now you have a perfectly formatted column with intact formulas and blank inputs, ready to receive mapped data, executed in roughly 50 milliseconds.

### 5. Where does it silently lose determinism, and the Ledger design?
**Where determinism dies:** The Agent node will map "SG&A" to "Operating Expenses" on Tuesday, and to "Selling, General & Admin" on Wednesday. Without your Python code refereeing every mapping via cross-statement arithmetic, you risk mapping drift.

**The Ledger Design (`_SPEC` hidden sheet):**
Because Power Automate can be flaky, the Ledger must live inside Excel as an **Excel Table (`ListObject`)**.
*   **Columns:** `Timestamp | Statement | Agent_Extracted_Label | Model_Target_Row | Analyst_Locked (True/False) | Tie_Status`
*   **The deterministic shield:** Before the Flow sends *anything* to the Agent for mapping judgment, Script B queries the `_SPEC` table. If `Agent_Extracted_Label` matches an entry where `Analyst_Locked == True`, the script performs the mapping natively and bypasses the LLM entirely. 
*   **Human Review:** The Flow's "Approval" node sends an Adaptive Card (Teams/Email) to the analyst showing un-locked mappings. The analyst clicks "Approve," and the Flow writes `True` to

### Response C — x-ai/grok-4.6

**The workbook must be the bus.** If anatomy, staging, plan, and ledger travel as JSON through the flow, you will lose to payload, timeouts, and silent truncation long before the Python laws are the problem. Scripts should be thin kernels that read/write hidden sheets; the flow should pass only `{runId, mode, pointers}`.

Below is a hard look at the six questions, then a Phase-1 kit that an intern can actually paste.

---

## 1. What breaks first (300-page PDF, ~1,000 writes, 10 sheets)

**Order of failure in practice:**

| Rank | Failure | Why it hits first | Mitigation |
|---|---|---|---|
| 1 | **Agent extraction completeness** | A 300-page filing is not a prompt. Agent-node context, OCR fidelity, and “helpfully summarized” tables will drop notes, restatements, and small print. Tie-checks catch *mapped* errors; they do not prove a table was seen. | Never one-shot the PDF. TOC/pass-1 → per-statement pass-2 → notes pass-3. Completeness oracle = prior-year actuals in the model (see Q3). Gate on missing-expected-lines, not on Agent confidence. |
| 2 | **120s script wall** | Format+formula copy, used-range scans across 10 sheets, and `getCellProperties` on wide panels are the killers. 1,000 *value* writes are fine; 1,000 *format* round-trips are not. | `copyFrom` on the *used* prior column (not cell-by-cell, not the whole 1M-row column). One panel or one sheet per invocation. Flow loops. Persist plan on `_PLAN`, not in the return JSON. |
| 3 | **Flow ↔ script payload / truncation** | Anatomy of a 10-sheet model (addresses, formulas, formats, labels, number formats) blows past comfortable JSON sizes. Failures look like “mysteriously missing rows,” not a clean error. | **Do not return grids.** Snapshot writes `_ANATOMY` + `_HASHES` in-workbook. Script I/O is counts, hashes, exception lists, `ok/refuse` codes. Stay well under 200KB. |
| 4 | **Excel Online lock / co-authoring** | SharePoint trigger + human review + chained scripts on the *live* file = merge conflict, partial writes, recalc of a half-updated book. | **Clone first.** Every run copies the model to `runs/{runId}/model.xlsx` and works only there. Promote back after balance police + analyst sign-off. |
| 5 | **Recalc vs read race** | Office Scripts can write formulas and read cached values before Excel Online finishes calc. Balance police then false-fails or worse, false-passes. | After writes: `workbook.getApplication().calculate(ExcelScript.CalculationType.full)` then re-read. If still dirty, return `NEED_RECALC` and let the flow retry the check script. |
| 6 | **Agent-node + flow quotas / duration** | Dozens of Agent calls × loops × approvals. Personal Productivity env is the first place this gets throttled or the run becomes un-debuggable. | Bound Agent calls (cap N per phase). Cache extraction to `_STAGING` once. Idempotent scripts. One human gate per phase, not per line. |
| 7 | **Script source size / drift** | 15k Python lines concatenated into 4–6 self-contained TS files with a duplicated “pure core” will diverge on the third edit. Intern paste-in makes this certain. | One dispatcher script (mode param) *plus* hidden-sheet state, or at most two scripts (read-kernel / write-kernel) with identical preamble generated from one local source. Local Node fixtures remain mandatory. |

Payload caps and flow quotas are real; they are not the first *silent* failure. The first silent failure is **the Agent omitting a table that your ties never asked about.**

---

## 2. Script cut: snapshot / write / check / report is the wrong grain

The right grain is **state in the workbook, modes in one (or two) kernels**, with the flow looping *work units*, not *laws*.

**Do this:**

- Hidden sheets (all tables, append-only where noted):
  - `_SPEC` — locked analyst rulings (you already wanted this)
  - `_ANATOMY` — axes, panels, column map, input vs formula cells, prior-year keys
  - `_STAGING` — extracted facts with `sourcePage`, `statement`, `period`, `value`, `rawLabel`, `confidence`
  - `_PLAN` — proposed writes: dest address, value/formula, reason, `tieStatus`, `rulingId`
  - `_LEDGER` — immutable events
  - `_LOCK` — single-cell lease (see Q5)
  - `_REPORT` — as today
- **One kernel script** `Run(mode, runId)`:
  `SNAPSHOT | PLAN_APPLY | RECALC_CHECK | REPORT | COPY_COLUMN | LOCK | UNLOCK`
- Flow calls the same script repeatedly with a mode and a small JSON pointer (`sheet`, `panelId`, `planRowFrom/To`).

Why not 4–6 concatenated cores:
- No modules ⇒ 6 copies of tie arithmetic. The first intern edit breaks one copy.
- Your laws (ties, refuse-on-clobber, panel translation) must be identical at plan time and apply time.
- 120s is a *work-unit* limit, not a *law* limit. Split by **panel/sheet/row-batch**, not by function name.

When a mega-script still risks timeout: keep **two files only** — `kernel_read.ts` and `kernel_write.ts` — generated from one local source (concat preamble + mode). Never hand-maintain four cores.

**Per-sheet scripts** are a reasonable *flow* loop (call kernel with `sheet=IS`), not separate source files.

**Per-law scripts** (restatement vs mark-to-actual vs roll-forward) look clean on a whiteboard and guarantee duplicated axis discovery. Don’t.

---

## 3. PDF extraction without a page walker — make completeness a proof, not a vibe

You cannot “walk pages in code.” So **the model’s prior-year actuals are the completeness spec.** The Agent is a staging loader, not the source of truth.

### Extraction structure (forced multi-pass)

Pass 0 — **inventory (cheap, bounded)**  
Ask only for: document identity, period, currency, restatement flags, list of statements/notes with **page ranges** and table titles. Output a `_TOC` table. If page count / statement list is implausible vs filing type, refuse.

Pass 1 — **known statements, one at a time**  
For each TOC row: “Extract this statement on pages L–R as a grid. Do not summarize. Every numeric cell. Repeat header/period on each row.”  
Write to `_STAGING` with `sourcePage` **required**. Drop rows without a page.

Pass 2 — **notes / restatements / share counts / one-offs**  
Same rule, bounded by TOC pages. Separate Agent calls.

Pass 3 — **coverage audit (no new facts)**  
Feed: (a) expected keys from `_ANATOMY` prior-year actuals, (b) `_STAGING` labels+values, (c) TOC. Agent may only mark `found / restated / not-in-this-disclosure / unknown`. Unknowns → human review, not guesses.

### Chunking / page budgets

- **Never** send the whole 300-page PDF to one Agent node.
- Chunk by **TOC page ranges**, not by token guess. Typical IS/BS/CF chunks are small; notes explode — cap pages per call (e.g. 8–12) and split notes.
- If the environment cannot pass page ranges reliably, split the PDF in SharePoint *before* the Agent (even a dumb “PDF split by 10 pages” flow) so each Agent call has a small file. Completeness then includes “every split file produced a TOC or an explicit empty.”

### Detecting “Agent skipped a table” with only ties + prior-year values

Maintain `expected_keys` from the model:

- Every prior-year actual that the recipe might mark (IS/BS/CF key lines + any line that was an input last cycle).
- Period arithmetic: if this is FY, expect FY comparatives; if H1, expect H1 comparatives, etc.

Then:

1. **Value triangulation (your existing law):** staging row matches an expected key if `|staging − priorActual| < ε` **or** a declared restatement explains the delta. Label match is insufficient (keep this).
2. **Coverage ratio:** `found_expected / expected_keys` per statement. Thresholds by statement (BS/IS near 100% of key lines; notes lower). Below threshold → `INCOMPLETE`, do not write.
3. **Orphan clusters:** staging values that form a grid (same page, aligned periods) but map to nothing — possible *new* table (segment, new line). Do not auto-write; flag.
4. **Page gaps:** if TOC says pages 34–37 are “Note 4 – Revenue” and `_STAGING` has no `sourcePage` in 34–37, that table was skipped **even if ties on the IS still pass**.
5. **Control totals:** where the disclosure prints “Total revenue / Total assets / Total cash from ops”, require staging to reproduce that total by sum of children. If the Agent skipped a child, the total won’t tie internally — that’s your replacement for pdfplumber completeness.

**Do not** let the Agent “map and extract” in one call. Extraction errors become mapping folklore. Staging is facts; mapping is a later, tie-refereed step.

---

## 4. Mark-to-actual column copy: `getCellProperties` is the trap; `copyFrom` is the recipe

Cell-by-cell `getCellProperties` / `setCellProperties` on a whole column will **lose the 120s budget** on a busy sheet (used range taller than you think, plus format objects).

**Do this instead:**

```typescript
// used rows only — never A:A
const src = sheet.getRangeByIndexes(firstRow, priorCol, rowCount, 1);
const dst = sheet.getRangeByIndexes(firstRow, newCol, rowCount, 1);
dst.copyFrom(src, ExcelScript.RangeCopyType.all); // formulas + formats + number formats
```

Then overwrite **inputs only** from `_PLAN` (values, not formulas). Orange flag fills on back-outs as a second, narrow `getFormat().getFill().setColor` over the planned addresses, not the whole column.

Why this matches the Python recipe: Excel’s own copy is how “copy prior actual column’s formulas+formats” actually works; relative refs shift by column. That *is* a large part of panel translation. Absolute `$` refs will *not* shift — snapshot must record which formulas are absolute and refuse or rewrite those explicitly (this is a law, not a format problem).

**Viability inside 120s:** one panel, used-range `copyFrom`, then a few hundred value overwrites: usually fine. Ten sheets × formats via object model: not fine.

**Fallback if a sheet is too big:**

1. `copyFrom` one panel (H1 / FY / Q) per script invocation; flow loops panels.
2. If `copyFrom` still times out (rare, pathological used ranges): copy **formulas** with `getFormulas()` / `setFormulas()` in row batches of 200, and copy formats only for `usedRowCount` via `RangeCopyType.formats` in the same batches. Skip copying formats for empty rows.
3. Last resort: copy formulas only; apply a **format template** (number format + orange/input/actual styles from `_SPEC`) to planned cells. Loses exotic per-cell cosmetics; keeps the audit look. Document it as a known downgrade.

**Also:** snapshot `usedRange` *before* copy. A stray format in row 50,000 is a classic Excel Online timeout.

After copy + input overwrite: full calc, then balance police (Q1).

---

## 5. Where determinism dies, and a cheap ledger that survives concurrency

**Silent determinism leaks (even with your referees):**

- Agent extraction (missing rows, merged-cell OCR, sign/scale, “in millions”).
- Agent mapping when *two* staging rows both triangulate (restated vs original; parent vs child). Ties can still pass on the wrong child.
- Excel recalc timing (Q1).
- Formula copy with mixed absolute/relative refs (panel translation diverges from Python).
- Floating point / display rounding vs stored value (`getNumberFormat` vs `getValue`).
- Human review arriving late and being applied to a different `_PLAN` generation.
- **Concurrent flows on the same workbook** (SharePoint trigger double-fire, analyst re-save, two disclosures). Last writer wins; ledger lies.
- Script source not versioned (no Git). The kernel that ran is not the kernel you think ran.
- `gpt-5.6` non-determinism on the same prompt. k=2 is weaker in this stack because you cannot cheaply isolate a second model; a second Agent call is still the same system.

Keep the Python invariant: **code referees every write**. The Agent never writes the model. If it doesn’t reconcile, it doesn’t go in (`refuse` → red flag row on `_PLAN`). That is the only reason this port stays “a proven engine” rather than a chatbot with a spreadsheet.

**Concurrency: don’t share the file.**  
Cheapest correct design: `Copy file` to `runs/{runId}/` at start. All scripts, Agent staging, human review operate on the copy. Promotion is a final SharePoint copy-back after `BALANCE_OK` + approval. Concurrent runs cannot clobber each other.

**Ledger on a hidden sheet (cheap, good enough):**

`_LEDGER` as an Excel table, **append-only**, columns:

`seq | runId | utc | scriptVersion | mode | event | sheet | address | fromHash | toHash | rulingId | planGen | ok`

- `seq` = `MAX(seq)+1` in the same script invocation (read last row, write n rows). Not a flow variable.
- `scriptVersion` = hard-coded constant in the kernel (intern-visible). Bump on every paste.
- `fromHash` / `toHash` = hash of the **planned batch** and of the **read-back values** after recalc (not of the whole book).
- `planGen` increments whenever mapping re-runs. Human approvals bind to `planGen`; stale approvals refuse.
- Events include `LOCK`, `SNAPSHOT`, `STAGE_LOAD`, `MAP_REFUSE`, `APPLY`, `RECALC`, `BALANCE_FAIL`, `PROMOTE`.

`_LOCK` sheet: one cell `lease = runId|expiryUtc`. Kernel `LOCK` mode: if lease valid and `runId` differs, refuse. Unlock at end / on failure path. This is a **courtesy lock** for the live file; the copy-per-run is the real isolation. Do both.

Replay: `_SPEC` rulings are the only LLM-replacing memory; `_LEDGER` is forensic. Same as your decision ledger, minus Python.

---

## 6. Phase 1 — what to explicitly NOT attempt

Phase 1 exists to prove **plumbing + referee**, not research-model fidelity.

**Do not attempt:**

- 300-page PDFs, scanned OCR, notes, segments, restatements, true-up, roll-forward, H1=Q1+Q2 panel translation.
- Ten sheets. Formats beyond “copy one column with `copyFrom`.”
- k=2, cascade mapping beyond **direct prior-year value triangulation + refuse**.
- Back-out formula synthesis, orange-flag policy beyond a single fill color.
- Balance police on the full BS/cash loop (a *single* check on one control total is enough).
- Concurrent runs, promote-back, intern-facing `_REPORT` polish.
- Agent mapping of the whole statement. No “estimate+flag.”
- Duplicated 4–6 cores. No Git-less mega-port of 15k lines.
- Writing staging from the flow cell-by-cell (Graph death). Staging load is a script `setValues` of a 2D array from a compact JSON **or** a CSV dropped next to the workbook and read in-script (if you cannot fetch, have the flow write a `_STAGING` range in one `Run script` with a rectangular array — still keep the array small in Phase 1).

**Phase 1 scope (intern < 1 hour paste-in):**

1. One cloned sample workbook, one sheet, ~15 key lines, one prior actual column, one new column.
2. One tiny `_STAGING` (hand-built or one Agent call on a **2-page** excerpt).
3. Two modes in **one** script: `SNAPSHOT` (write `_ANATOMY` for that sheet), `APPLY` (copyFrom prior column used range → overwrite 15 inputs only if each triangulates to staging within ε → recalc → write `_LEDGER` + pass/fail).
4. Flow: copy file → run SNAPSHOT → (optional one Agent) → run APPLY → human approval on the refuse list. No loops.
5. Local Node fixtures for the kernel with 3 workbooks: happy path, broken tie (must refuse), empty staging (must refuse). Intern does not invent laws.

If Phase 1 cannot refuse a non-reconciling write, stop. Do not add PDF coverage.

---

## Design challenges (the ones that will actually hurt)

1. **Two Agent hops (extract then map) without a frozen `_STAGING` snapshot** will make ledger replay impossible. Freeze staging (`planGen`) before mapping.
2. **Excel Online is a better calculator and a worse batch editor** than openpyxl. Optimize for few large range ops, not Pythonic cell loops.
3. **Personal Productivity + no Git** means the kernel *is* the product. One file, version constant, fixtures, refuse-by-default. Split sources only when 120s forces you to split *work


## Stage 2 — peer reviews

### Review by openai/gpt-5.6-terra

### Response A

**What it does well**

- Correctly identifies the central architectural risk: not TypeScript porting, but loss of controlled PDF evidence acquisition and transaction-like model update discipline.
- Strong fail-closed principle: Agent proposes evidence; Office Scripts validate, plan, and apply model changes.
- Accurately prioritizes likely technical bottlenecks:
  - large anatomy snapshots and formula/format payloads;
  - chatty Office Script calls;
  - flow orchestration at fact/cell level;
  - Agent context/completeness limitations for long PDFs.
- Gives sound Office Scripts performance guidance: bulk reads, in-memory processing, batched writes, avoid `getCell()` in loops, avoid repeated recalculation.
- Its transactional decomposition is especially strong:
  - `preflightSnapshot`
  - `validateAndPlan`
  - `applyBatch`
  - `auditAndBalance`
  - `finalizeReportAndLedger`
  
  This is a materially better cut than merely snapshot/write/check/report because it separates proposal validation from workbook mutation.
- Correctly emphasizes idempotency, run IDs, locks, fingerprints, plan versions, and immutable batch records. Those are essential because flows retry and are not inherently transactional.
- The recommendation not to use a mega-script is well reasoned: retries, diagnostics, and timeout recovery are materially better when planning, application, and audit are separate.

**What it does poorly**

- The response is visibly incomplete: it stops in the middle of the decomposition discussion and does not fully answer the remaining questions, particularly PDF completeness mechanics, column-copy implementation, hidden-sheet concurrency design, and a sharply bounded Phase 1.
- It recommends persisting large state in `_SPEC`, but `_SPEC` should primarily hold specifications and locked rulings. Operational run state, staging, plans, hashes, and ledger events should preferably be separated into dedicated hidden tables/sheets. Conflating them risks making analyst rulings mutable operational clutter.
- It says “setting calculation mode to manual” as a possible tactic without sufficiently qualifying that calculation-mode behavior and recovery need careful validation in Excel Online/Office Scripts. The important operational point is to batch changes and explicitly calculate/check afterward, not to assume desktop-like calculation control is always a safe optimization.
- It does not explicitly call out cloning the workbook per run as the most robust concurrency mitigation. A lock helps, but it is weaker than isolation through a run-specific workbook copy.
- It lacks practical PDF extraction architecture. It correctly says that a 300-page filing cannot be trusted as a single Agent input, but it does not get far enough to specify inventory, statement-level extraction, note/restatement passes, page-range coverage controls, or prior-year anchor coverage gates.
- It does not address the user’s Phase 1 “intern under an hour” constraint in a concrete enough way.

Overall, this is excellent architectural reasoning, but it is incomplete relative to the requested six-part council answer.

---

### Response B

**What it does well**

- It identifies several important concerns:
  - Agent context/completeness risk for 300-page PDFs;
  - Office Script timeout risk from cell-by-cell API calls;
  - flow concurrency risk when multiple analysts or parallel loops touch the same workbook.
- The prior-year-anchor extraction idea is useful. Asking the Agent to locate a statement using known prior-year Revenue, Net Income, Total Assets, etc. is a sensible way to constrain extraction and verify that the intended comparative table was found.
- It rightly recommends in-memory range processing via `getValues()` / `getFormulas()` followed by bulk writes.
- It correctly warns against passing full workbook anatomy through flow JSON.
- It gives a useful bulk-copy suggestion: `copyFrom(sourceRange, ExcelScript.RangeCopyType.all)` is much more appropriate than cell-level formula/format copying.
- It recognizes that locked analyst mappings should bypass repeat LLM judgment.

**What it does poorly**

- The response is incomplete, ending mid-ledger discussion. It does not fully answer all six questions.
- It is overly confident and occasionally imprecise about platform behavior. For example, calling Office Scripts “blisteringly fast” and claiming certain operations occur “instantly” or in “roughly 50 milliseconds” is not operationally defensible across large, formula-heavy Excel Online workbooks.
- Its suggested Script B combines mapping, writing, recalculation, checking, and rollback. That is a poor transactional boundary:
  - mapping and validation should happen before mutation;
  - Office Scripts do not provide a true transaction/rollback mechanism;
  - attempting rollback after partial workbook changes can introduce more failure modes than a plan-then-apply model.
- The `getSpecialCells(constants)` approach is risky as presented. After copying a prior actual column, clearing all constants may be valid for some narrowly defined numeric-input columns, but it can also erase intentionally copied hardcoded constants that are not new inputs, such as static assumptions, helper constants, template elements, or mixed formula/input structures. The existing system’s law is “overwrite inputs only,” which requires an explicit writable-input map or source-cell classification, not merely all constants.
- “Retry with a higher temperature” is an inappropriate recommendation for a deterministic production process. The system should retry with a different bounded evidence scope or request human review, not use temperature variation as a completeness mechanism.
- Its completeness model relies too heavily on arithmetic ties. Ties can detect incomplete tables only when the omitted item participates in a checked identity. They do not prove that note tables, restatement disclosures, segment tables, share counts, or non-modeled disclosures were actually inspected.
- Concurrency control set to one in a flow is not sufficient protection by itself. It may serialize a specific flow instance but does not robustly protect against duplicate triggers, other flows, manual workbook edits, or separate runs against the same file. Workbook cloning or a durable lock plus run isolation is needed.
- It does not meaningfully discuss flow quotas, payload budgeting, plan/state storage, recalc races, ledger versioning, or the requested Phase 1 exclusions.

Overall, Response B contains several good instincts but is more hand-wavy, less fail-safe, and less technically rigorous than the others.

---

### Response C

**What it does well**

- This is the most complete response and directly addresses all six requested areas.
- Its core architectural principle is excellent: **the workbook should be the durable state store/bus**, while the flow passes only small control messages such as run ID, mode, sheet/panel pointer, and row-batch pointers.
- It correctly identifies that full workbook anatomy, formulas, formats, and plans should not travel through flow JSON. Its recommendation to return counts, hashes, status codes, and concise exception lists is highly practical.
- It gives a strong failure ordering:
  1. Agent extraction completeness;
  2. Office Script timeout;
  3. payload truncation;
  4. Excel locking/coauthoring;
  5. recalc/read races;
  6. flow/Agent quotas;
  7. source drift without Git.
  
  This is nuanced: it distinguishes what is likely to fail silently from what merely fails visibly.
- Its decomposition advice is strong. Using one dispatcher/kernel script with a `mode` parameter, or at most a read and a write kernel, avoids duplicated deterministic-law logic across four to six manually maintained script files.
- It also correctly says the runtime split should be by **work unit**—sheet, panel, or row batch—rather than by law or source file. That directly addresses the 120-second execution cap.
- The extraction design is among the best parts:
  - document inventory / table-of-contents pass;
  - statement extraction by bounded page range;
  - separate notes/restatement/one-off extraction;
  - coverage audit with no new facts;
  - required page provenance;
  - expected-key matching against prior-year model actuals;
  - coverage ratios;
  - page-gap checks;
  - control-total checks;
  - orphan-grid detection.
  
  This correctly recognizes that ties alone cannot prove completeness.
- It strongly preserves the core deterministic invariant: Agents stage facts and propose mappings; code referees all writes; non-reconciling entries are refused rather than guessed.
- The `copyFrom(..., RangeCopyType.all)` recommendation is correct for the formula-and-format copying recipe. Its warning not to copy entire Excel columns, and its recommendation to work only on used panel ranges, are especially important.
- Its fallback hierarchy for large sheets is practical: panel-level copy, row-batched formula/format copying, and a documented formula-first formatting downgrade as a final fallback.
- Its list of determinism leaks is excellent: OCR/sign/scale errors, ambiguous triangulation, recalc timing, mixed absolute/relative references, rounding, stale approvals, concurrent flows, source drift, and LLM nondeterminism.
- The clone-per-run approach is the strongest concurrency recommendation in the answers. It avoids relying solely on a workbook lock and makes human-review waits much safer.
- Its ledger design is concrete and useful: append-only `_LEDGER`, script version, plan generation, source/target hashes, ruling IDs, statuses, and stale-approval binding.
- Its Phase 1 scope is particularly well bounded and responsive to the “intern under an hour” requirement:
  - one workbook copy;
  - one sheet;
  - roughly 15 key lines;
  - one small staging table;
  - one or optional Agent call on a short excerpt;
  - snapshot and apply only;
  - direct triangulation and refusal;
  - no notes, restatements, roll-forward, k=2, full balance police, or broad formatting.

**What it does poorly**

- It overstates “the workbook must be the bus.” The general direction is correct, but not every operational object belongs inside the workbook. SharePoint should still retain immutable source PDF copies, run-folder identity, and potentially a run manifest/status file. The workbook is a good local run state store, not necessarily the only durable system-of-record.
- The recommendation to use one mega dispatcher/kernel has tradeoffs that it underplays. A mode-driven script can reduce copy-paste drift, but it can also become a giant, hard-to-maintain script in an environment with no modules, no source control, and potentially strict script-size or editor usability constraints. Its “at most two scripts” proposal is sensible, but the rhetoric against the five-script transactional cut is somewhat too absolute. A hybrid is probably best: one shared generated kernel plus a small number of operational entry points or modes.
- It suggests splitting PDFs before the Agent if page-range prompting is unreliable, but the stated allowed tools do not include a PDF splitting action or code capable of manipulating PDFs. Since external APIs, Azure, Python, and third-party connectors are unavailable, this should be framed as conditional on a verified first-party SharePoint/flow capability—not as an assumed fallback.
- Its suggestion that the flow could “write a `_STAGING` range in one `Run script` with a rectangular array” is directionally fine, but under the described constraints the script interface is JSON-string based. The implementation needs explicit serialization and payload sizing. Large staging tables may still require chunking.
- The ledger’s `MAX(seq)+1` approach is only safe because it advocates clone-per-run or a valid lock. On a shared workbook it remains race-prone. It should more explicitly say sequence generation is not concurrency-safe without isolation.
- “Promotion” by copying the run workbook back to the original model can itself create race and overwrite risks if the original has changed during review. A safer production approach is often to retain the run workbook as the deliverable or require a final compare-and-promote gate rather than blind replacement.
- It does not spend much time on Agent-node input limitations and exact page-range semantics. Whether the Agent can reliably honor page ranges depends on the actual Copilot Studio file-ingestion behavior, which should be empirically tested before treating it as a control.
- A few statements are more categorical than the evidence supports, such as implying Agent omissions are necessarily the first issue in every real run. For some complex workbooks, Excel Online recalculation or workbook locking could fail first. Still, its prioritization is reasonable.

Overall, Response C is the strongest answer: technically grounded, complete, operationally conservative, and unusually good on deterministic controls and Phase 1 scope.

FINAL RANKING:
1. Response C
2. Response A
3. Response B

### Review by google/gemini-3.1-pro-preview

### Evaluation of Responses

#### Response A
**What it does well:**
Response A provides a solid, traditional software-engineering approach to the problem. It correctly identifies that JSON payload sizes will bottleneck the architecture before cell writes do, and offers a smart mitigation: pass indexes, fingerprints, and pointers rather than whole workbook grids. Its proposed 5-script transactional boundary (`preflightSnapshot`, `validateAndPlan`, `applyBatch`, `auditAndBalance`, `finalizeReportAndLedger`) is a logical way to separate concerns and prevent the LLM from making unsanctioned writes.

**What it does poorly:**
The response is too generic regarding the specific technical constraints of Office Scripts and Power Automate. It fails to answer Q4 directly (it doesn't address the viability of `getCellProperties` vs `copyFrom`). For Q5, its solution to concurrency is just a "run lock," which is notoriously difficult to implement safely in cloud flows without race conditions. Finally, it completely ignores Q6, failing to provide the requested "Do Not Attempt" list for Phase 1. 

#### Response B
**What it does well:**
Response B shines in its deep, specific knowledge of the Office Scripts (TypeScript wrapper of Excel C++ engine) API. Its answer to Q4 is brilliant: using `range.copyFrom()` followed by `getSpecialCells(ExcelScript.SpecialCellType.constants)` and `clear()` is the absolute fastest and most native way to perform the mark-to-actual recipe in under 120 seconds. It also provides a practical, low-code answer to concurrency by advising the user to set the Flow's Concurrency Control to 1. 

**What it does poorly:**
The most glaring issue is that the response is incomplete. It cuts off mid-sentence at the end of Q5 and entirely misses Q6. Additionally, while relying on the Flow's concurrency control prevents race conditions, it acts as a global bottleneck—if multiple analysts try to run disclosures simultaneously, they will queue up and potentially time out waiting for the flow to free up.

#### Response C
**What it does well:**
Response C is a masterclass in architecting for heavily constrained Microsoft 365 environments. It answers every single question directly, practically, and with deep technical accuracy. 
- For Q1 and Q2, it correctly identifies that maintaining 4-6 duplicated scripts without a Git repository or module imports will lead to immediate code drift, and pragmatically recommends a 1-to-2 kernel approach driven by `mode` parameters. 
- For Q3, it provides a highly robust, multi-pass deterministic framework for proving completeness (TOC pass, coverage ratios, control totals) without relying purely on LLM vibes. 
- For Q4, it properly warns against `getCellProperties` and recommends `copyFrom` with fallback strategies for massive sheets. 
- For Q5, it solves the concurrent run issue flawlessly: *clone the file per run*, completely sidestepping SharePoint lock/co-authoring nightmares. 
- For Q6, it provides a perfect, highly specific list of what to exclude so an intern can actually build Phase 1 in an hour.

**What it does poorly:**
The response is quite dense and relies on the user managing a lot of hidden sheets (`_SPEC`, `_ANATOMY`, `_STAGING`, `_PLAN`, `_LEDGER`, `_LOCK`), which could bloat the template workbook. However, given the constraint that no external databases are allowed, this is a necessary evil. 

FINAL RANKING:
1. Response C
2. Response A
3. Response B

### Review by x-ai/grok-4.6

**Response A**

Does well:
- Frames the problem correctly: the risk is evidence acquisition and transactional discipline, not TypeScript translation. Fail-closed, Agent proposes, scripts accept.
- Strong on payload: snapshot indexes/fingerprints, not workbook dumps; persist state in `_SPEC`.
- Excellent timeout advice: rectangular blocks, no cell-by-cell Excel API, batch writes, recalc once, calculation-mode caveats.
- Flow should be coarse phases, not one action per fact — this is the right grain for Copilot Studio.
- Script split is upgraded into transactional boundaries (`preflightSnapshot`, `validateAndPlan`, `applyBatch`, `auditAndBalance`, `finalizeReportAndLedger`). Separating plan from write is the best idea in A: replay without touching the model.
- Agent PDF treated as evidence proposal, not complete ingestion — honest about what LLMs cannot prove.

Does poorly:
- Incomplete: the answer cuts off mid-sentence at “preflight → plan →”. Questions 3–6 are essentially unanswered (PDF completeness structure, `copyFrom` vs `getCellProperties`, ledger/concurrency, Phase 1 “do not attempt”).
- Five named scripts still duplicate a no-modules core; A does not resolve intern paste-in / source-drift as sharply as C.
- No concrete Office Scripts APIs for the recipe (`copyFrom`, `getSpecialCells`).
- Weaker on clone-the-workbook vs live-file co-authoring.

---

**Response B**

Does well:
- Concrete, operator-friendly mitigations: concurrency = 1, in-memory 2D arrays, scoped Agent prompts with prior-year anchors.
- Best single API recipe in the set: `range.copyFrom(..., RangeCopyType.all)` then `getSpecialCells(constants)` + clear contents — this is the actual Excel way to “copy formulas+formats, overwrite inputs.”
- Ledger as Excel Table with `Analyst_Locked` bypass of the LLM is cheap and matches “replay locked rulings.”
- Treat Excel as the database / pass instructions not giant snapshots — aligned with A/C but stated simply.

Does poorly:
- Overconfident and sometimes wrong: “timeouts in ~15 seconds,” “50 milliseconds,” “blisteringly fast,” “higher temperature retry” as a completeness strategy.
- Script split (Prep / Map&Write-in-a-loop / Roll-forward / Police) still shuttles extracted tables through PA JSON and loops Map&Write per statement — fights payload and quotas.
- PDF completeness is only prior-year triangulation + internal sum ties; no TOC, page ranges, coverage ratio, or page-gap detection. “Skipped a table you never asked about” is missed.
- Determinism section is thin (mapping drift only). No run isolation, plan generation, recalc race, absolute vs relative refs.
- Phase 1 “what NOT to attempt” is missing entirely.
- Truncates at Human Review / Adaptive Card.

---

**Response C**

Does well:
- Answers all six questions with an intern-assemblable Phase 1 and an explicit “do not attempt” list — the only complete council reply.
- Correct failure order: silent Agent omission first, then 120s format copy, then payload truncation, then co-authoring, recalc races, quotas, source drift.
- Best architectural cut: workbook as bus; hidden `_ANATOMY/_STAGING/_PLAN/_LEDGER/_LOCK`; one (or two generated) kernel with modes; split by panel/sheet work-unit, not by law. Directly attacks no-imports duplication.
- PDF: multi-pass TOC → per-statement grids with required `sourcePage` → notes → coverage audit; completeness from prior-year expected keys, coverage ratio, orphan clusters, page gaps, control totals. Staging frozen before mapping.
- Recipe: used-range `copyFrom`, not `getCellProperties`; panel loop fallback; absolute-`$` as a law; snapshot usedRange before copy.
- Determinism leaks are enumerated (OCR, dual triangulation, recalc, mixed refs, float, stale approvals, concurrency, unversioned scripts). Clone-per-run + courtesy lock + append-only ledger with `scriptVersion`/`planGen`/hashes is the cheapest design that actually survives flaky flows.
- Phase 1 is ruthless and correct: one sheet, ~15 lines, triangulation+refuse, one script, no restatement/roll-forward/k=2.

Does poorly:
- Dense; an intern would need a checklist extracted from it (though C already scopes paste-in).
- Dispatcher mega-script can become a 120s blob if modes are not kept thin; two generated kernels is mentioned but easy to botch without Git.
- `copyFrom` + overwrite is right; B’s `getSpecialCells(constants)` clear is a slightly cleaner “blank inputs” trick C does not use.
- Assumes SharePoint PDF-split and clone-to-`runs/{runId}/` are available in Personal Productivity — usually yes, not verified.
- No k=2 substitute beyond “same system twice.”

---

FINAL RANKING:
1. Response C
2. Response A
3. Response B


## Ranking tally (Borda)

- Response C (x-ai/grok-4.6): 9 pts
- Response A (openai/gpt-5.6-terra): 6 pts
- Response B (google/gemini-3.1-pro-preview): 3 pts

## Stage 3 — chairman synthesis (google/gemini-3.1-pro-preview)

The transition from a deterministic, unconstrained Python environment to the highly sandboxed, low-code Microsoft 365 ecosystem is a profound architectural shift. The council unanimously agrees that the greatest risk is not porting TypeScript—it is the loss of **controlled evidence acquisition and transactional discipline**.

By synthesizing the strongest insights across the council, here is the definitive architectural blueprint for your Copilot Studio and Office Scripts port.

---

### 1. What breaks first at scale, and what’s the mitigation?

The architecture will fail in a specific order if not mitigated:

1. **Agent Completeness (Silent Failure):** A 300-page PDF is not a prompt. Copilot/Agent nodes will hallucinate completeness, helpfully summarize, and silently skip notes or tables if fed massive documents. *Mitigation:* Never one-shot the PDF. Use bounded, multi-pass extraction (see Q3).
2. **Payload Caps & Truncation:** Passing a 10-sheet workbook's anatomy (addresses, formulas, formats) as JSON into Power Automate will exceed the ~5MB payload cap and silently truncate. *Mitigation:* **The workbook is the bus.** Flow should only pass small control messages (`{runId, mode, pointers}`). State must live inside hidden Excel sheets (`_ANATOMY`, `_STAGING`, `_PLAN`).
3. **120s Script Timeouts:** Chatty API calls across the Excel boundary (like cell-by-cell `getCellProperties` or `setFormat` inside a loop) will time out in ~15 seconds, let alone 120s. *Mitigation:* 100% in-memory 2D array processing. Read with `getValues()`, calculate in standard TypeScript, and write back in bulk.
4. **Excel Co-authoring Concurrency:** SharePoint triggers firing simultaneously on the live model will cause read/recalc/write race conditions and merge conflicts. *Mitigation:* **Clone-per-run.** The flow's first step must copy the model to `runs/{runId}/model.xlsx`. All scripts operate on this isolated clone. Only promote back after balance checks and analyst approval.

### 2. Is the script split (snapshot/write/check/report) the right cut?

**No.** While it is the correct *logical* separation, it is the wrong *physical deployment* strategy. 

Because Office Scripts lack module imports (no ES modules), maintaining 4–6 separate scripts means copy-pasting your "pure-logic core" (tie checks, panel translation) into 6 places. The moment a non-technical intern updates a core law in script 3 but not script 4, your determinism dies. 

**The Better Cut: The Mode-Driven Kernel**
Maintain exactly one (or at most two: read/write) "Kernel" script: `Run(mode, runId, payload)`. 
The flow loops over work units (sheets or panels) and calls the kernel with different modes:
*   `PREFLIGHT`: Reads axes, writes expected keys to `_ANATOMY`.
*   `VALIDATE_AND_PLAN`: Reads Agent-extracted `_STAGING`. Generates a write plan in `_PLAN`. *Crucially, it makes no model writes.* It accepts mappings only if they arithmetically reconcile. 
*   `APPLY_BATCH`: Reads `_PLAN` and mutates the model.
*   `POLICE`: Triggers Excel recalc and checks balances. 

Separating *Plan* from *Apply* creates a transactional boundary, allowing you to reject Agent hallucinations and request human rulings without needing to roll back Excel cell mutations.

### 3. PDF Completeness without code

Without a Python page-walker, you must mathematically prove completeness using the model's **prior-year actuals** as your oracle. 

Do not ask the Agent to "map and extract." Extraction is facts; mapping is a later code-refereed step. Use a forced multi-pass strategy:
1. **Pass 0 (Inventory):** Ask the Agent for a Table of Contents with page ranges. Output a `_TOC` table.
2. **Pass 1 (Extraction):** Loop through the TOC. Send highly scoped prompts: *"Extract the statement on pages 12-14. You must include the column containing 2023 values. Return every row."* Write to `_STAGING`, mandating a `sourcePage` column.

**Proving Completeness:**
*   **Coverage Ratio:** Compare `_STAGING` against expected prior-year keys in `_ANATOMY`. If the BS expected 40 keys and 39 triangulate, the Agent skipped a row. Refuse the write.
*   **Control Totals:** If the disclosure prints "Total Assets = 100", the script must sum the Agent's extracted children to equal 100. If it fails, a child was skipped.
*   **Page Gaps:** If the TOC says Note 4 is on pages 34-37, but `_STAGING` has no rows with `sourcePage` 34-37, the table was skipped, even if other ties pass.

### 4. The mark-to-actual recipe in 120s

`getCellProperties` is dead on arrival for whole-column copies. However, Office Scripts wraps the native Excel C++ engine, giving you a bulk operation that perfectly mimics your Python recipe ("copy formulas+formats, overwrite inputs"):

1. **Bulk Copy:** Target the used range of the prior column, not the whole 1M-row column.
   `dstRange.copyFrom(srcRange, ExcelScript.RangeCopyType.all);`
   *(This copies values, formats, and relative formulas instantly).*
2. **Clear Inputs natively:**
   `dstRange.getSpecialCells(ExcelScript.SpecialCellType.constants).clear();`
   *(This instantly wipes all hardcoded inputs, leaving copied formulas intact. Note: If your model has static assumptions that shouldn't be wiped, ensure they are rewritten from your `_PLAN` or flagged in `_ANATOMY` to be spared).*
3. **Apply _PLAN:** Use a single `setValues()` call to inject the newly mapped inputs into the cleared gaps.

If a sheet is exceptionally massive, mitigate by invoking the `APPLY_BATCH` script panel-by-panel (e.g., Q1, then Q2) in a Flow loop.

### 5. Determinism leaks and the Ledger design

**Where determinism silently dies:**
*   **Excel Recalc Races:** Office Scripts can read values before Excel Online finishes calculating. *Fix:* explicitly call `workbook.getApplication().calculate(Full)` after writes, and if the workbook is still dirty, return `NEED_RECALC` to let the Flow retry.
*   **Mapping Drift:** The Agent maps "SG&A" differently on Tuesday vs. Wednesday.

**The Ledger (`_LEDGER` and `_SPEC` hidden sheets):**
*   **`_SPEC` (The LLM Bypass):** An Excel Table holding Locked Analyst Rulings. Before `VALIDATE_AND_PLAN` asks the Agent to judge an unmapped row, it checks `_SPEC`. If a locked mapping exists, it maps it natively.
*   **`_LEDGER` (The Forensic Trail):** An append-only Excel Table updated during `APPLY_BATCH`. Columns: `runId | utc | scriptVersion | mode | sheet | address | fromHash | toHash | rulingId | ok`. Because you are using the **clone-per-run** mitigation (Q1), you will not have concurrent writers battling over this ledger.

### 6. Phase 1 — What to explicitly NOT attempt

Phase 1 exists to prove the plumbing and the deterministic referee, so that a non-technical intern can paste it together in under an hour. 

**DO NOT attempt:**
*   300-page PDFs, OCR handling, notes, segments, or restatements.
*   Roll-forward logic, true-ups, or panel translation (H1=Q1+Q2).
*   10-sheet workbooks or complex formatting beyond the `copyFrom` bulk operation.
*   k=2 Agent refereeing.
*   Live-file concurrency (always use a cloned file).

**DO attempt (The Phase 1 Scope):**
1. **One cloned workbook, one sheet, ~15 key lines.**
2. **One manually built (or 2-page extracted) `_STAGING` table.** 
3. **One Kernel Script** with two modes: `PREFLIGHT` (discover axes) and `APPLY` (copy prior column -> triangulate 15 inputs directly -> clear constants -> overwrite inputs -> pass/fail).
4. **Flow:** Trigger -> Clone File -> Run Preflight -> Run Apply -> Human Approval Node on the refuse list.
5. **Success criteria:** If the staging data breaks an arithmetic tie, Phase 1 must successfully abort the write and turn the row red. If it cannot refuse a bad write, do not proceed to Phase 2.
