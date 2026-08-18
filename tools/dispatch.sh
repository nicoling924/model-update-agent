#!/usr/bin/env bash
# THE ONE CANONICAL DISPATCH (AUDIT_2026-08-18_dispatch.md, owner-approved).
#
#   tools/dispatch.sh <company> <period>
#
# Never hand-build a dispatch curl again. This script:
#   1. asserts local rebuild == origin/rebuild (never fly an unpushed head)
#   2. dispatches with action=updater EXPLICIT, with backoff on 5xx
#   3. resolves the run id by created-after filter (no newest-run race)
#   4. asserts the run's head_sha is the sha we just verified
#   5. waits; on completion downloads the log and asserts the UPDATER
#      FINGERPRINT ([run] DELIVERED / [run] census) before reporting
#      success — a run whose log lacks the fingerprint is reported as
#      WRONG-CHAIN, exit 2, never as a result.
# Output lines are the event stream for a Monitor.
set -euo pipefail
REPO="nicoling924/model-update-agent"
REF="rebuild"
COMPANY="${1:?usage: dispatch.sh <company> <period>}"
PERIOD="${2:?usage: dispatch.sh <company> <period>}"
cd "$(dirname "$0")/.."

TOKEN=$(printf "protocol=https\nhost=github.com\n" | git credential fill \
        | grep '^password=' | cut -d= -f2-)
API="https://api.github.com/repos/$REPO"
auth() { curl -s -H "Authorization: Bearer $TOKEN" \
              -H "Accept: application/vnd.github+json" "$@"; }

# 1. the head we think we are flying must BE the pushed head
git fetch -q origin "$REF"
LOCAL=$(git rev-parse "$REF")
REMOTE=$(git rev-parse "origin/$REF")
if [ "$LOCAL" != "$REMOTE" ]; then
  echo "ABORT: local $REF ($LOCAL) != origin/$REF ($REMOTE) — push first"
  exit 1
fi
echo "head verified: $LOCAL"

BEFORE=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# 2. dispatch, action explicit
for i in 1 2 3 4 5; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
    "$API/actions/workflows/update.yml/dispatches" \
    -d "{\"ref\":\"$REF\",\"inputs\":{\"company\":\"$COMPANY\",\"period\":\"$PERIOD\",\"action\":\"updater\"}}" \
    || echo 000)
  if [ "$code" = "204" ]; then
    echo "dispatched $COMPANY $PERIOD (action=updater explicit, attempt $i)"
    break
  fi
  echo "dispatch attempt $i: HTTP $code — retrying" >&2
  [ "$i" = 5 ] && { echo "DISPATCH FAILED after 5 attempts"; exit 1; }
  sleep $((i * 20))
done

# 3. resolve the run created after our dispatch (no newest-run race)
RID=""
for _ in 1 2 3 4 5 6; do
  sleep 10
  RID=$(auth "$API/actions/runs?branch=$REF&event=workflow_dispatch&created=%3E$BEFORE&per_page=5" \
    | python3 -c "import json,sys; d=json.load(sys.stdin, strict=False); rs=d.get('workflow_runs') or []; print(rs[0]['id'] if rs else '')" \
    2>/dev/null || echo "")
  [ -n "$RID" ] && break
done
[ -z "$RID" ] && { echo "ABORT: dispatched but no run appeared after $BEFORE"; exit 1; }

# 4. the run must be on the sha we verified
RSHA=$(auth "$API/actions/runs/$RID" | python3 -c \
  "import json,sys; print(json.load(sys.stdin, strict=False).get('head_sha',''))")
if [ "$RSHA" != "$LOCAL" ]; then
  echo "ABORT: run $RID is on $RSHA, not $LOCAL — cancelling it"
  auth -X POST "$API/actions/runs/$RID/cancel" > /dev/null || true
  exit 1
fi
echo "run id: $RID (sha verified)"

# 5. wait, then assert the updater fingerprint before reporting
while true; do
  ST=$(auth "$API/actions/runs/$RID" | python3 -c \
    "import json,sys; d=json.load(sys.stdin, strict=False); print(d.get('status',''), d.get('conclusion') or '')" \
    2>/dev/null || echo "")
  case "$ST" in
    completed*) break ;;
  esac
  sleep 60
done
TMP=$(mktemp -d)
auth -L "$API/actions/runs/$RID/logs" -o "$TMP/logs.zip" || true
if unzip -o -q "$TMP/logs.zip" -d "$TMP" 2>/dev/null \
   && grep -rql "\[run\] DELIVERED\|\[run\] census" "$TMP"; then
  echo "run $RID FINISHED ($ST) — UPDATER FINGERPRINT VERIFIED"
  rm -rf "$TMP"
  exit 0
fi
rm -rf "$TMP"
echo "run $RID finished ($ST) but the updater fingerprint is ABSENT — WRONG CHAIN OR CRASH; do not score this run"
exit 2
