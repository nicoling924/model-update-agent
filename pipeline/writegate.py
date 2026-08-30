"""The evidence law — the ONE write gate for the objective loop.

Run 7 autopsy (2026-08-30): both balance-killing writes came through
stage-4's set_input with nothing but a prose citation. The loop
OVERWROTE a deterministically proven value (Raw!U60, 15,193.8 -> a
note-page 53,546.5) trying to move a failing check, and stuffed a real
number into the wrong row (prepayments -> held-for-sale). The write
firewall had closed every heuristic writer except this door.

The law, applied to every loop write, on every model:

1. EVIDENCE   — the value must exist in the extraction ledger (under a
                legal unit scale). Not in the documents = not writable.
2. PRIOR TIE  — proven means the SAME evidence row also carries a
                number that ties the cell's stored prior-year value
                (the identity the whole join hangs on). Proven writes
                land clean.
3. ONE CLAIM  — an evidence row already serving another cell cannot be
                written a second time somewhere else.
4. PROVEN IS  — a cell served deterministically in stage 2 can only be
   PROTECTED     overwritten by evidence that itself ties the prior.
                Never change a proven number to move a check.
5. UNPROVEN   — a real but untied value may still be delivered, but
   IS RED        only RED-FLAGGED — never silently.

This file is pure law: no workbook, no LLM — testable offline.
"""

_TOL = 1e-3
_SCALES = (1.0, 1e2, 1e3, 1e4, 1e6)   # 元/千元/万元 and friends into model mn


def _nums(item):
    return item.nums if hasattr(item, "nums") else item.get("nums", [])


def _meta(item, field, default=None):
    return (getattr(item, field, default) if hasattr(item, field)
            else item.get(field, default))


def _close(a, b, tol=_TOL):
    return abs(a - b) <= max(0.5, abs(b) * tol)


def find_evidence(items, value):
    """Ledger rows carrying `value` under a legal scale: [(item, scale)]."""
    out = []
    for it in items:
        for n in _nums(it):
            if not isinstance(n, (int, float)) or n == 0:
                continue
            hit = False
            for f in _SCALES:
                if _close(n / f, value):
                    out.append((it, f))
                    hit = True
                    break
            if hit:
                break
    return out


def ties_prior(item, scale, prior):
    """Does this evidence row also carry the cell's prior-year value?"""
    if not isinstance(prior, (int, float)) or abs(prior) < 1:
        return False
    return any(isinstance(n, (int, float)) and _close(n / scale, abs(prior))
               for n in _nums(item))


def _claim_key(item, value):
    return (_meta(item, "doc"), round(abs(value), 1))


def claimed_keys(served):
    """The ONE-HOME register: (doc, |value|) pairs already bound by
    deterministic serves. Document-wide, not per-page — a section total
    printed on page 96 must not find a second home from page 12.
    Enforced for material figures only (small values repeat
    legitimately); the materiality bar lives in the judges."""
    out = set()
    for e in served.values():
        if isinstance(e, dict) and isinstance(e.get("value"), (int, float)):
            out.add((e.get("doc"), round(abs(e["value"]), 1)))
    return out


def judge_write(value, prior, was_served, evidence, claimed):
    """Returns (verdict, reason, forced_flag).
    verdict: ALLOW | ALLOW_FLAGGED | REFUSE."""
    if not evidence:
        return ("REFUSE",
                "the value appears NOWHERE in the extraction ledger — a "
                "number must come from the documents. find_line the printed "
                "row first; if it is not printed, flag_cell an estimate "
                "instead of writing one", None)
    tied = [(it, s) for it, s in evidence if ties_prior(it, s, prior)]
    material = abs(value) >= 50
    tied_free = [(it, s) for it, s in tied
                 if not material or _claim_key(it, value) not in claimed]
    if tied_free:
        return ("ALLOW", "proven — the evidence row ties the prior", None)
    if tied:
        return ("REFUSE",
                "the only evidence row whose comparative ties this prior "
                "already serves another cell — one row, one claim", None)
    if was_served:
        return ("REFUSE",
                "this cell already holds a PROVEN value (its evidence tied "
                "the prior). Your evidence does not tie — a proven number "
                "is never changed to move a check. Investigate the check's "
                "OTHER components instead", None)
    free = [(it, s) for it, s in evidence
            if not material or _claim_key(it, value) not in claimed]
    if not free:
        return ("REFUSE",
                "every ledger row carrying this value already serves "
                "another cell — one row, one claim", None)
    return ("ALLOW_FLAGGED",
            "unproven — the value is printed but its row's comparative "
            "does not tie this cell's prior; written RED-flagged for the "
            "analyst", "red")


def claimed_values(served):
    """(doc, |value|) pairs already served — the one-home register."""
    out = set()
    for e in served.values():
        if isinstance(e, dict) and isinstance(e.get("value"), (int, float)):
            out.add((e.get("doc"), round(abs(e["value"]), 1)))
    return out


def no_prior_duplicate(value, doc, claimed_vals):
    """Run-8 law: a NO-PRIOR read may not give a second home to a figure
    the same document already served into another row (Raw!U153 took the
    section total that row 156 had already proven — doubling the
    section). Material figures only; small numbers repeat legitimately."""
    return (isinstance(value, (int, float)) and abs(value) >= 50
            and (doc, round(abs(value), 1)) in claimed_vals)
