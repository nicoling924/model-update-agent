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
                    raw_lines=None):
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
            if trusted:
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
    for pn, sec, ln in _section_lines(fy24_raw, section_keywords):
        ns = lookup.line_nums(ln)
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
               "financial position", "comprehensive income")


def ctrlf_read(prior_value, raw_lines, row_label=None, tol=0.6):
    """The Ctrl+F read with disambiguating tie-breaks: find lines printing the
    prior value, take the left neighbour (magnitude-banded). If several survive,
    prefer primary-statement sections, then label similarity. Returns
    (value, page, line, unique) or (None, None, None, False)."""
    cands = []
    lab_n = lookup.norm(str(row_label or ""))
    lab_words = set(w for w in lab_n.split() if len(w) >= 4)
    for pn, sec, ln in raw_lines:
        ns = lookup.line_nums(ln)
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
    for pn, _s, ln in _section_lines(fy24_raw, section_keywords):
        ns_b = lookup.line_nums(ln)
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
    by_label = {}
    for pn, sec, ln in fy25_raw:
        lab = lookup.norm(lookup.label_of(ln) or "")
        if lab:
            ns = lookup.line_nums(ln)
            if ns:
                by_label.setdefault(lab, []).append((ns, pn))
    total, details = 0.0, []
    for lab, sign, v24, _pg in recipe:
        hits = by_label.get(lookup.norm(lab)) or []
        # 1st choice: the line whose SECOND number equals the FY24 value we
        # learned (current | prior layout) — proof it is the same line
        best = next(((ns, pn) for ns, pn in hits
                     if len(ns) >= 2 and abs(abs(ns[1]) - abs(v24)) <= 1.0), None)
        if best is None:  # fall back: old value anywhere on the line, neighbour left
            for ns, pn in hits:
                for i in range(1, len(ns)):
                    if abs(abs(ns[i]) - abs(v24)) <= 1.0:
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
