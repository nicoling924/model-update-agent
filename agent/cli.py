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

    # -- 2a. CHUNKED PAGE-READS FIRST — the primary path, never starved -------
    # Needs only page texts + the model's own prior values; runs before the big
    # extraction and is exempt from the LLM walk-away deadline by position.
    from . import targeted
    map_client = Client(temperature=cfg["updater"]["temperature"],
                        max_output_tokens=cfg["budgets"].get("mapping_output_tokens", 3000))
    # input census = spec-listed input rows UNION every hardcode the prior actual
    # column actually holds (runtime discovery — spec lists become a hint, not a cage)
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
            all_rows.append({"sheet": sheet_c, "row": r, "label": lab,
                             "prior_value": wsp[f"{pc_c}{r}"].value})
    chunked = targeted.rescue(map_client, system, disclosures, all_rows, cfg, [])
    print(f"[2a] chunked reads (primary) corroborated {len(chunked)}/{len(all_rows)} "
          "input rows", flush=True)

    # -- 2/3. ingest + extract (validated), cached by content signature ------
    import hashlib
    import json as _json
    sig_src = _prompt("extraction") + system + client.model + "".join(
        hashlib.sha256(p.read_bytes()).hexdigest() for p in disclosures)
    sig = hashlib.sha256(sig_src.encode()).hexdigest()[:16]
    # frozen digest first: the one careful reading beats any fresh single pass
    from . import digest as digest_mod
    dig_sig = digest_mod.signature(disclosures, _prompt("extraction"), system,
                                   client.model)
    frozen = digest_mod.load_if_valid(company_dir, period, dig_sig)
    if frozen is not None:
        print(f"[2] using FROZEN DIGEST ({len(frozen['items'])} items, "
              f"{frozen['_confidence']}) — variance-free", flush=True)
    staging_path = company_dir / "updates" / f"{period}_staging.json"
    staging = frozen
    if staging is None and staging_path.exists():
        cached = _json.loads(staging_path.read_text())
        if cached.get("_sig") == sig:
            staging = cached
            print(f"[2] reusing cached extraction ({len(staging['items'])} items) — "
                  "PDFs, prompts, and model unchanged")
    if staging is None:
        staging = extraction.extract(client, system, disclosures, _prompt("extraction"), cfg)
        staging["_sig"] = sig
        workbook.dump_json(staging, staging_path)
        print(f"[2] extracted {len(staging['items'])} items, {len(staging['ties'])} ties validated")

    # deterministic table lookup: memory identities served by CODE from the
    # rendered tables — numbers never pass through an LLM (clean status only;
    # sign-flips and restatements surface flagged)
    from . import lookup as lookup_mod
    det_results = {}
    # memory tab: identities learned by the learner agent (if present)
    from . import learn as learn_mod
    memory = learn_mod.read_memory_tab(pre_wb)
    if memory:
        print(f"[M] using {len(memory)} learned identities from {learn_mod.MEMORY_TAB} tab")
        idx_cur = lookup_mod.index_tables(disclosures)
        rows_ctx_lk = {}
        for (s_k, r_k), m_k in memory.items():
            if m_k.get("kind") != "input":
                continue
            ax_k = spec["year_axis"].get(s_k)
            if not ax_k:
                continue
            pc_k = ax_k["columns"].get(last_actual)
            pv_k = pre_values[s_k][f"{pc_k}{r_k}"].value if pc_k else None
            rows_ctx_lk[(s_k, r_k)] = {"label": None,
                                       "prior_value": pv_k if isinstance(pv_k, (int, float)) else None}
        det_results = lookup_mod.lookup_rows(idx_cur, memory, rows_ctx_lk,
                                             target_year, last_actual)
        raw_cur = lookup_mod.raw_lines(disclosures)
        raw_results = lookup_mod.raw_lookup_rows(raw_cur, memory, rows_ctx_lk)
        # unify: raw-text is primary; rendered tables confirm. Agreement -> clean;
        # disagreement -> flagged conflict; raw-only -> clean (the Ctrl+F standard)
        for k_, rr_ in raw_results.items():
            if rr_.get("status") != "clean":
                continue
            dr_ = det_results.get(k_)
            if dr_ and dr_.get("status") == "clean" and isinstance(dr_.get("value"), (int, float)) \
                    and abs(dr_["value"] - rr_["value"]) > 1.0:
                det_results[k_] = {"status": "restated", "value": rr_["value"],
                                   "prior_found": dr_.get("value"),
                                   "page": rr_.get("page"),
                                   "line_label": rr_.get("line_label")}
            else:
                det_results[k_] = rr_
        n_clean = sum(1 for v in det_results.values() if v.get("status") == "clean")
        print(f"[M2] deterministic table lookup: {n_clean} clean, "
              f"{sum(1 for v in det_results.values() if v.get('status')=='restated')} restated, "
              f"{sum(1 for v in det_results.values() if v.get('status')=='sign_flip')} sign-flips "
              f"of {len(det_results)} attempted", flush=True)

    # -- 4. restatement scan ------------------------------------------------
    wb = workbook.load(model_path)
    writer = workbook.Writer(wb, cfg)
    restatements = []
    for key, loc in (spec.get("statement_rows") or {}).items():
        prior_model = pre_values[loc["sheet"]][f"{prior_col}{loc['row']}"].value
        hits = extraction.find_by_prior(staging, prior_model,
                                        cfg["conventions"]["rounding_tolerance"])
        if prior_model is not None and not hits:
            cands = [it for it in staging["items"]
                     if mapping.norm(it["label"]) == mapping.norm(loc.get("label_seen", key))
                     and isinstance(it.get("prior"), (int, float))]
            if len(cands) == 1 and abs(cands[0]["prior"] - (prior_model or 0)) > cfg["conventions"]["rounding_tolerance"]:
                writer.restate(loc["sheet"], f"{prior_col}{loc['row']}", cands[0]["prior"],
                               f"comparative restated in {period} disclosure "
                               f"(p{cands[0]['page']}): {prior_model} -> {cands[0]['prior']}")
                restatements.append(f"{loc['sheet']}!{prior_col}{loc['row']}: "
                                    f"{prior_model} -> {cands[0]['prior']} (p{cands[0]['page']})")
    print(f"[3] restatement scan: {len(restatements)} restated")

    # -- 3b. WHOLE-COLUMN ROLLOVER (the analyst's own move; pure code, no LLM):
    # copy the entire prior actual column — values, Excel-shifted formulas,
    # types, formats — so the converted column is actual-mode with no cell
    # left behind. Disclosed inputs overwrite it next.
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
    print(f"[3b] whole-column rollover: prior actual column copied across "
          f"{len(rollover_hardcodes)} sheets (Excel-shifted formulas)", flush=True)

    # -- 5. map + apply ------------------------------------------------------
    glossary = mapping.build_glossary(cfg, spec)
    maplog, backouts, flags = [], [], []
    backout_rules = {str(b.get("row_ref")): b for b in spec.get("backout_rules") or []}
    deadline = t0 + cfg["budgets"]["max_run_minutes"] * 60 * 0.75
    rows_done = 0
    rescue_candidates = []
    pending = {}  # (sheet, row) -> cascade entry + coords, written after merge
    pending_consts = {}  # (sheet, row) -> formula with unresolved embedded constants
    for sheet, iv in (spec.get("input_vs_formula") or {}).items():
        s_axis = spec["year_axis"].get(sheet, axis)
        s_prior = s_axis["columns"].get(last_actual, prior_col)
        s_target = s_axis["columns"].get(target_year, target_col)
        ws_prior = pre_values[sheet]
        header_r = s_axis.get("header_row", 1)
        for r in census.get(sheet, []):
            if r == header_r:
                continue  # year headers are written separately, never mapped
            label = next((ws_prior[f"{lc}{r}"].value for lc in "ABCDEF"
                          if isinstance(ws_prior[f"{lc}{r}"].value, str)), f"row {r}")
            prior_cell = pre_wb[sheet][f"{s_prior}{r}"]
            row_ctx = {"sheet": sheet, "row": r, "label": label,
                       "prior_value": ws_prior[f"{s_prior}{r}"].value,
                       "prior_formula": prior_cell.value if isinstance(prior_cell.value, str) else None,
                       "backout_rule": backout_rules.get(f"{sheet}!{r}"),
                       "memory": memory.get((sheet, r))}
            # pass 1 is deterministic-only; values are NOT written yet — the
            # chunked page-read (primary path) runs next and the two results
            # are merged with cross-checking before any write
            dr = det_results.get((sheet, r))
            if dr and memory.get((sheet, r), {}).get("audit") == "SUSPECT" \
                    and isinstance(dr.get("value"), (int, float)):
                entry = {"value": dr["value"], "source": "table-lookup-suspect",
                         "flag": "red",
                         "note": "AUDIT-SUSPECT mapping — LLM doubts this row/line pairing; verify",
                         "page": dr.get("page")}
            elif dr and dr.get("status") == "clean" and isinstance(dr.get("value"), (int, float)):
                entry = {"value": dr["value"], "source": "table-lookup", "flag": None,
                         "note": f"code table-lookup: '{dr.get('line_label')}' p{dr.get('page')}"
                                 " (prior verified, no LLM)", "page": dr.get("page")}
            elif dr and dr.get("status") in ("restated", "sign_flip") and isinstance(dr.get("value"), (int, float)):
                entry = {"value": dr["value"], "source": f"table-lookup-{dr['status']}",
                         "flag": "red",
                         "note": f"code table-lookup ({dr['status']}): '{dr.get('line_label')}' "
                                 f"p{dr.get('page')}, prior in report {dr.get('prior_found')} — verify",
                         "page": dr.get("page")}
            else:
                entry = mapping.resolve_row(row_ctx, staging, glossary, None, system,
                                            _prompt("mapping"), cfg, maplog)
            rows_done += 1
            if rows_done % 50 == 0:
                print(f"    [4] {rows_done} rows pre-mapped ({sheet})", flush=True)
            pending[(sheet, r)] = {"entry": entry, "label": label,
                                   "prior_value": row_ctx["prior_value"],
                                   "coord": f"{s_target}{r}",
                                   "prior_coord": f"{s_prior}{r}"}
        # formula rows: re-copy prior pattern shifted one column (mark-to-actual
        # recipe) — but REWRITE any embedded prior-year constants (MODEL_SPEC rule);
        # a copied constant is a stale 2024 number wearing a 2025 costume
        # constants sweep over ALL rolled formula cells in this sheet's column:
        # rewrite embedded prior-year constants; queue unresolved for landmark reads
        ws_cur = wb[sheet]
        for r in range(1, min(ws_cur.max_row, 400) + 1):
            if r == header_r:
                continue
            cur = ws_cur[f"{s_target}{r}"].value
            if not (isinstance(cur, str) and cur.startswith("=")):
                continue
            if not re.search(r"(?<![A-Za-z0-9_.$])\d{2,}(?![A-Za-z0-9_.])", cur):
                continue
            new_f, ok, unresolved = mapping.rewrite_constants(cur, staging)
            if unresolved:
                lab = next((pre_values[sheet][f"{lc}{r}"].value for lc in "ABCDEF"
                            if isinstance(pre_values[sheet][f"{lc}{r}"].value, str)),
                           f"row {r}")
                pending_consts[(sheet, r)] = {
                    "formula": new_f, "unresolved": list(unresolved),
                    "coord": f"{s_target}{r}", "prior_coord": f"{s_prior}{r}",
                    "label": lab, "prior_formula": cur}
            elif new_f != cur:
                writer.write(sheet, f"{s_target}{r}", new_f,
                             prior_coord=f"{s_prior}{r}")
        writer.format_rollover(sheet, s_prior, s_target)
    # [4b] merge the (already-computed) chunked reads with the cascade, then write.
    # Agreement of the two independent paths -> unflagged; disagreement -> the
    # page-quoted chunk wins but is red-flagged with both values in the note.
    def _mag_flag(v_, pv_):
        if isinstance(v_, (int, float)) and isinstance(pv_, (int, float)) \
                and abs(pv_) >= 100 and v_ != 0:
            rr = abs(v_) / abs(pv_)
            return rr > 20 or rr < 0.05
        return False

    agree = conflict = chunk_only = cascade_only = 0
    for (s, r), p in sorted(pending.items()):
        e, c = p["entry"], chunked.get((s, r))
        # universal magnitude sanity: a 20x jump vs prior is never written silently
        for cand_e in (e,):
            v_chk = cand_e.get("value")
            if cand_e.get("flag") is None and _mag_flag(v_chk, p["prior_value"]):
                cand_e["flag"] = "red"
                cand_e["note"] = ("MAGNITUDE ALERT: >20x change vs prior year — verify. "
                                  + (cand_e.get("note") or ""))
        ev = e.get("value") if not e.get("formula") else _eval_const(e.get("formula"))
        if c is not None:
            cv = c["value"]
            if isinstance(ev, (int, float)) and abs(ev - cv) <= 1.0:
                keep = e.get("formula") or cv  # keep traceable formula when it agrees
                fl = c.get("flag")  # sign-harmonized chunks stay flagged
                writer.write(s, p["coord"], keep, prior_coord=p["prior_coord"],
                             note=e.get("note") or c["note"], flag=fl)
                if fl:
                    flags.append((s, p["coord"], c["note"]))
                agree += 1
            elif isinstance(ev, (int, float)) and e.get("flag") is None:
                note = (f"CONFLICT: chunked page-read {cv} vs cascade {round(ev,1)} "
                        f"({e.get('source')}) — page-quoted value written, verify. "
                        + (c.get("note") or ""))
                writer.write(s, p["coord"], cv, prior_coord=p["prior_coord"],
                             note=note, flag="red")
                flags.append((s, p["coord"], note))
                conflict += 1
            else:  # cascade had nothing solid — chunk stands on its corroboration
                writer.write(s, p["coord"], cv, prior_coord=p["prior_coord"],
                             note=c["note"], flag=c.get("flag"))
                if c.get("flag"):
                    flags.append((s, p["coord"], c["note"]))
                chunk_only += 1
        else:
            v = e.get("formula", e.get("value"))
            if v is None:
                continue
            writer.write(s, p["coord"], v, prior_coord=p["prior_coord"],
                         note=e.get("note"), flag=e.get("flag"))
            if e.get("flag") == "red":
                flags.append((s, p["coord"], e.get("note", "")))
                if e.get("source") in ("estimate", "label-only (uncorroborated)"):
                    rescue_candidates.append({"sheet": s, "row": r, "label": p["label"],
                                              "prior_value": p["prior_value"],
                                              "coord": p["coord"],
                                              "prior_coord": p["prior_coord"]})
            elif e.get("flag") == "orange":
                backouts.append((s, p["coord"], e.get("note", "")))
            cascade_only += 1
    print(f"[4b] merge: {agree} agreed, {conflict} conflicts (flagged), "
          f"{chunk_only} chunk-only, {cascade_only} cascade-only", flush=True)

    # [4b2] component-level landmark reads: each unresolved embedded constant is
    # its own tiny task — "find the line whose prior-year column shows <c>" —
    # generic across model styles because it needs only the constant itself
    if pending_consts and time.time() < deadline:
        comp_rows = []
        for (cs, cr), pc in pending_consts.items():
            for j, tok in enumerate(pc["unresolved"]):
                comp_rows.append({"sheet": cs, "row": f"{cr}#c{j}",
                                  "label": pc["label"],
                                  "prior_value": float(tok)})
        # memory component RECIPES: find by name, read by position, verify by prior
        raw25 = lookup_mod.raw_lines(disclosures)
        by_lab25 = {}
        for pn_, sec_, ln_ in raw25:
            by_lab25.setdefault(lookup_mod.norm(lookup_mod.label_of(ln_)), []).append((pn_, sec_, ln_))
        # memory-known components resolve without any LLM call
        mem_resolved = {}
        for (cs, cr), pc in pending_consts.items():
            m = memory.get((cs, cr))
            comps = (m or {}).get("components") or []
            for j, tok in enumerate(pc["unresolved"]):
                ident = next((c for c in comps if c and c.get("token") == tok), None)
                if not ident:
                    continue
                # STRICT raw-text read: same label, prior at learned pos+1, value at pos
                pos = ident.get("pos")
                cval = float(tok)
                founds = []
                for pn_, sec_, ln_ in by_lab25.get(lookup_mod.norm(ident["label"]), []):
                    ns = lookup_mod.line_nums(ln_)
                    if pos is not None and len(ns) > pos + 1 \
                            and abs(abs(ns[pos + 1]) - cval) <= 1.0:
                        founds.append((abs(ns[pos]), pn_))
                # layout-independent fallback: find the old number anywhere on the
                # line and take its LEFT NEIGHBOUR (statements print current | prior)
                for pn_, sec_, ln_ in by_lab25.get(lookup_mod.norm(ident["label"]), []):
                    ns = lookup_mod.line_nums(ln_)
                    for i_ in range(1, len(ns)):
                        if abs(abs(ns[i_]) - cval) <= 1.0:
                            founds.append((abs(ns[i_ - 1]), pn_))
                # a line where the "new" number equals the old constant is usually a
                # stale-ordered duplicate (summary tables) — prefer changed values
                changed = [f_ for f_ in founds if abs(f_[0] - cval) > 1.0]
                found = (changed or founds or [None])[0]
                if found:
                    mem_resolved[(cs, f"{cr}#c{j}")] = {"value": found[0],
                        "page": found[1],
                        "note": f"recipe read: '{ident['label'][:40]}' (prior verified, no LLM)"}
        comp_rows = [cr_ for cr_ in comp_rows
                     if (cr_["sheet"], cr_["row"]) not in mem_resolved]
        comp_res = targeted.rescue(map_client, system, disclosures, comp_rows, cfg, maplog)
        comp_res.update(mem_resolved)
        resolved_n = 0
        for (cs, cr), pc in sorted(pending_consts.items()):
            f_txt, left = pc["formula"], []
            for j, tok in enumerate(pc["unresolved"]):
                res = comp_res.get((cs, f"{cr}#c{j}"))
                if res and isinstance(res.get("value"), (int, float)):
                    nv = abs(res["value"])  # formula text carries its own sign operator
                    nv_s = str(int(nv)) if nv == int(nv) else str(nv)
                    f_txt = re.sub(rf"(?<![A-Za-z0-9_.$]){re.escape(tok)}(?![A-Za-z0-9_.])",
                                   nv_s, f_txt, count=1)
                    resolved_n += 1
                else:
                    left.append(tok)
            flag_row = "red" if left else None
            writer.write(cs, pc["coord"], f_txt, prior_coord=pc["prior_coord"],
                         note=(f"CONSTANTS UNRESOLVED {left} from prior formula "
                               f"{pc['prior_formula']} — verify" if left else
                               f"embedded constants rewritten (staging + landmark reads) "
                               f"from {pc['prior_formula']}"),
                         flag=flag_row)
            if flag_row:
                flags.append((cs, pc["coord"],
                              f"embedded constants unresolved: {left}"))
        print(f"[4b2] component landmark reads resolved {resolved_n} embedded "
              f"constants across {len(pending_consts)} composite formulas", flush=True)
    elif pending_consts:
        for (cs, cr), pc in sorted(pending_consts.items()):
            writer.write(cs, pc["coord"], pc["formula"], prior_coord=pc["prior_coord"],
                         note=f"CONSTANTS UNRESOLVED {pc['unresolved']} — verify",
                         flag="red")
            flags.append((cs, pc["coord"], "embedded constants unresolved (time budget)"))

    # [4c-pre] memory-guided page reads: identity known but label absent from this
    # extraction — read the remembered page area directly (page drift tolerated)
    from . import pdfs as pdfs_mod
    _doc_pages = {str(d): pdfs_mod.pages(d) for d in disclosures}
    mem_candidates = []
    for (s_m, r_m), p_m in sorted(pending.items()):
        m_e = memory.get((s_m, r_m))
        if not m_e or m_e.get("kind") != "input" or not m_e.get("page"):
            continue
        e_m = p_m["entry"]
        if e_m.get("source") == "memory-identity" and e_m.get("flag") is None:
            continue  # memory already served this row cleanly
        coord_m = p_m["coord"]
        if any(f_[0] == s_m and f_[1] == coord_m for f_ in flags) or True:
            # locate by SECTION TITLE in the CURRENT documents — the one anchor
            # stable across years (page numbers are not)
            sec = (m_e.get("section") or "").strip()
            pages_hint = []
            if sec:
                sec_norm = sec.lower()
                for d_path, pt in _doc_pages.items():
                    hits = [pn for pn, tx in pt if sec_norm in tx.lower()][:6]
                    if hits:
                        lo, hi = min(hits), max(hits)
                        pages_hint = list(range(max(1, lo - 1), hi + 4))
                        break
            if not pages_hint:
                pg = int(m_e["page"])
                pages_hint = list(range(max(1, pg - 2), pg + 18))
            mem_candidates.append({"sheet": s_m, "row": r_m,
                                   "label": m_e.get("label") or p_m["label"],
                                   "prior_value": p_m["prior_value"],
                                   "pages": pages_hint[:12],
                                   "coord": coord_m,
                                   "prior_coord": p_m["prior_coord"]})
    if mem_candidates and time.time() < deadline:
        mem_res = targeted.rescue(map_client, system, disclosures, mem_candidates, cfg, maplog)
        fixed_m = 0
        for cand in mem_candidates:
            res = mem_res.get((cand["sheet"], cand["row"]))
            if not res:
                continue
            writer.write(cand["sheet"], cand["coord"], res["value"],
                         prior_coord=cand["prior_coord"],
                         note="memory-guided page read: " + (res.get("note") or ""),
                         flag=res.get("flag"))
            flags = [f_ for f_ in flags if not (f_[0] == cand["sheet"] and f_[1] == cand["coord"])]
            if res.get("flag"):
                flags.append((cand["sheet"], cand["coord"], res.get("note") or ""))
            fixed_m += 1
        print(f"[4c0] memory-guided page reads recovered {fixed_m}/{len(mem_candidates)} rows",
              flush=True)

    # [4c] per-row LLM consults LAST, only for rows neither path resolved
    consults = 0
    for cand in rescue_candidates:
        if time.time() >= deadline:
            maplog.append(f"time budget: {cand['sheet']}!r{cand['row']} left as flagged estimate")
            continue
        entry = mapping._llm_map(cand, staging, map_client,
                                 system, _prompt("mapping"), cfg, maplog)
        if entry and (entry.get("value") is not None or entry.get("formula")):
            v = entry.get("formula", entry.get("value"))
            writer.write(cand["sheet"], cand["coord"], v,
                         prior_coord=cand["prior_coord"],
                         note=entry.get("note"), flag="red")
            consults += 1
    if consults:
        print(f"[4c] LLM consults resolved {consults} further rows (all red-flagged)", flush=True)

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
    card, obj_log, n_fix = objectives.converge(
        wb, spec, staging, cfg, writer_obj, pre_wb, pre_values, target_year,
        last_actual, keymap, proven, flags, backouts, t0, eligible_inputs,
        obj_deadline)
    for ln in obj_notes + obj_log:
        print("  [OBJ]", ln, flush=True)
    print(f"[6] bootstrap converge: {n_fix} deterministic fixes banked", flush=True)

    # TIE-WEB: every provable subtotal becomes an anchor — the key-number method
    # cast over the whole statement, so tail errors get caught by the arithmetic
    # above them (proven-only, same guards, plugs orange-flagged)
    tw_log = []
    tw_keymap, tw_proven = objectives.tie_web(
        wb, pre_wb, spec, staging, raw_all, cfg, last_actual, target_year, tw_log,
        exclude_rows={(v["sheet"], v["row"]) for v in keymap.values()})
    n_tw = 0
    if tw_keymap:
        _c, tw_clog, n_tw = objectives.converge(
            wb, spec, staging, cfg, writer_obj, pre_wb, pre_values, target_year,
            last_actual, tw_keymap, tw_proven, flags, backouts, t0,
            eligible_inputs, obj_deadline)
        tw_log += tw_clog
    for ln in tw_log:
        print("  [TIE]", ln, flush=True)
    print(f"[6t] tie-web: {n_tw} subtotal-anchored fixes", flush=True)
    obj_log = obj_log + tw_log

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

    decisions = []
    if (cfg.get("orchestrator") or {}).get("enabled", True):
        from . import orchestrator
        card, decisions = orchestrator.run(
            map_client, system, _prompt("orchestrator"), wb, spec, staging, cfg,
            writer_obj, pre_wb, target_year, last_actual, keymap, proven, flags,
            backouts, eligible_inputs, disclosures, t0, obj_deadline,
            lambda s: print(s, flush=True),
            bootstrap_log=obj_notes + obj_log, request_review=request_review)
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
