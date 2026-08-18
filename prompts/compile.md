# COMPILE — fill this sheet's open column

Below is one sheet's open work. UNDERSTAND WHAT THIS COLUMN IS: it is the
REPORTED period being marked to actual — the company has already
announced these results. Every open cell still holds LAST year's number
where this year's ACTUAL belongs. Segment splits, operating statistics,
volumes, prices for the reported period are HISTORY now, printed in the
results announcement's MD&A and segment tables — they are exactly what
the analyst opens this model expecting to see updated.

For each row, decide ONE of:
- **write** — the disclosure names this year's value (a candidate line, or
  your own reading of the statement's structure; a 同比/% line yields
  current = prior x (1+pct)). Full precision, cite the page.
- **not_disclosed** — the document genuinely does not carry it this
  period. Say where you looked (at least the statement, the notes, and
  one more place).
- **flag** — you believe a value but cannot cite it, or the mapping is
  ambiguous. Say why in one line.
- **skip** — RARE: only for a cell that stays an analyst's own assumption
  EVEN IN A REPORTED YEAR (a valuation input, a normalized margin the
  analyst overrides). A reported-period operating/segment/financial
  figure is never a skip — if you cannot find it, that is not_disclosed
  or flag, said honestly.

Candidate lines marked [prior-tie] matched this row by NUMBER (last
year's value appears in the line) — that is the reliable signal. Lines
marked [label-kin] matched only by words; read them more skeptically:
same words often mean a different scope (a note row, a ratio, prose).
A 同比/%-change line lets you compute this year's value as
current = prior x (1 + pct) — cite it as such.

TRANSCRIPTION FIRST: rows that ARE statement lines (balance sheet,
income statement, cash flow details) transcribe from THE STATEMENTS
block, top-to-bottom, at full precision — every line of a statement is
printed; a statement row left stale or guessed is always wrong.

ACCEPT BY RECONCILIATION, NOT BY CITATION (the analyst's habit):
- before writing a statement row, check its SECTION still sums to the
  printed subtotal with your value in place; a single-number line is
  placed by that equation (absent from a column = a proven ZERO there);
- a 其中/of-which line is a COMPONENT of the line above, never a peer —
  and when parent and sub-line share the same comparative, a prior-tie
  cannot tell them apart; decide by the prefix and the section equation;
- the report prints important lines TWICE (the analysis section repeats
  the statements with comparatives and YoY%) — an agreeing second
  printing settles a value; never override two agreeing printings with
  one different reading;
- a breakdown block is a PARTITION: read its formulas (derived members,
  residual rows, the total) before writing any member. A re-based /
  merged category must never be written into a narrower model row — see
  the basis-change test in METHOD; unresolved members go stale + RED
  with the disclosure's new partition recorded in the flag note;
- a numeric literal inside a driver formula is a hidden input: search
  the PRIOR document for that exact value to learn what it is, then
  find this year's counterpart — or flag the driver as structurally
  obsolete if its category no longer exists.

SEGMENT PERSISTENCE (owner law): segment breakdowns are scattered
across MULTIPLE tables in the report — the MD&A product tables, the
segment note behind the statements, operating-data tables, the prior
report's grids (your map). Failing to find in ONE table never ends the
search: a number that sits in the model as a HARDCODE is highly likely
printed somewhere — ask for other places ("need") and keep looking.
NEVER write an estimate for a segment row. The terminal state, only
after the tables in ALL documents are exhausted, is the stale figure
with a RED FLAG stating where you looked — the analyst takes it from
there.

LOOK ELSEWHERE (the analyst's skill): the same economics print in
several places — the statement face, the SEGMENT NOTE behind the
statements, other MD&A tables, the five-year summary. If the tables in
front of you lack a row you believe is disclosed, do not guess and do
not give up — ASK for more places with "need". You will receive
additional tables and lines for those rows from elsewhere in the
document. Claim not_disclosed only after the other places came back
empty too.

THE MAP AND ITS COUNTERPART: a [LAST-YEAR report ...] hint shows where
your row's number lived in the prior report; when it carries
"COUNTERPART in CURRENT report", the walk is done for you — that IS
your row's current-period line. If the counterpart's comparative no
longer ties your prior, the company RE-BASED the category: the analyst
method (owner ruling) is to WRITE the counterpart's current-year value,
cite its page, and flag it noting both the model prior and the restated
comparative. Re-based is not stale — stale is only for lines with no
counterpart found anywhere.

SIGHTINGS AND DERIVED LINES: a [SIGHTED in CURRENT report ...] hint is
a line printing your row's prior beside another number — judge the
columns (is the neighbour this year's value, or something else, e.g. a
provision?) before writing. Evidence labelled "closure" or "缺行 /
MISSING ROW" comes from the statement's own subtotal arithmetic: a
single-number line proven to be the comparative means this year's value
is ZERO (write 0, note the absence); a missing-row gap gives you the
value of a line the extraction dropped — reconcile it against your
row's prior (mind the model's own adjustments, e.g. financial-services
flows carved out into separate rows) before writing.

Respond with ONE JSON object:
{"writes": [{"cell": "Sheet!U49", "value": 123.45, "why": "p102: <the line>"}],
 "need": [{"cell": "Sheet!U53", "looking_for": "segment revenue split"}],
 "not_disclosed": [{"cell": "Sheet!U50", "looked": ["statement", "notes", "five-year summary"]}],
 "flags": [{"cell": "Sheet!U51", "why": "two candidate scopes, p60 vs p154"}],
 "skips": ["Sheet!U52"]}

Your writes go through the guarded chokepoint; some may come back
rejected with a reason (wrong magnitude, breaks a passing check, cell is
evidence-tied). You will get one repair pass with those reasons —
rejections are information about the model, not noise.
