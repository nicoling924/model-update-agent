# Historical input findings — owner approved

These are errors in the unchanged supplied workbooks. The two isolated Codex-branch workbook copies have been corrected; Claude's checkout and original workbooks are unchanged. Pre-correction copies are archived. Proposed corrections are data/formula corrections for the analyst, not company-specific pipeline rules. They do not demonstrate live-agent generality.

## DFE 1H2006

- Existing `Model!AG132`, labelled Cash - year beginning: `=B132`, evaluates to 12,163.40.
- Its cash-flow and ending-cash links use the half-year source column AA on Raw financials. The source's opening cash `Raw financials!AA242` is 3,873.24, and ending cash `Raw financials!AA243` is 3,144.12. These source values are already present in the input workbook.
- The model's cash movement is -729.11. 3,873.24 - 729.11 = 3,144.13, matching ending cash within the existing rounded check. The existing 12,163.40 opening produces an 8,290 rounded discrepancy.
- Proposed output correction: `Model!AG132` becomes `='Raw financials'!AA242`. This preserves a source-linked formula, with an audit note describing the period-link correction.
- Owner explicitly approved this historical formula correction. Applied to the Codex copy; the cash check now evaluates to zero.

## CLP FY2024

- Existing `ROAFNA!AH19`, labelled Other assets: `=4223+36`.
- The 2025 annual report, PDF page 243, prints 2024 comparative current assets of 5,487 and non-current assets of 36. The 2024 annual report, PDF page 274, prints the same figures for 2024. Both were checked directly in the PDFs as well as in the pinned extraction ledger.
- Proposed output correction: `=5487+36`, retaining the analyst's composition. The 1,264 increase exactly closes `ROAFNA!AH31` because the other balance-sheet components already reconcile to the same report table.
- This is not a disclosure restatement: the two documents agree. It is a pre-existing embedded input error.
- Owner explicitly approved this historical formula correction. Applied to the Codex copy; the balance check now evaluates to zero.

Originals inspected: the input copies in `/private/tmp/codex-mvp-verified/DFE-1H25/model/DFE Model.xlsx` and `/private/tmp/codex-mvp-verified/CLP-FY25/model/CLP Model.xlsx`. The failed historical checks were measured before candidate code changed any workbook inputs.

The exact corrections, source/output hashes, archive paths and changed XML members are recorded in [approved-history.json](approved-history.json). Only the targeted worksheet XML member changed in each package; other package parts were preserved byte-for-byte. These are approved data corrections, not new pipeline exceptions.
