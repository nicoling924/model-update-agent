# Objectives mindmap — 2026-08-17 rework session

**Central question: what should a model-update agent actually optimize for,
from the analyst's point of view?**

Status: BRAINSTORM IN PROGRESS. Nothing here is decided. Tensions marked ⚡.

```
WHAT SHOULD THE AGENT OPTIMIZE FOR (analyst's POV)?
│
├── 1. DONE-NESS — what does "finished" mean?
│   ├── deliver-with-flags vs refuse-until-proven
│   ├── ⚡ current gate: refusal is treated as the SAFE output
│   │     … but a refusal delivers ZERO value; a flagged hole delivers most
│   ├── is delivery binary at all? (deliver the proven subset + honest map
│   │     of the unproven remainder = maybe the only real output)
│   └── Q: what does the analyst ACTUALLY do when the gate refuses?
│
├── 2. THE FLAG BUDGET
│   ├── 15% bar: where did it come from? what harm does 16% cause?
│   ├── ⚡ Driver/MD&A sheets at 24-26% are the standing refusal cause
│   ├── do driver/stats sheets deserve the statements' bar at all?
│   ├── what a flag MEANS to the Monday-morning analyst:
│   │     "look here" (good, saves time) vs "agent failed here" (noise)
│   └── flags as budget vs flags as ROUTING (which cells, not how many)
│
├── 3. ACCURACY TIERS — which cells must be right?
│   ├── Tier A: keys (10-15 numbers) + balance identities → correct or die
│   ├── Tier B: statement faces → correct-or-flagged
│   ├── Tier C: driver/stats/MD&A detail → may stay stale IF marked stale?
│   ├── ⚡ current scoring (% of all cells vs reference) weights a Driver
│   │     stat row the same as net profit
│   └── Q: is "stale but labeled stale" an error at all?
│
├── 4. THE LOOP'S AUTHORITY
│   ├── what Luna may do alone: joins with proof, apply_diff with citation
│   ├── ⚡ the analyst's own endgame moves (plug the 59, re-anchor) are
│   │     currently forbidden — the human champion USES those moves
│   ├── authority tiers: free / allowed-with-orange-flag / surface-only
│   └── definition calls (core profit etc.): agent picks + flags, or asks?
│
├── 5. TIME / COST + WHAT A CHAMPION IS MEASURED ON
│   ├── ≤60 min ceiling (not target); accuracy wins
│   ├── ⚡ champion metric: % vs a "reference" that is itself an agent run
│   ├── should the champion metric be analyst-minutes-saved instead?
│   └── cold vs warm runs: which one is the product?
│
├── 6. DEPARTMENT ROLLOUT (20 analysts, 20 models)
│   ├── genericity proven (DFE + CLP, zero per-company code)
│   ├── ⚡ objectives tuned on 2 models may not transfer
│   ├── per-analyst tolerance for flags/refusals will differ
│   └── who reads the _REPORT tab? does anyone?
│
├── 7. [Claude] FAILURE ASYMMETRY — the real loss function
│   ├── cost(wrong unflagged number that reaches a note) = catastrophic
│   ├── cost(flagged hole) = minutes of analyst review
│   ├── cost(refusal) = the whole run's value + trust in the tool
│   ├── ⚡ the current gate prices refusal at ~0; the analyst prices it high
│   └── candidate objective: NEVER wrong-unflagged; everything else is
│         degrees of useful
│
├── 8. [Claude] REVIEW ECONOMICS — the analyst's time is the currency
│   ├── the product is not a correct model, it is a REVIEWABLE model
│   ├── optimize: minutes-to-verify, not just %-correct
│   ├── a flag that routes attention SAVES time; 80 undifferentiated
│   │     stale flags COST time
│   └── Q: how long does the analyst spend reviewing a delivered run today?
│
└── 9. [Claude] GROUND TRUTH & LEARNING
    ├── ⚡ scoring vs a prior-agent-run "reference" — RUNLOG shows the
    │     filing sometimes supports the challenger (raw % understates)
    ├── what IS ground truth? (filing > reference)
    ├── warm-run compounding: is steady-state, not first-run, the product?
    └── does the champion/challenger law measure the right thing?
```

## Decisions log — MAP STABILIZED 2026-08-17

The map converged via the boss mindmap + grilling session. Rulings live in
**BOSS_MINDMAP.md** (governing, with dated clarifications) and are encoded
in **REBUILD.md** (the rewritten constitution). Headlines:

1. Done-ness → ALWAYS deliver; refusal dead; reason-and-fix, then flagged
   back-out/plug. One pause only: restatement (ask, then resume).
2. Flag budget → dead. Flags = "look here" routing on uncertain/derived
   cells only; proven non-disclosure stays stale, unflagged, one _REPORT line.
3. Accuracy tiers → keys + segment breakdowns + key drivers + adjustments
   must be right; completion % dead.
4. Loop authority → full reason-and-fix authority incl. forecast-column
   integrity repairs and flagged plugs; restatement needs the analyst.
5. Measurement → 4 Police laws pass/fail, fewest flags, ≤60 min ceiling.
   Champion retired; no re-scoring.
6. Rollout → generic, zero onboarding, self-discovery + _SPEC. Luna both
   roles (Tera reviewer fallback).
7-9. Failure asymmetry / review economics / ground truth → absorbed: the
   loss function is "never wrong-unflagged, refusal priced at full cost";
   the currency is analyst review minutes (flag quality); scoring vs the
   old agent-run "reference" abandoned with completion %.

This file is now historical; BOSS_MINDMAP.md + REBUILD.md govern.
