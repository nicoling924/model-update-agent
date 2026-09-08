"""ROLL-FORWARD SCHEDULES — the vertical prior tie (owner 2026-09-10).

A movement table prints ONE year: rows = opening / increases / decreases /
closing, columns = classes, last column = total. It has no prior-year
column, so the horizontal prior tie can never fire on it — but its opening
row IS last year's closing. The model's schedule block (a Beginning cell
that links to last year's Ending, movement rows, an Ending that sums them)
ties that opening down the page instead of across it.

The agent works out what a table is from two things it already has: the
table's own arithmetic (which rows add to which) and which model cells its
numbers tie. Nothing here keys on a page, a rotation or a name alone.

Roles are settled the way definitions are — by the model's own prior-year
values against the prior-year report when it is on hand (DFE 2024: 购置
211.93 was Addition; the rest of the increases were Transfer; the whole
decrease group was Disposal) — else by role words, else the residual.

Significance (owner 2026-09-10): an opening within 1% of the model's prior
closing is the same balance — keep the model's figure, serve the movements,
record the gap in the report. Beyond 1%: nothing served, the Beginning cell
red with the difference named. The 1% is measured on AMOUNTS only (|prior|
>= 1, not percent-formatted); a ratio never enters this test.
"""
import re
from collections import defaultdict

from .checks import prior_column, year_columns
from .evaluator import Evaluator
from .numerics import kinship, norm_label, row_tol

SIGNIFICANCE = 0.01          # owner 2026-09-10
_OPEN = re.compile(r"上年年末|年初|期初|opening|beginning|at 1 jan|1 january", re.I)
_CLOSE = re.compile(r"期末|年末|closing|ending|at 31 dec|31 december|carrying amount at end", re.I)
_SCALES = (1.0, 1e3, 1e4, 1e6, 1e8)


def _ref_rows(formula, col):
    """Rows referenced in `col` by a formula (ranges expanded), same sheet."""
    out = set()
    f = str(formula).replace("$", "")
    for m in re.finditer(rf"(?<![A-Z']){col}(\d+):{col}(\d+)", f):
        a, b = int(m.group(1)), int(m.group(2))
        out.update(range(min(a, b), max(a, b) + 1))
    f2 = re.sub(rf"{col}\d+:{col}\d+", " ", f)
    for m in re.finditer(rf"(?<![A-Z'!]){col}(\d+)(?!\d)", f2):
        out.add(int(m.group(1)))
    return out


def find_blocks(wb, spec, target_year):
    """The model's schedule blocks: Beginning links to last year's Ending;
    Ending sums the block; the rows between with typed numbers are the
    movements. -> [{sheet, beg, end, rows:[(r, prior)], prior_end, tcol, pcol}]"""
    ev = Evaluator(wb)
    blocks = []
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        pcol = prior_column(spec, sheet, target_year)
        if not tcol or not pcol:
            continue
        ws = wb[sheet]
        for r in range(1, ws.max_row + 1):
            v = ws[f"{tcol}{r}"].value
            if not (isinstance(v, str) and v.startswith("=")):
                continue
            m = re.match(rf"^=\+?\$?{pcol}\$?(\d+)$", v.replace(" ", ""))
            if not m:
                continue
            e = int(m.group(1))
            if not (r < e <= r + 14):
                continue
            # the Beginning cell's own link names the block's Ending row; the
            # Ending may sum the block or link to the balance sheet (DFE's
            # intangibles end at =Model!U61) — either way the block is r..e
            rows = []
            for rr in range(r + 1, e):
                tv = ws[f"{tcol}{rr}"].value
                typed = isinstance(tv, (int, float)) or (
                    isinstance(tv, str) and tv.startswith("=") and not re.search(r"[A-Z]{1,3}\d+", tv.replace("$", "")))
                if not typed:
                    continue
                try:
                    pv = ev.cell(sheet, f"{pcol}{rr}")
                except Exception:
                    pv = None
                rows.append((rr, float(pv) if isinstance(pv, (int, float)) else 0.0))
            if not rows:
                continue
            try:
                pe = ev.cell(sheet, f"{pcol}{e}")
            except Exception:
                continue
            if not isinstance(pe, (int, float)) or abs(pe) < 1:
                continue
            if "%" in str(ws[f"{pcol}{e}"].number_format or ""):
                continue                      # a ratio never enters the 1% test
            blocks.append({"sheet": sheet, "beg": r, "end": e, "rows": rows,
                           "prior_end": float(pe), "tcol": tcol, "pcol": pcol,
                           "label": str(ws.cell(r, 1).value or ws.cell(max(1, r - 1), 1).value or "")})
    return blocks


