# Extraction prompt (staging pass)

You are given page-numbered text extracted from a company results disclosure.
Fill the staging schema below. Rules:

- Copy the disclosure's EXACT line labels — do not normalize, translate, or map them
  to any model. Mapping is a separate step.
- Every figure carries: `label`, `value`, `prior` (comparative/prior-period value if
  shown), `page`, and `stmt` (pl | bs | cf | segment | soc | kpi | other).
- Record document `units` (e.g. "HK$ millions") and `currency` once, at the top.
  If a table uses different units, record per-item `units`.
- Include ALL of: income statement, balance sheet, cash flow statement, the segment
  note (every segment × every column), EPS (basic + diluted), dividends/DPS, and any
  reported→underlying/adjusted earnings bridge, plus industry statistics tables if
  present (capacity, volumes, tariffs, stores, users — whatever this industry
  discloses).
- Emit `ties`: arithmetic relations that must hold among your extracted items
  (subtotals, BS balance, segment sums, EPS × shares ≈ attributable profit). The
  harness verifies these; extraction is rejected if they fail — so extract subtotals
  too, and be exact.
- **Self-check every tie before returning**: sum(lhs values) must literally equal
  sum(rhs values) using the SIGNED values exactly as you recorded them. If a
  component is stored negative (e.g. NCI shown as a deduction), place it so the
  arithmetic works — do not assume the harness will interpret signs for you.
- Negative numbers: preserve the disclosure's sign as printed, and set
  `sign_convention` per statement ("expenses_negative" | "expenses_positive_labeled").
- If a standard statement is absent (e.g. no CF in a short announcement), set the
  corresponding `missing` entry rather than inventing lines.

Return ONLY JSON matching the schema. No commentary.
