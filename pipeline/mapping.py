"""THE MAPPING (owner 2026-09-17: "there is no thinking in preparing the
cards"). The brain maps the disclosure into the MODEL, not a card: code
indexes (the model's input rows, what each row feeds, the printed lines
whose comparative ties the row's prior, the constants a formula still
carries), answers the tools the brain calls, verifies the evidence of every
write and measures coverage.

Code decides nothing here. It refuses a write in two cases only — over the
model's own arithmetic (a formula cell) and outside the actual column — and
everything else the brain says lands: with tying evidence it lands plain,
without it lands RED carrying the brain's own reason. What the brain refused
stays in its record, so a line it has already judged is never re-offered as
if it were new.

The unit of work is a STATEMENT FACE, not a row: the context puts a printed
face beside the model rows that belong to it, and one `sets` batch marks the
face. The loop mirrors pipeline/review.py — one reading per turn, JSON calls,
answers back next turn, the clock is the only end.
"""
import json
import re
import time

from .checks import prior_column
from .evaluator import Evaluator
from .review import (_act_col, _col_of, _fmt, _held, _hist_cols, _label, _num,
                     _parse_ref, _record_line, _record_text, _row_of, t_find,
                     t_show)

MANDATE = """You are the equity analyst marking your OWN model to this disclosure.

The model is yours; the disclosure is somebody else's document. Your job is to say, row by row,
which printed line IS this row of your model, and to write the actual column.

A NUMBER MATCH IS A LEAD, NOT A MAPPING. The leads below are printed lines whose comparative equals
what your model already holds for last year — that is all they are. Read the printed line and read
the model row, and say what the line IS before you write it. Two lines can carry the same figure;
one of them is your row.

COMPOSITION IS YOURS TO STATE. When your row is several printed lines (net finance cost = finance
cost - finance income; an opex total the face prints in four pieces), state the arithmetic over
printed figures and code re-computes it.

DEFINITIONS FOLLOW THE MODEL. What a line means here is what THIS model means by it — read the
model's own definitions in the context (its spec, its section structure, what each row feeds) and
reconcile against the company's own bridge, never against a bare label. Every model is different:
reason in this model's terms.

NEVER TYPE OVER THE MODEL'S OWN ARITHMETIC. A formula cell is the model thinking; it is refused —
if the number belongs there, its input site is named for you and you set that instead.

WORK FACE BY FACE. A printed face is shown beside the model rows that belong to it: read it once,
then answer with ONE `sets` batch marking every row of that face you can map. Looking at rows one
at a time spends the clock; the batch is measured as one change.

You answer in JSON only: {"thinking": "...", "calls": [ ... ]}. Any number of calls per turn,
executed in the order you write them; their answers come back in the next turn. The calls:
  {"tool":"anatomy","checks":["Sheet!99"],"keys":[{"name":"revenue","ref":"Sheet!7"}],
      "statements":["Sheet"],"because":"..."}   only when section 0 asks: what this model's rows ARE
  {"tool":"page","n":23}                                the page's own text
  {"tool":"find","q":"46.3"}   or  {"q":"Fuel Cost"}    printed lines carrying that number or label
  {"tool":"show","ref":"Sheet!AI16"}                    the row, its history, what uses it
  {"tool":"sets","sets":[{"ref":"Sheet!AI16","printed":74206,"page":23,
      "line":"Operating expenses (74,206) (76,061)","because":"this is my opex row"}, ...]}
  {"tool":"set","ref":"Sheet!AI20","value":432.2,"because":"p23: 396.2 + 36 — my row is the two lines together"}
  {"tool":"set","ref":"Sheet!AI22","formula":"=88018-74206-1810","because":"p23: the print no longer
      splits this line, so I back it out of the total and the two lines it does print"}
  {"tool":"skip","ref":"Sheet!AI31","because":"not disclosed at this granularity in an announcement"}
  {"tool":"restate","ref":"Sheet!AI16","printed":76061,"page":23,"line":"...","because":"the print's
      comparative is not what my model holds for last year"}
  {"tool":"done"}                          accepted when every input row is filled or skipped with a reason

YOUR HISTORY IS NEVER CHANGED BY ANYONE BUT YOU. When the printed comparative differs from what your
model holds for last year, the model keeps its history: you still map THIS year, and `restate` records
the question — row, what the print says, what the model holds, your quote — for the analyst's yes. It
writes nothing into the prior column, and neither does code.

WHEN A LINE HAS BEEN RECLASSIFIED. Same item, same figure last year: map it as usual. The name or the
figure has changed and you cannot say confidently which line it is: do not guess — BACK IT OUT of what
the print does give you, as a `formula` over printed figures (=total-a-b), so the analyst can see how
it was built. It lands orange with your note of what changed in the print.

WHEN THE COMPARATIVE NO LONGER MATCHES YOUR MODEL, TRIANGULATE THROUGH LAST YEAR'S REPORT. `find` your
model's prior figure in the prior-period document (it is indexed for you on first use), read that line
to learn what the item IS — its name, its statement, its neighbours — then `find` that item in this
year's report by name and position and read this year's figure. Identify by number and name, never by
page. A renamed neighbour is your reading, not a string match.
`printed` is the figure AS PRINTED on the page (code proves the scale from the comparative and the
model's own sign convention). `value` is in the model's units and needs arithmetic in `because`.
A set lands PLAIN when the quoted line is on that page and its comparative ties your model's prior,
or when the arithmetic re-computes; otherwise it lands RED with your reason, for the analyst. It is
never refused for want of evidence. `skip` lands red too — "not disclosed" is your judgment, recorded."""


# ── the index: what code FINDS ───────────────────────────────────────────

def _val(ev, sheet, coord):
    """THE MODEL MAY HOLD ARITHMETIC CODE CANNOT READ (CX cold run 2026-09-17:
    a SUMIFS over a date range raised out of the evaluator and the whole
    context died on turn 1). A cell the evaluator cannot work out reads as
    nothing here; the loop goes on."""
    try:
        return _num(ev.cell(sheet, coord))
    except Exception:  # noqa: BLE001
        return None


def _items(loop):
    return getattr(loop.ledger, "items", []) or []


def _quote(it):
    return " ".join(str(getattr(it, "source_line", "") or getattr(it, "label", "")).split())


