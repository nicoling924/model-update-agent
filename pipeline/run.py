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
from .ledger import Ledger, vintage_ban as _vintage_ban, sourceable as _sourceable
from .orchestrator import ObjectiveLoop
from .stage1_read import read_documents
from .stage2_join import decisions_to_json, join, join_bound_tables
from .stage3_read import read_gaps
from .writer import (Writer, formula_map, load, resolve_input_site,
                     roll_year_headers, rollover_column, save)


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


def _judge_serve(wb, spec_d, target_year, ledger, entry, sheet, row, value, pv, log):
    """THE LINE WITH NO NAME (reviewer 2026-09-17): CXMODEL!AO223 took 59,101
    from a printed row carrying NO LABEL AT ALL, and shipped PLAIN into an
    unbalanced balance sheet. It could, because the name judge skips such a
    serve by construction — `name_mismatches` needs a line to judge, and there
    was none — so nothing in the run ever asked what that row IS.

    Code cannot say what an unlabelled row is; only the brain can, off a card.
    So a serve whose own printed line has no name, and which the brain never
    named, lands RED, unproven and unlocked. The rest of the naming discipline
    stays where it already lives: the walk refuses unkin wide-row and
    small-prior ties as it reads them, and the name judge rules on the
    mismatched ones. Re-judging those here reddened 60 correct CLP serves and
    cost a key — a second court for a case already tried.
    -> (flag, note_suffix) or (None, "")."""
    if entry.get("named") or entry.get("flag"):
        return None, ""            # the brain named it, or it already wears a colour
    line = str(entry.get("line") or "").strip()
    import re as _re
    if line and not _re.match(r"^[\d,.\s()|%+-]+$", line):
        return None, ""            # the line has a name; the walk and the name judge own it
    return "red", (" [the printed line this came from carries NO NAME — a number on an unlabelled "
                   "row. Code cannot say what such a row is; please confirm the item]")


