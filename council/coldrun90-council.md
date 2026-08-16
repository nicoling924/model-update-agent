# LLM Council transcript

## Question

# Council question: vet this plan — ONE cold run tonight must score ≥90% on DFE

## Hard constraints
- Engine: pure gpt-5.6-luna in the run (no stronger model anywhere in the run path).
- ONE more GitHub Actions dispatch tonight (~50 min runtime); scoring is vs a
  reference model (itself a prior strong-agent run) with filing adjudication.
- Broadly-available Python libs only. Generic across companies (no DFE-specific logic).
- Deadline: tonight. Owner presents to management Monday.

## Where we stand (measured today)
- Clean-room strong-model free-form ceiling: 96.0%.
- Latest guarded run (114): 75.5% raw = 206/273; filing-adjudicated ≈81%
  (of 67 disagreements: 16 genuinely wrong, 8 the RUN is right and the
  reference wrong, 7 both printed, 36 computed-subtotal fallout).
- Run 114 is CLEAN: zero absurd writes (this morning's audit added a
  world-band write guard at the single Writer chokepoint, row-relative
  tolerances everywhere, checksum-read locks, statement-wins in the closing
  loop). EPS exact, signs exact, valuation tabs 100%.
- Post-mortem of 114's residuals (done by hand in ~20 min):
  (a) ENTIRE 2025 balance gap (+2,238.6) = 2 cells, both inflated by the
      ALLOCATION pass, which scaled prior-year structure (x4.82) to force the
      non-current-assets total WHILE THE TRUE VALUES PRINT ON THE BS FACE
      (使用权资产 462.8; 长期应收款 79.87). Statement-wins violated at the
      allocation level; allocation writes formula strings so the numeric
      band guard never saw them.
  (b) Constant +362 forecast-year gap = one propagating base.
  (c) ~16 wrong reads, mostly Driver (MD&A/segment/ops tables).
- Historic pattern: unattended runs land 73–81; an offline "post-update
  evaluation" pass (a strong model chasing every residual to a named cell,
  fixing with page cites) lifted yesterday's run to 85.7. That stage does
  not yet exist IN-RUN.

## The proposal to vet ("finish like Fable" — add the missing final stage)
1. ALLOCATION OBEYS STATEMENT-WINS (deterministic): before scaling any
   component to a proven total, prior-anchor-search the disclosure for that
   component's own printed line; components found on the statement face take
   their printed value (cited, unscaled); only truly-undisclosed components
   share the residual scaling.
2. POST-WRITE STATEMENT RECONCILIATION (deterministic gate): after all
   writes, re-run the prior-anchored aligner (existing machinery, measured
   24/24 on this filing) between every disclosed statement in both docs and
   the WRITTEN column. Every DIFF = a named suspect {cell, written, printed,
   page} handed to the repair loop.
3. NEW ORCHESTRATOR TOOL decompose {check}: for a failing check row, emit the
   component-vs-statement diff list with cites (mechanizes the by-hand
   two-cell decomposition of (a)).
4. TARGETED RE-READ: suspects with no deterministic printed value go back
   through the whole-page fable-mode reader WITH their statement-page images
   (look at the page again, not at labels).
5. EVIDENCE-CITED LOCK OVERRIDE: locks keep binding mechanical writers, but a
   repair from stages 2/3 carrying a printed-value cite may override a locked
   cell (it IS the statement).
6. Everything else frozen (sign rule, band guard, tolerances, learner refocus).

VALIDATION BEFORE THE ONE DISPATCH: replay the new stage OFFLINE against run
114's actual artifact (workbook + staging + logs, all on disk). Dispatch is
allowed only if the offline replay autonomously (i) names and fixes the two
allocation cells from the printed statement values, (ii) closes the 2025
balance to 0, (iii) resolves the +362 forecast base, (iv) corrects ≥10 of the
16 filing-cited wrong reads. Expected result if it transfers: 206 + ~16 reads
+ ~36 fallout ≈ 250–258/273 = 92–94%; floor scenario ≈87–88.

## Questions
Q1: Holes and failure modes in this plan, given exactly ONE dispatch tonight?
    What will we wish we had validated offline but didn't?
Q2: Is there a materially better plan under the constraints? (Considered and
    rejected: run-twice-and-vote — errors are positively correlated across
    draws and it doubles quota; a one-mega-context rewrite — too risky
    tonight.) Argue if the rejection is wrong.
Q3: The +362 forecast base and the 16 Driver reads are the least-derisked
    parts. Concretely, how should stage 3/4 handle forecast-year residuals
    and MD&A-table rows so they close tonight, not "eventually"?
Be concrete. Flag what other members will get wrong.


## Stage 1 — answers

### Response A — openai/gpt-5.6-terra

## Bottom line

The proposal is directionally right: the missing capability is not another broad extraction pass, but a **bounded, evidence-backed post-write repair stage** that can trace a residual to named cells and correct them from the filing.

However, with one dispatch, I would not ship it as “a new autonomous repair loop” unless it is made very conservative. The main risk is not failing to find the obvious two allocation cells; it is allowing reconciliation to create new errors through bad period/units/authority matching, formula recalculation issues, or over-eager lock overrides.

Also, the arithmetic is encouraging but not a guarantee:

- `206 + 16 + 36 = 258`, or 94.5% raw.
- But those gains are not necessarily independent:
  - Some of the 36 fallout cells may overlap the 16 bad reads.
  - A repair can move a disagreement rather than remove it.
  - Reference-model errors and filing adjudication mean raw and adjudicated improvements will not map one-for-one.
- Your stated floor of 87–88% means this plan is not yet a credible “must score ≥90%” guarantee. It is a reasonable high-upside attempt only if offline replay clears much stronger safety gates than the four listed.

I would approve the direction, but only with a **repair-manifest / fail-closed implementation** and a strict offline promotion gate.

---

# Q1. Holes and failure modes

## 1. “24/24 statement alignment” is not enough proof for cell-level repair

The aligner being 24/24 on statements is excellent, but a statement-level match can still be wrong at the line/column level. Common failure modes:

