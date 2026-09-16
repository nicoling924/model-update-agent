"""THE CANDIDATE INDEX (what the card queue left behind, owner 2026-09-17).

The work queue is gone — a card decided a cell's meaning from a one-shot list
of number ties, with ticks and defaults, and could overrule the brain. What
stays here is everything it used to FIND: the printed lines that carry a row's
prior, the label-only and companion searches, the model's own neighbourhood
around a row (what uses it, the block it sits in, its story). The mapping loop
and the investigator read these; nothing in this module writes.
"""

import re

from .checks import forecast_columns, prior_column, year_columns
from .evaluator import Evaluator
from .numerics import row_tol, to_model_units
from .ledger import sourceable as _sourceable

MAX_CANDS = None      # no cap (deduction 2026-09-08): every candidate, ordered; the brain judges

_SYSTEM = (
    "You are an equity research analyst answering ONE bounded question "
    "about one cell of a valuation model. Everything needed is on the "
    "card: the model row, its history, and machine-extracted candidate "
    "lines from the disclosure with the machine's own warnings. Reply "
    "with JSON {\"answer\": \"<one of the listed answer ids>\", \"why\": "
    "\"<one sentence>\"}. Rules: a warned candidate needs a reason to "
    "trust it; when two candidates both look plausible, the one marked "
    "IMPROVES MOST is the model's own arithmetic telling you which "
    "definition this row carries — prefer it; an EXACT prior "
    "tie outranks a positional read; when unsure, answer the abstaining "
    "option — a red flag is a correct deliverable, a wrong number is the "
    "one unforgivable failure.")


def _tcol(loop, sheet):
    return year_columns(loop.spec, sheet).get(loop.ty)


def _prior_of(loop, sheet, row):
    t = loop.targets.get((sheet, row))
    if t is not None and isinstance(t.prior_value, (int, float)):
        return float(t.prior_value), t
    pcol = prior_column(loop.spec, sheet, int(loop.ty))
    if pcol and sheet in loop.wb.sheetnames:
        v = loop.wb[sheet][f"{pcol}{row}"].value
        if isinstance(v, (int, float)):
            return float(v), t
        if isinstance(v, str) and v.startswith("="):
            try:
                return float(Evaluator(loop.wb).cell(sheet, f"{pcol}{row}")), t
            except Exception:
                pass
    return None, t