def _lead_index(loop):
    """{rounded |comparative| in model units: [(item, scale, current)]} over
    every printed line that prints a pair — built ONCE. The key is the
    comparative, because that is the number the model already holds."""
    idx = loop.__dict__.get("_map_leadindex")
    if idx is not None:
        return idx
    from .writegate import _SCALES, _nums, _sourceable, comparative_index
    idx = {}
    for it in _items(loop):
        if not _sourceable(it):
            continue
        ns = [n for n in _nums(it) if isinstance(n, (int, float))]
        if len(ns) < 2:
            continue
        cols = getattr(it, "columns", None)
        for i, n in enumerate(ns):
            ci = comparative_index(ns, cols, i)
            if ci is None:
                continue
            for f in _SCALES:
                comp = abs(ns[ci]) / f
                if comp < 0.5:
                    continue
                for k in (round(comp, 1), float(round(comp))):
                    idx.setdefault(k, []).append((it, f, n / f))
    loop.__dict__["_map_leadindex"] = idx
    return idx


def _nil_index(loop):
    """{rounded |figure|: [item]} over lines printing ONE number — last year's
    figure beside a blank slot. A lead ("this period may be nil"), never a write."""
    idx = loop.__dict__.get("_map_nilindex")
    if idx is not None:
        return idx
    from .writegate import _SCALES, _nums, _sourceable
    idx = {}
    for it in _items(loop):
        if not _sourceable(it):
            continue
        ns = [n for n in _nums(it) if isinstance(n, (int, float))]
        if len(ns) != 1 or not ns[0]:
            continue
        for f in _SCALES:
            v = abs(ns[0]) / f
            for k in (round(v, 1), float(round(v))):
                idx.setdefault(k, []).append(it)
    loop.__dict__["_map_nilindex"] = idx
    return idx


def _hits_printed(loop, value, page_text=None):
    """Is this figure printed on any page on file, at any legal scale? THE PAGE
    IS THE PROOF (the same law the quoted line lives by): the extractor's lines
    first, then the pages themselves — a face the table extractor could not
    parse still prints its figures."""
    from .writegate import _SCALES, _nums, _sourceable
    v = abs(float(value))
    for it in _items(loop):
        if not _sourceable(it):
            continue
        for n in _nums(it):
            if isinstance(n, (int, float)) and n and any(
                    abs(abs(n) / f - v) <= max(0.05, v * 1e-3) for f in _SCALES):
                return True
    if page_text is None:
        return False
    digits = f"{v:,.0f}".replace(",", "")
    pat = re.compile(r"(?<!\d)" + r",?".join(digits) + r"(?![\d])")
    for _k, txt in page_text.items():
        if pat.search(str(txt)):
            return True
    return False


def leads_for(loop, prior, k=4):
    """The printed lines whose comparative ties this row's prior — information,
    not a ranking: no ticks, no shares, no 'preferred'. -> [(item, current)]"""
    from .writegate import ties_prior
    if not isinstance(prior, (int, float)) or abs(prior) < 0.5:
        return []
    idx, seen, out = _lead_index(loop), set(), []
    for key in (round(abs(prior), 1), float(round(abs(prior)))):
        for it, f, cur in idx.get(key, ()):
            sig = (id(it), round(cur, 2))
            if sig in seen:
                continue
            seen.add(sig)
            if not ties_prior(it, f, prior, cur):
                continue
            out.append((it, cur))
            if len(out) >= k:
                return out
    return out


def nil_leads(loop, prior, k=1):
    """Lines printing the prior alone — a blank beside a tying prior."""
    if not isinstance(prior, (int, float)) or abs(prior) < 0.5:
        return []
    out = []
    for key in (round(abs(prior), 1), float(round(abs(prior)))):
        for it in _nil_index(loop).get(key, ()):
            if it not in out:
                out.append(it)
            if len(out) >= k:
                return out
    return out


def detection_line(loop, sheet, coord):
    """A formula still carrying last period's literals: each constant with the
    printed figures that carry it. Detection only — code rewrites nothing."""
    from .composites import literals_of
    from .writegate import _SCALES, _nums, _sourceable
    f = loop.wb[sheet][coord].value
    if not (isinstance(f, str) and f.startswith("=")):
        return ""
    try:
        lits = [l for l in literals_of(f) if abs(float(l)) >= 0.5]
    except Exception:  # noqa: BLE001
        return ""
    if not lits:
        return ""
    parts = []
    for lit in lits[:4]:
        v, hits = abs(float(lit)), []
        for it in _items(loop):
            if len(hits) >= 2:
                break
            if not _sourceable(it):
                continue
            for n in _nums(it):
                if isinstance(n, (int, float)) and n and any(
                        abs(abs(n) / s - v) <= max(0.05, v * 1e-3) for s in _SCALES):
                    hits.append(f"p{getattr(it, 'page', '?')} '{_quote(it)[:50]}'")
                    break
        parts.append(f"{lit} → " + ("; ".join(hits) if hits else "printed nowhere on file"))
    return f"      this formula still carries last period's constants: {str(f)[:60]} | " + " | ".join(parts)


# ── what each row feeds (the model's own wiring) ─────────────────────────

def _uses_index(loop):
    """{(sheet, coord): [(sheet, coord) that reference it]} over the actual
    column — one pass of the workbook, the model's own wiring."""
    idx = loop.__dict__.get("_map_uses")
    if idx is not None:
        return idx
    from .investigate import _refs
    idx, wb = {}, loop.wb
    for sh in wb.sheetnames:
        for row in wb[sh].iter_rows():
            for c in row:
                v = c.value
                if not (isinstance(v, str) and v.startswith("=")):
                    continue
                try:
                    for (s2, c2) in _refs(v, sh, wb):
                        idx.setdefault((s2, c2), []).append((sh, c.coordinate))
                except Exception:  # noqa: BLE001
                    continue
    loop.__dict__["_map_uses"] = idx
    return idx


def _classes(loop, rows):
    """What each input row FEEDS, by the model's own formulas: a key, a balance
    check, the report's headline table, or nothing measured. Information for
    the brain — never an order of work. -> {(sheet, coord): text}"""
    cls = loop.__dict__.get("_map_classes")
    if cls is not None:
        return cls
    uses, ty = _uses_index(loop), int(loop.ty)
    seeds = {}
    for k in (loop.spec.get("key_rows") or []):
        sh = k.get("sheet")
        col = _act_col(loop, sh) if sh in loop.wb.sheetnames else None
        if col:
            seeds[(sh, f"{col}{int(k['row'])}")] = f"key '{k.get('name', '')}'"
    for c in (loop.spec.get("check_rows") or []):
        sh = c.get("sheet")
        col = _act_col(loop, sh) if sh in loop.wb.sheetnames else None
        if col:
            seeds[(sh, f"{col}{int(c['row'])}")] = "a balance check"
    try:
        from .reportpage import resolve_rows
        rr, _p = resolve_rows(loop.wb, loop.spec, ty, getattr(loop, "period", None) or "FY")
        for role, v in (rr or {}).items():
            if v and v[0] in loop.wb.sheetnames:
                col = _act_col(loop, v[0])
                if col:
                    seeds.setdefault((v[0], f"{col}{int(v[1])}"), f"the report's {role}")
    except Exception:  # noqa: BLE001
        pass
    # walk DOWN from every input row through the cells that use it, to a seed
    cls = {}
    for sheet, coord, _r in rows:
        seen, frontier, found = set(), [(sheet, coord)], None
        for _hop in range(6):
            nxt = []
            for node in frontier:
                if node in seen:
                    continue
                seen.add(node)
                if node in seeds and node != (sheet, coord):
                    found = seeds[node]
                    break
                nxt += uses.get(node, [])
            if found or not nxt:
                break
            frontier = nxt
        cls[(sheet, coord)] = found or "nothing measured"
    loop.__dict__["_map_classes"] = cls
    return cls


