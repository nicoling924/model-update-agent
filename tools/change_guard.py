#!/usr/bin/env python3
"""THE CHANGE GUARD — the owner's hardwire against the patching reflex
(2026-09-09: "is there any hardwire or reminder ... to prevent that").

Two uses:
  --hook   Claude Code PreToolUse hook on Edit/Write: reads the tool call
           from stdin, inspects the NEW text going into pipeline/*.py, and
           BLOCKS (exit 2) when it adds a fence — a rule about WHERE the
           agent may look or HOW MANY it may consider — printing the law.
  --diff   reads a unified diff from stdin (bench.sh: git diff HEAD -U0)
           and fails (exit 1) on the same patterns in ADDED lines.

A fence is never generic: every company prints the same figure in a
different place. Safety lives in the EVIDENCE test (number tie at the
model's precision, label kinship, blank beside the tie, subtotal
reconciliation), never in location or caps. An added line that needs one
of these patterns must carry the marker `# evidence:` on the same line
with the evidence it stands on — the guard then lets it through and the
reviewer reads the reason.
"""
import json
import re
import sys

FENCES = [
    (r"\.faces\.get\(", "page-type gate (statement faces only)"),
    (r"\bstmt_face\b", "page tag gate"),
    (r"\bJOIN_FACES\b", "faces-only pool"),
    (r"\bparent_pages\b", "page-class gate"),
    (r"\bpage\s+(?:not\s+)?in\s*\(", "page-number gate"),
    (r"\bMAX_[A-Z_]+\s*=\s*\d", "a numeric cap"),
    (r"\[\s*:\s*k\b", "a candidate cap"),
    (r"\bmax_lines\w*\s*=\s*\d", "a table-length cap"),
    (r"\bmax_rows\s*=\s*\d", "a row cap"),
    (r"\bCALL_CAP\b|\bMAX_CARDS\b|\bMAX_CANDS\s*=\s*\d", "a budget cap by count (the budget is time)"),
    (r"\bWIDE_ROW\b|is_statement_line\(", "a wide-row fence"),
    (r"\bABORT_AFTER\s*=\s*\d", "an abort-by-count fence"),
    (r"\bnoncurrent_docs\(\)|_vintage_ban\(", "prior-year documents used as a ban (allowed only as 'never a SOURCE'; identity reads must stay open)"),
]
LAW = ("CHANGE LAW (BOSS_MINDMAP 2026-08-31 / owner 2026-09-09): fix the underlying cause, never patch.\n"
       "  A rule about WHERE to look or HOW MANY to consider is a fence; fences hide evidence and are not generic.\n"
       "  Put safety in the EVIDENCE test instead: number tie at the model's precision, label kinship, blank beside\n"
       "  the tie, subtotal reconciliation. If this line truly is evidence, add `# evidence: <why>` on the same line.\n"
       "  Before any pipeline change: (1) name the root cause in one sentence, (2) state the generic rule,\n"
       "  (3) pin it in the museum, (4) replay the three ledgers, (5) readiness on the affected cells.")


def offending(lines):
    out = []
    for ln in lines:
        if "# evidence:" in ln or ln.lstrip().startswith("#"):
            continue
        for pat, why in FENCES:
            if re.search(pat, ln):
                out.append((why, ln.strip()[:110]))
                break
    return out


def main(argv):
    mode = argv[0] if argv else "--hook"
    if mode == "--hook":
        try:
            call = json.load(sys.stdin)
        except Exception:
            return 0
        ti = call.get("tool_input") or {}
        path = str(ti.get("file_path") or "")
        if "/pipeline/" not in path.replace("\\", "/") or not path.endswith(".py"):
            return 0
        new = ti.get("new_string") or ti.get("content") or ""
        if not new and isinstance(ti.get("edits"), list):
            new = "\n".join(str(e.get("new_string", "")) for e in ti["edits"])
        hits = offending(new.splitlines())
        if not hits:
            return 0
        sys.stderr.write("BLOCKED by the change guard — this edit adds a fence:\n")
        for why, ln in hits:
            sys.stderr.write(f"  - {why}: {ln}\n")
        sys.stderr.write(LAW + "\n")
        return 2
    if mode == "--diff":
        added = [ln[1:] for ln in sys.stdin.read().splitlines()
                 if ln.startswith("+") and not ln.startswith("+++")]
        hits = offending(added)
        if not hits:
            print("change guard: no fences added")
            return 0
        print("change guard RED — added lines carry fences:")
        for why, ln in hits:
            print(f"  - {why}: {ln}")
        print(LAW)
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
