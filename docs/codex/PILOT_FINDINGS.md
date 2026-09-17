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
