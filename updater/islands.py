"""Table Islands — grid-intact evidence for the compile packets.

Council ruling (2026-08-18 night): the segment wall is a REPRESENTATION
problem. Flat-line extraction destroys grid geometry, so cross-language
binding and the implied-prior identity lose their anchors. An ISLAND is a
page's table re-rendered with the column header attached to every cell:

    营业收入 | 2025年: 88,018 | 同比增减(%): 12.07

The compile packet receives intact islands (selected NUMBER-ANCHORED:
an island is relevant when its numbers tie the packet's open priors, or
an island row's value+pct reproduces a prior via the implied identity).
The AGENT reads the grid natively — cross-language by reading, no
dictionaries — and writes with island citations. Implied-prior is
write-time validation, never a retrieval scanner.

The renderer is the validated legacy one (run-103 line). Cached
digest-once per document.
"""
import hashlib
import json
import re
from pathlib import Path

from .numerics import SCALES, line_numbers, row_tol, to_model_units

CACHE = Path(".cache/islands")
VERSION = "v1"
MAX_ISLANDS_PER_PACKET = 4
MAX_ISLAND_CHARS = 2400


def _render_table(rows):
    """One extracted table -> 'label | HDR1: v1 | HDR2: v2' lines (the
    validated legacy renderer, ported verbatim)."""
    rows = [[(c or "").strip().replace("\n", " ") for c in r] for r in rows if r]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2 or max(len(r) for r in rows) < 2:
        return None
    header, body_start = None, 0
    for idx, r in enumerate(rows[:4]):
        tail = [c for c in r[1:] if c]
        if len(tail) >= 2 and all(len(c) <= 24 for c in tail):
            header, body_start = r, idx + 1
            break
    if header is None:
        header, body_start = [""] * max(len(r) for r in rows), 0
    lines = []
    for r in rows[body_start:]:
        label = r[0] if r else ""
        cells = []
        for j, c in enumerate(r[1:], 1):
            if not c:
                continue
            h = header[j] if j < len(header) and header[j] else f"col{j}"
            cells.append(f"{h}: {c}")
        if label and cells:
            lines.append(f"{label} | " + " | ".join(cells))
    return "\n".join(lines) if len(lines) >= 2 else None


def extract(pdf_path):
    """[(page, island_text), ...] for every table pdfplumber reconstructs.
    Cached by content hash (digest-once)."""
    pdf_path = Path(pdf_path)
    digest = hashlib.sha256(pdf_path.read_bytes()
                            + VERSION.encode()).hexdigest()[:16]
    cache_file = CACHE / f"{digest}.json"
    if cache_file.exists():
        return [(p, t) for p, t in json.loads(cache_file.read_text())]
    out = []
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            rendered = [r for t in tables if t
                        for r in [_render_table(t)] if r]
            if not rendered:
                try:
                    tables = page.extract_tables(
                        {"vertical_strategy": "text",
                         "horizontal_strategy": "text",
                         "min_words_vertical": 3}) or []
                    rendered = [r for t in tables if t
                                for r in [_render_table(t)] if r]
                except Exception:
                    pass
            for r in rendered:
                out.append((i, r))
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(out))
    return out


def relevant(doc_islands, open_priors, cap=MAX_ISLANDS_PER_PACKET):
    """NUMBER-ANCHORED island selection for one packet: an island scores
    by how many of the packet's open priors its numbers tie — directly,
    or through the implied identity (a value and a %%-marked pct in the
    same rendered LINE reproducing the prior). Top scorers win."""
    priors = [p for p in open_priors
              if isinstance(p, (int, float)) and abs(p) >= 1.0]
    if not priors:
        return []
    pct_hdr = re.compile(r"[%％]|同比|增减|变动|增长|下降|yoy", re.IGNORECASE)
    scored = []
    for page, text in doc_islands:
        score = 0
        for line in text.splitlines():
            # STRUCTURED PAIRING BY HEADER (the legacy strict-pairing law,
            # restored by the grid): 'h: v' cells whose header names a
            # change-% are pct candidates; the rest are values.
            nums, pcts = [], set()
            for seg in line.split(" | "):
                h, _, v = seg.partition(":")
                seg_nums = line_numbers(v if _ else seg)
                if _ and pct_hdr.search(h):
                    pcts.update(seg_nums)
                else:
                    nums += seg_nums
            for pv in priors:
                tol = row_tol(pv)
                hit = any(abs(abs(to_model_units(n, s)) - abs(pv)) <= tol
                          for n in nums for s in SCALES)
                if not hit:
                    for v in nums:
                        if v == 0 or abs(v) in {abs(p) for p in pcts}:
                            continue
                        for pct in pcts:
                            if pct <= -100 or abs(pct) < 0.5 \
                                    or abs(pct) >= 400:
                                continue
                            implied = v / (1 + pct / 100.0)
                            if any(abs(abs(implied) / s - abs(pv))
                                   <= max(abs(pv) * 0.005, 0.6)
                                   for s in SCALES):
                                hit = True
                                break
                        if hit:
                            break
                if hit:
                    score += 1
        if score >= 2:                    # one tie is a coincidence
            scored.append((score, page, text[:MAX_ISLAND_CHARS]))
    scored.sort(key=lambda x: -x[0])
    return [(page, text) for _s, page, text in scored[:cap]]
