#!/bin/sh
# Dispatch the model-update chain on GitHub Actions.
# Usage: sh dispatch.sh [COMPANY] [PERIOD] [PRIOR_PERIOD] [BRANCH]
COMPANY="${1:-CLP}"; PERIOD="${2:-FY25}"; PRIOR="${3:-FY24}"; BRANCH="${4:-objective-driven}"
TOKEN=$(printf "protocol=https\nhost=github.com\n" | git credential fill | grep "^password=" | cut -d= -f2)
[ -z "$TOKEN" ] && { echo "no stored GitHub credential found"; exit 1; }
CODE=$(curl -s -o /tmp/dispatch_resp.txt -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/nicoling924/model-update-agent/actions/workflows/update.yml/dispatches \
  -d "{\"ref\":\"$BRANCH\",\"inputs\":{\"company\":\"$COMPANY\",\"period\":\"$PERIOD\",\"prior_period\":\"$PRIOR\",\"action\":\"chain\"}}")
if [ "$CODE" = "204" ]; then
  echo "DISPATCHED: $COMPANY $PERIOD chain on branch $BRANCH"
  echo "watch: https://github.com/nicoling924/model-update-agent/actions"
else
  echo "FAILED ($CODE):"; cat /tmp/dispatch_resp.txt
fi
