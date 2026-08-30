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
echo "BENCH GREEN"
