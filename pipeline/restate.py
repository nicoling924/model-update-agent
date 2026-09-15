"""RESTATING THE PRIOR PERIOD (owner 2026-09-15: "if we restate the previous
period it is similar to a usual model update — map using the previous
unrestated results, then map with the newly restated previous-period
results"). Only when the run is started with RESTATE=1; never unasked.

For every model row with a typed prior: last year's report proves the
NAME (its line whose own figure equals the model's prior), this year's
report prints the same name with a restated comparative; that comparative
is written into the prior column, clean (a restatement is an update, not a
doubt), and listed on the report page. Everything after then maps this
year's figures against the restated priors.
"""
import re

from .checks import prior_column, year_columns
from .ledger import sourceable as _sourceable
from .numerics import kinship, norm_label, to_model_units


def _comparative(it, target_year, period):
    """The comparative's index among the line's numbers: by the column
    headers when the reading names them, else the second number."""
    try:
        from .tables import target_columns
        tc = target_columns(it, target_year, period)
        if tc and tc[1] is not None:
            return tc[1]
    except Exception:  # noqa: BLE001
        pass
    from .writegate import comparative_index
    ns = [n for n in (it.nums or []) if isinstance(n, (int, float))]
    cols = [str(c) for c in (getattr(it, "columns", None) or [])]
    return comparative_index(ns, cols, 0) if ns else None


def _specific(label):
    t = norm_label(str(label)).replace(" ", "")
    cjk = sum(1 for ch in t if "一" <= ch <= "鿿")
    return bool(t) and (cjk >= 3 or len(str(label).split()) >= 2)


def _close(a, b):
    return abs(abs(a) - abs(b)) <= max(0.6, abs(b) * 5e-4)


def restated_priors(ledger, targets, scales, target_year=None, period=None):
    """-> {(sheet, row): (restated_value, old_line, new_line, doc, page)} for
    rows whose prior is restated by this year's report."""
    prior_lines = [it for it in ledger.items if not _sourceable(it) and getattr(it, "channel", "") != "prose"
                   and getattr(it, "table_kind", None) == "period" and _specific(it.label)]
    cur_lines = [it for it in ledger.items if _sourceable(it) and getattr(it, "channel", "") != "prose"
                 and getattr(it, "table_kind", None) == "period"]
    by_name = {}
    for it in cur_lines:
        by_name.setdefault(norm_label(str(it.label)).replace(" ", ""), []).append(it)
    out = {}
    for (sheet, row), t in sorted(targets.items()):
        pv = getattr(t, "prior_value", None)
        if not isinstance(pv, (int, float)) or abs(pv) < 1:
            continue
        names = set()
        model_label = str(getattr(t, "label", "") or "")
        for it in prior_lines:
            ns = [n for n in (it.nums or []) if isinstance(n, (int, float))]
            if ns and _close(ns[0], pv) and (not model_label or kinship(model_label, str(it.label))):
                names.add(norm_label(str(it.label)).replace(" ", ""))   # the number AND the name prove last year's line
        if not names:
            continue
        found = []
        for nm in names:
            for it in by_name.get(nm, []):
                ns = [n for n in (it.nums or []) if isinstance(n, (int, float))]
                ci = _comparative(it, target_year, period) if target_year else (1 if len(ns) > 1 else None)
                if ci is None or ci >= len(ns):
                    continue
                sc = scales.get((it.doc, it.page)) or 1.0
                comp = to_model_units(ns[ci], sc)
                if _close(comp, pv):
                    continue                        # not restated
                if abs(comp) > 30 * abs(pv) or abs(comp) * 30 < abs(pv):
                    continue                        # another world: not this item
                found.append((comp, it))
        vals = {round(v, 1) for v, _ in found}
        if len(vals) != 1:
            continue                                # none, or the documents disagree: not written
        comp, it = found[0]
        signed = comp if (pv >= 0) == (comp >= 0) else -abs(comp) if pv < 0 else abs(comp)
        out[(sheet, row)] = (float(signed), str(it.label)[:50], it.doc, it.page)
    return out


def restate_prior_column(wb, wb_values, spec, target_year, ledger, targets, writer, log, period=None):
    """Write the restated comparatives into the prior column (both workbooks).
    -> number of cells restated."""
    from .stage2_join import ratify_page_scales
    priors = [t.prior_value for t in targets.values() if isinstance(getattr(t, "prior_value", None), (int, float))]
    scales = ratify_page_scales([it for it in ledger.items if it.joinable()], priors, [])
    found = restated_priors(ledger, targets, scales, target_year=target_year, period=period)
    n = 0
    for (sheet, row), (val, line, doc, page) in sorted(found.items()):
        pcol = prior_column(spec, sheet, target_year)
        if not pcol or sheet not in wb.sheetnames:
            continue
        coord = f"{pcol}{row}"
        held = wb[sheet][coord].value
        if not isinstance(held, (int, float)):
            continue                                # a formula prior is the model's design, never overwritten
        note = f"Restated: this year's report prints last year at {val:,.2f} under '{line}' ({doc} p{page}); was {held:,.2f}."
        ok = writer.write(sheet, coord, val, trusted=True, force_lock=True, note=note)
        if not ok:
            continue
        try:
            from openpyxl.comments import Comment
            wb[sheet][coord].comment = Comment(note[:700], "model-update-agent")   # a restated cell says so (no colour: an update, not a doubt)
        except Exception:  # noqa: BLE001
            pass
        try:
            wb_values[sheet][coord].value = val
        except Exception:
            pass
        t = targets.get((sheet, row))
        if t is not None:
            t.prior_value = float(val)
        writer.log.setdefault("restatements", []).append(f"{sheet}!{coord}: {held:,.2f} -> {val:,.2f} ('{line}', {doc} p{page})")
        n += 1
    log(f"[run] restate: {n} prior-period cell(s) restated to this year's report" if n else "[run] restate: nothing to restate — this year's report prints last year as the model holds it")
    return n
