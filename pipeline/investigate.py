"""THE INVESTIGATOR (owner 2026-09-10). The analyst's own way with a
suspicious line on the report page: "where does the swing come from?" —
press into the line, find the input that explains most of the move, press
into that, until a typed cell; then judge that cell.

  contribution  = put ONE input's pre-update content back and measure how
                  much of the swing disappears; the input that explains
                  most is the culprit at this level (the rollover dossier's
                  own probe, applied level by level)
  trail         = net profit -> associates -> Australia -> income tax
  the swing factor, three cases:
    (1) the agent's own red or orange — a mapping or a back-out: a better
        answer is sought, in order: a printed line that ties the prior and
        names the item; the residual of a printed total it belongs to (the
        parent's other parts proven); last year's share of its parent.
        Each lands orange with the trail, only if the headline gap shrinks
        and no check opens — else reverted.
    (2) a proven figure with an unusual move (100 every year, then 700):
        left alone, reported ("genuine per the print, unusual per history")
    (3) anything else: red, with the trail, for the analyst.
  unusual       = this year's move lies outside the range of the model's
                  own past year-on-year moves (owner: no margin for now)
Nothing here lands outside the cell laws; nothing may widen a headline gap.
"""
import re

from .checks import prior_column, year_columns
from .evaluator import Evaluator
from .numerics import kinship

_REF = re.compile(r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?\$?([A-Z]{1,3})\$?(\d+)(?::\$?([A-Z]{1,3})\$?(\d+))?")


def _refs(formula, sheet, wb):
    """Direct references of a formula (ranges expanded, same-column only)."""
    out = []
    for m in _REF.finditer(str(formula).replace("$", "")):
        sh = (m.group(1) or m.group(2) or sheet).strip()
        if sh not in wb.sheetnames:
            continue
        if m.group(5) and m.group(3) == m.group(5):
            a, b = int(m.group(4)), int(m.group(6))
            for r in range(min(a, b), max(a, b) + 1):
                out.append((sh, f"{m.group(3)}{r}"))
        elif not m.group(5):
            out.append((sh, f"{m.group(3)}{m.group(4)}"))
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _pre_content(pre_wb, sheet, coord):
    try:
        return pre_wb[sheet][coord].value
    except Exception:
        return None


def _val(wb, sheet, coord):
    try:
        v = Evaluator(wb).cell(sheet, coord)
    except Exception:
        return None
    return v if isinstance(v, (int, float)) else None


def contributors(wb, pre_wb, sheet, coord):
    """[(sheet, coord, share)] of the swing new-vs-old at `sheet!coord`,
    largest first. Share = the part of the swing that disappears when the
    input's pre-update content is put back."""
    from .execreport import _pre_val
    from openpyxl.utils import column_index_from_string as _ci
    f = wb[sheet][coord].value
    if not (isinstance(f, str) and f.startswith("=")):
        return []
    new = _val(wb, sheet, coord)
    m = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
    old = _pre_val(pre_wb, sheet, int(m.group(2)), _ci(m.group(1))) if m else None
    if new is None or not isinstance(old, (int, float)) or abs(new - old) < 1e-9:
        return []
    swing = new - old
    out = []
    for sh, c in _refs(f, sheet, wb):
        if (sh, c) == (sheet, coord):
            continue
        cur = wb[sh][c].value
        # the analyst's pre-update VALUE goes back (the forecast formulas are
        # the same in both models; the difference lives in what they consume)
        mc = re.match(r"^([A-Z]{1,3})(\d+)$", c)
        pre_v = _pre_val(pre_wb, sh, int(mc.group(2)), _ci(mc.group(1))) if mc else None
        cur_v = _val(wb, sh, c)
        if not isinstance(pre_v, (int, float)) or cur_v is None or abs(cur_v - pre_v) < 1e-9:
            continue
        wb[sh][c].value = pre_v
        try:
            t = _val(wb, sheet, coord)
        finally:
            wb[sh][c].value = cur
        if t is None:
            continue
        out.append((sh, c, (new - t) / swing))
    out.sort(key=lambda x: -abs(x[2]))
    return out


def trace(wb, pre_wb, sheet, coord, depth=30, floor=0.2):
    """Follow the largest contributor down to a typed cell.
    -> (trail [(sheet, coord, label, share)], leaf (sheet, coord) or None)"""
    trail = []
    cur = (sheet, coord)
    seen = set()
    for _ in range(depth):
        if cur in seen:
            break
        seen.add(cur)
        v = wb[cur[0]][cur[1]].value
        if not (isinstance(v, str) and v.startswith("=")):
            return trail, cur                      # a typed cell: the swing factor
        cs = contributors(wb, pre_wb, cur[0], cur[1])
        if not cs or abs(cs[0][2]) < floor:
            # spread across inputs — no single factor; name the largest few
            trail.append((cur[0], cur[1], "SPREAD: " + ", ".join(
                f"{str(wb[s].cell(int(re.sub('[A-Z]', '', c)), 1).value or c)[:22]} {sh_*100:.0f}%" for s, c, sh_ in cs[:3]), 0.0))
            return trail, None
        sh, c, share = cs[0]
        r = int(re.sub(r"[A-Z]", "", c))
        trail.append((sh, c, str(wb[sh].cell(r, 1).value or "")[:30], share))
        cur = (sh, c)
    return trail, None


def unusual_by_history(wb, spec, sheet, row, target_year):
    """This year's move lies outside the range of the model's own past
    year-on-year moves on this row (no margin). -> (bool, this_move, (lo, hi))"""
    cols = year_columns(spec, sheet)
    years = sorted(int(y) for y in cols if str(y).isdigit() and int(y) <= target_year)
    vals = []
    for y in years:
        v = _val(wb, sheet, f"{cols[str(y)]}{row}")
        vals.append(v)
    moves = []
    for a, b in zip(vals, vals[1:]):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a) >= 1:
            moves.append((b - a) / abs(a))
    if len(moves) < 2:
        return False, None, None
    this, past = moves[-1], moves[:-1]
    lo, hi = min(past), max(past)
    return (this < lo or this > hi), this, (lo, hi)


