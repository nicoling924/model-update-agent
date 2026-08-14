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
    print(f"[L1] extracting prior-year disclosures ({prior_period}) ...", flush=True)
    staging = extraction.extract(client, system, disclosures, _prompt("extraction"), cfg)
    print(f"[L1] extracted {len(staging['items'])} items, {len(staging['ties'])} ties", flush=True)
    # census of prior-column hardcodes
    census = {}
    for sheet_c, ax_c in spec["year_axis"].items():
        pc_c = ax_c["columns"].get(str(ax_c.get("last_actual")))
        hr_c = ax_c.get("header_row", 1)
        if not pc_c or sheet_c not in wb.sheetnames:
            continue
        wsf = wb[sheet_c]
        rows_c = [r for r in range(1, min(wsf.max_row, 400) + 1)
                  if isinstance(wsf[f"{pc_c}{r}"].value, (int, float)) and r != hr_c]
        census[sheet_c] = rows_c
    from . import pdfs as pdfs_mod
    page_sections = {}
    for d in disclosures:
        page_sections.update(pdfs_mod.sections(pdfs_mod.pages(d)))
    det = learn_mod.deterministic_identities(disclosures, wb, pre_values, spec)
    print(f"[L1b] deterministic identities (code-only, literal labels): {len(det)}", flush=True)
    entries = learn_mod.learn(wb, pre_values, spec, staging, census,
                              page_sections=page_sections)
    merged = {}
    for e in entries:
        if e.get("kind") == "input":
            merged[(e["sheet"], e["row"])] = e
    for k, e in det.items():
        merged[k] = {"sheet": k[0], "row": k[1], **{kk: vv for kk, vv in e.items() if kk != "method"}}
    recipes = learn_mod.component_recipes(disclosures, wb, pre_values, spec)
    print(f"[L1c] component recipes (raw-text find-and-search, strict): {len(recipes)} composite rows", flush=True)
    entries = recipes + list(merged.values())
    # LLM MAP-AUDIT (one call): semantic sanity of the learned map — a row named
    # "Working capital" mapped to a "Dividends paid" line passes every numeric
    # lock yet is conceptually wrong; reasoning catches what arithmetic cannot
    audit_pairs = []
    for e in entries:
        if e.get("kind") != "input" or not e.get("label"):
            continue
        wsx = pre_values[e["sheet"]]
        rl = next((wsx[f"{lc}{e['row']}"].value for lc in "ABCDEF"
                   if isinstance(wsx[f"{lc}{e['row']}"].value, str)), "")
        audit_pairs.append({"id": f"{e['sheet']}!{e['row']}",
                            "model_row": str(rl)[:60], "mapped_to": str(e["label"])[:60]})
    if audit_pairs:
        import json as _j
        try:
            resp = client.json(
                "You audit financial line mappings.",
                "For each pair, judge whether the model row plausibly corresponds to "
                "the mapped disclosure line (synonyms are fine: sales=revenue). Return "
                '{"suspects": ["<id>", ...]} listing ONLY conceptually implausible pairs.\n'
                + _j.dumps(audit_pairs),
                lambda o: [] if isinstance(o.get("suspects"), list) else ["missing suspects"],
                repair_retries=1)
            suspects = set(resp.get("suspects") or [])
            for e in entries:
                if e.get("kind") == "input" and f"{e['sheet']}!{e['row']}" in suspects:
                    e["audit"] = "SUSPECT"
            print(f"[L1d] map-audit: {len(suspects)} suspect mappings flagged of "
                  f"{len(audit_pairs)}", flush=True)
        except Exception as ex:
            print(f"[L1d] map-audit skipped ({ex})", flush=True)
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
    all_rows = []
    for sheet_c, rows_c in census.items():
        ax_c = spec["year_axis"][sheet_c]
        pc_c = ax_c["columns"].get(last_actual)
        wsp = pre_values[sheet_c]
        for r in rows_c:
            lab = next((wsp[f"{lc}{r}"].value for lc in "ABCDEF"
                        if isinstance(wsp[f"{lc}{r}"].value, str)), f"row {r}")
            m_e = memory.get((sheet_c, r)) or {}
            all_rows.append({"sheet": sheet_c, "row": r, "label": lab,
                             "prior_value": pre_wb[sheet_c][f"{pc_c}{r}"].value,
                             "memory_hint": m_e.get("label"),
                             "memory_page": m_e.get("page")})
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
    blocks = mapper.cluster(all_rows)
    n_home = sum(1 for r in all_rows if r["pages"])
    print(f"[2] retrieval: {n_home}/{len(all_rows)} rows located "
          f"({len(blocks)} blocks) across {len(raw_all)} raw lines", flush=True)
    mapped = {}
    map_prompt = _prompt("direct_map")
    deadline_map = t0 + cfg["budgets"]["max_run_minutes"] * 60 * 0.55
    for bi, b in enumerate(blocks):
        if time.time() > deadline_map:
            print(f"    [2] map deadline — {len(blocks)-bi} blocks left as carried",
                  flush=True)
            break
        try:
            mapped.update(mapper.map_block(client, system, map_prompt, b, raw_map, cfg))
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
                   or mapped[(r["sheet"], r["row"])].get("value") is None]
        if not nf_rows or time.time() > deadline_map:
            break
        for r in nf_rows:
            top = [p for p, _n in (aff.get(r["sheet"]) or _Counter()).most_common(4)]
            m_nf = mapped.get((r["sheet"], r["row"])) or {}
            hinted = mapper.pages_for_hint(m_nf.get("hint"), raw_map) \
                if m_nf.get("status") == "NEED_PAGES" else []
            r["pages"] = (hinted + top + sorted(set(r["pages"])))[:mapper.MAX_BLOCK_PAGES]
        rescue_blocks = mapper.cluster([r for r in nf_rows if r["pages"]])
        got = 0
        for b in rescue_blocks:
            if time.time() > deadline_map:
                break
            try:
                res_b = mapper.map_block(client, system, map_prompt, b, raw_map, cfg)
                got += sum(1 for v in res_b.values() if v.get("value") is not None)
                for k_b, v_b in res_b.items():
                    if v_b.get("value") is not None or k_b not in mapped:
                        mapped[k_b] = v_b
            except Exception as ex:
                print(f"    [2r] rescue block failed ({ex})", flush=True)
        print(f"[2r] rescue round {rescue_round}: {got} of {len(nf_rows)} unresolved "
              "rows recovered", flush=True)
    mapped = mapper.audit(mapped, all_rows, raw_map)
    st_c = _Counter(m["status"] for m in mapped.values())
    print(f"[2b] direct map: {dict(st_c)} of {len(all_rows)} rows", flush=True)

    # staging for the AUDIT layer — two independent sources so the auditors can
    # actually check the mapper: (a) the mapped rows themselves, (b) a code-only
    # pseudo-extraction of EVERY printed line (label + current + prior read
    # positionally) — thousands of items, no LLM, restores prove()/tie-web sight
    staging = {"items": [], "ties": [], "_direct": True}
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
                                 "page": pg_n, "stmt": None})
    n_raw_items = 0
    for pn_r, _sec_r, ln_r in raw_all:
        ns_r = lookup_mod.line_nums(ln_r)
        if len(ns_r) < 2:
            continue
        lab_r = lookup_mod.label_of(ln_r)
        if not lab_r or len(lab_r) < 4:
            continue
        staging["items"].append({"label": lab_r, "value": ns_r[0], "prior": ns_r[1],
                                 "page": pn_r, "stmt": None, "_src": "rawline"})
        n_raw_items += 1
    print(f"[2c] audit staging: {len(staging['items'])} items "
          f"({n_raw_items} code-parsed raw lines)", flush=True)
    workbook.dump_json(staging, company_dir / "updates" / f"{period}_staging.json")

    # -- 3. rollover + write the mapped column --------------------------------
    wb = workbook.load(model_path)
    writer = workbook.Writer(wb, cfg)
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
        if m["status"] in ("OK", "RESCALED"):
            fl_w = None if m["status"] == "OK" else "red"
            writer.write(s_w, coord_w, m["value"], prior_coord=f"{pcol_w}{r_w}",
                         note=(f"direct-map: '{m.get('line','')}' p{m.get('page')}"
                               + (f"; {m.get('note')}" if m.get('note') else "")),
                         flag=fl_w)
            if fl_w:
                flags.append((s_w, coord_w, m.get("note") or "rescaled"))
            n_ok += 1
        elif m["status"] == "DERIVED":
            writer.write(s_w, coord_w, m["value"], prior_coord=f"{pcol_w}{r_w}",
                         note=f"direct-map DERIVED: {m.get('line','')} p{m.get('page')}",
                         flag="orange")
            backouts.append((s_w, coord_w, m.get("line", "")[:60]))
            n_der += 1
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
            new_f, ok_c, unresolved = mapping.rewrite_constants(cur, staging)
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
    raw_all = lookup_mod.raw_lines(disclosures)
    proven = objectives.prove(keymap, staging, raw_all, pre_wb, spec,
                              last_actual, cfg, obj_notes)
    eligible_inputs = set()
    for sh_o, rows_o in rollover_hardcodes.items():
        tc_o = spec["year_axis"][sh_o]["columns"].get(target_year)
        if tc_o:
            eligible_inputs |= {(sh_o, f"{tc_o}{r}") for r in rows_o}
    eligible_inputs |= {(cs_o, pc_o["coord"]) for (cs_o, _r), pc_o in pending_consts.items()}
    writer_obj = workbook.Writer(wb, cfg)
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

    card, obj_log, n_fix = objectives.converge(
        wb, spec, staging, cfg, writer_obj, pre_wb, pre_values, target_year,
        last_actual, keymap, proven, flags, backouts, t0, eligible_inputs,
        obj_deadline)
    for ln in obj_notes + obj_log:
        print("  [OBJ]", ln, flush=True)
    print(f"[6] key-number converge (final word): {n_fix} fixes banked", flush=True)
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
    if cfg["reviewer"]["enabled"]:
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
            if not any(abs(val - sv) <= 1.0 or abs(-val - sv) <= 1.0 for sv in staged_vals_b):
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
    eligible_cl = {f"{s_}!{c_}" for s_, c_, _n in flags} - obj_written \
        - {f"{s_}!{c_}" for s_, c_ in key_cells_prot}
    writer_cl = workbook.Writer(wb, cfg)
    writer_cl.log["written"] = list(writer_obj.log["written"])
    cl_log = closing.close_residuals(wb, spec, staging, cfg, writer_cl, flags,
                                     target_year, pre_values=pre_values,
                                     eligible=eligible_cl)
    writer_obj.log["written"] = list(writer_cl.log["written"])
    breadth_log += cl_log or []
    print(f"[6p] breadth pass: {len(breadth_log)} repairs "
          "(reviewer-corroborated + closing residuals; objective cells protected)",
          flush=True)

    decisions = []
    if (cfg.get("orchestrator") or {}).get("enabled", True):
        from . import orchestrator
        card, decisions = orchestrator.run(
            map_client, system, _prompt("orchestrator"), wb, spec, staging, cfg,
            writer_obj, pre_wb, target_year, last_actual, keymap, proven, flags,
            backouts, eligible_inputs, disclosures, t0, obj_deadline,
            lambda s: print(s, flush=True),
            bootstrap_log=obj_notes + obj_log + breadth_log,
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
