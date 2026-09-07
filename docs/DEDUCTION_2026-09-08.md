# Deduction pass — 2026-09-08: why the agent could not map what the report printed

Owner's question: "we are trying to identify what happened fundamentally … point one and
point two hindered the operation of the whole agent … fix the underlying problem to make the
agent generic and meet the key objective in BOSS_MINDMAP.md."

BOSS_MINDMAP objectives this serves: §Key required output 1 (three statements reconcile) and
2 (key numbers updated correctly, found by reasoning not by name), §A (understand the model
structure — modelling is an art), and the 2026-08-17 clarification "every fix must be generic
and fix the underlying fundamental — never just patch".

## 1 · The two fundamentals

**F1 — Location rules were used as admission, not priority.** The evidence test the agent
runs on a printed line is sound and generic: tie last year's number at the model's own
precision, confirm the label, read this year's; a blank beside the tie is 0; a subtotal must
reconcile. Around that test, 57 code sites (inventory below) decide WHERE the test may run:
statement-face pages only, tagged pages only, prior-vintage documents never read, lines with
more than three numbers never a statement line, tables longer than 80 lines skipped, at most
4 candidates per card, 60 serve cards, 60 brain calls. Every one of these was added after a
specific misfire. Every one of them hides a class of real evidence from BOTH code and brain.
On run 254 alone: the investment line printed on the summary table (p20) was invisible; the
dividend's noun proof in last year's report was banned; the order-intake card was drained by
the call cap; the bond line's 0 was refused by a tag rule.

The fundamental error is architectural, not any one rule: safety was placed on LOCATION
(where the agent may look) instead of on EVIDENCE (what a line must prove). Location cannot
be a generic safety, because every company prints the same figure in different places.

**F2 — One reading of a page is trusted with no corroboration.** Stage 1 reads a scanned page
by vision with a multi-pass consensus PER PAGE (rows must agree digit-for-digit across passes;
otherwise the row is "disputed" and never joinable). There is no corroboration ACROSS
appearances: the same figure is printed on the statement face, in the summary table, in the
five-year data and in a note, and the agent never uses one appearance to repair or confirm
another. On run 254 the vision read of the cash-flow statement dropped one column on one line;
the line then had one number, tied nothing, and the row was held at growth and later plugged
by 14,601 — while p20 printed the line with both numbers. F1 hid p20; F2 trusted the single
bad read. A chat model reading the whole PDF would have seen both.

## 2 · Inventory of location gates (57 sites, grouped) and their disposition

| Gate | Where | What it hides | Disposition |
|---|---|---|---|
| Statement faces only (`JOIN_FACES`, `.faces.get(...) in ("pl","bs","cf")`) | ledger.join_pool, reconcile (fixed today: faces FIRST, then all pages), stage2_join ×2, composites ×3, docid ×3, stage3_read | every summary table, five-year table, note, segment table | **Demote to priority.** A face claims first; every current-document page is walked. Same evidence test everywhere. |
| Face/tag required by the nil check (`stmt_face`, `face_pages`) | writegate.nil_current_zero (removed today), run.py sweep args, orchestrator verifier (fixed today) | a blank-beside-prior on any non-face page | **Removed.** The tie at full precision + significant digits + label kinship IS the safety. |
| Prior-vintage documents banned from READING (`_vintage_ban`, `noncurrent_docs`) | 14 sites | last year's report as the tie for prose nouns, restated comparatives, segment definitions | **Split the ban.** Never a SOURCE of a current-year number (keep); always readable for TIES (nouns, priors, definitions). Prose branch fixed today; table/segment branches still banned. |
| Wide row is not a statement line (`WIDE_ROW=4`, `is_statement_line`) | reconcile | summary tables with current / prior / growth %, five-year tables | **Replace with the pair test.** Any adjacent (current, prior) pair whose prior ties is evidence; extra columns are context. The "small-prior needs kinship" law already guards coincidences. |
| Table longer than 80 lines skipped (`max_lines_per_table`) | reconcile | long note tables (related parties, subsidiaries) | **Remove.** Cost is only time; the deadline is the budget. |
| Candidate caps (`MAX_CANDS` 4 / 6) | workqueue, stage2_join | the 5th appearance of a figure; a card whose right answer is candidate 5 | **Remove from the card; keep the join's "more than N agreeing printings is noise" only as a warning.** |
| Serve cap 60 / call cap 60 / reserved share | workqueue (removed today) | every smaller row once the big ones are asked | **Removed.** Time is the budget. |
| Joinable = at least two numbers (`joinable()`) | ledger, 6 call sites | any line whose comparative was lost by the read, any line new this year | **Keep for the JOIN, add the single-number paths:** blank-beside-tie → 0 (exists); exact label + blank prior → new line (added today); single number + another appearance carrying the pair → corroborated (F2, below). |
| Small prior needs kinship (`SMALL_PRIOR=50`) | reconcile | nothing real | **Keep.** This is an evidence rule, not a location rule. |
| Parent pages evicted (`parent_pages`) | docid, stage1, stage3 | the parent-company statements | **Keep as priority only** (consolidated first); never as a ban — the model may hold a parent line. |

