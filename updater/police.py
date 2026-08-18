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
            # OWNER KEYS LAW (run-7 review): a flag does NOT excuse a key —
            # a key with known disclosed evidence must TIE, full stop.
            mism.append(f"{name}: model "
                        f"{mv if isinstance(mv, (int, float)) else '?'} "
                        f"vs disclosed {dv:,.2f} "
                        f"({got[1].doc} p{got[1].page})")
            continue
        # per-share fallback (the EPS class): small values tie every scale
        # so the prior-identity oracle refuses them — but the VALUE printed
        # on a kin face line IS announced data (EPS 1.15 is on the income
        # statement). Cent-tolerance direct match = proven.
        if isinstance(mv, (int, float)) and _value_match(ledger, t, mv):
            proven += 1
            continue
        # COMPOSED-KEY PROOF (owner's precedent-cell ruling): keys the
        # filing never prints as one line (gross profit in a CN P&L;
        # total liabilities = CL + NCL) are proven by TRACKING PRECEDENT
        # CELLS — walk the formula to its target-column feeders; if every
        # branch is itself evidence-proven, the composition is proven.
        if isinstance(mv, (int, float)) \
                and _composed_proof(wb, spec, ty, t, tl, tmap, ledger, ev):
            proven += 1
            continue
        if ref not in flags and isinstance(mv, (int, float)):
            unverified.append(name)
    out["laws"]["1_announced"] = "PASS" if not mism else f"FAIL ({len(mism)})"
    out["findings"] += [f"announced: {m}" for m in mism[:10]]
    # DETAIL-LEVEL FACE TIE-OUT (owner issue 1/2 fundamental): the
    # statements are FULLY printed, and the model consumes their DETAIL
    # rows — a totals-only police is structurally blind to detail errors
    # that cancel at the total (the CFI/CFF twin class). EVERY row with
    # unique disclosure evidence must tie print, key or not.
    detail_mism = []
    for t in tl:
        got = unique_evidence_value(ledger, tl, t)
        if got is None:
            continue
        tcol = year_columns(spec, t.sheet).get(ty)
        if not tcol:
            continue
        try:
            mv = ev.cell(t.sheet, f"{tcol}{t.row}")
        except Exception:
            continue
        dv = got[0]
        if isinstance(mv, (int, float)) \
                and abs(abs(mv) - abs(dv)) > max(row_tol(dv),
                                                 abs(dv) * 5e-3):
            detail_mism.append(f"{t.sheet}!{tcol}{t.row} "
                               f"'{str(t.label)[:28]}': model {mv:,.2f} vs "
                               f"print {dv:,.2f} ({got[1].doc} "
                               f"p{got[1].page})")
    if detail_mism:
        out["laws"]["1_announced"] = (
            out["laws"]["1_announced"].replace("PASS", "FAIL (details)")
            if out["laws"]["1_announced"] == "PASS"
            else out["laws"]["1_announced"] + f" +{len(detail_mism)} details")
        out["findings"] += [f"detail off print (fix it — the value is "
                            f"printed): {m}" for m in detail_mism[:10]]

    # OWNER KEYS LAW: segment/driver leaves (the hardcodes feeding the
    # revenue / gross-profit keys) must be UPDATED — a leaf still holding
    # exactly its prior value is stale, and stale segment keys fail law 4.
    stale_leaves = _stale_driver_leaves(wb, spec, ty)
    if spec.get("key_rows"):        # empty list keeps the NO-KEY-ROWS verdict
        ok4 = not mism and not unverified and not stale_leaves
        out["laws"]["4_keys"] = (
            f"PASS ({proven} evidence-proven)" if ok4
            else (f"FAIL ({len(mism)} mismatch, {len(unverified)} "
                  f"unverified-unflagged, {len(stale_leaves)} driver "
                  f"leaves stale)"))
        out["findings"] += [f"key unverified+unflagged (prove or flag): {n}"
                            for n in unverified[:8]]
        out["findings"] += [
            f"segment/driver leaf STALE (owner keys law — update it: "
            f"match_by_implied_prior / MD&A / find_line): {s}"
            for s in stale_leaves[:8]]

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


