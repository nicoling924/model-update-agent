"""Digest-once: read each disclosure set carefully ONCE, freeze the result.

A report's content never changes, but a weak model reads it differently every
pass — the measured ±4-5pp run lottery. This module spends 3 extraction passes
ONE time, merges them coverage-preserving (union + arbitration, not
intersection), corroborates against the raw page text, and freezes the result
as digest.json beside the PDFs. Updates then consume the frozen digest:
reproducible, variance-free, and the best reading the model ever produced.
"""
import hashlib
import json
import re
from pathlib import Path

from . import extraction, lookup

PASSES = 3


def signature(disclosure_paths, prompt, system, model):
    src = prompt + system + model + "".join(
        hashlib.sha256(p.read_bytes()).hexdigest() for p in disclosure_paths)
    return hashlib.sha256(src.encode()).hexdigest()[:16]


def _key(it):
    lab = re.sub(r"[^a-z0-9]+", " ", str(it.get("label", "")).lower()).strip()
    return (it.get("stmt"), lab, it.get("segment"))


def build(client, system, disclosure_paths, extraction_prompt, cfg, out_path, sig):
    """3 passes -> union merge with per-item confidence -> frozen digest."""
    passes = []
    for i in range(PASSES):
        print(f"[D1] extraction pass {i + 1}/{PASSES} ...", flush=True)
        passes.append(extraction._extract_once(client, system, disclosure_paths,
                                               extraction_prompt, cfg))
        print(f"[D1] pass {i + 1}: {len(passes[-1]['items'])} items, "
              f"{len(passes[-1]['ties'])} ties", flush=True)
    # raw-text corroboration index: every |number| printed anywhere, by page
    raw_nums = {}
    for pn, _sec, ln in lookup.raw_lines(disclosure_paths):
        for m in re.finditer(r"\(?-?[\d,]{3,}(?:\.\d+)?\)?", ln):
            t = m.group(0).replace(",", "").strip("()")
            try:
                raw_nums.setdefault(round(abs(float(t)), 1), set()).add(pn)
            except ValueError:
                pass

    buckets = {}
    for pi, p in enumerate(passes):
        for it in p["items"]:
            if not isinstance(it.get("value"), (int, float)):
                continue
            buckets.setdefault(_key(it), []).append((pi, it))
    merged, n_major, n_corr, n_single = [], 0, 0, 0
    for k, entries in buckets.items():
        by_val = {}
        for pi, it in entries:
            slot = next((v for v in by_val if abs(v - it["value"]) <= 1.0), None)
            by_val.setdefault(slot if slot is not None else round(it["value"], 1),
                              []).append((pi, it))
        # winner: the value most passes agree on; ties broken by raw-text presence
        ranked = sorted(by_val.items(),
                        key=lambda kv: (len({pi for pi, _ in kv[1]}),
                                        len(raw_nums.get(round(abs(kv[0]), 1), ()))),
                        reverse=True)
        val, its = ranked[0]
        votes = len({pi for pi, _ in its})
        it = dict(its[0][1])
        if votes >= 2:
            it["confidence"] = "majority"
            n_major += 1
        elif raw_nums.get(round(abs(val), 1)):
            it["confidence"] = "raw-corroborated"
            n_corr += 1
        else:
            it["confidence"] = "single-pass"  # kept for coverage, marked
            n_single += 1
        merged.append(it)
    ties = []
    seen_t = set()
    for p in passes:
        for t in p.get("ties", []):
            d = t.get("desc", "")
            if d not in seen_t:
                seen_t.add(d)
                ties.append(t)
    digest = {"items": merged, "ties": ties,
              "units": passes[0].get("units"), "currency": passes[0].get("currency"),
              "sign_convention": passes[0].get("sign_convention"),
              "missing": sorted({m for p in passes for m in p.get("missing", [])}),
              "bridge": max((p.get("bridge") or [] for p in passes), key=len),
              "_digest": True,
              "_sig": sig,
              "_passes": PASSES,
              "_confidence": {"majority": n_major, "raw_corroborated": n_corr,
                              "single_pass": n_single}}
    out = Path(out_path)
    out.write_text(json.dumps(digest, indent=1))
    print(f"[D2] digest frozen -> {out} ({len(merged)} items: {n_major} majority, "
          f"{n_corr} raw-corroborated, {n_single} single-pass; {len(ties)} ties)",
          flush=True)
    return digest


def load_if_valid(company_dir, period, sig):
    """Return the frozen digest when present and signed for these exact PDFs."""
    p = Path(company_dir) / "disclosures" / period / "digest.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    if d.get("_sig") != sig:
        print(f"[D] digest present but stale (PDFs/prompt/model changed) — ignoring",
              flush=True)
        return None
    return d
