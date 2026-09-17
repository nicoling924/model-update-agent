"""The composite-constants law (owner ruling 2026-08-31, CLP run 6).

The silent-carry class, back as a LAW. A target-column formula that
embeds numeric literals (=4976+23, =158532+10183) and still EVALUATES
to its own prior actual is last year's hand-marked actual, never rolled
— run 51's exhibit cell (cash =4976+23) reappeared on CLP because the
old heuristic rewriter was retired with the middle layers (it corrupted
roll-forward bases in run 52) and the capability was never rebuilt.

The law replaces the heuristic with proof:
- TRIGGER: a formula cell in the target column that embeds a literal
  >= LITERAL_FLOOR and evaluates to its own prior actual (the stale
  fingerprint). Cells that compute something new are never touched.
- PROOF, per literal: the literal must tie the COMPARATIVE of a
  current-document face line (prior-identity, in-world scale), and all
  tying lines must agree on ONE current-year counterpart — the same
  figure printed twice (announcement + statements) corroborates, two
  different figures refuse.
- REWRITE: every literal proves or the cell is untouched. The new
  formula preserves the composition (=166094+10034) and lands through
  the writer — numeric preview + band-vs-prior is the run-52 guard: a
  wrong-table tie produces a wild value and is refused.
- HONESTY: an unproven cell keeps its red flag and gains a note naming
  exactly which literals tied what — the loop's evidence, never a
  silent skip.

The thinking this mechanizes (the owner's teaching): stillness is the
signal — in a year where everything moved, a cell equal to its prior is
suspect; and the comparative column is the map — the disclosure prints
last year next to this year, so each stale literal names its own
replacement.
"""
import re

from .ledger import sourceable as _sourceable

from .checks import prior_column, year_columns
from .evaluator import Evaluator
from .numerics import SCALES, row_tol, to_model_units

LITERAL_FLOOR = 100.0     # a cell must embed one literal this big to trigger
VINTAGE_FLOOR = 50.0      # vintage mode: smaller carried actuals qualify
STALE_TOL = 1.0           # evaluated == prior actual within this = stale
AXIS_BAND = 3             # header rows, never swept

# structural scalers, never carried actuals: unit conversions, percent
# factors, hours-in-a-year — they stay in the formula untouched and
# neither trigger nor fail a cell (run-198 offline proof: 1000, 100 and
# 8760 all tried to "prove" and poisoned the sweep)
MODELING_CONSTANTS = {0.5, 1.0, 2.0, 3.0, 4.0, 10.0, 12.0, 24.0, 52.0, 100.0,
                      365.0, 366.0, 1000.0, 8760.0, 10000.0, 100000.0,
                      1000000.0}

_REF = re.compile(r"(?:'[^']{1,60}'|[A-Za-z_][A-Za-z0-9 _.]{0,30})?!?"
                  r"\$?[A-Z]{1,3}\$?\d{1,5}(?::\$?[A-Z]{1,3}\$?\d{1,5})?")
_LIT = re.compile(r"(?<![A-Za-z0-9_.])(\d+(?:\.\d+)?)(?![\d.])")


def literals_of(formula):
    """Numeric literals embedded in a formula, refs removed first.
    -> list of literal STRINGS in order of appearance (deduped)."""
    body = _REF.sub(" ", formula)
    out = []
    for m in _LIT.finditer(body):
        if m.group(1) not in out and float(m.group(1)) != 0:
            out.append(m.group(1))
    return out


def already_current(ledger, lit, row_label=""):
    """THE ALREADY-CURRENT GUARD (run-232 cash autopsy): a literal that
    prints as THIS YEAR's figure on a current statement face — the
    first number of a (current, prior) line whose prior differs — is
    already updated. Re-mapping it because it also appears as a
    comparative elsewhere (the cash MOVEMENT row 'opening 4,976 |
    -787 | closing 3,905' paired 3,905 with 787) rewrote a correct
    =3905+23 into =787+23. -> (doc, page, label) or None."""
    v = abs(float(lit))
    if v < 100:
        return None
    from .numerics import kinship
    prior_docs = ledger.noncurrent_docs()
    pv_tabs = getattr(ledger, "_pv_tables", set())
    tol = row_tol(v, base=0.6)
    # the faces vote: the literal is 'current' only if some statement
    # line prints it FIRST (with a different comparative) and NO
    # statement line prints it as a COMPARATIVE — a movement row
    # (opening 4,976 | -787 | closing 3,905) prints last year's cash
    # first, so 4,976 is contested and stays re-mappable
    first, second = None, 0
    for it in ledger.items:
        if getattr(it, "table_kind", None) == "matrix" \
                or not _sourceable(it) or not it.joinable() \
                or (it.doc, it.page, it.table_id) in pv_tabs:
            continue                      # a period line anywhere (owner 2026-09-14: no 'statement pages only')
        ns = [float(n) for n in it.nums if isinstance(n, (int, float))]
        if len(ns) >= 2 and 0 < ns[0] <= 120 and float(ns[0]).is_integer() \
                and min(abs(x) for x in ns[1:]) > 2 * ns[0]:
            ns = ns[1:]
        if len(ns) < 2:
            continue
        if row_label and not kinship(str(it.label or ""), row_label):
            continue
        if abs(abs(ns[1]) - v) <= tol:
            second += 1
        elif abs(abs(ns[0]) - v) <= tol and first is None:
            first = (it.doc, it.page, str(it.label)[:40])
    return first if (first and second == 0) else None