def candidates_for(loop, sheet, row, k=MAX_CANDS):
    """Prior-identity candidates for one model row, WITH indictments.
    Reuses the join's own pairing law (adjacent pair whose second element
    ties the prior) but returns EVERY tying line instead of demanding a
    single agreeing one — the ambiguity is the card's reason to exist."""
    from .stage2_join import ratify_page_scales, _tying_pairs, _world_tol
    pv, t = _prior_of(loop, sheet, row)
    if pv is None or pv == 0:
        return _reader_first(loop, sheet, row, _label_only_candidates(loop, sheet, row, t, k), keep=k)
    p2 = getattr(t, "prior2_value", None) if t is not None else None
    periods = getattr(loop.ledger, "_doc_periods", None) or {}
    # WIDER than join_pool (face authority relaxed): a card is a judged
    # PROPOSAL with provenance printed on it, not a silent serve — the
    # SoC-style regulatory schedules live on non-face pages (oracle
    # audit: the whole SoC statement block was invisible to cards).
    # The face tag stays on every candidate; the writegate still
    # referees the answer.
    bad = loop.ledger.noncurrent_docs()
    pv_tabs = getattr(loop.ledger, "_pv_tables", set())
    pool = [it for it in loop.ledger.items
            if it.joinable() and _sourceable(it)
            and (it.doc, it.page, it.table_id) not in pv_tabs]
    priors = [tt.prior_value for tt in loop.targets.values()
              if isinstance(tt.prior_value, (int, float))]
    scales = ratify_page_scales(pool, priors, [])       # the scale is ratified on named rows only
    # THE UNLABELLED ROW REACHES THE BRAIN (the page prints subtotals with no
    # label of their own — the CLP P&L's operating-expense total among them).
    # Code may not say what such a row IS, so it never joins and never proves
    # a write by itself; it is offered on the card with its tie, and the
    # brain's pick is what names it.
    pool += [it for it in loop.ledger.items
             if not str(it.label or "").strip() and len(it.nums or []) >= 2
             and not it.disputed and _sourceable(it)
             and (it.doc, it.page, it.table_id) not in pv_tabs]
    pool = [it for it in pool if (it.doc, it.page) in scales]
    tol = _world_tol(pv)
    exact_home = any(
        abs(abs(to_model_units(n, scales[(it.doc, it.page)])) - abs(pv))
        <= 0.6
        for it in pool for n in it.nums)
    out = _companion_candidates(loop, pv, p2, periods, pool, scales)
    for it in pool:
        s = scales[(it.doc, it.page)]
        ns = [to_model_units(n, s) for n in it.nums]
        for sv, i in _tying_pairs(ns, pv, tol):
            warns = []
            if periods.get(it.doc) != "current":
                warns.append("document vintage UNKNOWN — may be a "
                             "prior-year filing; prefer a current-doc line")
            off = abs(abs(ns[i + 1]) - abs(pv))
            tie_off = off
            if off > 0.6 and exact_home:
                warns.append(f"loose tie (off {off:,.1f}) while the exact "
                             "prior prints elsewhere — likely a different "
                             "definition")
            if not (abs(sv) <= 100 * abs(pv) and abs(sv) * 100 >= abs(pv)):
                continue        # per-share-next-to-total class: 1.89
                                # paired with a 4,775 prior is not a serve
            if abs(abs(sv) - abs(pv)) <= row_tol(pv, base=0.01):
                if periods.get(it.doc) == "current" and \
                        loop.ledger.face(it.doc, it.page):
                    warns.append("value UNCHANGED vs prior — a current "
                                 "statement face may confirm this")
                else:
                    warns.append("value EQUALS this row's prior — may be "
                                 "the prior-year column/table, not this "
                                 "year")
            if isinstance(p2, (int, float)) and \
                    abs(abs(sv) - abs(p2)) <= max(0.6, abs(p2) * 5e-4):
                warns.append("value equals prior2 — the year BEFORE last")
            if i + 2 < len(ns):
                nxt = ns[i + 2]
                series = isinstance(p2, (int, float)) and \
                    abs(abs(nxt) - abs(p2)) <= max(0.6, abs(p2) * 5e-4)
                delta = abs(nxt - (sv - ns[i + 1])) <= 1.0 \
                    or abs(nxt - abs(sv - ns[i + 1])) <= 1.0
                if not (series or delta) and abs(nxt) >= 10:
                    warns.append("wide row without a time-series shape — "
                                 "may be a SEGMENT row (column error)")
            if abs(pv) >= 50 and (abs(sv) > 8 * abs(pv)
                                  or abs(sv) * 8 < abs(pv)):
                warns.append(f"out of proportion vs prior ({abs(sv/pv):,.1f}x)")
            if abs(pv) < 50:
                warns.append("small-value row — ties are coincidence-"
                             "prone; prefer derivation or leave red")
            from .numerics import kinship
            lab_m = str(getattr(t, "label", "") or "")
            if lab_m and off > 0.6 and not kinship(lab_m, str(it.label)) \
                    and not any(
                        kinship(ctx, str(it.label))
                        for ctx in _block_context(loop, sheet, row)):
                # THE EXACT TIE IS THE IDENTITY (run 34993405014: ROAFNA!29
                # 'Capital' 58,405 and Aus!70 'Mount Piper' 6,314 — both the
                # analyst's own answers — carried this warning beside a
                # comparative that reproduced the model's prior exactly, and
                # the brain declined both). A line whose comparative equals
                # the prior at the model's own precision IS this row's line;
                # the name adds nothing to that. A LOOSE tie still needs it.
                # neither the row's own label NOR its section header
                # is kin (run-214: 'Closing balance' under the 'Fuel
                # Clause Recovery' header wrongly indicted the printed
                # 'Fuel Clause Account' line and steered the answerer
                # to a warning-free coincidence instead)
                warns.append("label unrelated to the model row's — a "
                             "numeric coincidence unless the position "
                             "proves it")
            face = loop.ledger.face(it.doc, it.page)
            out.append({"value": sv, "doc": it.doc, "page": it.page,
                        "line": str(it.label)[:60], "face": face or "no-face",
                        "tie_off": tie_off, "warnings": warns})
    # A BLANK THIS YEAR, JUDGED BY MEANING (owner 2026-09-08): a line
    # printing last year's figure and nothing this year is offered as a
    # candidate worth 0 — 'bond financing is financing' is the brain's
    # call on the label, the prior tie is code's. No page or table rule.
    from .writegate import nil_current_zero
    seen_nil = set()
    for it in loop.ledger.items:
        if it.doc in bad or it.joinable():
            continue
        nums = [n for n in (it.nums or []) if isinstance(n, (int, float))]
        if len(nums) != 1:
            continue
        hit = nil_current_zero([it], pv, {(it.doc, it.page)}, bad,
                               prior2=getattr(t, "prior2_value", None))
        if hit is None or (it.doc, it.page, str(it.label)[:40]) in seen_nil:
            continue
        seen_nil.add((it.doc, it.page, str(it.label)[:40]))
        face = loop.ledger.face(it.doc, it.page)
        out.append({"value": 0.0, "doc": it.doc, "page": it.page,
                    "line": str(it.label)[:60], "face": face or "no-face",
                    "tie_off": 0.0, "nil": True,
                    "warnings": ["prints the model's OWN last-year figure with a "
                                 "BLANK this year. The number tie says this is "
                                 "where the report keeps the model's item this "
                                 "year, whatever the report now calls it (a "
                                 "company folds a bond line into 'other "
                                 "financing' and the name changes, the item "
                                 "does not) — so the blank means 0 this year, "
                                 "unless the same figure is a coincidence on an "
                                 "unrelated line (judge the meaning)"]})
    # LAST YEAR'S REPORT NAMES THE ITEM (deduction 2026-09-08, vintage
    # split): a prior-vintage document is never a SOURCE of this year's
    # number, but it is evidence of IDENTITY — the line whose own current
    # equalled the model's prior tells the item's printed label; this
    # year's lines under that label are candidates (the segment that
    # moved, the row the company renamed). Same rule as the prose noun.
    from .numerics import kinship as _kin3, to_model_units as _tmu3, norm_label as _norm3
    from .writegate import _SCALES as _SC3, _ties_full_precision as _tfp3
    old_labels = set()
    _GENERIC = re.compile(r"^(合计|小计|总计|其他|其中|total|subtotal|other|others|sum|net|amount)$", re.IGNORECASE)

    def _specific(lab):
        # a name is an identity only when it names an item: 'Total', '合计',
        # 'Other' name nothing (run 255: '合计' matched 23 note totals and the
        # brain served last year's figure); two words or three CJK characters
        t = _norm3(str(lab)).replace(" ", "")
        if not t or _GENERIC.match(t):
            return False
        cjk = sum(1 for ch in t if "一" <= ch <= "鿿")
        return cjk >= 3 or len(str(lab).split()) >= 2
    for it in loop.ledger.items:
        if it.doc not in bad or getattr(it, "channel", "") == "prose":
            continue
        nums0 = [n for n in (it.nums or []) if isinstance(n, (int, float))]
        # the line must carry a current AND a comparative: a lone number is
        # a bare figure, not a line that identifies an item
        if len(nums0) >= 2 and _specific(it.label) and any(_tfp3(nums0[0] / f, pv) for f in _SC3):
            old_labels.add(_norm3(str(it.label)).replace(" ", ""))
    if old_labels:
        seen_old = {round(c["value"], 1) for c in out}
        for it in loop.ledger.items:
            if it.doc in bad or getattr(it, "channel", "") == "prose":
                continue
            lab_n = _norm3(str(it.label)).replace(" ", "")
            if not any(lab_n == o or _kin3(o, lab_n) for o in old_labels):
                continue
            nums1 = [n for n in (it.nums or []) if isinstance(n, (int, float))]
            sc = scales.get((it.doc, it.page))
            if not nums1 or not sc:
                continue
            val = _tmu3(nums1[0], sc)
            if len(nums1) == 1 and any(_tfp3(nums1[0] / f, pv) for f in _SC3):
                continue        # a lone number equal to last year's IS last year's — the nil law's line, never a candidate
            if round(val, 1) in seen_old:
                continue
            seen_old.add(round(val, 1))
            face = loop.ledger.face(it.doc, it.page)
            out.append({"value": val, "doc": it.doc, "page": it.page,
                        "line": str(it.label)[:60], "face": face or "no-face",
                        "noun_proven": True, "no_number_tie": True,
                        "warnings": ["⚠ NO NUMBER TIE — last year's report prints the model's prior under this "
                                     "LABEL; this year's line under the same label is a name match, not a tie"]})
    # PROSE FIGURES (owner 2026-09-08): a sentence naming this item is a
    # candidate even without a prior tie — the brain judges the item and
    # the unit from the sentence printed on the card; code's guard is the
    # world band against the model's previous period. Money is shown in
    # the model's units via the document's own ratified scale.
    from .numerics import kinship as _kin2, to_model_units as _tmu2
    lab_row = str(getattr(t, "label", "") or "")
    doc_scale = {}
    for (d_, p_), sc in scales.items():
        doc_scale.setdefault(d_, []).append(sc)
    doc_scale = {d_: max(set(v), key=v.count) for d_, v in doc_scale.items()}
    # LAST YEAR'S REPORT GIVES THE TIE (owner 2026-09-08, dividend): a
    # sentence in the PRIOR-vintage document whose figure is the model's
    # prior names the item — the same noun in this year's document is
    # the candidate, whatever the model row is called ('现金分红' vs the
    # report's '共计派发现金股利'). The prior doc proves the noun; the
    # current doc supplies the number.
    from .numerics import norm_label as _norm2
    tied_nouns = set()
    for it in loop.ledger.items:
        if getattr(it, "channel", "") != "prose" or it.doc not in bad or not it.nums:
            continue
        sc0 = doc_scale.get(it.doc)
        if getattr(it, "unit_dim", "") == "money":
            from .writegate import _SCALES as _SC
            v0s = [_tmu2(it.nums[0], sc0)] if sc0 else [float(it.nums[0]) / f for f in _SC]
        else:
            v0s = [float(it.nums[0])]
        if any(abs(abs(v0) - abs(pv)) <= max(0.6, abs(pv) * 5e-3) for v0 in v0s):
            tied_nouns.add(_norm2(str(it.label)))
    seen_prose = set()
    for it in loop.ledger.items:
        if getattr(it, "channel", "") != "prose" or it.doc in bad:
            continue
        noun_tied = bool(tied_nouns) and any(
            n_ and (n_ == _norm2(str(it.label)) or _kin2(n_, str(it.label))) for n_ in tied_nouns)
        if not noun_tied and (not lab_row or not _kin2(lab_row, str(it.label))):
            continue
        key = (it.doc, it.page, str(it.label)[:40])
        if key in seen_prose or not it.nums:
            continue
        seen_prose.add(key)
        money = getattr(it, "unit_dim", "") == "money"
        sc = doc_scale.get(it.doc)
        from .numerics import prose_money_value as _pmv
        val = _pmv(float(it.nums[0]), loop.spec, sc) if money else float(it.nums[0])
        warns = [f"PROSE: '{str(it.source_line)[:90]}' — judge the item AND the unit"
                 + ("" if money and sc else f" (printed unit {getattr(it, 'unit_dim', '')[5:] or 'money'}, "
                    "convert to the model's units)")]
        if not (abs(val) <= 100 * abs(pv) and abs(val) * 100 >= abs(pv)):
            warns.append("out of the model's world vs its prior — probably a different unit or item")
        if len(it.nums) >= 2:
            pr = _tmu2(it.nums[1], sc) if (money and sc) else float(it.nums[1])
            off = abs(abs(pr) - abs(pv))
            if off <= max(0.6, abs(pv) * 5e-3):
                warns.append("✔ the sentence's own growth/prior implies LAST year = the model's prior")
        if noun_tied:
            warns.append("✔ LAST YEAR'S report states this same item at the model's prior — the noun is proven")
            noun_proven_flag = True
        else:
            noun_proven_flag = False
        out.append({"value": val, "doc": it.doc, "page": it.page,
                    "line": str(it.label)[:60], "face": "prose", "noun_proven": noun_proven_flag,
                    "tie_off": (0.0 if any(w.startswith("✔") for w in warns) else 9.0),
                    "warnings": warns})
    seen, uniq = set(), []
    # EXACT TIE OUTRANKS EVERYTHING (strict-policy audit 2026-09-01:
    # 'Operating costs' twins — the group P&L line on a face page
    # outsorted the SoC schedule line whose prior tied EXACTLY; 18/30
    # wrong picks were ordering, not absence)
    for c in sorted(out, key=lambda c: (1 if c.get("no_number_tie") else 0, round(c.get("tie_off", 0.05), 1),
                                        len(c["warnings"]),
                                        c["face"] == "no-face",
                                        c["doc"], c["page"])):
        key = round(c["value"], 1)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    uniq = _reader_first(loop, sheet, row, uniq)
    return uniq if k is None else uniq[:k]


