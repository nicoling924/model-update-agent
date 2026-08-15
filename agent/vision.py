"""Eyes: the engine's own vision on image-only PDF pages.

A filing's audited statements are sometimes pure scans (Dongfang FY25 pp95-106
— exactly the balance sheet run 97 needed). pdfplumber extracts no text there,
so to the text pipeline those numbers do not exist: the agent diagnosed its own
15,199 gap and could not close it because the number was a picture.

This module gives the SAME engine its eyes — no second model, no OCR binary:

1. PAGE CLASS (code): a page with no extractable digits but an embedded image
   is `image`; everything else stays with the text pipeline.
2. PIXELS WITHOUT A RENDERER (the bank constraint — no poppler/tesseract/
   pypdfium2): scanned CN filings are layered (MRC) — a 1-bit CCITT text MASK
   over a JPEG background. Measured on Dongfang p95: the JPEG holds only
   ruling lines and the chop; the MASK carries every digit. We pull the
   embedded streams via pdfminer's own filter chain and rebuild the mask with
   PIL. Prefer the mask; fall back to the JPEG.
3. TRANSCRIBE (the engine, vision): both columns as strict JSON, digits exact.
   The prompt never contains our known values — the checksum below must stay
   independent evidence, not an echo.
4. CHECKSUM (code): the model already holds ~dozens of prior-period values for
   these statements. A real transcription reproduces them (at the document's
   unit scale); a hallucinated one cannot. Gates: >=ANCHOR_MIN known values
   found (scale locked per page), and the current column must not simply copy
   the prior column. Fail -> one retry at higher resolution -> page marked
   unread, loudly. Never invent digits.
5. INJECT: accepted rows become ordinary raw lines ("<name> <current> <prior>",
   canonical comma format) on their true page number. Retrieval, mapping,
   audit, the orchestrator — everything downstream works unchanged.

Transcriptions are cached on disk per (pdf, page, prompt version) so the
learner, updater and orchestrator share one paid read per page.
"""
import base64
import hashlib
import io
import json
import re
from pathlib import Path

from PIL import Image

from . import lookup

PROMPT_VERSION = "v1"
LONG_EDGE = 2400
LONG_EDGE_RETRY = 3072
ANCHOR_MIN = 4          # known values a self-standing page must reproduce
ANCHOR_MIN_BLOCK = 2    # enough when a sibling page proved the block's scale:
                        # two 11-digit exact matches at a fixed scale are
                        # already beyond coincidence (CF pages measured 2-3 —
                        # the model simply tracks fewer CF rows than BS rows)
COPY_MAX = 0.8          # max fraction of rows where current == prior
SCALES = (1, 1e3, 1e4, 1e6, 1e8)
MAX_PAGES_PER_DOC = 24

_SYSTEM = (
    "You transcribe scanned Chinese financial statements. You copy digits "
    "exactly as printed. You never compute, estimate, or fill in numbers that "
    "are not visible."
)

_PROMPT = """This is a scanned page from a Chinese annual report (unit: as printed, usually 人民币元).

Transcribe the financial table on this page. Return STRICT JSON only:

{"title": "<page/table title if visible>",
 "rows": [{"name": "<line item label, verbatim>",
           "current": "<value in the current-period column (期末余额 / 本期发生额 / 本期金额), exactly as printed, or null if blank>",
           "prior": "<value in the prior-period column (上年年末余额 / 上期发生额 / 上期金额), exactly as printed, or null if blank>"}]}

Rules:
- Copy digits EXACTLY as printed, keeping separators as you see them. Do not round, do not add or drop digits.
- A blank cell is null. Never copy one column into the other.
- Include every row of the table, including 合计/总计 subtotal rows and section headers (headers with no numbers: both values null).
- Do not compute anything. Do not "fix" anything. If a value is unreadable, use null.
"""


# -- page classification -----------------------------------------------------

