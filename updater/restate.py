"""Restatement — the ONE human-in-the-loop pause (BOSS_MINDMAP Task B).

Detection is the lookup law from the legacy stack (proven concept):
find-by-name, verify-by-number — a RESTATEMENT is a row whose label matches
but whose comparative (prior-year) number does not. One row of that is a
mapping doubt; several rows on the same statement face is a restated basis.

On detection the run PAUSES COMPLETELY (no writes) and asks the analyst two
things: (a) the prior financial report, (b) restate the model yes/no — with
the boss's warning that restating financials may break reconciliation with
unrestated operational data. The pause is a RESUME, not a rerun: the
question and the answer live in a JSON state file; a re-dispatch with the
answer present continues.

Analyst answer file (updates/restatement_<period>.json):
    {"status": "answered", "restate": true|false,
     "prior_report": "<path or empty>", "note": "..."}
"""
import json
from pathlib import Path

from .numerics import kinship, row_tol, to_model_units, SCALES

MIN_SUSPECTS = 5      # >= this many mismatched comparatives on faces = act
_BAND = (0.25, 4.0)   # a moved comparative stays in the row's world; a note
                      # line about something else usually does not


def scan(ledger, targets):
    """Comparatives vs model history, number-anchored and comparative-SHAPED.

    A suspect requires ALL of (precision tuned on the DFE false-fire —
    label homonyms across statements/notes are the noise source):
    - a label-KIN line on a ratified current-doc face,
    - the line prints exactly TWO in-world numbers (current, comparative —
      the statement-line shape; note tables with 3+ columns are skipped),
    - the comparative slot sits in the row's own band (0.25x-4x of the
      model prior: restatements move numbers, they do not replace them
      with different concepts),
    - and NO kin line anywhere ties the prior at row tolerance.
    Deterministic code only names CANDIDATES; judging whether they are a
    real restatement is the agent's/analyst's call (BOSS_MINDMAP Task B).
    """
    prior_docs = ledger.prior_period_docs()
    suspects = []
    for t in targets:
        pv = t.prior_value
        if not isinstance(pv, (int, float)) or abs(pv) < 10.0:
            continue
        cands, tied = [], False
        for it in ledger.items:
            if it.doc in prior_docs or not it.joinable():
                continue
            if ledger.face(it.doc, it.page) is None:
                continue
            if not kinship(t.label, it.label):
                continue
            tol = row_tol(pv)
            alt = getattr(t, "alt_prior_value", None)
            for s in SCALES:
                ns = [to_model_units(n, s) for n in it.nums]
                if any(abs(abs(n) - abs(pv)) <= tol for n in ns):
                    tied = True
                    break
                # interim runs: the prior YEAR-END is an equally legal
                # comparative (BS lines print Dec-31, not Jun-30)
                if isinstance(alt, (int, float)) and abs(alt) >= 10.0 \
                        and any(abs(abs(n) - abs(alt)) <= row_tol(alt)
                                for n in ns):
                    tied = True
                    break
                world = [n for n in ns if n != 0
                         and 0.01 <= abs(n) / abs(pv) <= 100.0]
                if len(world) == 2 \
                        and _BAND[0] <= abs(world[1]) / abs(pv) <= _BAND[1]:
                    cands.append((world[1], it))
            if tied:
                break
        if cands and not tied:
            dv, best = cands[0]
            suspects.append({
                "row": f"{t.sheet}!{t.row}", "label": str(t.label)[:60],
                "model_prior": pv, "disclosed_comparative": dv,
                "doc": best.doc, "page": best.page,
                "line": best.source_line[:100]})
    return suspects


def state_path(company_dir, period):
    return Path(company_dir) / "updates" / f"restatement_{period}.json"


def load_state(company_dir, period):
    p = state_path(company_dir, period)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


class RestatementPause(RuntimeError):
    """Raised to stop the run cleanly. NOT a refusal — a question."""