def _sections(rows):
    """rows: [(label, total)] in print order. A section is opening + increase
    group − decrease group = closing on the totals, with the opening or the
    closing named as such. Components: the rows strictly inside a group
    that sum to it. -> [{open, inc, dec, close, inc_c, dec_c}] (indices)."""
    out = []
    n = len(rows)
    for i in range(n):
        lo, to = rows[i]
        for c in range(i + 2, min(n, i + 16)):
            lc, tc = rows[c]
            if not (_OPEN.search(lo) or _CLOSE.search(lc)):
                continue
            tol = max(row_tol(tc, base=1.0), abs(tc) * 2e-3)
            found = None
            for I in range(i + 1, c):
                tI = rows[I][1]
                if abs(to + tI - tc) <= tol:
                    found = {"open": i, "inc": I, "dec": None, "close": c}
                    break
                for D in range(I + 1, c):
                    if abs(to + tI - rows[D][1] - tc) <= tol:
                        found = {"open": i, "inc": I, "dec": D, "close": c}
                        break
                if found:
                    break
            if not found:
                continue
            def comps(a, b, total):
                inner = list(range(a + 1, b))
                s = sum(rows[k][1] for k in inner)
                return inner if inner and abs(s - total) <= tol else []
            found["inc_c"] = comps(found["inc"], found["dec"] if found["dec"] is not None else c, rows[found["inc"]][1])
            found["dec_c"] = comps(found["dec"], c, rows[found["dec"]][1]) if found["dec"] is not None else []
            out.append(found)
            break
    return out


def _doc_rows(ledger, doc):
    """A document's printed rows in order (page, row) — a movement table may
    turn a page (DFE: accumulated amortisation opens on p192, closes on p193)."""
    its = sorted([it for it in ledger.items if it.doc == doc and it.nums],
                 key=lambda it: (it.page, it.row_ord or 0))
    return [(str(it.label or ""), float([n for n in it.nums if isinstance(n, (int, float))][-1]), it.page) for it in its
            if any(isinstance(n, (int, float)) for n in it.nums)]


_SEC_CACHE = {}


def _all_sections(ledger, docs):
    """Every section in `docs`: [(doc, page, rows, sec)]; rows are the
    document's rows (label, total) and sec indexes into them."""
    out = []
    for doc in docs:
        key = (id(ledger), doc)
        if key not in _SEC_CACHE:
            drows = _doc_rows(ledger, doc)
            rows = [(l, t) for l, t, _pg in drows]
            _SEC_CACHE[key] = [(doc, drows[sec["open"]][2], rows, sec) for sec in _sections(rows)]
        out.extend(_SEC_CACHE[key])
    return out


def _find_section(ledger, docs, value, by="open"):
    """Sections in `docs` whose opening (or closing) total ties |value| at some
    scale; -> [(rel_diff, scale, doc, page, rows, section)] tightest first."""
    hits = []
    for doc, pg, rows, sec in _all_sections(ledger, docs):
        t = rows[sec[by]][1]
        for f in _SCALES:
            if t == 0:
                continue
            rel = abs(abs(t) / f - abs(value)) / abs(value)
            if rel <= SIGNIFICANCE:
                hits.append((rel, f, doc, pg, rows, sec))
    hits.sort(key=lambda h: h[0])
    return hits


def _roles_from_prior(block, ledger, prior_docs):
    """The model's own last-year values against the prior report's table:
    row -> ('component', label) | ('group', 'inc'|'dec') | None."""
    hits = _find_section(ledger, prior_docs, block["prior_end"], by="close")
    if not hits:
        return {}
    rel, f, doc, pg, rows, sec = hits[0]
    roles = {}
    for r, pv in block["rows"]:
        if pv == 0:
            continue
        v = abs(pv) * f
        for grp in ("inc", "dec"):
            gi = sec[grp]
            if gi is None:
                continue
            if abs(abs(rows[gi][1]) - v) <= max(row_tol(v, base=1.0), v * 2e-3):
                roles[r] = ("group", grp)      # the whole group: the roll closes on it
                break
            for k in sec[grp + "_c"]:
                if abs(abs(rows[k][1]) - v) <= max(row_tol(v, base=1.0), v * 2e-3):
                    roles[r] = ("component", norm_label(rows[k][0]), grp)
    return roles


