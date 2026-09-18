"""The by-hand teachings (owner mandate 2026-09-01: "teach it how you
think"). Six habits of the analyst who finished CLP FY25 by hand,
mechanized as GENERIC laws — every anchor comes from the workbook and
the run's own documents at runtime; nothing is company-shaped.

1. FORECAST INVIOLABILITY lives in run.py (the sign-absurd freeze writer
   is dead; tripwires investigate, causes get fixed in the actual
   column) and in the forecast_diff tool (orchestrator).
2. TWIN RE-ANCHOR (here): a quantity often lives in several homes —
   the BS row and the roll base that feeds the forecasts. After the
   actual column is served, any row whose PRIOR equals a written row's
   prior and which still holds that stale prior is the same quantity's
   other home: hardcode twins re-anchor to the served value (orange,
   traceable), formula twins become tripwires.
3. COLLAPSE GUARD (here): a write must survive its consequences. A
   false zero can be evidence-clean and still delete next year's
   revenue (the run-204 tariff). The first forecast year is evaluated
   at baseline from the analyst's own file; any batch of writes that
   COLLAPSES a healthy forecast row (to ~zero, or sign-flipped large)
   is unwound write-by-write, like the error guard.
4. PLUG METER (here): the model's own residual rows (=total - parts)
   are truth meters — the analyst read the export plug at -1,598 vs a
   prior of -4 and knew the tariff was wrong. A residual row that moves
   wildly is a tripwire pointing at its inputs.
5. COMPOSITE VINTAGE lives in composites.py (literals tying the
   prior-year print are last year's numbers even without the stale
   fingerprint).
6. SEGMENT PRIOR DISCIPLINE lives in the orchestrator's set_input
   (a cited page that does not carry the row's own prior cannot
   produce a clean write).
"""
import re

from .checks import forecast_columns, prior_column, year_columns
from .evaluator import Evaluator
from .numerics import row_tol

TWIN_MIN = 50.0          # priors below this tie coincidences, not twins
TWIN_MAX_HOMES = 4       # a value in 5+ rows is a constant, not a twin


def forecast_baseline(pre_wb, spec, target_year, max_row=300):
    """Evaluate the analyst's own first-forecast column, sheet by sheet.
    -> {(sheet, row): value}. The pre-update model is the definition of
    'healthy' — it balanced before we touched it."""
    ev = Evaluator(pre_wb)
    out = {}
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in pre_wb.sheetnames:
            continue
        fc = forecast_columns(spec, sheet, target_year)
        if not fc:
            continue
        ws = pre_wb[sheet]
        for r in range(1, min(ws.max_row, max_row) + 1):
            v = ws[f"{fc[0]}{r}"].value
            if not (isinstance(v, str) and v.startswith("=")):
                continue
            try:
                got = ev.cell(sheet, f"{fc[0]}{r}")
            except Exception:
                continue
            if isinstance(got, (int, float)):
                out[(sheet, r)] = got
    return out


def collapsed_forecasts(wb, spec, target_year, base, max_row=300):
    """Healthy forecast rows this update KILLED. -> [(sheet, row, now,
    was)] where the analyst's value was substantial and ours is ~zero
    or sign-flipped large."""
    ev = Evaluator(wb)
    out = []
    for (sheet, r), was in base.items():
        if abs(was) < 100:
            continue
        fc = forecast_columns(spec, sheet, target_year)
        if not fc or sheet not in wb.sheetnames:
            continue
        v = wb[sheet][f"{fc[0]}{r}"].value
        if not (isinstance(v, str) and v.startswith("=")):
            continue                      # value cells are others' business
        try:
            now = ev.cell(sheet, f"{fc[0]}{r}")
        except Exception:
            continue                      # errors are the error guard's
        if not isinstance(now, (int, float)):
            continue
        if abs(now) < max(1.0, abs(was) * 0.02) \
                or (now * was < 0 and abs(now) > abs(was) * 0.5):
            out.append((sheet, r, now, was))
    return out


