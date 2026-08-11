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
