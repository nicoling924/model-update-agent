# Run log — CLP FY25 benchmark (runs 12-17: gpt-5.6-luna; runs 18+: gpt-5.6-terra)

Scoring vs the Fable-verified ground truth (`CLP Model FY25 (Updated).xlsx`, 690
evaluated cells in the 2025 column). "Correct" = evaluated value within
max(1.0, 0.5%). Criteria: balanced (Final!AI99=0) · full rollover · ≥90% correct ·
≤60 min · every uncertain cell red-flagged.

| Run | When (UTC) | Runtime | Correct % | Balance gap | Wrong-unflagged | Wrong-flagged | Outcome / major errors |
|---|---|---|---|---|---|---|---|
| 12 (baseline) | 08-11 12:15 | 45m | 68.8% | 250 | 172 (mostly propagation from ~15 root inputs) | 43 | Gate blocked delivery. Roots: BS composite rows misread, cash column-misread, MI composition missed, SoC 5-yr table gaps, net finance costs LLM-mapped wrong. |
| 13 | 08-11 13:08 | 46m | 68.3% | 130 | 171 | 48 | First DELIVERED workbook (with exceptions). Major errors: rescue pass skipped (mapping consults ate the time budget — reordered for r14); post-gate crash in reviewer dump (RGB serialization — fixed); P&L composition roots persist (net finance costs, NCI split, one-offs bridge). |
| 14 | 08-11 13:59 | 47m ✓ | 69.4% | 130 | 175 | 36 | First GREEN end-to-end run (reviewer + provenance + report). Rescue 13/80, consults 24. Major find in autopsy: formula-pattern copy carries STALE 2024 CONSTANTS into 2025 (root of most unflagged errors); also prior-value collisions (D&A line matched as Minority Interests). |
| 15 | 08-11 14:54 | 46.5m ✓ | **75.7%** | -5,986 (honest — prior small gaps were offsetting stale values) | 111 | 57 | Constants-rewrite worked (+6.3pp, best jump). Job red: OpenAI 429 rate limit during reviewer call (fixed: patient backoff). MI captured by wrong-line consensus before spec rule (fixed: spec rules first, stmt-qualified components). |
| 16 | — | cancelled ×2 | — | — | — | — | Cancelled pre-completion: first for a half-landed cascade fix, then for the fairness scrub (leaky MODEL_SPEC). |
| 17 | 08-11 15:51 | 46.9m ✓ | **70.1% (clean)** | -2,114 | 139 | 67 | **First fair-benchmark run, job green.** Fresh uncontaminated extraction (1,486 items/163 ties — leaner than the cached 1,694); rescue 17/91; consults 15; MI composition rule worked (row no longer wrong). New issues: forecast-year balance rows blew out (~71k — a roll-forward base row mapped badly) and ROAFNA worse (-66.9k — SoC statistics tables under-extracted in the fresh pass). Clean 70.1% vs contaminated 75.7% suggests leak+extraction-variance was worth ~5pp. |

**LUNA VERDICT (after 6 scored runs):** on a complicated multi-sheet model
(CLP: 10 data sheets, SoC regulatory block, 5 regional segments), **gpt-5.6-luna
plateaus at ~70% first-run cell accuracy** (clean benchmark 70.1%; best
contaminated 75.7%). It delivers on time with everything uncertain flagged, but
cannot reach the 90% bar unassisted — extraction completeness on dense
statistics tables and definition-sensitive rows are the binding constraints.
Escalating the model tier from run 18: **gpt-5.6-terra** (updater + reviewer).

| 18 (Terra) | 08-11 17:02 | 42.1m ✓ | **82.0% (clean, cold)** | -5,986 | 91 | 33 | **Terra baseline: +12pp over Luna clean — model tier closed half the gap.** Reviewer sharper (REJECT verdict, caught NCI sign + cash). Remaining roots: components matcher tripped by zero-value note rows (fixed: exact-label first), rescue accepted sign-flipped NCI (fixed: harmonize to model sign + flag), 2-digit stale constants unflagged (fixed: lower rewrite gate). |

| 19 (Terra) | 08-11 17:49 | 45.2m ✓ | 75.8% | -2,114 | 110 | 57 | MI/NCI fixes landed (gone from wrong list), but -6pp vs r18: **cold-run extraction variance (~±5pp) now dominates** — this pass misallocated the revenue split (sum right, split wrong) where r18's extraction had it right. Countermeasure for r20: double-extraction consensus voting (agreement filters misreads at the source). |

| 20 (Terra) | 08-11 18:38 | 46.9m ✓ | 76.5% | -2,114 | 104 | 58 | Consensus double-extraction: stabilized the floor (no r19-style split misread) but also shrank coverage (agreement filter drops items where passes differ), so the score settled mid-band rather than lifting. |

**TERRA VERDICT (3 cold scored runs: 82.0 / 75.8 / 76.5):** on the same
complicated model under strict cold-context rules, **gpt-5.6-terra plateaus at
~78% ±4pp first-run cell accuracy** — a clear tier gain over Luna's ~70%, with
faster convergence (fewer retries), a genuinely useful adversarial reviewer, and
the same guarantees (on time, ~100% filled, all uncertainty flagged, structural
damage impossible). The remaining gap to 90% is dominated by single-pass
extraction variance on dense tables and definition-sensitive CF/split rows;
within-run engineering has hit diminishing returns. Paths that would close it,
in order of leverage: (1) per-company spec accumulation across periods (the
compounding design — structural rules only, fairness-compatible), (2) letting
the blind reviewer's incontrovertible catches auto-apply with read-back (max 2
iterations, per the original Project M workflow), (3) a stronger/cross-provider
reviewer model.

**PHASE 3 (run 21+): back to gpt-5.6-luna with the upgraded harness** — chunked
page-reads as the PRIMARY path for all input rows (~20-30 rows/batch, prior-value
landmarks, corroboration-gated), majority-of-3 extraction voting, cascade
cross-check on every write (agreement -> unflagged, conflict -> flagged), and
bounded reviewer auto-apply of incontrovertible catches. Hypothesis: a better
harness lifts the weakest model past its own ~70% plateau.

| 21 (Luna, new harness) | 08-12 01:06 | 86.6m ❌ (>60) | 62.3% | 9,636 | 169 | 91 | **The headline feature never ran**: triple extraction on slow Luna consumed the whole LLM time budget, so the chunked primary reads were skipped by the walk-away deadline (0/179 corroborated) — the run degraded to cascade-only on a heavily shrunken majority-filtered extraction (890 of ~1,700 items). Reviewer auto-apply worked (4 incontrovertible fixes applied + re-verified). Not a test of the chunked design — a scheduling failure. Fix queued for r22: chunked reads run FIRST and are exempt from the deadline; votes 3→2 for slow models. |

| 22 (Luna, fixed harness) | 08-12 02:47 | 50.4m ✓ | 71.7% | 1,811 | 125 | 70 | Chunked-primary executed properly (57/179 corroborated; 44 dual-confirmed, 1 conflict flagged); 2-pass coverage-preserving consensus; reviewer auto-applied 4; first OpenRouter-billed run. **Luna-with-best-harness verdict: ~72% — harness sets the floor and safety, model quality sets the ceiling** (Luna fails chunk corroboration 2 of 3 times on dense tables). |
| 23 (Terra, new harness) | 08-12 05:06 | 42.4m ✓ | 74.9% | 1,811 | 116 | 57 | Within Terra's 78±4 band — chunked harness adds safety (conflict caught, dual-confirmed cells) but not points, for either model: chunk corroboration is landmark-limited (~1/3 of rows have a printed prior to anchor on; Terra 59/179 vs Luna 57/179). Bottleneck shifts to extraction quality -> run 24 tests table-aware reading. |

| 24 (Luna+tables, branch) | 08-12 05:15 | cancelled @90m | — | — | — | — | Table-aware pages doubled reading volume x 2 voting passes -> timeout during extraction; no cells written. Fix: single-pass extraction (tables replace voting as the variance control). |
| 25 (Luna+tables, 1-pass) | 08-12 06:48 | 67.8m ❌ (>60) | **71.7%** | -2,086 | 126 | 69 | Richest extraction of the benchmark (2,202 items / 223 ties) — and accuracy IDENTICAL to Luna without tables (r22: 71.7%). The residual errors are no longer reading errors: same stubborn set (revenue split allocation, FCA asset-vs-liability side, one-offs bridge) — these are JUDGMENT/definition calls, not transcription. |

**HARNESS-CEILING VERDICT (Luna, 3 harness generations: 70.1 / 71.7 / 71.7):**
harness engineering has converged for this model tier. Reading quality is no
longer the constraint (tables proved it); the remaining ~28%% needs judgment
(allocation, definitions, bridges) that only a stronger model, per-company spec
accumulation across periods, or analyst rulings can supply. Recommended
production shape: Luna/Terra updater + accumulated spec + reviewer auto-apply,
with first-run flags resolved by the analyst feeding the spec.

| 26 (Terra+tables, branch) | 08-12 08:02 | **36.1m ✓ (fastest)** | 77.4% | -3,158 | 104 | 52 | Matrix complete: mid-band for Terra (78±4) — no breakout. Same stubborn judgment rows across all configs (FCA side, revenue split, recurring bridge). Tables verdict: cheapest+fastest+safest configuration at equal accuracy — merge-worthy on economics, not accuracy. |

**BENCHMARK CLOSED (16 scored runs):** cold-first-run ceilings — Luna ~72%,
Terra ~78% — are set by model judgment (allocation/definition calls), not by
reading, process, or prompting (proven by elimination across 3 harness
generations). Production path to 90%+: accumulate analyst rulings in the
per-company spec across periods; each run's flags are the next run's rules.

| 27 (Sol+tables, branch) | 08-12 09:04 | 63.2m ❌ | 75.7% | 1,810 | 115 | 53 | Sol lands mid-tier, between Luna (71.7) and Terra (77.4), confirming the model-quality gradient. Most thorough extraction of the benchmark (3,637 items / 470 ties) yet mid-band accuracy — same judgment-bound ceiling. Benchmark remains closed; no further runs without explicit instruction. |

| 29 (Luna, full stack) | 08-12 12:49 | crashed 28m | — | — | — | — | OpenRouter returned 200-with-error-body during extraction; client crashed before any cell was written (fixed: retryable no-choices handling). |
| 30 (Luna, full stack) | 08-12 13:19 | 60.2m ✓ | **75.8% (Luna live best)** | 4,284 | 108 | 58 | First complete execution of the full stack: whole-column rollover (analyst's copy-paste method, 216 inputs auto-discovered, zero cycles), chunked reads 62/216, component landmark reads, reviewer auto-apply 4, closing loop 10 repairs. Luna live trajectory: 70.1 → 71.7 → 74.2 → 75.8. |

**OVERNIGHT PHASE 4 — the learner agent (self-supervised calibration):**
| Learn v1 | 08-12 18:07 | 58m ✓ | — | — | — | — | Learner works: 134 identities (108 inputs + 26 composites) from FY24 report vs 2024A answer key; privacy-safe hidden _UPDATE_MAP tab committed. (First attempt crashed on string-number coercion — fixed.) |
| Mem v1 update | 08-12 19:35 | 48.3m ✓ | 73.5% | -3,129 | 119 | 63 | Attribution: 53 cells correct straight from memory; 36 learner gaps (20 unidentified + 16 ambiguous segment-less identities); 27 identities unusable against that run's extraction. |
| Learn v2 + update | 08-12 20:29 | ✓ / blocked | — | — | — | — | Learner v2 (segment+page identities). Update blocked by the cycle guard — root cause was OURS: constants-rewriter treated the '41' in 'AI$41' as data and created a self-reference. Fixed ($-boundary); the guard proved it will never ship a corrupted workbook. |
| Mem v2 update | 08-12 21:5x | 45.7m ✓ | 73.6% | -3,106 | 126 | 55 | Segment-aware identities live; memory-guided page reads only 2/57 (prior-year page drift). |
| Mem v3 update (drift band) | 08-13 | 45.7m ✓ | 71.6% | -3,107 | 138 | 57 | Drift band widened -> still 3/68 corroborated: Luna cannot reliably quote the prior even when pointed at the right pages. PLATEAU CONFIRMED. |

**OVERNIGHT VERDICT — the user's question answered:** the learner is sound
(identities correct when precise; 53 direct hits) and NOT the limiter. The
limiter is the updater's raw material: **Luna's per-run extraction lottery**
(71.6–75.8 across four identical-code cold runs). No within-run machinery —
memory, tables, chunking, voting, closing loops — moves the live score outside
that band, because each cold run re-reads the documents from scratch and reads
them differently each time.

**RECOMMENDATION (production architecture):** split "document digestion" from
"model update". A report's content never changes — digest each disclosure ONCE
into a validated extraction artifact (best-of-N passes, or a stronger model,
or human-spot-checked), stored alongside the PDF; every update then runs
against the frozen artifact: reproducible, variance-free, and the memory tab's
identities always find their lines. Cold-run-per-update is a benchmarking
constraint, not a production requirement — dropping it is the single change
that makes 90% reachable with the existing harness.

**PHASE 5 (design-partnership iterations, 08-13):** section anchors (user's
hypothesis — correct, located sections; reader still failed proof) -> v3 run
71.6% incl one catastrophic unflagged reviewer-apply (fixed: universal 20x
magnitude guard) -> deterministic-first learner + code table-lookup serving
memory (numbers never pass through the LLM; find-by-name, verify-by-number,
restatement = name-match-number-mismatch) -> v4 run 69.3%: lookup served 37
rows (17 clean — all guaranteed digit-exact), but net score unchanged.

**FINAL VERDICT (25+ scored runs):** under the deployment constraints (weakest
model tier + fully clean context + memory-tab-only carryover), the system
converges at **~72% ±4 first-run accuracy with ~95% of errors pre-flagged,
inside 60 minutes, structurally incapable of shipping silent corruption**.
Every mechanism proposed by either party was built and measured; each adds
locally-correct cells but the run-to-run score is dominated by the one factor
no harness can remove: the weakest model's inconsistent broad reading of dense
documents. The measured levers to 90%: (1) Terra-class reading (+6-10pp,
proven), (2) analyst rulings compounding into the spec across periods, (3)
relaxing clean-context for DOCUMENTS only (digest-once). The pack, the
learner, the memory format, and all guardrails are production-ready and
model-agnostic; raising the model tier raises the score with zero code change.

**FAIRNESS NOTE (15:5x UTC):** runs ≤15 ran with a system prompt that included the
original MODEL_SPEC, which contained some FY25 figures (tie-out anchors, FX
rulings) — deterministic mapping was unaffected but LLM consults could in
principle have seen answers for a handful of headline cells. Both per-company
files are now scrubbed to structural knowledge only; the extraction cache was
invalidated by the scrub, so the clean benchmark starts at run 17 with a fresh,
uncontaminated extraction. Treat pre-17 accuracy as indicative, run 17+ as the
fair benchmark.

## Fix history feeding these runs
- r1–r2: API dialect + reasoning-budget escalation (plumbing)
- r3–r8: extraction schema discipline, tie self-check, quarantine, empty windows
- r9–r10: full pipeline reached; style-copy bug; mapping pacing (budget + walk-away)
- r11: first integrity-gate verdict (balance 18,241; 113 flags)
- r12: corroboration-gated cascade, consensus dedup, sign-flip, recompose → gap 250
- r13: targeted rescue (5/6 on hardest rows in live test), always-flag LLM, tiered gate

**PHASE 6 (objective-driven branch, 08-13):** tier ladder — balance > key numbers
(sales/GP/NP/cash/CA/CL/NCA/NCL/equity/CFO/CFI/CFF + breakdowns, 100% target) >
60min > whole-model 90%. Convergence in code: proof-by-redundancy, anchor-plug,
balance diagnostic.

| 31 (Luna, objectives v1, GitHub chain) | 08-13 12:22 | learn 40.5m + upd 47.0m ✓ | 69.6% | -5,958 | 145 | 62 | First cloud run (learn+update one dispatch). Objective layer INERT — 3 bugs: proof-by-redundancy elected small ubiquitous numbers (equity "9,508" vs model's correct 107,610), retry loop burned the fix budget on one unfixable key, precedent-walk regex ate bare same-sheet refs (plug never found a site). Replay-validated fixes: triangulation-first + magnitude guard + word-boundary labels + statement-locality (6 proven-right/0 pluggable-wrong/5 honest-unproven on run-31's own staging), one-attempt-per-key, definition band (op profit 3.3% gap flagged not plugged), sign harmonization, ref-walk fixed. Learner tab committed — next runs skip the learn leg. |

| 32 (Luna, objectives v2, GitHub) | 08-13 14:44 | 53.6m ✓ | 70.3% | -1,043 (was -7,001 pre-fixes) | 141 | 61 | **Objective layer live: 4 plugs applied, ALL exactly right vs GT** (net profit 10,468, CA 22,838, CL 38,414, CFI -14,328); op profit definition-flagged not plugged (correct); key numbers 6->9/12; balance gap cut 85%, diagnostic honestly declined the uncorroborated rest. Remaining misses (NCL/CFO/CFF) all pre-declared unprovable + flagged. |

| 33 (Luna, orchestrator v1, GitHub) | 08-13 16:09 | 49.0m ✓ | 68.5% | -3,892 | 153 | 61 | **Orchestrator investigated like the design intended** (traced check row -> components -> NCI hypothesis -> disclosure search; guardrails refused 2 formula-cell writes) but net effect NEGATIVE: (a) closing loop ran AFTER objectives and clobbered the net-profit plug (10,468 -> 13,563), (b) reviewer auto-apply wrote 61,800 into a zero-prior row (guard hole), (c) orchestrator re-read same pages 4x, never found NCI under 'minority interests'. Fixes: objectives phase moved to END of pipeline (last word), zero-prior reviewer guard, page-dedup, synonym hints, clearer refusals. |

| 36 | — | cancelled | — | — | — | — | Cancelled pre-completion twice (35/36): tie-web + 3 Fable skills (statement_diff, read_bridge, segment tie-web) landed mid-flight; re-dispatched rather than measure a stale harness. |
| 37 (Luna, full skills) | 08-13 18:01 | 52.3m ✓ | 66.2% | **0 (2025 Final!) / fcst +3.4-4.8k** | 153 | 77 | **First 2025 balance PASS in 37 runs — agent found perpetual-securities composition (AI97=9,815, EXACTLY GT) via gap-matches-line + footnote.** But its TA repair put the right amount (7,562) in the WRONG row (AI63 vs AI65): fixed TA, silently broke CA — nothing re-checked after the write. Tie-web: 103 anchors, 12 fixes; keys 8/12 in-run. Fixes for r38: guarded writes (auto-rescore + auto-REVERT on any regression — offline test reproduces and blocks the exact AI63 mistake), plug de-stacking. |

| 38 (Luna, self-check writes) | 08-13 18:59 | 48.7m ✓ | 68.7% | 0 (2025) / fcst ~3.3-4.7k | 144 | 69 | 2025 balance PASS repeated (perpetual-securities repair reproduced, self-check passed). NEW SYSTEMIC FLAW FOUND: tie-web plugged INTO the sales cell (+436 to tie pretax — key rows were anchor-excluded but not plug-site-excluded); definition band then excused the corrupted sales (0.5% < 1%); revert guard blocked the orchestrator's correct restore (downstream plug had absorbed the error). r39 fixes (all offline-verified on a replica): key cells protected as plug sites, sales band tightened to 0.2%, guarded writes now transactional with AUTO-REPLUG of downstream keys before judging revert. |

| 39 (Luna, full consistency system) | 08-13 19:55 | 49.8m ✓ | 66.2% | -3,872 (perpetual repair not reproduced) / fcst small (-550..858) | 160 | 70 | Keys 9/12 (ties best); guards all held (protected plug sites, auto-replug, no self-corruption). New monster (SOC Accounts ±82,724, GT 0) traced to ONE misread upstream input propagating — pure extraction lottery, not machinery. **LUNA PLATEAU CONFIRMED on final harness: 66.2/68.7/66.2 — balance achievable but not reproducible (evidence-dependent). Per plan: Terra x2 on identical harness.** |

**TERRA VERDICT (identical harness, runs 40-41):**
| 40 (TERRA, full stack) | 08-13 20:46 | 48.9m ✓ | 66.9% | 0 (2025) / fcst -23k | 154 | 71 | 2025 balance PASS; keys 8/12. |
| 41 (TERRA, + breadth pass) | 08-13 21:38 | 48.7m ✓ | 63.2% | 0 (2025) / fcst 1.2-2.6k | 172 | 78 | Breadth pass live (9 repairs); Aus unit-scale misreads (27.5 vs 27,500) dominate the wrong list. |

**OVERNIGHT CONCLUSION (runs 37-41):** the objective architecture RELIABLY wins
its objectives — 2025 balance passed 4 of 5 runs (never before achieved), keys
stable 8-9/12, exact-GT investigative repairs (perpetual securities 9,815),
zero unguarded corruption — but whole-model % REGRESSED vs the phase-4 stack
(Luna ~68 vs ~72-76; Terra ~65 vs ~77). Root cause isolated by elimination:
extraction volume unchanged (2,100-2,600 items every run) -> NOT the reading;
the regression is PLUG DISPLACEMENT — each subtotal plug moves an innocent
sibling to absorb a residual whose true cause is a wrong sibling. FIX BUILT +
REPLAY-VALIDATED (not yet run live): sibling-first correction — check each
component's own disclosed value before plugging; on run-41 replay 8/9 sibling
corrections exactly match GT. Next live run carries it (budget cap reached;
awaiting analyst).

**PHASE 7 — DIRECT MAPPING (the brain reads, the hands verify), 08-14:** side
test (user-run, ChatGPT Terra-light on Final sheet: 82.5% vs our Terra+harness
73.3% on identical rows) proved the extract-then-match pipeline throttles the
model. Pipeline deleted; replaced by retrieval (prior-value Ctrl+F, 80% of rows
located incl. notes) -> holistic per-block mapping -> code audit -> objective loop.

| 42 | — | cancelled | — | — | — | — | superseded pre-flight by the remap freedom upgrade. |
| 43 (Luna, direct-map v1) | 08-14 05:29 | **8.2m ✓ (6x faster, 1/4 cost)** | 69.7% | **-263** / fcst <1.6k | **127 (lowest ever)** | 79 | Ties branch-best accuracy at a fraction of time/cost; best balance profile ever. Two decoded flaws: 96/216 NOT_FOUND (mapper conservatism -> carried), audit layer blind (synthesized staging too thin: 0 tie-web anchors, 0 key fixes, keys 5/12). r44: sheet-affinity rescue pass + code-parsed raw-line staging (2,802 items; keys provable again: 6 right/1 wrong offline) + thin-proof plug guard (>=3 sources). |

| 44 | — | cancelled | — | — | — | — | superseded pre-flight by mission-aware mapper (NEED_PAGES routing). |
| 45 (Luna, mission-aware map) | 08-14 05:53 | **11.1m ✓** | **74.3% (branch record)** | 0 (2025) / fcst <2k | 120 | 55 | Rescue +29 rows; audit layers all live (12 tie-web + 10 key + 15 breadth fixes); keys 5/12 — BS keys carried. |
| 46 (Luna, doc-qualified pages) | 08-14 06:13 | 13.1m ✓ | 72.2% | 0 (2025) / fcst <1.8k | 128 | 61 | Retrieval 216/216, rescue +41; score oscillated (mapper nondeterminism ±2pp). ROOT CAUSE of stuck BS keys found: cash/CA/TA are FORMULA rows summing REGIONAL-sheet inputs that group disclosures don't publish at model granularity — the same segment-allocation class every config (incl. raw ChatGPT 82.5% side test) misses. Not a mapping bug.

**DIRECT-MAP VERDICT (runs 43-46):** architecture validated — 74.3% branch
record, 6x faster (~12 min), ~1/4 cost (~$1.50/run), lowest unflagged-wrong,
2025 balance passing consistently. Remaining gap is concentrated in segment-
granularity derivation rows (regional BS splits, CF composition, one-offs
bridge) — the class that needs learned per-company recipes (FY24 calibration)
or analyst rulings, not better reading. Next: learner v6 — component recipes
for regional splits + CF composition, learned from FY24 answer key.

| 50 (Luna, candidate-line injection) | 08-14 09:21 | 26.9m ✓ | 74.1% | 0 (2025) | 124 | 52 | User's diagnosis vindicated by measurement: 153/156 FY24 hardcodes ARE printed in the docs — findability, not derivation, was the wall. Code-found candidate lines now fed to the mapper. BS chain still stale -> traced to the TRUE root: |
| 51 (Luna, no-silent-carry) | 08-14 09:53 | 23.9m ✓ | **75.3% (record)** | **0 (2025)** / fcst +26k (new propagation, flagged) | **117 (record low)** | 51 | **THE SILENT-CARRY BUG (since run 30s): composite rows like cash '=4976+23' kept stale constants UNFLAGGED when the rewriter failed — 4 runs of identical invisible wrongness. Fixed with Ctrl+F neighbour fallback (magnitude-banded) + always-flag rule. Keys 4->8/12 (cash EXACT), whole model record.** Remaining: CA/TA (one BS input ~3.2k off), CFO recipe ambiguity (1.5%), CFF (no recipe), forecast propagation of a 2025 repair. |

| 52 (Luna+4-row Terra esc.) | 08-14 11:49 | 27.3m ✓ | 73.8% | 0 (2025) / fcst +25.8k | 129 | 49 | All 5 overnight subsystems fired; forecast blowout traced to constants-Ctrl+F corrupting the NFA roll-forward bases (multi-column note tables). Terra escalation removed after (user: pure Luna). |
| 53 (pure Luna, base protection) | 08-14 17:25 | 27.8m ✓ | 71.9% | **0 (2025) / fcst <1.6k — FIXED** | 138 | 53 | Bases carried+flagged, never auto-rewritten: forecast gaps 26k -> <1.6k. Keys 7/12 — CA/CL still draw-dependent though their TOTALS prove nearly every run -> r54 wires the allocation pass (structure-scale unconfident components to proven totals). |

**OVERNIGHT SPRINT 2 (runs 53-64, all pure Luna, one investigated change each):**
| 53 | base protection | 71.9% | keys 7 | fcst FIXED <1.6k |
| 54 | (exposed range bug) | 70.7% | keys 7 | SUM ranges never expanded — fixed |
| 55 | range expansion | 72.1% | keys 7 | allocation fired, then disturbed -> sealed plug_key |
| 56 | write-path sealed | 71.2% | keys 8 | allocation starved of anchors |
| 57 | (instrumented) | 74.7% | keys 8 | skip reasons now logged |
| 58-59 | anchor widening + instrumentation | 74.1/71.9 | keys 7 | composites had lost input eligibility — fixed |
| 60 | composite eligibility | 74.3% | keys 7 | CA/TA tie via machinery; year-token poison found |
| 61 | year filter | 73.2% | **keys 9 (record)** | cash/CA/TA/CFO all exact |
| 62 | identity anchors | 73.2% | keys 8 | CL derived EXACT (38,414) but post-converge |
| 63 | anchors pre-converge | 72.4% | keys 6 (bad draw) | |
| 64 | coverage pass | 71.9% | **keys 9** | 19 carried rows decided; CL anchor unreliable across draws |

**MORNING STATE:** keys 9/12 twice (from 4), cash/CA/TA/NCL structurally solved
(year filter + composite eligibility + identity machinery), balance 2025 passes
most draws, forecasts <2k when 2025 passes, runtime ~27min. Completion pinned
71.9-75.3 vs the 80 floor: per-run draw variance now dominates — every
mechanism is individually validated; the composite score re-rolls nightly.
NEXT (designed, not built): (1) CL identity-anchor reliability (fire on every
draw, not just when TA proves first), (2) MEMORY COMPOUNDING — persist each
run's verified mappings to _UPDATE_MAP so runs stop re-reading from scratch;
the permanent end of the draw lottery and the road to the 80 floor.

**DFE GENERICITY LEG (runs 90-97, 08-15):** each failure a real generic gap, fixed
in sequence — universal rollover (partial rollovers birth circular refs), stable
tokens for Excel data-table objects (70 false clobbers), reviewer dump
stringify, evaluator memo poisoning, structural self-awareness
(`resolve_input_site` follows last year's formula to where the number is
actually typed). Then two found by EXECUTING rather than reading:

| 95 | 08-15 13:00 | crashed 4.6m | — | — | — | — | `site_labels` read above its assignment — the update leg died every run. Compile checks cannot see binding order; the (rebuilt, now committed) stubbed dry-run harness catches it in 90 seconds. Learner leg also showed VERIFIED **0 of 210** and all three CF bridges rejected at `FY24 0.0`. |
| 96 | 08-15 13:09 | cancelled | — | — | — | — | Second session's dispatch: ran against a live model a run output had been committed over, and predates the scale fix. Cancelled to save budget. |
| 97 | 08-15 13:28 | 34.5m ✓ | **79.1%** (216/273 vs the completed Fable-5 model; adjudicated >=82%) | -16,548 (2025) / -16,909 fcst | 46 | 11 | **First scored DFE run.** Units fix landed: learner VERIFIED 19 rows (was 0), 40 identities stored; retrieval 210/210; mapper OK 131 + DERIVED 12 (was 0); 125 rows conf>=4; flags collapsed 207 red -> 56 red + 16 orange, 317 clean. Sales EXACT (78,615.28). Balance FAIL traced to a document limit, not the machinery — see below. |

**ROOT CAUSE OF THE DFE WALL — units, not reading.** The CN annual report prints
yuan (`营业总收入 69,695,135,723.47`); the model holds millions (69,695.14). Every
"does this line carry this value" test compared printed digits at scale 1, so
retrieval-by-prior-value found **19/75** known values and the learner's
both-years arithmetic proof verified **0 of 210** — not because the numbers were
absent but because they were printed 1,000,000x larger. `_num_variants` had
`for scale in (1,)`: the hypothesis had been narrowed to one. Fix: detect the
document's scale ONCE per run by reconciliation (the scale that explains the
most known model values), thread it through every value test, tell the reader,
and convert document-unit answers back. Measured offline: DFE findability
19/75 -> 69/75, retrieval 87 -> 161/210 (learn) and evidence candidates 34 ->
137 (update); CLP detects scale 1, takes the original string path byte-for-byte,
and is unchanged at 216/216.

