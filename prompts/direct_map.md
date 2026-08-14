# Direct mapping — read the pages, fill the rows

Below are (1) pages from the company's latest results disclosure and (2) a block
of rows from an equity research model that must be marked to actual. For each
row, find this year's actual value in the pages.

How to work, in priority order:
- **Match on the prior-year number.** Each row shows its prior-year value; find
  that number in the pages' comparative column and read across to the current
  year on the same line. This beats label matching — labels drift, numbers don't.
- Labels are synonyms, not exact (turnover=revenue; PP&E=fixed assets). A row's
  memory hint (where it mapped last year) is strong evidence.
- **Respect the model's sign convention**: return the value with the SAME SIGN
  PATTERN as the prior-year value shown (if prior is positive and the report
  prints the figure in brackets, return it positive; costs shown negative stay
  negative).
- A model row may be a combination of disclosure lines (net = cost − income);
  status DERIVED, and say the components in "line".
- If the figure is genuinely not in these pages, status NOT_FOUND — never guess.
- If you found a number but are unsure it is the right line, status UNCERTAIN.

Return JSON:
{"mappings": [{"id": "<sheet>!<row>", "value": <number or null>,
               "status": "OK|DERIVED|UNCERTAIN|NOT_FOUND",
               "page": <page number>, "line": "<the line you read, briefly>"}]}
Include EVERY row id listed below exactly once.

## Pages
{PAGES}

## Model rows to fill
{ROWS}
