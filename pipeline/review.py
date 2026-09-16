"""THE REVIEW (owner 2026-09-16: "the card is an issue — there is no
thinking in preparing the cards, so the brain thinks from wrong choices or
choices without enough context"). The brain reviews the MODEL, not a card:
code measures the objectives, lays out the headline lines and every cell
the run wrote with its move against that cell's own history and its
evidence, and answers the tools the brain calls. The brain decides what to
look at and what to change; code applies, verifies the evidence, measures
the consequence and logs the turn. The only decision code makes is the very
last one: at the clock, any actual-year check still off goes to the
terminal ladder, orange, so the model is delivered balanced.
"""
import json
import re
import time

from .checks import CHECK_TOL, forecast_columns, prior_column, year_columns
from .consequence import _fault, _plug_here, broken_objectives, restore, sanity_rows, sanity_watch, snapshot
from .evaluator import Evaluator

MANDATE = """You are the equity analyst reviewing your own model update before delivery.

The model must (1) balance every year, (2) tie every key number to the print, (3) roll forward
sanely — no negative cash or assets, no headline line moving out of its history without a printed
reason. A wrong number is a failure; so is a number you could have fixed and left.

When something is off, find the INPUT that caused it — look at what moved against its history
first — and fix it with evidence. Compensating errors come in pairs; name both and set them
together. Say `done` only when every objective holds or you have named why it cannot.

You answer in JSON only: {"thinking": "...", "calls": [ ... ]}. Any number of calls per turn,
executed in the order you write them; their answers come back in the next turn. The calls:
  {"tool":"show","ref":"Sheet!AI16"}                  the row's inputs, what uses it, its history, printed lines on file
  {"tool":"find","q":"46.3"}  or {"q":"Fuel Cost"}    printed lines carrying that number or naming that label, with page
  {"tool":"try","sets":[{"ref":"Sheet!AI16","value":46.3}]}    preview on a snapshot: the objectives before and after, then restored
  {"tool":"set","sets":[{"ref":"Sheet!AI16","value":46.3}],"because":"p243 'Fuel Cost Adjustment 46.3 46.3'"}
  {"tool":"restore","ref":"Sheet!AI16","why":"..."}   put back what the analyst had, red
  {"tool":"plug","check":"Sheet!AI99","into":"Sheet!AI95","why":"..."}   orange, reported
  {"tool":"done","objectives":{"balance":"holds | cannot be closed because ...","keys":"...","rollforward":"..."}}
A `sets` list with two entries is applied and measured as ONE change — that is how a compensating
pair is resolved. A `set` lands plain only when its evidence ties (the quote is on the page and the
comparative ties the model's prior), or when `because` states arithmetic code can verify; otherwise
it lands red for the analyst — it is never refused for want of evidence."""


# ── reading the model ────────────────────────────────────────────────────

def _num(x):
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return None


def _fmt(x):
    if x is None:
        return ""
    return f"{x:,.2f}" if abs(x) < 100 else f"{x:,.0f}"


def _label(ws, r):
    for c in ("A", "B", "C", "D"):
        v = ws[f"{c}{r}"].value
        if isinstance(v, str) and v.strip():
            return v.strip()[:40]
    return f"row {r}"


def _row_of(coord):
    return int(re.sub(r"[A-Z$]", "", coord))


def _col_of(coord):
    return re.sub(r"[0-9$]", "", coord)


def _act_col(loop, sheet):
    return year_columns(loop.spec, sheet).get(str(int(loop.ty)))


def _hist_cols(loop, sheet, n=4):
    yc = year_columns(loop.spec, sheet)
    yrs = sorted(int(y) for y in yc if str(y).isdigit() and int(y) < int(loop.ty))
    return [yc[str(y)] for y in yrs[-n:]]


def _fill(cell):
    try:
        rgb = cell.fill.fgColor.rgb if cell.fill and cell.fill.fill_type else None
    except Exception:  # noqa: BLE001
        rgb = None
    return {"FFFFC7CE": "red", "FFFFC000": "orange"}.get(rgb or "", "plain")


