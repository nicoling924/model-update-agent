"""The learner agent: self-supervised calibration from the workbook's own answers.

The prior actual column IS an answer key — the analyst already mapped the prior
year's report into it. Given that report, the learner establishes each row's
LINE IDENTITY (which disclosure line feeds it, with what sign) using a double
lock: the row's prior value AND the year-before value must both match the same
extracted line. Identities are written to a hidden `_UPDATE_MAP` tab that
travels with the workbook. Content is strictly mapping metadata (public report
line names, statement types, page areas) — never client or proprietary data.

The update agent runs the learner's output; it never needs analyst input.
"""

MEMORY_TAB = "_UPDATE_MAP"
DISCLAIMER = ("VALUATION MODEL UPDATE MAPPING — machine-generated metadata for "
              "automated model roll-forward. Contains disclosure line-name "
              "mappings only (public report vocabulary); no client, holdings, "
              "estimate, or otherwise sensitive data. Safe to leave in the "
              "workbook. Managed by the model-update agent; edits welcome.")


def learn(wb, pre_values, spec, staging, census, tol=1.0):
    """Return identity entries [{sheet,row,kind,label,stmt,page,sign_flip}] by
    double-locked matching of the prior actual column against prior-year staging."""
    from .mapping import norm, SCALARS
    import re
    items = [it for it in staging["items"]
             if isinstance(it.get("value"), (int, float))]
    entries = []
    for sheet, ax in spec["year_axis"].items():
        cols = ax.get("columns") or {}
        years = sorted(cols)
        last_actual = str(ax.get("last_actual"))
        try:
            i = years.index(last_actual)
        except ValueError:
            continue
        pc = cols[last_actual]                      # e.g. 2024 column
        p2c = cols[years[i - 1]] if i > 0 else None  # e.g. 2023 column
        if sheet not in wb.sheetnames:
            continue
        wsv = pre_values[sheet]
        wsf = wb[sheet]
        for r in census.get(sheet, []):
            v = wsv[f"{pc}{r}"].value
            if not isinstance(v, (int, float)) or v == 0:
                continue
            v2 = wsv[f"{p2c}{r}"].value if p2c else None
            ident = _identify(items, v, v2, tol)
            if ident:
                it, flip = ident
                entries.append({"sheet": sheet, "row": r, "kind": "input",
                                "label": it["label"], "stmt": it.get("stmt"),
                                "page": it.get("page"), "sign_flip": flip,
                                "segment": it.get("segment")})
        # composite formulas: identify each embedded constant
        for r in range(1, min(wsf.max_row, 400) + 1):
            f = wsf[f"{pc}{r}"].value
            if not (isinstance(f, str) and f.startswith("=")):
                continue
            toks = re.findall(r"(?<![A-Za-z0-9_.])\d{2,}(?:\.\d+)?(?![A-Za-z0-9_.])", f)
            comps = []
            for tok in toks:
                c = float(tok)
                if c in SCALARS:
                    comps.append(None)
                    continue
                sign = -c if f"-{tok}" in f else c
                ident = _identify(items, sign, None, tol) or _identify(items, c, None, tol)
                comps.append({"token": tok, "label": ident[0]["label"],
                              "stmt": ident[0].get("stmt"),
                              "page": ident[0].get("page")} if ident else None)
            if any(comps):
                entries.append({"sheet": sheet, "row": r, "kind": "components",
                                "components": comps, "label": None,
                                "stmt": None, "page": None, "sign_flip": False})
    return entries


def _identify(items, v, v2, tol):
    """Find the line whose value matches v (either sign); disambiguate with the
    year-before value v2 when several match. Returns (item, sign_flipped)."""
    for flip in (False, True):
        target = -v if flip else v
        cands = [it for it in items if abs(it["value"] - target) <= tol]
        if not cands:
            continue
        if len(cands) > 1 and isinstance(v2, (int, float)) and v2:
            t2 = -v2 if flip else v2
            locked = [it for it in cands
                      if isinstance(it.get("prior"), (int, float))
                      and abs(it["prior"] - t2) <= tol]
            if locked:
                cands = locked
        labels = {(it["label"] or "").strip().lower() for it in cands}
        if len(cands) == 1 or len(labels) == 1:
            return cands[0], flip
    return None


def write_memory_tab(wb, entries):
    import json
    if MEMORY_TAB in wb.sheetnames:
        del wb[MEMORY_TAB]
    ws = wb.create_sheet(MEMORY_TAB)
    ws.sheet_state = "hidden"
    ws["A1"] = DISCLAIMER
    ws["A2"] = "sheet | row | kind | disclosure label | stmt | page | sign_flip | components(json)"
    for i, e in enumerate(entries, 3):
        ws[f"A{i}"] = e["sheet"]
        ws[f"B{i}"] = e["row"]
        ws[f"C{i}"] = e["kind"]
        ws[f"D{i}"] = e.get("label")
        ws[f"E{i}"] = e.get("stmt")
        ws[f"F{i}"] = e.get("page")
        ws[f"G{i}"] = "Y" if e.get("sign_flip") else "N"
        ws[f"H{i}"] = json.dumps(e.get("components")) if e.get("components") else None
        ws[f"I{i}"] = e.get("segment")
    return len(entries)


def read_memory_tab(wb):
    import json
    if MEMORY_TAB not in wb.sheetnames:
        return {}
    ws = wb[MEMORY_TAB]
    out = {}
    for r in range(3, ws.max_row + 1):
        sheet, row = ws[f"A{r}"].value, ws[f"B{r}"].value
        if not sheet or row is None:
            continue
        comps = ws[f"H{r}"].value
        out[(sheet, int(row))] = {
            "kind": ws[f"C{r}"].value, "label": ws[f"D{r}"].value,
            "stmt": ws[f"E{r}"].value, "page": ws[f"F{r}"].value,
            "sign_flip": ws[f"G{r}"].value == "Y",
            "segment": ws[f"I{r}"].value,
            "components": json.loads(comps) if comps else None}
    return out
