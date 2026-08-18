"""Bulk operations the agent invokes as tools — proven bodies, evidence-graded.

These are the mechanical moves ported from the validated pipeline run
(rollover, guarded serving, stale honesty, composition back-outs), lifted
out of any fixed control flow: the AGENT decides when to call each (live),
and the dry-run harness calls them directly as a test path. Every write
goes through the ONE chokepoint and lands in the EvidenceBook.

Grades applied here:
  join/read conf>=4 -> A (identity/checksum-proven, citation carried)
  read conf 3       -> C (red)
  composition back-out -> D (orange formula, true-up later)
  stale rolled hardcode -> C (red) — silent staleness is illegal (r51 law)
"""
import re

from openpyxl.comments import Comment

from .checks import prior_column, year_columns
from .stage2_join import infer_composition, join, join_bound_tables
from .writer import resolve_input_site, roll_year_headers, rollover_column


def rollover_all(wb, spec_d, target_year, writer, log):
    """The owner's column convention on every axis sheet. Returns the
    hardcode census {sheet: [rows]} — the inputs actuals must overwrite."""
    census = {}
    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if not (tcol and pcol and sheet in wb.sheetnames):
            continue
        hard = rollover_column(wb, sheet, pcol, tcol)
        census[sheet] = hard
        years = sorted(year_columns(spec_d, sheet))
        py = years[years.index(str(target_year)) - 1]
        nh = roll_year_headers(writer, sheet, pcol, tcol, py, target_year)
        log(f"[ops] rolled {sheet}: {pcol}->{tcol}, {len(hard)} hardcodes, "
            f"{nh} year headers")
    return census


def run_join(ledger, targets, run_log):
    """Stage-2 deterministic join: faces, then bound non-statement tables."""
    served, decisions = join(ledger, targets, run_log)
    extra, dec2 = join_bound_tables(ledger, targets, served, run_log)
    served.update(extra)
    return served, decisions + dec2


def write_served(wb, spec_d, target_year, served, writer, priors, book, log):
    """Served values -> input cells (mark-to-actual + redirect sign law —
    the run-1 GP autopsy). Records provenance per write."""
    n_written = n_redirect = n_skip = 0
    for (sheet, row), entry in sorted(served.items()):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if not tcol or sheet not in wb.sheetnames:
            continue
        site = (sheet, row)
        value = entry["value"]
        held = wb[sheet][f"{tcol}{row}"].value
        if isinstance(held, str) and held.startswith("=") and pcol:
            site = resolve_input_site(wb, sheet, row, pcol) or (None, None)
            if site == (None, None):
                n_skip += 1
                continue
            if site != (sheet, row):
                if site in served:
                    n_skip += 1
                    continue
                n_redirect += 1
        s_sheet, s_row = site
        s_tcol = year_columns(spec_d, s_sheet).get(str(target_year))
        s_pcol = prior_column(spec_d, s_sheet, target_year)
        if not s_tcol:
            n_skip += 1
            continue
        if site != (sheet, row) and s_pcol:
            row_pv = (priors or {}).get((sheet, row))
            site_pv = wb[s_sheet][f"{s_pcol}{s_row}"].value
            if isinstance(row_pv, (int, float)) and row_pv != 0 \
                    and isinstance(site_pv, (int, float)) and site_pv != 0 \
                    and (row_pv < 0) != (site_pv < 0):
                value = -value
        conf = int(entry.get("conf") or 0)
        flag = entry.get("flag") or (None if conf >= 4 else "red")
        ok = writer.write(
            s_sheet, f"{s_tcol}{s_row}", value,
            prior_coord=f"{s_pcol}{s_row}" if s_pcol else None,
            note=entry.get("note"), flag=flag, trusted=conf >= 4)
        if ok:
            n_written += 1
            ref = f"{s_sheet}!{s_tcol}{s_row}"
            cite = (entry.get("note") or entry.get("line") or "")[:150]
            if conf >= 4:
                book.record(ref, "A", "join/checksum read",
                            citation=cite or f"p{entry.get('page')}")
            else:
                book.record(ref, "C", "low-confidence read", note=cite)
            if conf >= 5:
                writer.lock(s_sheet, f"{s_tcol}{s_row}")
    log(f"[ops] wrote {n_written} served values ({n_redirect} redirected, "
        f"{n_skip} derived/skipped)")
    return n_written


