"""Cold runs must not receive a previous run's model knowledge or evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from openpyxl import Workbook
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.cold_run import prepare


class ColdInputs(unittest.TestCase):
    def fixture(self, root, learned=False):
        company = root / "company"
        (company / "model").mkdir(parents=True)
        wb = Workbook()
        wb.active["A1"] = "Analyst's original row"
        wb.active["B1"] = "=10+20"
        if learned:
            wb.create_sheet("_SPEC")["A1"] = "Prior agent knowledge"
        wb.save(company / "model" / "input.xlsx")
        disclosures = company / "disclosures" / "FY25"
        disclosures.mkdir(parents=True)
        (disclosures / "report.pdf").write_bytes(b"fixture PDF bytes")
        (company / "spec.yaml").write_text("learned: previous run")
        (company / "MODEL_SPEC.md").write_text("Prior manually prepared mappings")
        (company / "replay").mkdir()
        (company / "replay" / "ledger.json").write_text("old evidence")
        return company

    def test_only_workbook_and_attached_pdf_are_copied(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); company = self.fixture(root)
            manifest = prepare(company, "FY25", root / "cold")
            paths = {str(p.relative_to(root / "cold")) for p in (root / "cold").rglob("*") if p.is_file()}
            self.assertEqual(paths, {"model/input.xlsx", "disclosures/FY25/report.pdf"})
            self.assertEqual((root / "cold/model/input.xlsx").read_bytes(),
                             (company / "model/input.xlsx").read_bytes())
            self.assertEqual(manifest["prior_context"], [])
            json.dumps(manifest)

    def test_learned_workbook_is_rejected_before_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); company = self.fixture(root, learned=True)
            with self.assertRaisesRegex(ValueError, "original workbook"):
                prepare(company, "FY25", root / "cold")

    def test_existing_destination_cannot_supply_a_cache_or_spec(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); company = self.fixture(root)
            (root / "cold").mkdir()
            (root / "cold/spec.yaml").write_text("old knowledge")
            with self.assertRaises(FileExistsError):
                prepare(company, "FY25", root / "cold")

    def test_launcher_uses_empty_cwd_and_exports_new_evidence_separately(self):
        import tools.cold_run as runner
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); company = self.fixture(root)
            repo = root / "repo"; (repo / ".cache").mkdir(parents=True)
            (repo / ".cache/old.json").write_text("prior extraction")
            def child(cmd, cwd, env):
                self.assertFalse((cwd / ".cache").exists())
                self.assertFalse((Path(cmd[3]) / "spec.yaml").exists())
                cache = cwd / ".cache/pipeline-vision"; cache.mkdir(parents=True)
                (cache / "new.json").write_text("new evidence")
                return SimpleNamespace(returncode=0)
            with patch.object(runner,"REPO",repo), patch.object(runner.subprocess,"check_output",return_value="revision"), patch.object(runner.subprocess,"run",side_effect=child):
                self.assertEqual(runner.main([str(company),"FY25","2025","--dry"]),0)
            out = repo / "cold_out/company-FY25"
            self.assertEqual((out / "extraction/new.json").read_text(),"new evidence")
            self.assertFalse((out / "extraction/old.json").exists())
            self.assertTrue((company / "spec.yaml").exists())


if __name__ == "__main__":
    unittest.main()