_ROLE_WORDS = {
    "inc": re.compile(r"购置|购入|新增|addition|purchase|acquisition|转入|transfer in|计提|charge|depreciation|amortis", re.I),
    "dec": re.compile(r"处置|报废|disposal|转出|transfer out|减少|written off|impairment reversal", re.I),
}


def _sec_roles(rows, sec):
    """{role: total} for a section: opening, closing, inc, dec, and each
    component by its normalised label."""
    d = {"opening": rows[sec["open"]][1], "closing": rows[sec["close"]][1]}
    if sec["inc"] is not None:
        d["inc"] = rows[sec["inc"]][1]
        for k in sec["inc_c"]:
            d["inc:" + norm_label(rows[k][0])] = rows[k][1]
    if sec["dec"] is not None:
        d["dec"] = rows[sec["dec"]][1]
        for k in sec["dec_c"]:
            d["dec:" + norm_label(rows[k][0])] = rows[k][1]
    return d


def serve_literals(wb, spec, target_year, ledger, served, writer, log):
    """THE VERTICAL TIE FOR CARRIED LITERALS. The analyst's own formulas
    embed last year's note figures (DFE: Transfer '=1265.03-J95' carries the
    2024 increase total; Impairment '=-128.29+…' carries the 2024 closing
    provision; Amortisation '=1206.84-1332.46+157.00' carries the 2024
    opening and closing accumulated amortisation and the ROU charge). Each
    literal is placed by the same evidence a number has anywhere: it equals
    a movement table's opening in this year's report (so it is last year's
    closing, replaced by this year's closing), or it equals a role total in
    last year's table (so it takes the same role in this year's table whose
    opening is that table's closing). -> cells rewritten."""
    from .composites import literals_of, MODELING_CONSTANTS, VINTAGE_FLOOR
    from .writegate import _ties_full_precision as _full      # a literal ties at ITS OWN precision (157.00234067 is not 157.3)
    non = set(ledger.noncurrent_docs())   # evidence: last year's report is the SOURCE of last year's roles (which sub-line the model's 2024 value was), never of this year's number
    cur_docs = sorted({it.doc for it in ledger.items} - non)
    prior_docs = sorted(non)
    cur_secs = _all_sections(ledger, cur_docs)
    prior_secs = _all_sections(ledger, prior_docs) if prior_docs else []
    n = 0
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sheet).get(str(target_year))
        pcol = prior_column(spec, sheet, target_year)
        if not tcol:
            continue
        ws = wb[sheet]
        for r in range(1, ws.max_row + 1):
            if (sheet, r) in served:
                continue
            f = ws[f"{tcol}{r}"].value
            if not (isinstance(f, str) and f.startswith("=")):
                continue
            lits = [x for x in literals_of(f) if abs(float(x)) not in MODELING_CONSTANTS and abs(float(x)) >= VINTAGE_FLOOR]
            if not lits:
                continue
            new_f, notes = f, []
            for lit in lits:
                v = abs(float(lit))
                rep = None
                # (1) this year's tables: the literal is an opening -> take the closing
                best = None
                for doc, pg, rows, sec in cur_secs:
                    op = rows[sec["open"]][1]
                    for sc in _SCALES:
                        if op and _full(abs(op) / sc, v):
                            cand = (abs(abs(op) / sc - v), abs(rows[sec["close"]][1]) / sc, f"{doc} p{pg} closing")
                            if best is None or cand[0] < best[0]:
                                best = cand
                if best is not None:
                    rep = (best[1], best[2])
                # (2) last year's tables: the literal is a role total there -> the same role in this year's table
                if rep is None and prior_secs:
                    for doc, pg, rows, sec in prior_secs:
                        roles = _sec_roles(rows, sec)
                        for sc in _SCALES:
                            for role, tot in roles.items():
                                if not tot or not _full(abs(tot) / sc, v):
                                    continue
                                # this year's table is the one whose opening is last year's closing
                                p_close = roles["closing"]
                                # last year's closing and this year's opening are the SAME printed
                                # balance — they agree to the cent; the 1% band is for the model's
                                # figure, never for linking two prints (DFE: 293.57 had linked to
                                # a neighbouring table opening at 295.05)
                                cands = [(d2, pg2, rows2, sec2) for d2, pg2, rows2, sec2 in cur_secs
                                         if _full(abs(rows2[sec2["open"]][1]), abs(p_close))]
                                if len(cands) == 1:
                                    d2, pg2, rows2, sec2 = cands[0]
                                    r2 = _sec_roles(rows2, sec2)
                                    if role in r2 and r2[role]:
                                        rep = (abs(r2[role]) / sc, f"{d2} p{pg2} {role}")
                                if rep:
                                    break
                            if rep:
                                break
                        if rep:
                            break
                if rep is None:
                    continue
                new_f = re.sub(r"(?<![A-Za-z0-9_.])" + re.escape(lit) + r"(?![\d.])", f"{rep[0]:.6g}", new_f, count=1)
                notes.append(f"{lit}->{rep[0]:.6g} ({rep[1]})")
            if new_f != f and len(notes) == len(lits):
                ok = writer.write(sheet, f"{tcol}{r}", new_f, prior_coord=f"{pcol}{r}" if pcol else None, trusted=True)
                if ok:
                    n += 1
                    try:
                        _val = Evaluator(wb).cell(sheet, f"{tcol}{r}")
                    except Exception:
                        _val = None
                    _m = re.search(r"\((.+?\.pdf) p(\d+) ", notes[0])
                    # a proven serve record (value, document, page): the rollover
                    # card's dossier reverts only UNPROVEN inputs (DFE live
                    # 2026-09-08: '=1961.8-J95' was reverted to last year's literal)
                    served[(sheet, r)] = {"value": float(_val) if isinstance(_val, (int, float)) else None,
                                          "status": "OK", "conf": 4, "homed": True,
                                          "doc": _m.group(1) if _m else None, "page": int(_m.group(2)) if _m else None,
                                          "line": "; ".join(notes)[:60], "note": "schedule literals: " + "; ".join(notes)}
                    log(f"[run] schedule literals {sheet}!{tcol}{r}: {'; '.join(notes)}")
            elif new_f != f:
                log(f"[run] schedule literals {sheet}!{tcol}{r}: only {len(notes)}/{len(lits)} literals placed — left as is: {'; '.join(notes)}")
    return n


