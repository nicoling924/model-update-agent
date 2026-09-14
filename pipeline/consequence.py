"""THE CONSEQUENCE CARD (owner 2026-09-15: "if I move this number, will it
change my key numbers? if so how should I solve it? how do I make sure the
model meets the balancing requirement — these should all be thought by the
AI"). Goal-based, not scripted: code measures the objectives — the balance
checks in every year, the keys against the print — and when one is broken
it puts the consequence in front of the brain: what is off, which inputs
the run moved into it (the swing census, own flags first, each with its
evidence), and the ways to resolve it — take a mover back to what the
analyst had, absorb the residual in a mover as a traceable back-out, plug
the model's own residual row (the last resort), or leave it open as a
question for the analyst with the gap named. The brain picks; code applies
the pick through the writer's laws, re-measures, and takes a pick back that
made things worse. This replaces the bulk take-back of every serve and the
automatic plug ladder as the deciders; they remain the executors of a pick.
"""
import re
import time

from .checks import forecast_columns, prior_column, year_columns
from .evaluator import Evaluator


def broken_objectives(loop, keys_before, key_panel, panel_path):
    """-> [(kind, sheet, coord, amount, text)] largest first.
    kind: check (actual year) | forecast-check | key (rule 2 / off the print)"""
    wb, spec, ty = loop.wb, loop.spec, int(loop.ty)
    out = []
    ev = Evaluator(wb)
    for c in (spec.get("check_rows") or []):
        sheet, row = c.get("sheet"), int(c.get("row"))
        if sheet not in wb.sheetnames:
            continue
        expect = float(c.get("expect", 0))
        tcol = year_columns(spec, sheet).get(str(ty))
        cols = [(tcol, "check")] if tcol else []
        cols += [(fc, "forecast-check") for fc in (forecast_columns(spec, sheet, ty) or [])]
        for col, kind in cols:
            try:
                v = ev.cell(sheet, f"{col}{row}")
            except Exception:
                continue
            if isinstance(v, (int, float)) and abs(v - expect) > 1.0:
                out.append((kind, sheet, f"{col}{row}", float(v - expect),
                            f"balance check {sheet}!{col}{row} computes {v:,.1f} (should be {expect:,.0f})"))
    try:
        from .keytie import key_violations, key_state
        for nm, ref, then, now in key_violations(wb, spec, ty, loop.ledger, panel_path, keys_before, panel=key_panel):
            sh, co = ref.split("!", 1)
            amt = (now if isinstance(now, (int, float)) else 0.0) - then
            out.append(("key", sh, co, float(amt), f"key '{nm}' at {ref} was proven-printed {then:,.1f}, now {now if now is None else f'{now:,.1f}'} — printed nowhere"))
        for nm, got, want, ok in key_state(wb, spec, ty, panel_path, panel=key_panel):
            if ok:
                continue
            kk = next((k for k in (spec.get("key_rows") or []) if k.get("name") == nm), None)
            if not kk:
                continue
            tc = year_columns(spec, kk.get("sheet")).get(str(ty))
            if not tc:
                continue
            ref = f"{kk['sheet']}!{tc}{int(kk['row'])}"
            if any(o[1] == kk["sheet"] and o[2] == f"{tc}{int(kk['row'])}" for o in out):
                continue
            out.append(("key", kk["sheet"], f"{tc}{int(kk['row'])}", float(got - want), f"key '{nm}' at {ref} computes {got:,.1f} vs printed {want:,.1f}"))
    except Exception:
        pass
    out.sort(key=lambda o: -abs(o[3]))
    return out


def _colour(wb, writer, sheet, coord):
    ref = f"{sheet}!{coord}"
    try:
        rgb = str(wb[sheet][coord].fill.fgColor.rgb or "")[-6:]
    except Exception:
        rgb = ""
    return "red" if rgb == "FFC7CE" or ref in writer.log.get("flags", []) else "orange" if rgb == "FFC000" else "blue" if rgb == "BDD7EE" else "plain"


def _evidence(loop, sheet, coord):
    r = int(re.sub(r"[A-Z]", "", coord))
    e = (loop.served or {}).get((sheet, r))
    if isinstance(e, dict):
        return f"served from '{str(e.get('line') or '')[:36]}' p{e.get('page')} (conf {e.get('conf')})"
    note = None
    try:
        c = loop.wb[sheet][coord].comment
        note = c.text if c else None
    except Exception:
        pass
    return (str(note)[:60] if note else "no evidence recorded")


