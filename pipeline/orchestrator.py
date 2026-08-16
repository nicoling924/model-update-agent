"""Stage 4b — the OBJECTIVE LOOP: Luna owns the update; code is its hands.

This is the anti-workflow-machine (owner mandate 2026-08-17): no scripted
sequence of steps. The engine sees the objectives, the live scorecard, its
own notes/todos/history, and a toolbox — and decides, one action per turn,
how to close the gap. It works the way Fable 5 works free-form; the
deterministic stages before this loop are its assistance, and the guards
around every tool are why it cannot break the model:

- set_input goes through the ONE write chokepoint (world-band guard,
  numeric preview, read-back) AND is TRANSACTIONAL: if the write worsens
  the target-year check rows, it auto-reverts and the loop is told why
  (the run-39 law).
- Subtotal/designed-formula cells are refused — repair components, never
  totals.
- Every action and result lands in the history the engine sees next turn;
  notes and todos persist. Machine heuristics never write on their own.
- The ledger IS the disclosure: find_line and statement_diff search the
  evidence items (text and accepted vision lines alike), so "re-reading
  the filing" is a code lookup, not a paid call.

Generic: objectives, check rows and key rows come from the spec; the loop
knows no company, language, or layout.
"""
import json
import re
from pathlib import Path

from .checks import prior_column, scorecard, summarize, year_columns
from .evaluator import Evaluator
from .numerics import SCALES, line_numbers, row_tol, to_model_units

MAX_ACTIONS = 60
MAX_HISTORY_SHOWN = 30
MAX_FINDS = 12

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "stage4_objective.md"


def _load_prompt():
    return _PROMPT_PATH.read_text(encoding="utf-8")


