"""THE ROLLOVER INVESTIGATION (owner teaching 2026-09-03).

An analyst who rolls a model forward looks at the first forecast year
and asks: does the change make sense? If 2025 actual came in 10% above
the old estimate, the new 2026 forecast should sit roughly 5-15% above
the old one. When the forecast moves far out of proportion — or flips
sign, or collapses — they go back to the desk and find the input that
did it. Sometimes the big change is genuine (rare); usually an input is
wrong. So this is not a gate that fails the run; it is the reminder,
the dossier, and the judgment:

  1. THE PROPORTIONALITY TEST (code) — every first-forecast formula row:
     actual surprise (2025A vs the analyst's 2025E) against the forecast
     move (new 2026E vs old 2026E). Strange = sign flip, collapse, or a
     move far beyond what the surprise explains.
  2. THE DOSSIER (code) — trace the forecast cell to the actual-year
     inputs this update changed, and PROBE each: put the analyst's old
     value back and measure how much of the swing disappears. That
     names the culprit with a number ("recovers 92% of the swing").
  3. THE JUDGMENT (brain) — one card per strange row: this input is
     wrong (revert it, red-flag it), the change is genuine (say why), or
     cannot tell (flag). Executed through the guarded tools.
  4. THE REPORT — headline rows' rollover check on page one, with the
     verdict of each investigation.

Run-228 lesson: 2026 operating profit fell 69% while the 2025 actual
missed by 4%; the fuel-clause driver 44.3 -> 2 explained it; the model
balanced and delivered. The old collapse test (near-zero or sign flip)
never fired on a -69% move; this test does.
"""
from .checks import forecast_columns, year_columns
from .evaluator import Evaluator

MIN_SIZE = 100.0        # rows below this in the old forecast are noise


def estimate_baseline(pre_wb, spec, target_year, max_row=300):
    """The analyst's own estimate for the target year and their first
    forecast year, per labelled row, evaluated BEFORE any write.
    -> {(sheet, row): (label, est_t, old_f)}"""
    ev = Evaluator(pre_wb)
    out = {}
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in pre_wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        fc = forecast_columns(spec, sheet, target_year)
        if not tcol or not fc:
            continue
        ws = pre_wb[sheet]
        for r in range(1, min(ws.max_row, max_row) + 1):
            lab = ws.cell(r, 1).value
            if lab is None or not str(lab).strip():
                continue
            fv = ws[f"{fc[0]}{r}"].value
            if not (isinstance(fv, str) and fv.startswith("=")):
                continue                  # value cells are others' business
            vals = []
            for c in (tcol, fc[0]):
                try:
                    v = ev.cell(sheet, f"{c}{r}")
                except Exception:
                    v = None
                vals.append(v if isinstance(v, (int, float)) else None)
            if vals[1] is not None:
                out[(sheet, r)] = (str(lab).strip()[:40], vals[0], vals[1])
    return out


def strange(est_t, act_t, old_f, new_f):
    """The owner's proportionality test. -> (is_strange, reason)."""
    if old_f is None or new_f is None:
        return False, ""
    if abs(old_f) < MIN_SIZE:
        # APPEARED FROM ZERO (run-232 D&A autopsy): the analyst's residual
        # 'Others' forecast 0; after the update it forecast 4,636 — a
        # wrong China D&A absorbed by the residual and rolled into every
        # year. The most suspicious move of all was invisible to a
        # percentage test.
        if abs(new_f) >= 10 * MIN_SIZE:
            return True, (f"APPEARED FROM ZERO: old forecast {old_f:,.0f} -> "
                          f"new {new_f:,.0f}")
        return False, ""
    fmove = (new_f - old_f) / abs(old_f)
    if new_f * old_f < 0 and abs(new_f) > 0.2 * abs(old_f):
        return True, f"SIGN FLIP: old forecast {old_f:,.0f} -> new {new_f:,.0f}"
    if abs(new_f) < 0.02 * abs(old_f):
        return True, f"COLLAPSED: old forecast {old_f:,.0f} -> new {new_f:,.0f}"
    surprise = None
    if isinstance(est_t, (int, float)) and isinstance(act_t, (int, float)) \
            and abs(est_t) >= 1:
        surprise = (act_t - est_t) / abs(est_t)
    # the owner's rule: the actual came in 10% above the estimate -> the
    # rolled forecast should sit roughly 5-15% above the old one. A move
    # AGAINST the surprise, or far beyond it, is strange.
    if surprise is not None and abs(surprise) >= 0.02 \
            and fmove * surprise < 0 and abs(fmove) > 0.10:
        return True, (f"AGAINST THE ACTUAL: the actual surprised by "
                      f"{surprise:+.0%} but the forecast moved {fmove:+.0%} "
                      f"({old_f:,.0f} -> {new_f:,.0f})")
    allowed = 0.50 if surprise is None else max(0.25, 3 * abs(surprise) + 0.10)
    if abs(fmove) > allowed:
        s = f"{surprise:+.0%}" if surprise is not None else "n/a"
        return True, (f"OUT OF PROPORTION: forecast moved {fmove:+.0%} "
                      f"({old_f:,.0f} -> {new_f:,.0f}) while the actual "
                      f"surprised by {s}")
    return False, ""


