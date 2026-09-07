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
import re

_TOL = 1e-3
_SCALES = (1.0, 1e2, 1e3, 1e4, 1e6)   # 元/千元/万元 and friends into model mn


def _nums(item):
    return item.nums if hasattr(item, "nums") else item.get("nums", [])


def _meta(item, field, default=None):
    """Field of a ledger item — a LedgerItem, a plain object, or a dict."""
    if isinstance(item, dict):
        return item.get(field, default)
    return getattr(item, field, default)


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
                # sign-blind: disclosures print magnitudes; the MODEL owns
                # the sign convention (costs stored negative). Direction is
                # still policed by the prior tie + the transactional band.
                if _close(abs(n) / f, abs(value)):
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
    # sign-blind like find_evidence (run-227 autopsy: the fund balance
    # prints -370 where the model stores 370 — the row IS the tie; the
    # MODEL owns the sign convention)
    return any(isinstance(n, (int, float))
               and _close(abs(n) / scale, abs(prior))
               for n in _nums(item))


def _claim_key(item, value):
    return round(abs(value), 1)


def _homed(entry):
    """A CLAIM NEEDS A HOME (run-227 autopsy): a served figure counts as
    claimed only if it actually landed in a model cell. A serve skipped
    as a derived row (its formula computes it) never took the number —
    it must not lock the figure away from the cell that needs it."""
    return (isinstance(entry, dict)
            and isinstance(entry.get("value"), (int, float))
            and entry.get("homed", True) is not False)


def is_proven(entry):
    """A claim is PROVEN when its evidence tied the prior and it landed
    clean (stage-2 identity joins, proven loop writes). A no-prior read,
    a red-flagged landing, or a low-confidence serve is UNPROVEN."""
    if not isinstance(entry, dict):
        return False
    if entry.get("flag") == "red":
        return False
    text = f"{entry.get('note') or ''} {entry.get('line') or ''}"
    if "UNPROVEN" in text or "no prior" in text.lower():
        return False
    return int(entry.get("conf") or 0) >= 4


def claim_holders(served):
    """|value| -> [(cell, entry)] for HOMED claims only."""
    out = {}
    for cell, e in served.items():
        if _homed(e):
            out.setdefault(round(abs(e["value"]), 1), []).append((cell, e))
    return out


def claimed_keys(served):
    """The ONE-HOME register: |values| already bound by deterministic
    serves. Document-AGNOSTIC (run-9 pin: OCI -57.9 served from one
    document found a second home as FX-translation from another,
    counting the negative twice in equity) — the MODEL has one home per
    figure, whichever page printed it. Enforced for material figures
    only (small values repeat legitimately); the bar lives in the
    judges. A refused duplicate becomes a loud flagged hole — always
    safer than a silent double-count."""
    out = set()
    for e in served.values():
        if _homed(e):
            out.add(round(abs(e["value"]), 1))
    return out


def judge_write(value, prior, was_served, evidence, claimed, holders=None):
    """Returns (verdict, reason, forced_flag).
    verdict: ALLOW | ALLOW_FLAGGED | REFUSE | EVICT.

    EVICT (run-227 autopsy — PROOF OUTRANKS ARRIVAL): the write is
    proven (its row ties the prior) but the figure's only home(s) are
    UNPROVEN claims. The caller reverts and red-flags those holders,
    then lands this write clean. A PROVEN holder still blocks."""
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
        if holders is not None and material:
            hs = holders.get(_claim_key(None, value), [])
            if hs and not any(is_proven(e) for _c, e in hs):
                return ("EVICT",
                        "proven — the evidence row ties the prior; the "
                        "figure's current home is UNPROVEN and yields "
                        "(proof outranks arrival)", None)
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


# ONE register, one law: stage-3's claimed_values and the loop's
# claimed_keys are the SAME function. Two names survive for the museum's
# history; two implementations may never exist again (a duplicate pair
# drifted doc-keyed here while the law went document-agnostic, leaving
# stage-3's guard silently dead — caught before run 10 delivered).
claimed_values = claimed_keys


def no_prior_duplicate(value, doc, claimed_vals):
    """Runs 8+9 law: a NO-PRIOR read may never give a second home to a
    figure already served into another row — the section total (run 8)
    and the OCI-as-FX double count (run 9, across documents). Material
    figures only; small numbers repeat legitimately. `doc` is kept in
    the signature for the museum's history but no longer narrows the
    law."""
    return (isinstance(value, (int, float)) and abs(value) >= 50
            and round(abs(value), 1) in claimed_vals)


_NIL_TOKENS = {"-", "–", "—", "―", "/", "不适用"}


