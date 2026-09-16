"""THE OBJECTIVES, MEASURED (owner 2026-09-16: "the card is an issue — there
is no thinking in preparing the cards"). What is left here is code's half of
the ending: the balance checks in every year, the keys against the print,
cash and total assets under water — measured, never judged — plus the
snapshot/restore a trial runs on and the last resort's plug site. The
judging moved to pipeline/review.py, where the brain reads the model
itself.
"""
import re

from .checks import CHECK_TOL, forecast_columns, year_columns
from .evaluator import Evaluator


def snapshot(loop):
    """What a trial may disturb: the write journal mark, the provenance
    (served), the locks, the sense rulings. Previews and take-backs restore
    all four (audit 2026-09-15: a preview un-served and unlocked proven
    movers; a taken-back pick left its ruling in the memory)."""
    w = loop.writer
    return (len(w.log.get("writes_all", [])), dict(loop.served or {}), set(getattr(w, "locked", ())),
            dict(w.log.get("rulings", {}) or {}), list(w.log.get("plugs", []) or []))


def restore(loop, snap):
    """Unwind every write since the snapshot through the writer (value AND
    look), then put back what the run believed: served, locks, rulings."""
    w = loop.writer
    mark, served0, locked0, rulings0, plugs0 = snap
    journal = w.log.get("style_journal", [])[mark:]
    for sh_w, co_w, old_w, _new in reversed(list(w.log.get("writes_all", []))[mark:]):
        style = next((j for j in journal if (j[0], j[1]) == (sh_w, co_w)), (sh_w, co_w, "", None, False))
        w.take_back(sh_w, co_w, old_w, style)
    if isinstance(loop.served, dict):
        loop.served.clear(); loop.served.update(served0)
    if hasattr(w, "locked"):
        w.locked.clear(); w.locked.update(locked0)
    if "rulings" in w.log:
        w.log["rulings"].clear(); w.log["rulings"].update(rulings0)
    if "plugs" in w.log:
        w.log["plugs"][:] = plugs0


def _fault(loop, text):
    """An objective the measure could not take is SAID, never swallowed
    (run 34935869107: the key objectives vanished from the ending without
    a word). Kept on the loop; run_ending logs each new one once."""
    faults = loop.__dict__.setdefault("objective_faults", [])
    if text not in faults:
        faults.append(text)


def broken_objectives(loop, keys_before, key_panel, panel_path, quiet=False):
    """-> [(kind, sheet, coord, amount, text)] largest first.
    kind: check (actual year) | forecast-check | key (rule 2 / off the print).
    quiet: a trial measure (plugs lifted) says nothing about cells it cannot evaluate."""
    wb, spec, ty = loop.wb, loop.spec, int(loop.ty)
    out = []
    ev = Evaluator(wb)
    say = (lambda t: None) if quiet else (lambda t: _fault(loop, t))
    for c in (spec.get("check_rows") or []):
        sheet, row = c.get("sheet"), int(c.get("row"))
        if sheet not in wb.sheetnames:
            continue
        expect = float(c.get("expect", 0))
        tcol = year_columns(spec, sheet).get(str(ty))
        cols = [(tcol, "check")] if tcol else []
        cols += [(fc, "forecast-check") for fc in (forecast_columns(spec, sheet, ty) or [])]
        for col, kind in cols:
            try:
                v = ev.cell(sheet, f"{col}{row}")
            except Exception as e:  # noqa: BLE001
                say(f"check {sheet}!{col}{row} cannot be evaluated: {e!r}")
                continue
            if isinstance(v, (int, float)) and abs(v - expect) > CHECK_TOL:
                out.append((kind, sheet, f"{col}{row}", float(v - expect),
                            f"balance check {sheet}!{col}{row} computes {v:,.1f} (should be {expect:,.0f})"))
    from .keytie import key_violations, key_state
    try:
        for nm, ref, then, now in key_violations(wb, spec, ty, loop.ledger, panel_path, keys_before, panel=key_panel):
            sh, co = ref.split("!", 1)
            amt = (now if isinstance(now, (int, float)) else 0.0) - then
            out.append(("key", sh, co, float(amt), f"key '{nm}' at {ref} was proven-printed {then:,.1f}, now {now if now is None else f'{now:,.1f}'} — printed nowhere"))
    except Exception as e:  # noqa: BLE001
        _fault(loop, f"key violations unavailable: {e!r}")
    try:
        # key_state speaks five fields (name, ref, value, print, tied); run
        # 34935869107 unpacked four, raised on every round, and the keys
        # were never an objective — the fault is now said, never swallowed.
        # A key the tie already JUDGED (confirmed by the bridge, or a
        # definition question for the analyst) is not re-raised every round.
        judged = set(loop.writer.log.get("key_verdicts", {}) or {})
        for nm, ref, got, want, ok in key_state(wb, spec, ty, panel_path, panel=key_panel):
            if ok or not isinstance(got, (int, float)) or nm in judged:
                continue
            sh, co = ref.split("!", 1)
            if any(o[1] == sh and o[2] == co for o in out):
                continue
            out.append(("key", sh, co, float(got - want), f"key '{nm}' at {ref} computes {got:,.1f} vs printed {want:,.1f}"))
    except Exception as e:  # noqa: BLE001
        _fault(loop, f"key objectives unavailable: {e!r}")
    try:
        out += sanity_breaks(loop)
    except Exception as e:  # noqa: BLE001
        _fault(loop, f"sanity objectives unavailable: {e!r}")
    out.sort(key=lambda o: -abs(o[3]))
    return out


