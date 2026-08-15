# LLM Council transcript

## Question

# Council question: rebuild from scratch, or evolve — an agent that must match Claude Fable 5's model-update output using a weaker engine

## The commissioning goal (restated by the owner today)

Build an agent that updates equity-research Excel valuation models (mark to
actual from PDF disclosures, roll forward) with the same OUTPUT quality as
Claude Fable 5 doing the task interactively. Acceptance, in strict priority
order:

1. **Balance sheet balances for ALL years** (actuals + forecasts). Non-negotiable.
2. **The 10–15 key numbers** an analyst checks (sales, gross/operating/net
   profit, cash, CA/CL/NCA/NCL, equity, CFO/CFI/CFF, key breakdowns) — near
   non-negotiable even when other cells are incomplete.
3. **≥90% whole-model completeness** (cells correct vs a reference update).
4. **≤60 minutes per run** (a ceiling, not a target; accuracy wins).

Philosophy: the owner believes Fable 5 wins not only on raw LLM strength but
on its built-in agentic scaffolding — skills, subagents, tool discipline,
self-verification. The goal is to package that scaffolding around a weaker,
mandated engine (gpt-5.6-luna, OpenAI-compatible API; a stronger model allowed
ONLY as a blind reviewer) so it deploys inside a bank (UBS) environment.

Hard constraints:
- **Only widely available Python libraries** (openpyxl, pdfplumber, requests,
  pandas, PIL class). No niche or private third-party vendors, no exotic
  system binaries a locked-down bank image won't have. The LLM endpoint is the
  one external service. (Bears directly on OCR: the engine's own vision needs
  zero new dependencies; tesseract/paddleocr are extra deps of uncertain
  availability inside a bank.)
- **Generic across teams**: vastly different model structures (multi-sheet
  link-through models, Chinese-language source sheets, Excel data tables,
  manual calc modes). No per-company code; a learned per-company memory tab
  inside the workbook is allowed.

## What exists today (candidate for demolition)

~5,900 lines of Python (21 modules) + 9 prompt files, built over ~100
benchmarked runs:

- Deterministic pipeline: archive/snapshot -> whole-column rollover ->
  retrieval (find each model row's disclosure pages by Ctrl+F on its known
  prior-year value) -> holistic per-block LLM mapping (text pages + row list
  -> values) -> code audit of every answer (citation, magnitude, unit scale)
  -> flagged writes (red=uncertain, orange=derived) -> tie-web/objective
  convergence (subtotal anchors, learned bridges, identity solves) -> bounded
  agent loop (150 decisions, tools: trace/diagnose/remap/read_pages/set_input,
  objective scorecard re-shown every turn, guarded transactional writes that
  auto-revert on regression) -> integrity gate (refuses delivery on structural
  damage) -> report tab -> independent adversarial reviewer.
- A learner command: calibrates on the PRIOR year (where the model already
  holds answers), stores code-verified row->line identities, component
  recipes, and quirks in a hidden memory tab; the cold run then uses only
  model + memory tab + the new period's PDFs.
