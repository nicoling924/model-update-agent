"""CLI orchestrator — the deterministic state machine that owns the workflow.

    python run.py discover companies/<NAME>
    python run.py update   companies/<NAME> <PERIOD>

The LLM never controls sequencing. Steps, budgets, and gates all live here, so a
weaker model cannot loop, stall, or skip verification.
"""
import re
import shutil
import sys
import time
from pathlib import Path

import yaml

from . import discover as discover_mod
from . import extraction, mapping, report, verify, workbook
from .evaluator import Evaluator
from .llm import Client

ROOT = Path(__file__).resolve().parent.parent


def _load_cfg():
    return yaml.safe_load((ROOT / "config.yaml").read_text())


def _prompt(name):
    return (ROOT / "prompts" / f"{name}.md").read_text()


def _system(company_dir):
    sys_p = _prompt("system")
    spec_md = Path(company_dir) / "MODEL_SPEC.md"
    if spec_md.exists():
        sys_p += "\n\n# Per-company knowledge (MODEL_SPEC)\n" + spec_md.read_text()
    return sys_p


def _model_path(company_dir, spec=None):
    model_dir = Path(company_dir) / "model"
    if spec and spec.get("model_file") and (model_dir / spec["model_file"]).exists():
        return model_dir / spec["model_file"]
    candidates = sorted(model_dir.glob("*.xls[xm]"))
    if not candidates:
        sys.exit(f"No model workbook found in {model_dir}")
    return candidates[0]


def cmd_discover(company_dir):
    cfg = _load_cfg()
    client = Client(temperature=cfg["updater"]["temperature"],
                    max_output_tokens=cfg["updater"]["max_output_tokens"])
    path = discover_mod.discover(client, _system(company_dir), _prompt("discover"),
                                 company_dir, _model_path(company_dir), cfg)
    print(f"Draft spec written: {path}")
    print("REVIEW IT (it is marked draft: true) — the engine refuses to update until "
          "an analyst removes the draft flag.")


def cmd_learn(company_dir, prior_period):
    """Calibration: learn row->disclosure-line identities from the PRIOR year's
    report vs the workbook's own prior actual column; write hidden _UPDATE_MAP."""
    from . import learn as learn_mod
    from . import derive as derive_mod
    from . import objectives as obj_mod
    t0 = time.time()
    cfg = _load_cfg()
    company_dir = Path(company_dir)
    spec = yaml.safe_load((company_dir / "spec.yaml").read_text())
    disclosures = sorted((company_dir / "disclosures" / prior_period).glob("*.pdf"))
    if not disclosures:
        sys.exit(f"No PDFs in disclosures/{prior_period}/ — attach the prior-year report.")
    model_path = _model_path(company_dir, spec)
    wb = workbook.load(model_path)
    if learn_mod.MEMORY_TAB in wb.sheetnames:
        print(f"{learn_mod.MEMORY_TAB} tab already present — memory exists, learner not needed.")
        return
    pre_values = workbook.load(model_path, data_only=True)
    system = _system(company_dir)
    client = Client(temperature=cfg["updater"]["temperature"],
                    max_output_tokens=cfg["updater"]["max_output_tokens"])
    # THE LEARNER, Fable-shaped: the model's own actual column IS the answer
    # key, so calibration is IDENTIFICATION — retrieval finds each row's home
    # pages by its KNOWN value, one holistic call per block points to the line,
    # and code verifies BOTH years' numbers on that line before storing.
    from . import mapper
    from . import lookup as lookup_mod
    from .evaluator import Evaluator as _EvL
    fy24_raw_l = None  # plain view, built once below
    raw24_map = []
    for d_i, d_p in enumerate(disclosures):
        for pn_d, sec_d, ln_d in lookup_mod.raw_lines([d_p]):
            raw24_map.append((d_i * 1000 + pn_d, sec_d, ln_d))
    fy24_raw_l = lookup_mod.raw_lines(disclosures)
    ev_learn = _EvL(wb)
    lrows = []
    for sheet_c, ax_c in spec["year_axis"].items():
        pc_c = ax_c["columns"].get(str(ax_c.get("last_actual")))
        yrs_c = sorted(ax_c.get("columns") or {})
        try:
            i_c = yrs_c.index(str(ax_c.get("last_actual")))
            ppc_c = ax_c["columns"][yrs_c[i_c - 1]] if i_c > 0 else None
        except ValueError:
            ppc_c = None
        hr_c = ax_c.get("header_row", 1)
        if not pc_c or sheet_c not in wb.sheetnames:
            continue
        for r in range(1, min(wb[sheet_c].max_row, 400) + 1):
            v24_c = wb[sheet_c][f"{pc_c}{r}"].value
            if not isinstance(v24_c, (int, float)) or r == hr_c:
                continue
            lab_c = next((wb[sheet_c][f"{lc}{r}"].value for lc in "ABCDEF"
                          if isinstance(wb[sheet_c][f"{lc}{r}"].value, str)), f"row {r}")
            v23_c = None
            if ppc_c:
                try:
                    v23_c = ev_learn.cell(sheet_c, f"{ppc_c}{r}")
                except Exception:
                    pass
            lrows.append({"sheet": sheet_c, "row": r, "label": lab_c,
                          "prior_value": v24_c, "v23": v23_c})
    # EYES for the practice year too: the FY-prior AR may be a scan as well.
    from . import vision as vision_mod
    vision_client_l = Client(temperature=0.0, max_output_tokens=8000)
    for d_i, d_p in enumerate(disclosures):
        vl24 = vision_mod.transcribe_image_pages(
            d_p, vision_client_l, [r["prior_value"] for r in lrows] +
            [r.get("v23") for r in lrows if isinstance(r.get("v23"), (int, float))],
            ".cache/vision", log=lambda m: print(m, flush=True))
        raw24_map += [(d_i * 1000 + pn_v, sec_v, ln_v)
                      for pn_v, sec_v, ln_v in vl24]
        if vl24:
            fy24_raw_l = fy24_raw_l + vl24
    scale_l = mapper.set_doc_scale(
        mapper.detect_scale([r["prior_value"] for r in lrows], raw24_map))
    pv_l_all = [r["prior_value"] for r in lrows]
    mapper.detect_page_scales(pv_l_all, raw24_map)
    mapper.detect_page_scales(pv_l_all, fy24_raw_l)
    if scale_l != 1:
        print(f"[L1u] document units: prints {scale_l:,.0f}x the model's units "
              "(reconciled against the model's own prior-year values)", flush=True)
    lrows = mapper.find_homes(lrows, raw24_map)
    for r_l in lrows:
        r_l["candidate_lines"] = [f"p{pn_l}: {ln_l.strip()[:110]}"
                                  for pn_l, _s_l, ln_l in raw24_map
                                  if mapper.line_has_value(ln_l, r_l["prior_value"])][:4]
        if isinstance(r_l.get("v23"), (int, float)):
            r_l["memory_hint"] = f"prior-prior year value: {r_l['v23']:,.1f}"
    # LEARNER REFOCUS (owner directive): budget goes ONLY to the HARD rows,
    # and difficulty is DISCOVERED, never assumed. Probe: fable-mode reads
    # the PRIOR year's report with the prior-prior value (v23) as the row
    # checksum; a served row whose result ties the workbook's own known
    # prior actual (v24) is EASY — next year's update read will get it
    # unaided, and its memory hint would be redundant (fable-mode serves
    # before the mapper ever looks). Everything else — unserved, mistied,
    # or unprobeable (no v23) — is the discovered hard set (for DFE this
    # surfaced the Driver/PPE blocks; other companies differ), and the
    # whole identification budget concentrates there.
    from . import fablemode
    probe_rows = [dict(r_p, prior_value=r_p["v23"]) for r_p in lrows
                  if isinstance(r_p.get("v23"), (int, float))]
    easy = set()
    if probe_rows:
        probe_client = Client(temperature=0.0, max_output_tokens=14000)
        plog = []
        try:
            probe = fablemode.region_read(probe_client, disclosures,
                                          probe_rows, plog)
        except Exception as ex_p:
            probe, plog = {}, plog + [f"probe failed: {ex_p}"]
        for ln_p in plog:
            print(f"    [L0] {ln_p}", flush=True)
        known_l = {(r_p["sheet"], r_p["row"]): r_p["prior_value"]
                   for r_p in lrows}
        for key_p, e_p in probe.items():
            pv_p = known_l.get(key_p)
            if isinstance(pv_p, (int, float)) and \
                    abs(e_p["value"] - pv_p) <= workbook.row_tol(pv_p):
                easy.add(key_p)
    lrows_hard = [r_p for r_p in lrows
                  if (r_p["sheet"], r_p["row"]) not in easy]
    print(f"[L0] refocus probe: {len(easy)}/{len(lrows)} rows EASY "
          f"(fable-read of the prior report ties the known actual — no "
          f"learner budget spent); {len(lrows_hard)} in the discovered "
          f"HARD set", flush=True)
    blocks_l = mapper.cluster(lrows_hard)
    print(f"[L1] retrieval: {sum(1 for r in lrows if r['pages'])}/{len(lrows)} "
          f"rows located, {len(blocks_l)} blocks (hard set only)", flush=True)
    lm_prompt = _prompt("learn_map")
    identified = {}
    for bi_l, b_l in enumerate(blocks_l):
        try:
            identified.update(mapper.map_block(client, system, lm_prompt, b_l,
                                               raw24_map, cfg))
        except Exception as ex_l:
            print(f"    [L1] block failed ({ex_l})", flush=True)
    # CODE VERIFICATION: the identified line must print the known FY24 value
    # (and FY23 beside it when we know it) — identification without arithmetic
    # proof is not stored
    raw_by_page_l = {}
    for pn_l, _s_l, ln_l in raw24_map:
        raw_by_page_l.setdefault(pn_l, []).append(ln_l)
    entries = []
    n_ver = n_rej = n_soft = 0
    for r_l in lrows:
        m_l = identified.get((r_l["sheet"], r_l["row"]))
        if not m_l or m_l.get("status") != "OK" or not m_l.get("line"):
            continue
        try:  # the reader answers "p46" as often as 46 — digits only
            pg_l = int(re.sub(r"[^0-9]", "", str(m_l.get("page"))) or "x")
        except ValueError:
            continue
        window_l = [(q, ln_q) for q in (pg_l - 1, pg_l, pg_l + 1)
                    for ln_q in raw_by_page_l.get(q, [])]
        lab_norm_l = lookup_mod.norm(str(m_l["line"]))
        verified = prior_hit = False
        for q_l, ln_l in window_l:
            if lab_norm_l[:24] not in lookup_mod.norm(ln_l):
                continue
            ns_l = lookup_mod.line_nums(ln_l)
            if mapper.num_matches(ns_l, r_l["prior_value"], page=q_l):
                prior_hit = True
                v23_l = r_l.get("v23")
                if isinstance(v23_l, (int, float)) and abs(v23_l) > 1:
                    verified = mapper.num_matches(ns_l, v23_l, page=q_l)
                else:
                    verified = True
                if verified:
                    break
        if verified or prior_hit:
            # SINGLE-YEAR identification is still an identity: MD&A stats and
            # segment tables print one year + % changes, never two years on a
            # line — demanding both years rejected every such row (the whole
            # Driver operating block). Both-years stays the gold standard;
            # single-year is stored as a hint (label+page), never a value.
            entries.append({"sheet": r_l["sheet"], "row": r_l["row"],
                            "kind": "input", "label": str(m_l["line"])[:80],
                            "page": pg_l % 1000,
                            "soft": (not verified) or None,
                            "sign_flip": (r_l["prior_value"] < 0)})
            n_ver += verified
            n_soft += (not verified)
        else:
            n_rej += 1
    print(f"[L2] identified {len(identified)}; VERIFIED (both-years arithmetic) "
          f"{n_ver}; single-year identities {n_soft}; rejected {n_rej}", flush=True)
    # diagnostic: verified+soft+rejected == 0 across runs 98-102 means every
    # entry failed the FIRST filter — show what the identification actually said
    from collections import Counter as _CL
    st_l = _CL(str((m or {}).get("status")) for m in identified.values())
    ex_l = [m for m in identified.values() if m][:2]
    print(f"[L2x] identification statuses: {dict(st_l)}; "
          f"examples: {[{k: str(v)[:40] for k, v in e.items()} for e in ex_l]}",
          flush=True)
    # ANALYST PRACTICE: rows that DON'T reconcile are findings, not failures.
    # For each material non-reconciling row: try a composition recipe (the
    # analyst's construction), else ask WHY in one reasoning batch — the
    # hypothesis is stored as a QUIRK the cold run gets told about.
    ver_keys = {(e["sheet"], e["row"]) for e in entries}
    hard_rows = sorted((r_l for r_l in lrows
                        if (r_l["sheet"], r_l["row"]) not in ver_keys
                        and isinstance(r_l["prior_value"], (int, float))),
                       key=lambda r: -abs(r["prior_value"]))[:20]
    n_recipe2 = 0
    for r_h in hard_rows[:]:
        v23_h = r_h.get("v23")
        rec_h = derive_mod.learn_composition(
            r_h["prior_value"], v23_h if isinstance(v23_h, (int, float)) else None,
            fy24_raw_l, [""], max_terms=3)
        if rec_h:
            entries.append({"sheet": r_h["sheet"], "row": r_h["row"],
                            "kind": "bridge_row", "label": str(r_h["label"])[:60],
                            "components": [{"label": l_h, "sign": s_h, "v24": v_h}
                                           for (l_h, s_h, v_h, _p) in rec_h]})
            hard_rows.remove(r_h)
            n_recipe2 += 1
    print(f"[L2d] non-reconciling rows: {n_recipe2} constructions recovered, "
          f"{len(hard_rows)} sent to reasoning", flush=True)
    if hard_rows:
        import json as _jq
        qlist = [{"id": f"{r_h['sheet']}!{r_h['row']}", "label": str(r_h["label"])[:50],
                  "model_fy24": r_h["prior_value"],
                  "nearest_lines": (r_h.get("candidate_lines") or [])[:2]}
                 for r_h in hard_rows]
        try:
            qresp = client.json(
                "You are an equity analyst studying a model you are inheriting.",
                "These model rows do NOT reconcile to any disclosed line for the "
                "known year. For each, give a one-line hypothesis WHY (reclassified"
                " like interest in OCF? netted? analyst-derived from a ratio? "
                "one-off reset?). Return {\"quirks\": [{\"id\": ..., "
                "\"why\": \"...\"}]}\n" + _jq.dumps(qlist),
                lambda o: [] if isinstance(o.get("quirks"), list) else ["missing quirks"],
                repair_retries=1)
            for q_h in qresp.get("quirks", []):
                mm_q = re.match(r"^([^!]+)!(\d+)$", str(q_h.get("id", "")))
                if mm_q:
                    entries.append({"sheet": mm_q.group(1), "row": int(mm_q.group(2)),
                                    "kind": "quirk",
                                    "section": str(q_h.get("why", ""))[:170]})
            print(f"[L2e] quirks reasoned: {len(qresp.get('quirks', []))}", flush=True)
        except Exception as ex_q:
            print(f"[L2e] quirk reasoning skipped ({ex_q})", flush=True)
    staging = {"items": [], "ties": []}
    census = {}
    merged = {(e["sheet"], e["row"]): e for e in entries}
    det = learn_mod.deterministic_identities(disclosures, wb, pre_values, spec)
    for k, e in det.items():
        merged.setdefault(k, {"sheet": k[0], "row": k[1],
                              **{kk: vv for kk, vv in e.items() if kk != "method"}})
    print(f"[L2b] deterministic identities added: {len(det)}", flush=True)
    recipes = learn_mod.component_recipes(disclosures, wb, pre_values, spec)
    print(f"[L2c] component recipes: {len(recipes)} composite rows", flush=True)
    entries = recipes + list(merged.values())
    # v6: DEFINITIONAL BRIDGES for keys the disclosure prints differently
    # (model CFO = statutory CFO +/- reclassifications). Mechanical recipe
    # first; LLM REASONING fallback — every hypothesis double-locked on
    # FY24 AND FY23 before it may be stored. FY24-only: fair for cold runs.
    from .evaluator import Evaluator as _Ev
    key_log = []
    km_l = obj_mod.locate(spec, wb, key_log)
    # English AND Chinese section markers — English-only left the bridge menu
    # EMPTY on CN filings (the LLM returned empty bridges; double-lock failed
    # at 0.0 on every DFE run 95-99)
    CF_SECT = ["cash flow", "operating activities", "investing activities",
               "financing activities", "现金流量", "经营活动", "投资活动", "筹资活动"]
    ev_l = _Ev(wb)
    n_bridges = 0
    for kind_l in ("cfo", "cfi", "cff"):
        loc_l = km_l.get(kind_l)
        if not loc_l:
            continue
        ax_l = spec["year_axis"].get(loc_l["sheet"]) or {}
        yrs_l = sorted(ax_l.get("columns") or {})
        la_l = str(ax_l.get("last_actual"))
        try:
            i_l = yrs_l.index(la_l)
            pc_l = ax_l["columns"][la_l]
            ppc_l = ax_l["columns"][yrs_l[i_l - 1]] if i_l > 0 else None
            v24_l = ev_l.cell(loc_l["sheet"], f"{pc_l}{loc_l['row']}")
            v23_l = ev_l.cell(loc_l["sheet"], f"{ppc_l}{loc_l['row']}") if ppc_l else None
        except Exception:
            continue
        if not isinstance(v24_l, (int, float)):
            continue
        recipe_l = derive_mod.learn_composition(v24_l, v23_l, fy24_raw_l, CF_SECT,
                                                max_terms=5)
        why_l = "mechanical composition (double-locked 2 years)"
        if recipe_l is None:
            blog = []
            v25_chk, why_b = derive_mod.llm_bridge(client, kind_l, v24_l, v23_l,
                                                   fy24_raw_l, fy24_raw_l,
                                                   CF_SECT, blog)
            for bl in blog:
                print("   ", bl[:130], flush=True)
            # llm_bridge replays on the raw passed as fy25 — here FY24 itself,
            # so success means the recipe verified; rebuild recipe from its log
            recipe_l = None if v25_chk is None else "LLM"
            if recipe_l == "LLM":
                # re-run learn path capturing terms via a fresh bridge call is
                # avoided: store the reasoning + re-derive at update by bridge
                entries.append({"sheet": loc_l["sheet"], "row": loc_l["row"],
                                "kind": "bridge_reason", "label": kind_l,
                                "section": (why_b or "")[:180]})
                n_bridges += 1
                continue
        if recipe_l and recipe_l != "LLM":
            comps_l = [{"label": lab_r, "sign": sg_r, "v24": v_r}
                       for (lab_r, sg_r, v_r, _p) in recipe_l]
            entries.append({"sheet": loc_l["sheet"], "row": loc_l["row"],
                            "kind": "bridge", "label": kind_l,
                            "components": comps_l})
            n_bridges += 1
            print(f"    [L1e] bridge {kind_l}: {len(comps_l)} terms ({why_l})",
                  flush=True)
    print(f"[L1e] definitional bridges learned: {n_bridges}", flush=True)
    n = learn_mod.write_memory_tab(wb, entries)
    workbook.save(wb, model_path)
    wb2 = workbook.load(model_path)
    assert learn_mod.MEMORY_TAB in wb2.sheetnames
    kinds = {}
    for e in entries:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(f"[L2] learned {n} identities {kinds} -> hidden {learn_mod.MEMORY_TAB} tab "
          f"written (privacy-safe metadata only). {(time.time()-t0)/60:.1f} min")