def rollover_anomalies(wb, spec, target_year, base, cap=12, key_rows=()):
    """-> [dict(sheet,row,label,est_t,act_t,old_f,new_f,reason,size)]
    sorted by the size of the move, capped; key rows always kept."""
    ev = Evaluator(wb)
    keyset = {(k["sheet"], int(k["row"])) for k in (key_rows or [])}
    out = []
    for (sheet, r), (label, est_t, old_f) in base.items():
        if sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        fc = forecast_columns(spec, sheet, target_year)
        if not tcol or not fc:
            continue
        fv = wb[sheet][f"{fc[0]}{r}"].value
        if not (isinstance(fv, str) and fv.startswith("=")):
            continue
        try:
            act_t = ev.cell(sheet, f"{tcol}{r}")
            new_f = ev.cell(sheet, f"{fc[0]}{r}")
        except Exception:
            continue
        if not isinstance(new_f, (int, float)):
            continue
        act_t = act_t if isinstance(act_t, (int, float)) else None
        ok, why = strange(est_t, act_t, old_f, new_f)
        if ok:
            out.append({"sheet": sheet, "row": r, "label": label,
                        "est_t": est_t, "act_t": act_t, "old_f": old_f,
                        "new_f": new_f, "reason": why,
                        "size": abs(new_f - old_f),
                        "key": (sheet, r) in keyset})
    out.sort(key=lambda d: (not d["key"], -d["size"]))
    return out[:cap]