def sanity_rows(loop):
    """The rows that must never go negative: cash (the report's own role) and
    total assets (a key row). -> {name: (sheet, row)}"""
    out = {}
    try:
        from .reportpage import resolve_rows
        rows, _primary = resolve_rows(loop.wb, loop.spec, int(loop.ty), getattr(loop, "period", None) or "FY")
        if rows.get("cash"):
            out["cash"] = (rows["cash"][0], int(rows["cash"][1]))
    except Exception as e:  # noqa: BLE001
        _fault(loop, f"cash row not resolved for the sanity objective: {e!r}")
    for kk in (loop.spec.get("key_rows") or []):
        nm = str(kk.get("name") or "").lower()
        if nm == "cash" and "cash" not in out:
            out["cash"] = (kk["sheet"], int(kk["row"]))
        if "total assets" in nm:
            out["total assets"] = (kk["sheet"], int(kk["row"]))
    return out


def _sanity_scan(loop):
    """Every cash / total-assets cell from the actual period on, in period order.
    -> [(name, sheet, coord, period_label, value)]"""
    out = []
    ev = Evaluator(loop.wb)
    ty = int(loop.ty)
    for nm, (sh, r) in sanity_rows(loop).items():
        if sh not in loop.wb.sheetnames:
            continue
        yc = year_columns(loop.spec, sh)
        cols = [(yc.get(str(ty)), str(ty))] + sorted(((c, y) for y, c in yc.items() if str(y).isdigit() and int(y) > ty), key=lambda x: int(x[1]))
        for col, year in cols:
            if not col:
                continue
            try:
                v = ev.cell(sh, f"{col}{r}")
            except Exception:
                continue
            if isinstance(v, (int, float)):
                out.append((nm, sh, f"{col}{r}", year, float(v)))
    return out


def sanity_breaks(loop, horizon=2):
    """Cash or total assets negative in the actual period or the next two
    periods (owner 2026-09-15: a normal roll-forward may go negative later
    on the analyst's own assumptions — that is flagged, not fixed).
    -> [("sanity", sheet, coord, value, text)]"""
    out = []
    seen = {}
    for nm, sh, coord, year, v in _sanity_scan(loop):
        k = seen.get(nm, 0)
        seen[nm] = k + 1
        if k > horizon:
            continue
        if v < -0.5:
            out.append(("sanity", sh, coord, v, f"{nm} goes negative in {year}: {v:,.0f} at {sh}!{coord}"))
    return out


def sanity_watch(loop, horizon=2):
    """Negatives beyond the horizon: for the analyst, never fixed. -> [text]"""
    out, seen = [], {}
    for nm, sh, coord, year, v in _sanity_scan(loop):
        k = seen.get(nm, 0)
        seen[nm] = k + 1
        if k > horizon and v < -0.5:
            out.append(f"{nm} goes negative in {year} ({v:,.0f} at {sh}!{coord}) — beyond the next two periods: your assumptions, your call")
    return out


def measure(loop, keys_before, key_panel, panel_path, lift_plugs=True):
    """One reading of the objectives — balance mass across every year, the
    keys off the print, cash/assets negatives — with the plug rows lifted for
    the balance and the keys (owner 2026-09-15: a plug masks a consequence).

    THE SANITY OBJECTIVE IS READ AS THE VERDICT READS IT — plugs live
    (reviewer 2026-09-16): check_mass, which takes the pick back, measures
    the model as it stands, so a preview taken with the plugs lifted showed
    the brain a cash break the verdict did not see, or hid one it did. One
    measurement for both. -> dict"""
    wb, writer = loop.wb, loop.writer
    lifted = []
    if lift_plugs:
        for ref in list(writer.log.get("plugs") or []):
            try:
                sh, co = ref.split("!", 1)
                if sh in wb.sheetnames:
                    lifted.append((sh, co, wb[sh][co].value))
                    wb[sh][co].value = 0
            except Exception:
                pass
    try:
        objs = broken_objectives(loop, keys_before, key_panel, panel_path, quiet=True)
        balance = sum(abs(o[3]) for o in objs if o[0] in ("check", "forecast-check"))
        keys_off = [(re.search(r"key '(.+?)' at ", o[4]).group(1) if re.search(r"key '(.+?)' at ", o[4]) else o[2]) for o in objs if o[0] == "key"]
    finally:
        for sh, co, v in lifted:
            wb[sh][co].value = v
    san = sanity_breaks(loop)              # the model as the verdict will measure it
    return {"balance": balance, "keys_off": keys_off, "sanity": san}


def _plug_here(loop, sheet, coord, log):
    """The last resort, in the period that is broken: the terminal ladder
    for an actual-period check, the forecast residual row of THAT year for
    a forecast one (the ladder reads only the actual period's checks, so a
    forecast break answered 'plug' was left to whichever forecast year the
    repair suite plugged next)."""
    from .forecast_balance import plug_period
    if plug_period(loop, sheet, coord, log):
        return
    from .orchestrator import terminal_ladder
    terminal_ladder(loop, log)
