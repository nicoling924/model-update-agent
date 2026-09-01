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
MODELING_CONSTANTS = {2.0, 3.0, 4.0, 10.0, 12.0, 24.0, 52.0, 100.0,
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


def candidates(ledger, lit):
    """One literal -> {current_value: set of (doc, page)}. A candidate
    is a face line where the literal sits in the COMPARATIVE position
    (nums[i+1]) and the adjacent current figure keeps the literal's
    order of magnitude — a real YoY pair does, a coincidence doesn't.
    The in-world scale is tried first; other scales only if it finds
    nothing (run-198 offline proof: the all-scales union manufactured
    ties)."""
    v = abs(float(lit))
    prior_docs = ledger.noncurrent_docs()
    tol = row_tol(v, base=0.6 if v >= 100 else 0.01)

    def scan(scales):
        found = {}
        pv_tabs = getattr(ledger, "_pv_tables", set())
        for it in ledger.items:
            if (it.doc, it.page) not in ledger.faces \
                    or it.doc in prior_docs or not it.joinable() \
                    or (it.doc, it.page, it.table_id) in pv_tabs:
                continue
            for s in scales:
                ns = [to_model_units(n, s) for n in it.nums]
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


def prove_cell(ledger, lits, row_label=""):
    """The composition proof (the by-hand method, mechanized): the
    disclosure prints a statement as a PAGE, so a composition's members
    live together — every literal must resolve on a COMMON page, every
    qualifying page must yield the SAME combination (corroboration
    resolves disagreements by page majority), and at least one tying
    line must be KIN to the row's own label (prose-junk guard).
    -> ({lit: (value, src)}, None) or (None, why)."""
    per_full, per, per_pair, ident = {}, {}, {}, {}
    for lit in lits:
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
            if (it.doc, it.page) not in ledger.faces \
                    or it.doc in prior_docs or not it.joinable() \
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
    ranked = sorted(combos.items(), key=lambda kv: -len(kv[1]))
    if len(ranked) > 1:
        # CORROBORATION RESOLVES (run-206: the true finance-cost pair
        # prints on the P&L face AND the CF note; the false one is a
        # single oldest-first series read backwards)
        if not (len(ranked[0][1]) >= 2
                and len(ranked[0][1]) > len(ranked[1][1])):
            return None, ("pages disagree on the combination: "
                          + "; ".join("+".join(f"{v:,.0f}" for v in k)
                                      for k in list(combos)[:3]))
    vals, pages = ranked[0]
    if not _kin_ok(per_full, lits, vals, row_label):
        return None, ("no tying line is kin to the row's own label — "
                      "probably a dense page's prose (run-208 lesson); "
                      "cell untouched")
    src = ", ".join(f"{d} p{p}" for d, p, _t in sorted(pages)[:3])
    return {lit: (v, src) for lit, v in zip(lits, vals)}, None


def rewrite_cell(wb, spec, target_year, ledger, writer, sheet, row):
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
    if not any(abs(float(x)) >= VINTAGE_FLOOR for x in lits):
        return False, (f"{sheet}!{tcol}{row}: all literals below "
                       f"{VINTAGE_FLOOR:g} — modeling constants, not "
                       "carried actuals")
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
        big = [x for x in lits if abs(float(x)) >= VINTAGE_FLOOR]
        if not big:
            return False, (f"{sheet}!{tcol}{row} evaluates {cur:,.2f} vs "
                           f"prior {pv:,.2f} — no stale fingerprint and no "
                           "vintage literals")
        for x in big:
            if not candidates(ledger, x):
                return False, (f"{sheet}!{tcol}{row}: literal {x} ties no "
                               "prior-position print — not a carried "
                               "actual; cell untouched")
        lits = big + [x for x in lits if abs(float(x)) < VINTAGE_FLOOR
                      and candidates(ledger, x)]
    row_label = ""
    for lc in ("A", "B", "C", "D", "E"):
        lv = wb[sheet][f"{lc}{row}"].value
        if isinstance(lv, str) and lv.strip():
            row_label = lv.strip()
            break
    proof, why = prove_cell(ledger, lits, row_label=row_label)
    if proof is None:
        return False, (f"{sheet}!{tcol}{row} UNPROVEN — {why} "
                       "— cell untouched, stays red")
    new_f = f
    for lit, (val, _src) in proof.items():
        new_f = re.sub(r"(?<![A-Za-z0-9_.])" + re.escape(lit) + r"(?![\d.])",
                       f"{val:g}", new_f, count=1)
    srcs = "; ".join(f"{lit}->{val:g} ({src})"
                     for lit, (val, src) in proof.items())
    ok = writer.write(
        sheet, f"{tcol}{row}", new_f, prior_coord=f"{pcol}{row}",
        flag="orange",
        note=(f"COMPOSITE REWRITE (constants law): was {f} = stale prior; "
              f"each literal tied to its disclosed comparative and "
              f"replaced by the same line's current figure: {srcs}"[:400]))
    if not ok:
        return False, (f"{sheet}!{tcol}{row}: rewrite {new_f} REFUSED by "
                       "the write guard (band vs prior) — the tie is "
                       "suspect, cell untouched")
    try:
        after = Evaluator(wb).cell(sheet, f"{tcol}{row}")
    except Exception:
        after = None
    return True, (f"{sheet}!{tcol}{row}: {f} -> {new_f}"
                  + (f" = {after:,.2f}" if isinstance(after, (int, float))
                     else ""))


def sweep(wb, spec, target_year, ledger, writer, log, check_rows=None):
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
            ok, msg = rewrite_cell(wb, spec, target_year, ledger, writer,
                                   sheet, r)
            if ok:
                n_ok += 1
                log(f"[run]   constants law: {msg}")
            elif "UNPROVEN" in msg or "REFUSED" in msg:
                n_red += 1
                log(f"[run]   constants law: {msg[:180]}")
    return n_ok, n_red