def _reader_first(loop, sheet, row, cands, keep=None):
    """THE READER'S OWN READING GOES FIRST (run 34993405014: Final!16's card
    offered a 250 MW battery and four tax lines; the reader had already read
    'Other gain 460' off the P&L face with the check that closes the printed
    operating profit, and its reading never reached the card at all). The
    brain read the whole disclosure for this row — its answer is the first
    thing the card shows, with the line it quoted and the check it stated."""
    def _trim(out):
        # the reading takes the FIRST place, it does not make the card longer:
        # it replaces the weakest option the machine offered (reviewer 2026-09-16)
        return out if keep is None else out[:keep]
    sug = (getattr(loop.ledger, "reader_suggestions", None) or {}).get(f"{sheet}!{row}")
    if not isinstance(sug, dict) or not isinstance(sug.get("value"), (int, float)):
        return cands
    why = str(sug.get("check") or sug.get("reason") or "").strip()
    seen_it = ("OPTION A IS THE READER'S OWN READING of this row from the whole disclosure — "
               f"the reader's suggestion, quoted from p{sug['page']} '{str(sug['line'])[:44]}'"
               + (f"; its check: {why[:120]}" if why else ""))
    # what the reading LACKS is said only of the reading itself: a candidate
    # the machine already found keeps its own evidence, prior tie included
    # (reviewer 2026-09-16: an EXACT-tie candidate was being fronted with
    # "no prior tie ... it lands red" pasted over it)
    note = seen_it + (" — no prior tie, and the line is not named like the row: judge whether "
                      "this is the item (it lands red)")
    same = next((c for c in cands if abs(abs(c.get("value") or 0) - abs(sug["value"])) <= 0.6), None)
    if same is not None:
        same["warnings"] = [seen_it + " — the machine found this line too; its own evidence is below"] \
            + list(same.get("warnings") or [])
        return _trim([same] + [c for c in cands if c is not same])
    return _trim([{"value": float(sug["value"]), "doc": sug["doc"], "page": sug["page"], "line": sug["line"],
                   "face": loop.ledger.face(sug["doc"], sug["page"]) or "no-face", "tie_off": 9.0,
                   "no_prior": True, "warnings": [note]}] + list(cands))


