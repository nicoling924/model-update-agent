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

LOOK ELSEWHERE (the analyst's skill): the same economics print in
several places — the statement face, the SEGMENT NOTE behind the
statements, other MD&A tables, the five-year summary. If the tables in
front of you lack a row you believe is disclosed, do not guess and do
not give up — ASK for more places with "need". You will receive
additional tables and lines for those rows from elsewhere in the
document. Claim not_disclosed only after the other places came back
empty too.

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
