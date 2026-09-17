"""Stage 4a — the deterministic verify web: the scorecard the loop lives on.

Everything here is pure measurement — no writes, no LLM, no repair. The
objective loop (orchestrator) reads this scorecard to decide its next move;
the delivery gate reads it to decide whether the run may deliver at all.

Generic: what counts as a check row, a key number, or a year column comes
from the run spec (built from the workbook's own _SPEC tab per company) —
code knows only cells, priors, and arithmetic.
"""
from .evaluator import Evaluator

CHECK_TOL = 0.5      # a check row's world is zero; half a unit absorbs the model's own display rounding (0.03 refused a closed run, 2026-09-15); the gate, the ending and the ladder all read this one


def year_columns(spec, sheet):
    return (spec.get("year_axis") or {}).get(sheet, {}).get("columns") or {}


def prior_column(spec, sheet, target_year):
    cols = year_columns(spec, sheet)
    years = sorted(cols)
    ty = str(target_year)
    if ty not in years or years.index(ty) == 0:
        return None
    return cols[years[years.index(ty) - 1]]


def forecast_columns(spec, sheet, target_year):
    cols = year_columns(spec, sheet)
    return [cols[y] for y in sorted(cols) if y > str(target_year)]


def scorecard(wb, spec, target_year, served=None, flags=None):
    """The live state of the model, measured. -> dict.

    - checks: every spec check row, every year column (balance, cash tie,
      RE roll, segment sums — whatever the model itself checks).
    - keys: the spec's key rows (revenue, profit, CA/NCA, liabilities,
      equity, CFO/CFI/CFF...) with value, provenance and flag state.
    - completion: filled cells in the target column vs the prior actual
      column, per sheet and overall.
    - cycles: circular references the evaluator hit.
    """
    served = served or {}
    flags = set(flags or ())
    ev = Evaluator(wb)
    out = {"checks": [], "keys": [], "completion": {}, "cycles": [],
           "eval_errors": []}

    for c in spec.get("check_rows") or []:
        sheet, row = c["sheet"], int(c["row"])
        expect = float(c.get("expect", 0))
        for year, col in sorted(year_columns(spec, sheet).items()):
            name = f"{sheet}!r{row} ({year})"
            try:
                got = ev.cell(sheet, f"{col}{row}")
            except Exception as e:
                out["eval_errors"].append(f"{name}: {e}")
                out["checks"].append({"name": name, "year": year, "got": None,
                                      "expect": expect, "status": "EVAL_ERROR"})
                continue
            ok = isinstance(got, (int, float)) and abs(got - expect) <= CHECK_TOL
            out["checks"].append({"name": name, "year": year,
                                  "got": got if isinstance(got, (int, float)) else None,
                                  "expect": expect,
                                  "status": "PASS" if ok else "FAIL"})

    # THE SYNTHETIC BALANCE CHECK (owner/reviewer 2026-09-17, the CX cold model:
    # it shipped 1,787 out of balance and NOTHING measured it, because the book
    # declares no check row of its own). Objective 1 must exist on EVERY model:
    # when the anatomy names the two total rows, code measures their difference
    # itself. It is said on the report as the run's own check, never as one the
    # analyst wrote.
    for cp in spec.get("check_pairs") or []:
        sheet = cp.get("sheet")
        # BUILT FROM WHATEVER TOTAL ROWS THE MODEL HAS (reviewer 2026-09-17):
        # not every book prints "total liabilities and equity" — CX does not —
        # so the objective is assets less liabilities less equity less any
        # separately-stated non-controlling interests, over the rows the anatomy
        # could name. `plus`/`minus` are lists of {sheet, row}; a_row/b_row
        # remain readable as the two-term form.
        plus = list(cp.get("plus") or ([{"sheet": sheet, "row": int(cp["a_row"])}] if cp.get("a_row") else []))
        minus = list(cp.get("minus") or ([{"sheet": cp.get("b_sheet") or sheet, "row": int(cp["b_row"])}]
                                         if cp.get("b_row") else []))
        if not plus or not minus:
            continue
        # the workbook's own cached results ride on the WORKBOOK, never in the
        # spec: the spec is written out as JSON (the _SPEC tab, the decisions
        # dump) and a Workbook in it kills the whole run at save time
        vwb = getattr(wb, "_values_wb", None)

        def _side(terms, year):
            tot = 0.0
            for t in terms:
                sh_t = t.get("sheet") or sheet
                col_t = year_columns(spec, sh_t).get(year)
                if not col_t:
                    raise KeyError(f"{sh_t} has no column for {year}")
                try:
                    v = ev.cell(sh_t, f"{col_t}{int(t['row'])}")
                except Exception:      # noqa: BLE001
                    v = None
                if not isinstance(v, (int, float)) and vwb is not None:
                    # CODE'S LIMITATION IS NOT THE MODEL'S FAULT: what Excel last
                    # computed stands where this evaluator cannot (the CX rows
                    # chain into AVERAGEIFS and full-column references)
                    try:
                        c = vwb[sh_t][f"{col_t}{int(t['row'])}"].value
                        v = c if isinstance(c, (int, float)) and not isinstance(c, bool) else v
                    except Exception:  # noqa: BLE001
                        pass
                if not isinstance(v, (int, float)):
                    raise TypeError(f"{sh_t}!{col_t}{t['row']} does not compute here")
                tot += float(v)
            return tot
        shown = (" + ".join(f"r{t['row']}" for t in plus) + " − "
                 + " − ".join(f"r{t['row']}" for t in minus))
        for year, col in sorted(year_columns(spec, sheet).items()):
            name = f"{cp.get('name') or 'balance'} [run's own] {sheet}!{shown} ({year})"
            try:
                got = _side(plus, year) - _side(minus, year)
            except Exception as e:  # noqa: BLE001
                out["eval_errors"].append(f"{name}: {e}")
                out["checks"].append({"name": name, "year": year, "got": None,
                                      "expect": 0.0, "status": "EVAL_ERROR"})
                continue
            ok = abs(got) <= CHECK_TOL
            out["checks"].append({"name": name, "year": year, "got": got,
                                  "expect": 0.0, "status": "PASS" if ok else "FAIL"})

    tcol_by_sheet = {sh: year_columns(spec, sh).get(str(target_year))
                     for sh in (spec.get("year_axis") or {})}
    for k in spec.get("key_rows") or []:
        sheet, row = k["sheet"], int(k["row"])
        tcol = tcol_by_sheet.get(sheet)
        if not tcol:
            continue
        coord = f"{tcol}{row}"
        try:
            val = ev.cell(sheet, coord)
        except Exception:
            val = None
        entry = served.get((sheet, row)) or {}
        out["keys"].append({
            "name": k.get("name", f"{sheet}!{row}"), "cell": f"{sheet}!{coord}",
            "value": val if isinstance(val, (int, float)) else None,
            "present": isinstance(val, (int, float)),
            "proven": int(entry.get("conf") or 0) >= 4,
            "flagged": f"{sheet}!{coord}" in flags})

    total_t = total_p = 0
    for sheet, tcol in tcol_by_sheet.items():
        if not tcol or sheet not in wb.sheetnames:
            continue
        pcol = prior_column(spec, sheet, target_year)
        ws = wb[sheet]
        n_t = sum(1 for r in range(1, ws.max_row + 1)
                  if ws[f"{tcol}{r}"].value is not None)
        n_p = (sum(1 for r in range(1, ws.max_row + 1)
                   if ws[f"{pcol}{r}"].value is not None) if pcol else 0)
        out["completion"][sheet] = {"target": n_t, "prior": n_p,
                                    "pct": round(100.0 * n_t / n_p, 1) if n_p else None}
        total_t += n_t
        total_p += n_p
    out["completion"]["_overall_pct"] = (round(100.0 * total_t / total_p, 1)
                                         if total_p else None)
    out["cycles"] = sorted(set(ev.cycles))
    return out


