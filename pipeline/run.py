"""The run — one update, end to end, through every stage and gate.

    archive -> census -> STAGE 1 read once -> STAGE 2 join -> rollover +
    guarded writes -> STAGE 3 checksummed gap reads -> STAGE 4 verify web +
    objective loop -> delivery gate -> _REPORT / _SPEC -> deliver or refuse

Everything the run learns is persisted: the evidence ledger and join
decisions to replay/ (the pinned snapshots the validation protocol needs),
the spec back into the workbook's _SPEC tab, the analyst report as the
first sheet. A gate refusal saves to a QUARANTINE name — a refused run is
a result, not a delivery.

client=None runs every deterministic stage and skips the LLM ones (the
dry-run path); the museum plus a dry run is the pre-flight bar before any
dispatch.
"""
import shutil
from pathlib import Path

from . import gate as gate_mod
from . import report as report_mod
from . import spec as spec_mod
from . import targets as targets_mod
from .ledger import Ledger
from .orchestrator import ObjectiveLoop
from .stage1_read import read_documents
from .stage2_join import decisions_to_json, join, join_bound_tables
from .stage3_read import read_gaps
from .writer import (Writer, formula_map, load, resolve_input_site,
                     roll_year_headers, rollover_column, save)


def _model_path(company_dir, spec):
    mdir = Path(company_dir) / "model"
    if spec.get("model_file") and (mdir / spec["model_file"]).exists():
        return mdir / spec["model_file"]
    cands = sorted([p for p in mdir.glob("*.xls[xm]")
                    if not p.name.startswith("~$")
                    and "(pipeline" not in p.name],   # never our own output
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        raise FileNotFoundError(f"no model workbook in {mdir}")
    return cands[0]


def _disclosures(company_dir, period):
    d = Path(company_dir) / "disclosures"
    sub = d / period
    root = sub if sub.is_dir() else d
    return sorted(str(p) for p in root.glob("*.[pP][dD][fF]"))


def _write_served(wb, spec_d, target_year, served, writer, priors, log):
    """Served values -> input cells, per the mark-to-actual law: only where
    the number is actually TYPED. Formula rows redirect to their input site
    (link-through models) or stay computed (derived rows).

    THE REDIRECT SIGN LAW (run-1 autopsy: GP = revenue + |COGS|): a served
    value is signed for the ORIGINAL row's convention; the input site may
    hold the opposite convention behind a negating link (Model COGS -18,615
    <- Raw financials +18,615). Re-sign by the SITE's own prior. And a site
    that is itself directly served is never overwritten by a redirect — the
    direct serving is the authoritative read of that cell."""
    from .checks import prior_column, year_columns
    n_written = n_redirect = n_skip = 0
    for (sheet, row), entry in sorted(served.items()):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if not tcol or sheet not in wb.sheetnames:
            continue
        site = (sheet, row)
        value = entry["value"]
        held = wb[sheet][f"{tcol}{row}"].value
        if isinstance(held, str) and held.startswith("=") and pcol:
            site = resolve_input_site(wb, sheet, row, pcol) or (None, None)
            if site == (None, None):
                n_skip += 1     # derived row: its formula computes it
                continue
            if site != (sheet, row):
                if site in served:
                    n_skip += 1     # the site has its own authoritative read
                    continue
                n_redirect += 1
        s_sheet, s_row = site
        s_tcol = year_columns(spec_d, s_sheet).get(str(target_year))
        s_pcol = prior_column(spec_d, s_sheet, target_year)
        if not s_tcol:
            n_skip += 1
            continue
        if site != (sheet, row) and s_pcol:
            row_pv = (priors or {}).get((sheet, row))
            site_pv = wb[s_sheet][f"{s_pcol}{s_row}"].value
            if isinstance(row_pv, (int, float)) and row_pv != 0 \
                    and isinstance(site_pv, (int, float)) and site_pv != 0 \
                    and (row_pv < 0) != (site_pv < 0):
                value = -value      # the link between site and row negates
        ok = writer.write(
            s_sheet, f"{s_tcol}{s_row}", value,
            prior_coord=f"{s_pcol}{s_row}" if s_pcol else None,
            note=entry.get("note"), flag=entry.get("flag"),
            trusted=int(entry.get("conf") or 0) >= 4)
        if ok:
            n_written += 1
            if int(entry.get("conf") or 0) >= 5:
                writer.lock(s_sheet, f"{s_tcol}{s_row}")
    log(f"[run] wrote {n_written} served values "
        f"({n_redirect} redirected to input sites, {n_skip} derived/skipped)")


def update(company_dir, period, target_year, client=None, loop_budget=60,
           log=print):
    """One model update. Returns dict with paths + outcome."""
    company_dir = Path(company_dir)
    run_log = []

    # -- load model + spec, archive the pre-update state. No spec anywhere ->
    # the agent works the anatomy out itself (deterministic discovery; the
    # draft persists to the _SPEC tab for the analyst to review).
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
        log(f"[run] no spec found — anatomy AUTO-DISCOVERED "
            f"({len(spec_d['year_axis'])} sheets, "
            f"{len(spec_d['check_rows'])} check rows, "
            f"{len(spec_d['key_rows'])} key rows); review lands in _SPEC tab")
    spec_mod.extend_axis(spec_d, target_year)   # roll the axis to the
                                                # target year where needed
    model_path = _model_path(company_dir, spec_d)
    archive = company_dir / "model-archive" / f"{model_path.stem}_{period}_pre{model_path.suffix}"
    archive.parent.mkdir(exist_ok=True)
    shutil.copy2(model_path, archive)
    log(f"[run] model: {model_path.name} (archived pre-update copy)")

    wb = load(model_path)                       # formulas
    wb_values = load(model_path, data_only=True)  # cached values
    pre_map = formula_map(wb)
    pre_estimates = report_mod.snapshot_estimates(wb_values, spec_d, target_year)

    # -- census + Stage 1
    targets = targets_mod.from_workbook(wb_values, spec_d, target_year,
                                    wb_formulas=wb)
    known = targets_mod.known_prior_values(targets)
    log(f"[run] census: {len(targets)} target rows, {len(known)} priors")
    docs = _disclosures(company_dir, period)
    if not docs:
        raise FileNotFoundError(f"no disclosures for {period} under {company_dir}")
    ledger = read_documents(docs, client=client, known_values=known, log=log)

    # -- Stage 2 (pure code): statement faces, then bound non-statement
    # tables (the Driver/MD&A path — council two-level binding)
    served, decisions = join(ledger, targets, run_log)
    extra, dec2 = join_bound_tables(ledger, targets, served, run_log)
    served.update(extra)
    decisions += dec2
    for ln in run_log[-4:]:
        log(f"[run] {ln}")

    # -- the owner's column convention, then guarded writes
    writer = Writer(wb)
    from .checks import prior_column, year_columns
    hardcode_census = {}          # sheet -> rows that arrived as hardcodes
    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if tcol and pcol and sheet in wb.sheetnames:
            hard = rollover_column(wb, sheet, pcol, tcol)
            hardcode_census[sheet] = hard
            cols = year_columns(spec_d, sheet)
            years = sorted(cols)
            py = years[years.index(str(target_year)) - 1]
            nh = roll_year_headers(writer, sheet, pcol, tcol, py, target_year)
            log(f"[run] rolled {sheet}: {pcol}->{tcol}, {len(hard)} hardcode "
                f"inputs, {nh} year headers rolled")
    prior_map = {t.key: t.prior_value for t in targets}
    _write_served(wb, spec_d, target_year, served, writer, prior_map, log)

    # -- Stage 3 (LLM, checksummed) — only what Stage 2 left
    if client is not None:
        gap_served = read_gaps(ledger, targets, served, client, docs, run_log)
        served.update(gap_served)
        _write_served(wb, spec_d, target_year, gap_served, writer, prior_map, log)
    else:
        log("[run] stage 3 skipped: no client (dry run)")

    # -- SILENT STALENESS is illegal: a rolled-over hardcode that no proven
    # read overwrote still holds LAST year's number — flag every one red.
    # (Volume is honesty: if too many stay stale, the flag budget refuses
    # delivery, which is the correct verdict for that sheet.)
    n_stale = 0
    for sheet, rows in hardcode_census.items():
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        for r in rows:
            if (sheet, r) in served or f"{sheet}!{tcol}{r}" in writer.log["written"]:
                continue
            cell = wb[sheet][f"{tcol}{r}"]
            if not isinstance(cell.value, (int, float)):
                continue
            from openpyxl.comments import Comment
            cell.fill = writer.fills["red"]
            cell.comment = Comment(
                "STALE INPUT: rolled from the prior actual column; no proven "
                "disclosure read replaced it — review or accept.", "Model Update Agent")
            writer.log["flags"].append(f"{sheet}!{tcol}{r}")
            n_stale += 1
    if n_stale:
        log(f"[run] {n_stale} unserved hardcode inputs flagged STALE (red)")

    # -- PRE-LOOP DETERMINISTIC SWEEP (owner ruling: find it and fix it;
    # the loop's budget must not be spent on rows code can prove). For each
    # stale row: unique identity-grade face evidence -> write it (stage-2-
    # grade, no LLM); else a prior-column composition identity -> write the
    # SUM formula, orange-flagged per the house back-out law.
    # (an earlier kinship-free WORLD-tolerance evidence sweep here measured
    # 15 wrong writes — that idea now lives INSIDE join() as tier 2, behind
    # every gate; only the composition back-out remains a sweep)
    from .stage2_join import infer_composition
    targets_by_key = {t.key: t for t in targets}
    n_comp = 0
    for sheet, rows in hardcode_census.items():
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        for r in rows:
            ref = f"{sheet}!{tcol}{r}"
            if ref not in writer.log["flags"]:
                continue
            if pcol:
                f = infer_composition(wb, sheet, r, pcol, tcol)
                # every term must itself be trustworthy: a SUM over cells
                # still holding LAST year's numbers bakes mixed-year garbage
                # (measured -128k check residual), and the formula string
                # escapes the magnitude sweep
                if f:
                    import re as _re
                    m2 = _re.match(rf"^=SUM\({tcol}(\d+):{tcol}(\d+)\)$", f)
                    if m2 and any(f"{sheet}!{tcol}{k}" in writer.log["flags"]
                                  for k in range(int(m2.group(1)),
                                                 int(m2.group(2)) + 1)):
                        f = None
                if f and writer.write(
                        sheet, f"{tcol}{r}", f,
                        prior_coord=f"{pcol}{r}",
                        flag="orange",
                        note=("backed out: composition inferred from the "
                              "prior column's own arithmetic — true up "
                              "against the detailed disclosure")):
                    n_comp += 1
    if n_comp:
        log(f"[run] stale sweep: {n_comp} compositions backed out (orange)")

    # -- THE DASH-NIL SWEEP (run-11 pin): a stale row whose disclosure
    # line prints a nil mark in the current slot next to a prior that
    # ties is PROVEN zero this period (cancelled treasury shares).
    from .stage2_join import ratify_page_scales
    from .writegate import nil_current_zero
    # the face register = pages stage-2 RATIFIED as statement faces (the
    # served-pages shortcut was too narrow: with a rich AR present, an
    # announcement face's rows all serve from AR pages and the page
    # never enters the register, blocking its own true nil — run 12)
    face_pages = set(ratify_page_scales(
        ledger.items, [t.prior_value for t in targets
                       if isinstance(t.prior_value, (int, float))]))
    face_pages |= {(e.get("doc"), e.get("page")) for e in served.values()
                   if isinstance(e, dict) and e.get("doc")}
    n_nil = 0
    for sheet, rows in hardcode_census.items():
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        for r in rows:
            ref = f"{sheet}!{tcol}{r}"
            if ref not in writer.log["flags"] or not pcol:
                continue
            pv = wb[sheet][f"{pcol}{r}"].value
            lab = next((wb[sheet].cell(row=r, column=k).value
                        for k in range(1, 7)
                        if isinstance(wb[sheet].cell(row=r, column=k).value,
                                      str)), "")
            import re as _re
            if _re.search(r"合计|小计|总计|total", str(lab), _re.IGNORECASE):
                continue                # a subtotal is never nil-proven
            it = (nil_current_zero(ledger.items, pv, face_pages)
                  if isinstance(pv, (int, float)) else None)
            if it is not None and writer.write(
                    sheet, f"{tcol}{r}", 0.0, prior_coord=f"{pcol}{r}",
                    trusted=True,
                    note=(f"disclosure prints nil (–) this period beside "
                          f"the tying prior — proven zero "
                          f"({it.doc} p{it.page})")):
                from openpyxl.styles import PatternFill
                wb[sheet][f"{tcol}{r}"].fill = PatternFill()  # clear red
                writer.log["flags"] = [
                    x for x in writer.log["flags"] if x != ref]
                n_nil += 1
    if n_nil:
        log(f"[run] dash-nil sweep: {n_nil} proven zeros served")

    # -- THE RECLASSIFICATION RECIPE (owner rulings 2026-08-30): stale
    # segment inputs in a block whose total is known are backed out at
    # the total's growth rate; the residual lands in the analyst's own
    # designed plug row (or the smallest stale segment). Then flag every
    # formula smuggling a prior-period constant (key drivers, mindmap).
    from .evaluator import Evaluator
    from .reclass import flag_embedded_hardcodes, reclass_sweep
    sheets_ax = list(spec_d.get("year_axis") or {})
    ycols = {s: year_columns(spec_d, s).get(str(target_year))
             for s in sheets_ax}
    pcols = {s: prior_column(spec_d, s, target_year) for s in sheets_ax}
    try:
        _ev = Evaluator(wb)
        _evaluate = (lambda sh, coord: _ev.cell(sh, coord))
    except Exception:
        _evaluate = None
    n_seg = reclass_sweep(wb, sheets_ax, ycols, pcols, writer, log,
                          evaluate=_evaluate)
    if n_seg:
        log(f"[run] reclassification: {n_seg} segment inputs held at the "
            "total's growth (orange)")
    flag_embedded_hardcodes(wb, sheets_ax, ycols, writer, log)

    # -- THE ASSUMPTION FREEZE (owner ruling 2026-08-30): a forecast
    # assumption wired to the past (%-formatted, formula referencing the
    # newly actual column or earlier) would silently rebase onto the
    # actual. Hold it at its PRE-UPDATE value as an orange hardcode; the
    # report lists each with its old formula so restoring is one paste.
    from openpyxl.utils import column_index_from_string
    from .freeze import apply_freezes, plan_freezes
    frozen_lines = []
    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        if not tcol or sheet not in wb.sheetnames \
                or sheet not in wb_values.sheetnames:
            continue
        plans = plan_freezes(wb, wb_values, [sheet],
                             column_index_from_string(tcol))
        frozen_lines += apply_freezes(wb, plans)
    if frozen_lines:
        writer.log.setdefault("frozen", []).extend(frozen_lines)
        log(f"[run] assumption freeze: {len(frozen_lines)} forecast "
            "assumptions held at their pre-update values (orange)")

    # -- Stage 4: the objective loop (Luna owns it), then the gate
    loop_summary = ""
    if client is not None:
        loop = ObjectiveLoop(wb, spec_d, target_year, ledger, targets, served,
                             writer, client, run_log, budget=loop_budget)
        loop_summary = loop.run()
        log(f"[run] objective loop: {loop_summary[:150]}")
    else:
        log("[run] stage 4 loop skipped: no client (dry run)")

    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if tcol and pcol and sheet in wb.sheetnames:
            writer.format_rollover(sheet, pcol, tcol)

    ok, failures, card = gate_mod.deliver_or_refuse(
        wb, spec_d, target_year, pre_map, writer.log, served=served)

    # -- report + spec-tab memory + snapshots
    report_mod.build_report(wb, spec_d, target_year, writer.log, served,
                            pre_estimates, failures, loop_summary)
    spec_d.setdefault("_last_run", {})
    spec_d["_last_run"] = {"period": period, "served": len(served),
                           "flags": len(writer.log["flags"]),
                           "gate": "PASS" if ok else "REFUSED"}
    spec_mod.write_spec_tab(wb, spec_d)

    replay_dir = company_dir / "replay" / str(period)
    replay_dir.mkdir(parents=True, exist_ok=True)
    ledger.save(replay_dir / "ledger.json")
    (replay_dir / "decisions.json").write_text(decisions_to_json(decisions),
                                               encoding="utf-8")
    targets_mod.save(targets, replay_dir / "targets.json")
    (replay_dir / "run_log.txt").write_text("\n".join(run_log), encoding="utf-8")

    tag = "" if ok else " QUARANTINE"
    out_path = (company_dir / "model"
                / f"{model_path.stem} {period} (pipeline{tag}){model_path.suffix}")
    save(wb, out_path)
    log(f"[run] {'DELIVERED' if ok else 'GATE REFUSED — quarantined'}: "
        f"{out_path.name}")
    # -- the executive _REPORT (owner's locked design): Luna composes,
    # the code renders and referees; includes the sense-check second
    # look. Regenerated on the delivered file; never fatal to the run.
    if client is not None:
        try:
            from .execreport import report_only
            rep = report_only(str(company_dir), str(out_path),
                              str(archive), client, str(out_path))
            log(f"[run] executive report: {rep['bridges']} bridges, "
                f"{rep['refused']} refused, "
                f"{len(rep.get('corrections', []))} corrected, sense "
                f"verdicts: "
                f"{len((rep['summary'].get('sense') or {}).get('verdicts', []))}")
        except Exception as ex:
            log(f"[run] executive report FAILED (old-style report kept): "
                f"{ex}")
    for f in failures[:12]:
        log(f"[run]   gate: {f}")
    return {"ok": ok, "out": str(out_path), "archive": str(archive),
            "served": len(served), "failures": failures,
            "completion": card["completion"].get("_overall_pct"),
            "replay": str(replay_dir)}
