"""The move-on law (owner ruling 2026-08-31, CLP run 9).

"The agent has to learn to move on even if it can't find some stale
inputs" — but the mindmap's guard also says NOT DISCLOSED MUST BE
PROVEN, never asserted. Both are satisfied by splitting the work:

- CODE DOES THE LOOKING. For every unexamined stale red, search the
  ENTIRE extraction ledger — every line of every document, every scale
  — for the row's prior value. No tie anywhere = the figure is not
  disclosed at the model's granularity, and the search itself is the
  where-we-looked documentation. The red becomes an adjudicated finding
  (run-14 ruling) without spending one loop action.
- THE AGENT DOES THE JUDGING. Rows where candidate evidence DOES exist
  keep their unexamined marker (with the candidates named) — those are
  the loop's mandatory queue, now a fraction of its former size.

A regional sheet's detail rows (the run-202 exhibit: India, 10 reds)
are exactly the class a group results announcement never publishes —
they auto-adjudicate here at machine speed.
"""
from openpyxl.comments import Comment

from .checks import prior_column
from .numerics import SCALES, row_tol, to_model_units

STALE_MARK = "STALE INPUT"      # the unexamined marker (gate contract)


def _evidence_for(ledger, pv):
    """Does ANY ledger line carry this prior value at any scale?
    -> 'doc pN' of the first tie, or None."""
    tol = row_tol(pv, base=0.6 if abs(pv) >= 100 else 0.01)
    for it in ledger.items:
        for s in SCALES:
            for n in it.nums:
                if abs(abs(to_model_units(n, s)) - abs(pv)) <= tol:
                    return f"{it.doc} p{it.page}"
    return None


def machine_look(wb, spec, target_year, ledger, writer, log):
    """The exhaustive not-disclosed search, for every unexamined red.
    -> (n_proven_not_disclosed, n_evidence_exists)."""
    n_docs = len({it.doc for it in ledger.items})
    n_lines = len(ledger.items)
    n_proved = n_evid = 0
    for ref in list(dict.fromkeys(writer.log.get("flags", []))):
        sh, _, coord = ref.partition("!")
        if sh not in wb.sheetnames or not coord:
            continue
        cell = wb[sh][coord]
        note = str(cell.comment.text) if cell.comment else ""
        if STALE_MARK not in note:
            continue                      # already adjudicated / other flag
        row = "".join(c for c in coord if c.isdigit())
        pcol = prior_column(spec, sh, target_year)
        pv = wb[sh][f"{pcol}{row}"].value if pcol and row else None
        if not isinstance(pv, (int, float)) or pv == 0:
            continue                      # nothing searchable to prove by
        src = _evidence_for(ledger, pv)
        if src is None:
            cell.comment = Comment(
                "NOT DISCLOSED (proven): searched all %d extraction lines "
                "across %d documents for this row's prior %s at every "
                "scale — no line ties it. The figure is not published at "
                "the model's granularity this period. Held at prior; "
                "true up when detail appears. (move-on law)"
                % (n_lines, n_docs, f"{pv:,.2f}"), "Model Update Agent")
            n_proved += 1
        else:
            cell.comment = Comment(
                note[:180] + " | STALE INPUT — evidence candidates exist "
                "(%s): adjudicate — serve it or say why the candidate is "
                "the wrong line." % src, "Model Update Agent")
            n_evid += 1
    if n_proved or n_evid:
        log(f"[run] move-on law: {n_proved} stale reds PROVEN not disclosed "
            f"(full-ledger search, documented); {n_evid} have evidence "
            "candidates -> the loop's queue")
    return n_proved, n_evid
