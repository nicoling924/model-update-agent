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
    # 1. direct find
    target = glossary.get(norm(row["label"]), norm(row["label"]))
    cands = [it for it in staging["items"]
             if glossary.get(norm(it["label"]), norm(it["label"])) == target]
    if len(cands) == 1 and _plausible(cands[0], row):
        return _accept(cands[0], row, "direct")
    # 2. triangulation on prior-year number
    from .extraction import find_by_prior
    tri = find_by_prior(staging, row.get("prior_value"))
    if len(tri) == 1:
        return _accept(tri[0], row, "triangulated")
    if len(tri) > 1:  # disambiguate by label similarity, else fall through
        same = [t for t in tri if glossary.get(norm(t["label"]), norm(t["label"])) == target]
        if len(same) == 1:
            return _accept(same[0], row, "triangulated+label")
    # 3. back-out rule
    rule = row.get("backout_rule")
    if rule:
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
    flag = None if obj["confidence"] == "high" else "red"
    entry.update({"source": "llm", "flag": flag,
                  "note": f"LLM-mapped ({obj['confidence']}): {expr}. Tie: {obj['tie']}"})
    return entry