def candidates(ledger, lit, row_label=""):
    """One literal -> {current_value: set of (doc, page)}. A candidate
    is a face line where the literal sits in the COMPARATIVE position
    (nums[i+1]) and the adjacent current figure keeps the literal's
    order of magnitude — a real YoY pair does, a coincidence doesn't.
    The in-world scale is tried first; other scales only if it finds
    nothing (run-198 offline proof: the all-scales union manufactured
    ties)."""
    v = abs(float(lit))
    if already_current(ledger, lit, row_label):
        return {}
    prior_docs = ledger.noncurrent_docs()
    tol = row_tol(v, base=0.6 if v >= 100 else 0.01)

    def scan(scales):
        found = {}
        pv_tabs = getattr(ledger, "_pv_tables", set())
        for it in ledger.items:
            if getattr(it, "table_kind", None) == "matrix" \
                    or not _sourceable(it) or not it.joinable() \
                    or (it.doc, it.page, it.table_id) in pv_tabs:
                continue
            for s in scales:
                ns = [to_model_units(n, s) for n in it.nums]
                # note-column discipline (2026-09-02: '[30, -104, -278]'
                # paired (30, x) and the sweep wrote the NOTE NUMBER
                # into the model): drop a leading positive small int
                # dwarfed by the money that follows
                if len(ns) >= 2 and 0 < ns[0] <= 120 \
                        and float(ns[0]).is_integer() \
                        and min(abs(x) for x in ns[1:]) > 2 * ns[0]:
                    ns = ns[1:]
                for i in range(len(ns) - 1):
                    if abs(abs(ns[i + 1]) - v) > tol:
                        continue
                    cur = abs(ns[i])
                    if not (v / 5.0 <= cur <= v * 5.0):
                        continue
                    # THE TIME-SIGNATURE LAW, ported from the join
                    # (r103 autopsy: 'Finance income' 69 paired with
                    # total 235 inside a WIDE SEGMENT row — segment
                    # neighbours, not years). In a wide row a (cur,
                    # comparative) pair is only a YoY pair if the next
                    # number is their delta; statement components print
                    # as two-number lines anyway.
                    # THE NARROW-LINE LAW (r103 autopsy, final form:
                    # the FY24 segment row 'Finance income [119, 14,
                    # 29, 4, 69, 235]' kept dodging adjacency tests via
                    # its small India column). Statement components
                    # print on NARROW lines — a (current, comparative)
                    # pair, at most with a note ref or a delta. A line
                    # with more than 3 numbers is a segment/series row:
                    # never a YoY source for a composition.
                    if len([x for x in ns if abs(x) >= 0.5]) > 3:
                        continue
                    found.setdefault(round(cur, 2), set()).add(
                        (it.doc, it.page, it.table_id,
                         str(it.label)[:60]))
        return found

    return scan([1]) or scan([s for s in SCALES if s != 1])


def _kin_ok(per_full, lits, vals, row_label):
    """At least ONE tying line of the chosen combination must be kin to
    the row's own label (run-208: 'Other assets' rewrote from an
    EnergyAustralia prose sentence that coincidentally carried both
    literals). Empty row labels can't be checked — pass."""
    if not row_label:
        return True
    from .numerics import STOPWORDS, norm_label

    def _stems(text):
        return {w.rstrip("s") for w in norm_label(text).split()
                if w not in STOPWORDS and len(w) > 2}

    ws_row = _stems(row_label)
    labels = [lab for lit, val in zip(lits, vals)
              for (_d, _p, _t, lab) in per_full.get(lit, {}).get(val, set())]
    if ws_row:
        for lab in labels:
            if ws_row & _stems(lab):
                return True
    # statement labels are SHORT; prose fragments are sentences. A
    # multi-literal composition whose every tying label reads like a
    # statement line passes even without word overlap ('Other
    # non-current liabilities' vs 'Deferred creditors and others' — no
    # shared word, both plainly statement lines; the EnergyAustralia
    # sentence fails on length).
    if len(lits) >= 2:
        ok_all = True
        for lit, val in zip(lits, vals):
            labs = [lab for (_d, _p, _t, lab)
                    in per_full.get(lit, {}).get(val, set())]
            if not labs or not any(
                    len(norm_label(lab).split()) <= 6 for lab in labs):
                ok_all = False
                break
        if ok_all:
            return True
    return False