def _value_index(loop):
    """{rounded model-units value: [(item, scale)]} over the ledger, built once —
    the comparative tie of 260 written cells costs one pass, not 260."""
    idx = loop.__dict__.get("_review_vindex")
    if idx is not None:
        return idx
    from .writegate import _SCALES, _nums, _sourceable
    idx = {}
    for it in getattr(loop.ledger, "items", []) or []:
        if not _sourceable(it):
            continue
        for n in _nums(it):
            if not isinstance(n, (int, float)) or n == 0:
                continue
            for f in _SCALES:
                idx.setdefault(round(abs(n) / f, 1), []).append((it, f))
    loop.__dict__["_review_vindex"] = idx
    return idx


def _evidence_line(loop, sheet, coord, value, prior):
    """THE PRINTED LINE, NOT THE CELL'S NOTE (owner 2026-09-16: a note is what
    the run said about itself). -> the quoted line with its page and whether the
    comparative ties the model's prior, or 'no printed line'."""
    from .writegate import ties_prior
    hits = _value_index(loop).get(round(abs(value), 1), []) if isinstance(value, (int, float)) else []
    for it, scale in hits[:12]:
        line = " ".join(str(getattr(it, "source_line", "") or getattr(it, "label", "")).split())[:90]
        tie = ties_prior(it, scale, prior, value) if isinstance(prior, (int, float)) else False
        return (f"p{getattr(it, 'page', '?')} '{line}'"
                + (f" — comparative ties the model's prior {_fmt(prior)}" if tie
                   else " — the comparative does NOT tie the model's prior "
                        + (_fmt(prior) if prior is not None else "(none)")))
    e = (loop.served or {}).get((sheet, _row_of(coord)))
    if isinstance(e, dict) and e.get("line"):
        return f"p{e.get('page')} '{str(e.get('line'))[:70]}' — the value is not printed on any page on file"
    return "no printed line"


def _metrics(loop, key_panel, panel_path):
    """Every objective as a NUMBER, in one ordered dict {ref: (what, value)} —
    the balance checks in every year, each key's gap to the print, cash and
    total assets from the actual period on. What `try` diffs, what `done` is
    held to, what the context prints."""
    wb, spec, ty = loop.wb, loop.spec, int(loop.ty)
    ev = Evaluator(wb)
    out = {}
    for c in (spec.get("check_rows") or []):
        sheet, row = c.get("sheet"), int(c.get("row"))
        if sheet not in wb.sheetnames:
            continue
        expect = float(c.get("expect", 0))
        for year, col in sorted(year_columns(spec, sheet).items(), key=lambda kv: str(kv[0])):
            try:
                v = ev.cell(sheet, f"{col}{row}")
            except Exception as e:  # noqa: BLE001
                _fault(loop, f"check {sheet}!{col}{row} cannot be evaluated: {e!r}")
                continue
            if isinstance(v, (int, float)):
                out[f"{sheet}!{col}{row}"] = (f"balance check {year} (must be {expect:,.0f})", float(v))
    try:
        from .keytie import key_state
        for nm, ref, got, want, ok in key_state(wb, spec, ty, panel_path, panel=key_panel):
            if isinstance(got, (int, float)):
                out[ref] = (f"key '{nm}' vs print {_fmt(_num(want))}" + ("" if ok else "  ← OFF THE PRINT"),
                            float(got) - (want if isinstance(want, (int, float)) else float(got)))
    except Exception as e:  # noqa: BLE001
        _fault(loop, f"key objectives unavailable: {e!r}")
    try:
        for nm, (sh, r) in sanity_rows(loop).items():
            if sh not in wb.sheetnames:
                continue
            yc = year_columns(spec, sh)
            cols = [(yc.get(str(ty)), str(ty))] + sorted(((c, y) for y, c in yc.items() if str(y).isdigit() and int(y) > ty),
                                                         key=lambda x: int(x[1]))
            for col, year in cols[:4]:
                if not col:
                    continue
                try:
                    v = ev.cell(sh, f"{col}{r}")
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(v, (int, float)):
                    out[f"{sh}!{col}{r}"] = (f"{nm} {year} (must not be negative)", float(v))
    except Exception as e:  # noqa: BLE001
        _fault(loop, f"sanity objectives unavailable: {e!r}")
    return out


def _metrics_text(m):
    return [f"  {ref:<20} {what:<46} {_fmt(v):>14}" for ref, (what, v) in m.items()]


