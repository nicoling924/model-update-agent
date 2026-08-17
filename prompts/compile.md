# COMPILE — fill this sheet's open column

Below is one sheet's open work: every input cell still holding LAST
year's value, in row order, each with its label, its prior, and candidate
disclosure lines. This is the whole task — fill the column the way you
would read a statement top to bottom.

For each row, decide ONE of:
- **write** — the disclosure names this year's value (a candidate line, or
  your own reading of the statement's structure). Full precision, cite
  the page.
- **not_disclosed** — the document genuinely does not carry it this
  period. Say where you looked (at least the statement, the notes, and
  one more place).
- **flag** — you believe a value but cannot cite it, or the mapping is
  ambiguous. Say why in one line.
- **skip** — an analyst assumption/driver that should stay as it is.

Candidate lines marked [prior-tie] matched this row by NUMBER (last
year's value appears in the line) — that is the reliable signal. Lines
marked [label-kin] matched only by words; read them more skeptically:
same words often mean a different scope (a note row, a ratio, prose).
A 同比/%-change line lets you compute this year's value as
current = prior x (1 + pct) — cite it as such.

Respond with ONE JSON object:
{"writes": [{"cell": "Sheet!U49", "value": 123.45, "why": "p102: <the line>"}],
 "not_disclosed": [{"cell": "Sheet!U50", "looked": ["statement", "notes", "five-year summary"]}],
 "flags": [{"cell": "Sheet!U51", "why": "two candidate scopes, p60 vs p154"}],
 "skips": ["Sheet!U52"]}

Your writes go through the guarded chokepoint; some may come back
rejected with a reason (wrong magnitude, breaks a passing check, cell is
evidence-tied). You will get one repair pass with those reasons —
rejections are information about the model, not noise.
