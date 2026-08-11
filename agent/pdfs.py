"""Disclosure ingestion: PDF -> page-numbered text, cached on disk.

Text is chunked by page so every extracted figure can carry a page reference,
and so long documents can be fed to the LLM in windows without losing citations.
"""
import hashlib
import json
from pathlib import Path

import pdfplumber

CACHE = Path(".cache/pdftext")


def pages(pdf_path):
    """Return [(page_no, text), ...] (1-based), cached by file content hash."""
    pdf_path = Path(pdf_path)
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:16]
    cache_file = CACHE / f"{digest}.json"
    if cache_file.exists():
        return [(p, t) for p, t in json.loads(cache_file.read_text())]
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            out.append((i, page.extract_text() or ""))
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(out))
    return out


def windows(page_texts, chars_per_window=60000, overlap_pages=1):
    """Split page list into overlapping windows that fit a modest context."""
    wins, cur, size = [], [], 0
    for p, t in page_texts:
        cur.append((p, t))
        size += len(t)
        if size >= chars_per_window:
            wins.append(cur)
            cur, size = cur[-overlap_pages:], sum(len(t) for _, t in cur[-overlap_pages:])
    if cur and (not wins or cur != wins[-1]):
        wins.append(cur)
    return wins


def render(win):
    return "\n\n".join(f"=== PAGE {p} ===\n{t}" for p, t in win)