def input_is_proven(served, sheet, coord, value, flags=(), wb=None, old=None):
    """PROVEN IS PROTECTED, for any input cell:
    - a served cell whose evidence tied the prior and landed clean; or
    - a constants composite (=-1860+194) whose EVERY literal equals a
      proven served figure (the machinery's rewrite from proven
      components — run-229: net finance costs had no serve record of
      its own and was reverted to last year's composite); or
    - a rewrite PROVEN BY WHAT IT CHANGED (run-233 autopsy): cash
      '=4976+23' became '=3905+23' — 3,905 is the printed year-end cash,
      the '+23' is the analyst's own carried adjustment. A carried
      literal needs no proof; only the literals the update CHANGED do.
      With the old formula in hand, the test is on the changed literals
      alone (the '+23' cannot be what the rollover reverts anyway). The
      machinery's own rewrite note ('COMPOSITE REWRITE (constants law)')
      is the same proof: each literal was tied to its comparative and
      replaced by the current figure before the write landed."""
    import re as _re
    from .writegate import is_proven
    ref = f"{sheet}!{coord}"
    if wb is None and ref in set(flags or ()):
        return False                  # without the workbook the flag list (both colours) is all there is
    if wb is not None:
        # RED = uncertain (unproven); ORANGE = derived from proven parts
        # (run-229: the writer's flag list holds both colours — the
        # orange composite read as 'flagged' and lost its protection)
        try:
            rgb = str(wb[sheet][coord].fill.fgColor.rgb or "")
            if rgb.endswith("FFC7CE"):
                return False
        except Exception:
            pass
    try:
        rr = int("".join(ch for ch in coord if ch.isdigit()))
    except ValueError:
        return False
    e = (served or {}).get((sheet, rr))
    if isinstance(e, dict) and is_proven(e):
        ev_ = e.get("value")
        if wb is not None and isinstance(ev_, (int, float)):
            # the proof is of THAT figure: a back-out written over the row (=(14035)-(3863))
            # no longer holds it and is not proven by it (reviewer 2026-09-15)
            try:
                from .evaluator import Evaluator
                cur_ = Evaluator(wb).cell(sheet, coord)
            except Exception:  # noqa: BLE001
                cur_ = None
            if isinstance(cur_, (int, float)) and abs(cur_ - ev_) > max(0.6, abs(ev_) * 5e-4):
                return False
        return True
    if isinstance(value, str) and value.startswith("=") \
            and not _re.search(r"[A-Z]{1,3}\d+", value.replace("$", "")):
        lits = [float(x) for x in _re.findall(r"\d+(?:\.\d+)?", value)]
        if not lits:
            return False
        if wb is not None:
            try:
                note = str(getattr(wb[sheet][coord].comment, "text", "") or "")
                if "COMPOSITE REWRITE (constants law)" in note:
                    return True
            except Exception:
                pass
        if isinstance(old, str) and old.startswith("=") \
                and not _re.search(r"[A-Z]{1,3}\d+", old.replace("$", "")):
            carried = [float(x) for x in _re.findall(r"\d+(?:\.\d+)?", old)]
            changed = []
            for l in lits:
                hit = next((i for i, cv in enumerate(carried)
                            if abs(cv - l) <= 1e-9), None)
                if hit is None:
                    changed.append(l)
                else:
                    carried.pop(hit)
            if changed:
                lits = changed
        proven_vals = [abs(float(v["value"])) for v in (served or {}).values()
                       if isinstance(v, dict) and is_proven(v)
                       and isinstance(v.get("value"), (int, float))]
        return all(any(abs(abs(l) - pv) <= max(0.6, pv * 1e-3) for pv in proven_vals)
                   for l in lits)
    return False


