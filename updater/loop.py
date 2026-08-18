"""THE AGENT — one thinking loop owns the whole update from minute zero.

REBUILD.md §2 (owner law): no fixed call-graph. The engine sees the
objective, the live scorecard, its own notes/todos/history and a toolbox —
bulk mechanics (rollover, join, gap reads) included as TOOLS it deploys
when it judges fit. The proven investigation/repair tools carry the legacy
loop's measured guards verbatim:

- set_input: citation required, subtotal-refusing, redirect-and-resign
  (run-1 GP law), TRANSACTIONAL (auto-revert if a passing check breaks —
  run-39 law).
- plug_residual: the deliberate LAST RESORT (BOSS_MINDMAP ladder) — loud,
  orange, refused while any evidence-based fix remains.
- diagnose_balance: fingerprint-first residual attribution (the measured
  fastest route from a failed check to its cause).
- Toolbox counters make every tool self-announcing (no silent zero-serve).
- EvidenceBook grades every write; flags fall out of grades automatically.

Delivery is not this module's concern: the run ALWAYS delivers; the loop's
job is to make what is delivered proven, and what is unproven flagged.
"""
import json
import re
from pathlib import Path

from .adjust import infer as infer_adjustments
from .checks import prior_column, scorecard, summarize, year_columns
from .evaluator import Evaluator
from .numerics import SCALES, line_numbers, row_tol, to_model_units
from .toolbox import Toolbox
from . import ops

MAX_ACTIONS = 120
MAX_HISTORY_SHOWN = 30
MAX_FINDS = 12

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "agent_loop.md"


