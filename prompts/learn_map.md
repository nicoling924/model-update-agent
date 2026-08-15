# Calibration mapping — identify each model row in last year's report

You are calibrating an equity research model against the year it was already
completed for. Each model row below shows its KNOWN values for that year (and
the year before, where available). The pages are from that year's disclosure.

Your task per row: point to THE LINE in the pages that IS this row — the line
whose printed figures match the known values (current year, and prior year
beside it where shown). This is identification, not estimation: the answer is
on the page. Prior-year values printed beside current ones are your strongest
confirmation.

- Labels are synonyms, not exact matches (turnover = revenue; PP&E = fixed
  assets). Match on the NUMBERS; report the label as printed.
- If the row's value appears on several lines (subtotal echoes), choose the
  line whose meaning matches the row's label; say so in "line".
- If the value genuinely appears nowhere in these pages, status NOT_FOUND —
  the row may be analyst-derived; never force a match.

Return JSON:
{"mappings": [{"id": "<sheet>!<row>", "value": <the known current-year value you
               matched>, "status": "OK|NOT_FOUND",
               "page": <page>, "line": "<the line's label as printed>"}]}
Include EVERY row id exactly once.

## Pages
{PAGES}

## Model rows to identify
{ROWS}
