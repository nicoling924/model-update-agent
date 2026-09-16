"""Test-prep — turn an already-updated model into a blind test + an answer key.

The other teams' models are updated through 1H26. To measure the update
agent on FY25 we need each model as it stood BEFORE its FY25 update: the
FY25 column back to being a FORECAST column, carrying the same formulas the
analyst used for FY26, with every FY25 actual hardcode gone. The untouched
original is then the answer key the run is scored against.

Three artefacts per model:
  <name>__TEST.xlsx   the blind model, FY25 de-actualised  (the agent's input)
  <name>__ANSWER.xlsx byte copy of the analyst's original  (the key)
  <name>__KEY.json    the FY25 column cell by cell: label, formula, value
  <name>__PREP.md     what changed, what was left, what needs a human ruling

Generic by construction: nothing here knows a company or a layout. Every
sheet's year axis is discovered from its own header rows, and the FY25
column is rebuilt from the FY26 column with each reference moved back one
period using THE REFERENCED SHEET'S OWN axis — the teams' layouts differ
sheet to sheet, so a uniform "shift one column left" is not safe.

    python tools/testprep.py scan  <model.xlsx> [--target 2025]
    python tools/testprep.py prep  <model.xlsx> [--target 2025] [--out DIR]
    python tools/testprep.py score <candidate.xlsx> <KEY.json>
"""
import argparse
import copy
import json
import re
import shutil
import sys
from pathlib import Path

import openpyxl

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from pipeline.discover import _year_of, period_tag          # noqa: E402
from pipeline.evaluator import Evaluator, col2n, n2col      # noqa: E402

SCAN_ROWS = 14          # evidence: a header block is the top of a sheet by definition


# ---------------------------------------------------------------- anatomy

def all_panels(ws, ws_v=None):
    """Every period panel on a sheet: [{tag, cols:{year:col_letter}}].

    A panel is an ascending run of same-tag year marks across columns. One
    mark per column, the text mark winning over a date (a column headed
    '2024-06-30' over '1H2024' is a half-year column, not an annual one).

    A ROLLED HEADER IS A FORMULA ('=AI2+1'): the mark is its VALUE, so the
    cached-value sheet is read first and the formula sheet only fills the
    blanks. Reading formulas alone finds no axis at all on a rolled model.
    """
    percol = {}
    for row in ws.iter_rows(min_row=1, max_row=min(SCAN_ROWS, ws.max_row)):
        for c in row:
            v = getattr(c, "value", None)
            if ws_v is not None and isinstance(v, str) and v.startswith("="):
                try:
                    v = ws_v[c.coordinate].value
                except Exception:
                    v = None
            y, _ = _year_of(v)
            if y is None or not getattr(c, "column", None):
                continue
            is_text = isinstance(v, str)
            cur = percol.get(c.column)
            if cur is None or (is_text and not cur[2]):
                percol[c.column] = (y, period_tag(v), is_text)
    marks = sorted((col, y, tag) for col, (y, tag, _t) in percol.items())
    panels = []
    for tag in sorted({m[2] for m in marks}):
        tm = [m for m in marks if m[2] == tag]
        run = [tm[0]]
        for prev, cur in zip(tm, tm[1:]):
            if cur[1] == prev[1] + 1 and cur[0] > prev[0]:
                run.append(cur)
            else:
                if len(run) >= 2:
                    panels.append((tag, run))
                run = [cur]
        if len(run) >= 2:
            panels.append((tag, run))
    return [{"tag": tag, "cols": {str(y): n2col(c) for c, y, _ in run}}
            for tag, run in panels]


