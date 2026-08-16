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

VISION (LLM, gated): scanned statement pages (CN annual reports print the
  audited statements as pictures — the exact pages the model needs most).
  Multi-pass consensus transcription: misreads rarely repeat identically,
  so only rows on which >= 2 passes agree digit-for-digit are consensus;
  the rest are kept but marked disputed (never joinable). Then the PRIOR-
  COLUMN CHECKSUM decides page acceptance: the model already holds last
  year, so a real transcription of a real consolidated statement reproduces
  dozens of known priors at one locked scale; a hallucination — or a
  母公司 parent-company twin, or an equity-movement grid — cannot
  (measured separation: real faces anchor 17-29, poison pages 0-2).
  Known values are NEVER in the prompt: the checksum must stay independent
  evidence, not an echo. Fail -> one retry at higher resolution -> the page
  is reported UNREAD, loudly. A loud gap beats an invented digit.

The accepted checksum scale is recorded on the page's items as scale_hint:
the old pipeline's checksums were SECRETLY the block-scale anchor (removing
them for no-prior rows caused run 116); here the anchor is explicit.

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

from .ledger import (Item, Ledger, parse_scale_hint, tag_faces, unit_dim_of)
from .numerics import SCALES, label_of, line_numbers, parse_number, row_tol

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
        nums = line_numbers(stripped)
        if not nums:
            gap += 1
            if gap >= 2:
                in_table = False
            continue
        gap = 0
        if not in_table:
            table_id += 1
            in_table = True
        lab = label_of(stripped)
        if not lab:
            continue        # bare number soup carries no identity
        items.append(Item(
            doc=doc, page=page_no, table_id=table_id, row_ord=ord_,
            label=lab, nums=nums, unit_dim=unit_dim_of(lab),
            scale_hint=current_hint, channel="text", consensus=1,
            source_line=ln[:200]))
    return items


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
            tol = max(row_tol(k) * s, t * 5e-4)
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
    h.update(b"text-v1")
    ck = Path(cache_dir) / f"{h.hexdigest()[:20]}.json"
    if ck.exists():
        return [(pn, t, c) for pn, t, c in json.loads(ck.read_text())]
    import pdfplumber
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, pg in enumerate(pdf.pages):
            txt = (pg.extract_text() or "").strip()
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


def _page_image(pg):
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
    re-spends a call. Higher-resolution retry only when the first vote's
    page anchors weakly (a strong page needs no second look at 3072px)."""
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
            if i == 0:
                hits, _s, _c = checksum_page(
                    [r for r in o.get("rows", []) if isinstance(r, dict)],
                    known_values)
                if hits < ANCHOR_MIN and LONG_EDGE_RETRY not in edges:
                    edges.append(LONG_EDGE_RETRY)   # weak page: one hi-res retry
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
                   cache_dir=".cache/pipeline-vision", log=print):
    """Documents -> Ledger. The one paid read of the run.

    known_values: the model's prior-year actuals (from the target census),
    used ONLY to judge vision acceptance — never shown to the LLM.
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
        # -- vision channel
        image_pages = [pn for pn, c in classes.items() if c == "image"]
        unread = []
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
            # measured ~6 min/page, a 2-hour Stage 1 on a scanned AR
            with pdfplumber.open(path) as pdf:
                imgs = {pn: _page_image(pdf.pages[pn - 1]) for pn in image_pages}
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(min(3, max(1, len(image_pages)))) as ex:
                entries = dict(zip(image_pages, ex.map(
                    lambda pn: _transcribe(path, pn, imgs[pn], client,
                                           known_values, votes, cache_dir, log),
                    image_pages)))
            for pn in image_pages:
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
                if hits < ANCHOR_MIN or copy_frac > COPY_MAX:
                    unread.append((pn, f"checksum FAILED: prior-column anchors "
                                       f"{hits}, copy {copy_frac:.0%}"))
                    continue
                for it in vision_items(doc, pn, title, rows, scale):
                    led.add(it)
                log(f"[stage1] {doc} p{pn}: vision accepted — anchors {hits} "
                    f"at scale {scale:g}, {len(rows)} rows")
        for pn, why in unread:
            log(f"[stage1] {doc} p{pn}: UNREAD — {why}")
        # -- deterministic structure: faces + parent eviction
        faces, parents = tag_faces(face_lines)
        for pn, f in faces.items():
            led.faces[(doc, pn)] = f
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