def dossier(wb, spec, target_year, sheet, row, old_f, writes_all, leaf_fn,
            served=None, max_inputs=5, flags=()):
    """The changed actual-year inputs this forecast consumes, each PROBED:
    put the analyst's pre-update value back and measure the share of the
    swing that disappears. -> [dict(sheet, coord, old, cur, share, prov,
    proven)] sorted by share.

    PROVEN IS PROTECTED (run-229 autopsy: the brain answered 'revert' on
    two proven actuals — bank loans 9,673 and net finance costs, both
    exactly the by-hand key — and the tool obeyed, breaking OP/NP/EPS).
    A proven actual (its evidence tied the prior, landed clean) is never
    offered for reversion: if a proven actual drives a strange forecast,
    the forecast's own driver or a frozen assumption is what is stale,
    and that is the analyst's call. Only UNPROVEN inputs can be
    reverted (= held at the analyst's value, red)."""
    fc = forecast_columns(spec, sheet, target_year)
    if not fc:
        return []
    target = f"{fc[0]}{row}"
    try:
        new_f = Evaluator(wb).cell(sheet, target)
    except Exception:
        return []
    if not isinstance(new_f, (int, float)) or old_f is None:
        return []
    first_old = {}
    for w in writes_all or []:
        s, c, old = w[0], w[1], w[2]
        first_old.setdefault((s, c), old)
    # the model's own order, deduped — a SET's order is the interpreter's, and
    # the card shows the head of this list (2026-09-16: two runs of the same
    # ledger offered different 5th options on the ROLLOVER cards)
    leaves = list(dict.fromkeys(leaf_fn(sheet, target)))
    # THE RESIDUAL DISCOUNT (run-229 autopsy): the model's own residual
    # rows (=total - SUM(parts), 'Others') absorb whatever does not add
    # up, and the forecast copies the residual forward — so reverting
    # almost ANY input "recovers the swing" through them. The probe is
    # therefore run twice: as is, and with every residual row frozen at
    # its current value; the second share is the honest one and ranks.
    residuals = residual_cells(wb, spec, target_year)
    # the residuals' CURRENT values (before any probe): what they hold
    # with the update's inputs in place — frozen there during probe 2
    res_now = {}
    for (rs, rc) in residuals:
        if (rs, rc) == (sheet, target):
            continue
        try:
            val = Evaluator(wb).cell(rs, rc)
        except Exception:
            continue
        if isinstance(val, (int, float)):
            res_now[(rs, rc)] = val
    cands = []
    for (s, c) in leaves:
        if (s, c) not in first_old:
            continue
        old, cur = first_old[(s, c)], wb[s][c].value
        if old == cur:
            continue
        wb[s][c].value = old
        try:
            probe = Evaluator(wb).cell(sheet, target)
        except Exception:
            probe = None
        frozen = []
        try:
            for (rs, rc), val in res_now.items():
                if (rs, rc) == (s, c):
                    continue
                frozen.append((rs, rc, wb[rs][rc].value))
                wb[rs][rc].value = val
            try:
                probe_x = Evaluator(wb).cell(sheet, target) if frozen else probe
            except Exception:
                probe_x = None
        finally:
            for rs, rc, f in frozen:
                wb[rs][rc].value = f
            wb[s][c].value = cur
        share = share_x = 0.0
        if isinstance(probe, (int, float)) and abs(old_f - new_f) > 1e-9:
            share = (probe - new_f) / (old_f - new_f)
        if isinstance(probe_x, (int, float)) and abs(old_f - new_f) > 1e-9:
            share_x = (probe_x - new_f) / (old_f - new_f)
        prov = ""
        try:
            rr = int("".join(ch for ch in c if ch.isdigit()))
        except ValueError:
            rr = None
        e = (served or {}).get((s, rr)) if rr is not None else None
        if isinstance(e, dict):
            prov = (str(e.get("note") or e.get("line") or "")[:70])
        proven = input_is_proven(served, s, c, cur, (), wb, old=old)
        cands.append({"sheet": s, "coord": c, "old": old, "cur": cur,
                      "share": share, "share_x": share_x,
                      "via_residual": bool(residuals) and abs(share - share_x) > 0.15,
                      "prov": prov, "proven": proven})
    cands.sort(key=lambda d: (-d["share_x"], -d["share"], d["sheet"], _row_of(d["coord"]), d["coord"]))
    return cands[:max_inputs]


def _row_of(coord):
    """The row number of a coordinate — the model's own order within a sheet."""
    import re as _re2
    m = _re2.match(r"^[A-Z]{1,3}(\d+)$", str(coord))
    return int(m.group(1)) if m else 0


def residual_cells(wb, spec, target_year, max_row=300):
    """The model's own residual rows in the target column (=A-B-C...,
    =X-SUM(...)): the plug-meter pattern. -> [(sheet, coord)]."""
    import re as _re
    pat = _re.compile(r"^=\+?[A-Z]{1,3}\d+\s*-")
    out = []
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        if not tcol:
            continue
        ws = wb[sheet]
        for r in range(1, min(ws.max_row, max_row) + 1):
            f = ws[f"{tcol}{r}"].value
            if isinstance(f, str) and pat.match(f.replace(" ", "")):
                out.append((sheet, f"{tcol}{r}"))
    return out


def _fmt(v):
    if isinstance(v, (int, float)):
        return f"{v:,.1f}" if abs(v) < 100 else f"{v:,.0f}"
    return str(v)[:24] if v is not None else "—"