**DFE BALANCE FAILURE — ROOT CAUSE IS THE PDF, NOT THE AGENT.** Pages **95-106**
of the FY25 annual report have **no text layer** (15 image-only pages in 280;
the run 95-106 is exactly the statements block the index on p89 lists: balance
sheet 1-4, income statement 5-6, cash flow 7-8, equity movement 9-12). So
`流动资产合计` / `资产总计` / `负债合计` return ZERO hits anywhere in the document, and
101,683.68 (total current assets) is unfindable. Everything the agent got, it
got from the MD&A tables (资产构成 p21), the five-year highlights (总资产
162,674,195,217.33, p5) and the notes.

This explains every DFE symptom at once: total assets understated by exactly
15,199 (built from partial components), 7 key numbers "not provable from
disclosure", and the agent loop burning 63 decisions hunting pages that contain
no text. It diagnosed its own gap correctly ("total assets understated by
15,199.0") and could not close it because the number is a picture.

**NEXT (highest leverage on DFE): OCR image-only pages.** Detect pages with no
text layer and OCR them into the raw-line stream. Secondary: the agent loop's
`set_input` refuses formula cells (`Model!U67 is not an input cell`) and never
redirects to the source-sheet input site, though `resolve_input_site` already
knows where that is — 63 decisions produced no write. Worth fixing, but on this
document it would only have moved a number the agent could not read.

**EYES + HANDS (runs 98-99, 08-15/16, council plan #1+#2 then the audit-web fix):**

| 98 (Luna, vision + resolver) | 08-15 15:56 | 50.9m ✓ | keys 6/13 (was 3) | balance FAIL -20,296 | 44 red | Eyes WORKED: the agent transcribed the scanned statements itself (checksum-gated, 7/16 pages FY25) and PROVED the values run 97 couldn't find (TA 162,674.2, CA 101,683.7, CFO/CFI/CFF exact). Hands worked as designed: set_input on derived SUMs returned structured MISSes, page reads exhausted at 2 — no 63-decision spiral. But converge banked 0 fixes: the evidence existed and the audit web could not SEE it. |

**RUN-98 AUTOPSY — the units disease had EIGHT more homes.** Code-parsed staging
items, prove()'s raw corroboration, ctrlf_read, the constants-Ctrl+F fallback,
learn_composition, the bridge menu (why every CF bridge double-lock failed at
`FY24 0.0` since run 95), replay_composition, and the learner's construction
matcher all compared yuan-printed numbers to model millions. Plus three
CLP-shaped assumptions: no Chinese captions in KEY_KINDS (and _norm DELETED
CJK — a CN synonym normalized to "" and boundary-matched labels containing
'&'), statement locality anchored on the earliest proven page (p5 five-year
summary) discarding the real BS on p95-96 as "off-page", and the >=3-source
plug gate blocking even sibling corrections for values a scanned BS prints
exactly once. All fixed: mapper.to_model_units at every boundary (page-scale
values convert, per-share stay printed; no-op at scale 1 — CLP untouched), CN
glossary + CJK-preserving _norm, densest-cluster locality, thin-proof =
sibling-only. REPLAY of run 98's own evidence through the fixed chain: 11/11
key numbers prove at the exact disclosed values.

| 99 (Luna, audit web sees) | 08-16 dispatched | — | — | — | — | The first run where the agent knows the right totals AND can repair the components that feed them. |

| 99 (Luna, audit-web sight) | 08-15 16:26 | cancelled @106m | — | — | — | — | Ran 2x normal (old vision code's JSON-truncation retries); cancelled at the grace window, superseded by 100 (a strict superset). Partial log still paid: sibling machinery LIVE (thin-proof -> sibling-only, GUILTY SIBLING writes firing), learner recovered 3 constructions + 4 recipes (was 0+1). Two watch-items for 100's score: junk-value sibling writes (U205 "disclosed 1.0, 12 src") and a wrong-scope thin proof (op profit 1,427 = quarterly-table line; correctly not plugged). CF bridges still 0.0 -> root-caused: CF_SECT section keywords were ENGLISH-ONLY, the bridge menu was EMPTY on CN filings for every DFE run ever. Fixed + CN markers; offline: CFO composition double-locks immediately. |
| 100 (Luna, full fix set) | 08-16 ~02:20 HKT | in flight | — | — | — | — | Audit-web sight + prior-column vision gate + 8k vision client + analyst-alignment prompts (owner directive). |
| 101 (Luna, CLP genericity) | 08-16 ~02:45 HKT | in flight | — | — | — | — | Same stack on CLP, parallel — the generic-agent read for Monday. All changes scale-gated or additive; CLP dry-run was byte-identical. |

| 100 (Luna, full fix set) | 08-16 02:20 | 55.3m ✓ | **77.3% whole / Model page 90.4%** | **2025 PASS (first on DFE)**; fcst -528; CF tie 19 | 43 unfl | **Keys 11/14** (op profit definitional 5.3%, CFI 0.18% off, GP unprovable). The audit-web + scope-gate stack worked: vision accepted exactly the consolidated statements (4+2 pages), no parent poisoning, sibling machinery repaired the BS chain. Adjudication: filing supports the RUN over the reference 10-8 (e.g. Driver!J6 58,005.4 printed verbatim; ref's 35,779.1 not in filing). Driver 63.0% is now the whole gap. |
| 101 (Luna, CLP genericity) | 08-16 02:45 | 55.3m ✓ | **75.0% (no regression — historical band 74-76)** | 2025 PASS; fcst 2.3-3.7k | 120 | Keys 6/12 (draw at low end of 6-9 band). Identical stack, zero company-specific code: CLP unmoved while DFE transformed — the generic-agent claim holds. Vision correctly silent (photo pages transcribe 0 rows, rejected). |

**DRIVER ANATOMY (run 100's 51 wrong cells, fully classified):** (1) ~17 cells:
product-segment splits (Wind/Thermal/...) — the FY25 MD&A 分产品 table prints
FY25-only values in 万元 with % changes, NO comparatives -> prior-triangulation
impossible on the new doc; the ANALYST's basis values are printed only in the
FY24 doc's own MD&A. (2) ~18 cells: operating-stats table (production/sales/
inventory triplets, raw MW units) — same single-year structure. (3) ~12: note
roll tables (PPE/intangibles). (4) ~4: 亿-narrative orders. Classes 1+2 share
one key: the LEARNER must identify these rows on the FY24 doc (where the
priors ARE printed) and hand (page, label) to the update mapper.

**Fixes staged for the next DFE run:** page-scale detection (scale is a
property of the PAGE — 万元/千元 note tables measured at 195/198/209/232;
threaded through every value test); learner SINGLE-YEAR identification
(both-years stays gold; single-year stored as label+page hint — MD&A tables
never print two years on a line, which is why VERIFIED was 0); CN CF_SECT
(bridge menu was empty on CN filings — offline, CFO now double-locks
immediately); mixed-units mapper prompt (convert to each row's prior's units).

| 102 (Luna, page scales + learner fallback) | 08-16 05:00 | 37.6m ✓ | 75.1% (Model 87.7 / Driver 60.9) | 2025 PASS; **fcst -10** (was -528); CF tie -585 | 44 | Keys 10/14: CF bridges LEARNED (CF_SECT fix — 3 double-locked) but replay OVERRODE better statement values (CFI/CFF drifted 1-8%); learner single-year stored 0 (first-filter break, 4 runs running — diagnostic ships next run). Whole-model oscillating 79/77/75 = the plateau trigger. |

**COUNCIL PLATEAU SESSION (08-16 ~06:00, transcripts in council/):** Grok ranked
#1 unanimously. Verdicts: (Q1) 90% vs this reference in 2 runs is implausible
(~78-86% reachable); present THREE metrics — hard contract (met), printed-fact
accuracy vs filing (run beats the reference 10-8), inter-model agreement
(75-79%, "agreement, not completion"). (Q2) THE mechanism for single-year MD&A
tables: implied_prior = current/(1+同比%) matched against the model's own prior
= row identity with no comparative printed. (Q3) CF bridges: statement wins on
conflict; the cash-tie is the oracle. (Q4) skip the PPE rolls and 亿-prose;
never hardcode company rules.

**BUILT + MEASURED for run 103:** structured-table lines reconnected (pdfs.pages
renders headers-per-cell; raw_lines had been DROPPING them — the mapper read
p14/p207 as bare number soup); implied-prior tie-out (13 right / 0 wrong on the
reference's stats block after strict-pairing tightening; correctly refuses the
one row where the model's own FY24 disagrees with the filing); bridge=additive;
cross-language sector glossary; learner diagnostic.

| 103 (Luna, council mechanisms) | 08-16 07:30 | 34.9m ✓ | **79.9% (record; Model 90.4 / Driver 68.1)** | 2025 PASS; fcst -876; CF tie 19 | 43 | Keys 11/14 (CFI 0.18% off; op-profit definitional, correctly flag-only). Implied-prior tie-out banked its 13 stats rows live; bridge stood down where the statement disagreed. **The diagnostic solved the learner's 5-run zero in one log line: identification answers 'p46' (string) where the verifier called int(page) — 164 OK identifications dropped at the first filter every run since vision landed.** |
| 104 (Luna, learner unlocked) | 08-16 08:20 | in flight | — | — | — | Digits-only page parse in learner verify + mapper audit; the identification path (164 OK answers) finally stores. |

| 104 (Luna, learner unlocked) | 08-16 08:20 | 36.2m ✓ | 75.8% (Model 82.5 / Driver 67.4) | **BALANCE PASS — ALL SIX YEARS (first ever)** | 53 | **Keys 12/14** — but net profit went materially WRONG (3,491.8 vs 3,831.3): a 3-source sibling "correction" (Raw financials!U11 4,043->3,781.8) matched the wrong line and moved a headline key away from its disclosed value while balance passed — the exact trade the contract forbids. Learner alive at last: VERIFIED 116 + single-year 27 (was 0). |
| 105 (Luna, key-guarded siblings) | 08-16 09:20 | in flight | — | — | — | Sibling corrections now transactional against their driving key (revert if the key moves AWAY from disclosed). The final overnight run. |

| 105 (Luna, key-guarded siblings) | 08-16 09:20 | 38.0m ✓ | **80.6% (night's record; Model 90.4 / Driver 69.6)** | 2025 PASS; fcst -539 (flagged) | 41 | **Keys 11/14 with NET PROFIT PROTECTED (the guard reverted the run-104 damage class); remaining misses: op profit (definitional, correctly flag-only), CFI 0.18%, GP unprintable.** Learner: 118 verified + 26 single-year identities. THE FLAGSHIP DELIVERABLE. |

**NIGHT VERDICT (runs 97-105, ~8 hours, ~$14):** DFE transformed from
79.1%-balance-FAIL-keys-3/13 to 80.6%-record with 2025 balance passing
consistently, all-years balance PROVEN reachable (run 104), keys 11-12/14
(remaining misses definitional or <0.2%), Model page at 90.4%, runtime ~35-38
min, CLP regression-free at 75.0%. Every fix generic; every fix measured
offline before dispatch; two council sessions (transcripts in council/).
The whole-model % is INTER-MODEL AGREEMENT vs an unverified Fable-5 run that
the agent BEATS on filing-adjudicated disagreements — present three metrics,
never one (PRESENTATION.md).

| 106 (warm) | 08-16 11:00 | 39.4m ✓ | 75.5% | fcst -1,101 | 55 | Memory hints net-NEGATIVE (-5pp vs cold 105): the hint path lacks a statement-wins guard; NP drifted again. Warm serving REMOVED from the critical path; cold is the production recommendation until guarded. |
| 107 | — | cancelled | — | — | — | Superseded mid-flight (owner's batch directive); payload inside 108. |
| 108 (finishing batch v1) | 08-16 13:00 | 38.7m ✓ | 78.8% (Model 86.8/Driver 68.8) | -75/-157 | 43 | Aligner SILENTLY SKIPPED (fed only unresolved rows -> <4 anchors); oracle skipped (期初 caption never survives extraction); CFF bridge served unarbitrated (5,553 wrong instance). All three root-caused same hour. |
| 109 (batch v2) | 08-16 14:30 | 41.9m ✓ | 78.8% | fcst **-570,000,035** | 43 | Aligner LIVE (20 anchors, 1 correction); oracle had pieces but MISPICKED ΔCash and demoted a correct cfi. The -570M: the mapper wrote a raw-yuan UNCERTAIN value into Driver!J97 — audit's units conversion SKIPPED non-OK statuses. Two-line hole, validated fix. |
| 110 (units hole + oracle log-only) | 08-16 15:50 | in flight | — | — | — | UNCERTAIN values get units conversion (poison case -570,000,000 -> -570.0 verified); oracle failure arm log-only, upgrade arm stays. |

**CLEAN-ROOM FABLE TEST (sealed room, audited): 96.0% — Model page 100%,
Driver 92.0%, ~50 min.** Audit CLEAN: complete file log; FY24 doc never
opened; every "suspect" value traced to print (117,251 = 新生效订单1172.51亿元
p10 — the grep missed it for a comma; 73,476.07 = 境内 7,347,606.99万元 p14);
diverges from the reference exactly on the underivable analyst rows. Its
workflow (read-complete -> ordered fill at full precision -> self-verify) is
the transplant source for statement_align + prose_growth_read.

| 111 (fable-mode live) | 08-16 17:50 | 37.1m ✓ | 76.9% | +438 / -476 | 51 | Fable-mode served 104/118 answered (all self-verified) but the runner's fresh draw served fewer than validation (154), a CFI proof SIGN-FLIPPED (cash identity off by exactly 2x — the fingerprint), and +437 entered the NCA chain. The read layer is proven; the VARIANCE around it is the enemy. |

**THE ASSEMBLY (post-update evaluation, run offline — the owner's diagnosis
that the agent lacks Fable's post-update self-evaluation, mechanized):** base =
run 105; apply the FROZEN validated fable-mode reads (156 rows, 103/103 vs
answer key, each row checksummed); then evaluate like the clean tester:
attribute every residual by fingerprint (equity +115.8 = 2x57.9 -> OCI sign
as printed p96; NCA -74.9 = exact delta -> 长期应收款 79.87 p95 replacing a 5.0
plug; forecast -539 = 520 PPE check + 19 CF tie decomposed; CFI view 18.9 =
the season-long CFI residual cornered to one detail row); re-anchor the
unreadable PPE roll to the statement-verified ending (orange, true-up);
close the finance-cost identity. **RESULT: 83.9% (best; Model page 93.9%,
valuation tabs 100%), EVERY check row 0 in EVERY year, all 9 statement keys
tie exactly. Deliverable: Dongfang Electric FY25 (agent final).xlsx.**

**NEXT BUILDS (owner directives, recorded):** (1) the post-eval stage as an
in-run agent phase (council transcripts in council/, posteval session Grok #1);
(2) the diagnostic playbook is now TAUGHT in prompts/orchestrator.md — extend
as new fingerprints are learned; (3) LEARNER REFOCUS: the learner must spend
its budget on the rows the update-grade read CANNOT self-verify (run
fable-mode against the PRIOR year's docs in the learn leg; rows that fail to
serve there = the company's HARD SET — Driver/PPE for DFE, different
elsewhere — and get recipes/locations/reasoning in the memory tab; rows that
serve easily get nothing). Generic by construction: difficulty is discovered,
never assumed.
**08-16 (day) — THE COLD-RUN TEST OF THE TEACHING.** Two of the three next
builds landed and validated before dispatch:
- **Sign rule (fablemode.py)**: the checksum tie is now SIGNED — comp ~ +pv
  serves AS PRINTED (rows legitimately flip: OCI, 投资损失 以-号填列, net CF
  section totals), comp ~ -pv serves flipped (page prints expenses positive
  where the model stores negative). Replay over the 156 frozen reads: 148
  identical, 8 sign-family diffs — four reproduce the assembly's hand
  corrections exactly (Raw 167/258/259/261); the fifth, **Raw!U219 CFI, was a
  NEW catch: the deliverable held +10,587.3 where the filing prints
  -10,587,324,054.32** — confirmed by the reference AND by CFO+CFI+CFF+FX=
  ΔCash tying to 0.0000 only with the negative. Deliverable corrected in
  place (both copies), read-back verified.
- **Learner refocus (cli.py cmd_learn)**: fable-mode probe of the PRIOR-year
  report (checksum = v23) discovers the EASY set (served value ties known
  v24); identification budget concentrates on the discovered hard set.
  Fail-open (probe serves nothing -> unchanged behavior). Bridges/recipes
  untouched.
- Deliverable rescored post-fix: 85.7% whole model (Raw sheet unscored — the
  U219 fix improves the statement tie, not the count), Model 112/114 (98.2%),
  Cons + both Fair Value tabs 100%, **Driver 101/138 (73.2%) = the entire
  remaining gap** — exactly what the refocus targets.
- **Cold run dispatched** (chain, branch head 3795b61 = sign rule + both
  playbooks; refocus landed post-dispatch at 11a5f30, so it rides the NEXT
  run). The question this run answers: does the taught thinking close the
  gap unattended?

**08-16 late — RUNS 115/116 AND THE ARCHITECTURE RULING.** Run 115 (all
guards + posteval stage): 76.9% raw, FIRST-EVER cold-run 2025 balance zero,
keys 9/14, Model 86.0%. Post-eval finish of 115 (page-cited, ~40 min):
83.9% / **Model tab 113/114 = 99.1%** (the 1 = flagged dividend definition
row) / balance -0.0 / cash tie 0.0 / net profit 3,831.3 exact — saved as
"Dongfang Electric FY25 (cold run + posteval).xlsx". Run 116
(complete-coverage build): REGRESSION — serve collapse 104->67 (bigger mixed
chunks) + a no-prior read wrote a wrong-scale figure (the checksum WAS the
scale anchor; removing it removed the anchor). Discarded.

**COUNCIL RULING (council/architecture-council.md): INVERT THE ARCHITECTURE.**
Evidence: zero errors all week from checksummed reads; 100% of failures from
heuristic middle-layer writers. Blueprint: Stage 1 read-once extraction
(evidence ledger: table_id/row_ord/col_bind/unit_dim) -> Stage 2
deterministic join (hard gates: prior identity x block-scale invariant x
face authority x unit dimension; ambiguity -> blank) -> Stage 3 whole-page
reader as gap-filler only -> Stage 4 deterministic verify + playbook chase.
Validation: pinned extraction snapshots + adversarial museum (112-116 as CI
negative tests) + canary contract — vision never in the local pre-flight
path. Day 0 (DONE): WRITE FIREWALL — allocation, closing loop, reviewer
auto-apply behind config flags, default OFF.

**08-30 — RUN 7 (pipeline, full DFE FY25) AND THE EVIDENCE LAW.** First
full run with freeze + executive report: freeze held 124 assumptions,
exec report composed 10 bridges (0 refused, 13 corrected). GATE REFUSED
— balance off 52,197, traced to the decimal: stage-4's set_input
OVERWROTE a proven serve (Raw!U60 15,193.8 -> note-gross 53,546.5,
UNFLAGGED, trying to move a failing check) and wrote the prepayments
note figure onto held-for-sale (Raw!U72, counted twice by an inherited
model double-count). 38,352.7 + 2x6,892.7 = 52,138. Root cause: the
write firewall had closed every heuristic writer EXCEPT the objective
loop's own set_input — a raw write channel with only a prose citation.
FUNDAMENTAL FIX (pipeline/writegate.py, generic all models): the
evidence law — no write without a ledger row; proven = the row also
ties the cell's prior; one row one claim; proven serves protected;
unproven values land RED, never clean; a write that worsens a failing
check reverts. Run-7's two writes pinned as museum exhibits (refused).
Sense check wired to the Evaluator (0 verdicts last run — needed
computed values, not caches). All suites green. Awaiting owner's
go for run 8.

**08-30 — RUN 8 (evidence law in force) AND THE ONE-HOME LAW.** The
evidence law HELD: no fabrications, assets side exact to the decimal
(U60 kept its proven 15,193.8; U72 honestly blank), sense check fired
(19 verdicts). GATE REFUSED at -12,124: ONE cell — stage-3's no-prior
reader wrote the section total (12,182.5, already PROVEN into Raw!156
from the same page) into blank component row Raw!U153, doubling
non-current liabilities. Red-flagged, so honest — but balance is
objective #1. Root cause: the one-row-one-claim law existed only at
the loop door; stage-3's no-prior path could still give a served
figure a second home. FIX: the one-home register (writegate
claimed_values/no_prior_duplicate) now guards stage-3's no-prior
serves; also fixed the worsen-revert reading got/expect (it was keyed
on a field checks never had — armed now). Both pinned as museum
exhibits. Remaining known: Driver flag budget 24% (serving depth, not
a law break) and the -58.6 equity residue. Awaiting go for run 9.

**08-30 — RUNS 9-11 AND THE FINAL LAWS.** Run 9: -59 (one cross-document
double-home, OCI as FX) -> one-home register made document-agnostic.
Run 10 stopped by owner mid-flight; the stop exposed that a duplicated
register had left stage-3's guard silently dead — unified to ONE
function. Run 11 (full stack): 2025 balance to 1.0 — the cancelled
treasury shares' disclosed ZERO was unservable (join skipped zeros; a
dash-nil is not a number). Forecast-year 10,679 = the analyst's own
model rebasing (pre model already failed -539); gate correctly scopes
checks to <= target year. FIXES: zero-serve allowed on prior-tied rows;
THE DASH-NIL LAW (a standalone nil directly before the full-precision
tying prior, on a served face page, never a subtotal) — tightened twice
by its own dry-run audits (20 -> 5 -> 3 zeros, final 3 all verified
correct); reclass sweep live (Driver segments at total growth, designed
plugs honored); embedded hardcodes flagged as key drivers; flag budget
counts RED only. All museum-pinned.

**08-30 — RUN 15: DELIVERED.** First gate-passing delivery of the
pipeline era. Balance check 0.0; total assets and equity EXACT to the
disclosed decimal; treasury zero served by the dash-nil law; segments
backed out per the owner's reclassification recipe with the analyst's
own plug rows; 124 assumptions frozen; every law in force. Run 14→15
ruling: the flag budget measures NEGLECT — adjudicated reds (where-
looked documented) are findings. Loop budget 90; 130 calls. Remaining
honest state: 26 unexamined reds spread under the per-sheet bar, net
profit 3,831.1 vs 3,831.3 (0.2 component rounding), forecast-year
checks (analyst re-forecast items) reported not gated. The trajectory:
52,197 → 12,124 → 59 → 1 → 0.

**08-31 — RUN 16 AND THE CASH-CONE LAW.** All-years gate live. The loop
used forecast_audit correctly but placed the movement of CASH ITSELF
(=V133, the CF's own output) back into the CF — a circular reference;
place_flow's legality check had only validated the TARGET. The cycle
poisoned the evaluator and the last-resort plug wrote a garbage
-47,554 (red). Gate refused (cycle + budget) — correctly. FIXES, all
museum-pinned: (1) the cash-cone source law — only true BS lines place;
anything wired through the CF block is the RESULT, refused with
teaching; the audit labels such rows "[RESULT of the CF — never place
this]"; (2) place_flow inherits set_input's laws: cycle -> REVERTED,
worse gap -> REVERTED; (3) plugs withheld on gaps > half the asset
base (structural break, analyst ruling) and on a broken actual base.
Driver unexamined reds 27% -> 18% (adjudication working; bar 15%).

**08-31 — RUN 19: DELIVERED, ALL OBJECTIVES.** Every check row, every
year: 0 failures, 0 cycles. 2026-2030 closed by attribution + ONE
honest plug (V113 -9,592, orange, analyst-noted). Attribution window +
look-law worked: loop reached the reds (6 adjudications), Driver under
the neglect bar. Run 19a crashed on a syntax break that a backgrounded
unread bench let through -> tools/bench.sh now gates every dispatch
with an exit code. DFE FY25 COMPLETE. Pivot to CLP genericity per the
overnight mandate.

**08-31 — CLP RUN 1 (genericity door-finder) AND FOUR LAWS.** The stack
largely ADAPTED: reclass sweep found the Aus segment block unaided and
applied the owner's recipe; 33 embedded hardcodes flagged; plugs
correctly withheld on a broken actual; per-sheet neglect gates fired.
Doors found + closed: (1) the dash-nil law zeroed the YEAR HEADER off a
prior-period document -> year-like priors never nil-prove, prior-period
docs banned as nil evidence, the axis band (rows<=3) excluded from all
sweeps; (2) exec report crashed on 'Model' -> the whole report stack is
now spec-driven (sheets, prior/target/next letters per sheet, primary
from key_rows); (3) ROAFNA 2024 -1,264 pre-existed -> the
inherited-break law: a check failing identically pre-update is the
analyst's standing item, reported not refused (worsening still
refuses); (4) ROAFNA 2025 (-859, ours) + SOC sign-absurd forecasts are
DATA hunts the loop owns under the evidence law in run 2.

**09-01 — THE FABLE-BY-HAND SESSION (owner mandate: do it yourself,
then teach the agent).** Starting from run-204's quarantine (2025 right,
forecasts wrecked): restored ALL forecast columns to the analyst's
formulas, then fixed every 2026+ symptom at its 2025 CAUSE: false-nil
Basic Tariff (97.1 = 95.8 x printed +1.4%), fuel clause -1,043 (was
stale 370 asset), TSF tie 2,786 (fund-arithmetic gap flagged), NFA roll
re-anchored (accdep actual -143,161), SoC depreciation basis 5,832 (not
the HK segment 5,965), segment D&A wrong-column serves (China -915 /
Aus -2,795 — the model's own prior column proves the mapping), India
221 (was 4,108 wrong line), one-offs bridge -441 (was 2024's 94), CF
compositions re-served from the printed CF statement (WC, non-cash,
net-interest, financing incl PCS redemption -3,933/issue +3,872 and the
sign-flipped short-term -1,768), RE plug removed for the true items
(PCS fold 9,815 = 5,943+3,872 red). RESULT: balance 0 EVERY year
2019-2030 (inherited ROAFNA 2024 reported), pretax/NP/OP/EPS/CFI exact
to print, CFO/CFF definition-bridged (interest classification, both
years), 2026 NP 11,632 vs analyst 11,819, ZERO new eval errors, new
executive _REPORT composed. Deliverable: CLP Model FY25 (Fable).xlsx.

## 2026-09-01 (overnight) — THE FABLE-DRIVE: Fable 5 drives the agent's own tools (owner's 3-part directive, part 3)

Fable 5 replayed the loop by hand through the REAL tool interface
(scratchpad fable_run/drive.py, no LLM) on the deterministic dry state.
RESULT with ~30 actions: balance 0 every year 2019-2030 (both checks),
ALL keys exact to the by-hand answer key (rev/OP/NP/EPS/CFO/CFI/CFF/
equity/recurring NP), CF statement marked via write_backout composites,
Final sheet 0 diffs vs answer. The experiment's real product was the
autopsy of every wrong deterministic serve met on the way. Root causes
fixed (all generic, museum-pinned, 92 exhibits green):
- TIME-SIGNATURE LAW (join): wide-row read-across only when the next
  number continues the time series (ties prior2) or is the delta —
  kills segment-axis column errors (CN got HK's 52,048).
- EXACT-BEATS-CLOSE (join): a 0.5%-band tie is refused when the prior
  is printed exactly elsewhere — kills definition mismatches (contracts
  36,972 tying total revenue 37,097) while restatements still tie.
- UNCHANGED-LAUNDERING GUARD (bound tables): a non-face serve equal to
  the row's own prior marked stale cells served-clean — refused.
- HEADER-SITE LAW: input-site redirects and the reconcile prior index
  skip year-header rows (a '31 Dec 2024' date line wrote 31 into AI2).
- INPUT-TWIN RESOLUTION (reconcile): multi-home priors resolve to the
  single non-formula home (D&A living on Driver AND SOC now serves).
- SIGN-BLIND EVIDENCE (writegate): printed 5,832 proves -5,832; the
  model owns the sign convention.
- provenance.json now persisted per run (who served every cell);
  find_line accepts name/query/label; write_backout documented in the
  prompt; scorecard no longer promises "auto-plug closes this" while
  plugs are withheld.
Post-fix dry run serves Aus 34,191 / MI -879 / PCS -199 correctly BY
ITSELF; replayed drive on the new base: keys all match, tripwires
collapsed from 5 chains to 2 singletons. Remaining answer-key diffs are
segment-detail back-outs (the loop's red queue), not serve errors.

## 2026-09-01 — THE FABLE-TRANSPLANT (owner: "pull ur skill and ur thinking process into luna agent")

Three transplants, museum-gated (92 green):
- ORDER OF WORK doctrine in the prompt — the exact drive sequence:
  actual-balance by decomposition first; then walk each statement whole
  via the PAGE VIEW; bridge unprinted splits from printed total-parts;
  trace_serve surprise numbers before believing them; tripwires last,
  bulk-verdicted once the actual year ties.
- find_line {"page": N} PAGE VIEW — the whole extracted page in print
  order (my reading method with zero transcription risk; runs 21-25
  proved Luna must never transcribe — this shows machine-extracted
  numbers only).
- trace_serve tool — the in-run autopsy: who served this cell, from
  which page, by which method; loop now receives the serve provenance.
Dispatching Luna on the fixed pipeline: the test of whether the floor
is now high enough for the cheap brain.

## 2026-09-01 (night) — THE WORK-QUEUE INVERSION (council build)

Owner: "we have been stuck for quite some time — make it a solid build —
call in the council." Three independent council seats (architect,
red-team, operator) reviewed the inversion against the run-210 evidence.
Verdicts: ADOPT-WITH-CHANGES / build-machinery-first-gate-the-LLM /
concrete build plan. Built per synthesis:

- pipeline/workqueue.py: machine-driven stage 4. Phase-0 auto-resolve
  (GUILTY diffs, stale-composite + red-formula rewrites — existing
  gates, earlier). Cards rendered lazily from LIVE state; SERVE /
  TRIPWIRE / PLUG kinds; candidates carry their own indictments
  (vintage, wide-row, loose-tie-vs-exact-home, proportion, kinship,
  small-value warnings) + positional COMPANION generator (prior found
  at slot k of a same-labelled twin table -> current read at slot k)
  + residual-hypothesis lines on plug cards. Every answer executes
  through the loop's existing guarded tools; flag is every card's
  default; not_disclosed adjudications are documented on the cell
  (examined red, the move-on law). Circuit breaker, call cap, wall
  clock; STAGE4_MODE=loop is the byte-identical rollback.
- Offline calibration on live CLP state (no LLM):
  * always-flag (production default): SAFE — machinery keys exact
    (OP 14,272 / NP 10,468 / CFI -14,328), 2025 closed, reds examined.
  * oracle (answer-key answerer): 25/45 serve cards carry the exact
    truth (was 6/43 before the companion/pool/ordering fixes).
  * strict auto-serve test: 16 right / 9 wrong -> auto-serve is NOT
    shippable; the wrongs are definitional twins (group-vs-segment
    'Operating costs', group associates into a segment sheet) — the
    genuine judgment residue. The "empty middle" is real and small.
- Museum: 96 exhibits green (4 new queue contracts: garbage answer ->
  default; serve lands with citation; out-of-world decoy never offered;
  no-LLM = machinery baseline). Bench GREEN.
NEXT (owner go required): dispatch ONE run, STAGE4_MODE=queue — Luna's
cheap A/B on ~40 cards vs the always-flag baseline, guards bounding the
damage. If Luna ≈ default or worse: route cards to a stronger engine or
leave them red (red-team verdict).

## 2026-09-01 (later) — RUN 211 (queue-mode, Luna) + the receipts build

Run 211, STAGE4_MODE=queue: NIGHT-AND-DAY vs run 210 — Luna answered 28
cards: 5 cited writes, 15 reasoned abstentions (it READ the warnings),
5 bulk tripwire verdicts, 2 plug refusals; zero repeats, zero spirals;
guards caught its 2 bad picks. Gate refused on ONE item: forecast years
flat 1,645 — traced to the 2025 equity gap closed by a one-cell PLUG
where the truth is a printed two-cell split (RE 84,367 + NCI/PCS 9,815).
HONESTY NOTE: scoring exposed that the Fable-drive file's own forecast
was wrong despite balancing (36 tripwires mass-approved unverified) —
the by-hand answer key remains the only correct forecast.

Built (council follow-through, museum 98 green):
- COMPONENT cards ("the receipts"): for a failing check, each numeric
  leaf's printed candidates are PROBED — the card shows 'residual
  -5,293 -> -1,421' / 'CLOSES the check' measured, not guessed; landed
  fixes re-deal the card (sequential receipts); plugs dealt strictly
  last. Candidate generators: prior-tie + positional companion +
  residual-completion (cur ± residual printed) + same-line co-printed.
- VERDICT RE-VERIFICATION: ERROR_FIXED is rejected by code while the
  cell still computes a sign-absurd value (my own drive's sin, now
  impossible for anyone).
- cap fix: the SERVE flood can no longer truncate COMPONENT/TRIPWIRE/
  PLUG items out of the queue.
Offline greedy test: ROAFNA terminal plug 1,190 -> 39; forecast gap
1,645 -> 196. Remaining: Final!99's receipt is guarded by the
proven-value law (surfaced loudly, analyst's call). Dispatching the
next queue run with owner go.

## 2026-09-01 — RUN 212 + the garbage-card fix

Run 212 (queue): Luna again flawless in conduct — 7 cited serves, 16
reasoned abstentions, honest verdicts, refused both plugs. The receipts
failed to land: the residual-completion generator offered TAUTOLOGICAL
closers (cur±residual matched to any printed number — 'Property under
development -> -4,606'), which the evidence law rightly refused; the
real receipt (9,815 co-printed with prior 6,063) ranked below them.
Exactly the red-team's garbage-card prediction, observed live.
FIXED: completion generator DELETED (evidence-grounded candidates only:
prior-tie / companion / co-printed), sign-flip warning, evidence
quality outranks the probe in offer ranking. Offline greedy: Final plug
5,320 -> 1,448, ROAFNA 1,190 -> 39, forecast gap 1,645 -> 196. Museum
98 green. Redispistched.

## 2026-09-01 — RUN 213 + THE PROVEN-PLUG LAW

Run 213 (queue): forecast gap down 1,645 -> 109/yr; Luna landed the
AI97 receipt (=9,815, exactly the answer key) and honestly refused both
plug cards. AUTOPSY: the residual-loop/endgame had plugged 1,421 into
SHARE CAPITAL 23,243 — a value reconciliation had PROVEN from print —
so 2025 "balanced" while every forecast year inherited the distortion.
NEW LAW (museum 99): a PROVEN cell is never a plug site — refused in
t_plug_residual AND excluded from diagnose's eligible-site list (the
terminal ladder inherits). Offline: all cosmetic plugs now refuse; the
gate shows the TRUE residual (-1,448 = 1,043+343+35+27, three SoC
account mis-mappings) instead of plug-balanced fiction. Deliver-refused
-but-honest beats balanced-but-wrong (owner's no-wrong-unflagged rule);
the receipts cards can now ask about the SoC leaves directly.

## 2026-09-01 — RUN 214 + BLOCK-CONTEXT KINSHIP

Run 214: fully honest state achieved — proven-plug law refused every
cosmetic plug (share capital, RE, NFA all protected); Luna refused both
plug cards; true residual exposed: Final -1,448 / ROAFNA -1,113.
AUTOPSY: -1,448 closes to -35 with ONE receipt — SOC Accounts!AI7
fuel-clause closing -1,043 (printed p37 'Fuel Clause Account (FCA)'
[1043, -370], exact prior tie) — which the card RANKED FIRST but
wrongly indicted "label unrelated" ('Closing balance' row under the
'Fuel Clause Recovery' section header), steering Luna to a warning-free
coincidence (343 'Cost').
FIX: block-context kinship — the section headers above the row count
as the row's identity. The receipt is now candidate A, warning-free.
Museum 99 green. Redispatched.

## 2026-09-01 — RUN 215 + LOAD-BEARING CARD PRIORITY

Run 215: same honest -1,448 — the fuel-clause card never got DEALT: the
serve cap ranks by |prior| and the 370-sized load-bearing cell lost its
slot to big rows that feed nothing. FIX: tier law applied to cards —
load-bearing rows (the lb trace) outrank size in SERVE priority.
Verified offline: the AI7 card now deals, candidate A = -1,043
(warning-free after block-context kinship), serve lands, residual moves
by exactly 1,413. Museum 99 green. Redispatched.

## 2026-09-01 — RUN 216 AUTOPSY: THE RE-ASK

216's fuel-clause card WAS dealt — Luna picked candidate D, the
one-home law refused the write, and the card was ABANDONED with the
clean candidate A still on it (invisible because card outcomes were
unnamed — observability shipped in 217, which is superseded and
cancelled). FIX: a guard refusal RE-ASKS the card once — refusal
reason shown, refused option removed (what a human does). Museum 100.

## 2026-09-01 — THE BISECT (owner: "rework the agent, compare past runs")

Every commit of the era scored by the SAME offline machinery run
(flag-default, no LLM) against the by-hand key:
  9d0cff7 pre-queue baseline : 2025 off 5,378 | fc 4,519 | keys 2/11
  35640bb autopsy serve laws : 2025 off 5,285 | fc 4,737 | keys 4/11
  a8bdf07 the work queue     : 2025 = 0      | fc   196 | keys 7/11  <- best
  9392b86 garbage-card fix   : 2025 = 0      | fc   196 | keys 7/11
  9a355c0 proven-plug BAN    : 2025 off 5,320 | fc 4,772 | keys 7/11  <- THE REGRESSION
  ...     (three commits inherit it)
  cfecf58 probe-tested plug  : 2025 = 0      | fc   196 | keys 7/11  <- restored
VERDICT: the owner was right — the blanket proven-plug ban (9a355c0)
broke the balance objective for runs 214-218. It is replaced by the
probe-tested plug (unproven sites first; a proven site only when the
live experiment shows zero forecast damage; lands RED). Everything
else the era added is neutral-or-better: the queue itself took the
machinery from keys 2/11 to 7/11 and closed 2025. Current head =
best machinery state of any commit, ever.

## 2026-09-01 (late) — GENERIC LAWS FROM THE 196/424 TRACE (no dispatches)

Owner rulings applied: no patches, teach thinking, all offline (zero
LLM cost). Root-caused via the asymmetry experiment (nudge each 2025
input, see which move forecasts but not 2025) and fixed as laws:
- ROLL-BASE CONSISTENCY: every typed actual must be reproduced by its
  own forecast formula pointed back one year; stale base inputs
  red-flag into the queue (found ROAFNA -1,190, India!7 -642 unaided).
- UNCHANGED-COMPONENT + pair-outranks-identity + all-identity-refused
  (composites): a literal printed this year with no YoY pair may stand.
- NARROW-LINE LAW (composites): a composition component is a =<3-number
  line; wide segment/series rows are never YoY sources.
- CURRENT-DOC-ONLY POOLS: unknown-vintage docs (the restated FY24 AR
  defeats every numeric vote) are context, never evidence, once any doc
  proves current. PRIOR-VINTAGE TABLES (slot-side vote per table)
  excluded everywhere.
RESULT (all offline, scripted answerers): CF composite =2254-235-15 now
rewrites to =1860-194-15 EXACT to the answer key; ceiling run: 2025
balance CLOSED at 0, forecasts flat 424 (remaining roll bases whose
values are unprinted — back-out/cards work), India flag budget 16%
vs 15%. Museum 100 green throughout.

## 2026-09-02 — FIRST FULLY-GREEN OFFLINE STATE (floor AND ceiling)

The last three generic laws (all experiment-based, zero cell-specific
code):
- ROLL-BASE ANCHOR: when a roll base misses its typed actual with
  NOTHING stale, the model's own arithmetic lacks a flow — anchor the
  largest unit-coefficient term so the roll reproduces the disclosed
  closing (transactional: kept only if forecast residual mass drops).
  Second idempotent pass after the queue (later writes shift bases).
- THE COEFFICIENT PROBE (forecast plugs): a plug sized on the +1
  assumption DOUBLED the residual (true coeff was -2). Bump the row,
  measure the check's response, size by it; unwind uses the recorded
  actual delta. Hold-tuner experiment retired (never proved).
- Ordering: causes (anchors) before residues (plugs).
RESULT: museum 100 green; offline gate DELIVERS at BOTH bounds —
always-flag floor (no LLM: balance all years, keys 6/11, 108 red /
47 orange, honest) and oracle ceiling (balance all years, one +10
orange plug). Remaining ceiling->floor gap = the card answers: Luna's
A/B is now a pure brain measurement, machinery fully proven.

## 2026-09-02 — RUN 219: DELIVERED (the first machine delivery of CLP)

Gate PASSED on GitHub with Luna. Balance ALL years 2019-2030 (Final +
ROAFNA; ROAFNA 2024 -1,264 is the analyst's own pre-existing item,
inherited & reported). Keys 6/11 exact vs the by-hand answer key
(revenue/OP/NP/EPS/CFI/DPS); misses = recurring NP, CFO, CFF, equity,
assets — all card-answer territory. 65 red / 40 orange, all documented.
33 LLM calls (cents). Luna-on-cards A/B verdict: Luna ≈ the flag-
default floor (its 15 adjudications added no keys over machinery) —
the red-team fallback stands: route the ~10 judgment cards to a
stronger engine, or the analyst rules them in Excel. Next: the
genericity test (a drastically different model from another team).

## 2026-09-02 (night) — THE RECOMPOSITION LAW + CEILING 10/11

Owner mandate: sustain root-cause->law->offline-proof->push; CLP bar =
ceiling green; then DFE genericity. Built tonight (all offline, museum
103):
- RECOMPOSITION LAW (composites.recompose_cell, hooked after the
  same-shape rewrite): the old recipe's comparatives locate its printed
  section; members refresh with THIS year's printed signs; NEW
  ingredients join (incl. one-number lines, invisible to joins);
  beneath-materiality items that grew join; the analyst's exclusions
  are respected (noted); section extension bounded by the one-home law.
  CF rows now EXACT to the by-hand key: =517+319+63-460-46,
  =-111+919-5+532-465-88, =12508-10672-1768-233-381-3933+3872.
- NOTE-COLUMN DISCIPLINE in candidates() (notes are positive small
  ints; '[30,-104,-278]' no longer pairs the note) -> =-159-975-104
  and =197-1418 exact.
- THE CHANGE VOTE: combos with fewer identity mappings outrank page
  majority (a real update changes numbers) — r119's true pair beat two
  note coincidences.
- FINAL CLOSER: terminal ladder re-runs before the gate (late keytie/
  anchor writes re-opened ROAFNA by 748). EXAMINATION CLOSER: every
  unreached red gets its documented look (flag budgets now honest).
OFFLINE: CEILING gate green, keys 10/11 exact (miss = recurring-NP
one-offs bridge, printed only on non-face pages, documented red — per
owner ruling flag is the deliverable). FLOOR gate green, keys 9/11.
Dispatching CLP (authorized run 1 of 2); DFE genericity test next.

## 2026-09-02 (overnight) — THE GENERICITY TEST: BOTH MODELS GREEN

DFE FY25 offline (pinned run-19 vision ledger — the new pinned-snapshot
path, since DFE's statements are scans a client=None rebuild cannot
read). DFE stressed the laws differently and each break became GENERIC:
- PAIRED DIFF (terminal): compensating guilty cells apply as one
  transactional batch (lone writes revert each other forever).
- CONTRARY-EVIDENCE: a GUILTY verdict must survive its own experiment —
  a mapped diff that WORSENS the check on probe is a wrong map, listed
  as CONTRARY, never applied, never blocks plugs (two DFE rows both
  "guilty" of the same junk 61.58).
- COEFFICIENT PROBE in t_plug_residual (actual-year plugs): size by the
  site's measured response, not the +1 assumption (a DFE plug doubled
  the residual; museum 199 exhibit re-pinned to the better law — the
  largest site now closes correctly instead of reverting).
- Ledger.from_json schema-tolerant; pinned_ledger param on update().
RESULT: DFE floor DELIVERED (gate green). CLP re-validated with the
DFE-born laws: ceiling 10/11 green, floor 9/11 green — ONE codebase,
zero company-shaped changes, both models green. Museum 103.

## 2026-09-02 (morning) — LIVE RESULTS: DFE DELIVERED, CLP 220 pre-law

DFE FY25 LIVE (Luna + vision, current head): **DELIVERED** — all six
check rows pass EVERY year, 22 red / 46 orange, all documented. The
genericity thesis holds live: one codebase, two structurally different
models (EN scheme-of-control multi-sheet vs CN scanned-statement),
both delivered.
CLP run 220 REFUSED (-1,063 / flat -316): it ran commit aa73644 —
dispatched BEFORE the three DFE-born laws (paired diff, contrary-
evidence, coefficient-probed plugs) which are exactly the closers its
residuals needed. Current head is offline-green for CLP (ceiling 10/11,
floor 9/11); one confirming CLP dispatch awaits the owner's go (the
overnight 2-run authorization is spent).

## 2026-09-02 — THE GATE LOOP (owner ruling: the gate feeds back, never just fails)

Run 221 (current head, live): refused with run-220's signature — Luna
picked candidate B on the fuel-clause card again; the all-flag floor
delivers, so a confidently-wrong serve is strictly worse than
abstention, and the plugs rightly refused to paper over it. The owner's
architectural reading: the gate was a JUDGE; an analyst's workflow is a
LOOP — unbalanced after update -> go back, take the wrong entry out,
redo the repair, check again.
BUILT: the closer suite refactored into repair_round() (roll-base
re-anchor, forecast plugs, sign-flip terminal, final closer — all
idempotent) + gate_once(); on refusal the failure feeds back: stage-4
serves (journal-watermarked either side of stage 4, so repair writes
are never mistaken for Luna's) are taken back in tiers — red first,
then all — the repair suite re-runs on the corrected state, the gate
judges again; a round that does not reduce total check residual is
undone; one last repair-only round; bounded. Taken-back cells stay RED
with the note and their candidates.
OFFLINE: Luna-sim (run-221's wrong pick) now DELIVERS via the loop
("2 stage-4 serves taken back, repairs re-run -> gate PASSED"); CLP
ceiling 10/11 green, floor 9/11 green; DFE floor green; museum 103.

## 2026-09-02 — RUN 222: CLP DELIVERED LIVE (gate-loop head 8265145)

Luna + the full law stack, live on Actions: **DELIVERED**. Balance every
year (ROAFNA 2024 -1,264 = the analyst's inherited standing item,
reported not gated); keys 10/11 EXACT to the by-hand answer key
(revenue, OP, NP, EPS, CFO, CFI, CFF, equity, assets, DPS; the one
miss = recurring NP's one-offs bridge, printed only on non-face
highlight pages, documented red); 60 red / 51 orange; 32 LLM calls,
8 card adjudications; the first gate passed outright (no loop round
needed). With DFE FY25 delivered live the night before, BOTH models
now deliver live on one generic codebase — the department bar.

## 2026-09-02 — THE OLD-ESTIMATE BLOCK (owner: "paste the old estimate before the update")

Owner's read of run 222's _REPORT: WHAT'S CHANGED / OLD columns mostly
empty. AUTOPSY: timing was already right (the archive IS the pre-update
model, copied before any write) — the values were lost to the
no-cached-values disease once more: report_only loaded the archive
data_only=True, and a manual-calc model caches nothing, so every
formula estimate read as empty (only the one hardcode survived).
FIX: (1) report_only loads the archive WITH formulas so _pre_val
evaluates the old estimates; (2) snapshot_estimates evaluates formulas
from the formulas workbook, taken before any write; (3) the executive
report renders WITHOUT a client too — _deterministic_summary (spec key
rows -> snapshot + mini P&L, every flag -> attention) so offline/dry
deliveries carry the same OLD-vs-NEW table. RESULT: OLD block filled
(revenue old 90,417 vs actual 88,018; OP 14,873 vs 14,272; NP 11,115
vs 10,468 ...); CLP floor green, DFE floor green, museum 103.

## 2026-09-02 — RUN 223 AUTOPSY: THE GUARDS ATE THE JOURNAL

Run 223 (head a96e0cd, report fix aboard): refused with the 220/221
signature and NO gate-loop tier line. AUTOPSY: the gate loop's take-back
read the undo journal — which the error/collapse guards POP while
unwinding. Live, the collapse guard popped through the stage-4 serves
(offline the guards had nothing to pop, so the Luna-sim passed). The
take-back saw an empty slice and silently did nothing.
FIX (generic): an append-only write ledger (writer.log["writes_all"])
that no guard consumes; the gate loop watermarks and reads THAT.
Museum 104 (exhibit: the ledger survives guard pops). Luna-sim: red
tier no help -> all tier takes back 2 serves (mass 21,859 -> 10,279) ->
final repair -> gate PASSED. CLP ceiling 10/11 / floor 9/11 green; DFE
floor green.

## 2026-09-02 — RUN 224 AUTOPSY: THE CLEAN-SLATE RULE

Run 224 (head c4aaa79, ledger fix aboard): the gate loop ENGAGED this
time — red tier took back 4 serves (mass 21k -> 5,255, kept), all tier
took back 2 more and got WORSE (5,255 -> 10,279), restored; final
repair could not close: 2025 -1,413 (fuel clause back at prior — Luna
picked C after D was refused; third wrong pick in three runs on the
same card) + a +352/yr forecast ramp + one unexamined DRIVER ROLL.
AUTOPSY: taking back the serves but KEEPING the anchors/plugs that
were solved AGAINST them leaves a state worse than the floor.
FIX (generic): the CLEAN-SLATE RULE — with the serves, every repair-
suite write made after stage 4 is taken back too (reverse order, from
the append-only ledger); the idempotent suite re-solves from a clean
base. Museum 104; CLP ceiling 10/11 / floor 9/11 green; DFE green.

## 2026-09-02 — RUN 224, SECOND AUTOPSY: THE FAITHFUL REPLAY

Built the council's pinned-serves path (pinned_served=provenance.json:
the live run's 201 stage-3 LLM serves replay offline). Faithful replay
of run 224 — live ledger + live serves + its exact 32 card picks —
DELIVERS offline, first gate, no loop needed. So the picks were not the
wedge. The one live-only stage left: the RESIDUAL FREE LOOP (mode
'queue' = cards + 10 free Luna actions). Its run-224 log: five plug
attempts BEFORE the repair suite ran, one landing over a proven value
(ROAFNA!AI29) — the red-team's random-walk verdict, observed live.
RULING: 'queue' = cards + machinery, no free loop; 'queue+loop' is the
explicit opt-in. The live path now equals the path that delivered the
faithful replay. Museum 104.

## 2026-09-02 — RUN 225 AUTOPSY: THE ARITHMETIC ARBITER

Run 225 (cards + machinery, no free loop): refused -1,063 / flat -316.
FAITHFUL REPLAY (tools/replay_live.py: live ledger + live provenance
serves + live card picks) REPRODUCES it exactly — the live run is now
fully debuggable offline. Live-vs-replay cell diff: ONE cell.
ROOT: the fuel-clause card is a genuine DEFINITIONAL FORK — p168 prints
both 'Fuel clause account' [20, 370] (the BS receivable, same-sign
exact prior tie) and [20, -1043]; p37 prints the FCA fund [1043, -370].
Luna picked the BS line (B=20) four runs running; the model row is the
fund balance (A=-1,043). No label settles it; the model's own checks
do: A closes 1,413 of the failing residual, B 350, C 27, D worsens.
LAW: THE ARITHMETIC ARBITER — SERVE cards probe every candidate against
the failing checks and print the effect; the unique largest improvement
is marked "IMPROVES MOST — best fit to the model's own checks"; the
prompt teaches the cascade (best fit > exact tie > positional read).
Cards also state "prior tie EXACT" explicitly (it was never said).
Auto-serve re-audited and stays FORBIDDEN (the only tight-unique card
on the live state was wrong). Museum 104; CLP ceiling 10/11 / floor
9/11 green; DFE green.

## 2026-09-02 — RUN 227 AUTOPSY: A CLAIM NEEDS A HOME

Run 227 (head 666cbff, arbiter live): refused, same signature (-1,063 /
-316). THE ARBITER WORKED — Luna picked A (-1,043) on the fuel-clause
card for the first time in five runs — and the WRITE GUARD refused it;
the re-ask fell back to B (20). Faithful replay reproduced the exact
refusal text: "every ledger row carrying this value already serves
another cell — one row, one claim". The holder: Final!72 'Fuel clause
account' (BS) — a stage-3 no-prior read of a FORMULA row that
_write_served correctly SKIPPED as derived. The number never landed in
the model; the claim register still counted it. A phantom claim by an
unproven read blocked a proven serve (exact prior tie, best fit).
Second defect found on the way: ties_prior was sign-sensitive on the
printed number while find_evidence was sign-blind — the FCA fund row
[1043, -370] did not "tie" prior 370, so even a free claim would have
landed red instead of clean.
THREE LAWS (writegate/run/orchestrator, museum 105):
- A CLAIM NEEDS A HOME — _write_served marks every entry homed/unhomed;
  only homed figures sit in the one-home register.
- TIES ARE SIGN-BLIND — like the evidence finder; the model owns signs.
- PROOF OUTRANKS ARRIVAL — judge_write returns EVICT when a proven,
  prior-tied write meets a figure whose only homes are UNPROVEN; the
  loop reverts those homes to their pre-serve value, red-flags them
  ("re-homed to X"), releases the claim, lands the proven write clean.
  A PROVEN holder still blocks. Loop serves now record conf 4 when
  proven, 3 when red, plus their home coordinate.
Also: tools/replay_live.py lost card picks for sheet names with spaces
('SOC Accounts!7') — fixed; the replay is now faithful for every card.
PROOF: faithful replay of 227 -> DELIVERED (SOC Accounts!AI7 = -1,043
WRITTEN, first gate); CLP floor DELIVERED; DFE floor DELIVERED; A/B of
the ceiling script on pre-fix vs fixed code: identical keys (the low
ceiling score is the rebuilt oracle script, not the laws). Keys are now
measured by scratch keys11.py (9 resolvable of the 11): replay-227
7/9 vs run-222 delivered 6/9 (total assets now exact).
Operational lesson: a "floor" run needs stage4_answerer=default — with
client=None and no answerer stage 4 is SKIPPED entirely (cost one false
alarm today).

## 2026-09-02/03 — RUN 228 DELIVERED, AND THE FORECAST WAS NEVER MEASURED

Run 228 (head 071373c) DELIVERED: balance all years, keys 7/9 measured,
report OLD block filled, fuel-clause A written first gate. Then the
owner's question "why is it not performing well" led to the finding of
the day: the FORECAST YEARS were collapsed in EVERY run on record —
2026 operating profit 4,867 (228), 2,492 (222), 623 (219), -1,648
(206, Aug 31), -39,573 (offline at 9d0cff7) vs the by-hand key 15,550.
Balance and keys passed because a wrong driver and a bent fuel-clause
balance cancel. Nothing in the bar, the gate, or my grading looked at
the forecast; the collapse guard logged "18 rows collapsed" in every
log and the report's own sense check wrote "ERROR FOUND: collapsed
forecast" in 228. Grading omission = mine.
ROOT (chain): (1) on Aug 19 I placed the FY24 annual report in
disclosures/FY25/ as the "last-year map"; (2) by design the agent read
no titles/dates — vintage was a numeric vote; (3) the vote returned
'unknown' for the FY24 AR (restated comparatives); (4) the serving
stages asked the weak test (prior only) and ran before the vote — 45
serves from the FY24 AR in 228, 124 in 210; the fuel-clause charge 2
(FY24 AR p274, "read across") replaced 44.3 and drove SoC revenue.
LAWS SHIPPED:
- fd6cd4a THE VINTAGE LAW, decided once (classify_from_targets right
  after stage 1; one strong test vintage_ban at all 11 sites; pinned
  serves bound; verdicts serialized). Replay 228: 2026 OP 15,673 vs key
  15,550; NP 12,418 vs 11,632. 9 forecast rows still collapse (cash
  chain) — open.
- DOCUMENT IDENTIFICATION (owner ruling 09-03: "the agent must be able
  to identify the period of the report — not a folder, not a count"):
  pipeline/docid.py — brain card per document (type, company, period
  end, months, comparatives) > printed-period reader (EN/CN: year
  ended / from-to / months ended / 年度报告 / 报告期 / 截至...止) >
  numeric vote as backstop+tripwire (contradiction -> UNKNOWN, flagged).
  Verdict binds every stage through the vintage register; _REPORT lists
  "DOCUMENTS RECEIVED" with how each was used. All six local documents
  (CLP x4, DFE x2 incl. both FY24 ARs) identify correctly offline;
  replay 228 and DFE floor DELIVER. Museum 107.
OWNER AUDIT ("other mechanical identity decisions?"): yes — company
identity (unchecked), statement-face pages (caption word lists),
model key rows / label dimensions (synonym lists). Plan: one brain
"reading" step (what am I holding, which pages are the primary
statements, which company) with numeric ratification of every claim.
BAR CHANGE PENDING (owner): forecast health in the gate (collapse ->
take-back loop) and on _REPORT page one.

## 2026-09-03 — THE READING STEP: brain judges, code verifies (owner ruling)

Owner: "is there any other mechanism deciding what a thing is
mechanically, without the brain? we can't work like that." Audit found
three more; all four now follow one pattern — the brain answers a
bounded card, code verifies the answer numerically, contradiction is
flagged, and a deterministic reader is the offline floor:
1. WHAT DOCUMENT (docid.identify_documents) — brain card > printed
   period > numeric vote as tripwire.
2. WHICH COMPANY (docid.issuer_check) — the issuer named by the most
   current documents is the company; a current document naming
   another issuer is set UNKNOWN and flagged. The floor considers every
   name printed (an announcement's cover names the exchange first).
3. WHICH PAGES ARE THE PRIMARY STATEMENTS (identify_statement_pages)
   — brain names consolidated P&L/BS/CF/segment pages and parent-only
   pages from the contents; a named page is adopted only if its
   numbers ratify against the model's prior year (ratify_page_scales);
   parent-only pages lose face authority. Caption tagger = the floor.
4. WHICH ROWS ARE THE MODEL'S KEY OUTPUTS (identify_key_rows) — brain
   reads each sheet's labels; a named row replaces the synonym-pattern
   pick only if it carries numbers in the year axis.
Legitimately mechanical (arithmetic a person also does): scale
ratification, prior-identity triangulation, restatement diffs, balance
and cash ties, vision checksum. Museum 108.

## 2026-09-03 — THE ROLLOVER INVESTIGATION (owner teaching, not a gate)

Owner: "I taught this already" — the tripwire existed (sign-flip
chains -> a verdict card) but was a DEAD END: Luna answered
'suspicious' five times in run 228 and nothing followed; and the
collapse test (near-zero / sign flip) never fired on a -69% move. The
owner's rule: compare the actual surprise (2025A vs 2025E) with the
forecast move (new 2026E vs old); a move against the surprise, far
beyond it, a sign flip or a collapse means go back and investigate —
sometimes it is genuine, so the agent must judge, not fail the run.
BUILT (pipeline/rollover.py, museum 109):
- estimate_baseline: the analyst's 2025E and 2026E per row, before any
  write. strange(): the proportionality test (AGAINST THE ACTUAL, OUT
  OF PROPORTION, SIGN FLIP, COLLAPSED).
- dossier(): trace the forecast cell to the actual-year inputs this
  update changed; PROBE each (restore the analyst's value, measure the
  share of the swing recovered); provenance shown.
- CARD ROLLOVER (queue order: after COMPONENT, before TRIPWIRE):
  revert:X (restore + red-flag + ERROR_FIXED verdict), justified
  (verdict with reason), not_sure (flag forecast, SUSPICIOUS). Default
  = not_sure. Tools t_rollover_revert / t_rollover_flag.
- _REPORT page one: ROLLOVER CHECK table (estimate, actual, old/new
  forecast, test, verdict) for key rows + every strange row.
Replay 228: 12 rollover cards render on the live state with probed
culprits (e.g. gas consumption: actual -11%, forecast +17% AGAINST;
A recovers 35%, B 24%); delivered with defaults. The brain's answers
are first exercised live.

## 2026-09-03 — RUN 229: DELIVERED (head 37a7a63) — the reading step live

First live exercise of the brain on the new cards. GOOD: all four
documents identified (brain + printed agree), company = CLP Holdings
Limited, statement pages 20/23 ratified, ZERO serves from the FY24 AR
(45 in run 228), fuel clause 44.3 / FCA -1,043 right, 2026 OP 15,177
vs key 15,550 (run 228: 4,867), 2026 rows off >5%: 96 (was 122),
cells 71.6%. BAD: keys 4/9 — on two ROLLOVER cards Luna answered
'revert' and the tool obeyed on PROVEN actuals (Final!AI76 bank loans
9,673 = key; Final!AI21 net finance costs composite = key), dragging
OP to 13,812. Design gap, mine: the card offered revert on every
changed input. Also the key-row verifier dropped the brain's correct
Final picks (formula rows cache no values) and a ROAFNA row surfaced
as 'net profit' on the report.
FIX (museum 109): PROVEN IS PROTECTED on rollover cards — a proven
served input, or a constants composite whose every literal is a
proven served figure, is shown ("✔ PROVEN — never reverted; the
forecast's own driver/assumption is stale") but never offered; the
tool refuses too. Proof status reads the cell's FILL (red = unproven;
orange = derived, protected) — the writer's flag list mixes both
colours and first hid the composite's protection. Formula rows count
as numeric for key-row verification.
Faithful replay of 229 on the fix: DELIVERED, no reverts, keys 7/9,
2026 OP 15,661 vs key 15,550.
THE CASH-CHAIN FLIP, root-caused: Aus!AI25 'Finance costs' (prior
-471) was served -6,608 by RECONCILIATION from AR p186 'Net book value
at 1 | 6,608 | 471 | 914 | 7,993' — a fixed-asset note row where 471
sits mid-row by coincidence; the wrong actual pushed 6,541 into the
model's 'Others' residual (Driver!112), which rolls into every
forecast year (net financial costs +4.7k, NP 2026 +50%). Sized on
229's own serves: reconciliation reads from WIDE rows (>=4 numbers)
were wrong 20 of 27; narrow lines right 32 of 39. Also p186 carried a
'cf' face from caption propagation, and the brain's page map only
added pages, never demoted stray ones.
TWO LAWS + ONE MORE (museum 109):
- TIME-SIGNATURE LAW in reconciliation: a statement line is current |
  prior (+ note ref) — a row with >=4 numbers is a note grid / five-
  year table / segment matrix, never reconciled positionally.
- THE BRAIN'S MAP IS THE AUTHORITY: once brain-named statement pages
  ratify, caption-propagated pl/bs/cf tags elsewhere in that document
  are demoted (kept within one page of a named statement).
- SMALL-PRIOR LAW: with wide rows gone, priors -23/-12/-10 found
  label-unrelated 'homes' ('Short-term deposits', 'Joint ventures',
  'Meters'); a prior under 50 must have label kinship with the model
  row; a material prior is its own identity.
Replay 229 on all three: DELIVERED, keys 7/9, cells 72.8% (best on
record), 2026 rows off >5%: 101 (228: 122), cash chain restored (2026
cash 1,283 vs key 2,058; was -3,559). DFE floor DELIVERED (7 wide
rows, 7 coincidences refused). OPEN: 2026 OP 18.3k vs key 15.6k — the
SoC revenue/fuel-mix chain (HK Sales!AJ4 transfer-from-fuel-cost
20.2k vs 16.0k; gas/coal forecast volumes) = the assumption-freeze
question the owner must rule on; India!AI24 'confirmed unchanged' 105
(material-size coincidence) noted.

## 2026-09-03 — RULE 2 AT THE GATE + THE RESIDUAL DISCOUNT (owner)

Owner: "rule 1 is balance, rule 2 is the keys — why did it fail rule
2? attention span?" Not attention: the keys were RIGHT before stage 4
(bank loans 9,673, net finance costs composite — both the key's
values), two late rollover 'revert' answers overwrote them, and the
gate checks balance only — rule 2 was enforced mid-run (key tie) and
never verified at delivery. Also the key tie in 229 aimed at the wrong
rows (the key-row verifier bug, fixed) so it could not rescue OP/NP.
Delivered file: keys 5/11; the fixed replay: 9/11 (misses: recurring
NP one-offs bridge; CFF off by 9).
BUILT (museum 110):
- RULE 2 AT THE GATE (keytie.key_snapshot / key_violations): every
  key proven-printed before stage 4 (pinned print, or a figure on a
  current statement face) — re-armed after the key tie — must still be
  so at the gate; a proven key moved to a value printed nowhere REFUSES
  the run and feeds the same take-back loop as balance (its distance
  counts in check_mass). A move to ANOTHER printed figure is a
  definition question (never refused); a never-proven key is flagged,
  never gated.
- THE RESIDUAL DISCOUNT (rollover.dossier): the model's residual rows
  (=total - SUM, 'Others') absorb anything and roll forward, so
  reverting almost ANY input "recovered the swing". The probe now runs
  twice — as is, and with every residual row frozen at its current
  value; the frozen share ranks and the card says "recovery through a
  residual is not evidence".
Proofs: replay 229 DELIVERED (rule 2 armed on eps/revenue/equity
before stage 4; re-armed after key tie), keys 7/9 (checker's 9),
rows-off 101; DFE floor DELIVERED.

## 2026-09-04 — RUN 230: REFUSED (head 9b200d8) — three causes, one cell each

Refused by rule 2 ("KEY investing cash flow was proven -14,328, now
-16,216 — printed nowhere") after the balance gate failed (mass
15,481). Faithful replay reproduces it. Causes:
1. THE CALL BUDGET: Luna answered 24 serve cards (229: 11); the 40-call
   cap was spent before the equity-fold COMPONENT card (Final!99) was
   dealt — it ran "(default)", never asked; balance failed at 3,872
   (the PCS fold). FIX: load-bearing COMPONENT cards are ordered before
   the serve flood; CALL_CAP 40 -> 60.
2. THE TAKE-BACK LOST THE KEY TIE: the clean-slate loop reverted every
   repair write incl. the key tie's CFI back-out, and repair_round never
   re-tied — rule 2 then refused, correctly. FIX: key_tie runs inside
   repair_round (idempotent) on every gate-loop round.
3. KEY ROWS AGAIN: the brain named Final!20 (EBIT) as 'operating
   profit'; the verifier used the data_only workbook (formula rows read
   as empty) and had no numeric check. FIX: formulas workbook + a named
   row's PRIOR must tie the pinned panel's prior for that key.
Replay 230 on the fixes with the live picks (fold card still
'not_disclosed' = never asked live): keys 7/9 (OP/NP now proven-
printed after the key tie), balance still 3,872 (the fold). With the
fold receipt answered as in run 229 (the answer the live run was never
able to ask for): DELIVERED, first gate, keys 7/9. Museum 110.
Owner: "why only 7/9 with the correct stuff?" Full 11 keys on the fold
replay: 8/11 — recurring NP (one-offs bridge, known), CFO 21,859 vs
22,848 and CFF -5,401 vs -9,803 (NEW vs 229). Cause: the cash-flow
composites (AI118/119/135/136) stayed at last year's literals /
were half-rewritten because the constants law found "no face line"
— the 230 ledger had only 9 face pages in the AR (229: 55). THE
PAGE-SPACE BUG (mine, from 09-03's "brain's map is the authority"):
the brain names PRINTED page numbers; the code took them as PDF
indices, "ratified" note pages that happen to tie priors, and
demoted the real P&L/BS/CF pages. FIX (museum 110): a named page is
adopted only if its OWN ROWS identify that statement
(face_from_row_labels) AND it ratifies; printed numbers are
translated to PDF pages via the footer; demotion never touches a
page whose rows identify a statement. The 230 ledger was pinned
after demotion, so the faithful replay cannot show this fix — the
next live run does.

## 2026-09-04 — RUN 231: DELIVERED (head cbfec1b) — keys 9/11 live

Gate loop needed two tiers + final repair, then PASSED. 53 LLM calls,
0 drained (the fold card was asked and answered fix:0). Rule 2 armed
on 4 keys pre-stage-4, +3 after key tie. KEYS 9/11 LIVE (misses:
recurring NP one-offs bridge; total assets +661). Two rollover
reverts (Final!AI57 cash composite, Aus!AI14) both ended at the key's
values after the loop. 2026: OP 15,419 vs key 15,550; NP 11,199 vs
11,632; cash -3,612 vs 2,058 (cash chain still open). Rollover page
one: 37 strange rows, 10 with verdicts (12-card cap), 25 flagged
only. Flags red 114 / orange 93; cells 70.0%. Statement pages: 8/11
AR pages ratified via the page-space law.
Owner: "total assets is off by 661 yet it balances?" Both sides off by
the same 661: receivables +1,134 and investment securities -622 held
at last year's split (red, composition ambiguous), NFA +149 (a
different printed split); minority interests +1,446 (the brain served
the printed NCI, a wider definition) and deferred creditors -785
(held). Balance compares totals; rule 2 never guarded total assets
because it was never proven-printed (CLP's HK-format BS prints no
'Total assets'; only the five-year table does).
THE PRINTED-SUBTOTAL LAW — built, museum-tested (111), NOT WIRED:
keytie.printed_subtotals / subtotal_tie pin every same-column
subtotal row to a face line (comparative ties the prior; noun-level
label kinship; leading pair of a multi-year table allowed) and back
the delta out into an UNRESOLVED (red) component, bounded at 10%,
transactional vs the checks. On run 231's replay, inside the gate
loop, it compounded wraps across rounds (AI60 -1,134 then -2,205),
landed a back-out on SOC Accounts!AI9, and left equity wrong ->
refused. Unwired; the stable head delivers. Wiring = its own session:
run it ONCE after the loop settles (not per round), never absorb
across sheets, and re-snapshot rule 2 after.
Kept: keytie._leaves expands SUM ranges (the range's interior rows
were invisible to every back-out search).

## 2026-09-04 — OWNER RULINGS: BS totals are keys; the analyst's order

1. TOTAL ASSETS and TOTAL LIABILITIES+EQUITY are KEYS (pinned in
   key_panel.json from the five-year table 238,644 | 233,713; key rows
   in spec.yaml). First attempt (unresolved-only absorbers for ALL
   keys) regressed OP/NP/CFO/CFI ties (their absorbers are orange, not
   red) -> reverted. What holds: red components absorb FIRST, a key
   row is never another key's absorber (the total-assets tie had
   wrapped CASH round after round), SUM ranges expanded. Result on the
   231 replay: assets tie via AI60 (receivables -1,732 orange), the
   balance check then EXPOSED the liabilities side off by 785 (the
   two-sided error had hidden it); L+E as a key backs the 785 into the
   red deferred-creditors line (= the by-hand 8,363). Keys 9/11 on both
   231 and 229 replays (misses: recurring NP bridge; CFF off by 9).
2. THE ANALYST'S ORDER in the queue: SERVE -> ROLLOVER -> COMPONENT ->
   TRIPWIRE -> PLUG, with the balance cards' calls RESERVED
   (reserve_for_balance) so the flood can never starve them; rollover
   cap 12 -> 30, key rows first.
Museum 111; DFE floor delivers.

## 2026-09-04 — RUN 232: DELIVERED (head fe993ae) — first gate, no loop

60 LLM calls, 0 drained; the analyst's order held (20 rollover cards
dealt BEFORE the balance receipts; balance cards asked and answered).
Keys: 7/11 at the checker's tight tolerance, effectively 10/11 —
total assets EXACT (238,644, first time live), total equity 107,586
(24 off), CFO 20 off, CFF 9 off (all within the key tie's 0.2%);
recurring NP the known bridge miss. 2026: OP 17,772, NP 13,325, cash
-3,056 (rollover bar, not the key). Rollover page: 48 strange rows —
4 justified, 2 reverted (ROAFNA!AI54, Aus!AI14 = the by-hand value),
14 flagged, 28 beyond the 30-card cap. Flags red 92 / orange 94;
cells 70.7%.

## 2026-09-04 — THE ONE-MINUTE PAGE (owner's report rulings)

Owner on the 232 report: no sense check (the agent's own note), no
rollover table (the mini P&L old-vs-new is the forecast review), and
'gross margin' was linked to Net operating income. Done: sense check
not rendered and not run; rollover block removed from the page (its
verdicts stay in the flags/log); mini-P&L rows are kept only when the
brain's label is kin to the model's own row label (code verifies),
and the deterministic path orders them as a P&L path (revenue ->
profits -> per-share, no BS/CF rows). 'Needs your attention': plugs in
full, reds capped at 30, orange as one count line; the complete flag
list moved to a _FLAGS sheet. Run 232's page: 227 rows -> 70.

## 2026-09-04 — RUN 232 CASH AUTOPSY (owner: "it had the right answer, why give up?")

Cash 2025: the constants law rewrote =4976+23 -> =3905+23 (the BS face
p168, correct). Then phase0's red-composite rewrite re-mapped the
literal 3,905 from the cash MOVEMENT row on p17 ('Cash and cash
equivalents 4,976 | 787 | 3,905' — opening, movement, closing) into
=787+23 = 810; 2026 cash then -3,056; the rollover card for cash was
answered 'justified' by the brain. Two defects:
1. phase0 chose its cells from the writer's FLAG LIST, which still held
   the cell from the stale sweep although a proven law had painted it
   ORANGE. Law: a cell painted orange by a proven law is not red (the
   colour is the truth; the list is history).
2. composites: a literal that already prints as THIS YEAR's figure on
   a statement face must never be re-mapped. Law (already_current):
   the faces vote — 'current' only if a statement line prints it first
   with a different comparative and NO line prints it as a
   comparative (a movement row prints last year's cash first, so 4,976
   stays re-mappable while 3,905 is protected).
Museum 112.
Part 2 — why cash stayed negative after the fix (2026 cash -3,184):
D&A 2026 collapsed to -4.1k (key -9.7k) because the model's residual
'Others' (Driver!19 = total D&A - segments) absorbed 4,636 and rolled
forward. Three inputs fed it: (a) Aus!AI14 amortisation 386 (key
-425) — the brain's revert to -425 was UNDONE by the twin re-anchor
(SOC!AI23 'Transfer to development fund' shares last year's -425 by
coincidence); (b) CN!AI9 D&A -5,727 (key -915) — the bound-table join
paired Hong Kong's number as 'current' against China's prior in the
SEGMENT MATRIX (p178: HK | CN | AU | IN | total); (c) India 0.
LAWS (museum 115):
- TWINS ARE KIN OR LINKED: same prior is not same quantity; labels must
  be kin or a formula must link them; a red cell is never re-anchored;
  cross-script twins (EN model over a CN filing) keep the prior-identity
  rule for distinctive values (>= 10x the twin floor).
- APPEARED FROM ZERO: a forecast that was ~0 and now >= 1,000 is strange
  (the residual's card now fires).
- THE SEGMENT-MATRIX LAW: a table whose rows sum across to their last
  number lists one period per row — never bound as a YoY table
  (tolerance capped at 50 so phone numbers cannot 'sum').
- The rollover dossier walks SUM ranges row by row (the ladder keeps
  the classic walk — expanding it there changed plug choices and blew
  the cash chain on a trial).
- Faithful replays pin only the brain's serves; deterministic serves
  recompute under the current laws (else a replay cannot show a law).
Replay 232 now: CN!AI9 held -840 red (no longer -5,727), 'Others' -251,
D&A 2026 -8,991 (key -9,730), cash 2025 3,928, 2026 -652 (was -3,184),
2027 -6,714 (key 648) — the remaining gap is the fuel-clause/fuel-mix
forecast chain (assumption freeze ruling). DFE floor delivers.

## Run 233 — 2026-09-06, head ba27bb3 — DELIVERED (first gate, 40 min, 60 LLM calls)
Balance every year; keys vs the pinned panel: revenue, operating profit
(14,272 print), net profit, EPS, total equity, total assets, L+E, CFI
exact; recurring NP 10,374 vs 10,909 (one-offs bridge, red); cash 2025
WRONG — held at last year's 4,999 (key 3,928). Reading step: 4 docs
identified, company verified, 17 statement pages ratified, 8 key rows
named by the brain and verified. Rollover: 23 cards; Luna reverted
Aus!AI14 -> -425 (key -476) and India!AI22 -> 85 (key 140), both red.
Forecast: 88 of 217 rows off >5% vs the by-hand key, the fuel-clause /
fuel-mix chain (gas 174k TJ vs 148k; fuel cost -20.8k vs -17.3k) —
awaiting the owner's freeze-vs-rebase ruling; cash 2026 4,013 vs 5,277.
CASH AUTOPSY (the fifth form of the cash fault): the constants law wrote
Final!AI57 '=4976+23' -> '=3905+23' correctly; the ROLLOVER card for
Driver!100 ('Cash') OFFERED it as revert:B because the composite read as
unproven — the '+23' (the analyst's own carried adjustment) matched no
proven figure — and Luna took it (run 232 answered 'justified' on the
same card). LAW: A REWRITE IS PROVEN BY WHAT IT CHANGED — with the old
formula in hand only the changed literals need proof; the machinery's
own 'COMPOSITE REWRITE (constants law)' note is the same proof. Museum
115 (exhibit 2c'). Faithful replay of 233: pre-fix reproduces the revert
(cash 4,999); fixed code -> not_sure, cash 2025 3,928, delivered.
Also: the report's snapshot unit label now reads the model's spec
('HK$ millions'), not the DFE 'RMB mn' literal.
Replay note: the replay's rollover card SET differs from live (30 vs 23
cards on different rows) because the pinned serves land in one pass and
the collapse guard fires differently (ROAFNA!AI71 restored to -1050 in
the replay; live's 0 matches the key). End states differ in 3 cells only.

## Run 233 review (owner, 2026-09-07) — notes for the analyst; the unflagged tariff
Owner: "quite good"; misses mostly flagged; ONE unflagged — the 2025
basic tariff (HK Sales!AI13) held at last year's 95.8 (key 98.0) with
no flag. Cause: the dash-nil sweep zeroed it from a stray '–', the
collapse guard restored the prior (auto-disproven) and REMOVED the flag,
leaving a 'proven zero' note on an unconfirmed prior. LAW: a guard's
restore is unconfirmed by definition — RED with a plain note.
Owner's note rulings: (1) notes ONLY on highlighted cells (144 agent
notes sat on plain inputs); (2) short, plain words — no 'tier-3',
'QUEUE-DOCUMENTED', 'stage-2.5 bound-table join'. Built pipeline/notes.py
(plain_note templates + hygiene pass at delivery, analyst notes and
_sheets untouched); writer.write attaches a note only with a flag.
Replay 233: 0 agent notes on plain cells, 145 flagged notes ≤ 98 chars,
tariff red 'Not found in the documents. Kept last period's figure.',
cash =3905+23 orange, snapshot label 'HK$ millions'. Museum 116.
Roll-base explained to the owner: the forecast's own roll (opening +
movements) re-applied to last year should reproduce this year's actual;
a gap means an input the roll uses was not updated — fix the input,
not the actual.

## 2026-09-07 — owner rulings from the run-233 review (structure, forecast colours)
1. THE STRUCTURE IS THE MODEL'S: a roll-base gap is closed by backing
   out the LEAST CONFIDENT INPUT of the roll (proven > orange > plain >
   held-at-prior/red), as a traceable formula — never by overwriting the
   formula cell or the typed actual. A tie at the bottom is flagged red
   on the tied inputs, nothing guessed; all-proven = definition question
   (watch-listed). Linear solve by two bumps (adj = -gap/slope).
   FOUND: the reference regex read 'AI9' as sheet 'A' cell 'I9', so the
   old law never saw unqualified inputs (fixed; three sites).
2. FORECAST YEARS CARRY NO ERROR FLAG: what a law finds strange in a
   forecast row goes on a WATCH LIST (writer.watch -> _FLAGS 'Forecast
   rows to check'), never painted; the cause is flagged in the actual
   column. Collapse guard, sign-flip terminal, roll-base mismatch, gate
   take-backs and the brain's flag_cell all route through it.
3. BLUE (BDD7EE) is the one forecast-year colour: frozen assumptions,
   auto-probe holds, one-off holds, forecast plugs. Report: blue tier as
   a count on page one, full list on _FLAGS.
Replay 233: AJ column = 30 blue, 0 red/orange; AI = 65 red / 46 orange;
4 roll-base back-outs fired (SOC Accounts!AI40 +20, Final!AI87 -11,
HK Sales!AI17 +0.2, India!AI8 -232), 9 rows all-proven -> watch list;
no 2024A-formula -> 2025A-hardcode structure change (0 before, 0 after).
Cash 2025 3,928; forecast cash still the fuel-chain ruling. Museum 118.

## Run 234 — 2026-09-07 night, head 1d762c6 — DELIVERED (first gate, 60 LLM calls)
The owner's final CLP check. Balance every year. Panel keys: revenue, NP,
EPS, OP (14,272 print), CFI, total assets, total equity, L+E exact (the
three 'not located' keys are model-definition composites: cash +23, CFO,
CFF). Cash 2025 = 3,928 (orange, 'Backed out from the disclosure (annual
report p168): 4976→3905'); the rollover card for Driver!100 answered
not_sure — the proven composite was not offered. Basic tariff held at
95.8 and RED ('Not found in the documents. Kept last period's figure').
Today's rules live: AI column 63 red / 51 orange; AJ column 30 blue and
NO red/orange; 0 agent notes on plain cells, longest note 131 chars;
0 rows where a 2024A formula became a 2025A hardcode; report label
'HK$ millions'; 30 forecast rows on the _FLAGS watch list. Roll-base
back-outs fired on SOC Accounts!AI40, HK Sales!AI17, Final!AI87
(re-solved across repair rounds; ends =((0)+(-11))-(774) after the L+E
key tie), ROAFNA!AI18. Forecast: 89/217 rows off vs the by-hand key —
the fuel chain (owner: leave it to the agent, no ruling); cash 2026
2,556 vs key 5,277 (positive, no longer collapsed). Recurring NP still
10,374 vs 10,909 (one-offs bridge). Verdict vs the owner's three
objectives + today's rules: MET. Next: DFE FY25 on the same head.

## Run 235 — 2026-09-07 night, head 83bc3b2 — DFE FY25 DELIVERED (first gate, 29 LLM calls)
Documents identified (2024 AR = prior, 2025 AR = current), 11 key rows
named by the brain and verified. Balance every year. Panel keys 6/10:
revenue, EPS, total assets, total current assets, CFO, cash exact; net
profit (4,012 after tax vs 3,831 attributable) and total equity (45,234
ex-NCI vs 48,168) are the model's own definitions (the by-hand key holds
the same); CFI -6,151 vs -10,587 and CFF 659 vs 5,102 are REAL misses,
both red. CFF root cause: 'cash received from investors' (the A+H share
placement, 5,236) and its 'of which: minority investors' sub-line (124)
both printed 110.0 last year -> two input homes for one prior -> the
reconciliation refused the line -> tier-3 held the parent at growth
(124). LAW: two input homes with one prior are told apart by the
disclosure line's LABEL (equal wins, else unique kinship) — museum 119.
CFI: the investing components (investment purchases/receipts) mapped to
other lines; not fixed tonight.
RECLASSIFICATION (the owner's check): the recipe fired as taught —
Driver rows 6,7,11,12 and 39,44,45 held at the total's growth (orange),
residual into the designed plug rows 13/46. BUT the 2025 AR prints the
segments under the NEW cut with restated 2024 comparatives (p207: 煤电
24,491.6/20,257.1; 水电 3,902.8/2,854.1; 气电 5,627.6/7,110.3; 风电
18,224.2/12,288.0; 新兴产业 7,708.8/6,643.7 — restated priors that no
longer tie the model's). The by-hand restated the prior column and
mapped the currents; the agent's growth-holds put 21,492 into 'Others'
(by-hand 13,896) and the mix drives 2026 NP 3,421 vs the by-hand 5,013
(-32%). PROPOSAL for the owner (not built — 'less change'): a RECLASS
card — the brain maps each held segment to a row of the disclosure's
segment table (cross-script), code verifies both years' totals and
restates the prior column with a logged restatement.
Structure: 0 rows where a 2024A formula became a 2025A hardcode; notes
plain; forecast columns carry no red/orange.
Interim: DFE 1H25 FLOOR (offline, real documents) DELIVERED — both
half-year reports identified, Raw financials 1H panel bound (AS/AT), 85
served; Model/Driver/Cons have no half-year panel the discovery reads
(Driver's H124/H224/H125/H225E block is not a year run) and are left out.
No quarterly panel anywhere -> a 1Q25 run refuses with 'nowhere to land'
(guard added so Q never lands in the 1H panel). Run 236 = DFE 1H25 live.

## Run 236 — 2026-09-07 night, head 0c7f8fc — DFE 1H25 DELIVERED (1 LLM call)
The first interim run of the rebuilt agent. Both half-year reports
identified (2024-06-30 prior / 2025-06-30 current); the 1H panel bound in
Raw financials (AS/AT); Model, Driver, Cons, Fair Value have no half-year
panel and were left out. 82 served (revenue 38,151, net profit 2,061,
cash 26,342 read from the interim statements), 87 stale -> 85 held at
growth (orange), queue 2 items. FINDING: every BALANCE-SHEET row was
'not found' — an interim balance sheet compares to the last YEAR-END
(total assets 156,365 | 142,009 = the FY24 column), not to the 1H24
column the run tied against; total assets stayed at 1H24's 131,570.
LAW: in an interim run the model's last annual column is a second home
for a printed comparative (spec 'annual_prior_axis' -> reconciliation
home index; museum 120). Replay pending. No quarterly panel exists in
the DFE model -> 1Q25 not dispatched (the run would refuse: nowhere to
land); the owner decides where quarterly figures go.

## 2026-09-08 small hours — the DFE annual's cash-flow statement was never walked
Replay of 235 with the label tie-break alone changed nothing: the
consolidated cash flow statement (PDF p101) was not a statement FACE —
no caption tagged it, the brain's page list did not resolve to it — so
the reconciliation never walked it; only the bound-table join touched
its lines. LAW: a page that proves itself (its own rows read as a
statement AND it ties the prior year at one scale) is adopted as a face
before the brain is asked (museum 121). Replay 235 on 41419bf: p101=cf
adopted, 127 rows served (was 108), the share placement 5,236 read,
CFF 5,695 vs print 5,102 and CFI -11,192 vs -10,587 (both red; the net
change in cash ties the by-hand to 0.4 — the remainder is component
shifts between borrowing/repayment and investment lines). Also adopted
p5=pl (the highlights table reads as a P&L by its rows) — watch for
one-home conflicts. 2026 forecast unchanged: the reclassification
mapping (see the RECLASS proposal) drives the NP gap.

## Run 237 — 2026-09-08 small hours, head 50a0fa7 — DFE 1H25 DELIVERED (1 LLM call)
The interim comparative law live: 106 served (was 82), 63 stale -> 62
held at growth (orange), 1 red. Half-year balance sheet now read: total
assets 156,365.5, cash 31,258.7, inventory 27,286.8; P&L revenue 38,151,
net profit 2,061; closing cash 26,341.8 — all the printed figures.
Total liabilities still held at growth (its year-end comparative did
not tie — one row, open). Caveat for the analyst: the _REPORT snapshot
of an interim run still links the ANNUAL key rows (Model!U4...) which
this run did not touch — the report should follow the run's own axis
(not fixed tonight; note for the deduction pass).

## Run 238 — 2026-09-08, head 23c21fc — DFE FY25 DELIVERED, cash-flow face still lost
Same keys as 235 (CFI/CFF red). The self-proving adoption adopted only
p5=pl: stage 1 had ALREADY tagged PDF p101 'cf' (vision, 22 anchors at
1e6, face from rows), so the adoption skipped it — and the brain's
'parent_only' list, given in PRINTED page numbers, then DELETED that
face (the parent-company statements follow the consolidated ones two
pages later). LAW (f552568): a page that ratifies against the model's
priors keeps its face whatever the brain called it — a parent-company
statement cannot tie consolidated priors. Museum 121. Run 239 = the
rerun on f552568.

## Run 239 — 2026-09-08, head f552568 — DFE FY25 DELIVERED (31 LLM calls)
The cash-flow statement walked at last: 127 rows served (was 108), the
share placement 5,236 read into Raw financials!U221. CFI -11,257 vs
print -10,587 and CFF 5,771 vs 5,102 — one ~670 component sits in the
financing block instead of investing (net cash change ties); both red
for the analyst. Other keys: revenue, EPS, total assets, current assets,
CFO, cash exact; NP / total equity = model definitions. Reclassification
as in 235 (growth holds; RECLASS card proposed). Colours: Driver J 27
orange / 19 red, forecast columns blue only; 0 structure changes.
Night total: CLP 234 MET; DFE FY25 235/238/239 delivered (CF face and
share placement fixed across the reruns); DFE 1H25 236/237 delivered
(interim panel + year-end comparative); 1Q25 not possible (no quarterly
panel in the model). Laws shipped tonight: 8 commits, museum 121.

## 2026-09-08 — the owner's rulings from the DFE review (built, proven offline, no reruns)
Rulings: (1) plug only the LEAST CONFIDENT input, never a proven value;
(2) the 30x guard is a suggestion, not a gate; (3) a model row that is a
subtotal of printed lines (Wind aggregate) is summed, not flagged, when
the prior year proves the pattern; (4) 0 means 0. Investigation first
(no rerun): the Raw financials tab is a Wind export — 27 of 166 rows are
Wind aggregates/splits with no printed line; the cash-flow misses were
2 lines transcribed with one number, the 30x guard killing the share
placement, the bond line printed nowhere, and the ladder plugging a
proven line. Built: the ladder ranks sites by confidence (held-at-prior
/ red, plain, orange) and the agent's own growth holds are leaf inputs
and plug sites (as composites); t_plug_residual refuses a proven site;
the 30x guard serves and red-notes on a kin map, plain on an exact-
label face map, drops only prior-only coincidences; the gate's
MAGNITUDE check skips exact-label face reads (1H25 finance costs 45 ->
-0.4 is the disclosure); a prior-proven composition is a plain SUM
(unflagged); CJK kinship reaches containment ('应收票据' ⊂
'应收票据及应收账款' — the word-overlap path had blocked it); the
self-proving page adoption skips pages that tie < max(3, best/3) priors
(parent-company statements). REMOVED after over-firing offline: an
'aggregate law' (82 coincidental windows) and a 'nil law' (zeroed real
lines with label variants / lost comparatives) — 0-means-0 needs the
prior-year statement read, which the prior-doc vision aborts on; left
open. Control: committed head delivers the 239 ledger; the refusal
mid-way was the ladder finding no site once proven values were banned
(holds were formulas, invisible to the leaf walk). Final offline:
FY25 replay DELIVERED — 收回投资 plugged 35,262 -> 24,088 (true 25,156),
投资支付 stays 31,456 (read), share placement 5,236 plain, receivables
=SUM plain; CFI/CFF still off ~600 = the bond hold. 1H25 replay
DELIVERED — total liabilities 110,962 read (the page-2 continuation of
the balance sheet adopted), finance costs -0.38 plain. Museum 122.

## Runs 240 (DFE FY25) + 241 (DFE 1H25) — 2026-09-08, head cb5155b, dispatched together — both DELIVERED
240 (32 LLM calls): total assets now exact 162,674; revenue, EPS, current
assets, CFO, cash exact; NP / equity = model definitions. The cash-check
plug went into the least confident site — the growth-held 'cash from
investment disposals' (39,775 -> 23,949; printed 25,156) — and 'cash
paid for investments' keeps its read 31,456; finance costs 117.69 read
plain; share placement 5,236 plain; receivables =SUM plain. CFI -11,257 /
CFF 5,771 vs print -10,587 / 5,102: the remaining 670 is the bond-issuance
line held at growth (printed nowhere this year; '0 means 0' needs the
prior-year statement read). Forecast 24/85 rows off vs by-hand (the
reclassification mix; RECLASS card still proposed). 0 structure changes;
forecast columns blue only; notes red 24 / orange 49.
241 (0 LLM calls): 149 read plain, 27 held (was 62 in run 237), 0 red.
Every headline read: total assets 156,366, total liabilities 110,962,
cash 31,259, inventory 27,287, revenue 38,151, net profit 2,061, finance
costs -0.38 (the 100x move served plain under its own label), closing
cash 26,342; receivables / payables as plain SUMs of their printed lines.

## 2026-09-08 — "0 means 0" landed (owner's screenshot: comparative printed, current blank)
The model's 'bond issuance' row is Wind's name for the printed line
'other cash received relating to financing' (593.5 last year, blank
this year). Three things stood between the line and a 0: (1) the nil
law only knew a printed dash — a one-number statement line whose only
number is last year's (blank current) and a printed '0' beside the
prior are nil now; (2) the nil landed as a plain write and the ladder
then plugged the cash gap INTO it — a printed nil is now registered as
a proven serve; (3) the collapse guard 'auto-disproved' the zero
because the forecast row growing off it fell to zero and restored the
growth hold — a proven nil is never restored, the forecast row is
watch-listed (the tariff lesson, the other way round). Also: the
composite plug's '{:g}' format left the cash check at -1 and reverted
the plug — full precision now. Replay of run 240 (real output = the
QUARANTINE file; an earlier reading of the stale delivered-name file
misled): nils 0 on 'other financing cash' and 'subsidiary disposals';
investing cash flow -10,587 and financing 5,102 TIE the print; keys
8/10 (NP / equity = model definitions); the cash plug lands in the
growth-held 'investment disposals' at 25,175 (printed 25,156). The
replay's one open check (Driver!139, -51) is a replay artefact — the
live brain closed it in run 240. Owner: no new rules — this is the
existing nil law + key tie doing their job once the nil survives.
Museum 123.

## 2026-09-08 — the true DFE base, and the nil law's one misfire
The base model in companies/DFE/model had been a Luna-updated failure
file since 09-02 (2025 column already overwritten: J8 = 4,876.71 flat,
J19 = J8/I8-1 = 0%). The analyst's original (Dongfang Electric (Old).xlsx:
J8 = I8*(1+U19), J19 = 30% typed) is restored as the base (8299f42); the
wrong file retired. So the 'Driver forecast frozen at 0%' the owner saw
was the freeze law faithfully copying a 0 that only existed in the wrong
base — on the true base the growth cells are typed assumptions.
Runs 242/243 cancelled (wrong base). Runs 244 (FY25, REFUSED) / 245
(1H25, delivered) ran on the true base but with the blank-cell nil
unrestricted: a NOTE page line printing one number equal to a prior
(p239 related-party purchases = 'service charge and others' -88.36;
1H25 p135 '机器设备' = a cost line 27,870) was read as a blank current
cell -> zeroed -> registered proven -> the ladder's evidence fix refused
-> Driver!139 open -> 244 refused. The blank-cell reading is positional,
so it is trusted only on a registered statement face (pl/bs/cf) —
museum 123 (the p239 case). True-base FY25 floor: DELIVERED with 3
genuine nils; 1H25 floor DELIVERED. Re-dispatched as 246/247.

## 2026-09-08 — the plug deadlock (run 244) closed inside the diagnosis
Rule A (plug only after every evidence fix is applied or ruled out) and
rule B (never overwrite a proven value) locked when a disclosure line
disagreed with a cell already proven: apply_diff refused by B, the plug
refused by A, the gate refused the run. The diagnosis now names such a
line a CONFLICT (two readings for one cell — the analyst's call), not a
GUILTY fix, so nothing stays pending and the ladder proceeds to the
least-confident plug. No new rule; the diagnosis stops asking for what B
forbids. Museum 123, bench green, true-base FY25 floor DELIVERED.

## 2026-09-08 — two readings: the brain judges, the check verifies
Owner: "if the agent has two proven values it should hold both and judge
which is better — that is why we use a brain." Built inside the
existing component card: the card already shows the brain a second
printed line for a component and what serving it does to the failing
check; the evidence law had refused the brain's choice outright because
the cell was proven. Now a component-card choice may replace a proven
value when the named check verifiably improves (probe before the write;
the run-39 law still reverts anything that breaks other checks) and
lands RED with BOTH readings in the note (held value + its evidence,
chosen line + its page) for the analyst. No card, or no improvement:
the proven value stays. Museum 124 (exhibit: no card refused; card +
closing check written red; card + worsening check refused). Bench green;
true-base FY25 floor DELIVERED.

## Runs 246 (DFE FY25) + 247 (DFE 1H25) — 2026-09-08, head 4bbb481, the TRUE base — both DELIVERED
246 (32 LLM calls): keys 8/10 — revenue, EPS, total assets, current
assets, CFO, CFI (-10,587.7 vs -10,587.3), CFF (5,101.7 exact), cash all
tie the print; NP / total equity = model definitions. The nil law did
its work: 'other financing cash' and 'subsidiary disposals' 0; the cash
plug went into the growth-held 'investment disposals' (25,174; printed
25,156); share placement 5,236 and finance costs 117.7 plain; receivables
=SUM plain. 0 structure changes; forecast columns blue only; notes red
22 / orange 45. Reclassification as taught (growth holds + designed
plugs); 2026 NP 4,010 vs by-hand 5,013 — the RECLASS card remains the
owner's decision. 247 (0 LLM calls): 152 read / 24 held / 0 red, every
headline right; one nil (AT16, 12.45) came from p9, an MD&A summary
table that self-adopts as a face — note for the deduction pass.

## 2026-09-08 — Fable-vs-Luna cross-check of the half-year (run 247)
Fable read the three consolidated statements of the 1H25 report (text
pages 45/46/49/51) and diffed every printed line against Luna's
half-year column: 148 printed lines carry a current figure, 121 have a
model row; Luna matches on 117; the 4 real misses are two nils (treasury
shares blank -> held 121; subsidiary disposals blank -> held -9.7) and
two Wind aggregate rows (在建工程(合计) = CIP + 工程物资, held at growth
while the printed CIP row itself was read). The nil misses were two
small bugs — the blank-cell branch compared the printed number WITH its
sign (a negative comparative never tied) and an interim run tested only
the half-year prior, not the year-end comparative a balance sheet
prints — both fixed. Verdict on the H1: on the printed statements Luna
is at 117/121 before the fix and every headline is right; the holds are
Wind-only rows.

## 2026-09-08 — a blank line under a different label is the brain's call
Owner: the generic map is number first, label to confirm, then this
year's figure — and a blank is 0; and where the label differs (Wind's
'bond issuance' for the printed 'other cash received relating to
financing') the LLM judges the MEANING, not a table or page rule. Built
that way: a literal label match lands the 0 by code; a differently named
one-number line that prints the row's prior is offered on the SERVE card
worth 0 ('blank this year — 0 if the same item'); the brain's answer
lands as a proven read (code's proof = the prior tie). The two-column
table test and every page-type gate on blanks are gone. Museum 124;
bench green; both true-base floors deliver (floors have no brain, so the
Wind-named bond line stays held there — the live brain decides it).

## 2026-09-08 — the label map survives PDF formatting
Owner: "six characters in the model, the same six with spaces and
formatting in the PDF — will it map?" Spaces inside CJK, line breaks,
punctuation and numbering already normalised; two gaps closed in
norm_label for every label path at once: full-width letters/digits ->
ASCII (NFKC) and a note reference glued to the label ('固定资产 五（二十）',
'Trade receivables (note 12)') stripped. Museum 125 (formatting
exhibit); bench green; true-base floors deliver with one more row
served in each (FY25 128, 1H25 112).

## 2026-09-08 — RULING: no RECLASS card
The owner declines the RECLASS card: it would load the brain further,
and a reclassification may rename items entirely (not the DFE pattern
of same names with restated comparatives). The recipe stands as taught
— untouched segments mapped, recut segments held at the block's growth
(orange), residual in the analyst's designed plug row — and the
ANALYST reclassifies. The reclassified-block holds stay orange and
listed in the report; no forecast-mix repair is attempted.

## 2026-09-08 — PROSE FIGURES (owner rulings): the reader keeps a sentence's figure
Owner: noun + amount (+ growth rate if given) from anywhere in the
report, this year's and last year's; the brain normalises the unit to
the model's, accepting only what sits in line with the previous period's
input; no fixed format rulebook — the LLM reasons over the sentence;
which figures matter differs per company (DFE: order intake; CLP:
tariffs); a figure with no tie lands RED; only model rows drive the
search. Built (pipeline/prose.py): sentences are joined across wrapped
lines and any 'noun phrase + amount + unit word' becomes a ledger line
(channel 'prose'); money is normalised to the base currency unit so the
page-scale machinery converts it exactly like a statement line; a growth
rate or stated prior gives the comparative, so the generic map (number
first, label to confirm) applies unchanged; non-currency amounts keep
their unit word for the brain. On the serve card, prose lines kin to the
row's label appear with the sentence printed and a unit warning; a line
whose own growth implies the model's prior is marked ✔. Measured: +100
to +460 lines per document against 2,500-3,500 table lines; the DFE 2024
report yields '新生效订单' 101,142 (implied prior 86,535), the 2025 report
'营业总收入' with an implied prior that ties the model's 69,695. Museum 126;
bench green; floors deliver (pinned ledgers carry no prose — the live run
is the proof).

## 2026-09-08 — rows with no prior get a label-only card; prose is the second stage
Owner: tables first; prose only for rows still empty, unfound or backed
out — that is the wiring (prose lines never enter the statement walk or
the joins; they surface only on cards, which exist only for open rows).
The one gap: a row the model names but never filled (DFE 'New orders')
had no prior to tie and no flag, so no card and no way for a sentence to
reach it. Now: candidates_for returns label-only candidates for a
no-prior row (prose first, then kin table lines, all warned 'no prior
tie'); build_queue adds a SERVE card for each such empty row that has a
candidate, last in the queue; the brain's pick lands RED past the
empty-row guard (allow_empty). A first fixed cap of 8 was removed at the
owner's objection — the call budget and the balance cards' reserved
share decide. Museum 127; bench green; both true-base floors deliver
(FY25 queue 36 items, 1H25 8, all defaulted with no brain).

## Run 248 — 2026-09-08, head 5547b24, DFE FY25 — DELIVERED but the prose proof did not fire
Delivered, yet no card reached the 'New orders' rows and the bond line
was held at growth again (CFI/CFF keys off, worse than 246). Two causes,
both mine: (1) the tier-3 sweep runs BEFORE the cards and held the
differently named bond line orange, and orange cells get no card — a
row whose prior prints beside a blank current slot now stays RED for the
card; (2) the model's row label 'New orders' is English and the sentence
'新生效订单' is Chinese: label kinship cannot bridge scripts, so the
no-prior row had no candidates and no card — across scripts the current
filing's sentences that carry their own growth or prior are offered and
the brain matches the meaning. Museum 127.

## 2026-09-08 — label-only cards are their own kind, dealt last
Offline check on the true base: the English 'New orders' row now got a
card, but (a) every empty labelled row in the model got one — 60 — and
SERVE-kind cards sort before the rollover and balance cards, so they
would have starved them; (b) across scripts the card showed only the
first four sentences with a growth rate, and the order-intake sentence
was the fifth. Now: never-filled rows are kind LABEL, dealt after every
other card so the budget's remainder decides how many run (no cap), and
a cross-script card lists up to eight sentences that carry their own
growth or prior. Museum 127.

## 2026-09-08 — the serve-card cap is gone; the budget decides
Readiness check for the live DFE annual run, on the run-246 ledger: the
bond line (prior 593.54, printed this year as a blank beside last
year's figure under 'other cash received relating to financing') had
its candidate worth 0 but never got a card — build_queue kept only the
largest serve cards (a fixed cap of 60 minus the rest), and 593 fell
off the list. The run loop already has the call cap, the balance cards'
reserved share and the deadline, so the cap was a second, size-sorted
budget. Removed; the queue returns every card in the analyst's order.
Card proven offline: A = 0 (exact prior tie, improves the checks most).
Bench green.

## 2026-09-08 — run 250 (DFE FY25, head 685b08b) DELIVERED, 35 min; the budget is time
Balance gate passed; key numbers 11/14; net profit off +134.68 red;
CFI/CFF tied by orange back-outs. The two aims missed: (1) the bond
line's card WAS asked and the brain said 'not the specific bond line'
— it read the name, not the number tie; the card now teaches that the
model's own prior sitting on a line makes that line the item's home
this year, whatever the report calls it. (2) 'New orders' was drained:
92 cards defaulted on a 60-call cap while 25 minutes of the hour sat
unused. The call cap and the balance cards' reserved share are gone;
the queue's deadline is what is left of the hour (target 60 min, 3 min
finish margin), and the balance cards are asked regardless of the
clock. Museum 128.

## 2026-09-08 — run 250 was a regression (reds 4 → 14, keys 14 → 11) — cause found
Against run 246 on the same base, ten rows turned red. Six were orange
holds in 246 (tax rate, exchange rate, total liabilities, non-current
liabilities, financial-class operating inflow, interest income): the
blank-beside-prior pre-check (added after 248) tied their priors to
junk across the whole report — '15,000,000' counted as eight digits
for the tax rate 15, '1000元' in a CSR sentence for the exchange rate
1, a shareholder count for total liabilities at 0.1% — so they were
not held, went to cards, and the brain rightly refused the junk. Fix
in nil_current_zero: significant digits only (leading and trailing
zeros stripped) and the tie at the model's own precision (half a unit
of the prior's last decimal). The other four: the bond line (the brain
read the name; card wording taught), and its two key totals (CFI/CFF)
plus the interest-income plug painted red. Museum 129.

## 2026-09-08 — run 252 (DFE FY25, head 04dbbce) DELIVERED, 38 min: keys 12/14, reds 7
Against 246 (keys 14/14, reds 4): the time budget worked — 136 cards
asked, none drained, 28.8 min of the hour offered; 'New orders' is
filled from the order-intake sentence (117,251, red, p10); the six
junk-tied rows are orange holds again. The bond line: the brain now
answered 0 on the reworded card — and set_input REFUSED it, because the
verifier demanded a statement-face tag that vision-read lines never
carry, while the card had shown the line. The verifier now judges the
same evidence the card showed. Its two key totals (CFI/CFF) are the
other two reds. Museum 130.

## 2026-09-08 — no page rule in the nil check; readiness proof before any dispatch
Owner: "these kind of rules will make the agent unable to adapt to other
kinds of statements." The 'statement faces only' guard inside the nil
check was the safety from before the test carried its own (precision,
significant digits, label kinship for the sweep) — removed; where a
line sits no longer matters. Runs 251 and 253 cancelled by the owner
("can u test before running"): the floors replay with default answers
and never exercise the brain's answer path, where the verifier bug
lived. tools/readiness.py now answers named cards the way the brain is
expected to, on a live run's own ledger, and proves the cells land —
part of the bench before any dispatch. Museum 130.

## 2026-09-08 — replays no longer pin the live run's own card answers
Readiness on run 252's ledger refused the New orders write: "this cell
already holds a PROVEN value" — the pinned provenance carried the live
brain's own card serve for that cell, so the replayed card met itself.
Worse, the floors had been scoring the live brain's answers as proven
instead of re-deciding them. Stage-4 products (card-adjudicated,
objective-loop notes) are dropped from the pin; only the reading
stages' serves replay. Card refusals now log their reason.

## 2026-09-08 — run 254 (DFE FY25, head 8ba8d27, owner's go) DELIVERED, 35 min
Keys 12/12 (the panel identified 12 keys this run, 14 before — not the
same denominator), reds 6 = 246's four (dividend, adjusting factor, net
profit 134.68 off, short-term borrowings plug) + the two intended: New
orders 117,251 from the order-intake sentence and the bond line 0, both
red for confirmation. CFI/CFF tie plain. 134 cards, none drained.
First run where both offline-proven cells landed live.

## 2026-09-08 — the key count is code's; the net-profit key was mixed
Owner: "i thought the key numbers are all written in the rules." They
are — the pinned panel (10 printed figures) tied 10/10 in 246 and 254,
8/10 in 252. The report's '14/14' and '12/12' were the brain's prose
(the prompt example said 'X/14'); the report now prints code's tally.
Finding: the panel's 'net profit' held the attributable print (3,831.30)
against the total's prior (3,287.53), so the model's total-net-profit
row was flagged red every run as '134.68 off' while correct against the
printed total (3,965.98). Repinned to the total; 'net profit
attributable' added as its own key. Floor: the false red is gone.

## 2026-09-08 — run 254 autopsy: the walk reads the whole report; last year's report gives the prose tie
Owner: "are there any other problems in the last run?" Yes: (1) the
cash line 'proceeds from investments' was held at growth and plugged by
14,601 to close the cash check, although the summary table on p20
prints it with its comparative tying the model's prior exactly — the
walk only entered statement-face pages. The walk now reads every page
of the current documents, statement faces first (first claim wins);
the prior index's 300-row cap is gone. (2) the dividend stayed at prior
(1,366.32, 'not found') although this year's report states 1,832.93 —
no label rule links '现金分红' to '派发现金股利'; last year's report
states the same noun at the model's prior, which proves the noun
(owner: "read last year's report for the tie") — a prose candidate
now carries that proof. (3) hydro segment revenue held (definition
differs from the printed 水电 line — analyst's), three small plugs as
in 246, 12 forecast rows on the watch list, interest-expense roll gap
22. Also: the key panel is built by prior tie at run time and the
report's key count is code's. Museum pins for each.

## 2026-09-08 — deduction pass, step 1 proven offline (no live run)
On run 254's own ledger, answering the cards as the brain should: bond
line 0 (red), New orders 117,251 (red), dividend 1,832.93 (red, noun
proven by last year's report), proceeds from investments 25,155.70
(plain, from the p20 summary table now walked), 'other investing cash
received' 19.08 (red, new line this year by exact label) — DELIVERED,
key numbers tied 9/9 by code's count. Two defects caught by the proof
and fixed: the new-line rule also took last year's bond figure (a lone
number that ties any model prior is a comparative, excluded); a
defaulted card overwrote a served cell's note (skipped when served) and
hygiene mapped the new-line note to 'not found' (passthrough). Written
up in docs/DEDUCTION_2026-09-08.md: F1 location-as-admission (57 gates,
dispositions), F2 single-read fragility (cross-appearance corroboration
planned). Step 2 (drop WIDE_ROW, table cap, candidate caps; split the
vintage ban at 12 sites) awaits the owner's approval.

## 2026-09-08 — deduction steps 2 and 3 landed (owner: "remove those patches and fix the underlying issues")
Removed: the wide-row fence, the table-length fence, the candidate caps.
Replaced by evidence: in a wide row the current is the nearest earlier
number of the prior's own magnitude and the label must confirm (run
229's grid still cannot serve); two printings that disagree are red
with both readings, never dropped or picked silently; last year's
report names a table item (identity, never a source); disputed vision
rows are rescued by a second printing (corroborate). Two harness bugs
the fence-free floor exposed: the tier-3 hold treated a served-but-
flagged row as stale (threw away 21 proven reads), and a two-readings
flag made a proven BS row look least confident to the plug ladder.
Fence-free proof on run 254's ledger: DELIVERED, five cells land, keys
9/9, 2 plugs, 3 genuine two-readings flags for the analyst. Museum 140.

## 2026-09-09 (night) — THE READING TEST: Luna reads a whole report in one call
Owner's priority before sleep: "test luna's ability to read like Fable 5
so that we are sure that we will have to use cards". Result, both
companies, one call each, the full disclosure text page-marked plus the
scanned pages as images: CLP 392k prompt tokens, 40 s, 24/28 rows
answered with page references, 18/24 equal to the by-hand key — every
miss a model convention (payout as % vs fraction, dividends sign, a
segment sheet given the group total, an analyst's own definition). DFE
368k tokens, 66 s, 41/42 answered — revenue, PBT, EPS, dividend 1,832.93,
totals, the three cash flows, cash, attributable profit, new orders
117,251 and two blank-beside-prior zeros all right; misses: the bond
line read as this year's (the comparative in the summary table), a
units slip (19,078 instead of 19.08), dividend paid vs declared, the
group order figure on a segment row, one line not found on a scanned
page. Conclusion: Luna reads like an analyst; its errors are exactly
what code verifies mechanically (prior tie on the cited line, units
from the printed number, sign from the model, blank beside the tie,
one home per figure). Design decision: a READER stage — Luna reads
whole, code verifies every answer — replaces the label cards and most
serve cards; cards stay for genuine conflicts.
Addendum (same night): the DFE balance-sheet block Luna returned (current
assets 97,562.73, non-current 65,111.46, current liabilities 96,628.36,
equity 54,449.33) is NOT what the scanned page prints (101,683.68 /
60,990.51 / 102,323.47 / 48,168.26, vision-read and pinned) — yet both
sets sum to the same 162,674.19. On an image it could not read exactly,
Luna produced a self-consistent balance sheet: fabricated, with page
references. The text-page answers were right. So: Luna reads text like
an analyst; on scans it can invent numbers that balance. The reader
stage therefore verifies every answer against a PRINTED number in the
ledger (text or vision consensus) before anything is written; an
unverifiable answer is never served, not even red.

## 2026-09-09 (night) — step 2: the reader stage, the roll's shape rule, the matrix rule refined
- pipeline/reader.py: after the deterministic stages, Luna reads the
  whole current-vintage disclosure in one call and answers every row
  still unproven; verify() recomputes each value from the PRINTED digits
  at the page's scale, ties the cited line's comparative to the model's
  prior, applies the model's sign, treats a lone number equal to the
  prior as 0, finds a page slip by the printed name, and refuses any
  number no printed line carries (the fabricated balance sheet of the
  reading test). Proven → plain; printed but untied → red with citation.
- writer.rollover_column: a target formula of the prior's SHAPE is the
  analyst's own carried-forward structure and is kept (the half-year
  Model/Driver panels lost 31 cells to a two-column shift of quarterly
  sums); a forecast formula is still replaced by the prior's structure.
- reconcile: a period table needs DISTINCT years in its header; repeated
  years (2025 2024 | 2025 2024) are a segment × year grid — never paired.
- Step-1 floors on the three ledgers all delivered; open checks are now
  marked red and delivered, never quarantined.
- reconcile: a second READING must name the item (label kin to the model
  row or to the first reading's line); a line whose comparative merely
  equals the prior by coincidence is no reading. CLP floor: 35 → 11 flags,
  delivered, keys 7/8.

## 2026-09-09 (night) — RUN 260 (DFE FY25, head 1d0653f, the reader stage live): DELIVERED, 33 min, keys 8/8
The reader read the whole report once (182 rows asked, 182 answers) and
wrote 16 rows: 7 proven — the bond line 0 (plain, from the lone printed
comparative), 拆出资金 1,016.53, 固定资产清理 11.99, deferred tax −82.32,
two small P&L lines — and 12 red reads with citations (dividend 1,832.93,
other investing receipts 19.08, Driver revenue/COGS, …). The verifier
rejected every fabricated or parent-page answer. Three verifier gaps it
exposed, all evidence rules, now pinned: a parameter printed alone (tax
rate 15) is never a nil; a lone number equal to ANY model prior is last
year's (593.54 had gone into 'other financing receipts', then the ladder
plugged it); a no-tie read must live in the row's world (10,820 read as
interest income, prior 132.71). The prose unit word ('1,172.51亿元') now
verifies. 3 plugs, 34 red cells (12 of them reader reads), 8/8 keys.

## 2026-09-09 (late night) — three more found by the half-year replay, all pinned
- The plug ladder's leaf walker did not expand SUM ranges (only their end
  rows): the stale dividends-payable inside 'SUM(BS69:BS74)' was invisible,
  so the Model's H125 balance stayed open by exactly that amount and no
  plug was even attempted. Every row of a range is an input now.
- The column roll copied the prior header 'H124' over the analyst's 'H125'
  (two H124 columns); the header roll knew only four-digit years. A target
  header marking another period is the author's and stays; two-digit
  marks move one period on.
- A note page with too few priors to ratify its own scale was never walked
  (dividends payable p153 tied the year-end prior exactly). A page without
  anchors takes the scale most of its document's ratified pages carry.
- CLP floor after the matrix-in-every-row rule: minority interests no
  longer mis-served from the equity statement; two readings 12 → 2; keys
  8/8; one open check (ROAFNA 2025, 1,405) delivered red. Half-year
  floor: Model balance 0, dividends payable 1,371.19 from the note. Head
  proven on all three ledgers; museum 151.

## 2026-09-10 (early morning) — RUN 262 (CLP FY25, head 08f5ba2): DELIVERED WITH OPEN CHECKS, 60 min — autopsy and fix set (7e4d383, 20eae3b)

Live: delivered at the hour with ROAFNA!AI31 open (−184); keys 8/9 by the report; 7/11 against the by-hand key;
117 red / 45 orange in the AI columns. The reader took 37 of the 60 minutes (332 rows in four 90-row chunks, each
re-sending all three documents); the queue got 15 minutes and drained 160 cards.

Root causes (each fixed as an evidence rule, pinned, museum 163):
1. Reader chunking multiplied the document text — one call now carries every row.
2. Reader wrote printed totals into rows the analyst never fills (CFI block header, FCFF, 'Dividend', 'Scheme of
   control items') and every sum above them moved — a row with no number in any year is not an input.
3. A no-tie read into 'Special dividend' from 'Fourth interim dividend declared' zeroed the final DPS — a no-tie
   read must be named like its row (same script; across scripts the brain's mapping stands, red).
4. writegate.ties_prior counted a row as 'tying the prior' when the prior appeared ANYWHERE on it: the segment
   matrix row '6,359 | 2,852 | 3,128 | 106 | 12,445' made 6,359 'proven' and a balance card overwrote the face's
   12,685 (Final!66). The prior must be the number's own comparative — the pair the walk reads.
5. The balance card's co-printed candidates ignored the matrix rule and the sign of the tie: the fuel clause closed
   (1,043) where 370 had printed as (370); +1,043 was written. reconcile.table_kind is now the one period/matrix
   law for the walk, the cards and the evidence gate; candidates carry the tie's sign.
6. The key tie stacked back-outs: each gate round wrapped a DIFFERENT component of total assets (receivables, then
   investment securities, then non-current assets). One absorber per key; a re-tie unwraps the same cell.
7. The component card's 'two readings' override let an untied number replace a proven one when a check moved
   (replay: joint ventures 12,125 -> 4,379 red). Removed — a reading of an item is a line whose comparative is the
   prior, and such a line passes the evidence law on its own.
8. Report count: a key row with no printed tie is now counted as untied (operating cash flow had no panel entry and
   the count read 8/9 while the row sat 1,308 off).
9. numerics.kinship: the CJK shared-stem rule (2026-09-08) was unreachable behind a bare return.

Offline: run 262 replayed on 20eae3b — delivered, Final!AI99 = 0, ROAFNA!AI31 = 0, keys 8/8, Final AI red 117 -> 7,
orange 45 -> 14; intangibles and joint ventures on the face values. Remaining differences from the by-hand key are
definitional (other income 460 split out of operating profit; one-offs; minority interests with the PCS fold) or
card-dependent (the fuel clause side — the replay scripts 'not_disclosed'; live the card now offers −1,043).
Floors: DFE FY25 (254) delivered, 9/12 (three roles have no print: gross profit, operating profit, DPS); the bond
line's ladder plug (−0.46) is identical on the old head (baseline replay) — the live reader serves that line 0.
DFE 1H25 (256) delivered, Model balance off by 1 (rounding), 9/10. CLP 257 delivered, 8/8.

## 2026-09-10 (morning) — RUNS 34178023348 (CLP FY25) and 34178028408 (DFE FY25) on 2e333e8: both DELIVERED

CLP: 62 min, checks closed (Final!AI99 0, ROAFNA!AI31 0), keys 8/10, Final AI red 8 / orange 15 (run 262: 117 / 45);
reader 71 s (run 262: 37 min); intangibles and joint ventures on the face values. Still off the by-hand key:
fuel clause +1,043 (the reader forced the prior's sign although the comparative printed negated — fixed: the sign
of the tie carries); associates 7,532 (a balance card took 'listed 954 | unlisted 7,532 | total 8,486' as a period
pair because 8,486 is the prior — fixed: a row total is not a comparative; a second tying line now lands red beside
a proven figure); the key tie moved to a second absorber after the gate loop's take-back (fixed: the recorded
absorber is reused). Queue budget 17.4 min: ~40 min pass before the queue (stage-1 vision votes, docid, the walk);
workflow logs now unbuffered so the next run shows real stage timestamps.
DFE: 36 min, keys 8/11 (gross profit, operating profit, DPS have no printed tie), reader 41 s, same two plugs as
run 260. Interest income 10,820.82 red: the reader tried the tie only at the page's ratified scale (10^4) while the
comparative ties at 10^6 (108.21) — fixed: every legal scale.
Owner 2026-09-10: interim balance-sheet keys take the model's year-end column as the prior (run 261 reported total
assets 'not tied'); a comparative no model column holds becomes an analyst question, never an estimate.
Commits e42f36c, +1 (row total). Museum 170.

## 2026-09-10 (morning) — RUNS 34182725503 (CLP FY25) and 34182720815 (DFE 1H25) on 20adfd4: both DELIVERED

CLP: 60 min, checks closed, keys 8/10, Final AI red 10 / orange 15; fuel clause on the liability side (−1,043 read
with the sign of the tie), associates 9,508 on the face. Remaining differences from the by-hand key are back-outs
(receivables 14,508 vs 14,035; deferred creditors 12,246 vs 8,363 absorbing the equity-side definition) and
definitions. With unbuffered logs the hour reads: stage 1 + document naming 4 min; stage 2 instant; STAGE 3 (the
image-based gap reader) 31 silent minutes for 168 rows; the reader stage 58 s for 194 rows; queue 20 min.
DFE 1H25: 18 min, keys 8/11 — total assets 156,365.52 and total equity 45,403.66 now tie through the model's
year-end column (the owner's interim rule, live); Model BS column red 3 (261: 6); Driver H1 column red 34
(segment rows with annual history but no interim prior, read red with citations — by design).
Change: the reader stage now runs BEFORE stage 3, so the per-region image read takes only what the whole-document
text read left (root cause of the 31 minutes: two brain readers, the slow one first). No rule changed.

## 2026-09-10 — RUN 34186514149 (CLP FY25, 9c2383b): DELIVERED, 60 min — the 33 minutes named

Same quality as the previous CLP run (checks closed, keys 8/10, red 10 / orange 15, fuel clause and associates on
the face). Reader-first saved nothing: the whole-document reader took 49 s (28 rows of 244), stage 3 still 33 min.
Its run_log shows why: 101 image calls, most answering nothing — every row with no printed prior ("homeless")
rode EVERY region in 70-row chunks (~600 rows × 11 regions). Rule: a row is read where its prior prints (the
checksum's comparative); a homeless row belongs to the whole-document reader, which already saw every page.
Pinned (rows_for_region); museum 172. Dispatched CLP FY25 on this head.

## 2026-09-10 — RUN 34193572830 (CLP FY25, b2f9f2f): DELIVERED clean, 40 min

Checks closed, no error cells, keys 8/10, Final AI red 12 / orange 16; Yangjiang 570 (named line), capacity 1,108
kept, unit cost computes. Timeline: documents 4 min, reader 1.5 min, gap reader 4.5 min, cards 28 min (327 calls,
0 drained). Remaining differences from the by-hand key are definitional (other income inside operating profit;
minority interests without the PCS fold) plus the two back-outs that absorb them (receivables, deferred creditors).
Preceding run 34190407637 (e99da58): 41 min but 888 error cells from one card zeroing a constant capacity —
root cause of the constant-row rule. Next: DFE FY25 + 1H25 on b2f9f2f as the regression pair, then stop.

## 2026-09-10 — RUNS 34196724937 (DFE FY25) and 34196731369 (DFE 1H25) on b2f9f2f: both DELIVERED

FY25: 36 min, keys 8/11, Model column identical to the morning run; interest income 108.21 plain (was 10,820.82
red — the every-scale tie). One plug (Driver!J102), as before. Driver segment reads differ run to run (red 36 vs
23) — no by-hand key for the Driver tab; the delivered statements are unchanged.
1H25: 18 min, keys 8/11 (total assets and equity via the year-end column). One regression: with homeless rows
no longer read by the image gap reader, the whole-document reader took them — and quoted '1' (a note reference,
五(六十九)) as a no-prior cash figure; the cash check then plugged 4,117 over it. Rule: a no-tie read needs at least
three significant digits (a reference or a parameter is not a figure). Museum 175. Re-running DFE 1H25.

## 2026-09-10 — RUN 34199950949 (DFE 1H25, d102c33): DELIVERED clean, 15 min — and the digits rule withdrawn

Balance 0, no ladder plugs, keys 8/11. The digits rule refused two GENUINE round figures ('收到其他与投资活动有关的现金
1,000,000.00' = RMB 1m; '专项应付款 240,000.00'); the LABEL card then wrote the same 1.0 and the cash check closed on
it. The earlier 4,117 plug was the ladder's choice of site on an off check, not this read. Rule withdrawn the same
morning; exhibit replaced by the round-figure acceptance. Museum 175. This closes the night: CLP FY25 clean 40 min,
DFE FY25 36 min, DFE 1H25 15 min, all on one head.

## 2026-09-10 — owner's two CLP rulings: the absorber is the least confident LEAF; carried constants are unproven

1. Final!AI30 '=94-AI29-AI28' carried last year's 94 into 2025; the constants law logged "stays red" but never
   painted it. Now an unproven carried constant is painted red with its literal named.
2. The key tie wrapped whole formulas (=(AI14-AI13-AI12)-(148.345)) and said "no component could absorb" for
   recurring net profit while two one-off leaves sat red at 0 and AI30 carried the 94. Owner: trace the components
   and back out the least confident cell, never the formula. Classes, in order: a red cell; a carried constant
   inside a plain formula (the literal absorbs: =(94-(535))-AI29-AI28); an orange cell; an estimate formula left
   in the actual column. A plain hardcode is a proven serve and a plain formula of references is the analyst's
   design — neither absorbs. The probe tries both signs (a component may enter the key negatively).
Museum 181 (fixtures for one-absorber / take-back re-based on a red leaf). Replays + CLP FY25 dispatch next.

## 2026-09-10 — RUN 34209839027 (CLP FY25, 63e8bc9): DELIVERED clean, 40 min — the owner's absorber rule live

Checks 0/0, red 13 / orange 17. Recurring net profit ties 10,909 through Final!AI30 (the carried 94 backed out to
−441, the by-hand's figure); net profit through Final!AI16 (other income); operating costs' formula untouched.
Operating profit left red, KEY OFF +148 — every cell in its chain is a plain served figure, so nothing absorbs;
the analyst's question, not a forced tie. Total assets / liabilities-and-equity still absorb into receivables and
deferred creditors (orange, one cell each across the gate rounds).

## 2026-09-10 (night) — landscape pages and roll-forward schedules (the owner's task)

Phase 1: a page is read in its displayed orientation (43 of DFE's 280 pages are /Rotate 270; text came out
reversed; 0 → 305 numeric lines; 237 portrait pages byte-identical). A line's enumerator ('（1）', '1.') is not a
number — the opening/closing rows of every movement table had lost their labels. Ratios tie relative-only.
Phase 2: pipeline/schedules.py — the vertical prior tie (see docs/PLAN_2026-09-10_landscape_pages.md §6).
Offline on the real DFE model + rebuilt ledger: the PP&E cost and depreciation rolls, the impairment literal
and the four-literal amortisation formula all served from p184–p193; Net PPE check 0. Museum 184.

## 2026-09-09 — RUN 34245296925 (DFE FY25, e75803c): DELIVERED, 38 min — the Driver PP&E schedule filled from landscape notes

Driver rows 94–122 match the hand-mapped answer key 17/17, no red cell in the block, no plug: Addition 244.41,
Transfer =1961.8-J95 (1,717.39), Disposal −607.39, Gross PPE 20,217.74, Depreciation −853.97, Disposal 434.56,
Impairment =-100.682+固定资产清理 (−88.69), Net PPE 6,465.27 = balance sheet (check 0), CIP 1,427.33 → 1,223.32
with transfer −1,717.39 and addition 1,513.38 by the analyst's own formulas, Amortisation −272.04 by the analyst's
own method. Balance 0, cash 0, keys 8/11. The previous run (47ccbc2) had served the same cells and then a
rollover card reverted the Transfer literal (my serve records lacked value/document/page) — fixed in e75803c.
Elsewhere: one rollover revert on Driver!J11 (Hydro, red, analyst to confirm) — not the night's topic.

## 2026-09-09 — THE SENSE CHECK (owner's rule), five live pairs to settle it

Rule: the report's mini P&L, updated model vs the analyst's pre-update model; a line whose next-year change is
more than 10 points away from its actual-year change is suspicious. Checkpoint after the automatic fill (chain
cells to the queue's front as review cards, red first; rolled-into-zero rows back to zero); final pass after the
checks (one review card per line, then keys and balance again). Lessons from the live pairs, each pinned:
- cash-flow lines swing by nature — the check reads the mini P&L roles only;
- a review that opened a check was taken back even when the check was already open — now only NEW failures;
- a review served an unproven line (Australia revenue 1,801) and next year's revenue went to −95 billion while
  the balance closed — a review now serves only a figure whose line ties the prior, and a review that widens any
  headline gap is taken back (the review is judged by its own measure);
- the sense-check lines have their own section on the report tab (they had been cut off a 40-line verdict list).
Final pair (580c300): CLP FY25 48 min, clean, keys 8/10, red 14 / orange 17 — checkpoint clean, four lines out of
line after the cards (operating profit −4.0% / +35.4%; net profit −5.8% / +21.5%), reviews refused as unproven,
written up with the cells to look at; next year's revenue sane. DFE FY25 36 min, clean (the 11-unit interest-roll
gap closed this time), schedule 17/17, keys 8/11; operating profit (+21.2% / −4.8%) and EPS written up.
Live so far the sense check detects, reviews and gives up safely; it has not yet resolved a line by itself — the
review candidates were second readings without a prior tie. Museum 185.

## 2026-09-10 (night) — THE INVESTIGATOR (owner's rule): the analyst's trace, built, practised on past runs, live

Rule: a suspicious headline line (next-year change >10 points from the actual-year change vs the pre-update
model) is traced level by level — put each input's pre-update value back and measure how much of the swing goes —
down to a typed cell; that cell is judged: the agent's own red/orange → a better answer (a printed line that ties
the prior and is named like the row; the residual of its total; last year's share), kept only if the gap shrinks
and no check opens; a proven figure outside its own history → reported, untouched; else red with the trail.
Practice (tools/investigate_past.py over the last five CLP deliveries): the owner's tax case traced exactly —
net profit → Total → Others → Australia → Earnings → income tax → Aus!AI27 holding the group's tax −2,655 —
and fixed from Australia's own printed line (−226, p29): 3 suspicious lines → 0. India revenue 88,018,000,000
(the group figure in dollars) traced and put back. Practice also caught two of my own errors before going live:
a per-share line used as the 'world' for an amount, and pass-through links taken as parents.
Live (cf8dca4): CLP FY25 48 min — at the checkpoint the investigator FIXED recurring net profit twice
(Australia income tax −284 from p29; Australia finance costs −185 from the printed line) and flagged revenue's
factor (Aus!AI5, no proof); at the final pass it judged India EBITDAF +742% genuine-but-unusual. Balance closed;
ROAFNA open by 968 this run (card variance in the tariff-stabilisation closing balance, not the investigator).
DFE FY25 30 min — schedule 17/17; operating profit's factor (Wind) judged genuine within history; the intermittent
interest-roll gap (11) open. Museum 186.

## 2026-09-13 — THE REPORT PAGE REVAMP (owner + boss): one fixed table, rendered by code

Owner's list: the analyst does not read the documents list, the sense-check paragraphs, the key-number
snapshot as it was, or "why it moved" — all gone. The boss's idea: fold the snapshot into the mini P&L, give
the mini P&L a FIXED structure on every model, and add the cash flow (and a little balance sheet).
The page now (pipeline/reportpage.py; execreport.report_only renders it, the brain composes nothing):
1. Verdict strip — updated to which period, minutes, balance and cash checks (the run's own years), key
   numbers tied n/m, red · orange · plugs (all counted by code from the file).
2. The table — 22 fixed lines: P&L (revenue, gross profit, EBITDA, EBIT, net finance costs, associates and
   JVs, pre-tax profit, tax, net profit attributable, recurring net profit, EPS, DPS), cash flow (operating,
   capex, investing, financing, free cash flow, dividends paid), balance sheet (cash, net debt, total equity,
   book value per share). Blocks: WHAT CHANGED (new ÷ old − 1) with the ten-point check, NEW (live formulas)
   with the PRINTED figure and page beside the actual and YoY, OLD (the pre-update model's values). A line the
   model has no row for says "not in this model" and keeps its place.
3. Key numbers — the model's own key rows: prior actual, actual, YoY, your estimate, actual vs estimate,
   tied to the print or not (the next-year columns removed at the owner's request).
4. Look here — the investigator's verdict per suspicious line with the cell its trail ended at as a link,
   open checks, plugs, and the flagged cells that sit on the page's own rows; the rest as a count per sheet
   (the analyst will not read a full list — it stays on _FLAGS).
THE PERIOD FOLLOWS THE RUN (owner): headers are explicit (FY24A · FY25A · FY26E; 1H24A · 1H25A) and the
columns are the model's own panel for the period updated. A half-year or quarterly panel that carries no
forecast columns says "no half-year forecast found in this model" where they would be; one that does shows
them. Case by case, from the model's structure — no rule about which models forecast interims.
HOW A LINE FINDS ITS ROW (generic): the run's proven key rows first; then the sheet's own labels — an exact
name, a whole-phrase name, or every word of a name present; a label carrying a word of another meaning is
another line (a 'tax' line is not 'deferred tax assets'); a shared word alone is no evidence (the first cut
put 'gross profit' on 'Profit after tax' and 'book value per share' on 'Share capital'); the sheet carrying
the fuller period axis wins, then the row nearest the lines of the same statement already placed.
Offline on the last deliveries: CLP 20/22 lines (no gross profit, no BVPS in that model), DFE 21/22 (no
recurring line), DFE 1H25 19/22 on the interim panel with the no-forecast note. Museum 187 (exhibit:
fixed table, period headers, print column, look-here link, interim panel). Floors: see below.
Owner's changes on seeing it (2026-09-14): statements in the order P&L, balance sheet, cash flow with one empty
row between them; the key-number section drops the Printed column and shows names in proper case (EPS, Net
profit). Floors on the repo's pinned ledgers (no pinned key rows, so key counts read 0/0 there except CLP 7/8):
DFE FY25 delivered with the standing magnitude check open (as before), DFE 1H25 delivered with open checks (as
before) on the interim panel with the no-forecast note, CLP FY25 delivered clean, keys 7/8 (was 1 open check).
Bench green, museum 187, head committed as the report revamp.

## 2026-09-14 — Owner's three findings on the DFE file, each to its cause

1. Header rows filled (Driver 'Revenue' over the segment lines, 'Hydro-generating unit 兆瓦' over
   Production/Sales/Inventory, Raw financials '非流动资产：'): label cards (the 2026-09-08 'infer from the
   label' exception) had no never-filled check. Owner 2026-09-14: "an overall check for the whole run" — THE
   NEVER-FILLED ROW LAW is the writer's: a row holding no number (a typed zero counts) and no formula in any
   other cell, past or future, takes no numeric write from any step, trusted or not
   (writer.row_never_filled; log key never_filled_refused); no label card is dealt for it. The 09-08 exception
   is superseded — 'New orders' stays blank (owner: "1 yes").
2. Driver!J10 '=16602.97-J11' plain, not flagged: the constants law HAD painted it red; the investigator then
   tried a fix on it (last year's share, orange), the gap did not close, and its restore was a plain write —
   which clears the standing flag — so the red went, the format rollover copied the prior column's look, and
   the final pass judged the now-unflagged cell "a proven figure within its history". Fix: the writer keeps a
   style journal beside writes_all (fill, note, flag standing before each write) and take_back() restores the
   look with the value; the investigator's trial restore and the final pass's take-back use it.
3. The sense check ran (operating profit 26 pts → traced to J10; EPS 17 pts → impairment losses, genuine) but
   skipped DPS (−11.9% / −30.4%) because a base under 1 was treated as a ratio: a per-share line is an amount
   whatever its size. Owner 2026-09-14: scope extended to every P&L AND cash-flow line of the report's fixed
   table (sensecheck.sense_rows via reportpage.resolve_rows; a spec key row keeps its name).
Museum 195 (three exhibits rewritten/added: 203 empty-row law + the writer's law; 09-08 label card superseded;
09-14 never-filled + DPS). Bench green.
4. Found by the faithful replay once cash flow was in scope: the schedule's proven disposal (Driver!J104 434.56,
   p184) was zeroed by rolled_into_zero — its forecast years were typed zeros that had never moved — and the
   opened PP&E check was then plugged over the proven figure (1,159). The rule now fires only when a forecast
   cell actually computes from the fill; typed zeros stay zero by themselves. Museum 197.
Faithful replay of the live DFE run (run 34386953100 artifact + its card answers) on this head: Driver!J10 red
with its note, the header rows blank ('New orders' too), the sense check over 14 lines (net finance costs fixed
at the checkpoint from the printed 长期借款, capex / investing / FCF traced to the CIP closing and judged genuine,
operating profit red → J10). Replay limit, same on cf8dca4: the saved ledger serves only one schedule row, so the
PP&E check sits open by 725 in replays where the live run closed it.

## 2026-09-14 (night) — DFE FY25 run 34771914611 (23 min) and CLP FY25 run 34772986687 (30 min), head 70bb04b
Both delivered clean, checks closed every year; DFE keys 8/11, CLP 8/10. The four fixes verified live on DFE
(J10 red with note; header rows and 'New orders' empty; DPS and cash-flow lines sense-checked; schedule intact).
Scores (tools/score_inputs.py, docs/scores/): CLP vs the analyst's finished model — 282 judged, 191 correct
(68%), wrong 91 = red 46 / orange 22 / unhighlighted 23; DFE vs the prior agent run (no hand-filled FY25 key) —
214 judged, 207 correct (97%), wrong 7 = red 6 / unhighlighted 1 (a 差额 difference row). Full report:
docs/MORNING_REPORT_2026-09-14.md. Wasted hour first: tools/dispatch.sh dispatches the previous-gen 'updater';
the root dispatch.sh with 'pipeline' is the only command (memory + RUNLOG).

## 2026-09-14 — THE TABLE READER (owner): the brain reads every table; the floors were drifting
Trace of the 23 unhighlighted CLP cells: 7 were segment/category columns paired as this year | last year
(the announcement's segment page 'Finance income 119 | 14 | 29 | 4 | 69 | 235' served 14 beside Australia's
prior 29; 'Associates 1,810 | 1,810' there zeroed CN's 1,607; a capacity 'units | MW' table served 2 for NED
solar; the page read took the EBITDAF segment row as Ho-Ping 181 | 261), 8 were bare prior ties on numbers
printed on 10–50 lines (294, 85, 120 …), 2 small carried literals (34; −40+29) under the constants law's floor,
6 not inputs at all (ratio/unit formulas; the scorer's mistake). Owner: no shape rule — "the brain has to be
reading the tables like a human analyst".
Built: pipeline/tables.py — every table of every document goes to the brain once (header lines from the page
text + first rows, ~300 tables a call; CLP 2,456 tables ≈ 8 calls) and it names the columns: periods /
segments / categories / movement / grid / other. The verdict is stamped on every printed line
(Item.table_kind period|matrix, Item.columns) and travels with the pinned ledger; the shape fallback
(ledger.table_kind_of) fills only where the brain said nothing. Every channel that pairs a current with a prior
consults the stamp: the walk (reconcile), the evidence law (writegate.ties_prior), the nil rule, the page reads
(stage3_read.matrix_pair), the cards. Museum 201, bench green.
The floors were not floors: every offline replay saved its own ledger, serves and decisions over
companies/<CO>/replay/<PERIOD>/ — each floor ran on the previous replay's outputs (CLP's 252 pinned serves had
drifted to 88; the ROAFNA check 'opened' with no code cause). A replay now writes beside the floor
(replay/<PERIOD>-replay/), and the floors are re-pinned from the last live artifacts (CLP FY25 run 34772986687:
8,355 items / 254 serves; DFE FY25 run 34771914611: 5,539 / 250; DFE 1H25 keeps the drifted copy — no live
artifact survives). Still open from the trace: the ambiguous-prior rule (uniqueness, not size) and the small
carried literals.

## 2026-09-14 — CLP FY25 run 34799733381 (33 min, clean, keys 8/10): the table reader live, and what it left
The brain read all 2,456 tables in 9 calls (periods 347, categories 472, segments 58, grid 34, movement 6,
other 1,539 — mostly one-number prose lines). Of the seven segment-table cells: Aus finance income 24 red (was 14
plain), CN associates 1,607 red (was 0), Ho-Ping 231 twice (was 181) — right. Score vs the analyst: 276 judged,
202 correct (73%, was 68%), wrong 74 = red 37 / orange 17 / unhighlighted 20 (was 23).
Three more causes found on the run and fixed the same day (museum 203, bench green):
- the WALK recomputed the table's shape instead of asking the brain's stamp — a capacity table 'Solar 2 | 294 |
  45' (categories) paired 2 | 294 → reconcile.table_kind honours Item.table_kind;
- a CARD 'proved' NED solar 2 with a 2024 hedge line at scale 100 (−161 | −2,102 → 1.61 | 21.0): the card path
  now excludes prior-vintage documents from its evidence (the vintage law — never a source), and a tie is at the
  number's own world (1.61 is not 2; the 0.5 rounding floor applies from 50 up);
- THE COINCIDENCE LAW: a prior's identity is its uniqueness in print, not its size — a prior printed under
  several names (294 on 14 lines, 120 on 13) needs the line's label kin to the row's (reconcile.prior_carriers);
  offline on the stamped ledger the walk serves 59 rows instead of 81 — the 22 coincidences now go to the reader
  and the cards, red where nothing proves them.
Floors re-pinned from the stamped live ledger (CLP FY25: 8,355 items, all stamped, 259 serves); replay clean.

## 2026-09-14 — GLOBAL LAWS (owner: "I want them applied in the entirety of the run")
Audit: six rules lived in one step only. Moved to the two gates every write passes — the writer and the
evidence finder — and the local copies removed:
1. The vintage law: `Item.sourceable` stamped on every printed line the moment a document's vintage is decided
   (classify_doc_periods, docid, from_json); `find_evidence`, `ties_prior` and `nil_current_zero` refuse an
   unsourceable line whoever calls them. The per-site `it.doc in prior_docs` filters in the walk, the join,
   the page reads, the key tie, the composites, the cards and the run now read the stamp; the card path's
   local ban of this morning is gone.
2. The sense check's `rolled_into_zero` retired: the zero-forecast row is the writer's law (measured on the
   analyst's model before the roll; rollover → 0; no estimate; not stale).
3. Every delivered write goes through the writer: forecast freezes, forecast-plug unwinds and the forecast-
   link zeroing had set cells directly and skipped every law (never-filled, zero-forecast, the style journal).
4. The constants law's size floor (50) is gone: a carried literal is last year's figure whatever its size
   (Aus!AI17 '=34-…', Final!AI125 '=-40+29+0'); 0.5 and 1 join the modeling constants so ratio formulas are
   untouched.
5. A page read with no prior tie must be named like the row (the reader's law, now the page read's; the
   brain returns the printed line's label).
Still local, by design or pending: the one-figure-one-home claim registry (cards and the walk each keep one;
the reader and the page reads use the shared `claimed_values`); the coincidence law (walk only — the reader
and cards prove by tie or label, not by bare number). Museum 207, bench green.

## 2026-09-14 — THE GATE, THE CLOCK, THE STAMP (owner: "fix the underlying issue, not patches")
The gate (pipeline/writer.py): `Writer.flag()` paints or clears a flag through the journal; `Writer.revert()`
lands a guard's take-back through the gate and un-locks and un-serves the cell; `take_back()` does the same.
THE PLUG LAW: a write declared `kind="plug"` is refused until the run opens the last-resort stage
(`plugs_allowed`: the queue reaching its plug cards; the repair rounds), and every plug that lands is
recorded (log["plugs"]). Plug writers declare themselves (t_plug_residual, last_resort_plug). Holds (t_hold),
auto-probe holds, tuned holds and the terminal paired-diff batch now land through the gate after their probe;
the error guard, the collapse guard and the gate loop revert through it (value, look, lock and served go
together). The clock (agent/llm.py): the client carries the run's deadline; no attempt starts past it and the
socket timeout shrinks to what is left; the queue's breaker trips on a five-minute call, and every card drains
five minutes past the deadline; the table reader stops batching ten minutes before the deadline. The stamp:
the join reads Item.table_kind (its own shape test is the fallback), the key tie reads sourceable and the
stamp, a brain reading of "other" is stamped plain so the tie decides. Also: a refused absorber falls through
to the next candidate and to KEY OFF (it had broken out silently); the sense check's final pass takes back a
review that fails the full check run. Museum 209, bench green.

## 2026-09-14 — THE ZERO FORECAST, as the owner stated it
"2025 same as other cells, mapped by our rules; it's just that 2026 → if the original forecast is 0 for 2026
onwards, then 2026 should be marked as 0." Built: the zero-forecast rows are the rows whose forecast cells all
evaluate 0 in the analyst's model (check rows excluded — 0 by construction); after the update, every forecast
cell of such a row that computes non-zero is held at 0 (blue, journaled, a sanctioned freeze the gate
accepts), before the repair rounds and again after the final sense pass with a repair round after it. The
estimate refusal and the rollover special case of the morning are withdrawn: the actual year rolls and maps
like every other cell. First cut held check rows and opened 20 checks; second cut held after the final pass
with no repair and opened the forecast balance — both caught by the floors. CLP replay: clean, keys 8/8,
ROAFNA!AI71 red (not found, last year's kept), AJ71/AK71 0 blue; score 226 judged, 147 correct, wrong 79 =
red 52 / orange 17 / unhighlighted 10. Museum 209, bench green.

## 2026-09-14 — the six approved items (owner): built offline
1. A literal carried from last year's formula that the documents never print is red (constants law).
2. The checkpoint checks itself: a fix the investigator tries there is kept only if no closed check opens.
3. A half-year run with no half-year panel delivers the model untouched with the finding on its report page —
   it never raises ("if the analyst runs a half-yearly update there should be a half-year column").
4. The face-page fences are gone (composites' already-current guard and sweeps, the key panel's print search,
   the key-tie pool): evidence is any sourceable period line wherever it is printed; a matrix is refused by
   its stamp, not by a count of numbers.
5. Every remaining hand-painted flag (14 blocks in teachings, keytie, schedules, composites, run; the plug
   painter in reclass; the brain's flag_cell tool) goes through the journaled writer.flag / flag_ref; the
   "0 means 0" unflag too. No `.fill = fills[...]` remains outside the writer.
6. Honest replays: the run's own products (schedule serves, sense-check fixes, holds, plugs, constants-law
   rewrites, nils, key-tie back-outs) are never pinned as brain reads; a replay keeps the live run's vintage
   verdicts instead of re-deriving them without the brain.
Museum 209, bench green.
Honest replays then showed the CLP floor delivering six open checks: the ladder refused every plug because
"evidence-based fixes remain" — a GUILTY diff (SOC Accounts!7: model 370 vs printed 20) that no card had
applied and a STALE COMPOSITE that was a formula of references ('=AI61-SOC!AI8' evaluating 0 = its prior,
nothing to rewrite). Root fixes: the last resort applies the evidence fixes it demands itself (t_apply_diff
through the evidence law; a refused one is ruled out), a card's not-disclosed verdict on a row is recorded as
ruled out and no longer counts as a fix that remains, and a reference-only formula is never a stale composite.
CLP floor clean again; museum 211.

## 2026-09-14 — CLP FY25 live run 34820388690 (head 225232d, 39 min): delivered with 1 open check
Keys 7/10, 4 plugs; score vs the analyst's workbook: 229 judged, 153 correct (67%), wrong 76 = red 53 /
orange 14 / unhighlighted 9 (docs/scores/CLP_FY25_run34820388690_vs_analyst.txt). Three causes, all root:
1. **The table reader crashed on its first "other" table** (`changed[kind]` knew two kinds, the stamp has three
   since the "other → plain" change) and the whole stage was skipped — every segment-table miss came back.
   Undetected offline because the reader runs only with a brain and replays run without one, and the exhibit's
   fake brain never answered "other". Fixes: the counter counts what it sees; the readings travel with the
   ledger pin and a replay stamps from them with no brain (the stamping code now runs offline); a crash logs
   STAGE LOST and the bench refuses any floor log carrying it; "other" is gone from the prompt — every table
   has a structure, the brain decides ("single" = one number column, named).
2. **Keys tied in the wrong order**: 'total liabilities and equity' tied before 'total equity' and absorbed its
   whole 9,513 gap into retained earnings (a leaf of total equity), which then sat at 113,568 vs 107,610 with
   nothing left. Fix: a key that is a leaf of another key ties first; the leaves of a key that ties its print
   never absorb for another key (the gap is between the two totals — the analyst's reasoning). Retained
   earnings backs out to 84,367 = the analyst's figure.
3. **Rule 2 armed a comparative**: `_printed` accepted any number on a current-document line, so last year's
   104,055 in the 2024 column of the 2025 balance sheet counted as this year's print. Fix: the current-period
   position only (the brain's column names when read, else the first number). The gate lists a failure once.
Also built (owner): the sense tracer's BRACKET — a headline line whose own check passed is proven and never
entered; among the contributors that carry the swing the agent's own flagged cells are looked at first, then
the largest swing ("operating income swings, gross profit stable → the issue is between; my flags first").
Museum 219, bench green; floors: CLP FY25 8/8 · 4 plugs (identical to the unchanged head), DFE FY25 8/11 · 0
plugs, DFE 1H25 one rounding check (1.0). Lesson recorded: a brain-only stage is untested until it replays.

## 2026-09-14 — CLP FY25 live run 34830794807 (head d3538bc, 38 min): DELIVERED clean
Keys 9/10 (dps: no printed line ties its prior), 3 plugs, 111 red / 57 orange. The table reader read all
2,456 tables in 9 calls (single 1,261, categories 746, periods 359, grid 50, segments 36, movement 4); no
stage lost. Score vs the analyst: 254 judged, 151 correct (59%); wrong 103 = red 76 / orange 18 /
unhighlighted 9. The run filled 25 more cells than 34820388690, mostly CN segment rows the analyst leaves at
0 (43 of the 103 wrong cells have analyst value 0, vs 11 before) — all red. On the cells the analyst fills:
151/211 = 72% (previous run 70%). Sense check: 12 lines reviewed, two scale errors caught and put back
(India!AI17 221,000,000; India!AI59 61,829), 11 written up — next-year forecasts moved (net profit +31%)
through India's red inputs (total debt, minority interest) and the fuel clause account. Unhighlighted 9 are
the same classes (Aus amortisation sign, MI definition, dividends, JCE investment, SEA solar, India one-off,
ROAFNA capex). docs/scores/CLP_FY25_run34830794807_vs_analyst.txt

## 2026-09-14 — after run 34830794807: the owner's three cells, traced to causes; the sense check redesigned with the owner
Aus!AI62 Ecogen 940 → 5,484 (the Hong Kong employee headcount): the positional companion rule found the prior
940 at slot 0 of a five-year-summary row ('Hong Kong number', a PERIOD table — slot 0 is FY2025) and read the
same-labelled row of another period table at slot 0. Fixes: the companion reads this year's table under the
COLUMN OF THE SAME NAME the brain read (position only when no table has names; a period table never pairs
this way); the gate refuses a line whose printed comparative contradicts the cell's prior ("comparative
contradicts": 5,397 beside 5,484 vs a model prior of 940 is another item); cards are written to the log.
Driver!112 'Others' 45 → 349: the residual formula copied correctly; HK/China inputs stale; the plug meter's
500 absolute floor hid a 7.7× move — the meter now reads the residual against its own total and history.
SOC Accounts!AI9: the key tie dumped a 5,758 gap (3,872 perpetual securities + fuel clause placement) into a
residual row — a residual row is never an absorber; a gap equal to ONE unhomed printed figure is named red
instead of absorbed (pairs/triples were tried and rejected: a coincidence machine on the floor).
The sense check, agreed with the owner: (1) the CENSUS — every typed cell ranked by its share of the headline
swing (the part that disappears when it is put back), all branches, own flags first; the walker now expands
ranges across columns (AVERAGE(AI66:AJ66) had cut the Australia trail one step short — on the live file the
census now leads with Aus!AI62 at 67% of next year's net profit swing); (2) the BRACKET — a headline line whose
own check passed is never entered; (3) the plug meter re-read after the checks; (4) THE RUNG CARD — for each
suspect cell the brain picks among the analyst's ways in order: a printed line that ties, a back-out the
model itself gives, last year's figure kept red as NOT FOUND, or keep; a plug is never on the card (terminal
ladder only). Code verifies the pick (evidence law, checks hold, take-back). No brain → the automatic ladder,
so floors are unchanged. Museum 231, bench green; floors CLP 8/8 · 4 plugs, DFE FY25 8/11, DFE 1H25 rounding.

## 2026-09-15 — THE ENDING: one loop (owner: "a loop at the end that identifies the issues, fixes them, makes sure the keys and the balance sheet balance, and stops itself")
The stacked ending (terminal ladder after stage 4, the final closer inside the repair suite, the two-tier bulk
take-back, the separate final sense pass, the extra zero hold, the consequence loop layered on top) is replaced
by `consequence.run_ending`: measure the objectives — balance checks in every year (the forecast years of one
row are one objective), the keys against the print, the headline lines out of line — take the biggest break,
put it to the brain with the movers (the swing census) and the ways to resolve it (revert a mover, back it out,
plug as the last resort, or a question for the analyst with the gap named), apply the pick through the
writer, re-run the model's own repairs, measure again; EVERY round is verified the same way (a new gate
failure or a worse total is taken back); stops when the objectives hold, when every remaining break has been
judged, or at the clock. No brain (floors): the model's own executor once per break, matched to its kind.
Also: the name judgment (naming.py) runs before every served write; the reader shows the brain each row's
sheet and section headers; the rung card offers the analyst's estimate AND last year's actual; the
"share of its total" rung needs a typed total (a share of a sum that includes the cell was a circular
reference on the CLP floor). Museum 235, bench green; floors: CLP clean 8/8, DFE FY25 clean 8/11, DFE 1H25
rounding 1.0. Owner's overnight bar: balanced, 2025 keys all correct, rollover swings sense-checked by the loop.

## 2026-09-15 — CLP FY25 live run 34874944306 (head 6eef038, 51 min): DELIVERED clean, keys 9/10
Every key equals the analyst's workbook except operating profit (ties the print 14,272; the analyst's own
definition computes 13,812). The ending loop ran 10 rounds: one consequence card (revert taken back when it
opened a check), then the swing lines with rung cards — picks visible per cell (keep / printed / estimate /
lastyear), verdicts genuine / unusual / fixed / stale. Score: 250 judged, 147 correct (59%), wrong 103 =
red 72 / orange 20 / unhighlighted 11. Two causes of the drop, both in today's own design: the name judgment
DELETED eighteen ties of which eleven were right numbers (Yallourn generation, retained earnings from the
two-sided balance-sheet row, JV balances) — a doubted name now lands RED, never deleted; and the rung card let
the brain trade PROVEN figures for the analyst's estimate (fuel clause −1,043 → 0) — a proven cell's ways are
now keep or another proven line only. docs/scores/CLP_FY25_run34874944306_vs_analyst.txt

## 2026-09-15 — CLP FY25 live run 34880517810 (head 3a1b909, 50 min): delivered with 2 open checks, keys 9/10
Score 249 judged, 151 correct (61%), unhighlighted 11. Both open checks were the loop's own doing: a 0.03
rounding residue on Final!99 counted as a NEW failure (CHECK_TOL was 0.01) and made the loop take back the
brain's back-out that had closed ROAFNA!31. Fixes in the loop itself: CHECK_TOL = 0.5 (the model's display
rounding); the loop verifies against its own objective set, not the gate's strings; a pick aimed at a check
or key must close most of it or is taken back; a widened swing line vetoes a SENSE pick only (balance is rule
1, keys rule 2, swing lines rule 3). Floors clean. docs/scores/CLP_FY25_run34880517810_vs_analyst.txt

## 2026-09-15 — CLP FY25 live run 34887799324 (head d3d7756, 47 min): delivered, 1 open check (the analyst's own ROAFNA!31, −968 vs −1,264 pre-update; the brain: a question), keys 9/10
Score 254 judged, 155 correct (61%), unhighlighted 10. The rollover loop ran 9 rounds; it caught Driver!AI17
221,000,000 (dwarfs the line, put back red). Root cause found for the biggest remaining forecast distortion:
Final!AI28 'Disposal or tax consolidation' = 390,000,000 — the prose 'net gain of HK$390 million' harvested
in base currency units and offered unconverted (the page scale of a millions document is 1). Fix at the
cause: a prose money figure is converted with the MODEL's stated units (numerics.model_unit_mult /
prose_money_value; spec 'HK$ millions' -> 390). Museum 237. docs/scores/CLP_FY25_run34887799324_vs_analyst.txt

## 2026-09-15 — CLP FY25 live run 34892926478 (head 7a733f1, 49 min): THE DELIVERABLE
Balance sheet closed every year; the one open check is the analyst's own ROAFNA!31 (−968; −1,264 before the
update), left as a question by the brain. Keys 9/10 equal the analyst's workbook (operating profit ties the
print 14,272 vs the analyst's 13,812 — definition). Rollover verdicts on the page: tax FIXED, pre-tax /
operating GENUINE, EBITDA unusual, FCF / CFO red for the analyst, financing genuine, net profit / EPS spread;
FY26 forecasts sane. Score 255 judged, 151 correct (59%), unhighlighted 14. AI28 = 390 (prose units fixed).
The CLP FY25 floor is re-pinned from this run: the reader replays 2,456 tables from the pin with 0 calls.
## 2026-09-15 — DFE FY25 live run 34897890192 (head 7a733f1, 34 min): the proof run
Delivered with one open check (Driver!J139 −19, a question by the brain); keys 8/11; 0 plugs; 180/192 (94%)
vs the prior agent file, unhighlighted 0. docs/MORNING_REPORT_2026-09-15.md holds the night's account.

## 2026-09-15 (day) — what the brain sees, and the consequences it must know (owner review of run 34892926478)
- ROAFNA!71 (coal capacity additions) read 2,910 from a capacity table: the card showed only the row's label.
  Every card now carries the row's PLACE (sheet > section headers > label), its history, and the formulas
  that use it (one helper, `row_context`); the row's STORY so far this run (`cell_story`: served from where,
  proven or not, sense rulings, flag) — memory for the brain, not a rule.
- THE GENERIC DERIVATION: if a cell feeds a formula whose answer is proven (printed / served with a prior
  tie), the cell must be whatever makes that formula give that answer — solved numerically on the model's
  own formula, any shape (`derive_via`, `derivations`, one tool `t_derive`); offered on the serve, rung and
  consequence cards as `derive:N`, plus `derive:via <cell>` for the brain's own route. A card is dealt even
  when no printed line ties but a derivation exists.
- Fuel clause / perpetual securities: a 3,652 key gap was dumped into the fuel clause account by confidence
  ranking (no meaning, no consequence) and sent 2026 cash to −728. With a brain the key tie PROPOSES, never
  places (`absorbers="none"`); every way on a consequence card shows its consequence — balance, keys off,
  cash/assets negative — measured with the plug rows lifted; cash and total assets negative in the actual
  period or the next two periods is an objective (later: a watch flagged for the analyst, never fixed). A
  pick is taken back only on the arithmetic (a check opened, the balance worse); a negative cash after a
  pick is the NEXT objective, not a veto (a correct input may expose a wrong one elsewhere).
Museum 245, bench green; floors CLP clean 8/8, DFE FY25 clean, DFE 1H25 rounding. Not yet proven live.
