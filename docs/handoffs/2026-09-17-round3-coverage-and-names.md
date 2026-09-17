# Round 3 (2026-09-17) — what the live runs said, and what changed

Live diagnosis: CLP 35162933611, DFE 35162935661. Faces answered in 2-6 s each, and the run still shipped
55 plain cells with 217 of 319 rows "not reached" (CLP), 12 plain / 116 red (DFE). Five CLP cells were plain
AND WRONG — a number tie under an unrelated label. DFE's keys were wrong because the inputs beneath them were
never reached and still held last year's figure, with no flag on the key itself.

## The nine changes (one commit each, each with its museum exhibit)

| # | Commit | The rule |
|---|--------|----------|
| 1 | The name must be kin to the row | A plain write needs the number tie AND the quoted line naming something kin to the row — its own label, or its section heading where the label says nothing; at word stems; through the house glossary; and silently across scripts, where code cannot compare. |
| 2 | Every open row is a queue the turns walk | The open rows are a queue (unfilled before red, the model's own order); a turn takes as many as the room holds and shows each under the face it is read against; the cursor moves by exactly those rows; a settled cell is never offered again; a row no printed line points at is spread over the statement faces; a face call is bounded by size, not by a count; progress is a figure landing in a cell. |
| 3 | The sequential pass gets what is left of the clock | `sequential_budget(map_budget, faces_took)` — what the faces did not spend is still the mapping's (CLP threw away 21 of 33 minutes). |
| 4 | The face contexts are snapshots under one lock | Both the worker building a context and the main thread applying a batch take the same lock; a face still lost is said in the log and carried to the brain. |
| 5 | A key says how many of its inputs were never mapped | The whole formula tree under each key is walked; unfilled/red inputs are counted on the key. A row skipped with a reason is closed, not open. The flag keeps any note already on the cell. |
| 6 | A zero is a figure only where a nil is printed | A row that carried a figure last year and none now needs a printed nil, a blank beside the comparative, or stated arithmetic; nothing is written and the row stays open. A row whose prior is nil keeps its zero. |
| 7 | The plain write stands after it is downgraded to red | The last PLAIN write stands; later readings land red carrying both. |
| 8 | The four halves of the balance sheet are keys | current/non-current assets and liabilities, measured on the MODEL's own total row against the printed total — the case the balance check cannot see (perpetuals in the wrong half). |
| 9 | Stated arithmetic stands on printed figures | (the reviewer's catch on rule 1) every term of a stated sum must be a figure some page prints. |

## What the fresh-context reviewer caught, and what was done

Confirmed and fixed before the commits: the write-progress measure was read AFTER the turn's writes (so no write
ever counted) and then counted flags as writes (a re-flagged row could turn for ever); the queue was rotated but
the FACE section still drained the room first, so the same 54 rows were served every turn and 95 were never shown;
a per-face count of 40 dropped 79 of 319 rows; the cursor over-advanced; the zero rule blocked a legitimately nil
row and read `false` as zero; the lock covered only one side of the race; the key walk stopped at twelve inputs and
counted skipped rows as open; the kin check refused the house glossary's own synonyms and plurals.
Left as noted, not fixed: the four new key names can enlarge a model's key denominator (owner's ruling), and
`reportpage.resolve_rows` ranks nearness above name strength for every role (pre-existing).

## Evidence

- Bench green on every commit; museum 391 exhibits.
- Floors, all DELIVERED: CLP FY25 (keys 1/8, 372 red — baseline at 6285dbc: 1/8, 370 red), CLP live-shape
  (1/8, 373 red), DFE FY25 (3/11, 248 red), DFE 1H25 (254 red), CX cold (0/1, 183 red).
- Pace (CLP FY25, synthetic brain, 20 s/turn): 315 input rows resolved — 51 plain, 74 red, 176 skipped with a
  reason, **14 not reached** (live before: 217 of 319). 140 turns, 54 simulated minutes against a 36-minute bar:
  coverage is solved, the per-turn cost is not — the clock still bounds a live run, and the rows it does not
  reach go red.
