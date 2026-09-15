"""THE WORK-QUEUE INVERSION (council ruling 2026-09-01).

Run-210 autopsy: a free-roaming weak LLM spent 90 actions on 61 repeated
investigations, 9 plug attempts and ZERO evidence writes, while every
good number in the run came from code. The Fable-drive proved the tools
suffice for a strong brain — and that the strong brain's real edge was
an ORDER, not freedom. So stage 4 inverts: THE MACHINE OWNS THE PLAN,
the LLM answers one bounded question at a time.

Council-mandated mechanics (architect / red-team / operator, all seats):
- Lazy cards: a card is rendered from LIVE workbook state at pop time,
  never up front — staleness impossible by construction.
- Phase 0 auto-resolve: everything the gates already decide (GUILTY
  diffs, stale composites) is applied by code BEFORE any LLM call, via
  the SAME guarded tools — a reordering of existing authority, never a
  new writer.
- Evidence before plugs: a check's PLUG card may not be dealt while
  component cards for that check remain open (per-check phase boundary).
- Flag is the lazy answer: every card's default (LLM absent, malformed,
  circuit-open, deadline) is the abstaining action — red flag, verdict
  SUSPICIOUS, or skip-to-terminal-ladder. Worst case = the machinery
  baseline, which delivers-with-flags.
- Cards execute ONLY through the ObjectiveLoop's guarded tool methods
  (t_set_input, t_apply_diff, t_rewrite_constants, t_verdict,
  t_plug_residual, t_flag_cell): the card is a proposal, the writegate
  stays the referee. No new write paths.
- Candidates carry their own indictments: prior-vintage, wide-row,
  loose-tie and proportion warnings are printed ON the card so the
  answerer sees the machine's doubts (red-team: sycophancy defence).

Pure code except the one client.json call per card; fully drivable
offline through the `answerer` hook.
"""
import re
import time
from dataclasses import dataclass, field

from .checks import forecast_columns, prior_column, year_columns
from .evaluator import Evaluator
from .numerics import row_tol, to_model_units
from .ledger import vintage_ban as _vintage_ban, sourceable as _sourceable

DEADLINE_S = 1200
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


@dataclass
class WorkItem:
    kind: str                 # SERVE | TRIPWIRE | PLUG
    sheet: str = ""
    row: int = 0
    check: str = ""           # owning check "Sheet!row" (PLUG)
    refs: list = field(default_factory=list)   # tripwire chain members
    priority: float = 0.0
    state: str = "OPEN"       # OPEN | DONE | DEFAULTED | MOOT
    note: str = ""            # SENSE: the reason the line is under review


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
        return _label_only_candidates(loop, sheet, row, t, k)
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
    scales = ratify_page_scales(pool, priors, [])
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
            if lab_m and not kinship(lab_m, str(it.label)) \
                    and not any(
                        kinship(ctx, str(it.label))
                        for ctx in _block_context(loop, sheet, row)):
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
                        "tie_off": 0.5, "noun_proven": True,
                        "warnings": ["✔ LAST YEAR'S report prints the model's prior under this "
                                     "label — the item's own name; this year's line under it"]})
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
    for c in sorted(out, key=lambda c: (round(c.get("tie_off", 0.05), 1),
                                        len(c["warnings"]),
                                        c["face"] == "no-face",
                                        c["doc"], c["page"])):
        key = round(c["value"], 1)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    return uniq if k is None else uniq[:k]


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
    pat_same = _re.compile(r"(?<![A-Z$!'])\$?" + col + r"\$?" + str(row) + r"(?!\d)")
    pat_x = _re.compile(r"(?:'" + _re.escape(sheet) + r"'|" + _re.escape(sheet) + r")!\$?" + col + r"\$?" + str(row) + r"(?!\d)")
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
                if (sh == sheet and pat_same.search(f) and f"{c_}{r}" != coord) or (sh != sheet and pat_x.search(f)):
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


