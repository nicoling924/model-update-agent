"""Stage 1 — READ ONCE: documents -> the evidence ledger.

The whole stage is a transcription problem. Code does structure (page
classification, table segmentation, face tagging, scale hints); the LLM's
ONLY job is transcribing scanned pages, both years per line. Nothing here
touches the workbook and nothing here writes a cell.

Two channels feed the ledger:

TEXT (deterministic): every digit-bearing line of every text page, parsed
  by code into items with table_id / row_ord / face / scale-hint metadata.
  Code does not misread; one pass is exact. Free, and the bulk of the
  evidence on text-layer filings.

VISION: independent transcriptions establish what a scanned page says.
  Agreeing rows remain available even when an unfamiliar or restated model
  contains no matching prior. Disagreements remain visible but not joinable.
  Model comparatives can corroborate a scale; they do not decide whether
  the rest of a document exists. Printed document identity establishes
  historical scope before eager vision. Known values never enter the prompt.

A corroborated scale remains a hint for downstream row mapping, which must
still resolve units, definitions, period and accounting relationships.

Heavy deps (pdfplumber, PIL) import lazily inside the functions that need
them — the pure logic (segmentation, consensus, checksum) runs on stdlib
so the museum can pin it locally.
"""
import base64
import hashlib
import io
import json
import re
from pathlib import Path

from .ledger import (Item, Ledger, face_from_row_labels, parse_scale_hint,
                     tag_faces, unit_dim_of)
from .numerics import SCALES, label_of, line_cells, line_numbers, parse_number

PROMPT_VERSION = "p1-v1"
VOTES = 2                    # transcription passes per scanned page
ANCHOR_MIN = 4               # known priors a page must reproduce, PRIOR column
                             # only (union-column counting is how a parent P&L
                             # got in once; prior-only, no ride-alongs)
COPY_MAX = 0.8               # max fraction of rows where current == prior
LONG_EDGE = 2400
LONG_EDGE_RETRY = 3072
MAX_VISION_PAGES = 24        # per document; the rest are reported unread
MIN_PAGE_IMAGE_PIXELS = 1_500_000   # a scan is page-sized; stamps are not

_SYSTEM = ("You transcribe scanned financial statements. You copy digits "
           "exactly as printed. You never compute, estimate, or fill in "
           "numbers that are not visible.")

_PROMPT = """This is a scanned page from an annual report (unit: as printed).

Transcribe the financial table on this page. Return STRICT JSON only:

{"title": "<page/table title if visible>",
 "rows": [{"name": "<line item label, verbatim>",
           "current": "<current-period column value exactly as printed, or null if blank>",
           "prior": "<prior-period column value exactly as printed, or null if blank>"}]}

Rules:
- Copy digits EXACTLY as printed, keeping separators as you see them. Do not round, do not add or drop digits.
- A blank cell is null. Never copy one column into the other.
- Include every row, including subtotal rows and section headers (headers with no numbers: both values null).
- Do not compute anything. Do not "fix" anything. If a value is unreadable, use null.
"""

_ENUM = re.compile(r"^\s*\d{1,2}[．、.]\s*")   # '2．少数股东损益' — enumerator, not a value


# ---------------------------------------------------------------------------
# TEXT CHANNEL (pure code; testable without any dependency)
# ---------------------------------------------------------------------------

def segment_page(doc, page_no, text):
    """One text page -> (items, scale_hint_lines_seen).

    Table segmentation: consecutive digit-bearing lines form one table block;
    a gap of >= 2 lines without numbers closes the block. row_ord is the
    PHYSICAL line index on the page — pre-filter geometric order, never a
    post-filter list index (list-index ordering is how left-neighbour
    poisons re-enter).

    A unit-header line ('单位：人民币千元', "RMB'000") sets the scale hint for
    the tables that FOLLOW it on the page. The hint is advisory: Stage 2
    ratifies every block's scale independently before any join.
    """
    items = []
    table_id, gap, in_table = -1, 99, False
    current_hint = None
    for ord_, raw in enumerate(str(text).splitlines()):
        ln = raw.strip()
        if not ln:
            gap += 1
            if gap >= 2:
                in_table = False
            continue
        hint = parse_scale_hint(ln)
        if hint is not None:
            current_hint = hint
        stripped = _ENUM.sub("", ln)
        nums = line_cells(stripped)
        if not nums:
            gap += 1
            if gap >= 2:
                in_table = False
            continue
        gap = 0
        if not in_table:
            table_id += 1
            in_table = True
        # A ROW THE PAGE PRINTS WITHOUT A LABEL IS STILL A ROW (run
        # 34993405014: the CLP P&L prints its operating-expense total as
        # '(74,206) (76,061)' under the four expense lines — the model keeps
        # that total on a row, and dropping the line lost the headline
        # figure and 11% of the statements' rows, all of them subtotals).
        # What the line MEANS is the brain's call; the item carries no
        # label, so stage 2 (which requires label kinship) can never join it
        # on its own.
        lab = label_of(stripped)
        items.append(Item(
            doc=doc, page=page_no, table_id=table_id, row_ord=ord_,
            label=lab, nums=nums, unit_dim=unit_dim_of(lab),
            scale_hint=current_hint, channel="text", consensus=1,
            source_line=ln[:200]))
    _strip_note_column(items)
    return items


