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


def _refs(formula, sheet, wb, max_cells=400):
    """Direct references of a formula, ranges expanded in both directions
    (owner 2026-09-14, CLP: the Australia generation formula averages
    capacity across two columns — AVERAGE(AI66:AJ66) — and a walker that
    dropped cross-column ranges lost the swing one step before the
    wrongly served capacity cell). A range wider than max_cells is a
    block reference, not a formula's inputs; it is skipped."""
    from openpyxl.utils import column_index_from_string as _ci, get_column_letter as _gl
    out = []
    for m in _REF.finditer(str(formula).replace("$", "")):
        sh = (m.group(1) or m.group(2) or sheet).strip()
        if sh not in wb.sheetnames:
            continue
        if m.group(5):
            c1, c2 = _ci(m.group(3)), _ci(m.group(5))
            a, b = int(m.group(4)), int(m.group(6))
            cols = range(min(c1, c2), max(c1, c2) + 1)
            rows = range(min(a, b), max(a, b) + 1)
            if len(cols) * len(rows) > max_cells:
                continue
            for cc in cols:
                for r in rows:
                    out.append((sh, f"{_gl(cc)}{r}"))
        else:
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
        if pre_v in (None, "") and isinstance(cur_v, (int, float)):
            pre_v = 0.0          # blank before the update, a number now: exactly a swing factor
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


def trace(wb, pre_wb, sheet, coord, depth=30, floor=0.2, stable=(), flagged=()):
    """Follow the swing down to a typed cell, the analyst's way (owner
    2026-09-14): a line that is itself STABLE (its own sense check passed)
    is proven — the swing sits between it and the line above it, so the
    trace never enters it; among the contributors that carry the swing,
    the agent's OWN flagged cells (red, orange) are looked at first, then
    the largest swing.
    -> (trail [(sheet, coord, label, share)], leaf (sheet, coord) or None)"""
    trail = []
    cur = (sheet, coord)
    seen = set()
    stable, flagged = set(stable) - {cur}, set(flagged)
    for _ in range(depth):
        if cur in seen:
            break
        seen.add(cur)
        v = wb[cur[0]][cur[1]].value
        if not (isinstance(v, str) and v.startswith("=")):
            return trail, cur                      # a typed cell: the swing factor
        cs = [c for c in contributors(wb, pre_wb, cur[0], cur[1]) if (c[0], c[1]) not in stable]
        own = [c for c in cs if (c[0], c[1]) in flagged and abs(c[2]) >= floor]
        if own:
            cs = own + [c for c in cs if c not in own]
        if (not cs or abs(cs[0][2]) < floor) and str(_pre_content(pre_wb, cur[0], cur[1])) != str(v):
            # the formula itself was rewritten by the update (a key-tie back-out,
            # a constants-law rewrite) and no input explains the swing: the
            # rewritten formula IS the swing factor
            return trail, cur
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


