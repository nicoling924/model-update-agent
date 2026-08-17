"""L0 planner + L1 closer — the packetized thinking loop (REDESIGN.md).

The agent thinks where judgment lives; mechanics are hands:
- L0 (rare): reads the scorecard + queue + last report, picks the packet.
- L1 compile: ONE call fills a sheet's open column as a write array;
  the chokepoint applies each write and returns an APPLY REPORT; one
  repair pass on the rejections. No inspect tools exist here.
- L1 surgeon: the runtime AUTO-SURFACES the diagnosis (leaf tree with
  evidence status + reclass candidates); the only legal reply is
  decisions[] — write / flag / retain / plug per leaf. "I looked" is
  schema-invalid. One extra round if the apply report contains new facts.

All writes run through the existing guarded toolkit (AgentLoop's
set_input / plug_residual / flag_cell / not_disclosed) — transactional,
cited, truth-guarded, world-banded. Guards never appear in prompts; they
appear as rejection REASONS in apply reports, which is how a mid-tier
model learns from THIS run instead of a rulebook of past ones.
"""
import json
from pathlib import Path

from . import packets
from .checks import scorecard, summarize

_PROMPTS = Path(__file__).resolve().parent.parent / "prompts"

MAX_L0_CALLS = 16
MAX_PACKETS = 24
SURGEON_ROUNDS = 2
COMPILE_ROUNDS = 2


def _p(name):
    return (_PROMPTS / name).read_text(encoding="utf-8")


