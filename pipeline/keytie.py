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
from .ledger import vintage_ban as _vintage_ban

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
    txt = v.replace("$", "")
    # SUM(C57:C63) names every row of the range, not just its ends
    # (run-231 autopsy: the receivables row inside a subtotal's range
    # was invisible to the back-out search)
    for m in re.finditer(r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?"
                         r"([A-Z]{1,3})(\d+):([A-Z]{1,3})(\d+)", txt):
        sh = (m.group(1) or m.group(2) or sheet).strip()
        if sh in wb.sheetnames and m.group(3) == m.group(5):
            r1, r2 = int(m.group(4)), int(m.group(6))
            for rr in range(min(r1, r2), max(r1, r2) + 1):
                out += _leaves(wb, sh, f"{m.group(3)}{rr}", depth + 1, seen)
    txt = re.sub(r"[A-Z]{1,3}\d+:[A-Z]{1,3}\d+", " ", txt)
    for m in re.finditer(r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?"
                         r"([A-Z]{1,3})(\d+)", txt):
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
    prior_docs = _vintage_ban(ledger)
    tol = max(0.6, abs(v) * 1e-4)
    for it in ledger.items:
        if it.doc in prior_docs or (it.doc, it.page) not in ledger.faces:
            continue
        for n in it.nums:
            if abs(abs(n) - abs(v)) <= tol:
                return f"{it.doc} p{it.page}"
    return None


def _bridge_rows(wb, spec, target_year, sheet, key_coord, pcol,
                 d_prior, d_cur, max_size=3):
    """NAME the adjustment: model rows in the key's chain whose PRIOR
    values sum to d_prior AND whose CURRENT values sum to d_cur — the
    model's own wiring names what the analyst adds/removes vs the print
    (e.g. minority interests + perpetual coupons).
    -> [(sheet, row, label)] or None."""
    from itertools import combinations
    tcol = year_columns(spec, sheet).get(str(target_year))
    seen = set()
    _leaves(wb, sheet, key_coord, seen=seen)
    rows = []
    for (sh, coord) in seen:
        m = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
        if not m or (sh, coord) == (sheet, key_coord):
            continue
        tc = year_columns(spec, sh).get(str(target_year))
        pc = prior_column(spec, sh, target_year)
        if not tc or not pc or m.group(1) != tc:
            continue
        try:
            cv = Evaluator(wb).cell(sh, coord)
            pv = Evaluator(wb).cell(sh, f"{pc}{m.group(2)}")
        except Exception:
            continue
        if not (isinstance(cv, (int, float)) and isinstance(pv, (int, float))):
            continue
        if abs(pv) < 0.5 and abs(cv) < 0.5:
            continue
        lab = ""
        ws = wb[sh]
        for lc in ("A", "B", "C", "D"):
            v = ws[f"{lc}{m.group(2)}"].value
            if isinstance(v, str) and v.strip():
                lab = v.strip()[:30]
                break
        rows.append((sh, int(m.group(2)), lab, pv, cv))
    rows = sorted(rows, key=lambda x: -abs(x[3]))[:25]
    tol_p = max(1.0, abs(d_prior) * 0.01)
    tol_c = max(1.0, abs(d_cur) * 0.01)
    for size in (1, 2, 3):
        if size > max_size:
            break
        for combo in combinations(rows, size):
            if abs(sum(c[3] for c in combo) - d_prior) <= tol_p \
                    and abs(sum(c[4] for c in combo) - d_cur) <= tol_c:
                return [(c[0], c[1], c[2]) for c in combo]
    return None