def twin_reanchor(wb, pre_values_wb, spec, target_year, writer, log,
                  min_val=TWIN_MIN):
    """-> (n_rewritten, n_tripwired). For every value the run served
    into the target column, find the OTHER rows that held the same
    prior (the quantity's other homes) and are still stale at it."""
    from collections import defaultdict
    # index: prior value -> rows holding it (from the pre file, evaluated
    # cheaply from raw cells; formulas use their cached value if any)
    homes = defaultdict(list)
    ev = Evaluator(wb)

    def _pval(sheet, pcol, r):
        v = wb[sheet][f"{pcol}{r}"].value
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str) and v.startswith("="):
            try:
                got = ev.cell(sheet, f"{pcol}{r}")
            except Exception:
                return None
            if isinstance(got, (int, float)):
                return got
        return None

    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        pcol = prior_column(spec, sheet, target_year)
        if not pcol:
            continue
        ws = wb[sheet]
        for r in range(1, min(ws.max_row, 300) + 1):
            pv = _pval(sheet, pcol, r)      # priors live behind formulas
            if isinstance(pv, (int, float)) and abs(pv) >= min_val:
                homes[round(pv, 1)].append((sheet, r))
    n_rw = n_tw = 0
    for ref in list(writer.log.get("written", [])):
        sh, _, coord = ref.partition("!")
        m = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
        if not m or sh not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sh).get(str(target_year))
        if m.group(1) != tcol:
            continue
        row = int(m.group(2))
        pcol = prior_column(spec, sh, target_year)
        pv = _pval(sh, pcol, row) if pcol else None
        if not isinstance(pv, (int, float)) or abs(pv) < min_val:
            continue
        served = wb[sh][coord].value
        if isinstance(served, str) and served.startswith("="):
            try:
                served = ev.cell(sh, coord)   # a constants-law REWRITE is
            except Exception:                 # a serve too (run-208: the
                continue                      # NFA twin never fired)
        if not isinstance(served, (int, float)) \
                or abs(served - pv) <= row_tol(pv):
            continue                      # unchanged value teaches nothing
        twins = [t for t in homes.get(round(pv, 1), [])
                 if t != (sh, row)]
        if not twins or len(twins) > TWIN_MAX_HOMES:
            continue
        from .numerics import kinship as _kin
        lab_src = str(wb[sh].cell(row, 1).value or "")
        for (sh2, r2) in twins:
            tc2 = year_columns(spec, sh2).get(str(target_year))
            if not tc2:
                continue
            cell = wb[sh2][f"{tc2}{r2}"]
            cur = cell.value
            # TWINS ARE KIN OR LINKED (run-232 cash autopsy): Australia's
            # amortisation (-425) and a SoC transfer line (-425) shared
            # last year's value by coincidence; the sweep re-anchored the
            # amortisation to the transfer's 386 — undoing the brain's
            # correct revert. Same prior is not same quantity: the labels
            # must be kin, or one formula must reference the other.
            lab_tw = str(wb[sh2].cell(r2, 1).value or "")
            linked = (isinstance(cur, str) and coord in str(cur)) or \
                (isinstance(wb[sh][coord].value, str)
                 and f"{tc2}{r2}" in str(wb[sh][coord].value))
            # labels in DIFFERENT scripts (an English model over a
            # Chinese filing: 'Cash - year end' vs '现金的期末余额') cannot
            # be compared by words — there the prior identity stands
            # when the value is distinctive (large), as it always did
            import re as _re
            cjk = lambda t: bool(_re.search(r"[一-鿿]", t))
            comparable = (cjk(lab_src) == cjk(lab_tw))
            if not linked and lab_src.strip() and lab_tw.strip() \
                    and comparable and not _kin(lab_src, lab_tw):
                log(f"[run]   twin re-anchor: {sh2}!{tc2}{r2} shares the prior "
                    f"{pv:,.1f} with {ref} but is not kin ('{lab_tw[:24]}' vs "
                    f"'{lab_src[:24]}') — a coincidence, left alone")
                continue
            if not linked and not comparable and abs(pv) < 10 * min_val:
                log(f"[run]   twin re-anchor: {sh2}!{tc2}{r2} shares the prior "
                    f"{pv:,.1f} with {ref} across scripts and the value is not "
                    "distinctive enough to prove the same quantity — left alone")
                continue
            # a RED cell is an analyst hold or the brain's revert — never
            # re-anchored by a sweep
            try:
                rgb = str(cell.fill.fgColor.rgb or "")
            except Exception:
                rgb = ""
            if rgb.endswith("FFC7CE"):
                continue
            if isinstance(cur, (int, float)) \
                    and abs(cur - pv) <= row_tol(pv):
                ok = writer.write(
                    sh2, f"{tc2}{r2}", served,
                    prior_coord=f"{prior_column(spec, sh2, target_year)}{r2}",
                    trusted=True, flag="orange",
                    note=(f"TWIN RE-ANCHOR: this row's prior ({pv:,.1f}) "
                          f"is the same quantity as {ref} (both held it "
                          f"last year); {ref} was served {served:,.1f} and "
                          "this home was still stale. Same evidence, "
                          "re-anchored."))
                if ok:
                    n_rw += 1
                    log(f"[run]   twin re-anchor: {sh2}!{tc2}{r2} "
                        f"{pv:,.1f} -> {served:,.1f} (twin of {ref})")
            elif isinstance(cur, str) and cur.startswith("="):
                try:
                    cv = ev.cell(sh2, f"{tc2}{r2}")
                except Exception:
                    continue
                if isinstance(cv, (int, float)) \
                        and abs(cv - pv) <= row_tol(pv):
                    # THE TWIN BACK-OUT (owner's back-out rule, taught):
                    # the twin's own inputs are often unprovable
                    # composites (gross PPE / accum dep) — anchor the
                    # twin's NET to the served sibling with a VISIBLE
                    # back-out formula (=176128-AI71), components
                    # awaiting true-up. Only for simple 1-3 ref
                    # same-column compositions.
                    refs = re.findall(r"(?<![A-Za-z0-9_!])"
                                      + tc2 + r"(\d{1,5})",
                                      str(cur).replace("$", ""))
                    if 2 <= len(refs) <= 3 and "!" not in str(cur):
                        vals = []
                        for rr in refs:
                            try:
                                vals.append((abs(ev.cell(sh2,
                                            f"{tc2}{rr}")), rr))
                            except Exception:
                                vals.append((0.0, rr))
                        _big, big_r = max(vals)
                        others = [rr for rr in refs if rr != big_r]
                        bo = (f"=({served:.6g})-("
                              + "-".join(f"{tc2}{rr}" for rr in others)
                              + ")") if others else f"={served:.6g}"
                        # rewrite the LARGEST component so the twin's
                        # net equals the served sibling
                        ok2 = writer.write(
                            sh2, f"{tc2}{big_r}",
                            bo.replace("-(-", "-(0-").replace("-()", ""),
                            prior_coord=None, trusted=True, flag="orange",
                            note=(f"TWIN BACK-OUT: {sh2}!{tc2}{r2} must "
                                  f"equal {ref}'s served {served:,.1f} "
                                  "(same prior = same quantity); this "
                                  "component is backed out so the net "
                                  "ties — split awaiting true-up from "
                                  "the detailed report."))
                        if ok2:
                            n_rw += 1
                            log(f"[run]   twin back-out: {sh2}!{tc2}"
                                f"{big_r} anchored so {sh2}!{tc2}{r2} "
                                f"= {served:,.1f} (twin of {ref})")
                            continue
                    from openpyxl.comments import Comment
                    writer.flag_ref(f"{sh2}!{tc2}{r2}", "red",
                        f"STALE TWIN: evaluates to last year's {pv:,.1f} "
                        f"but {ref} (the same quantity's other home) was "
                        f"served {served:,.1f}. This roll/base must be "
                        "re-anchored — the run-204 NFA lesson: a stale "
                        "twin base breaks every forecast year.")
                    n_tw += 1
                    log(f"[run]   twin tripwire: {sh2}!{tc2}{r2} still "
                        f"evaluates the stale {pv:,.1f} (twin of {ref})")
    return n_rw, n_tw