def render(anom, cands):
    """The card text + answer key for one strange row."""
    est_t, act_t = anom["est_t"], anom["act_t"]
    sur = ""
    if isinstance(est_t, (int, float)) and isinstance(act_t, (int, float)) and abs(est_t) >= 1:
        sur = f" ({(act_t - est_t) / abs(est_t):+.0%})"
    lines = [f"CARD ROLLOVER {anom['sheet']}!{anom['row']} {anom['label']!r}",
             f"  target year: analyst's estimate {_fmt(est_t)} -> actual {_fmt(act_t)}{sur}",
             f"  first forecast year: old {_fmt(anom['old_f'])} -> new "
             f"{_fmt(anom['new_f'])}  ⚠ {anom['reason']}",
             "  inputs this update changed that this forecast consumes — probe: "
             "putting the analyst's old value back recovers:"]
    letters = "ABCDE"
    options = {}
    for i, c in enumerate(cands):
        L = letters[i]
        lines.append(f"    {L}: {c['sheet']}!{c['coord']} {_fmt(c['old'])} -> "
                     f"{_fmt(c['cur'])}  ⇒ recovers {c['share']:.0%} of the swing"
                     + (f" ({c.get('share_x', c['share']):.0%} with the model's residual "
                        "rows frozen — recovery through a residual is not evidence)"
                        if c.get("via_residual") else "")
                     + (f"  [{c['prov']}]" if c["prov"] else "")
                     + ("  ✔ PROVEN actual (its evidence ties the prior) — never "
                        "reverted; if the swing is wrong, the forecast's own "
                        "driver/assumption is stale (flag it)"
                        if c.get("proven") else "  (unproven — may be reverted)"))
        if c.get("proven"):
            continue
        options[f"revert:{L}"] = ("rollover_revert", {
            "cell": f"{c['sheet']}!{c['coord']}", "old": c["old"],
            "forecast": f"{anom['sheet']}!{anom['row']}",
            "why": (f"rollover card: {c['sheet']}!{c['coord']} "
                    f"{_fmt(c['cur'])} explains {c['share']:.0%} of a "
                    f"{anom['reason'][:40]} — judged wrong, restored to the "
                    "analyst's value, red for review")})
    if not cands:
        lines.append("    (no changed input found under this row — the "
                     "move comes from formulas or frozen assumptions)")
    lines.append("  answers: " + ", ".join(
        [f"revert:{letters[i]} (input wrong — restore the analyst's value, red-flag)"
         for i in range(len(cands)) if not cands[i].get("proven")]
        + ["justified (the change is genuine — the disclosure supports it)",
           "not_sure (flag the forecast for the analyst)"]))
    fc_ref = f"{anom['sheet']}!{anom['row']}"
    options["justified"] = ("verdict", {
        "items": [fc_ref], "verdict": "JUSTIFIED",
        "why": "rollover card: the change is genuine per the disclosure (brain)"})
    options["not_sure"] = ("rollover_flag", {
        "forecast": fc_ref, "why": f"rollover check: {anom['reason'][:120]}"})
    return "\n".join(lines), options, "not_sure"


def report_lines(wb, spec, target_year, base, key_rows, verdicts):
    """Page-one rollover check for the key rows + every strange row."""
    ev = Evaluator(wb)
    done = {}
    for v in verdicts or []:
        ref, _, rest = str(v).partition(": ")
        done[ref] = rest[:80]
    out = []
    keyset = [(k["sheet"], int(k["row"]), k.get("name", "")) for k in (key_rows or [])]
    anoms = {(a["sheet"], a["row"]): a for a in
             rollover_anomalies(wb, spec, target_year, base, cap=40, key_rows=key_rows)}
    seen = set()
    for sheet, r, name in keyset + [(a["sheet"], a["row"], a["label"]) for a in anoms.values()]:
        if (sheet, r) in seen or (sheet, r) not in base:
            continue
        seen.add((sheet, r))
        label, est_t, old_f = base[(sheet, r)]
        tcol = year_columns(spec, sheet).get(str(target_year))
        fc = forecast_columns(spec, sheet, target_year)
        try:
            act_t = ev.cell(sheet, f"{tcol}{r}")
            new_f = ev.cell(sheet, f"{fc[0]}{r}")
        except Exception:
            continue
        a = anoms.get((sheet, r))
        fcol = fc[0]
        verdict = done.get(f"{sheet}!{fcol}{r}") or done.get(f"{sheet}!{r}") or ""
        out.append((f"{sheet}!{fcol}{r}", name or label, est_t, act_t, old_f, new_f,
                    (a["reason"] if a else "in proportion"), verdict))
    return out
