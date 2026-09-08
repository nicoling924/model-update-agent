"""Stage 3 — READ GAPS: the checksummed reader, serving only what Stage 2 left.

The clean-room lesson: the plateau was never the brain, it was the working
conditions. This stage gives the engine what the 96% run had — whole pages
(images for scans via the CCITT mask, renders for text pages, plus the
ledger's own table text), the model's rows IN ORDER with their priors, one
large call per statement region — and accepts NOTHING on trust:

PER-ROW CHECKSUM (measured zero wrong reads, every run): an answered row
must return the COMPARATIVE (prior-year) figure as printed on the same
line. Code accepts the row only when that comparative ties the model's own
prior at some legal scale; the same tie then converts the current figure.
The tie is SIGNED: comparative ~ +prior means the page prints the model's
sign convention (serve as printed — rows may legitimately flip sign year
to year: OCI, FX, working-capital moves); comparative ~ -prior means the
page prints the opposite convention (serve flipped). Never force last
year's sign onto this year's figure.

NO-PRIOR ROWS (the run-116 surface): no comparative exists to tie, so the
row is served ONLY when its page's block scale was independently ratified
by Stage 2's law (>= 2 sibling prior ties) — the read borrows the block's
proven anchor, never its own magnitude. Served at conf 3, red-flagged for
review. No anchor -> the row stays empty and flagged; empty is legal.

Checksummed rows are conf 5 — the runner may lock them against later,
lower-confidence writers. Generic by construction: pages are pages and
priors are priors in any language, model, or industry.
"""
import base64
import io
from collections import Counter, defaultdict

from .numerics import SCALES, parse_number, row_tol, to_model_units
from .stage2_join import ratify_page_scales
from .ledger import vintage_ban as _vintage_ban

MAX_ROWS_PER_CALL = 70
MAX_IMAGES_PER_CALL = 5
MAX_TABLE_TEXT = 8000
REGION_GAP = 4          # untagged continuation pages ride along (liabilities
                        # pages carry no caption; splitting regions at them
                        # once cost ~60 served rows)
CONF_CHECKSUMMED = 5
CONF_NO_PRIOR = 3

_SYSTEM = ("You are an equity research analyst marking a valuation model to "
           "actual results. You read financial statement pages exactly as "
           "printed and copy digits precisely. You never invent, round, or "
           "compute a number that is not visible.")

_CONTRACT = """Below: (1) page images and/or table text from the company's new financial disclosure, (2) rows from the analyst's model, IN ORDER, each with its PRIOR-year value in the model's units (no prior shown = a new line this year).

For each row, find the SAME line in the pages and return BOTH columns:

{"rows":[{"id":"<sheet>!<row>","current":"<new-period figure exactly as printed>","comparative":"<prior-period figure exactly as printed on the same line, or null if the line has none>","status":"OK"}, ...]}

- status "OK" only when you located the row's line and read it.
- status "NOT_HERE" when these pages do not contain that row's figure. Never guess.
- Copy digits EXACTLY as printed (separators, signs, brackets). The page's units may differ from the model's — return what is PRINTED; we convert.
- The rows are in the model's order, which usually mirrors the statement's print order — use that structure.
- The model's labels may be in a different language than the filing — translate the MEANING, and match by position and by the prior value when unsure.
- Scope discipline: consolidated / group figures, never parent-company-only (母公司) pages, never one segment for a group row.

Answer with the JSON only."""


# ---------------------------------------------------------------------------
# pure logic (museum-testable)
# ---------------------------------------------------------------------------

def checksum_accept(current_txt, comparative_txt, prior_value):
    """The row-level checksum. -> (value_in_model_units, scale) or None.

    Signed: the comparative must tie +prior (serve as printed) or -prior
    (opposite sign convention — serve flipped) at ONE legal scale; that
    scale converts the current figure. Tolerance is the row's own world.
    """
    cur = parse_number(current_txt)
    comp = parse_number(comparative_txt)
    pv = prior_value
    if cur is None or comp is None or not isinstance(pv, (int, float)):
        return None
    tol = max(abs(pv) * 5e-3, 0.6 if abs(pv) >= 10 else 0.01)
    for s in SCALES:
        if abs(comp / s - pv) <= tol:
            return cur / s, s
        if abs(comp / s + pv) <= tol:
            return -cur / s, s
    return None


def no_prior_value(current_txt, anchor_scales):
    """The run-116 law as one function: a no-prior figure is served ONLY
    with exactly one distinct block scale ratified by sibling prior ties —
    then converted at THAT scale. Anything else (no anchor, conflicting
    anchors, unparseable figure) -> None: the row stays a loud hole."""
    cur = parse_number(current_txt)
    anchors = set(anchor_scales or ())
    if cur is None or len(anchors) != 1:
        return None
    return to_model_units(cur, anchors.pop())