def build_queue(loop):
    """The machine's own work list — spec- and ledger-derived only.
    Red FORMULA cells are not serve material (set_input rightly refuses
    designed formulas): they go to phase0's rewrite attempt and, failing
    that, stay red for the analyst. Serve cards are hardcode inputs."""
    items = []
    for sheet, row in _red_cells(loop):
        col = _tcol(loop, sheet)
        if not col or sheet not in loop.wb.sheetnames:
            continue
        held = loop.wb[sheet][f"{col}{row}"].value
        if isinstance(held, str) and held.startswith("="):
            continue
        pv, _t = _prior_of(loop, sheet, row)
        lb = getattr(loop, "load_bearing", None) or set()
        # LOAD-BEARING OUTRANKS SIZE (run-215: the fuel-clause cell —
        # prior 370, feeding the balance check — lost its card slot to
        # bigger rows that feed nothing; the tier law applied to cards)
        items.append(WorkItem("SERVE", sheet, row,
                              priority=(1e9 if (sheet, row) in lb else 0.0)
                              + abs(pv or 0.0)))
    # ROWS THE MODEL NAMES BUT NEVER FILLED (owner 2026-09-08): no prior to
    # tie, no flag to raise — yet the report may state the figure in a
    # sentence (DFE 'New orders'). Such rows get a label-only card when
    # the report offers a kin line. They sit LAST in the queue; the call
    # budget (the hour) decides how many run
    # (no fixed cap — the owner's ruling against magic numbers).
    seen_rows = {(w.sheet, w.row) for w in items}
    added = 0
    for (sheet, row), t in sorted(loop.targets.items()):
        if (sheet, row) in seen_rows:
            continue
        if isinstance(getattr(t, "prior_value", None), (int, float)):
            continue
        col = _tcol(loop, sheet)
        if not col or sheet not in loop.wb.sheetnames:
            continue
        if loop.wb[sheet][f"{col}{row}"].value not in (None, ""):
            continue
        if not str(getattr(t, "label", "") or "").strip():
            continue
        # the model's own CHECK / difference / balancing rows are never
        # inputs (run 256: label cards served 0.08 into '投资活动现金流入差额
        # (合计平衡项目)' and 2,208 into the direct-method difference row)
        from .discover import _CHECK_LABEL as _CHK
        if _CHK.search(str(t.label)) or any(
                c.get("sheet") == sheet and int(c.get("row", -1)) == row
                for c in (loop.spec.get("check_rows") or [])):
            continue
        # THE NEVER-FILLED ROW (owner 2026-09-14, superseding the 2026-09-08
        # label-card exception): a row holding no number in any period is
        # not an input — the writer refuses it; no card is dealt for it
        from .reader import never_filled
        if never_filled(loop.wb, sheet, row, col):
            continue
        if not _label_only_candidates(loop, sheet, row, t, 1):
            continue
        items.append(WorkItem("LABEL", sheet, row, priority=0.0))
        added += 1
    # THE ROLLOVER INVESTIGATION (owner teaching 2026-09-03): strange
    # first-forecast moves become cards with a probed dossier
    est_base = getattr(loop, "est_base", None)
    if est_base:
        from .rollover import rollover_anomalies
        done = {v.split(":", 1)[0] for v in loop.writer.log.get("verdicts", [])}
        for a in rollover_anomalies(loop.wb, loop.spec, loop.ty, est_base, cap=30,
                                    key_rows=loop.spec.get("key_rows") or []):
            if f"{a['sheet']}!{a['row']}" in done:
                continue
            items.append(WorkItem("ROLLOVER", a["sheet"], a["row"],
                                  priority=(1e9 if a["key"] else 0.0) + a["size"]))
    for g in loop._trip_groups():
        refs = [f"{s}!{c}{r}" for s, c, r, *_ in g]
        done = {v.split(":", 1)[0] for v in
                loop.writer.log.get("verdicts", [])}
        refs = [r for r in refs if r not in done]
        if refs:
            items.append(WorkItem("TRIPWIRE", refs=refs,
                                  priority=float(len(refs))))
    for sheet, row, res in loop._failing_target_checks():
        items.append(WorkItem("COMPONENT", sheet, row,
                              check=f"{sheet}!{row}", priority=abs(res)))
        items.append(WorkItem("PLUG", sheet, row,
                              check=f"{sheet}!{row}", priority=abs(res)))
    # THE ANALYST'S ORDER (owner 2026-09-04): mark the actuals, sanity-
    # check the rollover (a strange forecast usually means a wrong
    # actual-year input), THEN close the balance on the corrected inputs.
    # The balance cards (COMPONENT/PLUG) keep a RESERVED share of the
    # call budget so the serve/rollover flood can never starve them
    # (run 230's failure mode).
    # THE SENSE CHECK'S REVIEW ITEMS (owner 2026-09-09): the actual-year
    # cells feeding a headline line whose forecast moved out of line with
    # the actual go FIRST, whatever their colour, with the reason on the card
    prio = getattr(loop, "sense_priority", None) or {}
    have = {(w.sheet, w.row) for w in items if w.kind == "SERVE"}
    for (sh, r), (why, pr) in prio.items():
        items = [w for w in items if not (w.kind == "SERVE" and (w.sheet, w.row) == (sh, r))]
        items.append(WorkItem("SENSE", sh, r, priority=pr, note=why))
    order = {"SENSE": -1, "SERVE": 0, "ROLLOVER": 1, "COMPONENT": 2, "TRIPWIRE": 3, "PLUG": 4,
             "LABEL": 5}       # label-only cards for never-filled rows: last, budget-bound
    items.sort(key=lambda w: (order[w.kind], -w.priority, w.sheet, w.row))
    # NO CAP (owner 2026-09-08, "why is it capped though"): the run budget
    # decides — run_queue's deadline (what is left of the hour) drains the
    # tail; a size-sorted cap here dropped
    # the bond line (prior 593) before its card could ask 'same item?'
    return items


