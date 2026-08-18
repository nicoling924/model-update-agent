# LLM Council transcript

## Question

# Design question: generic model-anatomy discovery (the CLP campaign)

## Context

Our extraction-first model-update agent now meets the bar on its
calibration company (DFE, a CN-GAAP scanned filing + a CN-structured
workbook): 10/10 headline keys at print, balance passing, every previous
mistake class deterministically closed or taught. The owner's mandate:
prove GENERICITY on a second company (CLP — an English HK-IFRS filing
and a very different workbook anatomy), with the explicit warning that
per-company code is forbidden (the "100 failed runs" died of it) and
teaching-the-LLM is preferred over deterministic wraps, with
arithmetic-checking referees ratified as legal.

Offline diagnosis of CLP BEFORE any live run found (all evidence-backed):

1. **Key-row discovery is the choke point.** The workbook has no spec'd
   key rows; auto-discovery found only TWO (vs DFE's 20), and one is a
   country sub-row ("Aus!23 operating profit"), while "revenue" was
   bound to a row whose prior does NOT tie the disclosure's printed
   prior — a mismapped key. Everything downstream starves: the printed-
   key gate has nothing to pin, Police law 4 has no teeth, the oracle
   proves nothing. Discovery works by English label matching on row
   captions + a cross-sheet prior-consistency filter.
   The CLP workbook anatomy: statements on a sheet named "Final",
   country/segment sheets (SOC, HK Sales, Aus, India, SEA...), drivers
   on "Driver". Units HK$M (the filing ALSO prints HK$M — scale 1).
2. **Face tagging over-matches on English reports**: 78 pages tagged as
   statement faces across 3 documents (a real AR has ~6-10 face pages
   incl. continuations). CJK reports tag by caption lines; English
   captions ("Consolidated Statement of ...") appear in notes and
   cross-references too.
3. The extraction itself is CLEAN on CLP (text-native English PDF): the
   P&L rows come through perfectly with note-refs interleaved. Closure
   grammar has been made bilingual already. So reading is NOT the
   problem — binding the MODEL to the filing is.
4. The announcement has NO cash-flow statement (CF only in the AR) —
   the incomplete-announcement class is exercised too, but that
   machinery exists.

## The question

How should MODEL-ANATOMY DISCOVERY work so it is genuinely generic —
one mechanism that finds the key rows (revenue, NP, EPS, cash, CA/NCA/
CL/NCL, equity, CFO/CFI/CFF, segment blocks) in ANY analyst's workbook,
CJK or English, single-statement-sheet or multi-sheet anatomy — without
per-company code?

Constraints and assets:
- The workbook itself is rich: labels, YEARS of prior actuals, formulas
  (checks like Assets=L+E exist as rows), sheet names/roles (a spec may
  declare sheet roles but never key rows).
- The disclosure's printed figures are known-good anchors: the model's
  prior-year actuals MUST equal the filing's comparatives for the same
  concepts (the fablemode identity we already exploit row-wise).
- An LLM engine (gpt-5.6-luna) is available at discovery time; the
  owner PREFERS teaching/LLM-reasoning over deterministic heuristics,
  with deterministic verification as the referee.
- A wrong key binding is worse than a missing one (it mis-aims the
  Police and the gate) — bindings must be VERIFIED, not plausible.

Specific sub-questions:
1. Is the right design "the LLM reads the workbook and nominates the
   key rows, code verifies each nomination by the prior-identity tie
   against the filing" (nominate-then-verify)? What are its failure
   modes?
2. How should the CONSOLIDATED row be told apart from subsidiary/
   country/segment twins of the same concept (the Aus-operating-profit
   trap) — is prior-identity against the CONSOLIDATED filing statement
   sufficient given segment rows can coincide?
3. Face over-tagging: what is the generic page-level test for "this IS
   the statement face" in any language (our closure/articulation
   machinery can score pages by arithmetic; captions clearly cannot be
   trusted alone)?
4. Should discovery be a ONE-TIME onboarding artifact persisted to the
   workbook's _SPEC tab (the owner accepts no per-model onboarding by
   HUMANS, but a self-onboarding first run is fine), and what must be
   re-verified on every run vs trusted from _SPEC?

Answer concretely; the measure is a design that binds CLP's 10+ keys
correctly tonight without touching a line of CLP-specific code, and
binds the next unseen company equally well.


## Stage 1 — answers

### Response A — openai/gpt-5.6-terra

## Recommended design: LLM proposes an anatomy graph; deterministic code certifies or rejects bindings

Yes: the core pattern should be **nominate-then-verify**, but not as “LLM picks one row, compare one number.”

It should be:

1. **Extract a canonical filing-anchor set**
   - Consolidated revenue, operating profit, profit, profit attributable to owners, EPS, cash, current/non-current assets, current/non-current liabilities, equity, CFO/CFI/CFF, etc.
   - Each anchor includes:
     - canonical concept;
     - statement type;
     - reporting scope: consolidated / parent / segment;
     - period end and comparative period;
     - units and sign convention;
     - printed current and comparative values;
     - source document/page/table/row evidence;
     - confidence that the source page is a genuine statement face.

2. **Parse the workbook into a generic anatomy graph**
   - Sheets, used ranges, merged headers, hidden rows/columns, labels, formulas, dependencies, year columns, actual/estimate regions, check rows, row groupings, sheet roles, named ranges.
   - Do not initially assume that “Final” is consolidated or that “Driver” is a driver sheet. Treat those as evidence, not truth.
   - Identify candidate tables and historical actual blocks.

3. **Ask the LLM to interpret the workbook and nominate a structured mapping**
   - The LLM should not merely return “revenue = Final!17.”
   - It should return a proposed anatomy graph, for example:

```json
{
  "tables": [
    {
      "sheet": "Final",
      "role": "consolidated_financial_statements",
      "period_columns": {"FY2023A": "G", "FY2022A": "F"},
      "scope": "consolidated",
      "units": "HK$M"
    },
    {
      "sheet": "Aus",
      "role": "geographic_segment",
      "scope": "Australia"
    }
  ],
  "bindings": [
    {
      "concept": "revenue",
      "cell_row": "Final!23",
      "period_columns": {"prior": "F", "current": "G"},
      "scope": "consolidated",
      "statement": "income_statement",
      "confidence_reason": "Row is in consolidated P&L block; label and nearby subtotal structure support revenue."
    }
  ]
}
```

4. **Run deterministic certification**
   - A binding is accepted only if it receives a binding certificate.
   - A plausible LLM answer without a certificate is not a key row.
   - A failed or ambiguous binding remains unbound; it must not be used by the printed-key gate, Police, or updater.

This preserves the owner’s preference: the LLM performs semantic interpretation and adapts to unfamiliar workbook anatomy. Deterministic code acts as a referee rather than becoming a growing collection of CLP-specific rules.

---

# 1. Nominate-then-verify: correct, but verify a vector and a model role, not one prior number

The prior-year identity is an excellent verifier, but it is not by itself an identifier.

The required test should be a **binding certificate** with several independent evidence classes.

## Binding certificate for a financial-statement key

For a candidate workbook row/cell range \(r\) and filing concept \(c\), require:

### A. Period identity

The workbook historical actual value must match the filing comparative for the same reporting period.

Validate:

- correct fiscal year/date;
- current vs comparative orientation;
- units/scale;
- sign convention;
- rounding tolerance;
- restatement status;
- reported vs adjusted/underlying/continuing-operations basis.

For CLP, both filing and workbook are HK$M, so scale is expected to be 1. But scale must be inferred generically, not hardcoded. Candidate transformations should include at least:

- \(x\)
- \(-x\)
- \(x / 1{,}000\)
- \(x \times 1{,}000\)
- rounded variants consistent with printed presentation.

A match should be recorded as a specific transformation, not merely “close enough.”

### B. Multi-anchor identity

Do not certify revenue because one prior number matches.

Require as many independently useful anchors as available:

- prior and current historical actuals, if both are in the workbook;
- two or more historical years when available;
- related subtotal values;
- associated statement metrics;
- row’s participation in statement identities.

Examples:

