"""Objective-driven convergence — the tier ladder that replaces "fill cells" with
"satisfy objectives", all in code (no LLM in this module).

Tier 0  model balances every year          (hard constraint, diagnostic loop)
Tier 1  key numbers 100% correct           (proof-by-redundancy + anchor-plug)
Tier 2  finish inside the time budget      (scheduler: tiers 0-1 own the clock)
Tier 3  maximize whole-model accuracy      (existing cascade; scored as proxies)

The loop: score -> pick the lowest unsatisfied tier -> dispatch ONE targeted,
deterministic fix -> re-score. Fixes only ever touch input cells (rollover
hardcodes / constant formulas) in the target column; designed formulas are
never rewritten. Every plug is a traceable formula, flagged per house rules.
"""
import re
import time

from .evaluator import Evaluator

# canonical key numbers (Objective 2) and the labels they wear in models
KEY_KINDS = {
    "sales": ["total revenue", "revenue", "turnover", "sales", "operating revenue",
              "营业总收入", "营业收入"],
    "gross_profit": ["gross profit", "gross margin (hk$", "gross income", "毛利"],
    "operating_profit": ["operating profit", "operating income", "ebit",
                         "profit from operations", "营业利润"],
    "net_profit": ["net profits (reported)", "net profit", "profit attributable",
                   "net income", "profit for the year", "净利润"],
    "cash": ["cash and cash equivalents", "cash & cash equivalents", "cash and equivalents",
             "货币资金", "现金及现金等价物余额",
             "cash & bank", "bank balances and cash", "cash balance", "cash at end",
             "ending cash"],
    "current_assets": ["total current assets", "current assets", "流动资产合计"],
    "current_liabilities": ["total current liabilities", "current liabilities",
                            "流动负债合计"],
    "non_current_assets": ["total non-current assets", "non-current assets",
                           "total non current assets", "非流动资产合计"],
    "non_current_liabilities": ["total non-current liabilities", "non-current liabilities",
                                "total non current liabilities", "total long-term liabilities",
                                "long-term liabilities", "非流动负债合计"],
    "equity": ["total equity", "total shareholders", "shareholders' funds",
               "shareholders funds", "equity attributable", "net assets",
               "所有者权益合计", "股东权益合计"],
    "total_assets": ["total assets", "资产总计", "总资产"],
    "cfo": ["net cash flow from operations", "net cash from operating",
            "net cash flow from operating", "net cash generated from operating",
            "cash flows from operating", "operating cash flow",
            "经营活动产生的现金流量净额"],
    "cfi": ["net cash flow from investing", "net cash used in investing",
            "net cash from investing", "cash flows from investing",
            "investing cash flow", "投资活动产生的现金流量净额"],
    "cff": ["net cash flow from financing", "net cash used in financing",
            "net cash from financing", "cash flows from financing",
            "financing cash flow", "筹资活动产生的现金流量净额"],
}
# guards: "current assets" must never match "non-current assets"; CF totals must
# never match an "other …" or pre-subtotal line; BS totals must never match
# derived lines like "total assets less current liabilities"
_EXCLUDE = {"current_assets": ["non-current", "non current", "less", "net current",
                               "非流动"],
            "current_liabilities": ["non-current", "non current", "less",
                                    "total assets", "net current", "equity and",
                                    "非流动"],
            "non_current_liabilities": ["less", "total assets", "other", "net",
                                        "equity and", "debts"],
            "total_assets": ["liabilit", "return", "roa", "less", "负债", "收益率"],
            "cfo": ["other", "before working capital"],
            "cfi": ["other"],
            "cff": ["other"]}
# definition-sensitive keys: the company's own version of this line may lawfully
# differ from the model's scope — inside this band, flag for the analyst, never plug
_DEFN_BAND = {"operating_profit": 0.05, "gross_profit": 0.05, "net_profit": 0.01,
              "sales": 0.002}  # revenue has no real definition variants — tight band
_DEFN_DEFAULT = 0.01


def _norm(s):
    # keep CJK: a Chinese synonym must not normalize to "" (an empty pattern
    # boundary-matches labels containing '&' — every synonym would hit them)
    return re.sub(r"[^a-z0-9& 一-鿿]", "", str(s).lower()).strip()


def _syn_hit(syn, nl):
    """Word-boundary synonym match in normalized space — 'current liabilities'
    must NOT hit 'noncurrent liabilities' once the hyphen is stripped."""
    return re.search(rf"(?<![a-z0-9]){re.escape(_norm(syn))}(?![a-z0-9])", nl) is not None


def _excluded(kind, nl):
    return any(_syn_hit(x, nl) for x in _EXCLUDE.get(kind, []))


def _row_label(values_ws, r):
    for lc in "ABCDEF":
        v = values_ws[f"{lc}{r}"].value
        if isinstance(v, str) and v.strip():
            return v
    return None