def phase0(loop, log):
    """Everything the gates already decide, applied by code through the
    SAME guarded tools — no new authority, just no LLM round-trip."""
    n = 0
    for sheet, row, _res in loop._failing_target_checks():
        diag = loop.t_diagnose_balance({"check": f"{sheet}!{row}"})
        for m in list(re.finditer(r"GUILTY (\S+)!(\d+)", diag))[:6]:
            r = loop.t_apply_diff({"row": f"{m.group(1)}!{m.group(2)}"})
            n += str(r).startswith(("WRITTEN", "REWRITTEN"))
            log(f"[queue] phase0 apply_diff {m.group(1)}!{m.group(2)} -> "
                f"{str(r).splitlines()[0][:70]}")
        for m in list(re.finditer(
                r"STALE COMPOSITE (\S+)![A-Z]{1,3}(\d+)", diag))[:6]:
            r = loop.t_rewrite_constants(
                {"cell": f"{m.group(1)}!{m.group(2)}"})
            n += str(r).startswith("REWRITTEN")
            log(f"[queue] phase0 rewrite {m.group(1)}!{m.group(2)} -> "
                f"{str(r).splitlines()[0][:70]}")
    # red FORMULA cells: one proof-gated rewrite attempt each (the
    # constants law is deterministic — REWRITTEN when every literal
    # proves, untouched-red otherwise). Bounded.
    tried = 0
    for sheet, row in _red_cells(loop):
        if tried >= 20:
            break
        col = _tcol(loop, sheet)
        if not col or sheet not in loop.wb.sheetnames:
            continue
        held = loop.wb[sheet][f"{col}{row}"].value
        if not (isinstance(held, str) and held.startswith("=")):
            continue
        tried += 1
        r = loop.t_rewrite_constants({"cell": f"{sheet}!{row}"})
        if str(r).startswith("REWRITTEN"):
            n += 1
            log(f"[queue] phase0 rewrite(red) {sheet}!{row} -> "
                f"{str(r).splitlines()[0][:70]}")
    return n


