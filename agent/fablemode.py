"""Fable-mode reading: give the engine the working conditions that measured 96%.

The clean-room test proved the plateau was never the brain — it was the
harness: fragmented text lines, 40-row quizzes, 3k output caps, no images.
This pass gives the SAME engine (pure Luna) what the 96% run had:

- whole PAGES per call — the actual image for scans (CCITT mask) and for
  text pages whose tables matter (pypdfium2 render, shipped inside
  pdfplumber), plus the header-attached structured table text;
- the model's row block IN ORDER with each row's prior value beside it;
- one large-budget call per region (14k out), full printed precision;
- a self-verification CONTRACT: every answered row must also return the
  COMPARATIVE (prior-year) figure as printed. Code accepts a row only when
  that comparative ties the model's own prior — per-row checksum, the
  identification doctrine applied at read time. Rows that answer without
  tying are flagged, never trusted.

COMPLETE COVERAGE (the run-115 reflection): on the statement blocks the
LLM reads EVERYTHING — the region's row set is expanded to every census
row inside the block's span, INCLUDING rows with no prior actual (new
line items were structurally invisible to the checksum contract: 使用权
资产折旧 was never even asked). No-prior rows are served with a relaxed
contract (no checksum possible -> conf 2, red-flagged downstream, never
locked). Rows still unserved after the main pass get ONE targeted retry
with their region's page images. Whatever remains unserved is reported
so the caller can flag the hole — a flagged hole beats a machine guess.

Everything downstream (guards, flags, tie-outs, balance gate, reviewer) is
unchanged: this replaces the fragmented FIRST READ, not the verification web.
Generic by construction: pages are pages and priors are priors in any model,
any language. No values, no company logic.
"""
import base64
import io
import json
import re
from collections import defaultdict

from . import lookup, mapper, vision

MAX_ROWS_PER_CALL = 70
MAX_IMAGES_PER_CALL = 5
RENDER_DPI = 150

_SYSTEM = (
    "You are the equity research analyst marking a valuation model to actual "
    "results. You read financial statement pages exactly as printed and copy "
    "digits precisely. You never invent, round, or compute a number that is "
    "not visible."
)

_CONTRACT = """Below: (1) page images and/or table text from the company's new annual report, (2) rows from the model, IN ORDER, each with its PRIOR-year value in the model's units.

For each row, find the SAME line in the pages and return BOTH columns:

{"rows":[{"id":"<sheet>!<row>","current":"<new-year figure exactly as printed>","comparative":"<prior-year figure exactly as printed on the same line>","status":"OK"}, ...]}

- status "OK" only when you located the row's line and read both columns.
- status "NOT_HERE" when these pages do not contain that row's figure (no guessing).
- Copy digits EXACTLY as printed (separators, signs, brackets). Units on the page may differ from the model's (元/千元/万元) — return what is PRINTED; we convert.
- Rows marked "prior year: NONE (new line)" had no figure last year — read the current-year figure as printed; if the line prints a comparative, return it too, else comparative "".
- The rows are in the model's order, which usually mirrors the statement's print order — use that structure.
- The model's labels may be English for a Chinese filing — translate meaning, match by position and by the prior value when unsure.
- Scope discipline: consolidated (合并), never parent-company (母公司); the group total, never one segment, unless the row says otherwise.

Answer with the JSON only."""


def _regions(pdf_path, raw_lines):
    """Contiguous page groups worth a whole-page read: statement pages
    (scans already vision-classified + text pages carrying statement/segment
    captions) and dense table pages. Pure code, generic."""
    tagged = {}
    for pn, sec, ln in raw_lines:
        if pn in tagged:
            continue
        low = ln.lower()
        if "资产负债表" in ln or "balance sheet" in low:
            tagged[pn] = "bs"
        elif "现金流量表" in ln or "cash flow statement" in low:
            tagged[pn] = "cf"
        elif "利润表" in ln or "income statement" in low:
            tagged[pn] = "pl"
        elif "分部" in ln or "分产品" in ln or "分行业" in ln or "segment" in low:
            tagged[pn] = "segment"
        elif "产销量" in ln or sec == "table" and ("生产量" in ln or "销售量" in ln):
            tagged[pn] = "ops"
    # group tagged pages into regions, FILLING the gaps — the statements
    # block tags only its first pages (95 bs, 99 pl, 101 cf) and the untagged
    # continuation pages (96: liabilities!) must ride along (validation run:
    # the split regions never called p96/p101 and served 112 instead of ~170)
    groups = []
    for pn in sorted(tagged):
        if groups and pn - groups[-1][-1] <= 4:
            groups[-1].extend(range(groups[-1][-1] + 1, pn + 1))
        else:
            groups.append([pn])
    kinds = [{tagged[p] for p in grp if p in tagged} for grp in groups]
    return list(zip(groups, kinds))


