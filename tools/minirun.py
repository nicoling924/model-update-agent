"""CONFINED RUN — the production pipeline restricted to named sheets.

Owner request (2026-08-19): test whether the agent, with the Fable-pass
teachings, can now map the cells it previously missed — on the CF
details and the Driver tab — WITHOUT paying for a full run. Everything
is the SAME as the cloud run (fair-comparison rule): the same engine and
env, the same ledger/reading/join code, the same AgentLoop + PacketCloser
+ prompts, the same pre-update workbook rolled the same way. The ONLY
difference: the packet queue is confined to the sheets under test, and
stage-3's gap reader is skipped (the compile agent under test is the
subject, not the bulk reader).

    python3 tools/minirun.py <company_dir> <period> <target_year> \
        <sheet1,sheet2> [expectations.json]

expectations.json: {"Sheet!row": value | "stale" | "flag"} — scored at
the end (value = must equal within tolerance; "stale" = must still hold
the prior AND carry a red flag; "flag" = red flag required, any value).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(company_dir, period, target_year, sheets, expect_path=None):
    from updater import ops
    from updater import spec as spec_mod
    from updater import targets as targets_mod
    from updater.closer import PacketCloser
    from updater.evidence import EvidenceBook
    from updater.llm import Client
    from updater.loop import AgentLoop
    from updater.reading import read_complete
    from updater.run import _disclosures, _model_path, ensure_keys
    from updater.stage1_read import read_documents
    from updater.writer import Writer, load

    company_dir = Path(company_dir)
    target_year = int(target_year)
    sheets = [s.strip() for s in sheets.split(",")]
    log = print

    # env identical to the cloud runner (fair comparison)
    import os
    env_file = ROOT / ".env"
    if env_file.exists():
        for ln in env_file.read_text().splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    os.environ.setdefault("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    os.environ.setdefault("LLM_MODEL", "openai/gpt-5.6-luna")
    client = Client(temperature=0.1, max_output_tokens=14000)
    log(f"[mini] engine {os.environ['LLM_MODEL']} (same as cloud)")

    # the same front half as run.update
    spec_d = spec_mod.load(company_dir, None)
    spec_mod.extend_axis(spec_d, target_year)
    ensure_keys(spec_d, company_dir, target_year, log)
    model_path = _model_path(company_dir, spec_d)
    wb = load(model_path)
    wb_values = load(model_path, data_only=True)
    targets = targets_mod.from_workbook(wb_values, spec_d, target_year,
                                        wb_formulas=wb)
    known = targets_mod.known_prior_values(targets)
    docs = _disclosures(company_dir, period)
    ledger = read_documents(docs, client=client, known_values=known, log=log)
    ledger.ensure_vintage(
        [t.prior_value for t in targets
         if isinstance(t.prior_value, (int, float))],
        [t.prior2_value for t in targets
         if isinstance(getattr(t, "prior2_value", None), (int, float))],
        log=log)
    read_complete(ledger, targets, client, docs, spec_d, log)

    writer = Writer(wb)
    book = EvidenceBook()
    run_log = []
    census = ops.rollover_all(wb, spec_d, target_year, writer, run_log.append)
    served, _dec = ops.run_join(ledger, targets, run_log)
    priors = {t.key: t.prior_value for t in targets}
    ops.write_served(wb, spec_d, target_year, served, writer, priors, book,
                     run_log.append)
    na = ops.note_anchored_serves(ledger, targets, served, run_log.append)
    na.update(ops.new_line_serves(wb, spec_d, target_year, ledger, targets,
                                  served, run_log.append))
    na.update(ops.matrix_serves(wb, spec_d, target_year, ledger,
                                targets, served, run_log.append))
    served.update(na)
    ops.write_served(wb, spec_d, target_year, na, writer, priors, book,
                     run_log.append)
    for ln in run_log[-4:]:
        log(f"[mini] {ln}")

        _ruling_p = company_dir / 'updates' / 'rebased_ruling.json'
        _ruling = (json.loads(_ruling_p.read_text())
                   if _ruling_p.exists() else None)
    ops.declare_rebased_blocks(wb, spec_d, target_year, ledger, targets,
                               writer, book, run_log.append,
                                   ruling=_ruling)
    loop = AgentLoop(wb, spec_d, target_year, ledger, targets, served,
                     writer, book, client, run_log, budget=40,
                     restatement=None, docs=docs, census=census)
    closer = PacketCloser(loop, client, log)
    for sheet in sheets:
        rep = closer.run_compile(sheet)
        log(f"[mini] {rep[:180]}")

    # honesty pass on the tested sheets only
    ops.flag_stale(wb, spec_d, target_year,
                   {s: census.get(s, []) for s in sheets}, served, writer,
                   book, run_log.append, ledger=ledger)

    # ---- score ----
    if not expect_path:
        log("[mini] no expectations file — done")
        return 0
    exp = json.loads(Path(expect_path).read_text())
    from updater.checks import prior_column, year_columns
    flags = set(writer.log["flags"])
    n_pass = 0
    print("\n== SCORE ==")
    for ref, want in exp.items():
        sheet, row = ref.rsplit("!", 1)
        row = int(row)
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        cell = f"{tcol}{row}"
        v = wb[sheet][cell].value
        pv = wb[sheet][f"{pcol}{row}"].value if pcol else None
        flagged = f"{sheet}!{tcol}{row}" in flags
        if want == "stale":
            good = (v == pv) and flagged
            got = f"value {v!r} (prior {pv!r}), flagged={flagged}"
        elif want == "flag":
            good = flagged
            got = f"value {v!r}, flagged={flagged}"
        elif isinstance(want, dict):
            wv = float(want["value"])
            good = (isinstance(v, (int, float))
                    and abs(v - wv) <= max(0.02, abs(wv) * 2e-3)
                    and (flagged or not want.get("flag")))
            got = f"value {v!r}, flagged={flagged}"
        else:
            tol = max(0.02, abs(float(want)) * 2e-3)
            good = isinstance(v, (int, float)) and abs(v - float(want)) <= tol
            got = f"value {v!r}"
        n_pass += bool(good)
        print(f"  [{'PASS' if good else 'FAIL'}] {sheet}!{cell}: "
              f"want {want} | {got}")
    print(f"\nSCORE: {n_pass}/{len(exp)}")
    u = getattr(client, "usage", None)
    if u:
        print(f"engine usage: {u}")
    return 0 if n_pass == len(exp) else 1


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(*sys.argv[1:6]))