# ── the model's input rows ───────────────────────────────────────────────

def input_rows(loop, census):
    """[(sheet, coord, row)] — the actual column's INPUT cells: the rows that
    arrived as hardcodes, in this model's own order. A formula cell is not an
    input; the model's own arithmetic is never a mapping target."""
    out = []
    for sheet in sorted(census or {}):
        if sheet not in loop.wb.sheetnames:
            continue
        col = _act_col(loop, sheet)
        if not col:
            continue
        for r in sorted(census[sheet]):
            v = loop.wb[sheet][f"{col}{r}"].value
            if isinstance(v, str) and v.startswith("="):
                continue
            out.append((sheet, f"{col}{r}", int(r)))
    return out


def _written(loop):
    """WHAT THE MAPPING ITSELF PUT THERE (reviewer 2026-09-17: the write journal
    also carries the probes other stages make — writing a value, reading the
    consequence and putting it back — so a row could read 'filled' with nothing
    mapped). The mapping keeps its own ledger: {ref: 'filled' | 'red'}."""
    return loop.__dict__.setdefault("_map_written", {})


def status_of(loop, sheet, coord, written, skipped):
    ref = f"{sheet}!{coord}"
    if ref in skipped:
        return "skipped"
    st = written.get(ref)
    if st is None:
        return "unfilled"
    if st == "orange":
        return "backed out"
    return "red" if (st == "red" or ref in (loop.writer.log.get("flags", []) or [])) else "filled"


def coverage(loop, rows, skipped):
    """({sheet: {status: n}}, the unfilled rows) — the measure `done` is held to."""
    written, by_sheet, open_rows = _written(loop), {}, []
    for sheet, coord, _r in rows:
        st = status_of(loop, sheet, coord, written, skipped)
        by_sheet.setdefault(sheet, {}).setdefault(st, 0)
        by_sheet[sheet][st] += 1
        if st == "unfilled":
            open_rows.append((sheet, coord))
    return by_sheet, open_rows


# ── the context ──────────────────────────────────────────────────────────

def _page_text_of(page_text, n, cap=6000):
    out, room = [], cap
    if hasattr(page_text, "ensure_page"):
        page_text.ensure_page(n)
    for (doc, pg), txt in sorted((page_text or {}).items()):
        if str(pg) != str(n) or not txt:
            continue
        body = str(txt)[:room]
        room -= len(body)
        out.append(f"--- {doc} p{pg} ---\n{body}")
        if room <= 0:
            break
    return out or [f"no page {n} on file"]


def _faces(loop):
    """The pages the run judged to be statement faces: [(face, doc, page)]."""
    faces = getattr(loop.ledger, "faces", {}) or {}
    return sorted({(str(face), doc, int(pg)) for (doc, pg), face in faces.items() if face})


def cold_run():
    """COLD (owner 2026-09-17): the agent is run on other teams' models with no
    written spec and no memory. Cold is the default — the model itself is the
    spec, and nothing in the loop may depend on a spec being there."""
    import os
    return str(os.environ.get("COLD_RUN", "1")).strip().lower() not in ("0", "false", "no")


def _definitions(loop, cap=2500):
    """WHAT THIS MODEL MEANS, read off the model itself: every row's own
    history, the analyst's own estimate, the section it sits in and what it
    feeds are already beside each row below. A written spec, a `_SPEC` tab or a
    remembered alias is shown too WHEN IT EXISTS — optional, never relied on."""
    if cold_run():
        return ["  cold run: no spec is read. This model's meaning is in the model — each row's four-year "
                "history, the analyst's own estimate for this year, the section the row sits in, and what "
                "the row feeds (shown beside every row below)."]
    out, room = [], cap
    for txt in (getattr(loop, "model_spec_text", "") or "", getattr(loop, "spec_tab_text", "") or ""):
        for ln in str(txt).splitlines():
            ln = ln.strip()
            if not ln or room <= 0:
                continue
            out.append("  (optional, from the model's written spec) " + ln[:150])
            room -= len(ln)
    hints = [f"  (optional, remembered) {t.sheet}!{t.row} '{t.label[:30]}' — {t.memory_hint[:90]}"
             for t in (loop.targets or {}).values() if getattr(t, "memory_hint", "")]
    return out + hints[:20]


def _key_table(loop):
    """The model's keys against the print, every turn — the objective, measured."""
    try:
        from .keytie import key_state
        out = []
        for nm, ref, got, want, ok in key_state(loop.wb, loop.spec, int(loop.ty),
                                                getattr(loop, "key_panel_path", None),
                                                panel=getattr(loop, "key_panel", None)):
            out.append(f"  {nm:<24} {ref:<18} model {_fmt(_num(got)):>14} | print "
                       f"{_fmt(_num(want)):>14} | {'ties' if ok else 'OFF THE PRINT'}")
        return out or ["  (no key rows resolved in this model)"]
    except Exception as e:  # noqa: BLE001
        return [f"  (the keys could not be measured: {type(e).__name__}: {str(e)[:70]})"]


