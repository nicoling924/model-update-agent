"""Derivation — for rows the disclosure does not print.

Two mechanisms, both from the house rules:

1. ALLOCATION (BS splits): a proven disclosed TOTAL + the model's own prior-year
   structure. Confident components stay fixed; the unproven remainder is scaled
   to prior-year proportions so the total ties exactly. ("Hold prior-year
   ratios/structures and plug to disclosed totals" — mechanized.) Orange-flagged.

2. COMPOSITION (CF reclassification): the model's FY24 value is the answer key —
   search the FY24 disclosure's own lines for the subset that sums to it (<=4
   terms, same section). That subset IS the analyst's recipe; replay it on FY25
   by line name. (Model CFO = statutory CFO +/- specific reclassifications.)
"""
import itertools
import re

from . import lookup
from .evaluator import Evaluator


def recipe_pass(unresolved_rows, fy25_raw, log, max_rows=60):
    """Identity recipes for rows mapping could not resolve: the tie-broken
    Ctrl+F read. Unique -> serve (orange); ambiguous -> serve best red-flagged."""
    out = {}
    for r in unresolved_rows[:max_rows]:
        pv = r.get("prior_value")
        if not isinstance(pv, (int, float)) or abs(pv) < 10:
            continue
        v, pg, ln, unique = ctrlf_read(pv, fy25_raw, r.get("label"))
        if v is None:
            continue
        # sign follows the model's own convention (prior carries it)
        v_signed = v if pv >= 0 else -v
        out[(r["sheet"], r["row"])] = {
            "value": v_signed,
            "status": "RECIPE" if unique else "UNCERTAIN",
            "page": pg, "line": ln,
            "note": ("ctrlf-recipe: prior found, neighbour read"
                     + ("" if unique else " — AMBIGUOUS, verify"))}
    n_u = sum(1 for m in out.values() if m["status"] == "RECIPE")
    log.append(f"recipe pass: {n_u} unique reads + {len(out) - n_u} ambiguous "
               f"of {len(unresolved_rows)} unresolved rows")
    return out


def allocation_pass(wb, pre_wb, spec, target_year, last_actual, anchors,
                    confident, eligible_inputs, writer, flags, backouts, log,
                    raw_lines=None, protected=frozenset()):
    """anchors: {(sheet,row): disclosed_total}. For each anchor row that is a
    same-column SUM over input cells, scale the non-confident inputs to prior
    proportions so the sum ties exactly."""
    from . import objectives
    n_alloc = 0
    log.append(f"allocation anchors: {[(f'{s0}!r{r0}', round(v0,1)) for (s0,r0),v0 in anchors.items()]}")
    for (sheet, row), dv in anchors.items():
        axis = spec["year_axis"].get(sheet) or {}
        tcol = (axis.get("columns") or {}).get(target_year)
        pcol = (axis.get("columns") or {}).get(last_actual)
        if not tcol or not pcol or sheet not in wb.sheetnames:
            continue
        f = wb[sheet][f"{tcol}{row}"].value
        if not (isinstance(f, str) and f.startswith("=")):
            continue
        precs = objectives._precedent_inputs(wb, sheet, f"{tcol}{row}", {tcol},
                                             eligible_inputs)
        precs = sorted(set(precs))
        if len(precs) < 2:
            log.append(f"allocation {sheet}!r{row}: only {len(precs)} eligible "
                       "component(s) found — skipped")
            continue
        ev_c, ev_p = Evaluator(wb), Evaluator(pre_wb)
        fixed_sum = 0.0
        free = []
        for ps, pco in precs:
            r2 = int(re.sub(r"[A-Z]+", "", pco))
            try:
                cur = ev_c.cell(ps, pco)
                pri = ev_p.cell(ps, f"{pcol}{r2}")
            except Exception:
                continue
            if not isinstance(cur, (int, float)):
                continue
            trusted = (ps, pco) in confident
            if trusted and raw_lines and isinstance(pri, (int, float)) and abs(pri) >= 10:
                # trust must be POSITIVELY verified: only a unique Ctrl+F read
                # that AGREES keeps a component fixed; disagreeing or ambiguous
                # components are adjustable (an unverifiable "confident" cell
                # blocking a proven total is how run 62 stalled)
                v_c, _pg, _ln, uniq = ctrlf_read(pri, raw_lines)
                trusted = bool(uniq) and isinstance(v_c, (int, float)) \
                    and abs(abs(cur) - v_c) <= max(1.0, v_c * 0.005)
            if (ps, pco) in protected:
                fixed_sum += cur  # key-owned cells are NEVER scale targets
            elif trusted:
                fixed_sum += cur
            elif isinstance(pri, (int, float)) and pri != 0:
                free.append((ps, pco, pri))
            else:
                fixed_sum += cur
        if not free:
            log.append(f"allocation {sheet}!r{row}: no adjustable components "
                       f"({len(precs)} all trusted/zero-prior) — skipped")
            continue
        try:
            total_now = ev_c.cell(sheet, f"{tcol}{row}")
        except Exception:
            continue
        if isinstance(total_now, (int, float)) and abs(total_now - dv) <= 1.0:
            log.append(f"allocation {sheet}!r{row}: already ties — nothing to do")
            continue
        residual = dv - fixed_sum
        prior_free_sum = sum(p for _s, _c, p in free)
        if abs(prior_free_sum) < 1.0:
            continue
        factor = residual / prior_free_sum
        if not (0.2 <= factor <= 5):  # structure-hold must stay plausible
            log.append(f"allocation {sheet}!r{row}: factor {factor:.2f} implausible "
                       "— skipped")
            continue
        for ps, pco, pri in free:
            writer.write(ps, pco, f"={pri:.6g}*{factor:.6g}",
                         note=f"ALLOCATED: prior structure held, scaled so "
                              f"{sheet}!r{row} ties to disclosed {dv:,.1f}",
                         flag="orange")
            backouts.append((ps, pco, f"allocation to {sheet}!r{row}"))
        n_alloc += len(free)
        log.append(f"allocation {sheet}!r{row}: {len(free)} components scaled "
                   f"x{factor:.3f} -> ties to {dv:,.1f}")
    return n_alloc