def _strip_note_column(items):
    """THE NOTE REFERENCE IS A COLUMN OF THE BLOCK, NEVER A VALUE (run
    34993405014: 'Other gain 5 460 -' was read as 5 and 460 — the statement's
    note number taken for this year's figure and the year's own figure for
    last year's). A note column is the print's own numbering, and the evidence
    for it is that it is an EXTRA column: the row carries one more figure
    than the block's own width, its leading number is a small positive
    integer, and those integers ASCEND down the block. A leading integer on
    a row of the block's normal width is a figure, not a note (reviewer
    2026-09-16: 'Bank charges 3 5 / Other income 9 12' lost this year's
    figure to an ascent that was never a note column). Strips the note in
    place, per block."""
    blocks = {}
    for it in items:
        blocks.setdefault(it.table_id, []).append(it)

    def _small(it):
        return (len(it.nums) >= 2 and float(it.nums[0]).is_integer()
                and 0 < it.nums[0] < 100)
    for block in blocks.values():
        plain = [len(it.nums) for it in block if it.nums and not _small(it)]
        if plain:
            # the block's own number of period columns, read off the rows that
            # cannot be carrying a note; a noted row is one column wider
            width = max(set(plain), key=plain.count)
            seq = [(it, float(it.nums[0])) for it in block
                   if _small(it) and len(it.nums) > width]
        else:
            # EVERY ROW CARRIES ONE (reviewer 2026-09-16: a four-row noted P&L
            # has no un-noted row to measure against, and Revenue kept its note).
            # Then the leading column is the note column only if stripping it
            # still leaves each row a period pair — a note is an EXTRA column,
            # never the row's only figure beside one more.
            seq = [(it, float(it.nums[0])) for it in block
                   if _small(it) and len(it.nums) >= 3]
            if len(seq) != len([it for it in block if it.nums]):
                seq = []             # some row of the block does not carry it: not a column
        if len(seq) < 2:
            continue
        chains = []
        for it, v in seq:
            best = max([c for c in chains if c[-1][1] < v], key=len, default=[])
            chains.append(best + [(it, v)])
        run = max(chains, key=len, default=[])
        if len(run) < 2:
            continue
        for it, _v in run:
            it.nums = it.nums[1:]


# ---------------------------------------------------------------------------
# VISION CHANNEL — pure parts (consensus + checksum), testable on stdlib
# ---------------------------------------------------------------------------

def merge_votes(votes):
    """N transcription passes of one page -> (title, consensus_rows).

    Each vote: {"title": str, "rows": [{"name","current","prior"}]}.
    Rows are keyed by name within each vote (first occurrence wins; a page
    printing one label twice cannot be told apart by name alone, so later
    duplicates never overwrite). A row is CONSENSUS when >= 2 votes agree on
    the parsed (current, prior) pair exactly — misreads rarely repeat
    identically. Disagreeing or single-vote rows are kept DISPUTED so Stage 3
    can see them; they never join. One vote (votes=1 budget): everything
    passes through undisputed and the checksum gate is the only guard.
    """
    votes = [v for v in votes if isinstance(v, dict) and isinstance(v.get("rows"), list)]
    if not votes:
        return "", []
    title = next((str(v.get("title") or "").strip() for v in votes
                  if v.get("title")), "")
    if len(votes) == 1:
        rows = [dict(r, disputed=False) for r in votes[0]["rows"]
                if isinstance(r, dict) and r.get("name")]
        return title, rows

    def key(r):
        return re.sub(r"\s+", "", str(r.get("name") or ""))

    def pair(r):
        return (parse_number(r.get("current")), parse_number(r.get("prior")))

    by_name = {}
    for vi, v in enumerate(votes):
        for r in v["rows"]:
            if not isinstance(r, dict) or not r.get("name"):
                continue
            k = key(r)
            by_name.setdefault(k, {})
            if vi not in by_name[k]:            # first occurrence per vote
                by_name[k][vi] = r
    out = []
    for k, per_vote in by_name.items():
        groups = {}
        for vi, r in per_vote.items():
            groups.setdefault(pair(r), []).append((vi, r))
        best_pair, best = max(groups.items(), key=lambda kv: len(kv[1]))
        rep = dict(best[0][1])
        if len(best) >= 2:
            rep["disputed"] = False
            rep["consensus"] = len(best)
        else:
            rep["disputed"] = True
            rep["consensus"] = 1
        out.append(rep)
    return title, out


