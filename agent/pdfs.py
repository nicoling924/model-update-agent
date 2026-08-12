"""Disclosure ingestion: PDF -> page-numbered text, cached on disk.

Text is chunked by page so every extracted figure can carry a page reference,
and so long documents can be fed to the LLM in windows without losing citations.
"""
import hashlib
import json
from pathlib import Path

import pdfplumber

CACHE = Path(".cache/pdftext")


TEXT_VERSION = "v3-tables"  # bump when page rendering changes (invalidates cache)


def pages(pdf_path):
    """Return [(page_no, text), ...] (1-based), cached by file content hash.

    TABLE-AWARE: each page's flowed text is followed by structural re-renders of
    every table pdfplumber can reconstruct from the page geometry, one row per
    line with the column header attached to every cell:
        Revenue | 2025: 88,018 | 2024: 87,211
    This removes the which-column-is-which guesswork that causes most weak-model
    misreads. Pure deterministic code — no LLM involved.
    """
    pdf_path = Path(pdf_path)
    digest = hashlib.sha256(pdf_path.read_bytes() + TEXT_VERSION.encode()).hexdigest()[:16]
    cache_file = CACHE / f"{digest}.json"
    if cache_file.exists():
        return [(p, t) for p, t in json.loads(cache_file.read_text())]
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            rendered = [r for t in tables if t for r in [_render_table(t)] if r]
            if not rendered:
                # statements pages are usually whitespace-aligned (no gridlines):
                # retry with text-based column detection
                try:
                    tables = page.extract_tables(
                        {"vertical_strategy": "text", "horizontal_strategy": "text",
                         "min_words_vertical": 3}) or []
                    rendered = [r for t in tables if t for r in [_render_table(t)] if r]
                except Exception:
                    pass
            if rendered:
                text += "\n\n[STRUCTURED TABLES ON THIS PAGE — column headers " \
                        "attached to every value]\n" + "\n\n".join(rendered)
            out.append((i, text))
    CACHE.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(out))
    return out


def _render_table(rows):
    """Render one extracted table as 'label | HDR1: v1 | HDR2: v2' lines."""
    rows = [[(c or "").strip().replace("\n", " ") for c in r] for r in rows if r]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2 or max(len(r) for r in rows) < 2:
        return None
    # header = first row with 2+ short non-numeric-ish cells after the first col
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
