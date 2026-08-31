"""The key-tie law (owner ruling 2026-08-31, reviewing the first CLP
delivery).

Keys must be CORRECT — a flag does not excuse a wrong key (mindmap).
The disclosure PRINTS the headline keys, and the printed values are
pinned in replay/<period>/key_panel.json, so every key row can be tied
out exactly. A key that is off gets ONE component backed out — a
traceable orange formula wrapping the component's own expression — so
the key ties the print (the owner's ladder: "back out so the =SUM
matches the disclosed figure").

Component choice mirrors the run-203 autopsy: prefer the
ESTIMATE-IN-ACTUAL class — a target-column cell holding a FORMULA where
the prior actual holds a HARDCODE (the mark-to-actual type rule
violated: =AH14*(AI7/AH7) impersonating an actual) — then any largest
formula leaf. Transactional: the wrap must make the key tie and must
not create errors, or it reverts and the next candidate is tried.
"""
import json
import re
from pathlib import Path

from .checks import prior_column, year_columns
from .evaluator import Evaluator

TOL_REL = 0.002          # 0.2% — keys tie the print or get backed out
TOL_ABS = 1.0


def _leaves(wb, sheet, coord, depth=0, seen=None):
    seen = seen if seen is not None else set()
    if depth > 6 or (sheet, coord) in seen or len(seen) > 300:
        return []
    seen.add((sheet, coord))
    v = wb[sheet][coord].value if sheet in wb.sheetnames else None
    if not (isinstance(v, str) and v.startswith("=")):
        return [(sheet, coord)]
    out = []
    for m in re.finditer(r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?"
                         r"([A-Z]{1,3})(\d+)", v.replace("$", "")):
        sh = (m.group(1) or m.group(2) or sheet).strip()
        if sh in wb.sheetnames:
            out += _leaves(wb, sh, f"{m.group(3)}{m.group(4)}",
                           depth + 1, seen)
    return out or [(sheet, coord)]


def _printed(ledger, v):
    """Is v itself a printed disclosed figure? -> 'doc pN' or None.
    The definition guard: a model value the disclosure PRINTS is
    defensible — forcing it to a different pin is the adjusted-profit
    trap (run-203: the model's attributable 10,468 IS CLP's printed
    Total Earnings; the pin 11,546 is profit-for-the-year — two
    definitions, the analyst's ruling, never a forced write)."""
    if ledger is None:
        return None
    # CURRENT-document FACE pages only, tight tolerance — a loose
    # whole-ledger search excused every wrong key via coincidental ties
    # in the prior-year AR (measured on run-203's file)
    prior_docs = ledger.prior_period_docs()
    tol = max(0.6, abs(v) * 1e-4)
    for it in ledger.items:
        if it.doc in prior_docs or (it.doc, it.page) not in ledger.faces:
            continue
        for n in it.nums:
            if abs(abs(n) - abs(v)) <= tol:
                return f"{it.doc} p{it.page}"
    return None