def _section_lines(raw_lines, keywords):
    out = []
    for pn, sec, ln in raw_lines:
        blob = (str(sec) + " " + ln).lower()
        if any(k in blob for k in keywords):
            out.append((pn, sec, ln))
    return out


def learn_composition(target_cur, target_prior, fy24_raw, section_keywords,
                      max_terms=4, tol=1.5):
    """Find <=max_terms FY24 disclosure lines whose (current, prior) columns
    BOTH sum to the model's (FY24, FY23) values — the double-lock. A subset
    that only works one year is a coincidence and is rejected."""
    cands = []
    seen = set()
    from . import mapper as _mapper
    for pn, sec, ln in _section_lines(fy24_raw, section_keywords):
        ns = [_mapper.to_model_units(n, page=pn) for n in lookup.line_nums(ln)]
        if len(ns) < 2:
            continue  # need current AND prior printed on the line
        lab = lookup.label_of(ln)
        if not lab or len(lab) < 5:
            continue
        key = lookup.norm(lab)
        if key in seen:
            continue
        seen.add(key)
        if abs(ns[0]) > 1:
            cands.append((lab, ns[0], ns[1], pn))
    cands = cands[:60]
    have_prior = isinstance(target_prior, (int, float))
    for n in range(1, max_terms + 1):
        for combo in itertools.combinations(cands, n):
            for signs in itertools.product((1, -1), repeat=n):
                s_cur = sum(sg * c[1] for sg, c in zip(signs, combo))
                if abs(s_cur - target_cur) > tol:
                    continue
                if have_prior:
                    s_pri = sum(sg * c[2] for sg, c in zip(signs, combo))
                    if abs(s_pri - target_prior) > max(tol * 2, abs(target_prior) * 0.002):
                        continue  # fails the second year -> coincidence
                return [(c[0], sg, c[1], c[3]) for sg, c in zip(signs, combo)]
        if n == 2 and len(cands) > 35:
            cands = cands[:35]  # cap the cubic stage
    return None


_STMT_HINTS = ("statement of", "balance sheet", "income statement", "cash flow",
               "financial position", "comprehensive income",
               "资产负债表", "利润表", "现金流量表", "vision")  # vision lines ARE statements


