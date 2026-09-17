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
import re
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
from .writer import (Writer, formula_map, load, roll_year_headers,
                     rollover_column, save)


def artifact_dir(company_dir, period, pinned_ledger):
    """Where THIS run's own artifacts go. A replay never writes into the pin
    it is replaying (2026-09-14: replays saved their ledger and serves over
    companies/<CO>/replay/<PERIOD>/ and each floor then ran on the previous
    replay's outputs; 2026-09-16: the live-shape floor, which has a client,
    rewrote key_rows.json there and the plain floors stopped measuring the
    same thing). A pinned run's outputs go beside the floor, never on it."""
    return Path(company_dir) / "replay" / (f"{period}-replay" if pinned_ledger else str(period))


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


RUN_TARGET_S = 60 * 60      # the owner's acceptance criterion: one run, one hour
FINISH_MARGIN_S = 3 * 60    # gate loop + report + save, measured ~1 min on run 250


def review_budget_s(elapsed_s, run_target_s=RUN_TARGET_S, finish_margin_s=FINISH_MARGIN_S):
    """WHAT THE RUN HAS LEFT IS WHAT THE REVIEW GETS (owner 2026-09-16, after the
    first live review: a run that reached the review in 12 minutes was handed 12
    of the 45 minutes it still had, and the clock cut it mid-turn with the model
    unbalanced). The review's budget is the run's own remaining time less the
    margin reserved for the last resort, saving and the report — no second clock
    of its own. It is never negative: with nothing left the review runs no turns
    and goes straight to the ladder, which is exactly what the margin is for.
    -> seconds the review may spend."""
    return max(0.0, run_target_s - finish_margin_s - elapsed_s)


