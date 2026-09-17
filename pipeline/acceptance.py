"""The owner's three outcomes, independently recorded from delivery status.

Absence of evidence is unmeasured. A numerical tie is an arithmetic test;
source definitions and rollover reasonableness still need an analyst review.
"""
from .checks import scorecard
from .keytie import key_state, matches_print
from .sensecheck import headline_deltas, suspicious


def assess(loop, pre_wb, panel=None, panel_path=None):
    card = scorecard(loop.wb, loop.spec, int(loop.ty), loop.served, loop.writer.log.get("flags"))
    checks = card["checks"]
    # Keep inherited failures visible: 'balance every year' includes history.
    balance_status = "unmeasured" if not checks else (
        "fail" if any(c["status"] != "PASS" for c in checks) or card["cycles"] else "pass")
    keys = []
    for name, ref, got, want, ok in key_state(loop.wb, loop.spec, int(loop.ty), panel_path, panel=panel):
        measured = isinstance(got, (int, float)) and isinstance(want, (int, float))
        # The legacy key count allows a whole unit of error even for EPS.
        # Reuse the evidence precision rule, retaining the signed identity.
        tied = matches_print(got, want)
        keys.append({"name": name, "ref": ref, "actual": got, "printed": want,
                     "status": ("pass" if tied else "fail") if measured else "unmeasured"})
    named = loop.spec.get("key_rows") or []
    expected = {k.get("name") for k in named} | set(panel or {})
    represented = {k["name"] for k in keys}
    missing = sorted(str(n) for n in expected - represented)
    key_status = "fail" if any(k["status"] == "fail" for k in keys) else (
        "unmeasured" if not keys or missing or any(k["status"] == "unmeasured" for k in keys) else "pass")
    errors = []
    try:
        deltas = headline_deltas(loop.wb, pre_wb, loop.spec, int(loop.ty)) if pre_wb is not None else []
        swings = suspicious(deltas)
    except Exception as exc:
        deltas, swings = [], []
        errors.append(str(exc))
    rollover_status = "unmeasured" if not deltas else ("review_required" if swings else "no_detected_anomaly")
    return {
        "balance": {"status": balance_status, "checks": checks, "cycles": card["cycles"]},
        "keys": {"status": key_status, "checks": keys, "missing": missing,
                 "scope": "arithmetic against verified key panel; definitions require independent review"},
        "rollover": {"status": rollover_status, "checks": deltas, "suspicious": swings, "errors": errors,
                     "scope": "comparison with original analyst forecasts; no anomaly is not independent approval"},
        "calculation": "offline evaluator; full Excel recalculation has not been certified",
    }
