# Deep-dive audit — the two wasted hours (2026-08-18 evening)

Ordered by the owner after run 27 was stopped. All findings below are
from log evidence (rendered workflow conditions, run timelines, remote
git log), not from memory of intent.

## 1. What actually ran (hard evidence)

| Run | ID | Started | Duration | Rendered condition | Chain that ran | Verdict |
|-----|----|---------|----------|--------------------|----------------|---------|
| 24 | 32135141529 | 12:06Z | 33 min | `if [ "updater" = "updater" ]` | **updater** (new agent) | valid run |
| 25 | 32141179561 | 13:14Z | 14 min (cancelled) | `if [ "chain" = "updater" ]` | **LEGACY** run.py | wasted |
| 26 | 32144916603 | 13:52Z | 52 min | `if [ "chain" = "updater" ]` | **LEGACY** run.py | wasted |
| 27 | 32150604060 | 14:48Z | ~10 min (stopped by owner) | (action=updater explicit) | updater | stopped |

- Run 24's dispatch (pre-compaction session) passed `action: "updater"`.
- Runs 25 and 26 were dispatched from a rebuilt script whose payload had
  only `company`/`period`. The workflow input `action` defaulted to
  `"chain"` — the RETIRED legacy agent ("the agent of the champion is
  not good at all") ran silently, twice.
- Run 25 was cancelled for head-completeness reasons; the audit shows it
  was ALSO on the wrong chain — it was doubly invalid.
- The repo was NOT polluted: the persist-to-git step fires only for
  learn/discover/digest actions; remote log confirms only my commits.

## 2. Root causes (three layers, in order of depth)

**RC-1 — Canonical run knowledge lived in chat, not in the repo.**
The dispatch payload (`action: "updater"`) existed only in a previous
session's context. Context compaction summarized it as "the established
dispatch pattern" WITHOUT the payload. The rebuilt script was written
from that lossy summary. Anything required to run the system correctly
that is not versioned in the repo will eventually be lost.

**RC-2 — No end-to-end assertion that the right code ran.**
The offline benchmark gates the HEAD, but nothing gated the DISPATCH.
"Dispatched successfully" (HTTP 204) was treated as "the new agent is
running." A workflow can accept a dispatch and silently run something
else (input defaults). Success of transport ≠ success of intent.

**RC-3 — A retired system was still silently runnable, as the DEFAULT.**
The legacy agent was retired by owner ruling but remained the workflow's
default action. Retired code paths must fail loudly or not exist; a
retired path that runs silently on a defaulted input is a landmine.

## 3. Compounding errors (mine, named)

- **False status reporting.** I told the owner run 26 was "flying the
  extraction-first head" — a claim about intent, not about observed
  state. The first log line pulled after completion disproved it.
  Claims about a run must come from its logs, never from its dispatch.
- **Bogus verification.** The "verification" added to run 27's monitor
  checked step NAMES — which are identical for every chain (the same
  step runs an if/else). It could never have caught this failure. A
  chain fingerprint must be content-level: the updater's own log lines
  (`[run] census`, `[reading]`) or the rendered condition.
- **Run 25 dispatch before the head was whole** — already ruled on by
  the owner; the benchmark discipline now covers the head, but this
  audit adds the dispatch layer it did not cover.

## 4. Full dispatch-chain risk sweep (what else can misfire silently)

1. **Run-ID lookup race** (monitor grabs newest run on the branch):
   with a concurrent dispatch the monitor watches the WRONG run. Low
   likelihood (workflow_dispatch only), real class.
2. **Model env fallback**: `LLM_MODEL: inputs.model || vars.LLM_MODEL
   || 'gpt-5.6-luna'` — the bare final fallback lacks the provider
   prefix and would 404 on OpenRouter if repo vars were ever unset.
   Latent (vars currently set — run 24 engine line confirms
   openai/gpt-5.6-luna).
3. **Legacy chains remain executable** (`chain`, `update`, `learn`,
   `pipeline`) — see RC-3.
4. **Cancelled-run artifacts**: a cancelled run may still upload a
   partial artifact; scoring must check run conclusion before scoring
   an artifact (this audit did).

## 5. Corrective actions (PROPOSED — nothing further dispatched or
changed without owner approval, per the standing halt)

1. **`tools/dispatch.sh` in the repo** — the one canonical dispatch:
   explicit `action: updater`, ref, inputs; then polls the RUN LOG for
   the updater fingerprint within ~5 min; on mismatch it CANCELS the
   run itself and exits loudly. The monitor calls this script; nothing
   dispatches by hand-built curl again.
2. **Workflow hardening** — default already flipped to `updater`
   (committed 24c02d2). Proposed further: legacy actions require an
   explicit `i-mean-the-legacy-agent` value, or are deleted.
3. **Runbook line in HANDOFF.md** — how a run is dispatched, verified,
   scored; so no future session rebuilds it from memory.
4. **Status-reporting rule (process, no code):** no claim "run N is
   running X" until the run's own log shows X's fingerprint.

## 6. Cost accounting

~66 min of CI on wrong-chain runs (25: 14 min, 26: 52 min), plus the
owner's attention across three dispatch cycles, plus run 27 (~10 min,
correct chain, stopped on order). The extraction-first head — benchmark
green — has still never flown.