- Consolidated versus parent-company statement.
- Current versus prior year, restated versus originally reported comparative.
- Quarterly, annual, LTM, and forecast columns sharing labels.
- RMB/CNY units versus thousands/millions.
- Subtotal versus total having nearly identical Chinese labels.
- Continuing operations versus total company.
- A face-statement amount versus note disclosure amount for the same named line.
- Display-rounded face values versus more precise note values.

A repair must be keyed by more than `{label, page}`. It needs a canonical source identity such as:

```text
{document_id, statement_or_table_title, page, row_label, parent_section,
 period_end, column_header, units, sign_convention, source_bbox/evidence_id}
```

The repair engine should refuse to apply a value if any required identity field is ambiguous.

**What people will get wrong:** they will hear “the aligner is 24/24” and assume this validates all the semantic joins needed to overwrite cells. It does not.

---

## 2. The allocation fix can still recreate the formula-string guard bypass

You found the key defect: allocation writes formulas, so a numeric band guard did not inspect the effective value.

Fix this at the Writer chokepoint, not just in allocation:

1. Every write must have a typed origin:
   - `printed_statement_value`
   - `mechanical_formula`
   - `allocation_residual`
   - `forecast_formula`
   - `model_proposal`
2. Formula writes must be validated on:
   - formula text,
   - calculated value,
   - referenced cells/ranges,
   - resulting value after workbook recalculation.
3. The repair stage should preferably write **literal cited values**, not formula strings, when it is correcting a printed historical line.
4. For allocation specifically:
   - establish printed components first;
   - compute residual only from components that truly lack a printed value;
   - prohibit allocation from changing a cell whose source priority is `printed_statement_value`.

A simple source-priority rule is safer than a vague “statement wins” policy:

```text
printed filing value > deterministic statement identity > cited note value
> derived formula > allocation > model inference
```

No lower-priority producer may overwrite a higher-priority cell without an explicit demotion event, which should essentially never happen tonight.

---

## 3. “Every DIFF becomes a suspect” can create a repair storm

A mismatch is not necessarily a bad workbook value. It may be:

- rounding,
- unit conversion,
- a mapped but non-equivalent line,
- source authority conflict between the two documents,
- a statement layout mismatch,
- a legitimate model forecast instead of a historical statement column,
- a formula not yet recalculated,
- a subtotal mismatch caused by a child row elsewhere.

If all diffs are sent to the model, you will spend the 50-minute budget on noise and increase the chance of harmful edits.

Use a triage state machine:

```text
A. Exact printed historical value available and identity unambiguous:
   deterministic repair candidate.

B. Check residual decomposes to one or a few named workbook cells:
   deterministic candidate list, possibly model reread.

C. Forecast-only / no printed value:
   trace lineage; repair only with a cited driver or deterministic formula defect.

D. Ambiguous units, periods, scope, or authority:
   abstain; log unresolved.
```

The repair loop should not be allowed to “make the check pass.” It may only repair an identified source cell with valid evidence or a verified mechanical derivation.

---

## 4. The lock override is necessary, but dangerous without a narrow capability

“Printed-value cite may override a locked cell” is correct in principle. But the override must not be a broadly available escape hatch.

Require all of the following before an override:

1. Existing cell semantic identity matches the evidence identity.
2. Evidence includes period, units, row context, and page.
3. Source has higher priority than the locked cell’s current source.
4. The proposed value passes scale/sign checks after unit normalization.
5. The override is written to an append-only repair ledger.
6. The resulting workbook is recalculated and all affected checks are rerun.
7. The repair changes only the nominated cell(s), not arbitrary adjacent formula ranges.

The model should never receive direct write authority. It should emit a structured proposal; deterministic code validates it; the Writer applies it.

Example repair object:

```json
{
  "target_cell": "BS!F42",
  "target_semantics": {
    "line_item": "right-of-use assets",
    "period_end": "2025-12-31",
    "units": "CNY million",
    "scope": "consolidated"
  },
  "proposed_value": 462.8,
  "source": {
    "document": "annual_report.pdf",
    "page": 112,
    "table": "Consolidated Balance Sheet",
    "row_text": "使用权资产",
    "column_text": "2025年12月31日",
    "units_text": "人民币百万元"
  },
  "reason": "Printed face-statement value has higher source priority than allocation formula."
}
```

Anything less structured is too risky tonight.

---

## 5. Workbook calculation and dependency behavior may invalidate the reconciliation result

A large class of “post-write reconciled successfully” failures is actually calculation-engine behavior:

- Formula cache not updated.
- Excel-only functions differing under LibreOffice/Python tooling.
- Circular references / iterative calculations.
- Named ranges, external links, or tables not recalculated.
- A formula is replaced by a literal and silently breaks downstream logic.
- Repairing one historical base affects forecast columns through formulas.

Validate reconciliation against the **calculated output produced by the same engine/environment used in the dispatch**, not only by parsing workbook XML or cached values.

For the +362 issue, this is especially important: it may be a genuine dependency propagation problem, so a base-cell repair must be followed by a complete recalculation and downstream-delta review.

---

## 6. “Both docs” needs an authority policy before comparison

If the two documents disagree, reconciliation needs to know which source wins. Otherwise the repair loop can ping-pong values.

Define a generic authority rule now, for example:

1. Audited annual filing / primary financial statements.
2. Official amended filing, if applicable.
3. Official earnings release or supplemental disclosure.
4. Presentation / MD&A narrative table.
5. Derived values.

Then, within the same authority tier, prefer the source with matching period, scope, units, and statement/table identity.

Do not let the model decide source authority ad hoc.

---

## 7. Offline replay on one artifact can overfit

Your current acceptance criterion is necessary but not sufficient. It proves that the new stage can fix known failures in a known artifact. It does not prove it will behave safely in the fresh run.

The key hidden risks are:

- Different page-image ordering or availability in the dispatch.
- Different extraction/OCR results.
- Different prompt ordering and model attention.
- Timeout/retry behavior.
- A repair pass that depends accidentally on residual logs available only in the old artifact.
- Code paths that work with cached formula results but fail after a fresh workbook build.
- A repair that succeeds only because the hand post-mortem effectively leaked the answer into the implementation.

The clean test is: run the exact production container and code path from a fresh checkout against a copy of the run-114 inputs, without hand-created side files or manually edited staging data.

---

## What I would require in offline validation