def _metric_diff(m0, m1):
    """What a change did to the objectives, line by line — only what moved."""
    out = []
    for ref, (what, v1) in m1.items():
        v0 = m0.get(ref, (None, None))[1]
        if v0 is None or abs(v1 - v0) > CHECK_TOL:
            out.append(f"    {ref} {what}: {_fmt(v0)} → {_fmt(v1)}")
    for ref in m0:
        if ref not in m1:
            out.append(f"    {ref} {m0[ref][0]}: {_fmt(m0[ref][1])} → (no longer measurable)")
    return out or ["    nothing moved"]


def _headline_rows(loop):
    """The report table's own P&L / BS / CF roles — the model's structure, not a list."""
    try:
        from .reportpage import resolve_rows
        rows, _primary = resolve_rows(loop.wb, loop.spec, int(loop.ty), getattr(loop, "period", None) or "FY")
        return [(role, v[0], int(v[1])) for role, v in rows.items() if v and v[0] in loop.wb.sheetnames]
    except Exception as e:  # noqa: BLE001
        _fault(loop, f"headline lines not resolved: {e!r}")
        return []


def build_context(loop, pre_wb, key_panel, panel_path, notes=(), answers=(), cap=260, trace_budget_s=40.0):
    """One reading of the model for the brain: the objectives measured, the
    headline lines against the analyst's own book, every written actual-column
    cell with its move against its history and its printed evidence, and the
    trace of the forecast lines that moved."""
    wb, spec, ty = loop.wb, loop.spec, int(loop.ty)
    ev, ev0 = Evaluator(wb), Evaluator(pre_wb)
    L = ["## 1. OBJECTIVES, measured by code"]
    L += _metrics_text(_metrics(loop, key_panel, panel_path))
    L.append("")
    L.append("## 2. HEADLINE LINES (history | the analyst's pre-update estimate for the actual year | now | next year before → now)")
    for role, sh, r in _headline_rows(loop):
        ac, fcs = _act_col(loop, sh), forecast_columns(spec, sh, ty) or []
        if not ac:
            continue
        hist = " | ".join(_fmt(_num(ev0.cell(sh, f"{c}{r}"))) for c in _hist_cols(loop, sh))
        est, now = _fmt(_num(ev0.cell(sh, f"{ac}{r}"))), _fmt(_num(ev.cell(sh, f"{ac}{r}")))
        nx = (f" | next {_fmt(_num(ev0.cell(sh, f'{fcs[0]}{r}')))} → {_fmt(_num(ev.cell(sh, f'{fcs[0]}{r}')))}") if fcs else ""
        L.append(f"  {sh}!{ac}{r:<5} {role:26} {hist} | est {est} | now {now}{nx}")
    L.append("")
    L.append("## 3. EVERY CELL THE RUN WROTE IN THE ACTUAL COLUMN (largest move against the cell's own history first; "
             "a cell with no history to judge against is listed last)")
    first = {}
    for sh_w, co_w, old_w, _new in (loop.writer.log.get("writes_all", []) or []):
        if sh_w in wb.sheetnames and _col_of(co_w) == _act_col(loop, sh_w) and (sh_w, co_w) not in first:
            first[(sh_w, co_w)] = old_w
    rows = []
    for (sh, co), old in first.items():
        r = _row_of(co)
        try:
            new = _num(ev.cell(sh, co))
        except Exception:  # noqa: BLE001
            continue
        if new is None:
            continue
        hist = [h for h in (_num(ev0.cell(sh, f"{c}{r}")) for c in _hist_cols(loop, sh)) if h is not None]
        lo, hi = (min(hist), max(hist)) if hist else (None, None)
        if hist and hi - lo > 0:
            out = max(lo - new, new - hi, 0) / max(abs(hi), abs(lo), 1)
        elif hist:
            out = abs(new - hi) / max(abs(hi), 1)
        else:
            out = -1.0
        pcol = prior_column(spec, sh, ty)
        prior = _num(ev0.cell(sh, f"{pcol}{r}")) if pcol else None
        rows.append((out, sh, co, _label(wb[sh], r), _num(old), new, hist, _fill(wb[sh][co]),
                     _evidence_line(loop, sh, co, new, prior)))
    rows.sort(key=lambda t: -t[0])
    for _o, sh, co, lab, old, new, hist, flag, evid in rows[:cap]:
        L.append(f"  {sh}!{co:<6} {lab:40} was {_fmt(old):>11} → now {_fmt(new):>11} | "
                 f"history {', '.join(_fmt(h) for h in hist):32} | {flag:6} | {evid}")
    L.append(f"  ({len(rows)} written cells in total{'; the rest are within their history' if len(rows) > cap else ''})")
    L.append("")
    L.append("## 4. TRACE — the headline lines whose next-year forecast moved more than 10% against the analyst's book, "
             "and the typed inputs that carry the move")
    # the trace is the expensive half of the context: it is walked once per
    # state of the model (the write journal's mark), not once per turn, and the
    # whole section shares ONE budget — a turn is a turn, not a census
    mark, cached = loop.__dict__.get("_review_trace", (None, None))
    if mark == len(loop.writer.log.get("writes_all", []) or []):
        L += cached
    else:
        trace, t0 = [], time.monotonic()
        try:
            from .investigate import swing_leaves
            for role, sh, r in _headline_rows(loop):
                fcs = forecast_columns(spec, sh, ty) or []
                left = trace_budget_s - (time.monotonic() - t0)
                if not fcs or left <= 0:
                    if left <= 0:
                        trace.append("  (the trace used its budget — the lines below it are not walked)")
                        break
                    continue
                f0, f1 = _num(ev0.cell(sh, f"{fcs[0]}{r}")), _num(ev.cell(sh, f"{fcs[0]}{r}"))
                if f0 is None or f1 is None or abs(f0) < 1 or abs(f1 - f0) / abs(f0) < 0.10:
                    continue
                leaves = swing_leaves(wb, pre_wb, sh, f"{fcs[0]}{r}", budget_s=left)[:6]
                parts = [f"{s2}!{c2} '{_label(wb[s2], _row_of(c2))}' {_fmt(_num(ev0.cell(s2, c2)))} → {_fmt(_num(ev.cell(s2, c2)))}"
                         for (s2, c2), _share in leaves]
                trace.append(f"  {sh}!{fcs[0]}{r} {role} {_fmt(f0)} → {_fmt(f1)}: " + "; ".join(parts))
        except Exception as e:  # noqa: BLE001
            trace.append(f"  (the trace could not be walked: {type(e).__name__}: {str(e)[:80]})")
        loop.__dict__["_review_trace"] = (len(loop.writer.log.get("writes_all", []) or []), trace)
        L += trace
    if notes:
        L.append("")
        L.append("## 5. WHAT THE EARLY LOOK FOUND (the checkpoint sense check, before the writes)")
        L += [f"  {n}" for n in list(notes)[:30]]
    if answers:
        L.append("")
        L.append("## 6. YOUR LAST TURN")
        L += list(answers)
    return "\n".join(L)