class AgentLoop:
    def __init__(self, wb, spec, target_year, ledger, targets, served,
                 writer, book, client, log=None, budget=MAX_ACTIONS,
                 restatement=None, docs=(), census=None):
        self.wb = wb
        self.spec = spec
        self.ty = str(target_year)
        self.ledger = ledger
        self.targets = {t.key: t for t in targets}
        self.served = served
        self.writer = writer
        self.book = book
        self.client = client
        self.log = log if log is not None else []
        self.budget = budget
        self.restatement = restatement or {}
        self.docs = docs
        self.census = census if census is not None else {}
        self.history = []
        self.notes = []
        self.todos = []
        self.finished = None
        self._adjustments = None
        self._done = set()
        self._system = (
            "You are the equity research analyst responsible for delivering "
            "this model update. You ALWAYS deliver: reason and fix problems; "
            "back out and flag only what you truly cannot prove. You "
            "investigate before you act, cite evidence for every write, and "
            "never invent a number.")
        self.box = Toolbox()
        for name, fn, kind in (
                ("do_rollover", self.t_do_rollover, "write"),
                ("do_join", self.t_do_join, "write"),
                ("do_read_gaps", self.t_do_read_gaps, "write"),
                ("sweep_stale", self.t_sweep_stale, "write"),
                ("rescore", self.t_rescore, "query"),
                ("trace_cell", self.t_trace_cell, "query"),
                ("find_line", self.t_find_line, "query"),
                ("statement_diff", self.t_statement_diff, "query"),
                ("diagnose_balance", self.t_diagnose_balance, "query"),
                ("match_by_implied_prior", self.t_implied_prior, "query"),
                ("infer_adjustments", self.t_infer_adjustments, "query"),
                ("apply_adjustment", self.t_apply_adjustment, "write"),
                ("apply_diff", self.t_apply_diff, "write"),
                ("set_input", self.t_set_input, "write"),
                ("plug_residual", self.t_plug_residual, "write"),
                ("flag_cell", self.t_flag_cell, "write"),
                ("not_disclosed", self.t_not_disclosed, "write"),
                ("note", self.t_note, "control"),
                ("todo", self.t_todo, "control"),
                ("list_flags", self.t_list_flags, "query"),
                ("finish", self.t_finish, "control")):
            self.box.register(name, fn, kind)

    # -- state ---------------------------------------------------------------

    def _card(self):
        return scorecard(self.wb, self.spec, self.ty, served=self.served,
                         flags=self.writer.log["flags"])

    def _state_block(self):
        card = self._card()
        todos = [f"  [{i}] {t}" for i, t in enumerate(self.todos)]
        notes = [f"  - {n}" for n in self.notes[-12:]]
        hist = [f"  {h}" for h in self.history[-MAX_HISTORY_SHOWN:]]
        parts = [f"TARGET YEAR: {self.ty}   ACTIONS LEFT: {self.budget}"]
        if self.restatement.get("status") == "answered":
            parts.append(
                f"RESTATEMENT RULING: analyst said restate="
                f"{self.restatement.get('restate')}"
                + ("" if self.restatement.get("restate") else
                   " — comparatives differ by design; flag mismatches, map "
                   "via section positions, do NOT rewrite history"))
        parts += ["== SCORECARD ==",
                  summarize(card, self.ty, flags=self.writer.log["flags"],
                            spec=self.spec, wb=self.wb),
                  "== LAST ACTION RESULT (in full) ==",
                  getattr(self, "_last", "  (none yet)"),
                  "== TOOL HEALTH ==",
                  *(self.box.announcements() or ["  (no calls yet)"]),
                  "== OPEN TODOS ==", *(todos or ["  (none)"]),
                  "== YOUR NOTES ==", *(notes or ["  (none)"]),
                  "== ACTION HISTORY (newest last) ==",
                  *(hist or ["  (none)"])]
        return "\n".join(parts)

    def _tcol(self, sheet):
        return year_columns(self.spec, sheet).get(self.ty)

    def _key_rows(self):
        return {(k["sheet"], int(k["row"]))
                for k in self.spec.get("key_rows") or []}

    # -- bulk mechanics as tools (the agent decides when) --------------------

    def t_do_rollover(self, args):
        if self.census:
            return "MISS: rollover already done (census exists)"
        self.census.update(ops.rollover_all(
            self.wb, self.spec, self.ty, self.writer, self.log.append))
        n = sum(len(v) for v in self.census.values())
        return f"ROLLED {len(self.census)} sheets; {n} hardcode inputs to mark"

    def t_do_join(self, args):
        run_log = []
        served, _dec = ops.run_join(self.ledger,
                                    list(self.targets.values()), run_log)
        new = {k: v for k, v in served.items() if k not in self.served}
        self.served.update(new)
        priors = {t.key: t.prior_value for t in self.targets.values()}
        n = ops.write_served(self.wb, self.spec, self.ty, new, self.writer,
                             priors, self.book, self.log.append)
        return (f"JOINED {len(new)} rows deterministically, wrote {n} "
                f"({run_log[-1] if run_log else ''})")

    def t_do_read_gaps(self, args):
        if self.client is None:
            return "MISS: no LLM client (dry run) — gap reading unavailable"
        from .stage3_read import read_gaps
        run_log = []
        gap = read_gaps(self.ledger, list(self.targets.values()),
                        self.served, self.client, self.docs, run_log)
        new = {k: v for k, v in gap.items() if k not in self.served}
        self.served.update(new)
        priors = {t.key: t.prior_value for t in self.targets.values()}
        n = ops.write_served(self.wb, self.spec, self.ty, new, self.writer,
                             priors, self.book, self.log.append)
        return f"READ {len(new)} gap rows (checksummed), wrote {n}"

    def t_sweep_stale(self, args):
        n1 = ops.flag_stale(self.wb, self.spec, self.ty, self.census,
                            self.served, self.writer, self.book,
                            self.log.append)
        n2 = ops.sweep_compositions(self.wb, self.spec, self.ty, self.census,
                                    self.writer, self.book, self.log.append)
        return (f"{n1} stale inputs flagged red; {n2} compositions backed "
                "out orange — clear what you can prove, claim not_disclosed "
                "(with the search trail) for what the document lacks")

    # -- proven investigation tools (legacy loop bodies, guards intact) ------

    def t_implied_prior(self, args):
        """The run-103 mechanism for single-year MD&A tables (segment keys
        law): implied_prior = current/(1+同比%) tying the model's own
        prior. Returns CANDIDATES with citations — YOU judge each line's
        context (a real segment/MD&A table vs prose or an unrelated
        ratio), then set_input the ones that are genuine."""
        cands = ops.implied_prior_candidates(
            self.wb, self.spec, self.ty, list(self.targets.values()),
            self.ledger, self.served, self.log.append)
        if not cands:
            return ("MISS: no unique implied-prior ties among the remaining "
                    "stale rows — find_line the segment tables directly")
        return "\n".join(
            f"CANDIDATE {c['row']} '{c['label']}': prior {c['prior']:,.1f} "
            f"-> {c['value']:,.1f} ({c['pct']:+.2f}%) | {c['cite'][:70]}\n"
            f"  if the line is a genuine segment/MD&A table -> set_input "
            f"{{\"cell\": \"{c['cell']}\", \"value\": {c['value']}, "
            f"\"why\": \"p{c['page']}: implied-prior tie\"}}"
            for c in cands[:10])

    def t_rescore(self, args):
        return summarize(self._card(), self.ty)

    def t_trace_cell(self, args):
        ref = str(args.get("cell", ""))
        m = re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]{1,3})(\d+)$",
                     ref.replace("$", ""))
        if not m:
            return f"MISS: cell ref '{ref}' unparseable (Sheet!C7 form)"
        sheet, col, row = (m.group(1) or m.group(2)), m.group(3), int(m.group(4))
        if sheet not in self.wb.sheetnames:
            return f"MISS: no sheet '{sheet}'"
        ws = self.wb[sheet]
        v = ws[f"{col}{row}"].value
        ev = Evaluator(self.wb)
        out = [f"{ref} holds: {v!r}"]
        try:
            out.append(f"evaluates to: {ev.cell(sheet, f'{col}{row}'):,.4f}")
        except Exception as e:
            out.append(f"evaluation failed: {e}")
        if isinstance(v, str) and v.startswith("="):
            refs = re.findall(
                r"(?:'([^']+)'|([A-Za-z0-9 _]+))?!?([A-Z]{1,3})(\d+)",
                v.replace("$", ""))[:24]
            for sh2, sh3, c2, r2 in refs:
                sh = (sh2 or sh3 or sheet).strip()
                if sh not in self.wb.sheetnames:
                    continue
                try:
                    cur = ev.cell(sh, f"{c2}{r2}")
                except Exception:
                    cur = "?"
                pv = None
                sh_pcol = prior_column(self.spec, sh, self.ty)
                if sh_pcol and c2 == self._tcol(sh):
                    try:
                        pv = ev.cell(sh, f"{sh_pcol}{r2}")
                    except Exception:
                        pv = None
                lab = next((self.wb[sh][f"{lc}{r2}"].value
                            for lc in ("A", "B", "C")
                            if isinstance(self.wb[sh][f"{lc}{r2}"].value, str)),
                           "")
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
                              if isinstance(pv, (int, float)) else "") + mark)
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
        hits.sort(key=lambda it: (it.doc in prior_docs,
                                  self.ledger.face(it.doc, it.page) is None))
        hits = hits[:MAX_FINDS]
        if not hits:
            return (f"MISS: '{q}' not in the evidence ledger. Try ONE synonym, "
                    "then move on (walk-away law).")
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
        from .stage2_join import unique_evidence_value
        return unique_evidence_value(self.ledger, list(self.targets.values()), t)

    def _leaf_inputs(self, sheet, coord, depth=0, seen=None):
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
        """Fingerprint-first residual attribution (BUILD_PLAN §3.4) — name
        the guilty leaves; plugging only after this list is empty.

        Also accepts {"key": "investing cash flow"} (owner keys law): the
        residual becomes model-vs-DISCLOSED on that key's own chain — the
        machinery then hunts the misplaced component the same way."""
        key_q = str(args.get("key") or "").strip().lower()
        if key_q:
            match = next(
                (k for k in self.spec.get("key_rows") or []
                 if key_q in str(k.get("name", "")).lower()), None)
            if match is None:
                names = [k.get("name") for k in
                         (self.spec.get("key_rows") or [])][:12]
                return f"MISS: no key named like '{key_q}' (have: {names})"
            sheet, row = match["sheet"], int(match["row"])
            col = self._tcol(sheet)
            t = self.targets.get((sheet, row))
            got = self._diff_value(t) if t is not None else None
            if got is None:
                return (f"MISS: no unique disclosed value for key "
                        f"'{match.get('name')}' — find_line it and repair "
                        "components with set_input")
            ev = Evaluator(self.wb)
            try:
                mv = ev.cell(sheet, f"{col}{row}")
            except Exception as e:
                return f"MISS: key does not evaluate: {e}"
            residual = mv - got[0]
            out = [f"KEY {match.get('name')} {sheet}!{col}{row}: model "
                   f"{mv:,.2f} vs disclosed {got[0]:,.2f} "
                   f"({got[1].doc} p{got[1].page}) -> residual "
                   f"{residual:,.2f} to attribute on its own chain",
                   "  (repair COMPONENTS via set_input/apply_diff — "
                   "plug_residual on a key is FORBIDDEN: a key's target is "
                   "its DISCLOSED value, never zero)"]
            if abs(residual) <= max(0.6, abs(got[0]) * 5e-3):
                return out[0] + " — TIES, nothing to fix"
        else:
            ref = str(args.get("check") or args.get("cell") or "")
            m = re.match(r"^(?:'([^']+)'|([^!]+))!?([A-Z]{1,3})?(\d+)$",
                         ref.replace("$", ""))
            if not m:
                checks = [f"{c['sheet']}!{c['row']}"
                          for c in self.spec.get("check_rows") or []]
                return (f"MISS: name the check row, e.g. "
                        f"{{\"check\": \"{checks[0] if checks else 'Model!95'}\"}}"
                        " — or a key: {\"key\": \"investing cash flow\"}")
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
        flagged_refs = set(self.writer.log["flags"])
        for (sh, coord) in dict.fromkeys(self._leaf_inputs(sheet, f"{col}{row}")):
            mm = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
            if not mm or mm.group(1) != self._tcol(sh):
                continue
            t = self.targets.get((sh, int(mm.group(2))))
            cur = self.wb[sh][coord].value
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
        # RECLASS FINDER (run-6 law: the −12,116 was a reclassification —
        # prior-triangulation can never see the destination row, but the
        # residual fingerprints it). For evidence-less leaves, hunt a kin
        # face line whose disclosed value differs from the model by ≈ the
        # residual, and hand the agent the exact set_input.
        if guilty == 0:
            from .numerics import kinship
            from .stage2_join import ratify_page_scales
            pool = self.ledger.join_pool()
            priors = [t.prior_value for t in self.targets.values()
                      if isinstance(t.prior_value, (int, float))]
            scales = ratify_page_scales(pool, priors)
            rtol = max(1.0, abs(residual) * 0.02)
            found = 0
            for (sh, coord) in dict.fromkeys(
                    self._leaf_inputs(sheet, f"{col}{row}")):
                mm = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
                if not mm or mm.group(1) != self._tcol(sh) or found >= 4:
                    continue
                t = self.targets.get((sh, int(mm.group(2))))
                cur = self.wb[sh][coord].value
                if t is None or not isinstance(cur, (int, float)):
                    continue
                for it in pool:
                    s = scales.get((it.doc, it.page))
                    if s is None or not kinship(t.label, it.label):
                        continue
                    ns = [to_model_units(n, s) for n in it.nums]
                    world = [n for n in ns if n != 0 and abs(cur) > 0
                             and 0.01 <= abs(n) / max(abs(cur), 1.0) <= 100.0]
                    if not world:
                        continue
                    dv = world[0]
                    if abs((dv - cur) - residual) <= rtol \
                            or abs((dv - cur) + residual) <= rtol:
                        found += 1
                        out.append(
                            f"  RECLASS CANDIDATE {sh}!{coord} "
                            f"'{str(t.label)[:30]}': model {cur:,.2f} vs "
                            f"disclosed ≈{dv:,.2f} — the delta IS the "
                            f"residual -> set_input {{\"cell\": "
                            f"\"{sh}!{coord}\", \"value\": {dv:.2f}, "
                            f"\"why\": \"p{it.page}: {it.label[:30]}\"}}")
                        break
            if not found:
                out.append("  (reclass scan: 0 candidates — no kin line's "
                           "delta matches the residual)")
        if guilty == 0 and len(out) == 1:
            out.append("  no leaf disagrees and no unproven suspects — "
                       "find_line the residual amount, or (worst case) "
                       "plug_residual with a named component")
        # THE LADDER'S LAST RUNG HAS TEETH (run-4 autopsy: 67 diagnoses of
        # the same four evidence-less checks, zero plugs). From the second
        # guilty-free diagnosis of a check, the answer IS the escalation:
        # concrete plug sites, and an instruction to use one NOW.
        self._diag_counts = getattr(self, "_diag_counts", {})
        ck = f"{sheet}!{row}"
        self._diag_counts[ck] = self._diag_counts.get(ck, 0) + 1
        if key_q and guilty == 0 and self._diag_counts[ck] >= 2:
            out.append(
                "ESCALATE (key mode): no provable component cause — act on "
                "any RECLASS/SUSPECT above via set_input, or flag_cell the "
                "key with your best explanation and move on. NEVER "
                "plug_residual a key (its target is the disclosed value, "
                "not zero).")
        elif guilty == 0 and self._diag_counts[ck] >= 2:
            keys = self._key_rows()
            sites = []
            for (sh, coord) in dict.fromkeys(
                    self._leaf_inputs(sheet, f"{col}{row}")):
                mm = re.match(r"^([A-Z]{1,3})(\d+)$", coord)
                if not mm or mm.group(1) != self._tcol(sh):
                    continue
                if (sh, int(mm.group(2))) in keys:
                    continue
                if f"{sh}!{coord}" in self.writer.locked:
                    continue        # proven cells refuse writes — never
                                    # send the agent at a locked site (r4)
                if isinstance(self.wb[sh][coord].value, (int, float)):
                    sites.append(f"{sh}!{coord}")
                if len(sites) >= 5:
                    break
            out.append(
                f"ESCALATE NOW (diagnosis #{self._diag_counts[ck]} of this "
                "check, no guilty row exists in the evidence): further "
                "investigation is waste — this residual has NO provable "
                "cause in the disclosure. Boss law: back out and mark. "
                "Your next action for this check MUST be plug_residual"
                + (f" into one of: {', '.join(sites)}" if sites
                   else " (pick a numeric leaf from the list above)")
                + " — or flag_cell the check with your best explanation "
                "and move to the next objective.")
        return "\n".join(out)

    def t_plug_residual(self, args):
        """LAST RESORT on the BOSS_MINDMAP ladder — loud, orange, refused
        while any evidence-based fix remains."""
        check = str(args.get("check") or "")
        into = str(args.get("into") or "")
        why = str(args.get("why") or "")
        diag = self.t_diagnose_balance({"check": check})
        if "GUILTY" in diag:
            return ("REFUSED: evidence-based fixes remain — plug only after "
                    "these are applied or ruled out:\n" + diag)
        # column-qualified and 'r95'-style check refs are legal (run-4/8:
        # plugs died on format variants — never on intent)
        mc = re.match(r"^(?:'([^']+)'|([^!]+))!?[A-Za-z]{0,3}?(\d+)$",
                      check.replace("$", ""))
        mi = re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]{1,3})(\d+)$",
                      into.replace("$", ""))
        if not mc or not mi:
            return ("MISS: need {\"check\": \"Model!95\", "
                    "\"into\": \"Sheet!U177\", \"why\": ...}")
        c_sheet, c_row = (mc.group(1) or mc.group(2)).strip(), int(mc.group(3))
        # CHECK-ROWS-ONLY LAW (run-8: the agent fed KEY cells as "checks"
        # and the tool zeroed CFI itself, then ping-ponged components).
        # A check row's target is zero; a key row's target is its DISCLOSED
        # value — plugging may only ever zero a spec check row.
        spec_checks = {(c["sheet"], int(c["row"]))
                       for c in self.spec.get("check_rows") or []}
        if (c_sheet, c_row) not in spec_checks:
            return (f"REFUSED: {c_sheet}!{c_row} is not a check row — "
                    "plug_residual only zeroes designed check rows "
                    f"({sorted(f'{s}!{r}' for s, r in spec_checks)[:6]}). "
                    "A mismatching KEY is repaired through its COMPONENTS "
                    "via set_input/apply_diff (diagnose_balance "
                    "{\"key\": ...} names them); a key is never zeroed.")
        c_col = self._tcol(c_sheet)
        i_sheet, i_col, i_row = ((mi.group(1) or mi.group(2)).strip(),
                                 mi.group(3), int(mi.group(4)))
        if (i_sheet, i_row) in self._key_rows():
            return "REFUSED: key rows are never plug sites (run-38 law)"
        ev = Evaluator(self.wb)
        try:
            residual = ev.cell(c_sheet, f"{c_col}{c_row}")
        except Exception as e:
            return f"MISS: check row does not evaluate: {e}"
        if abs(residual) <= 0.01:
            return "MISS: that check already passes — nothing to plug"
        held = self.wb[i_sheet][f"{i_col}{i_row}"].value
        if isinstance(held, str) and held.startswith("="):
            # run-2 autopsy: three plug attempts died on formula cells.
            # A formula 'into' redirects to where its number is typed —
            # same law as set_input.
            from .writer import resolve_input_site
            pcol_i = prior_column(self.spec, i_sheet, self.ty)
            site = (resolve_input_site(self.wb, i_sheet, i_row, pcol_i)
                    if pcol_i else None)
            if site and site != (i_sheet, i_row):
                s_sheet, s_row = site
                s_tcol = self._tcol(s_sheet)
                if s_tcol and (s_sheet, s_row) not in self._key_rows():
                    i_sheet, i_col, i_row = s_sheet, s_tcol, s_row
                    into = f"{i_sheet}!{i_col}{i_row}"
                    held = self.wb[i_sheet][f"{i_col}{i_row}"].value
        if not isinstance(held, (int, float)):
            return (f"MISS: {into} is not a numeric input cell (and no "
                    "input site found behind it) — pick a NUMERIC component "
                    "from diagnose_balance's leaf list")
        # PRINTED LAND (owner issue 1/2 root cause): every line of a
        # statement section is a printed fact. A cell whose NEIGHBORS tie
        # face evidence sits inside a printed section — plugging there
        # plants a detail-level error that poisons every composition
        # downstream (the CFI/CFF twin was born this way). Statement rows
        # are never plug sites.
        neighbors_tied = 0
        for dr in (-2, -1, 1, 2):
            tn = self.targets.get((i_sheet, i_row + dr))
            if tn is not None and self._diff_value(tn) is not None:
                neighbors_tied += 1
        if neighbors_tied >= 2:
            # THE BELL EXCEPTION (owner's backout law outranks): at the
            # closing bell, when no site exists outside printed land, a
            # flagged plug may land in a printed section — ONLY into a
            # cell with no evidence of its own, and it says so loudly.
            t_into = self.targets.get((i_sheet, i_row))
            evid = self._diff_value(t_into) if t_into is not None else None
            if not (args.get("_bell") and evid is None):
                return (f"REFUSED: {into} sits inside a printed statement "
                        "section (neighboring rows tie the filing) — its "
                        "true value is printed; find it or flag it. Plugs "
                        "belong on non-statement presentation rows only.")
            args["_printed_section"] = True
        # ONE PLUG PER CELL (run-8: Raw!U203 was plugged three times,
        # ping-ponging 35,262 -> 5,089 -> -25,073 as two residuals fought
        # over it). A plug site is an analyst-review item; a second
        # residual landing on the same cell means its cause is elsewhere.
        prior_plug = self.book.entries.get(f"{i_sheet}!{i_col}{i_row}")
        if prior_plug is not None and prior_plug.method == "plug":
            return (f"REFUSED: {into} is already a plug site this run — a "
                    "second residual pointing here means its true cause is "
                    "elsewhere; diagnose the other check/key and repair or "
                    "flag it instead.")
        # TRUTH OUTRANKS BALANCE (run-6 law): a cell whose value ties
        # disclosure evidence is PROVEN — plugging it falsifies announced
        # data to satisfy an identity, the one forbidden trade.
        t_into = self.targets.get((i_sheet, i_row))
        if t_into is not None:
            got = self._diff_value(t_into)
            if got is not None and abs(abs(held) - abs(got[0])) <= \
                    max(0.6, abs(got[0]) * 5e-3):
                return (f"REFUSED: {into} is disclosure-proven at "
                        f"{got[0]:,.2f} ({got[1].doc} p{got[1].page}) — "
                        "plugging it would falsify announced data. Pick an "
                        "UNPROVEN component (diagnose's site list).")
        # target-column guard: a plug lands in the target year unless the
        # agent explicitly declares a forecast integrity repair
        tc_i = self._tcol(i_sheet)
        if tc_i and i_col != tc_i and not args.get("forecast_repair"):
            return (f"REFUSED: {into} is not in the {self.ty} column "
                    f"({tc_i}) — pass forecast_repair=true ONLY for a "
                    "forecast-year integrity repair")
        # SIGN-AWARE plug (run-6: six attempts doubled the residual on
        # negative-entry components and reverted): measure the check's
        # response to the cell, then plug residual/derivative.
        cell_obj = self.wb[i_sheet][f"{i_col}{i_row}"]
        cell_obj.value = held + 1.0
        try:
            r1 = Evaluator(self.wb).cell(c_sheet, f"{c_col}{c_row}")
        except Exception:
            r1 = None
        finally:
            cell_obj.value = held
        if not isinstance(r1, (int, float)) or abs(r1 - residual) < 1e-9:
            return (f"MISS: {into} does not affect check {check} — pick a "
                    "component inside its chain (trace_cell the check)")
        deriv = r1 - residual
        plug_value = held - residual / deriv
        pre_ties = self._tie_state()
        # FULL-SCORECARD guard (owner issue 2 — the swept imbalance):
        # set_input always had it; the plug tool verified only its own
        # check and silently broke the forecast years. Every write is
        # transactional against the WHOLE scorecard, no exceptions.
        before_fails = {c["name"] for c in self._card()["checks"]
                        if c["status"] == "FAIL"}
        pcol = prior_column(self.spec, i_sheet, self.ty)
        ok = self.writer.write(
            i_sheet, f"{i_col}{i_row}", plug_value,
            prior_coord=f"{pcol}{i_row}" if pcol else None,
            flag="orange",
            note=(("PRINTED-SECTION PLUG — this cell sits inside a printed "
                   "statement block; the analyst must reallocate. "
                   if args.get("_printed_section") else "")
                  + f"PLUG (last resort): absorbed check residual "
                  f"{residual:,.2f} from {check}; was {held:,.2f}. "
                  f"ANALYST MUST REVIEW. {why[:200]}"))
        if not ok:
            return "REFUSED by write guard (band/lock) — choose another component"
        try:
            after = Evaluator(self.wb).cell(c_sheet, f"{c_col}{c_row}")
        except Exception:
            after = None
        broken_ties = []
        broke_checks = []
        if after is not None and abs(after) <= 0.01:
            post = self._tie_state()
            broken_ties = sorted(k for k, v in pre_ties.items()
                                 if v and not post.get(k, False))
            after_fails = {c["name"] for c in self._card()["checks"]
                           if c["status"] == "FAIL"}
            broke_checks = sorted(after_fails - before_fails)
        if after is None or abs(after) > 0.01 or broken_ties or broke_checks:
            self.writer.write(i_sheet, f"{i_col}{i_row}", held,
                              prior_coord=f"{pcol}{i_row}" if pcol else None,
                              trusted=True, force_lock=True,
                              note="plug reverted: broke the check, other "
                                   "years, or announced ties")
            if broke_checks:
                return (f"REVERTED: the plug zeroed {check} but broke "
                        f"{broke_checks[:4]} — an imbalance moved is not an "
                        "imbalance closed; the cause lives elsewhere "
                        "(or this is a flag)")
            if broken_ties:
                return (f"REVERTED: the plug zeroed {check} but moved "
                        f"previously-tying announced values off the "
                        f"disclosure ({broken_ties[:3]}) — truth outranks "
                        "balance; pick a component outside proven totals")
            return (f"REVERTED: plugging {into} left the check at "
                    f"{after if after is not None else '?'} — pick a "
                    "component inside its chain")
        self.book.record(f"{i_sheet}!{i_col}{i_row}", "D", "plug",
                         note=f"absorbed {residual:,.2f} from {check}; {why[:120]}")
        return (f"PLUGGED {into}: {held:,.2f} -> {plug_value:,.2f} "
                f"(orange, in the report). Check {check} now zero.")

    def _tie_state(self):
        """Which announced rows currently TIE their unique disclosure
        evidence — the truth-guard snapshot (run-6 law: no write may move
        a tying row off the disclosure to satisfy an identity)."""
        ties = {}
        ev = Evaluator(self.wb)
        for t in self.targets.values():
            got = self._diff_value(t)
            if got is None:
                continue
            tcol = self._tcol(t.sheet)
            if not tcol:
                continue
            try:
                mv = ev.cell(t.sheet, f"{tcol}{t.row}")
            except Exception:
                continue
            if isinstance(mv, (int, float)):
                dv = got[0]
                ties[t.key] = abs(abs(mv) - abs(dv)) <= max(0.6,
                                                            abs(dv) * 5e-3)
        return ties

    def _row_ref(self, args):
        """Tolerant row-ref parsing (run-1-live autopsy: the agent lost its
        endgame to arg-format misses). Accepts row/cell/ref keys, optional
        separate sheet key, Sheet!49, Sheet!U49, and bare U49/49 forms."""
        ref = str(args.get("row") or args.get("cell") or args.get("ref") or "")
        ref = ref.replace("$", "").strip()
        sheet = str(args.get("sheet") or "").strip()
        m = re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]{0,3})(\d+)$", ref)
        if m:
            return (m.group(1) or m.group(2)).strip(), int(m.group(4))
        m = re.match(r"^([A-Z]{0,3})(\d+)$", ref)
        if m and sheet:
            return sheet, int(m.group(2))
        return None, None

    def t_apply_diff(self, args):
        sheet, row = self._row_ref(args)
        if sheet is None:
            return ("MISS: row ref unparseable — use "
                    "{\"row\": \"Sheet!49\"} (column letters are ok too)")
        t = self.targets.get((sheet, row))
        if t is None:
            return f"MISS: {sheet}!{row} is not a census row"
        got = self._diff_value(t)
        if got is None:
            return (f"MISS: no unique prior-identity evidence for {sheet}!{row} "
                    "— use find_line + set_input with your own citation, "
                    "or flag it")
        dv, it, s = got
        tcol = self._tcol(sheet)
        why = f"p{it.page}: {it.doc} '{it.label[:40]}' (prior-identity tie)"
        r = self.t_set_input({"cell": f"{sheet}!{tcol}{row}", "value": dv,
                              "why": why, "_grade": "A"})
        return r

    def t_infer_adjustments(self, args):
        if self._adjustments is None:
            self._adjustments = infer_adjustments(
                self.ledger, list(self.targets.values()))
        if not self._adjustments:
            return "no analyst adjustments inferred (all priors tie print)"
        return "\n".join(
            f"[{i}] {a['row']} '{a['label']}': model = disclosed "
            f"{'x' if a['kind'] == 'ratio' else '+'} {a['constant']}  "
            f"(disclosed current {a['disclosed_current']:,.2f} -> replicated "
            f"{a['replicated']:,.2f})  {a['cite'][:60]}"
            for i, a in enumerate(self._adjustments))

    def t_apply_adjustment(self, args):
        if not self._adjustments:
            return "MISS: run infer_adjustments first"
        try:
            a = self._adjustments[int(args.get("index"))]
        except (TypeError, ValueError, IndexError):
            return f"MISS: index 0..{len(self._adjustments) - 1} required"
        sheet, row = a["row"].split("!")
        tcol = self._tcol(sheet)
        r = self.t_set_input({
            "cell": f"{sheet}!{tcol}{row}", "value": a["replicated"],
            "why": (f"analyst adjustment replicated ({a['kind']} "
                    f"{a['constant']}); {a['cite']}"),
            "_grade": "B", "_method": "adjustment"})
        return r

    def t_set_input(self, args):
        # tolerant args (run-1-live autopsy): why/citation/cite/reason are
        # synonyms; the cell may come as Sheet!U49 or sheet=... + cell=U49
        ref = str(args.get("cell") or args.get("ref") or "")
        why = str(args.get("why") or args.get("citation") or args.get("cite")
                  or args.get("reason") or "")
        grade = str(args.get("_grade") or "B")
        method = str(args.get("_method") or "loop set_input")
        ref = ref.replace("$", "").strip()
        if "!" not in ref and args.get("sheet"):
            ref = f"{args['sheet']}!{ref}"
        m = re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]{1,3})(\d+)$", ref)
        if not m:
            m2 = re.match(r"^(?:'([^']+)'|([^!]+))!(\d+)$", ref)
            if m2:
                sh = (m2.group(1) or m2.group(2)).strip()
                tc = self._tcol(sh)
                if tc:
                    m = re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]{1,3})(\d+)$",
                                 f"{sh}!{tc}{m2.group(3)}")
        if not m:
            return (f"MISS: cell ref '{ref}' unparseable — "
                    "{\"cell\": \"Sheet!U49\", \"value\": ..., \"why\": "
                    "\"p102: ...\"}")
        # a citation is a disclosure page OR a proven workbook cell (run-2
        # autopsy: the agent found the cash-tie fix and cited the statement
        # cell 'Raw financials!U243' — internal-reconciliation cites are
        # legitimate; only citation-free writes are refused)
        if not re.search(r"p(?:age)?\.?\s*\d+", why, re.IGNORECASE) \
                and not re.search(r"![A-Z]{1,3}\d+", why):
            return ("REFUSED: 'why' must cite the disclosure page "
                    "(e.g. 'p102: ...') or a proven workbook cell "
                    "(e.g. 'ties Raw financials!U243') — no citation, no write")
        # EMBEDDED-CONSTANT SWAP (run-28 owner review): a formula cell's
        # numeric literal is last year's disclosed figure — the write is a
        # constant REWRITE that keeps the formula, transactional like any
        # other write.
        swap = args.get("swap_constant")
        if isinstance(swap, dict):
            s_sheet = (m.group(1) or m.group(2)).strip()
            s_col, s_row = m.group(3), int(m.group(4))
            if s_sheet not in self.wb.sheetnames:
                return f"MISS: no sheet '{s_sheet}'"
            held0 = self.wb[s_sheet][f"{s_col}{s_row}"].value
            if not (isinstance(held0, str) and held0.startswith("=")):
                return ("MISS: swap_constant applies to FORMULA cells; "
                        f"{ref} holds {held0!r} — use value for inputs")
            tc0 = self._tcol(s_sheet)
            if tc0 and s_col != tc0 and not args.get("forecast_repair"):
                return (f"REFUSED: {ref} is in column {s_col}, not the "
                        f"{self.ty} column — swap constants in the "
                        "mark-to-actual column only")
            try:
                old = float(swap.get("old"))
                new = float(swap.get("new"))
            except (TypeError, ValueError):
                return "MISS: swap_constant needs numeric old and new"
            toks = re.findall(r"(?<![A-Za-z0-9_.:$])\d+(?:\.\d+)?", held0)
            tok = next((x for x in toks
                        if abs(float(x) - old) <= max(0.01, abs(old) * 1e-6)),
                       None)
            if tok is None:
                return (f"MISS: constant {old} is not in the formula "
                        f"{held0[:48]}")
            new_txt = (f"{new:.10g}")
            newf = held0.replace(tok, new_txt, 1)
            before_fails = {c["name"] for c in self._card()["checks"]
                            if c["status"] == "FAIL"}
            ok = self.writer.write(
                s_sheet, f"{s_col}{s_row}", newf,
                note=f"agent constant swap {tok} -> {new_txt}: {why[:250]}",
                flag="red" if args.get("flag") else None)
            if not ok:
                return "REFUSED: the chokepoint rejected the rewrite"
            after_fails = {c["name"] for c in self._card()["checks"]
                           if c["status"] == "FAIL"}
            broke = after_fails - before_fails
            if broke:
                self.writer.write(s_sheet, f"{s_col}{s_row}", held0,
                                  note="reverted: swap broke checks")
                return (f"REVERTED: the swap broke "
                        f"{', '.join(sorted(broke)[:3])} — the constant may "
                        "not be what you think it is; trace the formula")
            self.book.record(f"{s_sheet}!{s_col}{s_row}", "B",
                             "embedded-constant swap", citation=why[:150])
            return (f"WRITTEN: {s_sheet}!{s_col}{s_row} constant {tok} -> "
                    f"{new_txt} (formula kept: {newf[:48]})")
        try:
            value = float(args.get("value"))
        except (TypeError, ValueError):
            return "MISS: numeric value required"
        sheet, col, row = (m.group(1) or m.group(2)), m.group(3), int(m.group(4))
        if sheet not in self.wb.sheetnames:
            return f"MISS: no sheet '{sheet}'"
        held = self.wb[sheet][f"{col}{row}"].value
        redirected = ""
        if isinstance(held, str) and held.startswith("="):
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
        # TARGET-COLUMN GUARD (run-6: two 2025 actuals landed in the 2026
        # column V75). Mark-to-actual writes belong in the target year;
        # forecast columns only via an explicit integrity-repair declaration
        # (the BOSS_MINDMAP forecast exception, made explicit).
        tc = self._tcol(sheet)
        if tc and col != tc and not args.get("forecast_repair"):
            return (f"REFUSED: {ref} is in column {col}, not the {self.ty} "
                    f"column ({tc}{row} is the mark-to-actual site). Pass "
                    "forecast_repair=true ONLY to repair integrity in a "
                    "forecast year — never to write actuals there.")
        # RECONCILIATION SEATBELT (run-28, the Fable pass): the pool's
        # agreeing print outranks any single reading — a write that
        # contradicts the evidence oracle's unique agreed value is refused
        # with the print cited. If the agent believes the print is the
        # wrong row, that belief is a flag, never a write.
        t_row = self.targets.get((sheet, row))
        if t_row is not None:
            from .stage2_join import unique_evidence_value
            got = unique_evidence_value(self.ledger, list(self.targets.values()),
                                        t_row)
            if got is not None:
                dv = got[0]
                if abs(abs(value) - abs(dv)) > max(0.6, abs(dv) * 5e-3):
                    return (f"REFUSED: the disclosure's agreeing print for "
                            f"this row is {dv:,.2f} ({got[1].doc} "
                            f"p{got[1].page}: '{got[1].source_line[:60]}') — "
                            f"your {value:,.2f} contradicts it. Write the "
                            f"printed value, or flag your disagreement with "
                            f"the reason; never override an agreeing print.")
        pcol = prior_column(self.spec, sheet, self.ty)
        # NEIGHBOUR BAND (confined test 4): a NEW line has no prior, so
        # the world band cannot judge it — but the column's neighbours
        # can. A value ~1000x the nearby rows' magnitude is a raw-units
        # slip (the disclosure prints yuan; the model speaks its own
        # units), not a big year. Arithmetic referee only — it refuses
        # and explains; the agent converts and rewrites.
        if pcol and value != 0:
            pv_here = self.wb[sheet][f"{pcol}{row}"].value
            if not isinstance(pv_here, (int, float)):
                neigh = [abs(self.wb[sheet][f"{pcol}{r2}"].value)
                         for r2 in range(max(1, row - 6), row + 7)
                         if isinstance(self.wb[sheet][f"{pcol}{r2}"].value,
                                       (int, float))
                         and abs(self.wb[sheet][f"{pcol}{r2}"].value) > 0.01]
                if neigh:
                    med = sorted(neigh)[len(neigh) // 2]
                    if med > 0 and (abs(value) / med >= 500
                                    or med / max(abs(value), 1e-12) >= 500):
                        return (f"REFUSED: {value:,.2f} is ~"
                                f"{max(abs(value) / med, med / abs(value)):,.0f}x "
                                f"the magnitude of this row's neighbours "
                                f"(median {med:,.2f}) — a raw-units slip? "
                                f"The model's column speaks its own units; "
                                f"convert and rewrite.")
        before_fails = {c["name"] for c in self._card()["checks"]
                        if c["status"] == "FAIL"}
        ok = self.writer.write(sheet, f"{col}{row}", value,
                               prior_coord=f"{pcol}{row}" if pcol else None,
                               note=f"agent: {why[:300]}",
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
                              note="agent: REVERTED (broke checks)")
            return (f"REVERTED: the write broke previously-passing checks "
                    f"{broke[:4]} — the target cell is wrong, not the value; "
                    "trace_cell / statement_diff to find the right row")
        # RE-BASED COMPARATIVE AUTO-FLAG (confined run 2, 2026-08-19: the
        # engine wrote the counterpart value but dropped the mandatory red
        # flag). If the disclosure line carrying this value prints a
        # comparative that does NOT tie the row's prior, the basis moved —
        # the flag is law, not a courtesy, so code sets it.
        if not args.get("flag"):
            pv0 = (self.targets.get((sheet, row)).prior_value
                   if (sheet, row) in self.targets else None)
            if isinstance(pv0, (int, float)) and abs(pv0) >= 1.0:
                from .numerics import SCALES, to_model_units
                prior_docs = self.ledger.prior_period_docs()
                vtol = max(0.6, abs(value) * 5e-4)
                ptol = max(0.6, abs(pv0) * 5e-4)
                carriers = [it for it in self.ledger.items
                            if it.doc not in prior_docs
                            and len(it.nums) >= 2
                            and any(abs(abs(to_model_units(n, s)) -
                                        abs(value)) <= vtol
                                    for n in it.nums for s in SCALES)]
                if carriers and not any(
                        abs(abs(to_model_units(n, s)) - abs(pv0)) <= ptol
                        for it in carriers for n in it.nums for s in SCALES):
                    c = self.wb[sheet][f"{col}{row}"]
                    c.fill = self.writer.fills["red"]
                    self.writer.log["flags"].append(ref)
                    from openpyxl.comments import Comment
                    c.comment = Comment(
                        f"RE-BASED COMPARATIVE: the disclosure line "
                        f"carrying {value:,.2f} prints a prior that does "
                        f"NOT tie the model's {pv0:,.2f} — the category "
                        f"basis moved; analyst to confirm the mapping. "
                        f"{why[:150]}", "Model Update Agent")
                    args["flag"] = True
        self.book.record(ref, "C" if args.get("flag") else grade, method,
                         citation=why[:150])
        self.served[(sheet, row)] = {"value": value, "status": "OK",
                                     "conf": 4 if grade == "A" else 3,
                                     "page": None, "line": why[:60],
                                     "note": f"agent: {why[:120]}"}
        fixed = sorted(before_fails - after_fails)
        return ("WRITTEN" + redirected
                + (f"; checks now passing: {fixed[:4]}" if fixed else ""))

    def t_flag_cell(self, args):
        ref = str(args.get("cell", ""))
        m = re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]{1,3}\d+)$",
                     ref.replace("$", ""))
        if not m:
            return f"MISS: cell ref '{ref}' unparseable"
        sheet, coord = (m.group(1) or m.group(2)), m.group(3)
        if sheet not in self.wb.sheetnames:
            return f"MISS: no sheet '{sheet}'"
        from openpyxl.comments import Comment
        cell = self.wb[sheet][coord]
        self.writer.log["flags"].append(f"{sheet}!{coord}")
        cell.fill = self.writer.fills["red"]
        cell.comment = Comment(str(args.get("why", "flagged for review"))[:400],
                               "Model Update Agent")
        self.book.record(f"{sheet}!{coord}", "C", "flag",
                         note=str(args.get("why", ""))[:150])
        return "FLAGGED"

    def t_not_disclosed(self, args):
        """The honest stale exit for NON-KEY rows: proves the search, lifts
        the red flag (the _REPORT lists it instead — new-objectives law:
        proven non-disclosure stays stale WITHOUT a cell flag)."""
        ref = str(args.get("cell", ""))
        looked = args.get("looked") or []
        m = re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]{1,3})(\d+)$",
                     ref.replace("$", ""))
        if not m:
            return f"MISS: cell ref '{ref}' unparseable"
        sheet, col, row = (m.group(1) or m.group(2)), m.group(3), int(m.group(4))
        if (sheet, row) in self._key_rows():
            return ("REFUSED: key rows are correct-or-flagged — a key may "
                    "never be quietly stale; keep the flag")
        # LAZY-ND GUARD (mindmap law: 'not disclosed' must be PROVEN, not
        # asserted — past agents labelled 'unable to find' as 'not
        # disclosed' while the figure sat in the document). A fact-check,
        # not a mapping: if the current document prints a line whose name
        # matches this row exactly, or whose comparative ties this row's
        # prior at identity, the claim is false and is refused with the
        # evidence quoted.
        t0 = self.targets.get((sheet, row))
        if t0 is not None:
            from .numerics import norm_label as _nl
            t_norm = _nl(str(t0.label or "")).replace(" ", "")
            pv0 = t0.prior_value
            prior_docs = self.ledger.prior_period_docs()
            for it in self.ledger.items:
                if (it.doc in prior_docs or getattr(it, "disputed", False)
                        or not it.nums):
                    continue
                name_hit = (len(t_norm) >= 3 and
                            _nl(str(it.label)).replace(" ", "") == t_norm)
                prior_hit = (isinstance(pv0, (int, float))
                             and abs(pv0) >= 1.0 and any(
                                 abs(abs(to_model_units(n, s)) - abs(pv0))
                                 <= max(0.6, abs(pv0) * 5e-4)
                                 for n in it.nums for s in SCALES))
                if name_hit or prior_hit:
                    return (f"REFUSED: not_disclosed is a PROVEN claim, and "
                            f"the report prints this line — p{it.page}: "
                            f"'{it.source_line[:80]}'. Map it (in the "
                            f"model's units) or flag your uncertainty; the "
                            f"claim as made is false.")
        try:
            self.book.claim_not_disclosed(f"{sheet}!{row}",
                                          [str(x) for x in looked])
        except ValueError as e:
            return f"REFUSED: {e}"
        coord = f"{col}{row}"
        full = f"{sheet}!{coord}"
        self.writer.log["flags"] = [f for f in self.writer.log["flags"]
                                    if f != full]
        pcol = prior_column(self.spec, sheet, self.ty)
        if sheet in self.wb.sheetnames:
            import copy as _copy
            cell = self.wb[sheet][coord]
            if pcol:
                cell._style = _copy.copy(self.wb[sheet][f"{pcol}{row}"]._style)
            from openpyxl.comments import Comment
            cell.comment = Comment(
                "Not updated this period: figure not disclosed (search "
                "trail in _REPORT).", "Model Update Agent")
        self.book.entries.pop(full, None)
        return "ACCEPTED: left stale, unflagged, listed in _REPORT"

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

    NO_DEDUP = ("rescore", "note", "todo", "finish", "diagnose_balance",
                "statement_diff", "list_flags", "infer_adjustments")

    def run(self, extra_objectives=()):
        prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        for o in extra_objectives:
            self.todos.append(str(o)[:200])
        self.finished = None
        while self.budget > 0 and self.finished is None:
            self.budget -= 1
            user = prompt + "\n\n" + self._state_block()

            def _val(o):
                if not isinstance(o.get("action"), str):
                    return ["missing 'action'"]
                if o["action"] not in self.box.tools:
                    return [f"unknown action '{o['action']}'; one of "
                            f"{self.box.names()}"]
                return []
            try:
                act = self.client.json(self._system, user, _val,
                                       repair_retries=1)
            except Exception as e:
                self.log.append(f"agent loop: call failed: {e}")
                break
            name = act["action"]
            args = {k: v for k, v in (act.get("args") or {}).items()
                    if not k.startswith("_")}     # engine may not set grades
            fingerprint = name + json.dumps(args, sort_keys=True,
                                            ensure_ascii=False)
            if name not in self.NO_DEDUP and fingerprint in self._done:
                result = ("REPEAT: you already ran exactly this action — "
                          "take a DIFFERENT one (your history shows what "
                          "you learned).")
            else:
                self._done.add(fingerprint)
                result = self.box.call(name, args)
            # CONVERSION PRESSURE (run-1-live autopsy: 75/120 actions were
            # traces; findings never became writes). Investigation is
            # capped by steering, not by force: after a stretch with no
            # write, every result carries an escalating nudge to convert.
            kind = self.box.tools[name].kind if name in self.box.tools else "query"
            if kind == "write" and not str(result).startswith(
                    ("MISS", "REFUSED", "TOOL ERROR")):
                self._streak = 0
            else:
                self._streak = getattr(self, "_streak", 0) + 1
            if self._streak >= 5:
                result = (str(result) + "\nSTEERING: "
                          f"{self._streak} actions without a landed write — "
                          "CONVERT what you already know: diagnose_balance "
                          "names GUILTY rows for apply_diff; set_input needs "
                          "{\"cell\": \"Sheet!U49\", \"value\": N, \"why\": "
                          "\"p<page>: ...\"}; if nothing is provable, flag "
                          "or plug and move to the next objective.")
            snip = json.dumps(args, ensure_ascii=False)[:90]
            first = str(result).splitlines()[0][:110] if result else ""
            # history is the compact trail; the FULL result of the latest
            # action goes to the state block. (Run-1-live discovery: the
            # legacy loop only ever showed the engine the first 110 chars
            # of each result — diagnose/find output was invisible, which
            # fed the trace-spam. The engine must SEE what its tools say.)
            self._last = f"{name} {snip}\n{str(result)[:3500]}"
            self.history.append(f"{name} {snip} -> {first}")
            self.log.append(f"agent: {name} {snip} -> {first}")
        if self.finished is None:
            self.finished = "(action budget exhausted)"
        return self.finished