def cmd_digest(company_dir, period):
    """Read the period's disclosures carefully ONCE (3 passes, union-merged,
    raw-corroborated) and freeze the result beside the PDFs. Updates then run
    variance-free on the frozen digest."""
    from . import digest as digest_mod
    cfg = _load_cfg()
    company_dir = Path(company_dir)
    disclosures = sorted((company_dir / "disclosures" / period).glob("*.pdf"))
    if not disclosures:
        sys.exit(f"No PDFs in disclosures/{period}/")
    system = _system(company_dir)
    client = Client(temperature=cfg["updater"]["temperature"],
                    max_output_tokens=cfg["updater"]["max_output_tokens"])
    sig = digest_mod.signature(disclosures, _prompt("extraction"), system, client.model)
    out = company_dir / "disclosures" / period / "digest.json"
    digest_mod.build(client, system, disclosures, _prompt("extraction"), cfg, out, sig)
    print(f"LLM provenance: {client.usage}")


def cmd_update(company_dir, period):
    t0 = time.time()
    cfg = _load_cfg()
    company_dir = Path(company_dir)
    spec_path = company_dir / "spec.yaml"
    if not spec_path.exists():
        sys.exit("No spec.yaml — run `discover` first (then review it).")
    spec = yaml.safe_load(spec_path.read_text())
    if spec.get("draft"):
        sys.exit("spec.yaml is a draft — an analyst must review it and set draft: false.")
    disclosures = sorted((company_dir / "disclosures" / period).glob("*.pdf"))
    if not disclosures:
        sys.exit(f"No PDFs in disclosures/{period}/ — attach the results documents.")

    system = _system(company_dir)
    client = Client(temperature=cfg["updater"]["temperature"],
                    max_output_tokens=cfg["updater"]["max_output_tokens"])
    name = company_dir.name
    model_path = _model_path(company_dir, spec)

    # -- 1. setup: archive, snapshots ---------------------------------------
    archive = company_dir / "model-archive" / f"{name}_{period}_pre{model_path.suffix}"
    archive.parent.mkdir(exist_ok=True)
    shutil.copy2(model_path, archive)
    pre_wb = workbook.load(model_path)
    pre_map = workbook.formula_map(pre_wb)
    pre_values = workbook.load(model_path, data_only=True)
    print(f"[1] archived -> {archive.name}")

    # target = first forecast column after last actual, per year_axis
    stmts_sheet = next(s for s, v in spec["sheets"].items()
                       if (v or {}).get("role") == "statements")
    axis = spec["year_axis"][stmts_sheet]
    cols = axis["columns"]
    years = sorted(cols)
    last_actual = str(axis["last_actual"])
    target_year = years[years.index(last_actual) + 1]
    prior_col, target_col = cols[last_actual], cols[target_year]
    # A HUMAN ROLLS EVERY TAB TOGETHER: any year-axis sheet missing the target
    # period gets its column CREATED next to the last actual (the analyst's
    # insert-new-year move) — partial rollovers are how circulars are born
    from openpyxl.utils import column_index_from_string, get_column_letter
    for sheet_x, ax_x in spec["year_axis"].items():
        cols_x = ax_x.get("columns") or {}
        la_x = str(ax_x.get("last_actual") or last_actual)
        if target_year in cols_x or la_x not in cols_x:
            continue
        new_col_x = get_column_letter(column_index_from_string(cols_x[la_x]) + 1)
        occupied = False
        if sheet_x in pre_wb.sheetnames:
            ws_x = pre_wb[sheet_x]
            occupied = any(ws_x[f"{new_col_x}{r_x}"].value is not None
                           for r_x in range(1, min(ws_x.max_row, 200) + 1))
        if occupied:
            print(f"[1x] {sheet_x}: cannot create {target_year} column "
                  f"({new_col_x} occupied) — flagged for analyst", flush=True)
            continue
        cols_x[target_year] = new_col_x
        print(f"[1x] {sheet_x}: {target_year} column {new_col_x} created "
              "(axis extended, will roll over)", flush=True)
    spec["_target_cols"] = [cols_.get(target_year) for cols_ in
                            [a.get("columns", {}) for a in spec["year_axis"].values()]]
    spec["_target_cols"] = [c for c in spec["_target_cols"] if c]
    est_snapshot = workbook.snapshot_column(pre_values, stmts_sheet, cols[target_year])
    print(f"[1] target: {target_year} (col {target_col}); prior actual: {last_actual} ({prior_col})")

    # -- 2. DIRECT MAPPING: the brain reads, the hands verify -----------------
    # Retrieval (code): every row's home pages via prior-value Ctrl+F across the
    # whole document — statements, notes, statistics tables alike. Then ONE
    # holistic LLM call per block: pages + rows -> mapped values. Then audit.
    from . import mapper
    from . import learn as learn_mod
    from . import lookup as lookup_mod
    map_client = Client(temperature=cfg["updater"]["temperature"],
                        max_output_tokens=cfg["budgets"].get("mapping_output_tokens", 3000))
    memory = learn_mod.read_memory_tab(pre_wb)
    census = {}
    for sheet_c, ax_c in spec["year_axis"].items():
        pc_c = ax_c["columns"].get(last_actual)
        hr_c = ax_c.get("header_row", 1)
        if not pc_c or sheet_c not in pre_wb.sheetnames:
            continue
        rows_c = set((spec.get("input_vs_formula") or {}).get(sheet_c, {}).get("input_rows", []))
        wsf = pre_wb[sheet_c]
        for r in range(1, min(wsf.max_row, 400) + 1):
            if isinstance(wsf[f"{pc_c}{r}"].value, (int, float)):
                rows_c.add(r)
        rows_c.discard(hr_c)
        census[sheet_c] = sorted(rows_c)
    # STRUCTURAL SELF-AWARENESS: follow each statement row's prior-year formula
    # to where its number is actually TYPED. On link-through models the Model
    # tab is a view — the input site is the source sheet — and the view's
    # English label is the best identifier for that (possibly Chinese) row.
    # Built BEFORE the census loop that reads it (run-95 binding-order crash).
    site_labels = {}
    for sheet_v, ax_v in spec["year_axis"].items():
        if sheet_v not in pre_wb.sheetnames:
            continue
        pc_v = (ax_v.get("columns") or {}).get(last_actual)
        if not pc_v:
            continue
        for r_v in range(1, min(pre_wb[sheet_v].max_row, 400) + 1):
            cellv = pre_wb[sheet_v][f"{pc_v}{r_v}"].value
            if not (isinstance(cellv, str) and cellv.startswith("=")):
                continue
            site = workbook.resolve_input_site(pre_wb, sheet_v, r_v, pc_v)
            if not site or site == (sheet_v, r_v):
                continue
            lab_v = next((pre_wb[sheet_v][f"{lc}{r_v}"].value for lc in "ABCDEF"
                          if isinstance(pre_wb[sheet_v][f"{lc}{r_v}"].value, str)), None)
            if lab_v and site not in site_labels:
                site_labels[site] = f"{sheet_v} row {r_v} calls this '{str(lab_v)[:40]}'"
    if site_labels:
        print(f"[1s] link-through model: {len(site_labels)} input sites identified "
              "in source sheets (view labels carried across)", flush=True)

    all_rows = []
    for sheet_c, rows_c in census.items():
        ax_c = spec["year_axis"][sheet_c]
        pc_c = ax_c["columns"].get(last_actual)
        wsp = pre_values[sheet_c]
        for r in rows_c:
            lab = next((wsp[f"{lc}{r}"].value for lc in "ABCDEF"
                        if isinstance(wsp[f"{lc}{r}"].value, str)), f"row {r}")
            m_e = memory.get((sheet_c, r)) or {}
            hint_c = m_e.get("label")
            view_c = site_labels.get((sheet_c, r))
            if view_c:
                hint_c = f"{hint_c or ''} [{view_c}]".strip()
            all_rows.append({"sheet": sheet_c, "row": r, "label": lab,
                             "prior_value": pre_wb[sheet_c][f"{pc_c}{r}"].value,
                             "memory_hint": hint_c,
                             "memory_page": m_e.get("page")})
    # NO-PRIOR HOLES (run-115 reflection): labeled rows with an EMPTY prior
    # sitting INSIDE a dense census block are new line items (使用权资产折旧 had
    # no prior year and was never even asked). Add them for fable-mode's
    # complete-coverage read — marked so the mapper machinery ignores them.
    n_holes = 0
    for sheet_c, rows_c in census.items():
        if not rows_c or sheet_c not in pre_values.sheetnames:
            continue
        wsp = pre_values[sheet_c]
        have = set(rows_c)
        for i_h in range(len(rows_c) - 1):
            a_h, b_h = rows_c[i_h], rows_c[i_h + 1]
            if not (1 < b_h - a_h <= 8):
                continue
            for r_h in range(a_h + 1, b_h):
                if r_h in have:
                    continue
                lab_h = next((wsp[f"{lc}{r_h}"].value for lc in "ABCDEF"
                              if isinstance(wsp[f"{lc}{r_h}"].value, str)), None)
                if lab_h and str(lab_h).strip():
                    all_rows.append({"sheet": sheet_c, "row": r_h,
                                     "label": str(lab_h).strip(),
                                     "prior_value": None,
                                     "no_prior_hole": True})
                    n_holes += 1
    if n_holes:
        print(f"[1h] {n_holes} no-prior rows inside census blocks added for "
              "the complete-coverage read (new line items)", flush=True)
    raw_all = lookup_mod.raw_lines(disclosures)
    # MAPPER view: document-qualified page ids (doc_i*1000 + page) so the AR's
    # p184 and the announcement's p25 never mix in one "page" — the run-45
    # cross-PDF collision. Audit/objectives keep the plain view.
    raw_map = []
    for d_i, d_p in enumerate(disclosures):
        for pn_d, sec_d, ln_d in lookup_mod.raw_lines([d_p]):
            raw_map.append((d_i * 1000 + pn_d, sec_d, ln_d))
    for r in all_rows:  # memory page hints (per-doc scheme) vote in every doc
        if r.get("memory_page"):
            r["memory_page"] = None  # ambiguous across docs — label/prior carry it
    # EYES: image-only pages (scanned statements) transcribed by the SAME
    # engine's vision, checksum-verified against the model's own prior values,
    # then injected as ordinary raw lines — downstream works unchanged.
    # Dedicated client: a 57-row statement page needs ~5k output tokens; the
    # 3k mapping budget truncated the JSON mid-string and run 98 lost the
    # consolidated CF page (p101) to "Unterminated string".
    from . import vision
    vision_client = Client(temperature=0.0, max_output_tokens=8000)
    for d_i, d_p in enumerate(disclosures):
        vl = vision.transcribe_image_pages(
            d_p, vision_client, [r.get("prior_value") for r in all_rows],
            ".cache/vision", log=lambda m: print(m, flush=True))
        raw_map += [(d_i * 1000 + pn_v, sec_v, ln_v) for pn_v, sec_v, ln_v in vl]
        raw_all += vl
    # DOCUMENT UNITS before any retrieval: on a filing printed in other units
    # (a CN annual report in yuan vs a model in millions) prior-value Ctrl+F
    # finds nothing and every proof fails, for no reason but the scale.
    doc_scale = mapper.set_doc_scale(
        mapper.detect_scale([r.get("prior_value") for r in all_rows], raw_map))
    if doc_scale != 1:
        print(f"[2u] document units: prints {doc_scale:,.0f}x the model's units "
              "(reconciled against the model's own prior-year values)", flush=True)
    pv_all = [r.get("prior_value") for r in all_rows]
    ps_u = mapper.detect_page_scales(pv_all, raw_map)
    mapper.detect_page_scales(pv_all, raw_all)
    if ps_u:
        print(f"[2u] page units: {len(ps_u)} pages reconcile at their OWN scale "
              f"(e.g. 万元 MD&A tables): {sorted(set(ps_u.values()))}", flush=True)
    all_rows = mapper.find_homes(all_rows, raw_map)
    # statements-sheet rows with no home inherit their sheet's modal home pages
    from collections import Counter as _C0
    sheet_mode = {}
    for r in all_rows:
        if r["pages"]:
            sheet_mode.setdefault(r["sheet"], _C0()).update(r["pages"][:2])
    for r in all_rows:
        if not r["pages"] and r["sheet"] in sheet_mode:
            r["pages"] = [p for p, _n in sheet_mode[r["sheet"]].most_common(4)]
    for r in all_rows:
        pv_a = r.get("prior_value")
        if isinstance(pv_a, (int, float)) and abs(pv_a) >= 10:
            r["candidate_lines"] = [f"p{pn_a}: {ln_a.strip()[:110]}"
                                    for pn_a, _s_a, ln_a in raw_map
                                    if mapper.line_has_value(ln_a, pv_a, page=pn_a)][:4]
    # no-prior holes are fable-only: the mapper machinery never sees them
    blocks = mapper.cluster([r for r in all_rows if not r.get("no_prior_hole")])
    n_home = sum(1 for r in all_rows if r["pages"])
    print(f"[2] retrieval: {n_home}/{len(all_rows)} rows located "
          f"({len(blocks)} blocks) across {len(raw_all)} raw lines", flush=True)
    mapped = {}
    # STAGE-2 DETERMINISTIC JOIN FIRST (the council's inversion, scoped to
    # where the replay ledger proved it surgical — the statement faces):
    # pure code joins face items to rows through hard gates (prior identity,
    # signed; parent-entity exclusion; block-scale ratification; label
    # kinship; agreement-or-nothing). 15/15 precision in offline validation.
    # Rows it serves never reach the mapper's label-matching at all.
    from . import join as join_mod
    s2_log = []
    for k_s2, m_s2 in join_mod.stage2_join(all_rows, raw_map, spec,
                                           target_year, s2_log).items():
        mapped[k_s2] = m_s2
    for ln_s2 in s2_log:
        print(f"[2j] {ln_s2}", flush=True)
    # FABLE-MODE FIRST READ: whole pages (images where layout matters), the
    # row block in model order with priors, one large call per region, and a
    # PER-ROW checksum — the returned comparative must tie the model's own
    # prior. Rows served here are done; the fragmented mapper only sees the
    # remainder. This is the 96%-run's working conditions, given to Luna.
    from . import fablemode
    fm_log = []
    fable_client = Client(temperature=0.0, max_output_tokens=14000)
    fable_served = set()  # checksum-verified reads — LOCKED against later
    # mechanical "improvement" (run 112: the closing loop swapped a correct,
    # self-verified EPS 1.15 for a misaligned note line's 3,831.3)
    fm_cov = {}
    for k_fm, m_fm in fablemode.region_read(fable_client, disclosures,
                                            all_rows, fm_log,
                                            coverage=fm_cov).items():
        mapped[k_fm] = m_fm
        if m_fm.get("conf") == 5:      # only checksummed reads earn the lock
            fable_served.add(k_fm)
    # STATEMENT-BLOCK LAW (run-115 reflection): on these rows the LLM reads,
    # machinery may not guess. Uncited/uncertain mapper answers are WITHHELD
    # there (flag-only); a hole beats a megawatt number in a P&L row.
    stmt_block_rows = fm_cov.get("stmt_rows", set())
    for ln_fm in fm_log:
        print(f"[2f] {ln_fm}", flush=True)
    for b in blocks:  # the old mapper reads only what fable-mode left
        b["rows"] = [r for r in b["rows"]
                     if (r["sheet"], r["row"]) not in mapped]
    blocks = [b for b in blocks if b["rows"]]
    map_prompt = _prompt("direct_map")
    deadline_map = t0 + cfg["budgets"]["max_run_minutes"] * 60 * 0.70
    for bi, b in enumerate(blocks):
        if time.time() > deadline_map:
            print(f"    [2] map deadline — {len(blocks)-bi} blocks left as carried",
                  flush=True)
            break
        try:
            mapped.update(mapper.map_block_voted(client, system, map_prompt, b, raw_map, cfg,
                                                 votes=(cfg.get('mapper') or {}).get('votes', 2)))
        except Exception as ex:
            print(f"    [2] block {b['sheet']} p{b['pages'][:3]} failed ({ex}) — "
                  "rows fall to carried", flush=True)
        if (bi + 1) % 8 == 0:
            print(f"    [2] mapped {bi+1}/{len(blocks)} blocks "
                  f"({len(mapped)} rows)", flush=True)
    # NOT_FOUND rescue: rows that failed re-map against the pages where their
    # SHEET-MATES succeeded — a sheet's rows live together in the document
    from collections import Counter as _Counter
    aff = {}
    for (s_a, _r_a), m_a in mapped.items():
        if m_a.get("status") == "OK" and m_a.get("page"):
            try:
                aff.setdefault(s_a, _Counter())[int(m_a["page"])] += 1
            except (TypeError, ValueError):
                pass
    for rescue_round in (1, 2):
        aff.clear()
        for (s_a, _r_a), m_a in mapped.items():
            if m_a.get("status") == "OK" and m_a.get("page"):
                try:
                    aff.setdefault(s_a, _Counter())[int(m_a["page"])] += 1
                except (TypeError, ValueError):
                    pass
        nf_rows = [r for r in all_rows
                   if (r["sheet"], r["row"]) not in mapped
                   or mapped[(r["sheet"], r["row"])].get("value") is None
                   or (mapped[(r["sheet"], r["row"])].get("conf", 5) == 0
                       and rescue_round == 1)]
        if not nf_rows or time.time() > deadline_map:
            break
        for r in nf_rows:
            top = [p for p, _n in (aff.get(r["sheet"]) or _Counter()).most_common(4)]
            m_nf = mapped.get((r["sheet"], r["row"])) or {}
            hinted = mapper.pages_for_hint(m_nf.get("hint"), raw_map) \
                if m_nf.get("status") == "NEED_PAGES" else []
            r["pages"] = (hinted + top + sorted(set(r["pages"])))[:mapper.MAX_BLOCK_PAGES]
            # code-found evidence comes TO the model: the exact lines where this
            # row's prior-year value is printed in the new documents
            pv_nf = r.get("prior_value")
            if isinstance(pv_nf, (int, float)) and abs(pv_nf) >= 10:
                cand_nf = [f"p{pn_c}: {ln_c.strip()[:110]}"
                           for pn_c, _s_c, ln_c in raw_map
                           if mapper.line_has_value(ln_c, pv_nf, page=pn_c)]
                r["candidate_lines"] = cand_nf[:4]
        rescue_blocks = mapper.cluster([r for r in nf_rows if r["pages"]])
        got = 0
        for b in rescue_blocks:
            if time.time() > deadline_map:
                break
            try:
                res_b = mapper.map_block_voted(client, system, map_prompt, b, raw_map,
                                               cfg, votes=(cfg.get('mapper') or {}).get('votes', 2))
                got += sum(1 for v in res_b.values() if v.get("value") is not None)
                for k_b, v_b in res_b.items():
                    if v_b.get("value") is not None or k_b not in mapped:
                        mapped[k_b] = v_b
            except Exception as ex:
                print(f"    [2r] rescue block failed ({ex})", flush=True)
        print(f"[2r] rescue round {rescue_round}: {got} of {len(nf_rows)} unresolved "
              "rows recovered", flush=True)
    # recipe pass (identity Ctrl+F, tie-broken) for anything still unresolved
    from . import derive
    from . import derive as derive_mod
    unres = [r for r in all_rows
             if (r["sheet"], r["row"]) not in mapped
             or mapped[(r["sheet"], r["row"])].get("value") is None]
    rp_log = []
    # SINGLE-YEAR TABLES first (deterministic): MD&A tables print current +
    # 同比% only — the implied prior (current / (1+pct)) matched against the
    # model's own prior identifies the row where Ctrl+F never can
    for k_ip, m_ip in derive_mod.implied_prior_read(unres, raw_all, rp_log).items():
        if k_ip not in mapped or mapped[k_ip].get("value") is None:
            mapped[k_ip] = m_ip
    unres = [r for r in unres
             if (r["sheet"], r["row"]) not in mapped
             or mapped[(r["sheet"], r["row"])].get("value") is None]
    # PROSE tie-out: "新生效订单1172.51亿元，同比增长15.93%" — the printed growth
    # reconciles the implied prior against the model's own (the orders block)
    for k_pg, m_pg in derive_mod.prose_growth_read(unres, raw_all, rp_log).items():
        if k_pg not in mapped or mapped[k_pg].get("value") is None:
            mapped[k_pg] = m_pg
    unres = [r for r in unres
             if (r["sheet"], r["row"]) not in mapped
             or mapped[(r["sheet"], r["row"])].get("value") is None]
    # STATEMENT ALIGNMENT (the clean-room tester's core move): the statements
    # mirror the source sheet in print order — prior-anchored, order-forced,
    # full line precision; measured 24/24 vs an independent answer key.
    # Anchors need the FULL census (run 108: fed only unresolved rows, found
    # <4 anchors, silently skipped); serves fill gaps AND correct mapped rows
    # that disagree with an anchored line (anchor-grade evidence outranks a
    # holistic read).
    n_sa_fill = n_sa_fix = 0
    for k_sa, m_sa in derive_mod.statement_align(all_rows, raw_map, rp_log).items():
        cur_sa = (mapped.get(k_sa) or {}).get("value")
        if cur_sa is None:
            mapped[k_sa] = m_sa
            n_sa_fill += 1
        elif abs(cur_sa - m_sa["value"]) > max(1.0, abs(m_sa["value"]) * 0.005):
            m_sa["note"] += f" [corrected mapped {cur_sa:,.1f}]"
            mapped[k_sa] = m_sa
            n_sa_fix += 1
        elif abs(cur_sa - m_sa["value"]) > 1e-9:
            mapped[k_sa]["value"] = m_sa["value"]  # snap to full line precision
    rp_log.append(f"statement-align applied: {n_sa_fill} filled, {n_sa_fix} corrected")
    unres = [r for r in unres
             if (r["sheet"], r["row"]) not in mapped
             or mapped[(r["sheet"], r["row"])].get("value") is None]
    for k_rp, m_rp in derive_mod.recipe_pass(unres, raw_all, rp_log).items():
        mapped[k_rp] = m_rp
    for ln_rp in rp_log:
        print(f"[2e] {ln_rp}", flush=True)
    # confidence-routed escalation: a stronger engine reads ONLY the rows the
    # weak one is unsure about (env ESCALATION_MODEL; ~cents per run)
    import os as _os
    esc_model = _os.environ.get("ESCALATION_MODEL")
    if esc_model and esc_model != client.model:
        esc_rows = [r for r in all_rows
                    if (mapped.get((r["sheet"], r["row"])) or {}).get("status")
                    in (None, "UNCERTAIN", "NEED_PAGES", "UNCITED")]
        if esc_rows and time.time() < deadline_map:
            esc_client = Client(model=esc_model,
                                temperature=cfg["updater"]["temperature"],
                                max_output_tokens=cfg["budgets"].get("mapping_output_tokens", 3000))
            got_e = 0
            for b_e in mapper.cluster([r for r in esc_rows if r["pages"]]):
                if time.time() > deadline_map:
                    break
                try:
                    res_e = mapper.map_block(esc_client, system, map_prompt, b_e,
                                             raw_map, cfg)
                except Exception as ex:
                    print(f"    [2f] escalation block failed ({ex})", flush=True)
                    continue
                for k_e, v_e in res_e.items():
                    if v_e.get("value") is not None:
                        v_e["note"] = f"escalated read ({esc_model.split('/')[-1]})"
                        v_e["status"] = "OK" if v_e.get("status") == "OK" else "UNCERTAIN"
                        mapped[k_e] = v_e
                        got_e += 1
            print(f"[2f] escalation: {got_e} rows resolved by {esc_model}", flush=True)
    # -- 6c. COVERAGE PASS: every still-carried row gets its Ctrl+F candidate
    # lines handed to the model (evidence-to-reader); answers are code-verified
    # against those lines before writing. Targets the completion rate directly.
    cov_rows = []
    for r_cv in all_rows:
        m_cv = mapped.get((r_cv["sheet"], r_cv["row"])) or {}
        if m_cv.get("value") is not None and m_cv.get("status") in ("OK", "DERIVED", "RECIPE", "RESCALED"):
            continue
        if not r_cv.get("candidate_lines"):
            pv_cv = r_cv.get("prior_value")
            if isinstance(pv_cv, (int, float)) and abs(pv_cv) >= 2:
                r_cv["candidate_lines"] = [f"p{pn_v}: {ln_v.strip()[:110]}"
                                           for pn_v, _s_v, ln_v in raw_map
                                           if mapper.line_has_value(ln_v, pv_cv, page=pn_v)][:4]
        if r_cv.get("candidate_lines"):
            cov_rows.append(r_cv)
    n_cov = 0
    if cov_rows and time.time() < deadline_map:
        for i_cv in range(0, len(cov_rows), 30):
            chunk_cv = cov_rows[i_cv:i_cv + 30]
            block_cv = {"sheet": chunk_cv[0]["sheet"], "pages": [], "rows": chunk_cv}
            try:
                res_cv = mapper.map_block(client, system, map_prompt, block_cv,
                                          raw_map, cfg)
            except Exception as ex_cv:
                print(f"    [6c] coverage block failed ({ex_cv})", flush=True)
                continue
            for (s_cv, r_cv2), v_cv in res_cv.items():
                val_cv = v_cv.get("value")
                if val_cv is None:
                    continue
                ctx_cv = next((x for x in chunk_cv
                               if x["sheet"] == s_cv and x["row"] == r_cv2), None)
                if ctx_cv is None:
                    continue
                # code check: the answered value must appear in the evidence lines
                cited_cv = any(mapper.line_has_value(cl, val_cv)
                               for cl in ctx_cv.get("candidate_lines") or [])
                tc_cv = spec["year_axis"].get(s_cv, {}).get("columns", {}).get(target_year)
                pc_cv = spec["year_axis"].get(s_cv, {}).get("columns", {}).get(last_actual)
                if not tc_cv:
                    continue
                fl_cv = "orange" if cited_cv else "red"
                mapped[(s_cv, r_cv2)] = {"value": val_cv,
                                         "status": "RECIPE" if cited_cv else "UNCERTAIN",
                                         "page": v_cv.get("page"),
                                         "line": v_cv.get("line", ""),
                                         "note": "coverage pass"}
                n_cov += 1
    print(f"[6c] coverage pass: {n_cov} carried rows decided "
          f"({len(cov_rows)} candidates)", flush=True)


    mapped = mapper.audit(mapped, all_rows, raw_map)
    st_c = _Counter(m["status"] for m in mapped.values())
    print(f"[2b] direct map: {dict(st_c)} of {len(all_rows)} rows", flush=True)

    # staging for the AUDIT layer — two independent sources so the auditors can
    # actually check the mapper: (a) the mapped rows themselves, (b) a code-only
    # pseudo-extraction of EVERY printed line (label + current + prior read
    # positionally) — thousands of items, no LLM, restores prove()/tie-web sight
    staging = {"items": [], "ties": [], "_direct": True}
    # page -> statement tag, from the pages' own captions. The direct-map
    # rewrite left every item stmt=None, which silently KILLED the agent
    # loop's statement_diff ("no staged items for stmt 'bs'" in every run) —
    # THE verification move returned nothing for the entire branch.
    page_stmt = {}
    for pn_t, _sec_t, ln_t in raw_all:
        if pn_t in page_stmt:
            continue
        if "资产负债表" in ln_t or "balance sheet" in ln_t.lower():
            page_stmt[pn_t] = "bs"
        elif "现金流量表" in ln_t or "cash flow" in ln_t.lower():
            page_stmt[pn_t] = "cf"
        elif "利润表" in ln_t or "income statement" in ln_t.lower():
            page_stmt[pn_t] = "pl"
        elif "分部" in ln_t or "分产品" in ln_t or "segment" in ln_t.lower():
            page_stmt[pn_t] = "segment"
    for (s_m, r_m), m in mapped.items():
        if m.get("value") is None:
            continue
        ctx_m = next((r for r in all_rows if r["sheet"] == s_m and r["row"] == r_m), {})
        pg_n = m.get("page")
        try:
            pg_n = int(pg_n) % 1000
        except (TypeError, ValueError):
            pass
        staging["items"].append({"label": m.get("line") or str(ctx_m.get("label")),
                                 "value": m["value"],
                                 "prior": ctx_m.get("prior_value"),
                                 "page": pg_n, "stmt": page_stmt.get(pg_n)})
    n_raw_items = 0
    for pn_r, _sec_r, ln_r in raw_all:
        ns_r = lookup_mod.line_nums(ln_r)
        if len(ns_r) < 2:
            continue
        lab_r = lookup_mod.label_of(ln_r)
        if not lab_r or len(lab_r) < 4:
            continue
        # MODEL UNITS at the boundary: staged items are the audit web's
        # currency (prove, sibling correction, tie-web, allocation) — on a
        # yuan-printed filing every triangulation silently failed (run 98:
        # vision delivered the evidence, the audit layer could not see it)
        staging["items"].append({"label": lab_r,
                                 "value": mapper.to_model_units(ns_r[0], page=pn_r),
                                 "prior": mapper.to_model_units(ns_r[1], page=pn_r),
                                 "page": pn_r, "stmt": page_stmt.get(pn_r % 1000 if isinstance(pn_r, int) else pn_r),
                                 "_src": "rawline"})
        n_raw_items += 1
    print(f"[2c] audit staging: {len(staging['items'])} items "
          f"({n_raw_items} code-parsed raw lines)", flush=True)
    workbook.dump_json(staging, company_dir / "updates" / f"{period}_staging.json")
    conf_map = {f"{s_m}!{r_m}": {"conf": m.get("conf", 0), "status": m.get("status"),
                                 "value": m.get("value")}
                for (s_m, r_m), m in mapped.items()}
    workbook.dump_json(conf_map, company_dir / "updates" / f"{period}_confidence.json")
    n_solid = sum(1 for v in conf_map.values() if v["conf"] >= 4)
    print(f"[2d] confidence: {n_solid} rows solid (conf>=4, skippable in later runs); "
          f"{sum(1 for v in conf_map.values() if v['conf'] <= 1)} need attention", flush=True)

    # -- 3. rollover + write the mapped column --------------------------------
    wb = workbook.load(model_path)
    writer = workbook.Writer(wb, cfg)

    def _prior_of(sheet_pl, coord_pl):
        """Prior-actual value for a target-column coord — feeds the Writer's
        world-band guard on writes that carry no prior_coord."""
        ax_pl = spec["year_axis"].get(sheet_pl) or {}
        tc_pl = (ax_pl.get("columns") or {}).get(str(target_year))
        pc_pl = (ax_pl.get("columns") or {}).get(str(last_actual))
        if not (tc_pl and pc_pl):
            return None
        m_pl = re.match(rf"^{tc_pl}(\d+)$", coord_pl)
        if not m_pl or sheet_pl not in pre_values.sheetnames:
            return None
        v_pl = pre_values[sheet_pl][f"{pc_pl}{m_pl.group(1)}"].value
        return v_pl if isinstance(v_pl, (int, float)) else None

    writer.prior_lookup = _prior_of
    restatements = []
    rollover_hardcodes = {}
    for sheet_rv, ax_rv in spec["year_axis"].items():
        pc_rv = ax_rv["columns"].get(last_actual)
        tc_rv = ax_rv["columns"].get(target_year)
        if not pc_rv or not tc_rv or sheet_rv not in wb.sheetnames:
            continue
        hr_rv = ax_rv.get("header_row", 1)
        rows_hc = workbook.rollover_column(wb, sheet_rv, pc_rv, tc_rv,
                                           header_rows={hr_rv})
        rollover_hardcodes[sheet_rv] = set(rows_hc)
    print(f"[3] whole-column rollover across {len(rollover_hardcodes)} sheets", flush=True)

    maplog, backouts, flags = [], [], []
    pending_consts = {}
    n_ok = n_der = n_unc = 0
    for r_ctx in all_rows:
        s_w, r_w = r_ctx["sheet"], r_ctx["row"]
        ax_w = spec["year_axis"][s_w]
        tcol_w = ax_w["columns"].get(target_year)
        pcol_w = ax_w["columns"].get(last_actual)
        if not tcol_w:
            continue
        coord_w = f"{tcol_w}{r_w}"
        m = mapped.get((s_w, r_w))
        if m is None or m.get("value") is None or m["status"] in ("NOT_FOUND",):
            continue  # rollover carry stands; [4d] flags it
        tr_w = (s_w, r_w) in fable_served  # checksum-tied: magnitude proven
        if m["status"] in ("OK", "RESCALED"):
            fl_w = None if m["status"] == "OK" else "red"
            writer.write(s_w, coord_w, m["value"], prior_coord=f"{pcol_w}{r_w}",
                         note=(f"direct-map [conf {m.get('conf', '?')}/5]: "
                               f"'{m.get('line','')}' p{m.get('page')}"
                               + (f"; {m.get('note')}" if m.get('note') else "")),
                         flag=fl_w, trusted=tr_w)
            if fl_w:
                flags.append((s_w, coord_w, m.get("note") or "rescaled"))
            n_ok += 1
        elif m["status"] in ("DERIVED", "RECIPE"):
            writer.write(s_w, coord_w, m["value"], prior_coord=f"{pcol_w}{r_w}",
                         note=f"direct-map DERIVED: {m.get('line','')} p{m.get('page')}",
                         flag="orange")
            backouts.append((s_w, coord_w, m.get("line", "")[:60]))
            n_der += 1
        elif (s_w, r_w) in stmt_block_rows and "fable-mode" not in str(m.get("note", "")):
            # STATEMENT-BLOCK LAW: an uncited/uncertain MACHINE answer on a
            # statement row is withheld — the hole is flagged for the analyst
            # instead (run 115: a megawatt figure from a production table was
            # "UNCERTAIN"-written into a P&L row and poisoned six cells).
            writer.write(s_w, coord_w, wb[s_w][coord_w].value,
                         prior_coord=f"{pcol_w}{r_w}",
                         note=f"STATEMENT ROW UNRESOLVED — machine answer "
                              f"withheld ({m['status']}: {m.get('line','')[:40]} "
                              f"p{m.get('page')}); verify from the statement",
                         flag="red")
            flags.append((s_w, coord_w, f"withheld {m['status']}: "
                                        f"{m.get('line','')[:40]}"))
            n_unc += 1
        else:  # UNCERTAIN / UNCITED — write but red-flag
            writer.write(s_w, coord_w, m["value"], prior_coord=f"{pcol_w}{r_w}",
                         note=f"direct-map {m['status']}: {m.get('line','')} "
                              f"p{m.get('page')} — verify",
                         flag="red")
            flags.append((s_w, coord_w, f"{m['status']}: {m.get('line','')[:50]}"))
            n_unc += 1
    print(f"[3b] wrote {n_ok} clean, {n_der} derived, {n_unc} uncertain", flush=True)

    # embedded constants: memory recipes serve deterministically; leftovers
    # rewritten from the mapped staging; unresolved -> red flag
    for sheet, iv in (spec.get("input_vs_formula") or {}).items():
        s_axis = spec["year_axis"].get(sheet, axis)
        s_prior = s_axis["columns"].get(last_actual, prior_col)
        s_target = s_axis["columns"].get(target_year, target_col)
        header_r = s_axis.get("header_row", 1)
        if sheet not in wb.sheetnames:
            continue
        ws_cur = wb[sheet]
        for r in range(1, min(ws_cur.max_row, 400) + 1):
            if r == header_r:
                continue
            cur = ws_cur[f"{s_target}{r}"].value
            if not (isinstance(cur, str) and cur.startswith("=")):
                continue
            if not re.search(r"(?<![A-Za-z0-9_.$])\d{2,}(?![A-Za-z0-9_.])", cur):
                continue
            # composites ARE input cells: register for eligibility (allocation,
            # plugs, trace all depend on this — lost in the direct-map rewiring)
            pending_consts[(sheet, r)] = {"coord": f"{s_target}{r}"}
            # roll-forward bases are NEVER auto-rewritten: their notes are
            # multi-column tables where neighbour reads corrupt (runs 51-52
            # forecast blowout); keep prior constants, red-flag for re-anchor
            base_cells = {(b.get("sheet"), b.get("cell"))
                          for b in spec.get("roll_forward_bases") or []}
            if (sheet, f"{s_target}{r}") in base_cells:
                rule_b = next((b.get("re_anchor_rule", "") for b in
                               spec.get("roll_forward_bases") or []
                               if (b.get("sheet"), b.get("cell")) == (sheet, f"{s_target}{r}")), "")
                writer.write(sheet, f"{s_target}{r}", cur, prior_coord=f"{s_prior}{r}",
                             note=f"ROLL-FORWARD BASE carried at prior structure — "
                                  f"re-anchor: {rule_b[:120]}", flag="red")
                flags.append((sheet, f"{s_target}{r}", "roll-forward base needs re-anchor"))
                continue
            new_f, ok_c, unresolved = mapping.rewrite_constants(cur, staging)
            # Ctrl+F fallback for every constant the rewriter left untouched:
            # the constant IS last year's number — find it in the new documents,
            # take the neighbour, magnitude-banded to kill junk. NO SILENT CARRY:
            # a composite that still holds a stale constant is always red-flagged.
            for tok_c in set(re.findall(r"(?<![A-Za-z0-9_.$])(\d{2,}(?:\.\d+)?)(?![A-Za-z0-9_.])", new_f)):
                tv = float(tok_c)
                if tv < 10:
                    continue
                cands_c = set()
                for _pn_c, _sec_c, ln_c in raw_all:
                    ns_c = [mapper.to_model_units(n_c, page=_pn_c)
                            for n_c in lookup_mod.line_nums(ln_c)]
                    for i_c in range(1, len(ns_c)):
                        if abs(abs(ns_c[i_c]) - tv) <= 0.6:
                            nb = abs(ns_c[i_c - 1])
                            if 0.2 <= nb / tv <= 5:
                                cands_c.add(round(nb, 1))
                if len(cands_c) == 1:
                    nv_c = cands_c.pop()
                    nv_s = str(int(nv_c)) if nv_c == int(nv_c) else str(nv_c)
                    new_f = re.sub(rf"(?<![A-Za-z0-9_.$]){re.escape(tok_c)}(?![A-Za-z0-9_.])",
                                   nv_s, new_f, count=1)
                elif tok_c not in (unresolved or []):
                    unresolved = list(unresolved or []) + [tok_c]
            if unresolved:
                lab_c = next((pre_values[sheet][f"{lc}{r}"].value for lc in "ABCDEF"
                              if isinstance(pre_values[sheet][f"{lc}{r}"].value, str)),
                             f"row {r}")
                writer.write(sheet, f"{s_target}{r}", new_f,
                             prior_coord=f"{s_prior}{r}",
                             note=f"CONSTANTS UNRESOLVED {unresolved} — verify",
                             flag="red")
                flags.append((sheet, f"{s_target}{r}",
                              f"embedded constants unresolved: {unresolved}"))
            elif new_f != cur:
                writer.write(sheet, f"{s_target}{r}", new_f,
                             prior_coord=f"{s_prior}{r}")
        writer.format_rollover(sheet, s_prior, s_target)

    # any rolled-over hardcode that mapping did not overwrite is, by definition,
    # a stale prior-year number: flag it red — complete coverage, no silent gaps
    written_set = set(writer.log["written"])
    carried_n = 0
    for sheet_hc, rowset in rollover_hardcodes.items():
        tc_hc = spec["year_axis"][sheet_hc]["columns"].get(target_year)
        for r in sorted(rowset):
            coord = f"{sheet_hc}!{tc_hc}{r}"
            if coord in written_set:
                continue
            cell_hc = wb[sheet_hc][f"{tc_hc}{r}"]
            writer.write(sheet_hc, f"{tc_hc}{r}", cell_hc.value,
                         note="CARRIED prior-year actual — not located in disclosure; verify",
                         flag="red")
            flags.append((sheet_hc, f"{tc_hc}{r}", "carried prior-year hardcode"))
            carried_n += 1
    if carried_n:
        print(f"[4d] {carried_n} rolled hardcodes not updated -> red-flagged as carried",
              flush=True)

    # circular-reference detection + repair (mark-to-actual law: a converted
    # column is actual-mode THROUGHOUT — no cell may be left in forecast-mode)
    leftover_cycles = workbook.repair_cycles(wb, spec, writer, flags,
                                             target_year, pre_wb)
    if leftover_cycles:
        print("STRUCTURAL FAILURE: unrepairable circular references:", leftover_cycles)
        sys.exit(2)

    # per-company confirmed corrections (machine-actionable MODEL_SPEC landmines)
    for fx in spec.get("analyst_fixes") or []:
        writer.restate(fx["sheet"], fx["cell"], fx["value"], fx["why"])
        restatements.append(f"{fx['sheet']}!{fx['cell']} -> {fx['value']} ({fx['why']})")
    print(f"[4] applied: {len(writer.log['written'])} cells "
          f"({len(flags)} red, {len(backouts)} orange). {len(maplog)} mapping notes.")

    # header: keep the prior header's TYPE (plain number stays plain number)
    hr = axis.get("header_row", 1)
    for sheet2, a2 in spec["year_axis"].items():
        tcol = a2["columns"].get(target_year)
        if tcol:
            hval = int(target_year) if a2.get("header_type") == "number" else str(target_year)
            writer.write(sheet2, f"{tcol}{a2.get('header_row', hr)}", hval)

    workbook.save(wb, model_path)

    # -- 6. verify (gate) ----------------------------------------------------
    wb = workbook.load(model_path)  # fresh load: verify what was SAVED
    # FABLE-LOCK, applied to the RELOADED wb (a lock set pre-save dies with
    # the old object): checksum-verified reads are DONE — no later mechanical
    # pass (bridges, breadth repairs, closing loop, plugs) may overwrite one.
    # Run 112: the closing loop swapped a correct, self-verified EPS 1.15
    # for a misaligned note line's 3,831.3.
    fable_lock_cells = set()
    for s_fl, r_fl in fable_served:
        tc_fl = (spec["year_axis"].get(s_fl, {}).get("columns") or {}).get(target_year)
        if tc_fl:
            fable_lock_cells.add(f"{s_fl}!{tc_fl}{r_fl}")
    wb._locked_cells = set(getattr(wb, "_locked_cells", set())) | fable_lock_cells
    print(f"[4L] {len(fable_lock_cells)} fable-served (checksum-verified) cells "
          "LOCKED against later mechanical writes", flush=True)
    allowed = {(s.split("!")[0], s.split("!")[1]) for s in
               [x.split(":")[0] for x in writer.log["restatements"]]}
    results, hard, soft = verify.run_checks(wb, spec, staging, cfg, pre_map, allowed)
    for nm, got, exp, st in results:
        print(f"  {st} {nm}: {got} vs {exp}")
    if hard:
        print("\nINTEGRITY GATE FAILED (structural) — model NOT delivered:")
        for f in hard:
            print("  -", f)
        sys.exit(2)
    filled = len(writer.log["written"])
    print(f"[5] integrity gate: {'all checks pass' if not soft else 'DELIVERED WITH EXCEPTIONS'}"
          f" — {filled} cells written, {len(flags)} red-flagged for analyst review")
    for f in soft:
        print("  EXCEPTION:", f)


    # -- 6. THE AGENT LOOP owns the rest of the run --------------------------
    # Bootstrap (code, free): objective state + deterministic converge, recorded
    # as the agent's own first moves. Then the orchestrator has FULL and FINAL
    # authority — blind review is a tool it calls; NOTHING writes after it.
    from . import objectives
    obj_notes = []
    spec["_target_year"] = target_year
    keymap = objectives.locate(spec, pre_wb, obj_notes)
    raw_all = (lookup_mod.raw_lines(disclosures)
               + vision.cached_lines(disclosures, ".cache/vision"))
    proven = objectives.prove(keymap, staging, raw_all, pre_wb, spec,
                              last_actual, cfg, obj_notes)
    eligible_inputs = set()
    for sh_o, rows_o in rollover_hardcodes.items():
        tc_o = spec["year_axis"][sh_o]["columns"].get(target_year)
        if tc_o:
            eligible_inputs |= {(sh_o, f"{tc_o}{r}") for r in rows_o}
    eligible_inputs |= {(cs_o, pc_o["coord"]) for (cs_o, _r), pc_o in pending_consts.items()}
    writer_obj = workbook.Writer(wb, cfg)
    writer_obj.prior_lookup = _prior_of
    writer_obj.log["written"] = list(writer.log["written"])
    obj_deadline = t0 + cfg["budgets"]["max_run_minutes"] * 60 * 0.92

    # ORDERING GUARANTEE: tie-web first (wide net over subtotals), key-number
    # converge LAST — the least-requirement keys get the final word, re-tying
    # anything a tie-web plug disturbed beneath them.
    tw_log = []
    tw_keymap, tw_proven = objectives.tie_web(
        wb, pre_wb, spec, staging, raw_all, cfg, last_actual, target_year, tw_log,
        exclude_rows={(v["sheet"], v["row"]) for v in keymap.values()})
    key_cells_prot = set()
    for v in keymap.values():
        tc_k = spec["year_axis"].get(v["sheet"], {}).get("columns", {}).get(target_year)
        if tc_k:
            key_cells_prot.add((v["sheet"], f"{tc_k}{v['row']}"))
    n_tw = 0
    if tw_keymap:
        _c, tw_clog, n_tw = objectives.converge(
            wb, spec, staging, cfg, writer_obj, pre_wb, pre_values, target_year,
            last_actual, tw_keymap, tw_proven, flags, backouts, t0,
            eligible_inputs, obj_deadline, protected_cells=key_cells_prot)
        tw_log += tw_clog
    for ln in tw_log:
        print("  [TIE]", ln, flush=True)
    print(f"[6t] tie-web: {n_tw} subtotal-anchored fixes", flush=True)

    # identity anchors: an unproven total whose COMPLEMENT line is printed
    # (net-format BS: "total assets less current liabilities") derives exactly —
    # complement found by prior-triangulation on the model's own arithmetic
    for kind_i, total_i in (("current_liabilities", "total_assets"),
                            ("current_assets", "total_assets")):
        loc_i = keymap.get(kind_i)
        p_i = proven.get(kind_i) or {}
        p_t = proven.get(total_i) or {}
        if not loc_i or p_i.get("status") == "proven" \
                or p_t.get("status") != "proven" \
                or not isinstance(p_t.get("value"), (int, float)):
            continue
        loc_t = keymap.get(total_i)
        ax_i = spec["year_axis"].get(loc_i["sheet"]) or {}
        pc_i = (ax_i.get("columns") or {}).get(last_actual)
        try:
            ev_i = Evaluator(pre_wb)
            part_prior = ev_i.cell(loc_i["sheet"], f"{pc_i}{loc_i['row']}")
            tot_prior = ev_i.cell(loc_t["sheet"], f"{pc_i}{loc_t['row']}")
        except Exception:
            continue
        if not (isinstance(part_prior, (int, float)) and isinstance(tot_prior, (int, float))):
            continue
        comp_v, _pg_i, _ln_i, uniq_i = derive.ctrlf_read(tot_prior - part_prior, raw_all)
        if uniq_i and isinstance(comp_v, (int, float)):
            derived_i = p_t["value"] - comp_v
            if 0.2 <= abs(derived_i) / max(abs(part_prior), 1e-9) <= 5:
                proven[kind_i] = {"status": "proven", "value": round(derived_i, 1),
                                  "sources": 3, "pages": ["identity-complement"]}
                obj_notes.append(f"identity anchor {kind_i}: {p_t['value']:,.1f} - "
                                 f"complement {comp_v:,.1f} = {derived_i:,.1f}")

    # BRIDGES from the learner's memory (FY24-calibrated, served cold):
    # replay each stored recipe on FY25 by verified line names — no FY24 docs
    # are read at update time (the cold-run contract)
    for (s_b, r_b), m_b in memory.items():
        if m_b.get("kind") == "quirk" and m_b.get("section"):
            obj_notes.append(f"KNOWN QUIRK {s_b}!{r_b}: {m_b['section']}")
            continue
        if m_b.get("kind") not in ("bridge", "bridge_row") or not m_b.get("components"):
            continue
        if m_b.get("kind") == "bridge_row":
            recipe_r = [(c_r["label"], c_r["sign"], c_r["v24"], None)
                        for c_r in m_b["components"]]
            v25_r, det_r = derive.replay_composition(recipe_r, raw_all)
            if v25_r is not None:
                ax_r = spec["year_axis"].get(s_b) or {}
                tc_r = (ax_r.get("columns") or {}).get(target_year)
                pc_r2 = (ax_r.get("columns") or {}).get(last_actual)
                if tc_r:
                    writer_obj.write(s_b, f"{tc_r}{r_b}", round(v25_r, 1),
                                     prior_coord=f"{pc_r2}{r_b}" if pc_r2 else None,
                                     note=f"learned construction: "
                                          + " ".join(det_r or [])[:120],
                                     flag="orange")
                    backouts.append((s_b, f"{tc_r}{r_b}", "learned construction"))
            continue
        kind_b = m_b.get("label")
        if kind_b not in keymap or (proven.get(kind_b) or {}).get("status") == "proven":
            continue
        recipe_b = [(c_b["label"], c_b["sign"], c_b["v24"], None)
                    for c_b in m_b["components"]]
        v25_b, det_b = derive.replay_composition(recipe_b, raw_all)
        if v25_b is None:
            obj_notes.append(f"bridge {kind_b}: not replayable — "
                             + "; ".join(det_b or [])[:100])
            continue
        # a bridge is ADDITIVE, never an override: replay can land on the
        # wrong line instance in a new document (run 102: CFI/CFF drifted
        # 1-8% off their statement values). If the statement offers ANY
        # candidate that disagrees, the statement wins and the bridge stands
        # down — bridges exist for rows the statements don't print.
        stmt_v = (proven.get(kind_b) or {}).get("value")
        if isinstance(stmt_v, (int, float)) and \
                abs(stmt_v - v25_b) > max(1.0, abs(v25_b) * 0.005):
            obj_notes.append(f"bridge {kind_b}: replay {v25_b:,.1f} conflicts "
                             f"with statement candidate {stmt_v:,.1f} — "
                             "statement wins, bridge skipped")
            continue
        if stmt_v is None and kind_b in ("cfo", "cfi", "cff"):
            # no statement candidate to arbitrate: the bridge value must
            # itself satisfy CFO+CFI+CFF+FX = ΔCash (run 108: an unarbitrated
            # CFF bridge served a wrong-instance 5,553)
            fx_b, end_b, beg_b = objectives.cf_pieces(staging)
            others = [(proven.get(x) or {}).get("value")
                      for x in ("cfo", "cfi", "cff") if x != kind_b]
            if end_b is not None and beg_b is not None \
                    and all(isinstance(o, (int, float)) for o in others):
                resid_b = sum(others) + v25_b + (fx_b or 0.0) - (end_b - beg_b)
                if abs(resid_b) > max(1.0, abs(end_b - beg_b) * 0.01):
                    obj_notes.append(f"bridge {kind_b}: replay {v25_b:,.1f} fails "
                                     f"the cash-tie identity by {resid_b:,.1f} — "
                                     "skipped, row stays flagged")
                    continue
        proven[kind_b] = {"status": "proven", "value": round(v25_b, 1),
                          "sources": 3, "pages": ["bridge-memory"]}
        obj_notes.append(f"bridge {kind_b}: memory recipe -> {v25_b:,.1f} = "
                         + " ".join(det_b)[:120])

    objectives.cash_tie_oracle(proven, staging, obj_notes)
    card, obj_log, n_fix = objectives.converge(
        wb, spec, staging, cfg, writer_obj, pre_wb, pre_values, target_year,
        last_actual, keymap, proven, flags, backouts, t0, eligible_inputs,
        obj_deadline)
    for ln in obj_notes + obj_log:
        print("  [OBJ]", ln, flush=True)
    print(f"[6] key-number converge (final word): {n_fix} fixes banked", flush=True)
    # HARD LOCKS: every cell the objective machinery wrote is now immutable to
    # later stages (the CFO/CFI drift class dies here)
    obj_cells_lock = set(writer_obj.log["written"]) - set(writer.log["written"])
    wb._locked_cells = set(getattr(wb, "_locked_cells", set())) | obj_cells_lock
    print(f"[6L] {len(obj_cells_lock)} objective-written cells LOCKED", flush=True)
    obj_log = tw_log + obj_log

    # blind review as a TOOL: the loop calls it when it wants a second pair of
    # eyes; findings return to the loop, which acts through its guarded writes
    findings_box = {}
    rc = None
    if cfg["reviewer"]["enabled"]:
        from . import reviewer as rev
        rc = Client.reviewer(cfg)
        conventions = (Path(company_dir) / "MODEL_SPEC.md").read_text() \
            if (Path(company_dir) / "MODEL_SPEC.md").exists() else ""

        def request_review():
            if "findings" not in findings_box:
                findings_box["findings"] = rev.review(
                    rc, _prompt("reviewer"), conventions, disclosures,
                    rev.column_dump(wb, spec), rev.column_dump(pre_wb, spec), cfg)
            return findings_box["findings"]
    else:
        request_review = None

    # -- 6p. BREADTH PASS (bootstrap, before the agent): the run-30 machinery
    # that repaired ~15 tail cells/run, reinstated UNDER the loop's authority —
    # it runs before the agent, never after, so it can never clobber the agent.
    obj_written = {c for c in writer_obj.log["written"]
                   if c not in set(writer.log["written"])}
    breadth_log = []
    _hw = cfg.get("heuristic_writers") or {}
    if cfg["reviewer"]["enabled"] and _hw.get("reviewer_auto_apply"):
        fnd = request_review()
        staged_vals_b = [it["value"] for it in staging["items"]
                        if isinstance(it.get("value"), (int, float))]
        applied_b = 0
        for f in fnd["findings"]:
            if applied_b >= 10 or f.get("severity") != "genuine_error":
                continue
            m = re.match(r"^\s*'?([A-Za-z0-9 _\-]+)'?!([A-Z]{1,3})(\d+)\s*$",
                         str(f.get("cell", "")))
            nums = re.findall(r"-?[\d,]+(?:\.\d+)?", str(f.get("disclosure_says", "")))
            if not m or not nums:
                continue
            sheet_f, col_f, row_f = m.group(1), m.group(2), int(m.group(3))
            coord_f = f"{col_f}{row_f}"
            if sheet_f not in wb.sheetnames or col_f not in spec.get("_target_cols", []) \
                    or f"{sheet_f}!{coord_f}" in obj_written \
                    or (sheet_f, coord_f) in key_cells_prot:
                continue
            try:
                val = float(nums[0].replace(",", ""))
            except ValueError:
                continue
            if not any(abs(val - sv) <= workbook.row_tol(sv, base=1.0)
                       or abs(-val - sv) <= workbook.row_tol(sv, base=1.0)
                       for sv in staged_vals_b):
                continue
            pv_chk = pre_values[sheet_f][f"{prior_col}{row_f}"].value \
                if sheet_f in pre_values.sheetnames else None
            if isinstance(pv_chk, (int, float)) and pv_chk != 0 and val != 0:
                ratio = abs(val) / abs(pv_chk)
                if ratio < 0.05 or ratio > 20:
                    continue
            elif abs(val) > 1000:
                continue
            writer_obj.write(sheet_f, coord_f, val,
                             note=f"REVIEWER-APPLIED (bootstrap): "
                                  f"{str(f.get('evidence', ''))[:140]}")
            f["outcome"] = "auto-applied"
            breadth_log.append(f"reviewer-applied {sheet_f}!{coord_f} = {val}")
            applied_b += 1
    from . import closing
    fable_locked = set()
    for s_fs, r_fs in fable_served:
        ax_fs = spec["year_axis"].get(s_fs) or {}
        tc_fs = (ax_fs.get("columns") or {}).get(str(target_year))
        if tc_fs:
            fable_locked.add(f"{s_fs}!{tc_fs}{r_fs}")
    eligible_cl = {f"{s_}!{c_}" for s_, c_, _n in flags} - obj_written \
        - {f"{s_}!{c_}" for s_, c_ in key_cells_prot} - fable_locked
    if _hw.get("closing_loop"):
        writer_cl = workbook.Writer(wb, cfg)
        writer_cl.prior_lookup = _prior_of
        writer_cl.log["written"] = list(writer_obj.log["written"])
        cl_log = closing.close_residuals(wb, spec, staging, cfg, writer_cl, flags,
                                         target_year, pre_values=pre_values,
                                         eligible=eligible_cl)
        writer_obj.log["written"] = list(writer_cl.log["written"])
        breadth_log += cl_log or []
    else:
        print("[6p] closing loop OFF (write firewall — council Day-0 ruling)",
              flush=True)
    print(f"[6p] breadth pass: {len(breadth_log)} repairs "
          "(reviewer-corroborated + closing residuals; objective cells protected)",
          flush=True)

    # ALLOCATION (house rule mechanized): components of a PROVEN total that the
    # mapper could not confidently resolve are scaled to prior-year structure so
    # the total ties exactly — keys stop depending on the mapper's draw
    anchors_a = {}
    alloc_log = []
    for kind_a in ("current_assets", "current_liabilities", "total_assets",
                   "non_current_assets", "non_current_liabilities"):
        p_a = proven.get(kind_a) or {}
        loc_a = keymap.get(kind_a)
        ok_anchor = p_a.get("status") == "proven"
        if not ok_anchor and p_a.get("status") == "single-source" and loc_a \
                and isinstance(p_a.get("value"), (int, float)):
            # single-source totals qualify when the Ctrl+F read confirms them
            ax_v = spec["year_axis"].get(loc_a["sheet"]) or {}
            pc_v = (ax_v.get("columns") or {}).get(last_actual)
            try:
                pv_v = Evaluator(pre_wb).cell(loc_a["sheet"], f"{pc_v}{loc_a['row']}")
            except Exception:
                pv_v = None
            if isinstance(pv_v, (int, float)):
                v_v, _pg_v, _ln_v, uniq_v = derive.ctrlf_read(pv_v, raw_all)
                ok_anchor = bool(uniq_v) and isinstance(v_v, (int, float)) \
                    and abs(v_v - abs(p_a["value"])) <= max(1.0, v_v * 0.005)
        if loc_a and ok_anchor and isinstance(p_a.get("value"), (int, float)):
            anchors_a[(loc_a["sheet"], loc_a["row"])] = p_a["value"]
    # GENERIC evidenced-identity solve: the MODEL'S OWN check-row equation is
    # the company's balance identity as the analyst built it. When exactly ONE
    # balance-sheet key is unproven and every other is evidenced, solve the
    # model's own equation for the unknown (sensitivity = linear solve on
    # whatever structure this model uses — no assumed formula, any company).
    bs_kinds_i = ["total_assets", "current_assets", "current_liabilities",
                  "non_current_assets", "non_current_liabilities", "equity"]
    present_i = [k2 for k2 in bs_kinds_i if k2 in keymap]
    unproven_i = [k2 for k2 in present_i
                  if (proven.get(k2) or {}).get("status") != "proven"]
    chk_i = next((c2 for c2 in spec.get("check_rows", [])
                  if (spec["sheets"].get(c2["sheet"]) or {}).get("role") == "statements"),
                 None)
    members_strong = all((proven.get(k2) or {}).get("sources", 0) >= 3
                         for k2 in present_i if k2 not in unproven_i)
    if len(unproven_i) == 1 and chk_i and members_strong:
        kind_u = unproven_i[0]
        loc_u = keymap[kind_u]
        ax_u = spec["year_axis"].get(chk_i["sheet"]) or {}
        tc_u = (ax_u.get("columns") or {}).get(target_year)
        ax_k = spec["year_axis"].get(loc_u["sheet"]) or {}
        tc_k = (ax_k.get("columns") or {}).get(target_year)
        if tc_u and tc_k:
            coef_u, base_u = objectives._sensitivity(
                wb, chk_i["sheet"], f"{tc_u}{chk_i['row']}",
                loc_u["sheet"], f"{tc_k}{loc_u['row']}")
            try:
                gap_u = Evaluator(wb).cell(chk_i["sheet"], f"{tc_u}{chk_i['row']}")                     - chk_i.get("expect", 0)
            except Exception:
                gap_u = None
            if coef_u and abs(coef_u) >= 0.5 and isinstance(gap_u, (int, float))                     and isinstance(base_u, (int, float)):
                solved_u = base_u - gap_u / coef_u
                if 0.2 <= abs(solved_u) / max(abs(base_u), 1e-9) <= 5:
                    proven[kind_u] = {"status": "proven",
                                      "value": round(solved_u, 1), "sources": 3,
                                      "pages": ["model-identity-solve"]}
                    obj_notes.append(
                        f"{kind_u} solved from the MODEL'S OWN balance equation: "
                        f"{solved_u:,.1f} (all other members evidenced; "
                        f"coef {coef_u:+.2f})")
    confident_a = set()
    for (s_m2, r_m2), m_m2 in mapped.items():
        if m_m2.get("conf", 0) >= 4:
            tc_m2 = spec["year_axis"].get(s_m2, {}).get("columns", {}).get(target_year)
            if tc_m2:
                confident_a.add((s_m2, f"{tc_m2}{r_m2}"))
    if not _hw.get("allocation"):
        n_alloc = 0
        alloc_log.append("allocation OFF (write firewall — council Day-0 ruling; "
                         "unresolved components stay blank/flagged)")
    else:
        n_alloc = derive.allocation_pass(wb, pre_wb, spec, target_year, last_actual,
                                     anchors_a, confident_a, eligible_inputs,
                                     writer_obj, flags, backouts, alloc_log,
                                     raw_lines=raw_all,
                                     protected=key_cells_prot
                                     | set(getattr(wb, "_locked_cells", set())
                                           and {tuple(c.split("!")) for c in wb._locked_cells}))
    for ln_a in alloc_log:
        print("  [ALLOC]", ln_a, flush=True)
    wb._locked_cells = set(getattr(wb, "_locked_cells", set())) \
        | (set(writer_obj.log["written"]) - set(writer.log["written"]))
    print(f"[6a] allocation: {n_alloc} components structure-scaled to proven totals",
          flush=True)

    # POST-WRITE STATEMENT RECONCILIATION (the run finishes like the analyst):
    # deterministic triple-lock join — prior ties (row identity) + statement
    # face (authority) + label kinship (confirmation) — of the WRITTEN column
    # against the extraction's statement-face items. Offline replay on run
    # 114: found and fixed both allocation-inflated cells from the printed
    # face (2025 balance +2,239 -> +1), zero false repairs, idempotent.
    from . import posteval
    fr_log = []
    n_fr = posteval.face_reconcile(wb, pre_values, spec, staging,
                                   {d.name: i for i, d in enumerate(disclosures)},
                                   writer_obj, flags, target_year, last_actual,
                                   fr_log, rows=all_rows)
    for ln_f in fr_log:
        print("  [FACE]", ln_f, flush=True)
    print(f"[6f] face reconciliation: {n_fr} statement-cited repairs", flush=True)


    # forecast-propagation attribution: any year whose balance gap WIDENED
    # during the repair phase gets a ready-made task naming the repaired cells
    # that feed its check (pure arithmetic, generic)
    prop_tasks = []
    try:
        post_card = objectives.scorecard(wb, spec, keymap, proven, cfg, t0)
        pre_gaps = {y: g for _c, y, g in card["tier0"] if g is not None}
        new_writes = [w for w in writer_obj.log["written"]
                      if w not in set(writer.log["written"])][-40:]
        for c_ref, y_p, g_p in post_card["tier0"]:
            if y_p == target_year or g_p is None:
                continue
            g_pre = pre_gaps.get(y_p)
            if g_pre is None or abs(g_p) <= abs(g_pre) + 1.0:
                continue
            chk_s, chk_c = c_ref.split("!")
            feeders = []
            for w_ref in new_writes:
                ws_, wc_ = w_ref.split("!")
                coef_w, _b = objectives._sensitivity(wb, chk_s, chk_c, ws_, wc_)
                if coef_w and abs(coef_w) > 0.01:
                    feeders.append(w_ref)
            prop_tasks.append(f"TASK: {y_p} balance gap widened "
                              f"{g_pre:+,.1f} -> {g_p:+,.1f} during repairs; "
                              f"repaired cells feeding it: {feeders[:6]}")
            break  # first widened year is enough — the drift is one cause
    except Exception as ex_p:
        prop_tasks.append(f"(propagation attribution failed: {ex_p})")
    for tline in prop_tasks:
        print("  [PROP]", tline, flush=True)

    decisions = []
    if (cfg.get("orchestrator") or {}).get("enabled", True):
        from . import orchestrator
        card, decisions = orchestrator.run(
            map_client, system, _prompt("orchestrator"), wb, spec, staging, cfg,
            writer_obj, pre_wb, target_year, last_actual, keymap, proven, flags,
            backouts, eligible_inputs, disclosures, t0, obj_deadline,
            lambda s: print(s, flush=True),
            bootstrap_log=obj_notes + obj_log + breadth_log + prop_tasks,
            request_review=request_review)
    writer.log["written"] = list(writer_obj.log["written"])
    workbook.save(wb, model_path)
    wb = workbook.load(model_path)
    results, hard, soft = verify.run_checks(wb, spec, staging, cfg, pre_map, allowed)
    if hard:
        print("\nINTEGRITY GATE FAILED post-loop (structural) — model NOT delivered:")
        for f in hard:
            print("  -", f)
        sys.exit(2)
    card = objectives.scorecard(wb, spec, keymap, proven, cfg, t0)
    print(f"[6z] agent loop done ({len(decisions)} decisions): "
          f"tier0 balance {'PASS' if card['t0_pass'] else 'FAIL'}, "
          f"tier1 key numbers {'PASS' if card['t1_pass'] else 'FAIL'}; "
          f"{len(soft)} exceptions remain", flush=True)

    findings = findings_box.get("findings")
    if cfg["reviewer"]["enabled"] and findings is None:
        # the loop chose not to consult the reviewer — still run it advisory-only
        # for the report (house rule: every run ends with an independent look)
        findings = request_review()
        print(f"[6r] advisory blind review: {len(findings['findings'])} findings — "
              f"{findings['verdict'][:100]}", flush=True)

    # -- 8. report -----------------------------------------------------------
    ev = Evaluator(wb)
    moves = report.big_moves_scan(ev, wb, spec, cfg)
    core = []
    for key, loc in list((spec.get("statement_rows") or {}).items())[:8]:
        est = est_snapshot.get(loc["row"])
        try:
            act = ev.cell(loc["sheet"], f"{target_col}{loc['row']}")
        except Exception:
            act = None
        if isinstance(est, (int, float)) and isinstance(act, (int, float)) and est:
            core.append((loc["sheet"], f"{target_col}{loc['row']}",
                         f"{key}: actual {act:,.2f} vs prior est {est:,.2f} "
                         f"({(act-est)/abs(est)*100:+.1f}%)"))
    report.write_report_tab(wb, cfg, flags, backouts, moves, core, findings,
                            writer.log["restatements"],
                            f"{name} — {period} update report (agent-generated)",
                            exceptions=soft)
    workbook.save(wb, model_path)
    md = company_dir / "updates" / f"{period}_update_report.md"
    md.parent.mkdir(exist_ok=True)
    # final objectives scorecard on the delivered workbook
    card = objectives.scorecard(wb, spec, keymap, proven, cfg, t0)
    obj_lines = objectives.render(card, obj_log + [f"[orchestrator] {d}" for d in decisions])
    for ln in obj_lines[:8]:
        print(ln, flush=True)
    provenance = [f"- updater: {client.usage}"]
    if cfg["reviewer"]["enabled"]:
        provenance.append(f"- reviewer: {rc.usage}")
    md.write_text(("## ⚠ DELIVERED WITH EXCEPTIONS\n" + "\n".join(f"- {e}" for e in soft)
                   + "\n\n" if soft else "")
                  + "\n".join(obj_lines) + "\n\n"
                  + _markdown_report(name, period, results, restatements, flags, backouts,
                                     moves, core, findings, maplog)
                  + "\n## LLM provenance (server-reported model + token usage)\n"
                  + "\n".join(provenance) + "\n")
    print("LLM provenance:", "; ".join(provenance))
    print(f"[7] report: _REPORT tab + {md}")
    print(f"DONE in {(time.time()-t0)/60:.1f} min. Deliverable: {model_path}")


