# Toolset audit — 100+ runs of evidence vs the new objectives (2026-08-17)

Judged against BOSS_MINDMAP.md / REBUILD.md §2: the agent THINKS and owns the
update; tools are hands it deploys at will. A tool survives only if the run
log shows it WORKED and it fits that shape. Sources: RUNLOG.md (runs 12–116),
council/architecture-council.md, MORNING_REPORT.md, module inspection of
`agent/` and `pipeline/`.

The single loudest lesson of the whole log (council ruling, 08-16): **zero
errors ever came from checksummed reads; ~100% of failures came from
heuristic middle-layer WRITERS** — code that decided numbers. That is also
the strongest argument for the new design: judgment belongs to the agent,
determinism belongs to verification.

---

## 1. PROVEN GOOD — give these to the agent as tools

| Tool | Evidence | New role |
|---|---|---|
| **Checksummed page reader** (agent/fablemode.py, pipeline/stage3_read.py) | 0 wrong reads across all runs; signed-checksum upgrade caught a real sign error (Raw!U219 CFI −10,587 vs +10,587) confirmed by the cash tie | `read_page` — the agent's trusted eyes on any statement page |
| **Deterministic join** (agent/join.py → pipeline/stage2_join.py) | 130/130 vs filing offline; 141 joins @ 175/176 precision live | `auto_join` — bulk-binds the provable rows so the agent spends thinking only on the hard residue |
| **Unit/scale doctrine** (pipeline/numerics.py) | The units disease had NINE homes (yuan vs millions killed DFE runs 95–98: findability 19/75 → 69/75 after fix); page-scale detection (万元/千元 per page) | Baked into every tool boundary — non-negotiable |
| **Write chokepoint: cited, transactional, read-back, auto-revert** (pipeline/writer.py) | Blocked the run-37 AI63 wrong-row repair offline; key-guarded siblings protected net profit in run 105 after run 104 corrupted it; zero structural corruption ever shipped | THE only write path. `set_input` stays citation-required and transactional |
| **Vision with checksum gate** (agent/vision.py) | Proved TA/CA/CFO/CFI/CFF on DFE's 12 image-only statement pages that text search could never find; prior-column checksum = parent-twin defense | `read_scanned_page` — for image-only disclosures |
| **Anatomy discovery** (pipeline/discover.py) | CLP ran end-to-end with ZERO company config (8 sheets, 57 joins); solved the 1H-panel trap | Task A's engine — which column, which periodicity, forecast-vs-reference |
| **Residual fingerprinting / post-eval** (agent/posteval.py + the taught playbook) | The assembly finish: every residual attributed by fingerprint (2× = sign, exact-delta = missing line); took run 115 from 76.9% to Model tab 99.1%, balance −0.0 | The heart of the new reason-and-fix ladder — this IS how the agent chases an unbalanced BS |
| **apply_diff (find-to-act bridge)** | Landed in the final overnight run, fired 5×; fixed Luna's one measured weakness (diagnoses well, converts findings to writes poorly) | Core loop action |
| **Implied-prior tie-out** (current ÷ (1+同比%) ≡ model prior) | 13 right / 0 wrong on DFE's single-year MD&A stats block — the only mechanism that ever cracked the Driver gap class | `match_by_implied_prior` — for tables with no comparatives |
| **Cash-tie / statement-wins arbitration** | Council Q3; the CFI sign catch; bridges stood down where the statement disagreed (run 103) | Police doctrine: the ties are the oracle, the statement outranks derived values |
| **Museum tests + pinned replay + dry runs** | Would have caught runs 112–116 pre-dispatch; gate caught 2 real poisons in dry runs alone; 50 exhibits green | Engineering discipline — survives untouched (REBUILD §7) |
| **_REPORT / _SPEC writers** (pipeline/report.py, spec.py) | Owner-required outputs | Extend _REPORT with the two forecast-comparison tables |

## 2. PROVEN BAD — dead, do not resurrect

