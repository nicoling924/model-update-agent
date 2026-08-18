"""SELF-ONBOARDING key discovery — semantic nomination + mathematical
interrogation (council #6, the CLP campaign, 2026-08-19).

The owner's law: no per-company code, no human onboarding, teaching over
heuristics. The council's unanimous design: the LLM reads the workbook
skeleton and the filing's statements and NOMINATES key-row bindings —
concept, model row, and the filing line it corresponds to. Code then
CERTIFIES each nomination or leaves the concept unbound:

  PERIOD IDENTITY   the model row's prior-year value ties the filing
                    line's comparative at identity grade (legal scales);
  CONSTELLATION     a sheet certifying >=3 concepts is the consolidated
                    home; a binding on a 1-concept sheet loses to it
                    (the Aus-operating-profit twin killer: a vector of
                    independently printed figures tying one block is
                    proof; one coincident number is not);
  UNIQUENESS        two surviving candidates for one concept = unbound.

A key is not a label — it is a verified mathematical identity, and
`unbound` always beats a guess. Bindings persist to the spec so the
printed-key gate and Police law 4 get teeth; the prior-identity is
re-checked every run by the machinery that consumes them.
"""
import json

from .checks import prior_column, year_columns
from .numerics import SCALES, to_model_units

CONCEPTS = [
    "revenue", "gross profit", "operating profit", "net profit", "eps",
    "cash year end", "total current assets", "total non-current assets",
    "total assets", "total current liabilities",
    "total non-current liabilities", "total liabilities", "total equity",
    "operating cash flow", "investing cash flow", "financing cash flow",
]

_PROMPT = """You are onboarding an equity-research Excel model to its
company's filing. For each CONCEPT below, nominate the MODEL ROW that
holds it and the FILING LINE it corresponds to — or leave it unbound.

Rules (the analyst's discipline):
- The row's NAME says what it is; nominate by meaning, any language.
- CONSOLIDATED rows only: a country/segment sheet's row with the same
  name is a twin, not the key. Prefer the sheet that carries the whole
  statement family.
- For each nomination give the filing line VERBATIM with its
  prior-year (comparative) figure — the certification will check that
  the model row's prior-year value equals it. If you cannot point to
  the filing line, leave the concept unbound.
- unbound is always better than a guess.

Respond with ONE JSON object:
{"bindings": [{"concept": "revenue", "sheet": "Final", "row": 7,
               "filing_line": "Revenue 88,018 90,964",
               "filing_prior": 90964.0}, ...]}
Only include concepts you can bind. CONCEPTS: %s
"""