def key_tie(wb, spec, target_year, writer, panel_path, log, ledger=None,
            panel=None, keys=None, max_delta_frac=None, absorbers="any"):
    """-> number of keys backed out to tie. Runs after the loop.
    panel / keys: an in-memory panel and key list override the pinned
    file (the printed-subtotal tie passes the statements' own totals)."""
    if panel is None:
        panel_path = Path(panel_path)
        if not panel_path.exists():
            return 0
        try:
            panel = json.loads(panel_path.read_text())
        except Exception:
            return 0
    key_rows = keys if keys is not None else (spec.get("key_rows") or [])

    def _key_state():
        """Every panel key's (name, got, want, ok) right now."""
        out = []
        ev = Evaluator(wb)
        for kk in key_rows:
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

    # a key row is never another key's absorber (run-231 replay: the
    # total-assets tie wrapped CASH, itself a key, round after round)
    key_cells = set()
    for kk in key_rows:
        tc_k = year_columns(spec, kk.get("sheet")).get(str(target_year)) \
            if kk.get("sheet") in wb.sheetnames else None
        if tc_k:
            key_cells.add((kk.get("sheet"), f"{tc_k}{int(kk.get('row'))}"))
    n = 0
    for k in key_rows:
        name, sheet, row = k.get("name"), k.get("sheet"), int(k.get("row"))
        want = (panel.get(name) or {}).get("print")
        if not isinstance(want, (int, float)) or sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        pcol = prior_column(spec, sheet, target_year)
        if not tcol:
            continue
        # ONE ABSORBER PER KEY (CLP run 262: the gate loop re-tied 'total
        # assets' three times and each pass wrapped a DIFFERENT component
        # — receivables, then investment securities, then non-current
        # assets — three orange back-outs whose sum was one plug, and the
        # current-asset block off by their stack). A key keeps its
        # absorber for the whole run: a re-tie unwraps that cell to its
        # original formula and re-solves the whole delta there.
        _abs_log = writer.log.setdefault("key_absorbers", {})
        prev_c, prev_wrapped = None, None
        prev = _abs_log.get(name)
        if prev:
            psh, pcoord, porig, pwrap_f, pwrap = prev
            held_p = wb[psh][pcoord].value if psh in wb.sheetnames else None
            if held_p == pwrap_f:
                wb[psh][pcoord] = porig
                prev_c = (-1, 0, psh, pcoord, porig, pwrap)
                prev_wrapped = (psh, pcoord, held_p)
            elif held_p == porig:
                # the gate loop's take-back already unwrapped it (CLP live
                # 2026-09-08: 'total assets' then moved to a second cell)
                prev_c = (-1, 0, psh, pcoord, porig, pwrap)
        try:
            got = Evaluator(wb).cell(sheet, f"{tcol}{row}")
        except Exception:
            continue                      # erroring keys are the error law's
        if not isinstance(got, (int, float)):
            continue
        delta = got - want
        if abs(delta) <= max(TOL_ABS, abs(want) * TOL_REL):
            if prev_c is not None:
                # the key ties on its own now — the back-out is withdrawn
                _, _, psh, pcoord, porig, _pw = prev_c
                writer.write(psh, pcoord, porig,
                             prior_coord=(f"{prior_column(spec, psh, target_year)}"
                                          f"{''.join(ch for ch in pcoord if ch.isdigit())}"
                                          if prior_column(spec, psh, target_year) else None),
                             trusted=True)
                _abs_log.pop(name, None)
                log(f"[run] key tie: '{name}' ties without its back-out — {psh}!{pcoord} restored")
            continue
        if max_delta_frac is not None and abs(delta) > max_delta_frac * max(abs(want), 1.0):
            # THE BOUNDED BACK-OUT (run-231: a subtotal tie on a transient
            # gate-loop state wrapped a 93,455 delta into one component):
            # a subtotal off by more than the bound is not a back-out
            # case — it is flagged, never absorbed
            from openpyxl.comments import Comment
            cell = wb[sheet][f"{tcol}{row}"]
            cell.fill = writer.fills["red"]
            cell.comment = Comment(
                f"SUBTOTAL OFF: computes {got:,.2f} vs printed {want:,.2f} "
                f"({delta:+,.2f}) — beyond the back-out bound; ANALYST.",
                "Model Update Agent")
            if f"{sheet}!{tcol}{row}" not in writer.log["flags"]:
                writer.log["flags"].append(f"{sheet}!{tcol}{row}")
            log(f"[run] key tie: '{name}' off {delta:+,.2f} — beyond the "
                "back-out bound, flagged")
            if prev_wrapped:
                wb[prev_wrapped[0]][prev_wrapped[1]] = prev_wrapped[2]   # a flagged/confirmed key keeps its standing back-out
            continue
        # THE PRIOR-DELTA PROTOCOL (owner ruling 2026-08-31): the PRIOR
        # year proves the definition. Model prior == printed prior ->
        # the model follows the print, tie this year too (back-out
        # below). Model prior != printed prior -> the difference IS the
        # analyst's adjustment: NAME it (find the model rows whose two
        # years' values ARE the two deltas), and if the same named
        # bridge closes this year, the model is RIGHT despite differing
        # from the print — confirmed, note on _REPORT, nothing forced.
        pin_prior = (panel.get(name) or {}).get("prior")
        model_prior = None
        if pcol:
            try:
                model_prior = Evaluator(wb).cell(sheet, f"{pcol}{row}")
            except Exception:
                pass
        adjusted = (isinstance(pin_prior, (int, float))
                    and isinstance(model_prior, (int, float))
                    and abs(model_prior - pin_prior)
                    > max(TOL_ABS, abs(pin_prior) * TOL_REL))
        if adjusted:
            d_prior = model_prior - pin_prior
            bridge = _bridge_rows(wb, spec, target_year, sheet,
                                  f"{tcol}{row}", pcol, d_prior, delta)
            from openpyxl.comments import Comment
            cell = wb[sheet][f"{tcol}{row}"]
            if bridge:
                labels = " + ".join(b[2] or f"{b[0]}!{b[1]}"
                                    for b in bridge)
                writer.log.setdefault("verdicts", []).append(
                    f"{sheet}!{tcol}{row}: JUSTIFIED — '{name}' differs "
                    f"from the print by design: model = print "
                    f"{'-' if delta < 0 else '+'} [{labels}] and the "
                    f"same bridge closes BOTH years "
                    f"({d_prior:+,.1f} prior, {delta:+,.1f} now)")
                log(f"[run] key tie: '{name}' {got:,.2f} vs print "
                    f"{want:,.2f} — CONFIRMED by the prior-delta "
                    f"bridge [{labels}]; the analyst's treatment is "
                    "preserved, nothing forced")
                continue
            src = _printed(ledger, got)
            cell.fill = writer.fills["red"]
            cell.comment = Comment(
                f"DEFINITION QUESTION: '{name}' computes {got:,.2f} vs "
                f"printed {want:,.2f} ({delta:+,.2f}), and the prior "
                f"year ALSO differed ({d_prior:+,.2f}) — an adjustment "
                "exists but no model rows explain BOTH deltas."
                + (f" Note: {got:,.2f} is itself printed ({src})."
                   if src else "")
                + " ANALYST RULING; nothing forced.",
                "Model Update Agent")
            writer.log["flags"].append(f"{sheet}!{tcol}{row}")
            log(f"[run] key tie: '{name}' off {delta:+,.2f} AND prior "
                f"off {d_prior:+,.2f} with no closing bridge — red "
                "question for the analyst")
            if prev_wrapped:
                wb[prev_wrapped[0]][prev_wrapped[1]] = prev_wrapped[2]   # a flagged/confirmed key keeps its standing back-out
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
        # THE ABSORBER IS THE LEAST CONFIDENT LEAF (owner 2026-09-10: "trace
        # the components within the formula and back out or plug the least
        # confident cell instead of plugging the entire formula"). Classes,
        # in order: (0) a red cell — an answer the run could not prove;
        # (1) a constant carried inside a formula from last year's column
        # (=94-AI29-AI28: the 94 is last year's one-off total); (2) an
        # orange cell — already backed out, still unproven; (3) an estimate
        # formula left in the actual column (formula over a hardcode prior,
        # run 203). A plain hardcode is a proven serve and a plain formula
        # of references is the analyst's design — neither absorbs.
        for (sh, coord) in seen - {(sheet, f"{tcol}{row}")}:
            m = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
            if not m or m.group(1) != year_columns(spec, sh).get(
                    str(target_year)):
                continue
            if (sh, coord) in key_cells:
                continue      # never absorb into another key's row
            f = wb[sh][coord].value
            is_formula = isinstance(f, str) and f.startswith("=")
            if is_formula and _SUBTOTAL.match(f.replace("$", "")):
                continue      # a subtotal row is never the absorber (run-231)
            try:
                rgb = str(wb[sh][coord].fill.fgColor.rgb or "")
            except Exception:
                rgb = ""
            red, orange = rgb.endswith("FFC7CE"), rgb.endswith("FFC000")
            if absorbers == "unproven" and not red:
                continue      # the owner's rule: only the numbers the run could NOT find
            pc = prior_column(spec, sh, target_year)
            pv = wb[sh][f"{pc}{m.group(2)}"].value if pc else None
            try:
                cv = Evaluator(wb).cell(sh, coord)
            except Exception:
                continue
            if not isinstance(cv, (int, float)):
                continue
            lit = None
            if is_formula:
                # the composites law's own reading of a formula's literals: a
                # modelling constant (0.5, 2, 100) is design; a carried actual
                # (94, 4976) that the prior column's formula also holds is last
                # year's number living in this year's cell
                from .composites import literals_of as _lits, MODELING_CONSTANTS as _MC, VINTAGE_FLOOR as _VF
                pf = str(pv) if isinstance(pv, str) else ""
                for x in _lits(f):
                    try:
                        xv = abs(float(x))
                    except ValueError:
                        continue
                    if xv not in _MC and xv >= _VF and pf.startswith("=") and x in pf:
                        lit = x
                        break
            if red:
                rank = 0
            elif lit is not None:
                rank = 1
            elif orange:
                rank = 2
            elif is_formula and isinstance(pv, (int, float)):
                rank = 3      # the estimate-in-actual class
            else:
                continue
            if is_formula and lit is not None and not red:
                # a plain formula whose only doubt is the carried literal: the
                # literal absorbs; a RED formula is unproven as a whole
                def _wrap(d, f=f, lit=lit):
                    return re.sub(r"(?<![A-Za-z0-9_.])" + re.escape(lit) + r"(?![\d.])",
                                  f"({lit}-({d:.6g}))", f, count=1)
            elif is_formula:
                def _wrap(d, f=f):
                    return f"=({f[1:]})-({d:.6g})"
            else:
                def _wrap(d, v=cv):
                    return f"=({v:g})-({d:.6g})"
            cands.append((rank, -abs(cv), sh, coord, f, _wrap))
        for _r, _sz, sh, coord, f, _wrap in ([prev_c] if prev_c else []) + sorted(cands, key=lambda c: (c[0], c[1]))[:8]:
            # probe: the component absorbs the delta — either sign, since a
            # component may enter the key negatively (one-offs are deducted)
            old = wb[sh][coord].value
            landed = None
            for _sgn in (1, -1):
                new_f = _wrap(_sgn * delta)
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
                    landed = new_f
                    break
                wb[sh][coord] = old
            if landed is not None:
                new_f = landed
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
                          f"print. Was: {str(f)[:120]}. ANALYST REVIEW."))
                if ok:
                    n += 1
                    _abs_log[name] = [sh, coord, f, new_f, _wrap]
                    log(f"[run] key tie: '{name}' {got:,.2f} -> {want:,.2f} "
                        f"via {sh}!{coord} (orange back-out)")
                break
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