def render_card(loop, item):
    """The card, from LIVE state. -> (text, options) where options maps
    answer-id -> (tool_name, args). None = item is moot."""
    if item.kind in ("SERVE", "LABEL", "SENSE"):
        sheet, row = item.sheet, item.row
        col = _tcol(loop, sheet)
        if not col or sheet not in loop.wb.sheetnames:
            return None
        if item.kind == "LABEL":
            if loop.wb[sheet][f"{col}{row}"].value not in (None, ""):
                return None                 # filled since queueing: moot
        elif item.kind == "SERVE" and f"{sheet}!{col}{row}" not in loop.writer.log.get("flags", []):
            return None                     # cleared since queueing: moot
        cands = candidates_for(loop, sheet, row)
        try:
            from .investigate import derivations as _derivs
            _derived = _derivs(loop, sheet, f"{col}{row}")
        except Exception:
            _derived = []
        if not cands and not _derived:
            return None                     # nothing to adjudicate: no printed line, no proven consumer
        pv, t = _prior_of(loop, sheet, row)
        held = loop.wb[sheet][f"{col}{row}"].value
        lab = str(t.label)[:40] if t is not None else "?"
        # THE ARITHMETIC ARBITER (runs 221-225: two printed lines both
        # tied the fuel-clause prior — the BS receivable 20 and the
        # scheme fund balance -1,043 — a definitional fork no label can
        # settle. The model's own checks can: probe each candidate and
        # print what it does to the failing checks. The COMPONENT cards
        # already do this; SERVE cards now do too.)
        fails = loop._failing_target_checks()
        probe = {}
        if fails and len(cands) <= 4 and isinstance(held, (int, float)):
            cell_p = loop.wb[sheet][f"{col}{row}"]
            base = sum(abs(r) for _s, _r, r in fails)
            for c in cands:
                cell_p.value = c["value"]
                try:
                    after = sum(abs(r) for _s, _r, r
                                in loop._failing_target_checks())
                except Exception:
                    after = None
                if isinstance(after, (int, float)):
                    probe[round(c["value"], 1)] = (base, after)
            cell_p.value = held
        lines = [f"CARD {'SENSE' if item.kind == 'SENSE' else 'SERVE'} {sheet}!{col}{row} '{lab}'"]
        # THE ROW'S PLACE IN THE MODEL (owner 2026-09-15): what the analyst sees
        # before judging — the section headers, the history, the formulas that
        # use the row (CLP ROAFNA!71: a capacity figure served into a net-additions row)
        _where, _used = row_context(loop, sheet, col, row, lab)
        if _where:
            lines.append(_where)
        if _used:
            lines.append(_used)
        _story = cell_story(loop, sheet, col, row)
        if _story:
            lines.append(_story)
        if item.kind == "SENSE":
            lines.append("  " + item.note)
            lines.append("  This cell feeds that line. Review it: keep the held figure only if its source is right; "
                         "otherwise serve the candidate whose printed line ties the prior AND names this item.")
        lines += [(f"  holds: {held!r}" + (" (RED: stale/unproven)" if item.kind == "SERVE" else "") if item.kind != "LABEL"
                  else "  holds: nothing — a row the model names but never filled; "
                       "no prior year to tie: judge by the item's meaning (lands red)"),
                 f"  prior year: {pv:,.2f}" if pv is not None else ""]
        if item.kind == "LABEL":
            # SCOPE AND COMPETING HOMES (runs 255/257: the group order-intake
            # sentence landed on a Driver segment row, the group debt on the
            # India sheet — the brain never saw that a better home existed)
            from .numerics import kinship as _kin_h
            lines.append(f"  SCOPE: this row lives on sheet '{sheet}' — a segment or entity "
                         "sheet takes that entity's own figure, never the group total; "
                         "qualifiers in the row's label (a product, a region) must match the line")
            homes = [(f"{s2}!{r2}", str(t2.label)[:40],
                      (f"{t2.prior_value:,.2f}" if isinstance(t2.prior_value, (int, float)) else "no prior"))
                     for (s2, r2), t2 in loop.targets.items()
                     if (s2, r2) != (sheet, row) and _kin_h(str(t2.label or ""), lab)][:6]
            if homes:
                lines.append("  OTHER ROWS NAMED LIKE THIS ONE (a figure has ONE home — if a "
                             "candidate belongs to one of these, answer not_disclosed here): "
                             + "; ".join(f"{h[0]} '{h[1]}' ({h[2]})" for h in homes))
        lines.append("  candidates (machine-extracted; warnings are the "
                     "machine's own doubts):")
        options = {}
        best_fit = None
        if probe:
            gains = {k: b0 - a0 for k, (b0, a0) in probe.items()}
            top = max(gains.values())
            if top > 1 and sum(1 for g in gains.values()
                               if g > top - 1) == 1:
                best_fit = max(gains, key=gains.get)
        for j, c in enumerate(cands):
            cid = chr(ord("A") + j)
            w = ("  ⚠ " + "; ⚠ ".join(c["warnings"])) if c["warnings"] else ""
            b = f"  [{c['basis']}]" if c.get("basis") else ""
            # THE STRONGEST FACT, SAID OUT LOUD (runs 221-225: the
            # fuel-clause card's right candidate tied the row's prior
            # EXACTLY and Luna passed it over three times — the card
            # never stated the tie, only the absence of warnings)
            to = c.get("tie_off")
            tie = ("  ✔ prior tie EXACT (this line's comparative = the "
                   "model's prior)" if isinstance(to, (int, float))
                   and to <= 0.6 else
                   (f"  ~ prior tie loose (off {to:,.1f})"
                    if isinstance(to, (int, float)) else ""))
            pr = probe.get(round(c["value"], 1))
            arb = ""
            if pr:
                b0, a0 = pr
                arb = (f"  ⇒ failing checks {b0:,.0f} -> {a0:,.0f} "
                       + ("(IMPROVES MOST — best fit to the model's own "
                          "checks)" if best_fit is not None
                          and round(c["value"], 1) == best_fit else
                          "(improves)" if a0 < b0 - 1 else
                          "(worsens)" if a0 > b0 + 1 else "(no effect)"))
            lines.append(f"    {cid}: {c['value']:,.2f} — {c['doc'][:24]} "
                         f"p{c['page']} [{c['face']}] '{c['line'][:44]}'"
                         f"{b}{tie}{arb}{w}")
            options[f"serve:{cid}"] = ("set_input", {
                "cell": f"{sheet}!{col}{row}", "value": c["value"],
                "nil": bool(c.get("nil")),
                "flag": "red" if c.get("no_prior") else None,
                "no_prior": bool(c.get("no_prior")),
                "noun_proven": bool(c.get("noun_proven")),
                "card": "sense" if item.kind == "SENSE" else None,
                "why": f"p{c['page']}: '{c['line'][:40]}' ({c['doc'][:28]}) "
                       f"— {'sense-check review' if item.kind == 'SENSE' else 'card-adjudicated'}"
                       + (" — printed blank this year, judged the same item: 0"
                          if c.get("nil") else "")})
        # THE DERIVED FILL on this card too (owner 2026-09-15: "make sure it's
        # applied in all cards"): code's derivations from proven consumers, and
        # the brain's own route — one card, one answer, the same tool verifies
        try:
            for j, (u_ref, u_lab, implied, target, why) in enumerate(_derived):
                lines.append(f"    derive:{j + 1}: {implied:,.2f} — the value that makes {u_ref} '{u_lab}' equal its proven {target:,.2f} ({why}); lands orange with that proof")
                options[f"derive:{j + 1}"] = ("derive", {"cell": f"{sheet}!{col}{row}", "via": u_ref,
                                                        "why": f"card-adjudicated derivation via {u_ref}"})
        except Exception:
            pass
        lines.append("    derive:via: derive it yourself — name in 'why' a formula cell that uses this row and whose figure is proven; code solves and verifies")
        options["derive:via"] = ("derive_via", {"cell": f"{sheet}!{col}{row}"})
        options["not_disclosed"] = (None, None)
        lines.append("  answers: " + ", ".join(options)
                     + "  (not_disclosed = leave red for the analyst)")
        return "\n".join(x for x in lines if x), options, "not_disclosed"
    if item.kind == "ROLLOVER":
        from .rollover import dossier, render, rollover_anomalies
        est_base = getattr(loop, "est_base", None) or {}
        anoms = [a for a in rollover_anomalies(loop.wb, loop.spec, loop.ty,
                                               est_base, cap=60)
                 if a["sheet"] == item.sheet and a["row"] == item.row]
        if not anoms:
            return None                   # no longer strange (repaired upstream)
        a = anoms[0]
        cands = dossier(loop.wb, loop.spec, loop.ty, item.sheet, item.row,
                        a["old_f"], loop.writer.log.get("writes_all", []),
                        loop._leaf_inputs_ranges, served=loop.served,
                        flags=loop.writer.log.get("flags", []))
        return render(a, cands)
    if item.kind == "TRIPWIRE":
        done = {v.split(":", 1)[0] for v in
                loop.writer.log.get("verdicts", [])}
        refs = [r for r in item.refs if r not in done]
        if not refs:
            return None
        ev = Evaluator(loop.wb)
        sample = []
        for ref in refs[:3]:
            try:
                sh, coord = ref.split("!")
                r_ = int(re.sub(r"[A-Z]", "", coord)); c_ = re.sub(r"\d", "", coord)
                sample.append(f"{ref} computes {ev.cell(sh, coord):,.1f} [{row_context_short(loop, sh, c_, r_)}]")
            except Exception:
                sample.append(ref)
        lines = [f"CARD TRIPWIRE chain of {len(refs)} sign-flipped "
                 "forecast rows sharing upstream inputs:",
                 "  " + "; ".join(sample),
                 "  The actual-year causes feeding them have just been "
                 "repaired where evidence allowed. Judge the chain:",
                 "  answers: error_fixed (causes repaired, values now "
                 "sane), justified (disclosure supports the sign), "
                 "suspicious (unresolved — analyst must look)"]
        options = {
            "error_fixed": ("verdict", {"items": refs,
                                        "verdict": "ERROR_FIXED",
                                        "why": "card: causes repaired"}),
            "justified": ("verdict", {"items": refs, "verdict": "JUSTIFIED",
                                      "why": "card: supported"}),
            "suspicious": ("verdict", {"items": refs,
                                       "verdict": "SUSPICIOUS",
                                       "why": "card: unresolved"})}
        return "\n".join(lines), options, "suspicious"
    if item.kind == "COMPONENT":
        # THE RECEIPTS CARD (run-211 autopsy: a 5,293 balance gap was
        # plugged into ONE cell when the truth was a printed two-cell
        # split — the machinery never ASKED about the check's own
        # components). For each numeric input feeding the failing check
        # that has a printed candidate, the probe MEASURES what serving
        # it does to the residual — "closes the check" is shown, not
        # guessed.
        sheet, row = item.sheet, item.row
        col = _tcol(loop, sheet)
        ev = Evaluator(loop.wb)
        try:
            residual = ev.cell(sheet, f"{col}{row}")
        except Exception:
            return None
        if abs(residual) <= 1.0:
            return None
        offers = []
        leaves = list(dict.fromkeys(
            loop._leaf_inputs(sheet, f"{col}{row}")))
        for sh, coord in leaves:
            m = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
            if not m or m.group(1) != _tcol(loop, sh):
                continue
            cur = loop.wb[sh][coord].value
            if not isinstance(cur, (int, float)):
                continue
            r2 = int(m.group(2))
            cands = candidates_for(loop, sh, r2, k=3)
            # SAME-LINE candidates: a number CO-PRINTED with the leaf's
            # prior in one line is a candidate even when not adjacent
            # (p17 'NCI' [6,063, 26,258, 9,815] — the model folds NCI
            # and PCS into one row; the closing 9,815 sits two slots
            # from the prior 6,063). The probe demotes the garbage.
            pv_l, _tl = _prior_of(loop, sh, r2)
            periods = getattr(loop.ledger, "_doc_periods", None) or {}
            if pv_l:
                nline = 0
                from .reconcile import table_kind as _tkind
                _tabs = {}
                for it2 in loop.ledger.items:
                    _tabs.setdefault((it2.doc, it2.page, it2.table_id), []).append(it2)
                _tol_l = max(0.6, abs(pv_l) * 5e-4)
                for it2 in loop.ledger.items:
                    if periods.get(it2.doc) != "current" or nline >= 3:
                        continue
                    ns2 = it2.nums or []
                    if not any(abs(abs(n) - abs(pv_l)) <= _tol_l for n in ns2):
                        continue
                    if _tkind(_tabs.get((it2.doc, it2.page, it2.table_id), [])) == "matrix":
                        continue      # evidence: a matrix row's columns are categories — the numbers beside the prior are other segments, not this year (run 262: intangibles served a segment's goodwill)
                    # THE SIGN OF THE TIE (run 262: the fuel clause closed
                    # (1,043) where last year's 370 printed as (370) — the
                    # line negates the model's convention, so its current
                    # negates too; the held value's sign is a forecast, not
                    # evidence)
                    _flip = not any(abs(n - pv_l) <= _tol_l for n in ns2)
                    for n in ns2:
                        if abs(abs(n) - abs(pv_l)) <= 0.6 or abs(n) < 10:
                            continue
                        if not (abs(n) <= 30 * abs(pv_l)
                                and abs(n) * 30 >= abs(pv_l)):
                            continue
                        v = -n if _flip else n
                        cands.append({
                            "value": v, "doc": it2.doc, "page": it2.page,
                            "line": str(it2.label)[:60],
                            "face": loop.ledger.face(it2.doc, it2.page)
                            or "no-face", "warnings": [],
                            "basis": (f"co-printed with the prior "
                                      f"{pv_l:,.1f} on one line")})
                        nline += 1
            # NO residual-completion candidates (run-212 autopsy: a
            # cur±residual value matched against ANY printed number
            # "closes the check" TAUTOLOGICALLY — a wrong plug wearing
            # a citation; the red-team's garbage-card prediction
            # observed live as 'Property under development -> -4,606'.
            # The evidence law refused it, but it must not be OFFERED).
            # Candidates are evidence-grounded only: prior-tie,
            # positional companion, co-printed with the prior.
            seen_v = set()
            for c in cands:
                if abs(c["value"] - cur) <= max(1.0, abs(cur) * 2e-3):
                    continue
                if round(c["value"], 1) in seen_v:
                    continue
                seen_v.add(round(c["value"], 1))
                ws = loop.wb[sh]
                old = ws[coord].value
                ws[coord] = c["value"]
                try:
                    after = Evaluator(loop.wb).cell(sheet, f"{col}{row}")
                except Exception:
                    after = None
                ws[coord] = old
                if not isinstance(after, (int, float)):
                    continue
                if (c["value"] < 0) != (cur < 0) and abs(cur) >= 10:
                    c = dict(c)
                    c["warnings"] = c["warnings"] + [
                        "SIGN FLIP vs the held value — almost never a "
                        "genuine serve"]
                offers.append((abs(after), sh, r2, coord, cur, c, after))
        if not offers:
            return None
        # evidence quality outranks the probe: a clean candidate that
        # merely IMPROVES beats a warned one that "closes" (run-212: the
        # closers were the garbage)
        offers.sort(key=lambda o: (len(o[5]["warnings"]), o[0], o[1], o[2]))
        offers = offers[:4]
        lines = [f"CARD COMPONENT check {sheet}!{col}{row} residual = "
                 f"{residual:,.2f}",
                 "  printed values exist for these components; the probe "
                 "shows what serving each does to the check:"]
        options = {}
        for j, (aft_abs, sh, r2, coord, cur, c, after) in enumerate(offers):
            t = loop.targets.get((sh, r2))
            lab = str(t.label)[:30] if t is not None else "?"
            mark = " <== CLOSES the check" if aft_abs <= 1.0 else ""
            w = ("  ⚠ " + "; ⚠ ".join(c["warnings"])) if c["warnings"] else ""
            lines.append(
                f"    fix:{j} {sh}!{coord} '{lab}' {cur:,.2f} -> "
                f"{c['value']:,.2f} ({c['doc'][:22]} p{c['page']} "
                f"'{c['line'][:36]}') residual {residual:,.1f} -> "
                f"{after:,.1f}{mark}{w}")
            lines.append(f"          [{row_context_short(loop, sh, _tcol(loop, sh), r2)}]")
            options[f"fix:{j}"] = ("set_input", {
                "cell": f"{sh}!{coord}", "value": c["value"],
                "card": "component", "check": f"{sheet}!{row}",
                "why": f"p{c['page']}: '{c['line'][:40]}' "
                       f"({c['doc'][:26]}) — component card: check "
                       f"residual {residual:,.1f} -> {after:,.1f}"})
        options["not_disclosed"] = (None, None)
        lines.append("  answers: " + ", ".join(options)
                     + "  (not_disclosed = leave the check for the plug "
                       "decision)")
        return "\n".join(lines), options, "not_disclosed"
    if item.kind == "PLUG":
        sheet, row = item.sheet, item.row
        still = [(s, r) for s, r, _ in loop._failing_target_checks()
                 if (s, r) == (sheet, row)]
        if not still:
            return None
        diag = loop.t_diagnose_balance({"check": f"{sheet}!{row}"})
        if "GUILTY" in diag:
            return None       # evidence remains: not this card's turn yet
        res = re.search(r"residual = ([-\d,\.]+)", diag)
        hyp = _residual_hypotheses(
            loop, float(res.group(1).replace(",", "")) if res else 0.0)
        sites = re.findall(r"^\s+(\S+)![A-Z]{1,3}(\d+) '([^']*)' = ([-\d,\.]+)",
                           diag, re.M)[:3]
        lines = ["CARD PLUG " + diag.splitlines()[0],
                 "  no component has unclaimed evidence. " + hyp,
                 "  A plug trades truth for balance and is orange-flagged "
                 "for the analyst. The refusing answer leaves the check "
                 "failing, loudly, for the terminal ladder and report."]
        options = {}
        for j, (sh, r, lab, _cur) in enumerate(sites):
            options[f"plug:{j}"] = ("plug_residual", {
                "check": f"{sheet}!{row}", "into": f"{sh}!{_tcol(loop, sh)}{r}",
                "why": f"card-adjudicated last resort into '{lab[:30]}'"})
            lines.append(f"    plug:{j} -> {sh}!{r} '{lab[:30]}'  [{row_context_short(loop, sh, _tcol(loop, sh), r)}]")
        options["refuse_flag"] = (None, None)
        lines.append("  answers: " + ", ".join(options))
        return "\n".join(lines), options, "refuse_flag"
    return None


