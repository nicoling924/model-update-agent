"""WHAT A TRIAL RUNS ON (owner 2026-09-16: "the card is an issue — there is
no thinking in preparing the cards"). The card machinery is gone and the
objectives are measured in ONE place now — review._metrics, the same
reading the brain is shown, `try` diffs and the last resort reads. What
stays here is the state a trial disturbs and puts back, the fault channel
that says an objective it could not take, the model's own cash/assets rows,
and the plug site of the period that is broken.
"""


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