Your four gates are good. Add these before promotion:

### A. Baseline reproducibility

First replay the old pipeline without the new stage and verify it reproduces run 114 closely enough:

- same written-cell values or an explainable deterministic equivalent;
- same check results;
- same formula-calculation behavior;
- no hidden dependence on mutable artifacts.

If you cannot reproduce the baseline, do not trust the new replay.

### B. Full-diff safety check

After applying the new stage:

- Every changed cell must have a repair-manifest entry.
- Every manifest entry must contain evidence identity and source priority.
- No changed cells outside the manifest.
- No formula should be introduced by a repair unless explicitly approved and evaluated.
- No previously correct target cell may regress, except for a deliberate and documented conflict resolution.

Do not only validate that the three known residuals close.

### C. Idempotence

Run the new final stage twice on its own output.

Expected result: second pass makes zero changes.

If the second pass keeps changing cells, the system is unstable and should not dispatch.

### D. Negative controls / abstention

Include known ambiguous cases from the artifact:

- duplicate labels,
- a subtotal and component with similar text,
- a unit mismatch,
- a different-period table.

The desired behavior is “abstain and log ambiguity,” not “guess a value.”

### E. Full scorer proxy, not just accounting checks

Run the closest available local scoring/evaluation pass over all 273 targets. A balance-sheet check reaching zero is a strong signal, but it is not equivalent to DFE scoring.

Track:

- pre/post exact agreement count,
- changed-target count,
- new disagreements,
- unresolved suspects,
- repair confidence categories,
- runtime and model-call count.

### F. Runtime and failure injection

Validate the actual 50-minute operating envelope:

- page-reader latency,
- model retries,
- partial failure behavior,
- missing page image behavior,
- whether a failed reread can leave a partial write.

The final repair stage should fail closed: no evidence, no write.

---

# Q2. Is there a materially better plan?

## I would not do run-twice-and-vote

The rejection is correct for full end-to-end runs.

The residual failures are not random sampling noise. They are structural:

- same bad source alignment,
- same allocation behavior,
- same driver-table interpretation,
- same forecast propagation,
- same workbook mapping.

Two correlated runs will often produce two confident versions of the same mistake. It also

### Response B — google/gemini-3.1-pro-preview

This is a strong, highly mechanical plan that rightly shifts the burden from LLM "vibes" to deterministic scaffolding. You are heavily leaning on the right architectural principle: **constrain the model via accounting identities rather than prompting.**

However, given you have exactly **one** dispatch and ~50 minutes of compute, there are critical blind spots in the plan that will blow up the run if not addressed. 

Here is the vetting, the traps your team will miss, and the concrete execution steps to hit $\ge 90\%$.

---

### Q1: Holes and Failure Modes (The "One Dispatch" Traps)

**Hole 1: The Allocation Formula Bypass (Fatal)**
You correctly diagnosed that the allocation pass bypassed your numeric band

### Response C — x-ai/grok-4.6

**Verdict: do not ship this plan as written.** Stages 1 + a *narrow* post-write face reconciliation are the only parts that are actually one-dispatch-safe. Stages 3–5 as specified are how you turn a clean 81% into a timeout, a lock-blowout, or a 70s score. The 92–94% transfer story is not earned. Floor is not 87–88 either — a botched override/repair loop has a left tail well below 114.

The 90% bar is reachable tonight only if you treat 114’s post-mortem as *already-known named defects* and harden generic mechanisms that replay those defects offline — not if you hope luna rediscovers them via a new orchestrator tool.

---

## Q1 — Holes and failure modes (one dispatch)

### The plan’s load-bearing lie
You are scoring a **cold** luna run. Offline replay against 114’s *already-written* workbook is a different task:

- Allocation that never emits the bad formulas ≠ “repair the two cells after the fact.”
- Suspect lists, lock overrides, and fable re-reads will fire on **new** luna mistakes that 114 never made.
- Path dependence: if stage 1 changes early writes, the +362 base, the 16 Driver misses, and the 36 “fallout” cells can all move.

A green offline replay on 114 is necessary and **nowhere near sufficient**. If you only validate that, you will wish you had validated a *second* prior artifact (a 73–81 run, not just 114) and a **mutated** 114 (corrupt two other face lines, inject a bad formula write, drop one Driver table) to see whether the new stage overfits the post-mortem you already did by hand.

### Hole A — Lock override is how absurd writes return
You closed absurd writes this morning by putting a **single** Writer chokepoint + world-band + checksum locks. Stage 5 punches a hole in that chokepoint.

A repair “carrying a printed-value cite” is not the statement. It is a luna string that *claims* to be the statement. Failure modes other people will underweight:

- Right number, wrong year / restated vs as-reported / parent vs consolidated / company vs segment.
- Right number, wrong scale (元 / 千 / 万 / million; per-share vs line; % vs bps).
- Number appears in a note, MD&A, or auditor’s report with a different meaning.
- Cite of a subtotal that is *near* the component (使用权资产 vs 租赁相关合计).
- Override of a cell that was locked because a **checksum** said the column was already consistent — you then re-break the column and the 36 fallout becomes 50 new fallout cells.

If override is not gated by a **deterministic** verifier (number+period+unit+entity actually found on the cited page/region; unique match; same statement as the cell’s role), do not ship it. “Cited” is not a type.

### Hole B — Formula strings still bypass the band
You already know allocation wrote formula strings so the numeric guard never saw them. Stage 1 (statement-wins before scale) fixes *this* allocation bug, not the class.

Tonight you will wish you had: **evaluate-or-refuse at the chokepoint**. Writer may emit a formula only after a numeric preview is band-checked. Otherwise the next “innocent” plug/allocation/YoY formula repeats 114’s failure on a different pair of cells, and stage 2 spends the whole budget chasing ghosts.

### Hole C — Stage 2 is not 24/24 in the only sense that matters
“Prior-anchored aligner 24/24 **on this filing**” violates the spirit of “generic across companies” and is not a runtime/precision result.

What blows up on a cold run:

- Label drift, bilingual headers, note-vs-face duplicates, continuing ops vs total, two cash-flow presentations.
- Forecast columns have **no printed face**. Aligning “every disclosed statement” to “the WRITTEN column” will either skip forecast years (then +362 never becomes a suspect) or invent diffs against the last historical year (then you “repair” forecasts toward history).
- DIFF volume. If you hand every DIFF to a repair loop you can thrash: fix A, break B, override a lock, blow a checksum, re-enter. 50 minutes is one attempt. Unbounded repair is how you submit a half-written book.

You need a **budgeted, monotonic** gate: max N repairs, max M page re-reads, only unique face matches, apply only if column checksum improves or is unchanged, else revert. Timeout behavior must leave 114-quality output, not a torn workbook.

### Hole D — `decompose {check}` is a new non-deterministic brain
The two-cell decomposition of (a) was easy *because a human already knew the 2025 gap equaled two inflated allocation components that print on the face*. A luna tool that “emits the component-vs-statement diff list” will:

- split the wrong total (assets vs non-current assets vs a note rollforward);
- treat a printed face line as “undisclosed” (search miss) and keep scaling it;
- treat a nearby line as the component (search hit) and write the wrong printed number with a sincere cite.

This must be **deterministic search over an already-built line index** (normalized labels, period, unit, statement id), not a free-form orchestrator essay. If you cannot replay 114’s two cells with *zero* model calls, you do not have stage 1/3.

### Hole E — The 36 fallout and the 16+2+1 arithmetic
`206 + ~16 + ~36 ≈ 250–258` assumes (i) the 36 are pure dependents, (ii) all 16 Driver reads are recoverable by luna fable re-read, (iii) +362 is one named base inside that set, (iv) you don’t *lose* any of the 206 or the 8 “run right / ref wrong” cells.

You will wish you had, offline, a **dependency cut**:

- zero those two allocation cells to face values in 114’s book → how many of the 36 flip?
- then fix the named +362 base → how many more?
- remaining disagreements, classified, with page cites.

If the cut does not produce ≥246/273 **before** inventing new tools, the 90% story is a vibe. Also remember the 96% ceiling is **strong-model free-form**, not luna, and the strong-model *offline chase* only got you to 85.7. Luna in-run will not beat a strong model with a human-shaped residual hunt unless the remaining errors are the deterministic class (a), not the Driver class (c).

### Hole F — Runtime and “clean abort”
New stages add aligner passes, tool calls, page images. 50 minutes was already a full run. You will wish you had a dry-time of stages 2–4 against 114’s artifact with the **same** luna, same image budget, and a hard kill that commits last-good book. If dispatch OOMs / tool-loops / vision-stalls, Monday’s number is “we had 81 and we gambled it.”

### Hole G — Scoring / don’t repair into the reference
8 cells the run is right and the reference is wrong; 7 both printed. Stage 2+5 will happily “fix” those toward the reference if the aligner is sloppy (wrong period, wrong statement copy). That can **drop** adjudicated score while looking like progress on raw-vs-ref. Offline replay must score with the **same filing adjudication rules**, and must mark those 15 cells do-not-touch unless a unique face cite contradicts *your* write.

### What you will wish you validated offline (checklist)
1. Stage 1 with **no** LLM: finds 使用权资产 462.8 and 长期应收款 79.87, refuses to scale them, residual goes only to truly undisclosed components, 2025 gap → 0.
2. Same stage 1 on **another** company’s 114-equivalent (or an older DFE run): no false “printed” matches.
3. Writer chokepoint sees **numeric preview** of every formula; band/lock still hold.
4. Dependency cut of the 36; named cell for +362; remaining genuine residuals listed.
5. Cite verifier: reject wrong-year / wrong-scale / non-unique / note-vs-face.
6. Lock override **disabled** except unique face match on the same statement+period+entity.
7. Repair loop: N/M caps, checksum monotonicity, revert, last-good snapshot.
8. Forecast columns: what suspects stage 2 even emits (today: probably none or nonsense).
9. Driver tables: unit/column map on the actual missed pages, not “look again.”
10. Wall-clock with luna + images; abort leaves a scorable book.
11. Adjudication-aware scoring so you don’t overwrite the 8 run-right cells.
12. A second artifact replay, not only 114.

If 1, 3, 4, 6, 7, 10 are not green **before** dispatch, do not dispatch.

---

## Q2 — Is there a better plan under the constraints?

Rejected options: run-twice-and-vote is correctly rejected (errors correlated; quota). Mega-rewrite is correctly rejected (you just got to a *clean* 114; a rewrite reopens absurd writes).

What is better tonight is **narrower**, not larger:

### Ship only what is mechanizable from the 20-minute post-mortem

**P0 (must ship or don’t bother)**  
1. **Allocation statement-wins, deterministic, pre-formula.** Index every printed face line (period, entity, unit, statement). Components with a unique hit are cited and frozen. Only the residual pool scales. No model in this path.  
2. **Numeric preview at the single Writer chokepoint** for formulas. Same band/lock/checksum as literals. This is the actual bug class behind (a).  
3. **Named +362 hunt offline, genericized as a rule.** Do not go to dispatch without the cell id, the wrong base, and the *class* of bug (copied 2024 instead of 2025? missed one-time? wrong sign on a driver? stub year?). Encode that class, not that cell.

**P1 (only if P0 replay already closes 2025 and most fallout)**  
4. **Post-write face recon, historical columns only.** Suspect = written ≠ unique printed face, same statement/period/entity/unit. Auto-apply those. No lock override except this set. Cap count. Checksum must not worsen.  
5. **Driver re-extract is a table parser pass, not fable-again.** For every Driver residual you already cited by hand: force a grid read (headers, units, years, scale, whether the cell is a level / Δ / %). Same pages you already know. Budget a fixed list of pages from 114’s 16, plus a generic “MD&A/segment tables with year headers” detector so it’s not DFE-specific.

**P2 (cut unless P0+P1 offline already ≥90 on replay *and* a second artifact)**  
- `decompose` as an LLM tool.  
- Open fable re-read of arbitrary suspects.  
- General lock override.  
- “Every DIFF to the repair loop.”

That is “finish like Fable” only in the sense Fable *looked at the face*. It is not “add an in-run strong-agent residual chase.” You do not have a strong agent in the run path, and the one time you *did* that offline you got 85.7 — **below** the Monday bar.