def locate(spec, pre_wb, log):
    """kind -> {sheet,row,label}. Explicit spec `key_numbers` wins; the rest are
    auto-located by label scan over statements-role sheets. Unlocated kinds are
    reported, never guessed. Takes the FORMULA-bearing workbook (openpyxl-saved
    files carry no cached values, so data_only rows read None)."""
    keymap = {}
    explicit = spec.get("key_numbers") or {}
    for kind, loc in explicit.items():
        if loc and loc.get("sheet") and loc.get("row"):
            keymap[kind] = {"sheet": loc["sheet"], "row": int(loc["row"]),
                            "label": loc.get("label", kind), "src": "spec"}
    pre_values = pre_wb  # same labels either way; guard below reads raw cells
    sheets = [s for s, v in (spec.get("sheets") or {}).items()
              if (v or {}).get("role") == "statements"]
    for kind, syns in KEY_KINDS.items():
        if kind in keymap:
            continue
        best = None
        for sheet in sheets:
            if sheet not in pre_values.sheetnames:
                continue
            axis = (spec.get("year_axis") or {}).get(sheet) or {}
            la_col = (axis.get("columns") or {}).get(str(axis.get("last_actual")))
            ws = pre_values[sheet]
            for r in range(1, min(ws.max_row, 400) + 1):
                lab = _row_label(ws, r)
                if not lab:
                    continue
                nl = _norm(lab)
                if _excluded(kind, nl):
                    continue
                # a key row must actually HOLD something — kills section headers
                lv = ws[f"{la_col}{r}"].value if la_col else 0
                if la_col and not (isinstance(lv, (int, float))
                                   or (isinstance(lv, str) and lv.startswith("="))):
                    continue
                if any(_syn_hit(syn, nl) for syn in syns):
                    rank = min(i for i, syn in enumerate(syns) if _syn_hit(syn, nl))
                    if best is None or rank < best[0]:
                        best = (rank, sheet, r, lab)
        if best:
            keymap[kind] = {"sheet": best[1], "row": best[2], "label": best[3],
                            "src": "auto"}
    # models without explicit non-current totals: the pair is covered by identity
    # (total - current), so the objective is satisfied through the located rows
    for kind, total_k, cur_k in (("non_current_assets", "total_assets", "current_assets"),
                                 ("non_current_liabilities", "total_assets", "current_liabilities")):
        if kind not in keymap and total_k in keymap and cur_k in keymap:
            log.append(f"{kind}: no model row — covered via {total_k} − {cur_k} identity")
    # gross OR operating profit — either satisfies the margin objective
    if ("gross_profit" in keymap) != ("operating_profit" in keymap):
        have = "gross_profit" if "gross_profit" in keymap else "operating_profit"
        other = "operating_profit" if have == "gross_profit" else "gross_profit"
        log.append(f"{other}: no model row — margin objective covered by {have}")
    missing = [k for k in KEY_KINDS if k not in keymap
               and not any(f"{k}:" in ln for ln in log)]
    if missing:
        log.append(f"key numbers NOT LOCATED (add key_numbers: to spec.yaml): {missing}")
    return keymap


