"""Stage 2: build the worklist — model row -> value/formula/flag, via the cascade.

Order (stop at first success), ONE pass per row, enforced here in code:
 1. direct label find (glossary + per-company aliases)
 2. triangulation on the model's stored prior-year value        <- primary weapon
 3. per-company back-out rule (formula over staging items)
 4. LLM mapping call (budgeted: exactly one; must name a validating tie)
 5. estimate = hold prior-year ratio/value, flag light-red, record where we looked

Acceptance for 1-4: the mapped value must RECONCILE (pass its tie) or it degrades
to step 5. Label plausibility alone never accepts a mapping.
"""
import json
import re


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def build_glossary(cfg, spec):
    g = {}
    for canon, alts in (cfg.get("glossary") or {}).items():
        g[norm(canon)] = norm(canon)
        for a in alts or []:
            g[norm(a)] = norm(canon)
    for canon, alts in (spec.get("aliases") or {}).items():
        g[norm(canon)] = norm(canon)
        for a in alts or []:
            g[norm(a)] = norm(canon)
    return g


def resolve_row(row, staging, glossary, client, system, mapping_prompt, cfg, log):
    """row: {sheet, row, label, prior_value, prior_formula, kind}
    Returns worklist entry: {value|formula, source, flag, note, page}."""
    # 1. direct find — accepted ONLY with prior-year corroboration (an uncorroborated
    # label match is the classic definition-mismatch trap: plausible, wrong, unflagged)
    target = glossary.get(norm(row["label"]), norm(row["label"]))
    cands = [it for it in staging["items"]
             if glossary.get(norm(it["label"]), norm(it["label"])) == target]
    pv = row.get("prior_value")
    if len(cands) == 1 and isinstance(pv, (int, float)) and \
            isinstance(cands[0].get("prior"), (int, float)) and \
            abs(abs(cands[0]["prior"]) - abs(pv)) <= 1.0:
        it = cands[0]
        if (it["prior"] < 0) != (pv < 0) and pv != 0:
            it = dict(it, value=-it["value"])
        return _accept(it, row, "direct+prior-corroborated")
    # 1b. constant-composition prior formula: structure-preserving, self-validating
    comp = _recompose(row.get("prior_formula"), staging)
    if comp:
        return {"formula": comp, "source": "recomposed",
                "flag": None, "note": f"components triangulated from prior constants "
                f"in {row.get('prior_formula')}", "page": None}
    # 2. triangulation on prior-year number
    from .extraction import find_by_prior
    tri = find_by_prior(staging, row.get("prior_value"))
    if len(tri) == 1:
        return _accept(tri[0], row, "triangulated")
    if len(tri) > 1:
        # same figure quoted in several places (statement + note + summary):
        # if every candidate agrees on the current value, they are duplicates
        vals = [t.get("value") for t in tri if isinstance(t.get("value"), (int, float))]
        if vals and max(vals) - min(vals) <= 1.0 and len(vals) == len(tri):
            return _accept(tri[0], row, "triangulated (multi-source consensus)")
        same = [t for t in tri if glossary.get(norm(t["label"]), norm(t["label"])) == target]
        if len(same) == 1:
            return _accept(same[0], row, "triangulated+label")
    if not tri and isinstance(row.get("prior_value"), (int, float)) and row["prior_value"]:
        # sign convention: model stores deductions negative, disclosures print positive
        neg = find_by_prior(staging, -row["prior_value"])
        nvals = [t.get("value") for t in neg if isinstance(t.get("value"), (int, float))]
        if nvals and (len(neg) == 1 or max(nvals) - min(nvals) <= 1.0):
            it = dict(neg[0])
            it["value"] = -it["value"]
            return _accept(it, row, "triangulated (sign-flipped)")
    # 2c. exact-label candidates with graduated prior tolerance: model priors are
    # sometimes DERIVED (formulas), not disclosed actuals — allow a near match on
    # the closest prior, unflagged when tight, red-flagged when loose
    exact = [it for it in staging["items"] if norm(it["label"]) == norm(row["label"])
             and isinstance(it.get("value"), (int, float))
             and isinstance(it.get("prior"), (int, float))]
    if exact and isinstance(pv, (int, float)) and pv:
        best = min(exact, key=lambda it: abs(it["prior"] - pv))
        d = abs(best["prior"] - pv)
        if d <= max(1.0, 0.02 * abs(pv)):
            return _accept(best, row, "label+prior-nearest")
        if d <= 0.15 * abs(pv):
            entry = _accept(best, row, "label+prior-near (loose)")
            entry["flag"] = "red"
            entry["note"] = (f"NEAR-MATCH: disclosure prior {best['prior']} vs model prior "
                             f"{round(pv,1)} ({d/abs(pv)*100:.1f}% off — model prior may be "
                             "derived); verify. ") + (entry["note"] or "")
            return entry
    # 2b. last resort before LLM: a lone label match WITHOUT corroboration is
    # usable but must be flagged for analyst review, never silently accepted
    if len(cands) == 1 and _plausible(cands[0], row):
        entry = _accept(cands[0], row, "label-only (uncorroborated)")
        entry["flag"] = "red"
        entry["note"] = ("UNCORROBORATED label match — prior-year value did not "
                         "confirm it; verify definition. ") + (entry["note"] or "")
        return entry
    # 3. back-out rule
    rule = row.get("backout_rule")
    if rule and rule.get("components"):
        # composition by disclosure label, with optional '-'/'+' sign prefix.
        # Accepted ONLY if the same composition over PRIOR values reproduces the
        # model's stored prior — self-corroboration against sign/label surprises.
        parts, prior_sum, pages, ok = [], 0.0, [], True
        for comp in rule["components"]:
            sign = -1.0 if comp.startswith("-") else 1.0
            cn = norm(comp.lstrip("+-"))
            hits = [it for it in staging["items"]
                    if cn in norm(it["label"]) and isinstance(it.get("value"), (int, float))]
            vals = sorted({round(h["value"], 1) for h in hits})
            if not vals or len(vals) > 1:
                ok = False
                break
            parts.append(sign * vals[0])
            pr = next((h.get("prior") for h in hits if isinstance(h.get("prior"), (int, float))), None)
            prior_sum = prior_sum + sign * pr if pr is not None and prior_sum is not None else None
            pages.append(hits[0].get("page"))
        pv = row.get("prior_value")
        corroborated = (prior_sum is not None and isinstance(pv, (int, float))
                        and abs(prior_sum - pv) <= 1.0)
        if ok and (corroborated or not isinstance(pv, (int, float))):
            f = "".join(("+" if p >= 0 else "-") + (str(int(abs(p))) if p == int(p) else str(abs(p)))
                        for p in parts)
            f = "=" + (f[1:] if f.startswith("+") else f)
            return {"formula": f, "source": "backout-components", "flag": None,
                    "note": f"Composition per spec: {' '.join(rule['components'])} "
                            f"(pages {pages}; prior corroborated {prior_sum})", "page": pages[0]}
    if rule and rule.get("method"):
        return {"formula": rule["method"], "source": "backout", "flag": "orange",
                "note": f"Backed out: {rule['method']} (per spec back-out rule)", "page": None}
    # 4. one LLM call
    if client is not None:
        entry = _llm_map(row, staging, client, system, mapping_prompt, cfg, log)
        if entry:
            return entry
    # 5. estimate + flag
    log.append(f"NOT FOUND {row['sheet']}!r{row['row']} '{row['label']}' — estimate flagged")
    return {"value": row.get("prior_value"), "source": "estimate", "flag": "red",
            "note": ("ESTIMATE: held at prior-period value; figure not located in "
                     "disclosure (searched: statements, notes, segment tables, KPIs)."),
            "page": None}