def key_tie(wb, spec, target_year, writer, panel_path, log, ledger=None):
    """-> number of keys backed out to tie. Runs after the loop."""
    panel_path = Path(panel_path)
    if not panel_path.exists():
        return 0
    try:
        panel = json.loads(panel_path.read_text())
    except Exception:
        return 0

    def _key_state():
        """Every panel key's (name, got, want, ok) right now."""
        out = []
        ev = Evaluator(wb)
        for kk in (spec.get("key_rows") or []):
            nm, sh2, r2 = kk.get("name"), kk.get("sheet"), int(kk.get("row"))
            w2 = (panel.get(nm) or {}).get("print")
            tc2 = year_columns(spec, sh2).get(str(target_year)) \
                if sh2 in wb.sheetnames else None
            if not isinstance(w2, (int, float)) or not tc2:
                continue
            try:
                g2 = ev.cell(sh2, f"{tc2}{r2}")
            except Exception:
                continue
            if isinstance(g2, (int, float)):
                out.append((nm, g2, w2,
                            abs(g2 - w2) <= max(TOL_ABS, abs(w2) * TOL_REL)))
        return out

    n = 0
    for k in (spec.get("key_rows") or []):
        name, sheet, row = k.get("name"), k.get("sheet"), int(k.get("row"))
        want = (panel.get(name) or {}).get("print")
        if not isinstance(want, (int, float)) or sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        pcol = prior_column(spec, sheet, target_year)
        if not tcol:
            continue
        try:
            got = Evaluator(wb).cell(sheet, f"{tcol}{row}")
        except Exception:
            continue                      # erroring keys are the error law's
        if not isinstance(got, (int, float)):
            continue
        delta = got - want
        if abs(delta) <= max(TOL_ABS, abs(want) * TOL_REL):
            continue
        # THE DEFINITION GUARD: if the model's own value IS a printed
        # disclosed figure, this is two definitions of one label —
        # a RED question for the analyst, never a forced write
        src = _printed(ledger, got)
        if src is not None:
            from openpyxl.comments import Comment
            cell = wb[sheet][f"{tcol}{row}"]
            cell.fill = writer.fills["red"]
            cell.comment = Comment(
                f"DEFINITION QUESTION: '{name}' computes {got:,.2f}, which "
                f"the disclosure ITSELF prints ({src}) — but the pinned "
                f"panel says {want:,.2f}. Two definitions of one label "
                "(reported vs attributable / underlying). ANALYST RULING; "
                "nothing forced.", "Model Update Agent")
            writer.log["flags"].append(f"{sheet}!{tcol}{row}")
            log(f"[run] key tie: '{name}' {got:,.2f} vs pin {want:,.2f} — "
                f"model value is itself printed ({src}): definition "
                "question, red, nothing forced")
            continue
        tied_before = {nm for nm, _g, _w, ok in _key_state() if ok}
        # candidates: every FORMULA cell in the key's chain (estimate
        # formulas are intermediate nodes, not leaves — run-203's
        # =AH14*(AI7/AH7) sums into the key through EBITDA), the
        # estimate-in-actual class first (formula over a hardcode
        # prior — the type violation), then by size
        seen = set()
        _leaves(wb, sheet, f"{tcol}{row}", seen=seen)
        cands = []
        for (sh, coord) in seen - {(sheet, f"{tcol}{row}")}:
            m = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
            if not m or m.group(1) != year_columns(spec, sh).get(
                    str(target_year)):
                continue
            f = wb[sh][coord].value
            if not (isinstance(f, str) and f.startswith("=")):
                continue
            pc = prior_column(spec, sh, target_year)
            pv = wb[sh][f"{pc}{m.group(2)}"].value if pc else None
            try:
                cv = Evaluator(wb).cell(sh, coord)
            except Exception:
                continue
            if not isinstance(cv, (int, float)):
                continue
            type_violation = isinstance(pv, (int, float))
            cands.append((0 if type_violation else 1, -abs(cv), sh, coord, f))
        for _t, _sz, sh, coord, f in sorted(cands)[:4]:
            # probe: wrap the component so it absorbs the delta
            new_f = f"=({f[1:]})-({delta:.6g})"
            old = wb[sh][coord].value
            wb[sh][coord] = new_f
            try:
                after = Evaluator(wb).cell(sheet, f"{tcol}{row}")
            except Exception:
                after = None
            untied = {nm for nm, _g, _w, ok in _key_state()
                      if not ok} & tied_before
            if isinstance(after, (int, float)) \
                    and abs(after - want) <= max(TOL_ABS, abs(want) * TOL_REL) \
                    and not untied:
                wb[sh][coord] = old       # land it through the chokepoint
                ok = writer.write(
                    sh, coord, new_f,
                    prior_coord=(f"{prior_column(spec, sh, target_year)}"
                                 f"{''.join(ch for ch in coord if ch.isdigit())}"
                                 if prior_column(spec, sh, target_year)
                                 else None),
                    trusted=True, flag="orange",
                    note=(f"KEY-TIE back-out: '{name}' computed {got:,.2f} "
                          f"vs disclosed {want:,.2f} — this component "
                          f"absorbed the {delta:,.2f} so the key ties the "
                          f"print. Was: {f[:120]}. ANALYST REVIEW."))
                if ok:
                    n += 1
                    log(f"[run] key tie: '{name}' {got:,.2f} -> {want:,.2f} "
                        f"via {sh}!{coord} (orange back-out)")
                break
            wb[sh][coord] = old           # try the next candidate
        else:
            log(f"[run] key tie: '{name}' OFF {delta:+,.2f} vs print "
                f"{want:,.2f} and no component could absorb it — "
                "left for the analyst (red)")
            cell = wb[sheet][f"{tcol}{row}"]
            from openpyxl.comments import Comment
            cell.fill = writer.fills["red"]
            cell.comment = Comment(
                f"KEY OFF: computes {got:,.2f} vs disclosed {want:,.2f} "
                f"({delta:+,.2f}); no component absorbed it. ANALYST.",
                "Model Update Agent")
            writer.log["flags"].append(f"{sheet}!{tcol}{row}")
    return n
