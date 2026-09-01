"""THE WORK-QUEUE INVERSION (council ruling 2026-09-01).

Run-210 autopsy: a free-roaming weak LLM spent 90 actions on 61 repeated
investigations, 9 plug attempts and ZERO evidence writes, while every
good number in the run came from code. The Fable-drive proved the tools
suffice for a strong brain — and that the strong brain's real edge was
an ORDER, not freedom. So stage 4 inverts: THE MACHINE OWNS THE PLAN,
the LLM answers one bounded question at a time.

Council-mandated mechanics (architect / red-team / operator, all seats):
- Lazy cards: a card is rendered from LIVE workbook state at pop time,
  never up front — staleness impossible by construction.
- Phase 0 auto-resolve: everything the gates already decide (GUILTY
  diffs, stale composites) is applied by code BEFORE any LLM call, via
  the SAME guarded tools — a reordering of existing authority, never a
  new writer.
- Evidence before plugs: a check's PLUG card may not be dealt while
  component cards for that check remain open (per-check phase boundary).
- Flag is the lazy answer: every card's default (LLM absent, malformed,
  circuit-open, deadline) is the abstaining action — red flag, verdict
  SUSPICIOUS, or skip-to-terminal-ladder. Worst case = the machinery
  baseline, which delivers-with-flags.
- Cards execute ONLY through the ObjectiveLoop's guarded tool methods
  (t_set_input, t_apply_diff, t_rewrite_constants, t_verdict,
  t_plug_residual, t_flag_cell): the card is a proposal, the writegate
  stays the referee. No new write paths.
- Candidates carry their own indictments: prior-vintage, wide-row,
  loose-tie and proportion warnings are printed ON the card so the
  answerer sees the machine's doubts (red-team: sycophancy defence).

Pure code except the one client.json call per card; fully drivable
offline through the `answerer` hook.
"""
import re
import time
from dataclasses import dataclass, field

from .checks import prior_column, year_columns
from .evaluator import Evaluator
from .numerics import row_tol, to_model_units

MAX_CARDS = 60
CALL_CAP = 40
DEADLINE_S = 1200
MAX_CANDS = 4

_SYSTEM = (
    "You are an equity research analyst answering ONE bounded question "
    "about one cell of a valuation model. Everything needed is on the "
    "card: the model row, its history, and machine-extracted candidate "
    "lines from the disclosure with the machine's own warnings. Reply "
    "with JSON {\"answer\": \"<one of the listed answer ids>\", \"why\": "
    "\"<one sentence>\"}. Rules: a warned candidate needs a reason to "
    "trust it; when unsure, answer the abstaining option — a red flag "
    "is a correct deliverable, a wrong number is the one unforgivable "
    "failure.")


@dataclass
class WorkItem:
    kind: str                 # SERVE | TRIPWIRE | PLUG
    sheet: str = ""
    row: int = 0
    check: str = ""           # owning check "Sheet!row" (PLUG)
    refs: list = field(default_factory=list)   # tripwire chain members
    priority: float = 0.0
    state: str = "OPEN"       # OPEN | DONE | DEFAULTED | MOOT


def _tcol(loop, sheet):
    return year_columns(loop.spec, sheet).get(loop.ty)


def _prior_of(loop, sheet, row):
    t = loop.targets.get((sheet, row))
    if t is not None and isinstance(t.prior_value, (int, float)):
        return float(t.prior_value), t
    pcol = prior_column(loop.spec, sheet, int(loop.ty))
    if pcol and sheet in loop.wb.sheetnames:
        v = loop.wb[sheet][f"{pcol}{row}"].value
        if isinstance(v, (int, float)):
            return float(v), t
        if isinstance(v, str) and v.startswith("="):
            try:
                return float(Evaluator(loop.wb).cell(sheet, f"{pcol}{row}")), t
            except Exception:
                pass
    return None, t


