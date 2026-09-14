"""THE TABLE READER (owner 2026-09-14): the brain reads every table of the
documents like an analyst and says what its columns ARE — years, segments,
categories, movements, units, a grid of both — and code stamps that
reading on every printed line of the table. No rule on shape: "there are
just too many different kinds of table"; the brain decides, the code only
carries the verdict to the channels that pair a current with a prior (the
walk, the evidence law, the nil rule, the page reads, the cards).

    describe_tables(client, ledger, docs, target_year, period, log)

Each table goes to the brain once with its printed header lines (from the
page text) and its first rows; the reply names the columns. A table the
brain calls periods keeps pairing (current = the target period's column,
prior = last period's); anything else never pairs. Where the brain gave
no reading the ledger's shape fallback stands (table_kind_of).
"""
import re
from pathlib import Path

KINDS = ("periods", "segments", "categories", "movement", "grid", "other")
_MAX_TABLES_PER_CALL = 300
_HEADER_LINES = 5

_SYSTEM = """You are an equity research analyst reading the tables of a company's
results documents (annual report, results announcement, presentation).
For EACH table you are shown, say what its columns are, the way an analyst
reads a table before taking a number from it. Look at the header lines
printed above the table and at the first rows.

Kinds:
- "periods": the columns are reporting periods side by side (e.g. 2025 | 2024,
  or FY2025 | FY2024 | FY2023, or 1H2025 | 1H2024). A number's neighbour is the
  same line in another period.
- "segments": the columns are business segments, regions or entities
  (Hong Kong | Australia | China | India | ...), all for ONE period.
- "categories": the columns are classes of one thing (cost | depreciation |
  net; current | non-current; units | MW; ageing buckets; currencies).
- "movement": the columns (or rows) are the steps of a roll-forward
  (opening | additions | disposals | closing).
- "grid": segments or categories crossed with periods (Hong Kong 2025 |
  Hong Kong 2024 | Australia 2025 | ...).
- "other": anything else, or you cannot tell.

For "periods" and "grid", name each column's period exactly as the document
means it, in the form FY2025, FY2024, 1H2025, 2H2024, 3Q2025, and for a grid
also the segment or category, e.g. "Hong Kong FY2025". For the other kinds
name each column in the document's own words. Columns are counted left to
right over the NUMBER columns only (the row label is not a column). If a
table has a single numeric column say so with one column. If the rows you
are shown do not look like one table (the header lines belong to another
block), still answer for the rows shown.

Answer with ONE JSON object and nothing else:
{"tables": [{"id": <int>, "kind": "<one of the kinds>",
             "columns": ["<column 1>", "<column 2>", ...],
             "note": "<one short phrase, optional>"}, ...]}
Every id you were given must appear exactly once."""


def _validate(obj):
    errs = []
    if not isinstance(obj, dict) or not isinstance(obj.get("tables"), list):
        return ["object with a 'tables' list required"]
    for t in obj["tables"]:
        if not isinstance(t, dict) or not isinstance(t.get("id"), int):
            errs.append("each table needs an integer id")
            continue
        if t.get("kind") not in KINDS:
            errs.append(f"table {t.get('id')}: kind must be one of {', '.join(KINDS)}")
        if not isinstance(t.get("columns"), list):
            errs.append(f"table {t.get('id')}: columns must be a list")
    return errs[:6]


def _page_lines(doc_path):
    """{page: [text lines]} for a document from the stage-1 text cache."""
    try:
        from .stage1_read import page_texts
        return {pn: (t or "").splitlines() for pn, t, cls in page_texts(str(doc_path)) if cls != "image"}
    except Exception:
        return {}


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _header_for(lines, first_label, n=_HEADER_LINES):
    """The printed lines just above the table's first row: the header."""
    if not lines or not first_label:
        return []
    key = _norm(first_label)[:24]
    for i, ln in enumerate(lines):
        if key and key in _norm(ln):
            return [x for x in lines[max(0, i - n):i] if x.strip()]
    return []


def _fmt_num(n):
    if isinstance(n, float) and n.is_integer():
        return f"{int(n):,}"
    return f"{n:,.2f}" if isinstance(n, float) else str(n)