def plug_meter(wb, spec, target_year, max_row=300):
    """The model's own residual rows, read as truth meters.
    -> [(sheet, row, now, prior)] for residual-pattern rows that moved
    wildly. A residual formula subtracts same-column siblings
    (=A-B-C..., =X-SUM(...)) — when it explodes vs its prior, an input
    feeding its total is probably wrong (the export-plug lesson)."""
    pat = re.compile(r"^=\+?[A-Z]{1,3}\d+\s*-")
    ev = Evaluator(wb)
    out = []
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        pcol = prior_column(spec, sheet, target_year)
        if not tcol or not pcol:
            continue
        ws = wb[sheet]
        for r in range(1, min(ws.max_row, max_row) + 1):
            f = ws[f"{tcol}{r}"].value
            if not (isinstance(f, str) and pat.match(f.replace(" ", ""))):
                continue
            if f.count("-") < 1 or "!" in f.split("-")[0]:
                pass
            try:
                now = ev.cell(sheet, f"{tcol}{r}")
                was = ev.cell(sheet, f"{pcol}{r}")
            except Exception:
                continue
            if not (isinstance(now, (int, float))
                    and isinstance(was, (int, float))):
                continue
            # wild = the plug moved far beyond its own history AND is
            # material against the total it is the residual of (owner
            # 2026-09-14, CLP Driver!112: 45 -> 349 on a -1,666 total is
            # wild — 21% of the total after 2% every year; the export
            # plug -185 on 48,967 of sales after the fix is 0.4%: quiet).
            # No absolute floor — units differ by model.
            total_now = None
            try:
                m_tot = re.match(r"^=\+?((?:'[^']+'!|[A-Za-z0-9_]+!)?[A-Z]{1,3}\d+)", f.replace(" ", "").replace("$", ""))
                if m_tot:
                    ref_t = m_tot.group(1)
                    sh_t, c_t = (ref_t.rsplit("!", 1) if "!" in ref_t else (sheet, ref_t))
                    total_now = ev.cell(sh_t.strip("'"), c_t)
            except Exception:
                total_now = None
            beyond_history = abs(now - was) > 4 * max(abs(was), 1.0)
            material = (isinstance(total_now, (int, float)) and abs(total_now) >= 1
                        and abs(now) >= 0.01 * abs(total_now))
            if beyond_history and material:
                out.append((sheet, r, now, was))
    return out


def oneoff_no_propagate(wb, spec, target_year, writer, log):
    """THE ONE-OFF NO-PROPAGATE LAW (roll-forward checklist; the
    sanctioned narrow forecast edit under the mindmap's integrity
    clause). A forecast cell that is a BARE LINK to the actual column
    (=AI107), on a row whose prior year was ~nil while the actual is
    material, drags a NEW one-off item into every forecast year — the
    run-204/206 hedging cost leaked +352 of imbalance per year. The
    link is replaced with 0 (orange, formula in the note) — the one
    forecast edit the owner's law sanctions, because it restores the
    analyst's intent (the row forecast nil before the one-off existed).
    -> count."""
    from openpyxl.comments import Comment
    n = 0
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        pcol = prior_column(spec, sheet, target_year)
        fcs = forecast_columns(spec, sheet, target_year)
        if not tcol or not pcol or not fcs:
            continue
        ws = wb[sheet]
        ev = Evaluator(wb)
        for r in range(1, min(ws.max_row, 300) + 1):
            av = ws[f"{tcol}{r}"].value
            if not (isinstance(av, (int, float)) and abs(av) >= 50):
                continue
            try:
                pv = ev.cell(sheet, f"{pcol}{r}")
            except Exception:
                continue
            if not (isinstance(pv, (int, float)) and abs(pv) < 1):
                continue                  # not a NEW one-off
            for fc in fcs:
                f = ws[f"{fc}{r}"].value
                if isinstance(f, str) and re.match(
                        r"^=\s*\+?\s*" + tcol + str(r) + r"\s*$",
                        f.replace("$", "")):
                    if not writer.write(ws.title, f"{fc}{r}", 0, trusted=True, force_lock=True, flag="blue"):
                        continue                                        # through the writer (2026-09-14)
                    ws[f"{fc}{r}"].comment = Comment(
                        f"ONE-OFF NOT PROPAGATED: the actual {av:,.1f} "
                        f"is new this year (prior ~0); this cell linked "
                        f"it into the forecast ({f}). Set to 0 per the "
                        "roll-forward law; restore the link if the item "
                        "recurs.", "Model Update Agent")
                    writer.log["flags"].append(f"{sheet}!{fc}{r}")
                    # the gate's driver-roll check exempts FROZEN cells;
                    # a one-off held at 0 is one (run 257: the law fired and
                    # the gate refused its own sanctioned action)
                    writer.log.setdefault("frozen", []).append(
                        f"{sheet}!{fc}{r}: one-off not propagated (actual {av:,.1f}, prior ~0)")
                    n += 1
                    log(f"[run]   one-off law: {sheet}!{fc}{r} link to "
                        f"{tcol}{r} ({av:,.1f}, prior ~0) -> 0 (orange)")
    return n


