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
