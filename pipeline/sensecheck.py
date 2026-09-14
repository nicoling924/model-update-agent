"""THE SENSE CHECK (owner 2026-09-09). The report's own mini P&L compares
the updated model with the analyst's pre-update model: FY0 is the actual
against the estimate, FY+1 onward the new forecast against the old. An
analyst reading "net profit −5.8% vs estimate, +15.7% vs the old forecast"
stops and looks for a rollover error. So does the agent:

  suspicious line  = |Δ(FY+1) − Δ(FY0)| > 10 points on a headline AMOUNT
                     (ratios are not sense-checked)
  chain            = the actual-year cells this run wrote that feed the
                     line's FY+1 cell — the agent's own red and orange
                     cells first, because a back-out or a mis-read is the
                     likeliest cause
  rolled into zero = a chain row whose forecast years were all zero before
                     the update and whose actual cell the run filled: the
                     forecast was never meant to move — the fill is taken
                     back and the row stays at zero

Two moments (owner 2026-09-09): a CHECKPOINT after the automatic fill,
before the cards (the chain cells go to the front of the queue as review
cards with the reason on them), and a FINAL PASS after the checks close
(one review card per line still suspicious if time allows; then keys and
balance are re-run and a change that breaks them is taken back; what is
left is written up, never hidden). The loop gives up with the objectives
intact.
"""
import re

from .checks import prior_column, year_columns
from .evaluator import Evaluator

SENSE_GAP = 0.10          # owner 2026-09-09: 10 points between the two changes
# the report's mini P&L lines (owner 2026-09-09: "rows in the REPORT tab mini
# P&L for now"): the P&L roles among the agent's key-row vocabulary. Cash
# flows swing by nature and balance-sheet totals are checked by the balance
# itself — neither is sense-checked here.
PL_ROLES = ("revenue", "gross profit", "operating profit", "net profit", "net profit attributable",
            "recurring net profit", "eps", "dps")


def sense_rows(wb, spec, target_year):
    """The lines the sense check watches (owner 2026-09-14: every P&L and
    cash-flow line of the report's fixed table, plus the key rows in the
    P&L roles): [{name, sheet, row}], one per cell. A row that is a spec
    key keeps the key's name."""
    from .reportpage import ROLES, resolve_rows
    keys = spec.get("key_rows") or []
    by_cell = {(k.get("sheet"), int(k.get("row"))): k.get("name") for k in keys if isinstance(k.get("row"), int)}
    out, seen = [], set()
    try:
        found, _primary = resolve_rows(wb, spec, target_year, "FY")
    except Exception:
        found = {}
    for role in ROLES:
        key, label, group = role[0], role[1], role[2]
        if group not in ("P&L", "Cash flow") or key not in found:
            continue
        sh, r, _lab = found[key]
        if (sh, r) in seen:
            continue
        seen.add((sh, r))
        out.append({"name": by_cell.get((sh, r)) or label.lower(), "sheet": sh, "row": r})
    for k in keys:
        if str(k.get("name") or "").lower() in PL_ROLES and (k.get("sheet"), int(k.get("row"))) not in seen \
                and isinstance(k.get("row"), int):
            seen.add((k["sheet"], int(k["row"])))
            out.append({"name": k.get("name"), "sheet": k["sheet"], "row": int(k["row"])})
    return out