class ObjectiveLoop:
    def __init__(self, wb, spec, target_year, ledger, targets, served,
                 writer, client, log=None, budget=MAX_ACTIONS):
        self.wb = wb
        self.spec = spec
        self.ty = str(target_year)
        self.ledger = ledger
        self.targets = {t.key: t for t in targets}
        self.served = served
        self.writer = writer
        self.client = client
        self.log = log if log is not None else []
        self.budget = budget
        self.history = []
        self.notes = []
        self.todos = []
        self.finished = None
        self._system = ("You are the equity research analyst responsible for "
                        "delivering this model update. You investigate before "
                        "you act, cite evidence for every write, and never "
                        "invent a number.")

    # -- state ---------------------------------------------------------------

    def _card(self):
        return scorecard(self.wb, self.spec, self.ty, served=self.served,
                         flags=self.writer.log["flags"])

    def _state_block(self):
        card = self._card()
        todos = [f"  [{i}] {t}" for i, t in enumerate(self.todos)]
        notes = [f"  - {n}" for n in self.notes[-12:]]
        hist = [f"  {h}" for h in self.history[-MAX_HISTORY_SHOWN:]]
        return "\n".join([
            f"TARGET YEAR: {self.ty}   ACTIONS LEFT: {self.budget}",
            "== SCORECARD ==",
            summarize(card, self.ty, flags=self.writer.log["flags"],
                      spec=self.spec, wb=self.wb),
            "== OPEN TODOS ==", *(todos or ["  (none)"]),
            "== YOUR NOTES ==", *(notes or ["  (none)"]),
            "== ACTION HISTORY (newest last) ==", *(hist or ["  (none)"]),
        ])

    # -- tools ---------------------------------------------------------------

    def _tcol(self, sheet):
        return year_columns(self.spec, sheet).get(self.ty)

    def t_rescore(self, args):
        return summarize(self._card(), self.ty)

    def t_trace_cell(self, args):
        ref = str(args.get("cell", ""))
        m = re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]{1,3})(\d+)$", ref.replace("$", ""))
        if not m:
            return f"MISS: cell ref '{ref}' unparseable (Sheet!C7 form)"
        sheet, col, row = (m.group(1) or m.group(2)), m.group(3), int(m.group(4))
        if sheet not in self.wb.sheetnames:
            return f"MISS: no sheet '{sheet}'"
        ws = self.wb[sheet]
        v = ws[f"{col}{row}"].value
        ev = Evaluator(self.wb)
        pcol = prior_column(self.spec, sheet, self.ty)
        out = [f"{ref} holds: {v!r}"]
        try:
            out.append(f"evaluates to: {ev.cell(sheet, f'{col}{row}'):,.4f}")
        except Exception as e:
            out.append(f"evaluation failed: {e}")
        if isinstance(v, str) and v.startswith("="):
            refs = re.findall(r"(?:'([^']+)'|([A-Za-z0-9 _]+))?!?([A-Z]{1,3})(\d+)",
                              v.replace("$", ""))[:24]
            for sh2, sh3, c2, r2 in refs:
                sh = (sh2 or sh3 or sheet).strip()
                if sh not in self.wb.sheetnames:
                    continue
                try:
                    cur = ev.cell(sh, f"{c2}{r2}")
                except Exception:
                    cur = "?"
                # the component's OWN sheet's prior column, evaluated
                pv = None
                sh_pcol = prior_column(self.spec, sh, self.ty)
                if sh_pcol and c2 == self._tcol(sh):
                    try:
                        pv = ev.cell(sh, f"{sh_pcol}{r2}")
                    except Exception:
                        pv = None
                lab = next((self.wb[sh][f"{lc}{r2}"].value
                            for lc in ("A", "B", "C")
                            if isinstance(self.wb[sh][f"{lc}{r2}"].value, str)), "")
                mark = ""
                if isinstance(cur, (int, float)) and isinstance(pv, (int, float)) \
                        and pv != 0:
                    move = (cur - pv) / abs(pv)
                    if (cur < 0) != (pv < 0) and abs(pv) > 1:
                        mark = "  <== SIGN FLIPPED vs prior — suspect"
                    elif abs(move) > 0.5:
                        mark = f"  <== moved {move:+.0%} YoY — suspect"
                out.append(f"  {sh}!{c2}{r2} '{str(lab)[:30]}' = {cur}"
                           + (f"  (prior {pv:,.2f})"
                              if isinstance(pv, (int, float)) else "")
                           + mark)
        return "\n".join(out)

    def t_find_line(self, args):
        q = str(args.get("name", "")).strip()
        if not q:
            return "MISS: empty query"
        qnum = None
        try:
            qnum = float(q.replace(",", ""))
        except ValueError:
            pass
        prior_docs = self.ledger.prior_period_docs()
        hits = []
        for it in self.ledger.items:
            if q.lower() in it.label.lower() or q.lower() in it.source_line.lower():
                hits.append(it)
            elif qnum is not None and any(
                    abs(abs(to_model_units(n, s)) - abs(qnum)) <= row_tol(qnum)
                    for n in it.nums for s in SCALES):
                hits.append(it)
            if len(hits) >= MAX_FINDS * 2:
                break
        # current-period evidence first; prior-period doc lines are context,
        # never citations for a current-year write
        hits.sort(key=lambda it: it.doc in prior_docs)
        hits = hits[:MAX_FINDS]
        if not hits:
            return (f"MISS: '{q}' not in the evidence ledger. Try ONE synonym, "
                    "then move on.")
        return "\n".join(
            f"{it.doc} p{it.page} "
            f"[{'PRIOR-PERIOD DOC — not citable' if it.doc in prior_docs else self.ledger.face(it.doc, it.page) or 'no-face'}]"
            f" {it.source_line[:110]}" for it in hits)

    def t_statement_diff(self, args):
        stmt = str(args.get("stmt", "bs"))
        prior_docs = self.ledger.prior_period_docs()
        pages = [(d, p) for (d, p), f in self.ledger.faces.items()
                 if f == stmt and d not in prior_docs]
        if not pages:
            return f"MISS: no {stmt} face pages in the ledger"
        # ratio/margin rows (|prior| < 1) tie junk — statements print money
        rows = [t for t in self.targets.values()
                if isinstance(t.prior_value, (int, float))
                and abs(t.prior_value) >= 1.0]
        out, seen = [], set()
        for it in self.ledger.items:
            if (it.doc, it.page) not in pages or not it.joinable():
                continue
            for t in rows:
                pv = t.prior_value
                tol = row_tol(pv, base=0.6 if abs(pv) >= 100 else 0.01)
                for s in SCALES:
                    ns = [to_model_units(n, s) for n in it.nums]
                    tied = [(ns[i], i) for i in range(len(ns) - 1)
                            if abs(abs(ns[i + 1]) - abs(pv)) <= tol]
                    if len(tied) != 1 or t.key in seen:
                        continue
                    seen.add(t.key)
                    tcol = self._tcol(t.sheet)
                    mv = self.wb[t.sheet][f"{tcol}{t.row}"].value if tcol else None
                    try:
                        mv_n = (Evaluator(self.wb).cell(t.sheet, f"{tcol}{t.row}")
                                if isinstance(mv, str) else mv)
                    except Exception:
                        mv_n = None
                    dv = tied[0][0]
                    diff = (isinstance(mv_n, (int, float))
                            and abs(abs(mv_n) - abs(dv)) > max(0.6, abs(dv) * 5e-3))
                    tag = "DIFF" if diff else ("EMPTY" if mv_n in (None, "") else "ok")
                    if tag != "ok":
                        out.append(f"{tag} {t.sheet}!{t.row} '{str(t.label)[:32]}' "
                                   f"model={mv_n if mv_n is not None else '—'} "
                                   f"disclosed≈{dv:,.2f} "
                                   f"({it.doc} p{it.page}: {it.source_line[:60]})")
                    break
        return "\n".join(out[:40]) or f"no diffs: {stmt} lines tie the model"

    def t_set_input(self, args):
        ref = str(args.get("cell", ""))
        why = str(args.get("why", ""))
        m = re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]{1,3})(\d+)$", ref.replace("$", ""))
        if not m:
            return f"MISS: cell ref '{ref}' unparseable"
        if not re.search(r"p(?:age)?\.?\s*\d+", why, re.IGNORECASE):
            return ("REFUSED: 'why' must cite the disclosure page "
                    "(e.g. 'p102: ...') — no citation, no write")
        try:
            value = float(args.get("value"))
        except (TypeError, ValueError):
            return "MISS: numeric value required"
        sheet, col, row = (m.group(1) or m.group(2)), m.group(3), int(m.group(4))
        if sheet not in self.wb.sheetnames:
            return f"MISS: no sheet '{sheet}'"
        held = self.wb[sheet][f"{col}{row}"].value
        if isinstance(held, str) and held.startswith("=") \
                and re.search(r"SUM|[+\-]", held[1:], re.IGNORECASE):
            return (f"REFUSED: {ref} is a designed formula ({held[:40]}) — "
                    "repair its COMPONENTS, never the total (trace_cell it)")
        pcol = prior_column(self.spec, sheet, self.ty)
        before_card = self._card()
        before_fails = {c["name"] for c in before_card["checks"]
                        if c["status"] == "FAIL"}
        ok = self.writer.write(sheet, f"{col}{row}", value,
                               prior_coord=f"{pcol}{row}" if pcol else None,
                               note=f"objective loop: {why[:300]}",
                               flag="red" if args.get("flag") else None)
        if not ok:
            reason = (self.writer.log["band_refused"][-1]
                      if self.writer.log["band_refused"] else
                      self.writer.log["lock_refused"][-1]
                      if self.writer.log["lock_refused"] else "guard refusal")
            return f"REFUSED by write guard: {reason}"
        after_fails = {c["name"] for c in self._card()["checks"]
                       if c["status"] == "FAIL"}
        broke = sorted(after_fails - before_fails)
        if broke:
            self.writer.write(sheet, f"{col}{row}", held,
                              prior_coord=f"{pcol}{row}" if pcol else None,
                              force_lock=True, trusted=True,
                              note="objective loop: REVERTED (broke checks)")
            return (f"REVERTED: the write broke previously-passing checks "
                    f"{broke[:4]} — the target cell is wrong, not the value; "
                    "trace_cell / statement_diff to find the right row")
        self.served[(sheet, row)] = {"value": value, "status": "OK",
                                     "conf": 3, "page": None,
                                     "line": why[:60],
                                     "note": f"objective loop: {why[:120]}"}
        fixed = sorted(before_fails - after_fails)
        return "WRITTEN" + (f"; checks now passing: {fixed[:4]}" if fixed else "")

    def t_flag_cell(self, args):
        ref = str(args.get("cell", ""))
        m = re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]{1,3}\d+)$", ref.replace("$", ""))
        if not m:
            return f"MISS: cell ref '{ref}' unparseable"
        sheet, coord = (m.group(1) or m.group(2)), m.group(3)
        if sheet not in self.wb.sheetnames:
            return f"MISS: no sheet '{sheet}'"
        cell = self.wb[sheet][coord]
        self.writer.log["flags"].append(f"{sheet}!{coord}")
        from openpyxl.comments import Comment
        cell.fill = self.writer.fills["red"]
        cell.comment = Comment(str(args.get("why", "flagged for review"))[:400],
                               "Model Update Agent")
        return "FLAGGED"

    def t_note(self, args):
        self.notes.append(str(args.get("text", ""))[:300])
        return "noted"

    def t_todo(self, args):
        if args.get("add"):
            self.todos.append(str(args["add"])[:200])
            return f"added [{len(self.todos) - 1}]"
        if args.get("done") is not None:
            i = int(args["done"])
            if 0 <= i < len(self.todos):
                return f"closed: {self.todos.pop(i)}"
        return "MISS: use {'add': ...} or {'done': index}"

    def t_list_flags(self, args):
        flags = self.writer.log["flags"]
        return "\n".join(flags[-40:]) or "(no flags)"

    def t_finish(self, args):
        self.finished = str(args.get("summary", ""))[:800]
        return "finished"

    # -- the loop ------------------------------------------------------------

    TOOLS = {"rescore": t_rescore, "trace_cell": t_trace_cell,
             "find_line": t_find_line, "statement_diff": t_statement_diff,
             "set_input": t_set_input, "flag_cell": t_flag_cell,
             "note": t_note, "todo": t_todo, "list_flags": t_list_flags,
             "finish": t_finish}

    def run(self):
        prompt = _load_prompt()
        while self.budget > 0 and self.finished is None:
            self.budget -= 1
            user = prompt + "\n\n" + self._state_block()

            def _val(o):
                if not isinstance(o.get("action"), str):
                    return ["missing 'action'"]
                if o["action"] not in self.TOOLS:
                    return [f"unknown action '{o['action']}'; one of "
                            f"{sorted(self.TOOLS)}"]
                return []
            try:
                act = self.client.json(self._system, user, _val, repair_retries=1)
            except Exception as e:
                self.log.append(f"stage-4 loop: call failed: {e}")
                break
            name = act["action"]
            args = act.get("args") or {}
            fingerprint = name + json.dumps(args, sort_keys=True, ensure_ascii=False)
            if name not in ("rescore", "note", "todo", "finish") \
                    and fingerprint in getattr(self, "_done", set()):
                result = ("REPEAT: you already ran exactly this action — the "
                          "result has not changed. Take a DIFFERENT action "
                          "(your history shows what you learned).")
            else:
                self._done = getattr(self, "_done", set())
                self._done.add(fingerprint)
                try:
                    result = self.TOOLS[name](self, args)
                except Exception as e:
                    result = f"TOOL ERROR: {e}"
            snip = json.dumps(args, ensure_ascii=False)[:90]
            first = str(result).splitlines()[0][:110] if result else ""
            self.history.append(f"{name} {snip} -> {first}")
            self.log.append(f"stage-4: {name} {snip} -> {first}")
        if self.finished is None:
            self.finished = "(action budget exhausted)"
        return self.finished