def _label_only_candidates(loop, sheet, row, t, k=MAX_CANDS):
    """NO PRIOR TO TIE (owner 2026-09-08: 'if there is no past-year number
    you infer from the item label'): a row the model names but never
    filled (DFE 'New orders') is offered the report's lines whose label is
    kin to its own — prose lines first (the sentence is printed), then
    table lines — every one warned 'no prior tie', for the brain to judge
    the item and the unit. Nothing lands proven from here."""
    from .numerics import kinship as _kin, to_model_units as _tmu
    from .stage2_join import ratify_page_scales
    lab_row = str(getattr(t, "label", "") or "")
    if not lab_row:
        ws = loop.wb[sheet] if sheet in loop.wb.sheetnames else None
        lab_row = next((str(ws.cell(row, c).value) for c in range(1, 5)
                        if ws is not None and isinstance(ws.cell(row, c).value, str)
                        and ws.cell(row, c).value.strip()), "")
    if not lab_row:
        return []
    bad = loop.ledger.noncurrent_docs()
    periods = getattr(loop.ledger, "_doc_periods", None) or {}
    priors = [tt.prior_value for tt in loop.targets.values()
              if isinstance(tt.prior_value, (int, float))]
    scales = ratify_page_scales([it for it in loop.ledger.items if it.joinable()], priors, [])
    doc_scale = {}
    for (d_, p_), sc in scales.items():
        doc_scale.setdefault(d_, []).append(sc)
    doc_scale = {d_: max(set(v), key=v.count) for d_, v in doc_scale.items()}
    out, seen = [], set()
    import re as _re
    cjk_row = bool(_re.search(r"[一-鿿]", lab_row))
    for it in loop.ledger.items:
        if not _sourceable(it) or not it.nums or periods.get(it.doc) not in (None, "current"):
            continue
        kin = _kin(lab_row, str(it.label))
        if not kin:
            # ACROSS SCRIPTS (an English model over a Chinese filing) no
            # label can be kin; the brain matches the MEANING — so the
            # current filing's sentences that state a figure with its own
            # growth or prior (the ones a report writes about) are offered
            cjk_line = bool(_re.search(r"[一-鿿]", str(it.label)))
            if not (getattr(it, "channel", "") == "prose" and cjk_line != cjk_row
                    and len(it.nums) >= 2):
                continue
        key = (it.doc, it.page, str(it.label)[:40], round(float(it.nums[0]), 1))
        if key in seen:
            continue
        seen.add(key)
        prose = getattr(it, "channel", "") == "prose"
        money = getattr(it, "unit_dim", "") == "money"
        sc = doc_scale.get(it.doc) or scales.get((it.doc, it.page))
        from .numerics import prose_money_value as _pmv0
        val = (_pmv0(float(it.nums[0]), loop.spec, sc) if (prose and money)
               else _tmu(it.nums[0], sc) if (sc and (money or not prose)) else float(it.nums[0]))
        warns = ["NO PRIOR in the model to tie — judged on the label alone; lands red"]
        if prose:
            warns.append(f"PROSE: '{str(it.source_line)[:90]}' — judge the item AND the unit"
                         + ("" if money and sc else f" (printed unit {getattr(it, 'unit_dim', '')[5:] or 'money'})"))
        out.append({"value": val, "doc": it.doc, "page": it.page,
                    "line": str(it.label)[:60],
                    "face": "prose" if prose else (loop.ledger.face(it.doc, it.page) or "no-face"),
                    "tie_off": 9.0, "no_prior": True, "warnings": warns})
    out.sort(key=lambda c: (c["face"] != "prose", c["doc"], c["page"]))
    if k is not None and out and not any(_kin(lab_row, c["line"]) for c in out):
        k = max(k, 8)         # across scripts the brain needs to SEE the sentences
    return out if k is None else out[:k]


