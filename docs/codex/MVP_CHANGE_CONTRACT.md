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

## Integrating Claude's page-routing work

Root cause: a numeric coincidence chose which disclosure page the model row was read against, so the agent repeatedly examined irrelevant pages and stopped without mapping the remaining inputs.

Generic rule: page selection is a semantic judgment about the model row and disclosure; numeric matches remain leads. Reuse Claude's routing/scope changes through 984e86b on the Codex branch, preserving document-qualified tools, explicit unit domains and the shared mapping/review writer. A refusal of one page must not retract a previously landed value or close a different row reached from the key table.

The imported routing exhibits cover route placement, re-routing after a rejected page, explicit disclosure-wide closure and fallback when the router supplies no answer. One merge conflict in the parallel-face test was resolved by retaining the newly appropriate minority-interest row and our explicit model-unit proposal; both behavioral assertions stand.

Replay must distinguish routing answers, page-specific mapping answers and sequential mapping answers. The combined harness has separate queues and refuses a missing phase-specific reply without consuming another phase's answer. Routing replies are logged in full; a new contract test re-parses an answer longer than the former truncation point.

Full bench, 16 shared contracts and four extraction contracts pass. The final integrated replay and routing-first readiness gates passed; evidence is in validation/integrated/summary.json. The historical routing diagnosis is imported as `docs/scores/CLP_FY25_pace35217769192_v3-skip-scope.txt`; neither its old metrics nor synthetic routing pace are claimed as current live results. Claude's branch/worktree is unchanged.

## One disclosure view for extraction, routing and quote verification

Root cause: scan evidence existed in the ledger but the page tool indexed only native PDF text, so routing could name a scanned page that the quote verifier could not read.

Generic rule: all reading and verification tools use the same accepted disclosure evidence. Native page text keeps priority; when it is absent, the page view preserves the ledger's non-disputed vision rows in their recorded order and document/page identity. Disputed transcriptions never enter this verified view. Two contract tests exercise the actual page-tool → set-tool path and native-text/disputed-row boundaries. The mapping and review prompts also explain the existing explicit model-unit fallback instead of incorrectly requiring arithmetic for every value.

This completes the integrated candidate under validation. Source is frozen in `/private/tmp/codex-final-build`; the full suite and all three replay/routing-readiness cases passed. No more implementation is being added before the next live evidence.

The final harness exposed a scope mismatch between the automatic face pass and routing: known prior-period pages still received current-input batches. The face pass now reuses `_other_period_docs` exactly as routing does; explicit historical page lookup remains available. A nineteenth shared contract pins both properties. The release snapshot is `/private/tmp/codex-release-build`; final evidence is recorded against that snapshot, superseding the earlier intermediate snapshots.

## Route before bulk mapping (17 September, next candidate)

Root cause: bulk mapping constructed its row/page batches before semantic routing, so the expensive first pass used positional assignments that the later routing stage could not undo efficiently.

Generic rule: establish the model row's semantic source assignment before constructing its batch; page position and numeric coincidence are not assignment evidence. The same mapping clock includes routing. Compact route replies need only references and pages when the choice is unambiguous; figure/definition verification remains in the shared write path.

Related root cause: treating each replacement route as fresh progress let repeated refusals reset the no-progress guard without writing a cell. Generic rule: only the first placement counts as newly completed routing work; a corrected route does not manufacture another unit of progress. This reuses the independently reproduced finding from Claude commit d364d98, without taking its unrelated changes.

Pins: `Contract.test_bulk_mapping_routes_before_it_builds_any_face_batch` failed before the change and now proves a row is read and written from its routed note page in the bulk pass. `Contract.test_rerouting_without_writing_does_not_reset_the_progress_guard` reproduced nine refusal turns before the change versus the existing guard's four-turn bound. Existing concurrency/refusal museum fixtures now explicitly answer the new routing question; their substantive assertions are unchanged.

The readiness harness now requires the named cell to be reached in the bulk pass, rather than allowing the sequential cleanup to mask this ordering defect. Full bench and 21 shared contracts plus four extraction contracts passed. All three frozen replays remain balanced, and all three bulk-readiness values survive delivery with one source candidate each; see validation/route-first/summary.json. Running full pilots remain on dfa4cc4 and are not evidence for this new candidate.

## Strict cold input and discovery contract (owner clarification, 17 September)

Root cause: a fresh runner still loaded checked-in model maps and prompts containing calibration figures, so prior knowledge could enter a nominally cold trial. Generic rule: live inputs are an original workbook and its attached disclosures only; run-specific knowledge is derived inside that run. `tools/cold_run.py` stages byte-verified inputs in a new directory, rejects learned `_SPEC`/`_REPORT` workbooks, excludes sidecars and past artifacts, and exports outputs separately. Existing inputs are not overwritten. The workflow records an input manifest and preserves new extraction evidence. Prompt examples no longer supply CLP's disclosed figures.