| Tool | Evidence of harm |
|---|---|
| **Heuristic auto-writers**: allocation scaling, closing loop, tie-web plugs, reviewer auto-apply | Closing loop clobbered a correct net-profit plug (run 33); reviewer auto-apply wrote 61,800 into a zero-prior row (33) and one catastrophic unflagged apply (v3); tie-web plugged INTO the sales cell (38); plug displacement caused the phase-6 whole-model regression (37–41). Council: every failure class traced here. Under the new law, only the AGENT decides a plug, with citation, through the chokepoint |
| **Fixed-stage workflow as control flow** (agent/cli.py's 1,713-line state machine) | The failed legacy design by owner ruling; phase-ordering bugs (objectives ran before closing loop and got clobbered, run 33) are intrinsic to call-graph control |
| **Extract-then-match as the primary path** | ChatGPT side test 82.5% vs the harness's 73.3% on identical rows — the pipeline THROTTLED the model; direct-map (brain reads, hands verify) was 6× faster at equal accuracy (runs 43–46) |
| **N-pass extraction voting / consensus filtering** | Triple extraction burned the whole budget (run 21); agreement filtering shrank coverage and settled mid-band (run 20); tables made voting redundant (24–26) |
| **Refusal gate + 15% flag budget** (pipeline/gate.py refusal arm) | Dead by objective — quarantined a 70.3%/59-residual model the owner wanted delivered. Gate checks become Police inputs; refusal and budget arithmetic deleted |
| **Completion-% scoring vs an agent-run reference** (tools/score_run.py as champion metric) | Reference itself loses filing adjudications 8–10 vs the run (run 100); metric retired with the champion |
| **Unguarded warm-memory serving** | Run 106: memory hints net −5pp, net profit drifted — hint path lacked the statement-wins guard |
| **Label-first matching / proof-by-redundancy** | Elected ubiquitous small numbers (equity "9,508" vs correct 107,610, run 31); prior-value collisions (D&A matched as Minority Interests, run 14). Number-anchored triangulation only |

## 3. MIXED — salvage the lesson, rebuild the tool

- **The learner** (agent/learn.py): sound when precise (53 direct hits; 118
  verified identities by run 105) but spent 5 runs at zero on one `int(page)`
  bug and its memory-guided reads failed (2/57, 3/68). The REFOCUS design
  (probe the prior-year doc, discover the company's hard set, spend budget
  only there) is right and generic. Rebuild lean, writing to `_SPEC`.
- **The orchestrator/objective loop** (pipeline/orchestrator.py): "Luna owns
  the update; code is its hands" is exactly the new design — but it sits as
  Stage 4b at the END of a fixed pipeline, on a starvation-prone loop budget.
  INVERT: the loop becomes the whole agent from minute zero; stages 1–3
  become tools it invokes (`digest_documents`, `auto_join`, `read_page`).
- **Digest-once** (agent/digest.py): the phase-4 recommendation — a
  disclosure never changes, so freeze one validated extraction artifact per
  document. Was blocked by the old cold-run benchmarking constraint; the new
  objectives have no such constraint. Adopt: it kills the measured #1
  plateau cause (per-run extraction lottery, 71.6–75.8 on identical code).
- **Reviewer** (agent/reviewer.py): blind fresh-context review caught real
  errors (NCI sign, cash — run 18); its AUTO-APPLY caused disasters. New
  shape: the Police reviews and sends findings BACK TO THE AGENT to fix —
  review survives, auto-apply stays dead.
- **Derivation/back-out recipes** (agent/derive.py): needed for the flagged
  back-out/plug exit (3.4) — but invoked by the agent as a deliberate last
  resort, never fired by code on its own.

## 4. MISSING — new tools the objectives demand

1. **Restatement detector + pause/resume** — detection primitive exists
   (lookup.py: name-match-number-mismatch); the full-stop, analyst question,
   and resume state do not.
2. **Cross-report section mapper** — the analyst's restatement-"No" method
   (locate line's section in the unrestated prior report → same section in
   the new report).
3. **Adjustment-logic inferrer** — read how the prior actual column adjusts
   reported figures; replicate on new actuals (Police law 2). Nothing in
   either codebase does this today.
4. **Forecast-comparison snapshot** — pre-update snapshot exists implicitly
   (archive copy); the _REPORT tables (FY25 proj vs actual; old-vs-new FY26)
   need building.
5. **Non-disclosure proof log** — "not disclosed" only claimable with a
   recorded exhausted search (the anti-laziness guard).
6. **Forecast-integrity repair authority** — tracing a broken forecast year
   to its cause and fixing it (may edit forecast columns, integrity only).
   The fingerprint playbook is the method; the authority is new.

## 5. The architecture implication (one sentence)

Keep every proven VERIFICATION and READING tool, delete every deciding
WRITER and the workflow spine, promote the objective loop to BE the agent
from minute zero, and hand it the toolbox above plus the Police at its back.