def _companion_candidates(loop, pv, p2, periods, pool, scales, k=MAX_CANDS):
    """THE POSITIONAL COMPANION GENERATOR (oracle audit 2026-09-01: 33 of
    33 missed truths were PRINTED — in current-year segment tables that
    hold no prior at all; the prior sits at the SAME POSITION in the twin
    prior-year table). The by-hand method: find the prior in a table, read
    the same-position cell of the same-labelled row in the companion
    current table."""
    from .numerics import norm_label
    if abs(pv) < 10:
        return []
    by_label = {}
    for it in pool:
        by_label.setdefault(norm_label(str(it.label)), []).append(it)
    out = []
    for it_p in pool:
        # THE COLUMN IS READ BY ITS NAME (owner 2026-09-14: "why can't the
        # AI read the table and understand how it works"): the brain names
        # every column (Hong Kong | Australia | China | Total; FY2025 |
        # FY2024). The prior sits under a named column of last year's
        # table; this year's same-labelled row is read under the column of
        # the SAME NAME. Position is the fallback only where no table has
        # names. A period table never pairs this way — its columns are
        # years, and "the prior's column" is last year (CLP Ecogen: the
        # five-year summary's 'Hong Kong number' row held 940 in FY2025 by
        # coincidence and another same-labelled row read 5,484 — the
        # employee headcount — as Ecogen's capacity).
        if getattr(it_p, "table_kind", None) == "period":
            continue
        s_p = scales[(it_p.doc, it_p.page)]
        ns_p = [to_model_units(n, s_p) for n in it_p.nums]
        cols_p = [str(c).strip().lower() for c in (getattr(it_p, "columns", None) or [])]
        for kpos, n in enumerate(ns_p):
            if abs(abs(n) - abs(pv)) > max(0.6, abs(pv) * 5e-4):
                continue
            col_name = cols_p[kpos] if kpos < len(cols_p) else None
            for it_c in by_label.get(norm_label(str(it_p.label)), []):
                if (it_c.doc, it_c.page, it_c.table_id) == \
                        (it_p.doc, it_p.page, it_p.table_id):
                    continue
                if periods.get(it_c.doc) != "current":
                    continue
                if getattr(it_c, "table_kind", None) == "period":
                    continue
                s_c = scales[(it_c.doc, it_c.page)]
                ns_c = [to_model_units(m, s_c) for m in it_c.nums]
                cols_c = [str(c).strip().lower() for c in (getattr(it_c, "columns", None) or [])]
                if col_name and cols_c:
                    if col_name not in cols_c:
                        continue          # this year's table has no column of that name: not a read
                    kread = cols_c.index(col_name)
                    basis_how = f"column '{col_name}'"
                elif col_name or cols_c:
                    continue              # one table named, the other not: no honest pairing
                else:
                    kread = kpos          # neither table named: position is all there is
                    basis_how = f"slot {kpos} (no column names read)"
                if kread >= len(ns_c):
                    continue
                sv = ns_c[kread] if n >= 0 else -abs(ns_c[kread])
                if abs(abs(sv) - abs(pv)) <= max(0.6, abs(pv) * 5e-4) \
                        and len(ns_c) > 1:
                    continue        # companion also holds the prior there:
                                    # same-vintage twin, not a current table
                if not (abs(sv) <= 30 * abs(pv) and abs(sv) * 30 >= abs(pv)):
                    continue
                warns = []
                if isinstance(p2, (int, float)) and abs(abs(sv) - abs(p2)) \
                        <= max(0.6, abs(p2) * 5e-4):
                    warns.append("value equals prior2 — the year BEFORE "
                                 "last")
                out.append({
                    "value": sv, "doc": it_c.doc, "page": it_c.page,
                    "line": str(it_c.label)[:60],
                    "face": loop.ledger.face(it_c.doc, it_c.page)
                    or "no-face",
                    "warnings": warns,
                    "basis": (f"same-labelled row, {basis_how}: prior {pv:,.1f} "
                              f"there in {it_p.doc[:20]} p{it_p.page}")})
    return out if k is None else out[: k * 3]


