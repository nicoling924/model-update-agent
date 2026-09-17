"""Run from a workbook and disclosures only, in a new empty working directory.

The source company directory is never updated. Specs, replay outputs, learned
tabs and cross-run caches are not inputs. Results and the input manifest are
exported separately, including when the child process is interrupted.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

REPO = Path(__file__).resolve().parents[1]


def prepare(company, period, destination):
    company, destination = Path(company).resolve(), Path(destination).resolve()
    if not period or Path(period).name != period:
        raise ValueError("Period must be a single directory name")
    models = [p for p in (company / "model").iterdir()
              if p.suffix.lower() in (".xlsx", ".xlsm") and not p.name.startswith("~$")]
    if len(models) != 1:
        raise ValueError("Cold input must contain exactly one original workbook")
    with zipfile.ZipFile(models[0]) as archive:
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        names = [n.attrib["name"] for n in root.findall(".//{*}sheet")]
    if any(n.upper() in ("_SPEC", "_REPORT") for n in names):
        raise ValueError("Cold input contains agent knowledge/report tabs; supply its original workbook")
    disclosures = sorted((company / "disclosures" / period).rglob("*.pdf"))
    if not disclosures:
        raise ValueError("No attached disclosures for this period")
    destination.mkdir(parents=True, exist_ok=False)
    inputs = [(models[0], Path("model") / models[0].name)]
    inputs += [(p, Path("disclosures") / period / p.relative_to(company / "disclosures" / period))
               for p in disclosures]
    manifest = {"mode": "cold", "period": period, "source_company": str(company),
                "inputs": [], "prior_context": [],
                "contract": "Only original workbook and attached PDFs; no sidecar specs, learned tabs, replay data or prior caches"}
    for source, relative in inputs:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Input copy differs: {relative}")
        manifest["inputs"].append({"path": str(relative), "sha256": digest})
    return manifest


def export(work, company, output):
    output.mkdir(parents=True, exist_ok=True)
    for name in ("model", "model-archive", "updates", "replay"):
        source = company / name
        if source.exists():
            shutil.copytree(source, output / name, dirs_exist_ok=True)
    source = work / ".cache" / "pipeline-vision"
    if source.exists():
        shutil.copytree(source, output / "extraction", dirs_exist_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("company")
    parser.add_argument("period")
    parser.add_argument("year", type=int)
    parser.add_argument("--budget", type=int, default=90)
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args(argv)
    company = Path(args.company).resolve()
    output = REPO / "cold_out" / f"{company.name}-{args.period}"
    if output.exists():
        raise ValueError("Cold output already exists; use a fresh checkout/run")
    scratch = REPO / ".cold_work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="model-cold-", dir=scratch) as temp:
        work = Path(temp)
        staged = work / "input"
        manifest = prepare(company, args.period, staged)
        manifest["working_directory_initially_empty"] = not (work / ".cache").exists()
        manifest["source_revision"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
        output.mkdir(parents=True)
        (output / "cold-inputs.json").write_text(json.dumps(manifest, indent=2))
        print("[cold] " + json.dumps(manifest), flush=True)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO)
        cmd = [sys.executable, "-m", "pipeline.cli", str(staged), args.period,
               str(args.year), f"--budget={args.budget}"]
        if args.dry:
            cmd.append("--dry")
        try:
            result = subprocess.run(cmd, cwd=work, env=env)
            return result.returncode
        finally:
            export(work, staged, output)


if __name__ == "__main__":
    raise SystemExit(main())