def regions_from_ledger(ledger, doc):
    """Contiguous page groups worth a whole-page read for one document:
    statement-face pages plus segment-ish pages, gaps <= REGION_GAP filled
    so caption-less continuation pages ride along."""
    tagged = sorted(pn for (d, pn) in ledger.faces if d == doc)
    groups = []
    for pn in tagged:
        if groups and pn - groups[-1][-1] <= REGION_GAP:
            groups[-1].extend(range(groups[-1][-1] + 1, pn + 1))
        else:
            groups.append([pn])
    # parent pages never enter a region's image/text set
    parents = {pn for (d, pn) in ledger.parent_pages if d == doc}
    return [[pn for pn in g if pn not in parents] for g in groups if g]


def row_homes(ledger, targets):
    """{(sheet,row): set of (doc,page)} — pages where any ledger item ties
    the row's prior at any legal scale. Number-anchored and language-blind:
    this is how a row finds its statement without reading a single label.
    Bisect over sorted priors — the naive cross-product hangs on big models."""
    import bisect
    by_abs = defaultdict(list)          # abs(prior) -> target keys
    for t in targets:
        pv = t.prior_value
        if isinstance(pv, (int, float)) and pv != 0:
            by_abs[abs(pv)].append(t.key)
    sorted_abs = sorted(by_abs)
    homes = defaultdict(set)
    if not sorted_abs:
        return homes
    prior_docs = _vintage_ban(ledger)
    for it in ledger.items:
        if it.disputed or it.doc in prior_docs:
            continue
        page = (it.doc, it.page)
        for n in it.nums:
            for s in SCALES:
                a = abs(to_model_units(n, s))
                i = bisect.bisect_left(sorted_abs, a * 0.99 - 1.0)
                while i < len(sorted_abs) and sorted_abs[i] <= a * 1.01 + 1.0:
                    pv = sorted_abs[i]
                    tol = row_tol(pv, base=0.6 if pv >= 100 else 0.01)
                    if abs(a - pv) <= tol:
                        for key in by_abs[pv]:
                            homes[key].add(page)
                    i += 1
    return homes


# ---------------------------------------------------------------------------
# the reads
# ---------------------------------------------------------------------------

def _page_png(pdf, pn, cache):
    """Page image: scans via the embedded mask, text pages via pdfplumber's
    renderer. None (and no image) is survivable — the ledger text still
    rides in the prompt."""
    if pn in cache:
        return cache[pn]
    out = None
    try:
        pg = pdf.pages[pn - 1]
        txt = (pg.extract_text() or "").strip()
        if len(txt) < 200:
            from .stage1_read import _encode, _page_image
            img = _page_image(pg)
            if img is not None:
                out = _encode(img, 2200)
        if out is None:
            im = pg.to_image(resolution=150)
            buf = io.BytesIO()
            im.original.convert("RGB").save(buf, "PNG")
            out = ("image/png", base64.b64encode(buf.getvalue()).decode())
    except Exception:
        out = None
    cache[pn] = out
    return out


def rows_for_region(unserved, homes, doc, grp, out):
    """A row is read where its evidence is: the region whose pages print
    its prior (the checksum's comparative). A row whose prior prints on no
    page has no checksum anywhere — it belongs to the whole-document
    reader, which already saw every page in one call. (CLP 2026-09-08:
    'homeless rows ride every region' sent ~600 such rows to each of 11
    regions in 70-row chunks — 101 image calls, 33 minutes, most of them
    answering nothing.)"""
    grp_pages = {(doc, pn) for pn in grp}
    return [t for t in unserved if t.key not in out
            and (homes.get(t.key, set()) & grp_pages)]