import os as _os_mod
_os_env = _os_mod.environ


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
    if client is not None:
        # THE RUN CLOCK (audit 2026-09-14): every LLM call reads the run's
        # deadline — no call or retry outlives the hour
        try:
            client.deadline = _run_t0 + RUN_TARGET_S
        except Exception:
            pass
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
            # DELIVER WITH THE PROBLEM, NEVER REFUSE (owner 2026-09-14): the
            # analyst asked for a half-year update, so the model should carry
            # a half-year panel — none was found; the model goes back
            # untouched with the finding on its report page
            _msg = (f"no sheet in the model carries a {_kind0} panel for {target_year} — an interim "
                    "update has nowhere to land; the analyst decides where interim figures go")
            log(f"[run] {_msg}")
            _out0 = _model_path(company_dir, spec_d)
            _deliv = _out0.with_name(f"{_out0.stem} {period} (pipeline){_out0.suffix}")
            try:
                _wb0 = load(_out0)
                from .reportpage import build as _build_page
                _build_page(_wb0, None, spec_d, target_year, period,
                            {"open_checks": [f"NO {_kind0} PANEL: {_msg}"], "period": str(period)}, log)
                save(_wb0, _deliv)
            except Exception as _e_np:
                log(f"[run] report for the missing panel not written: {_e_np!r}")
            return {"ok": False, "gate_ok": False, "open_checks": [_msg], "out": str(_deliv),
                    "archive": None, "served": 0, "failures": [_msg], "completion": None, "replay": None}
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
    # THE KEY ROWS TRAVEL WITH THE REPLAY (owner 2026-09-08, "test before
    # running"): the brain's named rows are pinned beside the ledger so a
    # faithful replay ties the same keys and prints the same count
    # A REPLAY NEVER OVERWRITES THE PIN IT IS REPLAYING (2026-09-16: the
    # live-shape floor has a client, so it rewrote the very key_rows.json the
    # plain floors read as their pin — the floors stopped comparing). A run
    # given a pinned ledger writes its own artifacts beside its own output,
    # exactly where its decisions and provenance already go.
    _kr_path = artifact_dir(company_dir, period, pinned_ledger) / "key_rows.json"
    if client is not None and spec_d.get("key_rows"):
        try:
            _kr_path.parent.mkdir(parents=True, exist_ok=True)
            _kr_path.write_text(json.dumps(spec_d["key_rows"], ensure_ascii=False, indent=1))
        except Exception:
            pass
    elif client is None and pinned_ledger and not spec_d.get("key_rows"):
        _kr_pin = Path(pinned_ledger).parent / "key_rows.json"
        if _kr_pin.exists():
            try:
                spec_d["key_rows"] = json.loads(_kr_pin.read_text())
                log(f"[run] key rows PINNED: {len(spec_d['key_rows'])} replayed from {_kr_pin}")
            except Exception:
                pass
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
        """MEASURED, NOT UNDONE (owner 2026-09-17: code never takes back what
        the brain wrote). Cells that stopped computing after a stage are named,
        flagged red where they live, and reach the brain and the gate."""
        cur = new_errors(err_base, error_cells(wb, spec_d), spec_d, target_year)
        if not cur:
            return
        for s_e, c_e, _w in cur[:cap]:
            writer.flag_ref(f"{s_e}!{c_e}", "red",
                            f"This cell stopped computing after the {stage} stage — its inputs no longer "
                            "make sense to the model. Please check what feeds it.")
        log(f"[run]   error guard [{stage}]: {len(cur)} new errors — red, said, not reverted: "
            + "; ".join(f"{s_e}!{c_e}" for s_e, c_e, _w in cur[:5]))

    def collapse_guard(stage, cap=40):
        """A write must survive its consequences (the run-204 tariff: an
        evidence-clean ZERO deleted next year's revenue) — SO IT IS MEASURED
        AND SAID (owner 2026-09-17). The forecast rows that collapsed against
        the analyst's own baseline go on the watch list with the actual-column
        cause; nothing is reverted by code."""
        cur = collapsed_forecasts(wb, spec_d, target_year, fc_base)
        if not cur:
            return
        for (sh, r, now, was) in cur[:cap]:
            from .checks import forecast_columns as _fc
            fc1 = _fc(spec_d, sh, target_year)
            if not fc1:
                continue
            # a forecast cell is never painted (owner 2026-09-07): the
            # row goes on the watch list; the cause lives in the actual column
            writer.watch(sh, f"{fc1[0]}{r}",
                         f"forecast moved from {was:,.0f} to {now:,.0f} "
                         "after the update")
        log(f"[run]   collapse guard [{stage}]: {len(cur)} forecast rows collapsed against the "
            "analyst's baseline — watch-listed with their cause, not reverted")

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
    _restate = str(_os_env.get("RESTATE", "")).strip().lower() in ("1", "true", "yes")
    if not docs:
        raise FileNotFoundError(f"no disclosures for {period} under {company_dir}")
    if pinned_ledger:
        # THE PINNED-SNAPSHOT PATH (operator council 2026-09-01): replay
        # a prior run's evidence ledger — offline validation for models
        # whose statements need vision (scanned pages read nothing in a
        # client=None rebuild; the pinned ledger carries the checksummed
        # transcriptions)
        ledger = Ledger.from_json(Path(pinned_ledger).read_text())
        ledger.corroborate(log)
        log(f"[run] stage 1 PINNED: ledger replayed from {pinned_ledger} "
            f"({len(ledger.items)} items)")
    else:
        ledger = read_documents(docs, client=client, known_values=known,
                                log=log)
        ledger.corroborate(log)
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
    _pinned_periods = dict(getattr(ledger, "_doc_periods", None) or {}) if pinned_ledger else None
    documents = identify_documents(docs, ledger, client, target_year, _kind, log)
    if _pinned_periods:
        # a replay keeps the live run's vintage verdicts (audit 2026-09-14: re-deriving them
        # offline without the brain had moved documents between current and unknown)
        ledger._doc_periods = _pinned_periods
        ledger.stamp_vintages()
    from .docid import identify_statement_pages
    identify_statement_pages(docs, ledger, client, known, log)
    # THE TABLE READER (owner 2026-09-14): the brain says what every
    # table's columns are — periods, segments, categories, movements, a
    # grid — before any stage pairs a current with a prior; no shape rule
    try:
        from .tables import describe_tables
        describe_tables(client, ledger, docs, target_year, period, log)
    except Exception as _e_tab:
        # deliver-never-refuse: the run goes on with the shape stamps, but
        # the loss is loud — the bench refuses a floor whose log carries it
        log(f"[tables] STAGE LOST: table reader crashed ({_e_tab!r}) — the shape stamps stand")
        run_log.append(f"[tables] STAGE LOST: table reader crashed ({_e_tab!r})")
    _ban = _vintage_ban(ledger)
    if _ban:
        log(f"[run] vintage law: {len(_ban)} document(s) may not source "
            f"current-year values: {sorted(_ban)}")
    writer = Writer(wb)          # the one writer of the run
    # ONE RESTATEMENT DECIDER (owner 2026-09-17): the disagreements between
    # this year's comparatives and the model's own prior column are FOUND here
    # and shown to the brain beside the row; the brain's `restate` tool is the
    # only thing that writes a prior cell.
    _restate_leads = {}
    log(f"[run] restate: RESTATE={'on' if _restate else 'off'} — "
        "comparative disagreements are indexed for the brain either way")
    try:
        from .restate import restatement_leads
        _restate_leads = restatement_leads(wb, wb_values, spec_d, target_year, ledger,
                                           {t.key: t for t in targets}, log, period=period)
    except Exception as _e_rs:
        log(f"[run] restate index STAGE LOST: {_e_rs!r}")
        run_log.append(f"[run] restate index STAGE LOST: {_e_rs!r}")

    # -- Stage 2 (pure code): statement faces, then bound non-statement
    # tables (the Driver/MD&A path — council two-level binding)
    # THE RECONCILIATION STAGE (owner ruling 2026-09-01): whole
    # statements walked line-by-line — the by-hand method as the serve
    # engine. Its serves are authoritative; the scattered joins only
    # fill what reconciliation left open.
    # WHAT CODE FINDS IS A LEAD, NOT A WRITE (owner 2026-09-17): the
    # statement walk and the number-tie join are candidate INDEXES now —
    # their pairings reach the brain in the mapping context, beside the row
    # they are a lead for, and nothing here fills a cell.
    from .reconcile import reconcile
    recon_serves, recon_map = reconcile(wb, spec_d, target_year, ledger,
                                        log)
    join_serves, decisions = join(ledger, targets, run_log)
    extra, dec2 = join_bound_tables(ledger, targets, join_serves, run_log)
    decisions += dec2
    leads = {}
    for _k_rs, _v_rs in (_restate_leads or {}).items():
        leads.setdefault(_k_rs, []).append(_v_rs)
    for src, pool in (("the statement walk", recon_serves), ("the number tie", join_serves),
                      ("a bound table", extra)):
        for (sh_l, r_l), e_l in (pool or {}).items():
            if not isinstance(e_l, dict) or not isinstance(e_l.get("value"), (int, float)):
                continue
            leads.setdefault((sh_l, r_l), []).append(
                f"{src}: {e_l['value']:,.2f} from {e_l.get('doc', '?')} p{e_l.get('page', '?')} "
                f"'{str(e_l.get('line') or '')[:60]}'")
    log(f"[run] leads: {len(leads)} rows carry a candidate from the statement walk / the number tie "
        f"(shown to the brain, never written)")
    served = {}                       # nothing is served until the brain maps it
    for ln in run_log[-4:]:
        log(f"[run] {ln}")

    # -- the owner's column convention, then guarded writes
    writer.served = served                       # a take-back un-serves what it takes back
    # the forecast columns per sheet: a law that finds a forecast cell
    # strange watch-lists it instead of painting it (owner 2026-09-07)
    from .checks import forecast_columns as _fcols0
    writer.forecast_cols = {
        sh: set(_fcols0(spec_d, sh, target_year) or ())
        for sh in (spec_d.get("year_axis") or {}) if sh in wb.sheetnames}
    from .checks import prior_column, year_columns
    # THE ZERO-FORECAST ROWS (owner 2026-09-14): measured once on the
    # analyst's own model before anything rolls — a row at zero this year
    # and in every forecast year rolls in as 0 and takes no estimate
    from .writer import unforecast_rows as _unforecast_rows
    try:
        from .evaluator import Evaluator as _Ev0
        _ev0 = _Ev0(wb)
        _eval0 = (lambda sh_, co_: _ev0.cell(sh_, co_))
    except Exception:
        _eval0 = None
    writer.unforecast_rows = set()
    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        if tcol and sheet in wb.sheetnames:
            _chk_rows = {int(c_.get("row")) for c_ in (spec_d.get("check_rows") or []) if c_.get("sheet") == sheet and c_.get("row") is not None}
            for r_ in _unforecast_rows(wb, sheet, tcol, sorted(writer.forecast_cols.get(sheet) or ()), _eval0, skip_rows=_chk_rows):
                writer.unforecast_rows.add((sheet, r_))
    if writer.unforecast_rows:
        log(f"[run] zero forecast: {len(writer.unforecast_rows)} rows whose forecast years are all 0 in the "
            f"analyst's model — they stay 0 whatever the actual (held after the update)")
    hardcode_census = {}          # sheet -> rows that arrived as hardcodes
    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if tcol and pcol and sheet in wb.sheetnames:
            hard = rollover_column(wb, sheet, pcol, tcol,
                                   zero_rows={r_ for (sh_, r_) in writer.unforecast_rows if sh_ == sheet})
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
            if _n.startswith(("schedule", "sense check", "new-line", "tier-3", "0 means 0", "printed nil",
                              "KEY-TIE", "PLUG", "Plug", "COMPOSITE", "constants law", "roll-base", "held")):
                continue        # THE RUN'S OWN PRODUCTS ARE RE-DECIDED (audit 2026-09-14): a
                                # schedule serve, a sense-check fix, a hold or a plug is not a
                                # brain read; pinning them flattered the floors
            served[key_p] = {"value": e["value"], "status": "OK",
                             "doc": e.get("doc"), "page": e.get("page"),
                             "line": e.get("line"),
                             "conf": e.get("conf") or 4,
                             "note": "PINNED replay: " + str(e.get("note"))}
            n_pin += 1
        log(f"[run] served PINNED: {n_pin} live serves replayed from "
            f"{pinned_served}")
    # -- ROLL-FORWARD SCHEDULES (owner 2026-09-10): the vertical prior tie —
    # a movement table's opening row is last year's closing. A LEAD now: the
    # tie is found and shown, the brain says whether that row IS this one.
    try:
        from .schedules import schedule_leads as _schedule_leads
        for (_sh_s, _r_s), _txt_s in (_schedule_leads(wb, spec_d, target_year, ledger, log) or {}).items():
            leads.setdefault((_sh_s, _r_s), []).append(_txt_s)
    except Exception as _e_sched:
        log(f"[run] schedule leads skipped: {_e_sched!r}")

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
            writer.flag_ref(f"{sheet}!{tcol}{r}", "red",
                "STALE INPUT: rolled from the prior actual column; no proven "
                "disclosure read replaced it — review or accept.")
            n_stale += 1
    if n_stale:
        log(f"[run] {n_stale} unserved hardcode inputs flagged STALE (red)")

    # -- WHAT THE SWEEPS USED TO WRITE IS NOW A LEAD (owner 2026-09-17).
    # The constants law, the composition sweep, the tier-3 hold, the dash-nil
    # sweep and the new-line serve all DECIDED a cell from a coincidence of
    # numbers. What they found is kept — the formula's stale constants and the
    # prior year's own composition reach the brain in the mapping context,
    # beside the row — and none of them writes.
    from .stage2_join import infer_composition
    targets_by_key = {t.key: t for t in targets}
    n_lead_comp = 0
    for sheet, rows in hardcode_census.items():
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if not tcol or not pcol:
            continue
        for r in rows:
            f = infer_composition(wb, sheet, r, pcol, tcol)
            if f:
                leads.setdefault((sheet, r), []).append(
                    f"last year this row IS its own component rows added up ({f}) — "
                    "the same arithmetic this year is yours to state")
                n_lead_comp += 1
    if n_lead_comp:
        log(f"[run] composition leads: {n_lead_comp} rows whose prior year proves a sum of their own "
            "component rows (shown to the brain, never written)")
    # the load-bearing trace stays a MEASURE: which rows the model's own
    # formulas carry to the key rows (shown as 'what this row feeds')
    from .loadbearing import trace as lb_trace
    lb = lb_trace(wb, spec_d, target_year)
    # -- WHAT THE MODEL'S OWN STRUCTURE SAYS, AS INFORMATION (owner
    # 2026-09-17): the segment block whose total is known, the forecast
    # assumption wired to the past, the quantity with a second home, the
    # roll base that no longer reproduces its actual. Each is FOUND by code
    # and SAID — to the brain in the mapping context and to the review on the
    # watch list — and none of them decides a cell any more.
    from .evaluator import Evaluator
    from .reclass import flag_embedded_hardcodes
    sheets_ax = list(spec_d.get("year_axis") or {})
    ycols = {s: year_columns(spec_d, s).get(str(target_year))
             for s in sheets_ax}
    flag_embedded_hardcodes(wb, sheets_ax, ycols, writer, log)

    from openpyxl.utils import column_index_from_string
    from .freeze import plan_freezes
    wb_pre_formulas = load(archive)      # manual-calc models cache nothing
    n_fz = 0
    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        if not tcol or sheet not in wb.sheetnames \
                or sheet not in wb_values.sheetnames:
            continue
        for pl in plan_freezes(wb, wb_values, [sheet],
                               column_index_from_string(tcol),
                               pre_formulas_wb=wb_pre_formulas):
            _ref_fz = f"{sheet}!{pl.get('coord')}" if isinstance(pl, dict) else str(pl)
            _co_fz = _ref_fz.split("!", 1)[-1]
            writer.watch(sheet, _co_fz,
                         "this forecast assumption reads the column that has just become actual — "
                         "it rebases onto the actual year unless you hold it; the analyst's own value "
                         f"was {str((pl.get('value') if isinstance(pl, dict) else ''))[:20]}")
            n_fz += 1
    if n_fz:
        log(f"[run] assumption watch: {n_fz} forecast assumptions read the newly actual column "
            "(watch-listed for the review — nothing frozen by code)")
    err_guard("structure watch")
    collapse_guard("structure watch")

    from .teachings import plug_meter, twin_leads
    for (_sh_t, _r_t), _txt_t in (twin_leads(wb, wb_values, spec_d, target_year, log) or {}).items():
        leads.setdefault((_sh_t, _r_t), []).append(_txt_t)

    # -- ROLL-BASE CONSISTENCY (owner ruling 2026-09-01): a typed actual whose
    # forecast is computed must be REPRODUCED by its own roll formula pointed
    # back one year. Measured and flagged red; re-anchoring is the brain's.
    from .teachings import roll_base_mismatches
    n_rb = roll_base_mismatches(wb, spec_d, target_year, writer, log,
                                served=served)
    if n_rb:
        log(f"[run] roll-base consistency: {n_rb} rows roll from bases "
            "that do not reproduce their typed actuals — red, for the brain")

    # -- THE MOVE-ON LAW (owner ruling 2026-08-31): code does the
    # exhaustive not-disclosed looking for every stale red, and says so.
    from .moveon import machine_look
    machine_look(wb, spec_d, target_year, ledger, writer, log)

    # -- THE MAPPING (owner 2026-09-17): the brain maps the disclosure into
    # the model. Code lays out the model's own input rows with their leads and
    # the printed faces, answers the tools, verifies every write and measures
    # coverage. No cards, no code-decided serves, no one-shot per-row answers.
    undo_mark = len(writer.log.get("writes_all", []))
    # RULE 2 AT THE GATE (owner, 2026-09-03: "rule 1 is balance, rule 2 is the
    # keys"): the keys proven-printed HERE must still be so at delivery.
    from .keytie import key_snapshot as _key_snapshot
    _panel_path = company_dir / "replay" / str(period) / "key_panel.json"
    # THE KEY PANEL BY PRIOR TIE (owner 2026-09-08): each headline row's
    # print is read off the printed line whose comparative equals the
    # model's own prior; the pinned file only fills what the tie cannot
    from .keytie import panel_by_prior_tie as _pbpt, merge_panel as _merge_panel, _panel as _load_panel
    _built = _pbpt(wb, spec_d, target_year, ledger, log, served=served)
    _key_panel = _merge_panel(_built, _load_panel(_panel_path), log)
    log(f"[run] key panel: {len(_built)} keys by prior tie "
        f"({', '.join(sorted(_built))}); {len(_key_panel) - len(_built)} from the pinned file")
    for _kn, _ke in sorted(_built.items()):
        log(f"[run]   key '{_kn}': print {_ke['print']:,.2f} prior {_ke['prior']:,.2f} — {_ke.get('line', '')}")
    keys_before = _key_snapshot(wb, spec_d, target_year, ledger, _panel_path, panel=_key_panel)
    if keys_before:
        log(f"[run] rule 2 armed: {len(keys_before)} key(s) proven-printed "
            f"before the mapping ({', '.join(sorted(keys_before))})")
    loop_summary = ""
    loop = ObjectiveLoop(wb, spec_d, target_year, ledger, targets, served,
                         writer, client, run_log, budget=loop_budget)
    loop.load_bearing = lb           # the wiring: what each input row feeds
    loop.key_panel = _key_panel      # the proven prints of the key rows
    loop.key_panel_path = _panel_path
    loop.period = period
    loop.leads = leads               # what code found, for the brain to judge
    loop.pre_path = str(archive)
    loop.est_base = est_base
    loop.brain = client is not None or getattr(stage4_answerer, "maps", None) is not None
    if stage4_mode:
        log(f"[run] stage4_mode={stage4_mode!r} is not read any more: the mapping loop is the stage")
    # THE SENSE CHECK'S CHECKPOINT (owner 2026-09-09): the headline lines
    # against the analyst's pre-update model, for the review to read
    try:
        from .sensecheck import checkpoint as _sense_checkpoint
        _pre_wb_sense = load(str(archive))
        _sense_checkpoint(loop, _pre_wb_sense, log)
    except Exception as _e_sc:
        _pre_wb_sense = load(str(archive))
        log(f"[sense] checkpoint STAGE LOST: {_e_sc!r}")
        run_log.append(f"[sense] checkpoint STAGE LOST: {_e_sc!r}")
    from .mapping import page_text_of_docs as _page_text_of_docs, run_mapping as _run_mapping
    # the EARLIER periods' documents are on the shelf, not in the context: the
    # brain reaches for last year's report only to triangulate a row whose
    # comparative no longer matches, and the index is built then (owner 2026-09-17)
    _earlier = sorted(q for q in (Path(company_dir) / "disclosures").glob("*/*.pdf")
                      if q.parent.name != str(period))
    _page_text = _page_text_of_docs(docs, _earlier, log)
    if _earlier:
        log(f"[map] {len(_earlier)} earlier-period document(s) on the shelf, indexed only if the brain "
            f"reaches for them: {', '.join(q.name for q in _earlier[:4])}")

    def _ask_map(system, user):
        """One mapping turn. A replay's recorded turns stand in for the brain."""
        _scripted = getattr(stage4_answerer, "maps", None)
        if callable(_scripted):
            return _scripted(system, user)     # a harness that answers from the context (the pace test)
        if _scripted is not None:
            if not _scripted:
                raise RuntimeError("the replay has no further mapping turns recorded")
            return _scripted.pop(0)
        if client is None:
            raise RuntimeError("no brain in this run")
        return client.json(system, user,
                           lambda o: [] if isinstance(o, dict) and isinstance(o.get("calls"), list)
                           else ["reply must be {\"thinking\": ..., \"calls\": [...]}"],
                           repair_retries=1)
    # THE BUDGET SPLIT (owner 2026-09-17): the mapping takes the larger share
    # of what the hour has left; the review takes the rest, and the finish
    # margin is never touched.
    _left_map = RUN_TARGET_S - FINISH_MARGIN_S - (_time.monotonic() - _run_t0)
    _map_budget = max(60.0, _left_map * 0.75)
    log(f"[run] budget: {(_time.monotonic() - _run_t0)/60:.1f} min already spent; {_left_map/60:.1f} min "
        f"left — {_map_budget/60:.1f} to the mapping, {(_left_map - _map_budget)/60:.1f} to the review")
    try:
        from .llm import set_reasoning as _set_reasoning
        _set_reasoning("low", log)        # the mapping reads and writes; the review reasons
    except Exception as _e_r:
        log(f"[llm] the stage's reasoning effort could not be set: {_e_r!r}")
    # THE FACES FIRST, ALL AT ONCE (owner 2026-09-17): one call per printed
    # face, concurrent — then a short sequential pass for what crosses faces.
    from .mapping import map_faces as _map_faces
    _face_budget = _map_budget * 0.7
    _map_t0 = _time.monotonic()
    if loop.brain:
        try:
            _map_faces(loop, _pre_wb_sense, hardcode_census, _page_text, log, _ask_map,
                       deadline_s=_face_budget, workers=8)
        except Exception as _e_mf:
            log(f"[map] the face round STAGE LOST: {_e_mf!r}")
            run_log.append(f"[map] the face round STAGE LOST: {_e_mf!r}")
    # WHAT THE FACES DID NOT SPEND IS STILL THE MAPPING'S (owner 2026-09-17: the
    # CLP faces answered in 2.3 of their 23.2 minutes and the other 21 were
    # thrown away)
    from .mapping import sequential_budget as _seq_left
    _seq_budget = _seq_left(_map_budget, _time.monotonic() - _map_t0)
    log(f"[map] the face round took {(_time.monotonic() - _map_t0)/60:.1f} min; "
        f"{_seq_budget/60:.1f} min of the mapping's clock go to the rows that are left")
    loop_summary = _run_mapping(loop, _pre_wb_sense, hardcode_census, _page_text, log, _ask_map,
                                deadline_s=_seq_budget, brain=loop.brain)
    undo_mark2 = len(writer.log.get("writes_all", []))   # end of the mapping's writes
    err_guard("mapping")
    collapse_guard("mapping")
    # the model's own residual rows are truth meters — a wild plug means an
    # input feeding its total is wrong (reported, never silent)
    done_v = {v.split(":", 1)[0] for v in writer.log.get("verdicts", [])}
    for (pm_sh, pm_r, pm_now, pm_was) in plug_meter(wb, spec_d, target_year):
        tc_pm = spec_d["year_axis"][pm_sh]["columns"].get(
            str(target_year)) if pm_sh in spec_d.get("year_axis", {}) else None
        if not tc_pm or f"{pm_sh}!{tc_pm}{pm_r}" in done_v:
            continue
        writer.flag_ref(f"{pm_sh}!{tc_pm}{pm_r}", "red",
            f"PLUG METER: this residual row computed {pm_was:,.1f} "
            f"last year and {pm_now:,.1f} now — the model's own plug "
            "is absorbing something wrong in the inputs that feed "
            "its total. ANALYST REVIEW.")
        writer.log.setdefault("verdicts", []).append(
            f"{pm_sh}!{tc_pm}{pm_r}: SUSPICIOUS — the model's own "
            f"residual swung {pm_was:,.1f} -> {pm_now:,.1f}; an "
            "input feeding its total is probably wrong")
    # THE KEYS ARE MEASURED, NEVER CLOSED BY CODE (owner 2026-09-17: the key
    # tie's automatic back-out is gone). What is off the print is said here
    # and reaches the review, which can set it with evidence.
    # A KEY COMPUTED FROM UNMAPPED INPUTS SAYS SO (owner 2026-09-17): the number
    # in a key row is only as good as the rows underneath it, and the analyst
    # must see how many of those were never mapped.
    try:
        from .mapping import keys_on_open_inputs as _keys_open, input_rows as _in_rows
        for _nm_k, _ref_k, _open_k in _keys_open(loop, _in_rows(loop, hardcode_census),
                                                 spec_d, target_year):
            # A NOTE ALREADY ON THE CELL IS KEPT (reviewer 2026-09-17: painting a
            # flag replaces the comment wholesale, so this would erase whatever
            # the mapping or the key tie had already said about the same row)
            _sh_k, _, _co_k = _ref_k.partition("!")
            _had = wb[_sh_k][_co_k].comment.text if (_sh_k in wb.sheetnames
                                                     and wb[_sh_k][_co_k].comment is not None) else ""
            writer.flag_ref(_ref_k, "red",
                f"COMPUTED FROM {len(_open_k)} UNMAPPED INPUT(S): this key is the model's own "
                f"arithmetic over rows that were never mapped or are red — {', '.join(_open_k[:6])}. "
                "Its number is only as good as those."
                + (f" | {str(_had)[:300]}" if _had else ""))
            log(f"[run] key '{_nm_k}' at {_ref_k} is computed from {len(_open_k)} unmapped input(s): "
                + ", ".join(_open_k[:6]))
    except Exception as _e_ku:
        log(f"[run] the keys' input coverage could not be measured: {_e_ku!r}")
        run_log.append(f"[run] the keys' input coverage could not be measured: {_e_ku!r}")
    try:
        from .keytie import key_state as _key_state
        for _nm, _ref, _got, _want, _ok in _key_state(wb, spec_d, target_year, _panel_path, panel=_key_panel):
            log(f"[run] key '{_nm}' at {_ref}: model {_got if _got is None else f'{_got:,.2f}'} vs print "
                f"{_want if _want is None else f'{_want:,.2f}'} — {'ties' if _ok else 'OFF THE PRINT'}")
    except Exception as _e_ks:
        log(f"[run] the keys could not be measured: {_e_ks!r}")
    _more = _key_snapshot(wb, spec_d, target_year, ledger, _panel_path, panel=_key_panel)
    _new_keys = sorted(set(_more) - set(keys_before))
    keys_before.update(_more)
    if _new_keys:
        log(f"[run] rule 2 re-armed after the mapping: +{len(_new_keys)} ({', '.join(_new_keys)})")

    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if tcol and pcol and sheet in wb.sheetnames:
            writer.format_rollover(sheet, pcol, tcol)

    # THE ONE-OFF THAT WOULD PROPAGATE, AS A WATCH (owner 2026-09-17): a
    # forecast link to an actual-year one-off, and a roll artifact the
    # analyst's own baseline disowns, are FOUND by code and said on the watch
    # list — the review's brain decides whether to hold them, with `set` and
    # `restore` in its hand. Code no longer edits a forecast by rule.
    from .teachings import oneoff_watch, probe_watch
    n_oo = oneoff_watch(wb, spec_d, target_year, writer, log)
    n_ap = probe_watch(wb, spec_d, target_year, fc_base, writer, log)
    if n_oo or n_ap:
        log(f"[run] forecast watch: {n_oo} forecast link(s) to an actual-year one-off, "
            f"{n_ap} roll artifact(s) against the analyst's baseline — watch-listed for the review")

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

    writer.plugs_allowed = True                  # THE PLUG LAW: the repair rounds are the last resort
    def repair_round(tag):
        """THE REPAIR SUITE — everything that closes checks after the
        actual column is marked: roll-base re-anchoring, forecast plugs,
        the sign-flip terminal, the final closer. Idempotent by design
        (anchors re-solve, plugs re-measure, verdicts skip the done),
        so the gate loop can run it again on a corrected state."""
        # (the key tie's automatic back-out is gone — owner 2026-09-17: a key
        # that is off the print is measured and said; closing it is the
        # brain's, with evidence, in the review)
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
                                                  ledger, _panel_path, keys_before, panel=_key_panel):
            _msg = (f"KEY {nm} at {ref}: was proven-printed "
                    f"{then:,.1f}, now {now if now is None else f'{now:,.1f}'}"
                    " — printed nowhere (rule 2)")
            if _msg not in fails_g:
                fails_g.append(_msg)
            ok_g = False
        return ok_g, fails_g, card_g

    # THE REVIEW (owner 2026-09-16): the brain reads the MODEL — the
    # objectives measured, the headline lines, every cell the run wrote with
    # its move against its own history and its printed evidence — calls the
    # tools it wants, and code applies, measures and verifies. No cards.
    from .review import run_review as _run_review
    _pre_end = locals().get("_pre_wb_sense")
    if _pre_end is None:
        _pre_end = load(str(archive))
    # THE REVIEW NEVER EATS THE FINISH MARGIN (reviewer 2026-09-16: a floor of
    # 120 s could run the review past the time reserved for saving, reporting and
    # the last resort). With nothing left it runs no turns and goes straight to
    # the ladder, which is exactly what the margin is for.
    _left_e = review_budget_s(_time.monotonic() - _run_t0)
    try:
        from .llm import set_reasoning as _set_reasoning2
        _set_reasoning2("medium", log)
    except Exception as _e_r2:
        log(f"[llm] the review's reasoning effort could not be set: {_e_r2!r}")

    def _ask_review(system, user):
        """One review turn. A replay's recorded turns stand in for the brain."""
        _scripted = getattr(stage4_answerer, "reviews", None)
        if _scripted is not None:
            if not _scripted:
                raise RuntimeError("the replay has no further review turns recorded")
            return _scripted.pop(0)
        if client is None:
            raise RuntimeError("no brain in this run")
        return client.json(system, user,
                           lambda o: [] if isinstance(o, dict) and isinstance(o.get("calls"), list)
                           else ["reply must be {\"thinking\": ..., \"calls\": [...]}"],
                           repair_retries=1)

    _notes = [str(x) for x in (writer.log.get("sense_check") or [])]
    try:
        ok, failures, card = _run_review(
            loop, _pre_end, log, _ask_review, gate_once, repair_round,
            keys_before, _key_panel, _panel_path,
            deadline_s=_left_e, notes=_notes,
            brain=(client is not None or getattr(stage4_answerer, "reviews", None) is not None))
    except Exception as _e_end:
        log(f"[review] STAGE LOST: {_e_end!r}")
        run_log.append(f"[review] STAGE LOST: {_e_end!r}")
        repair_round("first")
        ok, failures, card = gate_once()
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
        log(f"[run] rollover report STAGE LOST: {e!r}")
        run_log.append(f"[run] rollover report STAGE LOST: {e!r}")
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

    # A REPLAY NEVER WRITES INTO THE PINNED FLOOR (2026-09-14 autopsy: every
    # offline replay had been saving its own ledger, serves and decisions
    # over companies/<CO>/replay/<PERIOD>/, so each floor ran on the
    # previous replay's outputs — 252 pinned serves had drifted to 88 and a
    # check 'opened' that no code change had touched). A replay's outputs
    # go beside the floor, never on it.
    replay_dir = artifact_dir(company_dir, period, pinned_ledger)
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
    # THE WRITE JOURNAL (audit 2026-09-14: a cell's writer could not be named): every write and flag,
    # in order, with the look the cell had before it
    try:
        _wj = [{"i": k, "sheet": w_[0], "coord": w_[1], "old": str(w_[2])[:80], "new": str(w_[3])[:80],
                "before": (writer.log.get("style_journal") or [None] * (k + 1))[k][2:] if k < len(writer.log.get("style_journal") or []) else None}
               for k, w_ in enumerate(writer.log.get("writes_all", []))]
        (replay_dir / "writes.json").write_text(json.dumps(_wj, ensure_ascii=False, indent=0), encoding="utf-8")
    except Exception as _e_wj:
        log(f"[run] write journal STAGE LOST: {_e_wj!r}")
        run_log.append(f"[run] write journal STAGE LOST: {_e_wj!r}")
    (replay_dir / "provenance.json").write_text(
        json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8")

    # THE AGENT ALWAYS DELIVERS (BOSS_MINDMAP 2026-08-17: "refusal is dead
    # — no flag budget, no quarantine ... if truly unsolvable: back out,
    # mark, still deliver"; owner 2026-09-09 re-read it: "the gate must
    # stop refusing"). A check the repair could not close is MARKED on
    # its own cell — red, the residual in the note — and listed first
    # on the report; the workbook ships. Only a restatement pauses a run.
    open_checks = []
    if not ok:
        import re as _re_g
        for f_ in failures or []:
            m_ = _re_g.match(r"\s*CHECK (\S+)!r(\d+) \((\d{4})\): (\S+) vs (\S+)", str(f_))
            if not m_:
                continue                      # listed once, by the loop below
            sh_, r_, yr_, got_ = m_.group(1), int(m_.group(2)), m_.group(3), m_.group(4)
            col_ = year_columns(spec_d, sh_).get(yr_) if sh_ in wb.sheetnames else None
            if col_:
                from openpyxl.comments import Comment as _Cm
                c_ = wb[sh_][f"{col_}{r_}"]
                writer.flag_ref(f"{sh_}!{col_}{r_}", "red",
                    f"Open check: off by {got_}. The update could not close it — "
                                 "please trace the inputs of this check.")
            open_checks.append(f"{sh_}!{col_ or '?'}{r_} ({yr_}) off by {got_}")
        for f_ in failures or []:
            if not str(f_).lstrip().startswith("CHECK"):
                open_checks.append(str(f_)[:120])
        log(f"[run] delivered with {len(open_checks)} OPEN CHECK(S) marked red for the analyst: "
            + "; ".join(open_checks[:6]))
    tag = ""
    out_path = (company_dir / "model"
                / f"{model_path.stem} {period} (pipeline{tag}){model_path.suffix}")
    save(wb, out_path)
    log(f"[run] {'DELIVERED' if ok else 'DELIVERED WITH OPEN CHECKS'}: "
        f"{out_path.name}")
    # -- the executive _REPORT (owner's locked design): Luna composes,
    # the code renders and referees; includes the sense-check second
    # look. Regenerated on the delivered file; never fatal to the run.
    # Without a client the deterministic parts still render (owner
    # 2026-09-02: the OLD-estimate block belongs on every delivery).
    if True:
        try:
            from .execreport import report_only
            try:
                from .keytie import key_state as _key_state
                _key_ties_for_report = [
                    {"name": n_, "ref": ref_, "value": v_, "print": w_, "tied": ok_}
                    for n_, ref_, v_, w_, ok_ in _key_state(wb, spec_d, target_year, _panel_path, panel=_key_panel)]
                # a key row whose print no line tied is NOT tied (run 262:
                # operating cash flow had no panel entry and the count
                # read 8/9 while the row sat 1,308 off the by-hand answer)
                _have = {k_["name"] for k_ in _key_ties_for_report}
                for kk_ in (spec_d.get("key_rows") or []):
                    if kk_.get("name") not in _have:
                        _key_ties_for_report.append(
                            {"name": kk_.get("name"), "ref": f"{kk_.get('sheet')}!{kk_.get('row')}",
                             "value": None, "print": None, "tied": False})
                        _ask = ""
                        if spec_d.get("annual_prior_axis") is not None \
                                and not (spec_d.get("annual_prior_axis") or {}).get(kk_.get("sheet")):
                            # owner 2026-09-10: an interim statement compares to a
                            # date this model has no column for — ask, never estimate
                            _ask = (" — the model has no column holding the comparative the "
                                    "report prints; the analyst should provide the report for "
                                    "that date (annual report / prior period)")
                            writer.log.setdefault("verdicts", []).append(
                                f"{kk_.get('sheet')}!{kk_.get('row')}: ANALYST — key "
                                f"'{kk_.get('name')}' has no comparative in this model{_ask}")
                        log(f"[run] key '{kk_.get('name')}': no printed line ties its prior — not tied{_ask}")
            except Exception as _e:
                _key_ties_for_report = []
                log(f"[run] key count unavailable for the report: {_e!r}")
            log(f"[run] key count: {sum(1 for k in _key_ties_for_report if k['tied'])}/"
                f"{len(_key_ties_for_report)} tied to the print "
                f"(key rows {len(spec_d.get('key_rows') or [])}, panel {len(_key_panel)})")
            rep = report_only(str(company_dir), str(out_path),
                              str(archive), client, str(out_path),
                              target_year=target_year,
                              extra={"key_ties": _key_ties_for_report,
                                     "sense_check": writer.log.get("sense_check", []),
                                     "sense_rows": list(writer.log.get("sense_rows", [])),
                                     "restatements": list(writer.log.get("restatements", [])),
                                     "period": str(period),
                                     "elapsed_min": (_time.monotonic() - _run_t0) / 60.0,
                                     "provenance": {f"{sh_}!{r_}": {k_: e_.get(k_) for k_ in
                                                                    ("value", "doc", "page", "conf")}
                                                    for (sh_, r_), e_ in served.items() if isinstance(e_, dict)},
                                     "open_checks": open_checks,
                                     "documents": [d["line"] for d in documents],
                                     "rollover": rollover,
                                     "forecast_watch": list(
                                         writer.log.get("forecast_watch", []))})
            log(f"[run] executive report coverage line: {rep.get('coverage')!r}")
        except Exception as ex:
            log(f"[run] executive report STAGE LOST (old-style report kept): {ex!r}")
            run_log.append(f"[run] executive report STAGE LOST: {ex!r}")
    for f in failures[:12]:
        log(f"[run]   gate: {f}")
    return {"ok": True, "gate_ok": ok, "open_checks": open_checks,
            "out": str(out_path), "archive": str(archive),
            "served": len(served), "failures": failures,
            "completion": card["completion"].get("_overall_pct"),
            "replay": str(replay_dir)}
