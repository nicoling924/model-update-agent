"""THE RECONCILIATION STAGE (owner ruling 2026-09-01, after run 208:
"the agent plugged 2025 and called it a day").

The by-hand method AS the serve engine. An analyst does not serve
scattered rows — they lay a whole printed statement beside the model
and reconcile line by line. This stage walks EVERY table of every
current-document face page:

  - each printed line's (current, prior) pair is matched to model rows
    by the PRIOR (the map), giving a complete, auditable mapping table;
  - a printed line whose current EQUALS its prior CONFIRMS the model's
    unchanged value — served clean, red cleared (the owner's
    "mappable: the number didn't change vs last year");
  - the ACCEPTANCE TEST is the statement's own arithmetic: where a
    table prints a total that ties a model total-row, the served
    children must sum to it — a serve set that breaks its own printed
    total is rejected WHOLESALE (an India-taking-Australia's-number
    cannot survive, because it breaks the total it sits inside);
  - every printed line with no model home and every model row with no
    line are listed — the leftovers that name missing lines.

Generic: tables, priors, totals all come from the run's own ledger and
workbook. Runs BEFORE the scattered joins; whatever reconciliation
serves is authoritative (conf 5); the joins fill only what remains.
"""
import re
from collections import defaultdict

from .checks import prior_column, year_columns
from .evaluator import Evaluator
from .numerics import row_tol, to_model_units
from .ledger import vintage_ban as _vintage_ban

CONF_RECON = 4   # trusted, NOT locked — a new stage earns locks later
UNCHANGED_CONF = 4


def _model_prior_index(wb, spec, target_year, max_row=300):
    """Evaluated prior for every target row -> {round(pv,1): [(sheet,
    row)]}, plus per-row lookup {(sheet,row): pv}. Formula priors are
    evaluated (the no-cached-values discipline)."""
    ev = Evaluator(wb)
    homes = defaultdict(list)
    by_row = {}
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        pcol = prior_column(spec, sheet, target_year)
        if not pcol:
            continue
        hdr = (spec.get("year_axis") or {}).get(sheet, {}).get("header_row")
        ws = wb[sheet]
        for r in range(1, min(ws.max_row, max_row) + 1):
            if hdr and r == int(hdr):
                # the year-header row: its prior IS a year (2024), which a
                # printed date line ("31 December 2024") would fake-match
                continue
            v = ws[f"{pcol}{r}"].value
            if isinstance(v, str) and v.startswith("="):
                try:
                    v = ev.cell(sheet, f"{pcol}{r}")
                except Exception:
                    v = None
            if isinstance(v, (int, float)) and abs(v) >= 0.5:
                homes[round(v, 1)].append((sheet, r))
                by_row[(sheet, r)] = float(v)
    return homes, by_row


def _resolve(rows, wb, spec, target_year):
    """Multi-home priors (a D&A figure living on Driver AND SOC as
    linked twins) are resolvable when exactly ONE home is an INPUT cell
    in the target column — the formula twins just read it. Serving the
    input home serves them all."""
    if len(rows) <= 1:
        return rows
    inputs = []
    for sheet, r in rows:
        col = year_columns(spec, sheet).get(str(target_year))
        if not col:
            continue
        v = wb[sheet][f"{col}{r}"].value
        if not (isinstance(v, str) and v.startswith("=")):
            inputs.append((sheet, r))
    return inputs if len(inputs) == 1 else rows


def _pairs(ns, scale):
    """(current, prior) pairs from a printed line, positionally: the
    classic two-column statement puts current first. Note-column
    numbers (small leading ints) are skipped by trying every adjacent
    pair."""
    out = []
    vals = [to_model_units(n, scale) for n in ns]
    for i in range(len(vals) - 1):
        out.append((vals[i], vals[i + 1]))
    return out


