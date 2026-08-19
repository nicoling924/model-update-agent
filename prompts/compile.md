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

UNITS (every write): the disclosure prints raw currency; the model's
column speaks its own units (thousands/millions). Your value must live
in the SAME unit world as the row's neighbours — before writing, compare
your magnitude against the nearby rows' values; being ~1,000x or
~1,000,000x their size is a unit slip, not a big year. This matters most
on NEW lines, where no prior anchors the scale for you.

SUB-ROWS FIRST (partition mapping order, any language): a partition
table's MEMBERS — the indented rows, the 其中/of-which rows, the
sub-categories — map ONE-TO-ONE onto the model's sub-rows by MEANING
(coal-power equipment is 煤电 is thermal; gas/气电; wind/风电;
hydro/水电; nuclear/核能 — translation is mapping, scope is what you
verify). Map every direct counterpart FIRST. Only then handle parents:
a parent row takes its OWN printed value, or the sum of its
already-mapped subs — and a residual/constructed combination is the
LAST resort, never the first move. A bridge you assembled while direct
counterparts sat unmapped is a wrong answer even when it adds up.

THE BRIDGE TEST (re-based categories): you may only combine the new
table's rows to reconstruct a model row if the SAME combination
reproduces the model's PRIOR from the new table's prior column — last
year is where the truth is known, so last year is where a bridge is
proven. A combination that cannot reproduce last year is not a bridge,
it is an estimate — and segment estimates are never written unless the
analyst has RULED the re-basing (then: direct counterparts first, red
flag always): otherwise stale + RED flag, with the new partition
recorded for the analyst.

THE MAPPING ORDER (owner ruling): the row's NAME says WHAT the item is —
that is what you are mapping. Last year's NUMBER is the quick way to
find WHERE the item lived (find the prior in the report, read across).
The ARITHMETIC (section sums, prior ties) is how a candidate is
ACCEPTED. Name to know it, number to find it, arithmetic to accept it.
A row BLANK last year with a printed value this year is a NEW LINE —
completely normal: map this year's number in by the row's name (a blank
prior locates nothing, so the name and the statement's structure carry
the mapping; the section equation still accepts it).

Candidate lines marked [prior-tie] matched this row by NUMBER (last
year's value appears in the line) — that is the reliable signal for
LOCATING. Lines marked [label-kin] matched only by words; read them
more skeptically: same words often mean a different scope (a note row,
a ratio, prose). A 同比/%-change line lets you compute this year's
value as current = prior x (1 + pct) — cite it as such.

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
- detailed reports often print important lines TWICE (the analysis
  section repeats the statements with YoY%) — when a second printing
  exists, an agreeing pair settles the value and one different reading
  never overrides it; when the document is short and prints a number
  only ONCE, that is normal — the section equation and the prior-column
  tie carry acceptance by themselves;
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

SHOW YOUR WORKING (mandatory): every write carries a "check" — the
three questions an analyst answers BEFORE accepting a number, answered
with numbers, not adjectives:
- "section": which printed subtotal does this line sit under (or
  "not a statement line" for drivers/operating data)?
- "sums": the section arithmetic WITH your value in place, digits shown
  (e.g. "5236.18+5569.62+0 = 10805.80 = printed subtotal"), or the
  partition/total tie for a breakdown row, or "n/a" with the reason;
- "prior_tie": what the line's comparative shows against the model's
  prior — "ties 110.02 exactly", "RE-BASED: prints 2854.08 vs model
  2955.37" (then the write must be flagged), or "new line — blank last
  year".
A write whose check you cannot fill honestly is not a write — it is a
flag or a not_disclosed. The check is your own acceptance test; the
machinery will also verify it, and a write that contradicts its own
check is worse than no write.

Respond with ONE JSON object:
{"writes": [{"cell": "Sheet!U49", "value": 123.45, "why": "p102: <the line>",
             "check": {"section": "经营活动现金流入小计", "sums": "123.45+... = <subtotal> = printed", "prior_tie": "ties 118.20 exactly"}},
            {"cell": "Sheet!U50", "swap_constant": {"old": 1234.56, "new": 1350.0}, "why": "p..: the constant is last year's <category> total; this year's counterpart",
             "check": {"section": "not a statement line", "sums": "n/a — category total swap", "prior_tie": "old constant found in prior report as the category total"}}],
 "need": [{"cell": "Sheet!U53", "looking_for": "segment revenue split"}],
 "not_disclosed": [{"cell": "Sheet!U50", "looked": ["statement", "notes", "five-year summary"]}],
 "flags": [{"cell": "Sheet!U51", "why": "two candidate scopes, p60 vs p154"}],
 "skips": ["Sheet!U52"]}

Your writes go through the guarded chokepoint; some may come back
rejected with a reason (wrong magnitude, breaks a passing check, cell is
evidence-tied). You will get one repair pass with those reasons —
rejections are information about the model, not noise.
