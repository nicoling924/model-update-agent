"""The reclassification back-out recipe (owner ruling 2026-08-30).

Reclassification = the TOTAL is unchanged but the item classification
changed. The AGENT judges which segments truly survived (name AND
prior-year figure both unchanged); THIS module executes the estimate so
the arithmetic cannot be wrong:

- mapped segments keep their disclosed actuals;
- every other segment = prior year x the total's growth (formula);
- the SMALLEST backed-out segment is instead the plug
  = total - all other segments (formula), so the table always sums to
  the disclosed actual total;
- a plug that turns negative or swings wildly vs its own prior year is
  delivered (the total must tie) but escalated RED — a weird plug
  usually means a mapped segment is wrong.

The company's re-cut category figures are ignored except their total —
the model is never re-based. Applies to every segment table that sums
to a disclosed total, each with its own total's growth rate.
"""

WILD_MOVE = 0.5      # plug vs its own prior: beyond this is a red flag


def plan_backout(segments, total_actual, total_prior):
    """segments: [{"name": str, "prior": float, "actual": float|None}]
    — "actual" is the disclosed figure for segments the agent MAPPED
    (name + prior both matched); None for everything reclassified.

    Returns {"rows": [...], "growth": g, "plugName": str} where each row
    is {"name", "kind": mapped|growth|plug, "value", "formula", "flag",
    "note"}. Formulas are Excel-style over the OTHER rows by name — the
    caller substitutes real cell refs.
    """
    if not isinstance(total_actual, (int, float)) or not segments:
        raise ValueError("total_actual and segments are required")
    growth = (total_actual / total_prior
              if isinstance(total_prior, (int, float)) and total_prior
              else None)
    unmapped = [s for s in segments if s.get("actual") is None]
    rows = []
    if growth is None and unmapped:
        raise ValueError("total_prior is required to grow the back-outs")
    plug = (min(unmapped, key=lambda s: abs(s.get("prior") or 0))
            if unmapped else None)
    for s in segments:
        if s.get("actual") is not None:
            rows.append({"name": s["name"], "kind": "mapped",
                         "value": float(s["actual"]), "formula": "",
                         "flag": "", "note": ""})
            continue
        if s is plug:
            continue                      # placed last, needs the others
        val = round(float(s["prior"]) * growth, 1)
        rows.append({"name": s["name"], "kind": "growth", "value": val,
                     "formula": "=%s*%s" % (s["prior"], round(growth, 6)),
                     "flag": "orange",
                     "note": "held at the total's growth (%+.1f%%), "
                             "awaiting true-up" % ((growth - 1) * 100)})
    if plug is not None:
        others = sum(r["value"] for r in rows)
        val = round(float(total_actual) - others, 1)
        flag, note = "orange", "= total − other segments (the plug)"
        prior = plug.get("prior")
        if val < 0 or (isinstance(prior, (int, float)) and prior and
                       abs(val / prior - 1) > WILD_MOVE):
            flag = "red"
            note = ("plug = total − other segments came out %s vs prior "
                    "%.1f — check the MAPPED segments before trusting "
                    "any of this split" % (round(val, 1), prior))
        rows.append({"name": plug["name"], "kind": "plug", "value": val,
                     "formula": "=total-(%s)" % "+".join(
                         r["name"] for r in rows),
                     "flag": flag, "note": note})
    ssum = round(sum(r["value"] for r in rows), 1)
    if abs(ssum - total_actual) > 0.5:
        raise AssertionError("backout does not tie: %s vs %s"
                             % (ssum, total_actual))
    return {"rows": rows, "growth": growth,
            "plugName": plug["name"] if plug else ""}
