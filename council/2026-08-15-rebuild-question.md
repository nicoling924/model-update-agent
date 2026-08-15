# Council question: rebuild from scratch, or evolve — an agent that must match Claude Fable 5's model-update output using a weaker engine

## The commissioning goal (restated by the owner today)

Build an agent that updates equity-research Excel valuation models (mark to
actual from PDF disclosures, roll forward) with the same OUTPUT quality as
Claude Fable 5 doing the task interactively. Acceptance, in strict priority
order:

1. **Balance sheet balances for ALL years** (actuals + forecasts). Non-negotiable.
2. **The 10–15 key numbers** an analyst checks (sales, gross/operating/net
   profit, cash, CA/CL/NCA/NCL, equity, CFO/CFI/CFF, key breakdowns) — near
   non-negotiable even when other cells are incomplete.
3. **≥90% whole-model completeness** (cells correct vs a reference update).
4. **≤60 minutes per run** (a ceiling, not a target; accuracy wins).

Philosophy: the owner believes Fable 5 wins not only on raw LLM strength but
on its built-in agentic scaffolding — skills, subagents, tool discipline,
self-verification. The goal is to package that scaffolding around a weaker,
mandated engine (gpt-5.6-luna, OpenAI-compatible API; a stronger model allowed
ONLY as a blind reviewer) so it deploys inside a bank (UBS) environment.

Hard constraints:
- **Only widely available Python libraries** (openpyxl, pdfplumber, requests,
  pandas, PIL class). No niche or private third-party vendors, no exotic
  system binaries a locked-down bank image won't have. The LLM endpoint is the
  one external service. (Bears directly on OCR: the engine's own vision needs
  zero new dependencies; tesseract/paddleocr are extra deps of uncertain
  availability inside a bank.)
- **Generic across teams**: vastly different model structures (multi-sheet
  link-through models, Chinese-language source sheets, Excel data tables,
  manual calc modes). No per-company code; a learned per-company memory tab
  inside the workbook is allowed.

## What exists today (candidate for demolition)

~5,900 lines of Python (21 modules) + 9 prompt files, built over ~100
benchmarked runs:

- Deterministic pipeline: archive/snapshot -> whole-column rollover ->
  retrieval (find each model row's disclosure pages by Ctrl+F on its known
  prior-year value) -> holistic per-block LLM mapping (text pages + row list
  -> values) -> code audit of every answer (citation, magnitude, unit scale)
  -> flagged writes (red=uncertain, orange=derived) -> tie-web/objective
  convergence (subtotal anchors, learned bridges, identity solves) -> bounded
  agent loop (150 decisions, tools: trace/diagnose/remap/read_pages/set_input,
  objective scorecard re-shown every turn, guarded transactional writes that
  auto-revert on regression) -> integrity gate (refuses delivery on structural
  damage) -> report tab -> independent adversarial reviewer.
- A learner command: calibrates on the PRIOR year (where the model already
  holds answers), stores code-verified row->line identities, component
  recipes, and quirks in a hidden memory tab; the cold run then uses only
  model + memory tab + the new period's PDFs.
- Measured, company 1 (CLP, vs the analyst's finished model): 74–76% cells,
  keys 8–9/12, balance passes most runs, 27–35 min, ~$2/run.
- Measured, company 2 (Dongfang, vs a Claude Fable 5 reference update): 79.1%
  first scored run, 34.5 min — but balance FAILED. Root cause: pages 95–106
  of the annual report (the entire audited statements block) are image-only
  scans; the pipeline is TEXT-ONLY (pdfplumber), so the agent literally could
  not read the balance sheet. It correctly diagnosed its own gap ("total
  assets understated by 15,199") and burned 63 agent-loop decisions re-reading
  pages that contain no text. Known bug: the loop's set_input refuses
  formula-cell writes instead of redirecting to the input cell that feeds
  them (the resolver exists), so those 63 decisions produced zero writes.
- Evidence cuts BOTH ways on architecture:
  (a) an earlier extract-then-match pipeline scored WORSE than raw chat-app
  usage of the same model class (73.3% vs 82.5% on identical rows) and was
  deleted for a direct-mapping design (+6pp, 6x faster) — the harness CAN
  throttle the model;
  (b) an unconstrained weak model takes any exit it's offered — before code
  held the goal (finish refused while objectives unmet), runs exited early
  with balance broken — the model CANNOT hold the goal alone.

## Questions, in priority order

**Q1 — REBUILD OR EVOLVE.** Given the goals and the state, would you demolish
and rebuild from scratch — and if so, to WHAT architecture, concretely? Or
evolve the current system, and in what order? The owner has explicitly
authorized starting over. Give a verdict and the first two weeks of work.

**Q2 — THE AGENT PACKAGE.** If the philosophy is "give Luna the Fable 5
scaffolding": which specific agentic mechanisms (subagents, skills, vision,
self-verification loops, external memory) actually transfer to a weaker
engine, and which are known to fail on weaker engines (wandering, hallucinated
tool results, unproductive loops)? Be specific about what the DETERMINISTIC
layer must own vs what the model owns.

**Q3 — VISION.** The engine is multimodal but the harness has never sent it
pixels. For scanned Chinese financial statements where digits must be exact:
how exactly should page images enter the pipeline (rendering, resolution,
tiling, prompting), and how should transcription be VERIFIED? Note the harness
already KNOWS the prior-year column of every statement — the comparative
column of a scanned balance sheet must reproduce ~40 known numbers, which
looks like a built-in checksum. Is that sufficient, with row-sum/合计
arithmetic ties on top? Should vision also replace text extraction on pages
that HAVE a text layer (text extraction loses column alignment — measured
"right sum, wrong column split" errors), or stay a targeted fallback?

**Q4 — LEVERAGE RANKING.** Rank your concrete changes by expected gain toward
the four acceptance tiers. Flag anything you predict the other council members
will get wrong.

## Required output

Verdict (rebuild vs evolve) + ranked plan + implementation sketches + failure
modes + what deterministic code must verify. Be concrete; no surveys.