def prove(keymap, staging, raw_lines, pre_wb, spec, last_actual, cfg, log):
    """Objective 2's foundation: each key number's disclosed value must be PROVEN
    by redundancy — the same figure found in >=2 independent places (distinct
    pages across staging items + raw text), matched by prior-value triangulation
    (sign-safe) or synonym label. Single-source values are provisional."""
    tol = cfg["conventions"]["rounding_tolerance"]
    proven = {}
    from . import mapper as _mapper
    # quarterly-breakdown pages (分季度 tables) print the same captions with
    # QUARTER values — a label-only proof drawn there is a wrong number wearing
    # the right name (run 99: op profit "proven" at a Q4-sized 1,427; run 103:
    # 816). Label-only candidates from these pages are excluded; triangulated
    # candidates are untouched (a matching prior is its own defence).
    quarterly_pages = set()
    for pn_q, _s_q, ln_q in raw_lines:
        if any(k in ln_q for k in ("分季度", "第一季度", "第二季度", "第三季度", "第四季度")):
            quarterly_pages.add(pn_q)
    raw_num_pages = {}  # rounded |value| in MODEL units -> pages it appears on
    for pn, _sec, ln in raw_lines:
        for m in re.finditer(r"\(?-?[\d,]{3,}(?:\.\d+)?\)?", ln):
            t = m.group(0).replace(",", "")
            neg = t.startswith("(")
            t = t.strip("()")
            try:
                v = float(t)
            except ValueError:
                continue
            v = _mapper.to_model_units(-v if neg else v, page=pn)
            raw_num_pages.setdefault(round(abs(v), 1), set()).add(pn)
    ev_prior = Evaluator(pre_wb)
    for kind, loc in keymap.items():
        axis = spec["year_axis"].get(loc["sheet"])
        if not axis:
            continue
        pc = axis["columns"].get(last_actual)
        pv = pre_wb[loc["sheet"]][f"{pc}{loc['row']}"].value if pc else None
        if pc and not isinstance(pv, (int, float)):
            try:  # formula row: recompute the prior actual ourselves
                pv = ev_prior.cell(loc["sheet"], f"{pc}{loc['row']}")
            except Exception:
                pv = None
        # triangulated candidates (matched on the model's own prior — strong)
        # kept separate from label-only ones (weak); label-only serves ONLY when
        # no triangulation exists, and every candidate must pass the magnitude
        # guard — a key line does not move 5x, so a tiny same-label note row
        # can never outvote the real figure (the run-31 failure mode)
        cands_tri, cands_lab = {}, {}
        for it in staging.get("items", []):
            iv, ip = it.get("value"), it.get("prior")
            if not isinstance(iv, (int, float)):
                continue
            sign = None
            if isinstance(pv, (int, float)) and isinstance(ip, (int, float)) and abs(pv) > tol:
                if abs(ip - pv) <= max(tol, abs(pv) * 0.001):
                    sign = 1
                elif abs(-ip - pv) <= max(tol, abs(pv) * 0.001):
                    sign = -1  # model stores this line with flipped sign (e.g. liabilities +)
            syns = KEY_KINDS.get(kind, [])  # pseudo-kinds (tie-web) have none:
            nl_it = _norm(it.get("label", ""))  # triangulation-only, the strong path
            label_hit = bool(syns) and any(_syn_hit(s, nl_it) for s in syns) \
                and not _excluded(kind, nl_it)
            if sign is not None:
                cands_tri.setdefault(round(iv * sign, 1), set()).add(("item", it.get("page")))
            elif label_hit and it.get("page") not in quarterly_pages:
                # harmonize to the MODEL's sign convention (disclosures print
                # liabilities negative where models store them positive — a raw
                # label-only value must never flip the model's sign)
                iv_h = iv if not (isinstance(pv, (int, float)) and pv) \
                    else abs(iv) * (1 if pv > 0 else -1)
                cands_lab.setdefault(round(iv_h, 1), set()).add(("item", it.get("page")))
        cands = dict(cands_tri) if cands_tri else dict(cands_lab)
        # magnitude guard: BS/P&L key lines do not move 5x in a year; CF lines
        # legitimately swing wider, so they get a looser band
        lo, hi = (0.05, 20) if kind in ("cfo", "cfi", "cff") else (0.2, 5)
        if isinstance(pv, (int, float)) and abs(pv) > 10:
            cands = {v: s for v, s in cands.items() if lo <= abs(v) / max(abs(pv), 1e-9) <= hi}
        for mv, srcs in cands.items():
            for rp in raw_num_pages.get(round(abs(mv), 1), ()):
                if all(rp != p for _t, p in srcs):
                    srcs.add(("raw", rp))
        if not cands:
            proven[kind] = {"status": "missing", "value": None, "sources": 0}
            continue
        best = max(cands.items(), key=lambda kv: len(kv[1]))
        val, srcs = best
        status = "proven" if len(srcs) >= 2 else "single-source"
        proven[kind] = {"status": status, "value": val, "sources": len(srcs),
                        "pages": sorted(str(p) for _t, p in srcs)[:4]}
    # statement locality: the group BS lives on the pages where the PROVEN
    # anchors (equity, total assets ...) sit; a single-source BS candidate far
    # from there is a subsidiary/segment statement wearing the same label —
    # drop it to honest-unproven rather than trust the wrong entity
    BS_KINDS = {"cash", "current_assets", "current_liabilities", "non_current_assets",
                "non_current_liabilities", "equity", "total_assets"}
    anchor_pages = [int(x) for k in BS_KINDS
                    if proven.get(k, {}).get("status") == "proven"
                    for x in (proven[k].get("pages") or []) if str(x).isdigit()]
    if anchor_pages:
        # the statements sit where proven anchors CLUSTER — min-of-pages let a
        # five-year-summary hit on p5 define the window while the actual BS
        # lived on p95 (DFE), dropping every true statement value as "off-page"
        center = max(anchor_pages,
                     key=lambda c: sum(1 for x in anchor_pages if c - 2 <= x <= c + 8))
        lo_p, hi_p = center - 2, center + 8
        for k in BS_KINDS:
            p = proven.get(k)
            if p and p.get("status") == "single-source":
                pgs = [int(x) for x in (p.get("pages") or []) if str(x).isdigit()]
                if pgs and all(not (lo_p <= x <= hi_p) for x in pgs):
                    log.append(f"{k}: single-source {p['value']:,.1f} sits off the "
                               f"statement pages (p{pgs} vs ~p{lo_p}-{hi_p}) — dropped")
                    p.update(status="missing", value=None)
    # arithmetic corroboration upgrades single-source values whose identity ties
    def _v(k):
        p = proven.get(k) or {}
        return p.get("value") if p.get("status") in ("proven", "single-source") else None
    ties = [("equity", lambda: (_v("current_assets") or 0) + (_v("non_current_assets") or 0)
             - (_v("current_liabilities") or 0) - (_v("non_current_liabilities") or 0),
             all(_v(k) is not None for k in ("current_assets", "non_current_assets",
                                             "current_liabilities", "non_current_liabilities")))]
    for kind, fn, ready in ties:
        p = proven.get(kind)
        if ready and p and p.get("status") == "single-source" \
                and abs(abs(fn()) - abs(p["value"])) <= max(tol * 4, abs(p["value"]) * 0.002):
            p["status"] = "proven"
            p["sources"] += 1
            p["pages"].append("identity-tie")
    n_p = sum(1 for p in proven.values() if p["status"] == "proven")
    log.append(f"key numbers: {len(keymap)} located, {n_p} proven by redundancy, "
               f"{sum(1 for p in proven.values() if p['status'] == 'single-source')} single-source, "
               f"{sum(1 for p in proven.values() if p['status'] == 'missing')} not in disclosure")
    return proven