def ctrlf_read(prior_value, raw_lines, row_label=None, tol=0.6):
    """The Ctrl+F read with disambiguating tie-breaks: find lines printing the
    prior value, take the left neighbour (magnitude-banded). If several survive,
    prefer primary-statement sections, then label similarity. Returns
    (value, page, line, unique) or (None, None, None, False)."""
    from . import mapper as _mapper
    from .workbook import row_tol
    tol = row_tol(prior_value, base=tol)  # per-share rows tie in their own world
    cands = []
    lab_n = lookup.norm(str(row_label or ""))
    lab_words = set(w for w in lab_n.split() if len(w) >= 4)
    for pn, sec, ln in raw_lines:
        # printed numbers -> MODEL units, so the Ctrl+F works on yuan filings
        ns = [_mapper.to_model_units(n, page=pn) for n in lookup.line_nums(ln)]
        for i in range(1, len(ns)):
            if abs(abs(ns[i]) - abs(prior_value)) <= tol:
                nb = ns[i - 1]
                if not (0.2 <= abs(nb) / max(abs(prior_value), 1e-9) <= 5):
                    continue
                sec_l = str(sec).lower()
                score = (2 if any(h in sec_l for h in _STMT_HINTS) else 0)
                ln_words = set(lookup.norm(ln).split())
                score += min(2, len(lab_words & ln_words))
                cands.append((round(abs(nb), 1), score, pn, ln.strip()[:90]))
                break
    if not cands:
        return None, None, None, False
    vals = {c[0] for c in cands}
    if len(vals) == 1:
        c = cands[0]
        return c[0], c[2], c[3], True
    best = sorted(cands, key=lambda c: -c[1])
    if best[0][1] > (best[1][1] if len(best) > 1 else -1):
        return best[0][0], best[0][2], best[0][3], True
    return best[0][0], best[0][2], best[0][3], False  # ambiguous — caller flags


def llm_bridge(client, key_name, v24, v23, fy24_raw, fy25_raw, section_keywords,
               log):
    """The REASONING path for a model-vs-disclosed difference: show the LLM the
    model's two prior-year values and the disclosed statement lines for both
    years, ask it to EXPLAIN the bridge (which named lines, which signs, WHY).
    Code then double-locks the hypothesis on FY24 AND FY23 — reasoning that does
    not survive two years of arithmetic dies — and only then replays on FY25."""
    lines24 = []
    seen_b = set()
    from . import mapper as _mapper
    for pn, _s, ln in _section_lines(fy24_raw, section_keywords):
        ns_b = [_mapper.to_model_units(n, page=pn) for n in lookup.line_nums(ln)]
        lab_b = lookup.label_of(ln)
        if len(ns_b) < 2 or not lab_b or len(lab_b) < 5:
            continue
        k_b = lookup.norm(lab_b)
        if k_b in seen_b:
            continue
        seen_b.add(k_b)
        lines24.append((lab_b, ns_b[0], ns_b[1], pn))
    lines24 = lines24[:45]
    menu = "\n".join(f"L{i}: '{lab}' = {c:,.1f} (prior {pr:,.1f}) p{pn}"
                     for i, (lab, c, pr, pn) in enumerate(lines24))
    user = (
        f"An equity research model holds '{key_name}' = {v24:,.1f} for FY24 and "
        f"{v23:,.1f} for FY23. The company's disclosed lines (FY24 report) are the "
        f"NUMBERED MENU below.\n\n"
        f"The model differs from the headline figure because the analyst "
        f"RECLASSIFIES items (commonly interest paid/received, dividends). REASON "
        f"OUT the bridge: which menu lines, added or subtracted, reproduce the "
        f"model's value in BOTH years? Check your arithmetic for both years "
        f"before answering.\n\n{menu}\n\n"
        'Return JSON: {"bridge": [{"idx": <L-number>, "sign": 1 or -1}], '
        '"reasoning": "<one sentence: why these reclassifications>"}')
    try:
        resp = client.json("You reconcile model definitions to disclosed figures. "
                           "Match definitions, not words.", user,
                           lambda o: [] if isinstance(o.get("bridge"), list)
                           else ["missing bridge"], repair_retries=1)
    except Exception as ex:
        log.append(f"bridge {key_name}: LLM error {ex}")
        return None, None
    s24 = s23 = 0.0
    recipe = []
    for term in resp.get("bridge", []):
        try:
            i_t = int(term.get("idx"))
            lab_t, c_t, pr_t, _pn_t = lines24[i_t]
        except (TypeError, ValueError, IndexError):
            log.append(f"bridge {key_name}: bad menu index {term} — rejected")
            return None, None
        sign_t = 1 if term.get("sign", 1) >= 0 else -1
        s24 += sign_t * c_t
        s23 += sign_t * pr_t
        recipe.append((lab_t, sign_t, c_t, None))
    tol_b = max(1.5, abs(v24) * 0.002)
    if abs(s24 - v24) > tol_b or abs(s23 - v23) > max(tol_b, abs(v23) * 0.002):
        log.append(f"bridge {key_name}: hypothesis fails double-lock "
                   f"(FY24 {s24:,.1f} vs {v24:,.1f}; FY23 {s23:,.1f} vs {v23:,.1f}) — rejected")
        return None, None
    v25, det = replay_composition(recipe, fy25_raw)
    if v25 is None:
        log.append(f"bridge {key_name}: verified on 2 years but not replayable — "
                   + "; ".join(det or []))
        return None, None
    log.append(f"bridge {key_name}: REASONED + double-locked -> FY25 {v25:,.1f} "
               f"({resp.get('reasoning', '')[:90]})")
    return round(v25, 1), resp.get("reasoning", "")


