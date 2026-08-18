"""Section closure — the statement's own arithmetic as a reading checksum.

Run-24 autopsy (owner's same-page law, second pass): the two remaining
stale classes on the CF face were not mapping failures but READING gaps
with a deterministic proof sitting in plain sight:

1. THE ABSENT LINE (the ±593.5 CFI/CFF twin). The FY25 filing prints
   "收到其他与筹资活动有关的现金 593,536,698" with ONE number. Which
   column? The section subtotal answers: the CURRENT column closes
   exactly WITHOUT it (5,236.2 + 5,569.6 = 10,805.8 to the yuan) and the
   PRIOR column closes exactly WITH it. The number is the comparative;
   the current-year value is a PROVEN ZERO. The model's stale 593.54
   inflated CFF and (via the cash residual) depressed CFI — the twin.

2. THE MISSING ROW (销售商品 73,358). Vision dropped the first row of
   the CF table; recovery mode cannot resurrect a row the transcription
   never produced. But the section subtotal DEFINES the gap: subtotal
   minus the rows present IS the missing row's value, both columns —
   derived-by-difference evidence the agent can reason from.

Both are one law: a printed subtotal is an equation over its section;
solve it. Emissions:
  - single-number rows in a CLOSED section -> a corrected two-column
    item ([v, 0] or [0, v]) with the placement PROVEN, channel
    "closure", verified (join-eligible; a proven zero may serve);
  - sections that do NOT close -> a gap item per placement (<=2),
    channel "closure-gap", verified (evidence for the agent; it only
    auto-serves if the gap itself ties a model prior at identity —
    which is the proof);
  - two-column rows of a closed section -> marked verified (the
    subtotal vouches for them — a second checksum).

Scope: statement FACES only (bs/is/cf). Note tables prove internal
consistency, not column semantics — an aging table closes over
[carrying, provision] columns, and admitting it would rebuild the
run-21 corruption class. Faces are the one place [current, prior] is
the guaranteed shape.
"""
import re

from .ledger import Item

SUBTOTAL_RE = re.compile(r"小计|合计|总计")
SKIP_RE = re.compile(r"^\s*(其中|加[:：]|减[:：])")
MAX_SINGLES = 6
TOL = 1.0                     # statements add to the cent; sections are short


def _sections(rows):
    """(subtotal_row, [member rows]) per subtotal, scanning backwards to
    the previous subtotal / table start. None-section on any row shape
    the equation cannot hold (3+ numbers = not a two-column line)."""
    out = []
    for si, s_row in enumerate(rows):
        if not (SUBTOTAL_RE.search(s_row.label or "")
                and len(s_row.nums) == 2):
            continue
        sec, ok = [], True
        for r in reversed(rows[:si]):
            if SUBTOTAL_RE.search(r.label or "") and len(r.nums) >= 2:
                break
            if SKIP_RE.match(r.label or "") or not r.nums:
                continue
            if len(r.nums) > 2:
                ok = False
                break
            sec.append(r)
        if ok and sec:
            out.append((s_row, sec))
    return out


def _solve(s_row, sec):
    """-> ('closed', mask) | ('gap', [(gc, gp), ...]) | None.
    mask bit j set = singles[j] belongs to the CURRENT column."""
    twos = [r for r in sec if len(r.nums) == 2]
    ones = [r for r in sec if len(r.nums) == 1]
    if len(ones) > MAX_SINGLES:
        return None, ones
    base_c = sum(r.nums[0] for r in twos)
    base_p = sum(r.nums[1] for r in twos)
    sc, sp = s_row.nums[0], s_row.nums[1]
    gaps, seen = [], set()
    for mask in range(1 << len(ones)):
        c = base_c + sum(o.nums[0] for j, o in enumerate(ones)
                         if mask >> j & 1)
        p = base_p + sum(o.nums[0] for j, o in enumerate(ones)
                         if not mask >> j & 1)
        if abs(c - sc) <= TOL and abs(p - sp) <= TOL:
            return ("closed", mask), ones
        gc, gp = sc - c, sp - p
        # a gap beyond the subtotal's own magnitude is structure (nested
        # totals), not a missing line — emit nothing for it
        if abs(gc) <= abs(sc) * 1.05 + TOL and abs(gp) <= abs(sp) * 1.05 + TOL:
            k = (round(gc, 2), round(gp, 2))
            if k not in seen and len(gaps) < 2:
                seen.add(k)
                gaps.append((gc, gp))
    return (("gap", gaps) if gaps and len(ones) <= 2 else None), ones


def closure_sweep(ledger, log):
    """Deterministic; runs after ingestion, before the join. Mutates the
    ledger only (verified marks + new closure items) — never the model."""
    prior_docs = ledger.prior_period_docs()
    groups = {}
    for it in ledger.items:
        if (it.doc in prior_docs or it.table_id is None
                or it.row_ord is None
                or getattr(it, "channel", "") in ("closure", "closure-gap")
                or ledger.faces.get((it.doc, it.page))
                not in ("bs", "is", "cf")):
            continue
        groups.setdefault((it.doc, it.page, it.table_id), []).append(it)
    n_zero = n_gap = n_ver = 0
    new_items = []
    for (doc, page, _tid), rows in sorted(groups.items()):
        rows.sort(key=lambda x: x.row_ord)
        for s_row, sec in _sections(rows):
            solved, ones = _solve(s_row, sec)
            if solved is None:
                continue
            kind, payload = solved
            if kind == "closed":
                for r in sec + [s_row]:
                    if len(r.nums) == 2 and not getattr(r, "verified", False):
                        r.verified = True
                        n_ver += 1
                for j, o in enumerate(ones):
                    v = o.nums[0]
                    cur_col = bool(payload >> j & 1)
                    nums = [v, 0.0] if cur_col else [0.0, v]
                    which = "CURRENT" if cur_col else "PRIOR (current-year "
                    which += "" if cur_col else "line ABSENT — proven zero)"
                    new_items.append(Item(
                        doc=doc, page=page, table_id=910, row_ord=o.row_ord,
                        label=o.label, nums=nums, channel="closure",
                        verified=True,
                        source_line=(f"{o.label}: single printed number "
                                     f"{v:,.2f} belongs to the {which} "
                                     f"column — section above "
                                     f"'{s_row.label[:24]}' closes exactly "
                                     f"with this placement")))
                    n_zero += 1
            else:
                for gc, gp in payload:
                    if abs(gc) <= TOL and abs(gp) <= TOL:
                        continue
                    new_items.append(Item(
                        doc=doc, page=page, table_id=911,
                        row_ord=s_row.row_ord, label=f"缺行 above "
                        f"{s_row.label[:24]}", nums=[gc, gp],
                        channel="closure-gap", verified=True,
                        source_line=(f"MISSING ROW(S) derived by "
                                     f"difference: section above "
                                     f"'{s_row.label[:24]}' does not close "
                                     f"— gap current {gc:,.2f} / prior "
                                     f"{gp:,.2f} (may aggregate several "
                                     f"missing lines; placement of "
                                     f"single-number rows may vary)")))
                    n_gap += 1
    ledger.items.extend(new_items)
    try:
        ledger._oracle_cache = None       # pool changed
    except Exception:
        pass
    if n_zero or n_gap or n_ver:
        log(f"[closure] {n_ver} rows verified by subtotal closure, "
            f"{n_zero} single-number placements proven, "
            f"{n_gap} missing-row gaps derived")
    return n_zero + n_gap
