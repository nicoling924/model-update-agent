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

    # -- 2/3. ingest + extract (validated), cached by content signature ------
    import hashlib
    import json as _json
    sig_src = _prompt("extraction") + system + client.model + "".join(
        hashlib.sha256(p.read_bytes()).hexdigest() for p in disclosures)
    sig = hashlib.sha256(sig_src.encode()).hexdigest()[:16]
    staging_path = company_dir / "updates" / f"{period}_staging.json"
    staging = None
    if staging_path.exists():
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

    # -- 5. map + apply ------------------------------------------------------
    glossary = mapping.build_glossary(cfg, spec)
    maplog, backouts, flags = [], [], []
    backout_rules = {str(b.get("row_ref")): b for b in spec.get("backout_rules") or []}
    # mapping consultations are small questions — small fast budget, no escalation needed
    map_client = Client(temperature=cfg["updater"]["temperature"],
                        max_output_tokens=cfg["budgets"].get("mapping_output_tokens", 3000))
    deadline = t0 + cfg["budgets"]["max_run_minutes"] * 60 * 0.75
    rows_done = 0
    rescue_candidates = []
    for sheet, iv in (spec.get("input_vs_formula") or {}).items():
        s_axis = spec["year_axis"].get(sheet, axis)
        s_prior = s_axis["columns"].get(last_actual, prior_col)
        s_target = s_axis["columns"].get(target_year, target_col)
        ws_prior = pre_values[sheet]
        header_r = s_axis.get("header_row", 1)
        for r in iv.get("input_rows", []):
            if r == header_r:
                continue  # year headers are written separately, never mapped
            label = next((ws_prior[f"{lc}{r}"].value for lc in "ABCDEF"
                          if isinstance(ws_prior[f"{lc}{r}"].value, str)), f"row {r}")
            prior_cell = pre_wb[sheet][f"{s_prior}{r}"]
            row_ctx = {"sheet": sheet, "row": r, "label": label,
                       "prior_value": ws_prior[f"{s_prior}{r}"].value,
                       "prior_formula": prior_cell.value if isinstance(prior_cell.value, str) else None,
                       "backout_rule": backout_rules.get(f"{sheet}!{r}")}
            # pass 1 is deterministic-only (fast); LLM help comes later in
            # priority order: targeted rescue first, per-row consults last
            entry = mapping.resolve_row(row_ctx, staging, glossary, None, system,
                                        _prompt("mapping"), cfg, maplog)
            entry["_ctx"] = row_ctx
            rows_done += 1
            if rows_done % 50 == 0:
                print(f"    [4] {rows_done} rows mapped ({sheet})", flush=True)
            value = entry.get("formula", entry.get("value"))
            if value is None:
                continue
            writer.write(sheet, f"{s_target}{r}", value,
                         prior_coord=f"{s_prior}{r}",
                         note=entry.get("note"), flag=entry.get("flag"))
            if entry.get("flag") == "red":
                flags.append((sheet, f"{s_target}{r}", entry.get("note", "")))
                if entry.get("source") in ("estimate", "llm", "label-only (uncorroborated)"):
                    rescue_candidates.append({"sheet": sheet, "row": r, "label": label,
                                              "prior_value": row_ctx["prior_value"],
                                              "coord": f"{s_target}{r}",
                                              "prior_coord": f"{s_prior}{r}"})
            elif entry.get("flag") == "orange":
                backouts.append((sheet, f"{s_target}{r}", entry.get("note", "")))
        # formula rows: re-copy prior pattern shifted one column (mark-to-actual
        # recipe) — but REWRITE any embedded prior-year constants (MODEL_SPEC rule);
        # a copied constant is a stale 2024 number wearing a 2025 costume
        for r in iv.get("formula_rows", []):
            pv = pre_wb[sheet][f"{s_prior}{r}"].value
            if isinstance(pv, str) and pv.startswith("="):
                shifted = workbook.shift_formula(pv, s_prior, s_target)
                new_f, flag_row = shifted, None
                if mapping._CONSTS.match(pv):
                    comp = mapping._recompose(pv, staging)
                    if comp:
                        new_f = comp
                    else:
                        flag_row = "red"
                elif re.search(r"(?<![A-Za-z0-9_.])\d{3,}(?![A-Za-z0-9_.])", pv):
                    new_f, ok = mapping.rewrite_constants(shifted, staging)
                    if not ok:
                        flag_row = "red"
                writer.write(sheet, f"{s_target}{r}", new_f,
                             prior_coord=f"{s_prior}{r}",
                             note=("CONSTANTS NOT FULLY REWRITTEN from prior formula "
                                   f"{pv} — verify each embedded number" if flag_row else None),
                             flag=flag_row)
                if flag_row:
                    flags.append((sheet, f"{s_target}{r}",
                                  f"prior formula {pv}: embedded constants unresolved"))
        writer.format_rollover(sheet, s_prior, s_target)
    # [4a] targeted rescue FIRST (few batched calls, high yield)
    rescued_keys = set()
    if rescue_candidates and time.time() < deadline:
        from . import targeted
        rescued = targeted.rescue(map_client, system, disclosures,
                                  rescue_candidates, cfg, maplog)
        for (rs, rr), res in rescued.items():
            cand = next(c for c in rescue_candidates
                        if c["sheet"] == rs and c["row"] == rr)
            writer.write(rs, cand["coord"], res["value"],
                         prior_coord=cand["prior_coord"], note=res["note"])
            flags = [f for f in flags if not (f[0] == rs and f[1] == cand["coord"])]
            rescued_keys.add((rs, rr))
        print(f"[4a] targeted rescue: {len(rescued)}/{len(rescue_candidates)} "
              "flagged rows recovered with prior-corroborated re-reads", flush=True)

    # [4b] per-row LLM consults LAST, only for unrescued rows, within time budget
    consults = 0
    for cand in rescue_candidates:
        if (cand["sheet"], cand["row"]) in rescued_keys:
            continue
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
        print(f"[4b] LLM consults resolved {consults} further rows (all red-flagged)", flush=True)

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

    # -- 7. blind review -----------------------------------------------------
    findings = None
    if cfg["reviewer"]["enabled"]:
        from . import reviewer as rev
        rc = Client.reviewer(cfg)
        conventions = (Path(company_dir) / "MODEL_SPEC.md").read_text() \
            if (Path(company_dir) / "MODEL_SPEC.md").exists() else ""
        findings = rev.review(rc, _prompt("reviewer"), conventions, disclosures,
                              rev.column_dump(wb, spec), rev.column_dump(pre_wb, spec), cfg)
        print(f"[6] reviewer: {len(findings['findings'])} findings — {findings['verdict'][:120]}")

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
    provenance = [f"- updater: {client.usage}"]
    if cfg["reviewer"]["enabled"]:
        provenance.append(f"- reviewer: {rc.usage}")
    md.write_text(("## ⚠ DELIVERED WITH EXCEPTIONS\n" + "\n".join(f"- {e}" for e in soft)
                   + "\n\n" if soft else "")
                  + _markdown_report(name, period, results, restatements, flags, backouts,
                                     moves, core, findings, maplog)
                  + "\n## LLM provenance (server-reported model + token usage)\n"
                  + "\n".join(provenance) + "\n")
    print("LLM provenance:", "; ".join(provenance))
    print(f"[7] report: _REPORT tab + {md}")
    print(f"DONE in {(time.time()-t0)/60:.1f} min. Deliverable: {model_path}")


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
    elif cmd == "update":
        if len(sys.argv) < 4:
            sys.exit("usage: python run.py update <company_dir> <period>")
        cmd_update(sys.argv[2], sys.argv[3])
    else:
        sys.exit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
