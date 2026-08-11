"""Stage 5: blind adversarial review — a fresh context that re-derives and diffs.

Independence rules (a same-context "check your work" is a rubber stamp):
- the reviewer sees ONLY: disclosure text, updated column dump, pre-update dump,
  per-company conventions — never the updater's staging, worklist, or reasoning;
- optionally a different (stronger) model via REVIEWER_* env vars;
- findings are surfaced in the report; only "genuine_error" items with
  incontrovertible page evidence are auto-applied, max 2 fix iterations, each
  fix read back. Everything else is for the analyst.
"""
import json

from . import pdfs


def column_dump(wb, spec, col_key="_target_cols"):
    out = {}
    for sheet, axis in spec["year_axis"].items():
        cols = [c for c in spec.get(col_key, []) if c in (axis.get("columns") or {}).values()]
        ws = wb[sheet]
        rows = []
        for r in range(1, min(ws.max_row, 400) + 1):
            label = None
            for lc in "ABCDEF":
                v = ws[f"{lc}{r}"].value
                if isinstance(v, str) and v.strip():
                    label = v.strip()
                    break
            for col in cols:
                c = ws[f"{col}{r}"]
                if c.value is None:
                    continue
                rows.append({"row": r, "col": col, "label": label,
                             "value": c.value if not isinstance(c.value, str) else None,
                             "formula": c.value if isinstance(c.value, str) else None,
                             "flag": c.fill.start_color.rgb if c.fill and c.fill.fill_type else None,
                             "note": c.comment.text if c.comment else None})
        out[sheet] = rows
    return out


def review(client, reviewer_prompt, conventions_md, disclosure_paths,
           updated_dump, pre_dump, cfg):
    doc_text = []
    for p in disclosure_paths:
        for win in pdfs.windows(pdfs.pages(p), chars_per_window=150000):
            doc_text.append(f"--- {p} ---\n{pdfs.render(win)}")
            break  # headline statements live early; reviewer scope is headline + flags
    user = (f"{reviewer_prompt}\n\n## Per-company conventions\n{conventions_md}\n\n"
            f"## Updated column\n{json.dumps(updated_dump)[:400000]}\n\n"
            f"## Pre-update column\n{json.dumps(pre_dump)[:200000]}\n\n"
            f"## Disclosure text\n{chr(10).join(doc_text)[:500000]}\n\n"
            'Return JSON: {"findings": [{"severity": "genuine_error|needs_analyst_ruling|confirmed_ok",'
            ' "cell": "...", "model_holds": "...", "disclosure_says": "...", "page": 0,'
            ' "evidence": "..."}], "verdict": "..."}')

    def validate(obj):
        errs = []
        if "findings" not in obj or "verdict" not in obj:
            errs.append("missing findings/verdict")
        for f in obj.get("findings", []):
            if f.get("severity") not in ("genuine_error", "needs_analyst_ruling", "confirmed_ok"):
                errs.append(f"bad severity in finding {f}")
        return errs

    return client.json("You are an independent adversarial reviewer.", user, validate,
                       repair_retries=cfg["budgets"]["json_repair_retries"])