_CONSTS = re.compile(r"^=\s*[+-]?\d+(?:\.\d+)?(?:\s*[+-]\s*\d+(?:\.\d+)?)+\s*$")
_TERM = re.compile(r"([+-]?)\s*(\d+(?:\.\d+)?)")


def _recompose(prior_formula, staging):
    """=166094+10034 -> =<current fixed assets>+<current ROU>, by triangulating
    each constant on its own prior value. All components must resolve uniquely
    (or by consensus) or we return None and the row falls through the cascade."""
    if not (isinstance(prior_formula, str) and _CONSTS.match(prior_formula)):
        return None
    from .extraction import find_by_prior
    out = []
    for sign, num in _TERM.findall(prior_formula.lstrip("=")):
        c = float(num)
        if c < 10:  # tiny constants (adjustment plugs) rarely appear as lines
            return None
        signed = -c if sign == "-" else c
        hits = find_by_prior(staging, signed) or \
            [dict(h, value=-h["value"]) for h in find_by_prior(staging, -signed)]
        vals = [h.get("value") for h in hits if isinstance(h.get("value"), (int, float))]
        if not vals or max(vals) - min(vals) > 1.0:
            return None
        cur = vals[0]
        out.append(f"{'+' if cur >= 0 else '-'}{abs(int(cur)) if cur == int(cur) else abs(cur)}")
    s = "".join(out)
    return "=" + (s[1:] if s.startswith("+") else s)


