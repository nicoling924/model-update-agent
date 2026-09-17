# Codex MVP integration — root causes and evidence rules

Approved scope: implementation, offline validation, then automatic GitHub runs when ready. Work only on codex/mvp-integration. Base d6247fc. Owner's outcomes: all-period balance, key numbers tied to print, and largely correct rollover. Delivering a file does not establish any of these.

## Root cause

Mapping, correction, and evaluation represent the same source-backed change differently, so evidence, workbook state and success measurements can disagree.

## Generic rules

- A disclosure quote has a document identity and a declared unit domain. `printed` defaults to document units, `units: model` is explicit compatibility, and `value` is a model-unit proposal. Never infer the domain from magnitude.
- Mapping and correction use one evidence/write path. Correction batches commit together or restore values, source records, flags and mapping state together. Every successful proposal leaves a persisted before/after/evidence record.
- A prior actual hardcode is evidence of an input role. A cross-sheet link, current-period subtotal or historical accounting formula is structure; relative column letters do not establish its role.
- Measurement and repair use the same existing balance tolerance; independent definitions of balanced caused a check to be rejected by the gate but ignored by repair.
- Objective identity includes its purpose, not just its cell. A positive total-assets value cannot erase a mismatch with the printed total. A missing printed target is unmeasured, not zero difference.
- Key repair, review, snapshots and reporting use one signed evidence-precision comparison. The legacy whole-unit/percentage comparison incorrectly accepted EPS 0.94 against 1.15. Review uses that key verdict, rather than applying the balance-check tolerance to every kind of objective.
- A source claim belongs to the cell state it proves. Every changed write invalidates that cell's prior claim; another period in the same row is a different cell. New evidence is recorded after a successful write, and rollback restores values, evidence and progress together, including when the proposed write changed a hardcode into a formula.
- Arithmetic can establish a calculation, not the meaning of its operands. Keep derivations as formulas and uncertain definitions visible.
- Source tools in both stages refer to the same document shelf. A document-qualified page request never substitutes another document's page.

## Existing code reused

Mapping verdict/application, reader unit proof, Writer read-back and undo journal, consequence snapshot, key panel, forecast comparison, reporting and replay machinery. No company-name/page-location exceptions. No alternate engine or model-specific forks.

## Museum and verification

Independent contract tests in tests/test_mvp_contract.py cover cross-sheet formulas, accounting rolls, inputs below former scan extent, document vs model units through both stages, atomic rollback, nested provenance, independent objectives, and document-qualified page access.

Historical tests whose contracts changed are updated explicitly: model-unit quotes declare their units; a non-writable partner is a structural formula rather than an arbitrary magnitude refusal; numeric compositions retain formulas and need definition review. These changes are not reported as unchanged historical behaviour.

Frozen ledgers and their SHA-256 manifest are under /private/tmp/codex-mvp-pins. Baseline workbooks are separate copies under /private/tmp/codex-mvp-baseline. Replays without recorded mapping turns test deterministic machinery, not live reasoning quality. New acceptance.json separates all three outcomes from delivery.

The present integration is a candidate, not a generality claim. Multi-panel anatomy, evaluator limitations and independent source/rollover review remain acceptance risks. No live dispatch until museum, all three replay balance checks, and affected-cell readiness are recorded.

## Mixed-unit evidence (17 September, next candidate)

Root cause: automatic conversion treats a page's monetary scale as authoritative for every row, including metrics whose comparative establishes a conflicting scale.

Generic rule: conflicting comparative and page units do not establish a conversion. Keep the input unchanged, return the conflicting evidence to the caller, and permit an explicit model-unit proposal through the shared write path. A nonzero comparative can establish evidence even below one model unit. This does not let a coincidental numeric tie override the document's unit evidence.

Museum pin: `test_mixed_unit_pages_do_not_force_a_currency_scale_on_small_metrics` covers positive EPS, small ratios, negative values, refusal without mutation, and an explicit model-unit resolution. Existing conflicting-scale museum exhibits remain unchanged. Full bench and 15 contract tests passed. All three frozen replays delivered and passed their discovered balance checks; all three affected-cell readiness values survived. Evidence is in validation/units/summary.json. This clears this change’s code gate, not overall MVP acceptance.

The GitHub workflow also retains raw vision transcriptions in a separate artifact on cancellation/failure. This preserves paid extraction for diagnosis without introducing cross-run cache reuse or changing production input selection.

## Extraction and model compatibility (next candidate)

Root cause: the reader uses agreement with model priors to decide whether disclosure evidence may be retained, confusing transcription reliability with mapping compatibility.

Generic rule: printed document identity determines historical scope; agreement between independent transcriptions establishes what a scanned row says; matching model comparatives may corroborate units but cannot erase an otherwise readable document. Missing or conflicting transcriptions justify a clearer reading. A merely unfamiliar model does not. Uncorroborated readings stay visible and disputed, outside the automatic join pool. Downstream mapping still owns scope, definitions, conversion and reconciliation.

Museum pins: four independent tests in `tests/test_extraction_boundary.py` cover unfamiliar current reports, disputed rows, printed prior-period scope, and evidence-driven rescanning. An explicit before/after replay of the synthetic specimen retains 0 rows on the previous reader and all 8 agreed rows on the candidate. This tests the boundary; it is not a measured financial accuracy rate. The actual CLP/DFE documents' printed identities were separately checked and correctly identify their current and prior annual reports.

The existing independent transcription, ledger, document identity and mapping components are reused. No company/page-specific exception or larger count fence was added. The full bench, 15 shared-contract tests and four extraction tests pass; all three frozen replays remain balanced and all three full-pipeline readiness cases retain their expected values (one candidate each). Evidence is in validation/extraction/summary.json. Pinned-ledger replays bypass vision and therefore cannot establish new OCR accuracy or actual runtime. Only a completed live pilot can measure those.