def prove_cell(ledger, lits, row_label="", trust_names=False):
    """The composition proof (the by-hand method, mechanized): the
    disclosure prints a statement as a PAGE, so a composition's members
    live together — every literal must resolve on a COMMON page, every
    qualifying page must yield the SAME combination (corroboration
    resolves disagreements by page majority), and at least one tying
    line must be KIN to the row's own label (prose-junk guard).
    -> ({lit: (value, src)}, None) or (None, why).
    trust_names: the brain has judged the tying lines to be this row's
    items — the kinship guard steps aside (owner 2026-09-15: the model's
    names differ from the report's; a number that ties is mapped and the
    name is the brain's judgment, never code's)."""
    per_full, per, per_pair, ident = {}, {}, {}, {}
    for lit in lits:
        ac = already_current(ledger, lit, row_label)
        if ac:
            return None, (f"{lit}: already this year's printed figure "
                          f"({ac[0]} p{ac[1]} '{ac[2]}') — nothing to rewrite")
        got = candidates(ledger, lit)
        candidates_pair = {v: set(ps) for v, ps in got.items()}
        # THE UNCHANGED-COMPONENT OPTION (the -35 autopsy 2026-09-01:
        # '=2254-235-15' refused because the 15 — dividends received,
        # SAME both years — prints this year with no comparative pair.
        # The analyst keeps it. So the literal's OWN value, wherever it
        # prints as a current face figure, is always one more candidate
        # — the common-page intersection and page-majority corroboration
        # below arbitrate it against the YoY-pair readings exactly like
        # any other candidate.)
        v = abs(float(lit))
        tol = row_tol(v, base=0.6 if v >= 100 else 0.01)
        prior_docs = ledger.noncurrent_docs()
        pages = set()
        pv_tabs = getattr(ledger, "_pv_tables", set())
        for it in ledger.items:
            if getattr(it, "table_kind", None) == "matrix" \
                    or not _sourceable(it) or not it.joinable() \
                    or (it.doc, it.page, it.table_id) in pv_tabs:
                continue
            if any(abs(abs(n) - v) <= tol for n in it.nums):
                pages.add((it.doc, it.page, it.table_id,
                           str(it.label)[:60]))
        got_pair = dict(candidates_pair or {})
        if pages:
            got.setdefault(round(v, 2), set()).update(pages)
        if not got:
            return None, f"{lit}: no face line's comparative ties it"
        per_full[lit] = got
        # COHERENCE IS TABLE-LEVEL (r103 autopsy: page-level let junk
        # coincidences from other tables of a face page outvote the one
        # printed statement table that holds the whole composition —
        # "a composition's members live TOGETHER" means one table)
        per[lit] = {v: {(d, p, t) for (d, p, t, _l) in ps}
                    for v, ps in got.items()}
        per_pair[lit] = {v: {(d, p, t) for (d, p, t, _l) in ps}
                         for v, ps in got_pair.items()}
        ident[lit] = round(v, 2)
    common = set.intersection(*(
        {p for ps in per[lit].values() for p in ps} for lit in lits))
    if not common:
        # THE UNIQUE TIE ACROSS PAGES (audit 2026-09-15, CLP dividends received
        # =770+1659+15: associates on one note, JCEs on another): when EVERY
        # literal has exactly one comparative-pair reading in the documents,
        # the composition is proven line by line, whatever page each line is on
        uniq = {}
        for lit in lits:
            vp = {v: ps for v, ps in per_pair[lit].items() if ps}
            if len(vp) == 1:
                uniq[lit] = next(iter(vp.items()))
            elif not vp and ident[lit] in per[lit]:
                uniq[lit] = (ident[lit], per[lit][ident[lit]])     # unchanged, printed as is this year
            else:
                uniq = None
                break
        if uniq and any(abs(v - ident[lit]) > 0.6 for lit, (v, _ps) in uniq.items()):
            vals = [uniq[lit][0] for lit in lits]
            # EACH line must be kin to the row or read like a statement line — one kin
            # line cannot vouch for a coincidence on another page (reviewer 2026-09-15:
            # 'Number of directors 12 | 15' rewrote the 15)
            each_kin = all(_kin_ok(per_full, [lit], [v], row_label) for lit, v in zip(lits, vals))
            if trust_names or each_kin:
                return {lit: (v, f"{lit}->{v:g} ({', '.join(f'{d} p{p}' for d, p, _t in sorted(ps)[:2])})")
                        for lit, (v, ps) in uniq.items()}, None
            return None, ("no tying line is kin to the row's own label (each line of a cross-page "
                          "composition must be) — cell untouched")
        return None, ("no single page carries the whole composition — "
                      + "; ".join(
                          f"{lit} ties "
                          + ", ".join(f"{k:,.2f}" for k in sorted(per[lit])[:3])
                          for lit in lits[:3]))
    combos = {}
    for pg in common:
        vals = []
        for lit in lits:
            # a genuine YoY pair on this page OUTRANKS the identity
            # reading; identity (value unchanged, printed here) is the
            # fallback only where no pair value exists on the page
            vp = [v for v, ps in per_pair[lit].items() if pg in ps]
            if len(vp) == 1:
                vals.append(vp[0])
                continue
            if len(vp) > 1:
                break
            if pg in per[lit].get(ident[lit], set()):
                vals.append(ident[lit])
                continue
            break
        else:
            # a combination where NOTHING changed proves nothing — the
            # stale fingerprint said this cell should have moved; an
            # all-identity "proof" is the stale formula laundering
            # itself (caught by the museum before it ever shipped)
            if any(v != ident[lit] for v, lit in zip(vals, lits)):
                combos.setdefault(tuple(vals), []).append(pg)
    if not combos:
        return None, "composition ambiguous on every common page"
    def _n_ident(vals):
        return sum(1 for v, lit in zip(vals, lits)
                   if abs(v - abs(float(lit))) <= 0.6)
    ranked = sorted(combos.items(),
                    key=lambda kv: (_n_ident(kv[0]), -len(kv[1])))
    if len(ranked) > 1:
        # THE CHANGE VOTE (r119, 2026-09-02: the true pair 197+1,418
        # lost page-corroboration to two note coincidences that each
        # mapped a literal TO ITSELF. A real update CHANGES numbers —
        # a combination with strictly fewer identity mappings outranks;
        # only true ties fall back to page-majority corroboration.)
        if _n_ident(ranked[0][0]) < _n_ident(ranked[1][0]):
            pass                          # unique least-identity combo wins
        elif not (len(ranked[0][1]) >= 2
                  and len(ranked[0][1]) > len(ranked[1][1])):
            return None, ("pages disagree on the combination: "
                          + "; ".join("+".join(f"{v:,.0f}" for v in k)
                                      for k in list(combos)[:3]))
    vals, pages = ranked[0]
    if not trust_names and not _kin_ok(per_full, lits, vals, row_label):
        return None, ("no tying line is kin to the row's own label — "
                      "probably a dense page's prose (run-208 lesson); "
                      "cell untouched")
    src = ", ".join(f"{d} p{p}" for d, p, _t in sorted(pages)[:3])
    return {lit: (v, src) for lit, v in zip(lits, vals)}, None