- Consolidated assets should match filing assets and also participate in:
  \[
  Assets = Liabilities + Equity
  \]
- Cash should match filing cash and be consistent with:
  \[
  \Delta Cash = CFO + CFI + CFF + FX/Other
  \]
  where the model presents that bridge.
- EPS must match the filing’s correct EPS definition and, where possible, reconcile with attributable profit and weighted average shares.
- Revenue should sit in an income-statement structure with gross profit, operating profit, profit before tax, and profit after tax/subtotal relationships where those exist.

The more anchors a candidate row satisfies, the stronger the binding. This is also what prevents one coincidental matching number from becoming a false key.

### C. Scope identity

The candidate must be certified as having the same scope as the filing anchor:

- consolidated;
- parent/company-only;
- continuing operations;
- total segment;
- country segment;
- business segment;
- associate/JV;
- attributable to owners;
- non-controlling interests.

Scope should be inferred from a combination of:

- sheet/table role;
- enclosing headers;
- column group headers;
- nearby labels;
- formulas and references;
- whether the row is part of a financial-statement balance/check;
- whether it is a total of segment tabs or segment rows;
- LLM interpretation of workbook structure.

### D. Structural role identity

The row must occupy a structurally appropriate place:

- revenue belongs in a P&L-like block, not merely any row labelled “sales”;
- cash belongs in a balance-sheet/cash-flow bridge context;
- CFO/CFI/CFF belong in a cash-flow block;
- CA/NCA/CL/NCL/equity belong in a balance-sheet block;
- segment rows belong in a repeated segment table or segment sheet, not in the consolidated statements.

This is generic because it uses table structure and formula topology, not company names.

### E. Uniqueness / ambiguity margin

The candidate must be materially better than alternatives.

For every concept, retain all candidates that pass basic numerical tests. Then require either:

- one unique certified candidate; or
- a clear score margin over the next-best candidate.

If two candidates remain indistinguishable, the correct outcome is:

> `AMBIGUOUS — no binding emitted`

That is preferable to binding the wrong row.

## A useful formal rule

A row becomes a key only if:

\[
\text{SemanticFit}
\land
\text{PeriodIdentity}
\land
\text{ScopeIdentity}
\land
\text{StructuralRole}
\land
\text{Uniqueness}
\]

The LLM is primarily responsible for `SemanticFit` and candidate generation. Deterministic machinery certifies the rest.

---

## Failure modes of nominate-then-verify

This pattern is strong, but it has known failure modes that should be explicitly designed for.

### 1. LLM nominates the wrong but numerically matching row

Example: `Aus!23 operating profit` happens to equal the consolidated operating profit comparative.

Mitigation:

- do not accept one-value prior matching;
- require consolidated scope evidence;
- require multiple related anchors and statement-topology evidence;
- compare against alternative candidates globally.

### 2. LLM misses the right row entirely

If the LLM sees only selected rows or is asked a narrow question, recall will be poor.

Mitigation:

- give it a compact but complete workbook map, not a manually pre-filtered subset;
- allow multiple candidates per concept;
- ask it first for table/sheet roles and only then for rows;
- run a second “adversarial search” pass: “What alternative rows could plausibly be consolidated revenue / profit / cash?”
- allow the verifier to ask the LLM targeted follow-ups when no candidate passes.

### 3. Correct row does not exactly equal the filing due to definition mismatch

Common examples:

- continuing vs total operations;
- statutory vs adjusted profit;
- total profit vs attributable profit;
- cash including restricted cash vs cash and cash equivalents;
- restated comparative;
- post-IFRS-16 vs pre-IFRS-16 presentation;
- row is in thousands while filing is in millions.

Mitigation:

- anchors must carry a definition and scope, not merely a number;
- verifier should test known scale/sign transformations;
- accept only explicit, explainable transformations;
- record the selected definition variant in the specification.

### 4. Workbook historicals are stale or wrong

The filing can be right while the workbook prior actual is stale, manually overridden, or based on a prior restatement.

Mitigation:

- do not force-bind from semantic plausibility;
- report `WORKBOOK_PRIOR_DOES_NOT_TIE_TO_FILING`;
- allow the updater to repair an explicitly approved historical hardcode only if policy permits;
- do not use that row as an anchor until it has been repaired and re-certified.

### 5. Formula rows are not writable model inputs

A “revenue” row may be a formula output driven by a lower operational schedule. Binding it as a write target would be wrong even if it is the correct printed key.

Mitigation:

Each binding needs two distinct fields:

```json
{
  "display_row": "Final!23",
  "key_cell": "Final!G23",
  "write_policy": "formula_output",
  "upstream_driver_region": "HK Sales!G12:G18"
}
```

The printed-key gate can monitor the display row. The model updater must respect `write_policy` and update the appropriate upstream cells, not overwrite formulas.

---

# 2. Consolidated versus country/segment twins: prior identity is necessary, not sufficient

The Aus-operating-profit trap is exactly why a prior-value tie cannot be the sole test.

A country operating-profit row can accidentally equal consolidated operating profit in a given year. It can even equal it in two years if the other segments are small or loss-making. Therefore:

> A numeric tie to a consolidated filing figure is evidence of identity, but not proof of consolidated scope.

## Required consolidated-scope tests

A candidate is eligible to be a consolidated key only if it has positive evidence for consolidated scope.

### Strong positive evidence

1. **It sits in a table classified as consolidated statements**
   - broad financial-statement row set;
   - multiple statement sections;
   - balance-sheet or cash-flow identities;
   - consolidated presentation headers;
   - final output sheet role;
   - links from multiple operating tabs into a summary structure.

2. **It participates in consolidated checks**
   - assets = liabilities + equity;
   - cash-flow closing cash tie;
   - profit-to-equity or retained-earnings roll-forward;
   - consolidated segment-total reconciliation.

3. **It is downstream of multiple business/geography components**
   - formula references multiple country sheets;
   - formula sums region/business unit outputs;
   - or is the target of a consolidation bridge.

4. **It is not itself part of a repeated segment structure**
   - a country sheet, a region column, or a repeated block is negative evidence for consolidated scope.

5. **Its context contains other consolidated keys**
   - revenue, gross profit, operating profit, tax, profit, EPS in a coherent P&L;
   - CA/NCA/CL/NCL/equity in a coherent balance sheet.

### Negative evidence

A candidate should be heavily penalized or excluded from consolidated eligibility if:

- sheet/table title names a country, geography, business unit, division, legal entity, or customer group;
- it appears in a repeated region-by-region pattern;
- it reconciles upward into another row;
- it is referenced by a summary/consolidation sheet rather than being the summary;
- it has no balance-sheet/cash-flow peer structure.

## Global assignment matters

The system should not bind concepts independently. It should solve a constrained assignment problem across all keys.

For example:

- `Final!23` may be the only row that permits revenue, operating profit, cash, equity, and the balance check to form one coherent consolidated anatomy.
- `Aus!23` may numerically match operating profit but cannot simultaneously support the full consolidated P&L/balance-sheet/cash-flow graph.

The correct decision is therefore based on the best **whole-workbook explanation**, not just the best row for one label.

## What if consolidated and segment rows are truly indistinguishable?

Then no mechanism can prove which one is intended from the workbook alone.

If two rows:

- have the same label;
- have the same values for all available periods;
- have the same formulas/topology;
- have no differentiating scope metadata;

then the evidence is insufficient. A generic system must abstain.

The desired invariant is:

> No wrong key binding is better than a missing key binding.

The engine should report an ambiguity artifact and refuse live model update rather than invent confidence.

---

# 3. Generic statement-face detection: score statement topology, not captions

Caption-only tagging is inherently weak in English annual reports because captions are repeated in:

- notes;
- contents pages;
- accounting policy references;
- cross-references;
- “see Consolidated Statement of…” prose;
- multi-page note tables.

The generic question is not “does this page contain a statement caption?” It is:

> “Does this page participate in a table whose numeric and semantic topology behaves like a primary financial statement?”

## Build page/table-level statement-face scores

Each extracted page should receive evidence scores from several independent dimensions.

### A. Financial table geometry

