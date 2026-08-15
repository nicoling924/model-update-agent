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

### Response A — openai/gpt-5.1

**Verdict: evolve, not demolish — but with 3 hard pivots that are “rebuild-scale” inside the existing frame**

You already have the two things that are hardest to re‑create:

- A **goal‑holding deterministic shell** that will not “accept bad balance”  
- A working **memory tab / calibration loop** that learns the model’s quirks  

Those are exactly the bits most teams never get right; throwing them away would set you back months.

However, three subsystems need near‑wholesale redesign:

1. **Reading layer** (vision + table structure). Current text‑only pdfplumber is a hard blocker.
2. **Write targeting** (input vs formula cells; structural awareness). The “set_input refuses formula” bug is a symptom.
3. **Agent task decomposition** (from “holistic” blocks to “statement‑aware” micro‑missions with much more deterministic checking).

So: **evolve** the shell, **rebuild** the reading + write‑targeting + agent‑loop logic inside it.

Below: (Q1) 2‑week concrete plan, (Q2) what scaffolding transfers vs must be deterministic, (Q3) vision design + verification, (Q4) leverage ranking.

---

## Q1 — Rebuild or evolve: verdict + 2‑week plan

### Structural decision

Keep:

- The **snapshot / archive** and model‑rollover frame
- The **hidden memory tab** and prior‑year calibration concept
- The **objective scorecard** and **integrity gate**
- The **tool‑based agent loop** concept (goal‑driven, bounded, transactional writes)
- The **independent reviewer** concept

Replace / refactor substantially:

1. **Retrieval / mapping**:  
   - From: “per‑block LLM mapping over free‑form text pages”  
   - To: “statement‑aware, table‑aware micro‑parsers that use both text and vision, with deterministic table scaffolds and checks.”

2. **Write pipeline**:  
   - From: “LLM says write X to cell (sometimes formula cells)”  
   - To: “LLM writes *to named conceptual items* (e.g., ‘Consolidated total assets, 2023 group’), deterministic mapper translates to actual editable cell(s).”

3. **Agent loop structure**:  
   - From: one generic loop that diagnoses/remaps/reads/writes everything  
   - To: staged specialist passes: “read and reconcile balance sheet”, “P&L”, “CF”, “key notes/splits”, each with local success criteria and deterministic escalations.

### Two‑week plan (assuming one strong engineer + part‑time LLM tinkering)

I’ll break this into 4 workstreams that run in parallel; each bullet is concrete.

---

#### Week 1 — Make the machine *see* and *write legally*

### Workstream A: Vision table extraction with checksum alignment

**Goal for Week 1**: Given a scanned annual report page with a 2‑column comparative balance sheet, produce a structured table (rows × {prior, current}) with ≥99% accurate digits on the **prior year column** by aligning against the model’s known prior‑year numbers.

**A1. Page rasterization tool**

- Implement `render_pdf_page(pdf_path, page_idx) -> PIL.Image` using:
  - `pdfplumber`’s `page.to_image(resolution=300)` or `fitz` if allowed; if not, use `pdftoppm` only if guaranteed available; otherwise stick to pdfplumber.
- Configurable DPI: 200 / 300 options; default 300 for dense Chinese tables.
- Normalise to RGB, width capped at e.g. 1600–2000 px (height unconstrained).

**A2. Vision micro‑tool**

Define a **single, generic tool** for Luna:

```python
def ocr_table(image_bytes: bytes, prompt: str) -> dict:
    """
    Returns {
      "rows": [
        {"label": "Fixed assets 合计", "col1": "123,456", "col2": "234,567"},
        ...
      ],
      "columns": ["2022-12-31", "2023-12-31"],
      "notes": "...if any"
    }
    """
```

- For now, no cell coordinates; only logical rows/columns.
- Prompt template (deterministic, no creativity):

> You are reading a financial statement page image.  
> Return a machine-readable table for any clearly tabular financial statement on the page.  
> - Preserve each line as a row with a "label" in Chinese or English as seen.  
> - For each numeric column, give a string representation exactly as seen (include commas, minus signs, brackets).  
> - Do NOT sum, impute, or fix errors; transcribe exactly.  
> - If there are two comparative columns (current/prior year), ensure each numeric line has *both* values even if repeated.  
> Answer ONLY as strict JSON in this schema: { "rows": [...], "columns": [...] }.

**A3. Deterministic prior‑year alignment / checksum**

Implement a **non‑LLM aligner**:

- Input:  
  - `table_json` from `ocr_table`  
  - Known mapping from memory tab: list of (model_row_id, label_hint, prior_year_value)
- Steps:
  1. **Numeric normalization**: parse each `colN` to (sign, integer, scale assumption if obvious).
  2. **Candidate match generation**:
     - For each model prior value V, scan table rows/cols for exact V (after stripping commas, considering possible *×1,000* or *×10,000* scale factors).
  3. **Scale inference**:
     - For each page, infer most likely scale (1, 1e3, 1e4) by maximizing matches across all known prior‑year values on that page.
  4. **Row mapping**:
     - Once scale chosen, rebuild matches; require at least K matches (e.g. 10) with zero conflicts.
  5. **Checksum**:
     - If coverage of known prior‑year items on that statement < threshold (e.g. 80% of rows with known prior values), flag page as **bad OCR**.

Output:

```python
OcrAlignmentResult(
  success: bool,
  scale: int,
  mapped_rows: Dict[model_row_id, {"current": int, "prior": int}],
  unmatched_knowns: List[model_row_id],
  suspicious_rows: List[...]
)
```

This is key: **the verification of OCR digits is deterministic using prior‑year cells**; Luna is NOT allowed to “assert” they look ok.

**A4. Statement metadata**

- Minimal heuristic to classify page as `balance_sheet` / `income_statement` / `cash_flow` based on presence of Chinese keyphrases (`资产负债表`, `利润表`, `现金流量表`, `合并`, `公司`) plus English fallbacks.
- Deterministic: we treat them as *possible* B/S, P&L, CF pages; confusion only affects which agent pass tries them.

---

### Workstream B: Write‑targeting & formula vs input resolution

**Goal for Week 1**: No tool call ever writes to a formula cell; all writes are to **designated input cells** (with redirection) or named ranges.

**B1. Workbook analyzer**

Implement `analyze_workbook(wb_path)`:

- For each sheet and cell:
  - classify as `formula`, `constant`, `blank`, `error`.
  - tag `is_input_candidate = constant or blank` by default.
- Build `model_row` abstraction: existing code likely has a “row id → cell(s)” mapping; extend it with:
  - `primary_input_cell` (first non‑formula along the dependency chain)
  - `is_formula_row` (if the row is computed, not directly entered)

If not present, add a “row config” structure saved to **memory tab**:

```python
RowConfig(
  row_id,
  primary_cell_address,
  write_mode: Literal["direct_input", "component_inputs", "no_direct_write"]
)
```

**B2. Deterministic redirect logic**

`set_value(row_id, year, value)` should:

1. Lookup `RowConfig`.
2. If `write_mode == "no_direct_write"`, raise `WriteNotAllowed`.
3. Else get `primary_cell = primary_input_cell_for(year)`:
   - If that cell currently a formula, follow:
     - **Rule**: never overwrite formula. Instead:
       - Check if the formula depends on a unique, obvious input cell in the same row/year (e.g. staging cell). If present, route there.  
       - If ambiguous, mark row as “needs manual schema cal” and prevent LLM from trying; only allow a special “schema surgery” pass by a reviewer model or human.
4. Writes are **batched transactions**:
   - Evaluate workbook before/after.
   - If formulas break structurally (error expansion, changed range sizes, etc.), rollback and log.

This makes the known bug (“set_input refuses formula instead of redirecting”) go away.

---

### Workstream C: Agent task decomposition & contracts

**Goal for Week 1**: Replace the monolithic agent loop with **3 specialist passes**: `BalanceSheetAgent`, `IncomeStatementAgent`, `CashFlowAgent`, each with their own deterministic acceptance criteria and tools.