def _uses_of(loop, sheet, col, row, limit=4):
    """The target-year formulas that consume this cell, with their row labels
    (the relationships the analyst reads to know what a row IS).
    -> [(ref, label, formula)]"""
    import re as _re
    wb = loop.wb
    coord = f"{col}{row}"
    from .investigate import _refs
    out = []
    for sh in (loop.spec.get("year_axis") or {}):
        if sh not in wb.sheetnames:
            continue
        ws = wb[sh]
        tc = year_columns(loop.spec, sh).get(str(loop.ty))
        if not tc:
            continue
        fc = (forecast_columns(loop.spec, sh, int(loop.ty)) or [None])[0]       # the first forecast year: how the row rolls
        for c_ in [tc] + ([fc] if fc else []):
            for r in range(1, min(ws.max_row, 400) + 1):
                f = ws[f"{c_}{r}"].value
                if not (isinstance(f, str) and f.startswith("=")):
                    continue
                if f"{c_}{r}" == coord and sh == sheet:
                    continue
                if (sheet, coord) in _refs(f, sh, wb):
                    out.append((f"{sh}!{c_}{r}", str(ws.cell(r, 1).value or "")[:28], f[:40]))
                    if len(out) >= limit:
                        return out
    return out


def row_context(loop, sheet, col, row, lab=None, hist_n=4):
    """What the analyst sees before judging a cell (owner 2026-09-15): the
    row's place (sheet > section headers > label), its history, and the
    formulas that use it. -> (where_line, used_by_line or "")"""
    try:
        wb = loop.wb
        if lab is None:
            t = loop.targets.get((sheet, row)) if hasattr(loop, "targets") else None
            lab = str(getattr(t, "label", "") or "") or str(wb[sheet].cell(row, 1).value or "")
        ctx = _block_context(loop, sheet, row)
        yc = year_columns(loop.spec, sheet)
        hist = []
        for y in sorted(yc, key=lambda y: int(y) if str(y).isdigit() else 0):
            if str(y).isdigit() and int(y) < int(loop.ty):
                v = wb[sheet][f"{yc[y]}{row}"].value
                if isinstance(v, (int, float)):
                    hist.append(f"{y}: {v:,.2f}")
        where = ("  where: sheet '" + sheet + "'" + (" > " + " > ".join(ctx[::-1]) if ctx else "")
                 + f" > '{lab}'" + (f"; history {', '.join(hist[-hist_n:])}" if hist else ""))
        uses = _uses_of(loop, sheet, col, row)
        used = ("  used by: " + "; ".join(f"{u_ref} '{u_lab}' {u_f}" for u_ref, u_lab, u_f in uses[:4])) if uses else ""
        return where, used
    except Exception:
        return "", ""