def _row_block(loop, pre_wb, ev0, sheet, coord, r, st, cls):
    hist = [_held(pre_wb, ev0, sheet, f"{c}{r}") for c in _hist_cols(loop, sheet)]
    pcol = prior_column(loop.spec, sheet, int(loop.ty))
    prior = _held(pre_wb, ev0, sheet, f"{pcol}{r}") if pcol else None
    est = _val(ev0, sheet, coord)
    blk = [f"  {sheet}!{coord:<6} {_label(loop.wb[sheet], r):38} history "
           f"{', '.join(_fmt(h) for h in hist) or 'none in this model':30} | est {_fmt(est):>12} | "
           f"{st} | feeds {cls}"]
    if st != "unfilled":
        return blk
    # the row's own neighbourhood: the model's arithmetic is its definition
    for (s2, c2) in (_uses_index(loop).get((sheet, coord)) or ())[:2]:
        try:
            blk.append(f"      this row goes into {s2}!{c2} '{_label(loop.wb[s2], _row_of(c2))}' "
                       f"({str(loop.wb[s2][c2].value)[:60]})")
        except Exception:  # noqa: BLE001
            continue
    for it, cur in leads_for(loop, prior):
        blk.append(f"      lead: p{getattr(it, 'page', '?')} '{_quote(it)[:78]}' → this year {_fmt(cur)}")
    for it in nil_leads(loop, prior):
        blk.append(f"      lead: p{getattr(it, 'page', '?')} '{_quote(it)[:60]}' prints your prior alone — "
                   "a blank beside it; this period may be nil")
    if len(blk) == 1 and prior is not None:
        blk.append("      lead: no printed line on file carries a comparative equal to this row's prior")
    for extra in (getattr(loop, "leads", None) or {}).get((sheet, r), ())[:3]:
        blk.append(f"      lead: {str(extra)[:150]}")
    d = detection_line(loop, sheet, coord)
    if d:
        blk.append(d)
    return blk


def anatomy_wanted(loop):
    """Is this model's anatomy still unknown? A cold model from another team
    has no spec: code finds the year axes, but which rows are the checks and
    which are the keys is a reading of the model — the brain's first turn."""
    return not (loop.spec.get("check_rows") or []) or not (loop.spec.get("key_rows") or [])


def _anatomy_section(loop, cap=6000):
    """What code could work out about this model, and what it could not."""
    L = ["## 0. THE ANATOMY OF THIS MODEL — code could not finish it; this is your first job",
         "  Code found the year axes by reading the headers. It could NOT find:"]
    if not (loop.spec.get("check_rows") or []):
        L.append("  - the model's own CHECK rows (objective 1, balance, is unmeasured until you name them)")
    if not (loop.spec.get("key_rows") or []):
        L.append("  - the model's KEY rows (objective 2, the keys against the print)")
    for note in (loop.spec.get("check_notes") or [])[:4]:
        L.append(f"  code's own note: {note[:200]}")
    L.append("  Answer with {\"tool\":\"anatomy\", \"checks\":[\"Sheet!row\", ...], "
             "\"keys\":[{\"name\":\"revenue\",\"ref\":\"Sheet!row\"}, ...], \"statements\":[\"Sheet\"], "
             "\"because\":\"...\"} — a check is a row the model works out and expects to be zero "
             "(assets less liabilities and equity, cash less the cash-flow roll); a key is the row the "
             "MODEL computes, never a copy of the printed statement.")
    L.append("  The sheets, their year columns, and their labels:")
    room = cap
    for sh, ax in (loop.spec.get("year_axis") or {}).items():
        if sh not in loop.wb.sheetnames:
            continue
        cols = (ax.get("columns") or {}) if isinstance(ax, dict) else {}
        L.append(f"  --- {sh}: {len(cols)} year column(s); {loop.ty} is column {cols.get(str(loop.ty), '?')} ---")
        ws = loop.wb[sh]
        for r in range(1, min(ws.max_row, 400) + 1):
            lab = _label(ws, r)
            if lab.startswith("row "):
                continue
            f = ws[f"{cols.get(str(loop.ty), 'A')}{r}"].value
            ln = f"    {r}: {lab[:44]}" + (f"   {str(f)[:40]}" if isinstance(f, str) and f.startswith("=") else "")
            if room - len(ln) < 0:
                L.append(f"    (… more rows of {sh} — `show` any)")
                break
            room -= len(ln)
            L.append(ln)
    return L


def build_context(loop, pre_wb, rows, page_text, skipped, answers=(), history=(),
                  size_cap=26000, faces_cap=10000):
    """One reading of the MODEL and the print: the keys against the print, the
    coverage, the printed faces each beside the model rows that belong to it,
    the model's own definitions, and the brain's own turns."""
    ty = int(loop.ty)
    ev0 = Evaluator(pre_wb)
    written = _written(loop)
    by_sheet, open_rows = coverage(loop, rows, skipped)
    cls = _classes(loop, rows)
    L = []
    if anatomy_wanted(loop):
        L += _anatomy_section(loop)
        L.append("")
    L.append(f"## 1. THE KEYS against the print ({ty})")
    L += _key_table(loop)
    L.append("")
    L.append(f"## 2. COVERAGE of the actual column ({ty})")
    for sheet in sorted(by_sheet):
        c = by_sheet[sheet]
        L.append(f"  {sheet:<22} unfilled {c.get('unfilled', 0):>4} | filled {c.get('filled', 0):>4} | "
                 f"backed out {c.get('backed out', 0):>4} | red {c.get('red', 0):>4} | "
                 f"skipped {c.get('skipped', 0):>4}")
    open_cls = {}
    for sheet, coord in open_rows:
        k = cls.get((sheet, coord), "nothing measured")
        open_cls[k] = open_cls.get(k, 0) + 1
    L.append("  still unfilled, by what the row feeds: "
             + ("; ".join(f"{k}: {n}" for k, n in sorted(open_cls.items(), key=lambda kv: -kv[1])) or "none"))
    L.append("")
    L.append("## 3. THE MODEL'S OWN DEFINITIONS (its spec, its memory)")
    L += _definitions(loop) or ["  (this model carries no written spec)"]
    L.append("")
    L.append("## 4. THE PRINTED FACES, each with the model rows still to map "
             "(history | the analyst's estimate | status | what the row feeds, then its LEADS — "
             "printed lines whose comparative equals the row's prior: information, not a pick)")
    room_f = faces_cap
    for face, doc, pg in _faces(loop):
        txt = (page_text or {}).get((doc, pg))
        head = f"  ===== {face.upper()} — {doc} p{pg} ====="
        if not txt:
            L.append(head + " (no text on file — `find` reads its extracted lines)")
            continue
        body = "\n".join("   " + ln for ln in str(txt).splitlines()[:70])
        if room_f - len(body) < 0:
            L.append(head + f" (not shown here — `page {pg}`)")
            continue
        room_f -= len(body)
        L.append(head)
        L.append(body)
    L.append("")
    L.append("  ----- the model rows (unfilled first) -----")
    room, shown, unshown = size_cap, 0, 0
    order = sorted(rows, key=lambda t: (status_of(loop, t[0], t[1], written, skipped) != "unfilled", t[0], t[2]))
    for sheet, coord, r in order:
        st = status_of(loop, sheet, coord, written, skipped)
        text = "\n".join(_row_block(loop, pre_wb, ev0, sheet, coord, r, st, cls.get((sheet, coord), "")))
        if room - len(text) < 0:
            unshown += 1
            continue
        room -= len(text)
        shown += 1
        L.append(text)
    L.append(f"  ({len(rows)} input rows in total"
             + (f"; {unshown} more not shown here — `show` any of them, and they come back "
                "as the ones above are filled" if unshown else "") + ")")
    if answers:
        L.append("")
        L.append("## 5. YOUR LAST TURN")
        L += list(answers)
    if history:
        L.append("")
        L.append("## 6. EVERY TURN BEFORE THAT — including every line you refused, and why")
        L += _record_text(history)
    return "\n".join(L)