def _page_png(pdf, pn, cache={}):
    """Page image: scans via the XObject mask, text pages via pypdfium2."""
    if pn in cache:
        return cache[pn]
    out = None
    try:
        pg = pdf.pages[pn - 1]
        txt = (pg.extract_text() or "").strip()
        if len(txt) < 200:                      # scan: the mask carries the text
            img = vision._page_image(pg)
            if img is not None:
                out = vision._prep(img, 2200)
        if out is None:
            im = pg.to_image(resolution=RENDER_DPI)
            buf = io.BytesIO()
            im.original.convert("RGB").save(buf, "PNG")
            out = ("image/png", base64.b64encode(buf.getvalue()).decode())
    except Exception:
        out = None
    cache[pn] = out
    return out


def _accept(resp, chunk, served, log_prefix, log):
    """Apply the acceptance contract to one call's response. Returns
    (n_ok, n_tie)."""
    ctx = {f"{r['sheet']}!{r['row']}": r for r in chunk}
    n_ok = n_tie = 0
    for a in resp.get("rows", []):
        rid = str(a.get("id", ""))
        r = ctx.get(rid)
        if a.get("status") != "OK" or r is None:
            continue
        n_ok += 1
        cur = vision._parse_num(a.get("current"))
        comp = vision._parse_num(a.get("comparative"))
        pv = r.get("prior_value")
        if cur is None:
            continue
        sh, rw = rid.split("!")
        if not isinstance(pv, (int, float)):
            # NO-PRIOR row: no checksum possible. Accept the read at the
            # DOCUMENT scale (page-scale aware), conf 2 -> red-flagged,
            # never locked, still band-guarded downstream.
            pg0 = (r.get("pages") or [0])
            v = mapper.to_model_units(cur, page=pg0[0] if pg0 else 0)
            served[(sh, int(rw))] = {
                "value": v, "status": "UNCERTAIN", "page": r.get("_grp0"),
                "line": f"{a.get('current')} | {a.get('comparative')}",
                "conf": 2,
                "note": "fable-mode read of a NEW line (no prior to checksum; "
                        f"printed comparative: {a.get('comparative')!r}) — verify"}
            n_tie += 1
            continue
        if comp is None:
            continue
        # the row-level checksum: the comparative must tie the
        # model's own prior at SOME standard scale; that scale
        # then converts the current figure. The tie is SIGNED:
        # comp ~ +pv means the page prints this row in the
        # model's own sign convention -> serve AS PRINTED
        # (rows may legitimately flip sign year to year: OCI,
        # FX, gains 以-号填列, working-capital moves);
        # comp ~ -pv means the page prints the opposite
        # convention (expenses positive, model negative) ->
        # serve the printed figure flipped. Never force last
        # year's sign onto this year's figure.
        for s in (1, 1e3, 1e4, 1e6, 1e8):
            # row-relative: 0.6 absorbs rounding on aggregate
            # rows; a per-share row's world is ~1 and ties at
            # 0.5% or a cent (never let 1.15 "tie" 0.94)
            tol = max(abs(pv) * 5e-3, 0.6 if abs(pv) >= 10 else 0.01)
            if abs(comp / s - pv) <= tol:
                v = cur / s
            elif abs(comp / s + pv) <= tol:
                v = -cur / s
            else:
                continue
            served[(sh, int(rw))] = {
                "value": v, "status": "OK",
                "page": r.get("_grp0"),
                "line": f"{a.get('current')} | {a.get('comparative')}",
                "conf": 5,
                "note": "fable-mode read: comparative ties "
                        "the model's prior (row checksum, signed)"}
            n_tie += 1
            break
    return n_ok, n_tie


