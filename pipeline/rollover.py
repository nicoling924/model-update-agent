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
    if old_f is None or new_f is None or abs(old_f) < MIN_SIZE:
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


def dossier(wb, spec, target_year, sheet, row, old_f, writes_all, leaf_fn,
            served=None, max_inputs=5):
    """The changed actual-year inputs this forecast consumes, each PROBED:
    put the analyst's pre-update value back and measure the share of the
    swing that disappears. -> [dict(sheet, coord, old, cur, share, prov)]
    sorted by share."""
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
    leaves = set(leaf_fn(sheet, target))
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
        finally:
            wb[s][c].value = cur
        share = 0.0
        if isinstance(probe, (int, float)) and abs(old_f - new_f) > 1e-9:
            share = (probe - new_f) / (old_f - new_f)
        prov = ""
        if served:
            try:
                rr = int("".join(ch for ch in c if ch.isdigit()))
                e = served.get((s, rr))
                if isinstance(e, dict):
                    prov = (str(e.get("note") or e.get("line") or "")[:70])
            except ValueError:
                pass
        cands.append({"sheet": s, "coord": c, "old": old, "cur": cur,
                      "share": share, "prov": prov})
    cands.sort(key=lambda d: -d["share"])
    return cands[:max_inputs]


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
                     + (f"  [{c['prov']}]" if c["prov"] else ""))
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
         for i in range(len(cands))]
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