def tie_web(wb, pre_wb, spec, staging, raw_lines, cfg, last_actual, target_year, log,
            exclude_rows=frozenset()):
    """Extend the key-number method to EVERY subtotal: each formula row in a
    statements-role sheet whose disclosed value can be PROVEN (triangulation +
    redundancy, same guards as keys) becomes an anchor. A proven subtotal that
    disagrees with the model's computed value exposes a wrong input beneath it —
    the tail's errors get caught by the arithmetic above them."""
    pseudo = {}
    sheets = [s for s, v in (spec.get("sheets") or {}).items()
              if (v or {}).get("role") in ("statements", "segment")]
    for sheet in sheets:
        if sheet not in wb.sheetnames:
            continue
        axis = spec["year_axis"].get(sheet) or {}
        tcol = (axis.get("columns") or {}).get(target_year)
        if not tcol:
            continue
        for r in range(1, min(wb[sheet].max_row, 400) + 1):
            if (sheet, r) in exclude_rows:
                continue  # key numbers keep their own (definition-aware) handling
            v = wb[sheet][f"{tcol}{r}"].value
            if not (isinstance(v, str) and v.startswith("=")):
                continue
            if re.match(r"^=[\d+\-. ()]+$", v):
                continue  # constant back-out, an input not a subtotal
            lab = _row_label(wb[sheet], r)
            pseudo[f"sub:{sheet}!{r}"] = {"sheet": sheet, "row": r,
                                          "label": lab or f"row {r}", "src": "tieweb"}
    proven = prove(pseudo, staging, raw_lines, pre_wb, spec, last_actual, cfg, [])
    anchors = {k: p for k, p in proven.items() if p.get("status") == "proven"}
    log.append(f"tie-web: {len(pseudo)} subtotal rows scanned, "
               f"{len(anchors)} proven as anchors")
    return {k: pseudo[k] for k in anchors}, anchors


def _precedent_inputs(wb, sheet, coord, target_cols, eligible, depth=0, seen=None):
    """Walk a formula's reference tree; collect target-column INPUT cells
    (hardcodes or constant-only formulas) — the only legal plug sites."""
    seen = seen if seen is not None else set()
    if depth > 6 or (sheet, coord) in seen:
        return []
    seen.add((sheet, coord))
    v = wb[sheet][coord].value
    out = []
    if v is None or isinstance(v, (int, float)):
        if (sheet, coord) in eligible:
            out.append((sheet, coord))
        return out
    if not (isinstance(v, str) and v.startswith("=")):
        return out
    if (sheet, coord) in eligible:  # constant-formula input (back-out / composite)
        out.append((sheet, coord))
        return out
    body = v.replace("$", "")
    refs = []

    def _grab(m):  # sheet-qualified refs first, then strip so bare refs parse clean
        refs.append(((m.group(1) or m.group(2)).strip("'").strip(), m.group(3)))
        return " "

    bare = re.sub(r"(?:'([^']+)'|([A-Za-z][A-Za-z0-9 ]*?))!([A-Z]{1,3}\d+)", _grab, body)
    # expand same-column ranges: SUM(AI57:AI63) means EVERY cell between —
    # endpoint-only walks silently missed the middle (latent since day one)
    def _grab_range(m):
        c1, r1, c2, r2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        if c1 == c2 and abs(r2 - r1) <= 100:
            for rr in range(min(r1, r2), max(r1, r2) + 1):
                refs.append((sheet, f"{c1}{rr}"))
            return " "
        return m.group(0)

    bare = re.sub(r"(?<![A-Za-z0-9_])([A-Z]{1,3})(\d+):([A-Z]{1,3})(\d+)",
                  _grab_range, bare)
    for m in re.finditer(r"(?<![A-Za-z0-9_])([A-Z]{1,3}\d+)", bare):
        refs.append((sheet, m.group(1)))
    for sh, ref in refs:
        col = re.match(r"([A-Z]{1,3})", ref).group(1)
        if sh not in wb.sheetnames or col not in target_cols:
            continue
        out += _precedent_inputs(wb, sh, ref, target_cols, eligible, depth + 1, seen)
    return out


def _sensitivity(wb, t_sheet, t_coord, p_sheet, p_coord):
    """d(target)/d(input) by finite difference — layout-independent coefficient."""
    cell = wb[p_sheet][p_coord]
    old = cell.value
    try:
        base_in = Evaluator(wb).cell(p_sheet, p_coord)
        base = Evaluator(wb).cell(t_sheet, t_coord)
        cell.value = (base_in if isinstance(base_in, (int, float)) else 0) + 1.0
        bumped = Evaluator(wb).cell(t_sheet, t_coord)
        return bumped - base, (base_in if isinstance(base_in, (int, float)) else 0)
    except Exception:
        return None, None
    finally:
        cell.value = old


def _plug_formula(old_value, adj):
    if isinstance(old_value, str) and old_value.startswith("="):
        # collapse an existing trailing plug instead of stacking another
        m = re.match(r"^(.*)\+\((-?[\d.]+(?:[eE][+-]?\d+)?)\)$", old_value)
        if m:
            try:
                return f"{m.group(1)}+({float(m.group(2)) + adj:.6g})"
            except ValueError:
                pass
        return f"{old_value}+({adj:.6g})"
    base = old_value if isinstance(old_value, (int, float)) else 0
    return f"={base:.6g}+({adj:.6g})"