def replay_composition(recipe, fy25_raw):
    """Apply a learned recipe to FY25: find each line by name, VERIFY it is the
    right instance by last year's value sitting beside it (comparative column),
    and take the current value. Returns (value, details) or (None, why)."""
    from . import mapper as _mapper
    by_label = {}
    for pn, sec, ln in fy25_raw:
        lab = lookup.norm(lookup.label_of(ln) or "")
        if lab:
            ns = [_mapper.to_model_units(n, page=pn) for n in lookup.line_nums(ln)]
            if ns:
                by_label.setdefault(lab, []).append((ns, pn))
    total, details = 0.0, []
    from .workbook import row_tol
    for lab, sign, v24, _pg in recipe:
        hits = by_label.get(lookup.norm(lab)) or []
        tol_v = row_tol(v24, base=1.0)
        # 1st choice: the line whose SECOND number equals the FY24 value we
        # learned (current | prior layout) — proof it is the same line
        best = next(((ns, pn) for ns, pn in hits
                     if len(ns) >= 2 and abs(abs(ns[1]) - abs(v24)) <= tol_v), None)
        if best is None:  # fall back: old value anywhere on the line, neighbour left
            for ns, pn in hits:
                for i in range(1, len(ns)):
                    if abs(abs(ns[i]) - abs(v24)) <= tol_v:
                        best = ([ns[i - 1]], pn)
                        break
                if best:
                    break
        if best is None:
            return None, [f"line '{lab}' not verifiable in FY25 (prior {v24:,.1f} "
                          "not found beside any instance)"]
        val = best[0][0]
        total += sign * val
        details.append(f"{'+' if sign > 0 else '-'}{val:,.1f} '{lab[:32]}' p{best[1]}")
    return total, details