def classify_pages(pdf_path):
    """{page_no: 'text' | 'image' | 'empty'} — cheap, deterministic.

    `image` means A SCAN: essentially no text layer AND a page-scale embedded
    image. Prose pages carrying small stamps/logos are NOT scans — the loose
    version of this test classified 57 pages of the Dongfang FY25 AR as image
    when only ~12 are (measured), wasting the page budget on covers.
    """
    import pdfplumber
    out = {}
    with pdfplumber.open(pdf_path) as pdf:
        for i, pg in enumerate(pdf.pages):
            txt = (pg.extract_text() or "").strip()
            digits = sum(ch.isdigit() for ch in txt)
            big_img = any(im["srcsize"][0] * im["srcsize"][1] >= 1_500_000
                          for im in pg.images)
            if digits >= 20 or len(txt) >= 200:
                out[i + 1] = "text"
            elif big_img:
                out[i + 1] = "image"
            else:
                out[i + 1] = "empty"
    return out


# -- pixels without a renderer ----------------------------------------------

def _page_image(pg):
    """Best PIL image for a scanned page: CCITT text mask first, JPEG second.

    Measured on Dongfang: the mask (1-bit, full page) carries the text; the
    DCT layer is background. Streams are decoded by pdfminer's own filter
    chain — zero new dependencies.
    """
    mask = jpeg = None
    for im in sorted(pg.images, key=lambda i: -(i["srcsize"][0] * i["srcsize"][1])):
        w, h = int(im["srcsize"][0]), int(im["srcsize"][1])
        if w * h < 1_000_000:      # stamps/fragments, not the page
            continue
        st = im.get("stream")
        if st is None:
            continue
        filt = str(st.attrs.get("Filter"))
        try:
            data = st.get_data()
        except Exception:
            continue
        if mask is None and "CCITT" in filt:
            # pdfminer decodes CCITT G4 to a raw 1-bit bitmap: rows of (w+7)//8 bytes
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


def _prep(img, long_edge=LONG_EDGE):
    """(mime, base64) — mask pages as PNG (crisp bilevel), photos as JPEG."""
    bilevel = img.mode == "1"
    if bilevel:
        img = img.convert("L")
    if max(img.size) > long_edge:
        r = long_edge / max(img.size)
        img = img.resize((max(1, int(img.size[0] * r)), max(1, int(img.size[1] * r))))
    buf = io.BytesIO()
    if bilevel:
        img.save(buf, "PNG")
        mime = "image/png"
    else:
        img.convert("RGB").save(buf, "JPEG", quality=90)
        mime = "image/jpeg"
    return mime, base64.b64encode(buf.getvalue()).decode()


# -- number handling ---------------------------------------------------------

_FW = str.maketrans("０１２３４５６７８９，．（）", "0123456789,.()")


def _parse_num(s):
    """'22 679,594 590.64' / '(1,234)' / fullwidth -> float, else None."""
    if s is None:
        return None
    t = str(s).translate(_FW).strip()
    neg = t.startswith("(") and t.endswith(")") or t.startswith("-")
    t = re.sub(r"[^\d.]", "", t)
    if not t or not any(ch.isdigit() for ch in t):
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _fmt(v):
    return f"{v:,.2f}".rstrip("0").rstrip(".") if v == v else ""


# -- checksum ----------------------------------------------------------------

def _checksum(rows, known_values):
    """(anchors_hit, scale, copy_fraction). Known values are in MODEL units;
    the page prints DOCUMENT units — try the standard scales, lock the best."""
    nums = []
    for r in rows:
        for k in ("current", "prior"):
            n = _parse_num(r.get(k))
            if n is not None and abs(n) > 0:
                nums.append(abs(n))
    nums.sort()
    known = [abs(v) for v in known_values
             if isinstance(v, (int, float)) and abs(v) > 100]
    best_hits, best_scale = 0, 1
    import bisect
    for s in SCALES:
        hits = 0
        for k in known:
            t = k * s
            tol = max(0.6 * s, t * 5e-4)
            i = bisect.bisect_left(nums, t - tol)
            if i < len(nums) and nums[i] <= t + tol:
                hits += 1
        if hits > best_hits:
            best_hits, best_scale = hits, s
    both = [(r) for r in rows
            if _parse_num(r.get("current")) is not None
            and _parse_num(r.get("prior")) is not None]
    copies = sum(1 for r in both
                 if _parse_num(r["current"]) == _parse_num(r["prior"]))
    copy_frac = (copies / len(both)) if both else 0.0
    return best_hits, best_scale, copy_frac