def _judge(client, suspects):
    """The AGENT judges (BOSS_MINDMAP: 'when the agent identified any
    restatement') — deterministic code only surfaces candidates; whether
    they are a restated basis or label/granularity noise is reasoning."""
    lines = "\n".join(
        f"- {s['row']} '{s['label']}': model prior {s['model_prior']:,.2f} "
        f"vs comparative ≈{s['disclosed_comparative']:,.2f} "
        f"({s['doc']} p{s['page']}: {s['line'][:70]})" for s in suspects[:15])

    def _val(o):
        if o.get("verdict") not in ("restatement", "noise"):
            return ["verdict must be 'restatement' or 'noise'"]
        return []
    try:
        out = client.json(
            "You are an equity research analyst checking for a restatement.",
            "The new disclosure's prior-year comparatives disagree with the "
            "model's history on these rows. A RESTATEMENT is a changed "
            "reporting basis (reclassification, segment change, accounting "
            "policy) — coherent, usually clustered on a statement. NOISE is "
            "label homonymy (a note line, a different scope, a CF line "
            "matching a BS label). Judge:\n" + lines +
            "\n\nRespond {\"verdict\": \"restatement\"|\"noise\", "
            "\"why\": \"...\"}", _val, repair_retries=1)
        return out.get("verdict"), str(out.get("why", ""))[:200]
    except Exception as e:
        return "restatement", f"judge unavailable ({e}) — pausing on the safe side"


def check_or_pause(company_dir, period, ledger, targets, log, client=None):
    """The gatekeeper the run calls BEFORE any write.

    - no/few suspects -> proceed
    - suspects + analyst answer on file -> return the answer (the loop
      honors it: restate=yes -> restate history; restate=no -> the
      analyst's cross-report section-mapping method, mismatches flagged)
    - suspects + no answer: the AGENT judges. Judged noise -> proceed
      (candidates logged). Judged restatement (or no client to judge in a
      live run) -> write the question file, raise RestatementPause.
      Dry runs (client=None) never pause — they log candidates; pausing is
      a judgment call and dry runs cannot judge.
    """
    state = load_state(company_dir, period)
    if state and state.get("status") == "answered":
        log.append(f"restatement: analyst answered restate={state.get('restate')}")
        return state
    suspects = scan(ledger, targets)
    if len(suspects) < MIN_SUSPECTS:
        if suspects:
            log.append(f"restatement scan: {len(suspects)} isolated comparative "
                       "mismatches (below threshold) — left to the loop/flags")
        return {"status": "none", "isolated": suspects}
    if client is None:
        log.append(f"restatement scan: {len(suspects)} candidates (dry run — "
                   "no judge; candidates logged, not paused)")
        return {"status": "candidates", "suspects": suspects}
    verdict, why = _judge(client, suspects)
    if verdict == "noise":
        log.append(f"restatement: agent judged the {len(suspects)} candidates "
                   f"NOISE ({why}) — continuing, mismatches go to flags")
        return {"status": "judged_noise", "suspects": suspects, "why": why}
    log.append(f"restatement: agent judged RESTATEMENT ({why})")
    p = state_path(company_dir, period)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "status": "question",
        "question": (
            "RESTATEMENT DETECTED — the new disclosure's prior-year "
            "comparatives do not match the model's history on the rows "
            "below. Two questions before the update can continue:\n"
            "1. Please provide the PREVIOUS financial report (path), so the "
            "agent can map each model line's source section across the "
            "restatement.\n"
            "2. Restate the model's history to the new basis? WARNING: "
            "operational data are not restated by the company — restating "
            "the financials may break reconciliation with operational "
            "rows.\n"
            "Answer by saving this file with status='answered', "
            "restate=true/false, prior_report='<path>'."),
        "suspects": suspects}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    raise RestatementPause(
        f"paused for analyst: {len(suspects)} restated comparatives — "
        f"question written to {p}")