# ── the tools ────────────────────────────────────────────────────────────

def _parse_ref(loop, ref):
    sh, _, co = str(ref).partition("!")
    if sh not in loop.wb.sheetnames:
        return None, None, f"no sheet '{sh}' in this workbook"
    co = co.replace("$", "").upper()
    if not re.fullmatch(r"[A-Z]{1,3}\d+", co):
        # 'Sheet!16' — the row alone, in the actual column
        if co.isdigit() and _act_col(loop, sh):
            co = f"{_act_col(loop, sh)}{co}"
        else:
            return None, None, f"'{ref}' is not a cell"
    return sh, co, None


def t_show(loop, pre_wb, ref):
    sh, co, err = _parse_ref(loop, ref)
    if err:
        return [f"show {ref}: {err}"]
    r, wb = _row_of(co), loop.wb
    ev, ev0 = Evaluator(wb), Evaluator(pre_wb)
    out = [f"show {sh}!{co} '{_label(wb[sh], r)}'"]
    out.append("    history " + ", ".join(f"{c}={_fmt(_num(ev0.cell(sh, f'{c}{r}')))}" for c in _hist_cols(loop, sh))
               + f" | analyst's estimate {_fmt(_num(ev0.cell(sh, co)))} | now {_fmt(_num(ev.cell(sh, co)))}")
    held = wb[sh][co].value
    out.append(f"    the cell holds: {str(held)[:120]}")
    try:
        from .investigate import _refs
        if isinstance(held, str) and held.startswith("="):
            ins = _refs(held, sh, wb)[:12]
            out.append("    its inputs: " + "; ".join(f"{a}!{b} '{_label(wb[a], _row_of(b))}' = {_fmt(_num(ev.cell(a, b)))}"
                                                      for a, b in ins))
    except Exception as e:  # noqa: BLE001
        out.append(f"    (its inputs could not be read: {e!r})")
    users, t0 = [], time.monotonic()
    for s2 in wb.sheetnames:
        if time.monotonic() - t0 > 6.0 or len(users) >= 10:
            break
        for row in wb[s2].iter_rows():
            for c2 in row:
                v = c2.value
                if isinstance(v, str) and v.startswith("=") and re.search(rf"(?<![A-Z0-9]){co}(?![0-9])", v) \
                        and (s2 == sh or re.search(rf"'?{re.escape(sh)}'?!", v)):
                    users.append(f"{s2}!{c2.coordinate} '{_label(wb[s2], c2.row)}'")
                    if len(users) >= 10:
                        break
            if len(users) >= 10:
                break
    out.append("    used by: " + ("; ".join(users) if users else "nothing found in a 6 s walk"))
    cand = []
    for v in ({_num(ev.cell(sh, co)), _num(ev0.cell(sh, co))} | {_num(ev0.cell(sh, f"{c}{r}")) for c in _hist_cols(loop, sh)}):
        if not isinstance(v, (int, float)) or v == 0:
            continue
        for it, _f in _value_index(loop).get(round(abs(v), 1), [])[:3]:
            cand.append(f"{_fmt(v)} on p{getattr(it, 'page', '?')}: "
                        + " ".join(str(getattr(it, "source_line", "") or getattr(it, "label", "")).split())[:80])
    out.append("    printed lines carrying this row's figures: " + ("; ".join(cand[:8]) if cand else "none on file"))
    return out


