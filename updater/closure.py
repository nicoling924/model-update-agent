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

from .ledger import JOIN_FACES, Item

# the closure grammar is BILINGUAL (CLP prep, 2026-08-19: an English HK
# annual report closed 0 of 66 face pages under the CJK-only vocabulary)
# BILINGUAL closure grammar (CLP campaign). The roles differ by
# language: a CJK CF prints a 小计 (subtotal) AND a 净额 (net, a barrier
# combining two subtotals); an English CF's "Net cash inflow from
# operating activities" IS the section equation itself. Subtotal
# matching runs FIRST in _sections, so a row matching both is a subtotal.
SUBTOTAL_RE = re.compile(r"小计|合计|总计|^\s*total\s|^\s*subtotal|"
                         r"net cash (in|out)?flow|"
                         r"net cash (generated|used|from)|"
                         r"^\s*(operating|gross) profit|"
                         r"profit before|profit for the",
                         re.IGNORECASE)
SKIP_RE = re.compile(r"^\s*(其中|加[:：]|减[:：]|of which|including|"
                     r"thereof|less[:：]|add[:：])", re.IGNORECASE)
# a section BOUNDARY that is not itself a subtotal equation: the CJK CF
# activity-net rows, the numbered activity headers, and English bare
# activity headers ("Operating activities")
BARRIER_RE = re.compile(r"产生的现金流量净额|^\s*[一二三四五六七八九十]、|"
                        r"^\s*(operating|investing|financing) "
                        r"activities\s*$|"
                        r"net (increase|decrease) in cash", re.IGNORECASE)
MAX_SINGLES = 6
TOL = 1.0                     # statements add to the cent; sections are short


class _Row:
    """A note-stripped view of a ledger item (the CLP lesson: HK/IFRS
    tables print [note, current, prior] — the note column must be shed
    before the section equation can see the two value columns)."""
    __slots__ = ("label", "nums", "src", "row_ord")

    def __init__(self, it, strip_note):
        self.label = it.label
        self.row_ord = getattr(it, "row_ord", 0)
        ns = list(it.nums)
        if strip_note and len(ns) >= 2 and float(ns[0]).is_integer() \
                and 0 < ns[0] <= 99:
            ns = ns[1:]
        self.nums = ns
        self.src = it


def _detect_note_column(rows):
    """A table HAS a note column when a meaningful share of its
    multi-number rows lead with a small integer (1-99)."""
    multi = [r for r in rows if len(r.nums) >= 2]
    if len(multi) < 3:
        return False
    lead = sum(1 for r in multi
               if float(r.nums[0]).is_integer() and 0 < r.nums[0] <= 99)
    return lead >= max(2, len(multi) * 0.3)


def normalized_rows(rows):
    """Note-stripped views when the table carries a note column;
    the raw rows otherwise. All consumers of _sections share this."""
    strip = _detect_note_column([_Row(it, False) for it in rows])
    return [_Row(it, strip) for it in rows]


def _sections(rows):
    """(subtotal_row, [member rows]) per subtotal, scanning backwards to
    the previous subtotal / table start. None-section on any row shape
    the equation cannot hold (3+ numbers = not a two-column line).
    Rows may be ledger items or note-stripped _Row views."""
    out = []
    for si, s_row in enumerate(rows):
        if not (SUBTOTAL_RE.search(s_row.label or "")
                and len(s_row.nums) == 2):
            continue
        sec, ok, carry = [], True, None
        for r in reversed(rows[:si]):
            lab = r.label or ""
            if SUBTOTAL_RE.search(lab) and len(r.nums) >= 2:
                carry = r      # P&L anatomy: subtotals are CUMULATIVE —
                break          # the previous subtotal may carry in
            if BARRIER_RE.search(lab):
                break
            if SKIP_RE.match(lab) or not r.nums:
                continue
            if len(r.nums) > 2:
                ok = False
                break
            sec.append(r)
        if ok and sec:
            out.append((s_row, sec, carry))
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
            if k not in seen:
                seen.add(k)
                gaps.append((gc, gp))
    # PER-COLUMN PROOF (the confined-run fails, 2026-08-19): a column's
    # equation is self-contained — when EXACTLY ONE subset of the
    # single-number lines closes the CURRENT column, every single's
    # placement is decided by that column alone, even while the other
    # column stays gapped (a vision-missed comparative must not block a
    # proof the current year's own arithmetic completes). Symmetric for
    # the prior column.
    for col, base, target in (("cur", base_c, sc), ("pri", base_p, sp)):
        closing = [mask for mask in range(1 << len(ones))
                   if abs(base + sum(o.nums[0] for j, o in enumerate(ones)
                                     if mask >> j & 1) - target) <= TOL]
        if len(closing) == 1:
            mask = closing[0]
            # membership in this column decides both columns: a single
            # outside the closing subset belongs to the other column.
            # "closed_col": placements are proven; the section's two-num
            # rows are NOT verified off this (the other column is still
            # open — only a full closure vouches for the whole section)
            return ("closed_col", mask if col == "cur"
                    else (~mask) & ((1 << len(ones)) - 1)), ones
    # the MINIMAL gaps are the informative placements (run-25 bench: the
    # true placement — one single in the prior column, its own prior
    # missing — ranked past a first-two cap)
    gaps.sort(key=lambda g: abs(g[0]) + abs(g[1]))
    return (("gap", gaps[:2]) if gaps and len(ones) <= 4 else None), ones


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
                not in JOIN_FACES):
            continue
        groups.setdefault((it.doc, it.page, it.table_id), []).append(it)
    n_zero = n_gap = n_ver = 0
    new_items = []
    emitted = {(it.doc, it.page, it.label, tuple(it.nums))
               for it in ledger.items
               if getattr(it, "channel", "") in ("closure", "closure-gap")}
    for (doc, page, _tid), rows in sorted(groups.items()):
        rows.sort(key=lambda x: x.row_ord)
        rows_v = normalized_rows(rows)
        for s_row, sec, carry in _sections(rows_v):
            solved, ones = _solve(s_row, sec)
            if carry is not None and (
                    solved is None or solved[0] == "gap"):
                # cumulative-subtotal anatomy (the P&L): retry with the
                # previous subtotal carried into the section
                solved2, ones2 = _solve(s_row, sec + [carry])
                if solved2 is not None and solved2[0] in ("closed",
                                                          "closed_col"):
                    solved, ones = solved2, ones2
            if solved is None:
                continue
            kind, payload = solved
            if kind in ("closed", "closed_col"):
                if kind == "closed":
                    for r in sec + [s_row]:
                        tgt = getattr(r, "src", r)
                        if len(r.nums) == 2 and not getattr(tgt, "verified",
                                                           False):
                            tgt.verified = True
                            n_ver += 1
                for j, o in enumerate(ones):
                    v = o.nums[0]
                    cur_col = bool(payload >> j & 1)
                    nums = [v, 0.0] if cur_col else [0.0, v]
                    if (doc, page, o.label, tuple(nums)) in emitted:
                        continue
                    emitted.add((doc, page, o.label, tuple(nums)))
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
                    gkey = (doc, page, f"缺行 above {s_row.label[:24]}",
                            (gc, gp))
                    if gkey in emitted:
                        continue
                    emitted.add(gkey)
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