A statement face usually has:

- a dense tabular body;
- a row-label column;
- two or more aligned reporting-period columns;
- repeated numeric columns;
- statement-like indentation/subtotal hierarchy;
- many rows, not one isolated table

### Response B — google/gemini-3.1-pro-preview

Here is the generic, zero-custom-code design for the Model-Anatomy Discovery engine. 

The core philosophy of this design is **Semantic Nomination + Mathematical Interrogation**. We use the LLM (gpt-5.6-luna) for what it excels at (understanding that "Final" means consolidated and "Turnover" means Revenue), but we trust it for absolutely nothing. Every nomination must survive a deterministic, multi-variable mathematical gauntlet.

Here are the concrete answers and architectural blueprints for your four sub-questions.

---

### 1. The Core Mechanism: Nominate-then-Verify
**Yes, Nominate-then-Verify is the correct architectural pattern.**

**How it works generically:**
1. **The Skeleton Extraction (Code):** Code strips the analyst workbook into a lightweight JSON "Skeleton". It drops the columns of numbers but keeps: `Sheet_Name`, `Row_Index`, `Row_Caption`, `Is_Calculated` (boolean: does it have a formula?), and `Dependency_Target` (does this row sum up data from other sheets?).
2. **The Nomination (LLM):** The LLM is given the standard target keys (Revenue, NP, Total Assets, etc.) and the Skeleton. 
   * *Prompt instruction:* "You are mapping a financial model to standard keys. Return up to 3 candidate rows for each key, ranked by likelihood. Consider sheet names ('Final' or 'Consolidated' are better than 'Aus' or 'Segment')."
3. **The Referee (Code):** The deterministic engine evaluates the candidates sequentially. To become a verified binding, a candidate row MUST pass the **Fablemode Identity Test**: `Model_Prior_Actual (t-1) == Filing_Printed_Comparative (t-1)`. 

**The Failure Modes & Mitigations:**
* **Failure Mode A: The Coincidental Tie.** A subtotal happens to equal a total in $t-1$.
  * *Mitigation:* The Referee requires a **Multi-Year Vector match**. It doesn't just check $t-1$; it checks $(t-1, t-2, t-3)$ against the filing's multi-year history. Coincidences do not survive 3 years of actuals.
* **Failure Mode B: The Restatement Trap.** The filing restated $t-1$, so the model's locked historical actual no longer ties to the printed comparative, causing a false negative.
  * *Mitigation:* If $t-1$ fails, the Referee automatically shifts to check $t-2$ and $t-3$. If those tie, the binding is accepted, and the engine flags a restatement warning for $t-1$.

### 2. Solving the Consolidated vs. Segment Trap ("Aus Operating Profit")
If "Aus!23 Operating Profit" and "Final!45 Operating Profit" both mathematically tie to the filing in $t-1$ (e.g., if Australia was the only profitable region that year), how do we guarantee the engine picks "Final"?

**Prior identity is necessary, but NOT sufficient. We need Topological Dominance.**

When the Referee sees multiple candidates that mathematically tie, it applies the following deterministic tie-breakers:
1. **Formula Rooting (The Ultimate Proof):** Code inspects the Excel formulas. Does "Final!45" equal `SUM(Aus!23, India!23, SEA!23)`? If a candidate row mathematically *consumes* the other candidate rows, the consumer is definitively the Consolidated key. 
2. **LLM Sheet-Role Voting:** If formula links are broken/hardcoded, the Referee passes just the sheet names to the LLM: *"Which of these sheets represents the consolidated group rather than a segment: ['Final', 'SOC', 'Aus', 'HK Sales']?"* The LLM will easily flag "Final" as the parent. 

*Result:* The engine binds to "Final!45" because it sits at the top of the workbook's formula hierarchy and occupies a semantically dominant sheet.

### 3. Solving Face Over-Tagging (The 78-Page Problem)
Do not use English captions ("Consolidated Statement of...") as the primary gate. They appear in the TOC, Directors' Report, Notes, and Auditor's letter. 

The generic page-level test for "This is a statement face" relies on your existing **Arithmetic Closure Engine**, inverted to act as a radar.

**The "Density and Roots" Filter:**
1. **Arithmetic Density:** Code scans the 78 flagged pages. A text-heavy Note or TOC might have numbers, but it lacks dense algebraic articulation. Run the closure engine on each page. A true Face Statement will yield high arithmetic density (e.g., $>10$ valid $A + B = C$ relationships on a single page). Pages with $<3$ relationships are immediately discarded as noise.
2. **The Root Presence Test:** Segment notes also have high arithmetic density. To isolate the *Primary* Face Statements, the system asks: *Does this page contain the anchors?* The true P&L face MUST contain the printed figure that verified as "Consolidated Revenue". The true Balance Sheet MUST contain the verified "Total Assets". 

*Result:* By filtering for 1) Math Density and 2) Verification-Anchor presence, the 78 pages will deterministically collapse to the 3-5 actual face statements, regardless of whether they are in English, Chinese, or Swahili.

### 4. The Lifecycle: One-Time Onboarding vs. Per-Run
**Discovery MUST be a one-time self-onboarding artifact persisted to the `_SPEC` tab.** 

Running LLM discovery on a 50-sheet workbook every quarter is structurally fragile, slow, and violates the principle of deterministic execution at print time.

**The Generic Lifecycle:**
1. **First Run (Self-Onboarding):** The LLM/Referee discovery pipeline runs. It finds the 10+ keys. It writes the exact addresses to the `_SPEC` tab: 
   * `[Key: Revenue, Sheet: Final, Row: 45, Caption_Hash: "Turnover", Match_Confidence: High_MultiYear_Tie]`
2. **Subsequent Runs (Quarterly Update):** The system **bypasses LLM discovery** and goes straight to deterministic verification. It reads `_SPEC` and asserts two things:
   * *Structural Integrity:* Does `Final!45` still contain the string "Turnover"?
   * *Math Integrity:* Does the model's $t-1$ for `Final!45` tie to the *new* filing's $t-1$ comparative?
3. **Invalidation (The Safety Net):** If an analyst inserts 5 rows above Revenue, the Structural Integrity check fails (`Final!45` is now `Final!50`). If this happens, the agent securely triggers a **Targeted Re-Discovery** for that specific key, finding the new row, verifying the math tie, and silently healing the `_SPEC` tab.

### Summary of the Generic Pipeline Applied to CLP Tonight:
1. Code extracts CLP workbook skeleton.
2. LLM nominates "Turnover" on 'Final' and 'Aus' sheets.
3. Referee tests against CLP's printed comparatives. It finds ties on both.
4. Referee checks Excel topology. Discovers 'Final' is a parent/summation of 'Aus'. Discards 'Aus'.
5. Referee checks $(t-1)$ and $(t-2)$ actuals to confirm it's not a coincidence.
6. Binding verified. Persisted to `_SPEC`.
7. Extraction reads CLP English PDF. Finds 78 pages with keywords.
8. Arithmetic engine scores pages. Filters out TOC/Notes due to zero math closure. Filters out Segment notes because they lack the verified Consolidated Revenue anchor. 
9. Only the true CLP HK-IFRS faces remain. Extraction proceeds perfectly.

### Response C — x-ai/grok-4.6

**Nominate-then-verify is the right spine.** The LLM proposes bindings; only the prior-identity referee (plus a constellation test) may commit them. Persist the survivors to `_SPEC`. Re-verify identity every run. Never ship a plausible unmatched key.

Wrong binding is worse than missing: a miss starves one Police law; a wrong bind aims the gate at Aus OP and launders a green run. The design below is built so a twin cannot survive the referee even if the LLM is glib.

---

## 0. What “a key” is

A key is not a label. It is a **verified identity**:

```
model[sheet, row, prior_col]  ==  filing[concept, comparative]
  after scale, sign, and unit normalisation
  AND the row sits in a block whose other committed keys
      also match the same filing face (constellation)
```

Concepts to bind (the 10+ the gate cares about):

