"""The packet queue — the deterministic layer publishes the work; the agent
thinks inside it (REDESIGN.md, council 2026-08-18).

A packet is a bounded unit of analyst work derived from the workbook
ITSELF — its sheets, its open cells, its failing checks — never from
per-company logic and never from the agent's wanderlust:

    compile:<sheet>       fill that sheet's open target-column inputs
    residual:<Sheet!row>  explain one failing check
    repair:<law>          one Police finding group
    deliver               finish honestly (pre-finish auto-flags run)

State slicing: each packet carries ONLY what its work needs — the open
rows with their labels/priors and a small evidence slice per row. The
full history, other sheets, and law books do not exist here.
"""
import re

from .labels import resolve_label
from .checks import prior_column, scorecard, year_columns
from .ledger import JOIN_FACES
from .numerics import SCALES, kinship, row_tol, to_model_units

MAX_ROWS_PER_CALL = 18        # small enough that the engine's attention
                              # covers every row it signs (test-7 law)
MAX_EVIDENCE_PER_ROW = 2


# a bare numeric literal inside a formula (never part of a cell ref like
# I10 or a range I10:I12) — the EMBEDDED HARDCODE class the owner's
# mindmap names as key drivers ("hardcodes / embedded hardcodes")
EMBEDDED_RE = re.compile(r"(?<![A-Za-z0-9_.:$])\d+(?:\.\d+)?")
EMBEDDED_MIN = 100.0          # disclosed-figure territory; spares /12, *1.05




def _sum_covered(ws, tcol, _cache={}):
    """Rows of the target column consumed by some SUM range on the sheet
    (a blank cell nothing sums is a subheader, not an input)."""
    key = (id(ws), tcol)
    if key in _cache:
        return _cache[key]
    covered = set()
    for row in ws.iter_rows():
        for c in row:
            v = c.value
            if isinstance(v, str) and v.startswith("=") and tcol in v:
                for m in re.finditer(
                        rf"{tcol}(\d+):{tcol}(\d+)", v.replace("$", "")):
                    a, b = int(m.group(1)), int(m.group(2))
                    if 0 < b - a <= 120:
                        covered.update(range(a, b + 1))
    _cache[key] = covered
    return covered


