"""Offline CI entry point for the registered drytest workflow; no model calls."""
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parents[1]
for command in [['bash','tools/bench.sh'],[sys.executable,'tests/test_mvp_contract.py']]:
    subprocess.run(command,cwd=root,check=True)