def candidates_for(loop, sheet, row, k=MAX_CANDS):
    """Prior-identity candidates for one model row, WITH indictments.
    Reuses the join's own pairing law (adjacent pair whose second element
    ties the prior) but returns EVERY tying line instead of demanding a
    single agreeing one — the ambiguity is the card's reason to exist."""
    from .stage2_join import ratify_page_scales, _tying_pairs, _world_tol
    pv, t = _prior_of(loop, sheet, row)
    if pv is None or pv == 0:
        return []
    p2 = getattr(t, "prior2_value", None) if t is not None else None
    periods = getattr(loop.ledger, "_doc_periods", None) or {}
    # WIDER than join_pool (face authority relaxed): a card is a judged
    # PROPOSAL with provenance printed on it, not a silent serve — the
    # SoC-style regulatory schedules live on non-face pages (oracle
    # audit: the whole SoC statement block was invisible to cards).
    # The face tag stays on every candidate; the writegate still
    # referees the answer.
    pool = [it for it in loop.ledger.items
            if it.joinable() and periods.get(it.doc) != "prior"]
    priors = [tt.prior_value for tt in loop.targets.values()
              if isinstance(tt.prior_value, (int, float))]
    scales = ratify_page_scales(pool, priors, [])
    pool = [it for it in pool if (it.doc, it.page) in scales]
    tol = _world_tol(pv)
    exact_home = any(
        abs(abs(to_model_units(n, scales[(it.doc, it.page)])) - abs(pv))
        <= 0.6
        for it in pool for n in it.nums)
    out = _companion_candidates(loop, pv, p2, periods, pool, scales)
    for it in pool:
        s = scales[(it.doc, it.page)]
        ns = [to_model_units(n, s) for n in it.nums]
        for sv, i in _tying_pairs(ns, pv, tol):
            warns = []
            if periods.get(it.doc) != "current":
                warns.append("document vintage UNKNOWN — may be a "
                             "prior-year filing; prefer a current-doc line")
            off = abs(abs(ns[i + 1]) - abs(pv))
            tie_off = off
            if off > 0.6 and exact_home:
                warns.append(f"loose tie (off {off:,.1f}) while the exact "
                             "prior prints elsewhere — likely a different "
                             "definition")
            if not (abs(sv) <= 100 * abs(pv) and abs(sv) * 100 >= abs(pv)):
                continue        # per-share-next-to-total class: 1.89
                                # paired with a 4,775 prior is not a serve
            if abs(abs(sv) - abs(pv)) <= row_tol(pv, base=0.01):
                if periods.get(it.doc) == "current" and \
                        loop.ledger.face(it.doc, it.page):
                    warns.append("value UNCHANGED vs prior — a current "
                                 "statement face may confirm this")
                else:
                    warns.append("value EQUALS this row's prior — may be "
                                 "the prior-year column/table, not this "
                                 "year")
            if isinstance(p2, (int, float)) and \
                    abs(abs(sv) - abs(p2)) <= max(0.6, abs(p2) * 5e-4):
                warns.append("value equals prior2 — the year BEFORE last")
            if i + 2 < len(ns):
                nxt = ns[i + 2]
                series = isinstance(p2, (int, float)) and \
                    abs(abs(nxt) - abs(p2)) <= max(0.6, abs(p2) * 5e-4)
                delta = abs(nxt - (sv - ns[i + 1])) <= 1.0 \
                    or abs(nxt - abs(sv - ns[i + 1])) <= 1.0
                if not (series or delta) and abs(nxt) >= 10:
                    warns.append("wide row without a time-series shape — "
                                 "may be a SEGMENT row (column error)")
            if abs(pv) >= 50 and (abs(sv) > 8 * abs(pv)
                                  or abs(sv) * 8 < abs(pv)):
                warns.append(f"out of proportion vs prior ({abs(sv/pv):,.1f}x)")
            if abs(pv) < 50:
                warns.append("small-value row — ties are coincidence-"
                             "prone; prefer derivation or leave red")
            from .numerics import kinship
            lab_m = str(getattr(t, "label", "") or "")
            if lab_m and not kinship(lab_m, str(it.label)):
                warns.append("label unrelated to the model row's — a "
                             "numeric coincidence unless the position "
                             "proves it")
            face = loop.ledger.face(it.doc, it.page)
            out.append({"value": sv, "doc": it.doc, "page": it.page,
                        "line": str(it.label)[:60], "face": face or "no-face",
                        "tie_off": tie_off, "warnings": warns})
    seen, uniq = set(), []
    # EXACT TIE OUTRANKS EVERYTHING (strict-policy audit 2026-09-01:
    # 'Operating costs' twins — the group P&L line on a face page
    # outsorted the SoC schedule line whose prior tied EXACTLY; 18/30
    # wrong picks were ordering, not absence)
    for c in sorted(out, key=lambda c: (round(c.get("tie_off", 0.05), 1),
                                        len(c["warnings"]),
                                        c["face"] == "no-face",
                                        c["doc"], c["page"])):
        key = round(c["value"], 1)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    return uniq[:k]


