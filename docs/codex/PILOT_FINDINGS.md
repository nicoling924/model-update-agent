# Pilot evidence — 17 September 2026

Both Codex live pilots ran commit 0c5c611 and were intentionally cancelled after a separate offline probe exposed the mixed-unit conversion error. Neither reached a completed model; cancellation is not a measured accuracy verdict.

- DFE run 35220244123 transcribed the prior annual report, then aborted its scanned pages after insufficient comparative anchors. It subsequently spent several minutes transcribing the current report. Cancellation occurred during extraction.
- CLP run 35220269188 aborted vision for `e_2025 Annual Report.pdf` after early scanned pages lacked enough model-prior anchors. Subsequent document identification correctly classified it as the current annual report. The current document's remaining scanned evidence had already been excluded. Later statement identification refused its balance-sheet and cash-flow page candidates.
- Neither cancelled artifact contains a finished extraction ledger or recorded mapping turns. The raw vision cache was not uploaded by the existing workflow. These artifacts cannot support a faithful completed live replay.

The deeper unresolved issue is that extraction availability depends on compatibility with the model before document identity and mapping are established. A model with restatements, different granularity, or unfamiliar structure is particularly exposed. Simply raising the early-abort count would preserve this defect. The next investigation must separate transcription evidence from permission to write a model cell, preserve uncertainty, and maintain a bounded runtime.

Historical corroboration: the repository's scores for DFE 35193527927 and CLP 35193525021 both report zero review turns after earlier stages consumed the clock. DFE also records an incorrect zero cash write from a beginning-cash comparative. CLP records a balanced workbook whose retained-earnings plug hid a minority-interest definition mismatch. These are reasons to measure balance, printed keys and rollover independently, and not treat delivery or a green museum as a live accuracy claim.

Local downloaded evidence: `/private/tmp/codex-cancelled-pilots/{DFE,CLP}/{artifact,logs}`. No model in Claude's checkout was modified.

## Candidate response to the extraction failure

The new draft removes the numeric early-abort rule, classifies historical documents using their printed identity before vision, retains agreeing unanchored transcriptions without claiming a verified scale, and requests higher resolution on missing/conflicting readings rather than model mismatch. It removes more pipeline code than it adds. Four extraction contract tests and the full existing bench pass. Workbook gates and fresh live pilots must complete before an accuracy/runtime claim.

The earlier unit fix was pushed as bffc55e and GitHub regression run 35224106449 succeeded. Its three balanced replay results and successful EPS/inventory/finance-cost readiness cases are recorded under `validation/units`.

## Later warm pilots and the cold-start clarification

Runs 35228404338 (DFE) and 35228421482 (CLP), at dfa4cc4, were cancelled after the owner explicitly required no prior context in any form. Both loaded checked-in `spec.yaml`; the 15-minute CLP benchmark 35232276769 at 36b37bc also reused a pinned extraction and was cancelled. None meets that requirement. Their logs may inform engineering diagnosis but must never seed the cold agent.

Before cancellation, CLP extraction/preparation took 10.5 minutes; the unrouted bulk pass produced 5 plain and 11 red writes, and later sequential mapping reached 62 plain / 70 red with 119 inputs unreached. DFE preparation took 17.1 minutes; bulk mapping produced 2 plain / 4 red, followed by 44 plain / 42 red with 136 unreached. These are intermediate coverage counts, not correct-input counts or final accuracy. They corroborate the route-before-bulk fix already independently pinned and committed in 36b37bc. Both runs reached review before cancellation; no completed-model verdict is claimed.

The strict cold preflight additionally exposed missing formula-linked year headers and false check classification that saved specs had hidden. Their root causes and evidence-based changes are recorded in MVP_CHANGE_CONTRACT.md. The next live evaluation starts only from the original model and supplied PDFs, with a recorded input manifest.