# -- cache -------------------------------------------------------------------

def _cache_key(pdf_path, page_no):
    p = Path(pdf_path)
    h = hashlib.sha1()
    h.update(p.name.encode())
    h.update(str(p.stat().st_size).encode())
    h.update(f"p{page_no}-{PROMPT_VERSION}".encode())
    return h.hexdigest()[:20]


# -- main entry points -------------------------------------------------------

def transcribe_image_pages(pdf_path, client, known_values, cache_dir,
                           log=print):
    """-> list of (page_no, 'vision', line) for pages that PASS the checksum.

    Pages that fail twice are reported unread — a loud gap beats an invented
    digit. Transcriptions cache to disk; re-runs and the orchestrator reload
    them free.
    """
    import pdfplumber
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    classes = classify_pages(pdf_path)
    image_pages = [pn for pn, c in classes.items() if c == "image"]
    if not image_pages:
        return []
    if len(image_pages) > MAX_PAGES_PER_DOC:
        log(f"[vision] {Path(pdf_path).name}: {len(image_pages)} image pages, "
            f"capping at {MAX_PAGES_PER_DOC} (rest reported unread)")
        image_pages = image_pages[:MAX_PAGES_PER_DOC]

    def _validate(o):
        return [] if isinstance(o.get("rows"), list) else ["missing rows list"]

    def _transcribe_one(pn, img):
        """One page: vision call(s). Returns the RAW transcription — the gate
        is judged at load time, so tuning thresholds never re-spends a call."""
        entry = {"page": pn, "rows": None}
        if img is None:
            entry["why"] = "no decodable full-page image stream"
            return entry
        for attempt, edge in enumerate((LONG_EDGE, LONG_EDGE_RETRY)):
            mime, b64 = _prep(img, edge)
            try:
                o = client.json(_SYSTEM, _PROMPT, _validate,
                                repair_retries=1, images=[(mime, b64)])
            except Exception as e:
                entry["why"] = f"vision call failed: {e}"
                return entry
            rows = [r for r in o.get("rows", [])
                    if isinstance(r, dict) and r.get("name")]
            hits, _s, _c = _checksum(rows, known_values)
            if entry["rows"] is None or hits > entry.get("_hits", -1):
                entry.update(rows=rows, _hits=hits,
                             title=str(o.get("title") or "")[:60])
            if hits >= ANCHOR_MIN:
                break  # strong page; no need for the hi-res retry
        entry.pop("_hits", None)
        return entry

    # phase 1 (sequential, fast): cache lookups + image extraction —
    # pdfplumber page objects are not thread-safe, so pixels come out here
    todo, entries = [], {}
    with pdfplumber.open(pdf_path) as pdf:
        for pn in image_pages:
            ck = cache_dir / f"{_cache_key(pdf_path, pn)}.json"
            cached = json.loads(ck.read_text()) if ck.exists() else None
            # a cache entry is a TRANSCRIPTION, not a verdict: reuse only if
            # the rows are there (or the page is structurally unreadable) —
            # anything else, including transient call failures, re-calls
            if cached is not None and (
                    isinstance(cached.get("rows"), list)
                    or str(cached.get("why", "")).startswith("no decodable")):
                entries[pn] = cached
            else:
                todo.append((pn, _page_image(pdf.pages[pn - 1])))
    # phase 2 (parallel, slow): the vision calls — sequential 12-page docs
    # measured >10 min; 3 workers bring it to ~1/3
    if todo:
        log(f"[vision] {Path(pdf_path).name}: transcribing {len(todo)} scanned "
            f"pages ({len(entries)} cached)...")
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(min(3, len(todo))) as ex:
            for pn, entry in zip([p for p, _ in todo],
                                 ex.map(lambda t: _transcribe_one(*t), todo)):
                (cache_dir / f"{_cache_key(pdf_path, pn)}.json").write_text(
                    json.dumps(entry))
                entries[pn] = entry
                log(f"[vision]   p{pn}: "
                    + (f"transcribed {len(entry['rows'])} rows"
                       if entry.get("rows") is not None
                       else f"UNREAD — {entry.get('why', '?')}"))

    # phase 3 (code): the gate. Pass 1 — self-standing pages (>=ANCHOR_MIN
    # anchors). Pass 2 — block corroboration: a substantial page whose scale
    # AGREES with a self-standing sibling passes at ANCHOR_MIN_BLOCK (CF/P&L
    # pages print fewer model-tracked rows than the BS; measured 2-3 anchors
    # on real ones). The rows floor keeps small parent-company (母公司)
    # fragments — measured 2 anchors on 5 rows — out of the corroborated set;
    # zero-anchor parent statement pages reject on their own.
    judged = {}
    for pn, entry in entries.items():
        rows = entry.get("rows")
        if rows is None:
            judged[pn] = {"ok": False, "why": entry.get("why", "?")}
            continue
        hits, scale, copy_frac = _checksum(rows, known_values)
        judged[pn] = {"ok": hits >= ANCHOR_MIN and copy_frac <= COPY_MAX,
                      "why": f"anchors {hits}, copy {copy_frac:.0%}",
                      "scale": scale, "hits": hits, "copy": copy_frac,
                      "nrows": len(rows)}
    strong_scales = {j["scale"] for j in judged.values() if j["ok"]}
    for j in judged.values():
        if (not j["ok"] and strong_scales and j.get("scale") in strong_scales
                and j.get("hits", 0) >= ANCHOR_MIN_BLOCK
                and j.get("copy", 1) <= COPY_MAX and j.get("nrows", 0) >= 10):
            j["ok"] = True
            j["why"] += " — block-corroborated"

    out, accepted, rejected = [], [], []
    for pn in image_pages:
        j = judged.get(pn) or {"ok": False, "why": "?"}
        if j["ok"]:
            accepted.append(pn)
            title = entries[pn].get("title")
            if title:  # scope context for the reader (合并 vs 母公司)
                out.append((pn, "vision", title))
            for r in entries[pn]["rows"]:
                c, p = _parse_num(r.get("current")), _parse_num(r.get("prior"))
                if c is None and p is None:
                    continue
                nm = str(r["name"]).strip()[:60]
                out.append((pn, "vision",
                            f"{nm} {_fmt(c) if c is not None else ''} "
                            f"{_fmt(p) if p is not None else ''}".strip()))
        else:
            rejected.append((pn, j["why"]))
    name = Path(pdf_path).name
    if accepted:
        log(f"[vision] {name}: {len(accepted)}/{len(image_pages)} scanned pages "
            f"transcribed & checksum-PASSED ({len(out)} lines injected): "
            f"pp{accepted[0]}-{accepted[-1]}")
    for pn, why in rejected:
        log(f"[vision] {name} p{pn}: UNREAD — {why}")
    # the judged result, persisted whole — cached_lines() serves THIS, so late
    # consumers (objectives, orchestrator) see exactly what the mapper saw
    (cache_dir / f"{_cache_key(pdf_path, 0)}-doc.json").write_text(
        json.dumps({"lines": out}))
    return out


def cached_lines(pdf_paths, cache_dir):
    """The judged vision lines from cache only (no LLM, no re-gating) — for
    late consumers (objectives phase, orchestrator)."""
    cache_dir = Path(cache_dir)
    out = []
    for p in pdf_paths:
        ck = cache_dir / f"{_cache_key(p, 0)}-doc.json"
        if ck.exists():
            out += [tuple(x) for x in json.loads(ck.read_text())["lines"]]
    return out