def t_find(loop, q):
    q = str(q).strip()
    out = [f"find {q!r}"]
    hits = []
    try:
        v = float(q.replace(",", ""))
    except ValueError:
        v = None
    if v is not None:
        hits = [it for it, _f in _value_index(loop).get(round(abs(v), 1), [])]
    else:
        ql = q.lower()
        hits = [it for it in (getattr(loop.ledger, "items", []) or [])
                if ql in str(getattr(it, "label", "") or "").lower()
                or ql in str(getattr(it, "source_line", "") or "").lower()]
    for it in hits[:15]:
        out.append(f"    {getattr(it, 'doc', '?')} p{getattr(it, 'page', '?')}: "
                   + " ".join(str(getattr(it, "source_line", "") or getattr(it, "label", "")).split())[:110])
    if not hits:
        out.append("    nothing on file")
    elif len(hits) > 15:
        out.append(f"    ({len(hits)} lines match; the first 15 are shown — narrow the query)")
    return out


_ARITH = re.compile(r"[-+]?\d[\d,]*\.?\d*(?:\s*[-+*/]\s*[-+]?\d[\d,]*\.?\d*)+")


def _evidence_verdict(loop, sets, because):
    """Does this change land plain? The quote is on a page and the comparative
    ties the model's prior, OR the brain states arithmetic code verifies.
    -> (plain: bool, why: str)"""
    from .writegate import ties_prior
    because = str(because or "")
    for s in sets:
        sh, co, v = s["sheet"], s["coord"], s["value"]
        if not isinstance(v, (int, float)):
            return False, "the value is not a number code can tie"
        m = _ARITH.search(because)
        if m:
            try:
                got = float(eval(m.group(0).replace(",", ""), {"__builtins__": {}}, {}))  # noqa: S307
            except Exception:  # noqa: BLE001
                got = None
            if got is not None and abs(got - v) <= max(0.05, abs(v) * 1e-4):
                continue
        pcol = prior_column(loop.spec, sh, int(loop.ty))
        prior = _num(Evaluator(loop.wb).cell(sh, f"{pcol}{_row_of(co)}")) if pcol else None
        quoted = False
        for it, scale in _value_index(loop).get(round(abs(v), 1), [])[:20]:
            line = " ".join(str(getattr(it, "source_line", "") or getattr(it, "label", "")).split())
            words = [w for w in re.findall(r"[A-Za-z一-鿿]{4,}", because)]
            named = any(w.lower() in line.lower() for w in words) or str(getattr(it, "page", "")) in because
            if named and ties_prior(it, scale, prior, v):
                quoted = True
                break
        if not quoted:
            return False, f"{sh}!{co}: no quoted page line whose comparative ties the model's prior, and no arithmetic to verify"
    return True, "the evidence ties"


