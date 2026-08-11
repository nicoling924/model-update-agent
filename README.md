# Model Update Agent (portable pack)

An LLM-agnostic agent that marks equity-research valuation models (.xlsx) to actual
results and rolls them forward from financial disclosure PDFs — in one run, with
balance-sheet-grade accuracy, **on any OpenAI-compatible LLM** (GPT, DeepSeek, local
vLLM, Claude via proxy, ...).

Ported from a calibrated Claude Code ("Project M") setup. The accuracy does **not**
come from the LLM — it comes from the harness. The LLM is only consulted where
judgment is genuinely required; everything that can be deterministic **is**
deterministic Python:

| Step | Who does it |
|---|---|
| Read PDFs, page text | Python (pdfplumber), cached |
| Extract statements → staging JSON | LLM, **validated arithmetically in code**, retried once |
| Map disclosure line → model row | Code first (glossary + prior-year triangulation); LLM only for leftovers, 1 budgeted call each |
| Write cells (type/format copy, flags, notes) | Python, with read-back verification |
| Recalculate & integrity checks | Python formula evaluator (no Excel needed) |
| Formula-clobber protection | Python (pre/post formula-map diff) |
| Blind adversarial review | LLM, **fresh context**, optionally a different/stronger model |
| Reports (_REPORT tab + markdown) | Python |

This division of labour is what makes a weaker LLM viable: the model cannot loop,
cannot silently overwrite formulas, cannot deliver an unbalanced workbook — the
harness refuses.

## Generic by design

Nothing about any company, industry, or model layout is hard-coded in the engine.
All specifics live in two per-company files that travel with the model:

- `companies/<NAME>/spec.yaml` — machine-readable anatomy: sheet map, year axis
  (which column = which year), input rows, check cells, tie-out anchors, back-out
  rules. **Created automatically on first contact** by `discover` (cold-start
  anatomy discovery: the LLM reads the workbook structure and proposes the spec,
  marked as a draft for analyst review). Warm runs read it and get faster + safer.
- `companies/<NAME>/MODEL_SPEC.md` — prose contract: conventions, quirks,
  analyst rulings, per-company synonym aliases. Appended to the system prompt.

The mapping cascade is industry-agnostic because it matches on **numbers, not
names**: the primary strategy is triangulation — find last year's value (which the
model already holds) in the disclosure's comparative column, then read across to
the current-year figure in the same row. Works identically for a utility, a bank,
or a retailer, in any language, because it never depends on labels.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env          # set LLM_BASE_URL / LLM_API_KEY / LLM_MODEL
# drop your model + disclosures into companies/<NAME>/{model,disclosures/<PERIOD>}/
python run.py discover companies/<NAME>                 # first time only
python run.py update   companies/<NAME> <PERIOD>        # e.g. FY25, 1H26
```

Outputs: updated workbook in `model/` (pre-update copy archived), a `_REPORT`
first sheet (flags, back-outs, big moves, actual-vs-estimate — every entry a
clickable link with live value), and `updates/<PERIOD>_update_report.md`.

## The guardrails (why this survives a weak LLM)

1. **Extract before you map.** The LLM never edits a cell while reading a PDF.
   It fills a staging JSON (exact labels + page refs), which code validates:
   BS must balance, subtotals must add, EPS × shares must ≈ attributable profit.
   Invalid → one retry with the errors quoted → still invalid → hard stop.
2. **One-pass search budget.** Per missing figure: one cascade pass (direct find →
   triangulate → back-out rule → prior-year AR on demand → estimate + flag).
   The observed weak-LLM failure mode — burning hours re-searching one number —
   is structurally impossible: the loop is in code and it does not loop.
3. **Acceptance = reconciliation, not label match.** A mapping is accepted only if
   it makes an arithmetic tie pass. Catches the dangerous case: same word,
   different definition ("underlying profit" ≠ the model's "core profit").
4. **Mark-to-actual recipe.** Copy the prior actual column's formula pattern,
   cell type, and format; overwrite only disclosed inputs; rewrite formulas that
   embed prior-year constants. Enforced by `workbook.py`, not by prompt.
5. **No formula clobbering.** A full formula map is snapshotted pre-run; post-run
   diff must show changes only in the target column + logged restatements.
6. **Every write is read back.** Write success codes are not trusted.
7. **Integrity gate.** BS balances every period, CF ties to BS cash, RE roll,
   segment sums, EPS vs disclosed, no #REF!/#DIV0!, tie-out anchors exact.
   Any failure blocks delivery.
8. **Blind reviewer.** A fresh LLM context (configurable to a stronger model —
   recommended if the updater model is weak) gets ONLY the disclosures + the
   updated and pre-update workbooks. It re-extracts and diffs. Findings are
   surfaced in the report — never silently auto-fixed.
9. **Flag, don't guess silently.** Two-tier: light-red `FFC7CE` = uncertain /
   needs analyst review; orange `FFC000` = backed-out / awaiting true-up.
   Both carry methodology notes and appear in `_REPORT`.
10. **Compounding memory.** Judgment calls get written back to `spec.yaml` /
    `MODEL_SPEC.md` so the next run inherits them. Accuracy grows per company
    over runs — this is where most of the calibrated accuracy actually lives.

## Repo layout

```
agent/        engine (deterministic; LLM calls isolated in llm.py)
prompts/      all LLM-facing text — edit freely, no code changes needed
companies/    one folder per covered company (template included)
run.py        CLI entry
config.yaml   models, budgets, reviewer settings
```

## Model configuration

`config.yaml` / `.env`: any OpenAI-compatible `chat/completions` endpoint.
Set `reviewer.model` to a different (ideally stronger) model than `updater.model`
— cross-model review catches blind spots same-model review shares. JSON-schema
responses are requested where supported and fall back to prompt-enforced JSON
with code-side validation + retry.

## Benchmark fairness policy

Per-company files (`MODEL_SPEC.md`, `spec.yaml`) must hold STRUCTURAL knowledge
only — layouts, conventions, composition rules, prior-period corrections — never
current-period disclosed figures. The LLM's context per call is: generic prompts +
scrubbed MODEL_SPEC + the model's own stored priors + disclosure text. Run logs,
scoring tools, and any reference/ground-truth workbook stay outside every prompt.

## Honest limitations

- First run on a new company is a **calibration run**: expect the analyst to
  review the draft spec.yaml and the flagged cells. Runs 2+ are where the
  accuracy compounds.
- The formula evaluator covers the common function set (SUM/IF/AVERAGE/...).
  Exotic functions fall back to "open in Excel to recalc" (the file is saved
  with full-recalc-on-load).
- A weaker LLM will produce more `FFC7CE` flags and a few more reviewer
  findings, not silent errors — that is the design intent.
