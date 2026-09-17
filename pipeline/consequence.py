"""WHAT A TRIAL RUNS ON (owner 2026-09-16: "the card is an issue — there is
no thinking in preparing the cards"). The card machinery is gone and the
objectives are measured in ONE place now — review._metrics, the same
reading the brain is shown, `try` diffs and the last resort reads. What
stays here is the state a trial disturbs and puts back, the fault channel
that says an objective it could not take, the model's own cash/assets rows,
and the plug site of the period that is broken.
"""


from copy import deepcopy

def snapshot(loop):
    """What a trial may disturb: the write journal mark, the provenance
    (served), the locks, the sense rulings, the key verdicts and the flags.
    A trial restores all of them (audit 2026-09-15: a preview un-served and
    unlocked proven movers, and left a taken-back ruling in the memory;
    reviewer 2026-09-16: a trial's repair round also wrote key_verdicts and
    flag_ref entries that survived the restore, so a preview changed what the
    RUN believed about its keys)."""
    w = loop.writer
    return (len(w.log.get("writes_all", [])), deepcopy(loop.served or {}), set(getattr(w, "locked", ())),
            deepcopy(w.log.get("rulings", {}) or {}), list(w.log.get("plugs", []) or []),
            deepcopy(w.log.get("key_verdicts", {}) or {}), list(w.log.get("flags", []) or []),
            deepcopy(w.log.get("change_records", [])),
            {name: deepcopy(loop.__dict__.get(name, default))
             for name, default in (("_map_written", {}), ("_map_cells", 0), ("_map_refused", []))})


def restore(loop, snap):
    """Unwind every write since the snapshot through the writer (value AND
    look), then put back what the run believed: served, locks, rulings."""
    w = loop.writer
    mark, served0, locked0, rulings0, plugs0, verdicts0, flags0, changes0, mapped0 = snap
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
    if "key_verdicts" in w.log:
        w.log["key_verdicts"].clear(); w.log["key_verdicts"].update(verdicts0)
    if "flags" in w.log:
        w.log["flags"][:] = flags0
    w.log["change_records"] = changes0
    loop.__dict__.update(mapped0)


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
    # THE CHECK THE BRAIN NAMED, AND NO OTHER (owner 2026-09-16): `plug` ran the
    # whole ladder, so answering it for one check reached into every failing
    # check in the model — cells the brain had never looked at. The run's own
    # last resort, at the exit, is what takes whatever is still open.
    import re as _re
    terminal_ladder(loop, log, only=(sheet, int(_re.sub(r"[A-Z$]", "", str(coord)))))
