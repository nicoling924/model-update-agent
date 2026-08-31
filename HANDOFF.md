# HANDOFF — verified state as of 2026-08-31 ~15:30 (write nothing from chat memory; re-verify anything not listed here)

## Verified facts (each checked on disk this session)
- Branch: `rebuild`. Local = 352 commits ahead AND 287 behind
  `origin/rebuild` (Aug 26) — DIVERGED. origin/main is abandoned (Aug 12).
- Usual practice: runs on GitHub Actions via `sh dispatch.sh <CO> <PER>
  <PRIOR> rebuild pipeline`; Actions commits results back (that's the 287).
  Repo tracks CLP model + FY25 disclosures; LLM key in repo secrets.
- GitHub auth is BROKEN since Aug 12 (credential helper pointed into a
  deleted session scratchpad; helpers cleaned, keychain empty). Fix =
  `gh` device login (install to ~/.local/bin — download was failing on
  the owner's flaky network). Owner is non-technical: give them the
  device code + github.com/login/device, never a terminal.
- DFE FY25: DELIVERED and verified (run 19): 0 check failures ALL years,
  file "companies/Dongfang Electric/model/Dongfang Electric FY25 (run 19
  DELIVERED, all years).xlsx" (sent to owner).
- CLP: run 4 IN FLIGHT locally (started 14:58, log clp_live_run4.log,
  buffered/quiet is normal). Tier law active: loadbearing.py trace,
  tier-3 growth back-outs, sign-absurd freeze, LB-only neglect budget.
  All museum-pinned; `bash tools/bench.sh` is the ONLY dispatch gate.

## Next steps, in order
1. Read CLP run 4 card vs the 3 objectives (balance all years / segments
   / key numbers). Report card → problems → proposal; NO auto-redispatch.
2. Fix GitHub auth (device flow), then RECONCILE the divergence:
   fetch, merge origin/rebuild into local (code conflicts → local wins,
   tonight's laws are newest; keep remote's run artifacts), bench, push.
   Do NOT blind-push or force-push.
3. All future runs via dispatch.sh on Actions (owner's standing rule).
   Push before dispatch — Actions runs the pushed ref.

## Standing laws (memory dir has the rest)
Generic rules only · objective-based reasoning (balance/segments/keys) ·
think like Fable 5 · code = referee · report-card protocol between runs ·
never patch · VERIFY ON DISK BEFORE ASSERTING (this session's lesson).