def read_gaps(ledger, targets, served, client, pdf_paths, log=None):
    """-> new served entries for rows Stage 2 left. One call per region
    chunk; every acceptance is checksummed (or block-anchored for no-prior
    rows). Never overwrites an existing serving."""
    log = log if log is not None else []
    import pdfplumber
    from pathlib import Path
    by_name = {Path(p).name: p for p in pdf_paths}

    unserved = [t for t in targets
                if t.key not in served and not t.is_backout
                and (t.label or isinstance(t.prior_value, (int, float)))]
    if not unserved:
        return {}
    priors = [t.prior_value for t in targets
              if isinstance(t.prior_value, (int, float))]
    deep = [t.prior2_value for t in targets
            if isinstance(t.prior2_value, (int, float))]
    ledger.classify_doc_periods(priors, deep)
    prior_docs = _vintage_ban(ledger)
    homes = row_homes(ledger, targets)
    block_scales = ratify_page_scales(ledger.join_pool(), priors)
    text_by_page = defaultdict(list)
    for it in ledger.items:
        text_by_page[(it.doc, it.page)].append(it.source_line)

    out = {}
    for doc, path in by_name.items():
        if doc in prior_docs:
            log.append(f"stage-3: {doc} skipped (prior-period document)")
            continue
        for grp in regions_from_ledger(ledger, doc):
            rows = rows_for_region(unserved, homes, doc, grp, out)
            if len(rows) < 3:
                continue
            rows.sort(key=lambda t: (t.sheet, t.row))
            with pdfplumber.open(path) as pdf:
                img_cache = {}
                for i in range(0, len(rows), MAX_ROWS_PER_CALL):
                    chunk = rows[i:i + MAX_ROWS_PER_CALL]
                    votes = Counter(pn for t in chunk
                                    for (d, pn) in homes.get(t.key, ())
                                    if d == doc and pn in grp)
                    img_pages = ([pn for pn, _ in votes.most_common(MAX_IMAGES_PER_CALL)]
                                 or grp[:MAX_IMAGES_PER_CALL])
                    images = [im for pn in sorted(img_pages)
                              for im in [_page_png(pdf, pn, img_cache)] if im]
                    tbl = "\n".join(f"p{pn}: {ln}" for pn in grp
                                    for ln in text_by_page.get((doc, pn), []))[:MAX_TABLE_TEXT]
                    rows_txt = "\n".join(
                        f"- {t.sheet}!{t.row}: '{str(t.label)[:46]}'"
                        + (f" (prior year in model units: {t.prior_value:,.2f})"
                           if isinstance(t.prior_value, (int, float)) else " (no prior)")
                        for t in chunk)
                    user = (_CONTRACT + "\n\n[TABLE TEXT]\n" + tbl
                            + "\n\n[MODEL ROWS]\n" + rows_txt)

                    def _val(o):
                        return [] if isinstance(o.get("rows"), list) else ["missing rows"]
                    try:
                        resp = client.json(_SYSTEM, user, _val, repair_retries=1,
                                           images=images or None)
                    except Exception as ex:
                        log.append(f"stage-3 {doc} p{grp[0]}-{grp[-1]}: call failed: {ex}")
                        continue
                    n_ok = n_srv = 0
                    by_id = {f"{t.sheet}!{t.row}": t for t in chunk}
                    for a in resp.get("rows", []):
                        rid = str(a.get("id", ""))
                        t = by_id.get(rid)
                        if a.get("status") != "OK" or t is None or t.key in out:
                            continue
                        n_ok += 1
                        pv = t.prior_value
                        if isinstance(pv, (int, float)):
                            acc = checksum_accept(a.get("current"),
                                                  a.get("comparative"), pv)
                            if acc is None:
                                continue    # answered but did not tie: untrusted
                            v, s = acc
                            out[t.key] = {
                                "value": v, "status": "OK", "doc": doc,
                                "page": grp[0], "conf": CONF_CHECKSUMMED,
                                "line": f"{a.get('current')} | {a.get('comparative')}",
                                "note": ("stage-3 read: comparative ties the "
                                         "model's prior (signed row checksum, "
                                         f"scale {s:g})")}
                            n_srv += 1
                        else:
                            # no-prior: only with the block's ratified anchor
                            anchors = [block_scales[(doc, pn)] for pn in img_pages
                                       if (doc, pn) in block_scales]
                            v = no_prior_value(a.get("current"), anchors)
                            if v is None:
                                continue    # no proven scale -> stays a loud hole
                            from .writegate import (claimed_values,
                                                    no_prior_duplicate)
                            reg = claimed_values(served)
                            reg.update(claimed_values(out))
                            if no_prior_duplicate(v, doc, reg):
                                log.append(
                                    f"stage-3 REFUSED no-prior {t.key}: "
                                    f"{v:,.1f} already has a home in this "
                                    "document (one number, one home)")
                                continue
                            out[t.key] = {
                                "value": v, "status": "OK",
                                "doc": doc, "page": grp[0], "conf": CONF_NO_PRIOR,
                                "flag": "red",
                                "line": str(a.get("current"))[:60],
                                "note": ("stage-3 read (no prior): converted at "
                                         f"the block's RATIFIED scale "
                                         f"{anchors[0]:g}; review — no "
                                         "comparative to checksum")}
                            n_srv += 1
                    log.append(f"stage-3 {doc} p{grp[0]}-{grp[-1]} rows "
                               f"{len(chunk)}: {n_ok} answered, {n_srv} accepted")
    log.append(f"stage-3 total: {len(out)} rows served "
               f"({sum(1 for e in out.values() if e['conf'] == CONF_CHECKSUMMED)} "
               f"checksummed)")
    return out
