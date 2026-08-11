#!/usr/bin/env python3
"""Entry point. Loads .env if present, then dispatches to agent.cli."""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(line_buffering=True)  # milestones stream live when logging to a file
sys.stderr.reconfigure(line_buffering=True)

env = Path(__file__).parent / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            if v and k not in os.environ:
                os.environ[k] = v

from agent.cli import main  # noqa: E402

main()