def rewrite_cell(wb, spec, target_year, ledger, writer, sheet, row, trust_names=False):
    """Apply the law to ONE cell. -> (ok, message). Shared by the
    deterministic sweep and the loop's rewrite_constants tool."""
    tcol = year_columns(spec, sheet).get(str(target_year))
    pcol = prior_column(spec, sheet, target_year)
    if not tcol or not pcol:
        return False, f"no target/prior column for sheet '{sheet}'"
    cell = wb[sheet][f"{tcol}{row}"]
    f = cell.value
    if not (isinstance(f, str) and f.startswith("=")):
        return False, (f"{sheet}!{tcol}{row} holds {f!r} — the law covers "
                       "formula cells embedding numeric literals")
    lits = [x for x in literals_of(f)
            if abs(float(x)) not in MODELING_CONSTANTS]
    if not lits:
        return False, (f"{sheet}!{tcol}{row} embeds no carried-actual "
                       "literals (structural scalers don't count)")
    # (the size floor went 2026-09-14: a carried 34 or −40+29 is last
    # year's figure as much as 16,602.97 — owner, CLP Aus!AI17 / Final!AI125)
    ev = Evaluator(wb)
    try:
        cur = ev.cell(sheet, f"{tcol}{row}")
        pv = ev.cell(sheet, f"{pcol}{row}")
    except Exception as e:
        return False, f"{sheet}!{tcol}{row} does not evaluate: {e}"
    if not (isinstance(cur, (int, float)) and isinstance(pv, (int, float))):
        return False, f"{sheet}!{tcol}{row}: cell or prior not numeric"
    if abs(cur - pv) > STALE_TOL:
        # THE VINTAGE EXTENSION (by-hand teaching #4, run-204: the WC
        # row, the one-offs =94, net interest =2254-235-15 — literals
        # tying the PRIOR-year print are last year's numbers even when
        # the cell does not evaluate to its prior). Qualify only when
        # EVERY large literal individually ties a prior-position print;
        # the page-coherence proof below still decides.
        for x in lits:
            if not candidates(ledger, x):
                return False, (f"{sheet}!{tcol}{row}: UNPROVEN — literal {x} is carried from "
                               "last year's formula and the documents print no such figure "
                               "— cell untouched, stays red")
    row_label = ""
    for lc in ("A", "B", "C", "D", "E"):
        lv = wb[sheet][f"{lc}{row}"].value
        if isinstance(lv, str) and lv.strip():
            row_label = lv.strip()
            break
    proof, why = prove_cell(ledger, lits, row_label=row_label, trust_names=trust_names)
    if proof is None and "kin to the row" in str(why):
        # the numbers tie, the names do not: the rewrite is kept as a suggestion for
        # the row's card — the brain judges whether those lines are this row's items
        p2, _w2 = prove_cell(ledger, lits, row_label=row_label, trust_names=True)
        if p2:
            f2 = f
            for lit, (val, _src) in p2.items():
                f2 = re.sub(r"(?<![A-Za-z0-9_.])" + re.escape(lit) + r"(?![\d.])", f"{val:g}", f2, count=1)
            ledger.__dict__.setdefault("rewrite_suggestions", {})[f"{sheet}!{row}"] = {
                "formula": f2, "was": f, "srcs": "; ".join(f"{lit}->{val:g} ({src})" for lit, (val, src) in p2.items())[:300]}
    if proof is None:
        return False, (f"{sheet}!{tcol}{row} UNPROVEN — {why} "
                       "— cell untouched, stays red")
    new_f = f
    for lit, (val, _src) in proof.items():
        new_f = re.sub(r"(?<![A-Za-z0-9_.])" + re.escape(lit) + r"(?![\d.])",
                       f"{val:g}", new_f, count=1)
    srcs = "; ".join(f"{lit}->{val:g} ({src})"
                     for lit, (val, src) in proof.items())
    # A NAME THE BRAIN HAS JUDGED IS NOT A COINCIDENCE (owner ruling 2026-09-17,
    # refining the morning's rule): `trust_names` reaches this function from ONE
    # place — the rewrite card's own answer (workqueue 'rewrite:1'), the brain
    # saying those printed lines ARE this row's items. That is a judgment of
    # meaning, so the rewrite lands ORANGE, derived and awaiting true-up, like
    # any back-out. Code's own rewrites (phase0, the sweep) never reach here on
    # unlike names: prove_cell's kin test refuses them first.
    ok = writer.write(
        sheet, f"{tcol}{row}", new_f, prior_coord=f"{pcol}{row}",
        flag="orange",
        note=(f"COMPOSITE REWRITE (constants law): was {f} = stale prior; "
              f"each literal tied to its disclosed comparative and "
              f"replaced by the same line's current figure: {srcs}"
              + ("; the brain judged these printed lines to be this row's items, though they "
                 "are named unlike it" if trust_names else ""))[:400])
    if not ok:
        return False, (f"{sheet}!{tcol}{row}: rewrite {new_f} REFUSED by "
                       "the write guard (band vs prior) — the tie is "
                       "suspect, cell untouched")
    try:
        after = Evaluator(wb).cell(sheet, f"{tcol}{row}")
    except Exception:
        after = None
    served = getattr(writer, "served", None)
    if isinstance(served, dict) and isinstance(after, (int, float)):
        # the rewrite's proof is a serve record (audit 2026-09-15: receivables 14,035 and
        # deferred creditors 8,363 were rewritten correctly, then treated as unproven by
        # the cards and overwritten) — conf 4, orange: proven, not a doubt
        served[(sheet, row)] = {"value": float(after), "status": "OK", "conf": 4, "flag": "orange",
                                "doc": None, "page": None, "homed": False,
                                "line": "COMPOSITE REWRITE (constants law): " + srcs[:80],
                                "note": f"composite rewrite: each literal tied to its comparative ({srcs[:120]})"}
    return True, (f"{sheet}!{tcol}{row}: {f} -> {new_f}"
                  + (f" = {after:,.2f}" if isinstance(after, (int, float))
                     else ""))


