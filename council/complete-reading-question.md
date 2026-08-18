# Design question: is "complete-extraction-first" the right fundamental cut?

## Context

We are building a generic, objective-based agent (engine: gpt-5.6-luna) that
marks equity-research Excel models to actual results from PDF disclosures
(Chinese annual reports, often scanned). Hard requirements from the owner:
model balances every year; key numbers (sales + segment breakdown, GP +
breakdown, NP, cash, CA/NCA/CL/NCL, equity, CFO/CFI/CFF) must be CORRECT,
not just flagged; always deliver; never a wrong unflagged number; ≤60 min
per run. The agent must THINK like an analyst — no hardcoded workflows.

## The failure pattern we must escape

25 runs in. The architecture: deterministic evidence extraction feeds an
LLM agent that maps disclosure lines to model rows through guarded write
tools (writes need citations; identity checksums refuse unproven values;
zero wrong writes since guards landed). Balance now passes all years;
8-10/10 headline keys tie print. But EVERY run still fails on some rows
because the EVIDENCE POOL HAS HOLES, and each hole became its own bolt-on
channel across runs:

1. pdfplumber text lines (loses table columns)
2. "table islands" (grid rendering with headers)
3. vision transcription of scanned pages
4. "verified ingest" (whole-page LLM transcription, checksummed: a row is
   believed only if its comparative ties a model prior at identity grade)
5. "recovery mode" (vision-missed lines resurrected by prior-anchor)
6. "section closure" (subtotals as equations: proves single-number column
   placement → absent-line zeros; derives missing rows by difference)
7. "sightings" (note-page lines printing a model prior, surfaced to the
   agent because note pages are banned from machine writes after a junk
   note number once corrupted net profit)
8. "last-year map" (find the row's prior value in the PRIOR-year report,
   then walk to the current report's counterpart section by label overlap
   — handles re-based segment categories)

Each channel was born from one run's miss. The owner has now called this
what it is: a patch spiral. His directive: "if it's a fundamental issue,
fix it fundamentally."

## The proposed fundamental fix

Invert the architecture: the run's FIRST product is one complete,
column-resolved, verified transcription of the statements + relevant notes
(a canonical staging extraction), and mapping runs only against that
complete world. Completeness is PROVEN, not asserted:

- (a) every statement section closes against its printed subtotal
  (both columns);
- (b) every open model row's prior value is either LOCATED in the
  extraction or proven absent (searched pages enumerated);
- (c) pages failing (a) or (b) are re-read (better prompt, higher zoom,
  targeted) inside the run until the proof passes or the gap is
  explicitly recorded.

The existing channels stop being independent evidence sources and become
internal verification/repair steps of the ONE reading stage. Downstream,
the mapping agent gets a complete dataset, so "look elsewhere" becomes a
query over the extraction instead of a hope that the right snippet was
served.

Additionally: a pre-dispatch OFFLINE benchmark (we have the archived
documents + every historical failure class) — a head is dispatched only
when the full benchmark passes, so live runs stop being discovery tools.
Live runs cost the owner an hour each.

## Questions for the council

1. Is complete-extraction-first the right fundamental cut, or is the
   channel accumulation actually fine (convergent, not divergent) and the
   real fundamental issue elsewhere (e.g. in the mapping agent's task
   shape, or the guard design)?
2. What is the cleanest ARCHITECTURE for the one reading stage given a
   weak-ish engine (luna) that misreads scanned CN tables: how do we get
   whole-report completeness within ~30 min of runtime — page selection,
   per-page transcription with closure repair loops, what to do about
   notes (hundreds of pages, only some relevant)?
3. Completeness proof design: are (a)+(b) sufficient? What completeness
   claims can NOT be proven deterministically, and how should the run
   treat them honestly?
4. What are the failure modes of extraction-first (e.g. a wrong-but-
   internally-consistent extraction poisoning everything downstream), and
   what invariants prevent them?
5. Is the offline benchmark gate sound, or does it risk overfitting the
   agent to DFE's document quirks (the generic-agent requirement)?

Answer concretely. The measure of a good answer is a design we can build
once and stop patching.