def checksum_page(rows, known_values):
    """(anchors_hit, locked_scale, copy_fraction) for one transcribed page.

    Anchors count ONLY in the prior column — the one column the harness can
    verify because the model already holds last year. The page prints
    document units; known values are model units — every legal scale is
    tried and the best-anchoring one is locked. The locked scale is a
    PROVEN block scale (>= ANCHOR_MIN independent priors reproduced at it).
    """
    import bisect
    nums = sorted(abs(p) for r in rows
                  for p in [parse_number(r.get("prior"))] if p)
    known = sorted({abs(v) for v in known_values
                    if isinstance(v, (int, float)) and abs(v) > 100})
    best_hits, best_scale = 0, 1.0
    for s in SCALES:
        hits = 0
        for k in known:
            t = k * s
            # the MEASURED law: 0.6 document-units absolute or 0.05%
            # relative. A 0.5% window (row_tol at scale) measured 10x
            # looser and admitted 4 coincidences on a dense prior-year
            # summary page — an anchor is an identity, not a resemblance.
            tol = max(0.6 * s, t * 5e-4)
            i = bisect.bisect_left(nums, t - tol)
            if i < len(nums) and nums[i] <= t + tol:
                hits += 1
        if hits > best_hits:
            best_hits, best_scale = hits, s
    both = [r for r in rows
            if parse_number(r.get("current")) is not None
            and parse_number(r.get("prior")) is not None]
    copies = sum(1 for r in both
                 if parse_number(r["current"]) == parse_number(r["prior"]))
    copy_frac = (copies / len(both)) if both else 0.0
    return best_hits, best_scale, copy_frac


def vision_items(doc, page_no, title, rows, locked_scale):
    """Accepted transcription rows -> ledger items (one page = one table;
    row_ord = transcription order). The locked checksum scale rides along as
    the block's scale hint — the explicit anchor run 116 lost."""
    items = []
    for i, r in enumerate(rows):
        name = str(r.get("name") or "").strip()
        if not name:
            continue
        cur = parse_number(r.get("current"))
        pri = parse_number(r.get("prior"))
        nums = [v for v in (cur, pri) if v is not None]
        if not nums:
            continue
        items.append(Item(
            doc=doc, page=page_no, table_id=0, row_ord=i,
            label=name[:120], nums=nums, unit_dim=unit_dim_of(name),
            scale_hint=locked_scale, channel="vision",
            consensus=int(r.get("consensus") or 1),
            disputed=bool(r.get("disputed")),
            source_line=f"{name} {r.get('current') or ''} {r.get('prior') or ''}".strip()[:200]))
    return items


# ---------------------------------------------------------------------------
# VISION CHANNEL — document-facing parts (lazy heavy imports)
# ---------------------------------------------------------------------------

def rotated_text(pg, tol=3.0):
    """A PAGE IS READ IN ITS DISPLAYED ORIENTATION (owner 2026-09-10: 43 of
    DFE's 280 annual-report pages are landscape; pdfplumber lines their
    vertical characters up on the wrong axis and every string arrives
    reversed — '53.552,755,368,81' for 18,863,557,255.35, so the fixed-asset,
    CIP and intangible notes were invisible). The PDF says how the page is
    displayed (/Rotate) and each character carries its position: on a
    90/270 page a LINE is a run of characters sharing x, read along y in
    the direction the rotation implies; lines follow each other along x.
    Portrait pages never come here."""
    rot = int(getattr(pg, "rotation", 0) or 0) % 360
    if rot not in (90, 270):
        return None
    chars = [c for c in pg.chars if str(c.get("text", "")).strip() or c.get("text") == " "]
    if not chars:
        return ""
    # cluster on the fixed axis (x): a line
    chars.sort(key=lambda c: ((c["x0"] + c["x1"]) / 2.0))
    lines, cur, cur_x = [], [], None
    for c in chars:
        xm = (c["x0"] + c["x1"]) / 2.0
        if cur and abs(xm - cur_x) > tol:
            lines.append(cur)
            cur = []
        if not cur:
            cur_x = xm
        cur.append(c)
    if cur:
        lines.append(cur)
    # 270: the top of the displayed page is the smallest x, and a line reads
    # from large y to small y; 90: the mirror of both
    if rot == 90:
        lines.reverse()
    out = []
    for ln in lines:
        ln.sort(key=lambda c: -c["top"] if rot == 270 else c["top"])
        s, prev = [], None
        for c in ln:
            if prev is not None:
                gap = (prev["top"] - c["bottom"]) if rot == 270 else (c["top"] - prev["bottom"])
                if gap > tol:
                    s.append(" ")
            s.append(c["text"])
            prev = c
        text = "".join(s).strip()
        if text:
            out.append(text)
    return "\n".join(out)