def headline_deltas(wb, pre_wb, spec, target_year, key_rows=None):
    """[{name, sheet, row, ref0, ref1, d0, d1, old0, new0, old1, new1}] for
    every watched line (sense_rows) whose actual and first-forecast cells
    are numeric in both models. Percent-formatted ratios are skipped; a
    per-share line is an amount whatever its size."""
    from .execreport import _pre_val
    if key_rows is None:
        key_rows = sense_rows(wb, spec, target_year)
    ev = Evaluator(wb)
    out = []
    for kk in key_rows:
        sh, r, nm = kk.get("sheet"), int(kk.get("row")), kk.get("name")
        if sh not in wb.sheetnames or pre_wb is None or sh not in pre_wb.sheetnames:
            continue
        cols = year_columns(spec, sh)
        c0, c1 = cols.get(str(target_year)), cols.get(str(target_year + 1))
        if not c0 or not c1:
            continue
        if "%" in str(wb[sh][f"{c0}{r}"].number_format or ""):
            continue
        from openpyxl.utils import column_index_from_string as _ci
        vals = {}
        for tag, c in (("0", c0), ("1", c1)):
            ov = _pre_val(pre_wb, sh, r, _ci(c))
            try:
                nv = ev.cell(sh, f"{c}{r}")
            except Exception:
                nv = None
            vals[tag] = (ov, nv)
        (o0, n0), (o1, n1) = vals["0"], vals["1"]
        if not all(isinstance(x, (int, float)) for x in (o0, n0, o1, n1)):
            continue
        # a tiny base explodes a ratio — but a per-share line (DPS 0.60) is an
        # amount whatever its size (DFE live 2026-09-10: DPS −11.9% / −30.4%
        # went unreviewed)
        per_share = any(w in str(nm or "").lower() for w in ("eps", "dps", "per share"))
        if (abs(o0) < 1 or abs(o1) < 1) and not per_share:
            continue
        d0 = (n0 - o0) / abs(o0)
        d1 = (n1 - o1) / abs(o1)
        out.append({"name": nm, "sheet": sh, "row": r, "ref0": f"{sh}!{c0}{r}", "ref1": f"{sh}!{c1}{r}",
                    "d0": d0, "d1": d1, "old0": o0, "new0": n0, "old1": o1, "new1": n1})
    return out


def suspicious(deltas, gap=SENSE_GAP):
    """Lines whose forecast change is out of line with the actual's, worst first."""
    out = [d for d in deltas if abs(d["d1"] - d["d0"]) > gap]
    out.sort(key=lambda d: -abs(d["d1"] - d["d0"]))
    return out


def reason_text(d):
    return (f"SENSE CHECK '{d['name']}': actual {d['d0']*100:+.1f}% vs the analyst's estimate, "
            f"but the next year's forecast {d['d1']*100:+.1f}% vs the old forecast "
            f"({abs(d['d1']-d['d0'])*100:.0f} points apart) — an update or rollover error is likely in this line's inputs")


def _sense_row(writer, d, verdict, text, leaf, stage):
    """The report's record of one investigated line: what moved, the
    verdict, the cell the trail ended at (the page links to it)."""
    ref = None
    if isinstance(leaf, (list, tuple)) and len(leaf) >= 2:
        ref = f"{leaf[0]}!{leaf[1]}"
    writer.log.setdefault("sense_rows", []).append(
        {"name": d.get("name"), "d0": d.get("d0"), "d1": d.get("d1"), "ref1": d.get("ref1"),
         "verdict": verdict, "text": str(text or "")[:400], "leaf": ref, "stage": stage})


def chain_cells(wb, spec, target_year, d, writer):
    """The actual-year cells this run wrote that feed the line's FY+1 cell,
    the agent's own red first, then orange, then the rest.
    -> [(sheet, row, ref, colour)]"""
    from .keytie import _leaves
    seen = set()
    sh1, c1 = d["ref1"].split("!")
    _leaves(wb, sh1, c1, seen=seen)
    written = set(writer.log.get("written", []))
    flags = set(writer.log.get("flags", []))
    out = []
    for (sh, coord) in seen:
        m = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
        if not m or sh not in wb.sheetnames:
            continue
        tcol = year_columns(spec, sh).get(str(target_year))
        if m.group(1) != tcol:
            continue
        ref = f"{sh}!{coord}"
        if ref not in written:
            continue
        try:
            rgb = str(wb[sh][coord].fill.fgColor.rgb or "")[-6:]
        except Exception:
            rgb = ""
        colour = "red" if rgb == "FFC7CE" or ref in flags else "orange" if rgb == "FFC000" else "plain"
        out.append((sh, int(m.group(2)), ref, colour))
    rank = {"red": 0, "orange": 1, "plain": 2}
    out.sort(key=lambda x: (rank[x[3]], x[0], x[1]))
    return out