def anatomy(wb, target, source, wb_v=None, only=None, skip=()):
    """Per sheet: its panels, the FY target/source columns, the back-map.

    `only`/`skip` withhold a sheet from the REBUILD only — its axis is still
    read, because a formula on a prepped sheet that points at it must still
    be moved back a period using that sheet's own columns."""
    out = {}
    for sh in wb.sheetnames:
        ws = wb[sh]
        wsv = wb_v[sh] if wb_v is not None and sh in wb_v.sheetnames else None
        pans = all_panels(ws, wsv)
        back = {}
        for p in pans:
            for y, col in p["cols"].items():
                prev = p["cols"].get(str(int(y) - 1))
                if prev:
                    back[col2n(col)] = col2n(prev)
        pairs = []
        rebuild = sh not in skip and (only is None or sh in only)
        for p in pans:
            if rebuild and p["tag"] == "FY" and str(target) in p["cols"] \
                    and str(source) in p["cols"]:
                pairs.append((p["cols"][str(target)], p["cols"][str(source)]))
        # the columns that ARE the source period, in every panel — an anchored
        # reference to one of these is the column's own period, not a fixed base
        src_cols = {col2n(p["cols"][str(source)]) for p in pans
                    if str(source) in p["cols"]}
        out[sh] = {"panels": pans, "back": back, "pairs": pairs,
                   "source_cols": src_cols,
                   "target_col": pairs[0][0] if pairs else None,
                   "source_col": pairs[0][1] if pairs else None,
                   "interim": [p for p in pans
                               if p["tag"] != "FY" and str(target) in p["cols"]]}
    return out


# ------------------------------------------------------- formula rewriting

_REF = re.compile(
    r"(?P<sheet>(?:'[^']*'|[A-Za-z0-9_.一-鿿＀-￯]+)\s*!)?"
    r"(?P<ac>\$?)(?P<col>[A-Z]{1,3})(?P<ar>\$?)(?P<row>\d+)"
    r"(?![0-9A-Za-z_(])")


# a whole-column range ('Fleet!AF:AF', '$B:$B') carries no row, so the cell
# pattern above never sees it — and a fleet or lookup column left un-moved
# points the rebuilt year at the wrong column
_COLRANGE = re.compile(
    r"(?P<sheet>(?:'[^']*'|[A-Za-z0-9_.\u4e00-\u9fff]+)\s*!)?"
    r"(?<![A-Z0-9$])(?P<d1>\$?)(?P<c1>[A-Z]{1,3}):(?P<d2>\$?)(?P<c2>[A-Z]{1,3})"
    r"(?![A-Z0-9])")


def _strip_sheet(q):
    s = q[:q.rindex("!")].strip()
    return s[1:-1] if s.startswith("'") else s


def rewrite(formula, own_sheet, ana, notes):
    """Move every reference back one period using the REFERENCED sheet's own
    year axis. A reference to a column that is not a period column stays put
    (an assumption column, a label column). $-anchored columns stay put too —
    Excel's own copy semantics — and are reported, because an anchor into a
    period column is a judgment call, not arithmetic."""
    # string literals are protected from the reference pattern
    parts = re.split(r'("[^"]*")', formula)
    res = []
    for part in parts:
        if part.startswith('"'):
            res.append(part)
            continue
        def sub(m):
            sheet = _strip_sheet(m.group("sheet")) if m.group("sheet") else own_sheet
            info = ana.get(sheet)
            if not info:
                return m.group(0)
            cn = col2n(m.group("col"))
            new = info["back"].get(cn)
            if new is None:
                if cn in {col2n(c) for p in info["panels"] for c in p["cols"].values()}:
                    notes.append(f"ref to {sheet}!{m.group('col')}{m.group('row')} "
                                 f"is the earliest period column — left as is")
                return m.group(0)
            if m.group("ac") == "$" and cn not in info["source_cols"]:
                # AN ANCHOR TO ANOTHER PERIOD IS A DELIBERATE BASE (a 2020
                # share count, a base-year price) and stays. An anchor to the
                # SOURCE period is the copied column's own period and moves
                # with it — Excel would keep it, but this is not a copy, it is
                # the same column re-dated, and keeping it points the rebuilt
                # FY column at next year's numbers.
                notes.append(f"$-anchored ref {sheet}!${m.group('col')}"
                             f"{m.group('ar')}{m.group('row')} is another period's "
                             f"base — left anchored")
                return m.group(0)
            if m.group("ac") == "$":
                notes.append(f"$-anchored ref {sheet}!${m.group('col')}"
                             f"{m.group('ar')}{m.group('row')} is the source "
                             f"period's own column — moved back with it")
            return (m.group("sheet") or "") + m.group("ac") + n2col(new) \
                + m.group("ar") + m.group("row")
        def subcol(m):
            sheet = _strip_sheet(m.group("sheet")) if m.group("sheet") else own_sheet
            info = ana.get(sheet)
            if not info:
                return m.group(0)
            a_, b_ = info["back"].get(col2n(m.group("c1"))), \
                info["back"].get(col2n(m.group("c2")))
            if a_ is None or b_ is None:
                return m.group(0)
            return (m.group("sheet") or "") + m.group("d1") + n2col(a_) + ":" \
                + m.group("d2") + n2col(b_)
        res.append(_COLRANGE.sub(subcol, _REF.sub(sub, part)))
    return "".join(res)