def scorecard(wb, spec, keymap, proven, cfg, t0):
    """Compute the tier ladder's current state. Pure read, no writes."""
    tol = cfg["conventions"]["rounding_tolerance"]
    ev = Evaluator(wb)
    card = {"tier0": [], "tier1": [], "tier2": None, "log": []}
    for c in spec.get("check_rows", []):
        axis = spec["year_axis"].get(c["sheet"], {})
        for year, col in sorted((axis.get("columns") or {}).items()):
            try:
                got = ev.cell(c["sheet"], f"{col}{c['row']}")
            except Exception:
                card["tier0"].append((f"{c['sheet']}!{col}{c['row']}", year, None))
                continue
            gap = (got or 0) - c.get("expect", 0)
            card["tier0"].append((f"{c['sheet']}!{col}{c['row']}", year,
                                  round(gap, 2)))
    for kind, loc in keymap.items():
        p = proven.get(kind) or {}
        axis = spec["year_axis"].get(loc["sheet"], {})
        tcol = axis.get("columns", {}).get(spec["_target_year"])
        model_v = None
        if tcol:
            try:
                model_v = ev.cell(loc["sheet"], f"{tcol}{loc['row']}")
            except Exception:
                pass
        dv = p.get("value")
        if dv is None or p.get("status") == "missing":
            st = "UNPROVABLE"  # not in disclosure — needs back-out or analyst
        elif isinstance(model_v, (int, float)) \
                and abs(model_v - dv) <= max(tol, abs(dv) * 0.001):
            st = "CORRECT" if p.get("status") == "proven" else "MATCH-1SRC"
        else:
            st = "MISMATCH"
        card["tier1"].append({"kind": kind, "sheet": loc["sheet"], "row": loc["row"],
                              "coord": f"{tcol}{loc['row']}" if tcol else None,
                              "model": model_v, "disclosed": dv, "status": st,
                              "proof": p.get("status"), "pages": p.get("pages")})
    card["tier2"] = round((time.time() - t0) / 60, 1)
    card["t0_pass"] = all(g is not None and abs(g) <= max(tol, 0.01)
                          for _c, _y, g in card["tier0"])
    card["t1_pass"] = all(e["status"] in ("CORRECT", "MATCH-1SRC", "UNPROVABLE")
                          for e in card["tier1"])
    return card