def table_cards(ledger, docs):
    """[(key, card_text)] for every table of every document, in document
    order — the material the brain reads (the vintage law, not this pass,
    decides which document may source a value)."""
    by_name = {Path(d).name: Path(d) for d in docs}
    tabs = {}
    for it in ledger.items:
        tabs.setdefault((it.doc, it.page, it.table_id), []).append(it)
    lines_cache = {}
    cards = []
    for key in sorted(tabs, key=lambda k: (k[0], k[1], k[2])):
        doc, page, tid = key
        rows = sorted(tabs[key], key=lambda it: it.row_ord)
        if doc not in lines_cache:
            lines_cache[doc] = _page_lines(by_name[doc]) if doc in by_name else {}
        first = rows[0].source_line or rows[0].label
        header = _header_for(lines_cache[doc].get(page, []), first)
        body = [f"  {str(r.label)[:60]}: " + " | ".join(_fmt_num(n) for n in (r.nums or [])[:8])
                for r in rows[:4]]
        widths = sorted({len(r.nums or []) for r in rows})
        card = (f"[{doc} p{page} table {tid}; {len(rows)} rows; numbers per row {widths}]\n"
                + ("  header lines:\n" + "\n".join("    " + h[:140] for h in header) + "\n" if header else
                   "  (no header text found above the first row)\n")
                + "  rows:\n" + "\n".join(body))
        cards.append((key, card))
    return cards


def describe_tables(client, ledger, docs, target_year, period, log=print):
    """The brain reads every table once; the verdicts are stamped on the
    ledger's lines (Item.table_kind = period|matrix, Item.columns) and
    kept in ledger.table_readings. -> number of tables read."""
    if client is None:
        return 0
    cards = table_cards(ledger, docs)
    if not cards:
        return 0
    readings = {}
    n_calls = 0
    for start in range(0, len(cards), _MAX_TABLES_PER_CALL):
        batch = cards[start:start + _MAX_TABLES_PER_CALL]
        ids = {i + 1: key for i, (key, _c) in enumerate(batch)}
        user = (f"Reporting period being updated: {period} (target year {target_year}).\n"
                f"{len(batch)} tables follow. Each begins with its id.\n\n"
                + "\n\n".join(f"### id {i + 1}\n{card}" for i, (_k, card) in enumerate(batch)))
        try:
            obj = client.json(_SYSTEM, user, _validate, repair_retries=1)
            n_calls += 1
        except Exception as ex:
            log(f"[tables] call failed ({ex}); {len(batch)} tables keep the shape reading")
            continue
        for t in (obj or {}).get("tables", []):
            key = ids.get(t.get("id"))
            if key is None:
                continue
            readings[key] = {"kind": t.get("kind"), "columns": [str(c) for c in (t.get("columns") or [])],
                             "note": str(t.get("note") or "")[:120]}
    # the stamp: a periods table pairs; every other kind never does
    changed = {"period": 0, "matrix": 0}
    disagreed = []
    for it in ledger.items:
        rd = readings.get((it.doc, it.page, it.table_id))
        if rd is None:
            continue
        kind = "period" if rd["kind"] == "periods" else "matrix"
        if it.table_kind is not None and it.table_kind != kind and (it.doc, it.page, it.table_id) not in disagreed:
            disagreed.append((it.doc, it.page, it.table_id))
        it.table_kind = kind
        it.columns = list(rd["columns"])
        changed[kind] += 1
    ledger.table_readings = {f"{d}#p{p}#t{t}": v for (d, p, t), v in readings.items()}
    kinds = {}
    for v in readings.values():
        kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
    log(f"[tables] the brain read {len(readings)}/{len(cards)} tables in {n_calls} call(s): "
        + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items()))
        + f"; lines stamped period {changed['period']}, no-pair {changed['matrix']}; "
        f"{len(disagreed)} table(s) read differently from their shape")
    for d, p, t in disagreed[:12]:
        rd = readings[(d, p, t)]
        log(f"[tables]   {d} p{p} t{t}: {rd['kind']} — {', '.join(rd['columns'][:6])}" + (f" ({rd['note']})" if rd['note'] else ""))
    return len(readings)


def target_columns(item, target_year, period):
    """For a line of a periods table the brain read: (current index, prior
    index) among the line's number columns, or None when the reading does
    not name both — the pairing then falls back to the evidence law."""
    cols = getattr(item, "columns", None) or []
    if not cols:
        return None
    kind = str(period or "").upper()
    kind = ("1H" if kind.startswith(("1H", "H1")) else "2H" if kind.startswith(("2H", "H2"))
            else kind[:2] if re.match(r"^[1-4]Q", kind) else "FY")
    want_cur = f"{kind}{target_year}"
    want_pri = f"{kind}{target_year - 1}"
    cur = next((i for i, c in enumerate(cols) if want_cur in str(c).upper().replace(" ", "")), None)
    pri = next((i for i, c in enumerate(cols) if want_pri in str(c).upper().replace(" ", "")), None)
    if cur is None or pri is None:
        return None
    return cur, pri
