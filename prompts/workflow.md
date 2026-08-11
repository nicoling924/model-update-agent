# The update workflow (reference — executed BY THE HARNESS, in this order)

This file documents the pipeline for maintainers. The LLM sees only the step it is
asked to help with; the sequencing, budgets, and gates live in `agent/cli.py`.

1. **Setup** — archive the pre-update model to `model-archive/<NAME>_<period>_pre.xlsx`;
   snapshot the pre-update estimate column (needed later for actual-vs-estimate);
   snapshot the full formula map (clobber protection).
2. **Ingest** — extract page text from every disclosure PDF for the period (cached).
3. **Extract** — LLM fills a staging JSON: full P&L, BS, CF, segments, KPIs, and the
   comparative (prior-period) columns, with exact disclosure labels + page refs +
   units. Code validates arithmetic ties; one retry with quoted errors; hard stop if
   still invalid.
4. **Restatement scan** — code diffs staging comparatives against the model's stored
   prior-period column, statements AND segments. Mismatch beyond rounding =
   restatement: restate model history, log every cell. Also validate the prior
   column's own balance checks (prior hardcodes can be wrong).
5. **True-up check** — if flagged (orange) cells exist for this period from an earlier
   summary-disclosure run and this is the detailed report, replace them with actuals
   and clear flags.
6. **Map & build worklist** — for every input row in the target column, run the
   cascade ONCE (see prompts/mapping.md): direct find → prior-year triangulation →
   back-out rule → prior-year AR on demand → estimate + flag. Acceptance requires an
   arithmetic tie. Output: a deterministic worklist (row → value/formula/flag/note).
7. **Apply** — mark to actual per the recipe: copy prior actual column's formula
   pattern, cell TYPE, and format into the target column; overwrite only disclosed
   inputs; rewrite formulas embedding stale constants; back-outs as FORMULAS showing
   the computation; read back every write.
8. **Roll forward** — extend forecast periods by copying driver formulas exactly
   (never "improve" them); re-anchor roll-forward bases (NFA, debt, schedule endings)
   to actual closings; scan the first forecast column for one-off actual-year items
   that must not propagate (subject to per-company rulings in spec.yaml).
9. **Verify** — full recalc via the built-in evaluator; integrity checklist: BS
   balances every period, CF ties to BS cash, retained-earnings roll, segment sums,
   EPS vs disclosed, tie-out anchors exact, no error cells, formula-map diff clean
   outside the target column + logged restatements. Any failure blocks delivery.
10. **Report** — `_REPORT` first sheet (4 sections: red flags / orange back-outs /
    >50% big moves / core actual-vs-estimate, each row a clickable link + live value)
    plus `updates/<period>_update_report.md` with the tie-out table.
11. **Blind review** — fresh-context LLM (optionally a different model) receives ONLY
    the disclosures + updated + pre-update workbooks. It re-extracts and diffs.
    Findings go into the report classified genuine-error / needs-analyst-ruling /
    confirmed-OK. Incontrovertible fixes are applied (with read-back) at most twice;
    everything else stays surfaced, never silently fixed.
12. **Compound** — write resolved mappings, new quirks, restatements, and re-anchored
    bases back to spec.yaml / MODEL_SPEC.md so the next run inherits them.

**Results-announcement-only mode**: when only a summary announcement exists, the run
still completes: construct an indirect-method CF from BS deltas (flag the block),
hold prior-year ratios for missing splits plugged to disclosed totals (flag each),
and record methodology so the future detailed-report run can true up.