def open_rows(wb, spec, ty, sheet, served, writer_log):
    """The sheet's open work: target-column numeric inputs no proven write
    has replaced (the stale candidates), in row order — PLUS formula
    cells carrying embedded numeric constants (run-28 owner review: a
    formula like =16602.97-J11 is an input wearing a formula costume; the
    census that only saw numeric cells made this whole class invisible,
    so it was never updated and never flagged)."""
    tcol = year_columns(spec, sheet).get(ty)
    pcol = prior_column(spec, sheet, ty)
    if not tcol or sheet not in wb.sheetnames:
        return []
    written = set(writer_log.get("written") or [])
    rebased = set(writer_log.get("rebased") or [])
    out = []
    ws = wb[sheet]
    # BLOCK HEADERS (SoC class, 2026-08-20): a model row's own label can
    # be generic ("Closing balance", "Total") — the ACCOUNT'S name lives
    # in the text-only header above it (all year cells empty). The block
    # name travels with the row: it is how the analyst knows WHAT a
    # generic-labelled row is, and how evidence can name-match it.
    _yc_all = list((year_columns(spec, sheet) or {}).values())
    blocks, _cur_blk = {}, None
    for r in range(1, ws.max_row + 1):
        lab_b = next((ws[f"{lc}{r}"].value for lc in ("A", "B", "C", "D")
                      if isinstance(ws[f"{lc}{r}"].value, str)
                      and ws[f"{lc}{r}"].value.strip()), None)
        if lab_b and all(ws[f"{yc}{r}"].value is None for yc in _yc_all):
            _cur_blk = str(lab_b).strip()[:40]
        blocks[r] = _cur_blk
    numeric_rows = sorted(r for r in range(1, ws.max_row + 1)
                          if isinstance(ws[f"{tcol}{r}"].value, (int, float)))
    lo = numeric_rows[0] if numeric_rows else 0
    hi = numeric_rows[-1] if numeric_rows else -1
    for r in range(1, ws.max_row + 1):
        v = ws[f"{tcol}{r}"].value
        emb = None
        pattern = None
        if isinstance(v, str) and v.startswith("="):
            emb = [float(x) for x in EMBEDDED_RE.findall(v)
                   if abs(float(x)) >= EMBEDDED_MIN]
            pv_c = ws[f"{pcol}{r}"].value if pcol else None
            if not emb and isinstance(pv_c, (int, float)):
                # MARK-TO-ACTUAL RECIPE (the prior cell's TYPE wins): a
                # forecast formula sitting where the actual belongs, with
                # a HARDCODE prior, is an INPUT — the actual replaces the
                # formula. (DFE Driver!J7 = I7*(1+growth): invisible to
                # every census until now.)
                row = {"row": r, "cell": f"{sheet}!{tcol}{r}",
                       "label": "", "value": v, "prior": pv_c,
                       "overwrite": True}
                row["label"] = resolve_label(wb, sheet, r)[:48]
                if blocks.get(r) and blocks[r] != row["label"]:
                    row["block"] = blocks[r]
                if (sheet, r) not in served                         and f"{sheet}!{tcol}{r}" not in written:
                    out.append(row)
                continue
            if not emb:
                # THE PATTERN ROW (CLP + owner's DFE driver ruling): the
                # PRIOR actual cell may hold the input pattern —
                # '=4976+23', a printed figure plus an analyst adjustment
                # — while the target holds a roll/forecast formula. The
                # prior's TYPE is the pattern (mark-to-actual recipe);
                # its constant anchors the last-year map.
                pv_cell = ws[f"{pcol}{r}"].value if pcol else None
                if isinstance(pv_cell, str) and pv_cell.startswith("="):
                    p_emb = [float(x) for x in EMBEDDED_RE.findall(pv_cell)
                             if abs(float(x)) >= EMBEDDED_MIN]
                    if p_emb:
                        emb, pattern = p_emb, pv_cell
                if not emb:
                    continue
        elif v is None:
            # THE NEW-LINE CLASS (owner ruling 2026-08-19): a row blank
            # last year and printed this year is completely normal.
            # SUBHEADER LAW (CLP first flight, owner): a subheader has NO
            # numbers in ANY year and nothing sums it — only rows with
            # previous numbers, forecasts, or a consuming SUM range are
            # inputs. Both tests are structural, not linguistic.
            pv0 = ws[f"{pcol}{r}"].value if pcol else None
            import bisect as _b
            i = _b.bisect_left(numeric_rows, r)
            near = any(0 <= j < len(numeric_rows)
                       and abs(numeric_rows[j] - r) <= 2
                       for j in (i - 1, i))
            lab0 = resolve_label(wb, sheet, r) or blocks.get(r)
            year_cols = list((year_columns(spec, sheet) or {}).values())
            has_any_year = any(
                isinstance(ws[f"{yc}{r}"].value, (int, float))
                for yc in year_cols)
            # CLP run-4 lesson: SUM ranges SPAN header rows, so in-SUM
            # alone admits section headers — the agent wrote group
            # figures into them. A blank row with NO number in ANY year
            # is NEVER agent work: only the machine may fill it
            # (new_line_serves: name-exact + closure-proven). The agent
            # sees blank rows only when some year holds a number.
            if not (lab0 and pv0 is None and lo <= r <= hi and near
                    and has_any_year):
                continue
        elif not isinstance(v, (int, float)):
            continue
        if (sheet, r) in served or f"{sheet}!{tcol}{r}" in written \
                or f"{sheet}!{r}" in rebased:
            continue
        pv = ws[f"{pcol}{r}"].value if pcol else None
        lab = resolve_label(wb, sheet, r)
        row = {"row": r, "cell": f"{sheet}!{tcol}{r}",
               "label": str(lab)[:48], "value": v,
               "prior": pv if isinstance(pv, (int, float)) else None}
        if blocks.get(r) and blocks[r] != row["label"]:
            row["block"] = blocks[r]
        if emb:
            row["embedded"] = emb
            if pattern:
                row["pattern"] = pattern
            if row["prior"] is None:
                # the constant IS last year's figure — it anchors the
                # last-year map and sightings exactly like a prior
                row["prior"] = emb[0]
        out.append(row)
    return out


def derive_queue(wb, spec, ty, served, writer_log):
    """The queue, keys-first: compile packets for sheets with open work
    (sheets carrying key rows first, most keys first), then residual
    packets per failing check, then deliver."""
    key_count = {}
    for k in spec.get("key_rows") or []:
        key_count[k["sheet"]] = key_count.get(k["sheet"], 0) + 1
    compiles = []
    for sheet in (spec.get("year_axis") or {}):
        n_open = len(open_rows(wb, spec, ty, sheet, served, writer_log))
        if n_open:
            compiles.append((key_count.get(sheet, 0), n_open, sheet))
    compiles.sort(key=lambda x: (-x[0], -x[1]))
    queue = [f"compile:{sheet}" for _k, _n, sheet in compiles]
    card = scorecard(wb, spec, ty, served=served,
                     flags=writer_log.get("flags"))
    seen = set()
    for c in card["checks"]:
        if c["status"] == "PASS":
            continue
        name = c["name"].split(" (")[0].replace("!r", "!")   # Model!95
        if name not in seen:
            seen.add(name)
            queue.append(f"residual:{name}")
    queue.append("deliver")
    return queue


