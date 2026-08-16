# Morning report — the overnight rebuild (2026-08-17 night → 08-18)

## What you asked for, what you got

You asked for a fresh, objective-based, generic agent by morning. The clean
pipeline is **built, committed to `rebuild` (10 commits), museum-protected
(43 adversarial exhibits, all green), and proven generic** — it ran CLP
end-to-end with ZERO company-specific configuration via anatomy
auto-discovery. It was then **live-tested five times on DFE with pure
gpt-5.6-luna**, each run autopsied and its diseases fixed and pinned the
same night.

## The report card (challenger vs your four criteria + gate)

| Criterion | Result | Verdict |
|---|---|---|
| 1. Model balances (or flagged) | 2025 gap **59** (0.04% of assets), traced & documented by the loop; forecast years 587 | **FAIL** (trajectory 645 → 446 → 59 across the night) |
| 2. Key numbers correct-or-flagged | Revenue 78,615 ✓, EPS 1.15 ✓, BS totals ✓, equity ✓; CFI wrong-unflagged vs reference | **PARTIAL** |
| 3. Completion ≥80% | 70.3% whole-model vs reference; **Model tab 82.5%**; Driver 55.8% is the whole gap | **PARTIAL** |
| 4. Under one hour | ~35 min warm (vision cached); cold adds ~25 min | **PASS** |
| Delivery gate | **GATE REFUSED — correctly.** Flag budget 25-26% on Driver + Raw financials (80 stale inputs), balance 59 | honest refusal |

**Champion/challenger law: stable-run105 (80.6% / Model 90.4% / balance
PASS / delivered) KEEPS the title.** The challenger does not ship a number
it cannot prove — it quarantined itself, which is the designed behavior,
not a crash. Caveat on the score: the DFE "reference" is a prior agent run;
RUNLOG shows the filing sometimes supports the challenger over it (e.g.
Driver!J6) — the raw 70.3% modestly understates.

## What the night proved

- **The architecture works end to end**: read-once evidence ledger →
  deterministic triple-lock join → checksummed gap reader → objective loop
  → delivery gate, with a write monopoly and zero uncited writes.
- **Generic**: DFE (Chinese, scanned statements, link-through model) and
  CLP (English, 8-sheet segment model) run through identical code; the
  agent reasons out year columns itself (incl. the annual-vs-1H panel
  trap).
- **Luna diagnoses like an analyst** in the objective loop: it traced the
  balance gap to the equity chain and searched the exact 58.5 delta. Its
  weakness is CONVERTING findings into writes — fixed structurally with
  `apply_diff` (one action from finding to guarded, cited, transactional
  write); it fired 5 times in the final run.

## Six diseases found live and pinned as museum exhibits (all committed)

1. **FY24-doc checksum coincidence** — loose tolerance admitted a
   prior-year page; restored the identity-grade law + vision early-abort
   (saves ~⅓ of vision spend).
2. **Cropped-caption scan pages** — statement pages now self-identify from
   their own rows; the scanned faces joined deterministically after this.
3. **The redirect sign law** — served values re-signed to the input
   site's own convention (the GP = revenue + |COGS| disease).
4. **CLP dividend poison** — per-share printed next to the total; world
   band now enforced at join time.
5. **Year-axis census rows** — the header row briefly became a "target"
   (0.002025); census now skips year-mark rows.
6. **Prior-period document law** — deterministic doc-vintage classifier
   (distinctive-value second-slot voting); the FY24 AR is excluded from
   joins, reads, and citations.

## Where the remaining gap is (ranked for next session)

1. **Driver/MD&A tables (55.8%)** — the same gap the champion had. Needs
   the council's two-level table binding in Stage 2, or an MD&A-scoped
   apply_diff sweep.
2. **The endgame plug** — closing a 59 residual needs the analyst's
   re-anchor/plug move (orange-flagged). Decision needed (you/council):
   does the loop get that move with proof requirements, like legacy
   plug_key?
3. **Stale-flag clearing** — consider a pre-loop deterministic apply_diff
   sweep over STALE rows with unique face evidence (stage-2-grade, no LLM).

Runs, autopsies and every fix are in the `rebuild` git log (each commit
message is its own autopsy). Pinned replay snapshots + baseline (77
bindings): `companies/Dongfang Electric/replay/FY25/` (Project M tree).
The Actions workflow has a `pipeline` action ready for cloud runs.
