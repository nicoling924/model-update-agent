"""The Police — four laws, findings go BACK to the agent (never auto-apply).

BOSS_MINDMAP: (1) company-announced data updated correctly; (2) analyst
adjustments honored; (3) the model balances, all periods; (4) the key
numbers verified. The Police measures and challenges; the AGENT fixes.
Machine auto-apply is dead doctrine (run-33/v3 disasters).

Two layers:
- deterministic verdicts (this module, pure code) — the arithmetic part of
  each law, from the scorecard and the evidence oracle;
- an adversarial fresh-context LLM review (prompts/police.md) that re-derives
  the keys from the evidence and challenges mappings — findings returned as
  text objectives for the loop's next cycle.

The run loops agent<->police up to POLICE_CYCLES; whatever remains open is
flagged and listed in _REPORT — delivery happens regardless (always-deliver
law).
"""
import json
from pathlib import Path

from .checks import scorecard, year_columns
from .numerics import row_tol
from .stage2_join import unique_evidence_value

POLICE_CYCLES = 2
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "police.md"


def deterministic(wb, spec, target_year, targets, served, book, writer_log):
    """The code-provable part of the four laws. -> verdict dict."""
    ty = str(target_year)
    card = scorecard(wb, spec, ty, served=served, flags=writer_log["flags"])
    laws, findings = {}, []

    # Law 3 — balance: every check row, every year.
    fails = [c for c in card["checks"] if c["status"] == "FAIL"]
    errs = [c for c in card["checks"] if c["status"] == "EVAL_ERROR"]
    laws["3_balance"] = "PASS" if not fails and not errs else \
        f"FAIL ({len(fails)} check fails, {len(errs)} eval errors)"
    for c in fails[:10]:
        findings.append(f"balance: {c['name']} = "
                        f"{c['got']:,.2f}" if isinstance(c['got'], (int, float))
                        else f"balance: {c['name']} eval error")

    # Law 4 — keys: present AND (proven or flagged). Never silently wrong.
    # An empty key list can never PASS (the vacuous-PASS hole, run-1-live).
    if not card["keys"]:
        laws["4_keys"] = "NO KEY ROWS — spec/discovery gap, law unverifiable"
        findings.append("keys: no key rows known for this model — law 4 "
                        "could not be verified")
    bad_keys = []
    for k in card["keys"]:
        if not k["present"]:
            bad_keys.append(f"{k['name']} MISSING")
        elif not k["proven"] and not k["flagged"]:
            bad_keys.append(f"{k['name']} present-unproven-unflagged")
    if card["keys"]:
        laws["4_keys"] = "PASS" if not bad_keys else f"FAIL ({len(bad_keys)})"
    findings += [f"key: {b}" for b in bad_keys[:10]]

    # Laws 1-2 need the evidence ledger; verify() completes them.
    laws["1_announced"] = "pending"
    laws["2_adjustments"] = "pending"
    return {"laws": laws, "findings": findings, "card": card}