def evidence_slice(ledger, row, max_hits=MAX_EVIDENCE_PER_ROW,
                   home=frozenset()):
    """Up to N candidate disclosure lines for one open row: prior-tie
    first (number-anchored — the reliable signal), then label kinship.

    HOME pages outrank everything (SoC class, 2026-08-20): a prior like
    80 ties dozens of junk lines across a 300-page report, and the cap
    fills in page order before the real statement line is reached. Lines
    from the sheet's own statement pages are scanned FIRST."""
    pv = row.get("prior")
    hits, seen = [], set()
    prior_docs = ledger.prior_period_docs()

    def add(it, why):
        key = (it.doc, it.page, it.source_line[:40])
        if key in seen:
            return
        seen.add(key)
        hits.append(f"p{it.page} [{why}] {it.source_line[:100]}")

    def sweep(pool, why):
        if not (isinstance(pv, (int, float)) and abs(pv) >= 1.0):
            return
        tol = row_tol(pv)
        for it in pool:
            if it.doc in prior_docs or not it.joinable():
                continue
            if any(abs(abs(to_model_units(n, s)) - abs(pv)) <= tol
                   for n in it.nums for s in SCALES):
                add(it, why)
            if len(hits) >= max_hits:
                return

    if home:
        sweep([it for it in ledger.items if (it.doc, it.page) in home],
              "prior-tie|sheet's own statement page")
    if len(hits) < max_hits:
        sweep(ledger.items, "prior-tie")
    if len(hits) >= max_hits:
        return hits
    for it in ledger.items:
        if it.doc in prior_docs or not it.joinable():
            continue
        if kinship(row["label"], it.label):
            add(it, "label-kin")
        if len(hits) >= max_hits:
            break
    # BLOCK-NAME fallback (SoC class): a generic row label ("Closing
    # balance") can never name-match its printed line — the account's
    # name is the BLOCK header ("Fuel Clause Recovery" finds the
    # statement's "Fuel clause account" line). Only when nothing else
    # matched: the direct label stays the stronger signal.
    if not hits and row.get("block"):
        for it in ledger.items:
            if it.doc in prior_docs or not it.joinable():
                continue
            if kinship(row["block"], it.label):
                add(it, "block-kin: the row's section header names it")
            if len(hits) >= max_hits:
                break
    return hits


YEAR_RUN_RE = re.compile(r"((?:19|20)\d{2})\D{1,8}((?:19|20)\d{2})"
                         r"\D{1,8}((?:19|20)\d{2})")


PROSE_AMT_RE = re.compile(r"\d[\d,.]*\s*[亿億万萬]元")


def prose_digest(ledger, cap=12):
    """OPERATING PROSE (overnight 2026-08-25, the new-orders block): CN
    reports print operating data in SENTENCES (新增生效订单654.85亿元，
    同比增长16.78%…板块占37.59%) — table-anchored evidence never sees
    them, and when the model's own prior basis differs there is no
    number bridge either. The digest hands the agent the amount-bearing
    sentences; translation and %-decomposition are its judgment."""
    prior_docs = ledger.prior_period_docs()
    cands = []
    seen = set()
    for it in ledger.items:
        if it.doc in prior_docs:
            continue
        sl = str(it.source_line or "")
        if not PROSE_AMT_RE.search(sl):
            continue
        key = sl[:60]
        if key in seen:
            continue
        seen.add(key)
        cands.append((len(sl), it.page, sl))
    cands.sort(key=lambda x: -x[0])          # sentences beat table rows
    if not cands:
        return ""
    lines = ["-- OPERATING PROSE (amount-bearing sentences; 亿元 = x100 "
             "into a millions model; a TOTAL with segment percentages "
             "decomposes as total x pct) --"]
    for _l, page, sl in cands[:cap]:
        lines.append(f"  p{page}: {sl[:150]}")
    return "\n".join(lines)