# ── the write gate ───────────────────────────────────────────────────────

_ARITH = re.compile(r"[-+]?\d[\d,]*\.?\d*(?:\s*[-+*/]\s*[-+]?\d[\d,]*\.?\d*)+")


def _arith_ties(m, v):
    try:
        got = float(eval(m.group(0).replace(",", ""), {"__builtins__": {}}, {}))  # noqa: S307
    except Exception:  # noqa: BLE001
        return False
    return abs(got - v) <= max(0.05, abs(v) * 1e-4)


def _page_scales(loop):
    sc = loop.__dict__.get("_map_scales")
    if sc is not None:
        return sc
    try:
        from .stage2_join import ratify_page_scales
        priors = [t.prior_value for t in (loop.targets or {}).values()
                  if isinstance(getattr(t, "prior_value", None), (int, float))]
        sc = ratify_page_scales([it for it in _items(loop) if it.joinable()], priors, [])
    except Exception:  # noqa: BLE001
        sc = {}
    loop.__dict__["_map_scales"] = sc
    return sc


def _dominant(scales):
    dom = {}
    for (doc, _pg), f in (scales or {}).items():
        dom.setdefault(doc, {}).setdefault(f, 0)
        dom[doc][f] += 1
    return {d: max(c, key=c.get) for d, c in dom.items()}


def verdict(loop, entry, page_text, sources, log):
    """What lands, and how. -> (value, plain, why, evidence) or
    (None, False, refusal, {}). The two refusals are the model's own
    arithmetic and a cell outside the actual column; nothing else refuses.
    Weak evidence lands RED with the brain's reason."""
    sheet, coord = entry["sheet"], entry["coord"]
    held = loop.wb[sheet][coord].value
    if isinstance(held, str) and held.startswith("="):
        site = ""
        try:
            from .writer import resolve_input_site
            pcol = prior_column(loop.spec, sheet, int(loop.ty))
            s = resolve_input_site(loop.wb, sheet, _row_of(coord), pcol) if pcol else None
            if s and s != (None, None):
                col = _act_col(loop, s[0])
                site = f" — its input site is {s[0]}!{col}{s[1]}; set that instead"
            else:
                site = " — this row is computed by the model; its inputs are elsewhere"
        except Exception:  # noqa: BLE001
            pass
        return None, False, (f"{sheet}!{coord} holds the model's own arithmetic ({str(held)[:40]})"
                             f"{site}"), {}
    ty = int(loop.ty)
    pcol = prior_column(loop.spec, sheet, ty)
    prior = _held(loop.wb, Evaluator(loop.wb), sheet, f"{pcol}{_row_of(coord)}") if pcol else None
    because = str(entry.get("because") or "")
    printed, page, line = entry.get("printed"), entry.get("page"), entry.get("line")
    if isinstance(printed, (int, float)) and page is not None:
        from .reader import _page_line, _quoted_verdict
        scales = _page_scales(loop)
        try:
            pg = int(page)
        except (TypeError, ValueError):
            return float(printed), False, f"'{page}' is not a page number — the figure lands red", {}
        hit = _page_line(page_text, pg, float(printed), line or "", sources)
        if hit is None:
            # THE EXTRACTED LINE IS ALSO THE PRINT (a scanned page has no text to
            # quote from, and the table extractor is what read it): the same law
            # applied to the ledger's own line — the figure is on that page and
            # its comparative ties the model's prior.
            from .writegate import _SCALES, _nums, ties_prior
            for it in _items(loop):
                if str(getattr(it, "page", "")) != str(pg):
                    continue
                ns = [n for n in _nums(it) if isinstance(n, (int, float))]
                for f in _SCALES:
                    if not any(abs(abs(n) - abs(float(printed))) <= max(0.05, abs(float(printed)) * 1e-3)
                               for n in ns):
                        continue
                    v_m = float(printed) / f
                    if not ties_prior(it, f, prior, v_m):
                        continue
                    if isinstance(prior, (int, float)) and prior < 0 < v_m:
                        v_m = -v_m                 # the model owns the sign convention
                    return v_m, True, (f"p{pg} '{_quote(it)[:60]}' (the extracted line) — the comparative "
                                       "ties your prior"), {"doc": getattr(it, "doc", None), "page": pg,
                                                            "line": _quote(it)[:60]}
            return (float(printed), False,
                    f"no line of p{pg} on file prints {printed:,} as you quoted it — it lands red with your reason",
                    {"page": pg, "line": str(line or "")[:60]})
        v = _quoted_verdict(hit, float(printed), prior, pg, scales, _dominant(scales), log, f"{sheet}!{coord}")
        ev = {"doc": hit.get("doc"), "page": pg, "line": hit["text"][:60]}
        if v is None:
            return float(printed), False, f"p{pg} carries no proven scale — the printed figure lands red", ev
        return float(v["value"]), bool(v.get("flag") is None), (
            f"p{pg} '{hit['text'][:60]}'" + (" — the comparative ties your prior" if v.get("flag") is None
                                             else f" — {str(v.get('note') or 'no prior tie')[:70]}")), ev
    f_ = entry.get("formula")
    if isinstance(f_, str) and f_.strip().startswith("="):
        # A BACK-OUT IS A FORMULA, NOT A HARDCODE (house law): the analyst must
        # see how the number was built. Code checks that every term of it is a
        # figure the print carries; the arithmetic is the model's own from then on.
        terms = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.?\d*", f_)]
        missing = [t for t in terms if abs(t) >= 0.5 and not _hits_printed(loop, t, page_text)]
        if missing:
            return f_, False, (f"the back-out lands red: {', '.join(f'{m:,.2f}' for m in missing[:3])} "
                               "is not a figure printed on any page on file"), {"line": f_[:60]}
        return f_, "orange", f"backed out of printed figures: {f_[:60]}", {"line": f_[:60]}
    v = _num(entry.get("value"))
    if v is None:
        return None, False, f"{sheet}!{coord}: no `value`, `printed` figure or `formula` — a model cell takes a figure", {}
    if any(_arith_ties(m, v) for m in _ARITH.finditer(because)):
        return v, True, f"your stated arithmetic re-computes: {because[:80]}", {"line": because[:60]}
    return v, False, "no quoted printed line and no arithmetic code can re-compute — it lands red with your reason", {}


