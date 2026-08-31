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

    def _trip_lines(self):
        """Open tripwires: sign-flipped forecasts handed in by the sense
        check (owner ruling 2026-08-31: a mistake DETECTOR — investigate
        once, then verdict; never silently freeze)."""
        done = {v.split(":", 1)[0] for v in
                self.writer.log.get("verdicts", [])}
        out = []
        for (sheet, col, r, fv, pv, tv) in getattr(self, "tripwires", []):
            key = f"{sheet}!{col}{r}"
            if key in done:
                continue
            out.append(f"  {key}: forecast {fv:,.2f} NEGATIVE where actuals "
                       f"are positive ({pv:,.2f} -> {tv:,.2f}) — usually a "
                       f"mis-rolled or missing upstream input. trace_cell it "
                       f"ONCE, then verdict {{\"item\": \"{key}\", ...}}")
        return out

    def _state_block(self):
        card = self._card()
        todos = [f"  [{i}] {t}" for i, t in enumerate(self.todos)]
        notes = [f"  - {n}" for n in self.notes[-12:]]
        hist = [f"  {h}" for h in self.history[-MAX_HISTORY_SHOWN:]]
        trips = self._trip_lines()
        return "\n".join([
            f"TARGET YEAR: {self.ty}   ACTIONS LEFT: {self.budget}",
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

    def _diff_value(self, t):
        """The disclosed value for one target row — the shared evidence
        oracle (single agreeing in-world prior-identity candidate on a
        ratified current-doc face, or nothing)."""
        from .stage2_join import unique_evidence_value
        return unique_evidence_value(self.ledger, list(self.targets.values()), t)

    def _leaf_inputs(self, sheet, coord, depth=0, seen=None):
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
        out = []
        for sh2, sh3, c2, r2 in re.findall(
                r"(?:'([^']+)'|([A-Za-z0-9 _]+))?!?([A-Z]{1,3})(\d+)",
                v.replace("$", "")):
            sh = (sh2 or sh3 or sheet).strip()
            if sh in self.wb.sheetnames:
                out += self._leaf_inputs(sh, f"{c2}{r2}", depth + 1, seen)
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
                sites.append((sh, coord, str(t.label)[:30] if t else "?", cur))
            got = self._diff_value(t) if t is not None else None
            if got is not None and isinstance(cur, (int, float)):
                dv, it, _s = got
                tol = max(0.6, abs(dv) * 5e-3)
                if abs(cur - dv) > tol:
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
            best = sorted(sites, key=lambda s: -abs(s[3]))[:5]
            out.append("  eligible plug sites (numeric inputs feeding this "
                       "check, largest first):")
            for sh, coord, lab, cur in best:
                out.append(f"    {sh}!{coord} '{lab}' = {cur:,.2f}")
            sh, coord, _, _ = best[0]
            out.append(f"  e.g. plug_residual {{\"check\": \"{sheet}!{row}\", "
                       f"\"into\": \"{sh}!{coord}\", \"why\": ...}}")
        return "\n".join(out)

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
        ev = Evaluator(self.wb)
        try:
            residual = ev.cell(c_sheet, f"{c_col}{c_row}")
        except Exception as e:
            return f"MISS: check row does not evaluate: {e}"
        if abs(residual) <= 0.01:
            return "MISS: that check already passes — nothing to plug"
        held = self.wb[i_sheet][f"{i_col}{i_row}"].value
        if not isinstance(held, (int, float)):
            return (f"MISS: {i_sheet}!{i_col}{i_row} holds "
                    f"{'a formula' if isinstance(held, str) else 'nothing'}, "
                    "not a numeric input — plug into a numeric INPUT "
                    "component; diagnose_balance lists the eligible sites")
        pcol = prior_column(self.spec, i_sheet, self.ty)
        ok = self.writer.write(
            i_sheet, f"{i_col}{i_row}", held - residual,
            prior_coord=f"{pcol}{i_row}" if pcol else None,
            flag="orange",
            note=(f"PLUG (worst case): absorbed check residual "
                  f"{residual:,.2f} from {check}; was {held:,.2f}. "
                  f"ANALYST MUST REVIEW. {why[:200]}"))
        if not ok:
            return "REFUSED by write guard (band/lock) — choose another component"
        try:
            after = Evaluator(self.wb).cell(c_sheet, f"{c_col}{c_row}")
        except Exception:
            after = None
        if after is None or abs(after) > 0.01:
            self.writer.write(i_sheet, f"{i_col}{i_row}", held,
                              prior_coord=f"{pcol}{i_row}" if pcol else None,
                              trusted=True, force_lock=True,
                              note="plug reverted: did not zero the check")
            return (f"REVERTED: plugging {into} left the check at "
                    f"{after if after is not None else '?'} — the component "
                    "does not feed this check; pick one inside its chain")
        return (f"PLUGGED {into}: {held:,.2f} -> {held - residual:,.2f} "
                f"(orange-flagged, in the report). Check {check} now zero.")

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
        from .writegate import claimed_keys, find_evidence, judge_write
        pv_cell = (self.wb[sheet][f"{pcol}{row}"].value if pcol else None)
        evidence = find_evidence(self.ledger.items, value)
        verdict, law_reason, forced_flag = judge_write(
            value, pv_cell if isinstance(pv_cell, (int, float)) else None,
            (sheet, row) in self.served, evidence,
            claimed_keys(self.served))
        if verdict == "REFUSE":
            return "REFUSED by the evidence law: " + law_reason
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
        worsened = sorted(
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
                                     "conf": 3, "page": None,
                                     "line": why[:60],
                                     "note": f"objective loop: {why[:120]}"}
        fixed = sorted(before_fails - after_fails)
        return ("WRITTEN" + redirected
                + (f"; checks now passing: {fixed[:4]}" if fixed else ""))

    def t_flag_cell(self, args):
        ref = str(args.get("cell", ""))
        cr = self._cell_ref(ref)
        if not cr:
            return f"MISS: cell ref '{ref}' unparseable — use \"Sheet!AI99\" (a bare row flags the target-year column)"
        sheet, coord = cr[0], f"{cr[1]}{cr[2]}"
        if sheet not in self.wb.sheetnames:
            return f"MISS: no sheet '{sheet}'"
        cell = self.wb[sheet][coord]
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
        item = str(args.get("item") or args.get("cell") or "")
        v = str(args.get("verdict") or "").upper().replace("-", "_").replace(" ", "_")
        why = str(args.get("why") or "").strip()
        if v not in ("JUSTIFIED", "ERROR_FIXED", "SUSPICIOUS"):
            return ('MISS: need {"item": "Sheet!AJ39", "verdict": '
                    '"JUSTIFIED|ERROR_FIXED|SUSPICIOUS", "why": ...}')
        if len(why) < 15:
            return ("MISS: a verdict without its reasoning is not "
                    "adjudication — say what you traced and found")
        cr = self._cell_ref(item, default_tcol=False)
        key = (f"{cr[0]}!{cr[1]}{cr[2]}" if cr else None)
        if key is None:
            rr = self._row_ref(item)
            if not rr:
                return f"MISS: item '{item}' unparseable — use \"Sheet!AJ39\""
            key = f"{rr[0]}!{rr[1]}"
        self.writer.log.setdefault("verdicts", []).append(
            f"{key}: {v} — {why[:250]}")
        return f"VERDICT recorded for {key}: {v}"

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
             "apply_diff": t_apply_diff, "diagnose_balance": t_diagnose_balance,
             "plug_residual": t_plug_residual,
             "set_input": t_set_input, "flag_cell": t_flag_cell,
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