# -- RULE 2 AT THE GATE (owner, 2026-09-03): a key that was tied to the
# print must still be tied when the run delivers ------------------------
def _panel(panel_path):
    try:
        return json.loads(Path(panel_path).read_text())
    except Exception:
        return {}


def _sig_digits(v):
    return len(re.sub(r"[^0-9]", "", "%.2f" % abs(v)).strip("0"))


def panel_by_prior_tie(wb, spec, target_year, ledger, log=None, served=None):
    """THE OWNER'S RULE (2026-09-08): a model's headline row is whatever
    the analyst defined it as, and the definition shows in last year's
    number — find the printed line whose comparative equals the model's
    prior for that row, and that line's current figure is the print the
    row must tie this year. Names ('net profit', 'total net profit',
    'net recurring profit') are not the signal; the prior tie is.
    -> {name: {"print": current, "prior": model prior, "line": ...}} for
    every key row with exactly one such reading; several different
    currents tying the same prior = ambiguous, left out (logged)."""
    from .writegate import _SCALES, _ties_full_precision
    ev = Evaluator(wb)
    ban = _vintage_ban(ledger)
    out = {}
    for kk in (spec.get("key_rows") or []):
        nm, sh, r = kk.get("name"), kk.get("sheet"), int(kk.get("row"))
        pc = prior_column(spec, sh, target_year) if sh in wb.sheetnames else None
        if not pc:
            continue
        try:
            pv = ev.cell(sh, f"{pc}{r}")
        except Exception:
            continue
        # THE INTERIM COMPARATIVE (owner 2026-09-10): a half-year balance
        # sheet compares to the last YEAR-END, so the model's annual column
        # is a second prior for the key row; the interim prior is tried
        # first (P&L and cash-flow rows compare to the same period last year)
        _acol = (spec.get("annual_prior_axis") or {}).get(sh)
        pv_a = None
        if _acol:
            try:
                pv_a = ev.cell(sh, f"{_acol}{r}")
            except Exception:
                pv_a = None
        _priors = [p_ for p_ in (pv, pv_a)
                   if isinstance(p_, (int, float)) and abs(p_) >= 0.5 and _sig_digits(p_) >= 3]
        if not _priors:
            continue
        # THE WALK'S SERVE WINS (run 256: an equity-statement row tied the
        # equity prior mid-row and offered 3,117.50 as 'total equity'):
        # when the reconciliation served the key row from the statement
        # (first claim, proven), that value IS the print
        e_srv = (served or {}).get((sh, r))
        if isinstance(e_srv, dict) and isinstance(e_srv.get("value"), (int, float)) \
                and int(e_srv.get("conf") or 0) >= 4 and e_srv.get("doc"):
            out[nm] = {"print": float(e_srv["value"]), "prior": float(pv),
                       "line": f"{e_srv.get('doc')} p{e_srv.get('page')} (served)"}
            continue
        from .numerics import kinship as _kin_p
        row_label = str(wb[sh].cell(r, 1).value or "")
        reads = {}
        for pv in _priors:
            for it in ledger.items:
                if it.doc in ban or getattr(it, "channel", "") == "prose":
                    continue
                nums = [n for n in (it.nums or []) if isinstance(n, (int, float))]
                if len(nums) < 2:
                    continue
                wide = len(nums) >= 4
                if wide and not _kin_p(str(it.label or ""), row_label):
                    continue                    # a wide row's pair position is uncertain: the label must confirm
                for f in _SCALES:
                    vals = [n / f for n in nums]
                    for j in range(1, len(vals)):
                        if _sig_digits(nums[j]) >= 4 and _ties_full_precision(vals[j], pv) \
                                and (nums[j] < 0) == (pv < 0):
                            # the current is the nearest EARLIER number of the prior's own magnitude
                            cur = next((vals[i] for i in range(j - 1, -1, -1)
                                        if abs(vals[i]) <= 30 * abs(pv) and abs(vals[i]) * 30 >= abs(pv)), None)
                            if cur is not None:
                                reads.setdefault(round(cur, 2), (cur, f"{it.doc} p{it.page} '{str(it.label)[:40]}'"))
                            break

            if reads:
                break         # the prior that tied is the row's prior
        if len(reads) == 1:
            cur, where = next(iter(reads.values()))
            out[nm] = {"print": float(cur), "prior": float(pv), "line": where}
        elif log is not None and reads:
            log(f"[run] key panel: '{nm}' prior {pv:,.2f} ties {len(reads)} different "
                f"printed lines — left to the pinned panel")
    return out