- Measured, company 1 (CLP, vs the analyst's finished model): 74–76% cells,
  keys 8–9/12, balance passes most runs, 27–35 min, ~$2/run.
- Measured, company 2 (Dongfang, vs a Claude Fable 5 reference update): 79.1%
  first scored run, 34.5 min — but balance FAILED. Root cause: pages 95–106
  of the annual report (the entire audited statements block) are image-only
  scans; the pipeline is TEXT-ONLY (pdfplumber), so the agent literally could
  not read the balance sheet. It correctly diagnosed its own gap ("total
  assets understated by 15,199") and burned 63 agent-loop decisions re-reading
  pages that contain no text. Known bug: the loop's set_input refuses
  formula-cell writes instead of redirecting to the input cell that feeds
  them (the resolver exists), so those 63 decisions produced zero writes.
- Evidence cuts BOTH ways on architecture:
  (a) an earlier extract-then-match pipeline scored WORSE than raw chat-app
  usage of the same model class (73.3% vs 82.5% on identical rows) and was
  deleted for a direct-mapping design (+6pp, 6x faster) — the harness CAN
  throttle the model;
  (b) an unconstrained weak model takes any exit it's offered — before code
  held the goal (finish refused while objectives unmet), runs exited early
  with balance broken — the model CANNOT hold the goal alone.

## Questions, in priority order

**Q1 — REBUILD OR EVOLVE.** Given the goals and the state, would you demolish
and rebuild from scratch — and if so, to WHAT architecture, concretely? Or
evolve the current system, and in what order? The owner has explicitly
authorized starting over. Give a verdict and the first two weeks of work.

**Q2 — THE AGENT PACKAGE.** If the philosophy is "give Luna the Fable 5
scaffolding": which specific agentic mechanisms (subagents, skills, vision,
self-verification loops, external memory) actually transfer to a weaker
engine, and which are known to fail on weaker engines (wandering, hallucinated
tool results, unproductive loops)? Be specific about what the DETERMINISTIC
layer must own vs what the model owns.

**Q3 — VISION.** The engine is multimodal but the harness has never sent it
pixels. For scanned Chinese financial statements where digits must be exact:
how exactly should page images enter the pipeline (rendering, resolution,
tiling, prompting), and how should transcription be VERIFIED? Note the harness
already KNOWS the prior-year column of every statement — the comparative
column of a scanned balance sheet must reproduce ~40 known numbers, which
looks like a built-in checksum. Is that sufficient, with row-sum/合计
arithmetic ties on top? Should vision also replace text extraction on pages
that HAVE a text layer (text extraction loses column alignment — measured
"right sum, wrong column split" errors), or stay a targeted fallback?

**Q4 — LEVERAGE RANKING.** Rank your concrete changes by expected gain toward
the four acceptance tiers. Flag anything you predict the other council members
will get wrong.

## Required output

Verdict (rebuild vs evolve) + ranked plan + implementation sketches + failure
modes + what deterministic code must verify. Be concrete; no surveys.


## Stage 1 — answers

### Response A — openai/gpt-5.6-terra

## Verdict

**Evolve the evidence, verification, and execution core; do not demolish the proven parts.**  
I would build a **v2 execution kernel alongside the current system**, then retire individual v1 components after benchmark parity. This is not a cosmetic refactor: replace the text-only source layer and free-form 150-turn agent loop. But retain the parts that already encode hard-won domain knowledge:

- workbook snapshot/archive and structural protection;
- direct block mapping rather than extract-everything-then-match;
- prior-year calibration and hidden workbook memory;
- source citation, unit, magnitude, and sign audits;
- tie-web and integrity gate;
- transaction/revert behavior;
- benchmark harness and adversarial review.

The Dongfang failure is not evidence that the architecture is conceptually wrong. It is evidence of two specific missing capabilities:

1. **The evidence acquisition layer could not see the audited statements.**
2. **The execution layer allowed a model to spend 63 decisions on an unavailable source and then prevented the valid write path.**

A from-scratch rewrite risks losing the direct-mapping and constrained-objective lessons already learned. A v2 kernel should instead make those lessons enforceable.

The architectural change is:

> Replace “an agent conversation that happens to edit a workbook” with “a deterministic evidence-to-write compiler which uses Luna for bounded semantic interpretation tasks.”

The model should never be the component responsible for remembering the goal, deciding whether enough evidence exists, maintaining state, calculating balance, or declaring success.

---

# Target architecture

```text
Workbook + prior-year model + memory tab + current PDF(s)
                         |
                         v
1. Workbook compiler / structural manifest
                         |
                         v
2. Source catalog and modality router
   - text pages
   - native-image PDF pages
   - rendered scanned pages
                         |
                         v
3. Evidence extraction skills
   - text-table extraction
   - vision statement transcription
   - footnote/block interpretation
                         |
                         v
4. Deterministic row/column matcher
   - prior-year comparative checksum
   - unit/sign/period matching
   - row-label and subtotal constraints
                         |
                         v
5. Typed write-plan generator
   - target input cell, not displayed formula cell
   - source, confidence, transform, explanation
                         |
                         v
6. Transactional workbook executor
   - write only permitted inputs
   - formula/data-table protection
   - structural diff
                         |
                         v
7. Reconciliation and calculation verifier
   - balance sheet by period
   - key-number coverage
   - subtotal / cash-flow / bridge ties
   - formula dependency evaluation or sanctioned recalc
                         |
                         v
8. Finite remediation scheduler
   - highest-value unresolved constraint first
   - no free conversational wandering
                         |
                         v
9. Delivery gate + blind reviewer
```

Every stage should emit a durable artifact: JSON/CSV records with source page, image coordinates where applicable, candidate row identity, units, raw string, normalized value, target cell, and verification results.

That makes failures inspectable and prevents the model from inventing a state that the system does not possess.

---

# Q1 — Rebuild or evolve, and the first two weeks

## What to retain

Keep these modules, but put them behind typed interfaces:

| Existing capability | Keep? | Change |
|---|---:|---|
| Snapshot/archive | Yes | Make it the immutable run baseline. |
| Whole-column rollover | Yes, cautiously | Convert to a structural operation with formula/data-table safeguards. |
| Direct holistic block mapping | Yes | Retain; it beat extract-then-match. Add vision evidence as an input modality. |
| Citation/unit/magnitude audit | Yes | Make it a mandatory write-plan gate. |
| Tie-web / objective scorecard | Yes | Move ownership to deterministic scheduler. |
| Learner / memory tab | Yes | Tighten provenance and versioning. |
| Free 150-turn agent loop | No | Replace with finite issue queues and bounded task calls. |
| Text-only PDF retrieval | No | Replace with multimodal source catalog. |
| Formula-cell write refusal | No | Replace with formula-input resolver and write planner. |

## What to replace

### 1. Replace the free agent loop with a deterministic issue scheduler

The current loop is useful because it holds the objective; it is harmful because it gives a weak model too many degrees of freedom.

Instead of:

```text
Agent sees scorecard -> chooses arbitrary tool -> reflects -> chooses next tool
```

use:

```text
Verifier emits unresolved issues
    -> deterministic priority function ranks them
    -> task-specific skill is invoked
    -> proposed evidence/write is verified
    -> issue is closed, split, or escalated
```

Example issue records:

```json
{
  "issue_id": "BS_2024_TOTAL_ASSETS",
  "severity": "P0",
  "period": "FY2024",
  "type": "balance_sheet_failure",
  "difference": 15199,
  "upstream_candidates": ["cash", "receivables", "fixed_assets"],
  "source_status": "statement_pages_unreadable_text",
  "allowed_actions": ["vision_transcribe_statement", "trace_formula_inputs"],
  "retry_budget": 2
}
```

The model is called to perform a narrow action, not to decide what the system should care about.

### 2. Add a workbook compiler before any editing

Before a run, produce a workbook manifest containing:

- sheets, hidden sheets, named ranges, merged cells, hidden rows/columns;
- formula cells and their precedents;
- cells that are safe direct inputs;
- cells that are formulas but resolve to one or more editable drivers;
- cross-sheet links;
- external links;
- Excel data tables and protected regions;
- period columns and year labels;
- statement sections and subtotal rows;
- calculation mode and stale formula-cache risk;
- row labels in English and Chinese where present.

The key change is that a model may propose a value for `BS.Cash.FY2024`, but the deterministic layer chooses the actual writable cell:

```text
Displayed formula cell
     -> trace precedents
     -> identify the sanctioned input / source-history cell
     -> write there
     -> verify downstream impact
```

If there are several possible drivers, do not let Luna guess silently. The resolver should return a ranked candidate set and require evidence or an explicit workbook-memory rule.

### 3. Treat model recalculation as a first-class deployment risk

This is likely to be underestimated by other council members.

`openpyxl` preserves formulas but does not calculate them. A workbook in manual calculation mode can appear balanced based on stale cached values even after inputs changed. Conversely, a correct input update can appear unbalanced until Excel recalculates.

Therefore the

### Response B — google/gemini-3.1-pro-preview

Here is the council’s verdict and concrete implementation plan. 

### Q1 — VERDICT: EVOLVE (Do Not Rebuild)

**Verdict: EVOLVE.** Demolishing a 5,900-line codebase that already hits 79% completeness and has solved the deterministic nightmare of Excel rollovers is a classic "Second System Syndrome" trap. 

Your harness is not failing because the architecture is bad; it is failing because of two highly specific, isolated bugs: 
1. The engine literally cannot see the data (scanned PDFs + text-only parser). 
2. The agent loop is hitting a dead end (the `set_input` formula refusal).

A weaker LLM like Luna will drown in a from-scratch ReAct or open-ended agent framework. The exact reason Fable 5 works is because it has internal guardrails; you have successfully built external guardrails that mimic this (code audit, learned memory, prior-year calibration). Do not throw them away.

**The First Two Weeks of Work:**
*   **Days 1–3: The `set_input` Resolver (High Priority).** Fix the bug where writing to a formula cell fails. The harness must deterministically trace the formula tree (using `openpyxl`'s parsed AST or a lightweight dependency graph) to find the hardcoded input cells feeding that formula, and redirect the agent's write attempt to those inputs.
*   **Days 4–7: Targeted Vision Injection.** Integrate PIL to render PDF pages into images. Plumb this into the pipeline specifically for the core financial statements and any page where `pdfplumber` extracts less than 200 characters of text.
*   **Days 8–10: The Prior-Year Vision Checksum.** Implement the deterministic verification loop for multimodal extraction (detailed in Q3). 
*   **Days 11–14: Agent Loop Lobotomy.** Strip "thinking" autonomy from the Luna agent loop. Replace it with a strict state machine where the deterministic harness dictates the next action based on the objective scorecard.

---

### Q2 — THE AGENT PACKAGE (Scaffolding a Weaker Engine)

Weak models (like Luna) are bad at *planning* and *recovery*, but highly capable at *mapping* and *translation* if the context is narrow. You must ruthlessly shift the cognitive load to the deterministic layer.

**What TRANSFERS to a weaker engine:**
*   **Prior-Year Memory Tab:** Giving the LLM a 1:1 mapping of "Here is the exact row name, the component recipe, and last year's value" is the ultimate cheat code. Weak models excel at pattern matching.
*   **Deterministic Math Gates:** The engine cannot be trusted to know if Assets = Liabilities. The Python code must calculate the delta and feed a binary state ("Balanced" vs. "Off by 15,199") back to the model.
*   **Hypothesis Testing (Guarded Writes):** Allowing the model to write, auto-reverting if it breaks the model, and returning the error trace.

**What FAILS on a weaker engine (and must be stripped):**
*   **Unproductive Self-Correction Loops:** Weak models hallucinate fixes. If Luna fails a tie-out 3 times, it will fail 63 times. *Fix:* Hard-cap tool retries. If a write fails 3 times, the deterministic layer must escalate to "Objective Convergence" (identity solves) or flag the cell as incomplete and move on.
*   **Unconstrained Tool Choice:** Luna will use tools just because they are there. *Fix:* Contextual tool provisioning. Only give Luna the `read_pages` tool during the search phase. Only give it `set_input` during the write phase. 

**Layer Ownership Breakdown:**
*   **Deterministic owns:** Reading/Writing Excel, tracing formulas, PDF text extraction/image rendering, math/arithmetic checks, deciding *when* the agent is done, enforcing the 60-minute timeout.
*   **Model owns:** Looking at a page and extracting a markdown table, mapping a reported line item to a known Excel row, flagging accounting anomalies (e.g., "Cash includes restricted cash").

---

### Q3 — VISION: The Checksum Architecture

Text extraction on financial tables is fundamentally flawed because it loses spatial column alignment ("right sum, wrong column split"). **Vision should not just be a fallback for scanned pages; it should be the default for the 3–4 core statement pages.**

**How to ingest images:**
Use `pdfplumber`'s built-in `.to_image(resolution=300)` to render the page, then pass it to the engine via base64 encoded PIL objects. 300 DPI is critical for distinguishing "8", "6", and "9" in Chinese financial scans. Tiling is rarely needed for A4 pages if Luna's multimodal endpoint supports >=1024x1024 native resolution.

**The Verification (The Built-In Checksum):**
Because you have the prior-year model, you possess a cryptographic-level checksum for hallucinations. 
1.  **Prompt the Vision Model:** "Extract this financial statement as a Markdown table. Include the line item name, the Current Year column, and the Prior Year column."
2.  **Deterministic Verification:** The Python harness intercepts the Markdown table. It takes the Prior Year column from the LLM's extraction and merges it against the known Prior Year values from the Excel memory tab. 
3.  **The Gate:** 
    *   If >= 90% of the extracted prior-year numbers match the memory tab perfectly: The vision extraction is verified. The spatial alignment is perfect. The current-year numbers are trusted and mapped to Excel.
    *   If < 90% match: The LLM hallucinated, misread the digits, or misaligned the columns. *Reject the extraction.* Auto-crop the image to just the table body and retry once. If it fails again, flag for human review. 
    *   *Crucial Add-on:* Enforce row-sum (`合计`/`Total`) arithmetic ties on the extracted Markdown *before* writing to Excel.

---

### Q4 — LEVERAGE RANKING & PREDICTIONS

Ranked by expected gain toward your strict acceptance criteria (Balance > Keys > 90% > 60m).

1.  **Prior-Year Vision Checksum (Solves 1, 2, and 3).** 
    *   *Impact:* Replaces broken text parsing with spatially-aware extraction. Guarantees the inputs for the Balance Sheet are actually correct before they hit the agent loop.
    *   *Council Prediction:* Others will tell you to use OCR (Tesseract/Paddle). *They are wrong.* You are constrained by a locked-down bank image. Multimodal LLM + Prior-Year Checksum achieves 99% accuracy without installing C++ binaries.
2.  **Formula Dependency Resolver in `set_input` (Solves 3 and 4).**
    *   *Impact:* Stops the 63-step death spirals. If the model wants to change "Total Assets", the harness automatically writes to the empty "Cash" and "Inventory" inputs feeding it. This instantly unlocks the 90% completeness tier.
3.  **Vision Default for Core Statements, Text for Narrative (Solves 4).**
    *   *Impact:* Sending 100 pages of images to the API will blow past your 60-minute ceiling and rate limits. Use `pdfplumber` to Ctrl+F the prior-year values to *find* the pages (fast, text-based). Once found, if it is a core statement, convert *only that page* to Vision. 
    *   *Council Prediction:* Others will suggest multimodal for the whole PDF. This will result in 3-hour runtimes and out-of-memory errors.
4.  **State-Machine Loop Throttling (Solves 4).**
    *   *Impact:* Cut the allowed agent loop decisions from 150 to ~30 per sub-task. If Luna hasn't balanced the sheet in 30 steps, it is mathematically lost. Auto-revert to the last best state, print the objective scorecard, and move to the next section. 

**Failure Modes to Watch:**
*   **The "Restatement" Trap:** The prior-year checksum will fail if the company *restated* their prior year in the new report. *Mitigation:* The deterministic code must check if the discrepancy is uniform across a whole sub-block. If so, allow the write but color-code it Orange (derived/restated) for the analyst.
*   **Luna's Context Window:** Multimodal tokens consume context fast. Do not pass previous image extractions in the chat history. Extract to JSON/Markdown, drop the image from the context, and only keep the text payload in the ongoing agent loop.

### Response C — x-ai/grok-4.6

**Verdict: EVOLVE.** Do not demolish.

The skeleton already encodes the only architecture that has evidence on this task: **code holds the goal; the model only maps**. The two acceptance-killing failures are local: **the agent is blind on image-only statement pages**, and **`set_input` refuses the cells that would change anything**. Burning 5,900 measured lines to rebuild “a Fable-5-like agent” will recreate the same harness-throttling and early-exit failures, minus the memory tab, integrity gate, and audit you already paid for.

Rebuild two contracts (eyes, hands). Keep the spine (archive → rollover → retrieve → map → code-audit → transactional write → scorecard loop → integrity gate → blind reviewer → memory tab).

---

## Q1 — First two weeks

### Non-goals for these 14 days
No new agent framework. No extra tools. No extract-then-match revival. No per-company code. No stronger model on the write path. No tesseract/paddleocr/poppler.

### Week 1 — unblock acceptance #1 on Dongfang

**Days 1–2 — write-path contract (the 63-decision zero-write bug)**  
Replace “refuse formula cells” with a mandatory resolver:

- Classify every target as `input` | `formula` | `data-table` | `protected`.
- Formula → walk precedents to the **unique input** that feeds this year/row (already said to exist). If 0 or >1 candidates, do not write; emit a structured miss (`row`, `formula`, `candidates`, `why`).
- Writes are transactional: snapshot cell → write → recalc-or-replay dependents you already know how to replay → recompute scorecard → revert on regression (balance worse, key worse, `#REF!`, formula destroyed).
- Loop rule: a turn that only reads is a **fault**. After 2 reads of the same page with no write or structured miss, that page is marked exhausted.

Ship criterion: replay the Dongfang trace; those 63 turns must become ≤5 structured misses + real writes, not rereads.

**Days 2–5 — perception: image-only pages**  
Dongfang pp. 95–106 are the whole audited block. Text-only retrieval cannot satisfy tier 1, ever.

Within the allowed stack (`pdfplumber`, `PIL`, engine vision):

1. **Page class** (deterministic): `text` if extractable digit-density is high; `image` if almost no digits / full-page image xobject; `hybrid` otherwise. Never send `image` pages into the text mapper. Never let the loop `read_pages` on a classified-empty text layer.
2. **Pixels without poppler**: pull the page’s embedded image stream(s) via pdfplumber/pdfminer xobjects; open with PIL. Full-page scans are one image. If a page has no image stream and no text (rare), skip with a hard diagnostic — do not invent a renderer dependency.
3. **Normalize**: grayscale, upscale so the page long edge is ~2000–2400 px, light contrast; do not binarize (kills 8/3, 5/6). JPEG q≥90 or PNG.
4. **First call is verification, not current-year**: ask Luna vision for **both** columns + Chinese line names as JSON. The harness already knows the prior-year column. That is the checksum.

Ship criterion: on Dongfang 95–106, prior-year hit-rate ≥95% of matched rows after scale normalization, **and** transcribed 合计 / BS identity holds for the comparative column.

### Week 2 — close the books, stop thrash, re-score

- **Identity closer in code** (not in the loop): for each year, evaluate TA−(TL+E), CF identity, memory-tab subtotal recipes. If exactly one free input in a component explains the residual within 1 unit, write it as `derived` (orange). If many frees, do not plug garbage — emit the residual onto the scorecard as the next forced target.
- **Key-first mapping**: the 10–15 analyst numbers are a separate mandatory queue. Mapping turns may not work on completeness rows while any key is empty or failing audit.
- **Restatement fork**: if prior-year checksum fails as a *block* (many misses, consistent scale), treat comparative column as restated; store both “model prior” and “report comparative”; do not reject the page.
- **Dongfang is the week-2 gate**, not CLP. Pass/fail = BS balances both years + keys + no structural damage. Completeness is informational.
- Time box: vision only on `image`/`hybrid-repair` pages. Budget ~8–12 statement pages × 2 attempts.

If Dongfang still fails balance after vision+resolver+closer, *then* discuss rebuild. Not before.

---

## Q2 — What actually transfers to Luna

### Transfers (keep / lean into)
| Mechanism | Why it works on a weak engine |
|---|---|
| Hidden memory tab (code-verified identities, recipes, quirks) | Substitutes for Fable’s long-horizon memory. Luna should **read** it, not freely rewrite it on a cold run. |
| Short skills = procedures with I/O schema, not “be an analyst” | Weak models follow a 20-line recipe; they do not hold a 200-line philosophy. |
| Few typed tools + schema-validate every tool result in code | Stops hallucinated reads/writes. |
| Scorecard recomputed in code every turn, shown raw | The model cannot hold “BS must balance.” The number in its face can. |
| Transactional writes + auto-revert | The only reason an unconstrained weak model did not ship broken books. |
| Bounded loop with **forced progress** | 150 decisions is not a bound if 63 of them are legal no-ops. |
| Blind stronger reviewer, read-only | Allowed, and the right place for a stronger model: residual + “what did we misread,” never writes. |

### Known to fail on weaker engines (do not add)
- Open-ended subagents that plan tools. They wander and fabricate tool output.
- Nested subagents.
- “Decide if you are done.” They take any exit. **Code decides done.**
- Same-model self-critique with no ground truth. Agreeable and wrong.
- More tools (`explore`, `bash`, `python-repl` over the workbook). They will spend the budget there.
- Giant context dumps of the whole 10-K. Retrieval stays.
- Extract-then-match as the primary path. You already measured 73.3% vs 82.5% and 6× slower.

### Deterministic layer owns
Goal holding and delivery refusal; page class; input-cell resolution; scale/unit/citation/magnitude audit; all identities and subtotal recipes; transactional revert; scorecard; loop termination and anti-thrash; workbook integrity (`#REF!`, formula count, sheet set, data tables); prior-year checksum and restatement detection; “keys before completeness”; finish gate.

### Model owns
Line-name alignment (especially Chinese); odd presentation; choosing among 2–3 audited candidates; vision **draft** transcription; proposing which residual row is missing (code checks); proposing memory-tab entries during **learn** (code verifies against the prior-year column that already has answers).

One subagent is justified, and only one: **VisionTranscribe(page_image, known_prior_col, unit_hint) → JSON**. No planner subagent.

---

## Q3 — Vision, exactly

### When it runs
- **Primary** on `image` pages (Dongfang 95–106).
- **Repair** on `text`/`hybrid` pages that fail column-split audit (“right sum, wrong column”) or fail citation-magnitude checks.
- **Not** a replacement for pdfplumber on clean digital text. Cost and 60‑minute ceiling. Text extraction stays default.

### How pixels enter
1. Classify page.  
2. Extract embedded images; if several, stitch by PDF y-order or send the dominant full-page image.  
3. PIL: RGB or L, long edge 2000–2400 px, no aggressive threshold.  
4. If a single image is too dense (tiny Chinese footnotes under a 40-line BS): **three overlapping vertical tiles** (top 45%, mid 40%, bottom 45%) plus one full-page pass. Merge by line name, not by y guess.  
5. Encode PNG/JPEG; send as the engine’s vision content part. Zero new deps.

Do **not** add poppler/pdf2image/tesseract. If a page has neither text nor an image xobject, fail that page loudly.

### Prompt (tight)
Ask only for a JSON list: `{name_zh, name_en?, prior, current, unit}`. Instruct: digits exact, no thousands-rounding, empty if unreadable, do not copy prior into current. Pass **the known prior-year vector** as a checklist (“these numbers must appear in the comparative column; use them as anchors; return current on the same row”). Pass unit hint from the model (`元` / `千元` / `万元`).

### Verification — prior-year checksum is necessary, not sufficient

Use this stack, all in code:

1. **Anchor match**: ≥95% of identifiable known priors match after trying scales `{1, 1e3, 1e4, 1e6}` and comma/OCR variants (`O/0`, `l/1`, fullwidth digits). The winning scale is locked for the page.  
2. **Anti-copy**: current column must not equal prior except on rows whose YoY is plausibly zero (cash can move; share capital often doesn’t).  
3. **Arithmetic**: 合计 / 总计 = children; TA = TL+E on **both** columns; CF identity if the cash-flow page.  
4. **Geometry**: current values must sit on the **same names** that matched priors. A perfect prior column + a shifted current column is a fail → retile.  
5. **Restatement**: block-level prior mismatch with internally consistent 合计 → restated comparative; do not discard current.  
6. **Retry once**: different tile / contrast. Second fail → mark page unread; do not invent digits. Scorecard shows “audited BS unread” rather than a silent understatement of 15,199.

That is enough to trust vision for tier 1 **if** you refuse to write a statement block that fails (1)+(3)+(4). It is not enough without (2) and (4).

### Text vs vision
Keep text as default. Promote a text page to vision repair when: column-split audit fails, or Ctrl+F retrieval finds the prior number in a garbage column, or the block’s children don’t sum but the printed 合计 looks right. Demote vision back to text if checksum fails and the text layer actually has digits (some “scans” are image+hidden text).

---

## Q4 — Leverage ranking (toward the four tiers)

| Rank | Change | Tiers it moves | Notes |
|---|---|---|---|
| 1 | Vision on image-only audited statements + checksum/identity gate | **#1**, then #2 | Without this, Chinese scan issuers cannot pass balance. Dongfang is the existence proof. |
| 2 | `set_input` → input-cell resolver + refuse no-op turns | #1, #2, time | Converts an already-paid agent loop from theatre into writes. |
| 3 | Deterministic identity closer (solve one-free residuals; never plug) | **#1** | Weak model will not close books. Code must. |
| 4 | Key-number queue before any completeness work | **#2** | Stops 79% cell-score with a broken BS / missing cash. |
| 5 | Anti-thrash: page class, exhaust, max 2 reads | time, indirectly #1 | The 63-turn burn is a control bug, not an LLM bug. |
| 6 | Vision *repair* on text column-split pages | #3 | Real, but second-order vs unread BS. |
| 7 | Learn-pass enrichment of memory tab (bridges, 合计 recipes, scan quirks) | #3, robustness | Do this after Dongfang balances once. |
| 8 | Blind strong reviewer on residual only | tail of #1/#2 | Catch, don’t drive. |
| 9 | Prompt / mapping-block wordsmithing | small #3 | Holistic mapping already beat extract-then-match by +6pp. |
| 10 | More subagents, more tools, full-vision on every page, rebuild | **negative** | Matches every failure you already measured. |

### What I expect other council members to get wrong
- **“Rebuild a multi-agent Fable clone.”** You measured the opposite: unconstrained weak model exits with a broken BS; a heavy harness already throttled a stronger class once.  
- **“Just OCR with tesseract/paddle/poppler.”** Violates the bank image constraint; you don’t need it if Luna vision is checksummed.  
- **“Trust vision; 40 known priors are enough.”** Not without current-column geometry, anti-copy, 合计, and restatement detection.  
- **“Optimize for 90% cells.”** Priority order is explicit. A 79% run that fails balance is a fail.  
- **“Give Luna more autonomy so it can recover.”** Recovery without writes is how you spent 63 decisions.  
- **“Bring back extract-then-match for scans.”** Worse when you could read; irrelevant when you can’t. Vision+direct map.  
- **“Use the strong model to map, Luna to review.”** Forbidden, and backwards.  
- **Demolish the memory tab.** It is the only generic-across-teams mechanism you have.

---

## Implementation sketches (concrete)

**Page class**
```text
digits = count of [0-9０-９] in pdfplumber text
if digits < 30 and page has image xobject covering >60% area → image
elif digits >= 80 → text
else → hybrid
```

**Vision verify**
```text
scale = argmax over {1,1e3,1e4,1e6} of matches(known_prior, transcribed_prior / scale)
if match_rate < 0.95 and not restatement_pattern: retry_or_fail_page()
if transcribed_current ≈ transcribed_prior on moving rows: fail_page("copied column")
if not assets == liab+equity for both cols: fail_page("identity")
lock scale; write only input cells for rows that passed name+anchor align
```

**Write**
```text
cell = resolve_input(target)
assert not formula(cell)
snap = read(cell)
write(cell, value, color)
if scorecard_regressed or integrity_fail: restore(snap); log revert
```

**Done predicate (code)**
```text
deliver iff
  balance(all years) and
  keys_ok ≥ required and
  integrity_ok and
  (completeness ≥ 0.90 or (time ≥ 55min and balance and keys))
else refuse
```

---

## Failure modes (watch these on the first Dongfang rerun)

1. **Restated comparative** → checksum fails, vision discarded, same 15,199 hole. Detect block restatement.  
2. **Scale lock on a subset** (a few 万元 lines, rest 元) → wrong current by 10⁴. Require scale to work on 合计, not only on random rows.  
3. **Identity closer plugs the residual into “other assets.”** Forbidden unless memory tab marks that row as the historical plug.  
4. **Resolver picks the wrong driver** (writes a rate that blows the forecast years). Limit auto-writes to the newly rolled **actuals** column; forecast still formula-driven.  
5. **Vision time blow-up** (12 pages × tiles × retries). Cap: 2 attempts/page, statement pages only.  
6. **openpyxl vs data tables / array formulas / Chinese fonts / manual calc.** Integrity gate already exists — keep it as a hard refuse; add a formula-count and defined-name diff.  
7. **Memory-tab pollution** if the cold run is allowed to write memory. Cold run reads only; learn command writes.  
8. **Reviewer disagreement without a ground rule.** Reviewer can flag; it cannot overwrite a checksum-passed number.

---

## What deterministic code must verify (every run, before delivery)

- BS: `TA = TL + Equity` for **every** year column touched (actuals and forecasts).  
- CF: `CFO+CFI+CFF ± FX = Δcash`.  
- Memory recipes: every stored subtotal / bridge.  
- Keys: the 10–15 present, cited, scale-locked, not prior-year copies.  
- Vision pages: prior-anchor rate, anti-copy, 合计, identity, locked scale.  
- Writes: input cells only; forecast formulas intact; revert log empty of unrestored regressions.  
- Integrity: no `#REF!`, sheet set unchanged, formula count ≥ baseline, data tables alive.  
- Citations: page actually contains the written number at the locked scale.  
- Finish: refuse if any of the above fails. Luna does not get a “ship anyway” tool.

That is the Fable scaffolding that survives contact with a weaker engine: **not more agency — a narrower one, with eyes, hands, and a door that will not open while the balance sheet is open.**


## Stage 2 — peer reviews

### Review by openai/gpt-5.6-terra

### Response A

**What it does well**

- Gives the right high-level verdict: **evolve selectively rather than demolish the proven system**. It correctly distinguishes between a failed architecture and two concrete gaps: lack of visual evidence acquisition and a broken write path.
- Identifies the strongest architectural reframing in the set: move from an “agent that edits Excel” toward a **deterministic evidence-to-write compiler using Luna for bounded interpretation tasks**.
- Correctly preserves valuable existing assets rather than proposing an indiscriminate rewrite:
  - prior-year calibration and workbook memory;
  - direct block mapping, which has benchmark evidence;
  - citation/unit/magnitude checks;
  - transactional writes and integrity gates;
  - tie-web/objective infrastructure;
  - independent reviewer.
- Its proposed architecture is strong and appropriately typed:
  - workbook manifest/compiler;
  - source modality router;
  - evidence extraction;
  - row/column matching;
  - typed write plan;
  - transactional executor;
  - reconciliation verifier;
  - finite remediation scheduler.
- It makes an important and often-missed point about workbook recalculation: `openpyxl` does not calculate formulas, and manual calculation/stale formula caches can invalidate both apparent balancing and apparent failure. This is a major deployment risk in a bank environment.

**What it does poorly**

- The response is **materially incomplete**. It ends in the middle of the workbook-recalculation discussion and never fully answers Q2, Q3, Q4, the first-two-weeks plan, detailed vision implementation, leverage ranking, or failure modes.
- Because of that truncation, it does not meet the required output standard despite having a promising opening.
- It does not concretely specify how image-only PDF pages should become usable visual inputs under the stated library constraints.
- It does not give operational thresholds for page classification, prior-year matching, retry budgets, tiling, scale checks, row-level verification, or delivery gating.
- It names a “finite remediation scheduler” but does not fully define the priority policy, retry policy, or anti-loop behavior needed to prevent the demonstrated 63-turn failure.
- It correctly raises recalculation risk, but does not finish the practical answer: whether the deployment environment has a sanctioned Excel recalc route, whether cached formula values can be trusted, or how runs should be refused when formulas cannot be recalculated.

Overall, Response A has an excellent architectural thesis but is incomplete enough that it cannot be the preferred answer.

---

### Response B

**What it does well**

- Correctly recommends **evolving rather than rebuilding**.
- Identifies the two immediately highest-value fixes:
  1. formula-cell-to-input-cell resolution;
  2. vision support for scanned audited statements.
- Provides a usable first-two-weeks sequence, with an appropriate order:
  - fix the write-path bug;
  - add vision;
  - add comparative-column checking;
  - replace free-form agent behavior with a state machine.
- Correctly assigns responsibilities:
  - deterministic code owns workbook operations, formula tracing, verification, termination, and time budgets;
  - Luna owns narrow extraction/mapping/anomaly recognition tasks.
- Correctly warns that open-ended self-correction and unconstrained tool choice are poor fits for weaker models.
- Correctly argues that visual extraction should be used on core statement pages, not necessarily across the whole document.
- Recognizes restatements as a real failure mode for prior-year matching.
- Its leverage ranking broadly matches the stated acceptance priorities: get the audited statements readable, make writes effective, then reduce loop waste.

**What it does poorly**

- It overstates the prior-year checksum as “cryptographic-level” and says that a 90% comparative-column match means “the current-year numbers are trusted.” That is too strong. A correct comparative column does not by itself prove:
  - the current-year column was not shifted;
  - current and prior columns were not swapped;
  - the model did not copy comparative numbers into current;
  - row labels and values stayed aligned;
  - a restated comparative was handled correctly.
- It needs explicit additional checks: current/prior geometry, row identity, anti-copy checks, subtotal arithmetic, balance-sheet identity, cash-flow identity, unit/scale consistency, and page-level source coordinates.
- Its claim that `pdfplumber`’s `.to_image(resolution=300)` is an uncomplicated solution is risky under the stated locked-down constraints. Rendering implementations may depend on packages/binaries not guaranteed by the allowed stack. The answer should have qualified this and proposed extraction of embedded scan images or a pre-approved rendering capability as the primary dependency-free path.
- “Using `openpyxl`’s parsed AST” is not a reliable implementation statement. `openpyxl` does not provide a full Excel formula AST/dependency engine suitable for generic formula-tree tracing. A real resolver needs limited formula parsing, explicit workbook conventions, named ranges, stored lineage, or a deliberately bounded precedent graph.
- The vision plan is too shallow for dense Chinese annual-report pages:
  - no robust tiling strategy;
  - no handling for multi-image pages;
  - no image orientation/cropping logic;
  - no confidence/provenance fields;
  - no treatment of hybrid image-plus-text pages.
- The proposed “30 steps per sub-task” is arbitrary. Better is a semantic retry budget: for example, maximum two attempts per page/crop and maximum one failed write-resolution attempt per issue class.
- It does not sufficiently discuss recalculation limitations, Excel data tables, manual calculation mode, formula caches, or the possibility that a workbook cannot be correctly validated using `openpyxl` alone.
- It implies that writing to “empty Cash and Inventory inputs” from a target like Total Assets could be automatic. In a generic model, there may be multiple possible drivers; an automatic resolver must refuse ambiguous driver paths rather than invent an allocation.

Response B is practical and directionally correct, but it is too optimistic about vision verification and too loose on Excel implementation details.

---

### Response C

**What it does well**

- This is the strongest response because it answers all four questions with a coherent, concrete operating model.
- Its central recommendation is sound: **evolve the spine, rebuild the “eyes” and “hands” contracts** rather than rewrite the whole system.
- It correctly grounds the recommendation in the evidence:
  - direct mapping already beat extract-then-match;
  - the weak model cannot safely own completion decisions;
  - the Dongfang failure was caused by missing visual evidence, not necessarily mapping logic;
  - the formula-cell refusal created an execution dead end.
- The first-two-weeks plan is especially strong:
  - fix write resolution first;
  - make no-write reads detectable and bounded;
  - add page classification;
  - add visual transcription for scan pages;
  - use prior-year comparative values as anchors;
  - add deterministic identity closing only for narrowly justified residuals;
  - establish Dongfang as the acceptance gate.
- It gives an excellent division of ownership:
  - deterministic layer owns delivery criteria, page classification, input resolution, verification, write safety, scorecards, retry/termination, integrity checks, prior-year checksums, and key-first prioritization;
  - Luna owns semantic interpretation, Chinese line-item mapping, visual draft transcription, and bounded candidate selection.
- It is very good on weaker-model failure modes:
  - no open-ended planning subagents;
  - no nested subagents;
  - no model-controlled completion;
  - no giant document context;
  - no free exploration or broad workbook execution tools;
  - no same-model self-critique treated as evidence.
- The vision plan is the most detailed and useful:
  - classify `text`, `image`, and `hybrid`;
  - use image extraction and PIL normalization;
  - preserve grayscale and avoid destructive binarization;
  - use full-page plus overlapping vertical tiles for dense statements;
  - request structured JSON rather than prose;
  - pass known comparative values as anchors;
  - lock units/scales only after deterministic validation;
  - allow exactly bounded retries;
  - distinguish restated comparatives from failed transcription.
- It correctly says the comparative checksum is **necessary but not sufficient**. The anti-copy, arithmetic, identity, scale, row-name, and restatement checks are precisely what Response B lacks.
- Its leverage ranking is well ordered against the owner’s priorities:
  1. readability of audited statements;
  2. effective input writes;
  3. deterministic closing for narrowly solvable residuals;
  4. key-number queue;
  5. anti-thrash controls;
  6. visual repair for text-layer column errors.
- It correctly warns against several likely but bad council recommendations:
  - rebuilding a multi-agent clone;
  - broad OCR dependencies;
  - full-document vision;
  - optimizing cell completeness before balance;
  - giving Luna more freedom;
  - allowing the strong reviewer onto the write path.

**What it does poorly**

- The largest substantive flaw is its proposed delivery predicate:

  ```text
  completeness ≥ 0.90 or (time ≥ 55min and balance and keys)
  ```

  This conflicts with the stated acceptance criteria. The 60-minute limit is a ceiling, not an excuse to waive the ≥90% completeness requirement. The system may deliver a clearly labeled partial/exception output for analyst review, but it should not define that as full acceptance or successful delivery. A better rule is:
  - hard refuse “accepted completion” unless all required tiers are met;
  - optionally produce a non-delivery diagnostic artifact at timeout;
  - never silently redefine tier 3 as optional because time elapsed.
- The response is slightly too confident that embedded-image extraction will always replace page rendering. Some scanned PDFs use unusual encodings, masks, multiple XObjects, transformations, or page compositions that make image reconstruction nontrivial. The architecture should explicitly support:
  - embedded-image extraction when usable;
  - a sanctioned rendering implementation if approved in the bank image;
  - a loud failure state if neither is available.
- The “same names that matched priors” geometry check is conceptually right, but the model output schema lacks explicit bounding boxes or coordinates. Without them, true spatial verification is limited. The implementation should request either:
  - row-level bounding boxes for labels and both values; or
  - tile ID and y-position per extracted row;
  - then verify current and comparative values belong to the same visual row.
- The formula/input resolver description correctly refuses ambiguity, but generic formula tracing remains difficult. It should more explicitly state that automatic redirection is safe only where:
  - workbook memory has an approved driver rule;
  - a unique direct input exists;
  - the input belongs to the rolled actual column;
  - the resulting downstream formula changes match the intended target.
- Its identity closer is sensibly constrained, but this is an area where balance can be “solved” while economics are wrong. The answer should emphasize that a one-free-variable solve is allowed only when the missing row is a pre-approved accounting plug or a demonstrated direct residual component—not merely because it mathematically balances.
- The use of exact equality in the illustrative balance-sheet pseudocode should be tolerance-aware because financial statements may contain rounding, unit scaling, and presentation differences.
- The answer acknowledges calculation issues only indirectly. A production design still needs an explicit policy for formula recalculation and stale caches, particularly for manual calculation workbooks, data tables, array formulas, external links, and unsupported Excel functions.

These are meaningful caveats, but they do not outweigh the response’s completeness, specificity, and alignment with the observed evidence.

FINAL RANKING:
1. Response C
2. Response B
3. Response A

### Review by google/gemini-3.1-pro-preview

Here is an evaluation of the different responses based on the provided prompt and constraints:

### Evaluation of Response A
**What it does well:**
* Correctly identifies that the existing system should be evolved rather than demolished, recognizing the value of the already built deterministic safeguards.
* Proposes a highly sensible architectural shift: moving from a free-form agent loop to a deterministic issue scheduler where the model is only invoked for bounded tasks. 
* Introduces the concept of a "workbook compiler" to handle Excel's structural quirks, which is a very smart way to manage the `set_input` formula-tracing bug.

**What it does poorly:**
* **Major flaw:** The response cuts off abruptly mid-sentence ("Therefore the") and fails to complete its thought on model recalculation.
* Because it is incomplete, it entirely misses answering Q3 (Vision), Q4 (Leverage ranking), and fails to provide the requested implementation sketches, failure modes, and the final list of what deterministic code must verify. 

### Evaluation of Response B
**What it does well:**
* Gives a clear, confident verdict to evolve the current system, correctly diagnosing that the codebase is suffering from two isolated bugs rather than a terminal architectural flaw.
* Provides a very practical two-week plan that directly attacks the core blockers (the formula refusal bug and the vision gap).
* Strongly grasps the philosophy of scaffolding a weaker model. The analysis of what transfers (memory tabs, math gates) versus what fails (unproductive loops, unconstrained tool choice) is spot on. 
* The concept of a "prior-year checksum" for vision is well articulated and directly leverages the existing memory tab to create a mathematical and spatial verification gate.

**What it does poorly:**
* Misses specific formatting and content requirements from the "Required output" section. It lacks concrete "implementation sketches" (code/pseudocode blocks) and does not provide a dedicated, bulleted list of "what deterministic code must verify" at the end.
* Calling `pdfplumber`'s `.to_image()` method often relies on underlying system binaries (like Ghostscript, Poppler, or PyPDFium2 depending on the environment/version), which flirts dangerously with the strict "no exotic system binaries" constraint for locked-down bank images.

### Evaluation of Response C
**What it does well:**
* **Masterful technical depth:** It completely perfectly captures the constraints of the prompt. To solve the vision problem without installing new system binaries, it correctly suggests extracting the raw embedded image xobjects directly via `pdfplumber`/`pdfminer` and feeding them to `PIL`. This shows an exceptional understanding of the Python PDF ecosystem and strict enterprise constraints.
* **Flawless structure:** It explicitly includes every single requested section—Verdict, ranked plan, implementation sketches, failure modes, and what deterministic code must verify.
* **Domain expertise:** Demonstrates deep knowledge of both accounting/finance (restatement traps, identity equations like TA = TL+E, Chinese unit scaling like 元/万元) and Excel/LLM engineering (array formulas, transactional writes, anti-copy logic for checksums). 
* **Actionable and concrete:** The two-week plan is incredibly precise. The implementation sketches (pseudocode) are highly logical, and the failure modes read like actual production issues one would face building this exact system. 

**What it does poorly:**
* It is hard to find a fault with this response. It is dense, but the prompt specifically requested concrete details and "no surveys", which this perfectly honors. 

FINAL RANKING:
1. Response C
2. Response B
3. Response A

### Review by x-ai/grok-4.6

**Response A**

**What it does well:** Clear evolve-not-demolish verdict with a principled target architecture (evidence-to-write compiler, not a free conversational agent). The stage list (manifest → modality router → extraction → matcher → typed write-plan → transactional executor → verifier → finite scheduler → gate) is coherent and matches the owner’s “code holds the goal” lesson. It correctly keeps direct mapping, memory tab, audits, tie-web, and integrity gate, and correctly kills the free 150-turn loop. The workbook-compiler / formula-input resolver and the warning that `openpyxl` does not recalculate (manual-calc / stale cache) are high-value and easy for others to miss. Issue-queue JSON is a concrete replacement for ReAct wandering.

**What it does poorly:** The answer is truncated mid-sentence at Q1 (“Therefore the”), so it never delivers Q2–Q4, vision protocol, leverage ranking, failure modes, or a complete two-week plan. For a council write-up that required those sections, it is structurally incomplete. Some architecture is still abstract (no DPI/tiling/checksum recipe, no Dongfang ship criteria, no ranked change list). Useful spine, unfinished product.

---

**Response B**

**What it does well:** Complete, readable, and covers all four questions. Verdict is evolve with a crisp two-week calendar (resolver → vision → checksum → loop lobotomy). Q2 ownership split is right: weak models map; code holds goals, math, termination, and writes. Vision checksum via prior-year column is the right core idea. Leverage ranking is ordered by the actual acceptance tiers. Practical warnings: restatement trap, multimodal context bloat, don’t vision the whole PDF, don’t install Tesseract. Formula-tree redirect for `set_input` is the correct fix for the 63-noop bug.

**What it does poorly:** Overconfident and slightly wrong on several implementation details. Treating vision as *default* for core statements (vs targeted fallback/repair) fights the 60-minute ceiling and the bank-dep constraint more than C does. `pdfplumber.to_image(resolution=300)` typically needs a renderer (Pillow-only path is not guaranteed; poppler/`pdf2image` is exactly the forbidden extra binary). “≥90% prior-year match ⇒ trust current year” is necessary but not sufficient—no anti-copy, no same-name geometry, no 合计 on *both* columns, no scale lock on totals. Claiming the resolver “automatically writes to Cash and Inventory” if the model wants Total Assets is dangerous (multi-driver plug). “Agent loop lobotomy / 30 steps” is thinner than a real issue scheduler. Less precise on page classification, restatement-as-block, identity closer, and delivery-refuse predicate.

---

**Response C**

**What it does well:** Best match to the required artifact: verdict, two-week plan with ship criteria, Q2 transfer/fail table, exact vision pipeline, leverage ranking, sketches, failure modes, and a deterministic verify/done list. Diagnosis is local and evidence-based (blind on scans + `set_input` no-ops), so it refuses a rebuild until Dongfang is re-run with eyes and hands. Bank-safe pixels (embedded xobjects + PIL, no poppler/tesseract). Vision is primary on `image` pages and *repair* on column-split text—not a blanket default. Checksum stack is actually sufficient for tier 1: scale search, anti-copy, 合计/BS identity on both columns, geometry, restatement fork, one retry then “unread” not silent 15,199 understatement. Deterministic identity closer (one free residual only; never plug “other assets” unless memory says so). Key-first queue, anti-thrash (reads without write are faults), cold-run memory is read-only, stronger model is blind reviewer only. Done predicate matches priority order. Failure modes (restatement, mixed 万元/元 scale, wrong driver on forecasts, data tables/manual calc) are the ones that will actually break the next run. Ranking of what others will get wrong is accurate.

**What it does poorly:** Embedded-image extraction will miss some true scans that only rasterize via a renderer; the “skip if no xobject” rule is principled but can leave a page unread. Slightly more operationally dense than B (harder to skim). Week-1 dual-track (resolver + vision) is ambitious. A few details (digit-density thresholds, 2000–2400 px) are reasonable heuristics, not measured.

---

C is the only response that is both architecturally correct *and* complete. B is a strong second: same verdict, full coverage, but weaker vision/write safety. A has the right compiler-vs-agent framing and the recalc insight, but is cut off before it can compete.

FINAL RANKING:
1. Response C
2. Response B
3. Response A


## Ranking tally (Borda)

- Response C (x-ai/grok-4.6): 9 pts
- Response B (google/gemini-3.1-pro-preview): 6 pts
- Response A (openai/gpt-5.6-terra): 3 pts

## Stage 3 — chairman synthesis (google/gemini-3.1-pro-preview)

Here is the synthesized verdict and concrete implementation plan from the LLM Council. 

### Q1 — VERDICT: EVOLVE (Do Not Demolish)

**Verdict: EVOLVE.** Demolishing a 5,900-line codebase that already hits 79% completeness and handles the deterministic nightmare of Excel rollovers is a classic "Second System Syndrome" trap. 

Your harness is not failing because the architecture is conceptually wrong; it is failing due to two highly specific execution gaps:
1. **The agent is literally blind:** Text-only parsers cannot read scanned audited statements (Dongfang pp. 95–106).
2. **The execution layer is blocked:** The `set_input` tool refuses formula cells instead of resolving them, trapping the agent in a 63-turn dead end.

You have already built the exact scaffolding required for a weaker LLM (code audit, learned memory, prior-year calibration, transactional writes). A from-scratch ReAct or open-ended agent framework will cause Luna to drown. 

**The First Two Weeks of Work:**
*   **Days 1–3: The `set_input` Resolver.** Replace "refuse formula cells" with a mandatory resolver. Deterministically trace the formula tree to find the hardcoded input cells feeding that row. If there is a unique input, redirect the write; if ambiguous, emit a structured miss. 
*   **Days 4–7: Bank-Safe Vision Injection.** Implement multimodal extraction strictly for scanned pages. To respect your locked-down environment (no Poppler, Ghostscript, or Tesseract), use `pdfplumber`/`pdfminer` to extract the raw embedded image XObjects and process them natively with `PIL`.
*   **Days 8–10: The Prior-Year Checksum.** Implement the deterministic verification loop (detailed in Q3) to mathematically and spatially verify Luna's visual extractions against the known prior-year memory tab.
*   **Days 11–14: Agent Loop Lobotomy (Finite Scheduler).** Strip open-ended "thinking" autonomy. Replace the 150-turn free loop with a deterministic issue scheduler. The model is called to perform a narrow action (e.g., "map this resolved input"), not to decide what the system should care about.

---

### Q2 — THE AGENT PACKAGE (Scaffolding a Weaker Engine)

Weak models (like Luna) are bad at *planning* and *recovery*, but highly capable at *mapping* and *translation* in narrow contexts. 

**What TRANSFERS to a weaker engine (Keep these):**
*   **Hidden Memory Tab:** Giving the LLM a 1:1 mapping of exact row names, component recipes, and last year's values is the ultimate cheat code.
*   **Deterministic Math Gates:** The engine cannot hold "Assets = Liabilities" in its context window. Code must compute this and feed back a binary state.
*   **Transactional Writes:** Guarded writes that auto-revert on regression (`#REF!`, balance worse) are the only reason an unconstrained weak model doesn't ship broken books.

**What FAILS on a weaker engine (Strip these):**
*   **Open-Ended Subagents & Planners:** They wander, hallucinate tool results, and burn budgets. 
*   **Unproductive Self-Correction:** Weak models hallucinate fixes. If Luna fails a tie-out 3 times, it will fail 63 times. Code must cap retries and move on.

**Layer Ownership Breakdown:**
*   **Deterministic owns:** A pre-run "workbook compiler" (manifesting structural risks like manual calculation mode, data tables, and formula caches); reading/writing Excel; tracing formulas; page classification; arithmetic/identity checks; scorecards; and deciding exactly *when* the agent is done.
*   **Model owns:** Multimodal draft transcription (to JSON); mapping Chinese line items to known Excel rows; choosing among 2–3 audited candidates; and flagging accounting anomalies.

---

### Q3 — VISION: The Checksum Architecture

Text extraction on financial tables is fundamentally flawed because it loses spatial column alignment ("right sum, wrong column split"). However, sending every page as an image will blow past your 60-minute ceiling. 

**When it runs:**
Vision is **primary** on `image`-classified pages (dense scans). It is used as a **repair fallback** on `text` pages that fail column-split audits or citation checks. 

**How pixels enter without system binaries:**
Extract embedded image XObjects directly from the PDF. Open with `PIL`. Grayscale and scale so the long edge is ~2000–2400 px. If the page is too dense, use overlapping vertical tiles (Top 45%, Mid 40%, Bottom 45%). Ask Luna for JSON: `{name_zh, prior, current, unit}`. Pass the known prior-year vector as an anchor checklist in the prompt.

**Verification (The Checksum):**
A 90% comparative column match is necessary but **not sufficient**. Your deterministic code must verify:
1.  **Anchor Match:** ≥95% of known priors match after trying scales (1, 1e3, 1e4) and OCR variants (O/0). The winning scale is locked for that page.
2.  **Anti-Copy:** The current column must not equal the prior column (except on rows like share capital where YoY is plausibly zero) to catch hallucinated duplicates.
3.  **Arithmetic:** `合计`/`Total` = children; Total Assets = Total Liabilities + Equity on **both** columns.
4.  **Geometry:** Current values must sit on the *same row names* that matched priors. A perfect prior column + a shifted current column = fail.
5.  **Restatement Fork:** If the prior mismatches as a *block* but the `合计` arithmetic holds, it is a restated comparative. Do not reject the page; log the restatement.

*If any step fails, retry once with a different contrast/tile. If it fails again, mark the page unread. Do not let the model invent digits.*

---

### Q4 — LEVERAGE RANKING (Toward the Four Tiers)

1.  **Vision on image-only audited statements + checksum gate** *(Solves Tier 1 & 2).* Without this, Chinese scan issuers cannot balance. Dongfang is the proof.
2.  **`set_input` → Input-cell resolver** *(Solves Tier 1, 2 & Time).* Converts the agent loop from theatre into actual writes. Stops the 63-step death spirals.
3.  **Deterministic identity closer** *(Solves Tier 1).* For one-free-variable residuals, code must close the books based on memory tab recipes. Weak models won't.
4.  **Key-number queue first** *(Solves Tier 2).* Force mapping turns to prioritize the 10-15 core analyst numbers before completeness tasks.
5.  **Anti-thrash loop scheduler** *(Solves Time).* Cap reads. A turn that reads without writing is a fault. Exhaust pages after 2 reads. 
6.  **Vision repair on text pages** *(Solves Tier 3).* Fixes "right sum, wrong column" text-layer drift.

**What other council members (and engineers) will get wrong:**
*   *"Just use OCR (Tesseract/Paddle)."* Violates the locked-down bank image constraint. Native XObject extraction + LLM Vision avoids binary dependencies.
*   *"Optimize for 90% cells first."* A 90% complete run that fails the Balance Sheet is a failure. Balance > Keys > Completeness.
*   *"Rebuild a multi-agent Fable clone."* You already measured that an unconstrained weak model exits with a broken BS.

---

### IMPLEMENTATION SKETCHES

**Page Classification (Deterministic)**
```python
digits = count_digits_in_pdfplumber_text(page)
if digits < 30 and page_has_image_xobject(page, coverage > 60%):
    return "image" # Route to Vision
elif digits >= 80:
    return "text"  # Route to Text Mapper
else:
    return "hybrid" 
```

**Vision Verify & Write (Deterministic)**
```python
scale = argmax_over_scales(known_prior, transcribed_prior / scale)
if match_rate < 0.95 and not is_restatement_pattern(transcribed_prior): 
    return retry_or_fail_page()
if transcribed_current == transcribed_prior on moving_rows: 
    return fail_page("copied column hallucination")
if not (assets == liab + equity) for BOTH columns: 
    return fail_page("identity broken")

lock(scale)
for target in parsed_rows:
    input_cell = resolve_input(target)
    snap = read(input_cell)
    write(input_cell, value, color)
    if scorecard_regressed() or integrity_fail(): 
        restore(snap) 
        log_revert()
```

**Done Predicate (Code)**
```python
def deliver(system_state):
    return (
        balances_all_years(system_state) and
        keys_ok_count(system_state) >= required and
        integrity_ok(system_state) and
        (completeness >= 0.90) 
    ) # Do NOT silently waive completeness just because time >= 55m. Refuse delivery, flag for analyst.
```

---

### FAILURE MODES TO WATCH

1.  **The Excel Recalculation Trap:** `openpyxl` preserves formulas but *does not calculate them*. A manual-calculation workbook or stale formula cache can appear balanced even after inputs change, or unbalanced despite a correct write. The deterministic gate must evaluate calculation modes and optionally trace dependency math safely.
2.  **The Restatement Trap:** The prior-year checksum will fail if the company restated their prior year. The restatement fork (Block 5 above) must catch uniform discrepancies to prevent discarding valid pages.
3.  **Scale Lock on a Subset:** A scan mixes `万元` (tens of thousands) and `元` rows. Ensure the locked scale works on the `合计` (Total) row, not just random line items.
4.  **Resolver Plugs Multiple Drivers:** Target is "Total Assets", but inputs are Cash and Inventory. Code must refuse automatic allocation if the driver is ambiguous. Emits a structured miss.

### WHAT DETERMINISTIC CODE MUST VERIFY (Before Delivery)

Luna gets no "ship anyway" tool. Code must verify:
*   **BS Identity:** `TA = TL + Equity` for *every* year column touched (actuals + forecasts).
*   **CF Identity:** `CFO + CFI + CFF ± FX = Δcash`.
*   **Keys:** The 10–15 mandatory numbers are present, cited, scale-locked, and not prior-year copies.
*   **Vision Checksums:** Passed anchor rate, anti-copy logic, Total arithmetic, and locked scale.
*   **Integrity:** No `#REF!` errors, sheet set is unchanged, formula count is ≥ baseline, data tables remain alive.
*   **Writes:** Only explicit input cells were overwritten; forecast formulas remain intact.