def swing_leaves(wb, pre_wb, sheet, coord, stable=(), flagged=(), floor=0.05, depth=25, budget_s=None):
    """THE SWING CENSUS (owner 2026-09-14: "how much of the swing of the
    item we want to investigate is contributed by this item — tax moved
    10% but carries 50% of the jump in net income, so I look at tax").
    Every typed cell that carries a material share of the swing at
    sheet!coord, with its share of THAT swing (the product of the shares
    down the tree; each share = the part of the parent's swing that
    disappears when the input's pre-update content is put back). A
    stable line is never entered. -> [((sheet, coord), share)] — the
    agent's own flagged cells first, then by |share|."""
    import time as _t
    stable, flagged = set(stable) - {(sheet, coord)}, set(flagged)
    t0 = _t.monotonic()
    out = {}
    # the biggest branches first, so a clock stop keeps the material ones
    todo = [((sheet, coord), 1.0, 0, frozenset())]
    while todo:
        todo.sort(key=lambda x: -abs(x[1]))
        cur, share, d, seen = todo.pop(0)
        if cur in seen or d > depth or abs(share) < floor:
            continue
        if budget_s is not None and _t.monotonic() - t0 > budget_s:
            break
        seen = seen | {cur}
        v = wb[cur[0]][cur[1]].value
        if not (isinstance(v, str) and v.startswith("=")):
            out[cur] = out.get(cur, 0.0) + share
            continue
        cs = [c for c in contributors(wb, pre_wb, cur[0], cur[1]) if (c[0], c[1]) not in stable]
        if not cs:
            if str(_pre_content(pre_wb, cur[0], cur[1])) != str(v):
                out[cur] = out.get(cur, 0.0) + share      # the rewritten formula IS the factor
            continue
        for sh, c, s_ in cs:
            todo.append(((sh, c), share * s_, d + 1, seen))
    return sorted(out.items(), key=lambda kv: (0 if kv[0] in flagged else 1, -abs(kv[1])))


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
    """The actual-column formula cell, on any sheet, that sums this row
    (its group total) and the sibling cells it sums. A segment sheet's
    revenue is summed on the group sheet (CLP: Final's 'Others' adds India,
    SEA and CN), so the search crosses sheets.
    -> (parent (sheet, coord), [(sheet, coord) siblings])"""
    tcol = year_columns(spec, sheet).get(str(target_year))
    leaf = (sheet, f"{tcol}{row}")
    for psh in (spec.get("year_axis") or {}):
        if psh not in wb.sheetnames:
            continue
        pcol_t = year_columns(spec, psh).get(str(target_year))
        if not pcol_t:
            continue
        ws = wb[psh]
        for r in range(1, ws.max_row + 1):
            f = ws[f"{pcol_t}{r}"].value
            if not (isinstance(f, str) and f.startswith("=")) or not re.fullmatch(
                    r"=\s*\+?(SUM\([^)]*\)|(?:'[^']+'!|[A-Za-z0-9_]+!)?[A-Z]{1,3}\d+(\s*\+\s*(?:'[^']+'!|[A-Za-z0-9_]+!)?[A-Z]{1,3}\d+)+)\s*",
                    f.replace("$", "")):
                continue
            refs = _refs(f, psh, wb)
            if leaf in refs and len(refs) >= 2:
                return (psh, f"{pcol_t}{r}"), [x for x in refs if x != leaf]
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
    # OUT OF THE LINE'S WORLD (CLP: India's revenue held 88,018,000,000 — the
    # group's revenue in dollars — while the line itself, tied to the print,
    # is 88,018): an input feeding a headline line that dwarfs the line by
    # the run's own 30x band is not a figure of this model; it goes back to
    # what the analyst had, red, with the trail
    leaf_v = _val(wb, sh, coord)
    line_v = d.get("new0")
    per_share = str(d.get("name", "")).lower() in ("eps", "dps")     # a per-share line is no world for an amount
    if not per_share and isinstance(leaf_v, (int, float)) and isinstance(line_v, (int, float)) and abs(line_v) >= 1 \
            and abs(leaf_v) > 30 * abs(line_v):
        from .execreport import _pre_val
        from openpyxl.utils import column_index_from_string as _ci
        pre_v = _pre_val(pre_wb, sh, r, _ci(tcol))
        back = pre_v if isinstance(pre_v, (int, float)) else 0.0
        writer.write(sh, coord, back, prior_coord=f"{pcol}{r}" if pcol else None, trusted=True, force_lock=True, flag="red",
                     note=(f"Sense check: the swing in '{d['name']}' traced to this cell ({path}); its figure {leaf_v:,.0f} "
                           f"dwarfs the line itself ({line_v:,.0f}) — not a figure of this model; put back to what you had. Please look here."))
        served.pop((sh, r), None)
        return "fixed", (f"'{d['name']}': swing traced to {path} ({ref}) — {leaf_v:,.0f} dwarfs the line ({line_v:,.0f}); "
                         f"put back to {back:,.2f}, red")
    ask = getattr(loop, "ask", None)
    from .execreport import _pre_val
    from openpyxl.utils import column_index_from_string as _ci
    pre_v = _pre_val(pre_wb, sh, r, _ci(tcol)) if tcol else None

    def _auto_ladder():
        """The no-brain path (floors, replays): the rungs in order, the first that narrows the gap."""
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
        # (b) the residual of a printed total it belongs to — the parent is the
        # node the trail came through (it references the leaf directly); the
        # leaf must enter it one-for-one (probed), else the residual is meaningless
        parent, sibs = None, []
        if len(trail) >= 2:
            p_sh, p_c = trail[-2][0], trail[-2][1]
            refs = [x for x in _refs(wb[p_sh][p_c].value, p_sh, wb) if x != (sh, coord)]
            base = _val(wb, p_sh, p_c)
            held = wb[sh][coord].value
            lv = _val(wb, sh, coord)
            if isinstance(base, (int, float)) and isinstance(lv, (int, float)) and abs(lv) > 1e-9:
                wb[sh][coord].value = 0.0
                try:
                    t0 = _val(wb, p_sh, p_c)
                finally:
                    wb[sh][coord].value = held
                if isinstance(t0, (int, float)) and abs(abs(base - t0) - abs(lv)) <= max(0.6, abs(lv) * 1e-3):
                    parent, sibs = (p_sh, p_c), refs
        if parent is None:
            parent, sibs = _parent_of(wb, spec, sh, r, ty)

        def _q(s_, c_):
            return (f"'{s_}'!" if s_ != sh else "") + c_
        if parent and sibs:
            p_sh, p_c = parent
            p_row = int(re.sub(r"[A-Z]", "", p_c))
            p_entry = served.get((p_sh, p_row))
            p_ok = isinstance(p_entry, dict) and is_proven(p_entry)
            s_ok = all(isinstance(served.get((s_, int(re.sub(r"[A-Z]", "", c_)))), dict)
                       and is_proven(served.get((s_, int(re.sub(r"[A-Z]", "", c_))))) for s_, c_ in sibs)
            if (p_ok or isinstance(wb[p_sh][p_c].value, (int, float))) and s_ok:
                formula = "=" + _q(p_sh, p_c) + "".join("-" + _q(s_, c_) for s_, c_ in sibs)
                attempts.append((f"the residual of its total ({p_sh}!{p_c}) less the proven parts", None, formula))
        # (c) last year's share of the parent — only over a total that stands
        # on its own (typed), never over a sum of the parts: a share of a total
        # that includes the cell itself is a circular reference (CLP floor
        # 2026-09-15: ROAFNA!AI71 = AH71/AH64*AI64 with AI64 summing AI71)
        if parent and pcol and not (isinstance(wb[parent[0]][parent[1]].value, str)
                                    and str(wb[parent[0]][parent[1]].value).startswith("=")):
            p_sh, p_c = parent
            p_row = int(re.sub(r"[A-Z]", "", p_c))
            p_pcol = prior_column(spec, p_sh, ty)
            pv_leaf = _val(wb, sh, f"{pcol}{r}")
            pv_par = _val(wb, p_sh, f"{p_pcol}{p_row}") if p_pcol else None
            cur_par = _val(wb, p_sh, p_c)
            if isinstance(pv_leaf, (int, float)) and isinstance(pv_par, (int, float)) and abs(pv_par) >= 1 and isinstance(cur_par, (int, float)):
                attempts.append((f"last year's share of its total ({p_sh}!{p_c})", None,
                                 f"={pcol}{r}/" + _q(p_sh, f"{p_pcol}{p_row}") + "*" + _q(p_sh, p_c)))
        for what, value, formula in attempts:
            val = formula if formula else value
            mark = len(writer.log.get("writes_all", []))
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
            # the trial failed: the old value AND the old look come back (the
            # red the constants law painted is the analyst's 'look here')
            writer.take_back(sh, coord, old, writer.log["style_journal"][mark])
            if rerun is not None:
                rerun()
        return "red", f"'{d['name']}': swing traced to {path} ({ref}) — the agent's own {colour} figure; no better source proved. Please look here first."

    if ask is None or (proven and not unusual) or (colour == "plain" and not unusual):
        return _auto_ladder()
    # THE RUNG CARD (owner 2026-09-14: "brain picks the rung, code
    # verifies"): every way this cell could be filled, in the analyst's
    # order — a printed line that ties, a back-out the model itself gives,
    # last year's figure kept red — with the effect of each on the swing.
    # A plug is never on this card: it is the terminal ladder's last resort.
    old = wb[sh][coord].value
    gap0 = gap_of()
    options, ways = {}, []
    try:
        from .workqueue import candidates_for
        cands = candidates_for(loop, sh, r) or []
    except Exception:
        cands = []
    from .numerics import norm_label as _nl
    ranked = []
    for c in cands:
        line = str(c.get("line", ""))
        tie_off = c.get("tie_off")
        tie_off = float(tie_off) if isinstance(tie_off, (int, float)) else 1e9
        if c.get("no_prior") or c.get("nil") or tie_off > 0.6 or not kinship(line, label):
            continue
        exact = 0 if _nl(line).replace(" ", "") == _nl(label).replace(" ", "") else 1
        ranked.append((exact, tie_off, c))
    ranked.sort(key=lambda x: (x[0], x[1]))
    for i, (_e, _t, c) in enumerate(ranked[:2]):
        key = f"printed:{'AB'[i]}"
        ways.append((key, "printed", float(c["value"]), None,
                     f"printed line '{str(c.get('line', ''))[:40]}' {str(c.get('doc', ''))[:24]} p{c.get('page')} — its comparative ties the prior"))
    parent, sibs = None, []
    if len(trail) >= 2:
        p_sh, p_c = trail[-2][0], trail[-2][1]
        if isinstance(wb[p_sh][p_c].value, str) and wb[p_sh][p_c].value.startswith("="):
            refs = [x for x in _refs(wb[p_sh][p_c].value, p_sh, wb) if x != (sh, coord)]
            if refs:
                parent, sibs = (p_sh, p_c), refs
    if parent is None:
        parent, sibs = _parent_of(wb, spec, sh, r, ty)

    def _q(s_, c_):
        return (f"'{s_}'!" if s_ != sh else "") + c_
    if parent and sibs:
        p_sh, p_c = parent
        p_row = int(re.sub(r"[A-Z]", "", p_c))
        p_entry = served.get((p_sh, p_row))
        p_ok = isinstance(p_entry, dict) and is_proven(p_entry)
        s_ok = all(isinstance(served.get((s_, int(re.sub(r"[A-Z]", "", c_)))), dict)
                   and is_proven(served.get((s_, int(re.sub(r"[A-Z]", "", c_))))) for s_, c_ in sibs)
        if (p_ok or isinstance(wb[p_sh][p_c].value, (int, float))) and s_ok:
            ways.append(("backout:R", "backout", None, "=" + _q(p_sh, p_c) + "".join("-" + _q(s_, c_) for s_, c_ in sibs),
                         f"the residual of its total {p_sh}!{p_c} less the proven parts (a formula, orange)"))
        p_pcol = prior_column(spec, p_sh, ty)
        pv_leaf = _val(wb, sh, f"{pcol}{r}") if pcol else None
        pv_par = _val(wb, p_sh, f"{p_pcol}{p_row}") if p_pcol else None
        par_typed = not (isinstance(wb[p_sh][p_c].value, str) and str(wb[p_sh][p_c].value).startswith("="))
        if par_typed and isinstance(pv_leaf, (int, float)) and isinstance(pv_par, (int, float)) and abs(pv_par) >= 1 and pcol:
            ways.append(("backout:S", "backout", None, f"={pcol}{r}/" + _q(p_sh, f"{p_pcol}{p_row}") + "*" + _q(p_sh, p_c),
                         f"last year's share of its total {p_sh}!{p_c} (a formula, orange)"))
    # THE FALLBACKS ARE CASE BY CASE (owner 2026-09-15): when nothing proves
    # the figure, both stale figures are shown with their meaning — the
    # analyst's own estimate for this year (what the model held before the
    # update) and last year's actual — and the brain picks one and says
    # why; red either way. The owner's own instinct on India debt (estimate
    # 0, last year 61,829, nothing printed): keep the estimate, flag it.
    ly_v = _val(wb, sh, f"{pcol}{r}") if pcol else None
    # A PROVEN FIGURE IS NEVER TRADED FOR A GUESS (run 34874944306: the brain
    # replaced the proven fuel clause −1,043 with the analyst's estimate 0
    # because the cash-flow line swung): a proven cell's ways are keep, or
    # another proven printed line — never the estimate, last year's figure
    # or a back-out
    if proven and colour == "plain":
        ways = [w for w in ways if w[1] == "printed"]
    if isinstance(pre_v, (int, float)) and not (proven and colour == "plain"):
        ways.append(("estimate", "stale", float(pre_v), None,
                     f"keep the analyst's own estimate for this year ({pre_v:,.2f}) — nothing printed proves the figure; stays RED as 'not found'"))
    if isinstance(ly_v, (int, float)) and not (proven and colour == "plain") and (not isinstance(pre_v, (int, float)) or abs(ly_v - pre_v) > 0.5):
        ways.append(("lastyear", "stale", float(ly_v), None,
                     f"keep last year's actual ({ly_v:,.2f}) — nothing printed proves the figure; stays RED as 'not found'"))
    ways.append(("keep", "keep", None, None,
                 "keep the current figure — it belongs on this row (say why)"))
    # the effect of each way on the line's gap, by trial
    previews = {}
    for key, kind, value, formula, _desc in ways:
        if kind == "keep":
            previews[key] = gap0
            continue
        mark = len(writer.log.get("writes_all", []))
        try:
            ok_t = writer.write(sh, coord, formula if formula else value, prior_coord=f"{pcol}{r}" if pcol else None,
                                trusted=True, force_lock=True, flag="orange", note="sense check trial")
            previews[key] = gap_of() if ok_t else None
        finally:
            if len(writer.log.get("writes_all", [])) > mark:
                writer.take_back(sh, coord, old, writer.log["style_journal"][mark])
    cur_v = _val(wb, sh, coord)
    basis = (entry.get("line") if isinstance(entry, dict) else None) or "no evidence line"
    head = [f"CARD RUNG {sh}!{coord} '{label}'",
            f"  the line: '{d['name']}' — actual {d.get('d0', 0) * 100:+.1f}% vs the analyst's estimate, next year "
            f"{d.get('d1', 0) * 100:+.1f}% vs the old forecast; this cell carries {abs(trail[-1][3]) * 100:.0f}% of the swing"
            if trail and isinstance(trail[-1][3], (int, float)) else f"  the line: '{d['name']}'",
            f"  this cell now: {cur_v if cur_v is None else f'{cur_v:,.2f}'} ({colour}; {basis}); last year {pre_v if pre_v is None else f'{pre_v:,.2f}'}"
            + (f"; this year's move {this_move * 100:+.0f}% vs past {band[0] * 100:+.0f}% to {band[1] * 100:+.0f}%" if unusual and band else ""),
            "  the ways to fill it, in the analyst's order (a plug is never one of them). When nothing is printed, the",
            "  analyst's estimate is usually closer to what was expected than last year's figure — but judge this case:"]
    for key, kind, value, formula, desc in ways:
        pv_ = previews.get(key)
        eff = ("cannot be written" if pv_ is None else f"gap {gap0 * 100:.0f} → {pv_ * 100:.0f} points")
        shown = (f"{value:,.2f}" if isinstance(value, (int, float)) else (formula or "as is"))
        head.append(f"    {key}: {shown} — {desc} [{eff}]")
        options[key] = desc
    text = "\n".join(head) + "\n  answers: " + ", ".join(options)
    log(f"[queue] card RUNG {sh}!{r}: " + " | ".join(ln.strip() for ln in head[4:])[:900])
    pick = ask(text, options, "__auto__")
    if pick not in options:
        return _auto_ladder()
    way = next(w for w in ways if w[0] == pick)
    key, kind, value, formula, desc = way
    log(f"[queue] RUNG {sh}!{coord} -> {pick}")
    if kind == "keep":
        return ("genuine" if not unusual else "unusual"), (f"'{d['name']}': swing traced to {path} ({ref}) — the brain judged the figure belongs here"
                                                             + (f" (unusual per history: {this_move * 100:+.0f}%)" if unusual else ""))
    if kind == "printed":
        c = ranked[{"printed:A": 0, "printed:B": 1}[key]][2]
        res = str(loop.t_set_input({"cell": f"{sh}!{coord}", "value": value, "card": "sense",
                                    "why": f"p{c.get('page')}: {str(c.get('line', ''))[:60]} — sense-check rung 1"}))
        if res.startswith(("REFUSED", "REVERTED", "MISS")):
            log(f"[sense] RUNG {sh}!{coord} printed refused by the law: {res[:120]}")
            return "red", f"'{d['name']}': swing traced to {path} ({ref}) — the brain's printed pick was refused ({res[:80]}); please look here"
        return "fixed", f"'{d['name']}': swing traced to {path} ({ref}); {desc} — gap {gap0 * 100:.0f} → {gap_of() * 100:.0f} points"
    mark = len(writer.log.get("writes_all", []))
    if kind == "backout":
        ok_w = writer.write(sh, coord, formula, prior_coord=f"{pcol}{r}" if pcol else None, trusted=True, force_lock=True, flag="orange",
                            note=f"Sense check: the swing in '{d['name']}' traced to this cell ({path}); the brain chose {desc}. Please confirm.")
    else:
        ok_w = writer.write(sh, coord, value, prior_coord=f"{pcol}{r}" if pcol else None, trusted=True, force_lock=True, flag="red",
                            note=f"Sense check: the swing in '{d['name']}' traced to this cell ({path}); the run's figure was not proven — last year's kept, NOT FOUND. Please look here.")
    if not ok_w:
        return "red", f"'{d['name']}': swing traced to {path} ({ref}) — the brain's pick ({pick}) could not be written; please look here"
    broke = rerun() is False if rerun is not None else False
    if broke:
        writer.take_back(sh, coord, old, writer.log["style_journal"][mark])
        if rerun is not None:
            rerun()
        return "red", f"'{d['name']}': swing traced to {path} ({ref}) — the brain's pick ({pick}) opened a check and was taken back; please look here"
    if kind == "stale":
        served.pop((sh, r), None)
        return "stale", f"'{d['name']}': swing traced to {path} ({ref}) — not proven this year; last year's {value:,.2f} kept, red"
    served[(sh, r)] = {"value": _val(wb, sh, coord), "status": "OK", "conf": 3, "flag": "orange",
                       "doc": None, "page": None, "line": desc[:60], "note": "sense check: " + desc[:60]}
    return "fixed", f"'{d['name']}': swing traced to {path} ({ref}); {desc} — gap {gap0 * 100:.0f} → {gap_of() * 100:.0f} points"