def skeleton(wb, wbv, spec_d, target_year, max_rows=220):
    """Compact per-sheet row inventory: caption + prior-column value."""
    parts = []
    for sheet in (spec_d.get("year_axis") or {}):
        pcol = prior_column(spec_d, sheet, target_year)
        if not pcol or sheet not in wb.sheetnames:
            continue
        ws, wsv = wb[sheet], wbv[sheet]
        lines = [f"== SHEET {sheet} (prior col {pcol}) =="]
        n = 0
        for r in range(1, ws.max_row + 1):
            lab = next((ws[f"{lc}{r}"].value for lc in ("A", "B", "C", "D")
                        if isinstance(ws[f"{lc}{r}"].value, str)
                        and ws[f"{lc}{r}"].value.strip()), None)
            pv = wsv[f"{pcol}{r}"].value
            if lab is None and not isinstance(pv, (int, float)):
                continue
            kind = ("=" if isinstance(ws[f"{pcol}{r}"].value, str)
                    and str(ws[f"{pcol}{r}"].value).startswith("=") else "")
            pv_s = f"{pv:,.2f}" if isinstance(pv, (int, float)) else "-"
            lines.append(f"r{r}: {str(lab)[:40]} | prior {kind}{pv_s}")
            n += 1
            if n >= max_rows:
                lines.append("  ... (truncated)")
                break
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def certify(wbv, spec_d, target_year, ledger, bindings, log):
    """The referee. -> committed key_rows (spec shape)."""
    prior_docs = ledger.prior_period_docs()
    synonyms = {
        "profit for the year": "net profit", "profit": "net profit",
        "net income": "net profit", "earnings per share": "eps",
        "cash and cash equivalents": "cash year end", "cash": "cash year end",
        "cash at end of year": "cash year end", "turnover": "revenue",
        "sales": "revenue", "equity": "total equity",
        "shareholders' funds": "total equity",
        "net cash from operating activities": "operating cash flow",
        "net cash from investing activities": "investing cash flow",
        "net cash from financing activities": "financing cash flow",
    }
    survivors = []
    for b in bindings or []:
        try:
            concept = str(b["concept"]).strip().lower()
            concept = synonyms.get(concept, concept)
            sheet, row = str(b["sheet"]).strip(), int(b["row"])
            fp = float(b["filing_prior"])
        except (KeyError, TypeError, ValueError):
            log(f"[onboard] REJECT (malformed): {str(b)[:90]}")
            continue
        if concept not in CONCEPTS:
            log(f"[onboard] REJECT (unknown concept '{concept}'): "
                f"{str(b)[:80]}")
            continue
        if sheet not in wbv.sheetnames:
            log(f"[onboard] REJECT (no sheet '{sheet}')")
            continue
        pcol = prior_column(spec_d, sheet, target_year)
        if not pcol:
            log(f"[onboard] REJECT ({sheet}: no prior column in year axis)")
            continue
        mv = wbv[sheet][f"{pcol}{row}"].value
        if not isinstance(mv, (int, float)):
            log(f"[onboard] REJECT {concept}@{sheet}!{row}: prior cell "
                f"holds {mv!r} (not numeric)")
            continue
        # PERIOD IDENTITY: model prior == nominated filing comparative
        tol = max(0.6, abs(mv) * 5e-4) if abs(mv) >= 100 \
            else max(0.01, abs(mv) * 5e-3)
        if abs(abs(mv) - abs(fp)) > tol:
            log(f"[onboard] REJECT {concept}@{sheet}!{row}: model prior "
                f"{mv:,.2f} does not tie the nominated filing prior "
                f"{fp:,.2f}")
            continue
        # the nominated filing figure must actually PRINT in the filing
        printed = any(
            abs(abs(to_model_units(n, s)) - abs(fp)) <= tol
            for it in ledger.items if it.doc not in prior_docs
            and not getattr(it, "disputed", False)
            for n in it.nums for s in SCALES)
        if not printed:
            log(f"[onboard] REJECT {concept}@{sheet}!{row}: nominated "
                f"filing prior {fp:,.2f} not found in the filing")
            continue
        survivors.append({"concept": concept, "sheet": sheet, "row": row})
    # CONSTELLATION: a sheet certifying >=3 concepts is a consolidated
    # home; bindings on low-scoring sheets lose to a high-scoring rival
    # for the same concept — and concepts left with two survivors on
    # EQUAL footing stay unbound (uniqueness).
    score = {}
    for s in survivors:
        score[s["sheet"]] = score.get(s["sheet"], 0) + 1
    committed = {}
    for s in survivors:
        c = s["concept"]
        rival = committed.get(c)
        if rival is None:
            committed[c] = s
            continue
        rs, ss = score[rival["sheet"]], score[s["sheet"]]
        if ss > rs and ss >= 3:
            committed[c] = s
        elif rs == ss:
            committed[c] = None            # ambiguous — unbound
    out = [{"sheet": v["sheet"], "row": v["row"], "name": k}
           for k, v in committed.items() if v is not None]
    log(f"[onboard] certified {len(out)} key bindings "
        f"({len(bindings or []) - len(out)} rejected/unbound); "
        f"constellation: " + ", ".join(f"{k}={v}"
                                       for k, v in sorted(score.items())))
    return out


def nominate_and_certify(wb, wbv, spec_d, target_year, ledger, client, log):
    """The full onboarding pass. Returns committed key_rows (possibly
    empty — unbound beats a guess)."""
    if client is None:
        return []
    from .packets import statement_transcript
    card = (_PROMPT % ", ".join(CONCEPTS)
            + "\n\n== THE MODEL (skeleton) ==\n"
            + skeleton(wb, wbv, spec_d, target_year)
            + "\n\n== THE FILING (statements as extracted) ==\n"
            + statement_transcript(ledger, cap_chars=16000))

    def _val(o):
        return [] if isinstance(o.get("bindings"), list) \
            else ["'bindings' list required"]
    try:
        out = client.json(
            "You bind an Excel model's rows to a company filing. "
            "Nominate by meaning; unbound beats a guess.",
            card, _val, repair_retries=1)
    except Exception as e:
        log(f"[onboard] nomination failed: {e}")
        return []
    return certify(wbv, spec_d, target_year, ledger,
                   out.get("bindings"), log)
