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
    from openpyxl.utils import column_index_from_string as _ci
    axis_offsets = {}
    for sh0 in (spec_d.get("year_axis") or {}):
        t0 = year_columns(spec_d, sh0).get(str(target_year))
        p0 = prior_column(spec_d, sh0, target_year)
        if t0 and p0:
            axis_offsets[sh0] = _ci(t0) - _ci(p0)
    for sheet in (spec_d.get("year_axis") or {}):
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if not (tcol and pcol and sheet in wb.sheetnames):
            continue
        hard = rollover_column(wb, sheet, pcol, tcol,
                               axis_offsets=axis_offsets)
        census[sheet] = hard
        years = sorted(year_columns(spec_d, sheet))
        py = years[years.index(str(target_year)) - 1]
        nh = roll_year_headers(writer, sheet, pcol, tcol, py, target_year)
        log(f"[ops] rolled {sheet}: {pcol}->{tcol}, {len(hard)} hardcodes, "
            f"{nh} year headers")
    return census


def run_join(ledger, targets, run_log):
    """Stage-2 deterministic join: faces, then bound non-statement tables.

    ALT-ANCHOR PASS (interim runs, 2026-08-25): an interim filing's BS
    lines print [Jun-25, Dec-24] — the Dec-24 comparative ties the
    model's ANNUAL prior (alt_prior_value), not the Jun-24 interim prior.
    Unserved rows carrying an alt anchor get a second join pass with the
    alt as the identity key; serves are marked so notes say which anchor
    proved them."""
    served, decisions = join(ledger, targets, run_log)
    extra, dec2 = join_bound_tables(ledger, targets, served, run_log)
    served.update(extra)
    alt_ts = []
    import dataclasses as _dc
    for t in targets:
        alt = getattr(t, "alt_prior_value", None)
        if t.key in served or not isinstance(alt, (int, float)) \
                or abs(alt) < 1.0:
            continue
        if isinstance(t.prior_value, (int, float)) \
                and abs(alt - t.prior_value) <= max(0.02,
                                                    abs(alt) * 1e-4):
            continue
        alt_ts.append(_dc.replace(t, prior_value=alt))
    if alt_ts:
        s2, d2 = join(ledger, alt_ts, run_log)
        n_new = 0
        for k, entry in s2.items():
            if k in served:
                continue
            entry["note"] = ("year-end comparative anchor (interim BS "
                             "law): " + str(entry.get("note") or ""))[:200]
            served[k] = entry
            n_new += 1
        if n_new:
            run_log.append(f"[ops] alt-anchor join: {n_new} rows served "
                           f"via the prior YEAR-END comparative")
        decisions += d2
    return served, decisions


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