def converge(wb, spec, staging, cfg, writer, pre_wb, pre_values, target_year,
             last_actual, keymap, proven, flags, backouts, t0, eligible_inputs,
             deadline, protected_cells=frozenset()):
    """The tier loop. Deterministic fixes only; every write flagged + noted."""
    tol = cfg["conventions"]["rounding_tolerance"]
    spec["_target_year"] = target_year
    obj_log = []
    target_cols = set(spec.get("_target_cols") or [])
    staged_vals = sorted({round(abs(it["value"]), 1) for it in staging.get("items", [])
                          if isinstance(it.get("value"), (int, float))})

    def _corroborated(v):
        return any(abs(abs(v) - sv) <= tol for sv in staged_vals)

    max_fixes = int((cfg.get("objectives") or {}).get("max_fixes", 12))
    fixes = 0
    attempts = {}  # per-kind attempt counter: sibling fixes may take several passes
    ev_prior_c = Evaluator(pre_wb)

    def _sibling_disclosed(sheet_s, row_s):
        """The GUILTY-sibling check: this component's own disclosed value via
        prior triangulation. Returns (value, n_sources) or (None, 0)."""
        axis_s = spec["year_axis"].get(sheet_s) or {}
        pc_s = (axis_s.get("columns") or {}).get(last_actual)
        if not pc_s:
            return None, 0
        try:
            pv_s = ev_prior_c.cell(sheet_s, f"{pc_s}{row_s}")
        except Exception:
            return None, 0
        if not isinstance(pv_s, (int, float)) or abs(pv_s) <= tol:
            return None, 0
        cands_s = {}
        for it in staging.get("items", []):
            iv, ip = it.get("value"), it.get("prior")
            if not isinstance(iv, (int, float)) or not isinstance(ip, (int, float)):
                continue
            if abs(ip - pv_s) <= max(tol, abs(pv_s) * 0.001):
                sign_s = 1
            elif abs(-ip - pv_s) <= max(tol, abs(pv_s) * 0.001):
                sign_s = -1
            else:
                continue
            v_s = round(iv * sign_s, 1)
            if 0.2 <= abs(v_s) / abs(pv_s) <= 5:
                cands_s.setdefault(v_s, set()).add(it.get("page"))
        if not cands_s:
            return None, 0
        best_s = max(cands_s.items(), key=lambda kv: len(kv[1]))
        return best_s[0], len(best_s[1])

    for _iteration in range(max_fixes * 3):
        card = scorecard(wb, spec, keymap, proven, cfg, t0)
        if time.time() >= deadline or fixes >= max_fixes:
            break
        # ---- TIER 1 first in causal order: anchors feed the balance ----------
        mismatch = next((e for e in card["tier1"] if e["status"] == "MISMATCH"
                         and e["coord"] and attempts.get(e["kind"], 0) < 3), None)
        if mismatch is not None:
            attempts[mismatch["kind"]] = attempts.get(mismatch["kind"], 0) + 1
            s, coord, dv = mismatch["sheet"], mismatch["coord"], mismatch["disclosed"]
            # definition-risk zone: model and disclosure close but unequal is
            # more likely a scope difference (cash vs cash+deposits; company's
            # "operating earnings" vs the model's) — flag, never plug
            band = _DEFN_BAND.get(mismatch["kind"], _DEFN_DEFAULT)
            pages_m = [str(x) for x in ((proven.get(mismatch["kind"]) or {}).get("pages") or [])]
            reconciled = any(x.startswith(("bridge", "model-identity", "evidenced",
                                           "FY24", "identity"))
                             for x in pages_m)                 or (proven.get(mismatch["kind"]) or {}).get("sources", 0) >= 5
            if reconciled:
                band = 0.0  # the definition was already reconciled — fix exactly
            if not isinstance(mismatch["model"], (int, float)):
                # no numeric baseline (eval error) — plugging would be blind
                flags.append((s, coord, f"key {mismatch['kind']}: model value not "
                              f"evaluable; disclosed {dv:,.1f} — verify manually"))
                obj_log.append(f"T1 {mismatch['kind']}: model not evaluable — flagged")
                continue
            if dv and abs(mismatch["model"] - dv) <= abs(dv) * band:
                flags.append((s, coord, f"key {mismatch['kind']}: model "
                              f"{mismatch['model']:,.1f} vs disclosed {dv:,.1f} within "
                              f"{band:.0%} — possible definition/scope difference, review"))
                obj_log.append(f"T1 {mismatch['kind']}: within {band:.0%} of disclosed — "
                               "flagged as definition check, not plugged")
                continue
            n_src = (proven.get(mismatch["kind"]) or {}).get("sources", 0)
            plug_ok = n_src >= 3
            if not plug_ok:
                # thin proof never PLUGS the model — but sibling corrections
                # carry their own per-component evidence, so they still run
                # (run 98: CA/NCA proven only on the scanned statement page;
                # this gate blocked even the component repair)
                flags.append((s, coord, f"key {mismatch['kind']}: disclosed "
                              f"{dv:,.1f} has only {n_src} source(s) — verify, "
                              "not auto-plugged"))
                obj_log.append(f"T1 {mismatch['kind']}: proof thin ({n_src} src) "
                               "— plug disabled; sibling corrections only")
            residual = dv - mismatch["model"]
            if plug_ok and (s, coord) in eligible_inputs:
                # the key cell is itself an input: set it to the proven value
                fl = None if mismatch["proof"] == "proven" else "red"
                writer.write(s, coord, dv,
                             note=f"OBJECTIVE key[{mismatch['kind']}]: disclosed "
                                  f"{dv:,.1f} ({mismatch['proof']}, p{mismatch['pages']})",
                             flag=fl)
                if fl:
                    flags.append((s, coord, f"key {mismatch['kind']} single-source"))
                obj_log.append(f"T1 {mismatch['kind']}: input {s}!{coord} set to "
                               f"disclosed {dv:,.1f} ({mismatch['proof']})")
                fixes += 1
                continue
            # formula cell: anchor-plug through an existing input row — prefer a
            # NON-IMPORTANT line ("others"/misc/adjustment), then flagged cells;
            # never a row that is itself a key number, never a new row
            precs = _precedent_inputs(wb, s, coord, target_cols, eligible_inputs)
            flagged_set = {(fs, fc) for fs, fc, _n in flags}
            key_cells = {(k["sheet"], f"{k.get('coord')}")
                         for k in card["tier1"] if k.get("coord")}

            def _plug_rank(p):
                lab = _norm(_row_label(wb[p[0]], int(re.sub(r"[A-Z]+", "", p[1]))) or "")
                otherish = any(w in lab for w in
                               ("other", "misc", "sundr", "adjust", "其他", "其它"))
                return (0 if otherish else 1, 0 if p in flagged_set else 1)

            ranked = [p for p in sorted(set(precs), key=_plug_rank)
                      if p not in key_cells and p not in protected_cells]
            # FIX THE GUILTY SIBLING FIRST: a component whose own disclosed
            # value disagrees with its cell is the real error — correcting it
            # ties the subtotal without displacing an innocent row to a plug
            done = False
            ev_cur = Evaluator(wb)
            for ps, pco in ranked:
                row_p = int(re.sub(r"[A-Z]+", "", pco))
                dv_s, n_src = _sibling_disclosed(ps, row_p)
                if dv_s is None:
                    continue
                try:
                    cur_s = ev_cur.cell(ps, pco)
                except Exception:
                    continue
                if not isinstance(cur_s, (int, float)) \
                        or abs(cur_s - dv_s) <= max(tol, abs(dv_s) * 0.001):
                    continue
                fl_s = None if n_src >= 2 else "red"
                old_cell = wb[ps][pco].value
                writer.write(ps, pco, dv_s,
                             note=f"OBJECTIVE sibling correction: this component's "
                                  f"disclosed value is {dv_s:,.1f} ({n_src} source(s)); "
                                  f"was {cur_s:,.1f} — corrected while tying "
                                  f"{mismatch['kind']}",
                             flag=fl_s)
                # TRANSACTIONAL against the DRIVING key: a sibling "correction"
                # whose evidence matched the wrong line must not move the key
                # away from its disclosed value (run 104: U11 4,043->3,781.8 on
                # 3-source evidence took net profit from right to 339.5 wrong)
                try:
                    key_after = Evaluator(wb).cell(s, coord)
                except Exception:
                    key_after = None
                if isinstance(key_after, (int, float)) and isinstance(dv, (int, float)) \
                        and abs(key_after - dv) > abs(mismatch["model"] - dv) + tol:
                    wb[ps][pco].value = old_cell
                    obj_log.append(f"T1 {mismatch['kind']}: sibling {ps}!{pco} "
                                   f"REVERTED — moved the key AWAY from disclosed "
                                   f"({mismatch['model']:,.1f} -> {key_after:,.1f} "
                                   f"vs {dv:,.1f})")
                    continue
                if fl_s:
                    flags.append((ps, pco, f"sibling correction for {mismatch['kind']}"))
                obj_log.append(f"T1 {mismatch['kind']}: GUILTY SIBLING {ps}!{pco} "
                               f"{cur_s:,.1f} -> {dv_s:,.1f} ({n_src} src)")
                fixes += 1
                done = True
                break
            if done:
                continue  # re-score; if the subtotal still misses, plug next pass
            for ps, pco in (ranked if plug_ok else []):
                coef, base_in = _sensitivity(wb, s, coord, ps, pco)
                if not coef or abs(coef) < 0.01 or abs(coef) > 100:
                    continue
                adj = residual / coef
                old = wb[ps][pco].value
                writer.write(ps, pco, _plug_formula(old, adj),
                             note=f"OBJECTIVE back-out: plugged so "
                                  f"{mismatch['kind']} ({s}!{coord}) ties to disclosed "
                                  f"{dv:,.1f} (p{mismatch['pages']}); adj {adj:+,.1f}",
                             flag="orange")
                backouts.append((ps, pco, f"plug to key {mismatch['kind']}"))
                obj_log.append(f"T1 {mismatch['kind']}: plugged {ps}!{pco} "
                               f"{adj:+,.1f} -> {s}!{coord} = {dv:,.1f}")
                fixes += 1
                done = True
                break
            if done:
                continue
            obj_log.append(f"T1 {mismatch['kind']}: NO legal plug site for {s}!{coord} "
                           f"(disclosed {dv:,.1f}, model {mismatch['model']}) — flagged")
            flags.append((s, coord, f"key {mismatch['kind']} unfixable: disclosed "
                                    f"{dv:,.1f} vs model {mismatch['model']}"))
            continue
        # ---- TIER 0: balance diagnostic on the target-year gap ---------------
        gap_entry = next(((c, y, g) for c, y, g in card["tier0"]
                          if y == target_year and g is not None
                          and abs(g) > max(tol, 0.01)), None)
        if gap_entry is None:
            break  # tiers 0-1 satisfied (or unfixable) — done
        chk_ref, _y, gap = gap_entry
        chk_sheet, chk_coord = chk_ref.split("!")
        flagged_inputs = sorted({(fs, fc) for fs, fc, _n in flags
                                 if (fs, fc) in eligible_inputs})
        candidates = []
        for ps, pco in flagged_inputs[:80]:
            coef, base_in = _sensitivity(wb, chk_sheet, chk_coord, ps, pco)
            if not coef or abs(coef) < 0.01 or abs(coef) > 100:
                continue
            adj = -gap / coef
            new_v = (base_in or 0) + adj
            # corroboration: the corrected value (or a clean sign flip) must exist
            # in the validated extraction — a Fable-style "gap = 2x the line" catch
            if _corroborated(new_v) or abs(adj + 2 * (base_in or 0)) <= tol:
                candidates.append((ps, pco, adj, new_v))
        if len(candidates) == 1:
            ps, pco, adj, new_v = candidates[0]
            old = wb[ps][pco].value
            writer.write(ps, pco, _plug_formula(old, adj),
                         note=f"OBJECTIVE balance diagnostic: adjusting by {adj:+,.1f} "
                              f"zeroes the {target_year} balance gap ({gap:+,.1f}) and the "
                              f"corrected value {new_v:,.1f} is corroborated in the disclosure",
                         flag="red")
            flags.append((ps, pco, "balance-diagnostic repair — verify"))
            obj_log.append(f"T0 balance: {ps}!{pco} {adj:+,.1f} (gap was {gap:+,.1f}, "
                           f"corrected value corroborated)")
            fixes += 1
            continue
        if candidates:
            obj_log.append(f"T0 balance: gap {gap:+,.1f} at {chk_ref} — "
                           f"{len(candidates)} corroborated candidates (need exactly "
                           "1 to act); left for analyst")
        else:
            obj_log.append(f"T0 balance: gap {gap:+,.1f} at {chk_ref} — no "
                           "corroborated single-cell repair; left for analyst")
        break
    final = scorecard(wb, spec, keymap, proven, cfg, t0)
    return final, obj_log, fixes


