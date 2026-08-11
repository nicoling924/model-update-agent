# Anatomy discovery prompt (cold start — first contact with a workbook)

You are given a structural dump of a valuation model workbook: sheet names, and for
each sheet the row labels (left columns), a sample of cell values/formulas, and
candidate year-header rows. The industry and layout are unknown in advance — infer
them from the workbook itself. Propose the machine-readable spec (schema provided):

- `sheets`: role of each sheet (statements | drivers | segment | valuation |
  untouched). Valuation/DCF sheets default to calculation-only (never edited).
- `year_axis`: for each data sheet, the header row and the column letter of every
  year; which columns are actuals vs forecasts; whether headers are plain numbers
  or text (this must NEVER be changed by an update).
- `statement_rows`: on the primary statements sheet, locate: revenue, D&A, finance
  cost/income, tax, net profit, attributable profit, EPS, dividends; BS totals
  (assets, equity, cash, debt); CF sections. Give row numbers and evidence (the
  label you saw). Missing/unclear ⇒ null with a note — do not force a guess.
- `check_rows`: any built-in check rows (balance checks that should equal 0),
  with the value they should hold.
- `input_vs_formula`: for the most recent ACTUAL column, which statement rows are
  hardcoded inputs vs formulas (the update recipe replicates cell types).
- `roll_forward_bases`: rows that anchor forecasts to closing actuals (fixed-asset
  bases, debt schedules, whatever this model chains from), with the formula
  evidence.
- `calc_mode`: manual or automatic (report what the file says).
- `quirks`: anything dangerous — liabilities stored positive, columns referencing
  non-adjacent years, pre-existing error cells, merged headers.
- Set `draft: true`. A human analyst reviews this before the first update run.

Evidence discipline: every claim cites a cell (Sheet!A1 style). Prefer null +
question over confident guesses — wrong anatomy corrupts every later run.