def declare_rebased_blocks(wb, spec_d, target_year, ledger, targets,
                           writer, book, log, ruling=None):
    """THE REBASED BLOCK AS STATE (runs 29/31/32: write-time guards were
    re-phrased around under repair pressure, three full runs in a row).
    When >=2 segment leaves on one sheet have priors that tie NO
    current-filing comparative at identity, the filing re-based that
    partition — the owner's restatement class. Those rows leave the work
    queue entirely (red-flagged with the analyst question); leaves whose
    priors still tie stay open (their scope survived). Deterministic;
    runs at ground time."""
    import re as _re
    from openpyxl.comments import Comment
    from .checks import year_columns as _yc
    from .numerics import SCALES as _S, to_model_units as _tmu
    prior_docs = ledger.prior_period_docs()
    cur_nums = [n for it in ledger.items
                if it.doc not in prior_docs
                and not getattr(it, "disputed", False)
                for n in it.nums]

    def _ties_filing(pv):
        # cent-exact (the oracle's lesson): a loose tolerance lets junk
        # coincidences mask a re-base
        tol = max(0.6, abs(pv) * 2e-5)
        return any(abs(abs(_tmu(n, s)) - abs(pv)) <= tol
                   for n in cur_nums for s in _S)

    # collect revenue/GP key leaves (the segment world)
    seen, leaves = set(), []

    def walk(sh, coord, depth=0):
        if depth > 6 or (sh, coord) in seen or len(seen) > 400:
            return
        seen.add((sh, coord))
        v = wb[sh][coord].value if sh in wb.sheetnames else None
        m = _re.match(r"^([A-Z]{1,3})(\d+)$", coord)
        if isinstance(v, (int, float)):
            if m and m[1] == _yc(spec_d, sh).get(str(target_year)):
                leaves.append((sh, int(m[2])))
            return
        if not isinstance(v, str) or not v.startswith("="):
            return
        for sh2, sh3, c2, r2 in _re.findall(
                r"(?:'([^']+)'!|([A-Za-z0-9 _]+)!)?([A-Z]{1,3})(\d+)",
                v.replace("$", "")):
            s2 = (sh2 or sh3 or sh).strip()
            if s2 in wb.sheetnames:
                walk(s2, f"{c2}{r2}", depth + 1)

    for k in spec_d.get("key_rows") or []:
        if any(w in str(k.get("name", "")).lower()
               for w in ("revenue", "sales", "gross")):
            tc = _yc(spec_d, k["sheet"]).get(str(target_year))
            if tc and k["sheet"] in wb.sheetnames:
                walk(k["sheet"], f"{tc}{int(k['row'])}")

    # A PRESENTATION-LAYER segment block feeds FROM the key, not into it
    # (DFE: Driver!J14 = Model!U4, so a walk down from revenue never
    # reaches the block). Such a block announces itself: its TOTAL row
    # references a key cell; its own formulas within the neighbourhood
    # name the members.
    prior_by_row = {t.key: t.prior_value for t in targets
                    if isinstance(t.prior_value, (int, float))}
    key_cells = set()
    key_priors = set()
    for k in spec_d.get("key_rows") or []:
        if any(w in str(k.get("name", "")).lower()
               for w in ("revenue", "sales", "gross")):
            tc = _yc(spec_d, k["sheet"]).get(str(target_year))
            if tc:
                key_cells.add((k["sheet"].lower(), f"{tc}{int(k['row'])}"))
            t0 = next((t for t in targets
                       if t.key == (k["sheet"], int(k["row"]))), None)
            kv = getattr(t0, "prior_value", None)
            if isinstance(kv, (int, float)) and abs(kv) > 100:
                key_priors.add(abs(kv))
    for sh in (spec_d.get("year_axis") or {}):
        tc = _yc(spec_d, sh).get(str(target_year))
        if not tc or sh not in wb.sheetnames:
            continue
        ws = wb[sh]
        for r in range(1, ws.max_row + 1):
            v = ws[f"{tc}{r}"].value
            if not (isinstance(v, str) and v.startswith("=")):
                continue
            refs = _re.findall(
                r"(?:'([^']+)'|([A-Za-z0-9 _]+))!([A-Z]{1,3})(\d+)",
                v.replace("$", ""))
            ref_hit = any(((a or b).strip().lower(), f"{c}{d}")
                          in key_cells for a, b, c, d in refs)
            if not ref_hit:
                # VALUE anchor (the fablemode principle — anchor by
                # number, not by reference): a formula total whose
                # PRIOR-year value ties a key's prior cent-exact IS the
                # block total, whatever its formula shape. Priors come
                # from the census (the workbook view holds formulas).
                pv0 = prior_by_row.get((sh, r))
                if not (isinstance(pv0, (int, float)) and any(
                        abs(abs(pv0) - kp) <= max(0.6, kp * 2e-5)
                        for kp in key_priors)):
                    continue
            # anchor found: harvest same-sheet member rows from formulas
            # in the neighbourhood
            for r2 in range(max(1, r - 12), r + 4):
                v2 = ws[f"{tc}{r2}"].value
                if isinstance(v2, str) and v2.startswith("="):
                    for c3, r3 in _re.findall(r"(?<![A-Za-z0-9_!'])"
                                              r"([A-Z]{1,3})(\d+)",
                                              v2.replace("$", "")):
                        if c3 == tc and abs(int(r3) - r) <= 14:
                            leaves.append((sh, int(r3)))
                elif isinstance(v2, (int, float)):
                    if abs(r2 - r) <= 14:
                        leaves.append((sh, r2))

    fails_by_sheet = {}
    for sh, row in leaves:
        pcol = prior_column(spec_d, sh, target_year)
        pv = wb[sh][f"{pcol}{row}"].value if pcol else None
        if isinstance(pv, (int, float)) and abs(pv) > 1.0 \
                and not _ties_filing(pv):
            fails_by_sheet.setdefault(sh, []).append(row)
    rebased = set()
    # RECLASSIFICATION LAW (owner ruling 2026-08-24, BOSS_MINDMAP): a
    # re-cut partition whose PRIOR history is uncontradicted is a
    # reclassification, not a restatement — the agent maps the current
    # year by MEANING (or backs out), red-flagged, structure untouched,
    # and never stalls the block waiting for a ruling. The freeze path
    # remains only when an explicit ruling file says {"write_current":
    # false} (an analyst can still order a freeze).
    ruled = not (ruling and ruling.get("write_current") is False)
    for sh, rows in fails_by_sheet.items():
        if len(rows) < 2:
            continue
        tc = _yc(spec_d, sh).get(str(target_year))
        for row in rows:
            ref = f"{sh}!{tc}{row}"
            cell = wb[sh][f"{tc}{row}"]
            cell.fill = writer.fills["red"]
            if ruled:
                # THE ANALYST HAS RULED (restatement answered): keep the
                # prior year untouched, keep the structure, WRITE the
                # current year from the new partition — mandatory red.
                # Rows stay OPEN; derived mappings are analyst-sanctioned.
                rr = writer.log.setdefault("rebased_ruled", [])
                if f"{sh}!{row}" not in rr:
                    rr.append(f"{sh}!{row}")
                cell.comment = Comment(
                    "RECLASSIFIED partition (owner law): the filing re-cut "
                    "this breakdown; prior history is uncontradicted. The "
                    "current year is written by MEANING from the new "
                    "partition (or backed out), red flag kept; the prior "
                    "year and the model's structure stay untouched. "
                    + str((ruling or {}).get("ruled", ""))[:120],
                    "Model Update Agent")
                if ref not in writer.log["flags"]:
                    writer.log["flags"].append(ref)
                book.record(ref, "C", "reclassified — write by meaning",
                            note="reclassification law (structure untouched)")
                continue
            rebased.add((sh, row))
            cell.comment = Comment(
                "SEGMENT BASIS CHANGED (restatement class): this row's "
                "prior-year figure ties nothing in the current filing — "
                "the company re-cut its categories. Held STALE for the "
                "analyst's re-basing ruling; the filing's new partition "
                "is in _REPORT. No estimate is ever written here.",
                "Model Update Agent")
            if ref not in writer.log["flags"]:
                writer.log["flags"].append(ref)
            book.record(ref, "C", "rebased block",
                        note="basis changed — analyst ruling required")
    writer.log["rebased"] = sorted(f"{s}!{r}" for s, r in rebased)
    if rebased:
        log(f"[ops] REBASED BLOCK declared: {len(rebased)} segment rows "
            f"held stale+red for the analyst "
            f"({', '.join(writer.log['rebased'][:6])})")
    return rebased


