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
    """A tie at the number's own world: statement rounding (0.5) absorbs
    nothing on a small figure — 1.61 is not 2 (CLP live 2026-09-14: a
    hedge line at scale 100 tied NED solar's 2 | 21 that way)."""
    floor = 0.5 if abs(b) >= 50 else max(0.01, abs(b) * 0.005)
    return abs(a - b) <= max(floor, abs(b) * tol)


def _sourceable(item):
    s = _meta(item, "sourceable", None)
    return True if s is None else bool(s)


def find_evidence(items, value):
    """Ledger rows carrying `value` under a legal scale: [(item, scale)].
    A line the vintage law stamped unsourceable (last year's report) is
    never evidence for a current value, whoever asks."""
    out = []
    for it in items:
        if not _sourceable(it):
            continue
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


def ties_prior(item, scale, prior, value=None):
    """Does this evidence row carry the cell's prior-year value AS THE
    COMPARATIVE of `value`? With no value: anywhere on the row. With a
    value: the prior must be the number printed after it in the same
    magnitude band — the pair (current, prior) the walk reads. A row that
    merely CONTAINS the prior somewhere (run 262: the segment matrix row
    '6,359 | 2,852 | 3,128 | 106 | 12,445' holds last year's intangibles
    total at its end) proves nothing about a number elsewhere on it."""
    if not isinstance(prior, (int, float)) or abs(prior) < 1:
        return False
    # A MATRIX ROW NEVER PAIRS (owner 2026-09-14, CLP: 'Finance income
    # 119 | 14 | 29 | 4 | 69 | 235' across segments served 14 because the
    # Australia prior 29 sat beside it): the columns are categories, the
    # number beside the prior is another segment, not this year
    if value is not None and _meta(item, "table_kind") == "matrix":
        return False
    if value is not None and not _sourceable(item):
        return False                 # the vintage law: last year's report never sources this year
    # sign-blind like find_evidence (run-227 autopsy: the fund balance
    # prints -370 where the model stores 370 — the row IS the tie; the
    # MODEL owns the sign convention)
    ns = [n for n in _nums(item) if isinstance(n, (int, float))]
    if value is None:
        return any(_close(abs(n) / scale, abs(prior)) for n in ns)
    for i, n in enumerate(ns):
        if not _close(abs(n) / scale, abs(value)):
            continue
        ci = next((k for k in range(i + 1, len(ns))
                   if abs(ns[k]) <= 30 * abs(n) and abs(ns[k]) * 30 >= abs(n)), None)
        if ci is None or not _close(abs(ns[ci]) / scale, abs(prior)):
            continue
        if is_sum_row(ns, ci):
            continue      # the 'comparative' is the row's own total (run 262 live: 'share of net assets 954 | 7,532 | 8,486')
        return True
    return False


_RESTATED = re.compile(r"restat|re-?present|reclassif|重述|重列|追溯|重新表述|經重列|经重列", re.I)
_PERIOD_TOKEN = re.compile(r"(?<![A-Za-z0-9])(1H|2H|H1|H2|FY|[1-4]Q|Q[1-4]|interim|full[ -]?year)(?![A-Za-z])", re.I)   # '1H2025', 'FY2024'



def comparative_index(ns, cols, i):
    """The index of the comparative beside ns[i]: by the column headers when
    they carry years — the previous year under the same period kind (1H
    beside 1H, never FY beside 1H; audit 2026-09-15) — else the next
    number of the same order of magnitude. -> index or None"""
    if cols and len(cols) == len(ns):
        yrs = [re.search(r"(20\d\d)", c) for c in cols]
        yi = int(yrs[i].group(1)) if yrs[i] else None
        if yi is not None:
            tok_i = _PERIOD_TOKEN.search(cols[i])
            tok_i = tok_i.group(1).upper() if tok_i else None
            cands = [k for k, m in enumerate(yrs) if m and int(m.group(1)) == yi - 1 and k != i]
            toks = {k: (_PERIOD_TOKEN.search(cols[k]).group(1).upper() if _PERIOD_TOKEN.search(cols[k]) else None) for k in cands}
            same = [k for k in cands if toks[k] == tok_i] or [k for k in cands if toks[k] is None]
            if same:
                return same[0]              # the same period kind, else a plain year header
            if cands:
                return None                 # a previous year of another period kind is not the comparative
    return next((k for k in range(i + 1, len(ns)) if abs(ns[k]) <= 30 * abs(ns[i]) and abs(ns[k]) * 30 >= abs(ns[i])), None)