| Class | Concepts |
|---|---|
| P&L | revenue, operating profit / EBIT, profit before tax, NP / NPAT, EPS (basic, diluted if present) |
| BS | CA, NCA, total assets, CL, NCL, total liabilities, equity, cash |
| CF | CFO, CFI, CFF, Δcash (announcement may lack the face — bind from AR or leave unbound) |
| Structure | the consolidated statement *block* on its home sheet; segment/country blocks as second-class citizens |

A binding record:

```
concept, sheet, row_id, year_col_map, scale, sign, unit,
block_id, role=consolidated|segment|bridge|unknown,
evidence={prior_tie, constellation_score, formula_role},
status=committed|unbound
```

Missing → `unbound`. Never a guess.

---

## 1. Nominate-then-verify

### Phase A — workbook inventory (deterministic, cheap, generic)

No company names. For every sheet:

- row captions, indent / group outline, formula text, cached values
- year headers (map columns → FY-n; do not assume left-to-right)
- detected units in header/footer (`HK$M`, `RMB'000`, `万元`…)
- formula *roles*: balance check (`TA − TL − E ≈ 0`), roll-forwards, `=Aus+HK+India` consolidators, EPS `=NP/WA shares`
- a coarse sheet-role prior from name **plus** structure, never name alone:  
  `statement_home` if it hosts a multi-year P&L *and* a BS that closes;  
  `segment` if repeating country/division stubs with a total that feeds elsewhere;  
  `driver` / `check` / `bridge` otherwise

This is the only “anatomy” code. It is language-agnostic if you treat CJK/English captions as opaque strings plus a small bilingual synonym list for *units and years*, not for keys.

### Phase B — LLM nomination (taught, not wrapped)

Give the model, in one shot:

1. The inventory (captions + 2–3 prior-year numbers + formula crumbs + sheet-role prior). Truncate drivers. Keep every sheet that looks like a statement or a total.
2. The filing’s **printed comparatives** for the concept list, already scale-normalised, with face provenance (“P&L face, FY24 comparative”).
3. Standing instructions (this is the teaching; it replaces per-company code):

- Nominate ≤ 3 candidates per concept, ranked. Prefer `unbound` to a 0.6 guess.
- Consolidated beats any country/segment/division twin of the same words.
- A row whose formula is `=sum(segments)` *can* be the consolidated key (it is the total). A row that *feeds* such a sum cannot.
- “Revenue” bound to a row whose prior does not equal the face comparative is not revenue.
- Same number on two rows is not a tie-breaker — say so.

Output: JSON nominations only. No side effects.

### Phase C — referee (the only thing that can commit)

For each nomination, all of these must hold:

1. **Prior-identity.** `|model_prior − filing_comparative| ≤ tick` after applying the declared scale/sign. Tick is 0.5 unit at the *filing’s* printed scale (CLP: HK$M, scale 1). If the model stores thousands and the filing millions, the nominee must declare scale; the referee tries `{1, 1e3, 1e6, 1e-3}` *only* if the LLM omitted it, and records which one won. Ambiguous scale → reject.
2. **Column is actually the prior.** The year header must parse to the filing’s comparative year. A coincident number in FY-2 is not a tie.
3. **Not a check / not a variance / not a YoY %.** Formula role from Phase A. A row named “balance check” that happens to equal equity is not equity.
4. **Constellation (the twin-killer — see §2).**
5. **Uniqueness.** If two nominees pass 1–4, keep the one whose `block_id` already holds more committed siblings. If still tied, **commit neither**.

Failure modes of nominate-then-verify, and the counter for each:

| Failure | Why it happens | Counter |
|---|---|---|
| Numeric coincidence (Aus OP == group OP) | one concept, one year | constellation + sheet/block role |
| Restatement | model prior is unrestated; face comparative is restated | identity fails → `unbound` + restatement flag; do not “fix” the bind |
| Scale / sign | HK$M vs $'000; expenses stored positive | declared or tried scale; P&L expense sign probe against a second line |
| LLM skips the real row | long sheet, bland caption | inventory must include *numbers*, not just labels; if concept unbound, second-pass prompt restricted to rows whose prior equals the printed figure (deterministic candidate cut, LLM only ranks) |
| LLM picks a formula total on a bridge sheet | looks consolidated | constellation: bridge sheets almost never host *all* of {rev, NP, equity, TA} |
| Key is a computed pair (EPS) | not a raw amount | allow identity on the printed EPS *or* bind NP + WAS and verify `NP/WAS`; still referee’d |
| No CF face in the announcement | incomplete document | leave CF unbound; do not invent from the AR unless the AR face was itself referee’d in the same run |
| Label-only match, wrong year | English “Revenue” everywhere | identity is numeric; labels are nomination features only |

The second-pass “rows whose prior equals the printed figure” is the important backstop: it is *not* per-company code, it is the fablemode identity run in reverse, and it is how CLP’s revenue bind gets off the mismapped row tonight. The LLM still has to pick *which* equal-valued row is the consolidated one; the constellation referee decides.

---

## 2. Consolidated vs Aus-operating-profit

**Prior-identity on one concept is not sufficient.** Segment OP can equal group OP (dominant segment, rounding, or bad luck). Identity against the *consolidated* face is necessary, not adequate.

What *is* adequate is a **block constellation**:

1. Cluster rows into blocks by (sheet, outline parent, contiguous statement-shaped region). A block that contains revenue, several cost lines, and a profit total is a P&L block. A block that contains CA/NCA/CL/NCL/equity is a BS block. Cross-sheet is allowed only if a formula consolidator points at them.
2. Score each P&L block against the *vector* of filing comparatives `{revenue, OP, PBT, NP}` (whatever the face printed). Score = how many of those printed figures appear as priors in that block, unique-matched.
3. The winning P&L block is the one with the unique max score ≥ 2 (two independent ties). Same for BS `{TA, TL, equity, cash}` and CF `{CFO, CFI, CFF}` when the face exists.
4. Keys may only be committed *inside* the winning block for their statement. “Aus!23 operating profit” lives in a block that matches at most OP — it loses to `Final`’s block that matches rev+OP+PBT+NP.
5. Sheet-role prior is a tie-break, not a vote. `Final` vs `Aus` is a hint the LLM already sees; the referee does not need the string “Final”.
6. If two blocks tie (rare: a management-account sheet that reprints the face), prefer the block whose formulas are *sources* (literals / links from driver) over the block that is a `SUM` of the other. If still tied, unbound.

Coincidence of a *vector* of 3–4 independently printed figures on a non-consolidated sheet is not a thing that happens in real workbooks. That is the generic answer to the Aus trap. One-number identity was the old discovery’s bug.

Segment *blocks* (the thing you do want, later) are discovered the same way, against the **segment note** face, not the primary statements. They must roll up to the committed consolidated total. They never compete for the primary keys.

---

## 3. Face over-tagging (page-level, any language)

Captions are a prior. **Articulation is the test.** An English note that mentions “Consolidated Statement of Profit or Loss” has the caption and none of the arithmetic.

Score every page (and every 2-page window, for continuations):

| Signal | Face | Note / narrative |
|---|---|---|
| Year-pair columns matching the reporting dates | present, aligned | absent or a single year buried in prose |
| Numeric density in a grid | high | low / inline |
| Local sum-closure: labelled total = sum of the preceding body (tolerance 1 tick), recursively | many | few |
| Global articulation: BS `A = L+E`; P&L walks to “profit for the period”; CF `CFO+CFI+CFF = Δcash` | holds on page or page+1 | does not |
| Note-ref *column* (right-aligned markers `5`, `12(a)`) | typical | refs are inline sentences |
| Narrative token ratio | low | high |
| Caption lexicon (bilingual, small list: Statement of / 利润表 / 綜合損益 / …) | bonus only | often present as a cross-reference — **never sufficient** |

Commit a page as a face iff `articulation_score ≥ τ` (calibrate τ on the fact that a real AR has ~6–10 face pages including continuations; 78 tagged means τ is currently ~0). Caption-only hits are discarded. A page that closes `A = L+E` for the reporting dates *is* a BS face even if the heading is “Financial Position (continued)”.