def _residual_hypotheses(loop, residual):
    """Red-team Case A/D generator: printed lines whose value ≈ the
    residual are named ON the plug card — the analyst's first question."""
    if not residual:
        return ""
    prior_docs = _vintage_ban(loop.ledger)
    hits = []
    for it in loop.ledger.items:
        if not _sourceable(it):
            continue
        if any(abs(abs(n) - abs(residual)) <= max(1.0, abs(residual) * 5e-3)
               for n in (it.nums or [])):
            hits.append(f"'{str(it.label)[:36]}' ({it.doc[:20]} p{it.page})")
        if len(hits) >= 3:
            break
    return ("Residual matches printed line(s): " + "; ".join(hits) + "."
            if hits else "Residual matches no printed line.")


def _llm_answer(loop, client, text, options, log):
    def _val(o):
        if not isinstance(o, dict) or o.get("answer") not in options:
            return [f"answer must be one of {sorted(options)}"]
        return []
    obj = client.json(_SYSTEM, text, _val, repair_retries=1)
    return obj.get("answer"), str(obj.get("why", ""))[:120]


def run_queue(loop, client, log, answerer=None, deadline_s=DEADLINE_S, items=None):
    """The inverted stage 4. `answerer(text, options, default) -> answer
    id` overrides the LLM (offline drivers, tests).

    THE BUDGET IS TIME (owner 2026-09-08, run 250): the run's own target
    is the hour; `deadline_s` is what is left of it when the queue
    starts. Run 250 drained 92 cards on a 60-call cap while 25 minutes of
    the hour sat unused — the order-intake card among them. The balance
    cards (COMPONENT/PLUG) are few and close the model: they are asked
    regardless of the clock."""
    t0 = time.monotonic()
    if items is not None:                 # the sense check's final pass: its own short list
        n_auto = 0
        queue = list(items)
    else:
        n_auto = phase0(loop, log)
        queue = build_queue(loop)
    # plugs are dealt strictly LAST — a re-dealt COMPONENT card (next
    # receipt after a landed fix) must always outrank the plug decision
    work = [w for w in queue if w.kind != "PLUG"]
    plugs = [w for w in queue if w.kind == "PLUG"]
    calls = dead = done = defaulted = moot = 0
    breaker = 0
    seq, i = work, 0
    while True:
        if i >= len(seq):
            if seq is work:
                seq, i = plugs, 0
                loop.writer.plugs_allowed = True      # THE PLUG LAW: every evidence card has been dealt
                continue
            break
        item = seq[i]
        i += 1
        rendered = render_card(loop, item)
        try:
            _cand_lines = [ln.strip() for ln in str(rendered[0] if isinstance(rendered, tuple) else rendered).splitlines()
                           if ln.startswith("    ") and ln.strip()][:8]
            if _cand_lines:
                log(f"[queue] card {item.kind} {item.sheet}!{item.row or ''}: " + " | ".join(_cand_lines)[:900])
        except Exception:
            pass
        if rendered is None:
            item.state = "MOOT"
            moot += 1
            if item.kind == "SERVE":
                col = _tcol(loop, item.sheet)
                in_flags = f"{item.sheet}!{col}{item.row}" in \
                    loop.writer.log.get("flags", [])
                why_moot = ("no candidates" if in_flags
                            else "flag cleared")
                if in_flags:
                    # zero candidates IS an examination (the move-on
                    # law): document the look so the gate counts a
                    # finding, not neglect
                    loop.TOOLS["flag_cell"](loop, {
                        "cell": f"{item.sheet}!{item.row}",
                        "why": ("card rendered with ZERO candidates — "
                                "no current-document line ties this "
                                "row's prior at any scale; not "
                                "disclosed by triangulation, held at "
                                "prior for the analyst")})
                log(f"[queue] MOOT SERVE {item.sheet}!{item.row} "
                    f"({why_moot})")
            else:
                log(f"[queue] MOOT {item.kind} {item.sheet}!{item.row or ''}"
                    f" {item.check or ''}")
            continue
        text, options, default = rendered
        ans, why = default, "default"
        elapsed = time.monotonic() - t0
        drain = (breaker >= 3
                 or (item.kind not in ("COMPONENT", "PLUG") and elapsed > deadline_s)
                 or elapsed > deadline_s + 300)          # the grace for balance cards is five minutes, then everything drains
        if not drain:
            try:
                if answerer is not None:
                    ans = answerer(text, options, default)
                    why = "scripted"
                elif client is not None:
                    calls += 1
                    _c0 = time.monotonic()
                    ans, why = _llm_answer(loop, client, text, options, log)
                    # a call that took longer than five minutes counts as a dead endpoint (time, not exceptions)
                    breaker = breaker + 1 if time.monotonic() - _c0 > 300 else 0
                if ans not in options:
                    ans, why = default, "invalid->default"
            except Exception as e:
                breaker += 1
                ans, why = default, f"client error -> default ({e})"
        else:
            dead += 1
        tool, args = options[ans]
        if tool == "derive_via":
            m_via = re.search(r"((?:'[^']+'|[A-Za-z0-9_ ]+)!\$?[A-Z]{1,3}\$?\d+)", str(why or ""))
            tool = "derive"
            args = dict(args, via=(m_via.group(1) if m_via else ""), why=f"the brain's own route: {str(why or '')[:80]}")
        if tool is None:
            item.state = "DEFAULTED" if ans == default else "DONE"
            defaulted += ans == default
            if item.kind in ("SERVE", "COMPONENT") and item.row:
                # the card's verdict on this row is recorded: a fix the cards
                # ruled out no longer blocks the last resort (diagnose_balance)
                loop.writer.log.setdefault("ruled_out", []).append(f"{item.sheet}!{item.row}")
            if item.kind == "SERVE" and (item.sheet, item.row) not in (loop.served or {}):
                # a not_disclosed adjudication IS an examination (the
                # move-on law): document the look on the cell so the
                # gate counts a finding, not neglect — unless the cell
                # already holds a served value with its own note (the
                # new-line serve, run 254): a default never overwrites it
                ncand = text.count("\n    ")
                loop.TOOLS["flag_cell"](loop, {
                    "cell": f"{item.sheet}!{item.row}",
                    "why": (f"card-adjudicated NOT PROVEN: {ncand} "
                            f"candidate(s) reviewed and rejected "
                            f"({why[:50]}) — value left at prior for "
                            "the analyst")})
            log(f"[queue] {item.kind} {item.sheet}!{item.row or ''} "
                f"-> {ans} ({why[:60]})")
            continue
        try:
            res = str(loop.TOOLS[tool](loop, args))
        except Exception as e:
            res = f"TOOL ERROR: {e}"
        if res.startswith(("REFUSED", "MISS")) and len(options) > 2 \
                and not drain:
            # THE RE-ASK (run-216 autopsy: Luna picked candidate D on
            # the fuel-clause card, the one-home law refused it, and
            # the card was ABANDONED with the clean candidate A still
            # sitting on it). A refusal is information — show it, drop
            # the refused option, ask ONCE more.
            log(f"[queue] {item.kind} {item.sheet}!{item.row or ''} "
                f"-> {ans} REFUSED — re-asking without it "
                f"({res.splitlines()[0][:140]})")
            options2 = {k: v for k, v in options.items() if k != ans}
            text2 = (text + f"\n  NOTE: your previous answer '{ans}' was "
                     f"refused by the write guard: "
                     f"{res.splitlines()[0][:120]}\n  choose among the "
                     "remaining answers only.")
            try:
                if answerer is not None:
                    ans2 = answerer(text2, options2, default)
                elif client is not None:
                    calls += 1
                    ans2, why = _llm_answer(loop, client, text2, options2,
                                            log)
                else:
                    ans2 = default
                if ans2 not in options2:
                    ans2 = default
            except Exception:
                ans2 = default
            ans = ans2
            tool, args = options2.get(ans, (None, None))
            if tool is None:
                item.state = "DEFAULTED"
                defaulted += 1
                log(f"[queue] {item.kind} {item.sheet}!{item.row or ''} "
                    f"-> {ans} (after refusal)")
                continue
            try:
                res = str(loop.TOOLS[tool](loop, args))
            except Exception as e:
                res = f"TOOL ERROR: {e}"
        item.state = "DONE"
        done += 1
        log(f"[queue] {item.kind} {item.sheet}!{item.row or ''} -> {ans}: "
            f"{res.splitlines()[0][:90]}")
        if item.kind == "COMPONENT" and res.startswith("WRITTEN"):
            # a landed component fix may reveal the NEXT receipt (the
            # 84,367-then-9,815 sequence): re-deal for the same check,
            # bounded to 3 rounds
            rounds = sum(1 for w in work if w.kind == "COMPONENT"
                         and w.check == item.check)
            if rounds < 3 and any(
                    (s, r) == (item.sheet, item.row)
                    for s, r, _ in loop._failing_target_checks()):
                work.append(WorkItem("COMPONENT", item.sheet, item.row,
                                     check=item.check,
                                     priority=item.priority))
    # THE EXAMINATION CLOSER (owner bar 2026-09-02: an unexamined red is
    # neglect; a documented look is a finding). Every red cell the queue
    # did not reach — capped, moot, or never carded — gets its look
    # documented: candidates found (listed, awaiting adjudication) or
    # provably none (not disclosed by triangulation).
    n_doc = 0
    for sheet, row in _red_cells(loop):
        col = _tcol(loop, sheet)
        if not col or sheet not in loop.wb.sheetnames:
            continue
        cmt = loop.wb[sheet][f"{col}{row}"].comment
        if cmt is not None and "STALE INPUT" not in str(cmt.text):
            continue                      # already an examined finding
        cands = candidates_for(loop, sheet, row, k=2)
        if cands:
            why = ("QUEUE-DOCUMENTED: candidate(s) exist, awaiting "
                   "adjudication — " + "; ".join(
                       f"{c['value']:,.1f} ({c['doc'][:18]} p{c['page']})"
                       for c in cands[:2]))
        else:
            why = ("QUEUE-DOCUMENTED: zero candidates — no current-"
                   "document line ties this row's prior at any scale; "
                   "not disclosed by triangulation, held at prior")
        loop.TOOLS["flag_cell"](loop, {"cell": f"{sheet}!{row}",
                                       "why": why})
        n_doc += 1
    summary = (f"queue: {len(queue)} items — {n_auto} auto-resolved in "
               f"phase0, {done} adjudicated, {defaulted} defaulted, "
               f"{moot} moot, {dead} drained, {calls} LLM calls, "
               f"{n_doc} reds documented")
    log(f"[run] {summary}")
    return summary