If P0 replay on 114 does not zero the 2025 gap and collapse most of the 36, 90% is not a tonight objective; the honest move is present 81% clean + a measured residual list, not a lottery dispatch.

---

## Q3 — +362 and the 16 Driver reads, tonight not “eventually”

These are least-derisked **because your new machinery is statement-face-shaped and they are not.**

### Forecast +362
Stage 2/3 as written will not see a printed 2026/2027 face line. `decompose {check}` on a forecast residual will invent components.

Do this **before** dispatch, by hand, on 114’s book (you said one propagating base — name it):

1. Identify the exact cell and the first year the +362 appears.  
2. Classify the *mechanism* (only these are closable tonight):
   - **Historical seed wrong** → P0/P1 face recon fixes it; forecast follows.  
   - **One-time item not stripped / not added back** → deterministic policy: items tagged non-recurring in the historical close do not enter the forecast base; if 114 violated that, encode the gate, don’t “re-read.”  
   - **Wrong driver linkage** (growth applied to the wrong base, or a stock treated as a flow) → fix the linker, add a checksum: forecast(t0) must equal last historical close for stocks / equal last historical *run-rate* for flows, within stated policy.  
   - **Unit/scale on a driver** (362 looks like a thousands/millions or 万/百万 miss) → that’s a Driver read, treat as below.
3. Offline proof: patch only that mechanism on 114’s artifact → +362 and its dependents go to 0 **with no repair LLM**.  
4. In-run: a **forecast identity gate** (deterministic): for each forecast column, `base = f(last closed historical, policy)`. Any writer output that violates the identity becomes a named suspect with the identity formula, not a page cite. Stage 4 does **not** re-read MD&A to invent a forecast number.

If you cannot complete (1)–(3) in the next hour, stage 3/4 will not close +362 tonight. Do not pretend otherwise in the dispatch.

### 16 Driver / MD&A / segment / ops rows
“Look at the page again, not at labels” is the right *human* instinct and the wrong luna loop. Fable-mode already had the page and missed. A second pass with the same model and the same prompt shape will re-miss or flip a different column.

Concretely, stage 3/4 should not receive “failing check row.” They should receive a **table job**:

```
{pages, table_id, header_row_years, unit_hint, scale_hint,
 entity, whether_values_are_level|yoy|percent,
 target_line_aliases[], output_cells[]}
```

Procedure that can finish in one run:

1. **Offline:** for each of the 16, write that job from 114’s logs (you already have page cites). This is allowed — it is not DFE-specific logic; it is turning known miss *types* into a generic table job schema. Also build alias lists that are language-agnostic (normalize 使用权资产 / ROU / right-of-use).  
2. **In-run detector (generic):** any page with a numeric grid + year headers + a unit token in the caption is a table job. Don’t wait for a failing check.  
3. **Read the grid, not the narrative.** Column bind by year first, then row bind by alias, then apply scale from caption/header **only**. Reject if two rows match or two columns match.  
4. **Cross-check:** if the same line exists on a statement face, statement wins (stage 1). Driver tables lose. That prevents MD&A “approx” numbers from overriding the BS.  
5. **Budget:** at most the K pages already implicated by Driver checks + newly detected year-grid pages, hard cap. No recursive “read adjacent page.”  
6. **Do not lock-override from a Driver table.** Only face-of-statement cites override locks. This is the one rule that keeps (c) from undoing this morning’s guard.

If fewer than ~10 of the 16 can be expressed as unique (page, year-column, unit, alias) jobs **offline**, you will not correct ≥10 tonight. The dispatch gate (iv) is then theater.

### What “close tonight” actually looks like
- 2025 gap: closed by P0 with zero luna.  
- +362: closed by a named identity/policy gate proven on 114’s book.  
- Driver: closed only for table jobs that are unique-bind; the rest stay wrong.  
- Expected honest band if P0+identity work and ~8–12 Driver jobs bind: **high 80s adjudicated**, raw maybe ~88–92 depending on true fallout fraction.  
- 92–94% requires the 36 to be almost all fallout **and** ≥10 Driver fixes **and** no new luna damage. Do not brief that as the plan; brief it as the upper bound *if* the dependency cut says so.

---

## What other members will get wrong

- **“Offline replay of the new stage on 114 is the dispatch gate.”** It is a gate against *not even fixing the known bug*. It is not a gate for a cold luna run.  
- **“Lock override with a cite is still statement-wins.”** Without a deterministic unique-match verifier it is unattended writes with extra ceremony.  
- **“The 36 fallout come for free.”** Not unless you measure the cut. Some “fallout” is independent plug/sign/scale.  
- **“Fable re-read will pick up Driver tables.”** Same model already failed those pages; you need grid/unit/year binding.  
- **“decompose generalizes the two-cell trick.”** The two-cell trick was human insight plus a printed face. The tool will over-decompose.  
- **“24/24 aligner means stage 2 is safe.”** That’s recall on this filing’s historical statements, not precision, not forecast, not runtime, not generic.  
- **“96% ceiling / 85.7 offline chase imply 90 is conservative.”** 96 was a stronger model unguarded; 85.7 was a stronger model *with a human-shaped


## Stage 2 — peer reviews

### Review by openai/gpt-5.6-terra

### Response A

**What it does well**

- Gives a strong architectural framing: the right improvement is a **bounded, evidence-backed post-write repair stage**, not a wholesale new extraction strategy.
- Correctly challenges the arithmetic behind the projected 92–94% score. It notes that the gains from the 16 bad reads, 36 fallout cells, and allocation repair are not necessarily independent and that raw/reference agreement differs from adjudicated score.
- Identifies several important safety requirements:
  - source-priority ordering, with printed filing values above derived/allocation/model values;
  - formula evaluation and numeric preview rather than allowing formula strings to bypass guards;
  - structured repair manifests rather than free-form model edits;
  - narrow, verified lock overrides;
  - recalculation/dependency validation after repairs;
  - authority policy across two documents;
  - idempotence testing;
  - negative controls and abstention behavior;
  - runtime and failure-injection tests.