def home_pages(wb, spec, ty, sheet, ledger, min_hits=4, cap=3,
               targets=None):
    """THE SHEET'S OWN STATEMENT (SoC class, 2026-08-20): a page where
    MANY of the sheet's prior-column values print together IS the
    schedule this sheet models — whatever the page calls itself, in any
    language (a Scheme-of-Control statement, a five-year statistics
    table, a regulated-business schedule). Discovered by number mass,
    never by caption. Returns [(doc, page, n_distinct_priors_tied)]."""
    pcol = prior_column(spec, sheet, ty)
    if not pcol or sheet not in wb.sheetnames:
        return []
    ws = wb[sheet]
    uniq = []

    def _take(v):
        if isinstance(v, (int, float)) and abs(v) >= 1.0:
            if not any(abs(v - q) <= 0.01 for q in uniq):
                uniq.append(float(v))
    for r in range(1, min(ws.max_row, 400) + 1):
        _take(ws[f"{pcol}{r}"].value)
    # a DERIVED schedule's prior column is mostly formulas — the sheet's
    # evaluated priors (targets) carry the mass the raw cells cannot
    for t in (targets or {}).values() if isinstance(targets, dict) \
            else (targets or []):
        if getattr(t, "sheet", None) == sheet:
            _take(getattr(t, "prior_value", None))
    if len(uniq) < min_hits:
        return []
    prior_docs = ledger.prior_period_docs()
    # ENTITY QUARANTINE APPLIES (DFE run 37: the PARENT-company statement
    # pages mass-tie the group's priors too — near-identical magnitudes —
    # and home serves shifted parent figures into group rows). A page the
    # quarantine evicted can never be a sheet's home.
    parent = getattr(ledger, "parent_pages", None) or set()
    tied = {}
    for it in ledger.items:
        if it.doc in prior_docs or not it.nums \
                or (it.doc, it.page) in parent:
            continue
        for j, p in enumerate(uniq):
            tol = row_tol(p)
            if any(abs(abs(to_model_units(n, s)) - abs(p)) <= tol
                   for n in it.nums for s in SCALES):
                tied.setdefault((it.doc, it.page), set()).add(j)
    scored = sorted(((len(js), doc, page)
                     for (doc, page), js in tied.items()
                     if len(js) >= min_hits), key=lambda x: -x[0])
    # a multi-statement sheet (P&L+BS+CF in one) masses priors across
    # more pages than a single schedule — the cap scales with the mass
    # (CLP run 8: Final's cap of 3 dropped the BS first page itself)
    cap = max(cap, min(6, 2 + len(uniq) // 40))
    return [(doc, page, n) for n, doc, page in scored[:cap]]


def home_transcript(ledger, homes, ty, cap_lines=44):
    """Render the sheet's own statement pages, top-to-bottom in printed
    order, with a year-run column note when the page is a multi-year
    summary. The agent reads it like an analyst reads the schedule."""
    if not homes:
        return ""
    out = []
    for doc, page, n in homes:
        items = sorted((it for it in ledger.items
                        if it.doc == doc and it.page == page),
                       key=lambda it: it.row_ord)
        if not items:
            continue
        years = None
        for it in items[:8]:
            m = YEAR_RUN_RE.search(it.source_line)
            if m:
                years = m.group(0)
                break
        head = (f"-- THIS SHEET'S OWN STATEMENT — p{page} of {doc[:28]} "
                f"prints {n} of this sheet's prior-year values together: "
                f"it is the schedule this sheet models. Read it "
                f"top-to-bottom; transcription-first applies. --")
        if years:
            head += (f"\n   (columns are YEARS: {years} ... — your value "
                     f"is the {ty} column; the neighbouring year column "
                     f"must reproduce this sheet's priors. A prior that "
                     f"does NOT tie means the definition moved — the "
                     f"counterpart law applies: WRITE the {ty} column's "
                     f"value with a red flag noting both priors; leaving "
                     f"the row stale because the prior moved is the one "
                     f"wrong answer.)")
        lines = [head]
        seen = set()
        for it in items[:cap_lines]:
            sl = it.source_line[:104]
            if sl in seen:
                continue
            seen.add(sl)
            lines.append(f"  {sl}")
        out.append("\n".join(lines))
    return "\n\n".join(out)




def matrix_snippets(docs, rows, cap_pages=2):
    """Position-true matrix grids for the card (CLP diff class 1: agent
    fallback on refused matrix rows read flat text and grabbed the wrong
    region's column). Pages whose grids anchor any open row's prior are
    rendered with explicit column indices and the anchored column marked
    — the agent reads columns, not neighbouring digits."""
    from pathlib import Path as _P
    from .islands import matrix_grids
    priors = [r.get("prior") for r in rows
              if isinstance(r.get("prior"), (int, float))
              and abs(r.get("prior")) > 1.0]
    if not priors or not docs:
        return ""
    out = []
    for d in docs:
        if len(out) >= cap_pages:
            break
        try:
            import pdfplumber
            with pdfplumber.open(d) as pdf:
                npages = len(pdf.pages)
        except Exception:
            continue
        # cheap: only scan pages we can anchor — try the whole doc is too
        # slow; use a pre-pass grid on a sample? Instead: grids for pages
        # discovered lazily by the caller via ledger would be better; here
        # we accept a modest scan of up to 40 mid-document pages.
        candidates = list(range(1, min(npages, 300) + 1))
        grids = matrix_grids(d, candidates[:0])   # placeholder, filled below
        # anchor-scan in chunks to bound cost
        found = {}
        for start in range(1, min(npages, 300), 60):
            g = matrix_grids(d, list(range(start, min(start + 60,
                                                      npages + 1))))
            for pno, rws in g.items():
                score = 0
                marks = {}
                for lab, vals in rws:
                    for j, v in enumerate(vals):
                        if v is None:
                            continue
                        for pv in priors:
                            if abs(abs(v) - abs(pv)) <= max(0.6,
                                                            abs(pv) * 2e-5):
                                score += 1
                                marks[j] = marks.get(j, 0) + 1
                if score >= 3:
                    found[pno] = (score, rws, marks)
            if len(found) >= cap_pages:
                break
        for pno, (score, rws, marks) in sorted(
                found.items(), key=lambda x: -x[1][0])[:cap_pages]:
            col_star = max(marks, key=marks.get) if marks else None
            lines = [f"-- MATRIX GRID {_P(d).name[:24]} p{pno} — columns "
                     f"are REGIONS/CATEGORIES; your rows' priors anchor "
                     f"column {col_star + 1 if col_star is not None else '?'}"
                     f" — read THAT column only --"]
            for lab, vals in rws[:24]:
                cells = " | ".join(
                    (f"[{v:,.1f}]" if j == col_star and v is not None else
                     f"{v:,.1f}" if v is not None else "–")
                    for j, v in enumerate(vals))
                lines.append(f"  {lab[:34]:36s} {cells}")
            out.append("\n".join(lines))
    return "\n\n".join(out)


def compile_card(wb, spec, ty, sheet, served, writer_log, ledger, docs=(),
                 targets=None, adjustments=None):
    """The compile packet's whole world: the open column, in order, each
    row with its label, prior, current (stale) value, and evidence slice.
    Returned as chunks the engine can hold.

    Evidence is NUMBER-ANCHORED first (prior-tie, implied-prior) because
    labels die across languages (run-11: an English 'Gas Turbine' row can
    never label-match 燃气轮机 — but last year's number, or the implied
    prior from a 同比%, is language-free)."""
    rows = open_rows(wb, spec, ty, sheet, served, writer_log)
    from .ops import implied_prior_candidates

    class _T:
        pass
    tl = []
    for r in rows:
        t = _T()
        t.sheet, t.row, t.key = sheet, r["row"], (sheet, r["row"])
        t.label, t.prior_value = r["label"], r.get("prior")
        tl.append(t)
    ip = {}
    try:
        for c in implied_prior_candidates(wb, spec, ty, tl, ledger, served,
                                          lambda s: None):
            ip[c["row"]] = c
    except Exception:
        ip = {}
    try:
        pm = prior_map_hints(ledger, rows)
    except Exception:
        pm = {}
    try:
        cs = current_sightings(ledger, rows)
    except Exception:
        cs = {}
    try:
        homes = home_pages(wb, spec, ty, sheet, ledger, targets=targets)
        home_set = frozenset((d, p) for d, p, _n in homes)
        home_block = home_transcript(ledger, homes, ty)
    except Exception:
        home_set, home_block = frozenset(), ""
    try:
        prose_block = prose_digest(ledger)
    except Exception:
        prose_block = ""
    chunks = []
    for i in range(0, len(rows), MAX_ROWS_PER_CALL):
        chunk = rows[i:i + MAX_ROWS_PER_CALL]
        lines = [f"SHEET: {sheet}   TARGET YEAR: {ty}   "
                 f"open rows {i + 1}-{i + len(chunk)} of {len(rows)}"]
        for r in chunk:
            _row_start = len(lines)
            _dl = (f"{r['block']} › {r['label']}" if r.get("block")
                   else r["label"])
            if r.get("pattern"):
                lines.append(
                    f"{r['cell']} '{_dl}' | the PRIOR actual cell "
                    f"holds the INPUT PATTERN {str(r['pattern'])[:44]} — a "
                    f"disclosed figure, possibly plus an analyst "
                    f"adjustment (constants: "
                    + ", ".join(f"{c:,.2f}" for c in r["embedded"])
                    + "). Mark-to-actual: REPLICATE the pattern for THIS "
                      "year — find this year's counterpart of the "
                      "disclosed constant (the hints below locate where "
                      "it lived last year; find the SAME section in the "
                      "current report), infer whether the adjustment "
                      "carries (its logic, per the model), and respond "
                      "{\"cell\": ..., \"pattern_formula\": "
                      "\"=<new constant>+<adjustment>\", \"why\": "
                      "\"p..\"}; flag if the adjustment's logic is "
                      "uncertain.")
            elif r.get("embedded"):
                lines.append(
                    f"{r['cell']} '{_dl}' | FORMULA "
                    f"{str(r['value'])[:48]} with EMBEDDED CONSTANT(S) "
                    + ", ".join(f"{c:,.2f}" for c in r["embedded"])
                    + " — each constant is LAST YEAR'S disclosed figure "
                      "(its value is your search key; the hints below "
                      "locate it). Find THIS year's counterpart and "
                      "respond with swap_constant; if its category no "
                      "longer exists this year, flag the cell as a "
                      "structurally obsolete driver.")
            elif r["value"] is None:
                lines.append(
                    f"{r['cell']} '{_dl}' | BLANK last year — a NEW "
                    f"line this year is completely normal and MUST be "
                    f"mapped or the statement will not balance. Read the "
                    f"evidence under this row: if ANY line shows a "
                    f"current-year value for this name, WRITE it (in the "
                    f"MODEL'S units — match your neighbours' magnitude; "
                    f"the disclosure prints raw currency). BUT first check "
                    f"the SIBLING rows: if the printed line already lives "
                    f"in a neighbouring row (the model splits one printed "
                    f"line across two named rows), this blank row is "
                    f"genuinely absent this year — never write the same "
                    f"printed line into two rows. Only respond "
                    f"not_disclosed if the evidence is empty and the "
                    f"statement truly lacks the line — never silently "
                    f"skip a blank statement row.")
            elif r.get("overwrite"):
                ruled = f"{sheet}!{r['row']}" in (
                    writer_log.get("rebased_ruled") or [])
                lines.append(
                    f"{r['cell']} '{_dl}' | prior (hardcode) "
                    f"{r['prior']:,.2f} | this year holds a FORECAST "
                    f"formula {str(r['value'])[:36]} — mark-to-actual "
                    f"REPLACES it with the disclosed actual (the prior "
                    f"cell's TYPE is the pattern); write the value"
                    + (" | RECLASSIFIED block (owner law): map the "
                       "members the re-cut left unchanged; back out the "
                       "changed ones (=total-SUM(mapped), backout true); "
                       "never the re-based category value." if ruled
                       else ""))
            elif isinstance(r["prior"], (int, float)):
                ruled = f"{sheet}!{r['row']}" in (
                    writer_log.get("rebased_ruled") or [])
                lines.append(
                    f"{r['cell']} '{_dl}' | prior {r['prior']:,.2f} "
                    f"| currently STALE at {r['value']:,.2f}"
                    + (" | RECLASSIFIED block (owner law): the prior "
                       "year stays untouched. Map the members whose "
                       "priors still bridge; for a changed member, BACK "
                       "OUT (=<total>-SUM(<mapped members>), submit as "
                       "pattern_formula with backout true) and it will "
                       "be orange-flagged for the analyst. NEVER write "
                       "the re-based category's own value into this row."
                       if ruled else ""))
            else:
                lines.append(
                    f"{r['cell']} '{_dl}' | no prior | "
                    f"currently {r['value']:,.2f}")
            c = ip.get(f"{sheet}!{r['row']}")
            if c:
                lines.append(
                    f"    p{c['page']} [implied-prior] current "
                    f"{c['value']:,.2f} with {c['pct']:+.2f}% reproduces "
                    f"this row's prior — {c['cite'][:70]}")
            for h in evidence_slice(ledger, r, home=home_set):
                lines.append(f"    {h}")
            for h in pm.get(r["cell"], []):
                lines.append(f"    [{h}] — find this line's counterpart "
                             "in the CURRENT report")
            for h in cs.get(r["cell"], []):
                lines.append(f"    [{h}]")
            r["card"] = "\n".join(lines[_row_start:])
            adj = next((a for a in (adjustments or [])
                        if a.get("row") == f"{sheet}!{r['row']}"), None)
            if adj:
                lines.append(
                    f"    [INFERRED ANALYST ADJUSTMENT] the model's prior "
                    f"({adj['model_prior']:,.2f}) does not equal the "
                    f"filing's prior print ({adj['disclosed_prior']:,.2f}) "
                    f"— the analyst adjusts this row (their own netting/"
                    f"carve-out). Do NOT write the raw print clean: either "
                    f"replicate the adjustment logic (the sheet's nearby "
                    f"sub-rows usually carry it) or write with a RED flag "
                    f"naming both numbers. {adj['cite'][:80]}")
        if home_block:
            lines.append("")
            lines.append(home_block)
        if prose_block:
            lines.append("")
            lines.append(prose_block)
        chunks.append("\n".join(lines))
    # TABLE ISLANDS (council wall-1 design): intact grids, selected
    # number-anchored on this packet's own priors. The agent reads the
    # grid natively — cross-language by reading. Attached to every chunk.
    if docs and rows:
        try:
            from pathlib import Path as _P
            from . import islands as islands_mod
            open_priors = [r.get("prior") for r in rows]
            prior_names = set(ledger.prior_period_docs())
            n_dark = sum(1 for r in rows
                         if f"{sheet}!{r['row']}" not in ip)
            picked = []               # (tag, page, text)
            for d in docs:
                tag = ("PRIOR-YEAR" if _P(d).name in prior_names
                       else "CURRENT")
                isl_d = islands_mod.extract(d)
                # PRIOR-YEAR islands are the MAP (owner's cross-report
                # method): last year's report prints the model's own
                # basis, so number-anchored selection ties them hard.
                sel = islands_mod.relevant(
                    isl_d, open_priors,
                    cap=2 if tag == "PRIOR-YEAR" else 3)
                picked += [(tag, p, t) for p, t in sel]
                # SEGMENT-SHAPED channel (owner ruling): where numbers
                # cannot anchor, the agent maps by MEANING — it just
                # needs to SEE the table (both vintages).
                if n_dark >= 5:
                    have = {(tag, p) for tag, p, _t in picked}
                    picked += [(tag, p, t) for p, t in
                               islands_mod.revenue_shaped(isl_d, cap=2)
                               if (tag, p) not in have]
            picked = picked[:7]
            # THE STATEMENTS as ordered reading material (owner issue 1):
            # a statement-transcription sheet needs the statements, not
            # snippets. Attached to every compile card with open work.
            served_priors = {t.prior_value for t in tl
                             if (t.sheet, t.row) in served
                             and isinstance(t.prior_value, (int, float))
                             and abs(t.prior_value) >= 1.0}
            # also every prior of rows already written on this sheet
            stmt = statement_transcript(ledger,
                                        served_priors=served_priors)
            if stmt:
                chunks = [c + "\n\n== THE STATEMENTS — ordered, read "
                          "top-to-bottom; rows that ARE statement lines "
                          "transcribe from HERE at full precision, in "
                          "order ==\n" + stmt for c in chunks]
            try:
                msnip = matrix_snippets(docs, rows)
            except Exception:
                msnip = ""
            if msnip:
                chunks = [c + "\n\n== MATRIX GRIDS (position-true; the "
                          "marked column is yours) ==\n" + msnip
                          for c in chunks]
            if picked:
                block = ("\n\n== TABLE ISLANDS — intact grids from the "
                         "disclosures (headers attached to every value; "
                         "read them like the printed table; a value + its "
                         "同比% reproducing a row's prior identifies the "
                         "row across languages, and a TRANSLATED label "
                         "naming the same business is the same row — map "
                         "by meaning, cite the island page and row label. "
                         "PRIOR-YEAR islands are your MAP: last year's "
                         "report prints the model's own basis — locate "
                         "each row there, then find the CURRENT report's "
                         "corresponding line/category and write THIS "
                         "year's value citing the CURRENT report. If the "
                         "current disclosure re-based its categories and "
                         "no defensible bridge exists, flag with a bridge "
                         "note instead of forcing) ==\n"
                         + "\n\n".join(f"-- ISLAND {tag} p{p} --\n{t}"
                                       for tag, p, t in picked))
                chunks = [c + block for c in chunks]
        except Exception:
            pass
    return rows, chunks


def prior_map_hints(ledger, rows, cap_per_row=1):
    """THE LAST-YEAR MAP (owner ruling, run 23): the prior report prints
    the model's own numbers with their labels and sections — find each
    open row's PRIOR VALUE in the prior-year document (number-anchored,
    trivially reliable: it is the same number) and hand the agent the
    location as a map: 'your row lived HERE last year — find this line's
    counterpart in the current report.'

    RUN-24 EXTENSION — the map now WALKS ACROSS: for each last-year hit,
    locate the CURRENT report's counterpart section (the current-doc
    table sharing the most row labels with the last-year table) and the
    matched row inside it. When the counterpart's comparative no longer
    ties the model's prior, the disclosure RE-BASED its categories — the
    owner's analyst method applies: take the current-year value from the
    counterpart row, and RED-flag the comparative mismatch (both figures
    in the note). Stale is not an option when the counterpart is found."""
    from .numerics import norm_label
    prior_docs = ledger.prior_period_docs()
    if not prior_docs:
        return {}

    def _norm(lab):
        return norm_label(lab or "").replace(" ", "")

    # one pass: index tables of both vintages by (doc, page, table_id)
    cur_tables, pri_tables = {}, {}
    for it in ledger.items:
        tid = getattr(it, "table_id", None)
        if tid is None or not it.label:
            continue
        d = pri_tables if it.doc in prior_docs else cur_tables
        d.setdefault((it.doc, it.page, tid), []).append(it)
    cur_labelsets = {k: {_norm(i.label) for i in v} - {""}
                     for k, v in cur_tables.items()}

    out = {}
    for row in rows:
        pv = row.get("prior")
        if not isinstance(pv, (int, float)) or abs(pv) < 1.0:
            continue
        tol = max(0.6, abs(pv) * 5e-4)          # identity grade
        hits = []
        for it in ledger.items:
            # a location HINT tolerates messy labels the join would
            # refuse (run-24: the FY24 anchor for a segment row carried a
            # truncated one-character vision label) — disputed items only
            # are excluded
            if (it.doc not in prior_docs or not it.nums
                    or getattr(it, "disputed", False)):
                continue
            if not any(abs(abs(to_model_units(n, s)) - abs(pv)) <= tol
                       for n in it.nums for s in SCALES):
                continue
            hint = f"LAST-YEAR report p{it.page}: {it.source_line[:90]}"
            src = pri_tables.get((it.doc, it.page,
                                  getattr(it, "table_id", None))) or []
            src_labels = {_norm(x.label) for x in src} - {""}
            best, bestn = None, 2               # need >= 3 shared labels
            for k, ls in cur_labelsets.items():
                n = len(ls & src_labels)
                if n > bestn:
                    best, bestn = k, n
            if best:
                match = [x for x in cur_tables[best]
                         if _norm(x.label) == _norm(it.label)]
                if match:
                    m = match[0]
                    ties = any(
                        abs(abs(to_model_units(n, s)) - abs(pv)) <= tol
                        for n in m.nums for s in SCALES)
                    hint += (f" || COUNTERPART in CURRENT report p{m.page}: "
                             f"'{m.source_line[:80]}'")
                    if not ties:
                        hint += (" — its comparative does NOT tie your "
                                 "prior: the disclosure RE-BASED this "
                                 "category. ANALYST METHOD (owner ruling): "
                                 "take the CURRENT-year value from this "
                                 "counterpart row, write it citing this "
                                 "page, and RED-flag it noting both the "
                                 "model prior and the restated comparative")
                else:
                    hint += (f" || COUNTERPART section in CURRENT report "
                             f"p{best[1]} shares {bestn} row labels with "
                             f"the last-year location, but your line's "
                             f"label is ABSENT there — the category was "
                             f"likely renamed or merged this year. Read "
                             f"that section, reason the mapping, and "
                             f"red-flag your judgment")
            hits.append(hint)
            if len(hits) >= cap_per_row:
                break
        if hits:
            out[row["cell"]] = hits
    return out


def current_sightings(ledger, rows, cap_per_row=2):
    """PRIOR-ANCHORED SIGHTINGS outside the pool (run-24: 应收股利 sat in
    a note table with an identity-grade prior beside its current value —
    invisible to the join because note pages carry no face authority).
    For each open row, current-doc lines where SOME number ties the
    row's model prior at identity grade. Observation only — the agent
    judges the line's column semantics and writes with a citation; no
    machine write ever comes from a sighting (oracles observe)."""
    from .numerics import norm_label
    prior_docs = ledger.prior_period_docs()
    out = {}
    for row in rows:
        pv = row.get("prior")
        if not isinstance(pv, (int, float)) or abs(pv) < 1.0:
            # NAME-KEYED SIGHTING for priorless rows (owner's mapping
            # order: the name says WHAT it is; a blank prior locates
            # nothing, so the name carries the search) — current-doc
            # lines whose label matches the row's exactly.
            t_norm = norm_label(str(row.get("label") or "")).replace(" ", "")
            if len(t_norm) < 3:
                continue
            hits = []
            for it in ledger.items:
                if (it.doc in prior_docs or getattr(it, "disputed", False)
                        or not it.nums):
                    continue
                if norm_label(str(it.label)).replace(" ", "") == t_norm:
                    hits.append(f"SIGHTED by NAME in CURRENT report "
                                f"p{it.page}: {it.source_line[:90]}")
                if len(hits) >= cap_per_row:
                    break
            if hits:
                out[row["cell"]] = hits
            continue
        tol = max(0.6, abs(pv) * 5e-4)
        hits = []
        for it in ledger.items:
            if (it.doc in prior_docs or getattr(it, "verified", False)
                    or getattr(it, "disputed", False) or not it.nums):
                continue
            if any(abs(abs(to_model_units(n, s)) - abs(pv)) <= tol
                   for n in it.nums for s in SCALES):
                hits.append(f"SIGHTED in CURRENT report p{it.page}: "
                            f"{it.source_line[:90]} — a number here ties "
                            f"your prior; judge what the line is (which "
                            f"column, which table), then write the "
                            f"current-year value with a citation"
                            if len(it.nums) >= 2 else
                            f"SIGHTED in CURRENT report p{it.page}: "
                            f"{it.source_line[:90]} — your row's PRIOR "
                            f"prints here alone; this locates the row — "
                            f"read the surrounding table for this year's "
                            f"value")
            if len(hits) >= cap_per_row:
                break
        if hits:
            out[row["cell"]] = hits
    return out


def statement_transcript(ledger, cap_chars=12000, per_page_cap=3000,
                         served_priors=None):
    """The STATEMENTS, ordered — the transcription source (owner issue 1:
    Fable's 100%% on the Raw tab came from reading the statements
    completely and filling in order; per-row snippets were the wrong task
    shape for a transcription tab). Current-doc face pages only, page
    order, every line as extracted (vision transcripts included)."""
    prior_docs = ledger.prior_period_docs()
    pages = sorted((d, p) for (d, p), f in ledger.faces.items()
                   if f in JOIN_FACES and d not in prior_docs)
    sp = sorted(served_priors) if served_priors else []

    def _mapped(nums):
        if not sp:
            return False
        for n in nums[1:]:
            for s in SCALES:
                a = abs(to_model_units(n, s))
                tol = max(0.6, a * 5e-4)
                i = 0
                import bisect as _b
                i = _b.bisect_left(sp, a - tol)
                if i < len(sp) and abs(sp[i] - a) <= tol:
                    return True
        return False

    out, total = [], 0
    for d, p in pages:
        lines = []
        for it in ledger.items:
            if it.doc == d and it.page == p:
                mark = "   <- mapped" if _mapped(it.nums) else ""
                lines.append(it.source_line + mark)
        if not lines:
            continue
        block = (f"== STATEMENT PAGE p{p} "
                 f"({ledger.faces[(d, p)]}) — lines marked '<- mapped' "
                 f"already landed in the model; the UNMARKED lines are "
                 f"your remaining work ==\n"
                 + "\n".join(lines))[:per_page_cap]
        if total + len(block) > cap_chars:
            break
        out.append(block)
        total += len(block)
    return "\n\n".join(out)


def more_evidence(ledger, docs, rows_needed, exclude_pages, cap_lines=4,
                  cap_islands=3):
    """The look-elsewhere answer (owner skill ruling): for rows the agent
    ASKED about, fetch material from OTHER places — doc-wide number-
    anchored text hits (notes included, face or not) and the next-ranked
    islands not yet shown. Number-anchored first; the agent judges."""
    out = []
    prior_docs = ledger.prior_period_docs()
    for row in rows_needed:
        pv = row.get("prior")
        lines = []
        if isinstance(pv, (int, float)) and abs(pv) >= 1.0:
            tol = row_tol(pv)
            for it in ledger.items:
                if it.doc in prior_docs or not it.joinable():
                    continue
                if it.page in exclude_pages:
                    continue
                if any(abs(abs(to_model_units(n, s)) - abs(pv)) <= tol
                       for n in it.nums for s in SCALES):
                    lines.append(f"p{it.page}: {it.source_line[:100]}")
                if len(lines) >= cap_lines:
                    break
        out.append((row, lines))
    islands_block = []
    try:
        from . import islands as islands_mod
        isl = []
        for d in docs:
            isl += islands_mod.extract(d)
        isl = [(p, t) for p, t in isl if p not in exclude_pages]
        priors = [r.get("prior") for r, _l in out]
        picked = islands_mod.relevant(isl, priors, cap=cap_islands)
        have = {p for p, _t in picked}
        picked += [(p, t) for p, t in islands_mod.revenue_shaped(isl, cap=2)
                   if p not in have][:1]
        islands_block = picked
    except Exception:
        pass
    parts = []
    for row, lines in out:
        parts.append(f"{row['cell']} '{row['label']}' — other places:")
        parts += [f"    {ln}" for ln in lines] or ["    (no doc-wide "
                                                   "number hits)"]
    for p, t in islands_block:
        parts.append(f"-- ADDITIONAL ISLAND p{p} --\n{t}")
    return "\n".join(parts)


def parse_packet(pid):
    """'compile:Model' -> ('compile', 'Model'); 'residual:Model!95' ->
    ('residual', 'Model!95'); 'deliver' -> ('deliver', None)."""
    if ":" not in pid:
        return pid, None
    kind, _, arg = pid.partition(":")
    return kind, arg
