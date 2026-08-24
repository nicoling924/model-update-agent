"""One update, end to end — the ALWAYS-DELIVER run (BOSS_MINDMAP law).

    archive + snapshot -> spec/discovery -> census -> digest (read once)
    -> RESTATEMENT gate (the one human pause) -> THE AGENT LOOP (owns
    everything: rollover, join, reads, fixes, adjustments, flags, plugs)
    -> POLICE (verdicts; findings loop back, bounded) -> _REPORT / _SPEC
    -> DELIVER. Always.

There is no refusal path and no quarantine filename. What is unproven is
flagged; what is not disclosed is proven-searched and listed; the analyst
reviews inside Excel.

client=None = dry run: deterministic tools only (rollover, join, stale
sweep, police deterministic layer), scripted directly as a TEST harness —
the production control flow is the agent's own decisions.
"""
import json
import re
import shutil
from pathlib import Path

from . import ops
from . import police as police_mod
from . import report as report_mod
from . import restate as restate_mod
from . import spec as spec_mod
from . import targets as targets_mod
from .evidence import EvidenceBook
from .loop import AgentLoop
from .stage1_read import read_documents
from .stage2_join import decisions_to_json
from .writer import Writer, formula_map, load, save


def _model_path(company_dir, spec):
    mdir = Path(company_dir) / "model"
    if spec.get("model_file") and (mdir / spec["model_file"]).exists():
        return mdir / spec["model_file"]
    cands = sorted([p for p in mdir.glob("*.xls[xm]")
                    if not p.name.startswith("~$")
                    and "(updater" not in p.name
                    and "(pipeline" not in p.name],
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        raise FileNotFoundError(f"no model workbook in {mdir}")
    return cands[0]


def _disclosures(company_dir, period):
    d = Path(company_dir) / "disclosures"
    sub = d / period
    root = sub if sub.is_dir() else d
    return sorted(str(p) for p in root.glob("*.[pP][dD][fF]"))


def ensure_keys(spec_d, company_dir, target_year, log):
    """Supplement key/check rows from discovery (additive — a spec without
    key_rows would make Police law 4 pass vacuously) plus the cross-sheet
    prior-consistency filter. Shared by the live run and the offline
    benchmark so both score the SAME key set."""
    if not spec_d.get("key_rows") or not spec_d.get("check_rows"):
        from .discover import discover
        probe_path = _model_path(company_dir, spec_d)
        found = discover(load(probe_path), load(probe_path, data_only=True),
                         target_year=target_year)
        for part in ("key_rows", "check_rows"):
            if not spec_d.get(part):
                spec_d[part] = found.get(part) or []
                log(f"[run] spec had no {part} — supplemented "
                    f"{len(spec_d[part])} from discovery")
        # CROSS-SHEET PRIOR CONSISTENCY (run-2 autopsy: label-matching put
        # 'total liabilities' on a 9,954 note row when the real figure is
        # ~114,500). The same consolidated key must hold ≈ the same prior
        # on every sheet: keys whose prior deviates >20% from the same-name
        # key's median prior across sheets are dropped as mismapped.
        from .checks import prior_column as _pc, year_columns as _yc
        wbv = load(_model_path(company_dir, spec_d), data_only=True)
        by_name = {}
        for k in spec_d.get("key_rows") or []:
            pcol = _pc(spec_d, k["sheet"], target_year)
            if not pcol or k["sheet"] not in wbv.sheetnames:
                continue
            v = wbv[k["sheet"]][f"{pcol}{int(k['row'])}"].value
            if isinstance(v, (int, float)) and v != 0:
                by_name.setdefault(k.get("name", ""), []).append((k, v))
        keep, dropped = [], []
        for name, rows in by_name.items():
            vals = sorted(abs(v) for _k, v in rows)
            med = vals[len(vals) // 2]
            for k, v in rows:
                if len(rows) >= 2 and med and abs(abs(v) - med) / med > 0.2:
                    dropped.append(f"{k['sheet']}!{k['row']} ({name}: "
                                   f"{v:,.0f} vs median {med:,.0f})")
                else:
                    keep.append(k)
        named = {id(k) for k in keep}
        spec_d["key_rows"] = [k for k in spec_d.get("key_rows") or []
                              if not by_name.get(k.get("name", ""))
                              or id(k) in named]
        if dropped:
            log(f"[run] dropped {len(dropped)} mismapped discovered keys: "
                + "; ".join(dropped[:5]))



def update(company_dir, period, target_year, client=None, loop_budget=120,
           log=print):
    company_dir = Path(company_dir)
    run_log = []

    # -- spec or discovery (no spec anywhere -> the agent reasons the model
    # out itself; the draft persists to _SPEC for the analyst)
    wb_probe = None
    if not (company_dir / "spec.yaml").exists() \
            and not (company_dir / "spec.json").exists():
        wb_probe = load(_model_path(company_dir, {}), data_only=False)
    try:
        spec_d = spec_mod.load(company_dir, wb_probe)
    except spec_mod.SpecError:
        from .discover import discover
        kind = ("1H" if str(period).upper().startswith(("1H", "2H", "H1", "H2"))
                else "Q" if "Q" in str(period).upper() else "FY")
        probe_path = _model_path(company_dir, {})
        spec_d = discover(load(probe_path), load(probe_path, data_only=True),
                          target_year=target_year, period_kind=kind)
        log(f"[run] no spec — anatomy AUTO-DISCOVERED "
            f"({len(spec_d['year_axis'])} sheets, "
            f"{len(spec_d['check_rows'])} checks, "
            f"{len(spec_d['key_rows'])} keys)")
    # INTERIM PERIODS (owner test, 2026-08-25): a half-year/quarterly run
    # must target the model's OWN interim columns (H125 / 1H2025 / Q125),
    # which an annual spec cannot name — the axis is rebuilt from the
    # workbook's headers via discovery (period_kind-aware), sheets without
    # interim columns drop out of scope automatically, and the annual
    # extend step is skipped (interim columns already exist).
    _p = str(period).upper()
    _m = re.match(r"^([12])H|^H([12])", _p) or re.match(r"^([1-4])Q|^Q([1-4])", _p)
    if _m and "H" in _p[:3]:
        _kind = (_m.group(1) or _m.group(2)) + "H"
    elif _m:
        _kind = (_m.group(1) or _m.group(2)) + "Q"
    else:
        _kind = "FY"
    if _kind != "FY":
        from .discover import find_year_axis
        probe_f = load(_model_path(company_dir, spec_d))
        interim_axis = {}
        for sh in probe_f.sheetnames:
            ax = find_year_axis(probe_f[sh], period_kind=_kind)
            if ax and str(target_year) in ax:
                interim_axis[sh] = {"columns": ax}
        if not interim_axis:
            raise SystemExit(
                f"no interim ({_kind}) columns found for {target_year} in "
                f"the model — cannot run period {period}")
        spec_d["year_axis"] = interim_axis
        log(f"[run] interim axis ({_kind}): "
            + ", ".join(f"{sh}!{v['columns'][str(target_year)]}"
                        for sh, v in sorted(interim_axis.items())))
    else:
        spec_mod.extend_axis(spec_d, target_year)
    # A spec without key_rows would make Police law 4 pass VACUOUSLY (the
    # run-1-live false PASS): supplement keys/checks from discovery so the
    # law always has teeth. Discovery is additive here — never overrides
    # what the spec already declares.
    ensure_keys(spec_d, company_dir, target_year, log)

    model_path = _model_path(company_dir, spec_d)
    archive = (company_dir / "model-archive"
               / f"{model_path.stem}_{period}_pre{model_path.suffix}")
    archive.parent.mkdir(exist_ok=True)
    shutil.copy2(model_path, archive)
    log(f"[run] model: {model_path.name} (archived)")

    wb = load(model_path)
    wb_values = load(model_path, data_only=True)
    pre_map = formula_map(wb)
    snapshot = report_mod.snapshot_projections(wb_values, spec_d, target_year)

    # -- census + digest (read once; artifacts cached by stage 1)
    targets = targets_mod.from_workbook(wb_values, spec_d, target_year,
                                        wb_formulas=wb)
    known = targets_mod.known_prior_values(targets)
    log(f"[run] census: {len(targets)} target rows, {len(known)} priors")
    docs = _disclosures(company_dir, period)
    if not docs:
        raise FileNotFoundError(f"no disclosures for {period} under {company_dir}")
    ledger = read_documents(docs, client=client, known_values=known, log=log)
    # VINTAGE AT READ TIME (run-19 fundamental): which document is the
    # current period is a property of the ledger, established here for
    # every consumer — never a join side-effect, never silent.
    ledger.ensure_vintage(
        [t.prior_value for t in targets
         if isinstance(t.prior_value, (int, float))],
        [t.prior2_value for t in targets
         if isinstance(getattr(t, "prior2_value", None), (int, float))],
        log=log)
    # THE ONE READING STAGE (extraction-first — council ruling 2026-08-18):
    # entity quarantine -> spine read + closure + articulation with live
    # repair -> demand-driven notes -> sufficiency inventory. The mapping
    # world is COMPLETE AND PROVEN before any agent judgment; the old
    # channels live inside this stage as repair tactics. Offline (dry),
    # the same stage replays caches so the gate scores the same world.
    from .reading import read_complete
    reading_report = read_complete(ledger, targets, client, docs, spec_d,
                                   log)
    run_log.append(
        f"reading: {reading_report['located']}/"
        f"{reading_report['inventory']} priors located, "
        f"articulation {reading_report['articulation']}, "
        f"{len(reading_report['unlocated'])} unlocated")

    # -- THE ONE PAUSE: restatement (before any write; resume-friendly)
    restatement = restate_mod.check_or_pause(company_dir, period, ledger,
                                             targets, run_log, client=client)
    for ln in run_log[-2:]:
        log(f"[run] {ln}")

    writer = Writer(wb)
    book = EvidenceBook()
    census = {}
    loop_summary = ""
    verdict = None

    loop = None
    if client is not None:
        # -- GROUND (deterministic — mechanics are hands, not judgment):
        # rollover, join, guarded serving, checksummed gap reads.
        census.update(ops.rollover_all(wb, spec_d, target_year, writer,
                                       run_log.append))
        served, _dec = ops.run_join(ledger, targets, run_log)
        priors = {t.key: t.prior_value for t in targets}
        ops.write_served(wb, spec_d, target_year, served, writer, priors,
                         book, run_log.append)
        na = ops.home_serves(wb, spec_d, target_year, ledger, targets,
                             served, run_log.append)
        na.update(ops.note_anchored_serves(ledger, targets, served,
                                           run_log.append))
        na.update(ops.new_line_serves(wb, spec_d, target_year, ledger,
                                      targets, served, run_log.append))
        na.update(ops.matrix_serves(wb, spec_d, target_year, ledger,
                                    targets, served, run_log.append,
                                    docs=docs))
        served.update(na)
        ops.write_served(wb, spec_d, target_year, na, writer, priors,
                         book, run_log.append)
        from .stage3_read import read_gaps
        gap = read_gaps(ledger, targets, served, client, docs, run_log)
        ops.consensus_filter(gap, ledger, targets, run_log.append)
        served.update(gap)
        ops.write_served(wb, spec_d, target_year, gap, writer, priors,
                         book, run_log.append)
        for ln in run_log[-4:]:
            log(f"[run] {ln}")
        _ruling_p = company_dir / 'updates' / 'rebased_ruling.json'
        _ruling = (json.loads(_ruling_p.read_text())
                   if _ruling_p.exists() else None)
        ops.declare_rebased_blocks(wb, spec_d, target_year, ledger,
                                   targets, writer, book, run_log.append,
                                   ruling=_ruling)
        # -- THE AGENT thinks from here (packetized L0/L1 — REDESIGN.md)
        loop = AgentLoop(wb, spec_d, target_year, ledger, targets, served,
                         writer, book, client, run_log, budget=loop_budget,
                         restatement=restatement, docs=docs, census=census)
        from .closer import PacketCloser
        closer = PacketCloser(loop, client, log)
        loop_summary = closer.run()
        log(f"[run] closer: {loop_summary[:200]}")
        # -- POLICE cycles: verdict -> findings -> repair packets
        seen_findings = set()
        for cycle in range(police_mod.POLICE_CYCLES):
            verdict = police_mod.verify(wb, spec_d, target_year, ledger,
                                        targets, served, book, writer.log)
            findings = list(verdict["findings"])
            findings += police_mod.llm_review(client, verdict, wb, spec_d,
                                              target_year, book, writer.log,
                                              log)
            open_findings = [f for f in findings
                             if f and f not in seen_findings]
            seen_findings.update(open_findings)
            if not open_findings:
                break
            log(f"[run] police cycle {cycle + 1}: "
                f"{len(open_findings)} findings -> repair packets")
            closer.run_repairs(open_findings)
        # -- THE CLOSING BELL (council wall-2): one deterministic final
        # disposition per still-failing residual generator — an executed
        # plug or a reasoned flag; the endgame draw disappears.
        closer.closing_bell()
        # -- STRUCTURAL HONESTY (run-2 owner review): every unserved rolled
        # hardcode is flagged, every still-failing check cell marked.
        # Honesty is CODE, never an agent choice.
        ops.flag_stale(wb, spec_d, target_year, census, served, writer,
                       book, run_log.append, ledger=ledger)
        ops.sweep_compositions(wb, spec_d, target_year, census, writer,
                               book, run_log.append)
        ops.flag_failed_checks(wb, spec_d, target_year, writer, book,
                               run_log.append)
        for ln in run_log[-3:]:
            log(f"[run] {ln}")
        verdict = police_mod.verify(wb, spec_d, target_year, ledger, targets,
                                    served, book, writer.log)
    else:
        # -- dry-run TEST harness: deterministic tools, scripted
        log("[run] DRY RUN: deterministic tools only")
        census.update(ops.rollover_all(wb, spec_d, target_year, writer,
                                       run_log.append))
        served, decisions = ops.run_join(ledger, targets, run_log)
        priors = {t.key: t.prior_value for t in targets}
        ops.write_served(wb, spec_d, target_year, served, writer, priors,
                         book, run_log.append)
        na = ops.home_serves(wb, spec_d, target_year, ledger, targets,
                             served, run_log.append)
        na.update(ops.note_anchored_serves(ledger, targets, served,
                                           run_log.append))
        na.update(ops.new_line_serves(wb, spec_d, target_year, ledger,
                                      targets, served, run_log.append))
        na.update(ops.matrix_serves(wb, spec_d, target_year, ledger,
                                    targets, served, run_log.append,
                                    docs=docs))
        served.update(na)
        ops.write_served(wb, spec_d, target_year, na, writer, priors,
                         book, run_log.append)
        ops.implied_prior_candidates(wb, spec_d, target_year, targets,
                                     ledger, served, run_log.append)
        ops.flag_stale(wb, spec_d, target_year, census, served, writer,
                       book, run_log.append, ledger=ledger)
        ops.sweep_compositions(wb, spec_d, target_year, census, writer,
                               book, run_log.append)
        ops.flag_failed_checks(wb, spec_d, target_year, writer, book,
                               run_log.append)
        for ln in run_log[-6:]:
            log(f"[run] {ln}")
        verdict = police_mod.verify(wb, spec_d, target_year, ledger, targets,
                                    served, book, writer.log)

    # -- finish: formats, report, memory, snapshots — and DELIVER, always
    from .checks import prior_column, year_columns
    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if tcol and pcol and sheet in wb.sheetnames:
            writer.format_rollover(sheet, pcol, tcol)

    adjustments = loop._adjustments if loop is not None else None
    report_mod.build_report(wb, spec_d, target_year, book, snapshot,
                            adjustments=adjustments, police=verdict,
                            loop_summary=loop_summary,
                            reading=reading_report, client=client)
    spec_d["_last_run"] = {
        "period": period, "served": len(served),
        "flags": len(set(writer.log["flags"])),
        "police": {k: v for k, v in (verdict or {}).get("laws", {}).items()}}
    spec_mod.write_spec_tab(wb, spec_d)

    replay_dir = company_dir / "replay" / str(period)
    replay_dir.mkdir(parents=True, exist_ok=True)
    ledger.save(replay_dir / "ledger.json")
    targets_mod.save(targets, replay_dir / "targets.json")
    (replay_dir / "run_log.txt").write_text("\n".join(run_log),
                                            encoding="utf-8")

    out_path = (company_dir / "model"
                / f"{model_path.stem} {period} (updater){model_path.suffix}")
    save(wb, out_path)
    laws = (verdict or {}).get("laws", {})
    log(f"[run] DELIVERED: {out_path.name}  police={laws}")
    return {"ok": True, "out": str(out_path), "archive": str(archive),
            "served": len(served), "police": laws,
            "flags": len(set(writer.log["flags"])),
            "replay": str(replay_dir)}