Root cause: anatomy discovery treated saved Excel caches and worksheet visibility as authoritative evidence of model structure. Generic rule: resolve the workbook's header expressions, preserving linked text/date values and following its references, without editing cells. A hidden worksheet with a year axis is still part of the model. Unknown/circular formulas establish no year. The real CLP input exposes 10 dated sheets instead of 5 without using a saved map.

Root cause: discovery promoted historical zero differences into balance identities without reading their financial role; share issuance, conditional receivables and residual inputs can also be zero. Generic rule: arithmetic nominates candidates, the LLM identifies genuine accounting identities from the model's labels and expressions, and code then measures those identities. This shares the existing model-reading call rather than adding a separate agent or another stage. Unconfirmed checks stay unmeasured and remain visible to the later anatomy/review tools.

Pins: `test_system_examples_do_not_supply_calibration_answers`, `test_cold_discovery_follows_uncached_header_links_without_changing_cells`, `test_header_resolution_preserves_dates_and_rejects_cycles`, and `test_cold_zero_differences_are_candidates_until_their_role_is_read`; four cold-launch isolation tests also cover unchanged input bytes, rejected knowledge tabs, an occupied destination, an empty child working directory and separate evidence export. The missing-sheet and false-check pins reproduced failures before the changes.

Final frozen bench, 25 shared contracts, four extraction contracts and four cold-launch tests pass. All three mandatory replays are balanced and all three bulk readiness cases pass with one source candidate each; see validation/strict-cold/summary.json. Those historical fixtures are engineering tests, not cold-agent performance evidence. All future live acceptance runs must use the strict cold launcher. The two full pilots on dfa4cc4 and the short pinned benchmark on 36b37bc were cancelled when the owner clarified the requirement; none counts as cold acceptance.

## Source handoff, coverage and input boundaries (18 September)

Root cause: the displayed source identity, proposed edit and write validator did not describe the same operation. A copied heading could become an invalid document key; a formula-with-quote proposal was validated as a whole-cell number against the formula output instead of its changed operand. Generic rule: carry an exact structured source reference, and validate the specific operand being changed while preserving the expression's references and operators. Missing page, absent quote and unresolved scale are distinct findings. No source aliases or fuzzy document acceptance were added.

Root cause: global no-progress termination inferred that the model was exhausted from failures on only the rows already presented. Generic rule: unoffered independent work remains work; a no-progress exit cannot abandon it. Existing duplicate/read guards remain, without a larger turn or time limit.

Root cause: candidate checks were described by their own labels but not by their formula operands, concealing identities under misleading legacy labels. Generic rule: show the referenced operands' model labels when asking the brain to classify an identity. No company-specific check is promoted automatically.

Owner's input boundary: numeric operands inside formulas must be visible even when their magnitudes resemble conventional constants. The brain distinguishes financial inputs from structural scalers through meaning and source evidence. Pure formulas cannot accept numeric replacements or appended residuals. Forecast plug targets are rechecked in each period; an earlier period's numeric site does not make a later formula eligible. Orange colour and a previous agent write confer no permission to plug a formula.

Pins: source_handoff tests; the unoffered-input, operand-visibility, operand-vs-output and candidate-context contracts; plug_boundary tests including numeric C-period catch-all followed by formula D-period catch-all, and an orange pure formula offered to the residual tool. Pre-change queue and source pins reproduced failures. The old museum assertion permitting a prior-year forecast formula to be flattened is explicitly superseded by the owner's newer input-boundary instruction; the revised assertion requires the original expression to remain intact. Other museum updates only adapt source-header formatting. The recorded-face replay contract exercises both legacy and structured contexts.

A two-call local LLM component trial used only five original CLP model rows and one attached PDF page, with explicit user approval. The brain produced the correct two embedded-operand formula edits, which the old writer refused. Offline replay of that exact first answer through the corrected writer now updates both operands and preserves both formula structures. Two directly disclosed hardcodes also update; the separately undisclosed amortisation input remains unresolved. Usage: 5,379 prompt tokens and 1,888 completion tokens, model openai/gpt-5.6-luna. This is a focused component result, not full cold-model acceptance. No additional API calls were used for the corrected replay. The readiness candidate counter finds exactly one source line for each of the four supported local updates. Amortisation is unresolved, not claimed as a success. A separate read-only subagent audit found no actionable regression in the changed formula/plug branches.

Full bench passes, along with 28 shared contracts, five source-handoff tests, four plug-boundary tests, four extraction tests and four cold-input tests. All three pinned replays remain delivered and balanced (CLP FY25: 24 checks; DFE FY25: 118; DFE 1H25: 84). All three bulk-readiness values survive delivery, with one source candidate each. Results and source hashes are in validation/input-boundary/summary.json. These are engineering regression gates; full cold accuracy and native Excel verification are still unproven.
