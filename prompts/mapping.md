# Mapping prompt (used ONLY for rows the code could not resolve)

The harness resolves most model rows itself: direct label match via the glossary,
then triangulation (finding the model's stored prior-year value inside the staging
data's comparative column and reading across). You are consulted once per leftover
row. You get: the model row (its label, sheet context, prior-year value, and the
prior column's formula if any), the staging extraction (labels, values, priors,
pages), any per-company aliases/rulings, and the four failure modes to consider:

- **synonym** — same concept, different word → name the staging item.
- **definition** — same word, different scope. Check the company's bridge items in
  staging. If the definitions differ, map to the matching DEFINITION and say which
  bridge adjustments you included/excluded.
- **location** — the number lives in a note / five-year summary / segment table.
- **composition** — the model row combines staging items → return a formula over
  staging items (e.g. `finance_costs - finance_income`), not a single value.

You must return, in the schema provided:
- `mapping`: staging item id(s) or composition formula, or `not_found`.
- `tie`: the arithmetic relation that VALIDATES this mapping (e.g. "makes total
  operating expenses sum to -74,206", "segment earnings then sum to 10,909"). A
  mapping without a checkable tie will be rejected and the row will be estimated
  and flagged instead — prefer admitting `not_found` over an untied guess.
- `confidence`: high | medium | low. medium/low ⇒ the harness flags the cell
  light-red for analyst review regardless of your mapping.
- `where_looked`: when `not_found`, list the locations checked so the report can
  record it.

You get ONE call for this row. There is no follow-up. Do not ask questions.