def _sets_text(sets):
    return ", ".join("{0}!{1}={2}".format(s["sheet"], s["coord"], _fmt(_num(s["value"]))) for s in sets)


def _apply_sets(loop, sets, plain, note, log):
    """One change — a pair is ONE write batch, applied and measured together."""
    w, applied, refused = loop.writer, [], []
    for s in sets:
        sh, co, v = s["sheet"], s["coord"], s["value"]
        pcol = prior_column(loop.spec, sh, int(loop.ty))
        ok = w.write(sh, co, v, prior_coord=f"{pcol}{_row_of(co)}" if pcol else None,
                     trusted=bool(plain), force_lock=True, flag=None if plain else "red", note=note)
        (applied if ok else refused).append(f"{sh}!{co}")
        if ok and not plain:
            loop.served.pop((sh, _row_of(co)), None)
        if ok:
            back = Evaluator(loop.wb).cell(sh, co)          # read back: never trust the write code
            if isinstance(back, (int, float)) and isinstance(v, (int, float)) and abs(back - v) > max(0.05, abs(v) * 1e-6):
                log(f"[review] read-back {sh}!{co} shows {back} after writing {v}")
    return applied, refused


# ── the loop ─────────────────────────────────────────────────────────────

def _one_call(loop, pre_wb, call, key_panel, panel_path, log, repair_round, gate_once, state):
    """Answer one tool call. -> (lines, result) where result is None, or the
    gate's tuple when the model changed."""
    tool = str(call.get("tool") or "").strip().lower()
    if tool == "show":
        return t_show(loop, pre_wb, call.get("ref", "")), None
    if tool == "find":
        return t_find(loop, call.get("q", "")), None
    if tool in ("try", "set"):
        sets, bad = [], []
        for s in (call.get("sets") or ([call] if call.get("ref") else [])):
            sh, co, err = _parse_ref(loop, s.get("ref", ""))
            if err:
                bad.append(err)
                continue
            if _col_of(co) != _act_col(loop, sh):
                bad.append(f"{sh}!{co} is not in the actual column — the review changes the actual period only")
                continue
            sets.append({"sheet": sh, "coord": co, "value": s.get("value")})
        if bad:
            return [f"{tool}: " + "; ".join(bad)], None
        if not sets:
            return [f"{tool}: no cell named"], None
        m0 = _metrics(loop, key_panel, panel_path)
        if tool == "try":
            snap = snapshot(loop)
            try:
                _applied, refused = _apply_sets(loop, sets, True, "trial", log)
                repair_round("review try")
                lines = ["try " + _sets_text(sets) + ":"]
                if refused:
                    lines.append(f"    the writer refused {refused} — this change cannot be written as it stands")
                lines += _metric_diff(m0, _metrics(loop, key_panel, panel_path))
                lines.append("    (restored — nothing was kept)")
            finally:
                restore(loop, snap)
                repair_round("review try restore")
            return lines, None
        plain, why = _evidence_verdict(loop, sets, call.get("because"))
        note = ((f"Set by the review: {str(call.get('because'))[:200]}") if plain else
                (f"Set by the review WITHOUT tying evidence — please check: {str(call.get('because') or 'no reason given')[:200]}"))
        _applied, refused = _apply_sets(loop, sets, plain, note, log)
        repair_round("review")
        res = gate_once()
        lines = ["set " + _sets_text(sets) + " → " + ("plain, " + why if plain else "RED: " + why)]
        if refused:
            lines.append(f"    the writer refused {refused} (a guard, said out loud — not silently dropped)")
        lines += _metric_diff(m0, _metrics(loop, key_panel, panel_path))
        return lines, res
    if tool == "restore":
        sh, co, err = _parse_ref(loop, call.get("ref", ""))
        if err:
            return [f"restore: {err}"], None
        from openpyxl.utils import column_index_from_string as _ci
        m0 = _metrics(loop, key_panel, panel_path)
        back = pre_wb[sh].cell(_row_of(co), _ci(_col_of(co))).value
        why = str(call.get("why") or "")[:200]
        ok = loop.writer.write(sh, co, back if back is not None else 0.0, trusted=True, force_lock=True, flag="red",
                               note=f"Reverted by the brain: {why}. This input was moved by the run and is put back to what you had.")
        if ok:
            loop.served.pop((sh, _row_of(co)), None)
        repair_round("review restore")
        res = gate_once()
        return [f"restore {sh}!{co} → {_fmt(_num(back))} ({'written, red' if ok else 'the writer refused it'})"] \
            + _metric_diff(m0, _metrics(loop, key_panel, panel_path)), res
    if tool == "plug":
        sh, co, err = _parse_ref(loop, call.get("check", ""))
        if err:
            return [f"plug: {err}"], None
        m0 = _metrics(loop, key_panel, panel_path)
        loop.writer.plugs_allowed = True
        _plug_here(loop, sh, co, log)
        repair_round("review plug")
        res = gate_once()
        state.setdefault("plugged", []).append(f"{sh}!{co}")
        return [f"plug {sh}!{co} ({str(call.get('why') or '')[:120]}) — orange, reported"] \
            + _metric_diff(m0, _metrics(loop, key_panel, panel_path)), res
    return [f"'{tool}' is not one of the tools: show, find, try, set, restore, plug, done"], None