# ----------------------------------------------------------------- the prep

def _retag(src_h, dst_h, target, source):
    """The source header's mark, re-dated to the target year, keeping the
    author's data type (delivery law: a numeric header stays numeric, a date
    stays a date, text keeps its shape). None = leave the header alone."""
    if isinstance(src_h, str) and src_h.startswith("="):
        return None                     # self-dating header
    if _year_of(dst_h)[0] != target or _year_of(src_h)[0] != source:
        return None
    if isinstance(src_h, str):
        for a, b in ((str(source), str(target)),
                     (str(source)[2:], str(target)[2:])):
            if a in src_h:
                return src_h.replace(a, b)
        return None
    return dst_h                        # numeric / date header already correct


def prep_sheet(ws, sh, ana, blank_unforecast=False, retag=True,
               a_target=None, a_source=None):
    """Rebuild every target column on the sheet from its own source column.
    A sheet can carry more than one annual panel (a second projection block
    beside the main one); each is its own pair. -> list of record dicts."""
    out = []
    for tcol, scol in ana[sh]["pairs"]:
        rec = {"sheet": sh, "target_col": tcol, "source_col": scol,
               "changed": [], "kept_header": [], "source_blank": [],
               "notes": [], "blanked": []}
        for r in range(1, ws.max_row + 1):
            src, dst = ws[f"{scol}{r}"], ws[f"{tcol}{r}"]
            if type(src).__name__ == "MergedCell" or type(dst).__name__ == "MergedCell":
                continue
            v, old_v = src.value, dst.value
            if v is None:
                if old_v is not None:
                    rec["source_blank"].append([r, _label(ws, r), _short(old_v)])
                    if blank_unforecast:
                        dst.value = None
                        rec["blanked"].append(r)
                continue
            if r <= SCAN_ROWS and _year_of(v)[0] is not None:
                # A PERIOD MARK IS NEVER COPIED — that would put the source
                # year's label on the target column. But its STYLE of mark is
                # taken: '2026E' over '2025A' leaves '2025E', so the test model
                # does not announce which column is already an actual. A
                # formula header ('=AI2+1') re-dates itself and is left alone.
                new_h = _retag(v, old_v, a_target, a_source) if retag else None
                rec["kept_header"].append([r, _short(old_v), _short(new_h)])
                if new_h is not None and _differs(old_v, new_h):
                    dst.value = new_h
                continue
            notes = []
            new_v = (rewrite(v, sh, ana, notes)
                     if isinstance(v, str) and v.startswith("=") else v)
            dst.value = new_v
            dst._style = copy.copy(src._style)
            dst.number_format = src.number_format
            if dst.comment is not None:
                dst.comment = None    # an actual-year methodology note is an answer
            rec["changed"].append([r, _label(ws, r), _short(old_v), _short(new_v)])
            rec["notes"] += [f"{tcol}{r}: {n}" for n in notes]
        out.append(rec)
    return out


