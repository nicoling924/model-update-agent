"""Analyst-adjustment inference — Police law 2 (BOSS_MINDMAP).

The model's prior actual column is the analyst's own answer key: where its
hardcode DIFFERS from what the company disclosed for that same row, the
difference IS the analyst's adjustment (diff-of-columns, BUILD_PLAN §3.3).

Mechanism note: these rows are exactly where prior-identity ties FAIL (the
model deliberately deviates from print), so the number-anchored join oracle
cannot find them. This module works the complement: label-KIN lines on
ratified current-doc faces, restricted to the clean two-column case
(one in-world current + one in-world comparative on the line). Anything
messier is skipped — an adjustment inferred from ambiguous evidence is a
guess, and guesses are poison (run-14 collision law).

Output is CANDIDATES for the agent to confirm — never auto-written. Each
carries the disclosed current AND prior, the characterized logic:

    delta  — model = disclosed + constant   (e.g. excluding a one-off)
    ratio  — model = disclosed * constant   (e.g. a haircut / ownership %)

and the replication value under that logic. The agent replicates via
set_input (grade B, citation carried) and every inferred adjustment is
listed in _REPORT for the analyst to confirm once. Pure analysis: no
writes, no LLM.
"""
from .numerics import kinship, row_tol, to_model_units
from .stage2_join import ratify_page_scales

REL_TOL = 5e-3          # within this of print = nothing to adjust
MIN_BASE = 1.0          # per-share rows are definition-land, not adjustments


def _in_world(v, pv):
    a, b = abs(v), abs(pv)
    return a > 0 and b > 0 and max(a, b) / min(a, b) < 100.0


def infer(ledger, targets):
    """-> [{row, label, model_prior, disclosed_prior, disclosed_current,
            kind, constant, replicated, cite}]"""
    tl = list(targets)
    priors = [x.prior_value for x in tl
              if isinstance(x.prior_value, (int, float))]
    pool = ledger.join_pool()
    scales = ratify_page_scales(pool, priors)
    out = []
    for t in tl:
        pv = t.prior_value
        if not isinstance(pv, (int, float)) or abs(pv) < MIN_BASE:
            continue
        cands = []
        pool_t = pool
        try:
            from .packets import home_pages
        except Exception:
            home_pages = None
        for it in pool_t:
            s = scales.get((it.doc, it.page))
            if s is None or not kinship(t.label, it.label):
                continue
            ns = [to_model_units(n, s) for n in it.nums]
            world = [n for n in ns if _in_world(n, pv)]
            if len(world) == 2:
                cur, comp = world[0], world[1]
            elif (len(ns) == 2 and ns[0] and ns[1]
                  and 0.01 <= abs(ns[0] / ns[1]) <= 100.0):
                # SMALL-NET-PRIOR fallback (H1 财务费用 class): the model
                # holds a carved-out NET (−0.4) while the filing prints
                # the gross pair [45.1, 44.5] — the pv-world filter can
                # never see it. A clean mutually-in-world face pair is a
                # legal [current, comparative]; the adjustment may be
                # LARGER than the base.
                cur, comp = ns[0], ns[1]
            else:
                continue
            if abs(abs(comp) - abs(pv)) <= max(row_tol(pv), abs(pv) * REL_TOL):
                cands = []                 # ties print after all: no adjustment
                break
            cands.append((cur, comp, it))
        if not cands:
            continue
        # all kin lines must tell the SAME story or we know nothing
        comps = [c for _cur, c, _it in cands]
        if max(comps) - min(comps) > row_tol(max(comps, key=abs), base=1.0):
            continue
        cur, comp, it = cands[0]
        if comp == 0:
            continue
        delta = pv - comp
        ratio = pv / comp
        if 0.2 <= abs(ratio) <= 5.0 and abs(delta) > row_tol(pv):
            kind, const = ("ratio", round(ratio, 4)) if abs(ratio - 1) > 0.02 \
                else ("delta", round(delta, 4))
        else:
            kind, const = "delta", round(delta, 4)
        replicated = cur * const if kind == "ratio" else cur + const
        out.append({
            "row": f"{t.sheet}!{t.row}", "label": str(t.label)[:60],
            "model_prior": pv, "disclosed_prior": comp,
            "disclosed_current": cur,
            "kind": kind, "constant": const,
            "replicated": round(replicated, 4),
            "cite": f"{it.doc} p{it.page}: {it.source_line[:80]}"})
    return out