def _companion_candidates(loop, pv, p2, periods, pool, scales, k=MAX_CANDS):
    """THE POSITIONAL COMPANION GENERATOR (oracle audit 2026-09-01: 33 of
    33 missed truths were PRINTED — in current-year segment tables that
    hold no prior at all; the prior sits at the SAME POSITION in the twin
    prior-year table). The by-hand method: find the prior in a table, read
    the same-position cell of the same-labelled row in the companion
    current table."""
    from .numerics import norm_label
    if abs(pv) < 10:
        return []
    by_label = {}
    for it in pool:
        by_label.setdefault(norm_label(str(it.label)), []).append(it)
    out = []
    for it_p in pool:
        s_p = scales[(it_p.doc, it_p.page)]
        ns_p = [to_model_units(n, s_p) for n in it_p.nums]
        for kpos, n in enumerate(ns_p):
            if abs(abs(n) - abs(pv)) > max(0.6, abs(pv) * 5e-4):
                continue
            for it_c in by_label.get(norm_label(str(it_p.label)), []):
                if (it_c.doc, it_c.page, it_c.table_id) == \
                        (it_p.doc, it_p.page, it_p.table_id):
                    continue
                if periods.get(it_c.doc) != "current":
                    continue
                s_c = scales[(it_c.doc, it_c.page)]
                ns_c = [to_model_units(m, s_c) for m in it_c.nums]
                if kpos >= len(ns_c):
                    continue
                sv = ns_c[kpos] if n >= 0 else -abs(ns_c[kpos])
                if abs(abs(sv) - abs(pv)) <= max(0.6, abs(pv) * 5e-4) \
                        and len(ns_c) > 1:
                    continue        # companion also holds the prior there:
                                    # same-vintage twin, not a current table
                if not (abs(sv) <= 30 * abs(pv) and abs(sv) * 30 >= abs(pv)):
                    continue
                warns = []
                if isinstance(p2, (int, float)) and abs(abs(sv) - abs(p2)) \
                        <= max(0.6, abs(p2) * 5e-4):
                    warns.append("value equals prior2 — the year BEFORE "
                                 "last")
                out.append({
                    "value": sv, "doc": it_c.doc, "page": it_c.page,
                    "line": str(it_c.label)[:60],
                    "face": loop.ledger.face(it_c.doc, it_c.page)
                    or "no-face",
                    "warnings": warns,
                    "basis": (f"positional: prior {pv:,.1f} at slot {kpos} "
                              f"of the same-labelled row, {it_p.doc[:20]} "
                              f"p{it_p.page}")})
    return out[: k * 3]


def _red_cells(loop):
    """Red-flagged target-column cells: 'Sheet!AI7' -> (sheet, row)."""
    out = []
    for ref in dict.fromkeys(loop.writer.log.get("flags", [])):
        m = re.match(r"^([^!]+)!([A-Z]{1,3})(\d+)$", str(ref))
        if not m:
            continue
        sheet, col, row = m.group(1), m.group(2), int(m.group(3))
        if col == _tcol(loop, sheet):
            out.append((sheet, row))
    return out


