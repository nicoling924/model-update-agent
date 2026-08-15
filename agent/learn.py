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


def learn(wb, pre_values, spec, staging, census, tol=1.0, page_sections=None):
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
                sec = (page_sections or {}).get(it.get("page"))
                entries.append({"sheet": sheet, "row": r, "kind": "input",
                                "label": it["label"], "stmt": it.get("stmt"),
                                "page": it.get("page"), "sign_flip": flip,
                                "segment": it.get("segment"), "section": sec})
        # composite formulas: identify each embedded constant
        for r in range(1, min(wsf.max_row, 400) + 1):
            f = wsf[f"{pc}{r}"].value
            if not (isinstance(f, str) and f.startswith("=")):
                continue
            toks = re.findall(r"(?<![A-Za-z0-9_.$])\d{2,}(?:\.\d+)?(?![A-Za-z0-9_.])", f)
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
        ws[f"J{i}"] = e.get("section")
        ws[f"K{i}"] = e.get("audit")
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
            "section": ws[f"J{r}"].value,
            "audit": ws[f"K{r}"].value,
            "components": json.loads(comps) if comps else None}
    return out


def deterministic_identities(disclosure_paths, wb, pre_values, spec, tol=1.0):
    """Code-only learning: find each (prior, prior-1) pair in the RENDERED table
    lines of the prior-year documents; store the LITERAL rendered label+section.
    These identities are exact-matchable against next year's render."""
    from collections import defaultdict
    from . import lookup as lk
    idx = lk.index_tables(disclosure_paths)
    parsed = []
    for pnum, section, label, cells in idx:
        parsed.append((pnum, section, label,
                       lk._year_value(cells, _year_prior(spec)),
                       lk._year_value(cells, _year_prior2(spec))))
    by_val = defaultdict(list)
    for row in parsed:
        if row[3] is not None:
            by_val[round(row[3])].append(row)
    out = {}
    for sheet, ax in spec["year_axis"].items():
        cols = ax.get("columns") or {}
        years = sorted(cols)
        la = str(ax.get("last_actual"))
        try:
            i = years.index(la)
        except ValueError:
            continue
        pc, p2c = cols[la], (cols[years[i - 1]] if i > 0 else None)
        if sheet not in wb.sheetnames:
            continue
        wsf, wsv = wb[sheet], pre_values[sheet]
        hr = ax.get("header_row", 1)
        for r in range(1, min(wsf.max_row, 400) + 1):
            if r == hr:
                continue
            v = wsf[f"{pc}{r}"].value
            if not isinstance(v, (int, float)) or v == 0 or abs(v) < 50:
                continue  # small values collide; leave them to other paths
            v2 = wsv[f"{p2c}{r}"].value if p2c else None
            v2 = v2 if isinstance(v2, (int, float)) else None
            hits = []
            for flip in (1, -1):
                for row in by_val.get(round(flip * v), []):
                    if abs(row[3] - flip * v) > tol:
                        continue
                    lock2 = (v2 is None or row[4] is None or abs(row[4] - flip * v2) <= tol)
                    hits.append((row, flip, lock2))
            strong = [h for h in hits if h[2]]
            use = strong if strong else hits
            if not use:
                continue
            labels = {(h[0][2] or "").strip().lower() for h in use}
            if len(use) == 1 or len(labels) == 1:
                row, flip, _ = use[0]
                out[(sheet, r)] = {"kind": "input", "label": row[2], "section": row[1],
                                   "page": row[0], "sign_flip": flip == -1,
                                   "stmt": None, "segment": None, "method": "det"}
    return out


def _year_prior(spec):
    ax = next(iter(spec["year_axis"].values()))
    return str(ax.get("last_actual"))


def _year_prior2(spec):
    ax = next(iter(spec["year_axis"].values()))
    cols = ax.get("columns") or {}
    years = sorted(cols)
    i = years.index(str(ax.get("last_actual")))
    return years[i - 1] if i > 0 else ""


def component_recipes(disclosure_paths, wb, pre_values, spec, min_const=30, tol=1.0):
    """Learn embedded-hardcode recipes by the analyst's own method: Ctrl+F the
    constant in the prior-year report's raw text. STRICT acceptance — the paired
    year-before constant (same position in the year-before formula) must appear
    on the same line, or the label must be unique; everything else is left for
    the LLM/analyst arbiter at update time. Recipe = [{token,label,section,pos}]."""
    import re as _re
    from . import lookup as lk
    from .mapping import SCALARS
    TOKC = _re.compile(r"(?<![A-Za-z0-9_.$])\d{2,}(?:\.\d+)?(?![A-Za-z0-9_.])")
    L = lk.raw_lines(disclosure_paths)
    entries = []
    for sheet, ax in spec["year_axis"].items():
        cols = ax.get("columns") or {}
        years = sorted(cols)
        la = str(ax.get("last_actual"))
        try:
            i = years.index(la)
        except ValueError:
            continue
        pc, p2c = cols[la], (cols[years[i - 1]] if i > 0 else None)
        if sheet not in wb.sheetnames:
            continue
        wsf = wb[sheet]
        for r in range(1, min(wsf.max_row, 400) + 1):
            fh = wsf[f"{pc}{r}"].value
            if not (isinstance(fh, str) and fh.startswith("=")):
                continue
            toks = TOKC.findall(fh)
            if not toks:
                continue
            fg = wsf[f"{p2c}{r}"].value if p2c else None
            t2 = TOKC.findall(fg) if isinstance(fg, str) else []
            paired = list(zip(toks, t2)) if len(t2) == len(toks) else [(t, None) for t in toks]
            comps = []
            for tok, tok2 in paired:
                c = float(tok)
                if c < min_const or c in SCALARS:
                    comps.append(None)
                    continue
                c2 = float(tok2) if tok2 else None
                # scale-aware: on yuan-printed filings the constant's printed
                # form is 1e6x the model's — match numerically at doc scale
                from . import mapper as _mapper
                cands = [(pn, sec, ln) for pn, sec, ln in L
                         if _mapper.line_has_value(ln, c)
                         and len(lk.label_of(ln)) > 6]
                chosen = None
                if c2:  # strong lock: year-before constant on the same line
                    locked = [h for h in cands
                              if _mapper.num_matches(lk.line_nums(h[2]), c2)]
                    if locked:
                        chosen = locked[0]
                if chosen is None:
                    labels = {lk.norm(lk.label_of(h[2])) for h in cands}
                    if len(cands) >= 1 and len(labels) == 1:
                        chosen = cands[0]
                if chosen is None:
                    comps.append(None)
                    continue
                nums = [_mapper.to_model_units(n) for n in lk.line_nums(chosen[2])]
                pos = next((ix for ix, n in enumerate(nums) if abs(abs(n) - c) <= tol), None)
                if pos is None:
                    comps.append(None)
                    continue
                comps.append({"token": tok, "label": lk.label_of(chosen[2]),
                              "section": chosen[1], "pos": pos})
            if any(comps):
                entries.append({"sheet": sheet, "row": r, "kind": "components",
                                "components": comps, "label": None, "stmt": None,
                                "page": None, "sign_flip": False, "segment": None})
    return entries