def _ties_full_precision(x, prior):
    """The nil tie is at the MODEL'S OWN precision (run 250 autopsy: a
    shareholder count 989,682,463 tied total liabilities 98,867.0367 at
    0.1%; a JV balance 99,438,322 tied 9,954.0676 at 0.1% — the old 2e-3
    band let five-digit coincidences through). A prior stored to d
    decimals is matched within half a unit of its last decimal (593.54
    takes 593.5367; 98867.0367 takes nothing but itself), never looser
    than the old band."""
    p = abs(float(prior))
    r = repr(round(p, 8))
    d = len(r.split(".")[1]) if "." in r else 0
    tol = 0.5 * 10 ** (-d) + p * 1e-6
    return abs(abs(x) - p) <= min(tol, p * 2e-3)


def nil_current_zero(items, prior, face_pages=None, banned_docs=None,
                     statement_faces=None, row_label=None):
    """The dash-nil law (run-11 pin, treasury shares): a statement line
    printing a standalone nil mark IMMEDIATELY before a number that ties
    the model's prior to full precision proves the current value is zero
    ("Less: Treasury shares – 648,882.29" = nil this year, 0.6mn last).

    Tightened after its own dry-run audit zeroed 20 rows of which most
    were wrong (tax rebates 340.9 zeroed; a tax-rate parameter zeroed):
    - |prior| >= 0.5 — tiny ratios/factors prove nothing;
    - the tie is FULL-PRECISION (2e-3 relative, no absolute floor);
    - the tying printed number carries >= 4 significant digits — real
      monetary figures do, parameters (1, 15, 365) do not;
    - the nil token must sit DIRECTLY before the tying number — the
      empty current slot, then the comparative, nothing between.
    Returns the proving item or None."""
    if not isinstance(prior, (int, float)) or abs(prior) < 0.5:
        return None
    # a year-like prior can never nil-prove (run CLP-1: the 2024 YEAR
    # HEADER tied a dashed line in the prior-period AR and was zeroed)
    if float(prior).is_integer() and 1900 <= prior <= 2100:
        return None
    for it in items:
        if banned_docs and _meta(it, "doc") in banned_docs:
            continue                 # prior-period documents prove nothing
                                     # about THIS period's nils
        # NO PAGE RULE (owner 2026-09-08: "these kind of rules make the
        # agent unable to adapt to other kinds of statements"). The old
        # 'statement faces only' guard was the safety before the test
        # itself carried it — the tie is now at the model's own precision,
        # needs four significant digits, and the sweep needs label
        # kinship; where the line sits no longer matters. `face_pages` and
        # `statement_faces` are accepted and ignored.
        line = str(_meta(it, "source_line", ""))
        # A BLANK CURRENT CELL IS NIL TOO (owner 2026-09-08, DFE: 'other
        # cash received relating to financing' prints the comparative
        # 593,536,697.59 with the current cell empty — the line carries
        # exactly ONE number and it is last year's, full precision).
        # "If not found, back out; if 0, then 0."
        nums = [n for n in (_meta(it, "nums", None) or []) if isinstance(n, (int, float))]
        # ... and a PRINTED ZERO in the current slot beside the tying prior
        # ('0' / '0.00' | 593,536,697.59) is nil the same way
        if len(nums) == 2 and nums[0] == 0:
            nums = [nums[1]]
        # THE GENERIC MAP (owner 2026-09-08): tie last year's number, confirm
        # the LABEL, then read this year — and a blank this year is 0,
        # anywhere in the report. The label check is what stops a
        # related-party purchase line (DFE p239) whose one number equals
        # a prior from zeroing 'service charge and others'; no page rule.
        if len(nums) == 1 and row_label is not None:
            from .numerics import kinship
            if not kinship(str(row_label), str(_meta(it, "label", ""))):
                nums = []            # a differently named line is the brain's call (serve card)
        if len(nums) == 1:
            v = abs(nums[0])          # sign-blind: '-8,485,403.24' is the prior -8.49
            # SIGNIFICANT digits (run 250 autopsy): '15,000,000' is two of
            # them, not eight — the tax-rate parameter 15 tied it and six
            # orange holds turned red; '1000元' in a CSR sentence tied the
            # exchange-rate 1. Leading AND trailing zeros are not digits.
            digits = re.sub(r"[^0-9]", "", ("%.2f" % v)).strip("0")
            if len(digits) >= 4:
                for f in _SCALES:
                    if _ties_full_precision(v / f, prior):
                        return it
        if row_label is not None:
            from .numerics import kinship as _kin_d
            if not _kin_d(str(row_label), str(_meta(it, "label", ""))):
                continue             # a dash under another name is the brain's call
        toks = line.split()
        for i, t in enumerate(toks[:-1]):
            if t not in _NIL_TOKENS:
                continue
            nxt = toks[i + 1]
            digits = re.sub(r"[^0-9]", "", nxt)
            if len(digits.lstrip("0")) < 4:
                continue
            try:
                v = float(nxt.replace(",", "").replace(" ", ""))
            except ValueError:
                continue
            for f in _SCALES:
                if abs(v / f - abs(prior)) <= abs(prior) * 2e-3:
                    return it
    return None