def render(card, obj_log):
    """Console / markdown report-card lines (PASS/FAIL per objective)."""
    L = ["## Objectives scorecard"]
    t0_fail = [(c, y, g) for c, y, g in card["tier0"]
               if g is None or abs(g) > 0.01]
    L.append(f"- Objective 1 (balance, all years): "
             f"{'PASS' if card['t0_pass'] else 'FAIL — ' + ', '.join(f'{c} {y}: {g}' for c, y, g in t0_fail[:6])}")
    n_ok = sum(1 for e in card["tier1"] if e["status"] in ("CORRECT", "MATCH-1SRC"))
    n_bad = [e for e in card["tier1"] if e["status"] == "MISMATCH"]
    n_unp = [e["kind"] for e in card["tier1"] if e["status"] == "UNPROVABLE"]
    L.append(f"- Objective 2 (key numbers): {n_ok}/{len(card['tier1'])} correct"
             + (f"; MISMATCH: {[(e['kind'], e['model'], e['disclosed']) for e in n_bad]}" if n_bad else "")
             + (f"; not provable from disclosure: {n_unp}" if n_unp else ""))
    L.append(f"- Objective 3 (time): {card['tier2']} min elapsed")
    L.append("- Objective 4 (whole model): scored offline vs ground truth; "
             "in-run proxies in the integrity gate above")
    for e in card["tier1"]:
        L.append(f"    - {e['kind']}: {e['status']} model={e['model']} "
                 f"disclosed={e['disclosed']} ({e['proof']})")
    if obj_log:
        L.append("### Objective fixes applied")
        L += [f"- {x}" for x in obj_log]
    return L


