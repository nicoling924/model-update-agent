# Handoff brief — Model Update Agent (read this first)

Fresh-session brief, current as of run 99 (2026-08-16 overnight). Repo:
`/Users/lingling/Project M/model-update-agent`, branch `objective-driven`,
GitHub `nicoling924/model-update-agent`. Detailed history: RUNLOG.md (append
per run). Design verdicts: council/ (2026-08-15 rebuild-vs-evolve: EVOLVE).

## 1. What this is

An agent that marks equity-research valuation models to actual results from
disclosures, one pass, engine locked to **pure gpt-5.6-luna** (stronger models
only as blind reviewer). Two commands: `learn <dir> <prior_period>` (practice
year -> hidden `_UPDATE_MAP` memory tab) and `update <dir> <period>` (cold run:
model + memory + new PDFs only).

## 2. Acceptance (restated by owner 2026-08-16, strict order)

1. Balance, ALL years — non-negotiable.
2. The 10–15 key numbers — 100%, near non-negotiable.
3. **>=90% whole-model completion** (Model AND Driver pages explicitly).
4. <=60 min (ceiling, not target).

Constraints: widely available Python libs only (no tesseract/poppler — bank
image), generic across teams (no per-company code; per-company memory tab OK).
**Deadline: management presentation ~Mon 2026-08-17.** DFE first, then CLP
genericity check. On plateau or major decisions: convene the council
(`~/.claude/skills/llm-council`, reads the repo .env key).

## 3. State (see RUNLOG for full table)

- **CLP**: 74–76% vs analyst GT, keys 8–9/12, balance passes most draws.
- **DFE**: run 97 = 79.1% (273-cell reference = `companies/Dongfang Electric/
  model/Dongfang Electric Claude Fable 5.xlsx` in Project M — a Fable 5 run,
  not analyst-verified, so score with `--docs` adjudication). Run 98 = 63.0%
  (regression, autopsied). Run 99 in flight = audit-web fixes only.
- Score: `python tools/score_run.py "<artifact>/model/DFE Model.xlsx" --company
  DFE --docs companies/DFE/disclosures/FY25` (per-sheet breakdown included).

## 4. What was built on 08-15/16 (the vision + units arc)

- **Eyes** (`agent/vision.py`): DFE statements pp95–106 are SCANS (MRC: 1-bit
  CCITT text mask over background JPEG — the mask carries the text). The SAME
  Luna engine transcribes them (pdfplumber+PIL XObject extraction, zero new
  deps); gate = **prior-column anchors >=4** (measured: real consolidated pages
  17–29, 母公司/equity pages 0–2 — do NOT relax this with block corroboration;
  that caused run 98's parent-page poisoning) + anti-copy. Accepted rows inject
  as ordinary raw lines; cache in .cache/vision (transcriptions, not verdicts).
  Vision client needs 8k output tokens (3k truncated JSON = lost pages).
- **Hands**: orchestrator set_input auto-redirects view/formula cells to the
  typed input site (resolve_input_site); structured MISS otherwise; pages
  exhaust after 2 reads.
- **Units**: document scale detected once per run (mapper.detect_scale) and
  threaded through EVERY comparison via mapper.to_model_units / line_has_value
  — staging items, prove corroboration, ctrlf_read, constants fallback,
  compositions, bridges, replay, learner constructions. Scale 1 = identity
  (CLP untouched).
- **Audit web sight**: CN synonyms in objectives.KEY_KINDS (+CJK-preserving
  _norm), statement locality by densest anchor cluster, thin-proof keys get
  sibling corrections (never plugs). Offline replay of run-98 evidence: 11/11
  keys prove at exact disclosed values.
- **Alignment prompts** (owner directive): system.md = analyst identity;
  orchestrator.md = the subtotal repair pattern (trace -> guilty components ->
  set_input at input site -> sum re-ties); direct_map.md = objectives + scope
  discipline (合并 never 母公司).

## 5. Known remaining DFE wrongness (classified, from runs 97/98)

(a) 亿-suffix MD&A numbers (Driver!J83 = 734.76亿 -> 73,476): unit-suffix
conversion, unsolved. (b) Analyst-DERIVED embedded ratios/constants
(Driver!J155 `=J162*67.33%`, Driver!12 with restated comparative): learner
composition territory, hard tail — flag, don't chase. (c) Segment-note scope
(total vs external revenue). (d) Carry class — mapper conservatism.

## 6. How to operate

- Dispatch: `sh dispatch.sh DFE FY25 FY24` (GitHub Actions only; token comes
  from the git credential helper — persists across sessions).
- **Dry-run first, always**: `python tools/dry_run.py DFE FY25 FY24` (stubbed
  LLM, throwaway copy; catches binding-order bugs). Use the Project M venv:
  `"/Users/lingling/Project M/.venv/bin/python"`.
- Vision smoke tests hit the live engine for cents — cache under
  .cache/vision-smoke keeps them reusable; NEVER let dry-run stubs write into
  .cache/vision (delete it after local dry-runs).
- One investigated change-set per run; revert regressions; RUNLOG every run.
- The live `companies/DFE/model/DFE Model.xlsx` must stay PRISTINE at dispatch
  (no _UPDATE_MAP/_REPORT tabs — CI checks out what is committed).
- Runs take 35–60 min (98/99 ran ~60–100 with vision retries; watch with a
  stall-aware persistent Monitor). GH job cap 180 min.

## 7. Hard-won lessons — do not relearn

- Execute, don't inspect: the dry run and the offline replay catch what
  reading cannot (binding order, unit boundaries, gate behavior).
- Measure before believing: the "CF pages only anchor 2-3" belief was a
  misread of parent pages; the real CF anchors 17. One measurement killed a
  wrong design.
- The units disease recurs wherever printed numbers meet model numbers — any
  new comparison must go through mapper.to_model_units.
- Never let a later stage overwrite objective work; silence is the enemy
  (always-flag); the harness holds the goal (finish refused while objectives
  unmet).
- Owner's plateau trick: DO the update yourself as Fable 5, record your own
  workflow, transplant it (memory: plateau-trick-be-fable-yourself).
