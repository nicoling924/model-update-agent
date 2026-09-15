"""THE READER STAGE (owner 2026-09-09: "test Luna's ability to read like
Fable 5 so that we are sure whether to use cards") — Luna reads the whole
disclosure in one view and answers the model's rows; CODE verifies every
answer against a PRINTED number before anything is written.

What the reading test proved (RUNLOG 2026-09-09): on text pages Luna
reads like an analyst — revenue, profits, cash flows, a dividend in a
sentence, an order-intake figure, two blank-beside-prior zeros — with
page references, in one call. Its misses were model conventions (units,
sign, dividend paid vs declared, a group figure on a segment row) and,
on a scanned page it could not read exactly, a FABRICATED balance sheet
that balanced to the true total. Hence the split:

  Luna: which printed line answers this row, and why.
  Code: is that line really printed (ledger), does its comparative tie
        the model's prior at full precision, what is the value in the
        model's units from the PRINTED number, what sign does the model
        use, is this the one home for that figure.

Verified answers serve plain; a printed line with no tie serves RED with
its citation; an answer no printed number supports is never written.
Cards remain for genuine conflicts (two printed readings, a check that
will not close). No page rules: the whole current-vintage disclosure is
read; the verification is evidence, not location.
"""
import re
from pathlib import Path

from .checks import prior_column, year_columns
from .numerics import kinship

_SYSTEM = (
    "You are an equity research analyst updating a valuation model from a company's newly "
    "published financial disclosure. You are given the FULL disclosure text page by page (and "
    "images of scanned pages), and a list of model rows with the model's LAST-period value. For "
    "each row, find THIS period's value in the disclosure. Method, in order: (1) find the printed "
    "line whose last-period (comparative) figure equals the model's last-period value — that line "
    "is the item, whatever it is called; (2) confirm the label makes sense; (3) if the line prints "
    "last period's figure with this period's slot blank, dash or nil, the value is 0; (4) if a "
    "figure appears in several places they must agree — say so if they do not; (5) a row with no "
    "last-period value is identified by its label AND its scope: a group total belongs to the group "
    "row, a segment figure to the segment row — never both; (6) a figure the statement does not "
    "print as its own line (a total the model keeps but the page splits into components, or the "
    "reverse) is proved by ARITHMETIC: state in \"check\" an equation whose every other term is a "
    "line printed on that same page and which closes on a printed subtotal — e.g. '88,018 - 28,950 "
    "- 5,987 - 29,551 - 9,718 + 460 = 14,272' for the operating-profit block. Quote the printed line "
    "EXACTLY as it appears (label and the printed digits, in the document's own units) — the number "
    "you quote is checked against the page; a figure you cannot quote from a printed line and cannot "
    "prove with such a check is null with the reason 'not found'. Never guess. Answer ONLY with "
    "JSON: {\"rows\": [{\"row\": \"<id>\", "
    "\"printed\": <the printed number for THIS period, in the document's units, or null>, "
    "\"page\": <int or null>, \"line\": \"<printed line label>\", \"check\": \"<the closing "
    "equation, or null>\", \"reason\": \"<one sentence>\"}]}"
)

_MAX_CHARS = 1_600_000          # the model's context (1M tokens), less rows and images


def _doc_text(paths, max_chars=_MAX_CHARS):
    from .stage1_read import page_texts
    parts, images, n = [], [], 0
    for p in paths:
        for pn, text, cls in page_texts(str(p)):
            if cls == "image":
                images.append((p, pn))
                parts.append(f"\n=== {Path(p).name} page {pn} (SCANNED — see image) ===\n")
                continue
            t = (text or "").strip()
            if not t:
                continue
            block = f"\n=== {Path(p).name} page {pn} ===\n{t}\n"
            if n + len(block) > max_chars:
                parts.append(f"\n[truncated: {Path(p).name} from page {pn}]\n")
                break
            parts.append(block)
            n += len(block)
    return "".join(parts), images


def _images(images):
    out = []
    try:
        import pdfplumber
        from .stage1_read import _page_image, _encode
    except Exception:
        return out
    for p, pn in images:
        try:
            with pdfplumber.open(str(p)) as pdf:
                im = _page_image(pdf.pages[pn - 1])
            if im is not None:
                out.append(_encode(im, 1600))
        except Exception:
            continue
    return out