def page_texts(pdf_path, cache_dir=".cache/pipeline-text"):
    """[(page_no, text, cls)] for a document, disk-cached by content hash.

    cls is 'text' | 'image' | 'empty' — strict: 'image' means A SCAN
    (essentially no text layer AND a page-scale embedded image). Prose pages
    carrying stamps/logos are NOT scans (a loose test once classed 57 pages
    as image when ~12 were, burning the page budget on covers). Extraction
    is the slow step of a run — the cache makes every re-run free.
    """
    p = Path(pdf_path)
    h = hashlib.sha1()
    h.update(p.name.encode())
    h.update(str(p.stat().st_size).encode())
    h.update(b"text-v2")      # v2: landscape pages read in their displayed orientation
    ck = Path(cache_dir) / f"{h.hexdigest()[:20]}.json"
    if ck.exists():
        return [(pn, t, c) for pn, t, c in json.loads(ck.read_text())]
    import pdfplumber
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, pg in enumerate(pdf.pages):
            rt = rotated_text(pg)
            txt = (rt if rt is not None else (pg.extract_text() or "")).strip()
            digits = sum(ch.isdigit() for ch in txt)
            big = any(im["srcsize"][0] * im["srcsize"][1] >= MIN_PAGE_IMAGE_PIXELS
                      for im in pg.images)
            cls = ("text" if digits >= 20 or len(txt) >= 200
                   else "image" if big else "empty")
            out.append((i + 1, txt if cls == "text" else "", cls))
    ck.parent.mkdir(parents=True, exist_ok=True)
    ck.write_text(json.dumps(out, ensure_ascii=False))
    return out


def classify_pages(pdf_path):
    """{page_no: 'text'|'image'|'empty'} (cached via page_texts)."""
    return {pn: cls for pn, _t, cls in page_texts(pdf_path)}


