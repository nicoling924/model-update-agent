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
import json
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
        s_hdr = (spec_d.get("year_axis") or {}).get(s_sheet,
                                                    {}).get("header_row")
        if s_hdr and int(s_row) == int(s_hdr):
            n_skip += 1     # a formula that reads the YEAR HEADER redirects
            continue        # here — a header is never a data input site
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
           log=print, stage4_mode=None, stage4_answerer=None):
    """One model update. Returns dict with paths + outcome.

    stage4_mode: 'queue' (default — the council's work-queue inversion:
    machine plans, LLM answers one card at a time, then a small residual
    loop), 'queue-only' (no residual loop), 'loop' (the legacy free
    agent — byte-identical run-210 behavior, the instant rollback).
    stage4_answerer: offline driver for the queue (tests/replays) —
    callable(text, options, default) -> answer id; runs without any LLM."""
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

    # -- THE ERROR-BASELINE LAW (owner ruling 2026-08-31): count the
    # evaluation errors BEFORE touching anything. Pre-existing errors
    # are the analyst's; every error the update ADDS is ours and either
    # reverts (journaled writes) or refuses at the gate, traced.
    from .errorscan import error_cells, new_errors
    err_base = error_cells(wb, spec_d)
    if err_base:
        log(f"[run] error baseline: {len(err_base)} cells already fail to "
            "evaluate in the analyst's own model (their standing items)")
    # the by-hand teaching (owner 2026-09-01): the analyst's own first
    # forecast year, evaluated BEFORE we touch anything, defines
    # "healthy" — a write must survive its consequences there
    from .teachings import collapsed_forecasts, forecast_baseline
    fc_base = forecast_baseline(wb, spec_d, target_year)
    log(f"[run] forecast baseline: {len(fc_base)} healthy first-forecast "
        "rows recorded (collapse guard armed)")

    def err_guard(stage, cap=60):
        """A stage that made cells stop computing gets its journaled
        writes reverted, newest first, until the grid is back to the
        baseline — a 'proven' value that breaks the model is
        auto-disproven (the run-203 nuclear-capacity lesson)."""
        cur = new_errors(err_base, error_cells(wb, spec_d))
        if not cur:
            return
        undo = writer.log.get("undo", [])
        popped = 0
        while cur and undo and popped < cap:
            sh, coord, old = undo.pop()
            popped += 1
            prev = wb[sh][coord].value
            wb[sh][coord] = old
            now = new_errors(err_base, error_cells(wb, spec_d))
            if len(now) < len(cur):
                log(f"[run]   error guard [{stage}]: REVERTED {sh}!{coord} "
                    f"({str(prev)[:24]!r} -> restored {str(old)[:24]!r}) — "
                    "the write made cells stop computing (auto-disproven)")
                writer.log["flags"] = [x for x in writer.log["flags"]
                                       if x != f"{sh}!{coord}"]
                cur = now
            else:
                wb[sh][coord] = prev      # innocent write: keep it
        if cur:
            log(f"[run]   error guard [{stage}]: {len(cur)} new errors "
                "remain — the gate will refuse them: "
                + "; ".join(f"{s}!{c}" for s, c, _w in cur[:5]))

    def collapse_guard(stage, cap=40):
        """A write must survive its consequences (the run-204 tariff: an
        evidence-clean ZERO deleted next year's revenue). A ZERO write
        that collapsed a healthy forecast row is auto-disproven and
        reverted; a NON-zero write that did so is red-tripwired for the
        loop — it might be a real actual with a real consequence."""
        from openpyxl.comments import Comment
        cur = collapsed_forecasts(wb, spec_d, target_year, fc_base)
        if not cur:
            return
        undo = writer.log.get("undo", [])
        popped = 0
        while cur and undo and popped < cap:
            sh, coord, old = undo.pop()
            popped += 1
            prev = wb[sh][coord].value
            if not (isinstance(prev, (int, float)) and abs(prev) < 0.5):
                continue                  # only zero-writes auto-revert
            wb[sh][coord] = old
            now = collapsed_forecasts(wb, spec_d, target_year, fc_base)
            if len(now) < len(cur):
                log(f"[run]   collapse guard [{stage}]: REVERTED "
                    f"{sh}!{coord} (zero -> restored {str(old)[:22]!r}) — "
                    "the zero killed a healthy forecast row "
                    "(auto-disproven)")
                writer.log["flags"] = [x for x in writer.log["flags"]
                                       if x != f"{sh}!{coord}"]
                cur = now
            else:
                wb[sh][coord] = prev
        for (sh, r, now, was) in cur[:10]:
            from .checks import forecast_columns as _fc
            fc1 = _fc(spec_d, sh, target_year)
            if not fc1:
                continue
            cell = wb[sh][f"{fc1[0]}{r}"]
            cell.fill = writer.fills["red"]
            cell.comment = Comment(
                f"COLLAPSED FORECAST: the analyst's model computed "
                f"{was:,.1f} here; after the update it computes {now:,.1f}."
                " An actual-column input this row consumes changed "
                "drastically — verify that input (forecast_diff names "
                "candidates).", "Model Update Agent")
            writer.log["flags"].append(f"{sh}!{fc1[0]}{r}")
        if cur:
            log(f"[run]   collapse guard [{stage}]: {len(cur)} forecast "
                "rows collapsed vs the analyst's baseline — red-flagged, "
                "loop must trace the actual-column cause")
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
    # THE RECONCILIATION STAGE (owner ruling 2026-09-01): whole
    # statements walked line-by-line — the by-hand method as the serve
    # engine. Its serves are authoritative; the scattered joins only
    # fill what reconciliation left open.
    from .reconcile import reconcile
    recon_serves, recon_map = reconcile(wb, spec_d, target_year, ledger,
                                        log)
    served, decisions = join(ledger, targets, run_log)
    extra, dec2 = join_bound_tables(ledger, targets, served, run_log)
    served.update(extra)
    served.update(recon_serves)      # reconciliation wins conflicts
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
    # AXIS CELLS are structure, not data — and the test is the CELL,
    # not the row number (CLP-2: a blanket rows<=3 ban starved SOC!AI2,
    # a DATA row the analyst's own formulas consume, -215,773). A row is
    # axis iff its PRIOR cell is a year mark.
    def _is_year_mark(v, yr):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return abs(v - yr) < 0.5
        if hasattr(v, "year"):
            return abs(v.year - yr) <= 1
        return isinstance(v, str) and str(yr) in v and len(v) <= 12
    _py = int(target_year) - 1
    _axed = {}
    for sheet, rows in hardcode_census.items():
        _pc = prior_column(spec_d, sheet, target_year)
        _axed[sheet] = [
            r for r in rows
            if not (_pc and (_is_year_mark(wb[sheet][f"{_pc}{r}"].value,
                                           _py)
                            or _is_year_mark(wb[sheet][f"{_pc}{r}"].value,
                                             _py + 1)))]
    hardcode_census = _axed
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

    # -- THE COMPOSITE-CONSTANTS LAW (owner ruling 2026-08-31): formulas
    # still embedding last year's literals (=4976+23) are rewritten from
    # their own disclosed comparatives — the run-51 silent-carry class,
    # rebuilt as a proof-gated law (see composites.py).
    from .composites import sweep as composites_sweep
    n_cw, n_cr = composites_sweep(wb, spec_d, target_year, ledger, writer,
                                  log, check_rows=spec_d.get("check_rows"))
    if n_cw or n_cr:
        log(f"[run] constants law: {n_cw} stale composites rewritten from "
            f"disclosed comparatives (orange), {n_cr} unproven (red, "
            "evidence noted)")
    err_guard("constants law")
    collapse_guard("constants law")

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

    # -- THE LOAD-BEARING TRACE + TIER-3 SWEEP (owner ruling, CLP
    # campaign): effort follows the wiring. Rows the model's own
    # formulas consume on the way to the key rows are LOAD-BEARING —
    # staleness there stays red and must be adjudicated. Everything
    # else is tier-3: never searched, held at the group's growth as a
    # traceable orange formula, awaiting true-up.
    from .loadbearing import trace as lb_trace
    lb = lb_trace(wb, spec_d, target_year)
    rev_key = next((k for k in (spec_d.get("key_rows") or [])
                    if "rev" in str(k.get("name", "")).lower()), None)
    n_t3 = 0
    for sheet, rows in hardcode_census.items():
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if not tcol or not pcol:
            continue
        for r in rows:
            ref = f"{sheet}!{tcol}{r}"
            if ref not in writer.log["flags"] or (sheet, r) in lb:
                continue
            cell_now = wb[sheet][f"{tcol}{r}"]
            from openpyxl.styles import PatternFill as _PF
            try:
                rgb = cell_now.fill.start_color.rgb
            except Exception:
                rgb = ""
            if not (isinstance(rgb, str) and rgb.upper().endswith("FFC7CE")):
                continue                     # already handled by a sweep
            pv = wb[sheet][f"{pcol}{r}"].value
            if not isinstance(pv, (int, float)):
                continue
            if rev_key:
                ks, kr = rev_key["sheet"], rev_key["row"]
                ktc = year_columns(spec_d, ks).get(str(target_year))
                kpc = prior_column(spec_d, ks, target_year)
                f = (f"={pcol}{r}*('{ks}'!{ktc}{kr}/'{ks}'!{kpc}{kr})")
            else:
                f = f"={pcol}{r}"
            if writer.write(sheet, f"{tcol}{r}", f,
                            prior_coord=f"{pcol}{r}", flag="orange",
                            note=("tier-3 back-out: not load-bearing for "
                                  "the key rows; held at the group's "
                                  "growth — true up when segment detail "
                                  "is disclosed")):
                n_t3 += 1
    if n_t3:
        log(f"[run] tier-3 sweep: {n_t3} non-load-bearing stale inputs "
            "held at group growth (orange)")

    # -- THE DASH-NIL SWEEP (run-11 pin): a stale row whose disclosure
    # line prints a nil mark in the current slot next to a prior that
    # ties is PROVEN zero this period (cancelled treasury shares).
    from .stage2_join import ratify_page_scales
    from .writegate import nil_current_zero
    banned_docs = set(ledger.prior_period_docs()) \
        if hasattr(ledger, "prior_period_docs") else set()
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
            it = (nil_current_zero(ledger.items, pv, face_pages, banned_docs)
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
    err_guard("tier-3 + dash-nil")
    collapse_guard("tier-3 + dash-nil")

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
    wb_pre_formulas = load(archive)      # manual-calc models cache nothing
    frozen_lines = []
    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        if not tcol or sheet not in wb.sheetnames \
                or sheet not in wb_values.sheetnames:
            continue
        plans = plan_freezes(wb, wb_values, [sheet],
                             column_index_from_string(tcol),
                             pre_formulas_wb=wb_pre_formulas)
        frozen_lines += apply_freezes(wb, plans)
    if frozen_lines:
        writer.log.setdefault("frozen", []).extend(frozen_lines)
        log(f"[run] assumption freeze: {len(frozen_lines)} forecast "
            "assumptions held at their pre-update values (orange)")
    err_guard("reclass + freeze")
    collapse_guard("reclass + freeze")

    # -- TWIN RE-ANCHOR (by-hand teaching #2): a served quantity's other
    # homes (same prior, still stale) re-anchor with it — the run-204
    # NFA lesson: a stale twin base breaks every forecast year.
    from .teachings import plug_meter, twin_reanchor
    n_rw, n_tw = twin_reanchor(wb, wb_values, spec_d, target_year, writer,
                               log)
    if n_rw or n_tw:
        log(f"[run] twin re-anchor: {n_rw} stale twin hardcodes re-served, "
            f"{n_tw} formula twins red-tripwired")
    err_guard("twin re-anchor")
    collapse_guard("twin re-anchor")

    # -- ROLL-BASE CONSISTENCY (owner ruling 2026-09-01): every typed
    # actual whose forecast is computed must be REPRODUCED by its own
    # roll formula pointed back one year — a right hardcode over a stale
    # roll base balances the actual year and breaks every forecast year
    # by a constant. Stale base inputs are flagged into the queue.
    from .teachings import roll_base_mismatches
    n_rb = roll_base_mismatches(wb, spec_d, target_year, writer, log)
    if n_rb:
        log(f"[run] roll-base consistency: {n_rb} rows roll from bases "
            "that do not reproduce their typed actuals — base inputs "
            "flagged for the queue")

    # -- THE MOVE-ON LAW (owner ruling 2026-08-31): code does the
    # exhaustive not-disclosed looking for every stale red; the loop's
    # queue shrinks to the rows where evidence actually exists.
    from .moveon import machine_look
    machine_look(wb, spec_d, target_year, ledger, writer, log)

    # -- Stage 4: the work queue (machine plans, LLM answers cards) or
    # the legacy free loop, then the gate
    import os as _os
    mode = (stage4_mode or _os.environ.get("STAGE4_MODE") or "queue").strip()
    loop_summary = ""
    if client is not None or stage4_answerer is not None:
        loop = ObjectiveLoop(wb, spec_d, target_year, ledger, targets, served,
                             writer, client, run_log, budget=loop_budget)
        loop.load_bearing = lb           # tier law: the loop sees the wiring
        # sense tripwires (owner ruling 2026-08-31): sign-flipped
        # forecasts are handed to the loop as mistake-detector items —
        # investigate once, verdict on _REPORT; the terminal freeze
        # after the loop takes only what remains unresolved
        loop.tripwires = gate_mod.sign_absurd_rows(wb, spec_d, target_year)
        if loop.tripwires:
            log(f"[run] sense tripwires: {len(loop.tripwires)} sign-flip "
                "forecasts handed to the loop for investigation")
        # error-baseline law: NEW errors are the loop's mandatory work —
        # trace_error walks each to its cause (with the pre-update
        # archive as the before-picture)
        loop.pre_path = str(archive)
        loop.error_items = new_errors(err_base, error_cells(wb, spec_d))
        if loop.error_items:
            log(f"[run] {len(loop.error_items)} NEW evaluation errors "
                "handed to the loop (trace_error each to its cause)")
        # by-hand teaching #5: the model's own residual rows are truth
        # meters — a wild plug means an input feeding its total is wrong
        loop.plugmeters = plug_meter(wb, spec_d, target_year)
        if loop.plugmeters:
            log(f"[run] plug meter: {len(loop.plugmeters)} of the model's "
                "own residual rows moved wildly — the loop investigates "
                "their inputs")
        if mode == "loop":
            loop_summary = loop.run()
            log(f"[run] objective loop: {loop_summary[:150]}")
        else:
            from .workqueue import run_queue
            loop_summary = run_queue(loop, client, log,
                                     answerer=stage4_answerer)
            if mode == "queue" and client is not None:
                # the council's residual open loop: small, gated, only
                # for what no card could close
                loop.budget = min(loop.budget, 10)
                loop_summary += " | residual loop: " + loop.run()
                log(f"[run] residual loop: {loop_summary[-120:]}")
        # the referee's last rung (owner: back out, mark, still deliver)
        from .orchestrator import terminal_ladder
        n_tl = terminal_ladder(loop, log)
        if n_tl:
            log(f"[run] terminal ladder: {n_tl} actual-year checks closed "
                "(flagged plugs/diffs, reported)")
        err_guard("loop + terminal ladder")
        collapse_guard("loop + terminal ladder")
        # loop serves get the twin treatment too
        n_rw2, n_tw2 = twin_reanchor(wb, wb_values, spec_d, target_year,
                                     writer, log)
        if n_rw2 or n_tw2:
            err_guard("twin re-anchor 2")
            collapse_guard("twin re-anchor 2")
        # unresolved plug meters: reported, never silent
        from openpyxl.comments import Comment as _C2
        done_v = {v.split(":", 1)[0]
                  for v in writer.log.get("verdicts", [])}
        for (pm_sh, pm_r, pm_now, pm_was) in plug_meter(wb, spec_d,
                                                        target_year):
            tc_pm = spec_d["year_axis"][pm_sh]["columns"].get(
                str(target_year)) if pm_sh in spec_d.get(
                    "year_axis", {}) else None
            if not tc_pm or f"{pm_sh}!{tc_pm}{pm_r}" in done_v:
                continue
            cell = wb[pm_sh][f"{tc_pm}{pm_r}"]
            cell.fill = writer.fills["red"]
            cell.comment = _C2(
                f"PLUG METER: this residual row computed {pm_was:,.1f} "
                f"last year and {pm_now:,.1f} now — the model's own plug "
                "is absorbing something wrong in the inputs that feed "
                "its total. ANALYST REVIEW.", "Model Update Agent")
            writer.log["flags"].append(f"{pm_sh}!{tc_pm}{pm_r}")
            writer.log.setdefault("verdicts", []).append(
                f"{pm_sh}!{tc_pm}{pm_r}: SUSPICIOUS — the model's own "
                f"residual swung {pm_was:,.1f} -> {pm_now:,.1f}; an "
                "input feeding its total is probably wrong")
        # -- THE KEY-TIE LAW (owner ruling 2026-08-31): every key row
        # must tie its pinned printed value; the unresolvable component
        # is backed out (orange, traceable) so the key ties exactly.
        from .keytie import key_tie
        key_tie(wb, spec_d, target_year, writer,
                company_dir / "replay" / str(period) / "key_panel.json",
                log, ledger=ledger)
        err_guard("key tie")
        collapse_guard("key tie")
    else:
        log("[run] stage 4 loop skipped: no client (dry run)")

    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if tcol and pcol and sheet in wb.sheetnames:
            writer.format_rollover(sheet, pcol, tcol)

    # the one-off no-propagate law (roll-forward checklist; the one
    # sanctioned forecast edit — run-206's hedging leak, +352/yr) runs
    # BEFORE any forecast plug is sized
    from .teachings import auto_probe_holds, oneoff_no_propagate
    n_oo = oneoff_no_propagate(wb, spec_d, target_year, writer, log)
    if n_oo:
        log(f"[run] one-off law: {n_oo} forecast links to new one-off "
            "actuals set to 0 (orange)")
    # the mechanized bisect (owner 2026-09-01): probe-proven holds at
    # the analyst's own baseline — run-208's recurring hedging row had
    # a 2024 value, so the static one-off test missed it; the analyst's
    # pre-update FORECAST (0) is the true intent test
    n_ap = auto_probe_holds(wb, spec_d, target_year, fc_base, writer, log)
    if n_ap:
        log(f"[run] auto-probe: {n_ap} probe-proven roll artifacts held "
            "at the analyst's baseline (orange, reported)")

    # -- FORECAST-YEAR BALANCE, LAST RESORT (owner ruling: balance is
    # for ALL years; plug only what genuine attribution could not place;
    # the loop had its place_flow chance above). Parse the check row's
    # own formula for its first leg (the assets row) to scale the
    # red-if-large test.
    from .checks import forecast_columns as _fcols
    from .evaluator import Evaluator as _Ev
    from .forecast_balance import last_resort_plug
    for _c in (spec_d.get("check_rows") or []):
        _sheet = _c.get("sheet")
        if _sheet not in wb.sheetnames:
            continue
        _cols = _fcols(spec_d, _sheet, target_year)
        _tcol = year_columns(spec_d, _sheet).get(str(target_year))
        if not _cols or not _tcol:
            continue
        _assets = None
        _cf = wb[_sheet][f"{_tcol}{_c['row']}"].value
        if isinstance(_cf, str):
            _m = __import__("re").search(r"[A-Z]{1,3}(\d+)", _cf)
            if _m:
                _assets = int(_m.group(1))
        plugged = last_resort_plug(
            wb, writer,
            (lambda: (lambda s, cd, e=_Ev(wb): e.cell(s, cd))),
            _sheet, _c["row"], _cols, _assets, log)
    # THE HOLD TUNER (owner regression ruling 2026-09-01): a FLAT
    # forecast residual left after all repairs means an auto-probe hold
    # is off by exactly that constant — tune it by experiment
    from .teachings import tune_holds
    n_tune = tune_holds(wb, spec_d, target_year, writer, log)
    if n_tune:
        err_guard("hold tuner")
        collapse_guard("hold tuner")
    # -- FORECAST INVIOLABILITY (the by-hand teaching, owner 2026-09-01,
    # replacing the sign-absurd freeze writer that broke run 204's
    # balance): the analyst's forecast formulas are never hardcoded.
    # A sign-flip still unresolved after the loop is a red REPORTED
    # question naming where the cause lives — the actual column.
    from openpyxl.comments import Comment as _Cmt
    verdicted = {v.split(":", 1)[0]
                 for v in writer.log.get("verdicts", [])}
    n_sa = 0
    for (s_sh, s_c, s_r, s_fv, s_pv, s_tv) in gate_mod.sign_absurd_rows(
            wb, spec_d, target_year):
        key = f"{s_sh}!{s_c}{s_r}"
        if key in verdicted:
            continue
        cell = wb[s_sh][f"{s_c}{s_r}"]
        cell.fill = writer.fills["red"]
        cell.comment = _Cmt(
            f"SIGN-FLIP UNRESOLVED: this forecast computes {s_fv:,.1f} "
            f"where both actual years are positive ({s_pv:,.1f} -> "
            f"{s_tv:,.1f}). The formula is the analyst's and stays LIVE "
            "— the cause is an actual-column input it consumes. "
            "ANALYST REVIEW.", "Model Update Agent")
        writer.log["flags"].append(key)
        writer.log.setdefault("verdicts", []).append(
            f"{key}: SUSPICIOUS — sign-flip unresolved; the cause is in "
            "the actual column (formula left live, red)")
        n_sa += 1
    if n_sa:
        log(f"[run] sign-flip terminal: {n_sa} unresolved forecasts left "
            "LIVE, red, reported (never frozen — the run-204 lesson)")
    err_guard("plugs + terminal")
    collapse_guard("plugs + terminal")

    ok, failures, card = gate_mod.deliver_or_refuse(
        wb, spec_d, target_year, pre_map, writer.log, served=served,
        pre_values_wb=wb_values, load_bearing=lb,
        pre_formulas_path=str(archive), error_baseline=err_base)
    for line in card.get("inherited_breaks", []):
        log(f"[run]   inherited (analyst's): {line}")
    for line in card.get("moveon_reported", []):
        log(f"[run]   move-on (reported, not refused): {line}")

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
    # provenance: who served every cell — the debugging map without which
    # a bad serve (wrong column, wrong vintage) cannot be attributed
    prov = {f"{sh}!{r}": {k: e.get(k) for k in
                          ("value", "doc", "page", "line", "conf", "note")}
            for (sh, r), e in served.items() if isinstance(e, dict)}
    (replay_dir / "provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8")

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
                              str(archive), client, str(out_path),
                              target_year=target_year)
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