def merge_panel(built, pinned, log=None):
    """Runtime prior-tie entries win; a pinned entry only fills a key the
    tie could not build (and is flagged when it disagrees)."""
    out = dict(pinned or {})
    for nm, e in (built or {}).items():
        pin = (pinned or {}).get(nm)
        if pin and isinstance(pin.get("print"), (int, float)) \
                and abs(pin["print"] - e["print"]) > max(TOL_ABS, abs(e["print"]) * TOL_REL) \
                and log is not None:
            log(f"[run] key panel: '{nm}' pinned print {pin['print']:,.2f} disagrees with the "
                f"prior-tie print {e['print']:,.2f} ({e['line']}) — the prior tie wins")
        out[nm] = e
    return out


def _panel_or(panel, panel_path):
    return panel if panel is not None else _panel(panel_path)


def key_state(wb, spec, target_year, panel_path, panel=None):
    """Every panel key right now: [(name, ref, model value, print, tied)].
    Code's own count for the report (owner 2026-09-08: "i thought the key
    numbers are all written in the rules" — the report's 'X/14' line had
    been the brain's prose, copied from a prompt example)."""
    panel = _panel_or(panel, panel_path)
    ev = Evaluator(wb)
    out = []
    for kk in (spec.get("key_rows") or []):
        nm, sh, r = kk.get("name"), kk.get("sheet"), int(kk.get("row"))
        want = (panel.get(nm) or {}).get("print")
        tc = year_columns(spec, sh).get(str(target_year)) if sh in wb.sheetnames else None
        if not isinstance(want, (int, float)) or not tc:
            continue
        try:
            v = ev.cell(sh, f"{tc}{r}")
        except Exception:
            v = None
        ok = isinstance(v, (int, float)) and abs(v - want) <= max(TOL_ABS, abs(want) * TOL_REL)
        out.append((nm, f"{sh}!{tc}{r}", v, float(want), bool(ok)))
    return out