def _finish(loop, pre_wb, log, res, statement):
    """The closing rows the report reads, whatever the exit: the headline lines
    as they stand NOW, the negatives beyond the horizon as a watch, the count."""
    from .sensecheck import _sense_row, headline_deltas, suspicious
    writer, lines = loop.writer, loop.writer.log.setdefault("ending", [])
    earlier = {s.get("name"): s for s in writer.log.get("sense_rows", []) if isinstance(s, dict) and s.get("stage") != "ending"}
    try:
        deltas = headline_deltas(loop.wb, pre_wb, loop.spec, int(loop.ty))
        bad = {d["name"] for d in suspicious(deltas)}
        for d in deltas:
            e = earlier.get(d.get("name")) or {}
            leaf = tuple(str(e["leaf"]).split("!", 1)) if e.get("leaf") and "!" in str(e["leaf"]) else None
            if d["name"] in bad:
                _sense_row(writer, d, "red", (e.get("text") or "") + " — still out of line after the review; your ruling", leaf, "ending")
            else:
                _sense_row(writer, d, e.get("verdict") if e.get("verdict") in ("fixed", "genuine", "unusual") else "inline",
                           e.get("text") or "", leaf, "ending")
    except Exception as e:  # noqa: BLE001
        _fault(loop, f"closing sense rows not written: {e!r}")
    try:
        for w in sanity_watch(loop):
            lines.append("WATCH " + w)
            log("[review] watch: " + w)
            m = re.search(r"at ([^)]+!\S+)\)", w)
            if m:
                sh, co = m.group(1).split("!", 1)
                writer.watch(sh, co, "Sense check: " + w)
    except Exception as e:  # noqa: BLE001
        _fault(loop, f"the watch was not written: {e!r}")
    for f in loop.__dict__.get("objective_faults", []):
        if f"objective not measured: {f}" not in lines:
            lines.append(f"objective not measured: {f}")
            log(f"[review] FAULT {f}")
    if statement:
        for k, v in statement.items():
            lines.append(f"{k}: {v}")
            log(f"[review] {k}: {v}")
    return res