def row_context_short(loop, sheet, col, row):
    """The same context as row_context, on one line, for cards that list several cells."""
    where, used = row_context(loop, sheet, col, row)
    w = where.replace("  where: ", "")
    return w + ((" | " + used.replace("  used by: ", "")) if used else "")


def cell_story(loop, sheet, col, row):
    """MEMORY, NOT A RULE (owner 2026-09-15): what happened to this cell so
    far this run — where it was served from and whether that was proven,
    what the sense check ruled and why, its flag — so the brain can leave a
    confident cell alone, revisit a doubtful one, or overrule for a reason.
    -> one line or ''."""
    from .writegate import is_proven
    ref = f"{sheet}!{col}{row}"
    bits = []
    e = (getattr(loop, "served", None) or {}).get((sheet, row))
    if isinstance(e, dict) and isinstance(e.get("value"), (int, float)):
        bits.append(f"served {e['value']:,.2f} from '{str(e.get('line') or '')[:30]}' p{e.get('page')} "
                    + ("(proven: its line ties the prior)" if is_proven(e) else "(unproven)"))
    rl = (loop.writer.log.get("rulings") or {}).get(ref)
    if rl:
        bits.append(f"sense check ruled '{rl['pick']}' for '{rl['line']}' ({rl.get('desc', '')[:50]})")
    try:
        rgb = str(loop.wb[sheet][f"{col}{row}"].fill.fgColor.rgb or "")[-6:]
        if rgb == "FFC7CE" or ref in loop.writer.log.get("flags", []):
            bits.append("flagged red")
        elif rgb == "FFC000":
            bits.append("orange (backed out)")
    except Exception:
        pass
    return ("  so far this run: " + "; ".join(bits)) if bits else ""