def sweep(wb, spec, target_year, ledger, writer, log, check_rows=None, served=None):
    """The deterministic pass: every target-column formula cell with the
    stale fingerprint gets one lawful rewrite attempt. Unproven cells
    get their evidence note. -> (n_rewritten, n_unproven)."""
    checks = {(c.get("sheet"), int(c.get("row")))
              for c in (check_rows or [])}
    n_ok = n_red = 0
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        if not tcol:
            continue
        ws = wb[sheet]
        for r in range(AXIS_BAND + 1, ws.max_row + 1):
            if (sheet, r) in checks:
                continue
            f = ws[f"{tcol}{r}"].value
            if not (isinstance(f, str) and f.startswith("=")):
                continue
            lits = [x for x in literals_of(f)
                    if abs(float(x)) not in MODELING_CONSTANTS]
            if not lits or not any(abs(float(x)) >= VINTAGE_FLOOR
                                   for x in lits):
                continue
            if served is not None and (sheet, r) in served:
                continue          # a formula the vertical tie already rewrote (schedules.py) is proven; its literals are this year's
            ok, msg = rewrite_cell(wb, spec, target_year, ledger, writer,
                                   sheet, r)
            if not ok and ("UNPROVEN" in msg or "REFUSED" in msg):
                # same-shape refresh failed: the composition may have
                # CHANGED SHAPE (new ingredients) — the recomposition
                # law gets one attempt before the cell stays red
                ok2, msg2 = recompose_cell(wb, spec, target_year, ledger,
                                           writer, sheet, r)
                if ok2:
                    ok, msg = ok2, msg2
            if ok:
                n_ok += 1
                log(f"[run]   constants law: {msg}")
            elif "UNPROVEN" in msg or "REFUSED" in msg:
                n_red += 1
                log(f"[run]   constants law: {msg[:180]}")
                # the log had said "stays red" while the cell stayed plain
                # (CLP 2026-09-10, Final!AI30 '=94-AI29-AI28'): a formula
                # still carrying last year's literal is unproven — painted
                try:
                    from openpyxl.comments import Comment as _Cm
                    from .checks import year_columns as _yc
                    _tc = _yc(spec, sheet).get(str(target_year))
                    if _tc:
                        _cell = wb[sheet][f"{_tc}{r}"]
                        writer.flag_ref(f"{sheet}!{_tc}{r}", "red",
                            f"Formula still carries last period's constants ({', '.join(lits)}). "
                                            "Check they still hold.")
                except Exception:
                    pass
    return n_ok, n_red


