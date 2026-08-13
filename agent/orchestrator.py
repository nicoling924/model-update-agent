"""The objective-driven orchestrator: the LLM holds the goals and chooses the
next action; code executes it with guardrails and reports back.

This replaces the fixed convergence order with an observe-decide-act loop:
    state (scorecard + history) -> LLM picks ONE tool call -> code validates and
    executes -> result appended to history -> repeat.

Design constraints that make this safe on a weak model:
- The goal state is EXTERNAL (the scorecard is recomputed and shown each turn) —
  the model never needs to hold objectives in memory across turns.
- Every action is a small multiple-choice-style decision, the mode weak models
  are measurably reliable at.
- Code owns all guardrails: eligible-input checks, magnitude guards, mandatory
  flags, decision budget, wall-clock deadline. A bad decision wastes a turn,
  never corrupts the workbook.
"""
import json
import re
import time

from . import lookup as lookup_mod
from . import objectives, targeted
from .evaluator import Evaluator

MAX_DECISIONS = 25


def _fmt_scorecard(card):
    L = []
    t0_bad = [(c, y, g) for c, y, g in card["tier0"] if g is None or abs(g) > 1.0]
    L.append("OBJECTIVE 1 (balance): " + ("SATISFIED" if not t0_bad else
             "VIOLATED at " + "; ".join(f"{c} ({y}): gap {g}" for c, y, g in t0_bad[:6])))
    for e in card["tier1"]:
        L.append(f"OBJECTIVE 2 key[{e['kind']}] @ {e['sheet']}!{e['coord']}: {e['status']}"
                 + (f" model={e['model']:,.1f}" if isinstance(e['model'], (int, float)) else "")
                 + (f" disclosed={e['disclosed']:,.1f} ({e['proof']}, p{e['pages']})"
                    if isinstance(e['disclosed'], (int, float)) else " — no disclosed value proven"))
    return "\n".join(L)


