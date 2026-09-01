"""Stage 4a — the deterministic verify web: the scorecard the loop lives on.

Everything here is pure measurement — no writes, no LLM, no repair. The
objective loop (orchestrator) reads this scorecard to decide its next move;
the delivery gate reads it to decide whether the run may deliver at all.

Generic: what counts as a check row, a key number, or a year column comes
from the run spec (built from the workbook's own _SPEC tab per company) —
code knows only cells, priors, and arithmetic.
"""
from .evaluator import Evaluator

CHECK_TOL = 0.01     # a check row's world is zero; 0.01 absorbs display rounding


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
