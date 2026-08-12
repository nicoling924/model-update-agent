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
    # 0. spec-declared rules FIRST — analyst knowledge outranks all automation
    rule0 = row.get("backout_rule")
    if rule0:
        entry = _apply_rule(rule0, row, staging)
        if entry:
            return entry
    # 0.5 learned identity from the workbook's own _UPDATE_MAP memory tab:
    # the learner already established WHICH disclosure line feeds this row
    mem = row.get("memory")
    pv0 = row.get("prior_value")
    if mem and mem.get("kind") == "input" and mem.get("label"):
        hits = [it for it in staging["items"]
                if norm(it.get("label")) == norm(mem["label"])
                and isinstance(it.get("value"), (int, float))
                and (not mem.get("stmt") or it.get("stmt") == mem.get("stmt"))]
        if hits:
            best = hits[0]
            if isinstance(pv0, (int, float)) and pv0:
                best = min(hits, key=lambda it: abs(abs(it.get("prior") or 1e18) - abs(pv0)))
            v = -best["value"] if mem.get("sign_flip") else best["value"]
            corro = (isinstance(pv0, (int, float)) and pv0
                     and isinstance(best.get("prior"), (int, float))
                     and abs(abs(best["prior"]) - abs(pv0)) <= max(1.0, 0.02 * abs(pv0)))
            kin = _overlap(row.get("label"), mem["label"])
            entry = {"value": v, "source": "memory-identity",
                     "flag": None if (corro and kin) else "red",
                     "note": (f"memory identity: '{mem['label']}' p{best.get('page')}"
                              + ("" if corro else " (prior not corroborated — verify)")),
                     "page": best.get("page")}
            return entry
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
        # guard against coincidental prior collisions: unrelated label -> flag
        if _overlap(row["label"], tri[0]["label"]):
            return _accept(tri[0], row, "triangulated")
        entry = _accept(tri[0], row, "triangulated (label mismatch)")
        entry["flag"] = "red"
        entry["note"] = (f"PRIOR-COLLISION RISK: matched '{tri[0]['label']}' by prior "
                         "value only, labels unrelated — verify. ") + (entry["note"] or "")
        return entry
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


def _apply_rule(rule, row, staging):
    if rule and rule.get("components"):
        # composition by disclosure label, with optional '-'/'+' sign prefix.
        # Accepted ONLY if the same composition over PRIOR values reproduces the
        # model's stored prior — self-corroboration against sign/label surprises.
        parts, prior_sum, pages, ok = [], 0.0, [], True
        for comp in rule["components"]:
            sign = -1.0 if comp.startswith("-") else 1.0
            spec_part = comp.lstrip("+-")
            stmt = None
            if ":" in spec_part:  # optional statement qualifier, e.g. 'bs:trade payables'
                stmt, spec_part = spec_part.split(":", 1)
            cn = norm(spec_part)
            pool = [it for it in staging["items"]
                    if isinstance(it.get("value"), (int, float))
                    and (stmt is None or it.get("stmt") == stmt)]
            hits = [it for it in pool if norm(it["label"]) == cn]  # exact label first
            if not hits:
                hits = [it for it in pool if cn in norm(it["label"])]
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
        if ok:
            f = "".join(("+" if p >= 0 else "-") + (str(int(abs(p))) if p == int(p) else str(abs(p)))
                        for p in parts)
            f = "=" + (f[1:] if f.startswith("+") else f)
            # analyst DECLARED this composition; uncorroborated -> deliver flagged,
            # never silently drop it (definition may have changed vs prior year)
            return {"formula": f, "source": "backout-components",
                    "flag": None if corroborated else "red",
                    "note": (f"Composition per spec: {' '.join(rule['components'])} "
                             f"(pages {pages}; "
                             + (f"prior corroborated {prior_sum})" if corroborated else
                                f"PRIOR MISMATCH {prior_sum} vs model {pv} — definition "
                                "may have changed, verify)")), "page": pages[0]}
    if rule and rule.get("method"):
        return {"formula": rule["method"], "source": "backout", "flag": "orange",
                "note": f"Backed out: {rule['method']} (per spec back-out rule)", "page": None}
    return None


_CONSTS = re.compile(r"^=\s*\+?[+-]?\d+(?:\.\d+)?(?:\s*[+-]\s*\d+(?:\.\d+)?)+\s*$")
_TERM = re.compile(r"([+-]?)\s*(\d+(?:\.\d+)?)")
_STOP = {"and", "of", "in", "the", "net", "total", "other", "for"}


def _overlap(a, b):
    wa = {w for w in norm(a).split() if w not in _STOP and len(w) > 2}
    wb = {w for w in norm(b).split() if w not in _STOP and len(w) > 2}
    return bool(wa & wb) or not wa


SCALARS = {10, 12, 52, 100, 365, 1000, 8760, 10000}  # unit/time scalars, never data


def rewrite_constants(formula, staging):
    """Rewrite prior-year constants embedded in a MIXED formula (refs + constants).
    Each constant >=10 (non-scalar) triangulates (consensus) prior->current;
    returns (new_formula, all_resolved, unresolved_tokens). Unresolved literal
    tokens can be retried by component-level landmark reads."""
    from .extraction import find_by_prior
    all_ok = True
    unresolved = []

    def sub(m):
        nonlocal all_ok
        c = float(m.group(0))
        if abs(c) < 10 or c in SCALARS:
            return m.group(0)
        hits = find_by_prior(staging, c) or \
            [dict(h, value=-h["value"]) for h in find_by_prior(staging, -c)]
        vals = [h.get("value") for h in hits if isinstance(h.get("value"), (int, float))]
        if not vals or max(vals) - min(vals) > 1.0:
            all_ok = False
            unresolved.append(m.group(0))
            return m.group(0)
        v = vals[0]
        # plausibility: same sign, sane YoY ratio — else likely a prior collision
        if v * c < 0 or not (0.4 <= abs(v) / abs(c) <= 2.5):
            all_ok = False
            unresolved.append(m.group(0))
            return m.group(0)
        return str(int(v)) if v == int(v) else str(v)

    # match standalone numeric literals not part of cell refs (AH69) or row digits
    new = re.sub(r"(?<![A-Za-z0-9_.])\d+(?:\.\d+)?(?![A-Za-z0-9_.])", sub, formula)
    return new, all_ok, unresolved


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
        if cur * signed < 0 or not (0.4 <= abs(cur) / abs(signed) <= 2.5):
            return None  # prior collision — implausible YoY move for a component
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
    entry = {"value": item["value"], "source": how, "flag": None,
             "note": f"{item['label']}, {item.get('doc','')} p{item['page']}",
             "page": item["page"]}
    pv = row.get("prior_value") if isinstance(row, dict) else None
    v = entry["value"]
    if isinstance(pv, (int, float)) and isinstance(v, (int, float)) \
            and pv != 0 and v != 0 and (v < 0) != (pv < 0):
        # model's stored sign convention wins; genuine sign changes surface flagged
        entry["value"] = -v
        entry["flag"] = "red"
        entry["note"] = ("SIGN HARMONIZED to model convention (disclosure printed "
                         f"{v}) — verify. " + entry["note"])
    if item.get("disputed"):
        entry["flag"] = "red"
        entry["note"] = ("DISPUTED between extraction passes — verify. " + entry["note"])
    return entry


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