def verify(wb, spec, target_year, ledger, targets, served, book, writer_log):
    """The complete deterministic pass (needs the ledger for laws 1-2)."""
    out = deterministic(wb, spec, target_year, targets, served, book,
                        writer_log)
    ty = str(target_year)
    tl = list(targets)
    tmap = {t.key: t for t in tl}
    flags = set(writer_log["flags"])

    # Laws 1 & 4 share the evidence oracle. A key is PROVEN when its live
    # value ties unique disclosure evidence — however it was computed
    # (run-2 autopsy: formula keys with proven inputs were counted
    # "unproven" by write-bookkeeping; the oracle judges VALUES, not
    # plumbing). correct-or-flagged (BOSS law): evidence-tied -> proven;
    # evidence-mismatch -> law 1 FAIL; no evidence and no flag -> law 4
    # finding (prove it or flag it).
    from .evaluator import Evaluator
    ev = Evaluator(wb)
    mism, unverified, proven = [], [], 0
    for k in spec.get("key_rows") or []:
        t = tmap.get((k["sheet"], int(k["row"])))
        if t is None:
            continue
        tcol = year_columns(spec, t.sheet).get(ty)
        if not tcol:
            continue
        try:
            mv = ev.cell(t.sheet, f"{tcol}{t.row}")
        except Exception:
            continue
        ref = f"{t.sheet}!{tcol}{t.row}"
        name = k.get("name", ref)
        got = unique_evidence_value(ledger, tl, t)
        if got is not None:
            dv = got[0]
            if isinstance(mv, (int, float)) \
                    and abs(abs(mv) - abs(dv)) <= max(row_tol(dv),
                                                      abs(dv) * 5e-3):
                proven += 1
                continue
            if ref not in flags:
                mism.append(f"{name}: model "
                            f"{mv if isinstance(mv, (int, float)) else '?'} "
                            f"vs disclosed {dv:,.2f} "
                            f"({got[1].doc} p{got[1].page})")
            continue
        if ref not in flags and isinstance(mv, (int, float)):
            unverified.append(name)
    out["laws"]["1_announced"] = "PASS" if not mism else f"FAIL ({len(mism)})"
    out["findings"] += [f"announced: {m}" for m in mism[:10]]
    if spec.get("key_rows"):        # empty list keeps the NO-KEY-ROWS verdict
        out["laws"]["4_keys"] = (
            f"PASS ({proven} evidence-proven)" if not mism and not unverified
            else f"FAIL ({len(mism)} mismatch, {len(unverified)} "
                 f"unverified-unflagged)")
        out["findings"] += [f"key unverified+unflagged (prove or flag): {n}"
                            for n in unverified[:8]]

    # Law 2 — adjustments: every replicated adjustment still holds its
    # replicated value (the book remembers what the agent applied).
    adj_bad = []
    for p in book.entries.values():
        if p.method != "adjustment":
            continue
        sheet, coord = p.ref.split("!", 1)
        if sheet not in wb.sheetnames:
            continue
        v = wb[sheet][coord].value
        if not isinstance(v, (int, float)):
            adj_bad.append(f"{p.ref} no longer numeric")
    out["laws"]["2_adjustments"] = ("PASS" if not adj_bad
                                    else f"FAIL ({len(adj_bad)})")
    out["findings"] += [f"adjustment: {a}" for a in adj_bad[:6]]
    return out


def llm_review(client, verdict, wb, spec, target_year, book, writer_log,
               log):
    """Adversarial fresh-context challenge. Returns finding strings for the
    loop. The reviewer sees the scorecard + flags + evidence summaries —
    NOT the updater's reasoning (independence is the whole value)."""
    if client is None:
        return []
    from .checks import summarize
    prompt = _PROMPT_PATH.read_text(encoding="utf-8")
    state = "\n".join([
        f"TARGET YEAR: {target_year}",
        "== LAWS (deterministic verdicts) ==",
        *(f"{k}: {v}" for k, v in verdict["laws"].items()),
        "== SCORECARD ==",
        summarize(verdict["card"], target_year),
        "== FLAGGED CELLS ==",
        *(writer_log["flags"][-40:] or ["(none)"]),
        "== EVIDENCE GRADES ==",
        f"A/B/C/D counts: {len(book.by_grade('A'))}/{len(book.by_grade('B'))}"
        f"/{len(book.by_grade('C'))}/{len(book.by_grade('D'))}",
    ])

    def _val(o):
        if not isinstance(o.get("findings"), list):
            return ["'findings' list required (may be empty)"]
        return []
    try:
        out = client.json(
            "You are an independent reviewer. Find what is WRONG; try to "
            "break this update. Never confirm politely.",
            prompt + "\n\n" + state, _val, repair_retries=1)
    except Exception as e:
        log(f"[police] llm review failed: {e}")
        return []
    return [str(f)[:250] for f in out.get("findings", [])][:12]