def auto_probe_holds(wb, spec, target_year, fc_base, writer, log,
                     max_probes=24):
    """THE MECHANIZED BISECT (owner ruling 2026-09-01: hypothesis ->
    experiment -> proof -> sanctioned hold). For every first-forecast
    cell that is a bare link into the actual column and now computes
    away from the ANALYST'S OWN BASELINE (their pre-update forecast =
    their intent), probe holding it at the baseline value; keep the
    hold only when the model's total check residual PROVABLY drops.
    Transactional, orange, reported — the code-driven twin of the
    loop's hold_forecast. -> holds applied."""
    from openpyxl.comments import Comment
    from .checks import year_columns as _yc

    def _mass():
        m = 0.0
        for c in (spec.get("check_rows") or []):
            for y, ycol in _yc(spec, c["sheet"]).items():
                try:
                    v = Evaluator(wb).cell(c["sheet"],
                                           f"{ycol}{int(c['row'])}")
                except Exception:
                    continue
                if isinstance(v, (int, float)):
                    m += abs(v)
        return m

    mass = _mass()
    if mass <= 5:
        return 0
    cands = []
    from .forecast_balance import cf_start_row
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        fcs = forecast_columns(spec, sheet, target_year)
        if not tcol or not fcs:
            continue
        ws = wb[sheet]
        cf0 = cf_start_row(ws)
        if cf0 is None:
            continue      # FLOW rows only: holding a BS carry row
                          # "improves" checks by minting a fake
                          # working-capital flow — a plug in disguise
                          # (measured on run-208: AJ63/AJ88/AJ91 all
                          # "helped" compensatingly)
        ev = Evaluator(wb)
        for r in range(cf0 + 1, min(ws.max_row, 300) + 1):
            f = ws[f"{fcs[0]}{r}"].value
            if not (isinstance(f, str) and re.match(
                    r"^=\s*\+?\s*" + tcol + str(r) + r"\s*$",
                    f.replace("$", ""))):
                continue                  # bare link to the actual only
            base_v = fc_base.get((sheet, r))
            if base_v is None:
                base_v = 0.0
            try:
                now = ev.cell(sheet, f"{fcs[0]}{r}")
            except Exception:
                continue
            if not isinstance(now, (int, float)) \
                    or abs(now - base_v) < 50:
                continue                  # the roll changed nothing real
            cands.append((abs(now - base_v), sheet, r, fcs[0], base_v, f))
    n = 0
    for _d, sheet, r, fc1, base_v, old_f in sorted(cands,
                                                   reverse=True)[:max_probes]:
        cell = wb[sheet][f"{fc1}{r}"]
        cell.value = round(base_v, 6)
        m2 = _mass()
        # PROOF = the hold repaired more than its own one-year size
        # (it was compounding through the years) — a hold that merely
        # shuffles the imbalance moves the mass less than itself
        if m2 <= mass - max(100.0, 1.5 * _d):
            cell.value = old_f                 # probe over: the hold lands through the gate
            if not writer.write(sheet, f"{fc1}{r}", round(base_v, 6), trusted=True, force_lock=True, flag="blue",
                                note=(f"AUTO-PROBE HOLD: this forecast is a bare link to the "
                                      f"actual column; the analyst's own pre-update forecast "
                                      f"here was {base_v:,.1f} (their intent). Holding it "
                                      f"there cut the model's total check residual "
                                      f"{mass:,.1f} -> {m2:,.1f} — probe-proven roll "
                                      f"artifact (was {old_f}). Owner's law: balance "
                                      "outranks the freeze list.")):
                continue
            writer.log.setdefault("frozen", []).append(
                f"{sheet}!{fc1}{r}: held at {base_v:g} — was {old_f} "
                "(auto-probe, proven)")
            writer.log.setdefault("verdicts", []).append(
                f"{sheet}!{fc1}{r}: ERROR_FIXED — probe-proven roll "
                f"artifact held at the analyst's baseline {base_v:g}; "
                f"residual {mass:,.1f} -> {m2:,.1f}")
            log(f"[run]   auto-probe: {sheet}!{fc1}{r} held at "
                f"{base_v:g} (was {old_f}) — residual {mass:,.1f} -> "
                f"{m2:,.1f}")
            mass = m2
            n += 1
        else:
            cell.value = old_f            # experiment failed: restore
    return n


def tune_holds(wb, spec, target_year, writer, log):
    """THE HOLD TUNER (owner regression ruling 2026-09-01): when, after
    every repair stage, the forecast years of a check all fail by the
    SAME small constant, an auto-probe hold is off by exactly that
    constant — one more experiment (±constant on each held cell, kept
    only if every forecast year then ties) closes all years at once.
    Measure, never assume. -> tunes applied."""
    from .checks import forecast_columns, year_columns as _yc

    def _fc_resids():
        out = []
        ev = Evaluator(wb)
        for c in (spec.get("check_rows") or []):
            sh, r = c.get("sheet"), int(c.get("row"))
            if sh not in wb.sheetnames:
                continue
            for col in forecast_columns(spec, sh, int(target_year)):
                try:
                    v = ev.cell(sh, f"{col}{r}")
                except Exception:
                    continue
                if isinstance(v, (int, float)):
                    out.append(v)
        return out

    held_refs = []
    for entry in writer.log.get("frozen", []):
        m = re.match(r"^([^!]+)!([A-Z]{1,3})(\d+): held", str(entry))
        if m:
            held_refs.append((m.group(1), m.group(2), int(m.group(3))))
    if not held_refs:
        return 0
    resids = _fc_resids()
    live = [v for v in resids if abs(v) > 1.0]
    if not live or max(live) - min(live) > 2.0 or abs(live[0]) > 5000:
        return 0
    const = live[0]
    n = 0
    for sheet, col, row in held_refs:
        cell = wb[sheet][f"{col}{row}"]
        if not isinstance(cell.value, (int, float)):
            continue
        old = cell.value
        for sgn in (1, -1):
            cell.value = round(old + sgn * const, 6)
            after = [v for v in _fc_resids() if abs(v) > 1.0]
            if not after:
                tuned = cell.value
                cell.value = old               # probe over: the tune lands through the gate
                prev_note = str(cell.comment.text)[:280] if cell.comment is not None else ""
                if not writer.write(sheet, f"{col}{row}", tuned, trusted=True, force_lock=True, flag="blue",
                                    note=(prev_note + f" | HOLD TUNED by {sgn * const:+,.1f}: the flat "
                                          "forecast residual proved the held value off by "
                                          "this constant; all forecast years now tie.")):
                    break
                log(f"[run] hold tuner: {sheet}!{col}{row} "
                    f"{old:g} -> {cell.value:g} — flat forecast residual "
                    f"{const:+,.1f} closed in every year")
                n += 1
                break
            cell.value = old
        if n:
            break
    return n


