# REBUILD — the constitution (rewritten 2026-08-17, objectives rework)

**The governing objectives document is [BOSS_MINDMAP.md](BOSS_MINDMAP.md)**
(the owner's boss-approved mindmap + dated clarifications). This file turns
it into the working constitution. Where anything below conflicts with
BOSS_MINDMAP.md, the mindmap wins.

Everything before this rewrite (four-criteria law, delivery gate, champion/
challenger) is superseded — see **Dead doctrines** at the bottom. History
lives in RUNLOG.md and the git log.

---

## 1. Why the agent exists

The analyst uses the updated model to **forecast**: compare actuals against
their previous forecast, read growth trends, and re-project. The agent's
product is therefore:

- an **always-delivered**, balanced, trustworthy updated model, and
- a `_REPORT` tab showing, for the key numbers:
  (a) previous projection vs actual for the updated period, and
  (b) old vs new projection for the forecast years (how the forecast moved
  once actuals flowed through).

Re-projection is the analyst's job, never the agent's.

## 2. The design law: an agent, not a workflow

This is a **generic agent for the whole organisation**. It works the way
Fable 5 works on this task free-form:

- **One objective, one thinking loop.** The agent understands the task,
  then deploys whatever tools it sees fit, in whatever order the situation
  demands. There is NO fixed call-graph of scripted stages — that was the
  failed legacy design.
- **We provide the toolset; the agent provides the thinking.** Deterministic
  machinery gathers evidence, checks what is checkable, and constrains what
  may be written. It never invents a number and never decides the plan.
- **Generic, zero per-company code.** Every analyst's model differs in
  language, layout, style, industry. Mechanisms must be NUMBER-ANCHORED
  (prior-value triangulation, checksums, scale ratification), never label-
  or layout-bound. Per-company knowledge lives only in the workbook's own
  `_SPEC` tab and travels with the file. No onboarding: the first run
  discovers the model's anatomy itself and writes `_SPEC` for the next run.

## 3. What the agent must do

### 3.1 Understand the model first (modelling is an Art)

Before touching anything, the agent reasons out:
- forecast periodicity (quarterly / half-yearly / annual);
- which sheets are forecast sheets (P&L / BS / CF / drivers);
- **which column/year to update** — inferred from the model itself (e.g.
  hardcode density says 2024 is done, so 2025 is the target; Q1-Q4-FY
  layouts resolved the same way);
- which breakdowns are per-period forecast inputs vs reference-only.

### 3.2 The restatement stop (the ONE human-in-the-loop pause)

Detect restatements early (new doc's comparatives vs model history). On
detection: **pause completely** and ask the analyst for (a) the prior
financial report, (b) restate the model yes/no — warning that restating
financials may break reconciliation with unrestated operational data.
- **Yes** → restate history, continue.
- **No** → the analyst's method: use the UNRESTATED prior report to locate
  which section/table each model line is sourced from, map to the matching
  section of the new report, take current-period values from there, and
  flag the mismatched comparatives.
The pause is a **resume**, not a rerun — work already proven is kept.

### 3.3 Required output

1. **The model balances.** All three statements reconcile, every period —
   historical, updated, and forecast (quarterly/half-yearly/annual alike).
   If updating the actual year breaks a forecast year, the agent traces and
   fixes the error — which may include editing forecast columns, but ONLY
   to restore integrity, never to change the forecast view.
2. **Key numbers correct**: sales, segment breakdown, gross profit (and its
   breakdown), net profit, cash balance, current/non-current assets and
   liabilities, equity, CFO / CFI / CFF.
3. **Key drivers correct**: the hardcodes (including constants embedded in
   formulas) that feed the key numbers — identified by the agent, marked to
   actual for the reported period, untouched for forecast years.
4. **Analyst adjustments honored**: infer the adjustment logic from the
   model itself (how the prior actual column adjusts reported figures),
   replicate it on the new actuals, flag if the inference is uncertain.
5. **The column convention**: the new actual column is the prior actual
   column carried forward — same formulas (Excel-shifted), same formats,
   same cell types — with only inputs updated. The analyst finds everything
   where they left it.

### 3.4 Delivery: always

**Refusal does not exist.** The escalation ladder for every problem:

1. find the correct number (evidence-cited);
2. reason and fix — e.g. an unbalanced BS means trace the statements, find
   the cause, repair it;
3. after a few failed iterations: **back out / plug, flagged** — a plug to
   balance, or a back-out so a =SUM equals the disclosed figure — and
   still deliver.

Flags mean "look here" and nothing else:
- flags ONLY on uncertain/derived numbers (house colors: FFC7CE uncertain,
  FFC000 backed-out);
- non-key cells genuinely not disclosed this period stay stale with NO cell
  flag — one `_REPORT` line ("not updated this period");
- **"not disclosed" must be PROVEN, not asserted** — the agent shows where
  it searched before claiming non-disclosure. "Couldn't find" ≠ "not
  disclosed"; lazily conflating them is a known past disease.

## 4. The Police

A verification presence with four laws:

1. company-announced data updated correctly per the released statements;
2. analyst-adjusted numbers updated per the previous adjustments' logic;
3. the model balances (all periods);
4. the key numbers verified correct.

The Police **sends the agent back to fix** what it finds — it never merely
reports, and it never refuses delivery. After a few iterations without a
root-cause fix, the agent takes the flagged back-out/plug exit (3.4).

Structure (open design decision): deterministic checks + independent
fresh-context review. Engine: **Luna for both updater and Police**; if
Luna-as-reviewer underperforms, fall back to Luna updates + Tera reviews.

## 5. Measurement

A run is judged on, in order:

1. **the 4 Police laws — all pass** (pass/fail);
2. **fewest backed-out/flagged cells** (tiebreaker — fewer = better);
3. **≤60 minutes** (a ceiling, not a target; accuracy wins).

**Completion % is dead** — cells are not equally important; the keys and
segment breakdowns get the attention. There is **no champion**: stable-run105
is retired, not re-scored. We start new.

## 6. The toolset (evidence-based rulings — see TOOLSET_AUDIT.md)

The full audit of 100+ runs' worth of legacy tooling is in
**[TOOLSET_AUDIT.md](TOOLSET_AUDIT.md)** — every ruling cites its run
evidence. Headline (the log's loudest lesson, council-confirmed): zero
errors ever came from checksummed reads; ~100% of failures came from
heuristic middle-layer writers. Therefore:

- **KEEP as tools**: checksummed page reader (0 wrong reads ever), the
  deterministic join (130/130), unit/scale doctrine, the ONE transactional
  write chokepoint, checksum-gated vision, anatomy discovery, residual
  fingerprinting (the reason-and-fix method), apply_diff, implied-prior
  tie-out, cash-tie/statement-wins arbitration, museum + replay + dry runs,
  `_SPEC`/`_REPORT` writers.
- **DEAD**: all heuristic auto-writers (allocation, closing loop, tie-web
  plugs, reviewer auto-apply), the workflow state machine, extract-then-
  match as primary path, N-pass voting, the refusal gate + flag budget,
  completion scoring, unguarded warm-memory serving, label-first matching.
- **REBUILD**: the objective loop PROMOTED to be the whole agent from
  minute zero (stages become its tools); learner → lean hard-set discovery
  into `_SPEC`; digest-once adopted (the cold-run constraint died with the
  old benchmark); reviewer → the Police (findings go back to the agent —
  auto-apply stays dead); derive/back-out as the agent's deliberate flagged
  last resort.
- **BUILD NEW**: restatement pause/resume + cross-report section mapper,
  adjustment-logic inferrer, forecast-comparison _REPORT tables,
  non-disclosure proof log, forecast-integrity repair authority.

## 7. Validation discipline (survives unchanged)

- Museum tests green, always — every disease becomes an exhibit.
- Pinned snapshots + offline replay before any dispatch; dry runs (stubbed
  LLM) end-to-end on DFE and CLP.
- Every trial has an investigated root cause and a purposeful change —
  never rerun unchanged; revert on regression.
- Engine: pure gpt-5.6-luna (see §4 for the reviewer fallback).

## 8. Dead doctrines (do not resurrect)

- **Refusal / quarantine as an output** — the agent always delivers.
- **The 15% flag budget** — flags are routing, not a liability meter.
- **Completion-% scoring** (80/90/95 targets) — replaced by §5.
- **The champion/challenger law vs stable-run105** — champion retired.
- **Workflow-machine control flow** — the agent thinks; tools are hands.
- **Auto-restating history without asking** — restatement now pauses (3.2).
