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
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        pcol = prior_column(spec, sheet, target_year)
        if not pcol:
            continue
        ws = wb[sheet]
        for r in range(1, min(ws.max_row, 300) + 1):
            pv = ws[f"{pcol}{r}"].value
            if isinstance(pv, (int, float)) and abs(pv) >= min_val:
                homes[round(pv, 1)].append((sheet, r))
    n_rw = n_tw = 0
    ev = Evaluator(wb)
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
        pv = wb[sh][f"{pcol}{row}"].value if pcol else None
        if not isinstance(pv, (int, float)) or abs(pv) < min_val:
            continue
        served = wb[sh][coord].value
        if not isinstance(served, (int, float)) \
                or abs(served - pv) <= row_tol(pv):
            continue                      # unchanged value teaches nothing
        twins = [t for t in homes.get(round(pv, 1), [])
                 if t != (sh, row)]
        if not twins or len(twins) > TWIN_MAX_HOMES:
            continue
        for (sh2, r2) in twins:
            tc2 = year_columns(spec, sh2).get(str(target_year))
            if not tc2:
                continue
            cell = wb[sh2][f"{tc2}{r2}"]
            cur = cell.value
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
                    from openpyxl.comments import Comment
                    cell.fill = writer.fills["red"]
                    cell.comment = Comment(
                        f"STALE TWIN: evaluates to last year's {pv:,.1f} "
                        f"but {ref} (the same quantity's other home) was "
                        f"served {served:,.1f}. This roll/base must be "
                        "re-anchored — the run-204 NFA lesson: a stale "
                        "twin base breaks every forecast year.", "Model Update Agent")
                    writer.log["flags"].append(f"{sh2}!{tc2}{r2}")
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
            # wild = the plug moved by a lot in absolute terms AND far
            # beyond its own history (the export plug: -1,598 vs -4 is
            # wild; -185 vs -4 after the fix is quiet)
            wild = abs(now - was) > max(500.0, 4 * abs(was))
            if wild:
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
                    ws[f"{fc}{r}"].value = 0
                    ws[f"{fc}{r}"].fill = writer.fills["orange"]
                    ws[f"{fc}{r}"].comment = Comment(
                        f"ONE-OFF NOT PROPAGATED: the actual {av:,.1f} "
                        f"is new this year (prior ~0); this cell linked "
                        f"it into the forecast ({f}). Set to 0 per the "
                        "roll-forward law; restore the link if the item "
                        "recurs.", "Model Update Agent")
                    writer.log["flags"].append(f"{sheet}!{fc}{r}")
                    n += 1
                    log(f"[run]   one-off law: {sheet}!{fc}{r} link to "
                        f"{tcol}{r} ({av:,.1f}, prior ~0) -> 0 (orange)")
    return n