def key_snapshot(wb, spec, target_year, ledger, panel_path, panel=None):
    """Every key row whose value is PROVEN-PRINTED right now: equal to
    the pinned print, or itself a printed figure on a current statement
    face. -> {name: (ref, value, basis)}. Taken before stage 4, so a
    later write that moves a proven key off the print is caught."""
    panel = _panel_or(panel, panel_path)
    ev = Evaluator(wb)
    out = {}
    for kk in (spec.get("key_rows") or []):
        nm, sh, r = kk.get("name"), kk.get("sheet"), int(kk.get("row"))
        tc = year_columns(spec, sh).get(str(target_year)) if sh in wb.sheetnames else None
        if not tc:
            continue
        try:
            v = ev.cell(sh, f"{tc}{r}")
        except Exception:
            continue
        if not isinstance(v, (int, float)) or abs(v) < 1:
            continue
        want = (panel.get(nm) or {}).get("print")
        basis = None
        if isinstance(want, (int, float)) and abs(v - want) <= max(TOL_ABS, abs(want) * TOL_REL):
            basis = f"pinned print {want:,.2f}"
        else:
            where = _printed(ledger, v)
            if where:
                basis = f"printed on {where}"
        if basis:
            out[nm] = (f"{sh}!{tc}{r}", float(v), basis)
    return out