def consensus_filter(gap, ledger, targets, log):
    """Run 30: stage-3's single reader wrote the 其中 sub-line while the
    pool held the parent's value in THREE agreeing printings — a lone
    read may never contradict the pool. Where the evidence oracle holds
    a unique agreeing value for a row, a contradicting stage-3 answer is
    OVERRIDDEN by the pool's print (grade A evidence beats one reading);
    agreeing answers pass through untouched."""
    from .stage2_join import unique_evidence_value
    tmap = {t.key: t for t in targets}
    n = 0
    n_noprior = 0
    for k in list(gap.keys()):
        t = tmap.get(k)
        if t is None:
            continue
        # NO-PRIOR STAGE-3 WRITES DIE HERE (CLP run 5: the "no
        # comparative to checksum" acceptance wrote group figures into
        # section headers). Stage-3's authority IS the checksum; a row
        # with no prior belongs to new_line_serves (name-exact +
        # closure-proven) or to nobody.
        if not isinstance(t.prior_value, (int, float)) \
                or abs(t.prior_value) < 0.01:
            del gap[k]
            n_noprior += 1
            continue
        got = unique_evidence_value(ledger, targets, t)
        if got is None:
            continue
        dv = got[0]
        v = gap[k].get("value")
        if isinstance(v, (int, float)) \
                and abs(abs(v) - abs(dv)) > max(0.6, abs(dv) * 5e-3):
            gap[k] = {**gap[k], "value": dv, "conf": 4,
                      "note": (f"pool consensus OVERRODE a stage-3 read "
                               f"({v:,.2f}): the report's agreeing print is "
                               f"{dv:,.2f} ({got[1].doc} p{got[1].page}: "
                               f"'{got[1].source_line[:60]}')")}
            n += 1
    if n or n_noprior:
        log(f"[ops] consensus filter: {n} stage-3 reads overridden by the "
            f"pool's agreeing print; {n_noprior} no-prior reads dropped "
            f"(no checksum, no write)")
    return gap


def home_serves(wb, spec_d, target_year, ledger, targets, served, log):
    """HOME-SCOPED JOIN (SoC class, 2026-08-20): on the sheet's OWN
    statement page (packets.home_pages — discovered by prior-column mass,
    no captions, any language), a unique cent-exact two-number
    [current, prior] line IS the row's print. Global-oracle ambiguity (a
    prior like 80 ties junk lines all over a 300-page report) dissolves
    under home locality. Served conf 3 (grade C, red) — the analyst still
    reviews. Sign follows the model's own convention: the printed pair's
    prior sign is mapped onto the model prior's sign."""
    from .numerics import SCALES, to_model_units
    from .packets import home_pages
    from .stage2_join import _ofwhich_block
    out = {}
    # KEY rows are out of jurisdiction (DFE benchmark catch, 2026-08-20:
    # a grade-C home serve mutated the printed net-profit key). Keys are
    # pinned by the key gate and served by identity machinery only.
    key_rows = {(k["sheet"], int(k["row"]))
                for k in spec_d.get("key_rows") or []}
    sheets = {t.sheet for t in targets
              if t.key not in served
              and isinstance(t.prior_value, (int, float))
              and abs(t.prior_value) >= 1.0}
    for sheet in sorted(sheets):
        try:
            homes = frozenset(
                (d, p) for d, p, _n in home_pages(
                    wb, spec_d, str(target_year), sheet, ledger,
                    targets=targets))
        except Exception:
            homes = frozenset()
        if not homes:
            continue
        _strip = getattr(ledger, "strip_note_ref", lambda x: x)
        pool = [_strip(it) for it in ledger.items
                if (it.doc, it.page) in homes]
        for t in targets:
            if (t.sheet != sheet or t.key in served or t.key in out
                    or t.key in key_rows
                    or getattr(t, "is_backout", False)
                    or not isinstance(t.prior_value, (int, float))
                    or abs(t.prior_value) < 1.0):
                continue
            pv = t.prior_value
            tol = max(0.05, abs(pv) * 2e-5)
            cands = []
            for it in pool:
                if len(it.nums) != 2 \
                        or _ofwhich_block(t.label, it.label):
                    continue
                for s in SCALES:
                    p_print = to_model_units(it.nums[1], s)
                    if abs(abs(p_print) - abs(pv)) <= tol:
                        cv = to_model_units(it.nums[0], s)
                        sgn = 1 if (p_print >= 0) == (pv >= 0) else -1
                        v = cv * sgn
                        if not any(abs(v - v0) <= max(0.05,
                                                      abs(v0) * 5e-3)
                                   for v0, _i in cands):
                            cands.append((v, it))
                        break
            if len(cands) == 1:
                v, it = cands[0]
                out[t.key] = {
                    "value": round(v, 4), "status": "OK", "conf": 3,
                    "page": it.page, "line": it.label[:60],
                    "note": (f"home-statement join: the sheet's own "
                             f"statement (p{it.page}) prints "
                             f"'{it.source_line[:60]}' — unique pair "
                             f"tying prior {pv:,.2f}")}
    if out:
        log(f"[ops] home-statement join: {len(out)} rows served from "
            f"sheets' own statement pages (grade C, red)")
    return out