- Its proposed repair object is useful and concrete. Requiring a target semantic identity, value, page/table/row/column context, units, and reason is a good implementation direction.
- It correctly emphasizes that “24/24 statement alignment” is not enough to establish safe cell-level overwrites. That distinction is central and easy for a team to miss.
- It provides a valuable offline-validation addition: first reproduce the baseline run before trusting a replay with new code. This is one of the highest-value recommendations in a one-dispatch setting.

**What it does poorly**

- The supplied response is incomplete. It begins Q2 but cuts off before completing the comparison of alternatives, and it does not answer Q3. Since the user explicitly requested concrete handling of the +362 forecast base and 16 Driver/MD&A reads, this is a major failure of completeness.
- It is somewhat more expansive than necessary before answering the highest-risk operational question: what exactly should be shipped tonight versus cut. It identifies good controls, but does not provide as sharp a “P0/P1/cut” prioritization as Response C.
- It does not sufficiently distinguish between:
  - historical face-statement repairs, which can be highly deterministic; and
  - forecast/Driver-table repairs, which require lineage and table-structure handling rather than statement reconciliation.
- It warns that every DIFF becoming a suspect can create a repair storm, but it does not go far enough in specifying hard operational budgets: maximum repairs, maximum rereads, monotonic-improvement requirements, rollback behavior, and timeout behavior.
- It does not explicitly challenge the proposed offline gate’s likely overfitting to run 114 as forcefully as it should. It mentions replay limitations, but a one-artifact replay can prove only that known defects are repairable—not that cold-run behavior is safe.

### Response B

**What it does well**

- The opening framing is directionally sensible: deterministic accounting and mechanical scaffolding are more appropriate than relying on unconstrained LLM judgment.
- It recognizes that the one-dispatch constraint requires attention to failure modes rather than merely maximizing upside.

**What it does poorly**

- The response is effectively unusable because it is truncated almost immediately. It ends during “Hole 1” and does not provide substantive analysis, an alternative plan, or any answer to Q3.
- It does not engage with the crucial technical distinctions in the prompt:
  - allocation formula writes bypassing numeric guards;
  - how to safely reconcile historical statements;
  - forecast-year residual lineage;
  - MD&A/segment table extraction;
  - lock override constraints;
  - offline promotion criteria;
  - the difference between raw scoring and filing adjudication.
- It gives no actionable implementation details, no dispatch gate, no risk prioritization, and no discussion of whether run-twice-and-vote or a mega-context rewrite should remain rejected.
- Even if the omitted continuation had been strong, the supplied response cannot satisfy the requested task as presented.

### Response C

**What it does well**

- Provides the strongest overall judgment under the actual operational constraint: **do not ship the broad plan as written; ship a narrower deterministic subset.**
- Correctly identifies the central mismatch in the proposal: replaying repairs on a known run-114 artifact is materially easier than surviving a fresh cold luna run. This is arguably the most important insight in the entire evaluation.
- Clearly explains why the offline replay gate can overfit:
  - stage 1 may prevent a bad write that replay merely repairs;
  - cold-run suspect distributions will differ;
  - page ordering/OCR/model behavior can change;
  - known post-mortem knowledge can leak into implementation.
- Gives an excellent warning about lock overrides: a model-generated “cite” is not evidence unless it is verified deterministically for value, period, scale, entity, statement identity, and uniqueness.
- Correctly identifies the formula-string bypass as a general class defect, not merely an allocation-specific defect. Its “evaluate-or-refuse at the Writer chokepoint” recommendation is highly practical.
- Strongly distinguishes safe historical reconciliation from unsafe forecast reconciliation. The recommendation to restrict face reconciliation to **historical columns only** is especially important.
- Provides concrete operational controls absent from the initial proposal:
  - capped number of repairs and rereads;
  - monotonic checksum/improvement requirement;
  - revert/last-good-workbook behavior;
  - runtime testing with the same model/image budget;
  - dispatch failure must preserve a scorable workbook.
- Gives a much better prioritization framework:
  - **P0:** deterministic allocation statement-wins, formula numeric preview, and a named/mechanism-level +362 fix;
  - **P1:** narrow historical face reconciliation and bounded Driver table parsing;
  - **P2/cut:** open-ended LLM decompose, arbitrary fable rereads, broad lock override, and “every DIFF to repair.”
- Directly answers Q2: run-twice-and-vote and mega-context rewrite remain correctly rejected; the materially better alternative is a narrower, safer post-write system rather than a larger autonomous repair loop.
- Gives the best Q3 answer:
  - For the +362 forecast issue, identify the first affected year and exact base cell, classify the failure mechanism, prove a deterministic repair on run 114, and enforce a forecast identity gate.
  - For Driver/MD&A rows, send structured **table jobs**, not vague failing-check prompts. Bind year columns first, then rows, then units/scale; reject ambiguity; do not allow Driver tables to override face-statement values or locks.
- It is particularly good at identifying what colleagues may misunderstand: “36 fallout comes for free,” “a cite is enough,” “24/24 aligner means repair is safe,” and “rereading with the same model will fix missed tables.”

**What it does poorly**

- Its tone is intentionally forceful and occasionally overstated. Statements such as “load-bearing lie” and predictions of a score in the 70s may be rhetorically useful for a council review, but they are stronger than the evidence strictly supports.
- It may be too pessimistic in treating some proposed components as categorically unsafe. A carefully bounded `decompose` tool can be useful if it is deterministic and operates over a line-index/dependency graph, as the response itself later acknowledges. The issue is not necessarily the tool’s existence but whether it has model-driven write authority.
- The proposal to prepare fixed jobs from the 16 known bad reads is operationally sensible, but it needs a clearer explanation of how to preserve the “generic across companies” requirement. It gestures toward a generic table-job schema, but a reviewer could worry that pre-encoding known pages, aliases, or target rows becomes filing-specific tuning.
- It does not fully explore whether there is a constrained version of run-twice-and-vote that could help—for example, using a second partial review pass rather than a second full run. Still, given the quota/runtime constraint and correlated errors, its conclusion against two full runs is convincing.
- Its conclusion that 90% may not be a realistic tonight objective is appropriately candid, but management may need a more explicit decision rule: dispatch if P0/P1 achieve a stated replay score and runtime envelope; otherwise dispatch the stable baseline or explicitly accept the lower-probability upside gamble.

FINAL RANKING:
1. Response C
2. Response A
3. Response B

