"""PRACTICE ON PAST RUNS (owner 2026-09-10): replay the investigator, dry,
over past delivered CLP workbooks against the analyst's pre-update model —
which headline lines it would flag, where each swing traces to, and what
it would call the swing factor. No cell is written.
    python3 tools/investigate_past.py <company_dir> <PERIOD> <YEAR> <artifact_dir>...
"""
import glob, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from openpyxl import load_workbook as load
from pipeline import spec as spec_mod
from pipeline.sensecheck import headline_deltas, suspicious
from pipeline.investigate import trace, unusual_by_history


def main(argv):
    company, period, year = argv[0], argv[1], int(argv[2])
    cd = Path(company)
    pre = load(sorted(cd.glob("model-archive/*_pre.xlsx"))[-1])
    for art in argv[3:]:
        models = glob.glob(art + "/**/model/*(pipeline).xlsx", recursive=True)
        krs = glob.glob(art + f"/**/replay/{period}/key_rows.json", recursive=True)
        provs = glob.glob(art + f"/**/replay/{period}/provenance.json", recursive=True)
        if not models or not krs:
            continue
        wb = load(models[0]); spec = spec_mod.load(cd, wb); spec_mod.extend_axis(spec, year)
        kr = json.load(open(krs[0])); spec["key_rows"] = kr if isinstance(kr, list) else kr.get("key_rows", kr)
        prov = json.load(open(provs[0])) if provs else {}
        print(f"=== {Path(art).name} ({Path(models[0]).name})")
        for d in suspicious(headline_deltas(wb, pre, spec, year)):
            sh1, c1 = d["ref1"].split("!")
            trail, leaf = trace(wb, pre, sh1, c1)
            path = " → ".join(f"{t[2] or t[1]}({t[3]*100:.0f}%)" for t in trail)
            if leaf is None:
                print(f"  {d['name']:22} {d['d0']*100:+6.1f}% / {d['d1']*100:+6.1f}%  spread: {path}")
                continue
            sh, coord = leaf; r = int(re.sub(r"[A-Z]", "", coord))
            rgb = str(wb[sh][coord].fill.fgColor.rgb or "")[-6:]
            colour = "RED" if rgb == "FFC7CE" else "ORANGE" if rgb == "FFC000" else "plain"
            e = prov.get(f"{sh}!{r}") or {}
            un, mv, band = unusual_by_history(wb, spec, sh, r, year)
            print(f"  {d['name']:22} {d['d0']*100:+6.1f}% / {d['d1']*100:+6.1f}%  {path} → {sh}!{coord} [{colour}] "
                  f"{str(wb[sh].cell(r,1).value)[:24]!r} = {wb[sh][coord].value!r:.40} "
                  f"{'UNUSUAL' if un else 'within history'} src={str(e.get('note') or e.get('line'))[:50]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