def serve_schedules(wb, spec, target_year, ledger, served, writer, log):
    """-> rows written. Runs after the walk, before the reader."""
    blocks = find_blocks(wb, spec, target_year)
    n_lit = 0
    if not blocks:
        return serve_literals(wb, spec, target_year, ledger, served, writer, log)
    _SEC_CACHE.clear()
    non = set(ledger.noncurrent_docs())   # evidence: last year's report is the SOURCE of last year's roles (which sub-line the model's 2024 value was), never of this year's number
    cur_docs = sorted({it.doc for it in ledger.items} - non)
    prior_docs = sorted(non)
    ev = Evaluator(wb)
    n = 0
    closers = []
    for b in blocks:
        sheet, tcol, pcol = b["sheet"], b["tcol"], b["pcol"]
        if all((sheet, r) in served for r, _ in b["rows"]):
            continue
        hits = _find_section(ledger, cur_docs, b["prior_end"], by="open")
        if not hits:
            continue
        rel, f, doc, pg, rows, sec = hits[0]
        opening = rows[sec["open"]][1] / f
        closing = rows[sec["close"]][1] / f
        sign = -1.0 if b["prior_end"] < 0 else 1.0        # the model's convention vs the print's magnitudes
        tol_open = row_tol(b["prior_end"])
        gap = abs(abs(opening) - abs(b["prior_end"]))
        where = f"{doc} p{pg}"
        if gap > 0.005:           # any real difference is worth a line in the report
            writer.log.setdefault("verdicts", []).append(
                f"{sheet}!{tcol}{b['beg']}: schedule '{b['label'][:30]}' opens at {abs(opening):,.2f} in the report "
                f"({where}) vs the model's prior closing {abs(b['prior_end']):,.2f} — {rel*100:.3f}%, within the 1% "
                "significance margin; the model's figure kept")
        roles = _roles_from_prior(b, ledger, prior_docs) if prior_docs else {}
        groups = {"inc": rows[sec["inc"]][1] / f if sec["inc"] is not None else 0.0,
                  "dec": rows[sec["dec"]][1] / f if sec["dec"] is not None else 0.0}
        comps = {"inc": [(norm_label(rows[k][0]), rows[k][1] / f) for k in sec["inc_c"]],
                 "dec": [(norm_label(rows[k][0]), rows[k][1] / f) for k in sec["dec_c"]]}
        # which group does each model row belong to: its own prior's direction
        assign = {}
        for r, pv in b["rows"]:
            grp = None
            if r in roles:
                grp = roles[r][2] if roles[r][0] == "component" else roles[r][1]
            elif pv != 0:
                grp = "inc" if pv * sign > 0 else "dec"
            else:
                lab = str(wb[sheet].cell(r, 1).value or "")
                grp = "inc" if _ROLE_WORDS["inc"].search(lab) and not _ROLE_WORDS["dec"].search(lab) else "dec"
            assign[r] = grp
        written_here = []
        for grp in ("inc", "dec"):
            members = [r for r, _ in b["rows"] if assign.get(r) == grp]
            if not members or (sec[grp] is None):
                continue
            taken, residual_row, values = [], None, {}
            for r in members:
                role = roles.get(r)
                lab = str(wb[sheet].cell(r, 1).value or "")
                if role and role[0] == "component":
                    hit = next(((cl, cv) for cl, cv in comps[grp] if cl == role[1]), None)
                    if hit is None:
                        hit = next(((cl, cv) for cl, cv in comps[grp] if kinship(cl, role[1])), None)
                    if hit is not None:
                        values[r] = (hit[1], f"'{hit[0][:20]}'", None)
                        taken.append(hit[0])
                        continue
                if role and role[0] == "group":
                    values[r] = (groups[grp], "the whole group", None)
                    continue
                if not role:
                    hit = next(((cl, cv) for cl, cv in comps[grp] if cl not in taken and kinship(cl, lab)), None)
                    if hit is not None and len(members) > 1:
                        values[r] = (hit[1], f"'{hit[0][:20]}'", None)
                        taken.append(hit[0])
                        continue
                if residual_row is None:
                    residual_row = r
                else:
                    values[r] = None
            if residual_row is not None:
                assigned = [(cl, cv) for cl, cv in comps[grp] if cl in taken]
                rest = groups[grp] - sum(cv for _, cv in assigned)
                if assigned:
                    formula = f"=({groups[grp]:.6g})" + "".join(f"-({cv:.6g})" for _, cv in assigned)
                    values[residual_row] = (rest, "the group less " + ", ".join(f"'{cl[:14]}'" for cl, _ in assigned), formula)
                else:
                    values[residual_row] = (groups[grp], "the whole group", None)
            for r in members:
                v = values.get(r)
                if not v:
                    continue
                amount, what, formula = v
                pv = dict(b["rows"])[r]
                srow = (1.0 if pv > 0 else -1.0 if pv < 0 else (sign if grp == "inc" else -sign))
                val = formula if formula else round(abs(amount), 4)
                if formula and srow < 0:
                    val = "=-(" + formula[1:] + ")"
                elif not formula:
                    val = val * srow
                ok = writer.write(sheet, f"{tcol}{r}", val, prior_coord=f"{pcol}{r}", trusted=True,
                                  note=(f"schedule: {what} of the {grp}rease movements, {where} "
                                        f"(opening {abs(opening):,.2f} ties the model's prior closing)"))
                if ok:
                    n += 1
                    written_here.append((r, val))
                    served[(sheet, r)] = {"value": (amount * srow if not formula else abs(amount) * srow), "status": "OK",
                                          "doc": doc, "page": pg, "conf": 4, "line": what[:60],
                                          "note": f"schedule: {what}, {where}"}
        if written_here:
            closers.append((sheet, tcol, b, written_here[-1][0], closing, gap, where))
            log(f"[run] schedule '{b['label'][:30]}' ({sheet} rows {b['beg']}-{b['end']}): {len(written_here)} movement rows served from {where} "
                f"(opening {abs(opening):,.2f} vs prior closing {abs(b['prior_end']):,.2f}, closing prints {abs(closing):,.2f})")
    n += serve_literals(wb, spec, target_year, ledger, served, writer, log)
    # the roll must close — judged once the literals are placed too
    for sheet, tcol, b, r_last, closing, gap, where in closers:
        try:
            got = Evaluator(wb).cell(sheet, f"{tcol}{b['end']}")
        except Exception:
            got = None
        if not isinstance(got, (int, float)):
            continue
        drift = abs(abs(got) - abs(closing)) - gap
        if drift > max(row_tol(closing), abs(closing) * 2e-3):
            cell = wb[sheet][f"{tcol}{r_last}"]
            from openpyxl.comments import Comment
            cell.fill = writer.fills["red"]
            cell.comment = Comment(f"Schedule does not close: the model's ending computes {abs(got):,.2f} "
                                   f"vs the printed closing {abs(closing):,.2f} ({where}). Please check the movements.",
                                   "Model Update Agent")
            writer.log["flags"].append(f"{sheet}!{tcol}{r_last}")
            log(f"[run] schedule '{b['label'][:30]}' does not close: {abs(got):,.2f} vs printed {abs(closing):,.2f}")
    return n