def clear_column(ws, ws_v, col):
    """Empty a column that has NO source column to be rebuilt from — the
    analyst's fleet block ends at the actual year, there is no next-year
    column to copy. The agent must roll the column itself. The column's own
    PERIOD MARK is kept, so the column is still identifiable as that year."""
    cleared = []
    for r in range(1, ws.max_row + 1):
        c = ws[f"{col}{r}"]
        if type(c).__name__ == "MergedCell" or c.value is None:
            continue
        v = c.value
        if isinstance(v, str) and v.startswith("="):
            v = ws_v[f"{col}{r}"].value
        if r <= SCAN_ROWS and _year_of(v)[0] is not None:
            continue
        cleared.append([r, _label(ws, r), _short(c.value)])
        c.value = None
    return cleared


def _label(ws, r):
    for lc in ("A", "B", "C", "D", "E"):
        v = ws[f"{lc}{r}"].value
        if isinstance(v, str) and v.strip():
            return v.strip()[:60]
    return ""


def _short(v):
    s = "" if v is None else str(v)
    return s[:80]


# ------------------------------------------------------------- answer key

def build_key(path, target, source, only=None, skip=(), clear=(), pairs=()):
    wbf = openpyxl.load_workbook(path, data_only=False)
    wbv = openpyxl.load_workbook(path, data_only=True)
    ana = anatomy(wbf, target, source, wbv, only, skip)
    add_pairs(ana, pairs)
    for spec in clear:                  # a cleared column's cells are answers too
        sheet, _, col = spec.rpartition("!")
        if sheet in ana:
            ana[sheet].setdefault("cleared", []).append(col.upper())
    key = {"source_file": Path(path).name, "target_year": target,
           "source_year": source, "sheets": {}}
    for sh, info in ana.items():
        if not info["pairs"] and not info.get("cleared"):
            continue
        ws, wv = wbf[sh], wbv[sh]
        cols = [t for t, _s in info["pairs"]] + list(info.get("cleared", []))
        cells = {}
        for col in cols:
            for r in range(1, ws.max_row + 1):
                c = ws[f"{col}{r}"]
                if type(c).__name__ == "MergedCell" or c.value is None:
                    continue
                if r <= SCAN_ROWS and _year_of(
                        wv[f"{col}{r}"].value if isinstance(c.value, str)
                        and c.value.startswith("=") else c.value)[0] is not None:
                    continue          # the period header is not an answer
                cached = wv[f"{col}{r}"].value
                is_f = isinstance(c.value, str) and c.value.startswith("=")
                cells[f"{col}{r}"] = {
                    "label": _label(ws, r),
                    "formula": c.value if is_f else None,
                    "value": cached if isinstance(cached, (int, float))
                    and not isinstance(cached, bool) else None,
                    "raw": None if is_f else _short(c.value)}
        key["sheets"][sh] = {"columns": cols, "cells": cells}
    stale = sum(1 for b in key["sheets"].values() for c in b["cells"].values()
                if c["value"] is None and c["raw"] is None)
    key["cells_without_cached_value"] = stale
    return key, ana


# ----------------------------------------------------------------- commands

def cmd_scan(a):
    wb = openpyxl.load_workbook(a.model, data_only=False)
    wbv = openpyxl.load_workbook(a.model, data_only=True)
    ana = anatomy(wb, a.target, a.source, wbv, a.only_sheets, a.skip_sheets)
    add_pairs(ana, a.pairs)
    print(f"{Path(a.model).name}   target FY{a.target}  <- source FY{a.source}")
    ready = 0
    for sh, info in ana.items():
        ws = wb[sh]
        pans = ", ".join(f"{p['tag']}[{min(p['cols'])}-{max(p['cols'])}]"
                         f"@{p['cols'][min(p['cols'])]}..{p['cols'][max(p['cols'])]}"
                         for p in info["panels"]) or "no period axis"
        mark = "OK " if info["pairs"] else "-- "
        print(f"{mark}{sh:<28} rows={ws.max_row:<5} {pans}")
        if info["pairs"]:
            ready += 1
            for tcol, scol in info["pairs"]:
                print(f"      FY{a.target}={tcol}  FY{a.source}={scol}  "
                      f"FY{a.target} column: {_census(ws, tcol)}")
        for p in info["interim"]:
            cols = ", ".join(f"{y}:{c}" for y, c in sorted(p["cols"].items()))
            print(f"      !! {p['tag']} panel holds FY{a.target} -> {cols} "
                  f"(interim actuals can leak the answer — rule needed)")
    print(f"\n{ready}/{len(ana)} sheets preppable.")


