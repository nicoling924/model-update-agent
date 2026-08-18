# Design question: generic model-anatomy discovery (the CLP campaign)

## Context

Our extraction-first model-update agent now meets the bar on its
calibration company (DFE, a CN-GAAP scanned filing + a CN-structured
workbook): 10/10 headline keys at print, balance passing, every previous
mistake class deterministically closed or taught. The owner's mandate:
prove GENERICITY on a second company (CLP — an English HK-IFRS filing
and a very different workbook anatomy), with the explicit warning that
per-company code is forbidden (the "100 failed runs" died of it) and
teaching-the-LLM is preferred over deterministic wraps, with
arithmetic-checking referees ratified as legal.

Offline diagnosis of CLP BEFORE any live run found (all evidence-backed):

1. **Key-row discovery is the choke point.** The workbook has no spec'd
   key rows; auto-discovery found only TWO (vs DFE's 20), and one is a
   country sub-row ("Aus!23 operating profit"), while "revenue" was
   bound to a row whose prior does NOT tie the disclosure's printed
   prior — a mismapped key. Everything downstream starves: the printed-
   key gate has nothing to pin, Police law 4 has no teeth, the oracle
   proves nothing. Discovery works by English label matching on row
   captions + a cross-sheet prior-consistency filter.
   The CLP workbook anatomy: statements on a sheet named "Final",
   country/segment sheets (SOC, HK Sales, Aus, India, SEA...), drivers
   on "Driver". Units HK$M (the filing ALSO prints HK$M — scale 1).
2. **Face tagging over-matches on English reports**: 78 pages tagged as
   statement faces across 3 documents (a real AR has ~6-10 face pages
   incl. continuations). CJK reports tag by caption lines; English
   captions ("Consolidated Statement of ...") appear in notes and
   cross-references too.
3. The extraction itself is CLEAN on CLP (text-native English PDF): the
   P&L rows come through perfectly with note-refs interleaved. Closure
   grammar has been made bilingual already. So reading is NOT the
   problem — binding the MODEL to the filing is.
4. The announcement has NO cash-flow statement (CF only in the AR) —
   the incomplete-announcement class is exercised too, but that
   machinery exists.

## The question

How should MODEL-ANATOMY DISCOVERY work so it is genuinely generic —
one mechanism that finds the key rows (revenue, NP, EPS, cash, CA/NCA/
CL/NCL, equity, CFO/CFI/CFF, segment blocks) in ANY analyst's workbook,
CJK or English, single-statement-sheet or multi-sheet anatomy — without
per-company code?

Constraints and assets:
- The workbook itself is rich: labels, YEARS of prior actuals, formulas
  (checks like Assets=L+E exist as rows), sheet names/roles (a spec may
  declare sheet roles but never key rows).
- The disclosure's printed figures are known-good anchors: the model's
  prior-year actuals MUST equal the filing's comparatives for the same
  concepts (the fablemode identity we already exploit row-wise).
- An LLM engine (gpt-5.6-luna) is available at discovery time; the
  owner PREFERS teaching/LLM-reasoning over deterministic heuristics,
  with deterministic verification as the referee.
- A wrong key binding is worse than a missing one (it mis-aims the
  Police and the gate) — bindings must be VERIFIED, not plausible.

Specific sub-questions:
1. Is the right design "the LLM reads the workbook and nominates the
   key rows, code verifies each nomination by the prior-identity tie
   against the filing" (nominate-then-verify)? What are its failure
   modes?
2. How should the CONSOLIDATED row be told apart from subsidiary/
   country/segment twins of the same concept (the Aus-operating-profit
   trap) — is prior-identity against the CONSOLIDATED filing statement
   sufficient given segment rows can coincide?
3. Face over-tagging: what is the generic page-level test for "this IS
   the statement face" in any language (our closure/articulation
   machinery can score pages by arithmetic; captions clearly cannot be
   trusted alone)?
4. Should discovery be a ONE-TIME onboarding artifact persisted to the
   workbook's _SPEC tab (the owner accepts no per-model onboarding by
   HUMANS, but a self-onboarding first run is fine), and what must be
   re-verified on every run vs trusted from _SPEC?

Answer concretely; the measure is a design that binds CLP's 10+ keys
correctly tonight without touching a line of CLP-specific code, and
binds the next unseen company equally well.