def _fc_resids_of(wb, spec, target_year):
    out = []
    ev = Evaluator(wb)
    for c in (spec.get("check_rows") or []):
        sh, r = c.get("sheet"), int(c.get("row"))
        if sh not in wb.sheetnames:
            continue
        for col in forecast_columns(spec, sh, int(target_year)):
            try:
                v = ev.cell(sh, f"{col}{r}")
            except Exception:
                continue
            if isinstance(v, (int, float)):
                out.append(v)
    return out


def _ask_site(ask, card, options, log, ref):
    """One card to the brain, its answer said in the log. No answer, or an
    ask that fails (said out loud, never swallowed), leaves code's own
    ranking exactly as it was."""
    try:
        pick = ask(card, options, "site:code")
    except Exception as ex:  # noqa: BLE001
        log(f"[queue] PLUG {ref}: the brain could not answer ({type(ex).__name__}: {str(ex)[:80]}) "
            "— code's own ranking stands")
        return "site:code"
    log(f"[queue] PLUG {ref} -> {pick}")
    return pick if pick in options else "site:code"


def roll_base_mismatches(wb, spec, target_year, writer, log, tol_base=2.0,
                         served=None, ask=None):
    """THE ROLL-BASE CONSISTENCY LAW (owner ruling 2026-09-01, the flat-
    forecast-gap autopsy — and the mechanization of the standing
    checklist line "roll-forward bases re-anchored to actual closings").

    A quantity often has TWO homes at the anchor year: the actual
    column's typed value (marked to disclosure) and the cells the
    FORECAST formula rolls from. The model only works if they agree —
    a correct hardcode over a stale roll base balances the actual year
    while every forecast year is born broken by a constant.

    The test is the model's own arithmetic: point the first-forecast
    formula back one year (Excel copy-paste semantics) and evaluate.
    If it does not reproduce the typed actual, the roll base is stale:
    red-flag the base's stale INPUT cells (they join the work queue as
    load-bearing) and report the row. Generic — no labels, no sheets,
    no companies. -> mismatches found."""
    from .writer import shift_formula_excel
    from openpyxl.comments import Comment
    from openpyxl.styles import PatternFill
    ev = Evaluator(wb)
    n = 0
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        fcs = forecast_columns(spec, sheet, target_year)
        if not tcol or not fcs:
            continue
        from openpyxl.utils import column_index_from_string
        offset = column_index_from_string(tcol) \
            - column_index_from_string(fcs[0])
        ws = wb[sheet]
        for r in range(1, min(ws.max_row, 300) + 1):
            h = ws[f"{tcol}{r}"].value
            f = ws[f"{fcs[0]}{r}"].value
            if not isinstance(h, (int, float)) or abs(h) < 50:
                continue
            if not (isinstance(f, str) and f.startswith("=")):
                continue
            refs = re.findall(r"[A-Z]{1,3}\d+", f.replace("$", ""))
            if not refs or f"{tcol}{r}" in refs:
                continue          # forecast reads the actual: consistent
            # the one-offset shift is only valid when every referenced
            # sheet shares this sheet's year axis
            axis_ok = True
            for ms in re.finditer(r"(?:'([^']+)'|([A-Za-z0-9_]"
                                  r"[A-Za-z0-9 _]*))!", f):
                sh2 = (ms.group(1) or ms.group(2)).strip()
                if sh2 in wb.sheetnames and (
                        year_columns(spec, sh2).get(str(target_year))
                        != tcol
                        or forecast_columns(spec, sh2, target_year)[:1]
                        != fcs[:1]):
                    axis_ok = False
                    break
            if not axis_ok:
                continue
            shifted = shift_formula_excel(f, offset)
            try:
                got = ev.cell_formula(sheet, shifted) \
                    if hasattr(ev, "cell_formula") else None
            except Exception:
                got = None
            if got is None:
                # evaluate via a scratch cell, then restore
                scratch = f"ZZ{r}"
                old = ws[scratch].value
                ws[scratch] = shifted
                try:
                    got = Evaluator(wb).cell(sheet, scratch)
                except Exception:
                    got = None
                ws[scratch] = old
            if not isinstance(got, (int, float)):
                continue
            gap = got - h
            if abs(gap) <= max(tol_base, abs(h) * 5e-3):
                continue
            n += 1
            # the forecast cell is never painted (owner 2026-09-07: "the
            # formula is correct — why is it red?"): the row goes on the
            # watch list; the cause is flagged in the actual column below
            cell = ws[f"{fcs[0]}{r}"]
            writer.watch(sheet, f"{fcs[0]}{r}",
                         f"rolls {got:,.0f} from its inputs vs the typed "
                         f"actual {h:,.0f} (gap {gap:+,.0f})")
            # the base's stale inputs join the red queue, load-bearing
            for m in re.finditer(
                    r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?"
                    r"([A-Z]{1,3})(\d+)", shifted.replace("$", "")):
                sh2 = (m.group(1) or m.group(2) or sheet).strip()
                if sh2 not in wb.sheetnames:
                    continue
                c2, r2 = m.group(3), int(m.group(4))
                v2 = wb[sh2][f"{c2}{r2}"].value
                pcol2 = prior_column(spec, sh2, target_year)
                if not pcol2 or c2 != year_columns(
                        spec, sh2).get(str(target_year)):
                    continue
                pv2 = wb[sh2][f"{pcol2}{r2}"].value
                if isinstance(v2, (int, float)) \
                        and isinstance(pv2, (int, float)) \
                        and abs(v2 - pv2) <= row_tol(pv2) \
                        and f"{sh2}!{c2}{r2}" not in writer.log["flags"]:
                    writer.flag_ref(f"{sh2}!{c2}{r2}", "red",
                        (f"STALE ROLL BASE: still holds last year's "
                         f"{pv2:,.1f} while the {sheet}!{r} roll it feeds "
                         f"misses its typed actual by {gap:+,.1f}."))
            # THE INPUT BACK-OUT (owner ruling 2026-09-07): THE STRUCTURE
            # IS THE MODEL'S. A formula cell is never overwritten to close
            # a roll gap — the fix is always an INPUT of that formula.
            # The roll's leaf inputs (typed cells in the actual column)
            # are ranked by confidence; the LEAST confident one is backed
            # out, as a traceable formula, so the roll reproduces the
            # typed actual ("3 inputs, 2 confident -> back out the 3rd").
            # A tie at the bottom is flagged, never guessed; all-proven is
            # a definition question for the analyst. Solvability is tested
            # by perturbation (bump 1.0; only a unit-linear response
            # solves exactly), never assumed.
            leaves = []
            seen_leaf = set()

            def _walk(sh2, c2, r2, depth=0):
                if depth > 6 or (sh2, c2, r2) in seen_leaf:
                    return
                seen_leaf.add((sh2, c2, r2))
                if sh2 not in wb.sheetnames:
                    return
                v2 = wb[sh2][f"{c2}{r2}"].value
                if isinstance(v2, str) and v2.startswith("="):
                    for m2 in re.finditer(
                            r"(?:(?:'([^']+)'|([A-Za-z0-9_]"
                            r"[A-Za-z0-9 _]*))!)?([A-Z]{1,3})(\d+)",
                            v2.replace("$", "")):
                        _walk((m2.group(1) or m2.group(2) or sh2).strip(),
                              m2.group(3), int(m2.group(4)), depth + 1)
                    return
                if c2 != year_columns(spec, sh2).get(str(target_year)):
                    return
                if not isinstance(v2, (int, float)):
                    return
                pcol2 = prior_column(spec, sh2, target_year)
                pv2 = wb[sh2][f"{pcol2}{r2}"].value if pcol2 else None
                leaves.append((sh2, c2, r2, v2, pv2))

            for m in re.finditer(
                    r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?"
                    r"([A-Z]{1,3})(\d+)", shifted.replace("$", "")):
                _walk((m.group(1) or m.group(2) or sheet).strip(),
                      m.group(3), int(m.group(4)))

            def _conf(leaf):
                """0 = held at prior / red (unconfirmed); 1 = plain
                unproven; 2 = orange back-out; 3 = proven."""
                sh2, c2, r2, v2, pv2 = leaf
                try:
                    rgb = str(wb[sh2][f"{c2}{r2}"].fill.fgColor.rgb or "")
                except Exception:
                    rgb = ""
                if rgb.endswith("FFC7CE"):
                    return 0
                from .rollover import input_is_proven
                if input_is_proven(served, sh2, f"{c2}{r2}", v2, (), wb):
                    return 3              # proven (a confirmed-unchanged
                                          # value is proven, not stale)
                if isinstance(pv2, (int, float)) \
                        and abs(v2 - pv2) <= row_tol(pv2):
                    return 0
                if rgb.endswith("FFC000"):
                    return 2
                return 1

            def _coeff(leaf):
                """d(roll)/d(input) by a unit bump; None if not evaluable."""
                sh2, c2, r2, v2, _pv2 = leaf
                cellu = wb[sh2][f"{c2}{r2}"]
                cellu.value = v2 + 1.0
                scratch = f"ZZ{r}"
                old_s = ws[scratch].value
                ws[scratch] = shifted
                try:
                    got2 = Evaluator(wb).cell(sheet, scratch)
                except Exception:
                    got2 = None
                ws[scratch] = old_s
                cellu.value = v2
                if not isinstance(got2, (int, float)):
                    return None
                return got2 - got

            # an input the roll does not actually respond to (a dead
            # branch, a zero weight) is not a candidate
            live = []
            for lf in leaves:
                cf = _coeff(lf)
                if isinstance(cf, (int, float)) and abs(cf) > 1e-9:
                    live.append((lf, cf))
            backed = False
            if live:
                ranked = sorted(live, key=lambda x: _conf(x[0]))
                low = _conf(ranked[0][0])
                cands = [x for x in live if _conf(x[0]) == low]
                # WHERE THE GAP IS ABSORBED IS THE BRAIN'S CALL (run
                # 34993405014: this back-out fired 14 times and wrote over the
                # brain's own rulings on Driver!AI37 and Final!AI87 — code
                # ranked the roll's inputs by confidence and took the decision
                # itself). Code still proves which inputs the roll responds to,
                # how confident each is and what the gap is; the brain says
                # where it belongs, once per row, and the ruling stands for
                # the rest of the run. A PROVEN input is never offered.
                movable = [x for x in live if _conf(x[0]) < 3]
                if ask is not None and movable:
                    _key = f"{sheet}!{r}"
                    _rulings = writer.log.setdefault("rollbase_rulings", {})
                    _pick = _rulings.get(_key)
                    if _pick is None:
                        _card = [f"CARD PLUG {sheet}!{fcs[0]}{r}",
                                 f"  {sheet}!{r}: the typed actual is {h:,.1f}, but the row's own forecast formula "
                                 f"pointed back one year reproduces only {got:,.1f} — the roll base is off {gap:+,.1f}, "
                                 "so every forecast year is born wrong by that constant.",
                                 "  the inputs the roll actually responds to (a proven one is not offered — it is never "
                                 "backed out); WHERE does the gap belong?"]
                        _opts = {}
                        for _i, ((_sh2, _c2, _r2, _v2, _pv2), _cf2) in enumerate(movable):
                            _lab2 = str(wb[_sh2].cell(_r2, 1).value or "")[:30]
                            _cf = _conf((_sh2, _c2, _r2, _v2, _pv2))
                            _what = ("red, or still held at last year's figure" if _cf == 0
                                     else "this run's own orange back-out" if _cf == 2 else "plain, unproven")
                            _card.append(f"    site:{_i + 1}: {_sh2}!{_c2}{_r2} '{_lab2}' = {_v2:,.2f} "
                                         f"(last year {_pv2 if not isinstance(_pv2, (int, float)) else f'{_pv2:,.2f}'}) — {_what}")
                            _opts[f"site:{_i + 1}"] = (f"back the {gap:+,.1f} out of {_sh2}!{_c2}{_r2} '{_lab2}' "
                                                       "as a traceable formula — orange, trued up when disclosed")
                        _opts["none"] = ("absorb it nowhere — flag these inputs red and leave the gap for the analyst "
                                         "(the right answer when the roll is missing a flow the model does not carry)")
                        _opts["site:code"] = ("no preference — take code's own ranking: the least confident input, "
                                              "or nothing at all if several are equally uncertain")
                        _card.append("  answers: " + ", ".join(_opts))
                        _pick = _ask_site(ask, "\n".join(_card), _opts, log, f"{sheet}!{fcs[0]}{r}")
                        _rulings[_key] = _pick
                    if isinstance(_pick, str) and _pick.startswith("site:") and _pick != "site:code":
                        # THE RULING NAMES A CELL, NOT A POSITION (reviewer
                        # 2026-09-16: the cache held an index into a list
                        # rebuilt at every firing — after a repair round moved
                        # one input out of it, the remembered 'site:2' pointed
                        # at a different cell, or at none at all)
                        _j0 = int(_pick.split(":")[1]) - 1
                        if 0 <= _j0 < len(movable):
                            _pick = "{}!{}{}".format(*movable[_j0][0][:3])
                        else:
                            _pick = "site:code"
                        _rulings[_key] = _pick
                    if _pick == "none":
                        for (_sh2, _c2, _r2, _v2, _pv2), _cf2 in movable:
                            writer.flag_ref(f"{_sh2}!{_c2}{_r2}", "red",
                                            (f"An input of the {sheet}!{r} roll, which misses its typed actual by "
                                             f"{gap:+,.0f}; left open by the brain's judgment rather than backed out "
                                             "— please check."))
                        log(f"[run]   roll-base: {sheet}!{r} — the brain left the {gap:+,.0f} gap open; "
                            "inputs flagged, nothing guessed")
                        cands, low = [], -1
                    elif isinstance(_pick, str) and "!" in _pick:
                        # the remembered ruling is a CELL: find it among the
                        # inputs this firing offers, whatever their order
                        _hit = next((x for x in movable
                                     if "{}!{}{}".format(*x[0][:3]) == _pick), None)
                        if _hit is not None:
                            cands = [_hit]
                            low = _conf(_hit[0])
                        else:
                            log(f"[run]   roll-base: {sheet}!{r} — your ruling named {_pick}, which is no "
                                "longer an input this roll responds to; nothing guessed")
                            cands, low = [], -1
                if not cands:
                    pass
                elif low >= 3:
                    log(f"[run]   roll-base: {sheet}!{r} — every input of "
                        "the roll is proven, yet the roll misses the typed "
                        "actual: a flow is missing from the model's own "
                        "arithmetic — definition question for the analyst "
                        "(no formula touched)")
                elif len(cands) == 1:
                    (sh2, c2, r2, v2, _pv2), coeff = cands[0]
                    # linear in the input? a second bump must give the
                    # same slope; then adj = -gap / slope solves exactly
                    cellu = wb[sh2][f"{c2}{r2}"]
                    cellu.value = v2 + 2.0
                    scratch = f"ZZ{r}"
                    old_s = ws[scratch].value
                    ws[scratch] = shifted
                    try:
                        got3 = Evaluator(wb).cell(sheet, scratch)
                    except Exception:
                        got3 = None
                    ws[scratch] = old_s
                    cellu.value = v2
                    linear = isinstance(got3, (int, float)) \
                        and abs((got3 - got) - 2.0 * coeff) <= 1e-6 * max(1.0, abs(coeff))
                    if linear:
                        # MEASURED, NOT SOLVED (owner 2026-09-17): code says by
                        # how much this input is off and what it would take to
                        # make the roll reproduce the typed actual; the brain
                        # decides whether that input is what is wrong.
                        adj = round(-gap / coeff, 6)
                        writer.flag_ref(f"{sh2}!{c2}{r2}", "red",
                            (f"Least confident input of the {sheet}!{r} roll: with "
                             f"{adj:+,.1f} on this cell the roll would reproduce the "
                             f"disclosed {h:,.0f}. Code does not make that change — "
                             "check whether this input is the one that is wrong."))
                        log(f"[run]   roll-base: {sh2}!{c2}{r2} is {adj:+,.1f} short of "
                            f"reproducing {sheet}!{r}'s typed actual — red, not solved")
                    if not backed:
                        writer.flag_ref(f"{sh2}!{c2}{r2}", "red",
                            (f"Least confident input of the {sheet}!{r} roll "
                             f"(gap {gap:+,.0f}); not backed out because the "
                             "roll is not linear in it — please check."))
                else:
                    names = ", ".join(f"{x[0][0]}!{x[0][1]}{x[0][2]}" for x in cands[:6])
                    log(f"[run]   roll-base: {sheet}!{r} — {len(cands)} inputs "
                        f"tied at confidence {low} ({names}); flagged, none guessed")
                    for (sh2, c2, r2, _v2, _pv2), _cf in cands:
                        cellu = wb[sh2][f"{c2}{r2}"]
                        writer.flag_ref(f"{sh2}!{c2}{r2}", "red",
                            (f"One of {len(cands)} equally uncertain inputs "
                             f"of the {sheet}!{r} roll is off by "
                             f"{gap:+,.0f}; could not tell which — please "
                             "check."))
            if backed:
                # the gap is closed at its cause: the forecast row leaves
                # the watch list (owner, run 233: "the formula is correct
                # — why is it red?")
                _ref = f"{sheet}!{fcs[0]}{r}"
                writer.log["forecast_watch"] = [
                    x for x in writer.log.get("forecast_watch", [])
                    if x[0] != _ref]
            log(f"[run] roll-base mismatch: {sheet}!{r} actual {h:,.1f} "
                f"vs its own roll {got:,.1f} (gap {gap:+,.1f}) — "
                + ("least confident input backed out; forecast unflagged" if backed
                   else "inputs flagged for the analyst; no formula touched"))
    return n


