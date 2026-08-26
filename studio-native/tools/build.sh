#!/bin/sh
# Build the paste-in kernel: splice the tested core laws into kernel.ts
# at the __CORE_LAWS__ marker. Output dist/kernel.paste.ts is VERBATIM
# what goes into the Office Scripts editor (fully typed), plus a
# mail-friendly dist/kernel.txt copy.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$DIR/dist"
OUT="$DIR/dist/kernel.paste.ts"
CORE="${TMPDIR:-/tmp}/core_laws.$$.ts"
cat "$DIR/core/axis.ts" "$DIR/core/ties.ts" "$DIR/core/mapping.ts" > "$CORE"
awk -v corefile="$CORE" '
  /__CORE_LAWS__/ { while ((getline line < corefile) > 0) print line; next }
  { print }
' "$DIR/kernel/kernel.ts" > "$OUT"
rm -f "$CORE"
cp "$OUT" "$DIR/dist/kernel.txt"
wc -c "$OUT" | awk '{printf "built %s (%d bytes)\n", "'"$OUT"'", $1}'
