#!/bin/sh
# Run the studio-native core museum tests without Node: concatenate the
# pure-logic core + tests into one file and run it on JavaScriptCore
# (osascript -l JavaScript). Falls back to Node when available.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
if command -v node >/dev/null 2>&1; then
  node "$DIR/test/core.test.js"
  exit $?
fi
TMP="${TMPDIR:-/tmp}/studio_core_tests.$$.js"
cat "$DIR/core/axis.js" "$DIR/core/ties.js" "$DIR/test/core.test.js" > "$TMP"
OUT=$(osascript -l JavaScript "$TMP" 2>&1)
rm -f "$TMP"
echo "$OUT"
TMP2="${TMPDIR:-/tmp}/studio_e2e_tests.$$.js"
cat "$DIR/test/mock_excel.js" "$DIR/core/axis.js" "$DIR/core/ties.js" \
    "$DIR/kernel/kernel.js" "$DIR/test/kernel.e2e.js" > "$TMP2"
OUT2=$(osascript -l JavaScript "$TMP2" 2>&1)
rm -f "$TMP2"
echo "$OUT2"
case "$OUT$OUT2" in
  *"museum: "*" 0 fail"*"e2e: "*" 0 fail"*) exit 0 ;;
  *) exit 1 ;;
esac