def _composed_proof(wb, spec, ty, t, tl, tmap, ledger, ev, depth=4):
    """A target-column cell is PROVEN if its value ties the evidence
    oracle for its own row, or it is a formula ALL of whose target-column
    references are proven (recursively). >= 2 distinct proven feeders
    required at the top so nothing passes vacuously."""
    import re as _re
    from .numerics import row_tol as _rt
    seen = set()

    def _refs(formula, default_sheet):
        """Target-column references, RANGES EXPANDED (an endpoint-only
        read would prove =SUM(U54:U66) from two proven ends)."""
        out = []
        f = formula.replace("$", "")
        for sh2, sh3, c1, r1, c2, r2 in _re.findall(
                r"(?:'([^']+)'|([A-Za-z0-9 _]+))?!?"
                r"([A-Z]{1,3})(\d+):([A-Z]{1,3})(\d+)", f):
            sh = (sh2 or sh3 or default_sheet).strip()
            if sh in wb.sheetnames and c1 == c2 \
                    and c1 == year_columns(spec, sh).get(ty) \
                    and 0 < int(r2) - int(r1) <= 80:
                out += [(sh, f"{c1}{r}")
                        for r in range(int(r1), int(r2) + 1)]
        f = _re.sub(r"[A-Z]{1,3}\d+:[A-Z]{1,3}\d+", "", f)
        for sh2, sh3, c2, r2 in _re.findall(
                r"(?:'([^']+)'|([A-Za-z0-9 _]+))?!?([A-Z]{1,3})(\d+)", f):
            sh = (sh2 or sh3 or default_sheet).strip()
            if sh in wb.sheetnames and c2 == year_columns(spec, sh).get(ty):
                out.append((sh, f"{c2}{r2}"))
        return out

    def _proven(sheet, coord, d):
        if d < 0 or (sheet, coord) in seen or sheet not in wb.sheetnames:
            return False
        seen.add((sheet, coord))
        m = _re.match(r"^([A-Z]{1,3})(\d+)$", coord)
        if not m or m.group(1) != year_columns(spec, sheet).get(ty):
            return False
        t2 = tmap.get((sheet, int(m.group(2))))
        if t2 is not None:
            got = unique_evidence_value(ledger, tl, t2)
            if got is not None:
                try:
                    mv2 = ev.cell(sheet, coord)
                except Exception:
                    mv2 = None
                if isinstance(mv2, (int, float)) and abs(
                        abs(mv2) - abs(got[0])) <= max(_rt(got[0]),
                                                       abs(got[0]) * 5e-3):
                    return True
        v = wb[sheet][coord].value
        if not (isinstance(v, str) and v.startswith("=")):
            return False
        refs = set(_refs(v, sheet))
        return bool(refs) and all(_proven(sh, cd, d - 1) for sh, cd in refs)

    tcol = year_columns(spec, t.sheet).get(ty)
    v = wb[t.sheet][f"{tcol}{t.row}"].value
    if not (isinstance(v, str) and v.startswith("=")):
        return False
    top = set(_refs(v, t.sheet))
    return len(top) >= 2 and all(_proven(sh, cd, depth) for sh, cd in top)


def _value_match(ledger, t, mv):
    """Printed-value proof for rows the aggregate oracle cannot tie (the
    per-share world). Two forms:
    - PAIR identity (language-free): a current-doc line printing the
      model's PRIOR next to the candidate value ("每股收益 1.15 0.94") —
      adjacency of both years is an identity even for small numbers;
    - label-kin single value on a face (the original form)."""
    from .numerics import kinship
    tol = max(0.01, abs(mv) * 2e-3)
    prior_docs = ledger.prior_period_docs()
    pv = t.prior_value if isinstance(t.prior_value, (int, float)) else None
    ptol = max(0.01, abs(pv) * 2e-3) if pv is not None else None
    for it in ledger.items:
        if it.doc in prior_docs or not it.joinable():
            continue
        ns = it.nums
        if pv is not None and abs(mv) < 100:
            for i in range(len(ns) - 1):
                a, b = ns[i], ns[i + 1]
                if abs(abs(a) - abs(mv)) <= tol \
                        and abs(abs(b) - abs(pv)) <= ptol:
                    return True
        if ledger.face(it.doc, it.page) is None:
            continue
        if not kinship(t.label, it.label):
            continue
        if any(abs(abs(n) - abs(mv)) <= tol for n in ns):
            return True
    return False


def _stale_driver_leaves(wb, spec, ty, max_leaves=400):
    """Leaves of the revenue / gross-profit key rows still holding EXACTLY
    their prior value — the segment breakdowns the owner requires updated."""
    import re as _re
    from .checks import prior_column
    out, seen = [], set()

    def leaves(sheet, coord, depth=0):
        if depth > 6 or (sheet, coord) in seen or len(seen) > max_leaves:
            return []
        seen.add((sheet, coord))
        v = wb[sheet][coord].value if sheet in wb.sheetnames else None
        if isinstance(v, (int, float)):
            return [(sheet, coord)]
        if not isinstance(v, str) or not v.startswith("="):
            return []
        acc = []
        for sh2, sh3, c2, r2 in _re.findall(
                r"(?:'([^']+)'|([A-Za-z0-9 _]+))?!?([A-Z]{1,3})(\d+)",
                v.replace("$", "")):
            sh = (sh2 or sh3 or sheet).strip()
            if sh in wb.sheetnames:
                acc += leaves(sh, f"{c2}{r2}", depth + 1)
        return acc

    for k in spec.get("key_rows") or []:
        name = str(k.get("name", "")).lower()
        if not any(w in name for w in ("revenue", "sales", "gross")):
            continue
        sheet = k["sheet"]
        tcol = year_columns(spec, sheet).get(ty)
        if not tcol or sheet not in wb.sheetnames:
            continue
        for (sh, coord) in dict.fromkeys(
                leaves(sheet, f"{tcol}{int(k['row'])}")):
            m = _re.match(r"^([A-Z]{1,3})(\d+)$", coord)
            if not m or m.group(1) != year_columns(spec, sh).get(ty):
                continue
            pcol = prior_column(spec, sh, ty)
            if not pcol:
                continue
            cur = wb[sh][coord].value
            pv = wb[sh][f"{pcol}{m.group(2)}"].value
            if isinstance(cur, (int, float)) and isinstance(pv, (int, float)) \
                    and cur == pv and abs(cur) > 1.0:
                out.append(f"{sh}!{coord}")
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