def flag_stale(wb, spec_d, target_year, census, served, writer, book, log):
    """Silent staleness is illegal (r51): every rolled hardcode no proven
    read replaced is red-flagged. NOTE (new objectives): volume is honesty,
    and there is NO budget — flags route review, they never block delivery.
    The loop is expected to clear what it can prove and claim non-disclosure
    (with a search trail) for what the document genuinely lacks."""
    n_stale = 0
    for sheet, rows in census.items():
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        for r in rows:
            ref = f"{sheet}!{tcol}{r}"
            if (sheet, r) in served or ref in writer.log["written"]:
                continue
            cell = wb[sheet][f"{tcol}{r}"]
            if not isinstance(cell.value, (int, float)):
                continue
            cell.fill = writer.fills["red"]
            cell.comment = Comment(
                "STALE INPUT: rolled from the prior actual column; no proven "
                "disclosure read replaced it — review or accept.",
                "Model Update Agent")
            writer.log["flags"].append(ref)
            book.record(ref, "C", "stale rolled input",
                        note="prior-year value carried; not yet proven")
            n_stale += 1
    if n_stale:
        log(f"[ops] {n_stale} unserved hardcode inputs flagged STALE (red)")
    return n_stale


def implied_prior_candidates(wb, spec_d, target_year, targets, ledger,
                             served, log):
    """SINGLE-YEAR tables (run-103 mechanism, ledger shape): CANDIDATES
    ONLY — never writes (measured on this corpus: flat text lines admit
    prose coincidences no deterministic guard fully removes; the legacy
    13/0 precision came from structured table HEADERS stage 1 does not
    yet preserve). The AGENT judges each candidate's line context and
    writes via set_input — cited, transactional, truth-guarded. That is
    the owner's design: tools surface, the agent thinks.

    implied_prior = current / (1 + pct/100) must reproduce the model's own
    prior at identity grade. Guards: the line must declare a YoY-change
    context, the pct must print with a %% sign, the move must be real
    (|pct| >= 0.5), and the tie must be UNIQUE.
    """
    from .numerics import SCALES
    prior_docs = ledger.prior_period_docs()
    out = []
    for t in targets:
        pv = t.prior_value
        if (t.sheet, t.row) in served or not isinstance(pv, (int, float)) \
                or abs(pv) < 1.0:
            continue
        tcol = year_columns(spec_d, t.sheet).get(str(target_year))
        if not tcol or t.sheet not in wb.sheetnames:
            continue
        if not isinstance(wb[t.sheet][f"{tcol}{t.row}"].value, (int, float)):
            continue                      # only stale hardcode inputs
        cands = []
        for it in ledger.items:
            if it.doc in prior_docs or not it.joinable():
                continue
            # PRECISION GUARDS (measured: without them the sweep served 8
            # coincidences — associate-stake 2.41%, FX-sensitivity 5%
            # prose, dividend ratios). An implied prior needs BOTH:
            # (a) the line to declare itself a year-on-year CHANGE context
            #     (同比/增减/比上年/较上年/yoy) — ownership stakes and
            #     sensitivity percents never do;
            # (b) the pct to be printed WITH a percent sign.
            line = str(it.source_line)
            if not re.search(r"同比|增减|比上年|较上年|yoy", line,
                             re.IGNORECASE):
                continue
            pcts = {float(m2) for m2 in re.findall(
                r"(-?\d+(?:\.\d+)?)\s*[%％]", line)}
            if not pcts:
                continue
            for v in it.nums:
                if v == 0 or abs(v) in {abs(p) for p in pcts}:
                    continue
                for pct in pcts:
                    if pct <= -100 or abs(pct) < 0.5 or abs(pct) >= 400:
                        continue
                    implied = v / (1 + pct / 100.0)
                    for s in SCALES:
                        if abs(abs(implied) / s - abs(pv)) <= \
                                max(abs(pv) * 0.005, 0.6):
                            cur = abs(v) / s * (1 if pv >= 0 else -1)
                            cands.append((round(cur, 4), it, pct))
                            break
        vals = {c[0] for c in cands}
        if len(vals) != 1:
            continue                      # nothing, or ambiguous — honest
        cur, it, pct = cands[0]
        out.append({"row": f"{t.sheet}!{t.row}",
                    "label": str(t.label)[:40], "prior": pv,
                    "value": cur, "pct": pct, "cell": f"{t.sheet}!{tcol}{t.row}",
                    "cite": f"{it.doc} p{it.page}: {it.source_line[:80]}",
                    "page": it.page})
    log(f"[ops] implied-prior: {len(out)} candidates (agent to judge)")
    return out


