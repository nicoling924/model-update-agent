"""Offline failure-class benchmark — gate v2 (owner: no half-edited heads).

Every failure class bought with a live run-hour becomes an offline check.
A head is dispatch-eligible ONLY when the WHOLE benchmark is green — the
part just edited and every part that wasn't. Live runs stop being
discovery tools.

    python3 tools/benchmark.py <company_dir> <period> <target_year>

Layers:
1. DRY OUTCOMES — the deterministic pipeline on a scratch copy: balance
   scorecard across ALL years + the pinned printed-key panel (key_gate).
2. READING HEALTH — the evidence pool rebuilt offline (stage-1 + ingest
   cache replay + closure): every statement-face section either closes
   or emits a derived gap; unresolved sections are listed.
3. CARD COVERAGE — for every target row the deterministic ground pass
   leaves unserved, which card channel puts evidence in front of the
   agent (oracle / pool / closure / gap / sighting / last-year map /
   counterpart). A row the current document DEMONSTRABLY carries (its
   prior is locatable in the extraction) with NO channel is a FAIL —
   that is precisely the class that burned runs 23/24.
4. REGRESSION PINS — replay/<period>/probes.json names the historical
   failure cells and the channel that must now cover each.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.ledger import vintage_ban as _vintage_ban  # noqa: E402


def _build_pool(company_dir, period, target_year, log=None):
    """Rebuild the run's evidence world offline. Fidelity rule (run-24
    gate lesson): the scanned statement pages exist only as VISION items,
    and the vision cache lives on CI — so a purely local rebuild scores a
    DIFFERENT, smaller world than the live run (that is how a green gate
    once cleared a corrupted head). The latest run's replay ledger seeds
    the vision channel; everything else replays deterministically."""
    from updater import spec as spec_mod
    from updater import targets as targets_mod
    from updater.reading import read_complete
    from updater.run import _disclosures, _model_path
    from updater.stage1_read import read_documents
    from updater.writer import load
    log = log or (lambda *a, **k: None)
    company_dir = Path(company_dir)
    try:
        spec_d = spec_mod.load(company_dir, None)
    except Exception:
        from updater.discover import discover
        p = _model_path(company_dir, {})
        spec_d = discover(load(p), load(p, data_only=True),
                          target_year=target_year, period_kind="FY")
    spec_mod.extend_axis(spec_d, target_year)
    from updater.run import ensure_keys
    ensure_keys(spec_d, company_dir, target_year, lambda *a, **k: None)
    model_path = _model_path(company_dir, spec_d)
    wbv = load(model_path, data_only=True)
    wbf = load(model_path)
    targets = targets_mod.from_workbook(wbv, spec_d, target_year,
                                        wb_formulas=wbf)
    known = targets_mod.known_prior_values(targets)
    docs = _disclosures(company_dir, period)
    ledger = read_documents(docs, client=None, known_values=known,
                            log=lambda *a, **k: None)
    # seed the vision channel from the latest live run's replay ledger
    replay = company_dir / "replay" / str(period) / "ledger.json"
    if replay.exists():
        from updater.ledger import Ledger
        prev = Ledger.load(replay)
        have = {(it.doc, it.page, it.label, tuple(it.nums))
                for it in ledger.items}
        n = 0
        for it in prev.items:
            if getattr(it, "channel", "") != "vision":
                continue
            if (it.doc, it.page, it.label, tuple(it.nums)) in have:
                continue
            it.disputed = False
            ledger.items.append(it)
            if (it.doc, it.page) in prev.faces:
                ledger.faces.setdefault((it.doc, it.page),
                                        prev.faces[(it.doc, it.page)])
            n += 1
        log(f"  (seeded {n} vision items from {replay})")
    ledger.ensure_vintage(
        [t.prior_value for t in targets
         if isinstance(t.prior_value, (int, float))],
        [t.prior2_value for t in targets
         if isinstance(getattr(t, "prior2_value", None), (int, float))],
        log=lambda *a, **k: None)
    reading = read_complete(ledger, targets, None, docs, spec_d, log)
    return spec_d, targets, ledger, reading


def _section_health(ledger):
    from updater.closure import _sections, _solve, normalized_rows
    from updater.ledger import JOIN_FACES
    prior_docs = _vintage_ban(ledger)
    groups = {}
    for it in ledger.items:
        if (it.doc in prior_docs or it.table_id is None
                or getattr(it, "channel", "") in ("closure", "closure-gap")
                or ledger.faces.get((it.doc, it.page))
                not in JOIN_FACES):
            continue
        groups.setdefault((it.doc, it.page, it.table_id), []).append(it)
    closed = gapped = unresolved = 0
    bad = []
    for key, rows in sorted(groups.items()):
        rows.sort(key=lambda x: x.row_ord)
        for s_row, sec, carry in _sections(normalized_rows(rows)):
            solved, _ones = _solve(s_row, sec)
            if carry is not None and (solved is None
                                      or solved[0] == "gap"):
                s2, _o2 = _solve(s_row, sec + [carry])
                if s2 is not None and s2[0] in ("closed", "closed_col"):
                    solved = s2
            if solved is None:
                unresolved += 1
                bad.append(f"p{key[1]} '{s_row.label[:24]}'")
            elif solved[0] == "closed":
                closed += 1
            else:
                gapped += 1
    return closed, gapped, unresolved, bad


def _channels(ledger, targets, served):
    """{(sheet,row): set(channel)} for unserved rows with a real prior."""
    from updater.numerics import SCALES, to_model_units
    from updater.packets import current_sightings, prior_map_hints
    from updater.stage2_join import unique_evidence_value
    tl = list(targets)
    open_rows = [t for t in tl
                 if t.key not in served
                 and isinstance(t.prior_value, (int, float))
                 and abs(t.prior_value) >= 1.0]
    rows_fmt = [{"cell": f"{t.sheet}!{t.row}", "label": str(t.label),
                 "prior": t.prior_value} for t in open_rows]
    pm = prior_map_hints(ledger, rows_fmt)
    cs = current_sightings(ledger, rows_fmt)
    prior_docs = _vintage_ban(ledger)
    out = {}
    for t in open_rows:
        pv, ch = t.prior_value, set()
        tol = max(0.6, abs(pv) * 5e-4)
        if unique_evidence_value(ledger, tl, t) is not None:
            ch.add("oracle")
        for it in ledger.items:
            if it.doc in prior_docs:
                continue
            c = getattr(it, "channel", "")
            tie = any(abs(abs(to_model_units(n, s)) - abs(pv)) <= tol
                      for n in it.nums for s in SCALES)
            if not tie:
                continue
            if c == "closure":
                ch.add("closure")
            elif getattr(it, "verified", False):
                ch.add("pool")
            ch.add("locatable")
        for it in ledger.items:
            # a derived gap ATTACHES by proximity, not identity — the
            # missing row's print differs from the model's row exactly
            # when the model adjusts it (the 销售商品/金融类 carve-out)
            if getattr(it, "channel", "") == "closure-gap" \
                    and len(it.nums) == 2 and it.nums[1] and any(
                        abs(abs(to_model_units(it.nums[1], s)) - abs(pv))
                        <= abs(pv) * 0.05 for s in SCALES):
                ch.add("gap")
        cell = f"{t.sheet}!{t.row}"
        if cell in cs:
            ch.add("sighting")
        for h in pm.get(cell, []):
            ch.add("map")
            if "COUNTERPART" in h:
                ch.add("counterpart")
        out[(t.sheet, t.row)] = ch
    return out


def main(company_dir, period, target_year):
    company_dir = Path(company_dir)
    fails = []

    print("== LAYER 0: static sanity (undefined names crash live paths "
          "the dry gate never executes — run 34) ==")
    r0 = subprocess.run([sys.executable, "-m", "pyflakes", "updater",
                         "tools"], capture_output=True, text=True)
    undef = [ln for ln in r0.stdout.splitlines() if "undefined name" in ln]
    for ln in undef[:6]:
        print("  " + ln)
    if undef:
        fails.append(f"{len(undef)} undefined names (live-path crashes)")
    else:
        print("  clean")

    print("== LAYER 1: dry outcomes (key gate: balance + printed keys) ==")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "key_gate.py"),
                        str(company_dir), period, str(target_year)],
                       capture_output=True, text=True)
    print(r.stdout.strip()[-600:])
    if r.returncode != 0:
        fails.append("key gate not green")

    print("\n== LAYER 2: the reading stage (spine, articulation, "
          "sufficiency) ==")
    spec_d, targets, ledger, reading = _build_pool(
        company_dir, period, int(target_year), log=print)
    closed, gapped, unresolved, bad = _section_health(ledger)
    print(f"  sections: {closed} closed, {gapped} gap-derived, "
          f"{unresolved} unresolved")
    for b in bad[:6]:
        print(f"    unresolved: {b}")
    if closed == 0:
        fails.append("no section closed — reading layer blind")
    art = reading.get("articulation") or {}
    for k, v in art.items():
        print(f"  articulation {k}: {'OK' if v else 'FAIL'}")
        if not v:
            fails.append(f"articulation {k} FAILED — extracted columns "
                         f"do not share one reality")
    if not art:
        print("  articulation: not provable offline (keys not located)")
    print(f"  sufficiency: {reading['located']}/{reading['inventory']} "
          f"open-row priors located; {len(reading['unlocated'])} "
          f"unlocated")

    print("\n== LAYER 3: card coverage on unserved rows ==")
    from updater.ops import run_join
    served, _dec = run_join(ledger, targets, [])
    ch = _channels(ledger, targets, served)
    locatable = {k for k, v in ch.items() if "locatable" in v}
    covered = {k for k in locatable
               if ch[k] & {"oracle", "pool", "closure", "gap", "sighting"}}
    naked = sorted(locatable - covered)
    print(f"  {len(served)} rows served deterministically; "
          f"{len(ch)} open; {len(locatable)} locatable in the current "
          f"doc; {len(covered)} covered by a card channel")
    for k in naked[:10]:
        print(f"    LOCATABLE BUT NAKED: {k[0]}!{k[1]}")
    if naked:
        fails.append(f"{len(naked)} locatable rows reach the agent with "
                     f"no evidence channel")
    mapped = sum(1 for v in ch.values() if "map" in v)
    print(f"  last-year map: hints on {mapped}/{len(ch)} open rows")

    print("\n== LAYER 4: regression pins ==")
    probes = company_dir / "replay" / period / "probes.json"
    if probes.exists():
        pins = json.loads(probes.read_text())
        for cell, need in sorted(pins.items()):
            watch = need.startswith("watch:")
            need_ch = need.split(":", 1)[-1]
            sheet, row = cell.rsplit("!", 1)
            got = ch.get((sheet, int(row)), set())
            if (sheet, int(row)) in served:
                status = "served"          # the pipeline now writes it
            elif need_ch in got:
                status = "ok"
            elif watch:
                # a WATCH pin names a failure only the agent's judgment
                # can cover (no deterministic anchor exists in either
                # document) — reported for the analyst, never gating
                status = "watch"
            else:
                status = "FAIL"
                fails.append(f"pin {cell}: needs '{need_ch}', has "
                             f"{sorted(got) or 'nothing'}")
            print(f"  [{status}] {cell}: requires '{need}' "
                  f"(has: {', '.join(sorted(got)) or 'served/none'})")
    else:
        print(f"  (no pins at {probes})")

    print("\n" + "=" * 60)
    if fails:
        print(f"BENCHMARK: {len(fails)} FAILURES")
        for f in fails:
            print(f"  - {f}")
        print("VERDICT: DO NOT DISPATCH — the head is not whole")
        return 1
    print("BENCHMARK: all layers green")
    print("VERDICT: dispatch-eligible")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