def _census(ws, col):
    f = h = 0
    for r in range(1, ws.max_row + 1):
        c = ws[f"{col}{r}"]
        if type(c).__name__ == "MergedCell" or c.value is None:
            continue
        if isinstance(c.value, str) and c.value.startswith("="):
            f += 1
        elif isinstance(c.value, (int, float)) and not isinstance(c.value, bool):
            h += 1
    return f"{h} hardcode / {f} formula"


def cmd_prep(a):
    src = Path(a.model)
    out = Path(a.out or src.parent / "test-prep")
    out.mkdir(parents=True, exist_ok=True)
    stem = src.stem
    answer = out / f"{stem}__ANSWER{src.suffix}"
    test = out / f"{stem}__TEST{src.suffix}"
    shutil.copy2(src, answer)

    key, _ = build_key(src, a.target, a.source, a.only_sheets, a.skip_sheets,
                       a.clear_cols, a.pairs)
    (out / f"{stem}__KEY.json").write_text(json.dumps(key, indent=1, default=str))

    wb = openpyxl.load_workbook(src, data_only=False,
                                keep_vba=src.suffix.lower() == ".xlsm")
    wbv = openpyxl.load_workbook(src, data_only=True)
    ana = anatomy(wb, a.target, a.source, wbv, a.only_sheets, a.skip_sheets)
    add_pairs(ana, a.pairs)
    recs = [r for sh, info in ana.items() if info["pairs"]
            for r in prep_sheet(wb[sh], sh, ana, a.blank_unforecast,
                                not a.keep_header_tag, a.target, a.source)]
    cleared = {}
    for spec in a.clear_cols:
        sheet, _, col = spec.rpartition("!")
        if sheet not in wb.sheetnames:
            raise SystemExit(f"--clear-cols: no sheet named {sheet!r}")
        cleared[spec] = clear_column(wb[sheet], wbv[sheet], col.upper())
        ana[sheet].setdefault("cleared", []).append(col.upper())
    wb.save(test)

    report = _report(src, test, answer, key, ana, recs, a, cleared)
    (out / f"{stem}__PREP.md").write_text(report)
    rebuilt = sum(len(r["changed"]) for r in recs)
    print(f"{src.name}: FY{a.target} rebuilt from FY{a.source} — "
          f"{rebuilt} cells on {len({r['sheet'] for r in recs})} sheet(s), "
          f"{sum(len(v) for v in (cleared or {}).values())} cleared, "
          f"{len(key['sheets'])} sheets in the key")
    print(f"written to {out}   (report: {stem}__PREP.md)")