def _page_image_raw(pg):
    """Best PIL image for a scanned page: CCITT text mask first, JPEG second.

    Scanned CN filings are layered (MRC): a 1-bit CCITT mask carries every
    digit; the JPEG below holds ruling lines and the chop. Streams decode
    through pdfminer's own filter chain — no renderer, no OCR binary, no
    new dependency (the bank constraint).
    """
    from PIL import Image
    mask = jpeg = None
    for im in sorted(pg.images, key=lambda i: -(i["srcsize"][0] * i["srcsize"][1])):
        w, h = int(im["srcsize"][0]), int(im["srcsize"][1])
        if w * h < 1_000_000:
            continue
        st = im.get("stream")
        if st is None:
            continue
        try:
            data = st.get_data()
        except Exception:
            continue
        if mask is None and "CCITT" in str(st.attrs.get("Filter")):
            need = ((w + 7) // 8) * h
            if len(data) >= need:
                try:
                    mask = Image.frombytes("1", (w, h), data[:need])
                except Exception:
                    mask = None
        elif jpeg is None and data[:3] == b"\xff\xd8\xff":
            try:
                j = Image.open(io.BytesIO(data))
                j.load()
                jpeg = j
            except Exception:
                jpeg = None
    return mask or jpeg


def _page_image(pg):
    """The scan, turned the way the page is displayed (see rotated_text)."""
    im = _page_image_raw(pg)
    rot = int(getattr(pg, "rotation", 0) or 0) % 360
    if im is not None and rot:
        im = im.rotate(-rot, expand=True)     # PIL rotates counter-clockwise; /Rotate is clockwise
    return im


def _encode(img, long_edge):
    """(mime, base64) — bilevel masks as crisp PNG, photos as JPEG."""
    bilevel = img.mode == "1"
    if bilevel:
        img = img.convert("L")
    if max(img.size) > long_edge:
        r = long_edge / max(img.size)
        img = img.resize((max(1, int(img.size[0] * r)),
                          max(1, int(img.size[1] * r))))
    buf = io.BytesIO()
    if bilevel:
        img.save(buf, "PNG")
        mime = "image/png"
    else:
        img.convert("RGB").save(buf, "JPEG", quality=90)
        mime = "image/jpeg"
    return mime, base64.b64encode(buf.getvalue()).decode()


def _cache_key(pdf_path, page_no):
    p = Path(pdf_path)
    h = hashlib.sha1()
    h.update(p.name.encode())
    h.update(str(p.stat().st_size).encode())
    h.update(f"p{page_no}-{PROMPT_VERSION}".encode())
    return h.hexdigest()[:20]


def _validate_transcription(o):
    return [] if isinstance(o.get("rows"), list) else ["missing rows list"]


def _transcribe(pdf_path, page_no, img, client, known_values, votes, cache_dir, log):
    """One scanned page -> {"votes": [...], "why": ...} — RAW transcriptions,
    cached; acceptance is judged at load time so tuning thresholds never
    re-spends a call. Higher-resolution retry follows missing or conflicting transcription
    evidence, not absence of a match with an analyst's workbook."""
    ck = Path(cache_dir) / f"{_cache_key(pdf_path, page_no)}.json"
    if ck.exists():
        cached = json.loads(ck.read_text())
        if cached.get("votes") or str(cached.get("why", "")).startswith("no decodable"):
            return cached
    entry = {"page": page_no, "votes": []}
    if img is None:
        entry["why"] = "no decodable full-page image stream"
    else:
        edges = [LONG_EDGE] * votes
        for i, edge in enumerate(edges):
            mime, b64 = _encode(img, edge)
            try:
                o = client.json(_SYSTEM, _PROMPT, _validate_transcription,
                                repair_retries=1, images=[(mime, b64)])
            except Exception as e:
                entry["why"] = f"vision call failed: {e}"
                break
            entry["votes"].append({"title": o.get("title"), "rows": o.get("rows")})
            readings = entry["votes"]
            missing = not o.get("rows")
            disagreement = len(readings) > 1 and any(r.get("disputed") for r in merge_votes(readings)[1])
            if (missing or disagreement) and LONG_EDGE_RETRY not in edges:
                edges.append(LONG_EDGE_RETRY)  # evidence: conflicting or missing digits need a clearer reading
    ck.parent.mkdir(parents=True, exist_ok=True)
    ck.write_text(json.dumps(entry, ensure_ascii=False))
    log(f"[stage1] {Path(pdf_path).name} p{page_no}: transcribed "
        f"({len(entry['votes'])} vote(s))"
        if entry.get("votes") else
        f"[stage1] {Path(pdf_path).name} p{page_no}: {entry.get('why', '?')}")
    return entry


# ---------------------------------------------------------------------------
# MAIN ENTRY
# ---------------------------------------------------------------------------

def read_documents(paths, client=None, known_values=(), votes=VOTES,
                   cache_dir=".cache/pipeline-vision", log=print, target_year=None, period_kind="FY"):
    """Documents -> Ledger. The one paid read of the run.

    known_values: the model's prior-year actuals (from the target census),
    used to corroborate scale, never to discard an otherwise readable page
    and never shown to the LLM.
    client=None runs text-only (scanned pages reported unread) — the dry-run
    and text-filing path.
    """
    led = Ledger()
    for path in paths:
        doc = Path(path).name
        pages = page_texts(path)
        classes = {pn: cls for pn, _t, cls in pages}
        face_lines = []     # (page, line) fed to the deterministic face tagger
        # -- text channel
        for pn, text, cls in pages:
            if cls != "text":
                continue
            for ln in text.splitlines():
                if ln.strip():
                    face_lines.append((pn, ln.strip()))
            for it in segment_page(doc, pn, text):
                led.add(it)
            # PROSE FIGURES (owner 2026-09-08): a figure stated in a sentence
            # is evidence too — harvested as lines so the same map applies
            from .prose import harvest_prose
            for it in harvest_prose(doc, pn, text):
                led.add(it)
        # -- vision channel
        image_pages = [pn for pn, c in classes.items() if c == "image"]
        unread = []
        vision_faces = {}   # accepted scan pages self-identify by their rows
        # Printed period identity, not compatibility with an analyst's numbers,
        # establishes whether a document is historical. Unknown identity stays
        # available; later row mapping must resolve its scope.
        if image_pages and target_year is not None:
            from .docid import printed_identity, classify_identity
            identity = printed_identity([(pn, text) for pn, text, _cls in pages])
            if classify_identity(identity, target_year, period_kind) == "prior":
                log(f"[stage1] {doc}: printed prior-period identity — scanned evidence remains on demand")
                unread += [(pn, "printed prior-period identity: text only") for pn in image_pages]
                image_pages = []
        if image_pages and client is None:
            unread = [(pn, "no vision client") for pn in image_pages]
        elif image_pages:
            import pdfplumber
            if len(image_pages) > MAX_VISION_PAGES:
                log(f"[stage1] {doc}: {len(image_pages)} scanned pages, capping "
                    f"at {MAX_VISION_PAGES} (rest reported unread)")
                unread += [(pn, "over page budget")
                           for pn in image_pages[MAX_VISION_PAGES:]]
                image_pages = image_pages[:MAX_VISION_PAGES]
            # pixels come out sequentially (pdfplumber pages are not
            # thread-safe); the PAID calls run 3-wide — sequential vision
            # measured ~6 min/page, a 2-hour Stage 1 on a scanned AR.
            with pdfplumber.open(path) as pdf:
                imgs = {pn: _page_image(pdf.pages[pn - 1]) for pn in image_pages}
            from concurrent.futures import ThreadPoolExecutor
            entries = {}
            with ThreadPoolExecutor(3) as ex:
                for i in range(0, len(image_pages), 3):
                    batch = image_pages[i:i + 3]
                    for pn, entry in zip(batch, ex.map(
                            lambda pn: _transcribe(path, pn, imgs[pn], client,
                                                   known_values, votes,
                                                   cache_dir, log), batch)):
                        entries[pn] = entry
            for pn in [p for p in image_pages if p in entries]:
                entry = entries[pn]
                if not entry.get("votes"):
                    unread.append((pn, entry.get("why", "?")))
                    continue
                title, rows = merge_votes(entry["votes"])
                if title:
                    # even a REJECTED page's caption feeds the tagger — a
                    # 母公司 title must evict its page so consolidated
                    # captions cannot propagate onto it
                    face_lines.append((pn, title))
                judged = [r for r in rows if not r.get("disputed")]
                hits, scale, copy_frac = checksum_page(judged, known_values)
                anchored = hits >= ANCHOR_MIN and copy_frac <= COPY_MAX
                if not anchored:
                    # Agreement between independent transcriptions is evidence of
                    # what the page says, even when the model contains no matching
                    # prior. Uncorroborated readings remain visible but not joinable.
                    rows = [dict(r, disputed=bool(r.get("disputed")) or
                                 int(r.get("consensus") or 1) < 2) for r in rows]  # evidence: independently agreeing readings
                for it in vision_items(doc, pn, title, rows, scale if anchored else None):
                    led.add(it)
                inferred = face_from_row_labels(
                    [r.get("name") for r in rows if r.get("name")])
                if inferred:
                    vision_faces[pn] = inferred
                log(f"[stage1] {doc} p{pn}: vision accepted — anchors {hits} "
                    f"at scale {scale if anchored else 'unresolved'}, {len(rows)} rows retained"
                    + (f", face {inferred} (from rows)" if inferred else ""))
        for pn, why in unread:
            log(f"[stage1] {doc} p{pn}: UNREAD — {why}")
        # -- deterministic structure: faces + parent eviction. Caption tags
        # win; an accepted scan page whose caption was cropped falls back to
        # its row-label self-identification. Parent eviction stays SENIOR:
        # an evicted page never gets a face from any source.
        faces, parents = tag_faces(face_lines)
        for pn, f in faces.items():
            led.faces[(doc, pn)] = f
        for pn, f in vision_faces.items():
            if pn not in parents:
                led.faces.setdefault((doc, pn), f)
        led.parent_pages |= {(doc, pn) for pn in parents}
        led.doc_meta[doc] = {
            "pages": len(classes),
            "text_pages": sum(1 for c in classes.values() if c == "text"),
            "image_pages": sum(1 for c in classes.values() if c == "image"),
            "unread": [[pn, why] for pn, why in unread],
        }
        log(f"[stage1] {doc}: {len([i for i in led.items if i.doc == doc])} items, "
            f"faces on {len(faces)} pages, {len(parents)} parent pages evicted")
    return led