def _apply(loop, entries, page_text, sources, log):
    """Apply one change (a `sets` batch is ONE change). -> lines"""
    out, ty = [], int(loop.ty)
    for e in entries:
        sheet, coord = e["sheet"], e["coord"]
        v, plain, why, ev = verdict(loop, e, page_text, sources, log)
        if v is None:
            out.append(f"  {sheet}!{coord} REFUSED: {why}")
            loop.__dict__.setdefault("_map_refused", []).append(f"{sheet}!{coord}: {why[:120]}")
            continue
        colour = None if plain is True else ("orange" if plain == "orange" else "red")
        pcol = prior_column(loop.spec, sheet, ty)
        because = str(e.get("because") or "no reason given")[:200]
        note = (f"Mapped by the brain because: {because} [{why[:90]}]" if colour is None else
                (f"Backed out by the brain: {because} [{why[:90]}]" if colour == "orange" else
                 f"Mapped by the brain WITHOUT tying evidence — please check. Because: {because} [{why[:90]}]"))
        val = v if isinstance(v, str) else float(v)
        ok = loop.writer.write(sheet, coord, val,
                               prior_coord=f"{pcol}{_row_of(coord)}" if pcol else None,
                               trusted=(plain is True or plain == "orange"), force_lock=True,
                               allow_empty=True, author_brain=True, flag=colour, note=note)
        if not ok:
            # A CELL THAT CANNOT TAKE THE FIGURE IS SAID ONCE, NOT ASKED AGAIN
            # (pace test 2026-09-17: a merged cell refused the write, the row
            # stayed 'unfilled', and the loop offered it back turn after turn —
            # 1,670 turns). The row is red with what happened and is not
            # re-offered as if nothing had been tried.
            why_r = "; ".join(x for x in (loop.writer.log.get("skipped_merged") or [])[-1:]) or "a writer's law"
            loop.writer.flag_ref(f"{sheet}!{coord}", "red",
                                 f"COULD NOT BE WRITTEN: you mapped {str(val)[:20]} here and the cell would not "
                                 f"take it ({why_r}). Please place it. Because: {because[:120]}")
            _written(loop)[f"{sheet}!{coord}"] = "red"
            out.append(f"  {sheet}!{coord}: the cell would not take it ({why_r}) — red, and not offered again")
            loop.__dict__.setdefault("_map_refused", []).append(f"{sheet}!{coord}: the cell would not take the figure")
            continue
        back = Evaluator(loop.wb).cell(sheet, coord)
        shown = back if isinstance(back, (int, float)) else val
        if isinstance(back, (int, float)) and not isinstance(val, str) \
                and abs(back - float(val)) > max(0.05, abs(float(val)) * 1e-6):
            log(f"[map] read-back {sheet}!{coord} shows {back} after writing {val}")
        loop.served[(sheet, _row_of(coord))] = {
            "value": float(shown) if isinstance(shown, (int, float)) else None,
            "status": "OK", "doc": ev.get("doc"), "page": ev.get("page"),
            "line": ev.get("line") or str(e.get("line") or "")[:60],
            "conf": 4 if colour is None else 3, "homed": True, "home": (sheet, coord),
            "flag": colour,
            "note": f"mapping: {because[:90]} — {why[:100]}"}
        _written(loop)[f"{sheet}!{coord}"] = "filled" if colour is None else "red"
        out.append(f"  {sheet}!{coord} = {_fmt(shown) if isinstance(shown, (int, float)) else str(val)[:40]} → "
                   + ("plain, " if colour is None else ("ORANGE (backed out): " if colour == "orange" else "RED: "))
                   + why)
    return out


# ── the tools ────────────────────────────────────────────────────────────

def _entries(loop, call):
    """The cells this call names. -> (entries, complaints)"""
    raw = call.get("sets") or [call]
    entries, bad = [], []
    for s_ in raw:
        if not isinstance(s_, dict):
            bad.append(f"'{str(s_)[:50]}' is not a cell object")
            continue
        sheet, coord, err = _parse_ref(loop, s_.get("ref", ""))
        if err:
            bad.append(err)
            continue
        if _col_of(coord) != _act_col(loop, sheet):
            bad.append(f"{sheet}!{coord} is not in the actual column — the mapping writes the actual period only")
            continue
        e = dict(s_)
        e["sheet"], e["coord"] = sheet, coord
        if e.get("because") is None:
            e["because"] = call.get("because")
        entries.append(e)
    return entries, bad


def _t_restate(loop, call, page_text, sources, log):
    """THE AGENT NEVER CHANGES THE ANALYST'S HISTORY (owner, BOSS_MINDMAP
    standing law, restated 2026-09-17). A comparative that disagrees with the
    model's prior is a QUESTION, not a correction: the row is recorded — what
    the print says, what the model holds, the quoted line — for the report and
    for the analyst's yes, and the cell is marked red so it cannot be missed.
    Nothing here writes a prior-year cell, and neither does code."""
    sheet, coord, err = _parse_ref(loop, call.get("ref", ""))
    if err:
        return [f"restate: {err}"]
    ty = int(loop.ty)
    pcol = prior_column(loop.spec, sheet, ty)
    r = _row_of(coord)
    held = _num(loop.wb[sheet][f"{pcol}{r}"].value) if pcol else None
    printed = call.get("printed")
    if printed is None:
        printed = call.get("value")
    if not isinstance(printed, (int, float)):
        return [f"restate {sheet}!{coord}: say what the print's comparative is (`printed`)"]
    quote, why = str(call.get("line") or "")[:80], str(call.get("because") or "")[:150]
    pg = call.get("page")
    # the question is recorded against the ACTUAL column's cell, where the
    # analyst is reading this year — the prior column is left exactly as it is
    act = _act_col(loop, sheet)
    ref = f"{sheet}!{act}{r}" if act else f"{sheet}!{coord}"
    loop.writer.flag_ref(ref, "red",
                         f"COMPARATIVE RESTATED: this year's report prints last year as {printed:,.2f}; "
                         f"your model holds {_fmt(held)}. Restate? Your history has not been changed. "
                         f"p{pg} '{quote}' {why}")
    loop.writer.log.setdefault("restatements", []).append(
        f"QUESTION {sheet}!{pcol}{r}: the print says {printed:,.2f}, the model holds {_fmt(held)} "
        f"— p{pg} '{quote}' {why}")
    loop.__dict__.setdefault("_map_refused", []).append(
        f"{sheet}!{pcol}{r}: restatement recorded as a question, not written")
    return [f"restate {sheet}!{pcol}{r}: recorded as a QUESTION for the analyst — the print says "
            f"{printed:,.2f}, your model holds {_fmt(held)}; the model's history is unchanged and "
            f"{ref} is marked red. Map THIS year as usual."]