def _report(src, test, answer, key, ana, recs, a, cleared=None):
    L = [f"# Test prep — {src.name}", "",
         f"- target period: FY{a.target} (de-actualised, becomes a forecast column)",
         f"- source period: FY{a.source} (its column is the template)",
         f"- test model:   `{test.name}`",
         f"- answer key:   `{answer.name}` + `{src.stem}__KEY.json`", "",
         "## Sheets prepped", "",
         "| sheet | FY{} | FY{} | cells rebuilt | left (source blank) | headers kept |"
         .format(a.target, a.source),
         "|---|---|---|---|---|---|"]
    for r in recs:
        L.append(f"| {r['sheet']} | {r['target_col']} | {r['source_col']} | "
                 f"{len(r['changed'])} | {len(r['source_blank'])} | "
                 f"{len(r['kept_header'])} |")
    for spec, rows in (cleared or {}).items():
        L += ["", f"## Column `{spec}` CLEARED — no FY{a.source} column exists "
              "to rebuild it from", "",
              f"{len(rows)} cell(s) emptied; the period mark is kept. The agent "
              "must roll this column forward itself.", ""]
        L += ["| row | label | was |", "|---|---|---|"]
        L += [f"| {r} | {lab} | {val} |" for r, lab, val in rows[:10]]
        if len(rows) > 10:
            L.append(f"| … | | {len(rows)-10} more |")
    skipped = [sh for sh, i in ana.items() if not i["pairs"]]
    if skipped:
        L += ["", "## Sheets NOT prepped (no FY{}+FY{} pair found)".format(a.target, a.source),
              "", ", ".join(f"`{s}`" for s in skipped)]
    interim = [(sh, p) for sh, i in ana.items() for p in i["interim"]]
    if interim:
        L += ["", "## ⚠ Interim panels holding FY{} — needs a ruling".format(a.target), "",
              "The FY column can be a sum of these; if they still hold actuals the "
              "answer leaks through them.", ""]
        for sh, p in interim:
            L.append(f"- `{sh}` {p['tag']}: " +
                     ", ".join(f"{y}->{c}" for y, c in sorted(p["cols"].items())))
    blanks = [(r["sheet"], x) for r in recs for x in r["source_blank"]]
    if blanks:
        L += ["", "## Rows left as-is (FY{} blank, FY{} not) — possible answer leak"
              .format(a.source, a.target), "",
              "| sheet | row | label | FY{} value kept |".format(a.target),
              "|---|---|---|---|"]
        for sh, (row, lab, val) in blanks[:12]:
            L.append(f"| {sh} | {row} | {lab} | {val} |")
        if len(blanks) > 12:
            L.append(f"| … | | | {len(blanks)-12} more |")
        L.append("")
        L.append("Re-run with `--blank-unforecast` to clear them.")
    notes = [(r["sheet"], n) for r in recs for n in r["notes"]]
    if notes:
        seen, uniq = set(), []
        for sh, n in notes:
            k = (sh, n.split(":", 1)[1])
            if k not in seen:
                seen.add(k)
                uniq.append((sh, n))
        L += ["", "## Reference rulings made while rewriting formulas", ""]
        L += [f"- `{sh}` {n}" for sh, n in uniq[:60]]
        if len(uniq) > 60:
            L.append(f"- … {len(uniq)-60} more")
    if getattr(a, "verify", False):
        L += ["", "## Integrity of the prepped model", ""] + _verify(test, src, ana, a)
    else:
        L += ["", "_Integrity pass skipped (`--verify` to run it)._"]
    return "\n".join(L)


def zero_identities(ws_f, ws_v, fwd_cols):
    """Rows the model itself proves are identities AT THE TARGET YEAR, read
    from the FORECAST columns — the ones the rebuilt column is a copy of.

    The evidence is two things together: the formula SUBTRACTS (an identity
    is a difference) and its saved value is zero, in at least two forecast
    years. Read across thirty years of history instead and any row that is
    merely nil for a long stretch (CLP 'Fuel clause account', a carry-forward
    chain at zero) reads as a check and every legitimate change reads as a
    break.
    """
    out = []
    if len(fwd_cols) < 2:
        return out
    for r in range(1, ws_f.max_row + 1):
        z = n = 0
        for col in fwd_cols:
            f = ws_f[f"{col}{r}"].value
            if not (isinstance(f, str) and f.startswith("=") and "-" in f[1:]):
                continue
            n += 1
            v = ws_v[f"{col}{r}"].value
            if isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) <= 0.01:
                z += 1
        if z >= 2 and z == n:
            out.append(r)
    return out


def _differs(a_, b_):
    """Equal, with float round-trip noise forgiven: openpyxl re-prints a
    stored double at full precision and the 17th digit moves."""
    num = (int, float)
    if isinstance(a_, num) and isinstance(b_, num) \
            and not isinstance(a_, bool) and not isinstance(b_, bool):
        return abs(a_ - b_) > max(abs(a_), abs(b_), 1e-30) * 1e-12
    return a_ != b_