def restated_comparative(item, value, scale=1.0, all_items=None, prior=None):
    """THE RESTATEMENT TEST (owner 2026-09-15: "either it sees 'restated', or
    the 2024 number in 2025's report does not match the 2024 number in
    2024's report — then there is a restatement; very simple").
    (1) the comparative beside `value` sits under a column named restated
    (any language); or (2) last year's report prints the same-named line at
    the MODEL's prior (the model was built from last year's report) while
    this line's comparative differs from it. The witness must tie the prior:
    a same-named line that merely differs proves nothing (audit 2026-09-15:
    the Ecogen wrong-row write would have landed clean)."""
    if _meta(item, "table_kind") != "period":
        return False
    ns = [n for n in _nums(item) if isinstance(n, (int, float))]
    cols = [str(c) for c in (_meta(item, "columns") or [])]
    ci = None
    for i, n in enumerate(ns):
        if _close(abs(n) / scale, abs(value)):
            ci = comparative_index(ns, cols, i)
            break
    if ci is None:
        return False
    if cols and len(cols) == len(ns) and _RESTATED.search(cols[ci]):
        return True
    if not all_items or not isinstance(prior, (int, float)) or abs(prior) < 1:
        return False
    comp = abs(ns[ci]) / scale
    if _close(comp, abs(prior)):
        return False                                    # the comparative IS the model's prior: nothing restated
    from .numerics import norm_label
    me = norm_label(str(_meta(item, "label") or ""))
    for it in all_items:
        if _sourceable(it) or _meta(it, "table_kind") == "matrix" or getattr(it, "channel", "") == "prose":
            continue                                    # last year's report only, its statement lines
        if norm_label(str(_meta(it, "label") or "")) != me:
            continue
        theirs = [n for n in _nums(it) if isinstance(n, (int, float))]
        if not theirs:
            continue
        # last year's own figure ties the model's prior (at a legal scale) — the name is proven
        if any(_close(abs(theirs[0]) / sc, abs(prior)) for sc in (1.0, 1e3, 1e-3)):
            return True
    return False


def contradicts_prior(item, scale, prior, value):
    """THE COMPARATIVE CONTRADICTS (owner 2026-09-14, CLP Ecogen: 'Hong
    Kong number 5,484 | 5,397' was written into a row whose last year is
    940). A period line prints last year beside this year; when the
    comparative beside `value` is a figure that does NOT tie the cell's
    prior, the line is a different item — not merely unproven."""
    if not isinstance(prior, (int, float)) or abs(prior) < 1:
        return False
    if _meta(item, "table_kind") != "period":
        return False
    ns = [n for n in _nums(item) if isinstance(n, (int, float))]
    cols = [str(c) for c in (_meta(item, "columns") or [])]
    for i, n in enumerate(ns):
        if not _close(abs(n) / scale, abs(value)):
            continue
        ci = comparative_index(ns, cols, i)
        if ci is None or is_sum_row(ns, ci):
            continue
        if abs(ns[ci]) >= 1 and not _close(abs(ns[ci]) / scale, abs(prior)):
            return True
    return False


def is_sum_row(ns, ci):
    """The number at `ci` is the SUM of the numbers before it: a
    components-and-total row, not periods side by side (CLP associates
    note: 'listed 954 | unlisted 7,532 | total 8,486' — 8,486 is last
    year's carrying amount and 7,532 'tied' it as a comparative)."""
    if ci < 2:
        return False
    tot = ns[ci]
    return abs(sum(ns[:ci]) - tot) <= max(0.6, abs(tot) * 5e-4)


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


def holder_is_proven(entry, ref, plugs=(), fill_rgb=""):
    """Is the value the cell HOLDS proven? The serve's proof speaks only for
    the figure it served: if the run has since painted the cell red, or
    PLUGGED it (run 35043265913: Final!AJ108 held a forecast plug and twice
    refused the brain's printed pick as "a PROVEN value"), the cell no
    longer holds that proof. A plug is the run's own admission that nothing
    proves the number — it can never lock a cell against evidence."""
    if ref and ref in (plugs or ()):
        return False
    if str(fill_rgb or "").endswith("FFC7CE"):
        return False
    return is_proven(entry)


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


def _has_label(item):
    """A printed row the BRAIN can be said to have named. A row the page
    prints without a label carries no meaning code may assert (reviewer
    2026-09-16: 'Heading / 20 5' made any value 20 "proven — the evidence
    row ties the prior", and could evict a homed claim). Such a row is
    evidence the brain must name: it reaches the card with its tie, and the
    pick — not code's scan of the ledger — is what gives it meaning. A row
    that carries no label FIELD at all says nothing either way (a fixture, a
    foreign record): unknown is not unlabelled."""
    lab = _meta(item, "label", None)
    return lab is None or bool(str(lab).strip())