def _find(loop, page_text, q):
    """`find` reads the extracted lines AND the pages themselves — the same
    evidence the write gate checks a quote against. When this period's pages
    carry nothing, the earlier documents are indexed and searched too: that is
    how a row whose comparative no longer matches is triangulated through last
    year's report."""
    out = list(t_find(loop, q))
    q = str(q).strip()
    try:
        num = float(q.replace(",", ""))
    except ValueError:
        num = None
    if num is not None:
        digits = f"{abs(num):,.0f}".replace(",", "")
        pat = re.compile(r"(?<!\d)" + r",?".join(digits) + r"(?![\d])")
    else:
        pat = re.compile(re.escape(q), re.I)

    def _scan():
        hits = []
        for (doc, pg), txt in sorted(page_text.items()):
            for raw in str(txt).splitlines():
                if pat.search(raw):
                    hits.append(f"    {doc} p{pg}: " + " ".join(raw.split())[:110])
                    if len(hits) >= 12:
                        return hits
        return hits
    found = _scan()
    if not found and hasattr(page_text, "_ensure"):
        page_text._ensure()          # the earlier documents, read now that they are wanted
        found = _scan()
    if found:
        out.append("  on the pages themselves:")
        out += found
    return out


def _t_anatomy(loop, call, log):
    """THE BRAIN READS THE MODEL'S ANATOMY (owner 2026-09-17, the CX cold model:
    no spec, no labelled check, so objective 1 could not be measured at all).
    The brain names the check rows, the key rows and the statement sheets; code
    VERIFIES each row computes a number in the model and then measures the
    objectives on them from this turn on. Code records the reading (the _SPEC
    draft) and names anything it had to drop."""
    out, took, dropped = [], 0, []
    ev = Evaluator(loop.wb)
    for ref in (call.get("checks") or []):
        sh, co, err = _parse_ref(loop, ref)
        if err:
            dropped.append(f"{ref}: {err}")
            continue
        try:
            v = ev.cell(sh, co)
        except Exception as e:  # noqa: BLE001
            dropped.append(f"{ref}: the model cannot work this row out ({type(e).__name__})")
            continue
        if not isinstance(v, (int, float)):
            dropped.append(f"{ref}: reads {str(v)[:20]!r}, not a number — a check computes a figure")
            continue
        r = _row_of(co)
        if any(c.get("sheet") == sh and int(c.get("row")) == r for c in (loop.spec.get("check_rows") or [])):
            continue
        loop.spec.setdefault("check_rows", []).append({"sheet": sh, "row": r, "expect": 0})
        took += 1
        out.append(f"  check {sh}!{r} '{_label(loop.wb[sh], r)}' reads {_fmt(_num(v))} — measured from now on")
    for k in (call.get("keys") or []):
        if not isinstance(k, dict):
            continue
        sh, co, err = _parse_ref(loop, k.get("ref", ""))
        if err:
            dropped.append(f"{k.get('ref')}: {err}")
            continue
        try:
            v = ev.cell(sh, co)
        except Exception:  # noqa: BLE001
            v = None
        if not isinstance(v, (int, float)):
            dropped.append(f"{k.get('ref')}: reads nothing the model computes — a key is a computed row")
            continue
        r = _row_of(co)
        loop.spec.setdefault("key_rows", []).append({"name": str(k.get("name") or "key")[:40],
                                                     "sheet": sh, "row": r, "source": "the brain's anatomy"})
        took += 1
        out.append(f"  key '{k.get('name')}' at {sh}!{r} '{_label(loop.wb[sh], r)}' reads {_fmt(_num(v))}")
    loop.writer.log.setdefault("anatomy", []).append(
        f"the brain's reading of this model: {len(call.get('checks') or [])} check row(s), "
        f"{len(call.get('keys') or [])} key row(s), statements on "
        f"{', '.join(str(x) for x in (call.get('statements') or []))[:80]} — "
        f"{str(call.get('because') or '')[:150]}")
    for d in dropped:
        out.append(f"  dropped {d}")
    log(f"[map] anatomy: {took} row(s) taken, {len(dropped)} dropped — "
        f"{len(loop.spec.get('check_rows') or [])} check row(s), {len(loop.spec.get('key_rows') or [])} key row(s) now measured")
    return [f"anatomy: {took} row(s) taken, {len(dropped)} dropped"] + out


def _one_call(loop, pre_wb, call, page_text, sources, skipped, log):
    tool = str(call.get("tool") or "").strip().lower()
    if tool == "page":
        return _page_text_of(page_text, call.get("n") or call.get("page") or 0)
    if tool == "find":
        return _find(loop, page_text, call.get("q", ""))
    if tool == "show":
        return t_show(loop, pre_wb, call.get("ref", ""))
    if tool in ("set", "sets"):
        entries, bad = _entries(loop, call)
        out = ["set " + ", ".join(f"{e['sheet']}!{e['coord']}" for e in entries) + ":"] if entries else []
        if bad:
            out.append("  " + "; ".join(bad))
        if entries:
            out += _apply(loop, entries, page_text, sources, log)
        elif not bad:
            out = ["set: no cell named"]
        return out
    if tool == "skip":
        entries, bad = _entries(loop, call)
        if bad and not entries:
            return ["skip: " + "; ".join(bad)]
        out = []
        for e in entries:
            why = str(e.get("because") or "").strip()
            ref = f"{e['sheet']}!{e['coord']}"
            if not why:
                out.append(f"skip {ref}: a skip carries your reason — say why")
                continue
            loop.writer.flag_ref(ref, "red", f"NOT MAPPED — the analyst's own judgment: {why[:200]}")
            skipped[ref] = why
            loop.__dict__.setdefault("_map_refused", []).append(f"{ref}: skipped — {why[:110]}")
            out.append(f"skip {ref}: recorded red — {why[:100]}")
        return out
    if tool == "anatomy":
        return _t_anatomy(loop, call, log)
    if tool == "restate":
        return _t_restate(loop, call, page_text, sources, log)
    return [f"'{tool}' is not one of the tools: page, find, show, set, sets, skip, restate, done"]


# ── the loop ─────────────────────────────────────────────────────────────

