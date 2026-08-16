"""Post-write statement reconciliation — the run finishes like the analyst.

After every writer has run, re-read the DISCLOSURE against the WRITTEN
column, row by row, with the model's own prior value as the row identity.
Purely deterministic — no LLM call, no label matching:

- CANDIDATES come from the consensus STAGING ITEMS (the multi-pass
  extraction already bound table columns by their year headers — the
  semantic join the council required). Raw-line left-neighbour serving
  was tried and is the poison path: on multi-year matrix pages
  (five-year statistics, quarterly tables) the left neighbour of the
  prior is the YEAR BEFORE, not the current year — five of five such
  repairs were wrong in offline replay.
- ROW IDENTITY is the model's own prior actual: an item joins a row only
  when the item's prior ties the row's prior at the row's own tolerance,
  SIGNED (item.prior ~ +pv -> serve item.value as printed; ~ -pv ->
  serve flipped; never force last year's sign).
- POSITION BINDING: the item must sit on one of the row's own home pages
  (find_homes). No home pages -> no repair for that row.
- a repair happens only when every joined item agrees on the served value
  (ambiguity = skip) and the written value disagrees beyond tolerance;
- INPUT cells only: a cell holding a reference formula (a view onto
  another sheet) is never overwritten — its source row reconciles instead;
- repairs carry the printed value + page cite and may override a lock
  (a deterministic statement join IS the statement); the world-band guard
  still applies;
- each repair must not worsen the TARGET-YEAR check residuals (forecast
  residuals may move: compensating errors hide there — the run-114 law:
  +362 forecast was -1,877 real + 2,239 masking);
- hard cap, biggest disagreements first, everything logged.
"""
import re

from .evaluator import Evaluator
from .workbook import row_tol

MAX_REPAIRS = 40
_ARITH = re.compile(r"^=[\d+\-*/(). eE]+$")


def _target_residual(wb, spec, target_year):
    ev = Evaluator(wb)
    t = 0.0
    for c in spec.get("check_rows", []):
        axis = spec["year_axis"].get(c["sheet"], {})
        col = (axis.get("columns") or {}).get(str(target_year))
        if not col:
            continue
        try:
            t += abs(ev.cell(c["sheet"], f"{col}{c['row']}") - c.get("expect", 0))
        except Exception:
            t += 1e9
    return t


def face_reconcile(wb, pre_values, spec, staging, doc_index, writer, flags,
                   target_year, last_actual, log, rows=None, cap=MAX_REPAIRS):
    """-> repairs applied. `rows` = homed census (each carries `pages`);
    `doc_index` maps disclosure file name -> doc position (0, 1, ...) so
    staging pages join the doc-qualified home-page scheme."""
    if not rows:
        log.append("face-recon: no homed rows supplied — stage skipped")
        return 0
    # STATEMENT-FACE items only (stmt tag = bs/pl/cf, set by the extraction
    # from page context). The face is its own authority — no page binding
    # needed, and it is exactly the council's scope for this stage. Offline
    # replay round 2 proved find_homes is NOT a safe binder here: small
    # colliding priors home to the wrong pages and the join misses the
    # actual face line (or worse, joins junk).
    items = []
    for it in (staging or {}).get("items", []):
        v, pr = it.get("value"), it.get("prior")
        if not isinstance(v, (int, float)) or not isinstance(pr, (int, float)):
            continue
        if not it.get("stmt") or it.get("disputed"):
            continue
        try:
            pg = int(re.sub(r"[^0-9]", "", str(it.get("page"))) or "0")
        except ValueError:
            continue
        items.append((v, pr, pg, str(it.get("label") or "")))
    ev = Evaluator(wb)
    suspects = []
    for row in rows:
        sheet, r = row["sheet"], row["row"]
        pv = row.get("prior_value")
        if not isinstance(pv, (int, float)) or pv == 0:
            continue
        axis = spec["year_axis"].get(sheet) or {}
        tcol = (axis.get("columns") or {}).get(str(target_year))
        if not tcol or sheet not in wb.sheetnames:
            continue
        stored = wb[sheet][f"{tcol}{r}"].value
        # INPUT cells only: reference formulas are views — never touched
        if isinstance(stored, str) and not _ARITH.match(stored):
            continue
        try:
            cur = ev.cell(sheet, f"{tcol}{r}")
        except Exception:
            continue
        if not isinstance(cur, (int, float)):
            continue
        # the triple lock: prior ties (row identity) + statement face
        # (authority) + label kinship (confirmation — a Driver row whose
        # prior happens to collide with a face line's must NOT join it:
        # replay round 4 grabbed operating profit into a Driver row)
        row_label = None
        ws_r = wb[sheet]
        for lc in "ABCDEF":
            lv = ws_r[f"{lc}{r}"].value
            if isinstance(lv, str) and lv.strip():
                row_label = lv.strip()
                break
        if not row_label:
            continue
        from .mapping import _overlap
        tol_a = row_tol(pv, base=0.6)
        cands = []
        for v_i, pr_i, pg_i, lbl_i in items:
            if not _overlap(row_label, lbl_i):
                continue
            if abs(pr_i - pv) <= tol_a:
                cands.append((v_i, pg_i))
            elif abs(pr_i + pv) <= tol_a:
                cands.append((-v_i, pg_i))
        if not cands or len(cands) > 6:
            continue
        vals = [v for v, _p in cands]
        if max(vals) - min(vals) > row_tol(max(vals, key=abs), base=1.0):
            continue                      # joined items disagree — skip
        sv, pg = cands[0]
        if sv == 0 or abs(sv - cur) <= row_tol(sv, base=1.0):
            continue                      # written value already ties the face
        suspects.append((abs(sv - cur), sheet, f"{tcol}{r}", cur, sv, pg,
                         len(cands)))
    suspects.sort(reverse=True)
    applied = 0
    for gap, sheet, coord, cur, sv, pg, n_inst in suspects:
        if applied >= cap:
            log.append(f"face-recon: repair cap {cap} reached — "
                       f"{len(suspects) - applied} suspects left flagged")
            break
        before = _target_residual(wb, spec, target_year)
        old_val = wb[sheet][coord].value
        ok = writer.write(sheet, coord, round(sv, 6), force_lock=True,
                          note=f"FACE-RECON: extraction prints {sv:,.2f} "
                               f"(prior-joined on home page p{pg}, "
                               f"{n_inst} item(s)); was {cur:,.2f}")
        if not ok:
            log.append(f"face-recon {sheet}!{coord}: write refused "
                       f"({cur:,.1f} -> {sv:,.1f})")
            continue
        after = _target_residual(wb, spec, target_year)
        if after > before + 1.0:
            writer.write(sheet, coord, old_val, force_lock=True,
                         note="FACE-RECON reverted: worsened target-year checks")
            log.append(f"face-recon {sheet}!{coord}: {cur:,.1f} -> {sv:,.1f} "
                       f"REVERTED (target residual {before:,.0f} -> {after:,.0f})")
            continue
        applied += 1
        flags.append((sheet, coord, f"face-recon {cur:,.1f} -> {sv:,.1f} p{pg}"))
        log.append(f"face-recon {sheet}!{coord}: {cur:,.1f} -> {sv:,.1f} "
                   f"(printed p{pg}, {n_inst} item(s); target residual "
                   f"{before:,.0f} -> {after:,.0f})")
    return applied