def run(client, system, prompt, wb, spec, staging, cfg, writer, pre_wb,
        target_year, last_actual, keymap, proven, flags, backouts,
        eligible_inputs, disclosures, t0, deadline, log_print,
        bootstrap_log=None, request_review=None):
    """Returns (final_card, decisions_log). Mutates wb via writer.

    bootstrap_log: deterministic actions already taken this run — seeded into the
    loop's history so the agent owns them as its own first moves.
    request_review: callable running the blind reviewer once; exposed as a tool."""
    spec["_target_year"] = target_year
    history = [f"[bootstrap] {ln}" for ln in (bootstrap_log or [])][-12:]
    decisions = []
    raw_cache = lookup_mod.raw_lines(disclosures)
    tried = set()

    def _card():
        return objectives.scorecard(wb, spec, keymap, proven, cfg, t0)

    pages_served = set()

    def t_read_pages(args):
        pages = [int(p) for p in (args.get("pages") or [])][:12]
        if not pages:
            return "ERROR: no pages given"
        if set(pages) <= pages_served:
            return ("ALREADY READ these pages this run — the text does not change; "
                    "act on what you saw, or read DIFFERENT pages")
        pages_served.update(pages)
        lines = [f"p{pn}: {ln.strip()}" for pn, _s, ln in raw_cache
                 if pn in pages and re.search(r"\d", ln)][:80]
        return "PAGE TEXT (numeric lines):\n" + "\n".join(lines) if lines \
            else "no numeric lines on those pages"

    def t_find_line(args):
        name = lookup_mod.norm(str(args.get("name", "")))
        if not name:
            return "ERROR: no name"
        hits = [f"p{pn} [{sec}]: {ln.strip()}" for pn, sec, ln in raw_cache
                if name in lookup_mod.norm(ln)][:25]
        return "\n".join(hits) if hits else f"no line containing '{args.get('name')}'"

    def t_prove_key(args):
        kind = args.get("kind")
        if kind not in keymap:
            return f"ERROR: unknown/unlocated kind {kind}"
        sub = {kind: keymap[kind]}
        lg = []
        res = objectives.prove(sub, staging, raw_cache, pre_wb, spec,
                               last_actual, cfg, lg)
        proven[kind] = res.get(kind, proven.get(kind))
        p = proven[kind]
        return (f"{kind}: {p['status']}, value={p.get('value')}, "
                f"sources={p.get('sources')}, pages={p.get('pages')}")

    def t_plug_key(args):
        kind = args.get("kind")
        card = _card()
        e = next((x for x in card["tier1"] if x["kind"] == kind), None)
        if not e:
            return f"ERROR: unknown kind {kind}"
        if e["status"] != "MISMATCH":
            return f"nothing to plug: {kind} is {e['status']}"
        n_before = len(writer.log["written"])
        spec_t1 = dict(spec)
        spec_t1["check_rows"] = []  # key plug only — balance repair is its own tool
        objectives.converge(wb, spec_t1, staging, cfg, writer, pre_wb, None,
                            target_year, last_actual, {kind: keymap[kind]},
                            {kind: proven[kind]}, flags, backouts, t0,
                            eligible_inputs, deadline)
        made = len(writer.log["written"]) - n_before
        e2 = next((x for x in _card()["tier1"] if x["kind"] == kind), None)
        if made == 0:
            return (f"{kind}: refused — either inside the definition band (model "
                    "and disclosed close: scope difference, flag stands) or no "
                    "legal plug site. Do NOT retry; move to the next objective.")
        return f"{kind}: {made} write(s); now {e2['status'] if e2 else '?'}"

    def t_set_input(args):
        ref = str(args.get("cell", ""))
        m = re.match(r"^\s*'?([^'!]+)'?!([A-Z]{1,3})(\d+)\s*$", ref)
        if not m:
            return "ERROR: cell must be Sheet!COLROW"
        sheet, col, row = m.group(1), m.group(2), int(m.group(3))
        coord = f"{col}{row}"
        if (sheet, coord) not in eligible_inputs:
            return f"REFUSED: {ref} is not an input cell (designed formulas are protected)"
        try:
            val = float(args.get("value"))
        except (TypeError, ValueError):
            return "ERROR: numeric value required"
        why = str(args.get("why", ""))
        if not re.search(r"p\.?\s*\d+|page\s*\d+", why, re.I):
            return "REFUSED: cite the disclosure page in why"
        pv = None
        try:
            pv = Evaluator(pre_wb).cell(sheet, f"{spec['year_axis'][sheet]['columns'][last_actual]}{row}")
        except Exception:
            pass
        if isinstance(pv, (int, float)) and abs(pv) > 100 and val != 0:
            r = abs(val) / abs(pv)
            if r > 20 or r < 0.05:
                return f"REFUSED: magnitude guard (prior {pv:,.1f} vs {val:,.1f})"
        writer.write(sheet, coord, val, note=f"ORCHESTRATOR: {why[:180]}", flag="red")
        flags.append((sheet, coord, f"orchestrator set: {why[:80]}"))
        return f"written {ref} = {val} (red-flagged)"

    def t_diagnose_balance(args):
        card = _card()
        gap_e = next(((c, y, g) for c, y, g in card["tier0"]
                      if y == target_year and g is not None and abs(g) > 1.0), None)
        if not gap_e:
            return "balance already satisfied for the target year"
        chk_ref, _y, gap = gap_e
        chk_sheet, chk_coord = chk_ref.split("!")
        staged_vals = {round(abs(it["value"]), 1) for it in staging.get("items", [])
                       if isinstance(it.get("value"), (int, float))}
        out = []
        flagged_inputs = sorted({(fs, fc) for fs, fc, _n in flags
                                 if (fs, fc) in eligible_inputs})[:60]
        for ps, pco in flagged_inputs:
            coef, base_in = objectives._sensitivity(wb, chk_sheet, chk_coord, ps, pco)
            if not coef or abs(coef) < 0.01 or abs(coef) > 100:
                continue
            adj = -gap / coef
            new_v = (base_in or 0) + adj
            corr = any(abs(abs(new_v) - sv) <= 1.0 for sv in staged_vals)
            out.append(f"{ps}!{pco}: adjust {adj:+,.1f} -> {new_v:,.1f} "
                       f"{'[CORROBORATED in disclosure]' if corr else '[not corroborated]'}")
        return f"gap {gap:+,.1f} at {chk_ref}\n" + ("\n".join(out[:15]) or
                                                    "no candidate single-cell repairs")

    def t_apply_repair(args):
        ref = str(args.get("cell", ""))
        m = re.match(r"^\s*'?([^'!]+)'?!([A-Z]{1,3})(\d+)\s*$", ref)
        if not m:
            return "ERROR: cell must be Sheet!COLROW"
        sheet, coord = m.group(1), f"{m.group(2)}{m.group(3)}"
        if (sheet, coord) not in eligible_inputs:
            return f"REFUSED: {ref} is not an input cell"
        card = _card()
        gap_e = next(((c, y, g) for c, y, g in card["tier0"]
                      if y == target_year and g is not None and abs(g) > 1.0), None)
        if not gap_e:
            return "no balance gap to repair"
        chk_sheet, chk_coord = gap_e[0].split("!")
        gap = gap_e[2]
        coef, base_in = objectives._sensitivity(wb, chk_sheet, chk_coord, sheet, coord)
        if not coef or abs(coef) < 0.01 or abs(coef) > 100:
            return f"REFUSED: {ref} does not feed the balance check"
        adj = -gap / coef
        new_v = (base_in or 0) + adj
        staged_vals = {round(abs(it["value"]), 1) for it in staging.get("items", [])
                       if isinstance(it.get("value"), (int, float))}
        if not any(abs(abs(new_v) - sv) <= 1.0 for sv in staged_vals):
            return (f"REFUSED: corrected value {new_v:,.1f} is not corroborated by the "
                    "disclosure — a repair that merely forces the check is forbidden")
        old = wb[sheet][coord].value
        writer.write(sheet, coord, objectives._plug_formula(old, adj),
                     note=f"ORCHESTRATOR balance repair: {str(args.get('why', ''))[:150]}",
                     flag="red")
        flags.append((sheet, coord, "orchestrator balance repair — verify"))
        return f"repaired {ref} by {adj:+,.1f}; re-score to confirm"

    def t_trace_cell(args):
        """The Fable move: decompose a cell — formula, each precedent's current
        value side-by-side with its prior-year value, so the odd one out shows."""
        ref = str(args.get("cell", ""))
        m = re.match(r"^\s*'?([^'!]+)'?!([A-Z]{1,3})(\d+)\s*$", ref)
        if not m:
            return "ERROR: cell must be Sheet!COLROW"
        sheet, col, row = m.group(1), m.group(2), int(m.group(3))
        if sheet not in wb.sheetnames:
            return f"ERROR: no sheet {sheet}"
        cur = wb[sheet][f"{col}{row}"].value
        try:
            cur_v = Evaluator(wb).cell(sheet, f"{col}{row}")
        except Exception as ex:
            cur_v = f"eval-error {ex}"
        axis = spec["year_axis"].get(sheet, {})
        pcol = axis.get("columns", {}).get(last_actual)
        out = [f"{ref} = {cur!r} -> {cur_v}"]
        all_cells = {(s2.title, f"{col}{r2}") for s2 in wb.worksheets
                     for r2 in range(1, 401)} - {(sheet, f"{col}{row}")}
        precs = objectives._precedent_inputs(wb, sheet, f"{col}{row}", {col}, all_cells)
        ev_c, ev_p = Evaluator(wb), Evaluator(pre_wb)
        for ps, pco in precs[:20]:
            r2 = int(re.sub(r"[A-Z]+", "", pco))
            lab = objectives._row_label(wb[ps], r2) or f"row {r2}"
            try:
                cv = ev_c.cell(ps, pco)
            except Exception:
                cv = "?"
            pv2 = "?"
            if pcol:
                try:
                    pv2 = ev_p.cell(ps, f"{pcol}{r2}")
                except Exception:
                    pass
            fl = " [FLAGGED]" if any(f_[0] == ps and f_[1] == pco for f_ in flags) else ""
            out.append(f"  {ps}!{pco} '{str(lab)[:34]}': now={cv} | prior={pv2}{fl}")
        return "\n".join(out)

    notes = []

    def t_note(args):
        tx = str(args.get("text", ""))[:300]
        if tx:
            notes.append(tx)
        return f"noted ({len(notes)} notes kept)"

    todos = []  # [text, open?]

    def t_todo(args):
        add = str(args.get("add", ""))[:160]
        done = args.get("done")
        if add:
            todos.append([add, True])
            return f"todo added (#{len(todos)})"
        if done is not None:
            try:
                todos[int(done) - 1][1] = False
                return f"todo #{done} closed"
            except (ValueError, IndexError):
                return "ERROR: bad todo number"
        return "ERROR: pass add or done"

    def t_request_review(args):
        if request_review is None:
            return "reviewer disabled for this run"
        f = request_review()
        lines = [f"[{x.get('severity')}] {x.get('cell')}: "
                 f"{str(x.get('disclosure_says', ''))[:80]} — "
                 f"{str(x.get('evidence', ''))[:120]} (p{x.get('page', '?')})"
                 for x in f.get("findings", [])][:12]
        return ("REVIEWER VERDICT: " + str(f.get("verdict", ""))[:200] + "\n"
                + ("\n".join(lines) or "no findings")
                + "\nAct on findings you can verify (set_input needs the page cite); "
                  "ignore ones you cannot corroborate.")

    def t_list_flags(args):
        return "\n".join(f"{s_}!{c_}: {n_[:80]}" for s_, c_, n_ in flags[-40:]) \
            or "no flags"

    tools = {"read_pages": t_read_pages, "find_line": t_find_line,
             "prove_key": t_prove_key, "plug_key": t_plug_key,
             "set_input": t_set_input, "diagnose_balance": t_diagnose_balance,
             "apply_repair": t_apply_repair, "trace_cell": t_trace_cell,
             "note": t_note, "todo": t_todo,
             "request_review": t_request_review, "list_flags": t_list_flags,
             "rescore": lambda a: _fmt_scorecard(_card())}

    max_d = int((cfg.get("orchestrator") or {}).get("max_decisions", MAX_DECISIONS))
    for turn in range(max_d):
        if time.time() >= deadline:
            decisions.append("deadline reached — loop ended by scheduler")
            break
        card = _card()
        mins_left = max(0.0, (deadline - time.time()) / 60)
        open_td = [(i + 1, t) for i, (t, op) in enumerate(todos) if op]
        state = (f"TIME: {mins_left:.0f} min left (objective 3)\n\n"
                 + _fmt_scorecard(card)
                 + ("\n\nYOUR OPEN TASKS:\n" + "\n".join(f"#{i} {t}" for i, t in open_td)
                    if open_td else "")
                 + ("\n\nYOUR NOTES:\n" + "\n".join(f"- {n}" for n in notes[-10:])
                    if notes else "")
                 + "\n\nACTION HISTORY (latest last):\n"
                 + ("\n".join(history[-10:]) or "(none yet)"))
        try:
            resp = client.json(
                system + "\n\n" + prompt, state,
                lambda o: [] if isinstance(o.get("action"), str) else ["missing action"],
                repair_retries=1)
        except Exception as ex:
            decisions.append(f"LLM error ({ex}) — loop ended")
            break
        action = resp.get("action", "")
        args = resp.get("args") or {}
        why = str(resp.get("why", ""))[:160]
        if action == "finish":
            decisions.append(f"finish: {str(args.get('summary', why))[:200]}")
            break
        key = (action, json.dumps(args, sort_keys=True))
        if key in tried and action not in ("rescore",):
            history.append(f"[{action}] SKIPPED: identical action already tried")
            continue
        tried.add(key)
        fn = tools.get(action)
        if fn is None:
            history.append(f"[{action}] ERROR: unknown tool")
            continue
        try:
            result = str(fn(args))
        except Exception as ex:
            result = f"TOOL ERROR: {ex}"
        history.append(f"[{action}] {why} -> {result[:400]}")
        decisions.append(f"{action}({json.dumps(args)[:120]}): {why} -> {result[:160]}")
        log_print(f"  [ORCH {turn+1}] {action}: {why} -> {result[:120]}")
    return _card(), decisions
