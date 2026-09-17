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

# A RUN OF TURNS THAT READ NOTHING AND CHANGE NOTHING ENDS THE MAPPING (reviewer
# 2026-09-17: a brain answering `done` turned 19,434 times and ate the whole
# budget — live, every turn is a call; and a brain that answers nothing at all
# would spend the budget the same way). Reading IS work, so this only counts the
# turns that do neither; the number mirrors the review loop's own.
_EMPTY_RUN = 3

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

DEFINITIONS FOLLOW THE MODEL. What a line means here is what THIS model means by it, and the model
says so itself: each row's four-year history, the analyst's own estimate for this year, the section
it sits in and the arithmetic it feeds are printed beside it. Reconcile against the company's own
bridge, never against a bare label. Every model is different: reason in this model's terms.

NEVER TYPE OVER THE MODEL'S OWN ARITHMETIC. A formula cell is the model thinking; it is refused —
if the number belongs there, its input site is named for you and you set that instead.
For amounts embedded in an actual formula, supply `formula` with updated numeric operands while
keeping its references, operators and functions unchanged. A formula must never become a hardcode.

WORK FACE BY FACE, IN ONE BATCH. A printed face is shown beside the model rows its lines point at:
read it once, and on that first sight answer with ONE `sets` batch marking every row of that face
you can map. A turn costs about two minutes of your budget, so a face you inspect row by row is a
face you do not finish. Use `show` only when a ROW'S MEANING is unclear — never to inspect the
model's arithmetic: a key or a subtotal is computed, and the context already names the input rows
that feed it. Set those.