Document choice: score announcement and AR separately. Prefer the announcement for P&L/BS when it has a closing face (it’s what the market saw). Take CF from the AR only when the announcement has no CF face — that is the incomplete-announcement class, already in the machinery. Do not union 78 pages across 3 books.

CJK vs English: the scorer never reads a sentence. Closure grammar you already made bilingual is the language-specific piece; it stays where it is.

---

## 4. `_SPEC`: self-onboarding, what is trusted

Yes — **one self-onboarding run**, write the committed bindings to a `_SPEC` tab (or sidecar). No human per-model onboarding. The owner’s “no per-company code” is intact because the writer is the same generic pipeline.

**Trusted from `_SPEC` (structure, not truth):**

- `concept → (sheet, row_id, scale, sign, block_id)`
- year-column map *shape* (which header row, not the values)
- sheet-role labels the inventory assigned
- unit string

**Re-verified every run (truth):**

- row still exists, caption has not been replaced by a different concept (soft: embedding/token overlap; hard fail only if identity also fails)
- **prior-identity still holds** on the new filing’s comparative vs the model’s now-shifted prior column  
  - hold → keep  
  - fail + restatement detected on the face (comparative ≠ last year’s printed current) → keep bind, flag restatement, do not retarget  
  - fail + no restatement → **drop that key, rediscover it only**
- constellation of the surviving siblings still unique to that block (someone inserted an “Aus” sheet that reprints the face — re-score)
- face pages re-scored; if the previous face page no longer articulates, re-extract printed anchors before testing identity

`_SPEC` is a cache of *nominations that once passed*. It is not a constitution. The referee is the constitution.

First run on CLP tonight: empty `_SPEC` → full discovery → write. Next company: same. Next year on CLP: re-verify, almost certainly keep.

---

## What this does on CLP without CLP code

- Inventory sees `Final` as the only sheet whose blocks close a P&L *and* a BS; `Aus` / `HK Sales` / `India` are segment-shaped; `Driver` is drivers.
- Face scorer keeps ~the real statement pages of the announcement (no CF) plus AR CF if you ask for it; the 78 caption hits die.
- Printed anchors: revenue, OP, NP, EPS, the BS totals, at HK$M scale 1.
- Reverse-identity cut lists every row whose prior equals those prints. The mismapped “revenue” row is absent from the revenue cut (its prior does not tie). The Aus OP row *is* in the OP cut.
- Constellation: `Final`’s P&L block matches rev+OP+PBT+NP; `Aus` matches at most OP. Aus is rejected. Revenue / NP / EPS / BS keys commit on `Final`.
- CF keys stay `unbound` on the announcement-only path, or commit from the AR CF face if that face passed articulation.
- `_SPEC` written. Gate has pins. Police law 4 has teeth.

The same steps on a CJK single-sheet workbook reduce to “one block wins the constellation,” which is what already worked on DFE — except DFE’s 20 auto-keys were label-match luck. This mechanism does not need that luck.

---

## Teaching the LLM (the actual prompt contract)

Keep the deterministic surface tiny: inventory, identity, constellation, face articulation, `_SPEC` I/O. Put the judgement in a short standing brief:

- Prefer unbound to a single-number match.
- Consolidated block = the block that reproduces the *set* of printed face figures.
- Segment/country/division sheets are not statement homes unless no other block scores.
- Scale and sign are part of the nomination.
- You will be overruled by arithmetic; do not argue.

Do not add CLP synonyms, do not special-case `Final`, do not whitelist “operating profit” vs “Aus!23”. If the next workbook names the face `Consol.` and the segments `S1..S9`, nothing changes.


## Stage 2 — peer reviews

### Review by openai/gpt-5.6-terra

## Response A

### What it does well

Response A has the strongest architecture after Response C, especially on the central distinction between **semantic proposal** and **deterministic certification**.

- It correctly frames the solution as an **LLM-proposed anatomy graph plus deterministic binding certificates**, rather than a label matcher with a numerical sanity check.
- It recognizes that a key binding is not just a row address. The proposed anchor metadata is appropriately rich:
  - concept;
  - statement type;
  - scope;
  - period;
  - scale/sign;
  - source evidence;
  - face-page confidence.
- Its workbook-anatomy graph is well conceived. It includes useful generic signals: formulas, dependencies, merged headers, hidden rows, year columns, sheet roles, named ranges, historical blocks, and check rows.
- It correctly says that prior-year identity is a verifier, not a unique identifier. This is crucial given the CLP Aus operating-profit collision.
- The proposed binding certificate has several strong dimensions:
  - period/date identity;
  - scale and sign normalization;
  - multi-anchor matching;
  - structural role;
  - scope identity;
  - uniqueness margin.
- It explicitly identifies the important failure mode where the correct displayed key is a formula output rather than a writable input. Distinguishing `display_row`, `key_cell`, and `write_policy` is very useful operationally. A system can monitor a formula-output row as a printed key without overwriting the formula.
- Its treatment of the consolidated-versus-segment problem is particularly good:
  - one-value equality is not proof;
  - country/segment sheet context is negative evidence;
  - participation in group-level checks is positive evidence;
  - multi-segment downstream formula relationships are useful;
  - global assignment across keys is better than independent row selection.
- It appropriately allows abstention: if two rows cannot be distinguished with available evidence, the system should not bind either. This aligns with the stated preference that a missing key is safer than a wrong key.

### What it does poorly

The supplied response is incomplete. It begins a promising statement-face scoring section but stops before it actually delivers the generic page-level certification rule, persistence design, and recurring verification policy required by sub-questions 3 and 4.

Specific weaknesses:

- The face-detection section is only partially developed. It starts listing geometry features, but does not specify:
  - a concrete face score or acceptance rule;
  - how to handle continuations across pages;
  - how to distinguish a primary face from a well-structured financial note;
  - how announcement and annual-report sources are selected when cash flow is absent from the announcement;
  - how the face score is used before extracting the anchor set.
- It does not answer the `_SPEC` lifecycle question. There is no explicit distinction between:
  - fields trusted as cached structural metadata;
  - fields that must be re-certified every run;
  - invalidation/re-discovery triggers;
  - restatement handling;
  - behavior when rows shift due to inserted rows or changed layouts.
- Some of its certificate criteria are conceptually correct but not sufficiently operationalized. For example, “scope identity” and “structural role identity” need a reproducible scoring/constraint system, otherwise they risk becoming a vague deterministic wrapper around LLM judgment.
- It suggests accepting transformations such as scale/sign variants but does not clearly require uniqueness of the chosen transformation. Without that requirement, a small rounded number could potentially fit under more than one scale/sign interpretation.
- It correctly recommends global assignment, but it does not specify the actual assignment constraints. For example, a useful generic implementation would enforce that all consolidated P&L keys come from one winning P&L block unless explicit formulas prove a cross-sheet consolidated layout.

Overall, A is technically thoughtful and highly aligned with the problem, but it does not fully answer all four requested design areas in the supplied form.

---

## Response B

### What it does well

Response B is clear, concise, and correctly identifies the main architectural pattern:

- It endorses **nominate-then-verify**.
- It correctly says that prior identity alone is vulnerable to coincidental matches.
- It proposes asking the LLM for multiple ranked candidates rather than one irreversible guess.
- It identifies formula topology as useful evidence for distinguishing consolidated output rows from segment rows.
- It correctly treats captions as weak face-page evidence and proposes arithmetic structure as a stronger alternative.
- It supports persisting discovered bindings to `_SPEC` and performing re-verification on later runs.
- It gives a straightforward CLP narrative: LLM nominates candidates, formula hierarchy distinguishes `Final` from `Aus`, and the result is persisted.

These are all directionally correct and make the response easy to understand.

### What it does poorly

Response B is substantially too simplistic for the stated safety requirement: a wrong key binding is worse than a missing one.

#### 1. The proposed workbook “skeleton” discards essential evidence

It says code “drops the columns of numbers” while giving the LLM only captions, row indices, formula flags, and dependencies. That is a major weakness.

The LLM needs at least a compact history vector, period headers, units, and nearby values to reason about whether rows belong to the same financial-statement block. The filing anchors and workbook history are the central evidence in this task. Omitting them weakens nomination unnecessarily.