def _write_served(wb, spec_d, target_year, served, writer, priors, log, ledger=None):
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
        s_pv = wb[s_sheet][f"{s_pcol}{s_row}"].value if s_pcol else None
        j_flag, j_why = _judge_serve(wb, spec_d, target_year, ledger, entry,
                                     s_sheet, s_row, value, s_pv, log)
        flag = entry.get("flag") or j_flag
        conf = int(entry.get("conf") or 0)
        if j_flag == "red":
            # THE NAME IS IN DOUBT, NOT THE MAGNITUDE (the first cut lowered conf
            # here, which also turned OFF `trusted` — the world band then refused
            # the write outright and DFE lost a 153.50 serve, two keys with it).
            # The tie still proves the number belongs in this world; what nobody
            # has established is what the row IS. So it lands, red and unproven,
            # and the analyst decides — a flagged figure beats a silent hole.
            entry["flag"], entry["conf"] = "red", min(conf, 3)
            entry["note"] = (entry.get("note") or "") + j_why
        ok = writer.write(
            s_sheet, f"{s_tcol}{s_row}", value,
            prior_coord=f"{s_pcol}{s_row}" if s_pcol else None,
            note=entry.get("note"), flag=flag, trusted=conf >= 4)
        if ok:
            n_written += 1
            entry["homed"] = True
            entry["home"] = (s_sheet, f"{s_tcol}{s_row}")
            if int(entry.get("conf") or 0) >= 5 and j_flag != "red":
                writer.lock(s_sheet, f"{s_tcol}{s_row}")
    log(f"[run] wrote {n_written} served values "
        f"({n_redirect} redirected to input sites, {n_skip} derived/skipped)")


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
    # THE STRUCTURE TURN (owner 2026-09-17): a model whose spec is absent or
    # thin gets ONE brain turn BEFORE the card queue — what a row IS is a
    # reading, and until it is read, balance is not measured at all.
    from .anatomy import read as _read_anatomy, wanted as _anatomy_wanted
    if _anatomy_wanted(spec_d):
        try:
            _read_anatomy(wb, spec_d, client, target_year, log, period=str(period),
                          values_wb=wb_values)
        except Exception as _e_an:     # noqa: BLE001
            log(f"[anatomy] STAGE LOST: the structure turn crashed ({_e_an!r}) — "
                "the deterministic discovery stands")
            run_log.append(f"[anatomy] STAGE LOST: the structure turn crashed ({_e_an!r})")
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
                # the restored prior is unconfirmed: RED, plain note — through
                # the gate: unlocked, un-served, journaled
                wb[sh][coord] = prev
                writer.revert(sh, coord, old, "red", "Not confirmed in the documents. Kept last period's figure — please check.")
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
            if f"{sh}!{coord}" in (writer.log.get("rulings") or {}):
                # the brain ruled on this cell (a sense-check pick): code notes the
                # consequence, it does not overturn the ruling (owner 2026-09-15)
                writer.watch(sh, coord, "the brain's own pick; the forecast row it feeds moved with it — your call")
                continue
            wb[sh][coord] = old
            now = collapsed_forecasts(wb, spec_d, target_year, fc_base)
            if len(now) < len(cur):
                log(f"[run]   collapse guard [{stage}]: REVERTED "
                    f"{sh}!{coord} (zero -> restored {str(old)[:22]!r}) — "
                    "the zero killed a healthy forecast row "
                    "(auto-disproven)")
                wb[sh][coord] = prev
                writer.revert(sh, coord, old, "red", "Not confirmed in the documents. Kept last period's figure — please check.")
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
    writer = Writer(wb)          # the one writer of the run (the restatement below writes through it)
    if _restate:
        # RESTATE (owner 2026-09-15, only when asked): the prior column is first
        # mapped to this year's restated comparatives through last year's names;
        # this year's figures then map against the restated priors
        try:
            from .restate import restate_prior_column
            restate_prior_column(wb, wb_values, spec_d, target_year, ledger, {t.key: t for t in targets}, writer, log, period=period)
            known = targets_mod.known_prior_values(targets)
        except Exception as _e_rs:
            log(f"[run] restate STAGE LOST: {_e_rs!r}")
            run_log.append(f"[run] restate STAGE LOST: {_e_rs!r}")

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
    # THE NAME JUDGMENT (owner 2026-09-15): every tie whose printed name is
    # not kin to the model row goes to the brain before it lands
    try:
        from .naming import judge_names as _judge_names
        _judge_names(client, wb, spec_d, ledger, served, {t.key: t for t in targets}, writer, log, target_year=target_year)
    except Exception as _e_nm:
        log(f"[names] STAGE LOST: name judgment crashed ({_e_nm!r})")
        run_log.append(f"[names] STAGE LOST: name judgment crashed ({_e_nm!r})")
    _write_served(wb, spec_d, target_year, served, writer, prior_map, log, ledger)

    # -- ROLL-FORWARD SCHEDULES (owner 2026-09-10): the vertical prior tie —
    # a movement table's opening row is last year's closing; the model's
    # schedule blocks and the analyst's carried literals are served from
    # this year's table, roles settled by the model's own prior-year values
    if True:
        try:
            from .schedules import serve_schedules as _serve_schedules
            _n_sched = _serve_schedules(wb, spec_d, target_year, ledger, served, writer, log)
            if _n_sched:
                log(f"[run] schedules: {_n_sched} cells served by the vertical tie")
                err_guard("schedules")
        except Exception as _e_sched:
            log(f"[run] schedules skipped: {_e_sched!r}")

    # -- THE READER FIRST (CLP 2026-09-08: stage 3 read 168 rows from page
    # images in 31 silent minutes while the reader stage covered three
    # documents in 58 seconds from text): the whole-document text read
    # goes first; the per-region image read then takes only what it left
    if client is not None:
        try:
            from .reader import brain_read as _brain_read_early
            _n_read0 = _brain_read_early(client, company_dir, period, target_year, wb, spec_d,
                                         {t.key: t for t in targets}, ledger, served, writer, log)
            if _n_read0:
                err_guard("reader")
        except Exception as _e_read0:
            log(f"[read] reader stage skipped: {_e_read0!r}")
    # -- Stage 3 (LLM, checksummed) — only what Stage 2 and the reader left
    if client is not None:
        gap_served = read_gaps(ledger, targets, served, client, docs, run_log)
        served.update(gap_served)
        try:
            from .naming import judge_names as _judge_names2
            _judge_names2(client, wb, spec_d, ledger, served, {t.key: t for t in targets}, writer, log, target_year=target_year)
            # a doubt on a cell ALREADY written (the schedules, the reader) is painted now;
            # the gap serves below carry their doubt into the write itself
            for _k, _e in list(served.items()):
                if _k in gap_served or not isinstance(_e, dict) or _e.get("flag") != "red" or "NAME DOUBTED" not in str(_e.get("note") or ""):
                    continue
                _tc = year_columns(spec_d, _k[0]).get(str(target_year)) if _k[0] in wb.sheetnames else None
                if _tc and wb[_k[0]][f"{_tc}{_k[1]}"].value not in (None, ""):
                    writer.flag_ref(f"{_k[0]}!{_tc}{_k[1]}", "red", _e.get("note"))
        except Exception as _e_nm2:
            log(f"[names] STAGE LOST: name judgment crashed ({_e_nm2!r})")
            run_log.append(f"[names] STAGE LOST: name judgment crashed ({_e_nm2!r})")
        _write_served(wb, spec_d, target_year, gap_served, writer, prior_map, log, ledger)
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
            writer.flag_ref(f"{sheet}!{tcol}{r}", "red",
                "STALE INPUT: rolled from the prior actual column; no proven "
                "disclosure read replaced it — review or accept.")
            n_stale += 1
    if n_stale:
        log(f"[run] {n_stale} unserved hardcode inputs flagged STALE (red)")

    # -- THE COMPOSITE-CONSTANTS LAW (owner ruling 2026-08-31): formulas
    # still embedding last year's literals (=4976+23) are rewritten from
    # their own disclosed comparatives — the run-51 silent-carry class,
    # rebuilt as a proof-gated law (see composites.py).
    from .composites import sweep as composites_sweep
    n_cw, n_cr = composites_sweep(wb, spec_d, target_year, ledger, writer,
                                  log, check_rows=spec_d.get("check_rows"), served=served)
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
    # THE READER STAGE (owner 2026-09-09, the reading test): before any
    # row is held at growth, the brain reads the whole disclosure in one
    # view and answers every row the deterministic stages left unproven;
    # code verifies each answer against a printed number (tie, units,
    # sign, one home) and writes only what it can prove — plain when the
    # comparative ties the prior, red with its citation otherwise.
    # (the reader ran before stage 3 — see THE READER FIRST above; a second
    # pass here would re-send the documents for rows the sweeps just held)
    _n_read = 0
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
            if (sheet, r) in served:
                continue                     # a SERVED row is never a stale input,
                                             # whatever its flag (two readings, big
                                             # move): holding it at growth threw away
                                             # 21 proven reads on the fence-free floor
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
            from .checks import year_columns as _yc_nil
            _p2c = _yc_nil(spec_d, sheet).get(str(target_year - 2))
            _p2 = wb[sheet][f"{_p2c}{r}"].value if _p2c else None
            it = (nil_current_zero(ledger.items, pv, face_pages, banned_docs,
                                   row_label=lab, prior2=_p2)
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
                writer.flag(sheet, f"{tcol}{r}", None)          # the flag cleared through the gate
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
    # A LINE NEW THIS YEAR (owner 2026-09-08, run 254: 'other cash received
    # relating to investing' printed 19,078,348 with '不适用' last year;
    # the model row had no prior, so nothing tied and the cash check was
    # 19 off): no number to tie, so the LABEL is the proof — the printed
    # line's label IS the row's label, it carries one number, and its
    # comparative is blank — served red for the analyst. Any page.
    from .numerics import norm_label as _nl_new
    _scales_new = ratify_page_scales(
        ledger.items, [t.prior_value for t in targets
                       if isinstance(t.prior_value, (int, float))])
    n_new = 0
    from .writegate import _ties_full_precision as _tfp_new
    _all_priors = [abs(float(t.prior_value)) for t in targets
                   if isinstance(getattr(t, "prior_value", None), (int, float))
                   and abs(t.prior_value) >= 0.5]
    for t in targets:
        if isinstance(getattr(t, "prior_value", None), (int, float)):
            continue
        sh_n, r_n = t.sheet, int(t.row)
        tcol_n = year_columns(spec_d, sh_n).get(str(target_year)) if sh_n in wb.sheetnames else None
        if not tcol_n or wb[sh_n][f"{tcol_n}{r_n}"].value not in (None, ""):
            continue
        _strip = lambda x: re.sub(r"[（(][^（）()]{1,12}[）)]", "", _nl_new(str(x or ""))).replace(" ", "")
        rl = _strip(t.label)
        # the label must NAME an item: 'Note', 'Total', 'Other' name nothing
        # (CLP floor 2026-09-09: a 'Note:' memo row took 25 from a '(Note' line)
        _cjk = sum(1 for ch in rl if "一" <= ch <= "鿿")
        if len(rl) < 4 or re.fullmatch(r"(note|notes|total|subtotal|other|others|合计|小计|总计|其他|其中)", rl, re.IGNORECASE) \
                or (_cjk < 3 and len(str(t.label).split()) < 2):
            continue
        reads = {}
        for it in ledger.items:
            if not _sourceable(it) or getattr(it, "channel", "") == "prose":
                continue
            if _strip(it.label) != rl:
                continue
            nums = [n for n in (it.nums or []) if isinstance(n, (int, float))]
            if len(nums) == 2 and nums[1] == 0:
                nums = [nums[0]]
            if len(nums) != 1:
                continue
            sc = _scales_new.get((it.doc, it.page))
            if not sc:
                continue
            v = nums[0] / sc
            # the one number may be LAST year's (the bond line, relabelled,
            # printed 593.54 beside a blank): if it ties any model prior it
            # is a comparative, not a new line — the nil law's territory
            if any(_tfp_new(abs(v), pv_) for pv_ in _all_priors):
                continue
            reads.setdefault(round(v, 2), (v, it))
        if len(reads) != 1:
            continue
        v, it = next(iter(reads.values()))
        pcol_n = prior_column(spec_d, sh_n, target_year)
        if writer.write(sh_n, f"{tcol_n}{r_n}", float(v),
                        prior_coord=f"{pcol_n}{r_n}" if pcol_n else None,
                        flag="red", allow_empty=True,
                        note=(f"New line this year (blank last year). Label matches the "
                              f"statement ({it.doc} p{it.page}). Please confirm.")):
            served[(sh_n, r_n)] = {"value": float(v), "status": "OK", "doc": it.doc,
                                   "page": it.page, "line": str(it.label)[:60],
                                   "conf": 3, "note": "new line: exact label, blank prior"}
            n_new += 1
            log(f"[run]   new line: {sh_n}!{tcol_n}{r_n} = {v:,.2f} ({it.doc} p{it.page} "
                f"{str(it.label)[:30]!r}) — blank last year, label matches")
    if n_new:
        log(f"[run] new-line sweep: {n_new} rows new this year served (red, exact label)")
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
        frozen_lines += apply_freezes(wb, plans, writer=writer)
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
            f"before stage 4 ({', '.join(sorted(keys_before))})")
    import os as _os
    mode = (stage4_mode or _os.environ.get("STAGE4_MODE") or "queue").strip()
    loop_summary = ""
    loop = ObjectiveLoop(wb, spec_d, target_year, ledger, targets, served,
                         writer, client, run_log, budget=loop_budget)
    loop.load_bearing = lb           # tier law: the loop sees the wiring
    loop.key_panel = _key_panel      # the proven prints of the key rows (derivations solve against them)
    loop.period = period
    loop.brain = client is not None or stage4_answerer is not None
    if client is not None or stage4_answerer is not None:
        loop.brain = client is not None or stage4_answerer is not None

        def _ask(text, options, default):
            """The brain picks (owner 2026-09-14: 'brain picks the rung, code verifies'); a replay's answerer stands in.
            Both paths leave the same trace: last_why (a derive:via names its cells there) and last_ask_error."""
            loop.last_why, loop.last_ask_error = "", None
            if stage4_answerer is not None:
                _r = stage4_answerer(text, options, default)
                if isinstance(_r, tuple):
                    _r, loop.last_why = _r[0], str(_r[1] or "")
                return _r
            if client is None:
                loop.last_ask_error = "no brain in this run"
                return default
            try:
                from .workqueue import _llm_answer
                _ans, _why = _llm_answer(loop, client, text, options, log)
                loop.last_why = _why
                return _ans
            except Exception as _e_ask:
                loop.last_ask_error = repr(_e_ask)
                log(f"[sense] the brain could not answer a card: {_e_ask!r}")
                return default
        loop.ask = _ask
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
            # THE SENSE CHECK'S CHECKPOINT (owner 2026-09-09): the headline
            # lines against the analyst's pre-update model — a forecast that
            # moved out of line with the actual sends its inputs to the front
            try:
                from .sensecheck import checkpoint as _sense_checkpoint
                _pre_wb_sense = load(str(archive))
                _sense_checkpoint(loop, _pre_wb_sense, log)
            except Exception as _e_sc:
                _pre_wb_sense = None
                log(f"[sense] checkpoint STAGE LOST: {_e_sc!r}")
                run_log.append(f"[sense] checkpoint STAGE LOST: {_e_sc!r}")
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
        err_guard("loop")
        collapse_guard("loop")
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
            writer.flag_ref(f"{pm_sh}!{tc_pm}{pm_r}", "red",
                f"PLUG METER: this residual row computed {pm_was:,.1f} "
                f"last year and {pm_now:,.1f} now — the model's own plug "
                "is absorbing something wrong in the inputs that feed "
                "its total. ANALYST REVIEW.")
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
                log, ledger=ledger, panel=_key_panel,
                absorbers=("none" if client is not None else "any"))
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
        _more = _key_snapshot(wb, spec_d, target_year, ledger, _panel_path, panel=_key_panel)
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

    writer.plugs_allowed = True                  # THE PLUG LAW: the repair rounds are the last resort
    from .writer import hold_zero_forecasts as _hold_zero
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
                      ledger=ledger, panel=_key_panel,
                      absorbers=("none" if client is not None else "any"))
        n_rb2 = _rbm2(wb, spec_d, target_year, writer, log, served=served,
                      ask=getattr(loop, "ask", None))
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
            hold_zero=lambda: _hold_zero(writer, (lambda sh_, co_: Evaluator(wb).cell(sh_, co_)), log),
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
    # NOTHING THE RUN SWALLOWED STAYS OFF THE REPORT (the change law, (d)):
    # a stage that was lost, a hold a guard refused, a write refused over the
    # model's own arithmetic — each reaches the analyst's page, not only the log
    for _u in (writer.log.get("unheld_zero") or [])[:12]:
        open_checks.append(f"forecast NOT held at 0: {str(_u)[:110]}")
    for _fr in (writer.log.get("formula_refused") or [])[:12]:
        open_checks.append(f"write refused over the model's own arithmetic: {str(_fr)[:110]}")
    for _sl in run_log:
        if "STAGE LOST" in str(_sl):
            open_checks.append(str(_sl)[:120])
    # AN OBJECTIVE THE MEASURE COULD NOT TAKE IS NOT AN OBJECTIVE THAT HOLDS
    # (reviewer 2026-09-17: on CX the review context died on a SyntaxError and
    # the run went on to say "every objective holds"). Every fault the loop
    # recorded reaches the analyst's page, red.
    for _f in (locals().get("loop").__dict__.get("objective_faults", [])
               if isinstance(locals().get("loop"), object) and hasattr(locals().get("loop"), "__dict__") else [])[:12]:
        open_checks.append(f"objective NOT measured: {str(_f)[:110]}")
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