def run_review(loop, pre_wb, log, ask_json, gate_once, repair_round, keys_before, key_panel, panel_path,
               deadline_s=720.0, max_turns=40, notes=(), brain=True):
    """THE REVIEW LOOP. Every turn: code measures and lays out the model, the
    brain calls tools, code applies and measures and logs the turn verbatim.
    `done` is accepted only with a statement per objective. At the clock the
    terminal ladder plugs any actual-year check still off — the only decision
    code makes. -> (ok, failures, card) from the last gate."""
    writer, lines = loop.writer, loop.writer.log.setdefault("ending", [])
    t0 = time.monotonic()
    repair_round("first")
    result = gate_once()
    statement, state, answers = None, {}, []
    if ask_json is None or not brain:
        lines.append("no brain in this run: the review was not held")
        log("[review] no brain: straight to the last resort")
    else:
        for turn in range(max_turns):
            left = deadline_s - (time.monotonic() - t0)
            if left <= 0:
                lines.append("the clock ended the review; what remains is written up")
                log("[review] clock: what remains is written up")
                break
            ctx = build_context(loop, pre_wb, key_panel, panel_path, notes=notes, answers=answers)
            log(f"[review] turn {turn + 1}: context {len(ctx):,} chars, {left / 60:.1f} min left")
            try:
                reply = ask_json(MANDATE, ctx)
            except Exception as e:  # noqa: BLE001
                lines.append(f"the brain gave no answer at turn {turn + 1} ({type(e).__name__}) — what remains is written up")
                log(f"[review] turn {turn + 1}: the brain answered nothing ({e!r})")
                break
            log("[review] turn %d reply %s" % (turn + 1, json.dumps(reply, ensure_ascii=False)[:4000]))
            calls = reply.get("calls") if isinstance(reply, dict) else None
            if not isinstance(calls, list) or not calls:
                answers = ["    your last reply carried no calls — answer with a JSON list of calls, or `done` with a statement per objective"]
                continue
            answers, finished = [], False
            for call in calls:
                if not isinstance(call, dict):
                    answers.append(f"    '{str(call)[:60]}' is not a call object")
                    continue
                if str(call.get("tool") or "").lower() == "done":
                    st = call.get("objectives")
                    open_now = broken_objectives(loop, keys_before, key_panel, panel_path)
                    if not isinstance(st, dict) or not st:
                        answers.append("    done needs a statement per objective — balance, keys, rollforward: holds, or cannot be closed because ...")
                        continue
                    if open_now and len(st) < 3:
                        answers.append("    objectives still open, and your statement does not cover all three:")
                        answers += _metrics_text(_metrics(loop, key_panel, panel_path))
                        continue
                    statement = {str(k): str(v)[:300] for k, v in st.items()}
                    log(f"[review] done: {json.dumps(statement, ensure_ascii=False)[:600]}")
                    finished = True
                    break
                try:
                    out, res = _one_call(loop, pre_wb, call, key_panel, panel_path, log, repair_round, gate_once, state)
                except Exception as e:  # noqa: BLE001
                    _fault(loop, f"the call {json.dumps(call, ensure_ascii=False)[:120]} failed: {e!r}")
                    out, res = [f"    that call failed: {type(e).__name__}: {str(e)[:120]}"], None
                answers += out
                for ln in out:
                    log(f"[review]   {ln.strip()[:300]}")
                if res is not None:
                    result = res
            if finished:
                break
    open_now = broken_objectives(loop, keys_before, key_panel, panel_path)
    checks = [(o[1], o[2]) for o in open_now if o[0] == "check"]
    if checks:
        # THE ONLY DECISION CODE MAKES (owner 2026-09-15: "a balanced model with a
        # flagged plug beats an unbalanced model"): whatever was said, an actual-year
        # check still off at the end goes to the ladder, orange, reported.
        from .orchestrator import terminal_ladder
        log(f"[review] last resort: {len(checks)} actual-year check(s) still off — the model's own plug ladder, orange")
        lines.append(f"LAST RESORT: {len(checks)} actual-year check(s) went to the plug ladder")
        try:
            loop.writer.plugs_allowed = True
            terminal_ladder(loop, log)
            repair_round("review last resort")
            result = gate_once()
        except Exception as e:  # noqa: BLE001
            _fault(loop, f"the last resort failed: {e!r}")
    for o in broken_objectives(loop, keys_before, key_panel, panel_path):
        why = (statement or {}).get("balance" if o[0] in ("check", "forecast-check") else ("keys" if o[0] == "key" else "rollforward"))
        writer.flag_ref(f"{o[1]}!{o[2]}", "red", f"OPEN: {o[4]}" + (f" — the review's reading: {why}" if why else " — the review did not close it"))
        lines.append(f"OPEN {o[1]}!{o[2]}: {o[4]}")
    left_n = len(broken_objectives(loop, keys_before, key_panel, panel_path))
    lines.append(f"ended: {left_n} objective(s) still broken" if left_n else "ended: every objective holds")
    log(f"[review] {lines[-1]}")
    return _finish(loop, pre_wb, log, result if result is not None else gate_once(), statement)