def _eval_const(f):
    """Evaluate a pure-constants formula string ('=3872+5943'); None otherwise."""
    import re as _re
    if isinstance(f, str) and _re.match(r"^=[\d+\-. ]+$", f):
        try:
            return eval(f[1:], {"__builtins__": {}}, {})
        except Exception:
            return None
    return None


def _markdown_report(name, period, results, restatements, flags, backouts, moves,
                     core, findings, maplog):
    L = [f"# {name} — {period} update report\n"]
    L.append("## Integrity checks\n")
    L += [f"- {st} {nm}: {got} (expect {exp})" for nm, got, exp, st in results]
    L.append("\n## Restatements\n")
    L += [f"- {r}" for r in restatements] or ["- none"]
    L.append("\n## Flags (red = review, orange = true-up pending)\n")
    L += [f"- RED {s}!{c}: {n}" for s, c, n in flags]
    L += [f"- ORANGE {s}!{c}: {n}" for s, c, n in backouts]
    L.append("\n## Big moves\n")
    L += [f"- {s}!{c}: {n}" for s, c, n in moves]
    L.append("\n## Core figures — actual vs prior estimate\n")
    L += [f"- {n}" for _, _, n in core]
    if findings:
        L.append("\n## Reviewer findings\n")
        L += [f"- [{f['severity']}] {f.get('cell')}: {f.get('evidence','')[:300]}"
              for f in findings["findings"]]
        L.append(f"\nVerdict: {findings.get('verdict')}")
    if maplog:
        L.append("\n## Mapping log\n")
        L += [f"- {m}" for m in maplog]
    return "\n".join(L) + "\n"


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: python run.py discover <company_dir> | update <company_dir> <period>")
    cmd = sys.argv[1]
    if cmd == "discover":
        cmd_discover(sys.argv[2])
    elif cmd == "digest":
        if len(sys.argv) < 4:
            sys.exit("usage: python run.py digest <company_dir> <period>")
        cmd_digest(sys.argv[2], sys.argv[3])
    elif cmd == "learn":
        if len(sys.argv) < 4:
            sys.exit("usage: python run.py learn <company_dir> <prior_period>")
        cmd_learn(sys.argv[2], sys.argv[3])
    elif cmd == "update":
        if len(sys.argv) < 4:
            sys.exit("usage: python run.py update <company_dir> <period>")
        cmd_update(sys.argv[2], sys.argv[3])
    else:
        sys.exit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