## 3 · The generic principle to replace F1

For every model row, every printed line in every current-document page is a candidate, and
the SAME evidence test decides, in order: (1) the prior ties at the model's own precision →
the current is the value; (2) the label is exact or kin → confirms (1), or, with no prior to
tie, is the proof for a new line (red); (3) a blank beside the tie → 0; (4) the subtotal
reconciles → accepted, else the walk is wrong, fix it there. Location only ORDERS the
candidates (statement first, then summary tables, then notes) so that the first claim comes
from the statement when it exists. Prior-vintage documents feed step (1) and (2) with priors
and nouns but never supply a current-year value. The brain judges meaning where the test is
ambiguous (two readings, a changed name, a prose noun); code verifies numbers.

## 4 · The generic principle to replace F2 — corroboration across appearances

Every figure is printed more than once. Treat each appearance as a vote on the (current,
prior) pair for that line:
- A line read with one number on the face, and the same label read with two numbers on the
  summary table whose prior ties the model → the pair is corroborated; the face read is
  repaired, not trusted or discarded.
- A "disputed" vision row (passes disagree) becomes usable when another appearance agrees
  digit-for-digit with one of the passes.
- Two appearances that DISAGREE on the current value with the same tying prior → the brain's
  two-readings card (exists) — never a silent pick.
Implementation: one index over the whole ledger keyed by normalised label and by tying prior;
the walk consults it before serving; stage-1 consensus stays per page (it is cheap and
right), corroboration is a second, cross-page pass. No page types, no tags.

## 5 · Execution plan (each step: museum pin → bench → floors → readiness → commit; no live run
without the owner's go)

1. DONE today: walk reads all pages faces-first; nil check has no page rule; verifier judges
   the card's evidence; prose noun tie via last year's report; new-line serve by exact label
   (excluding numbers that tie any prior); forecast checks never veto an actual; no serve/call
   caps; key panel by prior tie; code-owned key count; replays carry key rows and do not pin
   card answers; readiness tool.
2. DONE (owner's go, same night): `WIDE_ROW` and `max_lines_per_table` gone (wide rows: nearest
   earlier number of the prior's magnitude + label confirms); candidate caps gone; the vintage ban
   split — last year's report names a table item, never supplies a number. The remaining
   `noncurrent_docs` sites are all SOURCE uses (kept by design). Faces-only in stage2_join /
   composites / docid stays as priority for now (the walk covers every page).
3. DONE (first cut): `Ledger.corroborate` rescues disputed vision rows by a second printing;
   the whole-report walk repairs a lost column through the other printing; disagreeing printings
   are red with both readings (the card lists both). A fuller per-figure index remains open.
4. Prove on DFE FY25 (run-254 ledger) and 1H25, and on CLP FY25 (genericity), offline first.

## 6 · What this does NOT change
The forecast inviolability laws, the roll-base least-confident back-out, the plug ladder, the
restatement full-stop, the flag colours, the reviewer pass. Those are objective laws; the
gates above were tooling.