def run_mapping(loop, pre_wb, census, page_text, log, ask_json, deadline_s=900.0, brain=True):
    """THE MAPPING LOOP. Every turn: code lays out the printed faces beside the
    model's input rows with their leads, the brain calls tools, code verifies,
    writes and logs the turn verbatim. The clock is the only end; on the clock
    every unfilled row lands red 'not reached' — never a silent estimate.
    -> a one-line summary."""
    rows = input_rows(loop, census)
    sources = {getattr(it, "doc", None) for it in _items(loop)} - {None}
    skipped, state, answers, dead, turn = {}, {"history": []}, [], 0, 0
    t0 = time.monotonic()
    log(f"[map] {len(rows)} input rows in the actual column; {deadline_s / 60:.1f} min for the mapping")
    if ask_json is None or not brain:
        log("[map] no brain in this run: nothing is mapped by hand")
    else:
        while True:
            turn += 1
            left = deadline_s - (time.monotonic() - t0)
            if left <= 0:
                log("[map] clock: the rest of the input rows are not reached")
                break
            try:
                ctx = build_context(loop, pre_wb, rows, page_text, skipped,
                                    answers=answers, history=state["history"])
            except Exception as e:  # noqa: BLE001
                log(f"[map] turn {turn}: the context could not be built ({e!r}) — the rest is not reached")
                break
            log(f"[map] turn {turn}: context {len(ctx):,} chars, {left / 60:.1f} min left")
            try:
                reply = ask_json(MANDATE, ctx)
            except Exception as e:  # noqa: BLE001
                dead += 1
                answers = [f"    your last reply could not be read ({type(e).__name__}: {str(e)[:120]}). "
                           "Answer with JSON only: {\"thinking\": \"...\", \"calls\": [ ... ]}."]
                log(f"[map] turn {turn}: the reply could not be read ({e!r}) — asked again")
                if dead >= 3:
                    log("[map] three unreadable turns running — the rest is not reached")
                    break
                continue
            dead = 0
            log("[map] turn %d reply %s" % (turn, json.dumps(reply, ensure_ascii=False)))
            calls = reply.get("calls") if isinstance(reply, dict) else None
            if not isinstance(calls, list) or not calls:
                answers = ["    your last reply carried no calls — answer with a JSON list of calls"]
                continue
            answers, finished = [], False
            for call in calls:
                if time.monotonic() - t0 > deadline_s:
                    answers.append("    the clock ended the mapping inside this turn")
                    log("[map] clock: the rest of the turn's calls were not run")
                    finished = True
                    break
                if not isinstance(call, dict):
                    answers.append(f"    '{str(call)[:60]}' is not a call object")
                    continue
                if str(call.get("tool") or "").lower() == "done":
                    _by, still = coverage(loop, rows, skipped)
                    if still:
                        answers.append(f"    not done: {len(still)} input row(s) are neither filled nor skipped "
                                       "with a reason. Map them, or `skip` each with your reason:")
                        answers += [f"      {sh}!{co}" for sh, co in still[:40]]
                        log(f"[map] done refused: {len(still)} input row(s) still open")
                        continue
                    log("[map] done: every input row is filled or skipped with a reason")
                    finished = True
                    break
                try:
                    out = _one_call(loop, pre_wb, call, page_text, sources, skipped, log)
                except Exception as e:  # noqa: BLE001
                    out = [f"    that call failed: {type(e).__name__}: {str(e)[:120]}"]
                    log(f"[map] the call {json.dumps(call, ensure_ascii=False)[:120]} failed: {e!r}")
                answers += out
                state["history"].append(_record_line(turn, call, out))
                for ln in out:
                    log(f"[map]   {ln.strip()[:300]}")
            if finished:
                break
    n_open = _close_out(loop, rows, skipped, log)
    by_sheet, _ = coverage(loop, rows, skipped)
    filled = sum(c.get("filled", 0) for c in by_sheet.values())
    red = sum(c.get("red", 0) for c in by_sheet.values())
    s = (f"mapping: {turn} turn(s), {filled} plain, {red} red, {len(skipped)} skipped with a reason, "
         f"{n_open} not reached (red) of {len(rows)} input rows")
    log("[map] " + s)
    return s


def _close_out(loop, rows, skipped, log):
    """On the clock, every input row the brain did not reach is RED and says so
    — never a silent estimate, never a code guess."""
    written, n = _written(loop), 0
    for sheet, coord, _r in rows:
        if status_of(loop, sheet, coord, written, skipped) != "unfilled":
            continue
        loop.writer.flag_ref(f"{sheet}!{coord}", "red",
                             "NOT REACHED: the mapping ran out of time before this input row was read "
                             "against the disclosure. It still holds last period's figure — please map it.")
        n += 1
    if n:
        log(f"[map] {n} input row(s) not reached — red, holding last period's figure")
    return n


class Pages:
    """THE PAGES, INDEXED WHEN THEY ARE ASKED FOR (owner 2026-09-17). This
    period's documents are read up front; LAST period's report is read only if
    the brain reaches for it — triangulating a row whose comparative no longer
    matches the model — so a cold run pays nothing for a document it never opens."""

    def __init__(self, docs, later_docs=(), log=print):
        self._d, self._later, self._log, self._loaded = {}, list(later_docs or ()), log, False
        for p in docs or ():
            self._read(p)

    def _read(self, p):
        from .stage1_read import page_texts
        name = p.name if hasattr(p, "name") else str(p)
        try:
            for pn, txt, _cls in page_texts(str(p)):
                if txt:
                    self._d[(name, pn)] = txt
        except Exception as e:  # noqa: BLE001
            self._log(f"[map] page text unavailable for {name}: {e!r} — the ledger's lines stand in")

    def _ensure(self):
        """Read the documents held back, once, the first time one is asked for."""
        if self._loaded:
            return
        self._loaded = True
        if not self._later:
            return
        self._log(f"[map] indexing {len(self._later)} earlier document(s) on demand: "
                  + ", ".join(getattr(p, "name", str(p)) for p in self._later))
        for p in self._later:
            self._read(p)

    def get(self, key, default=None):
        v = self._d.get(key)
        if v is None and not self._loaded:
            self._ensure()
            v = self._d.get(key)
        return default if v is None else v

    def items(self):
        return self._d.items()

    def docs(self):
        return {d for d, _p in self._d}

    def ensure_page(self, n):
        if not any(str(pg) == str(n) for _d, pg in self._d):
            self._ensure()

    def __bool__(self):
        return True


def page_text_of_docs(docs, later_docs=(), log=print):
    """{(doc, page): text} — this period's pages now, earlier ones on demand."""
    return Pages(docs, later_docs, log)