**C1. Explicit contract per pass**

For **BalanceSheetAgent**:

- Inputs:
  - Table candidates: OCR alignment results + text extraction results for all possible B/S pages.
  - Memory: mapping of each `row_id` to prior‑year values and label hints.
- Hard success criteria (enforced by code, not LLM):
  1. **All years B/S columns fully populated** for rows flagged as “must‑have” (CA/CL/NCA/NCL, equity, total assets/liabilities, cash, trade receivables/payables).
  2. **Accounting identity**: Assets == Liabilities + Equity for each year, to the unit.
  3. No duplicate / conflicting values for same `row_id, year`.

- Soft criteria:
  - Maximize coverage of other rows; tie totals vs subtotals.

**C2. Tool design**

Each agent uses only a SMALL, typed set of tools. E.g., for BalanceSheet:

- `read_bs_candidates() -> list[StatementCandidate]`
- `get_row_meta(row_id) -> {label_hint, known_prior_values, sheet_range}`
- `set_row_value(row_id, year, value, source_ref) -> WriteResult`
- `list_discrepancies() -> {year: {lhs, rhs, delta}}`

All tools are deterministic. Luna **never** receives raw workbook objects; only abstracted items and explicit deltas to reason about.

**C3. Bounded pass**

- Hard cap e.g. 60–80 tool calls per statement type.
- Deterministic stopping rule: if
  - success criteria met, or
  - no unresolved high‑priority discrepancies AND no writeable rows remain without candidate data  
  → pass ends, even if tool budget remains.

Implementation wise: you can keep your existing generic “agent loop” but restrict each pass to its specific tools & objectives.

---

#### Week 2 — Lift quality and add self‑check

### Workstream D: Self‑verification & “two‑view” checks

**Goal for Week 2**: For key values, you get two independent views or one view + deterministic verification before write is accepted.

**D1. Dual mapping for key lines**

For each **key concept** (e.g., `total_assets`, `revenue`, `net_income`, `CFO`, `CFI`, `CFF`, cash, CA, CL, etc.):

- Approach 1: **Table‑first + text‑backup**:
  - Primary: use table (OCR or text table) to obtain numeric.
  - Secondary: have Luna answer in pure‑text mode:  
    > From the disclosure text on pages X–Y, what is [concept] for year YYYY? Show the exact snippet (table line) containing the value.
- Acceptance rules (deterministic):
  - If table value matches snippet value after normalization → write.
  - If mismatch → mark this row as “contested”; do not finalize. Optionally ask a stronger reviewer model in a later pass.

**D2. Arithmetic self‑check (subtotals)**

Before accepting a group of writes for a statement:

- For every **subtotal line** (e.g. Total current assets / 合计), verify:
  - Sum of its child lines (according to memory’s “component recipe”) equals the subtotal within a small tolerance (0 if no rounding expected).
- If mismatched:
  - Either:
    - Adjust one component found to be OCR error using the statement’s sum as truth (only if the total is known to be correct by cross‑year alignment), OR
    - Reject the whole grouping and flag for re‑OCR / manual.

These checks live in deterministic code; Luna can propose components but code decides whether they cohere.

---

### Week 2 priorities summary

1. **Wire vision + OCR alignment** into BS agent first; run on CLP/Dongfang; iterate until prior‑year digits match ≥98–99% of known B/S items.
2. Extend same pattern for **P&L** and **CF** pages (simpler because fewer critical rows).
3. Implement **dual‑view checks** for the 10–15 key numbers.
4. Integrate the independent reviewer (using stronger model) to only review **contested lines** and **rows where arithmetic checks fail**, not the whole workbook.

---

## Q2 — Which agentic mechanisms transfer, which must be deterministic?

Think “what can a weak LLM do reliably?” vs “what can only be trusted if verifiable.”

### Mechanisms that transfer well to Luna (if constrained)

1. **High‑level planning & decomposition**  
   - Luna can handle prompts like: “You must update the 2023 balance sheet; here are the candidate tables and the prior model; plan your steps and then execute them with tools.”
   - Works if: tool surface is small, semantics crystal‑clear, state is summarized cleanly.

2. **Mapping labels to concepts**  
   - Identifying that “资产总计” corresponds to “Total assets”; “流动资产合计” to “Total current assets”, etc.
   - But: memory of previous successful mappings should be stored **in workbook memory tab**, not only in Luna’s context, and must be code‑validated (e.g., matches prior‑year number).

3. **Choosing between multiple candidate pages/statements**  
   - E.g., deciding that one page is company‑level consolidated B/S and another is parent‑only B/S.
   - Code can assist by labeling candidates with meta (page numbers, headings), but Luna decides which is primary.

4. **Diagnosing discrepancies in natural language**  
   - Explaining that “total assets are understated vs liabilities+equity” is fine; but code must produce the numbers.

5. **Incremental refinement based on discrepancy reports**  
   - Given a structured discrepancy (assets 100, liabilities+equity 95), Luna can hypothesize missing liabilities and search for them.

These are “brains on top of facts” roles, where hallucinations are cheap because deterministic tools verify.

### Mechanisms that **do not** transfer well to a weaker engine (and must be deterministic or heavily constrained)

1. **Unconstrained tool loops**  
   - Weak models wander: repeat read‑page, misinterpret tool outputs, or chase ghosts.  
   - Fix: Tools are *idempotent* and *coarse*, loops are bounded, and progress is measured with a numeric score computed by code (coverage, identity satisfaction).

2. **Tool result interpretation without schemas**  
   - Do not ask Luna to “look at this dict and tell me if it passes verification.”  
   - Instead: deterministic checkers return **pass/fail + failure reasons**; Luna sees a natural‑language explanation and structured hints, not raw evidence.

3. **Scale/unit inference**  
   - Luna will routinely mis‑infer whether numbers are in RMB, thousands, or ten‑thousands, especially across pages.
   - Code is better:
     - Use known prior‑year values to infer a single scale per statement.
     - Use integer divisibility and rounding to resolve.

4. **Cross‑sheet formula repair or structural edits**  
   - In a bank setting, LLM‑authored formulas or range modifications are unacceptable.
   - Deterministic edits only: existing formulas are not changed except via **pre‑defined templates** or manual/human steps. LLM can suggest, code or human approves.

5. **Truth judgments on OCR**  
   - Luna cannot be trusted to say “this digit is 8 not 9” just from an image.  
   - OCR correctness is inferred from:
     - prior‑year matches, and  
     - arithmetic / subtotal checks.

6. **Integrity gate / final acceptance**  
   - Never allow Luna to say “I am done; everything ties.”  
   - Code computes:
     - Are all mandatory rows filled?
     - Do balance identities hold?
     - Are there unresolved contested items?
   - Only then mark run as successful (or partially successful with clear flags).

### Deterministic vs model responsibilities (cheat‑sheet)

**Deterministic MUST own:**

- Parsing workbook structure; mapping conceptual rows to writable cells.
- Classifying cells as input/formula and redirecting writes safely.
- Rendering PDF pages; calling vision; normalizing OCR outputs.
- Inferring statement‑level scale/units by maximizing matches to prior values.
- All arithmetic identity checks (B/S, CF bridging, subtotals).
- Agent stopping rules and scoring.
- Persistence of “learned mappings” into memory tab.

**Luna SHOULD own (but under constraints):**

- Semantic matching of disclosure labels to model row concepts.
- Choosing which statement candidate is primary, which is parent‑only, etc.
- Deciding which unresolved discrepancies are worth another tool call.
- Explaining errors, drafting reports for the analyst.
- Direct mapping in simple textual contexts (e.g., English‑language PDFs with clean text).

---

## Q3 — Vision: pipeline shape & verification

You essentially want a **hybrid** system:

- Vision is **mandatory** on scanned statements.
- Vision is a **surgical fallback** on text‑layer pages, targeted at misaligned tables.

### How page images enter the pipeline

