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
            lab0 = next((ws[f"{lc}{r}"].value for lc in ("A", "B", "C", "D")
                         if isinstance(ws[f"{lc}{r}"].value, str)
                         and ws[f"{lc}{r}"].value.strip()), None)
            year_cols = list((year_columns(spec, sheet) or {}).values())
            has_any_year = any(
                isinstance(ws[f"{yc}{r}"].value, (int, float))
                for yc in year_cols)
            in_sum = r in _sum_covered(ws, tcol)
            if not (lab0 and pv0 is None and lo <= r <= hi and near
                    and (has_any_year or in_sum)):
                continue
        elif not isinstance(v, (int, float)):
            continue
        if (sheet, r) in served or f"{sheet}!{tcol}{r}" in written \
                or f"{sheet}!{r}" in rebased:
            continue
        pv = ws[f"{pcol}{r}"].value if pcol else None
        lab = next((ws[f"{lc}{r}"].value for lc in ("A", "B", "C", "D")
                    if isinstance(ws[f"{lc}{r}"].value, str)
                    and ws[f"{lc}{r}"].value.strip()), "")
        row = {"row": r, "cell": f"{sheet}!{tcol}{r}",
               "label": str(lab)[:48], "value": v,
               "prior": pv if isinstance(pv, (int, float)) else None}
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


def evidence_slice(ledger, row, max_hits=MAX_EVIDENCE_PER_ROW):
    """Up to N candidate disclosure lines for one open row: prior-tie
    first (number-anchored — the reliable signal), then label kinship."""
    pv = row.get("prior")
    hits, seen = [], set()
    prior_docs = ledger.prior_period_docs()

    def add(it, why):
        key = (it.doc, it.page, it.source_line[:40])
        if key in seen:
            return
        seen.add(key)
        hits.append(f"p{it.page} [{why}] {it.source_line[:100]}")

    if isinstance(pv, (int, float)) and abs(pv) >= 1.0:
        tol = row_tol(pv)
        for it in ledger.items:
            if it.doc in prior_docs or not it.joinable():
                continue
            if any(abs(abs(to_model_units(n, s)) - abs(pv)) <= tol
                   for n in it.nums for s in SCALES):
                add(it, "prior-tie")
            if len(hits) >= max_hits:
                return hits
    for it in ledger.items:
        if it.doc in prior_docs or not it.joinable():
            continue
        if kinship(row["label"], it.label):
            add(it, "label-kin")
        if len(hits) >= max_hits:
            break
    return hits


def compile_card(wb, spec, ty, sheet, served, writer_log, ledger, docs=()):
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
    chunks = []
    for i in range(0, len(rows), MAX_ROWS_PER_CALL):
        chunk = rows[i:i + MAX_ROWS_PER_CALL]
        lines = [f"SHEET: {sheet}   TARGET YEAR: {ty}   "
                 f"open rows {i + 1}-{i + len(chunk)} of {len(rows)}"]
        for r in chunk:
            if r.get("pattern"):
                lines.append(
                    f"{r['cell']} '{r['label']}' | the PRIOR actual cell "
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
                    f"{r['cell']} '{r['label']}' | FORMULA "
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
                    f"{r['cell']} '{r['label']}' | BLANK last year — a NEW "
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
            elif isinstance(r["prior"], (int, float)):
                ruled = f"{sheet}!{r['row']}" in (
                    writer_log.get("rebased_ruled") or [])
                lines.append(
                    f"{r['cell']} '{r['label']}' | prior {r['prior']:,.2f} "
                    f"| currently STALE at {r['value']:,.2f}"
                    + (" | THE ANALYST HAS RULED this re-based block: the "
                       "prior year stays untouched and THIS year MUST be "
                       "written from the new partition — sub-rows first "
                       "(the 其中/of-which members map one-to-one by "
                       "meaning), parents from their own printed line or "
                       "the sum of mapped subs. Stale is NOT acceptable "
                       "here; every write keeps its red flag."
                       if ruled else ""))
            else:
                lines.append(
                    f"{r['cell']} '{r['label']}' | no prior | "
                    f"currently {r['value']:,.2f}")
            c = ip.get(f"{sheet}!{r['row']}")
            if c:
                lines.append(
                    f"    p{c['page']} [implied-prior] current "
                    f"{c['value']:,.2f} with {c['pct']:+.2f}% reproduces "
                    f"this row's prior — {c['cite'][:70]}")
            for h in evidence_slice(ledger, r):
                lines.append(f"    {h}")
            for h in pm.get(r["cell"], []):
                lines.append(f"    [{h}] — find this line's counterpart "
                             "in the CURRENT report")
            for h in cs.get(r["cell"], []):
                lines.append(f"    [{h}]")
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
