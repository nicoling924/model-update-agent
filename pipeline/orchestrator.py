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
from .ledger import vintage_ban as _vintage_ban

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
        self.budget0 = budget
        self._fc_spend = 0            # actions spent on forecast work
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

    def _trip_groups(self):
        """Tripwires clustered by shared upstream inputs (run-198: 46
        traces for 18 tripwires that chain to a handful of SOC roots —
        one investigation per CHAIN, not per cell)."""
        trips = getattr(self, "tripwires", [])
        if not trips:
            return []
        leafsets = {}
        for (sheet, col, r, fv, pv, tv) in trips:
            leafsets[(sheet, col, r)] = frozenset(
                self._leaf_inputs(sheet, f"{col}{r}")) or frozenset(
                    [(sheet, f"{col}{r}")])
        groups = []
        for t in trips:
            k = (t[0], t[1], t[2])
            for g in groups:
                if leafsets[k] & leafsets[(g[0][0], g[0][1], g[0][2])]:
                    g.append(t)
                    break
            else:
                groups.append([t])
        return groups

    def _trip_lines(self):
        """Open tripwires: sign-flipped forecasts handed in by the sense
        check (owner ruling 2026-08-31: a mistake DETECTOR — investigate
        once per CHAIN, then verdict every member; never silently
        freeze). Spend is capped: the terminal freeze safely holds
        whatever remains."""
        done = {v.split(":", 1)[0] for v in
                self.writer.log.get("verdicts", [])}
        cap = max(6, self.budget0 // 6)
        spent = getattr(self, "_trip_spend", 0)
        out = []
        for g in self._trip_groups():
            open_g = [t for t in g if f"{t[0]}!{t[1]}{t[2]}" not in done]
            if not open_g:
                continue
            keys = ", ".join(f"{s}!{c}{r}" for s, c, r, *_ in open_g[:12])
            s0, c0, r0, fv0, pv0, tv0 = open_g[0]
            if len(open_g) > 1:
                out.append(
                    f"  CHAIN ({len(open_g)} rows share upstream inputs): "
                    f"{keys} — e.g. {s0}!{c0}{r0} computes {fv0:,.2f} where "
                    f"actuals are {pv0:,.2f} -> {tv0:,.2f}. ONE trace of "
                    f"the chain, then verdict {{\"items\": [{keys.split(', ')[0]!r}, ...], ...}} "
                    f"covering every member")
            else:
                out.append(
                    f"  {s0}!{c0}{r0}: forecast {fv0:,.2f} NEGATIVE where "
                    f"actuals are positive ({pv0:,.2f} -> {tv0:,.2f}) — "
                    f"usually a mis-rolled upstream input. trace_cell it "
                    f"ONCE, then verdict {{\"item\": \"{s0}!{c0}{r0}\", ...}}")
        if out and spent >= cap:
            out = [f"  (tripwire budget spent — {len(out)} chains remain; "
                   "verdict only what you already understand, the rest "
                   "freeze terminally at pre-update values)"]
        return out

    def _failing_target_checks(self, tol=1.0):
        """Spec check rows still failing in the TARGET year column.
        -> [(sheet, row, residual)]."""
        ev = Evaluator(self.wb)
        out = []
        for c in (self.spec.get("check_rows") or []):
            sheet, row = c.get("sheet"), int(c.get("row"))
            col = self._tcol(sheet)
            if not col or sheet not in self.wb.sheetnames:
                continue
            expect = float(c.get("expect", 0))
            try:
                got = ev.cell(sheet, f"{col}{row}")
            except Exception:
                continue
            if isinstance(got, (int, float)) and abs(got - expect) > tol:
                out.append((sheet, row, got - expect))
        return out

    def _state_block(self):
        card = self._card()
        todos = [f"  [{i}] {t}" for i, t in enumerate(self.todos)]
        notes = [f"  - {n}" for n in self.notes[-12:]]
        hist = [f"  {h}" for h in self.history[-MAX_HISTORY_SHOWN:]]
        trips = self._trip_lines()
        plugs = []
        done_v = {v.split(":", 1)[0]
                  for v in self.writer.log.get("verdicts", [])}
        for (pm_sh, pm_r, pm_now, pm_was) in getattr(
                self, "plugmeters", [])[:8]:
            key = f"{pm_sh}!{self._tcol(pm_sh)}{pm_r}"
            if key in done_v:
                continue
            plugs.append(
                f"  {key}: the model's own residual computed {pm_was:,.1f} "
                f"last year, {pm_now:,.1f} now — a wild plug means an "
                f"INPUT feeding its total is wrong (the export-plug "
                f"lesson). trace_cell the total's components, fix the "
                f"input, then verdict {{\"item\": \"{key}\", ...}}")
        errs = []
        for (s, c, why) in getattr(self, "error_items", [])[:10]:
            try:
                Evaluator(self.wb).cell(s, c)
                continue                       # since fixed
            except Exception:
                pass
            errs.append(f"  {s}!{c}: {why} — trace_error it, fix the "
                        "CAUSE (never paper over the symptom)")
        endgame = []
        if self.budget <= 10:
            fails = self._failing_target_checks()
            if fails:
                endgame = [
                    f"== ENDGAME — {self.budget} actions left, checks "
                    "still failing ==",
                    "  CLOSE THE LADDER NOW (owner's law: a balanced "
                    "flagged model beats an unbalanced one). For each "
                    "check below: plug_residual into the largest "
                    "eligible site (diagnose_balance names them). "
                    "NO more searching.",
                ] + [f"  CHECK {s}!{r} off {v:+,.1f}" for s, r, v in fails]
        return "\n".join([
            f"TARGET YEAR: {self.ty}   ACTIONS LEFT: {self.budget}",
            *endgame,
            *(["== NEW ERRORS (this update broke cells that computed "
               "before — HIGHEST priority) =="] + errs if errs else []),
            *(["== PLUG METERS (the model's own residual rows moved "
               "wildly — each needs ONE verdict) =="] + plugs
              if plugs else []),
            "== SCORECARD ==",
            summarize(card, self.ty, flags=self.writer.log["flags"],
                      spec=self.spec, wb=self.wb),
            *(["== TRIPWIRES (sign-flip sense check — each needs ONE "
               "verdict: ERROR_FIXED / JUSTIFIED / SUSPICIOUS) =="] + trips
              if trips else []),
            "== OPEN TODOS ==", *(todos or ["  (none)"]),
            "== YOUR NOTES ==", *(notes or ["  (none)"]),
            "== ACTION HISTORY (newest last) ==", *(hist or ["  (none)"]),
        ])

    # -- tools ---------------------------------------------------------------

    def _tcol(self, sheet):
        return year_columns(self.spec, sheet).get(self.ty)

    # ONE reference grammar for EVERY tool (run-197 exhibit: the loop's
    # own tools printed refs as 'Final!AI99' and plug_residual then
    # rejected that exact form with a MISS that never named the defect —
    # the endgame budget burned on format-guessing and the plug that
    # would have delivered never landed). Column letters are always
    # tolerated: row tools ignore them, cell tools default a missing
    # column to the target year's column.
    _REF_RE = re.compile(r"^(?:'([^']+)'|([^!]+))!?\s*([A-Z]{1,3})?(\d{1,5})$")

    def _row_ref(self, ref):
        """-> (sheet, row) or None. Accepts Model!95 AND Model!AI95."""
        m = self._REF_RE.match(str(ref).strip().replace("$", ""))
        if not m:
            return None
        return (m.group(1) or m.group(2)).strip(), int(m.group(4))

    def _cell_ref(self, ref, default_tcol=True):
        """-> (sheet, col, row) or None. A missing column defaults to the
        sheet's target-year column when default_tcol."""
        m = self._REF_RE.match(str(ref).strip().replace("$", ""))
        if not m:
            return None
        sheet = (m.group(1) or m.group(2)).strip()
        col = m.group(3) or (self._tcol(sheet) if default_tcol else None)
        if not col:
            return None
        return sheet, col, int(m.group(4))

    def t_rescore(self, args):
        return summarize(self._card(), self.ty)

    def t_trace_cell(self, args):
        ref = str(args.get("cell", ""))
        cr = self._cell_ref(ref)
        if not cr:
            return f"MISS: cell ref '{ref}' unparseable — use \"Sheet!C7\" (a bare row like \"Sheet!7\" reads the target-year column)"
        sheet, col, row = cr
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
            refs = re.findall(r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?([A-Z]{1,3})(\d+)",
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
        # PAGE VIEW (the Fable-drive method): {"page": 214} (optional
        # "doc" substring) lists that page's machine-extracted lines in
        # print order — the analyst's "lay the whole statement beside
        # the model", with zero transcription risk. This is how the CF
        # statement was composed in the by-hand drive.
        if args.get("page") is not None:
            try:
                pn = int(args["page"])
            except (TypeError, ValueError):
                return "MISS: page must be a number"
            dq = str(args.get("doc") or "").lower()
            prior_docs = _vintage_ban(self.ledger)
            items = [it for it in self.ledger.items
                     if it.page == pn and (not dq or dq in it.doc.lower())]
            if not items:
                return f"MISS: no extracted lines on p{pn}"
            items.sort(key=lambda it: (it.doc in prior_docs, it.doc,
                                       it.table_id or 0, it.row_ord or 0))
            out = []
            for it in items[:70]:
                tag = ("PRIOR-PERIOD DOC — not citable"
                       if it.doc in prior_docs
                       else self.ledger.face(it.doc, it.page) or "no-face")
                nums = " ".join(f"{n:,.10g}" for n in (it.nums or [])[:8])
                out.append(f"{it.doc[:24]} p{pn} [{tag}] "
                           f"'{str(it.label)[:52]}' {nums}")
            if len(items) > 70:
                out.append(f"... {len(items) - 70} more lines not shown")
            return "\n".join(out)
        q = str(args.get("name") or args.get("query")
                or args.get("label") or "").strip()
        if not q:
            return "MISS: empty query"
        qnum = None
        try:
            qnum = float(q.replace(",", ""))
        except ValueError:
            pass
        prior_docs = _vintage_ban(self.ledger)
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
        hits.sort(key=lambda it: (it.doc in prior_docs,
                                  self.ledger.face(it.doc, it.page) is None))
        hits = hits[:MAX_FINDS]
        if not hits:
            return (f"MISS: '{q}' not in the evidence ledger. Try ONE synonym, "
                    "then move on.")
        return "\n".join(
            f"{it.doc} p{it.page} "
            f"[{'PRIOR-PERIOD DOC — not citable' if it.doc in prior_docs else self.ledger.face(it.doc, it.page) or 'no-face'}]"
            f" {it.source_line[:110]}" for it in hits)

    def t_trace_serve(self, args):
        """THE AUTOPSY TOOL (owner directive 2026-09-01): who wrote this
        number? Reads the run's own serve provenance so a suspect value
        is traced to its page and gate before it is believed or fixed."""
        rr = self._cell_ref(str(args.get("cell") or args.get("row") or ""))
        if rr is None:
            return "MISS: give a cell like {\"cell\": \"Final!AI25\"}"
        sheet, col, row = rr
        coord = f"{col}{row}"
        e = self.served.get((sheet, row))
        held = self.wb[sheet][coord].value if sheet in self.wb.sheetnames \
            else None
        head = f"{sheet}!{coord} holds: {held!r}\n"
        if not isinstance(e, dict):
            return (head + "NOT served by the deterministic stages — the "
                    "value is a rollover, a sweep re-anchor, or a loop "
                    "write. If it still equals last year it is STALE: "
                    "find_line the printed current figure (or the page "
                    "view) and serve it with evidence.")
        v = e.get("value")
        vtxt = f"{v:,.2f}" if isinstance(v, (int, float)) else repr(v)
        return (head
                + f"served {vtxt} from {e.get('doc')} "
                  f"p{e.get('page')} line '{str(e.get('line'))[:48]}' "
                  f"(conf {e.get('conf')})\n"
                + f"method: {str(e.get('note'))[:200]}\n"
                + "If this number looks wrong, check the SOURCE ROW's "
                  "geometry with the page view (find_line {\"page\": N}): "
                  "wide segment rows and prior-vintage tables are the two "
                  "classic mis-serves.")

    def t_statement_diff(self, args):
        stmt = str(args.get("stmt", "bs"))
        prior_docs = _vintage_ban(self.ledger)
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
        out = out[:40]
        # UNMATCHED DISCLOSURE LINES (owner's teaching: the leftover
        # names the missing line). Single-year lines print NO comparative
        # so prior-identity can never surface them — run-199's perpetual
        # capital securities 3,872 stayed invisible through 90 actions.
        from .ledger import admissible_label
        priors = [abs(t.prior_value) for t in rows]
        model_vals = set()
        for sh in (self.spec.get("year_axis") or {}):
            tc = self._tcol(sh)
            if not tc or sh not in self.wb.sheetnames:
                continue
            ws = self.wb[sh]
            for rr in range(1, min(ws.max_row, 400) + 1):
                vv = ws[f"{tc}{rr}"].value
                if isinstance(vv, (int, float)):
                    model_vals.add(round(abs(vv), 1))

        def _tied(n):
            a = abs(n)
            if round(a, 1) in model_vals:
                return True
            return any(abs(a - p) <= row_tol(p, base=0.6 if p >= 100
                                             else 0.01) for p in priors)
        unmatched = []
        for it in self.ledger.items:
            if (it.doc, it.page) not in pages \
                    or not admissible_label(it.label):
                continue
            money = [n for n in it.nums if abs(n) >= 1.0]
            if not money or len(money) > 5 or max(abs(n) for n in money) < 50:
                continue
            if any(1990 <= abs(n) <= 2100 for n in money):
                continue                     # date/year furniture
            if any(_tied(n) for n in money):
                continue
            unmatched.append(
                f"  UNMATCHED '{str(it.label)[:40]}' = "
                + ", ".join(f"{n:,.1f}" for n in money[:4])
                + f" ({it.doc} p{it.page}) — ties NO model row: a line "
                "the model never carried? (balance-first fold, red)")
        if unmatched:
            out.append("UNMATCHED DISCLOSURE LINES — the leftover names "
                       "the missing line:")
            out += unmatched[:12]
        return "\n".join(out) or f"no diffs: {stmt} lines tie the model"

    def _diff_value(self, t):
        """The disclosed value for one target row — the shared evidence
        oracle (single agreeing in-world prior-identity candidate on a
        ratified current-doc face, or nothing)."""
        from .stage2_join import unique_evidence_value
        return unique_evidence_value(self.ledger, list(self.targets.values()), t)

    def _leaf_inputs_ranges(self, sheet, coord):
        """The range-aware walk (every row of a SUM range is a leaf)."""
        return self._leaf_inputs(sheet, coord, ranges=True)

    def _leaf_inputs(self, sheet, coord, depth=0, seen=None, ranges=False):
        """The leaf INPUT cells under a target-year formula cell: follow
        references recursively; a numeric hardcode is a leaf. Bounded."""
        seen = seen if seen is not None else set()
        if depth > 6 or (sheet, coord) in seen or len(seen) > 400:
            return []
        seen.add((sheet, coord))
        v = self.wb[sheet][coord].value if sheet in self.wb.sheetnames else None
        if isinstance(v, (int, float)):
            return [(sheet, coord)]
        if not isinstance(v, str) or not v.startswith("="):
            return []
        # the agent's OWN back-out formula (an orange growth hold written
        # this run) is a leaf: the least confident input in the chain,
        # and the ladder's first plug site (owner 2026-09-08). The
        # analyst's formulas are walked through, never treated as inputs.
        try:
            _rgb = str(self.wb[sheet][coord].fill.fgColor.rgb or "")
        except Exception:
            _rgb = ""
        if _rgb.endswith("FFC000") and f"{sheet}!{coord}" in self.writer.log.get("written", []):
            return [(sheet, coord)]
        out = []
        txt = v.replace("$", "")
        if ranges:
            # SUM(AI14:AI18) names every row of the range (run-232 D&A
            # autopsy: China's D&A inside the range was invisible to the
            # rollover dossier). Range-aware walking is for the DOSSIER
            # only — the terminal ladder's plug candidates keep the
            # classic walk (expanding ranges there changed the ladder's
            # choices and blew the cash chain on the 232 replay).
            for sh2, sh3, c2, r2, c3, r3 in re.findall(
                    r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?([A-Z]{1,3})(\d+):([A-Z]{1,3})(\d+)",
                    txt):
                sh = (sh2 or sh3 or sheet).strip()
                if sh in self.wb.sheetnames and c2 == c3:
                    for rr in range(min(int(r2), int(r3)), max(int(r2), int(r3)) + 1):
                        out += self._leaf_inputs(sh, f"{c2}{rr}", depth + 1, seen, ranges=True)
            txt = re.sub(r"[A-Z]{1,3}\d+:[A-Z]{1,3}\d+", " ", txt)
        for sh2, sh3, c2, r2 in re.findall(
                r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?([A-Z]{1,3})(\d+)",
                txt):
            sh = (sh2 or sh3 or sheet).strip()
            if sh in self.wb.sheetnames:
                out += self._leaf_inputs(sh, f"{c2}{r2}", depth + 1, seen, ranges=ranges)
        if not out:
            # a formula with no cell references (=4976+23) IS a leaf —
            # the constants-composite class was invisible to this walk
            # for four CLP runs (run-198 lesson)
            return [(sheet, coord)]
        return out

    def t_diagnose_balance(self, args):
        """FIND THE PART THAT DOES NOT BALANCE (owner ruling: the model
        must balance itself; an imbalance means a specific wrong cell).
        Decomposes a failing check row to its leaf input cells, compares
        each against unique disclosed evidence, and names the guilty ones
        with their disclosed values — each directly fixable by apply_diff.
        Plugging is the WORST case, only after this list is empty."""
        ref = str(args.get("check") or args.get("cell") or "")
        # accept Model!95, Model!U95 and 'Sheet name'!V95 forms — a rejected
        # ref burned real loop budget (measured)
        m = re.match(r"^(?:'([^']+)'|([^!]+))!?([A-Z]{1,3})?(\d+)$",
                     ref.replace("$", ""))
        if not m:
            checks = [f"{c['sheet']}!{c['row']}"
                      for c in self.spec.get("check_rows") or []]
            return f"MISS: name the check row, e.g. {{\"check\": \"{checks[0] if checks else 'Model!95'}\"}}"
        sheet, row = (m.group(1) or m.group(2)).strip(), int(m.group(4))
        col = m.group(3) or self._tcol(sheet)
        if not col:
            return f"MISS: no target column for sheet '{sheet}'"
        ev = Evaluator(self.wb)
        try:
            residual = ev.cell(sheet, f"{col}{row}")
        except Exception as e:
            return f"MISS: check row does not evaluate: {e}"
        out = [f"check {sheet}!{col}{row} residual = {residual:,.2f}"]
        guilty = 0
        sites = []          # numeric leaf inputs = the only legal plug sites
        flagged_refs = set(self.writer.log["flags"])
        for (sh, coord) in dict.fromkeys(self._leaf_inputs(sheet, f"{col}{row}")):
            mm = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
            if not mm or mm.group(1) != self._tcol(sh):
                continue
            t = self.targets.get((sh, int(mm.group(2))))
            cur = self.wb[sh][coord].value
            if isinstance(cur, (int, float)):
                # unproven sites rank first; proven sites are the
                # LAST-RESORT tier — the plug experiment (forecast
                # probe) referees them, per the owner's balance ruling
                pv_ok = (sh, int(mm.group(2))) not in (self.served or {})
                sites.append((sh, coord,
                              (str(t.label)[:30] if t else "?")
                              + ("" if pv_ok else " [PROVEN—last resort]"),
                              cur if pv_ok else cur))
            if isinstance(cur, str) and cur.startswith("="):
                # a ref-less composite leaf: stillness is the signal —
                # evaluating to its own prior = last year's actual never
                # rolled (the run-198 class)
                try:
                    ce = ev.cell(sh, coord)
                except Exception:
                    ce = None
                pv2 = None
                sh_p = prior_column(self.spec, sh, self.ty)
                if sh_p:
                    try:
                        pv2 = ev.cell(sh, f"{sh_p}{mm.group(2)}")
                    except Exception:
                        pv2 = None
                if isinstance(ce, (int, float)) \
                        and isinstance(pv2, (int, float)) \
                        and abs(ce - pv2) <= 1.0:
                    out.append(
                        f"  STALE COMPOSITE {sh}!{coord} holds {cur[:34]} "
                        f"and still evaluates its own prior {ce:,.2f} — "
                        f"last year's actual never rolled -> "
                        f"rewrite_constants {{\"cell\": \"{sh}!"
                        f"{mm.group(2)}\"}}")
                continue
            got = self._diff_value(t) if t is not None else None
            if got is not None and isinstance(cur, (int, float)):
                dv, it, _s = got
                tol = max(0.6, abs(dv) * 5e-3)
                if abs(cur - dv) > tol:
                    # A GUILTY VERDICT MUST SURVIVE ITS OWN EXPERIMENT
                    # (DFE Driver!139, 2026-09-02: two rows "guilty" of
                    # the same junk 61.58 — applying either WORSENED
                    # the check. Probe the diff before accusing.)
                    sign = -1.0 if (cur < 0 < dv) else 1.0
                    old_v = self.wb[sh][coord].value
                    self.wb[sh][coord] = sign * dv
                    try:
                        after_p = Evaluator(self.wb).cell(
                            sheet, f"{col}{row}")
                    except Exception:
                        after_p = None
                    self.wb[sh][coord] = old_v
                    if isinstance(after_p, (int, float)) \
                            and abs(after_p) > abs(residual) + 1.0:
                        out.append(
                            f"  CONTRARY {sh}!{int(mm.group(2))} "
                            f"'{str(t.label)[:30]}': the mapped "
                            f"{dv:,.2f} WORSENS the check "
                            f"({residual:,.1f} -> {after_p:,.1f}) — "
                            "wrong map, not a fix; left alone")
                        continue
                    # TWO PROVEN-GRADE CLAIMS ARE A CONFLICT, NOT A FIX
                    # (run 244: the cell held a proven nil, the diff
                    # named another line; apply_diff was refused by the
                    # proven law and the plug was refused while the
                    # 'evidence fix remained' — a deadlock). A diff
                    # against a proven cell is ruled out for the plug
                    # and listed for the analyst instead.
                    from .rollover import input_is_proven as _iip2
                    if _iip2(self.served, sh, coord, cur, (), self.wb):
                        out.append(f"  CONFLICT {sh}!{int(mm.group(2))} "
                                   f"'{str(t.label)[:30]}': the cell holds a "
                                   f"proven {cur:,.2f}; another line prints "
                                   f"{dv:,.2f} ({it.doc} p{it.page}) — two "
                                   "readings, the analyst's call; not a fix")
                        continue
                    guilty += 1
                    out.append(f"  GUILTY {sh}!{int(mm.group(2))} "
                               f"'{str(t.label)[:30]}': model {cur:,.2f} vs "
                               f"disclosed {dv:,.2f} ({it.doc} p{it.page}) -> "
                               f"apply_diff {{\"row\": \"{sh}!{mm.group(2)}\"}}")
                continue
            # UNPROVEN leaves are suspects: flagged/stale cells and no-prior
            # reads have no identity evidence, so the residual hides in them
            # (measured live: a no-prior misread of -57.89 plus a stale 0.65
            # WERE the 58.5 gap — both red-flagged, neither GUILTY-listable).
            # The exact-delta playbook move, automated: how far does zeroing
            # this cell move the check vs the residual?
            if isinstance(cur, (int, float)) and cur != 0 \
                    and (f"{sh}!{coord}" in flagged_refs
                         or t is None
                         or not isinstance(t.prior_value, (int, float))):
                closes = abs(abs(cur) - abs(residual))
                hint = (" <== zeroing ~CLOSES the residual"
                        if closes <= max(1.0, abs(residual) * 0.1) else "")
                lab = str(t.label)[:30] if t else "?"
                out.append(f"  SUSPECT {sh}!{coord} '{lab}' = {cur:,.2f} "
                           f"(unproven: flagged/no-prior){hint}")
        if guilty == 0 and len(out) == 1:
            out.append("  no leaf disagrees and no unproven suspects — "
                       "find_line the residual amount, or (worst case) "
                       "plug_residual with a named component")
        if guilty == 0 and sites:
            best = sorted(sites, key=lambda s: ("[PROVEN" in s[2],
                                                -abs(s[3])))[:5]
            out.append("  eligible plug sites (numeric inputs feeding this "
                       "check, largest first):")
            for sh, coord, lab, cur in best:
                out.append(f"    {sh}!{coord} '{lab}' = {cur:,.2f}")
            sh, coord, _, _ = best[0]
            out.append(f"  e.g. plug_residual {{\"check\": \"{sheet}!{row}\", "
                       f"\"into\": \"{sh}!{coord}\", \"why\": ...}}")
        return "\n".join(out)

    def _forecast_check_residuals(self):
        """Forecast-year residuals of every spec check row — the probe
        baseline for the plug experiment."""
        from .checks import forecast_columns
        ev = Evaluator(self.wb)
        out = {}
        for c in (self.spec.get("check_rows") or []):
            sh, r = c.get("sheet"), int(c.get("row"))
            if sh not in self.wb.sheetnames:
                continue
            for col in forecast_columns(self.spec, sh, int(self.ty)):
                try:
                    out[f"{sh}!{col}{r}"] = ev.cell(sh, f"{col}{r}")
                except Exception:
                    out[f"{sh}!{col}{r}"] = None
        return out

    def t_plug_residual(self, args):
        """THE WORST CASE, and it is loud (owner ruling): only after
        diagnose_balance names no guilty cell may the exact residual be
        absorbed into ONE named component — orange-flagged, annotated, and
        listed in the _REPORT for the analyst. Refused while any
        evidence-based fix remains."""
        check = str(args.get("check") or "")
        into = str(args.get("into") or "")
        why = str(args.get("why") or "")
        diag = self.t_diagnose_balance({"check": check})
        if "GUILTY" in diag:
            return ("REFUSED: evidence-based fixes remain — plug only after "
                    "these are applied or ruled out:\n" + diag)
        rc = self._row_ref(check)
        if not rc:
            return (f"MISS: check '{check}' unparseable — name the check ROW, "
                    "e.g. \"Final!99\" (column letters tolerated and ignored)")
        ci = self._cell_ref(into)
        if not ci:
            return (f"MISS: into '{into}' unparseable — the plug lands in ONE "
                    "numeric input cell, e.g. \"Sheet!U177\" (a bare row uses "
                    "the target-year column)")
        c_sheet, c_row = rc
        c_col = self._tcol(c_sheet)
        i_sheet, i_col, i_row = ci
        pe = (self.served or {}).get((i_sheet, i_row))
        proven = isinstance(pe, dict)
        # a PROVEN value is never a plug site (owner 2026-09-08): the plug
        # goes into the least confident input of the check's chain
        from .rollover import input_is_proven as _iip
        if proven and _iip(self.served, i_sheet, f"{i_col}{i_row}",
                           self.wb[i_sheet][f"{i_col}{i_row}"].value, (), self.wb):
            return (f"REFUSED: {i_sheet}!{i_col}{i_row} holds a PROVEN value "
                    f"({pe.get('value')} from {pe.get('doc')} p{pe.get('page')}) — "
                    "a plug goes into the least confident input of this "
                    "check's chain (a held-at-prior or red cell), never over "
                    "a read figure")
        # THE PROBE-TESTED PLUG (owner regression ruling 2026-09-01:
        # run-213's share-capital plug was wrong because it BROKE THE
        # FORECAST YEARS, not because the cell was proven — and the
        # blanket proven-ban made balance unreachable on a model where
        # every component is proven, quarantining runs 214-218 that the
        # earlier era delivered. Balance is the hard objective; the loud
        # plug is its sanctioned last resort. So: unproven sites first;
        # a proven site MAY take the plug, but only if the EXPERIMENT
        # below shows the forecast years do not get worse — and it
        # lands RED with the provenance in the note, never quietly.)
        ev = Evaluator(self.wb)
        try:
            residual = ev.cell(c_sheet, f"{c_col}{c_row}")
        except Exception as e:
            return f"MISS: check row does not evaluate: {e}"
        if abs(residual) <= 0.01:
            return "MISS: that check already passes — nothing to plug"
        held = self.wb[i_sheet][f"{i_col}{i_row}"].value
        hold_formula = None
        if isinstance(held, str) and held.startswith("="):
            # the agent's own growth hold (orange, this run) may take the
            # plug — as a traceable composite on its evaluated value
            try:
                rgb_h = str(self.wb[i_sheet][f"{i_col}{i_row}"].fill.fgColor.rgb or "")
            except Exception:
                rgb_h = ""
            if rgb_h.endswith("FFC000") and \
                    f"{i_sheet}!{i_col}{i_row}" in self.writer.log.get("written", []):
                try:
                    hv = Evaluator(self.wb).cell(i_sheet, f"{i_col}{i_row}")
                except Exception:
                    hv = None
                if isinstance(hv, (int, float)):
                    hold_formula, held = held, float(hv)
        if not isinstance(held, (int, float)):
            return (f"MISS: {i_sheet}!{i_col}{i_row} holds "
                    f"{'a formula' if isinstance(held, str) else 'nothing'}, "
                    "not a numeric input — plug into a numeric INPUT "
                    "component; diagnose_balance lists the eligible sites")
        pcol = prior_column(self.spec, i_sheet, self.ty)
        # THE COEFFICIENT PROBE (DFE Driver!139, 2026-09-02: a plug
        # sized on the +1 assumption DOUBLED the residual — the site's
        # true coefficient on the check was -1. Same law as the
        # forecast plugs: measure the response, size by it.)
        cell_pr = self.wb[i_sheet][f"{i_col}{i_row}"]
        old_pr = cell_pr.value
        cell_pr.value = held + 1.0
        try:
            probe_r = Evaluator(self.wb).cell(c_sheet, f"{c_col}{c_row}")
        except Exception:
            probe_r = None
        cell_pr.value = old_pr
        coeff = (probe_r - residual) if isinstance(probe_r, (int, float)) \
            else None
        if not isinstance(coeff, (int, float)) or abs(coeff) < 0.1:
            return (f"MISS: {i_sheet}!{i_col}{i_row} does not move this "
                    f"check (measured coefficient "
                    f"{coeff if coeff is None else round(coeff, 3)}) — "
                    "pick a component that feeds it")
        residual_eff = residual / coeff
        wild = abs(residual_eff) > 0.5 * max(abs(held), 1.0)
        wild_txt = (", WILD — swings the component by more than half; "
                    "a mapped sibling is probably wrong" if wild else "")
        fc_before = self._forecast_check_residuals()
        plug_value = (f"=({held!r})+({-residual_eff!r})" if hold_formula
                      else held - residual_eff)     # full precision: a
                                                    # 6-digit '{:g}' left
                                                    # the check at -1 and
                                                    # the plug was reverted
        ok = self.writer.write(
            i_sheet, f"{i_col}{i_row}", plug_value,
            prior_coord=f"{pcol}{i_row}" if pcol else None,
            trusted=True,
            flag="red" if wild else "orange",
            note=(f"PLUG (worst case{wild_txt}): absorbed check residual "
                  f"{residual:,.2f} from {check}; was {held:,.2f}. "
                  f"ANALYST MUST REVIEW. {why[:200]}"))
        if not ok:
            return ("REFUSED by write guard (lock) — choose another "
                    "component")
        try:
            after = Evaluator(self.wb).cell(c_sheet, f"{c_col}{c_row}")
        except Exception:
            after = None
        if after is None or abs(after) > 0.01:
            self.writer.write(i_sheet, f"{i_col}{i_row}", hold_formula or held,
                              prior_coord=f"{pcol}{i_row}" if pcol else None,
                              trusted=True, force_lock=True,
                              note="plug reverted: did not zero the check")
            return (f"REVERTED: plugging {into} left the check at "
                    f"{after if after is not None else '?'} — the component "
                    "does not feed this check; pick one inside its chain")
        # THE EXPERIMENT: a plug that repairs the actual year by breaking
        # the forecast years is the run-213 share-capital disease — any
        # site, proven or not. Measure, don't assume.
        fc_after = self._forecast_check_residuals()
        hurt = [(k, fc_before.get(k), v) for k, v in fc_after.items()
                if isinstance(v, (int, float))
                and isinstance(fc_before.get(k), (int, float))
                and abs(v) > abs(fc_before[k]) + 1.0]
        if hurt and hold_formula:
            # the least confident site (the agent's own growth hold) takes
            # the plug even where the forecast years move — that movement
            # is the rollover check's business (watch-listed), not a veto
            # (owner 2026-09-08: never plug a proven value instead)
            for k, before_v, after_v in hurt[:6]:
                try:
                    self.writer.watch(str(k).split("!", 1)[0], str(k).split("!", 1)[1],
                                      f"forecast check moved {before_v:,.0f} -> {after_v:,.0f} "
                                      f"after the {check} plug into {into}")
                except Exception:
                    pass
            hurt = []
        if hurt:
            self.writer.write(i_sheet, f"{i_col}{i_row}", hold_formula or held,
                              prior_coord=f"{pcol}{i_row}" if pcol else None,
                              trusted=True, force_lock=True,
                              note="plug reverted: forecast damage")
            worst = max(hurt, key=lambda h: abs(h[2]))
            return (f"REVERTED: plugging {into} zeroes {check} but BREAKS "
                    f"the forecast years ({len(hurt)} worsened, e.g. "
                    f"{worst[0]}: {worst[1]:,.1f} -> {worst[2]:,.1f}) — the "
                    "run-213 disease. This site rolls into the forecasts; "
                    "pick a site the probe leaves clean")
        if proven:
            ref_i = f"{i_sheet}!{i_col}{i_row}"
            self.writer.log["flags"].append(ref_i)
            cell_i = self.wb[i_sheet][f"{i_col}{i_row}"]
            cell_i.fill = self.writer.fills["red"]
            from openpyxl.comments import Comment
            cell_i.comment = Comment(
                (f"PLUG OVER PROVEN VALUE — this cell was served "
                 f"{pe.get('value'):,.2f} from {pe.get('doc')} "
                 f"p{pe.get('page')} and then absorbed the {check} "
                 f"residual {residual:,.2f} as the sanctioned last resort "
                 f"(forecast probe clean). ANALYST MUST RULE. {why[:150]}"),
                "Model Update Agent")
            return (f"PLUGGED {into} OVER A PROVEN VALUE: {held:,.2f} -> "
                    f"{held - residual_eff:,.2f} (RED, forecast-probe clean, "
                    f"in the report). Check {check} now zero.")
        return (f"PLUGGED {into}: {held:,.2f} -> {held - residual_eff:,.2f} "
                f"(orange-flagged, in the report). Check {check} now zero.")

    def t_trace_error(self, args):
        """FOLLOW THE ERROR TO ITS CAUSE (the run-203 investigation,
        taught): an erroring cell is a symptom — walk its precedents to
        the deepest cell that fails (or the zero divisor), then ask the
        provenance questions: what did that cell hold BEFORE the run
        (the archive is the before-picture), what does it hold now, is
        it flagged, did this run write it. A wrong unflagged write has
        nowhere to hide from this walk."""
        ref = str(args.get("cell", ""))
        cr = self._cell_ref(ref)
        if not cr:
            return f"MISS: cell ref '{ref}' unparseable — use \"Final!AJ99\""
        sheet, col, row = cr
        ev = Evaluator(self.wb)
        try:
            v = ev.cell(sheet, f"{col}{row}")
            return (f"{sheet}!{col}{row} evaluates fine ({v:,.2f}) — "
                    "no error to trace")
        except Exception as e:
            err = str(e).splitlines()[0][:60]
        chain = [f"{sheet}!{col}{row}: {err}"]
        cur = (sheet, f"{col}{row}")
        for _hop in range(30):
            sh, coord = cur
            f = self.wb[sh][coord].value if sh in self.wb.sheetnames else None
            if not (isinstance(f, str) and f.startswith("=")):
                break
            nxt = None
            zero_div = None
            for m in re.finditer(
                    r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?"
                    r"([A-Z]{1,3})(\d+)(?::([A-Z]{1,3})(\d+))?",
                    f.replace("$", "")):
                psh = (m.group(1) or m.group(2) or sh).strip()
                if psh not in self.wb.sheetnames:
                    continue
                # ranges expand row-wise: the failing cell is often
                # INSIDE a SUM range, not at its endpoints
                r1, r2 = int(m.group(4)), int(m.group(6) or m.group(4))
                probes = [f"{m.group(3)}{rr}"
                          for rr in range(min(r1, r2),
                                          min(max(r1, r2), min(r1, r2) + 50)
                                          + 1)]
                for pco in probes:
                    try:
                        pv = ev.cell(psh, pco)
                    except Exception:
                        nxt = (psh, pco)  # a precedent errors: go deeper
                        break
                if nxt:
                    break
                pco = probes[0]
                pv0 = None
                try:
                    pv0 = ev.cell(psh, pco)
                except Exception:
                    pass
                pv = pv0
                # a zero precedent that the formula divides by
                if pv == 0 and re.search(
                        r"/\s*(?:'" + re.escape(psh) + r"'!|"
                        + re.escape(psh) + r"!)?\$?"
                        + m.group(3) + r"\$?" + m.group(4)
                        + r"(?![0-9])", f.replace("$", "")):
                    zero_div = (psh, pco)
            if nxt is not None:
                chain.append(f"  <- {nxt[0]}!{nxt[1]} also fails")
                cur = nxt
                continue
            if zero_div is not None:
                sh2, co2 = zero_div
                # follow the zero through view chains (=AI125) to the
                # cell where the zero is actually TYPED — provenance
                # belongs to the hardcode, not the mirror
                for _f in range(6):
                    v2 = self.wb[sh2][co2].value
                    if not (isinstance(v2, str) and v2.startswith("=")):
                        break
                    refs2 = re.findall(
                        r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?"
                        r"([A-Z]{1,3})(\d+)", v2.replace("$", ""))
                    if len(refs2) != 1:
                        break
                    q = refs2[0]
                    qsh = (q[0] or q[1] or sh2).strip()
                    if qsh not in self.wb.sheetnames:
                        break
                    chain.append(f"  zero flows from {sh2}!{co2} ({v2})")
                    sh2, co2 = qsh, f"{q[2]}{q[3]}"
                cell = self.wb[sh2][co2]
                held = cell.value
                pcol = prior_column(self.spec, sh2, self.ty)
                r2 = "".join(c for c in co2 if c.isdigit())
                prior = (self.wb[sh2][f"{pcol}{r2}"].value if pcol else None)
                pre = "?"
                path = getattr(self, "pre_path", None)
                if path:
                    if getattr(self, "_pre_wb", None) is None:
                        import openpyxl
                        self._pre_wb = openpyxl.load_workbook(path)
                    if sh2 in self._pre_wb.sheetnames:
                        pre = self._pre_wb[sh2][co2].value
                flagged = f"{sh2}!{co2}" in self.writer.log["flags"]
                written = f"{sh2}!{co2}" in self.writer.log.get("written", [])
                note = (str(cell.comment.text)[:80] if cell.comment else "")
                chain.append(
                    f"  CAUSE: {sh2}!{co2} = {held!r} and the formula "
                    f"divides by it. BEFORE the run it held {pre!r}; "
                    f"prior actual {prior!r}; "
                    f"{'WRITTEN BY THIS RUN' if written else 'not written by this run'}, "
                    f"{'flagged' if flagged else 'UNFLAGGED'}"
                    + (f"; note: {note}" if note else "")
                    + ". Fix the cause (set_input the true value with "
                    "citation, or restore the pre-run value), then rescore.")
                break
            chain.append("  (no deeper failing precedent found — inspect "
                         "this cell's own formula with trace_cell)")
            break
        if len(chain) > 9:                # collapse the middle of a long walk
            chain = chain[:4] + [f"  ... ({len(chain) - 8} hops) ..."] \
                + chain[-4:]
        return "\n".join(chain)

    def t_probe(self, args):
        """THE EXPERIMENT (owner ruling 2026-09-01: think like Fable —
        hypothesis, experiment, measured proof). Temporarily set a cell
        to a value (default 0), re-measure EVERY failing check row in
        every year, restore the cell, and report which checks moved.
        Costless and reversible — the by-hand method that found the
        forecast leak ('zeroing this row moves the 2026 check to 0')."""
        ref = str(args.get("cell", ""))
        cr = self._cell_ref(ref, default_tcol=False)
        if not cr:
            return f"MISS: cell ref '{ref}' unparseable — use \"Final!AJ107\""
        sh, col, row = cr
        if sh not in self.wb.sheetnames:
            return f"MISS: no sheet '{sh}'"
        try:
            probe_val = float(args.get("value", 0))
        except (TypeError, ValueError):
            return "MISS: numeric value required"
        from .checks import year_columns as _yc
        before = {}
        ev = Evaluator(self.wb)
        for c in (self.spec.get("check_rows") or []):
            for y, ycol in sorted(_yc(self.spec, c["sheet"]).items()):
                try:
                    v = ev.cell(c["sheet"], f"{ycol}{int(c['row'])}")
                except Exception:
                    continue
                if isinstance(v, (int, float)) and abs(v) > 1:
                    before[(c["sheet"], int(c["row"]), y)] = v
        old = self.wb[sh][f"{col}{row}"].value
        self.wb[sh][f"{col}{row}"] = probe_val
        out = [f"PROBE {sh}!{col}{row} = {probe_val:g} (was "
               f"{str(old)[:26]!r}) — failing checks respond:"]
        ev2 = Evaluator(self.wb)
        moved = 0
        for (csh, crow, y), was in sorted(before.items()):
            try:
                now = ev2.cell(csh, f"{_yc(self.spec, csh)[y]}{crow}")
            except Exception:
                now = None
            if isinstance(now, (int, float)) and abs(now - was) > 1:
                moved += 1
                closes = " <== CLOSES" if abs(now) < 1 else ""
                out.append(f"  {csh}!{crow} ({y}): {was:,.1f} -> "
                           f"{now:,.1f}{closes}")
        self.wb[sh][f"{col}{row}"] = old      # a probe never commits
        if moved == 0:
            out.append("  (none — this cell does not drive the failing "
                       "checks)")
        else:
            out.append("  If a hold PROVES the fix and the cell is a "
                       "roll artifact, hold_forecast it (owner's law: "
                       "balance outranks the freeze list).")
        return "\n".join(out)

    def t_hold_forecast(self, args):
        """THE SANCTIONED HOLD (owner ruling 2026-09-01): when a probe
        proves a rolled-forward FORECAST cell un-balances the model,
        hold it at a value (default 0) — orange, noted, verdicted —
        even though no freeze rule names it: balancing the model is the
        key goal. Transactional: kept only if the failing checks
        actually improve."""
        ref = str(args.get("cell", ""))
        why = str(args.get("why", ""))
        cr = self._cell_ref(ref, default_tcol=False)
        if not cr:
            return f"MISS: cell ref '{ref}' unparseable"
        sh, col, row = cr
        from .checks import forecast_columns as _fc
        if col not in (_fc(self.spec, sh, self.ty) or []):
            return (f"MISS: {sh}!{col}{row} is not a forecast-column "
                    "cell — actual-column errors are fixed with "
                    "set_input/rewrite_constants, never held")
        if len(why) < 20:
            return ("MISS: say what your probe proved (which check "
                    "closed) — a hold without proof is a patch")
        try:
            hold_val = float(args.get("value", 0))
        except (TypeError, ValueError):
            return "MISS: numeric value required"
        fails0 = self._failing_target_checks()
        # forecast checks too
        ev = Evaluator(self.wb)
        from .checks import year_columns as _yc
        def _all_fail_mass():
            m = 0.0
            for c in (self.spec.get("check_rows") or []):
                for y, ycol in _yc(self.spec, c["sheet"]).items():
                    try:
                        v = Evaluator(self.wb).cell(
                            c["sheet"], f"{ycol}{int(c['row'])}")
                    except Exception:
                        continue
                    if isinstance(v, (int, float)):
                        m += abs(v)
            return m
        mass0 = _all_fail_mass()
        old = self.wb[sh][f"{col}{row}"].value
        self.wb[sh][f"{col}{row}"] = hold_val
        mass1 = _all_fail_mass()
        if mass1 >= mass0 - 1:
            self.wb[sh][f"{col}{row}"] = old
            return (f"REVERTED: holding {sh}!{col}{row} did not improve "
                    f"the checks (total residual {mass0:,.1f} -> "
                    f"{mass1:,.1f}) — the probe did not prove this cell")
        from openpyxl.comments import Comment
        cell = self.wb[sh][f"{col}{row}"]
        cell.fill = self.writer.fills["orange"]
        cell.comment = Comment(
            f"HELD BY THE AGENT (balance outranks the freeze list, "
            f"owner 2026-09-01): was {str(old)[:60]}; probe proved this "
            f"rolled cell un-balances the forecast (total residual "
            f"{mass0:,.1f} -> {mass1:,.1f}). {why[:200]}",
            "Model Update Agent")
        self.writer.log["flags"].append(f"{sh}!{col}{row}")
        self.writer.log.setdefault("frozen", []).append(
            f"{sh}!{col}{row}: held at {hold_val:g} — was {str(old)[:40]} "
            f"(agent hold, probe-proven)")
        self.writer.log.setdefault("verdicts", []).append(
            f"{sh}!{col}{row}: ERROR_FIXED — roll artifact held at "
            f"{hold_val:g}; checks improved {mass0:,.1f} -> {mass1:,.1f}")
        return (f"HELD {sh}!{col}{row} at {hold_val:g} (orange, "
                f"reported): total check residual {mass0:,.1f} -> "
                f"{mass1:,.1f}")

    def t_forecast_diff(self, args):
        """THE BY-HAND METHOD for broken forecast years (owner ruling
        2026-09-01: the forecast is the analyst's — never mutate it;
        every forecast symptom has an ACTUAL-column cause). Evaluates a
        forecast year row-by-row against the analyst's PRE-UPDATE model
        and lists the biggest movers with the actual-column cells their
        formulas consume — the cause candidates."""
        sheet = str(args.get("sheet") or "")
        path = getattr(self, "pre_path", None)
        if not path:
            return "MISS: no pre-update archive available"
        if getattr(self, "_pre_wb", None) is None:
            import openpyxl
            self._pre_wb = openpyxl.load_workbook(path)
        from .checks import forecast_columns
        evN, evP = Evaluator(self.wb), Evaluator(self._pre_wb)
        sheets = [sheet] if sheet else list(
            (self.spec.get("year_axis") or {}))
        movers = []
        for sh in sheets:
            if sh not in self.wb.sheetnames \
                    or sh not in self._pre_wb.sheetnames:
                continue
            fc = forecast_columns(self.spec, sh, self.ty)
            if not fc:
                continue
            ws = self.wb[sh]
            for r in range(1, min(ws.max_row, 300) + 1):
                f = ws[f"{fc[0]}{r}"].value
                if not (isinstance(f, str) and f.startswith("=")):
                    continue
                try:
                    vn = evN.cell(sh, f"{fc[0]}{r}")
                    vp = evP.cell(sh, f"{fc[0]}{r}")
                except Exception:
                    continue
                if isinstance(vn, (int, float)) \
                        and isinstance(vp, (int, float)) \
                        and abs(vn - vp) > max(200.0, abs(vp) * 0.5):
                    movers.append((abs(vn - vp), sh, r, vn, vp, f))
        if not movers:
            return ("forecast matches the analyst's pre-update model "
                    "everywhere material")
        out = ["FORECAST vs the analyst's own model (biggest moves; the "
               "cause of each is an ACTUAL-column input its formula "
               "consumes — fix the actual, never the forecast):"]
        tcols = {sh: self._tcol(sh) for sh in sheets}
        for _d, sh, r, vn, vp, f in sorted(movers, reverse=True)[:12]:
            causes = []
            for m in re.finditer(
                    r"(?:(?:'([^']+)'|([A-Za-z0-9_][A-Za-z0-9 _]*))!)?"
                    r"([A-Z]{1,3})(\d+)", str(f).replace("$", "")):
                csh = (m.group(1) or m.group(2) or sh).strip()
                if m.group(3) == tcols.get(csh) \
                        or m.group(3) == self._tcol(csh):
                    causes.append(f"{csh}!{m.group(3)}{m.group(4)}")
            out.append(f"  {sh}!{r}: now {vn:,.1f} vs analyst {vp:,.1f}"
                       + (f" — reads actuals {', '.join(causes[:4])}"
                          if causes else " — trace_cell it"))
        return "\n".join(out)

    def t_write_backout(self, args):
        """THE BACK-OUT, first-class (owner's rule: back-outs are
        FORMULAS, not hardcodes — the reader must trace how the number
        was made). Write a back-out FORMULA into a composite cell when
        the composition is justified by print: EVERY numeric literal in
        the formula must appear on the cited page's lines (that is the
        evidence), the why must cite the page, and the write is
        transactional (band + revert like set_input). Lands orange."""
        ref = str(args.get("cell", ""))
        formula = str(args.get("formula", ""))
        why = str(args.get("why", ""))
        cr = self._cell_ref(ref)
        if not cr:
            return f"MISS: cell ref '{ref}' unparseable"
        if not formula.startswith("="):
            return "MISS: a back-out is a FORMULA (starts with '=')"
        pm = re.search(r"p(?:age)?\.?\s*(\d+)", why, re.IGNORECASE)
        if not pm:
            return ("REFUSED: 'why' must cite the disclosure page — "
                    "no citation, no write")
        page = int(pm.group(1))
        from .composites import literals_of
        from .numerics import row_tol
        lits = [float(x) for x in literals_of(formula)]
        if not lits:
            return ("MISS: the formula carries no literals — use "
                    "set_input for plain values")
        page_nums = [n for it in self.ledger.items
                     if it.page == page for n in it.nums]
        for v in lits:
            tol = row_tol(abs(v), base=0.6 if abs(v) >= 100 else 0.01)
            if not any(abs(abs(n) - abs(v)) <= tol for n in page_nums):
                return (f"REFUSED: literal {v:g} is not printed on the "
                        f"cited page p{page} — every component of a "
                        "back-out must be a printed number")
        sheet, col, row = cr
        pcol = prior_column(self.spec, sheet, self.ty)
        ok = self.writer.write(
            sheet, f"{col}{row}", formula,
            prior_coord=f"{pcol}{row}" if pcol else None,
            flag="orange",
            note=(f"BACK-OUT (house rule: formulas, traceable): "
                  f"{formula} — every component printed on p{page}. "
                  f"{why[:250]}"))
        if not ok:
            return ("REFUSED by write guard (band/lock) — the back-out "
                    "value is out of world vs the prior")
        try:
            after = Evaluator(self.wb).cell(sheet, f"{col}{row}")
        except Exception:
            self.writer.log.setdefault("undo", [])
            return "REVERTED: the back-out does not evaluate"
        return f"WRITTEN {sheet}!{col}{row} = {formula} -> {after:,.2f} (orange)"

    def t_rewrite_constants(self, args):
        """THE CONSTANTS LAW, on demand (owner ruling 2026-08-31): a
        formula still embedding last year's literals (=4976+23) that
        evaluates to its own prior is rewritten from its own disclosed
        comparatives — every literal must tie a face line's comparative
        and all ties must agree, else the cell is untouched and the MISS
        names exactly what tied."""
        ref = str(args.get("cell") or args.get("row") or "")
        rr = self._row_ref(ref)
        if not rr:
            return (f"MISS: cell '{ref}' unparseable — use \"Final!65\" "
                    "(column letters tolerated)")
        from .composites import rewrite_cell
        ok, msg = rewrite_cell(self.wb, self.spec, self.ty, self.ledger,
                               self.writer, rr[0], rr[1])
        return ("REWRITTEN " + msg) if ok else ("MISS: " + msg)

    def t_apply_diff(self, args):
        """One action from finding to fixing: write the disclosed value for
        a DIFF/EMPTY/STALE row, evidence and citation auto-built, through
        the same transactional guards as set_input. The loop's primary
        repair move."""
        ref = str(args.get("row") or args.get("cell") or "")
        rr = self._row_ref(ref)
        if not rr:
            return f"MISS: row ref '{ref}' unparseable — use \"Model!49\" (column letters tolerated and ignored)"
        sheet, row = rr
        t = self.targets.get((sheet, row))
        if t is None:
            return f"MISS: {sheet}!{row} is not a census row"
        got = self._diff_value(t)
        if got is None:
            return (f"MISS: no unique prior-identity evidence for {sheet}!{row} "
                    "on a ratified face — use find_line + set_input with your "
                    "own citation, or flag it")
        dv, it, s = got
        tcol = self._tcol(sheet)
        why = f"p{it.page}: {it.doc} '{it.label[:40]}' (prior-identity tie)"
        return self.t_set_input({"cell": f"{sheet}!{tcol}{row}", "value": dv,
                                 "why": why})

    def t_set_input(self, args):
        ref = str(args.get("cell", ""))
        why = str(args.get("why", ""))
        cr = self._cell_ref(ref)
        if not cr:
            return f"MISS: cell ref '{ref}' unparseable — use \"Sheet!AI99\" (a bare row writes the target-year column)"
        if not re.search(r"p(?:age)?\.?\s*\d+", why, re.IGNORECASE):
            return ("REFUSED: 'why' must cite the disclosure page "
                    "(e.g. 'p102: ...') — no citation, no write")
        try:
            value = float(args.get("value"))
        except (TypeError, ValueError):
            return "MISS: numeric value required"
        sheet, col, row = cr
        if sheet not in self.wb.sheetnames:
            return f"MISS: no sheet '{sheet}'"
        # SEGMENT PRIOR DISCIPLINE (by-hand teaching #6, the run-204
        # wrong-column lesson: China's D&A was served Hong Kong's
        # number): a page cited for a row that has a known prior must
        # ALSO carry that prior somewhere — otherwise the write lands
        # RED, never clean. The row's own prior is the only proof you
        # read the right column.
        forced_flag = args.get("flag")
        pc0 = prior_column(self.spec, sheet, self.ty)
        pv0 = self.wb[sheet][f"{pc0}{row}"].value if pc0 else None
        if isinstance(pv0, str) and pv0.startswith("="):
            try:
                pv0 = Evaluator(self.wb).cell(sheet, f"{pc0}{row}")
            except Exception:
                pv0 = None
        corro = False
        if isinstance(pv0, (int, float)) and abs(pv0) >= 10:
            m_pg = re.search(r"p(?:age)?\.?\s*(\d+)", why, re.IGNORECASE)
            if m_pg:
                pg = int(m_pg.group(1))
                tol0 = row_tol(pv0, base=0.6 if abs(pv0) >= 100 else 0.01)
                for it in self.ledger.items:
                    if it.page != pg:
                        continue
                    if any(abs(abs(n) - abs(pv0)) <= tol0
                           for n in it.nums):
                        corro = True
                        break
            if not corro and not forced_flag:
                args = dict(args)
                args["flag"] = "red"
                args["why"] = (why + " [prior NOT corroborated on the "
                               "cited page — wrong-column risk, red]")
                why = args["why"]
        held = self.wb[sheet][f"{col}{row}"].value
        redirected = ""
        if isinstance(held, str) and held.startswith("="):
            # a single-reference view row redirects to the cell where the
            # number is actually typed (the legacy tool's own behavior);
            # composite designed formulas are refused — repair components
            from .writer import resolve_input_site
            pcol0 = prior_column(self.spec, sheet, self.ty)
            site = (resolve_input_site(self.wb, sheet, row, pcol0)
                    if pcol0 else None)
            if site is None or site == (sheet, row):
                return (f"REFUSED: {ref} is a designed formula ({held[:40]}) — "
                        "repair its COMPONENTS, never the total (trace_cell it)")
            s_sheet, s_row = site
            s_tcol = self._tcol(s_sheet)
            if not s_tcol:
                return (f"REFUSED: input site {s_sheet}!{s_row} has no target "
                        "column in the year axis")
            # the link may negate: re-sign to the SITE's own prior world
            row_pv = (self.targets.get((sheet, row)).prior_value
                      if (sheet, row) in self.targets else None)
            s_pcol = prior_column(self.spec, s_sheet, self.ty)
            site_pv = (self.wb[s_sheet][f"{s_pcol}{s_row}"].value
                       if s_pcol else None)
            if isinstance(row_pv, (int, float)) and row_pv != 0 \
                    and isinstance(site_pv, (int, float)) and site_pv != 0 \
                    and (row_pv < 0) != (site_pv < 0):
                value = -value
            redirected = f" (redirected from {ref} to its input cell)"
            sheet, col, row = s_sheet, s_tcol, s_row
            ref = f"{sheet}!{col}{row}"
            held = self.wb[sheet][f"{col}{row}"].value
        pcol = prior_column(self.spec, sheet, self.ty)
        # THE EVIDENCE LAW (run-7 autopsy): no write without a ledger row;
        # proven cells are protected; unproven values land red, never clean.
        from .writegate import (claimed_keys, claim_holders, find_evidence,
                                judge_write)
        pv_cell = (self.wb[sheet][f"{pcol}{row}"].value if pcol else None)
        evidence = find_evidence(self.ledger.items, value)
        holders = claim_holders(self.served)
        verdict, law_reason, forced_flag = judge_write(
            value, pv_cell if isinstance(pv_cell, (int, float)) else None,
            (sheet, row) in self.served, evidence,
            claimed_keys(self.served), holders)
        if verdict == "REFUSE" and args.get("card") == "component" \
                and "already holds a PROVEN value" in law_reason \
                and args.get("check"):
            # TWO READINGS -> THE BRAIN JUDGES, THE CHECK VERIFIES (owner
            # 2026-09-08: "hold both and judge which is better — that is
            # why we use a brain"). The cell holds a proven figure; the
            # component card showed the brain a second printed line and
            # what it does to the check; the brain chose it. Code's
            # verification: the named check must actually close or
            # improve. It lands RED with both readings in the note.
            rc2 = self._row_ref(str(args.get("check")))
            if rc2:
                c_sh, c_r = rc2
                c_col = self._tcol(c_sh)
                try:
                    r_before = Evaluator(self.wb).cell(c_sh, f"{c_col}{c_r}")
                except Exception:
                    r_before = None
                old_v = self.wb[sheet][f"{col}{row}"].value
                self.wb[sheet][f"{col}{row}"] = value
                try:
                    r_after = Evaluator(self.wb).cell(c_sh, f"{c_col}{c_r}")
                except Exception:
                    r_after = None
                self.wb[sheet][f"{col}{row}"] = old_v
                if isinstance(r_before, (int, float)) and isinstance(r_after, (int, float)) \
                        and abs(r_after) < abs(r_before) - 1.0:
                    pe_old = (self.served or {}).get((sheet, row)) or {}
                    verdict, forced_flag = "ALLOW_FLAGGED", "red"
                    law_reason = "two readings — the brain's choice, check-verified"
                    why = (f"TWO READINGS: held {held!r} ({str(pe_old.get('line') or pe_old.get('note') or 'proven read')[:50]}); "
                           f"the brain chose this line because {args.get('check')} moves "
                           f"{r_before:,.1f} -> {r_after:,.1f}. Please confirm. " + why)
        if verdict == "REFUSE":
            return "REFUSED by the evidence law: " + law_reason
        evicted = ""
        if verdict == "EVICT":
            # PROOF OUTRANKS ARRIVAL (run-227 autopsy): the unproven
            # holder(s) of this figure are reverted and red-flagged —
            # loud, never a silent double count — then the proven write
            # lands clean
            evicted = self._evict_claim(round(abs(value), 1), holders, ref)
            verdict = "ALLOW"
        proven = verdict == "ALLOW"
        flag = "red" if (forced_flag == "red" or args.get("flag")) else None
        if forced_flag == "red":
            why = "UNPROVEN (no prior tie) — " + why
        before_card = self._card()
        before_fails = {c["name"] for c in before_card["checks"]
                        if c["status"] == "FAIL"}
        before_gaps = {c["name"]: abs(c["got"] - c["expect"])
                       for c in before_card["checks"]
                       if c["status"] == "FAIL"
                       and isinstance(c.get("got"), (int, float))
                       and isinstance(c.get("expect"), (int, float))}
        ok = self.writer.write(sheet, f"{col}{row}", value,
                               prior_coord=f"{pcol}{row}" if pcol else None,
                               note=f"objective loop: {why[:300]}",
                               flag=flag)
        if not ok:
            reason = (self.writer.log["band_refused"][-1]
                      if self.writer.log["band_refused"] else
                      self.writer.log["lock_refused"][-1]
                      if self.writer.log["lock_refused"] else "guard refusal")
            return f"REFUSED by write guard: {reason}"
        after_card = self._card()
        after_fails = {c["name"] for c in after_card["checks"]
                       if c["status"] == "FAIL"}
        # THE RUN-39 LAW, as WRITTEN: revert what breaks previously-
        # PASSING checks. Worsening an already-failing check is
        # allowed for a PRIOR-CORROBORATED cited write — truth arrives
        # in steps (the RE fix must land before the PCS fold closes
        # the residual; per-write reverts made multi-step corrections
        # impossible — the Fable-drive finding).
        worsened = [] if corro else sorted(
            c["name"] for c in after_card["checks"]
            if c["status"] == "FAIL"
            and isinstance(c.get("got"), (int, float))
            and isinstance(c.get("expect"), (int, float))
            and c["name"] in before_gaps
            and abs(c["got"] - c["expect"]) > before_gaps[c["name"]] + 1.0)
        broke = sorted(after_fails - before_fails) + worsened
        if broke:
            self.writer.write(sheet, f"{col}{row}", held,
                              prior_coord=f"{pcol}{row}" if pcol else None,
                              force_lock=True, trusted=True,
                              note="objective loop: REVERTED (broke checks)")
            return (f"REVERTED: the write broke previously-passing checks "
                    f"{broke[:4]} — the target cell is wrong, not the value; "
                    "trace_cell / statement_diff to find the right row")
        self.served[(sheet, row)] = {"value": value, "status": "OK",
                                     "conf": 4 if proven else 3,
                                     "flag": flag,
                                     "homed": True,
                                     "home": (sheet, f"{col}{row}"),
                                     "page": None,
                                     "line": why[:60],
                                     "note": f"objective loop: {why[:120]}"}
        fixed = sorted(before_fails - after_fails)
        return ("WRITTEN" + redirected + evicted
                + (f"; checks now passing: {fixed[:4]}" if fixed else ""))

    def _evict_claim(self, key, holders, new_ref):
        """PROOF OUTRANKS ARRIVAL (run-227 autopsy): revert every UNPROVEN
        home of `key` to what the cell held before its serve, red-flag it
        with the re-homing note, and release the claim. Returns a log
        fragment. A home whose pre-serve value cannot be found in the
        writes ledger is flagged but left in place (loud, never silent)."""
        from .writegate import is_proven
        out = []
        for cell, entry in holders.get(key, []):
            if is_proven(entry):
                continue
            s, r = cell
            home = entry.get("home")
            if not home:
                tcol = self._tcol(s)
                home = (s, f"{tcol}{r}") if tcol else None
            reverted = False
            if home:
                h_sheet, h_coord = home
                found = False
                old = None
                for w_sheet, w_coord, w_old, _w_new in self.writer.log.get(
                        "writes_all", []):
                    if w_sheet == h_sheet and w_coord == h_coord:
                        old, found = w_old, True   # FIRST write = pre-serve
                        break
                if found:
                    self.writer.write(h_sheet, h_coord, old,
                                      force_lock=True, trusted=True,
                                      note=("objective loop: EVICTED — "
                                            f"figure {key:,.1f} re-homed "
                                            f"to {new_ref} (proven: its "
                                            "row ties the prior); this "
                                            "unproven read reverted"))
                    reverted = True
            self.TOOLS["flag_cell"](self, {
                "cell": f"{s}!{r}",
                "why": (f"EVICTED: figure {key:,.1f} re-homed to {new_ref} "
                        "(proven — its evidence row ties the prior); this "
                        "cell's unproven claim "
                        + ("reverted to its pre-serve value"
                           if reverted else "left in place — no pre-serve "
                           "value on record")
                        + " — analyst to confirm")})
            self.served.pop(cell, None)
            out.append(f"{s}!{r}" + ("" if reverted else " (not reverted)"))
        return (f"; EVICTED unproven home(s) of {key:,.1f}: {out}"
                if out else "")

    def t_rollover_revert(self, args):
        """ROLLOVER JUDGMENT (owner teaching 2026-09-03): the brain judged
        a changed actual-year input WRONG because the probe showed it
        drives an out-of-proportion forecast move. Restore the analyst's
        pre-update value, red-flag the cell with the reasoning, record
        the verdict on the forecast row."""
        cr = self._cell_ref(str(args.get("cell", "")), default_tcol=False)
        if not cr:
            return "MISS: cell ref unparseable"
        sheet, col, row = cr
        old = args.get("old")
        if old is None:
            return "MISS: no pre-update value on record"
        ref = f"{sheet}!{col}{row}"
        cur = self.wb[sheet][f"{col}{row}"].value
        # PROVEN IS PROTECTED (run-229 autopsy): a proven actual is never
        # reverted to an estimate to fix a downstream oddity
        from .rollover import input_is_proven
        if input_is_proven(self.served, sheet, f"{col}{row}", cur, (), self.wb,
                           old=old):
            return (f"REFUSED: {ref} is a PROVEN actual (its evidence ties the "
                    "prior) — never reverted; if the forecast is wrong, its own "
                    "driver or a frozen assumption is stale: flag the forecast "
                    "(not_sure) for the analyst")
        ok = self.writer.write(sheet, f"{col}{row}", old, force_lock=True,
                               trusted=True, flag="red",
                               note=f"objective loop: {str(args.get('why'))[:280]}")
        if not ok:
            return f"REFUSED by write guard: {ref}"
        self.served.pop((sheet, int(row)), None)
        self.TOOLS["flag_cell"](self, {
            "cell": f"{sheet}!{row}",
            "why": (f"ROLLOVER: {str(args.get('why'))[:200]} — held at the "
                    "analyst's pre-update value; analyst to confirm")})
        fc = str(args.get("forecast") or "")
        if fc:
            self.TOOLS["verdict"](self, {
                "items": [fc], "verdict": "ERROR_FIXED",
                "why": (f"rollover card: {ref} {str(cur)[:16]} judged wrong "
                        f"and restored to {str(old)[:16]} (red)")})
        return f"REVERTED {ref}: {str(cur)[:16]} -> {str(old)[:16]} (red, analyst to confirm)"

    def t_rollover_flag(self, args):
        """ROLLOVER: cannot tell — flag the forecast row and record SUSPICIOUS."""
        fc = str(args.get("forecast") or "")
        cr = self._cell_ref(fc, default_tcol=False) if fc else None
        if cr:
            from .checks import forecast_columns
            fcols = forecast_columns(self.spec, cr[0], self.ty)
            if fcols:
                self.TOOLS["flag_cell"](self, {
                    "cell": f"{cr[0]}!{fcols[0]}{cr[2]}",
                    "why": str(args.get("why") or "rollover check")[:200]})
        self.TOOLS["verdict"](self, {
            "items": [fc], "verdict": "SUSPICIOUS",
            "why": "rollover card: strange move left for the analyst (cannot tell)"})
        return f"FLAGGED {fc} for the analyst"

    def t_flag_cell(self, args):
        ref = str(args.get("cell", ""))
        cr = self._cell_ref(ref)
        if not cr:
            return f"MISS: cell ref '{ref}' unparseable — use \"Sheet!AI99\" (a bare row flags the target-year column)"
        sheet, coord = cr[0], f"{cr[1]}{cr[2]}"
        if sheet not in self.wb.sheetnames:
            return f"MISS: no sheet '{sheet}'"
        cell = self.wb[sheet][coord]
        if self.writer.in_forecast(sheet, coord):
            # forecast cells are never painted (owner 2026-09-07): the
            # row is watch-listed for the analyst's desk instead
            self.writer.watch(sheet, coord,
                              str(args.get("why", "flagged for review")))
            return "WATCH-LISTED (a forecast cell is never painted; the cause belongs in the actual column)"
        self.writer.log["flags"].append(f"{sheet}!{coord}")
        from openpyxl.comments import Comment
        cell.fill = self.writer.fills["red"]
        cell.comment = Comment(str(args.get("why", "flagged for review"))[:400],
                               "Model Update Agent")
        return "FLAGGED"

    def t_verdict(self, args):
        """SENSE-CHECK VERDICT (owner ruling 2026-08-31): a tripwire — a
        sign-flipped forecast or other loud anomaly — is a mistake
        DETECTOR. Investigate once (trace_cell), then adjudicate:
        ERROR_FIXED (you found and repaired the cause), JUSTIFIED (the
        disclosure supports it — say why), or SUSPICIOUS (unresolved —
        the analyst should look). Every verdict prints on _REPORT."""
        items = args.get("items") if isinstance(args.get("items"), list) \
            else [args.get("item") or args.get("cell") or ""]
        v = str(args.get("verdict") or "").upper().replace("-", "_").replace(" ", "_")
        why = str(args.get("why") or "").strip()
        if v not in ("JUSTIFIED", "ERROR_FIXED", "SUSPICIOUS"):
            return ('MISS: need {"item": "Sheet!AJ39"} (or {"items": '
                    '[...]}) with "verdict": '
                    '"JUSTIFIED|ERROR_FIXED|SUSPICIOUS", "why": ...')
        if len(why) < 15:
            return ("MISS: a verdict without its reasoning is not "
                    "adjudication — say what you traced and found")
        keys = []
        for item in items:
            cr = self._cell_ref(str(item), default_tcol=False)
            if cr:
                keys.append(f"{cr[0]}!{cr[1]}{cr[2]}")
                continue
            rr = self._row_ref(str(item))
            if not rr:
                return (f"MISS: item '{item}' unparseable — use "
                        "\"Sheet!AJ39\"")
            keys.append(f"{rr[0]}!{rr[1]}")
        if v == "ERROR_FIXED":
            # THE VERDICT RE-VERIFICATION LAW (2026-09-01: the Fable-drive
            # itself mass-approved 36 tripwires as fixed while forecast
            # profits were still negative — balance held, truth did not).
            # "Fixed" is not a claim, it is a state: code re-checks the
            # cell and rejects the verdict while the absurdity persists.
            trips = {(s, c, r): (pv0, tv0)
                     for (s, c, r, _f, pv0, tv0)
                     in getattr(self, "tripwires", []) or []}
            ev = Evaluator(self.wb)
            still = []
            for key in keys:
                mm = re.match(r"^([^!]+)!([A-Z]{1,3})(\d+)$", key)
                if not mm:
                    continue
                pt = trips.get((mm.group(1), mm.group(2),
                                int(mm.group(3))))
                if not pt:
                    continue
                try:
                    fv = ev.cell(mm.group(1),
                                 f"{mm.group(2)}{mm.group(3)}")
                except Exception:
                    continue
                if isinstance(fv, (int, float)) and fv < 0 \
                        and pt[0] > 0 and pt[1] > 0:
                    still.append(f"{key} still computes {fv:,.1f} where "
                                 f"actuals are {pt[0]:,.1f} -> "
                                 f"{pt[1]:,.1f}")
            if still:
                return ("REJECTED: ERROR_FIXED requires the error to be "
                        "GONE — code re-checked and these still compute "
                        "sign-absurd values: " + "; ".join(still[:6])
                        + ". Fix the actual-column cause first, or "
                        "verdict JUSTIFIED/SUSPICIOUS with reasons")
        for key in keys:
            self.writer.log.setdefault("verdicts", []).append(
                f"{key}: {v} — {why[:250]}")
        return f"VERDICT recorded for {', '.join(keys)}: {v}"

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
        # tier law: load-bearing reds are the loop's mandatory work;
        # tier-3 is swept automatically and must never be searched
        lb = getattr(self, "load_bearing", None)
        out = []
        for f in self.writer.log["flags"][-60:]:
            m = re.match(r"^(.+)![A-Z]+([0-9]+)$", f)
            if lb is not None and m:
                tag = ("LOAD-BEARING — yours"
                       if (m.group(1), int(m.group(2))) in lb
                       else "tier-3 — swept, do not search")
                out.append(f"{f}  [{tag}]")
            else:
                out.append(f)
        return "\n".join(out) or "(no flags)"

    def t_finish(self, args):
        self.finished = str(args.get("summary", ""))[:800]
        return "finished"

    # -- the loop ------------------------------------------------------------

    def _forecast_cols(self, sheet):
        from .checks import forecast_columns
        return forecast_columns(self.spec, sheet, self.ty)

    def _is_forecast_action(self, name, args):
        if name in ("forecast_audit", "place_flow"):
            return True
        if name not in ("trace_cell", "diagnose_balance", "plug_residual",
                        "set_input", "statement_diff"):
            return False
        blob = json.dumps(args, ensure_ascii=False)
        # tripwire investigation is MANDATED sense-check work (owner
        # ruling 2026-08-31), not the balance-gap re-tracing the
        # walk-away window exists to stop — it never counts against it
        for (sheet, col, r, _fv, _pv, _tv) in getattr(self, "tripwires", []):
            if f"{sheet}!{col}{r}" in blob:
                return False
        for sheet in (self.spec.get("year_axis") or {}):
            for col in self._forecast_cols(sheet):
                if re.search("[!\\s\"']" + col + "\\$?\\d", blob):
                    return True
        return False

    def _fc_window_closed(self):
        # THE WALK-AWAY RULE, MECHANIZED (runs 17-18: the engine burned
        # 80-90% of its budget re-tracing a forecast gap the end-of-run
        # plug was always going to close, and never reached the reds).
        return self._fc_spend >= max(10, self.budget0 // 4)

    def _bs_rows(self, sheet):
        ws = self.wb[sheet]
        rows, inside = [], False
        for r in range(1, min(ws.max_row, 250) + 1):
            lab = ""
            for c in range(1, 7):
                v = ws.cell(row=r, column=c).value
                if isinstance(v, str) and v.strip():
                    lab = v.strip()
                    break
            if re.search(r"balance\s*sheet", lab, re.IGNORECASE):
                inside = True
                continue
            if inside:
                if re.match(r"^check\b", lab, re.IGNORECASE):
                    break
                if lab:
                    rows.append((r, lab))
        return rows

    def t_forecast_audit(self, args):
        """The gap and the BS movements per failing forecast year — the
        evidence for place_flow attribution."""
        from .forecast_balance import audit
        sheet = str(args.get("sheet") or "Model")
        checks = [c for c in (self.spec.get("check_rows") or [])
                  if c.get("sheet") == sheet]
        if not checks or sheet not in self.wb.sheetnames:
            return "MISS: no check row declared for that sheet"
        tcol = self._tcol(sheet)
        cols = [tcol] + self._forecast_cols(sheet)
        ev = Evaluator(self.wb)
        rep = audit(self.wb, lambda s, cd: ev.cell(s, cd), sheet,
                    checks[0]["row"], self._bs_rows(sheet), cols)
        rep = [y for y in rep if y["col"] != tcol]
        if not rep:
            return "all forecast years TIE — nothing to attribute"
        out = []
        for y in rep:
            out.append(f"{y['col']}: gap {y['gap']:+,.1f} — biggest BS "
                       "movements vs the previous column:")
            for m in y["moves"][:12]:
                out.append(f"  r{m['row']} {m['label'][:36]}: "
                           f"{m['delta']:+,.1f}")
        out.append("Attribute each movement that has no cash-flow "
                   "counterpart with place_flow {bs_row, cf_row, col}; "
                   "the residue is auto-plugged at the end (last resort).")
        return "\n".join(out)

    def t_place_flow(self, args):
        """Attribution write: ONE BS row's movement lands in ONE designed
        CF input row as a traceable orange formula."""
        from .forecast_balance import place_flow
        sheet = str(args.get("sheet") or "Model")
        try:
            bs_row = int(args.get("bs_row"))
            cf_row = int(args.get("cf_row"))
        except (TypeError, ValueError):
            return 'MISS: need {"bs_row": int, "cf_row": int, "col": "V"}'
        col = str(args.get("col") or "")
        fcols = self._forecast_cols(sheet)
        if col not in fcols:
            return (f"MISS: col must be a forecast column {fcols} — "
                    "actual years are never re-wired")
        from openpyxl.utils import (column_index_from_string,
                                    get_column_letter)
        chain = [self._tcol(sheet)] + fcols
        prior = chain[chain.index(col) - 1]
        checks = [c for c in (self.spec.get("check_rows") or [])
                  if c.get("sheet") == sheet]
        held = self.wb[sheet][f"{col}{cf_row}"].value
        g0 = None
        if checks:
            try:
                g0 = Evaluator(self.wb).cell(sheet,
                                             f"{col}{checks[0]['row']}")
            except Exception:
                g0 = None
        f, err = place_flow(self.wb, self.writer, sheet, bs_row, cf_row,
                            col, prior)
        if err:
            return err
        # the placement laws of set_input apply here too (run-16 pin):
        # a placement that opens a CYCLE or makes the year's gap WORSE
        # is reverted on the spot
        ev2 = Evaluator(self.wb)
        g1 = None
        if checks:
            try:
                g1 = ev2.cell(sheet, f"{col}{checks[0]['row']}")
            except Exception:
                g1 = None
        why = None
        if ev2.cycles:
            why = ("it created a CIRCULAR REFERENCE — that row resolves "
                   "through the cash chain; attribute the underlying "
                   "balance-sheet lines instead")
        elif (isinstance(g0, (int, float)) and isinstance(g1, (int, float))
                and abs(g1) > abs(g0) + 1.0):
            why = (f"it made the {col} gap WORSE ({g0:+,.1f} -> "
                   f"{g1:+,.1f}) — wrong sign or wrong row")
        elif g1 is None and g0 is not None:
            why = "the check no longer evaluates"
        if why:
            self.wb[sheet][f"{col}{cf_row}"] = held
            self.writer.log["flags"] = [
                x for x in self.writer.log["flags"]
                if x != f"{sheet}!{col}{cf_row}"]
            return f"REVERTED: {why}"
        gap = (f" — {col} check now {g1:+,.1f}"
               if isinstance(g1, (int, float)) else "")
        return f"PLACED {f} into {sheet}!{col}{cf_row} (orange){gap}"

    TOOLS = {"rescore": t_rescore, "trace_cell": t_trace_cell,
             "forecast_audit": t_forecast_audit, "place_flow": t_place_flow,
             "find_line": t_find_line, "statement_diff": t_statement_diff,
             "trace_serve": t_trace_serve,
             "apply_diff": t_apply_diff, "diagnose_balance": t_diagnose_balance,
             "plug_residual": t_plug_residual,
             "rewrite_constants": t_rewrite_constants,
             "write_backout": t_write_backout,
             "trace_error": t_trace_error,
             "forecast_diff": t_forecast_diff,
             "probe": t_probe, "hold_forecast": t_hold_forecast,
             "forecast_diff": t_forecast_diff,
             "set_input": t_set_input, "flag_cell": t_flag_cell,
             "rollover_revert": t_rollover_revert,
             "rollover_flag": t_rollover_flag,
             "verdict": t_verdict,
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
            # A LOOK ALREADY TAKEN TEACHES NOTHING UNTIL THE WORLD
            # CHANGES (run-17: 17 forecast_audits + 12 diagnose_balances
            # on unchanged state burned the budget). State-view tools
            # repeat freely only after a write; bookkeeping tools always.
            if name in ("rescore", "diagnose_balance", "statement_diff",
                        "forecast_audit", "list_flags"):
                fingerprint += f"|w{len(self.writer.log['written'])}"
            if name not in ("note", "todo", "verdict", "finish") \
                    and fingerprint in getattr(self, "_done", set()):
                result = ("REPEAT: you already ran exactly this action — the "
                          "result has not changed. Take a DIFFERENT action "
                          "(your history shows what you learned).")
            elif self._is_forecast_action(name, args) \
                    and self._fc_window_closed():
                result = ("ATTRIBUTION WINDOW CLOSED (a quarter of your "
                          "budget went to forecast work — the walk-away "
                          "rule). Any remaining forecast residue is the "
                          "end-of-run plug's job and is HANDLED. Every "
                          "remaining action belongs to the RED cells: "
                          "list_flags, then serve or adjudicate each.")
            else:
                self._done = getattr(self, "_done", set())
                self._done.add(fingerprint)
                if self._is_forecast_action(name, args):
                    self._fc_spend += 1
                if name == "trace_cell" and any(
                        f"{s}!{c}{r}" in json.dumps(args, ensure_ascii=False)
                        for s, c, r, *_ in getattr(self, "tripwires", [])):
                    self._trip_spend = getattr(self, "_trip_spend", 0) + 1
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


def terminal_ladder(loop, log):
    """The referee's last rung (owner ruling: 'if truly unsolvable —
    back out, mark, still deliver'; a balanced model with a flagged
    plug beats an unbalanced model). Runs AFTER the loop. For each
    target-year check still failing: apply any remaining GUILTY
    evidence diffs, then plug the exact residual into the largest
    eligible numeric site — orange (red if wild), noted, reported.
    Deterministic; the loop had every chance to do better first.
    -> number of checks closed."""
    closed = 0
    for sheet, row, resid in loop._failing_target_checks():
        diag = loop.t_diagnose_balance({"check": f"{sheet}!{row}"})
        for g in list(re.finditer(r"GUILTY (\S+)!(\d+)", diag))[:5]:
            r = loop.t_apply_diff({"row": f"{g.group(1)}!{g.group(2)}"})
            log(f"[run] terminal ladder: apply_diff {g.group(1)}!"
                f"{g.group(2)} -> {str(r).splitlines()[0][:90]}")
        still = [x for x in loop._failing_target_checks()
                 if (x[0], x[1]) == (sheet, row)]
        if not still:
            closed += 1
            log(f"[run] terminal ladder: {sheet}!{row} closed by "
                "evidence diffs alone")
            continue
        # THE PAIRED DIFF (DFE Driver!139, 2026-09-02: two GUILTY cells
        # form a compensating pair — either lone write breaks the check
        # and reverts; applied TOGETHER they close it. The analyst
        # applies the batch, then judges. Transactional as a batch.)
        gl = list(re.finditer(r"GUILTY (\S+)!(\d+)", diag))[:5]
        if len(gl) >= 2:
            batch, olds = [], []
            for g in gl:
                sh2, r2 = g.group(1), int(g.group(2))
                t2 = loop.targets.get((sh2, r2))
                got = loop._diff_value(t2) if t2 is not None else None
                tc2 = loop._tcol(sh2)
                if got is None or not tc2:
                    continue
                dv, it2, _s2 = got
                cur2 = loop.wb[sh2][f"{tc2}{r2}"].value
                if not isinstance(cur2, (int, float)):
                    continue
                sign = -1.0 if (isinstance(cur2, (int, float))
                                and cur2 < 0 < dv) else 1.0
                batch.append((sh2, f"{tc2}{r2}", sign * dv, it2))
                olds.append((sh2, f"{tc2}{r2}", cur2))
            if len(batch) >= 2:
                before = abs(still[0][2])
                for sh2, coord2, dv2, _it2 in batch:
                    loop.wb[sh2][coord2] = dv2
                after = None
                try:
                    after = Evaluator(loop.wb).cell(
                        sheet, f"{loop._tcol(sheet)}{row}")
                except Exception:
                    pass
                if isinstance(after, (int, float)) \
                        and abs(after) < before - 1.0:
                    from openpyxl.comments import Comment
                    for sh2, coord2, dv2, it2 in batch:
                        c2 = loop.wb[sh2][coord2]
                        c2.fill = loop.writer.fills["orange"]
                        c2.comment = Comment(
                            (f"PAIRED DIFF (terminal): applied with its "
                             f"partner(s) as one batch — {dv2:,.2f} from "
                             f"{it2.doc} p{it2.page}; lone writes broke "
                             f"the check, the batch closed it "
                             f"{before:,.1f} -> {abs(after):,.1f}."),
                            "Model Update Agent")
                        loop.writer.log["flags"].append(f"{sh2}!{coord2}")
                        loop.writer.log["written"].append(f"{sh2}!{coord2}")
                    log(f"[run] terminal ladder: PAIRED DIFF closed "
                        f"{sheet}!{row} {before:,.1f} -> {abs(after):,.1f} "
                        f"({len(batch)} cells as one batch)")
                    still = [x for x in loop._failing_target_checks()
                             if (x[0], x[1]) == (sheet, row)]
                    if not still:
                        closed += 1
                        continue
                else:
                    for sh2, coord2, old2 in olds:
                        loop.wb[sh2][coord2] = old2
        tcol = loop._tcol(sheet)
        # PLUG ONLY THE LEAST CONFIDENT INPUT (owner ruling 2026-09-08,
        # DFE run 239: the ladder plugged -15,826 into 'cash paid for
        # investments', a line read correctly from the statement, while
        # the real gap sat in a line held at growth). Sites are ranked
        # by confidence — held-at-prior / red first, then plain, then
        # orange back-outs; a PROVEN value is never a plug site.
        from .rollover import input_is_proven
        sites = []
        for (sh, coord) in dict.fromkeys(
                loop._leaf_inputs(sheet, f"{tcol}{row}")):
            m = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
            if not m or m.group(1) != loop._tcol(sh):
                continue
            if f"{sh}!{coord}" in loop.writer.locked:
                continue      # run-208: locked high-confidence serves
                              # blocked the ladder's first two tries and
                              # the year was left failing — skip them
            v = loop.wb[sh][coord].value
            try:
                rgb = str(loop.wb[sh][coord].fill.fgColor.rgb or "")
            except Exception:
                rgb = ""
            if isinstance(v, str) and v.startswith("="):
                # the agent's OWN back-out (orange, written this run — a
                # growth hold) is the least confident input there is;
                # the analyst's formulas are never plug sites
                if not (rgb.endswith("FFC000")
                        and f"{sh}!{coord}" in loop.writer.log.get("written", [])):
                    continue
                try:
                    v = Evaluator(loop.wb).cell(sh, coord)
                except Exception:
                    continue
                if not isinstance(v, (int, float)):
                    continue
                sites.append((0, -abs(v), sh, coord))
                continue
            if not isinstance(v, (int, float)):
                continue
            if input_is_proven(loop.served, sh, coord, v, (), loop.wb):
                continue
            pc = prior_column(loop.spec, sh, loop.ty)
            pv = loop.wb[sh][f"{pc}{m.group(2)}"].value if pc else None
            held_at_prior = isinstance(pv, (int, float)) and abs(v - pv) <= max(0.6, abs(pv) * 1e-3)
            conf = (0 if (rgb.endswith("FFC7CE") or held_at_prior)
                    else 2 if rgb.endswith("FFC000") else 1)
            sites.append((conf, -abs(v), sh, coord))
        for _c, _v, sh, coord in sorted(sites)[:8]:
            r = loop.t_plug_residual(
                {"check": f"{sheet}!{row}", "into": f"{sh}!{coord}",
                 "why": ("terminal ladder: the loop ended with this "
                         "check failing; owner's law — back out, mark, "
                         "still deliver")})
            log(f"[run] terminal ladder: plug {sheet}!{row} into "
                f"{sh}!{coord} -> {str(r).splitlines()[0][:90]}")
            if str(r).startswith("PLUG"):
                closed += 1
                break
    return closed
