# studio-native — the fully-confined Copilot Studio edition

Port of the proven Python engine's laws into ONE Office Script (the
kernel) + Copilot Studio agent flows, per the council blueprint of
2026-08-26 (`council/2026-08-26-studio-native-port-council.md`):
mode-driven kernel, workbook-is-the-bus state sheets, clone-per-run,
plan/apply transactional boundary, prior-year triangulation as the
completeness oracle.

```
core/      pure law logic (plain JS = valid TS) — TESTED, single source
kernel/    kernel.js — the one Office Script (modes: PREFLIGHT, STAGE,
           APPLY, POLICE); __CORE_LAWS__ marker splices core in
dist/      kernel.paste.ts — THE build artifact you paste into Excel
prompts/   Agent-node prompt texts (extraction contract)
test/      mock ExcelScript + museum & e2e exhibits
tools/     build.sh (make dist), run_core_tests.sh (run all tests,
           works with zero installs via macOS JavaScriptCore)
ASSEMBLY.md  the paste-in guide for the analyst
```

Workflow for changes: edit `core/` or `kernel/kernel.js` → run
`tools/run_core_tests.sh` (must be all-green) → `tools/build.sh` →
re-paste `dist/kernel.paste.ts` into the Office Script. Never edit the
laws inside dist/ or inside the Studio editor — they'd be lost on the
next build.

Status: Phase 1 (referee + plumbing). Bench: 60 assertions green.
Phase 2 (full statements, restatement, back-outs) and Phase 3
(roll-forward, report, ledger parity) follow after the tenant-side
acceptance test in ASSEMBLY.md passes.