def rows_to_read(wb, spec, target_year, targets, served):
    """The rows the deterministic stages did not prove: every target row
    with a label whose serve is missing or unproven (conf < 4)."""
    out = []
    for (sheet, row), t in sorted(targets.items()):
        e = (served or {}).get((sheet, row))
        if isinstance(e, dict) and int(e.get("conf") or 0) >= 4:
            continue
        lab = str(getattr(t, "label", "") or "").strip()
        if not lab or re.search(r"差额|平衡|check|balance test", lab, re.IGNORECASE):
            continue
        tcol = year_columns(spec, sheet).get(str(target_year)) if sheet in wb.sheetnames else None
        if tcol:
            held = wb[sheet][f"{tcol}{row}"].value
            if isinstance(held, str) and held.startswith("="):
                continue             # a formula row (a link, a subtotal) is never an input
        pv = getattr(t, "prior_value", None)
        if tcol and never_filled(wb, sheet, row, tcol):
            # THE NEVER-FILLED ROW (CLP run 262: 'Dividend', 'Scheme of control
            # items', the CFI block header and FCFF carry no figure in ANY year
            # of the model; the reader put printed totals there and every sum
            # above them moved). A row the analyst never filled is not an
            # input — the model's own history says what the analyst tracks.
            continue
        p2 = getattr(t, "prior2_value", None)
        # THE ROW'S PLACE IN THE MODEL (owner 2026-09-15: the chat reads the
        # model AND the report; the agent's brain must see the same) — the
        # sheet and the section headers above the row travel with it
        from .naming import block_context as _bc
        ctx = " > ".join(_bc(wb, sheet, int(row)))
        out.append({"row": f"{sheet}!{row}", "sheet": sheet, "r": row, "label": lab, "context": ctx,
                    "prior": (round(float(pv), 4) if isinstance(pv, (int, float)) else None),
                    "prior2": (round(float(p2), 4) if isinstance(p2, (int, float)) else None)})
    return out


def never_filled(wb, sheet, row, tcol):
    """True when no cell of the row left of the target column ever held a
    number (or a formula): the analyst never tracked this line. (The
    writer's own law, row_never_filled, refuses the whole-row case from
    every step — owner 2026-09-14; this reader-side rule also keeps the
    reader off rows that hold only typed zeros in the past.)"""
    from openpyxl.utils import column_index_from_string as _ci
    ws = wb[sheet]
    for c in range(2, _ci(tcol)):
        v = ws.cell(row, c).value
        if (isinstance(v, (int, float)) and v != 0) or (isinstance(v, str) and v.startswith("=")):
            return False
    return True


def _near(a, b):
    return abs(abs(a) - abs(b)) <= max(0.02, abs(b) * 1e-4)


def _sig_digits(v):
    return len(re.sub(r"[^0-9]", "", "%.2f" % abs(float(v))).strip("0"))


_UNIT_WORDS = (1e8, 1e4, 1e6, 1e3, 1e2)      # 亿 / 万 / million / thousand / 百 — a sentence quotes '1,172.51亿元'


def _printed_match(items, page, printed, line, sources):
    """The ledger item on `page` of a current-vintage document that carries
    the quoted number — the proof the number is printed. Label kinship
    breaks ties between lines that print the same figure."""
    if not isinstance(printed, (int, float)):
        return None
    hits = []
    for it in items:
        if it.doc not in sources:
            continue
        nums = [n for n in (it.nums or []) if isinstance(n, (int, float))]
        # a sentence is harvested in base units while the brain quotes the
        # printed digits with their unit word ('1,172.51亿元'): both readings
        # of the same figure
        prose = getattr(it, "channel", "") == "prose"
        if not any(_near(n, printed) or (prose and any(_near(n, printed * u) for u in _UNIT_WORDS))
                   for n in nums):
            continue
        kin = bool(line and kinship(str(it.label or ""), str(line)))
        hits.append((it.page == page, kin, it))
    if not hits:
        return None
    # the cited page first; then the same number under the same name on
    # ANY page (the brain's page numbers slip — the reading test cited p5
    # for a figure printed on p2 and p44); a bare number elsewhere counts
    # only when it is printed once in the whole disclosure
    on_page = [h for h in hits if h[0]]
    if on_page:
        return max(on_page, key=lambda h: h[1])[2]
    kin_any = [h for h in hits if h[1]]
    if kin_any:
        return kin_any[0][2]
    return hits[0][2] if len(hits) == 1 else None