def home_pair(ledger, t, homes):
    """The sheet's-own-statement print for ONE target row (balance
    reconciliation law, 2026-08-20: CLP run 8 delivered unbalanced
    because mis-mapped BS rows had no globally-unique print — but their
    own statement page named them all along).

    -> (value, item, kind) | None.
    kind='pair':  a unique cent-exact [current, prior] home line ties the
                  row's prior — identity grade, sign mapped to the model.
    kind='label': no pair, but a unique home line KINSHIPS the row's
                  label (comparative does not tie) — counterpart-law
                  candidate, mandatory red flag if written. Scale is
                  unprovable without the prior anchor, so document scale
                  1 only, magnitude-banded against the model prior."""
    from .numerics import SCALES, kinship, to_model_units
    from .stage2_join import _ofwhich_block
    if not homes:
        return None
    _strip = getattr(ledger, "strip_note_ref", lambda x: x)
    pool = [_strip(it) for it in ledger.items
            if (it.doc, it.page) in homes]
    pv = t.prior_value
    if isinstance(pv, (int, float)) and abs(pv) >= 1.0:
        tol = max(0.05, abs(pv) * 2e-5)
        cands = []
        for it in pool:
            if len(it.nums) != 2 or _ofwhich_block(t.label, it.label):
                continue
            for s in SCALES:
                p_print = to_model_units(it.nums[1], s)
                if abs(abs(p_print) - abs(pv)) <= tol:
                    cv = to_model_units(it.nums[0], s)
                    v = cv * (1 if (p_print >= 0) == (pv >= 0) else -1)
                    if not any(abs(v - v0) <= max(0.05, abs(v0) * 5e-3)
                               for v0, _i in cands):
                        cands.append((v, it))
                    break
        if len(cands) == 1:
            return (cands[0][0], cands[0][1], "pair")
    # label-candidate mode: the comparative moved (restated / different
    # definition) but the statement still names the row
    lab_cands = []
    for it in pool:
        if len(it.nums) < 2 or not kinship(t.label, it.label) \
                or _ofwhich_block(t.label, it.label):
            continue
        cv = it.nums[0]
        if isinstance(pv, (int, float)) and abs(pv) >= 1.0 \
                and not (abs(pv) / 100 <= abs(cv) <= abs(pv) * 100):
            continue
        if not any(abs(cv - c0) <= max(0.05, abs(c0) * 5e-3)
                   for c0, _i in lab_cands):
            lab_cands.append((cv, it))
    if len(lab_cands) == 1:
        cv, it = lab_cands[0]
        if isinstance(pv, (int, float)) and pv < 0 <= cv:
            cv = -cv
        return (cv, it, "label")
    return None