def build_queue(loop):
    """The machine's own work list — spec- and ledger-derived only.
    Red FORMULA cells are not serve material (set_input rightly refuses
    designed formulas): they go to phase0's rewrite attempt and, failing
    that, stay red for the analyst. Serve cards are hardcode inputs."""
    items = []
    for sheet, row in _red_cells(loop):
        col = _tcol(loop, sheet)
        if not col or sheet not in loop.wb.sheetnames:
            continue
        held = loop.wb[sheet][f"{col}{row}"].value
        if isinstance(held, str) and held.startswith("="):
            continue
        pv, _t = _prior_of(loop, sheet, row)
        items.append(WorkItem("SERVE", sheet, row,
                              priority=abs(pv or 0.0)))
    for g in loop._trip_groups():
        refs = [f"{s}!{c}{r}" for s, c, r, *_ in g]
        done = {v.split(":", 1)[0] for v in
                loop.writer.log.get("verdicts", [])}
        refs = [r for r in refs if r not in done]
        if refs:
            items.append(WorkItem("TRIPWIRE", refs=refs,
                                  priority=float(len(refs))))
    for sheet, row, res in loop._failing_target_checks():
        items.append(WorkItem("PLUG", sheet, row,
                              check=f"{sheet}!{row}", priority=abs(res)))
    order = {"SERVE": 0, "TRIPWIRE": 1, "PLUG": 2}
    items.sort(key=lambda w: (order[w.kind], -w.priority, w.sheet, w.row))
    return items[:MAX_CARDS]


def phase0(loop, log):
    """Everything the gates already decide, applied by code through the
    SAME guarded tools — no new authority, just no LLM round-trip."""
    n = 0
    for sheet, row, _res in loop._failing_target_checks():
        diag = loop.t_diagnose_balance({"check": f"{sheet}!{row}"})
        for m in list(re.finditer(r"GUILTY (\S+)!(\d+)", diag))[:6]:
            r = loop.t_apply_diff({"row": f"{m.group(1)}!{m.group(2)}"})
            n += str(r).startswith(("WRITTEN", "REWRITTEN"))
            log(f"[queue] phase0 apply_diff {m.group(1)}!{m.group(2)} -> "
                f"{str(r).splitlines()[0][:70]}")
        for m in list(re.finditer(
                r"STALE COMPOSITE (\S+)![A-Z]{1,3}(\d+)", diag))[:6]:
            r = loop.t_rewrite_constants(
                {"cell": f"{m.group(1)}!{m.group(2)}"})
            n += str(r).startswith("REWRITTEN")
            log(f"[queue] phase0 rewrite {m.group(1)}!{m.group(2)} -> "
                f"{str(r).splitlines()[0][:70]}")
    # red FORMULA cells: one proof-gated rewrite attempt each (the
    # constants law is deterministic — REWRITTEN when every literal
    # proves, untouched-red otherwise). Bounded.
    tried = 0
    for sheet, row in _red_cells(loop):
        if tried >= 20:
            break
        col = _tcol(loop, sheet)
        if not col or sheet not in loop.wb.sheetnames:
            continue
        held = loop.wb[sheet][f"{col}{row}"].value
        if not (isinstance(held, str) and held.startswith("=")):
            continue
        tried += 1
        r = loop.t_rewrite_constants({"cell": f"{sheet}!{row}"})
        if str(r).startswith("REWRITTEN"):
            n += 1
            log(f"[queue] phase0 rewrite(red) {sheet}!{row} -> "
                f"{str(r).splitlines()[0][:70]}")
    return n