def reconcile(wb, spec, target_year, ledger, log, max_lines_per_table=80):
    """-> (serves, mapping) where serves is the standard serve dict and
    mapping = {"tables": n, "lines": n, "matched": n, "confirmed": n,
    "rejected_tables": [...], "unmatched_lines": [...],
    "unserved_rows_hint": n}."""
    homes, by_row = _model_prior_index(wb, spec, target_year)
    prior_docs = _vintage_ban(ledger)
    from .stage2_join import ratify_page_scales
    pool = ledger.join_pool()
    priors = list(by_row.values())
    page_scales = ratify_page_scales(pool, priors, [])
    tables = defaultdict(list)
    for it in pool:
        if it.doc in prior_docs or (it.doc, it.page) not in page_scales:
            continue
        tables[(it.doc, it.page, it.table_id)].append(it)

    serves, mapping = {}, {
        "tables": 0, "lines": 0, "matched": 0, "confirmed": 0,
        "rejected_tables": [], "unmatched_lines": []}
    claimed = {}          # (sheet,row) -> (value, src) the FIRST claim wins

    for key in sorted(tables):
        doc, page, tid = key
        items = sorted(tables[key], key=lambda i: i.row_ord or 0)
        if len(items) > max_lines_per_table:
            continue
        s = page_scales[(doc, page)]
        mapping["tables"] += 1
        table_serves = {}      # (sheet,row) -> (value, item, kind)
        for it in items:
            mapping["lines"] += 1
            hit = None
            for cur, pv in _pairs(it.nums, s):
                rows = _resolve(homes.get(round(pv, 1), []), wb, spec,
                                target_year)
                if len(rows) != 1:
                    # sign-flipped storage: model may hold the negative
                    rows = _resolve(homes.get(round(-pv, 1), []), wb, spec,
                                    target_year)
                    if len(rows) != 1:
                        continue
                    cur = -cur
                    pv = -pv
                (sheet, r) = rows[0]
                tol = row_tol(by_row[(sheet, r)])
                if abs(cur) > 30 * max(abs(pv), 1) \
                        or (abs(pv) > 30 and abs(cur) * 30 < abs(pv)):
                    continue           # out-of-world pair
                hit = (sheet, r, cur, pv)
                break
            if hit is None:
                money = [n for n in it.nums if abs(n) >= 50]
                if money and len(money) <= 4:
                    mapping["unmatched_lines"].append(
                        (doc, page, str(it.label)[:48], money[:3]))
                continue
            sheet, r, cur, pv = hit
            kind = ("confirmed" if abs(cur - pv)
                    <= row_tol(pv, base=0.01) else "served")
            if (sheet, r) not in table_serves:
                table_serves[(sheet, r)] = (cur, it, kind)
        # THE ACCEPTANCE TEST: if this table serves a model TOTAL row
        # whose model children are also served here, the children must
        # sum to the total — else the whole table's serves are refused
        ok_table = True
        for (sheet, r), (cur, it, kind) in table_serves.items():
            f = wb[sheet][
                f"{year_columns(spec, sheet)[str(target_year)]}{r}"].value
            m = re.match(r"^=\s*SUM\(([A-Z]{1,3})(\d+):[A-Z]{1,3}(\d+)\)\s*$",
                         str(f).replace("$", "")) \
                if isinstance(f, str) else None
            if not m:
                continue
            kids = [(sheet, rr) for rr in range(int(m.group(2)),
                                                int(m.group(3)) + 1)]
            kid_vals = [table_serves[k][0] for k in kids
                        if k in table_serves]
            if len(kid_vals) >= 2:
                # partial coverage allowed; full coverage must tie
                if len(kid_vals) == len([k for k in kids
                                         if k in by_row]) \
                        and abs(sum(kid_vals) - cur) > row_tol(cur,
                                                              base=2.0):
                    ok_table = False
                    mapping["rejected_tables"].append(
                        (doc, page, tid,
                         f"children sum {sum(kid_vals):,.1f} != printed "
                         f"total {cur:,.1f}"))
                    break
        if not ok_table:
            continue
        for (sheet, r), (cur, it, kind) in table_serves.items():
            if (sheet, r) in claimed:
                prev_v, _src = claimed[(sheet, r)]
                if abs(prev_v - cur) > row_tol(cur, base=1.0):
                    # two tables disagree on one row -> distrust both
                    serves.pop((sheet, r), None)
                continue
            claimed[(sheet, r)] = (cur, f"{doc} p{page}")
            mapping["matched"] += 1
            if kind == "confirmed":
                mapping["confirmed"] += 1
            serves[(sheet, r)] = {
                "value": cur, "status": "OK", "doc": doc, "page": page,
                "line": str(it.label)[:60],
                "conf": UNCHANGED_CONF if kind == "confirmed"
                else CONF_RECON,
                "note": (f"reconciliation: '{str(it.label)[:40]}' — "
                         f"prior {by_row[(sheet, r)]:,.2f} maps the line "
                         f"({doc} p{page}); "
                         + ("value CONFIRMED unchanged vs last year"
                            if kind == "confirmed" else
                            "current read from the same line"))}
    log(f"[run] reconciliation: {mapping['tables']} tables walked, "
        f"{mapping['matched']} rows served ({mapping['confirmed']} "
        f"confirmed unchanged), {len(mapping['rejected_tables'])} tables "
        f"rejected by their own sums, "
        f"{len(mapping['unmatched_lines'])} printed lines with no model "
        "home")
    return serves, mapping