def implied_prior_read(rows, raw_lines, log, tol=0.01):
    """SINGLE-YEAR tables, solved deterministically (council's tie-out).

    MD&A tables (segment splits in 万元, production/sales/inventory in MW)
    print ONLY the current year plus a 同比 % change — no comparative column,
    so prior-value Ctrl+F can never anchor them. But the % IS the comparative:
        implied_prior = current / (1 + pct/100)
    A structured table line whose implied prior reproduces the model's own
    known prior (within tol — the %% prints 2dp) identifies the row with near
    certainty, names the current value, and self-solves the unit scale (the
    scale that makes the implied prior match IS the table's scale). Rows whose
    model prior disagrees with the filing's implied prior are left alone —
    an honest hole beats a silent wrong write (measured: the gate correctly
    refuses 电站汽轮机 production, where the model's FY24 itself disagrees).
    """
    from . import mapper as _mapper
    # (page, [(value, pct), ...]) per structured table line
    cand_lines = []
    for pn, sec, ln in raw_lines:
        if sec != "table" or "%" not in ln and "％" not in ln:
            continue
        cells = []
        for seg in ln.split(" | "):
            if ":" not in seg:
                continue
            h, _, v = seg.partition(":")
            n = lookup.line_nums(v, skip_years=False)
            if len(n) == 1:
                cells.append((h.strip(), n[0]))
        pairs = []
        import re as _re
        for i, (h, v) in enumerate(cells):
            if "增减" in h or "%" in h or "％" in h or "变动" in h:
                continue
            # year-headed columns (5-year summaries, quarterlies) pair with
            # nothing — matching them produced FY23-as-FY24 coincidences
            if _re.search(r"\d{4}", h) or h.endswith("年"):
                continue
            # STRICT pairing: the pct header must carry the value header's own
            # token (生产量 ⊂ 生产量比上年增减) — positional guessing produced
            # cross-metric coincidences (thermal prior == turbine inventory)
            pct = next((v2 for h2, v2 in cells
                        if ("增减" in h2 or "变动" in h2) and abs(v2) < 400
                        and h[:3] and h[:3] in h2), None)
            # a ~0% change makes implied==current==prior and matches every
            # stagnant row — demand a real move
            if pct is not None and pct > -100 and abs(pct) >= 0.5:
                pairs.append((h, v, pct))
        if pairs:
            cand_lines.append((pn, ln, pairs))
    out = {}
    for r in rows:
        pv = r.get("prior_value")
        if not isinstance(pv, (int, float)) or abs(pv) < 2:
            continue
        best = None
        for pn, ln, pairs in cand_lines:
            for h, v, pct in pairs:
                implied = v / (1 + pct / 100.0)
                for s in (1, 1e3, 1e4, 1e6, 1e8):
                    if abs(implied / s - abs(pv)) <= max(abs(pv) * 0.005, 0.6):
                        cur = v / s * (1 if pv >= 0 else -1)
                        hit = (cur, pn, f"{h}: {v:,.1f} ({pct:+.2f}%)", ln)
                        if best is None:
                            best = hit
                        elif abs(best[0]) != abs(cur):
                            best = "AMBIGUOUS"
                        break
                if best == "AMBIGUOUS":
                    break
            if best == "AMBIGUOUS":
                break
        if best and best != "AMBIGUOUS":
            cur, pn, why, ln = best
            out[(r["sheet"], r["row"])] = {
                "value": cur, "status": "RECIPE", "page": pn,
                "line": ln[:90],
                "note": f"implied-prior tie-out: {why} -> implied FY-prior "
                        f"matches model prior {pv:,.1f}"}
    log.append(f"implied-prior tie-out: {len(out)} single-year rows identified "
               f"({len(cand_lines)} candidate table lines)")
    return out


_PROSE_NUM = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(亿|万)?元?[^0-9%％]{0,30}?(?:同比)?(?:增长|增减|下降|减少)\s*"
    r"(-?[\d.]+)\s*[%％]")


def prose_growth_read(rows, raw_lines, log, tol=0.01):
    """The clean-room tester's move, mechanized: narrative sentences print
    "新生效订单1172.51亿元，同比增长15.93%" — value ± unit suffix ± growth.
    implied_prior = value/(1±pct) against the model's own prior identifies the
    row exactly as the table tie-out does, for numbers that live in PROSE
    (the orders block; MD&A highlights). 下降/减少 mean the pct is a decline.
    """
    from . import mapper as _mapper
    cands = []
    for pn, sec, ln in raw_lines:
        if sec == "table":
            continue
        for m in _PROSE_NUM.finditer(ln):
            try:
                v = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            unit = {"亿": 100.0, "万": 0.01}.get(m.group(2), 1.0)  # -> RMB m
            try:
                pct = float(m.group(3))
            except ValueError:
                continue
            if "下降" in m.group(0) or "减少" in m.group(0):
                pct = -abs(pct)
            if abs(pct) < 0.5 or pct <= -100:
                continue
            cands.append((pn, ln, v * unit, pct))
    out = {}
    for r in rows:
        pv = r.get("prior_value")
        if not isinstance(pv, (int, float)) or abs(pv) < 2:
            continue
        best = None
        for pn, ln, vm, pct in cands:
            # the prose value may be in RMB m already or need no suffix scale —
            # try as-is plus plain-scale variants
            for v_try in (vm, vm * 100, vm / 100):
                implied = v_try / (1 + pct / 100.0)
                if abs(implied - abs(pv)) <= max(abs(pv) * tol, 0.6):
                    cur = v_try * (1 if pv >= 0 else -1)
                    if best is None:
                        best = (cur, pn, ln)
                    elif abs(best[0] - cur) > 1:
                        best = "AMBIGUOUS"
                    break
            if best == "AMBIGUOUS":
                break
        if best and best != "AMBIGUOUS":
            cur, pn, ln = best
            out[(r["sheet"], r["row"])] = {
                "value": cur, "status": "RECIPE", "page": pn, "line": ln[:90],
                "note": f"prose growth tie-out: implied prior matches model "
                        f"prior {pv:,.1f} (printed growth reconciles)"}
    log.append(f"prose growth tie-out: {len(out)} rows identified "
               f"({len(cands)} candidate sentences)")
    return out