def key_violations(wb, spec, target_year, ledger, panel_path, snapshot, panel=None):
    """Keys that were proven-printed at the snapshot and now hold a
    DIFFERENT value that is printed nowhere. -> [(name, ref, then, now)].
    A key that moved to another printed figure is a definition
    question, not a violation; a key never proven is flagged elsewhere,
    never gated here."""
    if not snapshot:
        return []
    panel = _panel_or(panel, panel_path)
    ev = Evaluator(wb)
    out = []
    for nm, (ref, then, _basis) in snapshot.items():
        sh, coord = ref.split("!", 1)
        try:
            now = ev.cell(sh, coord)
        except Exception:
            continue
        if not isinstance(now, (int, float)):
            out.append((nm, ref, then, None))
            continue
        if abs(now - then) <= max(TOL_ABS, abs(then) * TOL_REL):
            continue
        want = (panel.get(nm) or {}).get("print")
        if isinstance(want, (int, float)) and abs(now - want) <= max(TOL_ABS, abs(want) * TOL_REL):
            continue
        if _printed(ledger, now):
            continue
        out.append((nm, ref, then, float(now)))
    return out



# -- THE PRINTED-SUBTOTAL LAW (owner, 2026-09-04): every subtotal the
# statements print — total current assets, non-current assets, total
# assets, total liabilities, equity — either ties or is backed out ------
_SUBTOTAL = re.compile(r"^=\s*(?:SUM\(([A-Z]{1,3})(\d+):([A-Z]{1,3})(\d+)\)"
                       r"|\+?([A-Z]{1,3}\d+(?:\s*[+]\s*[A-Z]{1,3}\d+)+))\s*$")