#### 2. The referee is still effectively a one-dimensional prior-value test

Although the response mentions multi-year matching, its core certification test remains:

> `Model_Prior_Actual == Filing_Printed_Comparative`

That is necessary but not sufficient. It lacks a mandatory block-level constellation requirement such as:

- revenue + operating profit + PBT + NP in one P&L block;
- assets + liabilities + equity in one balance-sheet block;
- CFO + CFI + CFF + cash bridge in one cash-flow block.

Without this, the Aus trap can still survive whenever a segment happens to match multiple values or a segment sheet reproduces group metrics.

#### 3. The consolidation tie-breaker is not reliable enough

The answer relies heavily on:

- direct formula rooting; and
- LLM sheet-name interpretation.

Neither is a sufficient generic proof.

Formula rooting can fail because:

- consolidated outputs may be hardcoded;
- formulas may reference intermediate bridges rather than country sheets;
- summary sheets may reprint results without being the intended model output;
- some consolidated rows are not direct sums of segments due to eliminations, corporate costs, FX, or accounting adjustments.

LLM sheet-role voting based on names such as “Final” versus “Aus” is useful nomination evidence, but it cannot serve as deterministic verification. A future workbook may call the consolidated sheet “Output,” “Summary,” “Model,” “P&L,” or something opaque.

#### 4. The multi-year rule is not generally available

The response assumes that three years of comparable historical data will exist in both the filing and workbook. That may be false for:

- newly listed companies;
- shortened reporting histories;
- acquisition-heavy groups;
- workbooks containing only one prior actual;
- filings that print only current and comparative periods.

A robust design must work with one comparative value, but demand stronger structural and constellation evidence when only one value is available.

#### 5. The restatement policy is unsafe

It says that if \(t-1\) fails but \(t-2\) and \(t-3\) tie, the binding is accepted and a restatement warning is raised. That can be reasonable as a diagnostic, but not as unconditional certification.

A restated comparative can reflect:

- changed accounting policy;
- continuing/discontinued operations;
- reclassified line items;
- changed definition of cash;
- altered segment reporting;
- a stale workbook prior.

The engine should retain the prior binding as a candidate structural mapping, flag it, and require explicit re-certification against the revised definition and updated historical values. It should not silently accept a current mismatch merely because older years match.

#### 6. The face-page method is under-specified and has invalid assumptions

The “more than 10 arithmetic relationships” requirement is not generic.

- A genuine balance sheet may have one dominant equation: assets = liabilities + equity.
- A P&L may have very few exact arithmetic equations due to presentation conventions.
- A segment note can contain many arithmetically closing totals.
- A cash-flow statement can span multiple pages and require bridge-level rather than page-local closure.

The “Root Presence Test” is also circular: it requires already verified anchors to identify face pages, yet the anchors may depend on correctly identifying the face pages first. A robust system needs an iterative or joint face-and-binding process, with initial topology scoring followed by anchor-supported confirmation.

#### 7. `_SPEC` verification is too brittle

Checking whether `Final!45` still has the exact string “Turnover” is not enough. Row insertion, label edits, localization, indentation changes, or formula movement can invalidate a fixed address without changing the underlying row concept.

A persisted specification should store stable structural fingerprints, such as:

- sheet identity/fingerprint;
- row label features;
- neighboring labels;
- block identity;
- formula/dependency fingerprint;
- period-column mapping;
- prior-identity evidence;
- source-anchor definition.

The response’s targeted rediscovery idea is sound, but the re-verification criteria are too weak.

---

## Response C

### What it does well

Response C is the strongest answer because it gives a concrete generic mechanism that directly addresses the CLP failure mode without relying on CLP-specific labels, sheet names, or code.

#### 1. It defines a key correctly

Its central principle is excellent:

> A key is a verified identity, not a label.

It then turns that into a concrete binding record containing:

- concept;
- sheet and row;
- year-column map;
- scale/sign/unit;
- block identity;
- role;
- evidence;
- committed versus unbound status.

That is exactly the right artifact for both first-run onboarding and later deterministic operation.

#### 2. It gives the right division of labor

The response clearly separates:

- deterministic inventory;
- LLM semantic nomination;
- deterministic referee;
- persisted `_SPEC`.

This respects the owner’s preference for LLM reasoning while ensuring that the LLM cannot commit unsafe bindings.

The LLM is used for semantic interpretation and candidate generation, not final truth. The referee owns truth.

#### 3. It fixes the key-row discovery choke point

The reverse-identity candidate cut is particularly strong:

> If a concept is unbound, deterministically find rows whose historical value equals the filing comparative, then ask the LLM to rank those rows.

This directly solves the CLP revenue problem. If the current auto-discovered “revenue” row does not tie the filing comparative, it should not even remain an eligible revenue candidate. This is generic, uses the known-good filing anchors, and does not require a CLP synonym list.

#### 4. It gives a robust answer to the Aus operating-profit trap

The block-constellation approach is the best part of the response.

Rather than asking “which operating-profit row matches?”, it asks which block reproduces the vector of known consolidated filing figures:

- P&L: revenue, operating profit, PBT, NP;
- balance sheet: assets, liabilities, equity, cash;
- cash flow: CFO, CFI, CFF.

This makes a country operating-profit coincidence insufficient. `Aus!23` may match operating profit, but it should not be able to reproduce the consolidated P&L vector. A `Final` P&L block matching revenue, OP, PBT, and NP is overwhelmingly stronger evidence.

The response also correctly says that segment blocks should be discovered against segment-note anchors and must roll up to the committed consolidated total, rather than competing for primary-statement keys.

#### 5. It properly handles abstention

The response repeatedly preserves the key safety invariant:

- ambiguity means unbound;
- no plausible unmatched key may be shipped;
- a wrong binding is worse than a missing one.

That is exactly the requested risk posture.

#### 6. It gives a credible generic face-page test

The proposed face detector appropriately treats captions as a weak prior and articulation as the primary test. Its useful signals include:

- aligned reporting-period columns;
- numeric grid density;
- local subtotal closure;
- global statement articulation;
- note-reference-column patterns;
- narrative-token ratio;
- page-plus-next-page windows for continuations.

It also correctly separates source selection by statement type:

- use announcement P&L/BS if it contains a closing face;
- obtain cash flow from the annual report only when the announcement lacks it;
- do not merge all caption-hit pages across documents.

That directly addresses the CLP incomplete-announcement case.

#### 7. It gives a practical `_SPEC` policy

The distinction between trusted and re-verified fields is strong:

Trusted as cached structure:

- concept-to-row mapping;
- scale/sign;
- block identity;
- sheet-role and layout metadata.

Re-verified every run:

- row still exists and remains structurally recognizable;
- prior-year identity;
- block constellation;
- face-page articulation;
- source-anchor validity.

Its statement that `_SPEC` is “a cache of nominations that once passed” rather than a permanent truth source is exactly right.

### What it does poorly

Despite being the best response, C still has several areas that should be tightened.

#### 1. Some thresholds are too rigid

The rule that a winning block requires a unique score of at least two matching anchors is sensible as a minimum, but not universally sufficient or universally necessary.

Potential issues:

- A compact workbook might only expose one directly comparable P&L key in prior actuals.
- A segment sheet could coincidentally reproduce two values.
- A correct consolidated block might have renamed or formula-derived subtotals that make only one direct line comparable.

The implementation should use a weighted evidence score and require a margin over alternatives, not only a fixed count threshold. For example, a block with revenue + NP + balance-sheet closure + multi-sheet aggregation is much stronger than one with two coincidental numerical matches.

#### 2. The source-versus-SUM tie-breaker can be wrong

The response says that if two blocks tie, prefer the block whose formulas are “sources” rather than a `SUM` of another block.

That is not always correct. The intended consolidated output sheet is often explicitly a formula-driven summary that sums operating regions, incorporates eliminations, or links to schedules. The `SUM` output may be the correct displayed key row, while the “source” rows are components.

A better rule would distinguish:

- **consolidated presentation/output block**;
- **consolidation calculation block**;
- **segment/component blocks**;
- **driver blocks**.

