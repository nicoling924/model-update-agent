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
from .numerics import SCALES, kinship, row_tol, to_model_units

MAX_ROWS_PER_CALL = 55        # a compile chunk the engine can hold
MAX_EVIDENCE_PER_ROW = 2


def open_rows(wb, spec, ty, sheet, served, writer_log):
    """The sheet's open work: target-column numeric inputs no proven write
    has replaced (the stale candidates), in row order."""
    tcol = year_columns(spec, sheet).get(ty)
    pcol = prior_column(spec, sheet, ty)
    if not tcol or sheet not in wb.sheetnames:
        return []
    written = set(writer_log.get("written") or [])
    out = []
    ws = wb[sheet]
    for r in range(1, ws.max_row + 1):
        v = ws[f"{tcol}{r}"].value
        if not isinstance(v, (int, float)):
            continue
        if (sheet, r) in served or f"{sheet}!{tcol}{r}" in written:
            continue
        pv = ws[f"{pcol}{r}"].value if pcol else None
        lab = next((ws[f"{lc}{r}"].value for lc in ("A", "B", "C", "D")
                    if isinstance(ws[f"{lc}{r}"].value, str)
                    and ws[f"{lc}{r}"].value.strip()), "")
        out.append({"row": r, "cell": f"{sheet}!{tcol}{r}",
                    "label": str(lab)[:48], "value": v,
                    "prior": pv if isinstance(pv, (int, float)) else None})
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
    chunks = []
    for i in range(0, len(rows), MAX_ROWS_PER_CALL):
        chunk = rows[i:i + MAX_ROWS_PER_CALL]
        lines = [f"SHEET: {sheet}   TARGET YEAR: {ty}   "
                 f"open rows {i + 1}-{i + len(chunk)} of {len(rows)}"]
        for r in chunk:
            lines.append(
                f"{r['cell']} '{r['label']}' | prior {r['prior']:,.2f} | "
                f"currently STALE at {r['value']:,.2f}"
                if isinstance(r["prior"], (int, float)) else
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
        chunks.append("\n".join(lines))
    # TABLE ISLANDS (council wall-1 design): intact grids, selected
    # number-anchored on this packet's own priors. The agent reads the
    # grid natively — cross-language by reading. Attached to every chunk.
    if docs and rows:
        try:
            from . import islands as islands_mod
            open_priors = [r.get("prior") for r in rows]
            isl = []
            for d in docs:
                isl += islands_mod.extract(d)
            picked = islands_mod.relevant(isl, open_priors)
            # SEGMENT-SHAPED channel (owner ruling): where numbers cannot
            # anchor (analyst-defined segmentations, cross-language), the
            # agent maps by MEANING — it just needs to SEE the table.
            n_dark = sum(1 for r in rows
                         if f"{sheet}!{r['row']}" not in ip)
            if n_dark >= 5:
                have = {p for p, _t in picked}
                picked += [(p, t) for p, t in
                           islands_mod.revenue_shaped(isl)
                           if p not in have]
            if picked:
                block = ("\n\n== TABLE ISLANDS — intact grids from the "
                         "disclosure (headers attached to every value; "
                         "read them like the printed table; a value + its "
                         "同比% reproducing a row's prior identifies the "
                         "row across languages, and a TRANSLATED label "
                         "naming the same business is the same row — map "
                         "by meaning, cite the island page and row label. "
                         "If the disclosure's segmentation genuinely "
                         "differs from the model's, flag with a bridge "
                         "note instead of forcing) ==\n"
                         + "\n\n".join(f"-- ISLAND p{p} --\n{t}"
                                       for p, t in picked))
                chunks = [c + block for c in chunks]
        except Exception:
            pass
    return rows, chunks


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
