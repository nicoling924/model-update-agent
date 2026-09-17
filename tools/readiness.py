#!/usr/bin/env python3
"""READINESS — answer the cards the way the brain is expected to, on a
live run's own ledger, and PROVE the answers land in the cells.

Born of runs 250-253 (owner: "can u test before running"): the floors
replay with default answers (no brain), so a card the brain answers
correctly but the tool then refuses never shows offline. This drives
the exact card -> answer -> tool -> cell path for named cells.

usage: python3 tools/readiness.py <company_dir> <PERIOD> <YEAR> <artifact_dir> \
           "Sheet!Cell=<substring of the wanted option line>[=expected value]" ...

For each named cell the card is answered with the option whose line
contains the substring (else the default); at the end the cell's value,
fill and note are printed and checked against the expected value when
given. Exit 1 if any expectation fails or the run is refused.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main(argv):
    import json
    proposal_path = None
    if "--proposals" in argv:
        i = argv.index("--proposals")
        proposal_path = Path(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if len(argv) < 5:
        print(__doc__)
        return 2
    company, period, year, art = argv[0], argv[1], int(argv[2]), Path(argv[3])
    wants = {}
    for spec in argv[4:]:
        cell, _, rest = spec.partition("=")
        sub, _, exp = rest.partition("=")
        wants[cell.strip()] = (sub.strip(), exp.strip() or None)
    rep = art / "replay" / period
    ledger, served = rep / "ledger.json", rep / "provenance.json"
    if not ledger.exists():
        print(f"no ledger at {ledger}")
        return 2
    seen = {}

    def answerer(text, options, default):
        head = text.splitlines()[0]
        m = re.search(r"(\S+ financials!|\w+!)?([A-Za-z ]+!)?([A-Z]{1,3}\d+)", head)
        target = None
        for cell in wants:
            if cell in head:
                target = cell
        if target is None:
            return default
        sub, _ = wants[target]
        pick = default
        for line in text.splitlines():
            mm = re.match(r"\s+([A-Z]):\s", line)
            if mm and sub and sub in line:
                key = f"serve:{mm.group(1)}"
                if key in options:
                    pick = key
                    break
        seen[target] = (pick, head)
        print(f"[readiness] {target}: answered {pick} ({'matched ' + repr(sub) if pick != default else 'default'})")
        return pick

    if proposal_path:
        proposals = json.loads(proposal_path.read_text())
        from pipeline.ledger import Ledger
        evidence = Ledger.load(ledger)
        pending = [dict(p) for p in proposals]
        for p in proposals:
            candidates = [it for it in evidence.items
                          if (not p.get("doc") or it.doc == p["doc"])
                          and (not p.get("page") or it.page == p["page"])
                          and all(word.lower() in str(it.source_line or it.label).lower()
                                  for word in str(p.get("line", "")).split() if word.isalpha())]
            print(f"[readiness] {p['ref']}: {len(candidates)} source-line candidates for the supplied quote")
            seen[p["ref"]] = ("MAPPING PROPOSAL", str(p.get("line", "")))
        def maps(system, user):
            if pending:
                batch = list(pending)
                pending.clear()
                return {"calls": [{"tool": "sets", "sets": batch}]}
            return {"calls": [{"tool": "done"}]}
        answerer.maps = maps
    from pipeline.run import update
    logf = open(art / "readiness_run.log", "w")
    res = update(company, period, year, client=None, stage4_mode="queue-only",
                 stage4_answerer=answerer, pinned_ledger=str(ledger),
                 pinned_served=str(served) if served.exists() else None,
                 log=lambda s: (logf.write(str(s) + "\n"), logf.flush()))
    logf.close()
    print(f"[readiness] run log: {art / 'readiness_run.log'}")
    ok = bool(res.get("ok"))
    print("run:", "DELIVERED" if ok else "GATE REFUSED")
    import openpyxl
    out = res.get("model") or res.get("path") or res.get("out")
    if not out:
        cands = sorted(Path(company, "model").glob(f"* {period} (pipeline*.xlsx"))
        out = str(cands[-1]) if cands else None
    wb = openpyxl.load_workbook(out)
    from pipeline.evaluator import Evaluator
    ev = Evaluator(wb)
    fails = 0
    for cell, (sub, exp) in wants.items():
        sheet, coord = cell.split("!")
        c = wb[sheet][coord]
        shown = c.value
        if isinstance(c.value, str) and c.value.startswith("="):
            try:
                shown = ev.cell(sheet, coord)          # a check row is a formula: compare its VALUE
            except Exception:
                shown = c.value
        rgb = str(c.fill.fgColor.rgb or "")[-6:]
        note = (c.comment.text[:90].replace("\n", " ") if c.comment else "")
        asked = seen.get(cell, ("NO CARD", ""))[0]
        verdict = ""
        if exp is not None:
            try:
                good = abs(float(shown) - float(exp)) <= max(0.01, abs(float(exp)) * 1e-5)
            except (TypeError, ValueError):
                good = str(shown) == exp
            verdict = "OK" if good else "FAIL"
            fails += not good
        print(f"[readiness] {cell}: card {asked} -> value {shown!r} fill {rgb} {verdict} | {note}")
    return 0 if (ok and not fails) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
