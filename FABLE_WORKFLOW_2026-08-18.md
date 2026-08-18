# The Fable pass — run-28 wrong cells worked by hand, workflow retraced

Owner instruction: do the matching myself, retrace the steps, teach the
agent the REASONING ONLY — no company specifics, no page numbers. This
file is the traceability record (it cites the specific case); the
teachings extracted from it live in prompts/ and are fully generic.

## How each number was actually found (the retraced thinking)

### 1. The statement cells — I never "searched" for a number; I solved the section

For every suspect cash-flow cell I did the same thing first: took the
row's SECTION (the lines between two printed subtotals) and treated the
printed subtotal as an equation. That single move answered four cells:

- A line with ONE number where its peers have two: which column does the
  number belong to? Whichever column's subtotal CLOSES with it there.
  Absent from the current column = this year's value is ZERO (proven,
  not guessed). That settled two cells (one zero, one comparative), and
  a third the other way (the current column needed it).
- Two adjacent lines shared the SAME comparative value. That is not a
  coincidence to shrug at — it happens exactly when one line is an
  "of which" component that was 100% of its parent last year. The
  prefix (其中/of which/including) marks a COMPONENT, never a peer; the
  parent's value is the one the section equation demands. The
  prior-identity tie is ambiguous BY CONSTRUCTION here, so identity
  alone must never decide between a parent and its sub-line.
- Confirmation: the narrative section of the report REPRINTS the major
  statement lines (with comparatives and YoY%). Every number I accepted
  had two independent printings agreeing, or a closure proof plus one
  printing. One reading, however well cited, is not acceptance.

### 2. The model-vs-print delta — reconstruct the convention, or flag the equation

One statement row differs from print because the analyst carves a piece
into a sibling collector row. Method: compute the prior-year delta
(model row vs printed line), then try to reconstruct that delta as a sum
of printed prior-year lines. If it reconstructs, apply the same
composition to the current year. If it does not reconstruct from
anything printed, the split is the ANALYST'S convention — the honest
output is the joint constraint ("these two rows must sum to these
printed lines") written as a flag, never a forced allocation.

### 3. The segment block — the note's prior column is the re-base detector

I did NOT hunt for the model's category names. I found the disclosure's
OWN partition: the table whose 合计 ties the printed revenue total to
the cent. Then the decisive move: lay that table's PRIOR column against
the model's prior column, row by row. Three outcomes, three actions:
- prior ties EXACTLY -> the category's scope survived the re-base ->
  the current value is writable (one category passed this test, and the
  agent's write there was actually correct);
- prior close-but-off -> the scope was re-cut -> NOT writable at this
  row; it belongs with the block decision below;
- category names gone entirely / merged -> a BASIS CHANGE. A breakdown
  block is a partition: half-updating it (one merged-scope number into
  one narrow-scope row, siblings stale, derived rows =J6-J7-J8 going
  insane) destroys the whole block. The block-level answer is the
  owner's restatement rule: stale + RED flag on the unresolved members,
  with the disclosure's new partition (and its prior column) laid out
  in the report for the analyst's re-base decision.

### 4. The embedded constant — a formula literal is last year's disclosed figure

A driver formula contained a bare numeric literal. I searched the PRIOR
document for that exact value — it was a disclosed category total, and
the formula decodes as member = category_total − sibling. Then the
current document: the category no longer exists → the driver is
STRUCTURALLY OBSOLETE → flag, never silently roll the constant.
Generic: every numeric literal inside a driver formula is an
undeclared input; its value is its own search key in the prior filing;
what it turns out to BE tells you what to look for in the current one.

## What made the difference vs the agent (the meta-lesson)

I accepted nothing on a single local justification. Every write had to
survive a GLOBAL check that was already computable: the section
equation, the partition sum, the second printing, the prior-column
tie-out. The agent had every piece of evidence I used — including the
correct value three times in its own pool — and overrode it with one
locally-plausible read. Reconciliation is the acceptance test; label
matches and lone checksums are only leads.
