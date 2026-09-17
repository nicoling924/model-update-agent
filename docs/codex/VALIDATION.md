# Candidate status — 17 September 2026

Implementation is isolated in `codex/mvp-integration`, in the separate `codex-mvp` worktree. Claude's checkout and live company models were not edited. The offline commit/dispatch gate is now passed after the two owner-approved historical corrections. Live performance is not yet established. GitHub repository access and push permission were verified read-only / by push dry-run.

## What was built

Mapping and review corrections now share the evidence/write path, including explicit document identity, unit conversion, read-back and source records. Correction batches restore values and evidence together when any member cannot be written. Input discovery preserves cross-sheet links and accounting formulas while permitting numeric updates inside the same formula structure. Distinct objectives on one cell no longer overwrite each other. Forecast repair uses the same balance tolerance as measurement. Each run emits a separate three-objective acceptance record.

This reuses the existing extraction, writer, rollback, report and replay machinery. It is not a replacement engine. The precise rules and pins are in [MVP_CHANGE_CONTRACT.md](MVP_CHANGE_CONTRACT.md).

## Verified

- The full existing `tools/bench.sh` passed, including the historical museums and change guard. The pipeline museum has 262 distinct tests.
- All 12 independent contract tests passed. The precision tests reject the existing checker's false EPS successes: 0.94 versus 1.15 and 4.6476 versus 4.14.
- CLP `Driver!AI103`: proposed finance cost **-1,860** survived the complete run; one source-line candidate. It remains red because semantic equivalence needs review.
- DFE `Raw financials!U68`: disclosed inventory **26,171,153,034.44 RMB** became **26,171.15303444 million**, survived the complete run, and remains red pending semantic review; one source-line candidate.
- All three pinned replays produced workbooks. Delivery is not counted as acceptance.

The first CLP readiness attempt used the wrong document/page in the test fixture and failed; the corrected fixture cites annual-report page 166. The failed attempt was not counted as a success.

## Acceptance remains incomplete

| Offline replay | All-period balance | Printed keys | Rollover |
|---|---|---|---|
| CLP FY25 | Fails: ROAFNA row 31, 2024, -1,264 | Fails | Review required |
| DFE FY25 | Passes discovered checks | Fails | Review required |
| DFE 1H25 | Fails: Model row 135, 2006, -8,290 | Unmeasured | Unmeasured |

Both historical balance failures were independently reproduced in the **unchanged input workbooks** using the same discovered checks. They are not new failures introduced by this candidate, but they still violate the all-period requirement.

These saved artifacts have **no recorded LLM mapping turns**. They exercise deterministic processing and the ending, not the quality of live LLM reasoning. Key failures cannot be interpreted as a measured live-agent success rate. Under the stricter acceptance measurement, CLP ties 0/8 recorded keys and DFE FY25 ties 1/11; the baseline's old 1/8 and 3/11 counts included false EPS matches. The new final precision check was applied to the frozen runs' recorded final values without modifying their workbooks; the final reporting-only change has its own contract test.

Evidence files and code/ledger hashes are in [validation/summary.json](validation/summary.json) and the adjacent validation directory. Full temporary workbooks are under `/private/tmp/codex-mvp-verified` and `/private/tmp/codex-mvp-readiness-v3`.

## Remaining acceptance issues

1. **Resolved in phase 2:** key repair, review, source snapshots and reporting now share the same signed evidence-precision comparison. Review no longer applies the balance-check tolerance to EPS. The ordinary workbook counts now agree with acceptance (0/8 CLP, 1/11 DFE in the no-mapping-turn replays).
2. **Resolved for journaled writes in phase 2:** Writer invalidates a changed cell's old source claim and preserves claims belonging to other periods. Transactional restoration also restores evidence, progress and formula-to-hardcode transitions. Formula results that change indirectly through dependencies remain a separate evaluator/provenance concern.
3. The offline evaluator is not certified Excel calculation. Its limitations and absent interim key coverage mean that an unmeasured objective must stay unmeasured. Independent disclosure/rollover review has not been completed.
4. Both historical imbalances are now traced to exact input/formula errors; see [HISTORICAL_FINDINGS.md](HISTORICAL_FINDINGS.md). The owner approved both corrections. They are applied only to Codex-branch copies, with originals archived and exact before/after evidence recorded.

## Phase 2 verification

A frozen source snapshot ran all three original pinned replays plus both full-pipeline readiness cases. The full regression bench and all 12 focused tests pass. Both readiness values survive and have one source-line candidate each. Current evidence is in [validation/phase2/summary.json](validation/phase2/summary.json); this supersedes the initial reporting-only remeasurement above.

The original failures remain in the baseline evidence. After the approved corrections, fresh full replays pass every discovered balance check: CLP FY25 24/24, DFE FY25 118/118, DFE 1H25 84/84. See [validation/approved/summary.json](validation/approved/summary.json). The same frozen pipeline code passed the full bench and both readiness cases; SHA-256 comparison confirmed source identity before commit.

Only the code/dispatch gate is cleared. These replays still lack LLM mapping turns; native Excel calculation and independent semantic review have not been certified. This is ready for a controlled live pilot, not yet an accepted MVP. The GitHub dry-test step now uses explicit bash so a failing test cannot be hidden by the following `tee` command.

## Mixed-unit candidate verification

The unit conflict fix passed the full bench, 15 focused contracts, all three balanced pinned replays (24/24, 118/118, 84/84), and three full-pipeline readiness cases. EPS 1.15, inventory 26171.15303444 and finance costs -1860 survive the complete runs. Each quoted line has one label-qualified source candidate. These values remain red for semantic review. Evidence and test-harness limitations are in `validation/units/summary.json`. Live pilots remain cancelled; no new end-to-end accuracy claim is made.
