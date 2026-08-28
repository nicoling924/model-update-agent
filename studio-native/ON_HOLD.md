# Studio transferral — ON HOLD (2026-08-28)

Owner paused the Copilot Studio port to redesign the Excel `_REPORT`
page first. Resume from here when they say so.

## Where the port stands (all committed)

- **Kernel** `kernel/kernel.ts` (~1,100 lines), one script, modes:
  SEED / PREFLIGHT / EXTEND / STAGE / RESTATE / APPLY / POLICE / REPORT.
  Phases 1–5 done: mapping cascade, restatement full-stop, multi-sheet,
  EXTEND-by-approval, hardcode/embedded-driver classification,
  external-link + error health baseline, calc-mode manual+restore
  (fixed the 60s timeouts — real cause was a linked workbook recalcing
  on every read, proved by tools/probe/speed_probe.ts).
- **Instructions** `prompts/instructions.md` (221 lines, commit c0ee1b5)
  — rewritten to teach the objective loop ("think like Fable 5"), not a
  checklist. Owner confirmed alignment before it was generated.
- **Bench** `tools/run_core_tests.sh` — 186 assertions green
  (55 museum + 131 e2e, runs 1–17). Never commit on a red bench.

## Last real-model run (owner's DFE, in their tenant)

119 lines written, no timeouts (154s). Outstanding on that model:
- `Model!U95 = -6501` current-period check failure (need label at A95)
- new errors `Model!U43/U44` — likely ratios dividing by blank rows
- 52 awaitingFigures; 5 refused lines needing analyst ruling
  (其他应收款, 固定资产, 其他应付款, 其他综合收益, 利息收入)
- 4 embedded hardcodes flagged; `Raw financials!T266 = 199.14` pre-existing

## Next steps when resumed

1. Owner clears `Raw financials` col U (rows 3-down) on a COPY, pastes
   the final kernel + instructions, re-runs. Watch for *investigation*
   behaviour, not just reporting.
2. Rebuild `modeReport` to the owner's new layout (being designed now on
   the GitHub edition's `_REPORT` — see below). Known defects to fix:
   POLICE findings not on the tab, duplicated cell rows, empty Core
   Figures, truncated notes, no coverage line. Keep the exceptions
   banner + reviewer verdict from the GitHub edition.
3. Then the reasoning phase: derive/back out undisclosed lines, diagnose
   failed checks, infer analyst adjustment logic.
4. Check the `search-before-answer` skill can't reach the web.

## Current interruption task

Owner is redesigning the `_REPORT` page layout, working on top of the
best GitHub-edition DFE run: `companies/Dongfang Electric/model/
Dongfang Electric FY25 (agent final).xlsx` (the labelled deliverable,
_REPORT first tab). Whatever layout they settle on gets ported into
`modeReport` in the Studio kernel afterwards.

## Standing constraints

- Files cannot cross into the company — owner can only paste text/code.
- Never run anything on the live model; always a copy.
- Never run SEED on a real workbook.