def cf_pieces(staging):
    """(fx, cash_end, cash_begin) in model units from staged lines.
    Opening cash needs no label of its own: it is the PRIOR of the closing-
    cash line (the statement's comparative column) — the 期初 caption never
    survives line extraction cleanly (measured run 108), the identity does."""
    def _pick(syns):
        cands = {}
        for it in staging.get("items", []):
            lab = _norm(it.get("label", ""))
            v = it.get("value")
            if not isinstance(v, (int, float)) or not lab:
                continue
            if any(_syn_hit(s_, lab) for s_ in syns):
                cands.setdefault(round(v, 1), set()).add(
                    (it.get("page"), it.get("prior")
                     if isinstance(it.get("prior"), (int, float)) else None))
        if not cands:
            return None, None
        val, srcs = max(cands.items(), key=lambda kv: len(kv[1]))
        priors = [p_ for _pg, p_ in srcs if p_ is not None]
        return val, (sorted(priors)[len(priors) // 2] if priors else None)

    fx, _ = _pick(["汇率变动对现金及现金等价物的影响", "汇率变动",
                   "effect of exchange rate", "effect of foreign exchange"])
    end, end_prior = _pick(["期末现金及现金等价物余额", "期末现金", "年末现金",
                            "cash and cash equivalents at end", "cash at end"])
    return fx, end, end_prior


def cash_tie_oracle(proven, staging, log, tol_frac=0.005):
    """The CF identity as an ACTIVE verifier (council): CFO + CFI + CFF + FX
    must equal ΔCash (end − begin). All five pieces are printed; the model's
    units staging carries them. Outcomes per case:

    - identity TIES with the proven triplet -> all three CF proofs upgraded
      (sources +2): they corroborate each other through the strongest
      arithmetic there is.
    - identity FAILS and exactly ONE member's removal explains the residual ->
      that member's proof is demoted to suspect (wrong line instance wearing
      the right caption — the run-102 CFI/CFF class), logged for the loop.
    - pieces missing -> do nothing loudly.
    """
    fx, end, beg = cf_pieces(staging)
    cfs = {k: (proven.get(k) or {}).get("value") for k in ("cfo", "cfi", "cff")}
    if end is None or beg is None or any(not isinstance(v, (int, float))
                                         for v in cfs.values()):
        log.append("cash-tie oracle: pieces missing "
                   f"(end={end}, beg={beg}, cf={cfs}) — skipped")
        return
    fx = fx or 0.0
    delta = end - beg
    resid = sum(cfs.values()) + fx - delta
    tol = max(1.0, abs(delta) * tol_frac)
    if abs(resid) <= tol:
        for k in cfs:
            proven[k]["sources"] = proven[k].get("sources", 1) + 2
            proven[k]["status"] = "proven"
            proven[k].setdefault("pages", []).append("cash-tie")
        log.append(f"cash-tie oracle: CFO+CFI+CFF+FX = ΔCash ties "
                   f"(resid {resid:,.1f}) — all three CF proofs upgraded")
        return
    log.append(f"cash-tie oracle: identity FAILS by {resid:,.1f} "
               f"(cf={cfs}, fx={fx:,.1f}, ΔCash={delta:,.1f})")
    # which single member is the liar? the one whose proof, if wrong by
    # exactly -resid, would close the identity — flag the least-corroborated
    weakest = min(cfs, key=lambda k: (proven.get(k) or {}).get("sources", 0))
    proven[weakest]["status"] = "single-source"
    proven[weakest]["sources"] = 1
    proven[weakest].setdefault("pages", []).append("cash-tie-SUSPECT")
    log.append(f"cash-tie oracle: {weakest} demoted to suspect "
               "(least corroborated member of a failing identity)")
