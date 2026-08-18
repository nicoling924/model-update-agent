# TRANSCRIBE THIS PAGE — completely, exactly

Below is one page of a financial report. Transcribe EVERY line that
carries financial figures — statement rows, note-table rows, breakdown
rows — top to bottom, completely. Do not skip "minor" lines; do not
summarize; do not compute anything.

For each line give the printed label (verbatim, original language), the
CURRENT-period value and the PRIOR-period/comparative value, exactly as
printed (full precision, keep the sign; parentheses mean negative). If a
line prints only one period, set the other to null. If a line has more
than two values (multi-column tables), use the leftmost value column as
current and the matching comparative column as prior.

Respond with ONE JSON object:
{"rows": [
  {"label": "营业总收入", "current": 78615277439.83, "prior": 69695135723.47},
  {"label": "其中：利息收入", "current": 103572375.66, "prior": 103513832.60}
]}

Every row you emit is verified against the page's own printed numbers —
a row whose numbers are not on the page is discarded, so copy exactly.
