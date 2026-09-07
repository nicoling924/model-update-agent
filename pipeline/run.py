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
from .ledger import Ledger, vintage_ban as _vintage_ban
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
        # A CLAIM NEEDS A HOME (run-227 autopsy): an entry that never
        # lands in a cell must not hold the figure in the one-home
        # register — mark it un-homed on every skip path
        entry["homed"] = False
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
            entry["homed"] = True
            entry["home"] = (s_sheet, f"{s_tcol}{s_row}")
            if int(entry.get("conf") or 0) >= 5:
                writer.lock(s_sheet, f"{s_tcol}{s_row}")
    log(f"[run] wrote {n_written} served values "
        f"({n_redirect} redirected to input sites, {n_skip} derived/skipped)")


RUN_TARGET_S = 60 * 60      # the owner's acceptance criterion: one run, one hour
FINISH_MARGIN_S = 3 * 60    # gate loop + report + save, measured ~1 min on run 250


def update(company_dir, period, target_year, client=None, loop_budget=60,
           log=print, stage4_mode=None, stage4_answerer=None,
           pinned_ledger=None, pinned_served=None):
    """One model update. Returns dict with paths + outcome.

    stage4_mode: 'queue' (default — the council's work-queue inversion:
    machine plans, LLM answers one card at a time; no free loop),
    'queue+loop' (adds a 10-action residual free loop — opt-in, run-224
    showed it wedges), 'queue-only' (alias of 'queue'), 'loop' (the
    legacy free agent — byte-identical run-210 behavior, the rollback).
    stage4_answerer: offline driver for the queue (tests/replays) —
    callable(text, options, default) -> answer id; runs without any LLM."""
    import time as _time
    _run_t0 = _time.monotonic()
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
    # AN INTERIM PERIOD BINDS THE INTERIM PANEL (owner 2026-09-07: the
    # agent identifies the model's structure itself). A spec written for
    # annual updates maps the annual columns; a half-year or quarterly
    # update must land in the sheet's interim panel instead — the same
    # discovery that reads a spec-less model finds it (a run of
    # '1H2024, 1H2025' / '2024-06-30' marks). A sheet with no interim
    # panel has no home for interim figures and is left out of this run.
    _kind0 = ("1H" if str(period).upper().startswith(("1H", "2H", "H1", "H2"))
              else "Q" if "Q" in str(period).upper() else "FY")
    if _kind0 != "FY":
        from .discover import find_year_axis as _fya
        _wb0 = load(_model_path(company_dir, spec_d))
        _axis = {}
        for _sh in list((spec_d.get("year_axis") or {}).keys()):
            if _sh not in _wb0.sheetnames:
                continue
            _ax = _fya(_wb0[_sh], _kind0)
            # the panel found must be of the period's own kind: a quarterly
            # update must not land in a half-year panel (the discovery
            # scores 'interim' without telling H from Q) — the header
            # marks decide (Q/季 vs H/半年/06-30)
            if _ax and _kind0 == "Q":
                _hdr = " ".join(
                    str(c.value) for row in _wb0[_sh].iter_rows(min_row=1, max_row=6)
                    for c in row if c.column_letter in set(_ax.values())
                    and c.value is not None)
                if not re.search(r"[1-4]Q|Q[1-4]|季|-03-|-09-", _hdr):
                    _ax = None
            if _ax and str(target_year) in _ax and str(target_year - 1) in _ax:
                _axis[_sh] = dict(spec_d["year_axis"][_sh], columns=_ax)
                log(f"[run] interim panel: {_sh} {_kind0} columns "
                    f"{target_year - 1}={_ax[str(target_year - 1)]}, "
                    f"{target_year}={_ax[str(target_year)]}")
            else:
                log(f"[run] interim panel: {_sh} has no {_kind0} panel — "
                    "left out of this run (no home for interim figures)")
        if not _axis:
            raise RuntimeError(
                f"no sheet in the model carries a {_kind0} panel for "
                f"{target_year} — an interim update has nowhere to land; "
                "the analyst decides where interim figures go")
        # THE INTERIM COMPARATIVE (DFE run 236): an interim P&L / cash
        # flow compares to the same period last year, but an interim
        # BALANCE SHEET compares to the last YEAR-END — so the model's
        # last annual column is a second prior the disclosure may tie.
        # Kept beside the interim axis for the reconciliation's home index.
        _annual_prior = {}
        for _sh in _axis:
            _cols = (spec_d["year_axis"].get(_sh) or {}).get("columns") or {}
            _pc = _cols.get(str(target_year - 1))
            if _pc and _pc != _axis[_sh]["columns"].get(str(target_year - 1)):
                _annual_prior[_sh] = _pc
        spec_d["annual_prior_axis"] = _annual_prior
        spec_d["year_axis"] = _axis
    model_path = _model_path(company_dir, spec_d)
    archive = company_dir / "model-archive" / f"{model_path.stem}_{period}_pre{model_path.suffix}"
    archive.parent.mkdir(exist_ok=True)
    shutil.copy2(model_path, archive)
    log(f"[run] model: {model_path.name} (archived pre-update copy)")

    wb = load(model_path)                       # formulas
    wb_values = load(model_path, data_only=True)  # cached values
    # THE READING STEP for the model (owner ruling 2026-09-03): the brain
    # names the headline rows; code verifies each carries numbers
    from .docid import identify_key_rows
    identify_key_rows(wb, spec_d, client, log,
                      panel_path=company_dir / "replay" / str(period) / "key_panel.json",
                      target_year=target_year)
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
    # THE ROLLOVER INVESTIGATION (owner teaching 2026-09-03): the
    # analyst's own estimate for the target year AND their first
    # forecast, per row, before any write — the proportionality test's
    # baseline
    from .rollover import estimate_baseline
    est_base = estimate_baseline(wb, spec_d, target_year)

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
                # the restored prior is unconfirmed: RED, plain note
                from openpyxl.comments import Comment as _Cm
                _cell = wb[sh][coord]
                _cell.fill = writer.fills["red"]
                _cell.comment = _Cm(
                    "Not confirmed in the documents. Kept last period's "
                    "figure — please check.", "Model Update Agent")
                if f"{sh}!{coord}" not in writer.log["flags"]:
                    writer.log["flags"].append(f"{sh}!{coord}")
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
            # a PRINTED nil is a read, not a guess (owner 2026-09-08: "if
            # 0 then 0"): the disclosure showed last year's figure and a
            # blank current slot — the forecast that dies with it is the
            # rollover check's business, never grounds to restore a hold
            _rr = int("".join(ch for ch in coord if ch.isdigit()) or 0)
            try:
                _pe = served.get((sh, _rr))
            except NameError:
                _pe = None
            if isinstance(_pe, dict) and _pe.get("value") == 0.0 \
                    and int(_pe.get("conf") or 0) >= 4:
                writer.watch(sh, coord, "printed nil this year; the forecast "
                                        "row it feeds moved with it")
                continue
            wb[sh][coord] = old
            now = collapsed_forecasts(wb, spec_d, target_year, fc_base)
            if len(now) < len(cur):
                log(f"[run]   collapse guard [{stage}]: REVERTED "
                    f"{sh}!{coord} (zero -> restored {str(old)[:22]!r}) — "
                    "the zero killed a healthy forecast row "
                    "(auto-disproven)")
                # a value the run could NOT confirm is uncertain by
                # definition: the restored prior stays RED with a plain
                # note (run 233: the basic tariff was zeroed, restored to
                # last year's 95.8 and left unflagged with a 'proven
                # zero' note — the one miss the owner found unflagged)
                _cell = wb[sh][coord]
                _cell.fill = writer.fills["red"]
                _cell.comment = Comment(
                    "Not confirmed in the documents. Kept last period's "
                    "figure — please check.", "Model Update Agent")
                if f"{sh}!{coord}" not in writer.log["flags"]:
                    writer.log["flags"].append(f"{sh}!{coord}")
                cur = now
            else:
                wb[sh][coord] = prev
        for (sh, r, now, was) in cur[:10]:
            from .checks import forecast_columns as _fc
            fc1 = _fc(spec_d, sh, target_year)
            if not fc1:
                continue
            # a forecast cell is never painted (owner 2026-09-07): the
            # row goes on the watch list; the loop traces the cause in
            # the actual column and flags THAT
            writer.watch(sh, f"{fc1[0]}{r}",
                         f"forecast moved from {was:,.0f} to {now:,.0f} "
                         "after the update")
        if cur:
            log(f"[run]   collapse guard [{stage}]: {len(cur)} forecast "
                "rows collapsed vs the analyst's baseline — red-flagged, "
                "loop must trace the actual-column cause")
    # the OLD estimates: snapshot from the FORMULAS workbook (a
    # manual-calc model's data_only load caches nothing) — this line
    # runs before any write, so what it evaluates IS the old estimate
    pre_estimates = report_mod.snapshot_estimates(wb, spec_d, target_year)

    # -- census + Stage 1
    targets = targets_mod.from_workbook(wb_values, spec_d, target_year,
                                    wb_formulas=wb)
    known = targets_mod.known_prior_values(targets)
    log(f"[run] census: {len(targets)} target rows, {len(known)} priors")
    docs = _disclosures(company_dir, period)
    if not docs:
        raise FileNotFoundError(f"no disclosures for {period} under {company_dir}")
    if pinned_ledger:
        # THE PINNED-SNAPSHOT PATH (operator council 2026-09-01): replay
        # a prior run's evidence ledger — offline validation for models
        # whose statements need vision (scanned pages read nothing in a
        # client=None rebuild; the pinned ledger carries the checksummed
        # transcriptions)
        ledger = Ledger.from_json(Path(pinned_ledger).read_text())
        log(f"[run] stage 1 PINNED: ledger replayed from {pinned_ledger} "
            f"({len(ledger.items)} items)")
    else:
        ledger = read_documents(docs, client=client, known_values=known,
                                log=log)
    # THE VINTAGE LAW (run-228 autopsy): each document's vintage is
    # decided ONCE, here, before any stage serves. A document is
    # evidence for the periods it proves; 'unknown' is context, never a
    # current value, once a document has proved current. Reconciliation
    # and the join had served 45 rows from the prior-year AR (19 wrong)
    # because this verdict was first computed inside stage 3.
    ledger.classify_from_targets(targets)
    # DOCUMENT IDENTIFICATION (owner ruling 2026-09-03): the agent first
    # says what each document IS — brain card, printed period, numeric
    # vote as backstop — and the verdict binds every serving stage. The
    # folder is never the authority; the document is.
    from .docid import identify_documents
    _kind = ("1H" if str(period).upper().startswith(("1H", "2H", "H1", "H2"))
             else "Q" if "Q" in str(period).upper() else "FY")
    documents = identify_documents(docs, ledger, client, target_year, _kind, log)
    from .docid import identify_statement_pages
    identify_statement_pages(docs, ledger, client, known, log)
    _ban = _vintage_ban(ledger)
    if _ban:
        log(f"[run] vintage law: {len(_ban)} document(s) may not source "
            f"current-year values: {sorted(_ban)}")

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
    # the forecast columns per sheet: a law that finds a forecast cell
    # strange watch-lists it instead of painting it (owner 2026-09-07)
    from .checks import forecast_columns as _fcols0
    writer.forecast_cols = {
        sh: set(_fcols0(spec_d, sh, target_year) or ())
        for sh in (spec_d.get("year_axis") or {}) if sh in wb.sheetnames}
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
    if pinned_served:
        # THE PINNED-SERVES PATH (operator council 2026-09-01, built
        # 2026-09-02): replay a live run's provenance — its stage-3
        # LLM gap reads included — so an offline run reproduces the
        # live state faithfully instead of the client=None subset
        try:
            prov = json.loads(Path(pinned_served).read_text())
        except Exception:
            prov = {}
        n_pin = 0
        for ref, e in prov.items():
            sh_p, _, row_p = str(ref).partition("!")
            try:
                key_p = (sh_p, int(row_p))
            except ValueError:
                continue
            if key_p in served or not isinstance(e, dict) \
                    or not isinstance(e.get("value"), (int, float)):
                continue
            if e.get("doc") and e.get("doc") in _ban:
                continue        # the vintage law binds pinned serves too
            _n = str(e.get("note") or "")
            if "card-adjudicated" in _n or _n.startswith("objective loop"):
                continue        # STAGE-4 PRODUCTS ARE RE-DECIDED (readiness
                                # 2026-09-08): pinning the live run's own card
                                # serves made the cell 'already served' and
                                # its value 'already homed', so the replayed
                                # card was refused — and the floors were
                                # scoring the live brain's answers as proven
            if _n.startswith(("stage-2", "reconciliation")):
                continue        # deterministic serves recompute under the
                                # CURRENT laws; only the brain's reads are pinned
            served[key_p] = {"value": e["value"], "status": "OK",
                             "doc": e.get("doc"), "page": e.get("page"),
                             "line": e.get("line"),
                             "conf": e.get("conf") or 4,
                             "note": "PINNED replay: " + str(e.get("note"))}
            n_pin += 1
        log(f"[run] served PINNED: {n_pin} live serves replayed from "
            f"{pinned_served}")
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
                # NOT A BACK-OUT (owner 2026-09-08): a row the prior year
                # proves to be the sum of its own component rows — a Wind
                # aggregate of printed lines — is summed the same way
                # this year, plain, unflagged; the pattern is the model's
                if f and writer.write(
                        sheet, f"{tcol}{r}", f,
                        prior_coord=f"{pcol}{r}"):
                    from openpyxl.styles import PatternFill as _PFc
                    wb[sheet][f"{tcol}{r}"].fill = _PFc()
                    wb[sheet][f"{tcol}{r}"].comment = None
                    writer.log["flags"] = [x for x in writer.log["flags"] if x != ref]
                    n_comp += 1
    if n_comp:
        log(f"[run] stale sweep: {n_comp} aggregate rows summed from their own "
            "component rows (the prior year proves the pattern; plain)")

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
            # A BLANK BESIDE THE PRIOR IS THE BRAIN'S CALL, NOT A HOLD (run
            # 248: the differently named bond line was held at growth here
            # before the card could ask 'same item?') — such rows stay red
            from .writegate import nil_current_zero as _ncz0
            try:
                _blank = _ncz0(ledger.items, pv,
                               {(i_.doc, i_.page) for i_ in ledger.items},
                               set(_vintage_ban(ledger)))
            except Exception:
                _blank = None
            if _blank is not None:
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
    banned_docs = set(_vintage_ban(ledger)) \
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
            it = (nil_current_zero(ledger.items, pv, face_pages, banned_docs,
                                   row_label=lab)
                  if isinstance(pv, (int, float)) else None)
            # an interim balance sheet prints the YEAR-END comparative:
            # the annual prior is the second figure a nil may sit beside
            if it is None:
                _acol = (spec_d.get("annual_prior_axis") or {}).get(sheet)
                _apv = wb[sheet][f"{_acol}{r}"].value if _acol else None
                if isinstance(_apv, (int, float)) and abs(_apv) >= 0.5:
                    it = nil_current_zero(ledger.items, _apv, face_pages, banned_docs,
                                          row_label=lab)
            if it is not None:
                log(f"[run]   0 means 0: {ref} — prior {pv:,.2f} printed with a "
                    f"blank/nil current slot ({it.doc} p{it.page} "
                    f"{str(getattr(it, 'label', ''))[:24]!r})")
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
                # a printed nil is a READ, not a hold: registered as a
                # proven serve so no plug or revert lands on it (owner
                # 2026-09-08: "if 0 then 0"; the 240 replay plugged the
                # cash gap into the freshly served nil)
                served[(sheet, r)] = {
                    "value": 0.0, "doc": it.doc, "page": it.page,
                    "line": str(getattr(it, "label", ""))[:60], "conf": 4,
                    "homed": True, "home": (sheet, f"{tcol}{r}"),
                    "note": (f"reconciliation: printed nil this period beside "
                             f"the tying prior ({it.doc} p{it.page}) — 0")}
                n_nil += 1
            elif it is not None:
                log(f"[run]   0 means 0: {ref} write REFUSED by the guard "
                    f"(locked={ref in writer.locked})")
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
    n_rb = roll_base_mismatches(wb, spec_d, target_year, writer, log,
                                served=served)
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
    undo_mark = len(writer.log.get("writes_all", []))
    # RULE 2 AT THE GATE (owner, 2026-09-03: "why didn't it fill the 2025
    # keys correctly? rule 1 is balance, rule 2 is the keys"): the keys
    # that are proven-printed HERE — before any brain answer — must
    # still be so at delivery. Run 229 had them right at this point and
    # two late reverts broke four of them; the gate never looked.
    from .keytie import key_snapshot as _key_snapshot
    _panel_path = company_dir / "replay" / str(period) / "key_panel.json"
    keys_before = _key_snapshot(wb, spec_d, target_year, ledger, _panel_path)
    if keys_before:
        log(f"[run] rule 2 armed: {len(keys_before)} key(s) proven-printed "
            f"before stage 4 ({', '.join(sorted(keys_before))})")
    import os as _os
    mode = (stage4_mode or _os.environ.get("STAGE4_MODE") or "queue").strip()
    loop_summary = ""
    if client is not None or stage4_answerer is not None:
        loop = ObjectiveLoop(wb, spec_d, target_year, ledger, targets, served,
                             writer, client, run_log, budget=loop_budget)
        loop.load_bearing = lb           # tier law: the loop sees the wiring
        loop.est_base = est_base         # rollover cards: the analyst's baseline
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
            _left = RUN_TARGET_S - FINISH_MARGIN_S - (_time.monotonic() - _run_t0)
            log(f"[run] queue budget: {_left/60:.1f} min of the hour left for cards")
            loop_summary = run_queue(loop, client, log,
                                     answerer=stage4_answerer,
                                     deadline_s=max(60.0, _left))
            if mode == "queue+loop" and client is not None:
                # the residual free loop is OPT-IN only (run-224
                # autopsy: with 10 free actions it plugged proven cells
                # BEFORE the repair suite ran and wedged a state the
                # queue-only path delivers — the red-team verdict,
                # observed live). 'queue' == cards + machinery.
                loop.budget = min(loop.budget, 10)
                loop_summary += " | residual loop: " + loop.run()
                log(f"[run] residual loop: {loop_summary[-120:]}")
        undo_mark2 = len(writer.log.get("writes_all", []))   # end of stage-4 serves
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
        # THE OWNER'S RULE (2026-09-04): a key that is off is backed out
        # into a number the run could NOT find (a red component), within
        # a bound — never into a proven line like cash (the total-assets
        # tie on run 231's replay wrapped cash, then NFA, round after
        # round, and refused)
        key_tie(wb, spec_d, target_year, writer,
                company_dir / "replay" / str(period) / "key_panel.json",
                log, ledger=ledger)
        err_guard("key tie")
        collapse_guard("key tie")
        # THE PRINTED-SUBTOTAL LAW (owner 2026-09-04): current assets,
        # non-current assets, total assets, liabilities, equity — every
        # subtotal the statements print ties or is backed out (orange)
        # (built and museum-tested; NOT wired yet — inside the gate loop it
        # compounded wraps across rounds and landed a back-out on another
        # sheet on run 231's replay. Wiring is its own session.)
        # from .keytie import subtotal_tie as _subtotal_tie
        # keys_before.update(_subtotal_tie(wb, spec_d, target_year, writer,
        #                                  ledger, log, priors=known))
        # RULE 2, re-armed: keys the key tie just proved must also hold
        # through the repair suite and the gate loop
        _more = _key_snapshot(wb, spec_d, target_year, ledger, _panel_path)
        _new_keys = sorted(set(_more) - set(keys_before))
        keys_before.update(_more)
        if _new_keys:
            log(f"[run] rule 2 re-armed after key tie: +{len(_new_keys)} "
                f"({', '.join(_new_keys)})")
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
    from .teachings import roll_base_mismatches as _rbm2
    from .forecast_balance import last_resort_plug
    from openpyxl.comments import Comment as _Cmt

    def repair_round(tag):
        """THE REPAIR SUITE — everything that closes checks after the
        actual column is marked: roll-base re-anchoring, forecast plugs,
        the sign-flip terminal, the final closer. Idempotent by design
        (anchors re-solve, plugs re-measure, verdicts skip the done),
        so the gate loop can run it again on a corrected state."""
        # RULE 2 inside the suite (run-230: the clean-slate take-back
        # removed the key tie's CFI back-out and nothing re-tied it —
        # rule 2 then refused, correctly). The key tie is idempotent.
        if tag != "first":
            from .keytie import key_tie as _kt_again
            _kt_again(wb, spec_d, target_year, writer, _panel_path, log,
                      ledger=ledger)
        n_rb2 = _rbm2(wb, spec_d, target_year, writer, log, served=served)
        if n_rb2:
            err_guard(f"roll-base {tag}")
            collapse_guard(f"roll-base {tag}")
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
            last_resort_plug(
                wb, writer,
                (lambda: (lambda s, cd, e=_Ev(wb): e.cell(s, cd))),
                _sheet, _c["row"], _cols, _assets, log)
        # FORECAST INVIOLABILITY: unresolved sign-flips stay LIVE, red,
        # reported (never frozen — the run-204 lesson)
        verdicted = {v.split(":", 1)[0]
                     for v in writer.log.get("verdicts", [])}
        n_sa = 0
        for (s_sh, s_c, s_r, s_fv, s_pv, s_tv) in gate_mod.sign_absurd_rows(
                wb, spec_d, target_year):
            key = f"{s_sh}!{s_c}{s_r}"
            if key in verdicted:
                continue
            # never painted (owner 2026-09-07): watch-listed, the formula
            # stays live, the cause is in the actual column
            writer.watch(s_sh, f"{s_c}{s_r}",
                         f"forecast flips sign: computes {s_fv:,.0f} where "
                         f"both actual years are positive ({s_pv:,.0f} -> "
                         f"{s_tv:,.0f})")
            writer.log.setdefault("verdicts", []).append(
                f"{key}: SUSPICIOUS — sign-flip unresolved; the cause is in "
                "the actual column (formula left live, red)")
            n_sa += 1
        if n_sa:
            log(f"[run] sign-flip terminal: {n_sa} unresolved forecasts left "
                "LIVE, red, reported (never frozen — the run-204 lesson)")
        err_guard(f"plugs + terminal {tag}")
        collapse_guard(f"plugs + terminal {tag}")
        # THE FINAL CLOSER: keytie back-outs and anchors can re-open an
        # actual-year check by a residue — close once more before judging
        if client is not None or stage4_answerer is not None:
            n_tl2 = terminal_ladder(loop, log)
            if n_tl2:
                log(f"[run] terminal ladder ({tag}): {n_tl2} late-shifted "
                    "actual-year checks re-closed")
                err_guard(f"terminal {tag}")
                collapse_guard(f"terminal {tag}")

    from .keytie import key_violations as _key_violations

    def gate_once():
        ok_g, fails_g, card_g = gate_mod.deliver_or_refuse(
            wb, spec_d, target_year, pre_map, writer.log, served=served,
            pre_values_wb=wb_values, load_bearing=lb,
            pre_formulas_path=str(archive), error_baseline=err_base)
        # RULE 2: a proven-printed key that moved off the print refuses
        # the run exactly like an unbalanced check does — and feeds the
        # same take-back loop
        for nm, ref, then, now in _key_violations(wb, spec_d, target_year,
                                                  ledger, _panel_path, keys_before):
            fails_g.append(f"KEY {nm} at {ref}: was proven-printed "
                           f"{then:,.1f}, now {now if now is None else f'{now:,.1f}'}"
                           " — printed nowhere (rule 2)")
            ok_g = False
        return ok_g, fails_g, card_g

    def check_mass():
        ev_m = _Ev(wb)
        m = 0.0
        for _nm, _ref, then, now in _key_violations(wb, spec_d, target_year,
                                                    ledger, _panel_path, keys_before):
            m += abs((now if isinstance(now, (int, float)) else 0.0) - then)
        for c in (spec_d.get("check_rows") or []):
            sh = c.get("sheet")
            if sh not in wb.sheetnames:
                continue
            for _y, col in year_columns(spec_d, sh).items():
                try:
                    v = ev_m.cell(sh, f"{col}{int(c['row'])}")
                except Exception:
                    continue
                if isinstance(v, (int, float)):
                    m += abs(v)
        return m

    repair_round("first")
    ok, failures, card = gate_once()

    # THE GATE LOOP (owner ruling 2026-09-02: "the gate found it didn't
    # balance -> the agent takes back the action and revises where it
    # went wrong" — trial and error IS the analyst's workflow; a judge
    # that only refuses makes the agent give up). On refusal, the
    # failure feeds back: take back the run's own stage-4 serves in
    # tiers (the uncorroborated reds first, then all of them — the
    # all-flag floor is a proven-deliverable state), RE-RUN the repair
    # suite on the corrected state (anchors and plugs were solved
    # against the wrong values), and judge again. Bounded; each round
    # must not worsen the total check residual or it is undone.
    if not ok and (client is not None or stage4_answerer is not None):
        red_set = set(writer.log.get("flags", []))
        # the append-only ledger, not the undo journal: the guards POP
        # undo while unwinding (run-223: the take-back saw an empty slice)
        undo = [(sh_, co_, old_) for sh_, co_, old_, _new in
                list(writer.log.get("writes_all", []))[undo_mark:undo_mark2]]
        from .checks import year_columns as _yc2
        import re as _re2

        def _stage4_writes(only_red):
            out, seen_rv = [], set()
            for sh_u, coord_u, old_u in undo:
                ref_u = f"{sh_u}!{coord_u}"
                if ref_u in seen_rv:
                    continue
                if only_red and ref_u not in red_set:
                    continue
                m_u = _re2.match(r"^([A-Z]{1,3})(\d+)$", coord_u)
                if not m_u or m_u.group(1) != _yc2(spec_d, sh_u).get(
                        str(target_year)):
                    continue
                seen_rv.add(ref_u)
                out.append((sh_u, coord_u, old_u,
                            wb[sh_u][coord_u].value))
            return out

        mass0 = check_mass()
        reverted_all = []
        for tier, only_red in (("red", True), ("all", False)):
            if ok:
                break
            reverts = [r for r in _stage4_writes(only_red=only_red)
                       if (r[0], r[1]) not in {(x[0], x[1])
                                               for x in reverted_all}]
            if not reverts:
                continue
            snapshot = [(sh_u, coord_u, wb[sh_u][coord_u].value)
                        for sh_u, coord_u, _o, _w in reverts]
            # THE CLEAN-SLATE RULE (run-224: taking back the serves but
            # KEEPING the anchors and plugs that were solved AGAINST
            # them left a state worse than the floor — 5,255 -> 10,279).
            # Repairs are answers to the serves; when the serves go,
            # every repair-suite write made after stage 4 goes too, in
            # reverse order, and the idempotent suite re-solves from a
            # clean base. Everything stays in the ledger and the log.
            repairs = list(writer.log.get("writes_all", []))[undo_mark2:]
            snap_rep = [(sh_r, co_r, wb[sh_r][co_r].value)
                        for sh_r, co_r, _o, _n in repairs]
            for sh_r, co_r, old_r, _n in reversed(repairs):
                wb[sh_r][co_r] = old_r
            for sh_u, coord_u, old_u, _now in reverts:
                wb[sh_u][coord_u] = old_u
            repair_round(f"gate-loop {tier}")
            ok2, failures2, card2 = gate_once()
            mass1 = check_mass()
            if ok2 or mass1 < mass0 - 1.0:
                ok, failures, card = ok2, failures2, card2
                mass0 = mass1
                reverted_all += reverts
                for sh_u, coord_u, old_u, was in reverts:
                    if writer.in_forecast(sh_u, coord_u):
                        writer.watch(sh_u, coord_u,
                                     f"the run's answer ({was!r}) was taken "
                                     "back so the model could balance")
                        continue
                    c_u = wb[sh_u][coord_u]
                    c_u.fill = writer.fills["red"]
                    c_u.comment = _Cmt(
                        (f"Taken back: the run's answer here ({was!r}) "
                         "stopped the model balancing; kept last period's "
                         "figure — please check."),
                        "Model Update Agent")
                    if f"{sh_u}!{coord_u}" not in writer.log["flags"]:
                        writer.log["flags"].append(f"{sh_u}!{coord_u}")
                log(f"[run] gate loop ({tier} tier): {len(reverts)} "
                    f"stage-4 serves taken back, repairs re-run -> "
                    f"{'gate PASSED' if ok else f'residual mass {mass1:,.0f}, still refused'}")
            else:
                for sh_u, coord_u, was in snapshot:
                    wb[sh_u][coord_u] = was
                for sh_r, co_r, was_r in snap_rep:
                    wb[sh_r][co_r] = was_r
                log(f"[run] gate loop ({tier} tier): taking back "
                    f"{len(reverts)} serves did not help "
                    f"({mass0:,.0f} -> {mass1:,.0f}) — restored")
        if not ok:
            # one more repair-only round on the best state: anchors and
            # plugs re-solved once more may finish what the take-backs
            # opened (bounded: this is the last)
            repair_round("gate-loop final")
            ok3, failures3, card3 = gate_once()
            if ok3 or check_mass() < mass0 - 1.0:
                ok, failures, card = ok3, failures3, card3
                log(f"[run] gate loop (final repair): "
                    f"{'gate PASSED' if ok else 'improved, still refused'}")
    for line in card.get("inherited_breaks", []):
        log(f"[run]   inherited (analyst's): {line}")
    for line in card.get("moveon_reported", []):
        log(f"[run]   move-on (reported, not refused): {line}")

    # -- report + spec-tab memory + snapshots
    from .rollover import report_lines as _rollover_lines
    try:
        rollover = _rollover_lines(wb, spec_d, target_year, est_base,
                                   spec_d.get("key_rows") or [],
                                   writer.log.get("verdicts", []))
    except Exception as e:              # the report never blocks delivery
        rollover = []
        log(f"[run] rollover report skipped: {e}")
    report_mod.build_report(wb, spec_d, target_year, writer.log, served,
                            pre_estimates, failures, loop_summary,
                            documents=[d["line"] for d in documents],
                            rollover=rollover)
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
    # Without a client the deterministic parts still render (owner
    # 2026-09-02: the OLD-estimate block belongs on every delivery).
    if True:
        try:
            from .execreport import report_only
            rep = report_only(str(company_dir), str(out_path),
                              str(archive), client, str(out_path),
                              target_year=target_year,
                              extra={"documents": [d["line"] for d in documents],
                                     "rollover": rollover,
                                     "forecast_watch": list(
                                         writer.log.get("forecast_watch", []))})
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