def judge_write(value, prior, was_served, evidence, claimed, holders=None, held_proven=False,
                all_items=None, row_named=False):
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
    tied = [(it, s) for it, s in evidence if ties_prior(it, s, prior, value)]
    if not row_named:
        # the write did not name a printed row: an unlabelled line's tie is a
        # number coincidence until the brain says what the line IS
        tied = [(it, s) for it, s in tied if _has_label(it)]
    material = abs(value) >= 50
    tied_free = [(it, s) for it, s in tied
                 if not material or _claim_key(it, value) not in claimed]
    if tied_free:
        if held_proven:
            # TWO READINGS (owner 2026-09-08): the cell already holds a figure
            # whose line tied the prior; this is a second line that ties it
            # with a different current. The brain chose it; it lands RED
            # with both readings for the analyst, never clean over a proof
            return ("ALLOW_FLAGGED", "two readings — a second line ties the prior; "
                    "the brain's choice lands red beside the held figure", "red")
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
    if was_served and held_proven:
        # A PROVEN HOLDER, NOT MERELY AN EARLIER ONE (run 34993405014: this
        # branch fired on presence in `served` — a red read, an orange
        # derivation, a serve that never landed — and told the brain the cell
        # "already holds a PROVEN value"; ~20 brain picks were refused, the
        # correct perpetual-securities home among them). The evidence that
        # locks a cell is the holder's own: its line tied the prior and it
        # landed clean. Anything less yields to the brain's pick, which lands
        # red unless its own evidence ties.
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
    period_free = [(it, s) for it, s in free if _meta(it, "table_kind") == "period"]
    if isinstance(prior, (int, float)) and abs(prior) >= 1 and period_free \
            and all(contradicts_prior(it, s, prior, value) for it, s in period_free):
        # judged on the period lines: a KPI box repeating the figure neither proves nor refutes the comparative
        if any(restated_comparative(it, value, s, all_items, prior=prior) for it, s in period_free):
            return ("ALLOW",
                    "RESTATED comparative: this year's figure under the same name, last year restated away from "
                    f"the model's {prior:,.2f} — proven by the print, the model's history untouched", None)
        return ("REFUSE",
                "every line printing this value shows a DIFFERENT last-year "
                f"figure beside it — the model's last year is {prior:,.2f}; "
                "this is another item, not this row (comparative contradicts)", None)
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


def row_is_constant(prior, prior2):
    """THE CONSTANT ROW (CLP 2026-09-08: a plant's capacity, 1,108 MW,
    printed alone in the presentation's plant list, was read as 'last
    year's figure beside a blank' and zeroed — the divisor of every year's
    unit cost). A row whose last two years hold the same figure is a
    parameter; a lone printed number equal to it is the parameter again,
    never a nil. The model's own history is the evidence."""
    return (isinstance(prior, (int, float)) and isinstance(prior2, (int, float))
            and prior != 0 and abs(prior2 - prior) <= max(0.005, abs(prior) * 1e-6))


def nil_current_zero(items, prior, face_pages=None, banned_docs=None,
                     statement_faces=None, row_label=None, prior2=None):
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
    if row_is_constant(prior, prior2):
        return None                     # a constant printed alone is the constant
    if not isinstance(prior, (int, float)) or abs(prior) < 0.5:
        return None
    # a year-like prior can never nil-prove (run CLP-1: the 2024 YEAR
    # HEADER tied a dashed line in the prior-period AR and was zeroed)
    if float(prior).is_integer() and 1900 <= prior <= 2100:
        return None
    for it in items:
        if not _sourceable(it) or (banned_docs and _meta(it, "doc") in banned_docs):
            continue                 # the vintage law: last year's report proves nothing about this year's nils
        # NO PAGE RULE (owner 2026-09-08: "these kind of rules make the
        # agent unable to adapt to other kinds of statements"). The old
        # 'statement faces only' guard was the safety before the test
        # itself carried it — the tie is now at the model's own precision,
        # needs four significant digits, and the sweep needs label
        # kinship; where the line sits no longer matters. `face_pages` and
        # `statement_faces` are accepted and ignored.
        if _meta(it, "table_kind") == "matrix":
            continue                 # a segment row's blank is another segment's blank (CLP: 'Associates 1,810 | 1,810' on the segment page zeroed CN's 1,607)
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