def _verify(test, orig, ana, a):
    """Two proofs. (1) NOTHING OUTSIDE THE TARGET COLUMNS MOVED — a test model
    that differs from the analyst's anywhere else is not the same model, and
    the score would be measuring the prep. (2) The model's own zero identities
    still hold in the de-actualised year — if a balance row is no longer zero,
    the rebuilt column is wrong."""
    wbt = openpyxl.load_workbook(test, data_only=False)
    wbo = openpyxl.load_workbook(orig, data_only=False)
    wbv = openpyxl.load_workbook(orig, data_only=True)
    out, bad = [], 0

    clob = []
    for sh in wbo.sheetnames:
        if sh not in wbt.sheetnames:
            out.append(f"- ❌ sheet `{sh}` lost by the prep")
            bad += 1
            continue
        tcols = {t for t, _s in ana.get(sh, {}).get("pairs", [])} \
            | set(ana.get(sh, {}).get("cleared", []))
        wo, wt = wbo[sh], wbt[sh]
        for row in wo.iter_rows(min_row=1, max_row=wo.max_row):
            for c in row:
                if type(c).__name__ == "MergedCell" or c.column_letter in tcols:
                    continue
                if _differs(c.value, wt.cell(c.row, c.column).value):
                    clob.append(f"{sh}!{c.coordinate}")
    if clob:
        bad += 1
        out.append(f"- ❌ {len(clob)} cell(s) changed OUTSIDE the target columns: "
                   + ", ".join(f"`{x}`" for x in clob[:15])
                   + (" …" if len(clob) > 15 else ""))
    else:
        out.append("- ✅ no cell outside the target columns changed")

    refs = [f"{sh}!{t}{r}"
            for sh, info in ana.items() for t, _s in info["pairs"]
            for r in range(1, wbt[sh].max_row + 1)
            if isinstance(wbt[sh][f"{t}{r}"].value, str)
            and "#REF!" in wbt[sh][f"{t}{r}"].value]
    if refs:
        bad += 1
        out.append(f"- ❌ {len(refs)} #REF! introduced: " + ", ".join(f"`{x}`" for x in refs[:10]))
    else:
        out.append("- ✅ no #REF! in the rebuilt columns")

    evt = Evaluator(wbt)
    ident = broke = 0
    detail = []
    for sh, info in ana.items():
        if not info["pairs"]:
            continue
        for p in info["panels"]:
            if p["tag"] != "FY" or str(a.target) not in p["cols"]:
                continue
            tcol = p["cols"][str(a.target)]
            fwd = [c for y, c in p["cols"].items() if int(y) > a.target]
            for r in zero_identities(wbo[sh], wbv[sh], fwd):
                coord = f"{tcol}{r}"
                ident += 1
                try:
                    v = evt.cell(sh, coord)
                except Exception as e:
                    detail.append(f"- ⚠ `{sh}!{coord}` identity not evaluable here ({e})")
                    continue
                if isinstance(v, (int, float)) and abs(v) > 0.5:
                    broke += 1
                    detail.append(f"- ❌ `{sh}!{coord}` ({_label(wbo[sh], r)}) = "
                                  f"{v:,.1f}, was 0 — the rebuilt column broke an identity")
    if broke:
        bad += 1
    out.append(f"- {'❌' if broke else '✅'} {ident - broke}/{ident} of the model's own "
               f"zero identities still hold in the rebuilt FY{a.target} column")
    out += detail[:20]
    if evt.cycles:
        out.append(f"- ⚠ {len(set(evt.cycles))} circular reference(s) hit while checking "
                   "(normal in models with an interest/cash circularity)")
    out.append("")
    out.append(f"**{'FAIL — ' + str(bad) + ' problem class(es)' if bad else 'PASS'}**")
    return out