def build_card(loop, pre_wb, obj, movers, named):
    kind, sheet, coord, amount, text = obj
    wb, spec, ty = loop.wb, loop.spec, int(loop.ty)
    ev = Evaluator(wb)
    lines = [f"CARD CONSEQUENCE {sheet}!{coord}", f"  OBJECTIVE BROKEN: {text} — off by {amount:+,.1f}"]
    if named:
        lines.append("  the gap equals a printed figure not yet in the model: " + "; ".join(f"{v:,.0f} = '{lab}' ({where})" for v, lab, where in named))
    lines.append("  the inputs the run moved into this line, by their share of the move (your own flags first):")
    options = {}
    for i, ((sh, c), share) in enumerate(movers):
        r = int(re.sub(r"[A-Z]", "", c))
        label = str(wb[sh].cell(r, 1).value or "")[:30]
        try:
            now = ev.cell(sh, c)
        except Exception:
            now = None
        from .execreport import _pre_val
        from openpyxl.utils import column_index_from_string as _ci
        pre = _pre_val(pre_wb, sh, r, _ci(re.sub(r"\d", "", c)))
        col = _colour(wb, loop.writer, sh, c)
        lines.append(f"    [{i + 1}] {sh}!{c} '{label}': now {now if now is None else f'{now:,.2f}'} (was {pre if pre is None else f'{pre:,.2f}'}), "
                     f"{col}, {_evidence(loop, sh, c)}, carries {abs(share) * 100:.0f}% of the move")
        options[f"revert:{i + 1}"] = f"put {sh}!{c} back to what the analyst had ({pre if pre is None else f'{pre:,.2f}'}) — red, taken back by your judgment"
        options[f"backout:{i + 1}"] = f"absorb the residual in {sh}!{c} as a traceable formula — orange"
    options["plug"] = "plug the model's own residual row — the last resort, orange, reported"
    options["question"] = "leave it open, red: a definition question for the analyst (say what)"
    lines.append("  the ways to resolve it:")
    for k, v in options.items():
        lines.append(f"    {k}: {v}")
    lines.append("  Think like the analyst: which input is wrong, or is the model's definition different from the print? "
                 "A plug is only for a gap nothing explains. answers: " + ", ".join(options))
    return "\n".join(lines), options