def region_read(client, pdf_paths, all_rows, log, coverage=None):
    """-> {(sheet,row): mapped-entry}. conf 5 entries SELF-VERIFY (the
    returned comparative ties the model's own prior); conf 2 entries are
    no-prior reads (red-flag class). If `coverage` is a dict, it is filled
    with {"stmt_rows": set of (sheet,row) in statement blocks,
    "unserved": set of statement rows nothing could read}."""
    import pdfplumber
    raw_by_doc = {p: lookup.raw_lines([p]) for p in pdf_paths}
    served, answered = {}, 0
    stmt_rows = set()
    by_sheet = defaultdict(list)
    for r in all_rows:
        by_sheet[r["sheet"]].append(r)

    def _call(pdf, grp, page_text, chunk, tag):
        nonlocal answered
        from collections import Counter as _C
        pg_votes = _C(p % 1000 for r in chunk
                      for p in (r.get("pages") or [])[:3]
                      if (p % 1000) in grp)
        img_pages = [p for p, _n in pg_votes.most_common(MAX_IMAGES_PER_CALL)] \
            or grp[:MAX_IMAGES_PER_CALL]
        images = [im for pn in sorted(img_pages)
                  for im in [_page_png(pdf, pn)] if im]
        tbl_txt = "\n".join(
            f"p{pn}: {ln}" for pn in grp
            for sec, ln in page_text.get(pn, [])
            if sec in ("table", "vision"))[:8000]
        rows_txt = "\n".join(
            f"- {r['sheet']}!{r['row']}: '{str(r.get('label'))[:46]}' "
            + (f"(prior year in model units: {r['prior_value']:,.2f})"
               if isinstance(r.get("prior_value"), (int, float))
               else "(prior year: NONE (new line))")
            for r in chunk)
        user = (_CONTRACT + "\n\n[TABLE TEXT]\n" + tbl_txt
                + "\n\n[MODEL ROWS]\n" + rows_txt)

        def _val(o):
            return [] if isinstance(o.get("rows"), list) else ["missing rows"]
        try:
            resp = client.json(_SYSTEM, user, _val, repair_retries=1,
                               images=images or None)
        except Exception as ex:
            log.append(f"fable-mode{tag} p{grp[0]}-{grp[-1]}: call failed {ex}")
            return
        for r in chunk:
            r["_grp0"] = grp[0]
        n_ok, n_tie = _accept(resp, chunk, served, tag, log)
        answered += n_ok
        log.append(f"fable-mode{tag} p{grp[0]}-{grp[-1]} rows {len(chunk)}: "
                   f"{n_ok} answered, {n_tie} self-verified")

    for doc_i, pdf_path in enumerate(pdf_paths):
        raw = raw_by_doc[pdf_path]
        vlines = vision.cached_lines([pdf_path], ".cache/vision")
        groups = _regions(pdf_path, raw + vlines)
        if not groups:
            continue
        page_text = defaultdict(list)
        for pn, sec, ln in raw + vlines:
            page_text[pn].append((sec, ln))
        with pdfplumber.open(pdf_path) as pdf:
            grp_rows = []
            for grp, grp_kinds in groups:
                grp_q = {doc_i * 1000 + p for p in grp} | set(grp)
                anchored = [r for r in all_rows
                            if isinstance(r.get("prior_value"), (int, float))
                            and (set(r.get("pages") or []) & grp_q)]
                if len(anchored) < 5:
                    continue
                # COMPLETE COVERAGE, DENSITY-BOUND: expand only inside
                # CONTIGUOUS RUNS of anchored rows (gap <= 8, >= 4 anchors) —
                # the statement block reads as ONE statement including its
                # interior holes (no-prior new line items), but a sparse page
                # that anchors scattered rows may NOT claim the whole sheet
                # (live validation: a naive min..max span ballooned a 1-page
                # region to 264 rows and collapsed serving 104 -> 37).
                rows, seen = [], set()
                for sh in {r["sheet"] for r in anchored}:
                    rr = sorted(r["row"] for r in anchored if r["sheet"] == sh)
                    runs, cur_run = [], [rr[0]]
                    for x in rr[1:]:
                        if x - cur_run[-1] <= 8:
                            cur_run.append(x)
                        else:
                            runs.append(cur_run)
                            cur_run = [x]
                    runs.append(cur_run)
                    for run in runs:
                        if len(run) < 4:
                            keep = set(run)      # sparse: anchored rows only
                        else:
                            keep = set(range(run[0], run[-1] + 1))
                        for r in by_sheet[sh]:
                            if r["row"] in keep and r.get("label") \
                                    and (r["sheet"], r["row"]) not in seen:
                                rows.append(r)
                                seen.add((r["sheet"], r["row"]))
                # only bs/pl/cf regions join the machinery-ban set: on the
                # statement faces the LLM reads and code may not guess; on
                # segment/ops pages cited mapper fills still earn their keep
                if grp_kinds & {"bs", "pl", "cf"}:
                    stmt_rows |= seen
                rows.sort(key=lambda r: (r["sheet"], r["row"]))
                grp_rows.append((grp, rows))
                for i in range(0, len(rows), MAX_ROWS_PER_CALL):
                    _call(pdf, grp, page_text, rows[i:i + MAX_ROWS_PER_CALL], "")
            # TARGETED RETRY: one more focused call per region for the rows
            # the main pass could not serve — same pages, smaller ask.
            for grp, rows in grp_rows:
                left = [r for r in rows if (r["sheet"], r["row"]) not in served]
                if not left or len(left) > MAX_ROWS_PER_CALL:
                    continue
                _call(pdf, grp, page_text, left, " retry")
    if coverage is not None:
        coverage["stmt_rows"] = stmt_rows
        coverage["unserved"] = {k for k in stmt_rows if k not in served}
    log.append(f"fable-mode total: {len(served)} rows served "
               f"of {answered} answered; statement block {len(stmt_rows)} rows, "
               f"{len(stmt_rows) - len({k for k in stmt_rows if k in served})} "
               "unserved (holes -> flagged, never machine-filled)")
    return served