def _plausible(item, row):
    """Magnitude sanity: current vs the model's stored prior within 20x."""
    p, v = row.get("prior_value"), item.get("value")
    if not isinstance(p, (int, float)) or not isinstance(v, (int, float)) or p == 0:
        return True
    return abs(v) < abs(p) * 20 + 1000


def _accept(item, row, how):
    return {"value": item["value"], "source": how, "flag": None,
            "note": f"{item['label']}, {item.get('doc','')} p{item['page']}",
            "page": item["page"]}


def _llm_map(row, staging, client, system, mapping_prompt, cfg, log):
    slim = [{k: it[k] for k in ("id", "stmt", "label", "value", "prior", "page")}
            for it in staging["items"]]
    user = (f"{mapping_prompt}\n\nModel row: {json.dumps({k: row.get(k) for k in ('sheet', 'row', 'label', 'prior_value', 'prior_formula')})}\n"
            f"Staging items: {json.dumps(slim)}\n"
            'Schema: {"mapping": "<item_id or composition e.g. pl_3_0 - pl_4_0 or not_found>",'
            ' "tie": "...", "confidence": "high|medium|low", "where_looked": []}')

    def validate(obj):
        errs = []
        if "mapping" not in obj or "confidence" not in obj:
            errs.append("missing mapping/confidence")
        if obj.get("mapping") != "not_found" and not obj.get("tie"):
            errs.append("a mapping requires the arithmetic tie that validates it")
        return errs

    try:
        obj = client.json(system, user, validate,
                          repair_retries=cfg["budgets"]["json_repair_retries"])
    except Exception as e:  # budget spent — degrade to estimate
        log.append(f"LLM mapping failed for {row['sheet']}!r{row['row']}: {e}")
        return None
    if obj["mapping"] == "not_found":
        return None
    ids = {it["id"]: it for it in staging["items"]}
    expr = obj["mapping"]
    # single id -> value; composition -> formula over item values
    if expr in ids:
        value, page = ids[expr]["value"], ids[expr]["page"]
        entry = {"value": value, "page": page}
    else:
        subbed = expr
        for iid, it in sorted(ids.items(), key=lambda kv: -len(kv[0])):
            subbed = subbed.replace(iid, str(it["value"]))
        try:
            value = eval(subbed, {"__builtins__": {}}, {})
        except Exception:
            log.append(f"unparseable composition '{expr}' for {row['sheet']}!r{row['row']}")
            return None
        entry = {"formula": "=" + subbed, "value_check": value, "page": None}
    # LLM self-reported confidence is not corroboration — always flag for review
    entry.update({"source": "llm", "flag": "red",
                  "note": f"LLM-mapped ({obj['confidence']}, uncorroborated — verify): "
                          f"{expr}. Tie: {obj['tie']}"})
    return entry