def _parent_of(wb, spec, sheet, row, target_year):
    """The actual-column formula cell on the same sheet that sums this row
    (its group total) and the sibling rows it sums. -> (parent_row, [rows])"""
    tcol = year_columns(spec, sheet).get(str(target_year))
    ws = wb[sheet]
    for r in range(1, ws.max_row + 1):
        f = ws[f"{tcol}{r}"].value
        if not (isinstance(f, str) and f.startswith("=")):
            continue
        refs = [(s, c) for s, c in _refs(f, sheet, wb) if s == sheet and c.startswith(tcol)]
        rows = [int(c[len(tcol):]) for _s, c in refs]
        if row in rows and len(rows) >= 2 and re.fullmatch(r"=\s*(SUM\([^)]*\)|[A-Z]{1,3}\d+(\s*\+\s*[A-Z]{1,3}\d+)+)\s*", f.replace("$", "")):
            return r, [x for x in rows if x != row]
    return None, []


def judge_and_fix(loop, pre_wb, d, leaf, trail, log, gap_of, rerun=None):
    """The swing factor's three cases. -> ("fixed"|"genuine"|"unusual"|"red", text)"""
    from .writegate import is_proven
    wb, spec, ty, writer, served = loop.wb, loop.spec, int(loop.ty), loop.writer, loop.served
    sh, coord = leaf
    r = int(re.sub(r"[A-Z]", "", coord))
    tcol = year_columns(spec, sh).get(str(ty))
    pcol = prior_column(spec, sh, ty)
    label = str(wb[sh].cell(r, 1).value or "")[:30]
    path = " → ".join(f"{t[2] or t[1]}" for t in trail) + f" → {label or coord}"
    ref = f"{sh}!{coord}"
    try:
        rgb = str(wb[sh][coord].fill.fgColor.rgb or "")[-6:]
    except Exception:
        rgb = ""
    colour = "red" if rgb == "FFC7CE" or ref in writer.log.get("flags", []) else "orange" if rgb == "FFC000" else "plain"
    unusual, this_move, band = unusual_by_history(wb, spec, sh, r, ty)
    entry = served.get((sh, r))
    proven = colour == "plain" and (isinstance(entry, dict) and is_proven(entry))
    if proven or colour == "plain":
        if unusual:
            return "unusual", (f"'{d['name']}': swing traced to {path} ({ref}) — genuine per the print, unusual per history "
                               f"(this year {this_move*100:+.0f}%, past years {band[0]*100:+.0f}% to {band[1]*100:+.0f}%)")
        return "genuine", f"'{d['name']}': swing traced to {path} ({ref}) — a proven figure moving within its history"
    # (1) the agent's own red/orange: a better answer, in order
    old = wb[sh][coord].value
    gap0 = gap_of()
    attempts = []
    # (a) a printed line that ties the prior and names the item
    try:
        from .workqueue import candidates_for
        cands = candidates_for(loop, sh, r) or []
    except Exception:
        cands = []
    from .numerics import norm_label as _nl
    ranked = []
    for c in cands:
        positional = str(c.get("basis", "")).startswith("positional")   # the prior at the same slot of the twin table IS the tie
        line = str(c.get("line", ""))
        tie_off = c.get("tie_off")
        tie_off = float(tie_off) if isinstance(tie_off, (int, float)) else 1e9    # 0.0 is a tie, not 'missing'
        if c.get("no_prior") or c.get("nil") or (not positional and tie_off > 0.6) \
                or not kinship(line, label):
            continue
        # a line NAMED like the row outranks one that merely mentions a word of it
        # ('Revenue adjustment for SoC not subject to tax' shares 'tax' with
        # 'Income tax expense'); then the tighter tie; a twin-table slot last
        exact = 0 if _nl(line).replace(" ", "") == _nl(label).replace(" ", "") else 1
        ranked.append((exact, 1 if positional else 0, tie_off if tie_off < 1e9 else 0.0, c))
    ranked.sort(key=lambda x: (x[0], x[1], x[2]))
    for _e, _p, _t, c in ranked[:1]:
        attempts.append(("printed line " + str(c.get("line", ""))[:30] + f" p{c.get('page')}", float(c["value"]), None))
    # (b) the residual of a printed total it belongs to
    prow, sibs = _parent_of(wb, spec, sh, r, ty)
    if prow and sibs:
        p_entry = served.get((sh, prow))
        p_ok = isinstance(p_entry, dict) and is_proven(p_entry)
        s_ok = all(isinstance(served.get((sh, s)), dict) and is_proven(served.get((sh, s))) for s in sibs)
        if (p_ok or isinstance(wb[sh][f"{tcol}{prow}"].value, (int, float))) and s_ok:
            formula = f"={tcol}{prow}" + "".join(f"-{tcol}{s}" for s in sibs)
            attempts.append((f"the residual of its total (row {prow}) less the proven parts", None, formula))
    # (c) last year's share of the parent
    if prow and pcol:
        pv_leaf = _val(wb, sh, f"{pcol}{r}")
        pv_par = _val(wb, sh, f"{pcol}{prow}")
        cur_par = _val(wb, sh, f"{tcol}{prow}")
        if isinstance(pv_leaf, (int, float)) and isinstance(pv_par, (int, float)) and abs(pv_par) >= 1 and isinstance(cur_par, (int, float)):
            attempts.append((f"last year's share of its total (row {prow})", None, f"={pcol}{r}/{pcol}{prow}*{tcol}{prow}"))
    for what, value, formula in attempts:
        val = formula if formula else value
        ok = writer.write(sh, coord, val, prior_coord=f"{pcol}{r}" if pcol else None, trusted=True,
                          force_lock=True, flag="orange",
                          note=f"Sense check: the swing in '{d['name']}' traced to this cell ({path}); replaced by {what}. Please confirm.")
        if not ok:
            continue
        gap1 = gap_of()
        broke = rerun() is False if rerun is not None else False
        if gap1 < gap0 * 0.75 and not broke:
            served[(sh, r)] = {"value": _val(wb, sh, coord), "status": "OK", "conf": 3, "flag": "orange",
                               "doc": None, "page": None, "line": what[:60], "note": "sense check: " + what}
            return "fixed", (f"'{d['name']}': swing traced to {path} ({ref}); replaced by {what} — gap "
                             f"{gap0*100:.0f} → {gap1*100:.0f} points")
        writer.write(sh, coord, old, trusted=True, force_lock=True)
        if rerun is not None:
            rerun()
    return "red", f"'{d['name']}': swing traced to {path} ({ref}) — the agent's own {colour} figure; no better source proved. Please look here first."
