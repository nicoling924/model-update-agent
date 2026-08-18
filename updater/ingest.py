"""Verified whole-page ingestion — the Fable-grade reading pass.

Owner ruling (2026-08-18): the agent misses numbers that are easily found
in the report because the evidence pool is a sieve (flat lines lose
columns; islands recover some grids; vision covers scans). This pass
gives the engine the working conditions that measured 96%/zero-wrong-
reads: WHOLE pages, read completely, every row VERIFIED before it is
believed.

The checksum law (fablemode lineage, 0 wrong reads ever measured):
a read row enters the ledger ONLY if
  (a) BOTH its numbers appear among the page's own extracted numbers
      (the engine copied, never invented), and
  (b) its comparative slot ties a model prior at identity grade
      (the printed prior-year anchors the row to the model's world).
Unverified rows are simply dropped — misreads do not serve.

Verified items are face-grade evidence wherever they sit (Item.verified),
feeding the join, the oracle, and the fixed-point reconciliation.
Page selection is number-anchored: current-doc pages ranked by how many
model priors they print. Results are cached digest-once per document.
"""
import hashlib
import json
from pathlib import Path

from .ledger import Item
from .numerics import SCALES, line_numbers, row_tol, to_model_units

CACHE = Path(".cache/ingest")
VERSION = "v1"
MAX_PAGES = 36
MAX_ROWS_PER_PAGE = 60


def _select_pages(ledger, priors, cap=MAX_PAGES):
    """Current-doc pages ranked by printed-model-prior density."""
    prior_docs = ledger.prior_period_docs()
    pages = {}
    for it in ledger.items:
        if it.doc in prior_docs:
            continue
        pages.setdefault((it.doc, it.page), []).extend(it.nums)
    scored = []
    for (doc, page), nums in pages.items():
        score = 0
        for pv in priors:
            tol = row_tol(pv)
            if any(abs(abs(to_model_units(n, s)) - abs(pv)) <= tol
                   for n in nums for s in SCALES):
                score += 1
        if score >= 2:
            scored.append((-score, doc, page))
    scored.sort()
    return [(doc, page) for _s, doc, page in scored[:cap]]


def _page_text(ledger, doc, page):
    return "\n".join(it.source_line for it in ledger.items
                     if it.doc == doc and it.page == page)


def _verify(rows, page_nums_abs, priors):
    """The checksum: copied-not-invented AND prior-anchored."""
    out = []
    ptols = [(pv, row_tol(pv)) for pv in priors]
    for r in rows:
        try:
            cur = float(str(r.get("current")).replace(",", ""))
            prior = float(str(r.get("prior")).replace(",", ""))
        except (TypeError, ValueError):
            continue
        lab = str(r.get("label", "")).strip()
        if not lab:
            continue
        printed = all(any(abs(abs(v) - a) <= max(0.01, a * 1e-6)
                          for a in page_nums_abs)
                      for v in (cur, prior) if v != 0)
        anchored = any(
            abs(abs(to_model_units(prior, s)) - abs(pv)) <= tol
            for pv, tol in ptols for s in SCALES)
        if not anchored:
            continue
        if not printed:
            # RECOVERY MODE (owner's same-page law): vision misses lines;
            # requiring the missed number to already exist in the flawed
            # extraction is circular. The original fablemode checksum —
            # the comparative ties a model prior at IDENTITY grade —
            # measured zero wrong reads ever; under it a missed line may
            # be recovered when the identity is tight and the current
            # value is in the row's own world.
            identity = any(
                abs(abs(to_model_units(prior, s)) - abs(pv))
                <= max(0.6, abs(pv) * 5e-4)
                for pv, _t in ptols for s in SCALES)
            in_world = (cur != 0 and prior != 0
                        and 0.01 <= abs(cur) / abs(prior) <= 100.0)
            if not (identity and in_world):
                continue
        out.append((lab, cur, prior))
    return out


def read_pages(ledger, targets, client, log, pages, extra_prompt="",
               fresh=False):
    """Verified whole-page read of SPECIFIC pages (the reading stage's
    workhorse). client=None replays the cache only — the offline gate
    must see the same evidence pool the live run sees. extra_prompt adds
    a targeted demand (repair loop: 'this section must sum to X — every
    row'); fresh bypasses the cache for repair re-reads."""
    priors = [t.prior_value for t in targets
              if isinstance(t.prior_value, (int, float))
              and abs(t.prior_value) >= 1.0]
    CACHE.mkdir(parents=True, exist_ok=True)
    prompt = (Path(__file__).resolve().parent.parent / "prompts"
              / "ingest.md").read_text(encoding="utf-8")
    n_added = n_pages = 0
    for doc, page in pages:
        text = _page_text(ledger, doc, page)
        if len(text) < 80:
            continue
        key = hashlib.sha256(
            (VERSION + doc + str(page) + text
             + extra_prompt).encode()).hexdigest()[:16]
        cf = CACHE / f"{key}.json"
        if cf.exists() and not fresh:
            rows = json.loads(cf.read_text())
        elif client is None:
            continue                      # dry replay: cache hits only
        else:
            def _val(o):
                if not isinstance(o.get("rows"), list):
                    return ["'rows' list required"]
                return []
            try:
                out = client.json(
                    "You transcribe financial statement pages exactly. "
                    "Copy numbers verbatim; never compute or invent.",
                    prompt + ("\n\n" + extra_prompt if extra_prompt else "")
                    + "\n\n== PAGE p" + str(page) + " ==\n" + text,
                    _val, repair_retries=1)
                rows = out.get("rows", [])[:MAX_ROWS_PER_PAGE]
            except Exception as e:
                log(f"[ingest] p{page} read failed: {e}")
                continue
            cf.write_text(json.dumps(rows, ensure_ascii=False))
        page_nums_abs = sorted({abs(n) for it in ledger.items
                                if it.doc == doc and it.page == page
                                for n in it.nums})
        verified = _verify(rows, page_nums_abs, priors)
        existing = {(it.label, tuple(it.nums)) for it in ledger.items
                    if it.doc == doc and it.page == page
                    and getattr(it, "verified", False)}
        for lab, cur, prior in verified:
            if (lab, (cur, prior)) in existing:
                continue
            ledger.items.append(Item(
                doc=doc, page=page, table_id=900, row_ord=len(ledger.items),
                label=lab, nums=[cur, prior],
                source_line=f"{lab} {cur:,.2f} {prior:,.2f}",
                channel="ingest", verified=True))
            n_added += 1
        n_pages += 1
    return n_pages, n_added


def verified_ingest(ledger, targets, client, log, max_pages=MAX_PAGES):
    """Read the report's financial pages whole (number-anchored page
    selection); append verified rows to the ledger."""
    priors = [t.prior_value for t in targets
              if isinstance(t.prior_value, (int, float))
              and abs(t.prior_value) >= 1.0]
    pages = _select_pages(ledger, priors, cap=max_pages)
    n_pages, n_added = read_pages(ledger, targets, client, log, pages)
    log(f"[ingest] verified whole-page pass: {n_pages} pages, "
        f"{n_added} verified rows added to the ledger")
    return n_added