_TERM_RE = re.compile(r"[+\-−–—]|\(?\d[\d,]*(?:\.\d+)?\)?")


def _check_terms(text):
    """The terms of a stated arithmetic check and the figure it closes on:
    '88,018 − 28,950 − 5,987 − 29,551 − 9,718 + 460 = 14,272 = Operating
    profit' -> ([88018, -28950, -5987, -29551, -9718, 460], 14272).
    None when the text states no closing arithmetic."""
    from .numerics import parse_number
    s = str(text or "")
    if "=" not in s:
        return None
    left, right = s.split("=", 1)
    m = re.search(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", right)
    if not m:
        return None
    closes = parse_number(m.group(0))
    terms, sign = [], 1.0
    for tok in _TERM_RE.finditer(left):
        t = tok.group(0)
        if t in "+-−–—":
            sign = -1.0 if t != "+" else 1.0
            continue
        v = parse_number(t)
        if v is None:
            return None
        terms.append(sign * v)
        sign = 1.0
    if closes is None or len(terms) < 2:
        return None
    return terms, closes


def _note_column(items):
    """Which rows of a table block print a NOTE REFERENCE before their
    figures. A note is a COLUMN of the block — the statement's own note
    numbering, small positive integers that ASCEND down the table, blank on
    the rows that carry none — never a row's own first number (reviewer
    2026-09-16: 'Other gains 46 512' was read as this period 512 because 46
    looked like a note, which both invented a column mix and cost the row its
    comparative). The ledger's column names say the same thing where the
    extractor kept them. A leading integer that does not fit the block's
    ascent is a figure. -> {id(item)}"""
    seq = []
    for it in items:
        nums = [n for n in (it.nums or []) if isinstance(n, (int, float))]
        if len(nums) >= 2 and float(nums[0]).is_integer() and 0 < nums[0] < 100:
            seq.append((it, float(nums[0])))
    if len(seq) < 2:
        return set()
    named = [str(c).strip().lower() for c in (getattr(seq[0][0], "columns", None) or [])]
    chains = []
    for it, v in seq:
        best = max([c for c in chains if c[-1][1] < v], key=len, default=[])
        chains.append(best + [(it, v)])
    run = max(chains, key=len, default=[])
    if len(run) < 2 and not any(n.startswith("note") for n in named):
        return set()
    return {id(it) for it, _v in run}


def _row_figures(item, notes=()):
    """A printed row read as the statement prints it: (this period's figure,
    its comparative). The figure is the row's leftmost printed number, after
    the block's note column where the row carries one; the comparative is the
    number printed after it, or None where the row prints none — so a row of
    exactly two figures in a two-period block is (this period, comparative).
    -> (value, comparative) or None."""
    nums = [n for n in (item.nums or []) if isinstance(n, (int, float))]
    if not nums:
        return None
    i = 1 if (id(item) in notes and len(nums) > 1) else 0
    return nums[i], (nums[i + 1] if i + 1 < len(nums) else None)


def _exact(x, y):
    """The same printed number, SIGN INCLUDED, at the model's own precision.
    (A printed '(28,950)' is -28,950: a term whose sign contradicts the print
    is not that line, and an abs() match let an arbitrary residual close any
    check — reviewer 2026-09-16.)"""
    from .writegate import _ties_full_precision
    if not (isinstance(x, (int, float)) and isinstance(y, (int, float))):
        return False
    return (x < 0) == (y < 0) and _ties_full_precision(x, y)


def _reconciliation(check, printed, items, page, sources):
    """THE RECONCILIATION IS THE PROOF (run 34993405014: the table extractor
    dropped the operating-expenses total, so the reader's correct -74,206 —
    the four expense lines the page prints between revenue and the printed
    Operating profit — carried no ledger line and was refused).

    A stated check is evidence for `printed` only when it is the STATEMENT'S
    OWN arithmetic: every term and the subtotal it closes on is the
    this-period figure of a printed row, each row used once, all of them in
    the SAME table block of that page, each with the printed sign; the check
    closes at the model's precision; and the answered figure is the check's
    own statement about the row — one term, or a consecutive block of
    like-signed terms it totals. The answered figure's comparative is then
    the same rows' comparatives, read from the print (never from the
    answer's text), so the plain/red decision rests on the page too.
    -> {"check", "doc", "closer", "prior"} or None."""
    parsed = _check_terms(check)
    if not parsed or not isinstance(printed, (int, float)):
        return None
    terms, closes = parsed
    from .writegate import _ties_full_precision
    if not _ties_full_precision(sum(terms), closes) or (sum(terms) < 0) != (closes < 0):
        return None
    blocks = {}
    for it in items:
        if it.page == page and it.doc in sources:
            blocks.setdefault((it.doc, it.table_id), []).append(it)
    rows = []
    for block in blocks.values():
        notes = _note_column(block)          # the note column is the block's, not a row's
        for it in block:
            fig = _row_figures(it, notes)
            if fig is not None:
                rows.append((it, fig[0], fig[1]))

    def _row_of(v, used):
        return next(((it, cur, comp) for it, cur, comp in rows
                     if _exact(cur, v) and (it.doc, it.page, it.table_id, str(it.label)) not in used), None)
    used, matched = set(), []
    for t in terms + [closes]:
        hit = _row_of(t, used)
        if hit is None:
            return None                      # a term no printed row of this page carries, as printed
        used.add((hit[0].doc, hit[0].page, hit[0].table_id, str(hit[0].label)))
        matched.append(hit)
    closer = matched[-1][0]
    blocks = {(it.doc, it.table_id) for it, _c, _p in matched}
    if len(blocks) != 1:
        return None                          # terms taken from different tables prove nothing about one line
    span = None
    for i in range(len(terms)):
        acc = 0.0
        for j in range(i, len(terms)):
            if j > i and (terms[j] < 0) != (terms[i] < 0):
                break                        # a block of unlike signs is no one row's total
            acc += terms[j]
            if _exact(acc, printed):
                span = (i, j)
                break
        if span:
            break
    if span is None:
        return None
    comps = [matched[k][2] for k in range(span[0], span[1] + 1)]
    prior = sum(comps) if all(isinstance(c, (int, float)) for c in comps) else None

    def _t(v):
        return f"{v:,.2f}".rstrip("0").rstrip(".") if v % 1 else f"{v:,.0f}"
    txt = _t(terms[0]) + "".join(f" {'-' if t < 0 else '+'} {_t(abs(t))}" for t in terms[1:])
    return {"check": f"{txt} = {_t(closes)} ('{str(closer.label)[:30]}')",
            "doc": closer.doc, "closer": closer, "prior": prior}


def _reconciled_verdict(rec, printed, pv, page, page_scales, dom, log, rid):
    """The verdict on a figure proved by its reconciliation: the value at the
    scale its own comparative proves, the model's sign, PLAIN when the same
    rows' printed comparatives tie the model's prior at the model's
    precision and RED when they do not — or when the page's ratified scale
    and the scale of that tie disagree. The reconciliation is the note."""
    from .writegate import _SCALES, _ties_full_precision
    f_page = page_scales.get((rec["doc"], page)) or dom.get(rec["doc"])
    comp = rec.get("prior")
    f_tie = None
    if isinstance(comp, (int, float)) and isinstance(pv, (int, float)) and abs(pv) >= 0.5:
        f_tie = next((f for f in ([f_page] if f_page else []) + list(_SCALES)
                      if _ties_full_precision(comp / f, pv)), None)
    f_use = f_tie or f_page
    if not f_use:
        if log:
            log(f"[read]   unverified {rid}: the check closes but p{page} has no ratified scale — not written")
        return None
    scale_clash = bool(f_tie and f_page and f_tie != f_page)
    value = float(printed) / float(f_use)
    if f_tie and isinstance(pv, (int, float)) and pv != 0 and comp != 0 and (comp < 0) != (pv < 0):
        value = -value                       # the line negates the model's convention
    elif not f_tie and isinstance(pv, (int, float)) and pv != 0 and value != 0 and (pv < 0) != (value < 0):
        value = -value                       # no tie: the model owns the sign convention
    plain = bool(f_tie) and not scale_clash
    why = ("the printed comparatives of the same rows tie the prior" if plain
           else "the comparative ties at a scale the page does not carry" if scale_clash
           else "no printed comparative ties the prior")
    note = (f"Not printed as its own line; proved by the page's own arithmetic (p{page}): "
            f"{rec['check']}." + ("" if plain else f" The {why} — please confirm."))
    return {"value": value, "conf": 4 if plain else 3, "flag": None if plain else "red", "note": note,
            "doc": rec["doc"], "page": page, "line": str(rec["closer"].label)[:60],
            "why": f"read: the stated check closes the printed subtotal — {rec['check']}; {why}"}


def _nil_line(items, page, pv, sources):
    """A line on `page` printing ONE number equal to the model's prior:
    last year's figure beside a blank — this year is 0."""
    from .writegate import _SCALES, _ties_full_precision
    if not (isinstance(pv, (int, float)) and abs(pv) >= 0.5):
        return None
    for it in items:
        if it.page != page or it.doc not in sources:
            continue
        nums = [n for n in (it.nums or []) if isinstance(n, (int, float))]
        if len(nums) == 1 and any(_ties_full_precision(nums[0] / f, pv) for f in _SCALES):
            return it
    return None


def verify(answers, rows, ledger, page_scales, log=None, priors=None):
    """-> {row_id: verdict}; verdict = {"value", "conf", "flag", "note",
    "doc", "page", "line", "why"}. Nothing here trusts the brain's number:
    the value is recomputed from the printed digits at the page's ratified
    scale; the tie is checked on the printed line; the model's sign wins.
    `priors`: every model prior (all target rows), so a lone printed number
    equal to any of them is known for what it is — last year's."""
    from .writegate import _SCALES, _ties_full_precision
    by_row = {r["row"]: r for r in rows}
    all_priors = [abs(float(p)) for p in (priors if priors is not None else [r["prior"] for r in rows])
                  if isinstance(p, (int, float)) and abs(p) >= 0.5]
    sources = {it.doc for it in ledger.items} - set(ledger.noncurrent_docs())  # evidence: a prior-vintage document is never a SOURCE of this year's number; it stays readable for ties
    # a document's DOMINANT scale (the one most of its ratified pages carry)
    # answers for pages the anchors never ratified — a sentence page, a
    # note; prose figures are harvested in base units, so they take it too
    dom = {}
    for (d_, _p), sc in (page_scales or {}).items():
        dom.setdefault(d_, []).append(sc)
    dom = {d_: max(set(v), key=v.count) for d_, v in dom.items()}
    out, homes = {}, {}
    for a in answers:
        rid = str(a.get("row"))
        r = by_row.get(rid)
        page = a.get("page")
        if r is None or not isinstance(page, int):
            continue
        printed, line, pv = a.get("printed"), str(a.get("line") or ""), r["prior"]
        item = _printed_match(ledger.items, page, printed, line, sources)
        from .writegate import row_is_constant as _const
        constant = _const(pv, r.get("prior2"))
        if item is None:
            nil = _nil_line(ledger.items, page, pv, sources) if printed in (None, 0, 0.0) and not constant else None
            if nil is not None:
                out[rid] = {"value": 0.0, "conf": 4, "flag": None, "note": None, "doc": nil.doc,
                            "page": page, "line": str(nil.label)[:60],
                            "why": "read: last year's figure printed beside a blank — 0"}
                continue
            rec = _reconciliation(a.get("check") or a.get("reason"), printed, ledger.items, page, sources)
            if rec is not None:
                v = _reconciled_verdict(rec, printed, pv, page, page_scales, dom, log, rid)
                if v is not None:
                    key = (rec["doc"], page, rec["check"], round(abs(v["value"]), 2))
                    other = homes.get(key)
                    if other is not None and other != rid and not (
                            isinstance(pv, (int, float)) and by_row[other]["prior"] == pv):
                        # ONE HOME (the reader's own law): the same reconciliation
                        # cannot answer two different rows — neither is written
                        out.pop(other, None)
                        if log:
                            log(f"[read]   {rid} and {other} both claim the same reconciliation — neither written")
                        continue
                    homes[key] = rid
                    out[rid] = v
                    continue
            if log:
                log(f"[read]   unverified {rid}: no printed line on p{page} carries {printed!r} "
                    "and no stated check closes a printed subtotal from that page's lines — not written")
            continue
        nums = [n for n in (item.nums or []) if isinstance(n, (int, float))]
        idx = next((i for i, n in enumerate(nums) if _near(n, printed)), 0)
        raw = nums[idx]
        scale = page_scales.get((item.doc, item.page))
        tied = None
        specific = _sig_digits(raw) >= 4          # a parameter (15, 1) is never evidence of a nil
        if isinstance(pv, (int, float)) and abs(pv) >= 0.5:
            # the page's ratified scale first, then every legal scale: the
            # comparative tying the prior IS the line's scale (DFE p209:
            # '利息收入 108,208,159.60 132,705,664.58' on a page ratified at
            # 10^4 — the tie at 10^6 was never tried and 10,820.82 was
            # written for 108.21)
            from .writegate import is_sum_row as _is_sum_row
            for j in range(idx + 1, len(nums)):
                if _is_sum_row(nums, j):
                    continue          # the row's own total, not a comparative
                for f in ([scale] if scale else []) + [s_ for s_ in _SCALES if s_ != scale]:
                    if f and _ties_full_precision(nums[j] / f, pv):
                        tied = f
                        break
                if tied:
                    break
            if tied is None and len(nums) == 1 and any(_ties_full_precision(raw / f, pv) for f in _SCALES):
                if constant:
                    # the row's own history says this figure does not move: the
                    # lone number IS this year's value (a capacity, a rate)
                    out[rid] = {"value": float(pv), "conf": 4, "flag": None, "note": None, "doc": item.doc,
                                "page": page, "line": str(item.label)[:60],
                                "why": "read: a constant row — the printed figure is the parameter again"}
                    continue
                if specific:
                    out[rid] = {"value": 0.0, "conf": 4, "flag": None, "note": None, "doc": item.doc,
                                "page": page, "line": str(item.label)[:60],
                                "why": "read: the quoted number is last year's, printed alone — 0"}
                elif log:
                    # a parameter (15, 1) printed alone and equal to the prior says
                    # nothing new — neither a nil nor this year's figure
                    log(f"[read]   unverified {rid}: a lone parameter equal to the prior — no new evidence")
                continue
        if len(nums) == 1 and specific and any(
                _ties_full_precision(raw / f, p_) for f in _SCALES for p_ in all_priors):
            # run 260: the brain quoted the bond figure 593.54 — another row's
            # prior, printed alone — as 'other financing receipts'; a lone
            # number equal to ANY model prior is a comparative, never this year
            if log:
                log(f"[read]   {rid}: the quoted number is a model prior printed alone (last year's) — not written")
            continue
        if isinstance(pv, (int, float)) and abs(pv) >= 0.5 and tied is None and not any(
                abs(raw / f) <= 30 * abs(pv) and abs(raw / f) * 30 >= abs(pv) for f in _SCALES):
            # run 260: 10,820.82 read as interest income (prior 132.71) — a
            # no-tie read must live in the row's own world
            if log:
                log(f"[read]   unverified {rid}: {raw:,.2f} is out of the row's world (prior {pv:,.2f}) — not written")
            continue
        # (a digit-count rule was tried here on 2026-09-10 and withdrawn the
        # same morning: '收到其他与投资活动有关的现金 1,000,000.00' is a genuine
        # round figure — RMB 1m — and '专项应付款 240,000.00' another; the
        # 4,117 plug that prompted it came from the ladder's choice of site
        # on an off check, not from this read)
        f_use = tied or scale or dom.get(item.doc)       # a sentence page, a note: the document's own scale
        if not f_use and isinstance(pv, (int, float)) and abs(pv) >= 0.5:
            f_use = next((f for f in _SCALES if abs(raw / f) <= 30 * abs(pv) and abs(raw / f) * 30 >= abs(pv)), None)
        if not f_use:
            if log:
                log(f"[read]   unverified {rid}: no ratified scale for p{page} — not written")
            continue
        value = float(raw) / float(f_use)
        if tied and isinstance(pv, (int, float)) and pv != 0:
            # THE SIGN OF THE TIE (CLP fuel clause: the line prints
            # 1,043 | (370) where the model holds +370 — the line negates
            # the model's convention, so this year's balance is −1,043;
            # forcing the prior's sign would hide a balance that changed
            # side)
            comp = next((nums[j] for j in range(idx + 1, len(nums))
                         if _ties_full_precision(nums[j] / tied, pv)), None)
            if comp is not None and comp != 0 and (comp < 0) != (pv < 0):
                value = -value
        elif isinstance(pv, (int, float)) and pv != 0 and value != 0 and (pv < 0) != (value < 0):
            printed_value = value
            value = -value                                   # no tie: the model owns the sign convention
        key = (item.doc, item.page, str(item.label)[:40], round(abs(value), 2))
        if key in homes and homes[key] != rid \
                and not (isinstance(pv, (int, float)) and by_row[homes[key]]["prior"] == pv):
            # (two rows holding the SAME prior are the model's own duplicate
            # of one item — both take the figure; only differing rows compete)
            other = homes[key]
            mine = kinship(str(item.label or ""), r["label"])
            theirs = kinship(str(item.label or ""), by_row[other]["label"])
            if mine == theirs:
                # neither or both names match (a cross-script sentence, say):
                # the row WITHOUT qualifiers is the broader item — 'New orders'
                # takes the group figure, 'New orders - clean energy equipment'
                # does not (its qualifier is not in the line)
                def _toks(s):
                    return set(re.findall(r"[A-Za-z]+|[一-鿿]{2,}", str(s).lower()))
                a, b = _toks(r["label"]), _toks(by_row[other]["label"])
                if a < b:
                    mine, theirs = True, False
                elif b < a:
                    mine, theirs = False, True
            if theirs and not mine:
                if log:
                    log(f"[read]   {rid}: '{str(item.label)[:30]}' already home at {other} — skipped")
                continue
            out.pop(other, None)
            if not (mine and not theirs):
                if log:
                    log(f"[read]   {rid} and {other} both claim '{str(item.label)[:30]}' — neither written")
                continue
        homes[key] = rid
        if tied:
            out[rid] = {"value": value, "conf": 4, "flag": None, "note": None, "doc": item.doc,
                        "page": page, "line": str(item.label)[:60],
                        "why": f"read: printed p{page} '{str(item.label)[:30]}', comparative ties the prior"}
        else:
            _cjk_l = bool(re.search(r"[\u4e00-\u9fff]", str(item.label or "")))
            _cjk_r = bool(re.search(r"[\u4e00-\u9fff]", str(r["label"])))
            if _cjk_l == _cjk_r and not kinship(str(item.label or ""), r["label"]):
                # a read with no prior tie has one piece of evidence left —
                # the line's name; a line named unlike the row (in the same
                # script — across scripts the name is the brain's judgment)
                # is a guess (run 262: 'Fourth interim dividend' -> 'Special
                # dividend' zeroed the final DPS)
                if log:
                    log(f"[read]   {rid}: no prior tie and '{str(item.label)[:30]}' is not named "
                        f"like '{r['label'][:30]}' — a suggestion; the card puts it to the brain")
                # the suggestion is kept for the row's card (audit 2026-09-15: 'Other gain 460'
                # and 'net exchange difference −352' were the analyst's own answers and never
                # reached the brain) — the name is the brain's judgment, not code's
                # the READING travels whole: the value, the line it was quoted from
                # and the check the reader stated for it — the card shows all three
                ledger.__dict__.setdefault("reader_suggestions", {})[rid] = {
                    "value": value, "printed": locals().get("printed_value", value), "doc": item.doc,
                    "page": page, "line": str(item.label)[:60],
                    "check": str(a.get("check") or "")[:160],
                    "reason": str(a.get("reason") or "")[:160]}
                continue
            out[rid] = {"value": value, "conf": 3, "flag": "red",
                        "note": (f"Read from the disclosure (p{page} '{str(item.label)[:30]}'); the printed "
                                 "line does not carry last year's figure. Please confirm."),
                        "doc": item.doc, "page": page, "line": str(item.label)[:60],
                        "why": f"read: printed p{page}, no prior tie"}
    return out


def brain_read(client, company_dir, period, target_year, wb, spec, targets, ledger,
               served, writer, log, rows=None, chunk=None):
    """The stage. -> number of rows written. One call carries the whole
    disclosure and every row (CLP run 262: four 90-row chunks re-sent
    three documents four times — 37 of the run's 60 minutes)."""
    if client is None:
        return 0
    rows = rows if rows is not None else rows_to_read(wb, spec, target_year, targets, served)
    if not rows:
        return 0
    sources = {it.doc for it in ledger.items} - set(ledger.noncurrent_docs())  # evidence: the brain reads this period's documents; last year's is never a SOURCE of this year's number
    docs = [p for p in sorted((Path(company_dir) / "disclosures" / str(period)).glob("*.pdf"))
            if p.name in sources]
    if not docs:
        return 0
    text, image_pages = _doc_text(docs)
    imgs = _images(image_pages)
    from .stage2_join import ratify_page_scales
    priors = [t.prior_value for t in targets.values()
              if isinstance(getattr(t, "prior_value", None), (int, float))]
    page_scales = ratify_page_scales([it for it in ledger.items if it.joinable()], priors, [])
    units = str(spec.get("units") or "the model's units")

    def _val(o):
        return [] if isinstance(o, dict) and isinstance(o.get("rows"), list) else ["rows list required"]
    answers = []
    import time as _time
    _t0 = _time.monotonic()
    chunk = chunk or max(1, len(rows))
    for i in range(0, len(rows), chunk):
        part = rows[i:i + chunk]
        user = (f"MODEL UNITS: {units}\n\nMODEL ROWS (id | sheet > section headers > label | last-period value):\n"
                + "\n".join(f"{r['row']} | {r['sheet']}" + (f" > {r['context']}" if r.get('context') else "") + f" > {r['label']} | {r['prior']}" for r in part)
                + "\n\nDISCLOSURE (full text, page-marked; scanned pages attached as images in order):\n"
                + text)
        try:
            obj = client.json(_SYSTEM, user, _val, repair_retries=1, images=imgs or None)
        except Exception as e:
            log(f"[read] call failed: {e}")
            continue
        answers += [a for a in (obj.get("rows") or []) if isinstance(a, dict)]
    log(f"[read] the brain read {len(docs)} document(s) for {len(rows)} rows: {len(answers)} answers "
        f"({_time.monotonic() - _t0:,.0f}s)")
    verdicts = verify(answers, rows, ledger, page_scales, log, priors=priors)
    # the reading is evidence for the replay and the morning grade
    try:
        import json as _json
        rp = Path(company_dir) / "replay" / str(period)
        rp.mkdir(parents=True, exist_ok=True)
        (rp / "reader.json").write_text(_json.dumps(
            {"rows": rows, "answers": answers,
             "verdicts": {k: v for k, v in verdicts.items() if v}}, ensure_ascii=False, indent=1))
    except Exception:
        pass
    n = 0
    for r in rows:
        v = verdicts.get(r["row"])
        if not v:
            continue
        sheet, row = r["sheet"], r["r"]
        tcol = year_columns(spec, sheet).get(str(target_year))
        pcol = prior_column(spec, sheet, target_year)
        if not tcol:
            continue
        held = wb[sheet][f"{tcol}{row}"].value
        if isinstance(held, str) and held.startswith("="):
            continue                     # a formula row is never an input
        ok = writer.write(sheet, f"{tcol}{row}", float(v["value"]),
                          prior_coord=f"{pcol}{row}" if pcol else None,
                          flag=v.get("flag"), note=v.get("note"),
                          allow_empty=(r["prior"] is None), trusted=(v["conf"] >= 4))
        if ok:
            served[(sheet, row)] = {"value": float(v["value"]), "status": "OK", "doc": v["doc"],
                                    "page": v["page"], "line": v["line"], "conf": v["conf"],
                                    "note": v["why"]}
            n += 1
            log(f"[read]   {r['row']} = {v['value']:,.2f} ({v['why']})" + ("" if v["conf"] >= 4 else " — RED"))
    log(f"[read] reader stage: {n} rows written "
        f"({sum(1 for v in verdicts.values() if v and v['conf'] >= 4)} proven, "
        f"{sum(1 for v in verdicts.values() if v and v['conf'] < 4)} red)")
    return n