def cmd_score(a):
    """Score a candidate against the key: the analyst's own FY-target numbers
    are the truth, and a formula cell is judged on its VALUE — how the number
    was written is the agent's business, what it is is the analyst's."""
    key = json.loads(Path(a.key).read_text())
    target = key["target_year"]
    wbf = openpyxl.load_workbook(a.candidate, data_only=False)
    wbv = openpyxl.load_workbook(a.candidate, data_only=True)
    ev = Evaluator(wbf)
    tot = ok = miss = 0
    wrong = []
    per_sheet = {}
    for sh, blk in key["sheets"].items():
        if sh not in wbf.sheetnames:
            print(f"  ! sheet {sh} missing from the candidate")
            continue
        for coord, exp in blk["cells"].items():
            if exp["value"] is None:
                continue
            tot += 1
            st = per_sheet.setdefault(sh, [0, 0])
            st[1] += 1
            got = wbv[sh][coord].value
            if not isinstance(got, (int, float)) or isinstance(got, bool):
                try:
                    got = ev.cell(sh, coord)
                except Exception:
                    got = None
            if not isinstance(got, (int, float)) or isinstance(got, bool):
                miss += 1
                wrong.append((sh, coord, exp["label"], exp["value"], got))
                continue
            e = exp["value"]
            if abs(got - e) <= max(abs(e) * a.tol, a.abs_tol):
                ok += 1
                st[0] += 1
            else:
                wrong.append((sh, coord, exp["label"], e, got))
    if not tot:
        print("nothing to score — the key holds no numeric cells")
        return
    print(f"FY{target}: {ok}/{tot} = {ok/tot:.1%} within {a.tol:.2%}"
          f"   (unevaluable: {miss})")
    for sh, (o, t) in sorted(per_sheet.items()):
        print(f"  {sh:<24} {o}/{t}")
    print()
    for sh, coord, lab, e, g in wrong[:a.show]:
        ge = f"{g:,.2f}" if isinstance(g, (int, float)) else str(g)
        print(f"  {sh}!{coord:<6} {lab[:38]:<38} want {e:>16,.2f}  got {ge:>16}")
    if len(wrong) > a.show:
        print(f"  … {len(wrong)-a.show} more")


def add_pairs(ana, specs):
    """Explicit column pairs, 'Sheet!TARGET<-SOURCE'. A quarterly reporter
    books the year in its 4Q column, not the annual one — the annual column is
    a sum — so the column to re-forecast is not always the one the FY axis
    names."""
    for spec in specs:
        sheet, _, cols = spec.rpartition("!")
        tgt, _, src = cols.partition("<-")
        if sheet not in ana:
            raise SystemExit(f"--pairs: no sheet named {sheet!r}")
        ana[sheet]["pairs"].append((tgt.strip().upper(), src.strip().upper()))


def _csv(v):
    return tuple(x.strip() for x in v.split(",") if x.strip())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("scan", cmd_scan), ("prep", cmd_prep)):
        p = sub.add_parser(name)
        p.add_argument("model")
        p.add_argument("--target", type=int, default=2025)
        p.add_argument("--source", type=int, default=None)
        p.add_argument("--only-sheets", type=_csv, default=None,
                       help="rebuild only these sheets (comma separated)")
        p.add_argument("--skip-sheets", type=_csv, default=(),
                       help="never rebuild these sheets")
        if name == "prep":
            p.add_argument("--out")
            p.add_argument("--pairs", type=_csv, default=(),
                           help="extra column pairs, 'Sheet!TARGET<-SOURCE' "
                                "(e.g. a 4Q column rebuilt from next year's 4Q)")
            p.add_argument("--verify", action="store_true",
                           help="prove nothing outside the target columns moved "
                                "and the model's identities still hold (slow: it "
                                "walks every cell of the workbook)")
            p.add_argument("--clear-cols", type=_csv, default=(),
                           help="empty these columns outright, e.g. 'Fleet!AD' "
                                "(for a block with no next-year column to copy)")
            p.add_argument("--keep-header-tag", action="store_true",
                           help="leave the target header as it is (default: "
                                "re-tag '2025A' to the source's style, '2025E')")
            p.add_argument("--blank-unforecast", action="store_true",
                           help="clear target-year cells whose source-year cell is blank")
        p.set_defaults(fn=fn)
    p = sub.add_parser("score")
    p.add_argument("candidate")
    p.add_argument("key")
    p.add_argument("--tol", type=float, default=0.005)
    p.add_argument("--abs-tol", type=float, default=0.01)
    p.add_argument("--show", type=int, default=40)
    p.set_defaults(fn=cmd_score)
    a = ap.parse_args()
    if getattr(a, "source", None) is None and hasattr(a, "target"):
        a.source = a.target + 1
    a.fn(a)


if __name__ == "__main__":
    main()