# (rolled_into_zero retired 2026-09-14: the zero-forecast row is the writer's
# law for the whole run — measured on the analyst's model before anything
# rolls, enforced at the rollover, at every write and at the stale flag)


def checkpoint(loop, pre_wb, log):
    """After the automatic fill, before the cards: mark the chain cells of
    every suspicious headline line as review items for the queue's front.
    -> {(sheet,row): reason}"""
    wb, spec, ty, writer = loop.wb, loop.spec, int(loop.ty), loop.writer
    deltas = headline_deltas(wb, pre_wb, spec, ty)
    sus = suspicious(deltas)
    prio = {}
    lines = writer.log.setdefault("sense_check", [])
    from .investigate import trace, judge_and_fix
    import time as _t
    _t0 = _t.monotonic()
    for d in sus:
        if _t.monotonic() - _t0 > 240:                      # the checkpoint's slice: four minutes of the hour
            lines.append("NOT INVESTIGATED (checkpoint time slice used) " + reason_text(d))
            continue
        txt = reason_text(d)
        log("[sense] " + txt)
        verdict, text, leaf = investigate_line(loop, pre_wb, d, log, rerun=None)
        lines.append(txt + " | " + text)
        _sense_row(writer, d, verdict, text, leaf, "checkpoint")
        if verdict == "red" and leaf is not None:
            # the swing factor is the agent's own figure and nothing better proved:
            # its normal card goes first in the queue, with the trail on it
            prio[(leaf[0], int(re.sub(r"[A-Z]", "", leaf[1])))] = (text, 3e9)
    if not sus:
        log(f"[sense] checkpoint: {len(deltas)} headline lines, none out of line")
    loop.sense_priority = prio
    return prio


