#!/bin/bash
# THE BENCH — the only sanctioned pre-dispatch check. Exits nonzero on
# ANY failure, so `bash tools/bench.sh && <dispatch>` is safe to chain.
# Born of the run-19 incident: a for-loop's exit status gated nothing,
# a backgrounded chain's RED went unread, and a syntax error dispatched.
set -e
cd "$(dirname "$0")/.."
python3 -c "import sys; sys.path.insert(0,'.'); import pipeline.run, pipeline.orchestrator, pipeline.execreport, pipeline.reclass, pipeline.freeze, pipeline.writegate, pipeline.forecast_balance" \
  || { echo "BENCH RED: import/syntax"; exit 1; }
for t in tests/test_museum.py tests/test_updater_museum.py tests/test_pipeline_museum.py; do
  python3 "$t" >/dev/null 2>&1 || { echo "BENCH RED: $t"; python3 "$t" 2>&1 | tail -5; exit 1; }
done
python3 -m pipeline.execreport --selftest >/dev/null 2>&1 \
  || { echo "BENCH RED: execreport selftest"; exit 1; }
# an undefined name in a branch no floor takes (run.py's RESTATE branch used `writer` before it existed)
if python3 -m pyflakes --version >/dev/null 2>&1; then
  python3 -m pyflakes pipeline/*.py tools/*.py 2>/dev/null | grep "undefined name" && { echo "BENCH RED: undefined name"; exit 1; }
else
  echo "bench: pyflakes not installed — undefined-name check skipped (pip install pyflakes)"
fi
git diff HEAD -U0 -- pipeline | python3 tools/change_guard.py --diff \
  || { echo "BENCH RED: change guard (a fence was added — fix the cause, never patch)"; exit 1; }
# a replay that lost a stage is not a floor (run 34820388690: the table reader crashed live, unseen offline)
if grep -l "STAGE LOST" companies/*/replay/*-replay/*.txt 2>/dev/null | grep -q .; then
  echo "BENCH RED: a floor log carries STAGE LOST"; grep -h "STAGE LOST" companies/*/replay/*-replay/*.txt; exit 1
fi
echo "BENCH GREEN"
