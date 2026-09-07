#!/usr/bin/env python3
"""THE READING TEST (owner 2026-09-09, priority): can Luna read a report
the way Fable reads it — the whole document in one view, each model row
answered with this year's value, the page, the printed line and a reason?

This is NOT the agent. It is an experiment that decides a design
question: if Luna reads well, cards shrink to verification; if not,
cards stay and gain page context.

usage: python3 tools/read_test.py <company_dir> <PERIOD> <YEAR> [--rows N]

Inputs: the model (priors from the prior column), the current-period
disclosures (full text per page; scanned pages as images), a bilingual
list of headline + known-hard rows. Output: updates/read_test_<PERIOD>.json
and .md — Luna's answer per row beside code's own tie (the reconciliation
walk on the same documents) so the two can be scored against each other
and against the analyst's key.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROW_PATTERNS = [
    r"^营业收入$|^营业总收入$|^revenue$|^turnover$|^total revenue",
    r"^营业利润|^operating profit|^operating earnings",
    r"^利润总额|profit before tax",
    r"^净利润$|^净利润（|profit for the year|profit for the period",
    r"归属于母公司(股东|所有者)的净利润|attributable to (share|owner)",
    r"^流动资产合计|^total current assets",
    r"^非流动资产合计|^total non-current assets",
    r"^资产总计|^total assets",
    r"^流动负债合计|^total current liabilities",
    r"^非流动负债合计|^total non-current liabilities",
    r"^负债合计|^total liabilities$",
    r"所有者权益合计|股东权益合计|^total equity",
    r"经营活动产生的现金流量净额|net cash (from|generated from|inflow from) operating",
    r"投资活动产生的现金流量净额|net cash (used in|from|outflow from) investing",
    r"筹资活动产生的现金流量净额|net cash (used in|from|outflow from) financing",
    r"期末现金及现金等价物余额|cash and cash equivalents at (the )?end",
    r"发行债券收到的现金|收回投资收到的现金|收到其他与投资活动有关的现金|处置子公司及其他营业单位收到的现金净额",
    r"分配股利|dividend|new orders|新生效订单|order intake",
    r"基本每股收益|earnings per share|^eps",
]

_SYSTEM = (
    "You are an equity research analyst updating a valuation model from a company's newly "
    "published financial disclosure. You are given the FULL disclosure text page by page (and "
    "images of scanned pages), and a list of model rows with the model's LAST-period value. For "
    "each row, find THIS period's value in the disclosure. Method, in order: (1) find the printed "
    "line whose last-period (comparative) figure equals the model's last-period value — that line "
    "is the item, whatever it is called; (2) confirm the label makes sense; (3) if the line prints "
    "last period's figure with this period's slot blank, dash or nil, the value is 0; (4) if a "
    "figure appears in several places (statement, summary table, notes, text) they must agree — "
    "say so if they do not; (5) if the model row has no last-period value, identify it by its "
    "label and scope (a group total belongs to the group row, a segment figure to the segment "
    "row). Convert to the model's units. Answer ONLY with JSON: {\"rows\": [{\"row\": \"<id>\", "
    "\"value\": <number or null>, \"page\": <int or null>, \"line\": \"<printed line>\", "
    "\"reason\": \"<one sentence>\", \"confidence\": \"high|medium|low\"}]}. A value you cannot "
    "support with a printed line is null with the reason 'not found' — never guess."
)


def _rows(wb, spec, year):
    from pipeline.checks import prior_column, year_columns
    out = []
    for sheet in (spec.get("year_axis") or {}):
        if sheet not in wb.sheetnames:
            continue
        cols = year_columns(spec, sheet)
        pcol = prior_column(spec, sheet, year) or cols.get(str(year - 1))
        tcol = cols.get(str(year))
        if not pcol:
            continue
        ws = wb[sheet]
        for r in range(1, min(ws.max_row, 400) + 1):
            lab = ws.cell(r, 1).value
            if not isinstance(lab, str) or not lab.strip():
                continue
            l = lab.strip()
            if not any(re.search(p, l, re.IGNORECASE) for p in ROW_PATTERNS):
                continue
            if re.search(r"差额|平衡|check|balance test", l, re.IGNORECASE):
                continue             # the model's own balancing rows are not inputs
            pv = ws[f"{pcol}{r}"].value
            if isinstance(pv, str) and pv.startswith("="):
                pv = None            # a formula row: not an input, still asked (context)
            out.append({"row": f"{sheet}!{r}", "label": l,
                        "prior": (round(float(pv), 4) if isinstance(pv, (int, float)) else None),
                        "target_cell": f"{sheet}!{tcol}{r}" if tcol else None})
    return out


def _doc_text(paths, max_chars=1_600_000):
    from pipeline.stage1_read import page_texts
    parts, images, n = [], [], 0
    for p in paths:
        for pn, text, cls in page_texts(str(p)):
            if cls == "image":
                images.append((p, pn))
                parts.append(f"\n=== {p.name} page {pn} (SCANNED — see image) ===\n")
                continue
            t = (text or "").strip()
            if not t:
                continue
            block = f"\n=== {p.name} page {pn} ===\n{t}\n"
            if n + len(block) > max_chars:
                parts.append(f"\n[truncated: {p.name} from page {pn}]\n")
                break
            parts.append(block)
            n += len(block)
    return "".join(parts), images


def _images(images, limit=12):
    out = []
    try:
        import pdfplumber
        from pipeline.stage1_read import _page_image, _encode
    except Exception:
        return out
    for p, pn in images[:limit]:
        try:
            with pdfplumber.open(str(p)) as pdf:
                im = _page_image(pdf.pages[pn - 1])
            if im is not None:
                out.append(_encode(im, 1600))
        except Exception:
            continue
    return out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    company, period, year = Path(argv[0]), argv[1], int(argv[2])
    import openpyxl
    from pipeline import spec as spec_mod
    from pipeline.llm import make_client, env_ready
    from pipeline.run import _model_path
    if not env_ready():
        print("no LLM environment (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL)")
        return 2
    model = _model_path(company, spec_mod.load(company, None) if False else {})
    wbv = openpyxl.load_workbook(model, data_only=True)
    spec = spec_mod.load(company, wbv)
    rows = _rows(wbv, spec, year)
    docs = sorted((company / "disclosures" / period).glob("*.pdf"))
    if not docs:
        print("no disclosures for", period)
        return 2
    text, image_pages = _doc_text(docs)
    imgs = _images(image_pages)
    units = str(spec.get("units") or "the model's units (state them if the spec is silent)")
    user = (f"MODEL UNITS: {units}\n\nMODEL ROWS (id | label | last-period value):\n"
            + "\n".join(f"{r['row']} | {r['label']} | {r['prior']}" for r in rows)
            + "\n\nDISCLOSURE (full text, page-marked; scanned pages attached as images in order):\n"
            + text)
    client = make_client(temperature=0.0, max_output_tokens=20000)

    def _val(o):
        return [] if isinstance(o, dict) and isinstance(o.get("rows"), list) else ["rows list required"]
    t0 = time.time()
    obj = client.json(_SYSTEM, user, _val, repair_retries=1, images=imgs or None)
    took = time.time() - t0
    ans = {str(r.get("row")): r for r in (obj.get("rows") or []) if isinstance(r, dict)}
    # code's own ties on the same documents (the walk) for the scoreboard
    code = {}
    try:
        from pipeline.stage1_read import read_documents
        from pipeline.reconcile import reconcile
        wb = openpyxl.load_workbook(model)
        led = read_documents([str(d) for d in docs], client=None,
                             known_values=[r["prior"] for r in rows if r["prior"]], log=lambda s: None)
        serves, _m = reconcile(wb, spec, year, led, lambda s: None)
        code = {f"{k[0]}!{k[1]}": v.get("value") for k, v in serves.items()}
    except Exception as e:
        code = {"_error": str(e)}
    out = {"company": str(company), "period": period, "took_s": round(took, 1),
           "usage": getattr(client, "usage", {}), "rows": []}
    agree = asked = 0
    for r in rows:
        a = ans.get(r["row"]) or {}
        cv = code.get(r["row"])
        lv = a.get("value")
        both = isinstance(cv, (int, float)) and isinstance(lv, (int, float))
        same = both and abs(cv - lv) <= max(0.02, abs(cv) * 2e-3)
        asked += 1
        agree += bool(same)
        out["rows"].append({**r, "luna": lv, "luna_page": a.get("page"), "luna_line": a.get("line"),
                            "luna_reason": a.get("reason"), "luna_conf": a.get("confidence"),
                            "code": cv, "agree": same if both else None})
    out["summary"] = {"rows": asked, "both_answered": sum(1 for x in out["rows"] if x["agree"] is not None),
                      "agree": agree, "luna_answered": sum(1 for x in out["rows"] if isinstance(x["luna"], (int, float))),
                      "code_answered": sum(1 for x in out["rows"] if isinstance(x["code"], (int, float)))}
    up = company / "updates"
    up.mkdir(exist_ok=True)
    (up / f"read_test_{period}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    md = [f"# Reading test — {company.name} {period} ({took:.0f}s, {out['usage']})", "",
          f"rows {asked} · Luna answered {out['summary']['luna_answered']} · code tied {out['summary']['code_answered']} · both {out['summary']['both_answered']} · agree {agree}", "",
          "| row | label | prior | Luna | page | code | agree | Luna's reason |", "|---|---|---|---|---|---|---|---|"]
    for x in out["rows"]:
        md.append(f"| {x['row']} | {x['label'][:28]} | {x['prior']} | {x['luna']} | {x['luna_page']} | "
                  f"{x['code'] if x['code'] is None else round(x['code'], 2)} | {x['agree']} | {str(x['luna_reason'])[:90]} |")
    (up / f"read_test_{period}.md").write_text("\n".join(md))
    print("\n".join(md[:6]))
    print(f"written: {up / f'read_test_{period}.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