def final_pass(loop, pre_wb, log, client, answerer, deadline_s, rerun):
    """After the checks close: one review card per line still suspicious
    (time allowing), then keys and balance again; a change that breaks
    them is taken back. Unresolved lines are written up. -> n written"""
    import time
    from .workqueue import WorkItem, run_queue
    wb, spec, ty, writer = loop.wb, loop.spec, int(loop.ty), loop.writer
    deltas = headline_deltas(wb, pre_wb, spec, ty)
    sus = suspicious(deltas)
    lines = writer.log.setdefault("sense_check", [])
    if not sus:
        lines.append(f"Final sense check: {len(deltas)} headline lines, none out of line.")
        log(f"[sense] final: none of {len(deltas)} lines out of line")
        return 0
    if deadline_s < 90:
        for d in sus:
            cells = chain_cells(wb, spec, ty, d, writer)
            lines.append("UNRESOLVED (no time left) " + reason_text(d) + f"; look at: {', '.join(c[2] for c in cells[:8])}")
        log(f"[sense] final: {len(sus)} line(s) still out of line, no time left — written up")
        return 0
    mark = len(writer.log.get("writes_all", []))
    t0 = time.monotonic()
    # the objectives before the review: a check already open is not the
    # review's doing (DFE live 2026-09-09: three good review writes were
    # taken back because an 11-unit gap elsewhere had the gate refusing)
    try:
        fails_before = {s for s, _r, _v in loop._failing_target_checks()}
    except Exception:
        fails_before = set()
    from .investigate import trace, judge_and_fix
    for d in sus:
        if time.monotonic() - t0 > max(30.0, deadline_s - 60):
            lines.append("UNRESOLVED (no time left) " + reason_text(d))
            continue
        verdict, text, _leaf = investigate_line(loop, pre_wb, d, log, rerun=rerun)
        lines.append(("RESOLVED " if verdict == "fixed" else "") + reason_text(d) + " | " + text)
        _sense_row(writer, d, verdict, text, _leaf, "final")
    changed = writer.log.get("writes_all", [])[mark:]
    # cells whose content actually differs from before the pass (a write
    # the investigator itself reverted is not a change)
    first_old, last_new = {}, {}
    for sh, coord, old, new in changed:
        first_old.setdefault((sh, coord), old)
        last_new[(sh, coord)] = new
    changed = [(sh, coord, first_old[(sh, coord)], last_new[(sh, coord)]) for (sh, coord) in last_new
               if last_new[(sh, coord)] != first_old[(sh, coord)]]
    n = len(changed)
    ok = rerun()
    try:
        fails_after = {s for s, _r, _v in loop._failing_target_checks()}
    except Exception:
        fails_after = set()
    # THE REVIEW MUST NOT MAKE IT WORSE (CLP live 2026-09-09: a review write
    # sent next year's revenue to −95,225,646% while the balance still
    # closed). The review is judged by its own measure too: no headline
    # line's gap may widen and no new line may go out of line.
    gaps_before = {d["name"]: abs(d["d1"] - d["d0"]) for d in deltas}
    gaps_after = {d["name"]: abs(d["d1"] - d["d0"]) for d in headline_deltas(wb, pre_wb, spec, ty)}
    worse = [nm for nm, g in gaps_after.items()
             if g > gaps_before.get(nm, 0.0) + 0.01 and g > SENSE_GAP]
    if changed and ((fails_after - fails_before) or worse):
        # the review OPENED a check or WIDENED a gap: take every review write back, re-run
        journal = writer.log.get("style_journal", [])[mark:]
        for sh, coord, old, _new in reversed(changed):
            style = next((j for j in journal if (j[0], j[1]) == (sh, coord)), (sh, coord, "", None, False))
            writer.take_back(sh, coord, old, style)
        log(f"[sense] final: {n} review write(s) taken back — "
            + (f"they opened {sorted(fails_after - fails_before)[:3]}" if (fails_after - fails_before) else f"they widened {worse[:3]}"))
        rerun()
        n = 0
    deltas2 = headline_deltas(wb, pre_wb, spec, ty)
    still = suspicious(deltas2)
    for d in sus:
        now = next((x for x in still if x["name"] == d["name"]), None)
        if now is not None:
            lines.append("UNRESOLVED " + reason_text(now))
            log("[sense] " + lines[-1])
    log(f"[sense] final: {len(sus)} line(s) reviewed, {len(sus) - len(still)} resolved, {len(still)} written up "
        f"({time.monotonic() - t0:,.0f}s)")
    return n


def investigate_line(loop, pre_wb, d, log, rerun=None):
    """One suspicious headline line, the analyst's way: trace the swing to
    its factor, judge it, fix it if a better answer proves. -> (verdict, text)"""
    from .investigate import trace, judge_and_fix
    wb, spec, ty = loop.wb, loop.spec, int(loop.ty)
    sh1, c1 = d["ref1"].split("!")

    def gap_of():
        dd = next((x for x in headline_deltas(wb, pre_wb, spec, ty) if x["name"] == d["name"]), None)
        return abs(dd["d1"] - dd["d0"]) if dd else 0.0
    texts, verdict, last_leaf = [], "spread", None
    seen_leaves = set()
    for _round in range(3):                     # after a fix, the next factor — the analyst presses in again
        trail, leaf = trace(wb, pre_wb, sh1, c1)
        last_leaf = leaf or last_leaf
        path = " → ".join(t[2] or t[1] for t in trail)
        if leaf is None or leaf in seen_leaves:
            texts.append(f"'{d['name']}': the swing is spread across several inputs" + (f" ({path})" if path else "") + " — no single factor")
            verdict = "spread" if not texts[:-1] else verdict
            break
        seen_leaves.add(leaf)
        verdict, text = judge_and_fix(loop, pre_wb, d, leaf, trail, log, gap_of, rerun=rerun)
        log(f"[sense] {verdict.upper()}: {text}")
        texts.append(text)
        if verdict != "fixed" or gap_of() <= SENSE_GAP:
            break
    return verdict, " || ".join(texts), last_leaf
