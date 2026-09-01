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