### Review by google/gemini-3.1-pro-preview

**Evaluation of Responses:**

**Response A:**
*What it does well:* This response provides a highly intelligent and appropriately conservative evaluation of the proposed plan. Its breakdown of Q1 is excellent, correctly identifying that a 24/24 statement aligner does not guarantee cell-level semantic joins, and that "every diff becomes a suspect" is a recipe for a 50-minute repair storm. The requirements it sets for the offline validation (reproducibility, idempotence, full scorer proxy) are rigorous, actionable, and directly address the structural risks of the plan. 
*What it does poorly:* The response suffers from a major formatting/generation failure. It completely cuts off in the middle of answering Q2 and entirely fails to answer Q3. Because it misses a third of the prompt, it cannot be considered a complete response.

**Response B:**
*What it does well:* It starts with a strong, decisive tone that fits the persona of a technical vetting council, correctly identifying the core architectural principle (constrain via accounting identities, not prompting).
*What it does poorly:* The response cuts off after only two paragraphs. It fails to answer almost any of the prompt's questions and is completely unusable as a result.

**Response C:**
*What it does well:* This is a phenomenal, master-class response. It perfectly adopts the requested persona—a senior, highly technical engineering lead vetting a risky, last-minute deployment. It systematically dismantles the flaws in the proposed plan, correctly pointing out that the proposed offline validation is essentially overfitting to known post-mortem data rather than proving cold-run capability (the "load-bearing lie"). For Q2, it offers a strictly prioritized, deterministic alternative plan (P0, P1, P2) that respects the compute budget and constraints. For Q3, it provides incredibly concrete, step-by-step instructions on how to mechanize the forecast (+362) and Driver (16) misses without relying on open-ended LLM loops that are doomed to fail in a cold run. Finally, it succinctly and accurately flags exactly what other members (and the proposal's author) are getting wrong. It is thorough, complete, and technically flawless.
*What it does poorly:* There are virtually no flaws in this response. It perfectly balances context, tone, and actionable technical advice.

FINAL RANKING:
1. Response C
2. Response A
3. Response B

### Review by x-ai/grok-4.6

## Response A
**What it does well.** A is the most systematically engineered write-up of *risk controls*. It correctly treats the proposal as directionally right but not a ≥90 guarantee, and it spends its energy where a one-dispatch plan actually dies: identity mismatch (period/entity/units/scope), formula writes that bypass numeric guards, unbounded “every DIFF is a suspect” repair storms, lock override as an escape hatch, recalc/engine path dependence, dual-doc authority, and offline overfitting to a known artifact. The proposed artifacts are concrete and implementable (source-priority lattice, typed write origins, structured repair JSON, fail-closed Writer, idempotence + negative controls). The extra promotion gates (baseline replay, full-diff safety, scorer proxy, runtime injection) are stronger than the plan’s four listed gates.

**What it does poorly.** It does not finish the assignment. Q2 is truncated mid-sentence and Q3 is missing entirely — the two questions that matter most for “one cold run tonight.” It also slightly over-approves the *shape* of an autonomous repair loop (“approve the direction if gates pass”) without forcing the narrower P0/P1 cut that one 50-minute luna dispatch actually needs. Several sections are generic-excellent engineering rather than tied to the named residuals (the two allocation cells, +362, 16 Driver reads, 8 run-right/ref-wrong cells).

## Response B
**What it does well.** The opening frame is right: one dispatch, 50 minutes, constrain via identities not vibes; and it immediately names the allocation-formula bypass as fatal, which *is* the load-bearing bug from the 114 post-mortem.

**What it does poorly.** It is not an answer. It dies at “Hole 1” and never covers the rest of Q1, Q2, or Q3, never gives an offline validation checklist, never handles forecast/Driver, and never flags what other members will get wrong. As a council vet it is unusable.

## Response C
**What it does well.** C is the only response that actually vets the *plan as a one-dispatch object*. It names the central methodological error: offline replay on 114’s already-written book is a different task from a cold luna run, and a green replay is necessary but nowhere near sufficient. Holes A–G are specific to this codebase (lock chokepoint punched by “cites,” formula preview at Writer, 24/24 aligner ≠ cell-safe/generic/forecast-aware, `decompose` as a new non-deterministic brain, fallout arithmetic, runtime/abort, scoring into the reference). Q2 is better than A’s incomplete take: correctly keep the rejected options rejected, then replace “add Fable as an in-run residual chase” with a narrower P0/P1/P2 cut that can actually ship tonight. Q3 is the strongest section in the set — it refuses to pretend face-reconciliation will see forecast years, demands a named +362 mechanism *before* dispatch, and replaces “look at the page again” with table jobs (year bind → alias bind → scale from caption, statement wins, no Driver lock override). It also does the requested “what others will get wrong” list, and it is honest that 92–94% is an upper bound, not the plan.

**What it does poorly.** The ending is slightly clipped. The verdict is harsh enough that a team could under-ship a *safe* narrow face-recon that A would have kept. A few claims are assertive without numbers (left tail “well below 114,” “floor is not 87–88”) that would be stronger if tied to an explicit dependency cut. Tone is more prosecutor than design partner, which can bury the salvageable P0 items.

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

The Council has reviewed the proposal. The consensus is clear: **do not ship the plan as written.** 

While the architectural instinct to "finish like Fable" via post-write reconciliation is directionally correct, Stages 3, 4, and 5 of your proposal introduce non-deterministic, open-ended LLM loops. In a 50-minute, single cold-run environment, these stages will blow past your time budget, punch holes in the safeguards you built this morning, and risk dropping your score well below the current 81%. 

A 90%+ score is achievable tonight, but only if you treat Run 114’s post-mortem as a map of *known structural defects* to be fixed with deterministic accounting identities, rather than hoping a weaker model (luna) will autonomously rediscover and fix them via a new orchestrator tool.

Here is the Council's synthesized blueprint for what to ship, what to cut, and how to safely hit your target.

---

### Q1: Holes and Failure Modes (The "One Dispatch" Traps)

**1. The Cold-Run Replay Fallacy**
Replaying a repair stage on Run 114’s *already-written* workbook is a fundamentally different task than a cold luna run. Your offline replay tests whether you can fix a known mistake after the fact. It does not prove that the new code will survive fresh errors, or that if Stage 1 changes early writes, the cascade won't generate completely new failures that 114 never saw. Overfitting to the 114 artifact is your biggest blind spot.

**2. Lock Overrides Punch a Hole in the Chokepoint**
You secured the run this morning by funneling writes through a single chokepoint with world-band and checksum locks. Stage 5 bypasses this. A model-generated "cite" is not the statement; it is a string *claiming* to be the statement. If you allow luna to override locks based on a cite, you invite wrong-year mismatches, wrong-scale errors (millions vs. thousands), or note-vs-face authority conflicts. 

**3. "24/24 Alignment" ≠ Safe Cell Identity**
Statement-level alignment is not sufficient for cell-level overwrites. A text match on a label does not guarantee you are pulling the right number (e.g., continuing operations vs. total company, restated vs. as-reported). To safely overwrite a cell, the repair engine requires an exact, deterministic semantic join: `{document_id, statement, period_end, column_header, row_label, units, entity}`.

**4. The Allocation Formula Bypass (Class-Level Bug)**
You correctly diagnosed that allocation wrote formulas, bypassing the numeric band guard. Stage 1 fixes this for *allocation*, but misses the class-level bug: formula strings blind your guards. Any formula write must be evaluated into a numeric preview and run through the band/lock guards *before* the write is committed.

**5. The "Every DIFF" Repair Storm**
Feeding every diff to a repair loop will thrash your 50-minute budget on rounding differences, unit conversions, and benign forecast deviations. Repairs must be strictly bounded.

**What you must validate offline before dispatch:**
*   **Baseline Reproducibility:** Ensure you can reproduce Run 114's exact state without the new code.
*   **The Dependency Cut:** Prove that zeroing the two allocation cells to face values and fixing the +362 base *actually* collapses the 36 fallout cells. If it doesn't, your arithmetic for hitting 90% is flawed.
*   **Idempotence:** Run the new Stage 1/2 twice on its own output. The second pass must make zero changes.
*   **Scoring Parity:** Ensure the 8 cells where the run is right and the reference is wrong are mathematically protected from being "reconciled" toward the wrong reference.

---

### Q2: The Materially Better Plan (Prioritized for Tonight)

Run-twice-and-vote and mega-context rewrites are correctly rejected (correlated errors, quota limits, extreme variance). The better plan is narrower: **ship only what is mechanizable from the 20-minute post-mortem.**

**P0 (Must Ship Tonight or Abort Dispatch):**
1. **Deterministic Allocation Statement-Wins:** Before formulas run, index printed face lines deterministically. Unique hits freeze the component; only the truly undisclosed residual pool scales. *No LLM in this path.*
2. **Numeric Preview at Writer Chokepoint:** Evaluate all formulas at the Writer. Enforce bands, locks, and checksums on the resulting numeric value, not the string.
3. **Named +362 Mechanism Gate:** (See Q3 below).

**P1 (Ship only if P0 replay is flawless and fast):**
4. **Historical-Only Face Recon:** Limit Stage 2 recon exclusively to historical columns. Suspect = written ≠ unique printed face. Apply these fixes deterministically (no LLM). Cap the max number of repairs, and enforce a rule that checksums must monotonically improve or remain unchanged; otherwise, revert.
5. **Strict Driver Table Jobs:** (See Q3 below).

**P2 (CUT TONIGHT):**
*   `decompose {check}` as a free-form LLM tool. (It will invent components).
*   Open "fable re-reads" of arbitrary suspects.
*   General lock overrides.
*   Routing "every DIFF" to a repair loop.

---

### Q3: Handling Forecast (+362) and Driver Reads Tonight

These are the least derisked parts of your plan because your proposed machinery is "statement-face shaped," and forecasts/MD&A tables are not.

**The +362 Forecast Base:**
Stage 2/3 will not see a forecast residual because forecasts have no printed historical face. `decompose` will simply hallucinate components.
1. **Offline:** Hand-diagnose the exact mechanism on Run 114 right now. Is the historical seed wrong? Was a one-time item not stripped? Is a growth driver applied to the wrong base?
2. **In-Run:** Do not use an LLM to hunt this. Implement a **Deterministic Forecast Identity Gate**: `base = f(last closed historical, policy)`. Any output that violates this identity is flagged by the formula, and mechanically corrected based on the policy.

**The 16 Driver/MD&A/Segment Rows:**
"Look at the page again" is a human instinct. Fable-mode already had the page and missed it; sending the same model back to the same page with a similar prompt will yield the same failure.
1. **Offline:** Convert the 16 misses into strict, generic **Table Jobs**: `{pages, table_id, year_headers, unit_hint, scale_hint, aliases}`.
2. **In-Run Detector:** Any page with a numeric grid + year headers + a unit token triggers the parser. Do not wait for a failing check.
3. **Strict Binding:** Bind columns by year *first*, then rows by alias, then apply scale strictly from the caption/header. Reject if ambiguous.
4. **The Ultimate Guardrail:** Driver tables **CANNOT** override a statement face or a locked cell. Statement wins. This prevents MD&A approximations from destroying balance sheet integrity.

---

### What Other Members (and Management) Will Get Wrong

*   **"Offline replay of the new stage on 114 is our safety gate."** Replay only proves you can fix known bugs. It is a gate against failing the absolute minimum standard; it does not prove cold-run safety.
*   **"Lock override with a cite is safe because statement wins."** Without a strict deterministic verifier (period, scale, entity, uniqueness), an LLM cite is just an unattended write wearing a hallucinated permission slip.
*   **"The 36 fallout cells come for free once we fix the allocations."** Do not assume this. Measure the dependency cut. Some fallout is likely independent plug/sign/scale errors.
*   **"Fable re-read will pick up the Driver tables."** The model already failed those pages. You need rigid grid/year binding, not more tokens.
*   **"96% ceiling implies 90% is conservative."** The 96% ceiling was achieved with a stronger, unguarded model. Luna in-run will not beat a strong model's offline chase. Your honest upper bound tonight is 92-94% *if* P0 works perfectly and the 36 fallout cells are purely dependent. Prepare management for a high-80s adjudicated floor.