class PacketCloser:
    def __init__(self, toolkit, client, log):
        """toolkit = a fully-wired AgentLoop (used ONLY as the guarded
        tool layer — its own loop is never run)."""
        self.tk = toolkit
        self.client = client
        self.log = log
        self.reports = []          # packet reports, newest last
        self.calls = 0

    # -- shared -------------------------------------------------------------

    def _card_text(self):
        card = scorecard(self.tk.wb, self.tk.spec, self.tk.ty,
                         served=self.tk.served,
                         flags=self.tk.writer.log["flags"])
        return summarize(card, self.tk.ty, flags=self.tk.writer.log["flags"],
                         spec=self.tk.spec, wb=self.tk.wb)

    def _json(self, system, user, validate):
        self.calls += 1
        return self.client.json(system, user, validate, repair_retries=1)

    # -- L0 -----------------------------------------------------------------

    def pick_packet(self, queue):
        state = "\n".join([
            "== SCORECARD ==", self._card_text(),
            "== PACKET QUEUE ==", *(f"  {p}" for p in queue),
            "== LAST PACKET REPORT ==",
            self.reports[-1] if self.reports else "  (none yet)"])

        def _val(o):
            if o.get("packet") not in set(queue) | {"deliver"}:
                return [f"packet must be one of {queue} or 'deliver'"]
            return []
        try:
            out = self._json(_p("method.md"), _p("l0.md") + "\n\n" + state,
                             _val)
        except Exception as e:
            self.log(f"[closer] L0 failed ({e}) — taking queue head")
            return queue[0] if queue else "deliver"
        sit = str(out.get("situation", ""))[:400]
        if sit:
            self.log(f"[closer] L0: {sit.splitlines()[0][:120]}")
        return out["packet"]

    # -- compile ------------------------------------------------------------

    def run_compile(self, sheet):
        rows, chunks = packets.compile_card(
            self.tk.wb, self.tk.spec, self.tk.ty, sheet, self.tk.served,
            self.tk.writer.log, self.tk.ledger, docs=self.tk.docs)
        if not rows:
            report = f"compile:{sheet}: nothing open"
            self.reports.append(report)
            return report
        n_ok = n_rej = n_nd = n_flag = 0
        for chunk in chunks:
            result = self._compile_chunk(sheet, chunk)
            n_ok += result[0]
            n_rej += result[1]
            n_nd += result[2]
            n_flag += result[3]
        report = (f"compile:{sheet}: {n_ok} written, {n_rej} rejected, "
                  f"{n_nd} not-disclosed, {n_flag} flagged "
                  f"(of {len(rows)} open)")
        self.log(f"[closer] {report}")
        self.reports.append(report)
        return report

    def _val_compile(self, o):
        errs = []
        if not isinstance(o.get("writes", []), list):
            errs.append("'writes' must be a list")
        for w in o.get("writes", []) or []:
            if not (isinstance(w, dict) and w.get("cell")
                    and w.get("why") is not None):
                errs.append("each write needs cell, value, why")
                break
        return errs

    def _compile_chunk(self, sheet, chunk):
        n_ok = n_rej = n_nd = n_flag = 0
        user = _p("compile.md") + "\n\n" + chunk
        rejections = []
        for round_i in range(COMPILE_ROUNDS):
            try:
                out = self._json(_p("method.md"), user, self._val_compile)
            except Exception as e:
                self.log(f"[closer] compile call failed: {e}")
                break
            round_rej = []
            for w in out.get("writes", []) or []:
                r = self.tk.t_set_input({"cell": str(w.get("cell")),
                                         "value": w.get("value"),
                                         "why": str(w.get("why", ""))})
                if str(r).startswith("WRITTEN"):
                    n_ok += 1
                else:
                    round_rej.append(f"{w.get('cell')}: {str(r)[:140]}")
            for nd in out.get("not_disclosed", []) or []:
                r = self.tk.t_not_disclosed(
                    {"cell": str(nd.get("cell")),
                     "looked": nd.get("looked") or []})
                if str(r).startswith("ACCEPTED"):
                    n_nd += 1
                else:
                    round_rej.append(f"{nd.get('cell')}: {str(r)[:140]}")
            for f in out.get("flags", []) or []:
                r = self.tk.t_flag_cell({"cell": str(f.get("cell")),
                                         "why": str(f.get("why", ""))})
                if str(r).startswith("FLAGGED"):
                    n_flag += 1
            n_rej = len(round_rej)
            if not round_rej or round_i == COMPILE_ROUNDS - 1:
                break
            user = (_p("compile.md") + "\n\n" + chunk +
                    "\n\n== APPLY REPORT: these were REJECTED — read each "
                    "reason, it is information about the model ==\n" +
                    "\n".join(round_rej[:25]) +
                    "\nRe-decide ONLY these cells (write with a better "
                    "value/site, not_disclosed, or flag).")
            rejections = round_rej
        return n_ok, n_rej, n_nd, n_flag

    # -- surgeon ------------------------------------------------------------

    def run_surgeon(self, check_ref, extra_context=""):
        if check_ref.startswith("key:"):
            diag = self.tk.t_diagnose_balance({"key": check_ref[4:]})
        else:
            diag = self.tk.t_diagnose_balance({"check": check_ref})
        if str(diag).startswith("MISS"):
            report = f"residual:{check_ref}: {str(diag)[:100]}"
            self.reports.append(report)
            return report
        n_ok = n_flag = n_plug = n_rej = 0
        user = (_p("surgeon.md") + "\n\n== DIAGNOSIS (auto-surfaced) ==\n"
                + str(diag) + (("\n\n" + extra_context) if extra_context
                               else ""))
        for round_i in range(SURGEON_ROUNDS):
            try:
                out = self._json(_p("method.md"), user, self._val_surgeon)
            except Exception as e:
                self.log(f"[closer] surgeon call failed: {e}")
                break
            round_rej = []
            for d in out.get("decisions", []) or []:
                leaf = str(d.get("leaf", ""))
                do = str(d.get("do", ""))
                why = str(d.get("why", ""))
                if do == "write":
                    r = self.tk.t_set_input({"cell": leaf,
                                             "value": d.get("value"),
                                             "why": why})
                    if str(r).startswith("WRITTEN"):
                        n_ok += 1
                    else:
                        round_rej.append(f"{leaf} write: {str(r)[:140]}")
                elif do == "flag":
                    if str(self.tk.t_flag_cell(
                            {"cell": leaf, "why": why})).startswith("FLAGGED"):
                        n_flag += 1
                elif do == "retain":
                    self.tk.notes.append(f"retained (analyst assumption): "
                                         f"{leaf} — {why[:80]}")
                elif do == "plug":
                    r = self.tk.t_plug_residual({"check": check_ref,
                                                 "into": leaf, "why": why})
                    if str(r).startswith("PLUGGED"):
                        n_plug += 1
                    else:
                        round_rej.append(f"{leaf} plug: {str(r)[:140]}")
            n_rej = len(round_rej)
            # a second round only when rejections carry NEW facts
            if not round_rej or round_i == SURGEON_ROUNDS - 1:
                break
            fresh_diag = self.tk.t_diagnose_balance({"check": check_ref})
            user = (_p("surgeon.md") + "\n\n== DIAGNOSIS (updated) ==\n"
                    + str(fresh_diag) +
                    "\n\n== APPLY REPORT: rejected decisions ==\n"
                    + "\n".join(round_rej[:15]) +
                    "\nRe-decide only what the reasons change.")
        report = (f"residual:{check_ref}: {n_ok} written, {n_plug} plugged, "
                  f"{n_flag} flagged, {n_rej} rejected")
        self.log(f"[closer] {report}")
        self.reports.append(report)
        return report

    def _val_surgeon(self, o):
        ds = o.get("decisions")
        if not isinstance(ds, list) or not ds:
            return ["'decisions' list required — a diagnosis is complete "
                    "when each leaf has a disposition, not when more has "
                    "been read"]
        for d in ds:
            if not isinstance(d, dict) \
                    or d.get("do") not in ("write", "flag", "retain", "plug"):
                return ["each decision needs leaf + do in "
                        "write|flag|retain|plug"]
            if d.get("do") == "write" and d.get("value") is None:
                return ["write decisions need a value"]
        return []

    # -- the closing bell (council wall-2 design) ---------------------------

    def closing_bell(self):
        """One deterministic final pass: each still-failing check FAMILY
        (a residual propagating across years is ONE generator) gets ONE
        terminal disposition — an executed plug or a reasoned, cited
        flag. Runs exactly once; no new research; the draw disappears
        because the decision is forced, not because behavior is capped."""
        card = scorecard(self.tk.wb, self.tk.spec, self.tk.ty,
                         served=self.tk.served,
                         flags=self.tk.writer.log["flags"])
        gens = {}
        for c in card["checks"]:
            if c["status"] == "PASS":
                continue
            key = c["name"].split(" (")[0].replace("!r", "!")
            gens.setdefault(key, []).append(
                (c["year"], c["got"]))
        for ref, years in list(gens.items())[:4]:
            diag = self.tk.t_diagnose_balance({"check": ref})
            vec = ", ".join(f"{y}: {g:,.2f}" if isinstance(g, (int, float))
                            else f"{y}: ?" for y, g in years)
            user = (_p("closing_bell.md")
                    + f"\n\nGENERATOR {ref} — residual vector across years: "
                    f"{vec}\n(one 2025 cause usually propagates to every "
                    f"forecast year — one disposition closes the vector)\n\n"
                    "== DIAGNOSIS ==\n" + str(diag))

            def _val(o):
                if o.get("disposition") not in ("plug", "flag"):
                    return ["disposition must be 'plug' or 'flag'"]
                if o["disposition"] == "plug" and not o.get("into"):
                    return ["plug needs 'into'"]
                if not o.get("why"):
                    return ["'why' required — the analyst reads it"]
                return []
            try:
                out = self._json(_p("method.md"), user, _val)
            except Exception as e:
                self.log(f"[closer] closing bell call failed: {e}")
                continue
            # the bell is a DECISION, and a refused plug is information —
            # one informed retry, then the reasoned-flag fallback. The
            # bell never ends in silence.
            for attempt in range(2):
                if out["disposition"] == "plug":
                    r = self.tk.t_plug_residual({"check": ref,
                                                 "into": str(out["into"]),
                                                 "why": str(out["why"])})
                    self.log(f"[closer] bell {ref}: plug -> "
                             f"{str(r).splitlines()[0][:90]}")
                    if str(r).startswith("PLUGGED") or attempt == 1:
                        if not str(r).startswith("PLUGGED"):
                            out = {"disposition": "flag",
                                   "why": f"plug unavailable: {str(r)[:120]}"}
                            continue
                        break
                    try:
                        out = self._json(
                            _p("method.md"),
                            user + "\n\n== APPLY REPORT ==\n"
                            + str(r)[:200]
                            + "\nThe reason above is information about the "
                            "model. Decide again: another legal site, or "
                            "a reasoned flag.", _val)
                    except Exception:
                        out = {"disposition": "flag",
                               "why": f"plug refused: {str(r)[:120]}"}
                else:
                    sheet, row = ref.split("!")
                    col = self.tk._tcol(sheet)
                    self.tk.t_flag_cell({"cell": f"{sheet}!{col}{row}",
                                         "why": f"closing bell: {out['why']}"})
                    self.log(f"[closer] bell {ref}: flagged — "
                             f"{str(out['why'])[:90]}")
                    break
            self.reports.append(f"bell:{ref}: {out['disposition']}")

    # -- the atomic reclass packet (council wall-3 design) ------------------

    def atomic_reclass(self, key_a, key_b, amount):
        """Twin-residual signature: both keys off by the same amount with
        opposite signs — ONE item is booked in the wrong section. The
        packet shows both sections side by side and asks the single bound
        question; the answer is an ATOMIC two-legged move (both writes or
        neither), verified against both keys and reverted if it does not
        close them."""
        sides = []
        for kname in (key_a, key_b):
            match = next((k for k in self.tk.spec.get("key_rows") or []
                          if kname.lower() in
                          str(k.get("name", "")).lower()), None)
            if match is None:
                return f"reclass: key '{kname}' not found"
            sheet, row = match["sheet"], int(match["row"])
            col = self.tk._tcol(sheet)
            leaves = []
            for (sh, coord) in dict.fromkeys(
                    self.tk._leaf_inputs(sheet, f"{col}{row}")):
                v = self.tk.wb[sh][coord].value
                if not isinstance(v, (int, float)):
                    continue
                t = self.tk.targets.get(
                    (sh, int(coord[len(coord.rstrip('0123456789')):])))
                lab = str(t.label)[:36] if t is not None else "?"
                leaves.append(f"  {sh}!{coord} '{lab}' = {v:,.2f}")
            sides.append((match.get("name"), f"{sheet}!{col}{row}", leaves))
        user = (_p("reclass.md") + "\n\n"
                + f"AMOUNT: ≈{amount:,.2f} (same size, opposite signs)\n\n"
                + "\n\n".join(
                    f"== SECTION: {n} ({ref}) ==\n" + "\n".join(ls)
                    for n, ref, ls in sides))

        def _val(o):
            if "move" in o:
                m = o["move"]
                if not (isinstance(m, dict) and m.get("from")
                        and m.get("to") and m.get("amount") is not None
                        and m.get("why")):
                    return ["move needs from, to, amount, why"]
                return []
            if "flag" in o:
                return []
            return ["answer with {'move': {...}} or {'flag': '<why>'}"]
        try:
            out = self._json(_p("method.md"), user, _val)
        except Exception as e:
            return f"reclass call failed: {e}"
        if "flag" in out:
            self.log(f"[closer] reclass: flagged — {str(out['flag'])[:90]}")
            return "reclass: flagged"
        m = out["move"]
        return self._apply_atomic_move(str(m["from"]), str(m["to"]),
                                       float(m["amount"]), str(m["why"]),
                                       key_a, key_b)

    def _key_tie(self, kname):
        match = next((k for k in self.tk.spec.get("key_rows") or []
                      if kname.lower() in str(k.get("name", "")).lower()),
                     None)
        if match is None:
            return None
        t = self.tk.targets.get((match["sheet"], int(match["row"])))
        got = self.tk._diff_value(t) if t is not None else None
        if got is None:
            return None
        from .evaluator import Evaluator
        try:
            mv = Evaluator(self.tk.wb).cell(
                match["sheet"],
                f"{self.tk._tcol(match['sheet'])}{match['row']}")
        except Exception:
            return None
        from .numerics import row_tol
        return abs(abs(mv) - abs(got[0])) <= max(row_tol(got[0]),
                                                 abs(got[0]) * 5e-3)

    def _apply_atomic_move(self, src, dst, amount, why, key_a, key_b):
        import re as _re
        cells = []
        for ref in (src, dst):
            m = _re.match(r"^(?:'([^']+)'|([^!]+))!([A-Z]{1,3})(\d+)$",
                          ref.replace("$", ""))
            if not m:
                return f"reclass: unparseable cell {ref}"
            sh, co = (m.group(1) or m.group(2)).strip(), \
                f"{m.group(3)}{m.group(4)}"
            v = self.tk.wb[sh][co].value
            if not isinstance(v, (int, float)):
                return f"reclass: {ref} is not a numeric input cell"
            cells.append((sh, co, v))
        (s_sh, s_co, s_v), (d_sh, d_co, d_v) = cells
        self.tk.wb[s_sh][s_co].value = s_v - amount
        self.tk.wb[d_sh][d_co].value = d_v + amount
        ok_a, ok_b = self._key_tie(key_a), self._key_tie(key_b)
        if ok_a and ok_b:
            # commit through the chokepoint for notes/flags/provenance
            self.tk.wb[s_sh][s_co].value = s_v
            self.tk.wb[d_sh][d_co].value = d_v
            r1 = self.tk.t_set_input({"cell": f"{s_sh}!{s_co}",
                                      "value": s_v - amount,
                                      "why": f"atomic reclass (leg 1/2): "
                                             f"{why}"})
            r2 = self.tk.t_set_input({"cell": f"{d_sh}!{d_co}",
                                      "value": d_v + amount,
                                      "why": f"atomic reclass (leg 2/2): "
                                             f"{why}"})
            if str(r1).startswith("WRITTEN") and str(r2).startswith("WRITTEN"):
                self.log(f"[closer] reclass MOVED {amount:,.2f} "
                         f"{src} -> {dst}: both keys tie")
                return "reclass: moved, both keys tie"
            # one leg refused -> restore both
            self.tk.t_set_input({"cell": f"{s_sh}!{s_co}", "value": s_v,
                                 "why": f"reclass revert; ties {src}"})
            self.tk.t_set_input({"cell": f"{d_sh}!{d_co}", "value": d_v,
                                 "why": f"reclass revert; ties {dst}"})
            return "reclass: a leg was refused by the chokepoint — reverted"
        self.tk.wb[s_sh][s_co].value = s_v
        self.tk.wb[d_sh][d_co].value = d_v
        return (f"reclass: move did not make both keys tie "
                f"(a={ok_a}, b={ok_b}) — reverted, nothing written")

    # -- the run ------------------------------------------------------------

    def run(self):
        done = set()
        for _ in range(MAX_PACKETS):
            if self.calls >= 140:
                self.log("[closer] call budget reached — delivering")
                break
            queue = [p for p in packets.derive_queue(
                self.tk.wb, self.tk.spec, self.tk.ty, self.tk.served,
                self.tk.writer.log) if p not in done]
            if not queue or queue == ["deliver"]:
                break
            if len(self.reports) >= MAX_L0_CALLS:
                pid = queue[0]          # planner budget spent: take heads
            else:
                pid = self.pick_packet(queue)
            if pid == "deliver":
                break
            kind, arg = packets.parse_packet(pid)
            if kind == "compile":
                self.run_compile(arg)
            elif kind == "residual":
                self.run_surgeon(arg)
            else:
                self.log(f"[closer] unknown packet {pid} — skipped")
            done.add(pid)
        return "; ".join(self.reports[-6:]) or "(no packets run)"

    def run_repairs(self, findings):
        """Police findings -> repair work: key/check findings become
        surgeon packets; the rest are handed as one decisions card."""
        if not findings:
            return ""
        card = scorecard(self.tk.wb, self.tk.spec, self.tk.ty,
                         served=self.tk.served,
                         flags=self.tk.writer.log["flags"])
        failing = [c["name"].split(" (")[0].replace("!r", "!")
                   for c in card["checks"] if c["status"] != "PASS"]
        targets = list(dict.fromkeys(failing))[:6]
        # announced-key findings become key-mode surgeon packets
        for f in findings:
            s = str(f)
            if s.startswith("announced: ") and ":" in s[11:]:
                targets.append("key:" + s[11:].split(":", 1)[0].strip())
        ctx = ("== POLICE FINDINGS ==\n"
               + "\n".join(str(f)[:150] for f in findings[:10]))
        # TWIN-DELTA insight (auto-surfaced information, like leaf trees):
        # two keys off by the SAME amount means ONE item sits in the wrong
        # section — cross-key knowledge no single packet can see.
        import re as _re
        deltas = []
        for f in findings:
            m = _re.search(r"announced: ([^:]+): model ([-\d.,]+) vs "
                           r"disclosed ([-\d.,]+)", str(f))
            if m:
                try:
                    d = (float(m.group(2).replace(",", ""))
                         - float(m.group(3).replace(",", "")))
                    deltas.append((m.group(1).strip(), d))
                except ValueError:
                    pass
        moved_keys = set()
        for i in range(len(deltas)):
            for j in range(i + 1, len(deltas)):
                a, b = deltas[i], deltas[j]
                if abs(abs(a[1]) - abs(b[1])) <= max(1.0, abs(a[1]) * 0.02):
                    # council wall-3: the twin signature triggers the
                    # ATOMIC RECLASS packet — one bound question, a
                    # two-legged move or nothing.
                    r = self.atomic_reclass(a[0], b[0], abs(a[1]))
                    self.log(f"[closer] reclass {a[0]}/{b[0]} "
                             f"(±{abs(a[1]):,.2f}): {str(r)[:110]}")
                    self.reports.append(f"reclass:{a[0]}/{b[0]}: {r}")
                    if "both keys tie" in str(r):
                        moved_keys.update({a[0], b[0]})
        if deltas and not moved_keys:
            self.log(f"[closer] reclass scan: {len(deltas)} announced "
                     "deltas, no twin move landed")
        targets = [t for t in targets
                   if not (t.startswith("key:")
                           and t[4:] in moved_keys)]
        for ref in list(dict.fromkeys(targets))[:8]:
            if self.calls >= 160:
                break
            self.run_surgeon(ref, extra_context=ctx)
        return self.reports[-1] if self.reports else ""