def summarize(card, target_year, flags=None, spec=None, wb=None):
    """One-screen scorecard text for the objective loop's state block."""
    lines = []
    # the FLAG BUDGET is a delivery-gate objective — the loop must SEE it:
    # >15% of a sheet's filled target-column cells flagged = the run FAILS
    # that sheet. Clearing a stale flag = set_input with a cited disclosed
    # value (which unflags), or confirming the line is absent (flag stays,
    # honestly).
    if flags and spec and wb is not None:
        per_sheet = {}
        for ref in flags:
            per_sheet[ref.split("!", 1)[0]] = per_sheet.get(ref.split("!", 1)[0], 0) + 1
        for sheet, nf in sorted(per_sheet.items()):
            tcol = year_columns(spec, sheet).get(str(target_year))
            if not tcol or sheet not in wb.sheetnames:
                continue
            ws = wb[sheet]
            filled = sum(1 for r in range(1, ws.max_row + 1)
                         if ws[f"{tcol}{r}"].value is not None)
            pct = nf / filled if filled else 0
            lines.append(f"FLAG BUDGET {sheet}: {nf}/{filled} flagged "
                         f"({pct:.0%}) — {'FAILING (>15%)' if pct > 0.15 else 'ok'}")
    fails = [c for c in card["checks"] if c["status"] == "FAIL"]
    errs = [c for c in card["checks"] if c["status"] == "EVAL_ERROR"]
    ty = str(target_year)
    ty_fails = [c for c in fails if c["year"] == ty]
    fc_fails = [c for c in fails if c["year"] != ty]
    lines.append(f"BALANCE/CHECK ROWS: {len(ty_fails)} FAIL in {ty}, "
                 f"{len(fc_fails)} in forecast years — ALL are yours "
                 f"(balance is required for EVERY year). Forecast gaps: "
                 f"attribute each BS movement to a designed CF input row "
                 f"with place_flow; the plug is a LAST resort. "
                 f"{len(errs)} eval-error")
    for c in ty_fails[:12]:
        lines.append(f"  FAIL {c['name']}: {c['got']:,.2f} vs {c['expect']:,.2f}"
                     if isinstance(c["got"], (int, float)) else f"  FAIL {c['name']}")
    for c in fc_fails[:6]:
        lines.append(f"  FAIL {c['name']}: "
                     + (f"{c['got']:,.0f} vs {c['expect']:,.0f}"
                        if isinstance(c["got"], (int, float)) else "n/a")
                     + "  (once the ACTUAL year ties, the delivery plug "
                       "closes this — attribute what you can inside the "
                       "window; plugs stay WITHHELD while the actual year "
                       "is off)")
    if not ty_fails and flags:
        reds = []
        if wb is not None:
            for ref in flags:
                sh, _, coord = str(ref).partition("!")
                try:
                    rgb = wb[sh][coord].fill.start_color.rgb
                except Exception:
                    rgb = ""
                if isinstance(rgb, str) and rgb.upper().endswith("FFC7CE"):
                    reds.append(ref)
        if reds:
            lines.append(
                f"YOUR CHECKS ALL PASS. THE WORK QUEUE IS NOW THE "
                f"{len(reds)} RED (stale/unproven) CELLS — clear them with "
                f"find_line + set_input under the evidence law, most "
                f"material first:")
            for ref in reds[:15]:
                lines.append(f"  RED {ref}")
    for k in card["keys"]:
        state = ("PROVEN" if k["proven"] else
                 "flagged" if k["flagged"] else
                 "present-unproven" if k["present"] else "MISSING")
        v = f"{k['value']:,.2f}" if isinstance(k["value"], (int, float)) else "—"
        lines.append(f"  KEY {k['name']} [{k['cell']}] = {v} ({state})")
    comp = card["completion"].get("_overall_pct")
    lines.append(f"COMPLETION: {comp}% of prior-column cells filled"
                 if comp is not None else "COMPLETION: n/a")
    if card["cycles"]:
        lines.append(f"CYCLES: {len(card['cycles'])} circular refs, e.g. "
                     f"{card['cycles'][:3]}")
    return "\n".join(lines)