def resolve_objectives(loop, pre_wb, log, ask, gate_once, repair_round, check_mass, keys_before, key_panel, panel_path,
                       deadline_s=600.0, max_rounds=10):
    """The goal-based ending. -> (ok, failures, card) from the last gate_once, or None when no brain answered."""
    from .investigate import swing_leaves
    from .keytie import name_gap
    wb, spec, ty, writer = loop.wb, loop.spec, int(loop.ty), loop.writer
    t0 = time.monotonic()
    asked = set()
    result = None
    answered_any = False
    for _round in range(max_rounds):
        if time.monotonic() - t0 > deadline_s:
            log("[consequence] clock: the objectives that remain are written up")
            break
        objs = [o for o in broken_objectives(loop, keys_before, key_panel, panel_path) if (o[1], o[2]) not in asked]
        if not objs:
            break
        obj = objs[0]
        kind, sheet, coord, amount, text = obj
        flagged = {tuple(ref.split("!")) for ref in writer.log.get("flags", [])}
        census = swing_leaves(wb, pre_wb, sheet, coord, flagged=flagged, budget_s=60)
        movers = census[:6]
        named, _rest = name_gap(loop.ledger, amount, served=loop.served) if kind == "key" else ([], abs(amount))
        card, options = build_card(loop, pre_wb, obj, movers, named)
        log(f"[queue] card CONSEQUENCE {sheet}!{coord}: " + " | ".join(ln.strip() for ln in card.splitlines()[1:4 + len(movers)])[:900])
        pick = ask(card, options, "__auto__")
        if pick not in options:
            if not answered_any:
                return None                       # no brain here: the deterministic floor path decides
            asked.add((sheet, coord))
            continue
        answered_any = True
        log(f"[queue] CONSEQUENCE {sheet}!{coord} -> {pick}")
        mass0 = check_mass()
        mark = len(writer.log.get("writes_all", []))
        applied = True
        if pick == "question":
            writer.flag_ref(f"{sheet}!{coord}", "red", f"OPEN, by the brain's judgment: {text} — a question for the analyst"
                            + ("; the gap equals " + "; ".join(f"{v:,.0f} '{lab}' ({where})" for v, lab, where in named) if named else ""))
            asked.add((sheet, coord))
            continue
        if pick == "plug":
            from .orchestrator import terminal_ladder
            terminal_ladder(loop, log)
        else:
            i = int(pick.split(":")[1]) - 1
            (sh, c), _share = movers[i]
            r = int(re.sub(r"[A-Z]", "", c))
            pcol = prior_column(spec, sh, ty)
            if pick.startswith("revert:"):
                from .execreport import _pre_val
                from openpyxl.utils import column_index_from_string as _ci
                pre_content = pre_wb[sh].cell(r, _ci(re.sub(r"\d", "", c))).value
                back = pre_content if pre_content is not None else 0.0
                applied = writer.write(sh, c, back, prior_coord=f"{pcol}{r}" if pcol else None, trusted=True, force_lock=True, flag="red",
                                       note=f"Taken back by the brain's judgment: {text}; this input was moved by the run and is put back to what you had. Please check.")
                if applied:
                    loop.served.pop((sh, r), None)
            else:
                try:
                    cur = Evaluator(wb).cell(sh, c)
                except Exception:
                    cur = None
                held = wb[sh][c].value
                body = held[1:] if isinstance(held, str) and held.startswith("=") else (f"{cur:g}" if isinstance(cur, (int, float)) else None)
                if body is None:
                    applied = False
                else:
                    applied = writer.write(sh, c, f"=({body})-({amount:.6g})", prior_coord=f"{pcol}{r}" if pcol else None, trusted=True, flag="orange",
                                           note=f"Backed out by the brain's judgment so {text} closes: absorbed {amount:+,.1f} here. True up when disclosed.")
        if not applied:
            log(f"[consequence] the pick {pick} could not be written (the writer's law refused) — asked again without it")
            asked.add((sheet, coord))
            continue
        repair_round("consequence")
        result = gate_once()
        mass1 = check_mass()
        if mass1 > mass0 + 1.0:
            journal = writer.log.get("style_journal", [])[mark:]
            for sh_w, co_w, old_w, _new in reversed(list(writer.log.get("writes_all", []))[mark:]):
                style = next((j for j in journal if (j[0], j[1]) == (sh_w, co_w)), (sh_w, co_w, "", None, False))
                writer.take_back(sh_w, co_w, old_w, style)
            repair_round("consequence take-back")
            result = gate_once()
            log(f"[consequence] {pick} made the objectives worse ({mass0:,.0f} -> {mass1:,.0f}); taken back")
            asked.add((sheet, coord))
        else:
            log(f"[consequence] {sheet}!{coord}: {pick} -> objectives mass {mass0:,.0f} -> {mass1:,.0f}")
    return result