def note_anchored_serves(ledger, targets, served, log):
    """The SECOND-PRINTING law as code (the Fable pass, run-28 应收股利):
    a value printed in TWO independent places, each time on a line whose
    label matches the model row exactly and whose comparative ties the
    row's prior at identity grade, is disclosed — no face authority
    needed. Served conf 3 (grade C, red) so the analyst still reviews the
    note-world read. Requirements are conjunctive and strict: exact
    normalized label, identity prior tie, >=2 distinct pages, all
    printings agreeing on the current value."""
    from .numerics import SCALES, norm_label, to_model_units
    prior_docs = ledger.prior_period_docs()
    out = {}
    for t in targets:
        pv = t.prior_value
        if (t.key in served or getattr(t, "is_backout", False)
                or not isinstance(pv, (int, float)) or abs(pv) < 1.0):
            continue
        t_norm = norm_label(str(t.label)).replace(" ", "")
        if len(t_norm) < 2:
            continue
        tol = max(0.6, abs(pv) * 5e-4)
        hits = []
        for it in ledger.items:
            if (it.doc in prior_docs or getattr(it, "disputed", False)
                    or len(it.nums) < 2):
                continue
            if norm_label(str(it.label)).replace(" ", "") != t_norm:
                continue
            for s in SCALES:
                ns = [to_model_units(n, s) for n in it.nums]
                prs = [ns[i] for i in range(len(ns) - 1)
                       if abs(abs(ns[i + 1]) - abs(pv)) <= tol]
                if len(prs) == 1:
                    hits.append((round(prs[0], 4), it))
                    break
        pages = {it.page for _v, it in hits}
        vals = {v for v, _it in hits}
        if len(pages) >= 2 and len(vals) == 1:
            v, it = hits[0]
            out[t.key] = {
                "value": v, "status": "OK", "conf": 3, "page": it.page,
                "line": it.label[:60],
                "note": (f"note-anchored DOUBLE PRINTING: '{it.label[:30]}' "
                         f"with the row's prior beside it on "
                         f"{len(pages)} pages "
                         f"(p{', p'.join(str(p) for p in sorted(pages))}) — "
                         f"review (note-world read)")}
    if out:
        log(f"[ops] note-anchored double printings: {len(out)} rows served "
            f"(grade C, red)")
    return out