The chosen key should normally be the displayed row in the verified consolidated presentation block, even if it is downstream of formulas.

#### 3. Face detection should not rely exclusively on arithmetic closure

The response’s face scorer is strong, but a face can have limited page-local arithmetic, especially for:

- a P&L with few explicit subtotal relations;
- statement continuations;
- statements with comparative columns but sparse rows;
- regulated reporting formats with unusual grouping.

Conversely, notes can have extensive numerical closure.

The design should make face identification a combined table-level and document-structure problem, including:

- aligned reporting-period headers;
- table continuation continuity;
- row-label hierarchy;
- note-reference-column geometry;
- presence of standard anchor concepts;
- cross-page linkage;
- statement sequence within the document;
- arithmetic closure.

C implies much of this, but it could state the scoring and acceptance process more explicitly.

#### 4. Restatement handling needs a more explicit state model

The response is broadly right to avoid retargeting a row merely because a filing comparative changes. However, it should distinguish:

- structural binding still likely correct but values require historical refresh;
- concept definition changed;
- filing restated prior but workbook has stale historicals;
- filing source extraction error;
- actual row has moved or been replaced.

Rather than simply “keep bind, flag restatement,” the system should mark the binding as something like `STRUCTURALLY_VALID / FINANCIALLY_STALE`, block use as a strict printed-key gate until the historical value is reconciled, and require a defined repair path.

#### 5. The statement that multi-line vector coincidence “is not a thing that happens” is too absolute

In real analyst workbooks, a management summary, investor-relations output tab, or alternate presentation sheet may intentionally reproduce the entire consolidated statement vector. That is not an error; it is a legitimate ambiguity between multiple consolidated-like presentation blocks.

The response partly handles this with tie-breaking and abstention, but it should more explicitly allow multiple verified display bindings for a concept:

- one canonical gate-monitoring output row;
- one or more equivalent presentation mirrors;
- formula/dependency relationships proving equivalence.

That would avoid unnecessarily leaving a valid model unbound when it has duplicate consolidated presentation sheets.

Overall, however, C best satisfies the request. It is concrete, generic, safety-oriented, and directly explains how CLP

### Review by google/gemini-3.1-pro-preview

**Evaluation of Response A**
Response A provides a very thoughtful and detailed approach to the design question. For sub-question 1, it correctly identifies that "nominate-then-verify" is the right pattern and provides an excellent breakdown of the components required for a binding certificate (period, multi-anchor, scope, structural role). It also outlines realistic failure modes. For sub-question 2, it gives strong heuristics for determining consolidated scope versus segment scope. 
However, Response A has a major flaw: it is incomplete. The text cuts off in the middle of answering sub-question 3 (face over-tagging) and completely fails to address sub-question 4 (the lifecycle and `_SPEC` tab). Because of this severe truncation, it cannot be ranked highly despite the high quality of its initial sections.

**Evaluation of Response B**
Response B is a highly practical, complete, and well-structured answer. It addresses all four sub-questions clearly and concisely. For sub-question 1, it proposes a solid generic skeleton extraction and identifies key failure modes like coincidental ties and restatements, offering a multi-year vector match as a mitigation. For sub-question 2, it introduces "Topological Dominance" (formula rooting), which is a very strong generic way to prove a row is the consolidated total. For sub-question 3, it cleverly repurposes the existing Arithmetic Closure Engine to filter pages by "Math Density" and "Root Presence," which is an elegant, language-agnostic solution to face over-tagging. Finally, for sub-question 4, it gives a clear lifecycle for the `_SPEC` tab. Response B is an excellent, workable design.

**Evaluation of Response C**
Response C is outstanding and represents the best grasp of the specific domain, constraints, and existing architecture mentioned in the prompt. 
For sub-question 1, it outlines a highly robust 3-phase pipeline and includes a precise failure-mode matrix. It highlights that labels are just nomination features while identity is numeric. 
For sub-question 2, it introduces the concept of a "block constellation." This is an incredibly powerful, purely generic mechanism: instead of trying to prove one row is consolidated, it scores the entire block of rows against a vector of printed figures (Revenue, OP, PBT, NP). This completely solves the "Aus OP trap" without custom code. 
For sub-question 3, it heavily leans into the existing "closure/articulation machinery" mentioned in the prompt, providing a concrete scoring matrix (density, local sum-closure, global articulation) that perfectly ignores English captions. 
For sub-question 4, it provides the most nuanced and correct approach to `_SPEC`: cache the structure (sheet, row, scale) but re-verify the truth (prior-identity) on every run. Furthermore, the tone and terminology perfectly match the prompt's highly specific context (fablemode identity, Police laws, closure grammar).

FINAL RANKING:
1. Response C
2. Response B
3. Response A

### Review by x-ai/grok-4.6

## Response A

**What it does well.** This is the most architecturally ambitious answer. It correctly refuses a naïve “one LLM pick, one prior number” loop and upgrades nominate-then-verify into a *binding certificate*: period identity (scale/sign/restatement/basis), multi-anchor identity, scope, structural role, and uniqueness/ambiguity margin. The formal conjunction (`SemanticFit ∧ PeriodIdentity ∧ ScopeIdentity ∧ StructuralRole ∧ Uniqueness`) matches the owner’s invariant that a wrong bind is worse than a miss. Failure modes are real (coincidental numeric twins, missed recall, definition mismatch, stale workbook priors, formula-output vs writable input). The `display_row` / `write_policy` / `upstream_driver_region` split is a genuine operational insight the others barely touch. On the Aus trap it is right that prior-identity is necessary not sufficient, and the “whole-workbook explanation / constrained assignment” idea is stronger than per-concept greedy binding.

**What it does poorly.** It is unfinished. Face tagging starts the right idea (topology over captions) and then cuts off mid-list; `_SPEC` / re-verify-vs-trust is never answered. That is fatal against a four-part brief. The proposed machinery is also heavy: a full anatomy graph plus multi-class certificates is more than is needed to bind CLP tonight, and it under-specifies the cheap backstop that actually fixes CLP’s mismapped revenue (rows whose prior *equals* the printed comparative). Scope inference still leans on a lot of LLM interpretation. No concrete “what happens on CLP’s Final / Aus / Driver tonight” walkthrough.

## Response B

**What it does well.** It is complete, readable, and maps onto all four sub-questions. Skeleton → LLM nomination (≤3 candidates) → referee is the right spine. Formula-rooting (`Final = SUM(Aus, India, …)`) is a clean, generic consolidator test when formulas exist. `_SPEC` as one-time self-onboarding with structural + math integrity and targeted re-discovery is the right lifecycle. The CLP walkthrough is easy to execute against.

