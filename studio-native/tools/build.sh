#!/bin/sh
# Build the paste-in kernel: splice the tested pure-law core into
# kernel.ts at the __CORE_LAWS__ marker, stripping the node-only export
# guards (Office Scripts allow no modules). Output: dist/kernel.paste.ts
DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$DIR/dist"
OUT="$DIR/dist/kernel.paste.ts"
CORE="${TMPDIR:-/tmp}/core_laws.$$.js"
# strip everything from the @node-only marker to end of file, per core file
for f in "$DIR/core/axis.js" "$DIR/core/ties.js"; do
  sed '/@node-only/,$d' "$f" >> "$CORE"
  printf '\n' >> "$CORE"
done
awk -v corefile="$CORE" '
  /__CORE_LAWS__/ { while ((getline line < corefile) > 0) print line; next }
  { print }
' "$DIR/kernel/kernel.js" \
  | sed 's/^function main(workbook, input)/function main(workbook: ExcelScript.Workbook, input: string): string/' \
  > "$OUT"
rm -f "$CORE"
wc -c "$OUT" | awk '{printf "built %s (%d bytes)\n", "'"$OUT"'", $1}'