def _block_context(loop, sheet, row, span=8):
    """The section headers above a model row — a generic 'Closing
    balance' row means nothing without its block ('Fuel Clause
    Recovery'). Read from the sheet's own label columns walking up."""
    out = []
    if sheet not in loop.wb.sheetnames:
        return out
    ws = loop.wb[sheet]
    for r in range(row - 1, max(0, row - span), -1):
        for col in ("A", "B", "C", "D"):
            v = ws[f"{col}{r}"].value
            if isinstance(v, str) and len(v.strip()) > 3 \
                    and not v.startswith("="):
                out.append(v.strip())
                break
        if len(out) >= 3:
            break
    return out


def _red_cells(loop):
    """Red-flagged target-column cells: 'Sheet!AI7' -> (sheet, row)."""
    out = []
    for ref in dict.fromkeys(loop.writer.log.get("flags", [])):
        m = re.match(r"^([^!]+)!([A-Z]{1,3})(\d+)$", str(ref))
        if not m:
            continue
        sheet, col, row = m.group(1), m.group(2), int(m.group(3))
        if col != _tcol(loop, sheet) or sheet not in loop.wb.sheetnames:
            continue
        # THE CELL'S COLOUR IS THE TRUTH (run-232 cash autopsy): the flag
        # list keeps a cell the stale sweep flagged even after a proven
        # law rewrote it ORANGE; phase0 then rewrote the correct cash
        # composite (=3905+23) from a movement row and left 810. Only a
        # cell still painted RED is red.
        try:
            rgb = str(loop.wb[sheet][f"{col}{row}"].fill.fgColor.rgb or "")
        except Exception:
            rgb = ""
        if rgb.endswith("FFC000"):
            continue                      # painted ORANGE by a proven law: not red
        out.append((sheet, row))
    return out



# ---------------------------------------------------------------------------
# WHAT WAS REMOVED HERE (owner 2026-09-17, the mapping rebuild):
# build_queue / render_card / run_queue / phase0 / WorkItem / _llm_answer —
# the card queue. A card DECIDED a cell's meaning from a one-shot list of
# number-tie candidates with ticks and defaults, could overrule the brain
# ("proven", "was served", "one row one claim"), and had no memory of what the
# brain had already refused. The mapping loop (pipeline/mapping.py) replaces
# it: the brain reads the model and the print and decides; code indexes,
# verifies and measures.
#
# WHAT SURVIVES, AND WHY: everything above this line is a FINDING —
# candidates_for, the label-only and companion candidate searches, row_context,
# cell_story, _uses_of, _block_context. They locate printed lines and read the
# model's own neighbourhood; the investigator and the mapping context read
# them. None of them writes.
# ---------------------------------------------------------------------------
