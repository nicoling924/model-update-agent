# Overnight tuning log — CLP FY25 on gpt-5.6-luna (pure Luna, updater + reviewer)

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