_CHAIN = re.compile(r"^=\s*([+-]?\s*\d+(?:\.\d+)?)((?:\s*[+-]\s*"
                    r"\d+(?:\.\d+)?)*)\s*$")


def signed_literals(formula):
    """A pure ±-literal chain ('=9817-7131+2269') -> [(sign, lit)] or
    None. Recomposition v1 covers exactly this shape — the analyst's
    hand-summed statement section."""
    if not _CHAIN.match(str(formula).replace(" ", "")):
        return None
    out = []
    for m in re.finditer(r"([+-]?)(\d+(?:\.\d+)?)",
                         str(formula)[1:].replace(" ", "")):
        out.append((-1.0 if m.group(1) == "-" else 1.0, m.group(2)))
    return out or None


def _narrow_pair(ns):
    """(current, comparative) from a narrow printed line, or None.
    Two numbers = the pair; three with a small leading note ref = drop
    the note. Anything else is not a recompose source."""
    ms = [n for n in ns if abs(n) >= 0.5]
    def _note_like(a, rest):
        return (0 < a <= 120 and float(a).is_integer() and rest
                and min(abs(x) for x in rest) > 2 * abs(a))
    if len(ms) == 3 and _note_like(ms[0], ms[1:]):
        ms = ms[1:]
    elif len(ms) == 2 and _note_like(ms[0], ms[1:]):
        ms = ms[1:]
    if len(ms) == 2:
        return ms[0], ms[1]
    if len(ms) == 1:
        return (ms[0],)          # single current figure, no comparative
    return None