def statement_align(rows, raw_lines, log):
    """The clean-room tester's core move, mechanized: a statements-mirror sheet
    lists its rows in the SAME ORDER the statements print. Anchor every row
    whose prior matches a transcribed line's comparative (two-pointer, so
    matches are monotonic); between consecutive anchors, when the number of
    unmatched model rows EQUALS the number of unmatched statement lines, the
    pairing is forced — serve those current values deterministically. No
    search lottery, no per-row LLM call; a gap that doesn't count-match is
    left alone (holes over guesses).
    """
    from . import lookup as _lookup
    from . import mapper as _mapper
    # statement lines, in print order, per page run (vision lines only — they
    # are complete, ordered, and carry (current, prior) per line)
    lines = []
    for pn, sec, ln in raw_lines:
        if sec != "vision":
            continue
        ns = [_mapper.to_model_units(n, page=pn) for n in _lookup.line_nums(ln)]
        if len(ns) >= 2:
            lines.append((pn, ln.strip()[:80], ns[0], ns[1]))  # cur, prior
        elif len(ns) == 1:
            # single-number lines hold their PLACE in print order (gap counting)
            lines.append((pn, ln.strip()[:80], ns[0], None))
    if not lines:
        log.append("statement-align: no transcribed statement lines — skipped")
        return {}
    by_sheet = {}
    for r in rows:
        if isinstance(r.get("prior_value"), (int, float)):
            by_sheet.setdefault(r["sheet"], []).append(r)
    out = {}
    for sheet, srows in by_sheet.items():
        srows.sort(key=lambda r: r["row"])
        # two-pointer anchor pass
        anchors = []  # (row_idx, line_idx)
        li = 0
        for ri, r in enumerate(srows):
            pv = abs(r["prior_value"])
            if pv < 2:
                continue
            for lj in range(li, len(lines)):
                if lines[lj][3] is not None and \
                        abs(abs(lines[lj][3]) - pv) <= max(0.6, pv * 5e-4):
                    anchors.append((ri, lj))
                    li = lj + 1
                    break
        # LOCAL CONSISTENCY: a true anchor sits in a run of neighbours (the
        # statement mirrors the sheet); an isolated match is a prior-value
        # coincidence (measured: 3 of 27 v1 anchors were exactly that)
        anchors = [a for i, a in enumerate(anchors)
                   if (i > 0 and a[0] - anchors[i-1][0] <= 4
                       and a[1] - anchors[i-1][1] <= 4)
                   or (i + 1 < len(anchors) and anchors[i+1][0] - a[0] <= 4
                       and anchors[i+1][1] - a[1] <= 4)]
        if len(anchors) < 4:
            log.append(f"statement-align {sheet}: only {len(anchors)} consistent "
                       "anchors — sheet does not mirror the statements, skipped")
            continue
        served = 0
        for (r1, l1), (r2, l2) in zip(anchors, anchors[1:]):
            rows_gap = srows[r1 + 1:r2]
            lines_gap = lines[l1 + 1:l2]
            pairs = list(zip(rows_gap, lines_gap)) if len(rows_gap) == len(lines_gap) else []
            for r, (pn, ln, cur, pri) in pairs:
                if cur is None:
                    continue
                pv = r["prior_value"]
                v = cur if pv >= 0 else -abs(cur)
                out[(r["sheet"], r["row"])] = {
                    "value": v, "status": "RECIPE", "page": pn, "line": ln,
                    "note": ("statement-aligned: forced pairing between two "
                             "prior-anchored neighbours (order-preserving)")}
                served += 1
        # anchors themselves: serve current value at FULL LINE PRECISION
        for ri, lj in anchors:
            r = srows[ri]
            pn, ln, cur, pri = lines[lj]
            pv = r["prior_value"]
            v = cur if pv >= 0 else -abs(cur)
            out.setdefault((r["sheet"], r["row"]), {
                "value": v, "status": "RECIPE", "page": pn, "line": ln,
                "note": "statement-aligned: prior-anchored line, current read "
                        "across at full precision"})
        log.append(f"statement-align {sheet}: {len(anchors)} anchors, "
                   f"{served} gap rows forced, {len(out)} total served")
    return out