def twin_leads(wb, pre_values_wb, spec, target_year, log=print):
    """THE SECOND HOME, AS INFORMATION (owner 2026-09-17): a quantity typed in
    two places — the actual column and the cells a forecast rolls from — is
    FOUND here and said beside the row; whether they are the same quantity is
    the brain's call. {(sheet, row): one line}"""
    from .schedules import _Recorder
    rec = _Recorder()
    try:
        twin_reanchor(wb, pre_values_wb, spec, target_year, rec, lambda *a, **k: None)
    except Exception as e:  # noqa: BLE001
        log(f"[run] the twin index could not be built: {e!r}")
        return {}
    out = {}
    for sheet, coord, value, note in rec.proposed:
        m = re.search(r"(\d+)$", str(coord))
        if not m:
            continue
        v = f"{value:,.2f}" if isinstance(value, (int, float)) else str(value)[:40]
        out[(sheet, int(m.group(1)))] = (f"another home of this quantity (same prior, still holding last "
                                         f"period's figure): {v} — {note[:110]}")
    return out


def oneoff_watch(wb, spec, target_year, writer, log=print, pre_wb=None):
    """THE ONE-OFF, SAID NOT EDITED (owner 2026-09-17): the forecast cells that
    read an actual-year one-off are watch-listed with what the edit would be;
    the review's brain decides. -> how many."""
    from openpyxl.utils import column_index_from_string
    from .schedules import _Recorder
    candidates = {}
    axes = spec.get("year_axis") or {}
    ev = Evaluator(wb)

    def add_candidate(sheet, coord, note, forecast_refs):
        m = re.match(r"^([A-Z]{1,3})(\d+)$", str(coord))
        tcol = (axes.get(sheet) or {}).get("columns", {}).get(str(target_year))
        if not m or not tcol:
            return
        row = int(m.group(2))
        ref = f"{sheet}!{tcol}{row}"
        pcol = prior_column(spec, sheet, target_year)
        try:
            actual = ev.cell(sheet, f"{tcol}{row}")
        except Exception:
            actual = None
        try:
            prior = ev.cell(sheet, f"{pcol}{row}") if pcol else None
        except Exception:
            prior = None
        label = next((str(wb[sheet].cell(row, c).value).strip()
                      for c in range(1, 7)
                      if wb[sheet].cell(row, c).value not in (None, "")), "")
        section = ""
        for above in range(row - 1, 0, -1):
            if wb[sheet][f"{tcol}{above}"].value not in (None, ""):
                continue
            texts = [cell.value for cell in wb[sheet][above]
                     if cell.column < column_index_from_string(tcol)
                     and isinstance(cell.value, str) and not cell.value.startswith("=")]
            if texts:
                section = " | ".join(texts)
                break
        entry = candidates.setdefault(ref, {
            "id": ref, "sheet": sheet, "row": row,
            "actual": ref, "forecast": [],
            "label": label, "section": section, "actual_value": actual, "prior_value": prior,
            "note": "candidate found by one-off structural detector; analyst classification required",
        })
        for fref in forecast_refs:
            if fref not in entry["forecast"]:
                entry["forecast"].append(fref)
        writer.watch(forecast_refs[0].split("!", 1)[0],
                     forecast_refs[0].split("!", 1)[1],
                     "this forecast links to an actual-year one-off and would carry it into every "
                     "forecast year; code has not changed it. " + note[:120])

    if pre_wb is not None:
        from .freeze import hold_oneoff_forecasts
        old_ev = Evaluator(pre_wb)
        for sheet in axes:
            if sheet not in wb.sheetnames or sheet not in pre_wb.sheetnames:
                continue
            tcol = (axes.get(sheet) or {}).get("columns", {}).get(str(target_year))
            if not tcol:
                continue
            for row in range(1, wb[sheet].max_row + 1):
                try:
                    now = ev.cell(sheet, f"{tcol}{row}")
                    old = old_ev.cell(sheet, f"{tcol}{row}")
                except Exception:
                    continue
                if not isinstance(now, (int, float)) or not isinstance(old, (int, float)) \
                        or abs(now - old) <= row_tol(old):
                    continue
                plans = hold_oneoff_forecasts(wb, pre_wb, spec, target_year,
                                              sheet, row, None, preview=True)
                if plans:
                    add_candidate(sheet, f"{tcol}{row}",
                                   "original forecast input evaluated to zero; explicit classification required",
                                   [f"{p['sheet']}!{p['coord']}" for p in plans])
        if candidates:
            writer.log.setdefault("oneoff_candidates", {}).update(candidates)
        return len(candidates)

    rec = _Recorder()
    try:
        oneoff_no_propagate(wb, spec, target_year, rec, lambda *a, **k: None)
    except Exception as e:  # noqa: BLE001
        log(f"[run] the one-off index could not be built: {e!r}")
        return 0
    for sheet, coord, _v, note in rec.proposed:
        add_candidate(sheet, coord, note, [f"{sheet}!{coord}"])
    if candidates:
        writer.log.setdefault("oneoff_candidates", {}).update(candidates)
    return len(rec.proposed)


def probe_watch(wb, spec, target_year, fc_base, writer, log=print):
    """The roll artifact the analyst's own pre-update forecast disowns — found,
    said, never held by code. -> how many."""
    from .schedules import _Recorder
    rec = _Recorder()
    try:
        auto_probe_holds(wb, spec, target_year, fc_base, rec, lambda *a, **k: None)
    except Exception as e:  # noqa: BLE001
        log(f"[run] the probe index could not be built: {e!r}")
        return 0
    for sheet, coord, v, note in rec.proposed:
        writer.watch(sheet, coord,
                     f"the analyst's own baseline for this forecast cell was "
                     f"{v if not isinstance(v, (int, float)) else f'{v:,.4f}'}; the update moved it. "
                     + note[:110])
    return len(rec.proposed)
