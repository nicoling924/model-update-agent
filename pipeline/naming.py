"""THE NAME JUDGMENT (owner 2026-09-15: "the brain should be used to think
and reason for the item terms and names" — a number tie without a judgment
of meaning is not a mapping).

Code finds the lines whose comparative ties a model row's prior. Where the
line's name is not kin to the row's, the tie may be a coincidence (CLP: a
Hong Kong tariff-stabilisation line printing −425 became Australia
amortisation). Every such tie goes to the brain in ONE batched call — the
model row with its section headers and sheet, the printed line with its
page and the table's column names — and the brain says whether the line IS
that row. A refusal drops the serve: the row stays stale (red, "not found")
with the brain's reason. Nothing lands on a name the brain did not accept.
"""
import json
import re

from .numerics import kinship

_SYSTEM = """You are an equity research analyst checking a model update. For
each item you are shown a MODEL ROW (its sheet, the section headers above
it, its label, last year's figure) and a PRINTED LINE from the company's
results documents whose comparative equals last year's figure. The numbers
match; the names do not. Decide whether the printed line IS the model row —
the same item under another name (turnover = revenue; "Domestic" =
"Residential"; a segment sheet's row read from the segment table under that
segment's column) — or a different item that merely prints the same number
(a Hong Kong tariff line is not an Australian amortisation; a headcount is
not a capacity; a subtotal of another block). Use the sheet, the section
headers, the page and the table's columns. When in doubt, say no: a red
"not found" is a correct deliverable, a wrong number is the one unforgivable
failure.

Answer with ONE JSON object and nothing else:
{"items": [{"id": <int>, "same": true|false, "why": "<one short phrase>"}, ...]}
Every id you were given must appear exactly once."""


def _validate(obj):
    errs = []
    if not isinstance(obj, dict) or not isinstance(obj.get("items"), list):
        return ["answer must be {items: [...]}"]
    for t in obj["items"]:
        if not isinstance(t, dict) or not isinstance(t.get("id"), int) or not isinstance(t.get("same"), bool):
            errs.append("each item needs an int id and a boolean same")
    return errs


def block_context(wb, sheet, row, span=8):
    """The section headers above a model row, from the sheet's label columns."""
    out = []
    if sheet not in wb.sheetnames:
        return out
    ws = wb[sheet]
    for r in range(row - 1, max(0, row - span), -1):
        for col in ("A", "B", "C", "D"):
            v = ws[f"{col}{r}"].value
            if isinstance(v, str) and len(v.strip()) > 3 and not v.startswith("="):
                out.append(v.strip())
                break
        if len(out) >= 3:
            break
    return out


def name_mismatches(wb, served, targets):
    """The served rows whose printed line is not kin to the model row's label.
    -> [((sheet, row), entry, model_label)]"""
    out = []
    for (sheet, row), entry in sorted(served.items()):
        if not isinstance(entry, dict) or entry.get("named") or not isinstance(entry.get("value"), (int, float)):
            continue
        line = str(entry.get("line") or "")
        t = targets.get((sheet, row)) if isinstance(targets, dict) else None
        label = str(getattr(t, "label", "") or "") if t is not None else ""
        if not label and sheet in wb.sheetnames:
            label = str(wb[sheet].cell(int(row), 1).value or "")
        if not line or not label or re.match(r"^[\d,.\s()|-]+$", line):
            continue                     # a line that is only numbers has no name to judge
        if kinship(label, line):
            continue
        out.append(((sheet, row), entry, label))
    return out


def _table_columns(ledger, entry):
    for it in getattr(ledger, "items", []):
        if it.doc == entry.get("doc") and it.page == entry.get("page") and str(it.label)[:60] == str(entry.get("line") or "")[:60]:
            return [str(c) for c in (getattr(it, "columns", None) or [])], getattr(it, "table_kind", None)
    return [], None


def judge_names(client, wb, spec, ledger, served, targets, writer, log, batch=120):
    """One batched brain call over every name-mismatched tie. Refused serves
    are dropped (the row stays stale, red, with the reason). -> (asked, refused)"""
    items = name_mismatches(wb, served, targets)
    if not items:
        return 0, 0
    if client is None:
        log(f"[names] {len(items)} name-mismatched tie(s) — no brain to judge them (a floor); they stand as code served them")
        return len(items), 0
    refused = 0
    for start in range(0, len(items), batch):
        chunk = items[start:start + batch]
        lines = []
        for i, ((sheet, row), entry, label) in enumerate(chunk):
            ctx = " > ".join(block_context(wb, sheet, int(row)))
            cols, kind = _table_columns(ledger, entry)
            t = targets.get((sheet, row)) if isinstance(targets, dict) else None
            pv = getattr(t, "prior_value", None) if t is not None else None
            lines.append(f"### id {i + 1}\n  MODEL ROW: sheet '{sheet}' row {row}: '{label}'" + (f" (under: {ctx})" if ctx else "")
                         + (f"; last year {pv:,.2f}" if isinstance(pv, (int, float)) else "")
                         + f"\n  PRINTED LINE: '{str(entry.get('line') or '')[:70]}' — {str(entry.get('doc') or '')[:40]} p{entry.get('page')}"
                         + (f"; table columns: {', '.join(cols[:7])}" if cols else "") + (f" ({kind} table)" if kind else "")
                         + f"; this year's figure read: {entry['value']:,.2f}")
        user = f"{len(chunk)} items follow.\n\n" + "\n\n".join(lines)
        try:
            obj = client.json(_SYSTEM, user, _validate, repair_retries=1)
        except Exception as ex:
            log(f"[names] the brain could not judge {len(chunk)} name-mismatched tie(s) ({ex}); they stand as code served them")
            continue
        verdicts = {t["id"]: t for t in (obj or {}).get("items", []) if isinstance(t, dict)}
        for i, ((sheet, row), entry, label) in enumerate(chunk):
            v = verdicts.get(i + 1)
            entry["named"] = True
            if v is None or v.get("same"):
                continue
            why = str(v.get("why") or "")[:120]
            refused += 1
            served.pop((sheet, row), None)
            writer.log.setdefault("name_refusals", []).append(
                f"{sheet}!{row} '{label}': the brain refused the printed line '{str(entry.get('line') or '')[:50]}' "
                f"(p{entry.get('page')}, {entry['value']:,.2f}) — {why}")
            log(f"[names] REFUSED {sheet}!{row} '{label[:28]}' <- '{str(entry.get('line') or '')[:40]}' {entry['value']:,.2f} — {why}")
    log(f"[names] the brain judged {len(items)} name-mismatched tie(s): {len(items) - refused} accepted, {refused} refused (rows stay red, not found)")
    return len(items), refused