_GENERIC = {"total", "net", "and", "of", "the", "other", "others", "less", "sub",
            "subtotal", "amount", "amounts", "at", "end", "year", "for", "to", "in"}
# the nouns that decide identity; qualifiers (shareholders', group,
# consolidated) do not
_NOUNS = {"assets", "asset", "liabilities", "liability", "equity", "current",
          "noncurrent", "non", "income", "revenue", "cash", "profit", "loss",
          "borrowings", "debt", "receivables", "payables", "expenses", "costs",
          "earnings", "dividends"}


def subtotal_kin(a, b):
    """Two subtotal labels name the SAME thing only when their financial
    nouns agree (run-231: 'Total liabilities and shareholders' equity'
    pinned itself to the five-year 'Total assets' line on the word
    'total' alone — assets = L+E made the prior tie, the label did the
    rest; the back-out then broke the balance)."""
    from .numerics import norm_label
    ta = set(norm_label(a).split()) - _GENERIC
    tb = set(norm_label(b).split()) - _GENERIC
    if not ta or not tb:
        return False
    na, nb = ta & _NOUNS, tb & _NOUNS
    if na or nb:
        return na == nb
    return bool(ta & tb)


def printed_subtotals(wb, spec, target_year, ledger, max_row=300, priors=None):
    """Model subtotal rows (=SUM(range) / =A+B+C of same-column cells)
    whose PRINTED counterpart is identifiable on a current statement
    face: the face line's comparative ties the model's prior AND its
    label is kin to the row's. -> [{"name","sheet","row","print","prior"}].
    The prior-identity tie is the proof; the label is the tiebreak."""
    from .numerics import kinship, to_model_units
    from .stage2_join import ratify_page_scales
    if ledger is None:
        return []
    banned = _vintage_ban(ledger)
    faces = {(d, p): f for (d, p), f in ledger.faces.items() if f in ("pl", "bs", "cf")}
    # statement lines (2-3 numbers) AND multi-year summaries (up to 6:
    # CLP's HK-format balance sheet prints no 'Total assets' line — the
    # only printed total is the five-year table 238,644 | 233,713 | ...;
    # for a series the leading pair is current | prior)
    pool = [it for it in ledger.items
            if it.doc not in banned and (it.doc, it.page) in faces
            and 2 <= len([n for n in it.nums if isinstance(n, (int, float))]) <= 6]
    priors_all = []
    ev = Evaluator(wb)
    rows = []
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
            if not (isinstance(f, str) and _SUBTOTAL.match(f.replace("$", ""))):
                continue
            if tcol not in f:
                continue                  # not a same-column subtotal
            lab = ws.cell(r, 1).value
            if not lab:
                continue
            try:
                pv = ev.cell(sheet, f"{pcol}{r}")
            except Exception:
                continue
            if not isinstance(pv, (int, float)) or abs(pv) < 100:
                continue
            priors_all.append(pv)
            rows.append((sheet, r, str(lab), pv))
    if not rows:
        return []
    scales = ratify_page_scales(pool, list(priors or []) + priors_all)
    out = []
    for sheet, r, lab, pv in rows:
        hits = []
        for it in pool:
            sc = scales.get((it.doc, it.page))
            if not sc:
                # an unratified page still proves itself for THIS row when
                # a raw number ties the prior exactly (model units)
                if any(abs(abs(n) - abs(pv)) <= 0.6 for n in it.nums
                       if isinstance(n, (int, float))):
                    sc = 1.0
                else:
                    continue
            ns = [to_model_units(n, sc) for n in it.nums if isinstance(n, (int, float))]
            # comparative = the second of the (current, prior) pair; a note
            # ref may lead. In a multi-year series only the LEADING pair
            # is current | prior (the time-signature law: later slots
            # are older years)
            lead = 2 if len(ns) > 3 else len(ns) - 1
            for i in range(min(lead, len(ns) - 1)):
                cur, comp = ns[i], ns[i + 1]
                if i == 1 and abs(ns[0]) >= 100:
                    break          # a leading big number is current, not a note ref
                if abs(abs(comp) - abs(pv)) <= max(0.6, abs(pv) * 5e-4) \
                        and subtotal_kin(str(it.label or ""), lab):
                    sign = 1 if pv >= 0 else -1
                    hits.append(sign * abs(cur) if comp * pv >= 0 else -sign * abs(cur))
                    break
        if not hits:
            continue
        vals = sorted(hits)
        want = vals[len(vals) // 2]
        if any(abs(v - want) > max(1.0, abs(want) * 2e-3) for v in vals):
            continue                      # the faces disagree — no pin
        out.append({"name": f"printed subtotal '{lab.strip()[:30]}'", "sheet": sheet,
                    "row": r, "print": float(want), "prior": float(pv)})
    return out


def subtotal_tie(wb, spec, target_year, writer, ledger, log, priors=None):
    """Tie every printed subtotal (back-out into an unresolved component,
    orange, traceable) and return the tied rows for rule 2's register."""
    subs = printed_subtotals(wb, spec, target_year, ledger, priors=priors)
    if not subs:
        return {}
    panel = {d["name"]: {"print": d["print"], "prior": d["prior"]} for d in subs}
    keys = [{"name": d["name"], "sheet": d["sheet"], "row": d["row"]} for d in subs]

    def _mass():
        ev_m = Evaluator(wb)
        m = 0.0
        for c in (spec.get("check_rows") or []):
            sh = c.get("sheet")
            if sh not in wb.sheetnames:
                continue
            for _y, col in year_columns(spec, sh).items():
                try:
                    v = ev_m.cell(sh, f"{col}{int(c['row'])}")
                except Exception:
                    continue
                if isinstance(v, (int, float)):
                    m += abs(v)
        return m
    mass0 = _mass()
    n0 = len(writer.log.get("writes_all", []))
    n = key_tie(wb, spec, target_year, writer, None, log, ledger=ledger,
                panel=panel, keys=keys, max_delta_frac=0.10,
                absorbers="unproven")
    if n and _mass() > mass0 + 1.0:
        # TRANSACTIONAL (run-231: a subtotal back-out broke the balance):
        # a tie that worsens the model's own checks is undone
        for sh_w, co_w, old_w, _new in reversed(writer.log.get("writes_all", [])[n0:]):
            wb[sh_w][co_w] = old_w
        log(f"[run] printed subtotals: {n} back-out(s) UNDONE — they worsened "
            f"the model's checks ({mass0:,.0f} -> {_mass():,.0f} before undo)")
        n = 0
    ev = Evaluator(wb)
    tied = {}
    for d in subs:
        tc = year_columns(spec, d["sheet"]).get(str(target_year))
        try:
            v = ev.cell(d["sheet"], f"{tc}{d['row']}")
        except Exception:
            continue
        if isinstance(v, (int, float)) and abs(v - d["print"]) <= max(TOL_ABS, abs(d["print"]) * TOL_REL):
            tied[d["name"]] = (f"{d['sheet']}!{tc}{d['row']}", float(v),
                               f"printed subtotal {d['print']:,.1f}")
    log(f"[run] printed subtotals: {len(subs)} identified on the faces, "
        f"{len(tied)} tie ({n} backed out)")
    return tied