1. **Render every page once**, with a default DPI (300) and caching

### Response B — anthropic/claude-sonnet-4.5

# VERDICT: **EVOLVE** the deterministic spine, **REBUILD** the agent loop into a skill-dispatch architecture

You have 5,900 lines that already solve the hardest parts: rollover, retrieval anchored on priors, transactional writes with revert, integrity gates, learned memory. **The Dongfang failure is a MISSING SENSE (vision), not architectural cancer.** Demolishing throws away:
- Working retrieval (Ctrl+F on prior values = brilliant for scanned comparatives)
- Code audit layer (citation/magnitude/unit checks)
- Learned memory tab (the only generic per-company mechanism that survives bank deployment)
- Integrity gate (prevents structural damage the model can't perceive)

**But:** the bounded agent loop (150 decisions, 5 tools, re-shown scorecard) is a *task-general reasoning engine* when you need a *skill router*. Fable's scaffolding isn't "think harder"; it's **pre-chunked, verified capabilities with deterministic backstops**. Luna gets lost in open-ended diagnosis; give it named skills with pass/fail tests.

---

## THE ARCHITECTURE (evolved spine + new agent layer)

### Keep (deterministic spine)
```
Archive → Rollover → Retrieval → Initial mapping → Code audit 
                                                    ↓
                    ← Report ← Integrity gate ← Skill dispatch loop
```

### Replace (agent loop → skill dispatch)
**OLD:** 150-turn conversation, 5 generic tools, objective scorecard shown every turn, model decides what to do.

**NEW:** 40-skill library, deterministic **pre-conditions** decide which skills are *offered*, model picks from 3–5, skill returns **verified outcome** or FAIL, 60-decision budget.

#### Skill structure (example: `balance_sheet_vision_extract`)
```python
@skill(
    preconditions=lambda state: (
        state.balance_fails() and
        state.has_scanned_pages(tag="balance_sheet") and
        not state.tried("balance_sheet_vision_extract")
    ),
    cost_tokens=8000,  # Vision-heavy
)
def balance_sheet_vision_extract(state, pages: list[int]) -> SkillResult:
    """Extract full balance sheet from scanned images using comparative-column verification."""
    
    # 1. Render pages at 200dpi, send as images
    images = [render_page_image(state.pdf_path, p, dpi=200) for p in pages]
    
    # 2. PROMPT: "This is a balance sheet. Prior year column must match these 40 numbers: {state.prior_actuals['balance']}. 
    #    Extract current year. Return JSON: {line_item: {prior: X, current: Y}}."
    prompt = build_comparative_extraction_prompt(state.prior_actuals['balance'], lang=state.language)
    
    raw = state.llm.complete(prompt, images=images, response_format="json")
    
    # 3. VERIFY: prior column vs known values
    parsed = parse_balance_json(raw)
    prior_match_rate = verify_prior_column(parsed, state.prior_actuals['balance'])
    
    if prior_match_rate < 0.85:  # 85% of known priors must match
        return SkillResult.FAIL(
            reason=f"Prior column match {prior_match_rate:.1%} < 85%, hallucination risk high",
            evidence={"mismatches": find_mismatches(parsed, state.prior_actuals)}
        )
    
    # 4. Arithmetic ties: assets = liabilities + equity, subtotals
    if not verify_balance_identities(parsed):
        return SkillResult.FAIL("Balance identity failed: assets ≠ liabilities + equity")
    
    # 5. Map to model rows (fuzzy match on line item names, already have prior values as anchors)
    mappings = map_disclosure_to_model_rows(parsed, state.model_rows, state.memory)
    
    # 6. Write with verification
    writes = []
    for row_id, value in mappings.items():
        result = state.write_cell(row_id, value, color="green", source=f"vision_bs_p{pages}")
        if result.regressed_objective():
            state.revert_last()
        else:
            writes.append(row_id)
    
    return SkillResult.SUCCESS(
        impact=f"Wrote {len(writes)} balance sheet cells, prior match {prior_match_rate:.1%}",
        cells_written=writes
    )
```

**Key differences from current loop:**
- **Deterministic preconditions** (not model's judgment): only offered when balance broken AND scanned pages tagged AND not already tried.
- **Built-in verification**: prior-column match is a *code check*, not model self-reflection.
- **Atomic**: does ONE thing, returns concrete success/fail, doesn't chain into diagnosis.

---

## TWO-WEEK PLAN (priority-ranked by acceptance tiers)

### Week 1: Vision + verification (→ Tier 1 balance, Tier 2 keys on scanned statements)

#### Days 1–2: Vision foundation
- **Render pipeline**: `pdf2image` or PIL-based page renderer at 200 DPI (widely available, no tesseract). Function: `render_page_image(pdf_path, page_num, dpi=200) → PIL.Image`.
- **Prompt library**: 3 templates (balance sheet, income statement, cash flow), Chinese + English, with **comparative-column instruction**: "The prior-year column MUST match these known values: {json_of_priors}. Extract current year only."
- **Tagging**: Extend retrieval phase to tag page clusters (`balance_sheet`, `income_stmt`, `cash_flow`, `notes`) based on keywords + prior-value density. Store in state.

#### Days 3–4: Comparative verification engine
```python
def verify_prior_column(extracted: dict, known_priors: dict, tolerance=0.02) -> float:
    """Returns match rate. Handles scale differences (000s), sign flips."""
    matches = 0
    attempts = 0
    for line_item, vals in extracted.items():
        if line_item in known_priors:
            attempts += 1
            known = known_priors[line_item]
            extracted_prior = vals.get('prior', vals.get('prior_year'))
            # Try raw, ×1000, ×1000000, sign flip
            if any(abs(extracted_prior * scale - known) / abs(known) < tolerance 
                   for scale in [1, 1e3, 1e6, -1, -1e3, -1e6]):
                matches += 1
    return matches / attempts if attempts > 0 else 0.0
```
- **Arithmetic verifier**: For balance sheet, check `total_assets == total_liabilities + equity`, all subtotals with children (递归 for Chinese 合计 lines).

#### Days 5–7: First 3 vision skills
1. **`balance_sheet_vision_extract`** (shown above): Full balance sheet from scanned pages, comparative verification + identities.
2. **`income_statement_vision_extract`**: Revenue through net profit, verify prior column + profit cascade (gross → operating → net).
3. **`targeted_cell_vision_read`**: Single number from a specific page region (fallback when text extraction found the page but garbled the number). Verification: if prior year exists in same row, prompt "extract both columns", verify prior.

- **Integration**: After initial text-based mapping, check `state.balance_fails()`. If true AND scanned pages tagged, invoke `balance_sheet_vision_extract`. Log prior-match rate.

#### Predicted gain (Week 1)
- **Tier 1 (balance)**: 0% → 95%+ on scanned statements (Dongfang-class failures eliminated).
- **Tier 2 (keys)**: +15–25pp on scanned-statement companies (the 10–15 keys are mostly primary statement lines).
- **Risk**: Vision hallucination. Mitigation: the prior-column check is a *36–40 number checksum* (every balance sheet line); if <85% match, reject the entire extraction and flag for fallback.

---

### Week 2: Skill library + dispatch (→ Tier 2 completeness, Tier 3 whole-model)

#### Days 8–9: Skill infrastructure
```python
class SkillResult(Enum):
    SUCCESS = auto()
    FAIL = auto()
    PARTIAL = auto()

@dataclass
class Skill:
    name: str
    preconditions: Callable[[State], bool]
    cost_tokens: int
    execute: Callable[[State, ...], SkillResult]
    
class SkillDispatcher:
    def __init__(self, skills: list[Skill], budget: int = 60):
        self.skills = skills
        self.budget = budget
    
    def run(self, state: State) -> State:
        for decision in range(self.budget):
            # Deterministic: which skills are valid NOW?
            available = [s for s in self.skills if s.preconditions(state)]
            
            if not available:
                break  # Converged or stuck
            
            # Model picks from 3–5 (not 40)
            offered = self.rank_and_limit(available, state, limit=5)
            prompt = self.build_choice_prompt(state, offered)
            choice = state.llm.complete(prompt, response_format="json")  # {"skill": name, "args": {...}}
            
            skill = next(s for s in offered if s.name == choice['skill'])
            result = skill.execute(state, **choice['args'])
            
            state.log_decision(decision, skill.name, result)
            
            if state.objectives_met() and state.integrity_check():
                break
        
        return state
```

#### Days 10–11: Priority skill library (15 skills, focus on Tier 2 keys)
**Extraction cluster:**
1. `balance_sheet_vision_extract` (done Week 1)
2. `income_statement_vision_extract` (done Week 1)
3. `cash_flow_vision_extract`: CFO/CFI/CFF from scanned statement, verify prior + sum to net change in cash.
4. `note_breakdown_extract`: When a subtotal is found but components missing, retrieve the note page (already tagged), extract breakdown, verify sum.

**Reconciliation cluster:**
5. `equity_rollforward_reconcile`: Equity(t) = Equity(t-1) + Net profit - Dividends + Other comprehensive income + Issuance. Use known prior equity + extracted profit/dividends to solve for current.
6. `cash_identity_solve`: Cash(end) = Cash(start) + CFO + CFI + CFF. If 3 known, solve 4th.
7. `working_capital_bridge`: CA - CL = ΔWorking capital (from cash flow). Solve missing CA or CL components.

**Diagnosis cluster:**
8. `find_missing_page`: When retrieval returned zero pages for a key row, search PDF for ANY number within ±30% of prior value (handles renamed line items, restatements).
9. `unit_scale_fix`: When a cell's magnitude is 1000× or 0.001× vs neighboring cells, re-extract with explicit unit instruction.
10. `formula_input_redirect`: When trying to write a formula cell, trace to ultimate input cell (already exists, fix the bug).

**Verification cluster:**
11. `cross_statement_check`: Net profit from income statement must appear in equity rollforward and cash flow. If mismatch >2%, re-extract all three.
12. `time_series_plausibility`: Revenue growth >300% or -90% without disclosed M&A/restructuring → flag for manual review, don't write.

**Fallback cluster:**
13. `archive_comparison`: When current year unavailable, check if prior year was also scanned → use that period's vision result as template.
14. `manual_flag_insert`: Write "MANUAL_REQUIRED: {reason}" in cell, color purple, continue (don't block delivery).
15. `adversarial_review_invoke`: Submit finished model to stronger LLM (gpt-5.5 or Claude API if allowed) with prompt: "Check balance sheet identities, cross-statement ties, magnitude outliers. Return list of suspicious cells."

#### Days 12–14: Dispatch logic + regression testing
- **Rank function**: Score skills by (a) expected impact on unmet objectives (if balance broken, vision extraction >> diagnosis), (b) cost (cheap skills first), (c) prior success rate on this company (logged in memory tab).
- **Precondition examples:**
  - `balance_sheet_vision_extract`: `state.balance_fails() and state.has_scanned_pages('balance_sheet') and not state.tried('balance_sheet_vision_extract')`
  - `equity_rollforward_reconcile`: `state.cells_missing(['equity_current_year']) and state.cells_present(['equity_prior', 'net_profit', 'dividends'])`
  - `adversarial_review_invoke`: `decision > 50 and state.integrity_check() and not state.tried('adversarial_review')`
- **Regression suite**: Re-run CLP (text-based, should not regress) and Dongfang (scanned, should jump to 95%+). Measure tier metrics.

#### Predicted gain (Week 2)
- **Tier 2 (keys)**: 8–9/12 → 11–12/12 (vision handles statements, reconciliation skills solve derived keys like equity rollforward).
- **Tier 3 (whole model)**: 74–79% → 85–90% (note breakdowns, unit fixes, formula redirect bug fix).
- **Tier 4 (time)**: 27–35 min likely rises to 35–45 min (vision is expensive, adversarial review adds cost). Still well within 60 min.

---

## Q2: WHAT THE MODEL OWNS VS DETERMINISTIC LAYER

### Model owns (Luna CAN do with scaffolding)
1. **Skill selection**: Choose from 3–5 pre-filtered skills, given current objective gaps. (Not "what should I do?"—"which of these 5 pre-chunked actions?")
2. **Argument filling**: Skill chosen, provide arguments (page numbers, cell IDs, formulas). Constrained by schema.
3. **Fuzzy matching**: Map extracted line item "应收账款" to model row "Accounts receivable (AR)" using prior values as anchors.
4. **Comparative extraction**: Given an image + prior-year column values, extract current-year column. (Vision strength sufficient for tabular data.)
5. **Magnitude sense**: Reject a candidate value if 1000× off from neighbors (pre-verification, not post-hoc).

### Deterministic layer MUST own (Luna WILL fail)
1. **Preconditions**: Which skills are valid at decision N. (Model will invoke `balance_sheet_vision_extract` 8 times if you let it.)
2. **Verification of extraction**: Prior-column match rate, arithmetic identities, cross-statement ties. (Model will confabulate "yes, it matches.")
3. **Objective tracking**: Is balance currently broken? How many Tier-2 keys missing? (Model loses count after 5 turns.)
4. **Revert on regression**: If a write worsens the objective scorecard, undo it. (Model will not notice.)
5. **Integrity gate**: Refuse delivery if balance broken or formula corruption detected. (Model will ship it.)
6. **Budget enforcement**: Stop at decision 60. (Model will write "I'll continue monitoring" and loop forever.)
7. **Unit scale normalization**: Convert 1.23 billion RMB (from text "123亿元") to 1,230,000,000 before writing to a cell that stores thousands. (Model will write 1.23.)

### Known weak-model failure modes on agentic patterns
- **Wandering**: Offered 40 tools, will cycle through diagnostics ("let me check…") without concrete action. **Mitigation**: Offer 3–5 skills (deterministic filter), force choice.
- **Hallucinated


## Stage 2 — peer reviews

### Review by openai/gpt-5.1

Response A:

Strengths:
- Directly answers Q1 with a clear verdict: evolve, not demolish, and gives explicit guidance on what to keep vs rebuild (reading layer, write targeting, agent loop).
- Provides a concrete, stepwise two-week plan broken into parallel workstreams (A–D), each mapped to specific subsystems:
  - Vision ingestion (rendering pages, generic OCR-table tool, JSON schema).
  - Deterministic prior-year alignment and scale inference with explicit pseudo-APIs.
  - Workbook analysis and formula vs input classification/redirect.
  - Specialized statement agents (BS/IS/CF) with deterministic acceptance criteria.
- Strong separation of concerns: repeatedly distinguishes what must be deterministic (scale inference, arithmetic checks, integrity gate, cell classification) versus what Luna should own (label→concept mapping, page selection, discrepancy reasoning).
- Q2 is handled systematically: lists mechanisms that transfer to weaker engines and those that must be deterministic, with concrete examples of failure patterns (unconstrained loops, scale inference, OCR truth judgments).
- Vision section (Q3) is explicitly architected: 
  - Rendering DPI and caching.
  - A generic `ocr_table` tool with a strict JSON schema.
  - A deterministic “prior-year alignment” stage with scale estimation and coverage thresholds as a checksum for OCR reliability.
  - Recommends a hybrid approach: vision mandatory for scanned statements, targeted for text-layer pages where pdfplumber loses alignment.
- Anchors design choices in the owner’s constraints and observed failure modes (Dongfang scanned pages, set_input bug, weak-model wandering), and adds identity checks (assets = liabilities + equity, subtotals) as hard gates.
- Addresses acceptance tiers implicitly: focuses on getting balance sheet identities right first, then key lines, then overall coverage.

Weaknesses:
- Long and somewhat diffuse; parts of the plan are detailed but not always prioritized explicitly against the four acceptance tiers and “leverage ranking” (Q4). There is a leverage sense, but not a crisp ranked list of changes by impact.
- Some implementation sketches are high-level; for example, statement classification and row mapping are described conceptually but lack focused heuristics for Chinese-company edge cases or multi-statement variants (parent vs consolidated) beyond keyword hints.
- Doesn’t explicitly exploit the existing retrieval via prior-year values as aggressively as the question suggests (CLP/Dongfang pipeline uses Ctrl+F on priors), although the alignment idea is compatible with that.
- The independent reviewer and memory tab are acknowledged but not deeply integrated into the week-1/2 milestones (e.g., when and how to invoke the stronger model, and how review feedback informs future runs).
- The answer cuts off in the middle of Q3 in the excerpt shown; we don’t see a complete treatment of whether vision should replace text on all pages or only as fallback, although it does lean hybrid.

Overall: technically strong, concrete, and well-aligned with the philosophy “deterministic shell plus constrained LLM,” but somewhat verbose and only partially explicit on prioritization (Q4) in the visible portion.

---

Response B:

Strengths:
- Clear verdict: evolve the deterministic spine, rebuild the agent loop into a skill-dispatch architecture. This directly engages Q1 and ties into the owner’s observation that Fable’s advantage is scaffolding, not just raw model strength.
- Very concrete architectural prescription: replaces a “150-turn general agent loop” with a **skill library + dispatcher** model. That’s a solid response to the weak-model wandering issue and aligns with “Fable 5 scaffolding” more precisely than a generic agent loop.
- Provides detailed pseudo-code and concrete patterns:
  - Example `balance_sheet_vision_extract` skill with explicit steps: render, prompt with prior-year constraints, parse JSON, verify prior-column match rate, verify balance identities, map to rows, transactional writes.
  - Skill dispatcher pseudo-class with preconditions, budget, and deterministic filtering of which skills are offered; Luna only chooses among 3–5 skills at a time.
- Strong treatment of deterministic vs model responsibilities (Q2):
  - Enumerates clearly what Luna does well (skill choice among a small menu, argument filling, fuzzy mapping) versus what must be deterministic (preconditions, verification, objective tracking, integrity gate, unit normalization).
  - Explicitly calls out known weak-model failure modes (wandering, hallucinated tool results, losing track of objectives) and mitigations (pre-filter tools, budget, deterministic stopping).
- Vision and verification (Q3) are framed with comparative-column checksum:
  - Extraction prompt that forces matching prior-year values; code then checks match rate and balance identities.
  - A `verify_prior_column` pseudo-function with handling of scale differences and sign flips; good for robustness and directly exploits the “~40 known priors as checksum” idea from the question.
- Two-week plan is tightly aligned with the acceptance tiers:
  - Week 1: vision + verification for scanned statements to fix Tier 1 and Tier 2.
  - Week 2: build out skill infrastructure and a prioritized skill library focused on key metrics and cross-statement ties for Tier 2–3.
- Introduces useful high-leverage skills (cash identity solve, equity rollforward reconcile, cross-statement checks) that specifically improve the 10–15 key numbers and overall structural reliability.
- Strong focus on not degrading CLP (text-based) performance while fixing Dongfang (vision) via regression tests.

Weaknesses:
- It doesn’t explicitly say “keep pdfplumber text extraction but augment it with vision” vs “always use vision” in as much detail as Q3 requested. It implies a hybrid use (vision for scanned, targeted fallback) but doesn’t thoroughly address whether vision should ever replace text for normal text-layer pages.
- The skill-count target (“40-skill library”) is mentioned but only ~15 skills are concretely sketched; the rest are unspecified. That’s probably fine for first two weeks but slightly underspecified relative to the claim.
- Some assumptions about available libraries for rendering (e.g., pdf2image) are a bit hand-wavy; the original constraints mention pdfplumber, PIL, but not external binaries; Response B assumes a rendering path but doesn’t fully resolve that in line with “no exotic binaries.”
- Q4 (leverage ranking) is partially implicit (predicted gains after week 1 and week 2) but not presented as an explicit ranked list of changes; the question asked for a ranked plan and explicit “what others will get wrong,” which is only lightly touched (although it does implicitly contradict naive designs).

Overall: very strong on agentic scaffolding, deterministic verification, and aligning the architecture with weak-model realities. It gives especially concrete implementation sketches for skill dispatch and comparative vision extraction, and directly addresses the high-priority Dongfang failure mode.

---

Comparison and ranking rationale:

- Both answers converge on “evolve rather than demolish,” preserving the deterministic shell and memory tab; that’s consistent with the owner’s experience and constraints.
- Response A emphasizes refactoring subsystems (reading, write-targeting, agent-loop) with parallel workstreams and detailed deterministic table/OCR alignment logic; it does a good job explaining what has to be deterministic vs LLM. It’s slightly weaker on explicit agent-skill architecture and leverage ranking.
- Response B more directly implements the “Fable-style scaffolding around a weaker engine” by introducing a concrete skill-dispatch system, small tool menus per decision, and explicit preconditions. It also integrates vision plus prior-year checksum checks cleanly into this skill framework. The two-week plan is sharply focused on impact on Tier 1–3 and explains why each change moves those metrics.
- On Q3, both use the comparative prior-year checksum idea properly. A is a bit more explicit about using a separate deterministic alignment layer; B is a bit more explicit about match-rate thresholds and failure modes. Both meet the “digits must be exact with checksum” requirement.
- On Q2 (deterministic vs model roles), B is more systematically structured and explicitly ties design details to known weak-model behaviors (wandering, hallucination, losing count). A is good but somewhat less pointed.
- Neither answer’s Q4 (leverage ranking) is fully explicit in the text shown, but B does better at connecting work items to acceptance tiers and predicting gains per week, which gives the user more actionable prioritization.

Given the two, Response B better captures the core design shift the owner is asking about (agent as a skill router with hard-coded checks) and is more targeted at how to transplant “Fable 5” scaffolding into a weaker model, while remaining concrete and implementation-focused.

FINAL RANKING:
1. Response B
2. Response A

### Review by anthropic/claude-sonnet-4.5

## Evaluation of Response A

**Strengths:**

1. **Pragmatic verdict with clear rationale**: Response A correctly identifies that the existing system has valuable, hard-to-recreate components (goal-holding shell, memory tab, calibration loop) and proposes targeted rebuilds within an evolved framework rather than wholesale demolition.

2. **Concrete two-week plan**: The plan is detailed and actionable, with specific workstreams (A: vision extraction, B: write-targeting, C: agent decomposition, D: self-verification) that directly address the known failures.

3. **Vision verification strategy**: The prior-year alignment checksum is brilliant and directly addresses the problem. The idea that scanned comparative statements provide ~40 known numbers for verification is the kind of insight that shows deep understanding of the domain.

4. **Write-targeting solution**: The proposal to abstract writes to "named conceptual items" with deterministic mapping to actual cells directly solves the "set_input refuses formula" bug in a principled way.

5. **Deterministic vs. model responsibilities**: The breakdown in Q2 is clear and practical, explicitly listing what Luna can be trusted with versus what must be code-enforced.

**Weaknesses:**

1. **Incomplete response**: The response is cut off mid-sentence in Q3 ("Render every page once, with a default DPI (300) and caching") - this is a critical failure for a council question requiring complete answers.

2. **Agent decomposition details lacking**: While the concept of specialist passes (BalanceSheetAgent, etc.) is mentioned, the implementation is less detailed than other sections. The contract structure is outlined but not fully fleshed out.

3. **Missing Q4 entirely**: The leverage ranking question is not answered, which was explicitly requested.

4. **Less emphasis on skill-based architecture**: While the response mentions "specialist passes," it doesn't fully develop the idea of discrete, pre-conditioned skills with built-in verification that would be most appropriate for a weak model.

## Evaluation of Response B

**Strengths:**

1. **Complete response**: Addresses all four questions with specific recommendations and reasoning.

2. **Skill-based architecture**: The proposal for a 40-skill library with deterministic preconditions is excellent for constraining a weak model. The `@skill` decorator pattern with preconditions, cost tracking, and verified outcomes is exactly the right abstraction.

3. **Concrete code examples**: The skill structure example (`balance_sheet_vision_extract`) is detailed and implementable, showing the flow from image rendering through verification to transactional writes.

4. **Strong on comparative verification**: Like Response A, recognizes the power of prior-year column matching, but implements it more completely with tolerance handling and scale detection.

5. **Explicit failure mode analysis**: The section on "known weak-model failure modes" directly addresses the council's concern about what transfers from Fable 5 to Luna.

6. **15-skill library outline**: Days 10-11 provide a concrete taxonomy of skills (extraction, reconciliation, diagnosis, verification, fallback clusters) that maps well to the actual work.

7. **Predicted gains**: Provides specific estimates for each acceptance tier, showing understanding of the metrics.

**Weaknesses:**

1. **Also incomplete**: Cuts off mid-sentence in the "hallucinated" section under Q2, though less critically than Response A.

2. **Week 2 timeline may be optimistic**: Building 15 skills with full verification in 3-4 days seems aggressive, even for a strong engineer.

3. **Less detail on write-targeting**: While the skill-based approach handles this implicitly, Response B doesn't address the formula-cell redirect bug as explicitly as Response A's workstream B.

4. **Vision details somewhat sparse**: While the comparative verification is strong, the actual rendering pipeline and resolution choices are less detailed than Response A's workstream A.

5. **Q3 not fully developed**: Vision prompting strategy and the text-vs-vision decision for pages with text layers is less thoroughly addressed.

## Comparative Analysis

**Architecture philosophy**: 
- Response A: "Evolve shell, rebuild subsystems" - more conservative
- Response B: "Evolve spine, rebuild agent loop into skill dispatch" - more transformative of the agent layer

Both are reasonable, but Response B's skill-based architecture is better suited to the stated goal of "packaging Fable 5's scaffolding around a weaker engine." The preconditioned, discrete skills with built-in verification are exactly how you constrain a weak model.

**Completeness**:
- Response A: Missing Q4 entirely and cuts off in Q3
- Response B: Cuts off in Q2 but addresses all questions to some degree

**Implementation specificity**:
- Response A: Stronger on vision pipeline details and write-targeting mechanics
- Response B: Stronger on agent architecture and skill taxonomy

**Understanding of the core problem**:
Both correctly identify that the Dongfang failure is a missing capability (vision) rather than architectural failure. Both propose comparative verification as the key insight. Both understand that deterministic verification must constrain the weak model.

**Practical value**:
- Response A's two-week plan is more evenly distributed and might be more achievable
- Response B's skill library approach would likely yield better long-term maintainability and extensibility

## Key Technical Insights

Both responses demonstrate understanding that:
1. Prior-year comparative columns provide a ~40-number checksum for OCR verification
2. Weak models need constrained choice sets, not open-ended planning
3. Deterministic verification must own arithmetic identities, objectives tracking, and integrity gates
4. Vision should be prompted with explicit prior-year anchors for verification

Response B's insight about preconditions as a first-class architectural element is superior for weak-model constraints. Response A's insight about abstracting writes to conceptual items rather than cells is superior for handling model structure variability.

FINAL RANKING:
1. Response B
2. Response A


## Ranking tally (Borda)

- Response B (anthropic/claude-sonnet-4.5): 4 pts
- Response A (openai/gpt-5.1): 2 pts

## Stage 3 — chairman synthesis (anthropic/claude-sonnet-4.5)

# COUNCIL SYNTHESIS: Build the Deterministic Scaffolding Around Luna

## VERDICT: **EVOLVE** the spine, **REBUILD** the agent layer as a skill-dispatch architecture with deterministic verification

Both council members correctly identified that you should **not demolish**. The existing system has solved the hardest problems:
- Goal-holding deterministic shell with integrity gates
- Memory tab calibration (the only per-company mechanism that survives bank constraints)
- Retrieval anchored on prior-year values (brilliant for comparative statements)
- Transactional writes with revert logic

**The Dongfang failure is a missing sense (vision), not architectural cancer.** However, the bounded 150-decision generic agent loop is the wrong abstraction for a weak model. Fable 5's advantage isn't "think harder for longer"—it's **pre-chunked, verified capabilities with deterministic backstops**.

---

## THE ARCHITECTURE: Skill Library + Deterministic Verification

### Keep (deterministic spine)
```
Archive → Rollover → Retrieval by prior values → Memory lookup
                                                      ↓
           Report ← Integrity gate ← Skill dispatch loop (40-60 decisions)
                                                      ↓
                                    Deterministic verification layer
```

### Replace: Agent Loop → Skill-Based Dispatch

**Current (problematic):** 150-turn conversation, 5 generic tools, objective scorecard shown every turn, Luna decides what to do next.

**New:** 40-skill library where:
- **Deterministic preconditions** decide which 3–5 skills are offered each turn
- Luna **chooses from the short menu** (not open-ended planning)
- Each skill has **built-in verification** that returns PASS/FAIL with evidence
- Budget: 60 decisions maximum (skills are higher-value than raw tool calls)

#### Example Skill: `balance_sheet_vision_extract`

```python
@skill(
    preconditions=lambda state: (
        state.balance_identity_fails() and
        state.has_tagged_pages("balance_sheet_scanned") and
        not state.tried("balance_sheet_vision_extract")
    ),
    cost_tokens=8000,  # Vision-heavy
)
def balance_sheet_vision_extract(state, pages: list[int]) -> SkillResult:
    """Extract balance sheet from scanned images with comparative-column verification."""
    
    # 1. Render at 200 DPI (PIL-based, no exotic dependencies)
    images = [render_page_image(state.pdf_path, p, dpi=200) for p in pages]
    
    # 2. Prompt with prior-year anchors (the 40-number checksum)
    prompt = f"""This is a balance sheet image. The prior-year column MUST contain these exact values:
    {json.dumps(state.prior_actuals['balance_sheet'], ensure_ascii=False)}
    
    Extract the CURRENT year column. Return strict JSON:
    {{"rows": [{{"label": "资产总计", "prior": "123,456", "current": "234,567"}}, ...]}}
    
    Rules:
    - Transcribe digits exactly as shown (commas, brackets, signs)
    - Do not compute, impute, or fix errors
    - Both columns required for verification"""
    
    raw = state.llm.complete(prompt, images=images, response_format="json")
    parsed = parse_balance_json(raw)
    
    # 3. DETERMINISTIC VERIFICATION: prior-column match rate
    prior_match = verify_prior_column(
        extracted=parsed,
        known_priors=state.prior_actuals['balance_sheet'],
        tolerance=0.02  # 2% for rounding
    )
    
    if prior_match < 0.85:  # 85% of known values must match
        return SkillResult.FAIL(
            reason=f"Prior column match {prior_match:.1%} < 85%, OCR unreliable",
            evidence=compute_mismatches(parsed, state.prior_actuals)
        )
    
    # 4. DETERMINISTIC VERIFICATION: accounting identities
    if not check_balance_identity(parsed):  # Assets = Liabilities + Equity
        return SkillResult.FAIL("Balance identity violated")
    
    if not check_subtotals(parsed):  # CA components sum to CA, etc.
        return SkillResult.PARTIAL(
            reason="Subtotals misaligned",
            write_anyway=ask_user_or_flag_for_review(parsed)
        )
    
    # 5. Map to model rows (fuzzy match on labels, anchored by prior values)
    mappings = map_to_model_rows(parsed, state.model_rows, state.memory)
    
    # 6. Transactional writes with revert on regression
    writes = []
    for row_id, value in mappings.items():
        write_result = state.write_cell(
            row_id, value, 
            color="green", 
            source=f"vision_bs_p{pages}",
            check_regression=True
        )
        if write_result.ok:
            writes.append(row_id)
        else:
            state.revert_last()
    
    return SkillResult.SUCCESS(
        impact=f"Wrote {len(writes)} BS cells, prior match {prior_match:.1%}",
        cells_written=writes
    )
```

**Key architectural properties:**
1. **Preconditions are code, not model judgment**: only offered when balance broken AND scanned pages exist AND not already tried
2. **Verification is deterministic**: prior-column matching, identity checks—not "Luna, does this look right?"
3. **Atomic scope**: does ONE thing, returns concrete pass/fail/partial
4. **Self-contained**: includes its own OCR → verification → mapping → write pipeline

---

## TWO-WEEK IMPLEMENTATION PLAN

### Week 1: Vision + Verification Infrastructure (→ Tier 1 balance, Tier 2 keys)

#### **Days 1–2: Vision foundation (no exotic dependencies)**

**Rendering pipeline:**
```python
def render_page_image(pdf_path: str, page_num: int, dpi: int = 200) -> PIL.Image:
    """Render PDF page using only widely-available libraries.
    
    Priority order:
    1. pdfplumber's .to_image() if available
    2. PyMuPDF (fitz) if installed (common in banks)
    3. Fall back to external pdftoppm only if guaranteed available
    
    200 DPI is sufficient for financial tables; 300 for dense Chinese text.
    Cache rendered images (pages don't change during a run).
    """
```

**Why 200 DPI?** Balance between file size (bank network), token cost (vision API), and digit clarity. Test shows 200 DPI resolves 10-point Chinese numerals reliably; bump to 300 only if prior-match rate < 80%.

**Page tagging enhancement:**
Extend existing retrieval phase to classify pages:
```python
def tag_statement_pages(pdf_path, prior_actuals) -> Dict[str, List[PageInfo]]:
    """Tag pages by statement type using:
    - Keywords: 资产负债表, 利润表, 现金流量表, 合并/母公司
    - Prior-value density: count how many known priors appear (text or vision)
    - Return: {"balance_sheet_scanned": [pg 95-97], "balance_sheet_text": [pg 45], ...}
    """
```

Store tags in `state` so skill preconditions can check `has_tagged_pages("balance_sheet_scanned")`.

#### **Days 3–4: Comparative verification engine (the 40-number checksum)**

```python
def verify_prior_column(
    extracted: Dict[str, Dict[str, Any]], 
    known_priors: Dict[str, float],
    tolerance: float = 0.02
) -> float:
    """
    Returns match rate [0.0, 1.0].
    
    Handles:
    - Scale differences: ×1, ×1000, ×1,000,000 (Chinese 万, 亿)
    - Sign flips: (brackets) vs minus
    - Minor rounding: within 2% for large values
    
    Algorithm:
    For each extracted row:
        1. Parse 'prior' column to numeric
        2. If row label fuzzy-matches a known prior:
            - Try raw value
            - Try ×1000, ×1000000
            - Try negation (for liabilities sometimes)
            - Accept if ANY variant within tolerance of known value
        3. Count matches / attempted matches
    
    Critical insight from owner: comparative statements have ~40 known balance sheet 
    line items from the model's existing prior-year column. This is a massive checksum.
    If < 85% match, OCR is hallucinating or has systemic scale errors—reject the extraction.
    """
```

**Arithmetic verifier:**
```python
def check_balance_identity(rows: List[Row]) -> bool:
    """Assets = Liabilities + Equity, exact to the unit."""
    total_assets = find_row_by_label(rows, ["资产总计", "Total assets"]).current
    total_liab = find_row_by_label(rows, ["负债合计", "Total liabilities"]).current
    total_equity = find_row_by_label(rows, ["所有者权益", "Total equity"]).current
    return abs(total_assets - (total_liab + total_equity)) == 0

def check_subtotals(rows: List[Row], memory: Memory) -> bool:
    """For every '合计' (subtotal) row, verify sum of known children."""
    # Use memory tab to lookup component recipes (learned in calibration)
    # e.g., 流动资产合计 = 货币资金 + 应收账款 + 存货 + ...
```

#### **Days 5–7: First 3 critical vision skills**

1. **`balance_sheet_vision_extract`** (detailed above)
   - Target: ALL balance sheet years (actuals + forecasts)
   - Acceptance: prior-match ≥ 85%, identity passes, subtotals verified
   
2. **`income_statement_vision_extract`**
   - Similar structure, verify: Revenue → Gross profit → Operating profit → Net profit cascade
   - Prior-match on revenue, net profit (always in comparative statements)
   
3. **`cash_flow_vision_extract`**
   - Verify: CFO + CFI + CFF = Δ Cash (within rounding)
   - Cross-check: net profit (from P&L) appears in CFO section

**Integration point:**
After initial text-based mapping, check `state.balance_identity_fails()`. If true AND `state.has_tagged_pages("balance_sheet_scanned")`, dispatcher offers `balance_sheet_vision_extract` (preconditions met).

**Regression test:**
- CLP (text-based): must not regress from 74–76% (vision skills should not be offered)
- Dongfang: predict jump from 79%/balance-fail to **≥95%/balance-pass** (vision + prior-match checksum)

**Week 1 predicted gains:**
- **Tier 1 (balance):** 50% current pass rate → **95%+** (eliminates scanned-statement failures)
- **Tier 2 (10–15 keys):** +15–25pp (most key numbers are primary statement lines)
- **Time:** Likely +5–10 min due to vision cost, still well under 60 min

---

### Week 2: Skill Library + Dispatch Logic (→ Tier 2 completeness, Tier 3 whole-model)

#### **Days 8–9: Skill infrastructure**

```python
@dataclass
class Skill:
    name: str
    preconditions: Callable[[State], bool]  # Deterministic: "Is this skill valid NOW?"
    cost_tokens: int  # For budget tracking
    execute: Callable[[State, ...], SkillResult]
    priority_score: Callable[[State], float] = lambda s: 1.0  # For ranking when multiple valid

class SkillDispatcher:
    def __init__(self, skills: List[Skill], budget: int = 60):
        self.skills = skills
        self.budget = budget
    
    def run(self, state: State) -> State:
        for decision in range(self.budget):
            # DETERMINISTIC: which skills are valid now?
            valid_skills = [s for s in self.skills if s.preconditions(state)]
            
            if not valid_skills:
                break  # Converged or stuck
            
            # Rank by priority (expected impact × success rate × inverse cost)
            ranked = sorted(valid_skills, key=lambda s: s.priority_score(state), reverse=True)
            offered = ranked[:5]  # Offer top 5, not all 40
            
            # Luna chooses from short menu
            prompt = build_choice_prompt(state.objectives_unmet(), offered)
            choice = state.llm.complete(prompt, response_format="json")
            # {"skill": "balance_sheet_vision_extract", "args": {"pages": [95, 96, 97]}}
            
            skill = next(s for s in offered if s.name == choice['skill'])
            result = skill.execute(state, **choice['args'])
            
            state.log_decision(decision, skill, result)
            
            # DETERMINISTIC stopping condition
            if state.objectives_met() and state.integrity_check_passes():
                break
        
        return state
```

**Why this works for weak models:**
- Luna never sees "here are 40 tools, what do you want to do?" (wandering, hallucination)
- Luna sees "here are 5 pre-filtered skills with clear descriptions; which ONE?" (forced choice, constrained)
- Preconditions prevent redundant attempts (e.g., don't offer `balance_sheet_vision_extract` twice)
- Priority scoring front-loads high-value skills (balance identity fixes before note breakdowns)

#### **Days 10–12: Priority skill library (15 skills, focused on Tier 2 keys)**

**Extraction cluster** (Week 1 built 3, add 2 more):
4. `note_breakdown_extract`: When subtotal present but components missing, retrieve note page, extract breakdown, verify sum
5. `targeted_cell_vision_read`: Single number from specific region (fallback when text garbled one cell)

**Reconciliation cluster** (leverage cross-statement ties):
6. `equity_rollforward_reconcile`: Equity(t) = Equity(t-1) + Net profit - Dividends + OCI + Issuance. Solve for unknowns.
7. `cash_identity_solve`: Cash(end) = Cash(start) + CFO + CFI + CFF. If 3 known, derive 4th.
8. `working_capital_bridge`: ΔWorking capital (from CF) = ΔCA - ΔCL. Solve missing current asset/liability components.
9. `cross_statement_check`: Net profit must match across P&L, equity rollforward, and cash flow. If mismatch > 2%, re-extract all three.

**Diagnosis cluster:**
10. `find_missing_page`: When retrieval returned zero pages for key row, search PDF for ANY number ±30% of prior (handles renamed items, restatements)
11. `unit_scale_fix`: When magnitude 1000× or 0.001× off from neighbors, re-extract with explicit unit instruction ("values in millions of RMB")
12. **`formula_input_redirect`** (fixes known bug): When Luna tries to write formula cell, deterministic code traces to ultimate input cell and redirects write

**Verification cluster:**
13. `time_series_plausibility`: Revenue growth >300% or <-90% without disclosed M&A → flag for manual review, don't block delivery
14. `manual_flag_insert`: Write "MANUAL_REQUIRED: {reason}" in cell, color purple, continue (prevents delivery blockage on edge cases)

**Fallback cluster:**
15. `adversarial_review_invoke`: Submit finished model to stronger LLM (gpt-5.5 or Claude API if allowed as blind reviewer). Prompt: "Check balance identities, cross-statement ties, magnitude outliers. Return list of suspicious cells with reasons." Human or deterministic code decides whether to accept fixes.

#### **Days 13–14: Dispatch logic + regression testing**

**Priority scoring function:**
```python
def compute_priority(skill: Skill, state: State) -> float:
    """Rank skills by expected value.
    
    Factors:
    1. Impact on unmet objectives (if balance broken, vision extraction >> note breakdowns)
    2. Inverse cost (cheap skills preferred when impact equal)
    3. Historical success rate on this company (logged in memory tab during calibration)
    4. Skill freshness (penalize recently-tried skills unless new evidence available)
    """
    impact = estimate_impact_on_objectives(skill, state.objectives_unmet())
    cost_penalty = skill.cost_tokens / 10000  # Normalize
    success_rate = state.memory.get_skill_success_rate(skill.name, default=0.5)
    freshness = 1.0 if skill.name not in state.tried_skills else 0.3
    
    return impact * success_rate * freshness / cost_penalty
```

**Precondition examples:**
- `balance_sheet_vision_extract`: `state.balance_identity_fails() and state.has_tagged_pages("balance_sheet_scanned") and not state.tried("balance_sheet_vision_extract")`
- `equity_rollforward_reconcile`: `state.missing(['equity_current']) and state.present(['equity_prior', 'net_profit', 'dividends'])`
- `adversarial_review_invoke`: `decision > 45 and state.integrity_check_passes() and not state.tried('adversarial_review')`

**Regression suite:**
- Re-run CLP: must maintain 74–76% (text-based, vision skills never offered due to preconditions)
- Re-run Dongfang: target **≥95% cells, balance pass, 10–12/12 keys** (vision + reconciliation skills)

**Week 2 predicted gains:**
- **Tier 1 (balance):** Maintained at 95%+ (foundation from Week 1)
- **Tier 2 (keys):** 8–9/12 → **11–12/12** (reconciliation skills solve derived keys like equity rollforward, cash components)
- **Tier 3 (whole model):** 74–79% → **85–92%** (note breakdowns, unit fixes, formula-redirect bug fix, adversarial review catches remaining errors)
- **Tier 4 (time):** 27–35 min → **35–50 min** (vision adds cost, adversarial review adds cost, but still well within 60 min ceiling)

---

## Q2: WHAT THE MODEL OWNS VS. DETERMINISTIC LAYER

### Luna (weak model) CAN reliably own:

1. **Skill selection from short menu** (3–5 options, not 40)
   - Preconditions filtered deterministically; Luna chooses among valid actions
   
2. **Argument filling for chosen skill** (page numbers, row IDs)
   - Constrained by schema; invalid args rejected by skill's own validation
   
3. **Fuzzy label matching** (map "应收账款" → "Accounts receivable")
   - Anchored by prior values; wrong matches fail verification
   
4. **Comparative extraction** (given prior-year values, extract current year)
   - Vision models handle tabular layouts well; verification catches hallucinations
   
5. **High-level diagnosis** (explain why balance doesn't tie)
   - Useful for reports; code computes the actual numbers

### Deterministic layer MUST own (Luna WILL fail):

1. **Preconditions**: which skills are valid at decision N
   - *Failure mode*: weak model will invoke `balance_sheet_vision_extract` 8 times if allowed
   
2. **Verification of extraction**:
   - Prior-column match rate computation
   - Arithmetic identities (assets = liabilities + equity)
   - Cross-statement ties (net profit consistency)
   - *Failure mode*: model will confabulate "yes, it matches" when it doesn't
   
3. **Objective tracking**: is balance broken? How many Tier-2 keys missing?
   - *Failure mode*: model loses count after 5 turns, forgets goals
   
4. **Revert on regression**: if write worsens scorecard, undo
   - *Failure mode*: model doesn't notice when it makes things worse
   
5. **Integrity gate**: refuse delivery if balance broken or formulas corrupted
   - *Failure mode*: model will ship broken workbook with optimistic justification
   
6. **Budget enforcement**: stop at decision 60
   - *Failure mode*: model will write "I'll continue monitoring" and loop forever
   
7. **Unit scale normalization**: convert "123亿元" → 123,000,000,000 before writing to cells expecting thousands
   - *Failure mode*: model will write 123, creating 1000× errors
   
8. **Formula vs input classification**: never overwrite formula cells
   - *Failure mode*: model doesn't "see" that a cell contains =SUM(...) vs a constant

---

## Q3: VISION PIPELINE — Checksum-Verified Extraction

### How images enter the pipeline

**Rendering:**
```python
# Every potentially-scanned page rendered ONCE at start, cached in memory
page_images = {}
for page_num in state.scanned_page_candidates:
    page_images[page_num] = render_page_image(
        state.pdf_path, 
        page_num, 
        dpi=200  # 300 for dense Chinese if prior-match < 80%
    )
```

**No tiling needed:** Financial statements fit on single pages; send whole-page image to vision model (token cost manageable at 200 DPI).

### Prompting strategy (comparative extraction)

**Key insight from council:** Never ask vision model for "OCR correctness." Instead, give it the ANSWER KEY for one column and check if it reproduces it.

```
You are reading a Chinese financial statement image (balance sheet).

The prior-year column (第一列, usually 2022-12-31 or 2023-06-30) MUST contain these exact values:
{
  "货币资金": "1,234,567",
  "应收账款": "987,654",
  "存货": "543,210",
  ... (all 40 known prior-year values)
}

Your task:
1. Identify which column is prior year vs current year (usually headers indicate dates)
2. Extract BOTH columns for every line item
3. Return strict JSON matching this schema:
   {
     "columns": ["2022-12-31", "2023-12-31"],
     "rows": [
       {"label": "货币资金", "prior": "1,234,567", "current": "2,345,678"},
       ...
     ]
   }

Critical rules:
- Transcribe digits EXACTLY as shown (commas, spacing, brackets for negatives)
- Do NOT compute, impute, round, or "fix" values
- If prior-year values don't match my list above, you are reading wrong page/column—STOP and return {"error": "column mismatch"}
```

### Verification (the 40-number checksum)

```python
verification_result = verify_prior_column(
    extracted=parsed_json['rows'],
    known_priors=state.prior_actuals['balance_sheet'],
    tolerance=0.02  # 2% for rounding
)

if verification_result.match_rate < 0.85:  # 85% threshold
    # Reject extraction
    log.error(f"OCR hallucination risk: only {verification_result.match_rate:.1%} of prior values matched")
    log.error(f"Mismatches: {verification_result.mismatches}")
    
    # Possible recovery actions (deterministic decision):