def reconcile_details(wb, spec_d, target_year, targets, ledger, writer,
                      book, log, max_passes=3):
    """RETIRED AS A WRITER (council #4, unanimous): "Oracles observe;
    executors mutate." Granting the verification oracle write authority
    corrupted net profit in run 21 (unique-in-pool != identified). The
    police detail tie-out is the surviving OBSERVER for this evidence
    class; machine mutation on it is forbidden. Kept only so museum
    exhibits can pin the retirement; never called by the run.

    Any row where the evidence oracle holds a UNIQUE identity-grade tie
    (single agreeing in-world prior-anchored candidate on a ratified
    current-doc page — the join's own evidence class) and the model
    disagrees, is written to print through the chokepoint, grade A,
    cited. Passes repeat because one truth-write can expose the next
    mismatch; the statement balances, so at the fixed point the model's
    identities hold BY CONSTRUCTION — convergence no longer depends on
    the agent's draw.

    THE BRIGHT LINE (museum-pinned): code writes ONLY on unique evidence.
    Ambiguity, definitions, bridges, plugs — the judgment world — remain
    the agent's alone. Truth outranks balance: these writes are prints,
    so they are NOT check-transactional — a truth-write that breaks an
    identity is exposing the next wrong detail, which the next pass or
    the agent then closes."""
    from .evaluator import Evaluator
    from .numerics import row_tol
    from .stage2_join import unique_evidence_value
    tl = list(targets)
    total = 0
    for p in range(max_passes):
        batch = {}
        ev = Evaluator(wb)
        for t in tl:
            got = unique_evidence_value(ledger, tl, t)
            if got is None:
                continue                    # ambiguity = judgment-land
            tcol = year_columns(spec_d, t.sheet).get(str(target_year))
            if not tcol or t.sheet not in wb.sheetnames:
                continue
            try:
                mv = ev.cell(t.sheet, f"{tcol}{t.row}")
            except Exception:
                continue
            dv, it, _s = got
            if isinstance(mv, (int, float)) \
                    and abs(abs(mv) - abs(dv)) <= max(row_tol(dv),
                                                      abs(dv) * 5e-3):
                continue
            batch[(t.sheet, t.row)] = {
                "value": dv, "status": "OK", "conf": 4, "page": it.page,
                "line": it.source_line[:60],
                "note": (f"reconciled to print: {it.doc} p{it.page}: "
                         f"{it.source_line[:80]}")}
        if not batch:
            break
        priors = {t.key: t.prior_value for t in tl}
        n = write_served(wb, spec_d, target_year, batch, writer, priors,
                        book, log)
        log(f"[ops] reconcile pass {p + 1}: {len(batch)} rows off print, "
            f"{n} written")
        total += n
        if n == 0:
            break
    return total


def flag_failed_checks(wb, spec_d, target_year, writer, book, log):
    """Boss law 1: balanced OR marked. Any check row still failing at the
    end of the run gets its cell red-flagged in EVERY failing year — an
    unbalanced model may deliver, an unbalanced-and-unmarked one may not.
    Marking only; no value is ever invented here (dead-doctrine guard)."""
    from .checks import scorecard
    card = scorecard(wb, spec_d, str(target_year))
    n = 0
    for c in card["checks"]:
        if c["status"] == "PASS":
            continue
        sheet_row = c["name"].split(" (")[0]          # "Model!r95"
        sheet, row = sheet_row.split("!r")
        col = year_columns(spec_d, sheet).get(c["year"])
        if not col or sheet not in wb.sheetnames:
            continue
        ref = f"{sheet}!{col}{row}"
        cell = wb[sheet][f"{col}{row}"]
        if type(cell).__name__ == "MergedCell":
            continue
        cell.fill = writer.fills["red"]
        got = c["got"]
        cell.comment = Comment(
            f"BALANCE CHECK FAILING: residual "
            f"{got:,.2f} — unresolved by the agent; see _REPORT."
            if isinstance(got, (int, float)) else
            "BALANCE CHECK FAILING (eval error) — see _REPORT.",
            "Model Update Agent")
        if ref not in writer.log["flags"]:
            writer.log["flags"].append(ref)
        book.entries.pop(ref, None)
        book.record(ref, "C", "failing check",
                    note=f"residual {got}" if got is not None else "eval error")
        n += 1
    if n:
        log(f"[ops] {n} failing check cells red-flagged (balanced-or-marked law)")
    return n


def sweep_compositions(wb, spec_d, target_year, census, writer, book, log):
    """Prior-column composition identities -> SUM formulas, orange (house
    back-out law: formulas, never hardcodes). Mixed-year guard included
    (the -128k residual autopsy)."""
    n_comp = 0
    for sheet, rows in census.items():
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if not pcol:
            continue
        for r in rows:
            ref = f"{sheet}!{tcol}{r}"
            if ref not in writer.log["flags"]:
                continue
            f = infer_composition(wb, sheet, r, pcol, tcol)
            if f:
                m2 = re.match(rf"^=SUM\({tcol}(\d+):{tcol}(\d+)\)$", f)
                if m2 and any(f"{sheet}!{tcol}{k}" in writer.log["flags"]
                              for k in range(int(m2.group(1)),
                                             int(m2.group(2)) + 1)):
                    f = None
            if f and writer.write(
                    sheet, f"{tcol}{r}", f, prior_coord=f"{pcol}{r}",
                    flag="orange",
                    note=("backed out: composition inferred from the prior "
                          "column's own arithmetic — true up against the "
                          "detailed disclosure")):
                book.record(ref, "D", "composition back-out",
                            note=f"formula {f}")
                n_comp += 1
    if n_comp:
        log(f"[ops] {n_comp} compositions backed out (orange)")
    return n_comp
