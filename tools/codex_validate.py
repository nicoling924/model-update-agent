"""Offline CI entry point for the registered drytest workflow; no model calls."""
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
for command in [['bash','tools/bench.sh'],[sys.executable,'tests/test_mvp_contract.py'],[sys.executable,'tests/test_extraction_boundary.py'],[sys.executable,'tests/test_cold_inputs.py'],[sys.executable,'tests/test_source_handoff.py'],[sys.executable,'tests/test_plug_boundary.py'],[sys.executable,'tests/test_signed_operands.py'],[sys.executable,'tests/test_freeze_rollover_rules.py'],[sys.executable,'tests/test_anatomy_evidence.py'],[sys.executable,'tests/test_compact_report.py'],[sys.executable,'tests/test_oneoff_mapping_contract.py'],[sys.executable,'tests/test_mapping_model_units.py']]:
    subprocess.run(command,cwd=root,check=True)
