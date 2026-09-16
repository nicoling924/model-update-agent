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


# REMOVED WITH THE SWEEP (owner 2026-09-17): rewrite_cell and recompose_cell —
# code rewriting a formula's constants, and code recomposing a hand-summed
# chain, from printed figures that happened to match. Both DECIDED a
# composition. prove_cell above still FINDS what each literal could be; the
# mapping context shows that, and the brain states the composition.
