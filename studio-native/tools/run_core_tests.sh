#!/bin/sh
# Full offline bench: build the typed paste artifact, strip its types
# with the REAL TypeScript compiler (so the bench exercises the exact
# file the Office Scripts editor gets), then run museum + e2e exhibits
# on JavaScriptCore. Zero installs.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
sh "$DIR/tools/build.sh" || exit 1
JS="${TMPDIR:-/tmp}/kernel.transpiled.$$.js"
# Office Scripts house lints the compiler does not enforce:
# array-method callbacks must be ARROW functions (tenant-measured law).
if grep -nE '\.(sort|map|filter|forEach|reduce|some|every|find|findIndex)\(\s*function' "$DIR/dist/kernel.paste.ts"; then
  echo "LINT FAIL: function-expression callback (Office Scripts requires arrows)"
  exit 1
fi
TC=$(osascript -l JavaScript "$DIR/tools/typecheck.jxa" \
  "$DIR/tools/vendor" "$DIR/dist/kernel.paste.ts" 2>&1)
echo "$TC"
case "$TC" in "TYPECHECK CLEAN"*) ;; *) exit 1 ;; esac
osascript -l JavaScript "$DIR/tools/transpile.jxa" \
  "$DIR/tools/vendor/typescript.js" "$DIR/dist/kernel.paste.ts" "$JS" || exit 1
TMP="${TMPDIR:-/tmp}/studio_tests.$$.js"
cat "$DIR/test/mock_excel.js" "$JS" "$DIR/test/core.test.js" \
    "$DIR/test/kernel.e2e.js" > "$TMP"
OUT=$(osascript -l JavaScript "$TMP" 2>&1)
rm -f "$TMP" "$JS"
echo "$OUT"
case "$OUT" in
  *"museum: "*" 0 fail"*"e2e: "*" 0 fail"*) exit 0 ;;
  *) exit 1 ;;
esac