def run_ending(loop, pre_wb, log, ask, gate_once, repair_round, check_mass, keys_before, key_panel, panel_path,
               deadline_s, hold_zero=None, brain=True, max_rounds=14):
    """THE ENDING (owner 2026-09-15: "a loop at the end that identifies the
    issues, fixes them, makes sure the key numbers and the balance sheet
    balance, and if there is another problem fixes it again — and stops
    itself"). One loop, nothing stacked:
      measure the objectives — the balance in every year, the keys against
      the print, the headline lines out of line on the rollover — take the
      biggest break, put it to the brain with the movers and the ways to
      resolve it, apply the pick through the writer's laws, re-run the
      repairs the model itself defines, measure again. EVERY round is
      verified the same way: a new failure or a worse total is taken back.
    Stops when the objectives hold, when every remaining break has been
    judged (a question for the analyst, or a pick that did not help), or at
    the clock. With no brain (a floor) the model's own executors act once
    per break, matched to its kind. -> (ok, failures, card) from the last gate."""
    from .investigate import swing_leaves
    from .keytie import name_gap
    from .sensecheck import headline_deltas, suspicious, investigate_line, reason_text, _sense_row
    wb, spec, ty, writer = loop.wb, loop.spec, int(loop.ty), loop.writer
    t0 = time.monotonic()
    asked = set()
    lines = writer.log.setdefault("ending", [])
    loop.census_budget_s = 90 if (brain and ask is not None) else 10
    if hold_zero:
        hold_zero()
    repair_round("first")
    result = gate_once()
    if result[0] and not suspicious(headline_deltas(wb, pre_wb, spec, ty)):
        lines.append("objectives held at the first measure")
        return result
    order = {"check": 0, "key": 1, "forecast-check": 2, "sense": 3}

    def _breaks():
        raw = broken_objectives(loop, keys_before, key_panel, panel_path)
        out, seen_rows = [], set()
        for o in raw:
            kind, sheet, coord, amount, text = o
            if kind == "forecast-check":
                row = re.sub(r"[A-Z]", "", coord)
                if (sheet, row) in seen_rows:
                    continue                # the forecast years of one check row are ONE objective
                seen_rows.add((sheet, row))
            out.append((order[kind], abs(amount), o))
        for d in suspicious(headline_deltas(wb, pre_wb, spec, ty)):
            sh1, c1 = d["ref1"].split("!")
            out.append((order["sense"], abs(d["d1"] - d["d0"]), ("sense", sh1, c1, d["d1"] - d["d0"], reason_text(d), d)))
        out.sort(key=lambda x: (x[0], -x[1]))
        return [o for _p, _a, o in out]

    def _fails(res):
        """The broken objectives as a set — the same measure the loop works to, not the gate's strings."""
        return {(o[1], o[2]) for o in broken_objectives(loop, keys_before, key_panel, panel_path)}

    def _gaps():
        return {d["name"]: abs(d["d1"] - d["d0"]) for d in headline_deltas(wb, pre_wb, spec, ty)}

    def _amount_of(sheet, coord):
        for o in broken_objectives(loop, keys_before, key_panel, panel_path):
            if (o[1], o[2]) == (sheet, coord):
                return abs(o[3])
        return 0.0

    def _take_back(mark, why):
        journal = writer.log.get("style_journal", [])[mark:]
        for sh_w, co_w, old_w, _new in reversed(list(writer.log.get("writes_all", []))[mark:]):
            style = next((j for j in journal if (j[0], j[1]) == (sh_w, co_w)), (sh_w, co_w, "", None, False))
            writer.take_back(sh_w, co_w, old_w, style)
        repair_round("ending take-back")
        log(f"[ending] {why}; taken back")
        return gate_once()

    for rnd in range(max_rounds):
        if time.monotonic() - t0 > deadline_s:
            lines.append("the clock ended the loop; what remains is written up")
            log("[ending] clock: the objectives that remain are written up")
            break
        breaks = [b for b in _breaks() if (b[1], b[2]) not in asked]
        if not breaks:
            break
        obj = breaks[0]
        kind, sheet, coord, amount = obj[0], obj[1], obj[2], obj[3]
        mass0 = check_mass()
        fails0 = _fails(result)
        gaps0 = _gaps()
        mark = len(writer.log.get("writes_all", []))
        log(f"[ending] round {rnd + 1}: {kind} {sheet}!{coord} off {amount:+,.2f} (objectives mass {mass0:,.0f}; {len(breaks)} break(s) open)")
        pick = "__auto__"
        if kind == "sense":
            d = obj[5]
            def _rerun():
                repair_round("ending")
                return gate_once()[0]
            verdict, text, leaf = investigate_line(loop, pre_wb, d, log, rerun=_rerun)
            _sense_row(writer, d, verdict, text, leaf, "ending")
            lines.append(("RESOLVED " if verdict == "fixed" else "") + reason_text(d) + " | " + text)
            pick = verdict
        else:
            options, movers, named = {}, [], []
            if brain and ask is not None:
                flagged = {tuple(ref.split("!")) for ref in writer.log.get("flags", [])}
                movers = swing_leaves(wb, pre_wb, sheet, coord, flagged=flagged, budget_s=60)[:6]
                named, _rest = name_gap(loop.ledger, amount, served=loop.served) if kind == "key" else ([], abs(amount))
                card, options = build_card(loop, pre_wb, obj[:5], movers, named)
                log(f"[queue] card CONSEQUENCE {sheet}!{coord}: " + " | ".join(ln.strip() for ln in card.splitlines()[1:4 + len(movers)])[:900])
                pick = ask(card, options, "__auto__")
            if pick not in options:
                # no brain, or no answer: the model's own executor for this kind of break, once
                pick = "__auto__"
                if kind == "check":
                    from .orchestrator import terminal_ladder
                    terminal_ladder(loop, log)
                # a forecast-year check or a key: the repairs (forecast plugs, the key tie) re-solve below
            elif pick == "question":
                log(f"[queue] CONSEQUENCE {sheet}!{coord} -> question")
                writer.flag_ref(f"{sheet}!{coord}", "red", f"OPEN, by the brain's judgment: {obj[4]} — a question for the analyst"
                                + ("; the gap equals " + "; ".join(f"{v:,.0f} '{lab}' ({where})" for v, lab, where in named) if named else ""))
                lines.append(f"QUESTION {sheet}!{coord}: {obj[4]}")
                asked.add((sheet, coord))
                continue
            elif pick == "plug":
                log(f"[queue] CONSEQUENCE {sheet}!{coord} -> plug")
                from .orchestrator import terminal_ladder
                terminal_ladder(loop, log)
            else:
                log(f"[queue] CONSEQUENCE {sheet}!{coord} -> {pick}")
                i = int(pick.split(":")[1]) - 1
                (sh, c), _share = movers[i]
                r = int(re.sub(r"[A-Z]", "", c))
                pcol = prior_column(spec, sh, ty)
                applied = True
                if pick.startswith("revert:"):
                    from openpyxl.utils import column_index_from_string as _ci
                    pre_content = pre_wb[sh].cell(r, _ci(re.sub(r"\d", "", c))).value
                    back = pre_content if pre_content is not None else 0.0
                    applied = writer.write(sh, c, back, prior_coord=f"{pcol}{r}" if pcol else None, trusted=True, force_lock=True, flag="red",
                                           note=f"Taken back by the brain's judgment: {obj[4]}; this input was moved by the run and is put back to what you had. Please check.")
                    if applied:
                        loop.served.pop((sh, r), None)
                else:
                    try:
                        cur = Evaluator(wb).cell(sh, c)
                    except Exception:
                        cur = None
                    held = wb[sh][c].value
                    body = held[1:] if isinstance(held, str) and held.startswith("=") else (f"{cur:g}" if isinstance(cur, (int, float)) else None)
                    applied = bool(body) and writer.write(sh, c, f"=({body})-({amount:.6g})", prior_coord=f"{pcol}{r}" if pcol else None, trusted=True, flag="orange",
                                                          note=f"Backed out by the brain's judgment so {obj[4]} closes: absorbed {amount:+,.1f} here. True up when disclosed.")
                if not applied:
                    log(f"[ending] the pick {pick} could not be written (the writer's law refused)")
                    asked.add((sheet, coord))
                    continue
        # the same verification for every kind of pick
        if hold_zero:
            hold_zero()
        repair_round("ending")
        result = gate_once()
        mass1 = check_mass()
        new_fails = _fails(result) - fails0
        gaps1 = _gaps()
        from .sensecheck import SENSE_GAP
        # the objectives in the owner's order: balance first, keys second, the
        # swing lines third — a widened swing line vetoes a sense pick, never
        # a fix that closes the balance or a key (the loop returns to the line)
        widened = [nm for nm, g in gaps1.items() if g > gaps0.get(nm, 0.0) + SENSE_GAP and g > SENSE_GAP] if kind == "sense" else []
        # a fix that did not fix: a pick aimed at a check or key must close most of it
        half_done = kind in ("check", "forecast-check", "key") and pick != "__auto__" and _amount_of(sheet, coord) > 0.5 * abs(amount)
        if mass1 > mass0 + 1.0 or new_fails or widened or half_done:
            result = _take_back(mark, f"{kind} {sheet}!{coord}: {pick} "
                                + ("did not close the break" if half_done and not (new_fails or widened or mass1 > mass0 + 1.0)
                                   else f"made the objectives worse ({mass0:,.0f} -> {mass1:,.0f}")
                                + (f"; opened {sorted(new_fails)[:2]}" if new_fails else "")
                                + (f"; widened {widened[:2]}" if widened else "") + ")")
            asked.add((sheet, coord))
        else:
            log(f"[ending] {sheet}!{coord}: {pick} -> objectives mass {mass0:,.0f} -> {mass1:,.0f}")
            if mass1 >= mass0 - 1.0 and kind != "sense":
                asked.add((sheet, coord))
            elif kind == "sense":
                asked.add((sheet, coord))
    left = _breaks()
    lines.append(f"ended: {len(left)} objective(s) still broken" if left else "ended: every objective holds")
    log(f"[ending] {lines[-1]}")
    return result if result is not None else gate_once()
