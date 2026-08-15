# Direct mapping — read the pages, fill the rows

You are the analyst marking this model to actual results. Below are (1) pages
from the company's latest results disclosure and (2) a block of rows from the
model. For each row, find this year's actual value in the pages.

The run's objectives rank: balance > key numbers (sales, profits, cash, the
BS totals, CFO/CFI/CFF) >>> everything else. A statement-total or key row
deserves your maximum care — get the SCOPE right (consolidated 合并, never
parent-company 母公司; the group total, never a segment's) and name the tie
that validates it. Watch the statement's own arithmetic: a value that breaks
the subtotal it feeds is the wrong line, however good the label looks.

**Your mission: every row filled.** An analyst depends on this column being
updated — an unfilled row silently keeps LAST YEAR's number, which is worse
than a flagged estimate. Before giving up on any row, exhaust these options:
(a) the prior-year match anywhere on these pages; (b) DERIVING it from lines
that ARE here (totals minus known components); (c) if you are convinced the
figure lives elsewhere in the report, answer NEED_PAGES with your best guess
of where ("segment note", "five-year statistics", "fixed asset note",
"scheme of control statement") — the harness will fetch those pages and ask
you again. NOT_FOUND is the LAST resort, reserved for figures a results
disclosure genuinely never contains.

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
               "status": "OK|DERIVED|UNCERTAIN|NEED_PAGES|NOT_FOUND",
               "page": <page number>, "line": "<the line you read, briefly>",
               "hint": "<for NEED_PAGES: where you think the figure lives>"}]}
Include EVERY row id listed below exactly once.

## Pages
{PAGES}

## Model rows to fill
{ROWS}