def new_line_serves(wb, spec_d, target_year, ledger, targets, served, log):
    """THE NEW-LINE SERVE (owner's name-first ruling + closure proof):
    a statement line whose label matches a BLANK model row EXACTLY
    (normalized), carried by a closure item whose column placement the
    section arithmetic PROVED, is disclosed for that row — served grade
    C (red) for analyst review. Both legs are identities (exact name,
    proven placement); nothing is guessed. Scope is deliberately tight:
    closure-channel items only (faces, proven), target blank in BOTH
    year columns, and the name match unique."""
    from .checks import year_columns as _yc
    from .numerics import norm_label
    prior_docs = ledger.prior_period_docs()
    out = {}
    by_norm = {}
    for it in ledger.items:
        if it.doc in prior_docs or getattr(it, "channel", "") != "closure":
            continue
        if len(it.nums) == 2 and it.nums[0] != 0:
            by_norm.setdefault(
                norm_label(str(it.label)).replace(" ", ""), []).append(it)
    if not by_norm:
        return out
    # CENT-EXACT page ratification (resume test: the loose ratifier
    # picked a wrong scale on one draw and the serve landed 1000x off —
    # at 2e-5 tolerance junk cannot tie, so only the true scale
    # survives; ambiguity serves nothing)
    from .numerics import to_model_units as _tmu2
    model_priors = sorted({abs(t.prior_value) for t in targets
                           if isinstance(t.prior_value, (int, float))
                           and abs(t.prior_value) > 100})
    page_items = {}
    for it in ledger.items:
        if it.doc not in prior_docs and not getattr(it, "disputed", False):
            page_items.setdefault((it.doc, it.page), []).append(it)

    def _tight_scale(doc, page):
        import bisect as _b
        best = []
        for s2 in (1.0, 1e3, 1e4, 1e6, 1e8):
            hits = 0
            for it in page_items.get((doc, page), []):
                for n in it.nums[1:]:
                    a = abs(_tmu2(n, s2))
                    i = _b.bisect_left(model_priors, a - 1)
                    if i < len(model_priors) and abs(
                            model_priors[i] - a) <= max(
                                0.6, model_priors[i] * 2e-5):
                        hits += 1
                        break
            best.append((hits, s2))
        best.sort(reverse=True)
        if best[0][0] >= 2 and best[0][0] > best[1][0]:
            return best[0][1]
        return None

    scales = {}
    for sheet in (spec_d.get("year_axis") or {}):
        tcol = _yc(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        if not tcol or not pcol or sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        for r in range(1, ws.max_row + 1):
            if ws[f"{tcol}{r}"].value is not None \
                    or ws[f"{pcol}{r}"].value is not None \
                    or (sheet, r) in served:
                continue
            lab = next((ws[f"{lc}{r}"].value for lc in ("A", "B", "C", "D")
                        if isinstance(ws[f"{lc}{r}"].value, str)
                        and ws[f"{lc}{r}"].value.strip()), None)
            if not lab:
                continue
            key = norm_label(str(lab)).replace(" ", "")
            hits = by_norm.get(key) or []
            vals = {round(it.nums[0], 2) for it in hits}
            if len(hits) >= 1 and len(vals) == 1:
                it = hits[0]
                # scale must be RATIFIED for the page — an unproven scale
                # serves nothing (the scale law, unchanged)
                if (it.doc, it.page) not in scales:
                    scales[(it.doc, it.page)] = _tight_scale(it.doc,
                                                             it.page)
                s = scales.get((it.doc, it.page))
                if s is None:
                    continue
                from .numerics import to_model_units
                # NEIGHBOUR SANITY (resume test: one draw ratified the
                # page at the wrong scale and the serve landed 1000x off
                # — the write path here has no band, so the column's own
                # neighbours judge the unit world)
                cand = to_model_units(it.nums[0], s)
                neigh = [abs(ws[f"{pcol}{r2}"].value)
                         for r2 in range(max(1, r - 6), r + 7)
                         if isinstance(ws[f"{pcol}{r2}"].value, (int, float))
                         and abs(ws[f"{pcol}{r2}"].value) > 0.01]
                if neigh:
                    med = sorted(neigh)[len(neigh) // 2]
                    if med > 0 and abs(cand) / med >= 500:
                        continue
                out[(sheet, r)] = {
                    "value": to_model_units(it.nums[0], s), "status": "OK",
                    "conf": 3, "page": it.page, "line": it.label[:60],
                    "note": (f"NEW LINE this year: exact-name statement "
                             f"line with closure-proven placement "
                             f"({it.doc} p{it.page}) — review")}
    if out:
        log(f"[ops] new-line serves: {len(out)} blank rows filled from "
            f"closure-proven exact-name lines (grade C, red)")
    return out


def flag_stale(wb, spec_d, target_year, census, served, writer, book, log,
               ledger=None):
    """FLAG DISCIPLINE (owner's 2026-08-17 stale ruling, re-affirmed on
    the CLP first flight: "why is almost every input red?"): a red flag
    marks a figure the filing DEMONSTRABLY CARRIES (its prior is
    locatable) that the run failed to resolve — review it. A row the
    filing genuinely does not print stays quietly stale with one line in
    _REPORT and NO cell flag. Flags route review; wallpaper is noise."""
    from .numerics import SCALES as _S, to_model_units as _tmu
    prior_docs = ledger.prior_period_docs() if ledger is not None else set()
    cur_nums = ([n for it in ledger.items
                 if it.doc not in prior_docs
                 and not getattr(it, "disputed", False)
                 for n in it.nums] if ledger is not None else None)

    gap_priors = ([it.nums[1] for it in ledger.items
                   if getattr(it, "channel", "") == "closure-gap"
                   and len(it.nums) == 2 and it.nums[1]]
                  if ledger is not None else [])

    def _locatable(pv):
        if cur_nums is None:
            return True                    # no ledger: legacy behavior
        if not isinstance(pv, (int, float)) or abs(pv) < 1.0:
            return False
        tol = max(0.6, abs(pv) * 5e-4)
        if any(abs(abs(_tmu(n, s)) - abs(pv)) <= tol
               for n in cur_nums for s in _S):
            return True
        # a model-ADJUSTED row's prior is not printed, but its printed
        # line's derived gap sits within the adjustment's world — the
        # figure is in the filing (the 销售商品 carve-out signature)
        return any(any(abs(abs(_tmu(g, s)) - abs(pv)) <= abs(pv) * 0.05
                       for s in _S) for g in gap_priors)

    n_stale = n_quiet = 0
    for sheet, rows in census.items():
        tcol = year_columns(spec_d, sheet).get(str(target_year))
        pcol = prior_column(spec_d, sheet, target_year)
        for r in rows:
            ref = f"{sheet}!{tcol}{r}"
            if (sheet, r) in served or ref in writer.log["written"]:
                continue
            cell = wb[sheet][f"{tcol}{r}"]
            if not isinstance(cell.value, (int, float)):
                continue
            pv = wb[sheet][f"{pcol}{r}"].value if pcol else None
            if _locatable(pv):
                cell.fill = writer.fills["red"]
                cell.comment = Comment(
                    "STALE INPUT: the filing prints this figure's world "
                    "(its prior is locatable) but no proven read replaced "
                    "it — review.", "Model Update Agent")
                writer.log["flags"].append(ref)
                book.record(ref, "C", "stale rolled input",
                            note="prior locatable in filing; unresolved")
                n_stale += 1
            else:
                book.record(ref, "C", "not located in filing",
                            note="quietly stale — the filing does not "
                                 "print this figure's prior (listed, "
                                 "no cell flag)")
                n_quiet += 1
    if n_stale or n_quiet:
        log(f"[ops] stale inputs: {n_stale} red-flagged (locatable), "
            f"{n_quiet} quietly stale (_REPORT only)")
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


def rebase_serves(wb, spec_d, target_year, ledger, targets, writer, book,
                  ruling, client, log):
    """THE REBASE PACKET (owner-ruled blocks only): one focused call,
    machine-certified. The counterpart partition table is identified BY
    NUMBER (its total's current value ties the revenue key's oracle
    print cent-exact); its CURRENT column is identified the same way.
    The LLM maps model rows onto that table's rows by meaning; code
    accepts a value only if it IS a cell of the identified current
    column, or a parent equal to the sum of 2-4 such cells (sub-rows
    first). Every write is red (the ruling's law). Wrong-column and
    wrong-scale answers are impossible, not discouraged."""
    if client is None or not (ruling and ruling.get("write_current")):
        return 0
    ruled = list(writer.log.get("rebased_ruled") or [])
    if not ruled:
        return 0
    from .checks import year_columns as _yc
    from .numerics import SCALES as _S, to_model_units as _tmu
    from .stage2_join import unique_evidence_value
    tl = list(targets)
    tmap = {t.key: t for t in tl}
    # the revenue key's CURRENT print, via the oracle
    rev_cur = None
    for k in spec_d.get("key_rows") or []:
        if "revenue" in str(k.get("name", "")).lower() \
                or "sales" in str(k.get("name", "")).lower():
            t0 = tmap.get((k["sheet"], int(k["row"])))
            got = unique_evidence_value(ledger, tl, t0) if t0 else None
            if got is not None:
                rev_cur = abs(got[0])
                break
    if rev_cur is None:
        log("[rebase] no oracle print for revenue — packet skipped")
        return 0
    # the counterpart table + its current column, BY NUMBER
    prior_docs = ledger.prior_period_docs()
    tables = {}
    for it in ledger.items:
        if it.doc in prior_docs or getattr(it, "disputed", False) \
                or it.table_id is None:
            continue
        tables.setdefault((it.doc, it.page, it.table_id), []).append(it)
    home = col = None
    for key, rows in tables.items():
        for it in rows:
            for j, n in enumerate(it.nums):
                for s in _S:
                    if abs(abs(_tmu(n, s)) - rev_cur) <= max(
                            0.6, rev_cur * 2e-5):
                        home, col, scale = key, j, s
                        break
                if home:
                    break
            if home:
                break
        if home:
            break
    if home is None:
        log("[rebase] no partition table ties the revenue print — skipped")
        return 0
    rows = sorted(tables[home], key=lambda x: x.row_ord)
    legal = {}
    for it in rows:
        if len(it.nums) > col:
            legal[str(it.label)[:40]] = round(
                _tmu(it.nums[col], scale), 4)
    card = ["THE ANALYST RULED this re-based partition: prior year stays; "
            "THIS year is written from the new partition. Map each MODEL "
            "row to the new table's rows BY MEANING (any language). "
            "sub-rows first; a parent may be the sum of its mapped subs. "
            "Respond {\"mapping\": [{\"cell\": \"Sheet!row\", \"rows\": "
            "[\"<table row label>\", ...]}]} — every ruled row must "
            "appear; 'rows': [] is only legal WITH a concrete "
            "why_unmappable (the analyst has already ruled the block "
            "writable — the safe-looking refusal is the wrong answer "
            "here).",
            "== THE NEW PARTITION (current-year column, model units) =="]
    card += [f"  {lab}: {v:,.2f}" for lab, v in legal.items()]
    card.append("== THE MODEL BLOCK (its FORMULAS define each row's "
                "scope: a row derived as parent minus siblings is a "
                "COMPONENT; a parent excludes whatever sibling rows "
                "outside it carry — map SCOPES, not just names. A row "
                "whose PRIOR-year cell is a HARDCODE is an INPUT even if "
                "this year's cell holds a forecast formula — mark-to-"
                "actual replaces the formula, so MAP IT; a row that "
                "derives from its mapped siblings needs no mapping of "
                "its own) ==")
    shown = set()
    for ref in ruled:
        sh, r = ref.split("!")
        t0 = tmap.get((sh, int(r)))
        card.append(f"  {sh}!{r} '{str(getattr(t0, 'label', ''))[:36]}' "
                    f"prior {getattr(t0, 'prior_value', None)}")
        shown.add((sh, int(r)))
    # neighbouring block rows (formulas included) give the structure
    for ref in ruled[:1]:
        sh, _r0 = ref.split("!")
        tc0 = _yc(spec_d, sh).get(str(target_year))
        rows_n = sorted({int(x.split("!")[1]) for x in ruled
                         if x.startswith(sh + "!")})
        lo0, hi0 = max(1, rows_n[0] - 2), rows_n[-1] + 3
        card.append(f"  -- structure of {sh} rows {lo0}-{hi0} --")
        for r2 in range(lo0, hi0 + 1):
            v2 = wb[sh][f"{tc0}{r2}"].value
            lab2 = next((wb[sh][f"{c}{r2}"].value for c in "AB"
                         if isinstance(wb[sh][f"{c}{r2}"].value, str)), "")
            card.append(f"    r{r2} '{str(lab2)[:30]}' holds "
                        f"{str(v2)[:44]!r}")

    def _val(o):
        if not isinstance(o.get("mapping"), list):
            return ["'mapping' list required"]
        covered = {str(m.get("cell")) for m in o["mapping"]
                   if isinstance(m, dict)}
        missing = [r for r in ruled if r not in covered]
        if missing:
            return [f"every ruled row must appear: missing {missing}"]
        for m in o["mapping"]:
            if not m.get("rows") and not str(m.get("why_unmappable",
                                                   "")).strip():
                return [f"{m.get('cell')}: the analyst RULED this block "
                        "writable — map it, or state why_unmappable in "
                        "one concrete sentence (silent refusal is not "
                        "an answer)"]
        return []
    try:
        out = client.json("You map a model's segment rows onto a filing's "
                          "re-based partition. Meaning maps; the machine "
                          "verifies.", "\n".join(card), _val,
                          repair_retries=1)
    except Exception as e:
        log(f"[rebase] packet failed: {e}")
        return 0
    n = 0
    from openpyxl.comments import Comment
    for m in out.get("mapping", []) or []:
        ref = str(m.get("cell", ""))
        names = [str(x) for x in (m.get("rows") or [])]
        if ref not in ruled or not names or len(names) > 4:
            continue
        vals = [legal.get(x[:40]) for x in names]
        if any(v is None for v in vals):
            continue
        value = round(sum(vals), 4)
        sh, r = ref.split("!")
        tc = _yc(spec_d, sh).get(str(target_year))
        ok = writer.write(sh, f"{tc}{r}", value, flag="red",
                          note=(f"REBASED (analyst-ruled): mapped from the "
                                f"new partition rows {', '.join(names[:3])}"
                                f" — verify the scope"))
        if ok:
            book.record(f"{sh}!{tc}{r}", "C", "rebase mapping",
                        citation=f"partition p{home[1]}")
            n += 1
    log(f"[rebase] ruled block: {n} rows written from the certified "
        f"current column (red)")
    return n


def matrix_serves(wb, spec_d, target_year, ledger, targets, served, log,
                  docs=(), _grids=None):
    """THE 2D MATRIX JOIN, grid-true (CLP segment note): matrix pages are
    re-read as position-true grids (text-strategy keeps the empty cells,
    so columns are REAL — flat text drops the dashes and shifts
    positions, which is how a Mainland number landed in the Australia
    row). Identity anchors the row+column; the sibling matrix's same-
    labelled row serves the same column. Ambiguity serves nothing."""
    from .numerics import norm_label
    prior_docs = ledger.prior_period_docs()
    # candidate matrix pages: current-doc pages with wide rows
    cand_pages = {}
    for it in ledger.items:
        if it.doc in prior_docs or getattr(it, "disputed", False):
            continue
        if len(it.nums) >= 4:
            cand_pages.setdefault(it.doc, set()).add(it.page)
    grids = dict(_grids or {})
    if not grids:
        from pathlib import Path as _P
        from .islands import matrix_grids
        for d in docs:
            name = _P(d).name
            pages = sorted(cand_pages.get(name, []))[:24]
            if not pages:
                continue
            for pno, rows in matrix_grids(d, pages).items():
                grids[(name, pno)] = rows

    def _norm(x):
        return norm_label(str(x)).replace(" ", "")

    labelsets = {k: {_norm(lab) for lab, _v in rows} for k, rows in
                 grids.items()}
    out = {}
    for t in targets:
        pv = t.prior_value
        if (t.key in served or not isinstance(pv, (int, float))
                or abs(pv) < 1.0):
            continue
        tol = max(0.6, abs(pv) * 2e-5)
        hits = []
        for k, rows in grids.items():
            for lab, vals in rows:
                for j, v in enumerate(vals):
                    if v is not None and abs(abs(v) - abs(pv)) <= tol:
                        hits.append((k, lab, vals, j))
        if not hits or len(hits) > 6:
            continue
        # AGREEMENT law (the join's own rule): a prior printed in several
        # tables anchors several serves — accept when every resolvable
        # anchor serves the SAME current value; disagreement serves
        # nothing.
        serves = []
        for k0, lab0, vals0, pos in hits:
            best, bestn = None, 3
            for k in grids:
                if k == k0:
                    continue
                n0 = len(labelsets[k] & labelsets[k0])
                if n0 > bestn:
                    best, bestn = k, n0
            if best is None:
                continue
            cand = [vals for lab, vals in grids[best]
                    if _norm(lab) == _norm(lab0) and len(vals) > pos]
            if len(cand) != 1 or cand[0][pos] is None:
                continue
            serves.append((cand[0][pos], k0, lab0, pos, best))
        if not serves or len({round(x[0], 2) for x in serves}) != 1:
            continue
        cur, k0, lab0, pos, best = serves[0]
        if (pv < 0) != (cur < 0) and cur != 0:
            cur = -cur
        out[t.key] = {
            "value": round(cur, 4), "status": "OK", "conf": 3,
            "page": best[1], "line": lab0[:60],
            "note": (f"2D matrix join (grid-true): prior {pv:,.2f} "
                     f"anchors column {pos + 1} of '{lab0[:30]}' "
                     f"(p{k0[1]}); the sibling matrix serves the same "
                     f"column (p{best[1]}) — review the column meaning")}
    if out:
        log(f"[ops] 2D matrix join: {len(out)} rows served by "
            f"position-across (grade C, red)")
    return out