def recompose_cell(wb, spec, target_year, ledger, writer, sheet, row):
    """THE RECOMPOSITION LAW (owner ruling 2026-09-02: "when there is a
    new ingredient this year that adds into the subtotal, we add it —
    this is core analyst skill").

    The old recipe names its own source: its signed literals match the
    COMPARATIVE column of one contiguous run of lines in ONE printed
    table. Within that span, the analyst's thinking is mechanical:
      - a line whose comparative is in the old recipe -> refreshed to
        its current figure;
      - a line with NO comparative but a current figure -> genuinely
        NEW -> joins the sum (the owner's rule);
      - a line with a material comparative the analyst EXCLUDED last
        year -> stays excluded (their intent), noted for review.
    Every step is proven from print; ambiguity refuses. Generic: no
    labels, no sheet names, no statement knowledge."""
    tcol = year_columns(spec, sheet).get(str(target_year))
    pcol = prior_column(spec, sheet, target_year)
    if not tcol or not pcol:
        return False, "no target/prior column"
    cell = wb[sheet][f"{tcol}{row}"]
    f = cell.value
    sl = signed_literals(f) if isinstance(f, str) else None
    if not sl:
        return False, (f"{sheet}!{tcol}{row}: not a pure ±-literal chain "
                       "— recomposition v1 covers hand-summed sections")
    lits = [(s, x) for s, x in sl
            if abs(float(x)) not in MODELING_CONSTANTS]
    if len(lits) < 2:
        return False, f"{sheet}!{tcol}{row}: fewer than 2 carried literals"
    bad_docs = ledger.noncurrent_docs()
    pv_tabs = getattr(ledger, "_pv_tables", set())
    from collections import defaultdict
    tables = defaultdict(list)
    for it in ledger.items:
        # NOT joinable(): a NEW ingredient is exactly a ONE-number line
        # ('Issue of perpetual capital securities  3,872'), which the
        # join's two-number rule rightly ignores — recomposition needs
        # structure (table, row order), not a pair
        if not _sourceable(it) or it.disputed \
                or it.table_id is None or it.row_ord is None \
                or getattr(it, "table_kind", None) == "matrix" \
                or (it.doc, it.page, it.table_id) in pv_tabs:
            continue
        tables[(it.doc, it.page, it.table_id)].append(it)
    old_val = sum(s * float(x) for s, x in lits)
    held = set()
    for sh2 in (spec.get("year_axis") or {}):
        tc2 = year_columns(spec, sh2).get(str(target_year))
        if not tc2 or sh2 not in wb.sheetnames:
            continue
        ws2 = wb[sh2]
        for r2 in range(1, min(ws2.max_row, 300) + 1):
            v2 = ws2[f"{tc2}{r2}"].value
            if isinstance(v2, (int, float)) and abs(v2) >= 2.0:
                held.add(round(abs(v2), 1))
    results = {}
    for key, items in tables.items():
        items.sort(key=lambda i: i.row_ord or 0)
        pairs = []
        for it in items:
            p = _narrow_pair(it.nums or [])
            pairs.append((it, p))
        big = [(s2, x) for s2, x in lits if abs(float(x)) >= 10.0]
        small = [(s2, x) for s2, x in lits if abs(float(x)) < 10.0]
        if len(big) < 2:
            continue
        # phase 1: the big literals locate the span; coincidences are
        # resolved by LOCALITY (the line nearest the others wins)
        cand = {}
        for s2, x in big:
            v = abs(float(x))
            tol = row_tol(v, base=0.6 if v >= 100 else 0.01)
            hits = [j for j, (it, p) in enumerate(pairs)
                    if p is not None and len(p) == 2
                    and abs(abs(p[1]) - v) <= tol]
            if not hits:
                cand = None
                break
            cand[(s2, x)] = hits
        if not cand:
            continue
        anchor = [h[0] for h in cand.values() if len(h) == 1]
        if not anchor:
            continue
        mid = sorted(anchor)[len(anchor) // 2]
        matched, used = {}, set()
        ok_m = True
        for k, hits in sorted(cand.items(),
                              key=lambda kv: len(kv[1])):
            free = [h for h in hits if h not in used]
            if not free:
                ok_m = False
                break
            best = sorted(free, key=lambda h: abs(h - mid))
            if len(best) > 1 and abs(best[0] - mid) == abs(best[1] - mid):
                ok_m = False
                break
            used.add(best[0])
            matched[k] = best[0]
        if not ok_m:
            continue
        # identity-span filter: lines printing the same figure twice
        # (a note repeating one year) prove no vintage — discard when
        # they dominate
        n_ident = sum(1 for j in matched.values()
                      if pairs[j][1] is not None and len(pairs[j][1]) == 2
                      and abs(pairs[j][1][0] - pairs[j][1][1]) <= 0.6)
        if n_ident * 2 >= len(matched):
            continue
        js = sorted(matched.values())
        # SECTION EXTENSION (the r106 lesson: this year's NEW items —
        # a deconsolidation gain, FV gains — print just OUTSIDE the old
        # recipe's hull, inside the same section). Extend over member
        # lines (singles, or pairs whose comparative is immaterial);
        # STOP at the first line with a material unmatched comparative
        # in each direction — that is the neighbouring section's
        # territory (D&A above, exchange below, both other model rows).
        sum_lits0 = sum(abs(float(x)) for _s3, x in lits)
        tiny = max(2.0, 0.01 * sum_lits0)   # beneath-materiality bar:
                                            # an item immaterial LAST
                                            # year was left out of the
                                            # recipe; grown material
                                            # now, it joins
        lo, hi = js[0], js[-1]
        while lo - 1 >= 0:
            p2 = pairs[lo - 1][1]
            if p2 is not None and (len(p2) == 1 or abs(p2[1]) <= tiny):
                lo -= 1
                continue
            break
        while hi + 1 < len(pairs):
            p2 = pairs[hi + 1][1]
            if p2 is not None and (len(p2) == 1 or abs(p2[1]) <= tiny):
                hi += 1
                continue
            break
        span = range(lo, hi + 1)
        # phase 2: small literals must resolve INSIDE the span — a
        # comparative pair, or a single unchanged figure
        small_at = {}
        for s2, x in small:
            v = abs(float(x))
            hit = None
            for j in span:
                if j in used:
                    continue
                it, p = pairs[j]
                if p is not None and len(p) == 2 \
                        and abs(abs(p[1]) - v) <= 0.6:
                    hit = (j, p[0])
                    break
                if p is not None and len(p) == 1 \
                        and abs(abs(p[0]) - v) <= 0.6:
                    hit = (j, p[0])
                    break
            if hit is None:
                ok_m = False
                break
            used.add(hit[0])
            matched[(s2, x)] = hit[0]
            small_at[hit[0]] = (s2, abs(hit[1]))
        if not ok_m:
            continue
        mults = []
        for (s, x), j in matched.items():
            _it, p = pairs[j]
            if len(p) == 2 and p[1] != 0:
                mults.append(s * (1.0 if p[1] > 0 else -1.0))
        mult = 1.0 if sum(mults) >= 0 else -1.0
        terms, new_items, excluded = [], [], []
        sum_lits = sum(abs(float(x)) for _s, x in lits)
        ok_span = True
        for j in span:
            it, p = pairs[j]
            if j in small_at:
                s2m, vm = small_at[j]
                terms.append((s2m, vm, str(it.label)[:36]))
                continue
            if j in used:
                # THE SIGN COMES FROM THE PRINTED CURRENT (r136 lesson:
                # short-term borrowings flipped from an increase +2,269
                # to a decrease -1,768 — the comparative's sign is last
                # year's direction, never this year's)
                terms.append((mult * (1.0 if p[0] > 0 else -1.0),
                              abs(p[0]), str(it.label)[:36]))
                continue
            if p is not None and len(p) == 1:
                if abs(p[0]) >= 2.0 and round(abs(p[0]), 1) not in held:
                    # single current figure, no comparative: NEW item
                    # (one-home: a value already typed elsewhere in the
                    # model belongs to another row)
                    new_items.append((mult * (1.0 if p[0] > 0 else -1.0),
                                      abs(p[0]), str(it.label)[:36]))
                continue
            if p is None:
                continue
            cur2, comp2 = p
            if abs(abs(comp2) - sum_lits) <= row_tol(sum_lits, base=1.0):
                continue          # the section's own subtotal line
            if abs(comp2) > tiny:
                excluded.append((comp2, str(it.label)[:36]))
                continue
            if abs(cur2) >= 2.0 and round(abs(cur2), 1) not in held:
                new_items.append((mult * (1.0 if cur2 > 0 else -1.0),
                                  abs(cur2), str(it.label)[:36]))
        if not ok_span or len(excluded) > len(matched):
            continue
        parts = list(terms) + list(new_items)
        total = sum(sgn * v for sgn, v, _l in parts)
        fstr = "=" + "".join(
            (("+" if sgn > 0 else "-") if i or sgn < 0 else "")
            + f"{v:g}" for i, (sgn, v, _l) in enumerate(parts))
        results.setdefault(round(total, 1), []).append(
            (key, fstr, parts, new_items, excluded))
    if not results:
        return False, (f"{sheet}!{tcol}{row}: no printed table carries "
                       "the old recipe's comparatives in one span")
    if len(results) > 1:
        return False, (f"{sheet}!{tcol}{row}: tables disagree on the "
                       "recomposition ("
                       + "; ".join(f"{k:,.1f}" for k in results) + ")")
    (key, fstr, parts, new_items, excluded) = list(results.values())[0][0]
    doc, page, _t = key
    note = (f"RECOMPOSED (new-ingredient law): was {f}; the old recipe's "
            f"comparatives map one span of {doc} p{page}. "
            + (f"NEW items joined: "
               + ", ".join(f"{lab} {sgn * v:+,.0f}"
                           for sgn, v, lab in new_items) + ". "
               if new_items else "")
            + (f"Analyst-EXCLUDED last year, kept out: "
               + ", ".join(f"{lab} ({c:,.0f})"
                           for c, lab in excluded) + " — review. "
               if excluded else ""))
    ok = writer.write(sheet, f"{tcol}{row}", fstr,
                      prior_coord=f"{pcol}{row}", flag="orange",
                      note=note[:480])
    if not ok:
        return False, f"{sheet}!{tcol}{row}: recomposition {fstr} REFUSED by the write guard"
    return True, f"{sheet}!{tcol}{row}: {f} -> {fstr}"