def render_card(loop, item):
    """The card, from LIVE state. -> (text, options) where options maps
    answer-id -> (tool_name, args). None = item is moot."""
    if item.kind == "SERVE":
        sheet, row = item.sheet, item.row
        col = _tcol(loop, sheet)
        if not col or sheet not in loop.wb.sheetnames:
            return None
        if f"{sheet}!{col}{row}" not in loop.writer.log.get("flags", []):
            return None                     # cleared since queueing: moot
        cands = candidates_for(loop, sheet, row)
        if not cands:
            return None                     # nothing to adjudicate
        pv, t = _prior_of(loop, sheet, row)
        held = loop.wb[sheet][f"{col}{row}"].value
        lab = str(t.label)[:40] if t is not None else "?"
        lines = [f"CARD SERVE {sheet}!{col}{row} '{lab}'",
                 f"  holds: {held!r} (RED: stale/unproven)",
                 f"  prior year: {pv:,.2f}" if pv is not None else "",
                 "  candidates (machine-extracted; warnings are the "
                 "machine's own doubts):"]
        options = {}
        for j, c in enumerate(cands):
            cid = chr(ord("A") + j)
            w = ("  ⚠ " + "; ⚠ ".join(c["warnings"])) if c["warnings"] else ""
            b = f"  [{c['basis']}]" if c.get("basis") else ""
            lines.append(f"    {cid}: {c['value']:,.2f} — {c['doc'][:24]} "
                         f"p{c['page']} [{c['face']}] '{c['line'][:44]}'{b}{w}")
            options[f"serve:{cid}"] = ("set_input", {
                "cell": f"{sheet}!{col}{row}", "value": c["value"],
                "why": f"p{c['page']}: '{c['line'][:40]}' ({c['doc'][:28]}) "
                       f"— card-adjudicated"})
        options["not_disclosed"] = (None, None)
        lines.append("  answers: " + ", ".join(options)
                     + "  (not_disclosed = leave red for the analyst)")
        return "\n".join(x for x in lines if x), options, "not_disclosed"
    if item.kind == "TRIPWIRE":
        done = {v.split(":", 1)[0] for v in
                loop.writer.log.get("verdicts", [])}
        refs = [r for r in item.refs if r not in done]
        if not refs:
            return None
        ev = Evaluator(loop.wb)
        sample = []
        for ref in refs[:3]:
            try:
                sh, coord = ref.split("!")
                sample.append(f"{ref} computes {ev.cell(sh, coord):,.1f}")
            except Exception:
                sample.append(ref)
        lines = [f"CARD TRIPWIRE chain of {len(refs)} sign-flipped "
                 "forecast rows sharing upstream inputs:",
                 "  " + "; ".join(sample),
                 "  The actual-year causes feeding them have just been "
                 "repaired where evidence allowed. Judge the chain:",
                 "  answers: error_fixed (causes repaired, values now "
                 "sane), justified (disclosure supports the sign), "
                 "suspicious (unresolved — analyst must look)"]
        options = {
            "error_fixed": ("verdict", {"items": refs,
                                        "verdict": "ERROR_FIXED",
                                        "why": "card: causes repaired"}),
            "justified": ("verdict", {"items": refs, "verdict": "JUSTIFIED",
                                      "why": "card: supported"}),
            "suspicious": ("verdict", {"items": refs,
                                       "verdict": "SUSPICIOUS",
                                       "why": "card: unresolved"})}
        return "\n".join(lines), options, "suspicious"
    if item.kind == "PLUG":
        sheet, row = item.sheet, item.row
        still = [(s, r) for s, r, _ in loop._failing_target_checks()
                 if (s, r) == (sheet, row)]
        if not still:
            return None
        diag = loop.t_diagnose_balance({"check": f"{sheet}!{row}"})
        if "GUILTY" in diag:
            return None       # evidence remains: not this card's turn yet
        res = re.search(r"residual = ([-\d,\.]+)", diag)
        hyp = _residual_hypotheses(
            loop, float(res.group(1).replace(",", "")) if res else 0.0)
        sites = re.findall(r"^\s+(\S+)![A-Z]{1,3}(\d+) '([^']*)' = ([-\d,\.]+)",
                           diag, re.M)[:3]
        lines = ["CARD PLUG " + diag.splitlines()[0],
                 "  no component has unclaimed evidence. " + hyp,
                 "  A plug trades truth for balance and is orange-flagged "
                 "for the analyst. The refusing answer leaves the check "
                 "failing, loudly, for the terminal ladder and report."]
        options = {}
        for j, (sh, r, lab, _cur) in enumerate(sites):
            options[f"plug:{j}"] = ("plug_residual", {
                "check": f"{sheet}!{row}", "into": f"{sh}!{_tcol(loop, sh)}{r}",
                "why": f"card-adjudicated last resort into '{lab[:30]}'"})
            lines.append(f"    plug:{j} -> {sh}!{r} '{lab[:30]}'")
        options["refuse_flag"] = (None, None)
        lines.append("  answers: " + ", ".join(options))
        return "\n".join(lines), options, "refuse_flag"
    return None