You answer in JSON only: {"thinking": "...", "calls": [ ... ]}. Any number of calls per turn,
executed in the order you write them; their answers come back in the next turn. The calls:
  {"tool":"anatomy","checks":["Sheet!99"],"keys":[{"name":"revenue","ref":"Sheet!7"}],
      "statements":["Sheet"],"because":"..."}   only when section 0 asks: what this model's rows ARE
  {"tool":"page","doc":"report.pdf","n":23}                                the page's own text
  {"tool":"find","q":"46.3"}   or  {"q":"Fuel Cost"}    printed lines carrying that number or label
  {"tool":"show","ref":"Sheet!AI16"}                    the row, its history, what uses it
  {"tool":"sets","sets":[{"ref":"Sheet!AI16","printed":74206,"doc":"report.pdf","page":23,
      "line":"Operating expenses (74,206) (76,061)","because":"this is my opex row"}, ...]}
  {"tool":"set","ref":"Sheet!AI20","value":432.2,"because":"p23: 396.2 + 36 — my row is the two lines together"}
  {"tool":"set","ref":"Sheet!AI22","formula":"=88018-74206-1810","because":"p23: the print no longer
      splits this line, so I back it out of the total and the two lines it does print"}
  {"tool":"skip","ref":"Sheet!AI31","because":"this page is the auditor's report, it does not carry my row"}
      a skip is about THE PAGE YOU WERE SHOWN, and is never a verdict on the row: that page is taken off
      the row and the row comes back to you against a print it has not refused. Under each row you are
      shown the pages you have already refused for it. When NO print in this disclosure carries the row,
      add  "scope":"disclosure"  — that, and only that, closes the row, red, with your reason.
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
it was built. It retains the formula and a review note; arithmetic alone does not prove operand definitions.

WHEN THE COMPARATIVE NO LONGER MATCHES YOUR MODEL, TRIANGULATE THROUGH LAST YEAR'S REPORT. `find` your
model's prior figure in the prior-period document (it is indexed for you on first use), read that line
to learn what the item IS — its name, its statement, its neighbours — then `find` that item in this
year's report by name and position and read this year's figure. Identify by number and name, never by
page. A renamed neighbour is your reading, not a string match.
`printed` is the figure AS PRINTED on the page (code proves the scale from the comparative and the
model's own sign convention). `value` is in the model's units and needs arithmetic in `because`.
A set lands PLAIN when the quoted line is on that page and its comparative ties your model's prior,
with the model definition matching; arithmetic alone is not source proof and stays RED with its formula. It is
never refused for want of evidence. A `skip` carrying scope "disclosure" lands red too — "no print here
carries it" is your judgment, recorded; a skip of the page in front of you marks nothing and settles
nothing: it takes that page off the row, and the row comes back."""


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


def leads_for(loop, prior, k=3, skip_pages=()):
    """The printed lines whose comparative ties this row's prior — information,
    not a ranking: no ticks, no shares, no 'preferred'. -> [(item, current)]

    A lead the brain has already read this row against and refused is not a lead
    for this row any more (`skip_pages`): the tie was coincidence, and the row
    goes on to the prints that do carry it."""
    from .writegate import ties_prior
    if not isinstance(prior, (int, float)) or abs(prior) < 0.5:
        return []
    skip_pages = set(skip_pages or ())
    idx, seen, out = _lead_index(loop), set(), []
    for key in (round(abs(prior), 1), float(round(abs(prior)))):
        for it, f, cur in idx.get(key, ()):
            sig = (id(it), round(cur, 2))
            if sig in seen:
                continue
            seen.add(sig)
            if not ties_prior(it, f, prior, cur):
                continue
            if _page_of(it) in skip_pages:
                continue
            out.append((it, cur))
            if len(out) >= k:
                return out
    return out


def nil_leads(loop, prior, k=1, skip_pages=()):
    """Lines printing the prior alone — a blank beside a tying prior."""
    if not isinstance(prior, (int, float)) or abs(prior) < 0.5:
        return []
    out, skip_pages = [], set(skip_pages or ())
    for key in (round(abs(prior), 1), float(round(abs(prior)))):
        for it in _nil_index(loop).get(key, ()):
            if _page_of(it) in skip_pages:
                continue
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

def is_own_arithmetic(wb, sheet, coord, act_col, prior_col):
    """The prior actual's cell type defines an input; column distance does not.

    Cross-sheet links and accounting rolls remain formulas even when their
    references lie left of the target. A typed prior actual is evidence that
    a projection in that row is meant to be marked to actual.
    """
    f = wb[sheet][coord].value
    if not (isinstance(f, str) and f.startswith("=")):
        return False
    from openpyxl.formula.tokenizer import Tokenizer
    try:
        refs = [t.value for t in Tokenizer(f).items if t.type == "OPERAND" and t.subtype == "RANGE"]
    except Exception:
        return True
    # A link to another sheet is model structure, independent of its column.
    if any("!" in ref for ref in refs):
        return True
    r = _row_of(coord)
    prior = wb[sheet][f"{prior_col}{r}"].value if prior_col else None
    if isinstance(prior, str) and prior.startswith("="):
        return True
    if not isinstance(prior, (int, float)) or isinstance(prior, bool):
        return True
    # A subtotal consuming the current period remains structural even if the
    # same row happened to be typed in the preceding period.
    for ref in refs:
        for col in re.findall(r"(?:^|:)\$?([A-Z]+)\$?\d+", ref):
            if col == act_col:
                return True
    return not refs


def literal_template(formula):
    """References, operators and functions are structure; numeric inputs are not."""
    from openpyxl.formula.tokenizer import Tokenizer
    try:
        return tuple((t.type, t.subtype, "#" if t.type == "OPERAND" and t.subtype == "NUMBER" else t.value)
                     for t in Tokenizer(formula).items if t.type != "WHITE-SPACE")
    except Exception:
        return None


def has_embedded_inputs(formula):
    from .composites import literals_of, MODELING_CONSTANTS
    return (isinstance(formula, str) and formula.startswith("=")
            and any(abs(float(n)) not in MODELING_CONSTANTS for n in literals_of(formula)))


def input_rows(loop, census):
    """[(sheet, coord, row)] — the actual column's INPUT cells: the rows that
    arrived as hardcodes, AND the rows still holding the analyst's forecast for
    the year now being reported. The model's own arithmetic — a subtotal, a
    link, a check — is never a mapping target."""
    out, extra = [], 0
    for sheet in sorted(census or {}):
        if sheet not in loop.wb.sheetnames:
            continue
        col = _act_col(loop, sheet)
        if not col:
            continue
        pcol = prior_column(loop.spec, sheet, int(loop.ty))
        rows = set(int(r) for r in census[sheet])
        ws = loop.wb[sheet]
        for r in range(1, ws.max_row + 1):
            v = ws[f"{col}{r}"].value
            if isinstance(v, str) and v.startswith("="):
                if r in rows or has_embedded_inputs(v) or not is_own_arithmetic(loop.wb, sheet, f"{col}{r}", col, pcol):
                    if _label(ws, r).startswith("row "):
                        continue         # a formula on an unlabelled row is not a line of this model
                    rows.add(r)
                    extra += 1
                continue
        for r in sorted(rows):
            v = loop.wb[sheet][f"{col}{r}"].value
            if isinstance(v, str) and v.startswith("=") \
                    and not has_embedded_inputs(v) \
                    and is_own_arithmetic(loop.wb, sheet, f"{col}{r}", col, prior_column(loop.spec, sheet, int(loop.ty))):
                continue
            out.append((sheet, f"{col}{r}", int(r)))
    return out


def _written(loop):
    """WHAT THE MAPPING ITSELF PUT THERE (reviewer 2026-09-17: the write journal
    also carries the probes other stages make — writing a value, reading the
    consequence and putting it back — so a row could read 'filled' with nothing
    mapped). The mapping keeps its own ledger: {ref: 'filled' | 'red'}."""
    return loop.__dict__.setdefault("_map_written", {})


def _page_of(it):
    """The printed page an extracted line came off: (doc, page)."""
    return (str(getattr(it, "doc", "")), int(getattr(it, "page", 0) or 0))


def _page_skips(loop):
    """{ref: {(doc, page)}} — WHERE THE BRAIN REFUSED A ROW, NOT THAT IT REFUSED
    IT (live 35200922601: a coincidental lead put D&A under a presentation page
    and bank loans under the auditor's report; the brain answered "p37 does not
    disclose Development expenditure" — a verdict on the row AGAINST THAT PAGE —
    and code read it as "this disclosure does not carry the row", retiring 69
    rows the statement faces would have answered). A refusal takes that page off
    the row EVERYWHERE — its leads and the prints it is dealt to — and the row
    stays open. Only the brain's own "scope": "disclosure" closes a row."""
    return loop.__dict__.setdefault("_map_page_skips", {})


def _refused_pages(loop, sheet, coord):
    """The prints this row has been read against and refused."""
    return _page_skips(loop).get(f"{sheet}!{coord}") or ()


_WHOLE_DISCLOSURE = ("disclosure", "document", "run", "all", "whole disclosure", "not disclosed")


def _whole_disclosure(scope):
    """The brain's own words for 'no print in this report carries the row' — the
    only thing that turns a skip into a verdict on the ROW rather than on the
    page it was shown."""
    return " ".join(str(scope or "").split()).strip().lower().strip(".\"'") in _WHOLE_DISCLOSURE


def _read_against(loop):
    """{ref: (doc, page)} — the print each row was last laid beside, so a skip is
    scoped to what the brain was actually reading when it refused."""
    return loop.__dict__.setdefault("_map_read_against", {})


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


def open_queue(loop, rows, skipped):
    """THE ROWS STILL TO MAP, as a queue — unfilled before red, each sheet in the
    model's own order. A cell that is plain, backed out or skipped with a reason
    is SETTLED and is never offered again (owner 2026-09-17: the context was
    rebuilt around the same faces every turn, re-showing rows already mapped
    while 217 of CLP's 319 input rows were never put in front of anybody)."""
    written = _written(loop)
    q = []
    for sheet, coord, r in rows:
        st = status_of(loop, sheet, coord, written, skipped)
        if st in ("filled", "backed out", "skipped"):
            continue
        q.append((0 if st == "unfilled" else 1, sheet, r, coord))
    return [(sh, co, r) for _p, sh, r, co in sorted(q)]


def spread_over_faces(rows, faces, refused=None):
    """{(doc, page): [rows]} — the rows no printed line's comparative points at,
    placed on the statement faces this run identified. A row with no lead is
    still a row of this model: it is read against a print so the brain can say
    what it is, or say why the print does not carry it. EVERY row given is
    placed (reviewer 2026-09-17: a per-face count dropped 79 of 319 rows on the
    floor while the docstring said every open row gets a face) — except on a
    print it has already refused: `refused(row)` gives the pages the brain said
    do not carry that row, and the row is dealt on to the next face it has not
    seen. A row that has refused every face is placed nowhere and comes back
    loose, carrying the pages it refused, for the brain to `find` it or close
    it."""
    out = {}
    if not rows or not faces:
        return out
    faces = list(faces)
    k = max(1, (len(rows) + len(faces) - 1) // len(faces))
    for i, t in enumerate(rows):
        seen = set(refused(t) or ()) if callable(refused) else set()
        j = min(i // k, len(faces) - 1)          # this row's own share of the run's faces
        pick = next((f for f in faces[j:] + faces[:j] if f not in seen), None)
        if pick is not None:
            out.setdefault(pick, []).append(t)
    return out


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

def _page_text_of(page_text, n, cap=6000, doc=None):
    out, room = [], cap
    if hasattr(page_text, "ensure_page"):
        page_text.ensure_page(n, doc=doc)
    for (source_doc, pg), txt in sorted((page_text or {}).items()):
        if (doc is not None and source_doc != doc) or str(pg) != str(n) or not txt:
            continue
        body = str(txt)[:room]
        room -= len(body)
        out.append(f"--- {source_doc} p{pg} ---\n{body}")
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


def _feeding_inputs(loop, sheet, coord, rows, limit=5):
    """The INPUT rows this key is computed from — the model's own formula tree,
    walked down to cells the brain can actually set (owner 2026-09-17: the keys
    read OFF THE PRINT and the brain spent eleven turns `show`ing the arithmetic
    to find out what fed them)."""
    from .investigate import _refs
    want = {(sh, co) for sh, co, _r in rows}
    seen, frontier, out = set(), [(sheet, coord)], []
    limit = float("inf") if limit is None else limit   # evidence: the whole tree, when the answer is "how many of my inputs are open"
    for _hop in range(5):
        nxt = []
        for sh, co in frontier:
            if (sh, co) in seen or len(out) >= limit:
                continue
            seen.add((sh, co))
            if (sh, co) in want and (sh, co) != (sheet, coord):
                out.append((sh, co))
                continue
            v = loop.wb[sh][co].value if sh in loop.wb.sheetnames else None
            if isinstance(v, str) and v.startswith("="):
                try:
                    nxt += _refs(v, sh, loop.wb)[:12]
                except Exception:  # noqa: BLE001
                    continue
        if len(out) >= limit or not nxt:
            break
        frontier = nxt
    return out if limit == float("inf") else out[:limit]


def keys_on_open_inputs(loop, rows, spec, target_year, skipped=None):
    """A KEY IS ONLY AS GOOD AS THE ROWS UNDERNEATH IT (owner 2026-09-17, DFE
    live: U15/U22/U28 computed from `Raw financials!U8` and its neighbours,
    which were never reached and still held last year's figure under a red flag
    — the keys themselves carried no flag at all). -> [(name, key ref, [the
    input refs under it that are unfilled, red or not reached])]."""
    from .checks import year_columns
    written, skipped = _written(loop), (skipped if skipped is not None else
                                        loop.__dict__.get("_map_skipped") or {})
    out = []
    for kk in (spec.get("key_rows") or []):
        sh = kk.get("sheet")
        if sh not in loop.wb.sheetnames:
            continue
        tc = year_columns(spec, sh).get(str(target_year))
        if not tc:
            continue
        ref = f"{tc}{int(kk.get('row'))}"
        # the WHOLE tree under the key, and a row the brain closed with a reason
        # is closed (reviewer 2026-09-17: a walk that stopped at twelve could
        # miss every open input, and a skipped row is a judgment, not a gap)
        open_ins = [f"{a}!{b}" for a, b in _feeding_inputs(loop, sh, ref, rows, limit=None)
                    if status_of(loop, a, b, written, skipped) in ("unfilled", "red")]
        if open_ins:
            out.append((str(kk.get("name") or "key"), f"{sh}!{ref}", open_ins))
    return out


def _key_table(loop, rows=(), written=None, skipped=None):
    """The model's keys against the print, every turn — the objective, measured."""
    try:
        from .keytie import key_state
        out = []
        for nm, ref, got, want, ok in key_state(loop.wb, loop.spec, int(loop.ty),
                                                getattr(loop, "key_panel_path", None),
                                                panel=getattr(loop, "key_panel", None)):
            said = ("ties" if ok else ("no printed figure on file — quote one in a `set` or in `anatomy`"
                                       if want is None else "OFF THE PRINT"))
            out.append(f"  {nm:<24} {ref:<18} model {_fmt(_num(got)):>14} | print "
                       f"{_fmt(_num(want)):>14} | {said}")
            if not ok and rows:
                sh_k, co_k = ref.split("!", 1)
                fed = _feeding_inputs(loop, sh_k, co_k, rows)
                if fed:
                    out.append("      it is computed from these INPUT rows — act on them, not on the key: "
                               + "; ".join(
                                   f"{a}!{b} '{_label(loop.wb[a], _row_of(b))[:26]}' "
                                   f"({status_of(loop, a, b, written or {}, skipped or {})})"
                                   for a, b in fed))
        return out or ["  (no key rows resolved in this model)"]
    except Exception as e:  # noqa: BLE001
        return [f"  (the keys could not be measured: {type(e).__name__}: {str(e)[:70]})"]


def _cand_line(c):
    """One candidate, whatever shape the index hands back (an item, a pair, or
    the serve dict the join speaks in). -> (item or None, one line)"""
    it = c[0] if isinstance(c, (tuple, list)) and c else (None if isinstance(c, dict) else getattr(c, "item", None))
    if isinstance(c, dict):
        return None, (f"p{c.get('page', '?')} '{str(c.get('line') or c.get('label') or '')[:60]}' → "
                      f"{c.get('value')}" if c.get("value") is not None
                      else f"p{c.get('page', '?')} '{str(c.get('line') or '')[:60]}'")
    if it is not None:
        return it, f"p{getattr(it, 'page', '?')} '{_quote(it)[:70]}'"
    return None, str(c)[:80]


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
    refused = _refused_pages(loop, sheet, coord)
    for it, cur in leads_for(loop, prior, skip_pages=refused):
        blk.append(f"      lead: p{getattr(it, 'page', '?')} '{_quote(it)[:78]}' → this year {_fmt(cur)}")
    for it in nil_leads(loop, prior, skip_pages=refused):
        blk.append(f"      lead: p{getattr(it, 'page', '?')} '{_quote(it)[:60]}' prints your prior alone — "
                   "a blank beside it; this period may be nil")
    if len(blk) == 1 and prior is not None:
        blk.append("      lead: no printed line on file carries a comparative equal to this row's prior")
    if refused:
        blk.append("      you have refused this row against "
                   + ", ".join(f"{d} p{p}" for d, p in sorted(refused))
                   + " — those prints are not put under it again. If no print in this disclosure carries "
                     "it, skip it with \"scope\":\"disclosure\" and it is closed.")
    for extra in (getattr(loop, "leads", None) or {}).get((sheet, r), ())[:3]:
        blk.append(f"      lead: {str(extra)[:150]}")
    # the label-only and companion searches: what the card queue used to show
    # and nothing showed after it (reviewer 2026-09-17) — information, no ranks
    try:
        from .workqueue import _label_only_candidates, candidates_for
        seen_l = set()
        for c in (candidates_for(loop, sheet, r) or [])[:3]:
            it_c, q = _cand_line(c)
            if q in seen_l:
                continue
            seen_l.add(q)
            blk.append(f"      lead: {q[:110]}")
        t_row = (loop.targets or {}).get((sheet, r))
        if t_row is not None:
            for c in (_label_only_candidates(loop, sheet, r, t_row) or [])[:2]:
                it_c, q = _cand_line(c)
                if q in seen_l:
                    continue
                seen_l.add(q)
                blk.append(f"      lead: {q[:110]} — the label names this row, no number ties")
    except Exception:  # noqa: BLE001
        pass
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
    from .docid import KEY_NAMES as _KN
    L.append("  The key names this report measures — name the row THIS model computes for each one it "
             "carries, and omit the rest: " + ", ".join(_KN) + ".")
    L.append("  The four halves of the balance sheet are keys of their own: a figure that lands in the "
             "wrong half — perpetual securities in a liability row — leaves its half off the print while "
             "total liabilities and equity still ties, so the balance check cannot see it.")
    L.append("  The sheets, their year columns, and their labels:")
    room = cap
    for sh, ax in (loop.spec.get("year_axis") or {}).items():
        if sh not in loop.wb.sheetnames:
            continue
        cols = (ax.get("columns") or {}) if isinstance(ax, dict) else {}
        L.append(f"  --- {sh}: {len(cols)} year column(s); {loop.ty} is column {cols.get(str(loop.ty), '?')} ---")
        ws = loop.wb[sh]
        for r in range(1, ws.max_row + 1):
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
                  size_cap=16000, faces_cap=9000):
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
    L.append(f"## 1. THE KEYS against the print ({ty}) — a key is the model's own arithmetic: you never "
             "type into one, you set the inputs underneath it")
    L += _key_table(loop, rows, written, skipped)
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
    L.append("## 4. THE PRINTED FACES, each with the model rows it maps onto (history | the analyst's "
             "estimate | status | what the row feeds, then its LEADS — printed lines whose comparative "
             "equals the row's prior: information, not a pick)")
    # THE TURN CONTINUES WHERE THE LAST ONE STOPPED (owner 2026-09-17: every
    # turn rebuilt the same face order from the same rows, so the top faces
    # spent the whole budget and the rest of the model was never seen). What is
    # offered is the OPEN queue, and the next turn starts after the rows this
    # one showed — so the queue is walked, not the first page of it re-served.
    queue = open_queue(loop, rows, skipped)
    cur = int(loop.__dict__.get("_map_cursor") or 0)
    if cur >= len(queue):
        cur = 0
    order = queue[cur:] + queue[:cur]
    lead_pages, with_lead = {}, set()
    for sheet, coord, r in order:
        pcol = prior_column(loop.spec, sheet, ty)
        prior = _held(pre_wb, ev0, sheet, f"{pcol}{r}") if pcol else None
        for it, _cur in leads_for(loop, prior, k=2, skip_pages=_refused_pages(loop, sheet, coord)):
            lead_pages.setdefault(_page_of(it), []).append(
                (sheet, coord, r))
            with_lead.add((sheet, coord))
    placed, room = set(), size_cap
    # THE EARLIER PERIOD'S FACES ARE ON THE SHELF, NOT IN THE CONTEXT (reviewer
    # 2026-09-17: last year's report filled the section with stubs). `page` and
    # `find` still reach every one of them.
    here = set()
    try:
        here = {str(d) for d in (page_text.docs() if hasattr(page_text, "docs")
                                 else {d for d, _p in (page_text or {})})}
        old_docs = set(loop.ledger.noncurrent_docs() or ())   # evidence: the run's own verdict on which document proves THIS period; the shelf still answers `page`/`find`
    except Exception:  # noqa: BLE001
        old_docs = set()
    faces = [f for f in _faces(loop) if f[1] in here and f[1] not in old_docs]
    # every open row gets a face: a lead puts it on its own page, and a row no
    # printed line points at is read against the statement faces of this run —
    # never one it has already refused
    for _k, _chunk in spread_over_faces([t for t in order if (t[0], t[1]) not in with_lead],
                                        [(d, p) for _f, d, p in faces],
                                        refused=lambda t: _refused_pages(loop, t[0], t[1])).items():
        lead_pages.setdefault(_k, []).extend(_chunk)
    # THE ROWS COME FIRST, THE FACES FOLLOW THEM (reviewer 2026-09-17: the face
    # section was built face by face and drained the room before the queue was
    # reached, so the same 54 rows were served on all 30 turns and 95 rows were
    # never shown at all). This turn takes the queue in order, for as many rows
    # as the room holds, and shows each one under the face it is to be read
    # against — so the cursor moves by exactly the rows the brain saw.
    face_of = {}
    for _k, _rws in lead_pages.items():
        for _t in _rws:
            face_of.setdefault((_t[0], _t[1]), _k)
    faces_by_key = {(d, p): f for f, d, p in faces}
    shown, bodies, order_of_face, room = [], {}, [], size_cap
    for sheet, coord, r in order:
        key = face_of.get((sheet, coord))
        txt = (page_text or {}).get(key) if key else None
        cost, body = 0, None
        if key and key not in bodies:
            body = [ln for ln in str(txt).splitlines() if ln.strip()] if txt else []
            cost += sum(len(x) for x in body)
        st = status_of(loop, sheet, coord, written, skipped)
        block = "\n".join(_row_block(loop, pre_wb, ev0, sheet, coord, r, st, cls.get((sheet, coord), "")))
        cost += len(block)
        if room - cost < 0 and shown:
            break
        room -= cost
        if key and key not in bodies:
            bodies[key] = body
            order_of_face.append(key)
        shown.append((key, block))
        placed.add((sheet, coord, r))
        # WHAT THIS ROW IS BEING READ AGAINST, so its refusal is scoped to the
        # print in front of it and not to the whole disclosure
        if key:
            _read_against(loop)[f"{sheet}!{coord}"] = key
        else:
            _read_against(loop).pop(f"{sheet}!{coord}", None)
    for key in order_of_face:
        doc, pg = key
        face = faces_by_key.get(key, "table")
        L.append(f"  ===== {str(face).upper()} — {doc} p{pg} ====="
                 + ("" if bodies.get(key) else " (no text on file — `find` reads its extracted lines)"))
        L += ["   " + x for x in (bodies.get(key) or [])]
        mine = [b for k2, b in shown if k2 == key]
        L.append(f"    --- the model rows of this turn that are read against this face ({len(mine)}) ---")
        L += mine
    loose = [b for k2, b in shown if k2 is None]
    if loose:
        L.append("")
        L.append("  ----- the open rows this run found no printed face for — `find` or `page` what carries "
                 "them, or skip them with \"scope\":\"disclosure\" -----")
        L += loose
    unshown = len(queue) - len(shown)
    L.append(f"  ({len(rows)} input rows in total, {len(queue)} of them still open"
             + (f"; the {unshown} open rows this turn had no room for are the ones the next turn opens "
                "with, and `show` reaches any of them now" if unshown > 0 else "") + ")")
    # the queue moves on by exactly the rows this turn showed
    if queue:
        loop.__dict__["_map_cursor"] = (cur + max(1, len(shown))) % len(queue)
    ref_lines = list(loop.__dict__.get("_map_refused") or [])
    if ref_lines:
        L.append("")
        L.append("## 4b. WHAT YOU HAVE ALREADY REFUSED, AND WHY — a page you refused for a row is never put "
                 "under that row again; the row itself is closed only when you skip it with "
                 "scope \"disclosure\"")
        L += [f"  {x[:160]}" for x in ref_lines[-25:]]
    if answers:
        L.append("")
        L.append("## 5. YOUR LAST TURN")
        # a budget, like every other section (reviewer 2026-09-17: one batch of
        # 40 answers could outweigh the model itself)
        room_a, kept = 6000, 0
        for a in answers:
            if room_a - len(str(a)) < 0:
                L.append(f"  ({len(answers) - kept} more answers from that turn are not carried here)")
                break
            room_a -= len(str(a))
            kept += 1
            L.append(str(a))
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
    if isinstance(held, str) and held.startswith("=") and not is_own_arithmetic(
            loop.wb, sheet, coord, _act_col(loop, sheet), prior_column(loop.spec, sheet, int(loop.ty))):
        held = None                      # the analyst's forecast for this year: the actual replaces it
    proposed = entry.get("formula")
    preserves_structure = (has_embedded_inputs(held) and isinstance(proposed, str)
                           and literal_template(held) is not None
                           and literal_template(held) == literal_template(proposed))
    if isinstance(held, str) and held.startswith("=") and not preserves_structure:
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
    loop.__dict__["_map_ref"] = (sheet, coord)
    printed, page, line = entry.get("printed"), entry.get("page"), entry.get("line")
    # A ZERO IS A FIGURE ONLY WHERE A NIL IS PRINTED (CLP live: 34 rows answered
    # `printed: 0` with no line printing a nil, and 34 cells were zeroed). A row
    # that CARRIED a figure last year and carries none now is a real change, and
    # a real change is printed: the dash, the blank beside the comparative, or
    # the brain's own arithmetic. Nothing is written; the brain's reason is
    # recorded and the row stays open. A row whose prior is itself nil has no
    # magnitude to find, and the zero stands as the reading it is.
    _z = next((x for x in (printed, entry.get("value"))
               if isinstance(x, (int, float)) and not isinstance(x, bool)), None)
    if _z == 0 and isinstance(prior, (int, float)) and abs(prior) >= 0.5 and not nil_leads(loop, prior):
        return None, False, (f"{sheet}!{coord}: you answered zero and no line on file prints a nil beside "
                             f"this row's prior ({_fmt(prior)}) — say which line shows it, state the "
                             "arithmetic, or skip the row with your reason"), {}
    if isinstance(printed, (int, float)) and page is not None:
        try:
            pg = int(page)
        except (TypeError, ValueError):
            return float(printed), False, f"'{page}' is not a page number — the figure lands red", {}
        docs = {str(entry["doc"])} if entry.get("doc") else set(sources)
        if entry.get("units", "document") == "model":
            return _quote_verdict(loop, page_text, docs, pg, float(printed), line, prior)
        from .reader import _page_line, _quoted_verdict
        scales = _page_scales(loop)
        hits = []
        for doc in sorted(docs):
            text = (page_text or {}).get((doc, pg))
            if not text:
                text = "\n".join(_quote(it) for it in _items(loop)
                                 if getattr(it, "doc", None) == doc and getattr(it, "page", None) == pg)
            hit = _page_line({(doc, pg): text}, pg, float(printed), line or "", {doc}) if text else None
            if hit:
                answer = _quoted_verdict(hit, float(hit.get("figure", printed)), prior, pg,
                                         scales, _dominant(scales), log, f"{sheet}!{coord}")
                if answer:
                    kin, why_k = _name_is_kin(loop, sheet, coord, hit["text"])
                    plain = answer.get("conf") == 4 and kin
                    hits.append((answer["value"], plain, (answer.get("note") or answer.get("why", "")) if kin else why_k, answer))
        if len({(h[3].get("doc"), h[0]) for h in hits}) == 1:
            return hits[0]
        if hits:
            return None, False, "the quote resolves to multiple documents; specify doc", {}
        return None, False, "the document-unit quote has no verified conversion; specify doc and printed line", {}
    f_ = entry.get("formula")
    if isinstance(f_, str) and f_.strip().startswith("="):
        # A BACK-OUT IS A FORMULA, NOT A HARDCODE (house law): the analyst must
        # see how the number was built. Code checks that every term of it is a
        # figure the print carries; the arithmetic is the model's own from then on.
        from .composites import literals_of
        terms = [float(x) for x in literals_of(f_)]
        missing = [t for t in terms if abs(t) >= 0.5 and not _hits_printed(loop, t, page_text)]
        if missing:
            return f_, False, (f"the back-out lands red: {', '.join(f'{m:,.2f}' for m in missing[:3])} "
                               "is not a figure printed on any page on file"), {"line": f_[:60]}
        return f_, False, f"back-out arithmetic is traceable; verify operand definitions: {f_[:60]}", {"line": f_[:60]}
    v = _num(entry.get("value"))
    if v is None:
        return None, False, f"{sheet}!{coord}: no `value`, `printed` figure or `formula` — a model cell takes a figure", {}
    for m in _ARITH.finditer(because):
        if not _arith_ties(m, v):
            continue
        # THE ARITHMETIC STANDS ON PRINTED FIGURES (reviewer 2026-09-17: a
        # stated sum that re-computes to the value landed PLAIN with nothing
        # printed behind it — '440 + 20' can be invented). The same evidence the
        # back-out formula answers to: every term of size is a figure some page
        # on file prints.
        terms = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*\.?\d*", m.group(0))]
        missing = [t for t in terms if abs(t) >= 0.5 and not _hits_printed(loop, t, page_text)]
        if missing:
            return v, False, (f"your arithmetic re-computes, but {', '.join(f'{x:,.2f}' for x in missing[:3])} "
                              "is not a figure printed on any page on file — it lands red with your reason"), {}
        return "=" + m.group(0).replace(",", ""), False, f"arithmetic is traceable but operand meanings need review: {because[:80]}", {
            "line": because[:60]}
    return v, False, "no quoted printed line and no arithmetic code can re-compute — it lands red with your reason", {}


def _section_label(loop, sheet, r):
    """The section this row sits under — the model's own heading for it, which
    a row whose OWN name carries no content words ('of which', '— Australia')
    borrows. It is read as the nearest line above that names something and
    holds no figure of its own."""
    ws = loop.wb[sheet]
    for k in range(r - 1, 0, -1):
        lab = _label(ws, k)
        if lab.startswith("row ") or not _kin_words(lab):
            continue
        if any(isinstance(ws.cell(row=k, column=c).value, (int, float)) for c in range(2, 6)):
            continue   # evidence: a line carrying figures is a row of the statement, not its heading
        return lab
    return ""


def _kin_words(text):
    """The content words of a name, at their stems — 'Other gains, net' and
    'Other gain' are the same word twice."""
    from .numerics import norm_label, STOPWORDS
    return {(w[:-1] if len(w) > 3 and w.endswith("s") else w)
            for w in str(norm_label(text) or "").split()
            if w not in STOPWORDS and len(w) > 2}


# THE HOUSE GLOSSARY (CLAUDE.md): names an analyst's model and a printed
# statement both use for one thing. Two names in the same entry are kin —
# positive evidence, the same kind the number tie is, and the reason the
# glossary exists at all. It never decides a mapping; it only stops a correct
# mapping being called a name mismatch.
_GLOSSARY = (
    {"revenue", "turnover", "sales", "income from operations"},
    {"finance cost", "interest expense", "borrowing cost", "finance expense", "financial expense"},
    {"finance income", "interest income"},
    {"property plant and equipment", "ppe", "fixed asset", "tangible asset"},
    {"depreciation and amortisation", "depreciation and amortization", "d a", "da"},
    {"capex", "capital expenditure", "purchase of property plant and equipment",
     "purchase of fixed asset", "addition to property plant and equipment"},
    {"net profit", "net income", "profit attributable to shareholder",
     "profit attributable to owner", "profit for the year attributable to equity holder", "earnings"},
    {"minority interest", "non controlling interest", "noncontrolling interest"},
    {"associate", "joint venture", "jointly controlled entity", "jce"},
    {"cash", "cash and cash equivalent", "cash and bank balance", "bank balances and cash"},
    {"gearing", "net debt to total capital", "net debt to equity"},
)


def _glossary_kin(a, b):
    from .numerics import norm_label
    na, nb = " " + str(norm_label(a) or "") + " ", " " + str(norm_label(b) or "") + " "
    for entry in _GLOSSARY:
        if any(" " + t + " " in na or na.strip() == t for t in entry) \
                and any(" " + t + " " in nb or nb.strip() == t for t in entry):
            return True
    return False


def _name_is_kin(loop, sheet, coord, printed_line):
    """THE NAME MUST BE KIN, NOT ONLY THE NUMBER (owner 2026-09-17: Aus!AI25
    'Finance costs' was mapped from 'Lost Days - employees only ... 471' — the
    number tied and the line was about safety statistics). The brain quoted the
    line, so checking that it NAMES something kin to the row is verification,
    not a decision. -> (ok, why)"""
    from .numerics import kinship, label_of
    row_label = _label(loop.wb[sheet], _row_of(coord))
    # the row's OWN name answers first; a row whose name says nothing on its own
    # ('of which', a dash and a place) is read under its section's heading
    row_name = row_label if _kin_words(row_label) else \
        (row_label + " " + _section_label(loop, sheet, _row_of(coord))).strip()
    line_name = label_of(str(printed_line or "")) or str(printed_line or "")
    if not str(line_name).strip():
        return False, "the line you quoted carries no label to check the row's name against"
    # A MODEL WRITES 'Other gain' WHERE THE STATEMENT PRINTS 'Other gains, net',
    # and 'Turnover' where it prints 'Revenue'. A word and its plural are the
    # same word, and the house glossary's names are the same name.
    if kinship(row_name, line_name) or _kin_words(row_name) & _kin_words(line_name) \
            or _glossary_kin(row_name, line_name):
        return True, ""
    # CODE CHECKS ONLY WHAT IT CAN READ: a model labelled in English against a
    # statement printed in Chinese share no words by construction, and their
    # silence is not evidence against the brain's reading (DFE). Where the two
    # names are written in the same script, the check speaks.
    import re as _re2
    cjk_row = bool(_re2.search(r"[\u4e00-\u9fff]", row_name))
    cjk_line = bool(_re2.search(r"[\u4e00-\u9fff]", str(line_name)))
    if cjk_row != cjk_line:
        return True, "the names are in different scripts — code cannot compare them; your reading stands"
    return False, (f"the number ties but the name does not: your row is '{row_name[:40]}' and the line you "
                   f"quoted names '{str(line_name)[:40]}'")


def _quote_verdict(loop, page_text, sources, pg, printed, line, prior):
    """THE BRAIN QUOTES IN THE MODEL'S UNITS (DFE live 2026-09-17: every write
    landed red — "no line of p12 prints 78,615.27743983 as you quoted it" —
    because the page prints 78,615,277,439.83 yuan and the model holds
    thousands). The figure the brain gives is the figure for the MODEL; code
    finds the line it quoted and checks the printed number against it AT THE
    PAGE'S OWN SCALE. The scale stays the page's (a tie at another scale is
    still red); only the units of the quote have changed.
    -> (value, plain, why, evidence)"""
    from .reader import _page_line
    from .writegate import _SCALES, _ties_full_precision
    scales = _page_scales(loop)
    dom = _dominant(scales)
    best = None
    for doc in sorted(sources):
        txt = (page_text or {}).get((doc, pg))
        if not txt:
            continue
        f_page = scales.get((doc, pg)) or dom.get(doc)
        for fs in ([f_page] if f_page else list(_SCALES)):
            hit = _page_line({(doc, pg): txt}, pg, abs(printed) * fs, line or "", {doc})
            if hit is None:
                continue
            comp = hit.get("prior")
            tie = (isinstance(comp, (int, float)) and isinstance(prior, (int, float))
                   and abs(prior) >= 0.5 and _ties_full_precision(abs(comp) / fs, abs(prior)))
            # the print owns the sign; the magnitude is the brain's figure
            value = abs(printed) * (-1.0 if float(hit.get("figure") or 0) < 0 else 1.0)
            if isinstance(prior, (int, float)) and prior != 0 and tie and (comp < 0) != (prior < 0):
                value = -value
            ev = {"doc": doc, "page": pg, "line": hit["text"][:60]}
            if tie:
                kin, why_k = _name_is_kin(loop, loop.__dict__.get("_map_ref", ("", ""))[0],
                                          loop.__dict__.get("_map_ref", ("", ""))[1], hit["text"]) \
                    if loop.__dict__.get("_map_ref") else (True, "")
                if not kin:
                    return value, False, f"p{pg} '{hit['text'][:50]}' — {why_k}", ev
                return value, True, (f"p{pg} '{hit['text'][:60]}' — the comparative ties your prior"
                                     + (f" (the page prints in x{fs:,.0f})" if fs != 1 else "")), ev
            other = None
            if isinstance(comp, (int, float)) and isinstance(prior, (int, float)) and abs(prior) >= 0.5:
                other = next((g for g in _SCALES if _ties_full_precision(abs(comp) / g, abs(prior))), None)
            why = (f"p{pg} '{hit['text'][:50]}' — scale mismatch: its comparative ties your prior only at "
                   f"x{other:,.0f} and this page carries x{fs:,.0f}" if other and other != fs else
                   f"p{pg} '{hit['text'][:50]}' — the line carries no comparative that ties your prior")
            best = best or (value, False, why, ev)
    # A SCANNED PAGE HAS NO TEXT TO QUOTE FROM: the extractor's own line stands
    # in for the page's — and it must still be the line the brain read, at this
    # page's scale (the F2 and F10 laws, applied to the ledger).
    from .numerics import line_cells
    from .writegate import _nums, comparative_index, _sourceable
    want = [x for x in line_cells(str(line or "")) if isinstance(x, (int, float))]
    for it in _items(loop):
        if str(getattr(it, "page", "")) != str(pg) or not _sourceable(it):
            continue
        ns = [n for n in _nums(it) if isinstance(n, (int, float))]
        if not ns:
            continue
        f_page = scales.get((getattr(it, "doc", None), pg)) or dom.get(getattr(it, "doc", None))
        for fs in ([f_page] if f_page else list(_SCALES)):
            i_hit = next((i for i, n in enumerate(ns)
                          if _ties_full_precision(abs(n), abs(printed) * fs)), None)
            if i_hit is None:
                continue
            if want and any(not any(_ties_full_precision(abs(q), abs(n)) for n in ns) for q in want):
                continue                     # the brain quoted figures this line does not print
            ci = comparative_index(ns, getattr(it, "columns", None), i_hit)
            comp = ns[ci] if ci is not None else None
            ev = {"doc": getattr(it, "doc", None), "page": pg, "line": _quote(it)[:60]}
            value = abs(printed) * (-1.0 if ns[i_hit] < 0 else 1.0)
            if isinstance(comp, (int, float)) and isinstance(prior, (int, float)) and abs(prior) >= 0.5 \
                    and _ties_full_precision(abs(comp) / fs, abs(prior)):
                if prior < 0 and value > 0:
                    value = -value
                kin, why_k = _name_is_kin(loop, loop.__dict__.get("_map_ref", ("", ""))[0],
                                          loop.__dict__.get("_map_ref", ("", ""))[1], _quote(it)) \
                    if loop.__dict__.get("_map_ref") else (True, "")
                if not kin:
                    return value, False, f"p{pg} '{_quote(it)[:50]}' — {why_k}", ev
                return value, True, (f"p{pg} '{_quote(it)[:60]}' (the extracted line you quoted) — the "
                                     "comparative ties your prior"), ev
            other = next((g for g in _SCALES if isinstance(comp, (int, float)) and isinstance(prior, (int, float))
                          and abs(prior) >= 0.5 and _ties_full_precision(abs(comp) / g, abs(prior))), None)
            best = best or (value, False,
                            (f"p{pg} '{_quote(it)[:50]}' — scale mismatch: its comparative ties your prior "
                             f"only at x{other:,.0f} and this page carries x{fs:,.0f}" if other and other != fs
                             else f"p{pg} '{_quote(it)[:50]}' — no comparative on that line ties your prior"), ev)
    if best:
        return best
    return (float(printed), False,
            f"no line of p{pg} on file prints {printed:,.2f} as you quoted it, at this page's own scale "
            "— it lands red with your reason", {"page": pg, "line": str(line or "")[:60]})


def _apply(loop, entries, page_text, sources, log, skipped=None, deadline=None, correction=False):
    """Apply one change (a `sets` batch is ONE change). -> lines"""
    out, ty = [], int(loop.ty)
    for n_done, e in enumerate(entries):
        if deadline is not None and time.monotonic() > deadline:
            # THE CLOCK INSIDE A BATCH (reviewer 2026-09-17): what was verified
            # and written before it stands — nothing is unwound, and the count
            # is said out loud.
            out.append(f"  clock mid-batch: {n_done} of {len(entries)} applied; the rest were not reached")
            log(f"[map] clock mid-batch: {n_done} of {len(entries)} applied")
            break
        sheet, coord = e["sheet"], e["coord"]
        v, plain, why, ev = verdict(loop, e, page_text, sources, log)
        if v is None:
            # THE ROW STAYS OPEN (owner 2026-09-17): an answer code cannot write
            # is the brain's reason, kept in front of it, not a row swallowed.
            out.append(f"  {sheet}!{coord} nothing written: {why}")
            loop.__dict__.setdefault("_map_refused", []).append(f"{sheet}!{coord}: {why[:120]}")
            continue
        colour = None if plain is True else ("orange" if plain == "orange" else "red")
        # A LATER BATCH NEVER OVERWRITES AN EARLIER PLAIN WRITE (owner
        # 2026-09-17, the parallel faces): two faces that both claim a row are a
        # disagreement, and a disagreement is the analyst's, not code's — the
        # cell keeps the first reading and goes red carrying both.
        _st_now = _written(loop).get(f"{sheet}!{coord}")
        if not correction and _st_now in ("filled", "red") and (_st_now == "filled" or
                                             (loop.served.get((sheet, _row_of(coord))) or {}).get("conf", 0) >= 4):
            _prev = (loop.served.get((sheet, _row_of(coord))) or {}).get("value")
            _same = isinstance(_prev, (int, float)) and not isinstance(v, str) \
                and abs(float(_prev) - float(v)) <= max(0.05, abs(float(v)) * 1e-4)
            if not _same:
                loop.writer.flag_ref(f"{sheet}!{coord}", "red",
                                     f"TWO READINGS: this row was mapped {_fmt(_num(_prev))} and then "
                                     f"{_fmt(_num(v)) if not isinstance(v, str) else str(v)[:20]} from another "
                                     f"face ({str(e.get('because') or '')[:100]}). The first stands; "
                                     "your call which is right.")
                _written(loop)[f"{sheet}!{coord}"] = "red"
                out.append(f"  {sheet}!{coord}: two readings ({_fmt(_num(_prev))} then "
                           f"{_fmt(_num(v)) if not isinstance(v, str) else str(v)[:20]}) — the first stands, red")
                continue
            continue
        pcol = prior_column(loop.spec, sheet, ty)
        because = str(e.get("because") or "no reason given")[:200]
        note = (f"Mapped by the brain because: {because} [{why[:90]}]" if colour is None else
                (f"Backed out by the brain: {because} [{why[:90]}]" if colour == "orange" else
                 f"Mapped by the brain WITHOUT tying evidence — please check. Because: {because} [{why[:90]}]"))
        val = v if isinstance(v, str) else float(v)
        # the cell still holding a formula here is the analyst's FORECAST for
        # the year now reported (the gate refused the model's own arithmetic
        # above): the mark-to-actual recipe replaces it, and says so
        _cur = loop.wb[sheet][coord].value
        _over = isinstance(_cur, str) and _cur.startswith("=")
        if _over:
            note += f" [previous formula for {ty}: {str(_cur)[:40]}]"
        ok = loop.writer.write(sheet, coord, val,
                               prior_coord=f"{pcol}{_row_of(coord)}" if pcol else None,
                               trusted=(plain is True or plain == "orange"), force_lock=True,
                               allow_empty=True, author_brain=True, over_formula=_over,
                               flag=colour, note=note)
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
        # PROGRESS IS A FIGURE LANDING IN A CELL (reviewer 2026-09-17: the write
        # journal also carries the flags, so a turn that only painted a cell red
        # read as a write and the loop could turn for ever). This counts the
        # cells that took a figure, and nothing else.
        loop.__dict__["_map_cells"] = int(loop.__dict__.get("_map_cells") or 0) + 1
        back = Evaluator(loop.wb).cell(sheet, coord)
        shown = back if isinstance(back, (int, float)) else val
        if isinstance(back, (int, float)) and not isinstance(val, str) \
                and abs(back - float(val)) > max(0.05, abs(float(val)) * 1e-6):
            log(f"[map] read-back {sheet}!{coord} shows {back} after writing {val}")
        loop.writer.log.setdefault("change_records", []).append({
            "ref": f"{sheet}!{coord}", "before": _cur, "after": val,
            "period": getattr(loop, "period", str(ty)), "reason": str(e.get("because") or ""),
            "evidence": dict(ev), "flag": colour, "correction": bool(correction),
        })
        loop.served[(sheet, _row_of(coord))] = {
            "value": float(shown) if isinstance(shown, (int, float)) else None,
            "status": "OK", "doc": ev.get("doc"), "page": ev.get("page"),
            "line": ev.get("line") or str(e.get("line") or "")[:60],
            "conf": 4 if colour is None else 3, "homed": True, "home": (sheet, coord),
            "flag": colour,
            "note": f"mapping: {because[:90]} — {why[:100]}"}
        # THE LAST ACTION WINS (reviewer 2026-09-17: a row skipped and then
        # mapped still read 'skipped' and kept the skip's red flag)
        _written(loop)[f"{sheet}!{coord}"] = "filled" if colour is None else "red"
        if skipped is not None:
            skipped.pop(f"{sheet}!{coord}", None)
        if colour is None:
            loop.writer.flag(sheet, coord, None)
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
        if e.get("scope") is None:
            e["scope"] = call.get("scope")
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
        nm_k = str(k.get("name") or "key")[:40]
        loop.spec.setdefault("key_rows", []).append({"name": nm_k, "sheet": sh, "row": r,
                                                     "source": "the brain's anatomy"})
        if isinstance(k.get("printed"), (int, float)) and k.get("page") is not None:
            # the print of a key is evidence like any other: the quoted line
            # must be on that page, and code converts it at the page's scale
            try:
                from .reader import _page_line, _quoted_verdict
                sources = {getattr(it, "doc", None) for it in _items(loop)} - {None}
                pg = int(k["page"])
                hit = _page_line(getattr(loop, "_map_pages", None) or {}, pg, float(k["printed"]),
                                 k.get("line") or "", sources)
                pcol = prior_column(loop.spec, sh, int(loop.ty))
                prior = _held(loop.wb, ev, sh, f"{pcol}{r}") if pcol else None
                scales = _page_scales(loop)
                vv = _quoted_verdict(hit, float(k["printed"]), prior, pg, scales, _dominant(scales),
                                     log, f"{sh}!{co}") if hit else None
                if vv:
                    panel = getattr(loop, "key_panel", None)
                    if panel is None:
                        panel = loop.key_panel = {}
                    panel[nm_k] = {"print": float(vv["value"]), "prior": prior,
                                   "line": hit["text"][:60], "page": pg}
                    out.append(f"  the print for '{nm_k}': {vv['value']:,.2f} from p{pg} '{hit['text'][:50]}'")
                else:
                    dropped.append(f"the print you quoted for '{nm_k}' is not on p{k.get('page')}")
            except Exception as e_k:  # noqa: BLE001
                dropped.append(f"the print for '{nm_k}' could not be verified ({type(e_k).__name__})")
        took += 1
        out.append(f"  key '{k.get('name')}' at {sh}!{r} '{_label(loop.wb[sh], r)}' reads {_fmt(_num(v))}")
    loop.writer.log.setdefault("anatomy", []).append(
        f"the brain's reading of this model: {len(call.get('checks') or [])} check row(s), "
        f"{len(call.get('keys') or [])} key row(s), statements on "
        f"{', '.join(str(x) for x in (call.get('statements') or []))[:80]} — "
        f"{str(call.get('because') or '')[:150]}")
    for d in dropped:
        out.append(f"  dropped {d}")
    # WHAT WAS TAKEN, AND WHAT IS MEASURED, MUST AGREE (reviewer 2026-09-17: the
    # log said "2 key rows now measured" by counting the spec, while the key
    # table showed none — the next turn contradicted the log).
    try:
        from .keytie import key_state as _ks
        measured = len(_ks(loop.wb, loop.spec, int(loop.ty), getattr(loop, "key_panel_path", None),
                           panel=getattr(loop, "key_panel", None)))
    except Exception:  # noqa: BLE001
        measured = 0
    n_checks = len(loop.spec.get("check_rows") or [])
    log(f"[map] anatomy: {took} row(s) taken, {len(dropped)} dropped — {n_checks} check row(s) and "
        f"{measured} key row(s) are measured from this turn on")
    return [f"anatomy: {took} row(s) taken, {len(dropped)} dropped; {n_checks} check row(s) and "
            f"{measured} key row(s) are measured from now on"] + out


def _one_call(loop, pre_wb, call, page_text, sources, skipped, log, deadline=None, face=None):
    tool = str(call.get("tool") or "").strip().lower()
    if tool == "page":
        return _page_text_of(page_text, call.get("n") or call.get("page") or 0, doc=call.get("doc"))
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
            out += _apply(loop, entries, page_text, sources, log, skipped=skipped, deadline=deadline)
        elif not bad:
            out = ["set: no cell named"]
        return out
    if tool == "skip":
        entries, bad = _entries(loop, call)
        if bad and not entries:
            return ["skip: " + "; ".join(bad)]
        out = []
        # THE SKIP IS A VERDICT ON THE PRINT THE ROW WAS READ AGAINST, NEVER ON
        # THE ROW — unless the brain says the disclosure itself lacks it. "This
        # page does not carry my row" takes that page off the row (its leads,
        # and the faces it is dealt to) and the row goes back in the queue for
        # the prints it has not refused. Only "scope":"disclosure" closes it.
        for e in entries:
            why = str(e.get("because") or "").strip()
            ref = f"{e['sheet']}!{e['coord']}"
            if not why:
                out.append(f"skip {ref}: a skip carries your reason — say why")
                continue
            where = face or _read_against(loop).get(ref)
            whole = _whole_disclosure(e.get("scope"))
            if not whole and where is None:
                out.append(f"skip {ref}: no print was in front of you for this row, so there is nothing to "
                           "take off it. `find` or `page` what carries it — or, if NO print in this "
                           "disclosure does, skip it again with \"scope\":\"disclosure\" and it is closed.")
                continue
            _written(loop).pop(ref, None)      # the last action on a cell is the one that stands
            if not whole:
                _page_skips(loop).setdefault(ref, set()).add(where)
                # it is re-paired with a print it has not refused
                _read_against(loop).pop(ref, None)
                loop.__dict__.setdefault("_map_refused", []).append(
                    f"{ref}: refused against {where[0]} p{where[1]} — {why[:90]}")
                out.append(f"skip {ref}: {where[0]} p{where[1]} is taken off this row — it is not put under "
                           "it again, and the row stays open for the prints that do carry it. If NO print in "
                           "this disclosure carries it, skip it again with \"scope\":\"disclosure\".")
                continue
            loop.writer.flag_ref(ref, "red", f"NOT MAPPED — the analyst's own judgment: {why[:200]}")
            skipped[ref] = why
            loop.__dict__.setdefault("_map_refused", []).append(
                f"{ref}: skipped"
                + (f" against {where[0]} p{where[1]}" if where else "")
                + f" — closed, not in this disclosure — {why[:90]}")
            out.append(f"skip {ref}: recorded red — {why[:100]}")
        return out
    if tool == "anatomy":
        return _t_anatomy(loop, call, log)
    if tool == "restate":
        return _t_restate(loop, call, page_text, sources, log)
    return [f"'{tool}' is not one of the tools: page, find, show, set, sets, skip, restate, done"]


# ── the loop ─────────────────────────────────────────────────────────────

def sequential_budget(map_budget, faces_took, floor=60.0):
    """WHAT THE FACES DID NOT SPEND IS STILL THE MAPPING'S (owner 2026-09-17:
    the CLP face round answered in 2.3 minutes of the 23.2 it was given, and the
    sequential pass was handed the arithmetic remainder of the SPLIT — 9.9 min —
    so 21 minutes of the run's clock were thrown away with 217 rows unread).
    The clock is one clock: what is left of the mapping's budget is what is
    left, measured, not the share the split named."""
    return max(float(floor), float(map_budget) - float(faces_took))


def _face_rows(loop, pre_wb, rows, skipped):
    """{(doc, page): [open rows to put in front of that face]}.

    EVERY OPEN ROW GETS A PAGE (owner 2026-09-17: the faces were built only from
    rows that had a lead, so a row with no printed line whose comparative ties
    its prior was never shown to anybody and shipped "not reached"). A lead
    places a row on its own page; a row with no lead is placed on the faces of
    its own kind — the statement pages the name judgment identified — so the
    brain at least reads it against the right print and can say why not."""
    ev0 = Evaluator(pre_wb)
    written, out, placed = _written(loop), {}, set()
    for sheet, coord, r in rows:
        if status_of(loop, sheet, coord, written, skipped) != "unfilled":
            continue
        pcol = prior_column(loop.spec, sheet, int(loop.ty))
        prior = _held(pre_wb, ev0, sheet, f"{pcol}{r}") if pcol else None
        for it, _cur in leads_for(loop, prior, k=2, skip_pages=_refused_pages(loop, sheet, coord)):
            out.setdefault(_page_of(it), []).append(
                (sheet, coord, r))
            placed.add((sheet, coord))
    rest = [(sh, co, r) for sh, co, r in rows
            if (sh, co) not in placed and status_of(loop, sh, co, written, skipped) == "unfilled"]
    faces = [(d, p) for _f, d, p in _faces(loop) if (page_of_text(loop, d, p))]
    for key, chunk in spread_over_faces(rest, faces,
                                        refused=lambda t: _refused_pages(loop, t[0], t[1])).items():
        out.setdefault(key, []).extend(chunk)
    return out


def page_of_text(loop, doc, pg):
    pt = loop.__dict__.get("_map_pages") or {}
    return (pt.get((doc, pg)) if hasattr(pt, "get") else None)


def _face_context(loop, pre_wb, face, doc, pg, rows_here, page_text, rows_all, skipped, size_cap=14000):
    """ONE FACE, ON ITS OWN: its printed text, the model rows its lines point at,
    and the keys — small enough to answer in one batch, and nothing else."""
    ev0 = Evaluator(pre_wb)
    written = _written(loop)
    L = [f"## THIS TURN IS ONE FACE: {str(face).upper()} — {doc} p{pg}",
         "Answer with ONE `sets` batch for the rows below. Nothing else is asked of you now; the rows of "
         "other faces are another call's work.", ""]
    L.append(f"## THE KEYS against the print ({int(loop.ty)}) — a key is the model's own arithmetic: "
             "you never type into one, you set the inputs underneath it")
    L += _key_table(loop, rows_all, written, skipped)
    L.append("")
    L.append(f"## THE PAGE — {doc} p{pg}")
    txt = (page_text or {}).get((doc, pg))
    if txt:
        L += ["   " + ln for ln in str(txt).splitlines() if ln.strip()][:60]
    else:
        L.append("   (no text on file for this page — the extracted lines are in the leads below)")
    L.append("")
    L.append("## THE MODEL ROWS THIS FACE'S LINES POINT AT")
    cls = _classes(loop, rows_all)
    # THE CALL IS BOUNDED BY ITS SIZE, NOT BY A COUNT (reviewer 2026-09-17: a
    # per-face count dropped rows before anyone read them). What does not fit in
    # one call stays OPEN — the sequential queue puts it in front of the brain.
    room, left = size_cap, 0
    for sheet, coord, r in rows_here:
        blk = _row_block(loop, pre_wb, ev0, sheet, coord, r,
                         status_of(loop, sheet, coord, written, skipped), cls.get((sheet, coord), ""))
        cost = sum(len(x) for x in blk)
        if room - cost < 0:
            left += 1
            continue
        room -= cost
        L += blk
    if left:
        L.append(f"  ({left} more open row(s) of this model do not fit in this call — they stay open and "
                 "come back in the mapping loop)")
    # WHAT THESE ROWS HAVE ALREADY REFUSED comes with them (reviewer 2026-09-18:
    # the face round never carried it, so a row refused on one face was refused
    # again on the next without the brain knowing it had been there before)
    here = {f"{sh}!{co}:" for sh, co, _r in rows_here}
    ref_lines = [x for x in (loop.__dict__.get("_map_refused") or [])
                 if any(x.startswith(p) for p in here)]
    if ref_lines:
        L.append("")
        L.append("## WHAT YOU HAVE ALREADY REFUSED FOR THESE ROWS — a page you refused is never put under "
                 "that row again; the row itself is closed only by a skip with scope \"disclosure\"")
        L += [f"  {x[:160]}" for x in ref_lines[-25:]]
    return "\n".join(L)


def map_faces(loop, pre_wb, census, page_text, log, ask_json, deadline_s=900.0, workers=8):
    """THE FACES ARE MAPPED AT ONCE (owner 2026-09-17: Luna takes about two
    minutes a turn whatever the reasoning, so a sequential loop cannot reach a
    model of 337 rows in half an hour — CLP live: 19 turns, 34 minutes, 19
    cells). One call per printed face, all in flight together; code applies the
    batches in the order the faces come, under every gate rule, and a later
    batch never overwrites an earlier plain write. -> faces answered"""
    import concurrent.futures as _cf
    rows = input_rows(loop, census)
    loop.__dict__["_map_pages"] = page_text
    sources = {getattr(it, "doc", None) for it in _items(loop)} - {None}
    skipped = loop.__dict__.setdefault("_map_skipped", {})
    by_face = _face_rows(loop, pre_wb, rows, skipped)
    faces = {(d, p): f for f, d, p in _faces(loop)}
    work = sorted(by_face.items(), key=lambda kv: -len(kv[1]))
    if not work:
        log("[map] no face's lines point at an unfilled row — nothing to map in parallel")
        return 0
    log(f"[map] {len(work)} face(s) to map, {workers} at a time; "
        f"{sum(len(v) for _k, v in work)} rows between them")
    t0, answered = time.monotonic(), 0

    import threading
    _lock = threading.Lock()

    def _one(key_rows):
        (doc, pg), rows_here = key_rows
        # THE SHARED STATE IS READ AND WRITTEN UNDER THE SAME LOCK (live
        # 2026-09-17: three faces a run were lost to "dictionary changed size
        # during iteration" — a worker was reading the run's record of what is
        # written and skipped while the main thread applied another face's
        # batch. A lock only one side takes is not a lock: the applying below
        # takes this one too.) The context is a snapshot; the writes stay on
        # one thread.
        with _lock:
            try:
                ctx = _face_context(loop, pre_wb, faces.get((doc, pg), "table"), doc, pg, rows_here,
                                    page_text, rows, dict(skipped))
            except Exception as e:  # noqa: BLE001 — said in the log and carried to the face's line
                return (doc, pg, None, 0.0, f"its context could not be built: {e!r}")
        t1 = time.monotonic()
        try:
            reply = ask_json(MANDATE, ctx)
        except Exception as e:  # noqa: BLE001
            return (doc, pg, None, time.monotonic() - t1, repr(e)[:120])
        return (doc, pg, reply, time.monotonic() - t1, None)
    with _cf.ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futures = [pool.submit(_one, w) for w in work
                   if time.monotonic() - t0 < deadline_s]
        for fut in futures:
            left = deadline_s - (time.monotonic() - t0)
            try:
                doc, pg, reply, took, err = fut.result(timeout=max(1.0, left))
            except Exception as e:  # noqa: BLE001
                log(f"[map] a face's call did not come back: {e!r}")
                continue
            if err or not isinstance(reply, dict):
                log(f"[map] face {doc} p{pg}: no answer ({err}) — its rows stay open ({took:.0f}s)")
                # NOTHING IS SWALLOWED: the brain sees the face that was lost and
                # why, and the rows of that face stay open for the loop
                loop.__dict__.setdefault("_map_refused", []).append(
                    f"{doc} p{pg}: this face was not read — {str(err)[:100]}")
                continue
            log("[map] face %s p%s reply %s" % (doc, pg, json.dumps(reply, ensure_ascii=False)))
            answered += 1
            for call in (reply.get("calls") or []):
                if not isinstance(call, dict):
                    continue
                with _lock:
                    # the face this reply was read against: a refusal here is a
                    # refusal of THIS print, and code knows which one it was
                    out = _one_call(loop, pre_wb, call, page_text, sources, skipped, log,
                                    deadline=t0 + deadline_s, face=(doc, pg))
                for ln in out:
                    log(f"[map]   {ln.strip()[:300]}")
            log(f"[map] face {doc} p{pg}: answered in {took:.0f}s")
    by_sheet, still = coverage(loop, rows, skipped)
    log(f"[map] the face round: {answered}/{len(work)} face(s) answered in "
        f"{(time.monotonic() - t0) / 60:.1f} min — "
        f"{sum(c.get('filled', 0) for c in by_sheet.values())} plain, "
        f"{sum(c.get('red', 0) for c in by_sheet.values())} red, {len(still)} rows still open")
    return answered


def run_mapping(loop, pre_wb, census, page_text, log, ask_json, deadline_s=900.0, brain=True):
    """THE MAPPING LOOP. Every turn: code lays out the printed faces beside the
    model's input rows with their leads, the brain calls tools, code verifies,
    writes and logs the turn verbatim. The clock is the only end; on the clock
    every unfilled row lands red 'not reached' — never a silent estimate.
    -> a one-line summary."""
    rows = input_rows(loop, census)
    loop.__dict__["_map_pages"] = page_text
    sources = {getattr(it, "doc", None) for it in _items(loop)} - {None}
    skipped = loop.__dict__.setdefault("_map_skipped", {})
    state, answers, dead, turn, stuck = {"history": []}, [], 0, 0, 0
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
                # ONLY THE CLOCK ENDS THE MAPPING (reviewer 2026-09-17: three
                # unreadable turns ended the whole stage and every row shipped
                # red). An unreadable turn is a turn: say what was wrong and ask
                # again until the budget is spent.
                log(f"[map] turn {turn}: the reply could not be read ({e!r}) — asked again "
                    f"({dead} unreadable in a row)")
                # an unreadable turn read nothing and changed nothing: it counts
                # towards the no-progress measure like any other empty turn, so a
                # brain that answers nothing at all cannot spend the whole budget
                stuck += 1
                if stuck >= _EMPTY_RUN:
                    log(f"[map] {stuck} turns running read nothing and changed nothing — the mapping ends; "
                        "the rows still open go red 'not reached'")
                    break
                continue
            dead = 0
            log("[map] turn %d reply %s" % (turn, json.dumps(reply, ensure_ascii=False)))
            calls = reply.get("calls") if isinstance(reply, dict) else None
            if not isinstance(calls, list) or not calls:
                answers = ["    your last reply carried no calls — answer with a JSON list of calls"]
                continue
            answers, finished = [], False
            # PROGRESS IS MEASURED FROM BEFORE THE CALLS RUN (2026-09-17: the
            # write count was read AFTER the turn's writes had landed, so it
            # always matched itself and no write ever counted as progress).
            # PROGRESS IS MEASURED FROM BEFORE THE CALLS RUN (2026-09-17: the
            # count was read AFTER the turn's writes had landed, so it always
            # matched itself and no write ever counted as progress).
            # WHAT IS SETTLED IS WHAT IS WRITTEN OR CLOSED. Refusing a page is
            # not progress (reviewer 2026-09-18: counting page skips armed
            # nothing — a brain refusing page after page could spend the whole
            # budget writing no cell, and `done` stays refused while rows are
            # open, so only this measure can end it).
            _before = len(_written(loop)) + len(skipped)
            _writes_before = int(loop.__dict__.get("_map_cells") or 0)
            for call in calls:
                if time.monotonic() - t0 > deadline_s:
                    answers.append("    the clock ended the mapping inside this turn; what was already "
                                   "verified and written stands")
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
                        for _sh_c in sorted(_by):
                            _c = _by[_sh_c]
                            answers.append(f"      {_sh_c}: unfilled {_c.get('unfilled', 0)} | filled "
                                           f"{_c.get('filled', 0)} | red {_c.get('red', 0)} | skipped "
                                           f"{_c.get('skipped', 0)}")
                        _cls_d = _classes(loop, rows)
                        for sh, co in sorted(still, key=lambda x: (_cls_d.get(x, "zzz") == "nothing measured",
                                                                   x[0], _row_of(x[1])))[:40]:
                            answers.append(f"      {sh}!{co} '{_label(loop.wb[sh], _row_of(co))[:30]}' "
                                           f"— feeds {_cls_d.get((sh, co), '')}")
                        log(f"[map] done refused: {len(still)} input row(s) still open")
                        continue
                    log("[map] done: every input row is filled or skipped with a reason")
                    finished = True
                    break
                try:
                    out = _one_call(loop, pre_wb, call, page_text, sources, skipped, log,
                                    deadline=t0 + deadline_s)
                except Exception as e:  # noqa: BLE001
                    out = [f"    that call failed: {type(e).__name__}: {str(e)[:120]}"]
                    log(f"[map] the call {json.dumps(call, ensure_ascii=False)[:120]} failed: {e!r}")
                answers += out
                state["history"].append(_record_line(turn, call, out))
                for ln in out:
                    log(f"[map]   {ln.strip()[:300]}")
            if finished:
                break
            # A TURN THAT CHANGES NOTHING, TWICE OVER, IS THE END (reviewer
            # 2026-09-17: a brain that kept answering `done` turned 19,434 times,
            # ate the whole budget and shipped every row red — and live, every
            # one of those turns is a call). Not a turn count: a measure of
            # whether the model moved.
            # READING IS WORK — ONCE (reviewer 2026-09-17: any read disarmed the
            # measure, so `show X` + `done` repeated turned 7,260 times in twenty
            # seconds; live that is 7,260 calls). Progress is a change to the
            # model, or a read the brain has NOT made before. The same reply
            # twice running is no progress whatever it contains.
            _seen = state.setdefault("seen_calls", set())
            _new_read = False
            for c in calls:
                if not isinstance(c, dict) or str(c.get("tool") or "").lower() not in (
                        "page", "find", "show", "anatomy"):
                    continue
                sig = json.dumps({k: v for k, v in sorted(c.items())}, ensure_ascii=False, sort_keys=True)[:300]
                if sig not in _seen:
                    _seen.add(sig)
                    _new_read = True
            _same = json.dumps(reply, ensure_ascii=False, sort_keys=True)[:2000]
            if _same == state.get("last_reply"):
                _new_read = False
            state["last_reply"] = _same
            # PROGRESS IS A WRITE, NOT A MENTION (owner 2026-09-17): a `set`
            # that lands nothing changes no cell, however many rows it names —
            # and a red flag is not a write either.
            _wrote = int(loop.__dict__.get("_map_cells") or 0) != _writes_before
            if not _wrote and len(_written(loop)) + len(skipped) == _before and not _new_read:
                stuck += 1
                answers.append("    that turn changed nothing in the model. Map a row, or `skip` it with "
                               "your reason — another turn that changes nothing ends the mapping and the "
                               "rows still open go red.")
                if stuck >= _EMPTY_RUN:
                    log(f"[map] {stuck} turns running read nothing and changed nothing — the mapping ends; "
                        "the rows still open go red 'not reached'")
                    break
            else:
                stuck = 0
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
        # a row read against a print and refused THERE says so — it was reached,
        # and the analyst is told which prints did not carry it
        refused = sorted(_page_skips(loop).get(f"{sheet}!{coord}") or ())
        loop.writer.flag_ref(
            f"{sheet}!{coord}", "red",
            ("NOT MAPPED: read against " + ", ".join(f"{d} p{p}" for d, p in refused)
             + " and not carried there; no other print was reached in time. It still holds last "
               "period's figure — please map it.") if refused else
            ("NOT REACHED: the mapping ran out of time before this input row was read "
             "against the disclosure. It still holds last period's figure — please map it."))
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
        # ONE NAME FOR A DOCUMENT, EVERYWHERE (reviewer 2026-09-17: the pages
        # were keyed by the PATH the run happened to hold — a string from the
        # disclosures walk — while the ledger, the faces and every quote use the
        # basename, so not one page of this period was ever found: 168 of 168
        # faces printed "no text on file" and the quoted-line proof was dead).
        import os
        from .stage1_read import page_texts
        name = os.path.basename(str(getattr(p, "name", None) or p))
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
        # THE SHELF IS REACHED FOR, NOT SWEPT (reviewer 2026-09-17): a lookup
        # that misses does not read last year's report — only `page` and `find`
        # do, when the brain asks.
        v = self._d.get(key)
        return default if v is None else v

    def items(self):
        return self._d.items()

    def docs(self):
        return {d for d, _p in self._d}

    def ensure_page(self, n, doc=None):
        if not any(str(pg) == str(n) and (doc is None or _d == doc) for _d, pg in self._d):
            self._ensure()

    def __bool__(self):
        return True


def page_text_of_docs(docs, later_docs=(), log=print):
    """{(doc, page): text} — this period's pages now, earlier ones on demand."""
    return Pages(docs, later_docs, log)