**What it does poorly.** Several mitigations are too thin or actively wrong. Multi-year vector match does not save you when the workbook only has one locked prior, or when a dominant segment matches for several years. Shifting to *t−2*/*t−3* when *t−1* fails will *accept* restated or stale rows instead of leaving them unbound. Face detection is circular: it uses “this page contains already-verified Consolidated Revenue” to find the face, but printed anchors usually *come from* the face. “Ask the LLM which sheet is consolidated” is exactly the hope that already failed (labels like `Final` are evidence, not a referee). Little abstention: if formulas are hardcoded and two rows tie, B still wants a winner. Incomplete-announcement / CF-unbound and “commit neither on ambiguity” are underplayed.

## Response C

**What it does well.** This is the design most likely to bind CLP’s 10+ keys tonight with zero CLP code. It keeps nominate-then-verify but makes the referee do the real work: prior-identity *and* a **block constellation** (vector of printed face figures inside one statement-shaped block). That is the generic Aus-OP killer: `Aus` matches at most OP; `Final` matches rev+OP+PBT+NP. The reverse-identity second pass (cut to rows whose prior equals the print, LLM only ranks) is the precise fix for the mismapped revenue row and for LLM recall failure. Failure-mode table is complete (coincidence, restatement, scale/sign, skipped row, bridge totals, EPS, missing CF face). Face test is language-agnostic articulation (year-pair grid, local sum-closure, `A=L+E` / P&L walk / CF bridge), with captions as bonus only — no circularity. `_SPEC` is correctly a cache of once-certified nominations, not a constitution: structure trusted, identity + constellation + face re-verified every run; restatement keeps the bind and flags rather than retargeting. Explicit unbound for announcement-without-CF. Prompt contract stays small and taught, not wrapped. Ends with a CLP-without-CLP-code trace that hits every diagnosed choke point.

**What it does poorly.** Constellation ≥2 can starve a genuinely sparse workbook that only has one printable key. Block clustering is slightly underspecified for multi-sheet anatomies where P&L and BS live on different sheets with no formula bridge (CLP’s `Final` is fine; the next company might not be). Inventory still contains a fair amount of deterministic “anatomy code” (formula roles, sheet-role priors); that is legal as referee, but it is more surface area than the owner’s “teach the LLM” preference. Denser than B; a reader could miss that uniqueness-tie ⇒ commit neither is the load-bearing safety rule.

---

FINAL RANKING:
1. Response C
2. Response A
3. Response B


## Ranking tally (Borda)

- Response A (openai/gpt-5.6-terra): 8 pts
- Response B (google/gemini-3.1-pro-preview): 0 pts
- Response C (x-ai/grok-4.6): 0 pts

## Stage 3 — chairman synthesis (google/gemini-3.1-pro-preview)

To solve the generic model-anatomy discovery problem, the council unanimously agrees that the core architecture must be **Semantic Nomination + Mathematical Interrogation**. We must rely on the LLM to interpret the semantic structure of the workbook and propose candidates, while a strict, deterministic referee certifies or rejects those proposals based on numerical identity and topological structure. 

A key is not a label—it is a **verified mathematical identity**. A wrong binding aims the printed-key gate at the wrong target and launders a green run; therefore, ambiguity must always result in an `unbound` state.

Here is the synthesized, completely generic blueprint that addresses all four sub-questions and will bind CLP correctly tonight without a line of per-company code.

---

### 1. The Core Mechanism: Nominate-then-Verify (The Binding Certificate)

**Yes, nominate-then-verify is the exact right spine.** However, we must upgrade the verification step from a simple "one LLM pick, one prior number check" to a rigorous **Binding Certificate**. 

**The Pipeline:**
1. **Deterministic Inventory:** Code cheaply extracts a "skeleton" of every sheet: row captions, indentations, formula presence/roles (e.g., `=SUM()`), year-header maps, and detected units.
2. **LLM Nomination (The Teaching):** The LLM is given the skeleton and the filing’s printed comparatives. It is instructed to nominate up to 3 candidate rows per concept, ranked. Crucial instruction: *Prefer `unbound` over a guess. Consolidated blocks beat identically named segment twins.*
3. **The Referee:** Code tests the LLM's nominations. To commit, a binding must pass:
   * **Period Identity:** `|model_prior − filing_comparative| ≤ tick` (after scale/sign adjustment).
   * **Scope Identity / Constellation:** (See Sub-question 2).
   * **Uniqueness:** If two rows tie all tests, *commit neither*.

**Failure Modes & Mitigations:**
* **LLM misses the correct row (bland caption):** Implement a *Reverse-Identity Backstop*. If a key remains unbound, deterministically filter the workbook for rows whose $t-1$ value mathematically equals the printed comparative. Feed this cut back to the LLM to rank. (This specifically fixes CLP's mismapped revenue row tonight).
* **Restatement Trap:** The filing restated $t-1$, but the model is unrestated. Identity fails. *Mitigation:* The referee flags a restatement warning and leaves it `unbound`. Do not force-bind or skip to $t-2$; manual/agentic repair is required before gating.
* **Formula vs. Writable Input:** A consolidated output may be a formula, not a writable hardcode. The certificate must record a `display_row` (for the gate to monitor) and a `write_policy` (so the updater knows not to overwrite formulas).

### 2. The Segment Trap: The "Block Constellation"

**Prior-identity on a single concept is necessary but NOT sufficient.** A segment's operating profit (OP) can coincidentally equal the group's OP (e.g., CLP's `Aus!23`). 

To defeat this without sheet-name heuristics, we use a **Block Constellation**:
1. **Cluster Rows:** The referee deterministically clusters rows into blocks based on outline grouping and contiguous statement-shaped regions.
2. **Vector Scoring:** Score each block against the *vector* of known consolidated filing figures. 
   * A P&L block is scored against `{Revenue, OP, PBT, NP}`.
   * A Balance Sheet block is scored against `{Total Assets, Total Liab, Equity, Cash}`.
3. **The Twin-Killer:** `Aus!23` lives in a block that matches at most OP (Score: 1). `Final!45` lives in a block whose prior actuals uniquely match Revenue, OP, PBT, and NP (Score: 4). 
4. **Formula Rooting (Tie-breaker):** If two blocks tie (e.g., a summary sheet reprints the face), code inspects the formulas. The block that mathematically consumes the other (`=SUM(Aus, India)`) is the true consolidated face.

Coincidence of an entire vector of 3–4 independently printed figures on a non-consolidated sheet is statistically impossible. The block with the highest constellation score becomes the exclusive home for primary keys.

### 3. Face Over-Tagging: Arithmetic Articulation over Captions

Tagging pages based on English captions ("Consolidated Statement of...") yields 78 false positives because captions appear in TOCs, notes, and cross-references. **Captions are a weak prior; Arithmetic Articulation is the test.**

Turn your existing arithmetic-closure engine into a page-level scorer. A true face page in any language will pass:
* **Numeric Grid Density:** High density of aligned reporting-period columns (notes are inline/sparse).
* **Local Sum-Closure:** $A + B = C$ holds true sequentially down the page (e.g., revenue minus costs = gross profit).
* **Global Articulation:** The page (or page + continuation) naturally closes primary accounting identities (e.g., $\Delta Cash = CFO + CFI + CFF$ or $Assets = Liab + Equity$).
* **Narrative Token Ratio:** Low text-to-number ratio compared to notes.

Commit a document page as a statement face *only* if its `articulation_score` clears a threshold. Caption hits without math density are discarded entirely. This deterministically collapses CLP's 78 pages to the ~6 actual face statements, completely language-agnostic.

### 4. The Lifecycle: Self-Onboarding and the `_SPEC` Tab

Discovery must be a **one-time self-onboarding artifact** written to a `_SPEC` tab. Running the LLM discovery pipeline every quarter is structurally fragile and violates deterministic print-time execution.

* **First Run:** Empty `_SPEC` $\rightarrow$ full LLM discovery + Referee $\rightarrow$ Write committed bindings to `_SPEC`.
* **What is Trusted (Cached Structure):** 
  * `concept -> (sheet, row_id, scale, sign, block_id, write_policy)`
* **What is Re-verified Every Run (Truth):**
  * Does the `row_id` still exist structurally?
  * **Crucially: Does the model's new prior column still mathematically tie to the *new* filing's comparative?**
  * Does the constellation still uniquely point to this block?

**Invalidation:** If the prior identity fails and there is no declared restatement on the filing face, the structural bind is broken (e.g., the analyst inserted 5 rows and shifted the model). The engine securely drops the key and triggers a targeted LLM re-discovery for that specific concept to heal the `_SPEC` tab.

### Summary: What happens on CLP tonight (Without CLP Code)
1. Code extracts the CLP workbook skeleton and parses the English PDF.
2. The Articulation Scorer shreds the 78 caption hits, leaving only the dense, arithmetically closing HK-IFRS face pages.
3. Printed anchors (Revenue, OP, NP, Assets, etc., scale 1) are extracted from those true faces.
4. LLM nominates rows. The reverse-identity backstop guarantees the true revenue row is evaluated, dropping the historically mismapped row because its $t-1$ doesn't tie.
5. `Aus` and `Final` both yield OP candidates that tie the printed figure.
6. The Referee evaluates the Block Constellations. The `Final` P&L block matches `{Rev, OP, PBT, NP}`. `Aus` matches only `{OP}`. `Aus` is deterministically rejected.
7. Keys commit on `Final`. Values are written to `_SPEC`. The printed-key gate is armed, and Police Law 4 has teeth.