def _residual_hypotheses(loop, residual):
    """Red-team Case A/D generator: printed lines whose value ≈ the
    residual are named ON the plug card — the analyst's first question."""
    if not residual:
        return ""
    prior_docs = loop.ledger.prior_period_docs()
    hits = []
    for it in loop.ledger.items:
        if it.doc in prior_docs:
            continue
        if any(abs(abs(n) - abs(residual)) <= max(1.0, abs(residual) * 5e-3)
               for n in (it.nums or [])):
            hits.append(f"'{str(it.label)[:36]}' ({it.doc[:20]} p{it.page})")
        if len(hits) >= 3:
            break
    return ("Residual matches printed line(s): " + "; ".join(hits) + "."
            if hits else "Residual matches no printed line.")


def _llm_answer(loop, client, text, options, log):
    def _val(o):
        if not isinstance(o, dict) or o.get("answer") not in options:
            return [f"answer must be one of {sorted(options)}"]
        return []
    obj = client.json(_SYSTEM, text, _val, repair_retries=1)
    return obj.get("answer"), str(obj.get("why", ""))[:120]


def run_queue(loop, client, log, answerer=None, deadline_s=DEADLINE_S,
              call_cap=CALL_CAP):
    """The inverted stage 4. `answerer(text, options, default) -> answer
    id` overrides the LLM (offline drivers, tests)."""
    t0 = time.monotonic()
    n_auto = phase0(loop, log)
    queue = build_queue(loop)
    calls = dead = done = defaulted = moot = 0
    breaker = 0
    for item in queue:
        rendered = render_card(loop, item)
        if rendered is None:
            item.state = "MOOT"
            moot += 1
            continue
        text, options, default = rendered
        ans, why = default, "default"
        drain = (breaker >= 3 or calls >= call_cap
                 or time.monotonic() - t0 > deadline_s)
        if not drain:
            try:
                if answerer is not None:
                    ans = answerer(text, options, default)
                    why = "scripted"
                elif client is not None:
                    calls += 1
                    ans, why = _llm_answer(loop, client, text, options, log)
                    breaker = 0
                if ans not in options:
                    ans, why = default, "invalid->default"
            except Exception as e:
                breaker += 1
                ans, why = default, f"client error -> default ({e})"
        else:
            dead += 1
        tool, args = options[ans]
        if tool is None:
            item.state = "DEFAULTED" if ans == default else "DONE"
            defaulted += ans == default
            if item.kind == "SERVE":
                # a not_disclosed adjudication IS an examination (the
                # move-on law): document the look on the cell so the
                # gate counts a finding, not neglect
                ncand = text.count("\n    ")
                loop.TOOLS["flag_cell"](loop, {
                    "cell": f"{item.sheet}!{item.row}",
                    "why": (f"card-adjudicated NOT PROVEN: {ncand} "
                            f"candidate(s) reviewed and rejected "
                            f"({why[:50]}) — value left at prior for "
                            "the analyst")})
            log(f"[queue] {item.kind} {item.sheet}!{item.row or ''} "
                f"-> {ans} ({why[:60]})")
            continue
        try:
            res = str(loop.TOOLS[tool](loop, args))
        except Exception as e:
            res = f"TOOL ERROR: {e}"
        item.state = "DONE"
        done += 1
        log(f"[queue] {item.kind} -> {ans}: {res.splitlines()[0][:90]}")
    summary = (f"queue: {len(queue)} items — {n_auto} auto-resolved in "
               f"phase0, {done} adjudicated, {defaulted} defaulted, "
               f"{moot} moot, {dead} drained, {calls} LLM calls")
    log(f"[run] {summary}")
    return summary
