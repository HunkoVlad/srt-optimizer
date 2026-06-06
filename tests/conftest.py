"""Shared pytest configuration for local test runs.

The pyproject pytest config adds src to pytest's import path. A few tests spawn
fresh Python subprocesses, so mirror that path into PYTHONPATH for child
processes as well.
"""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = str(PROJECT_ROOT / "src")

existing_pythonpath = os.environ.get("PYTHONPATH", "")
if SRC_PATH not in existing_pythonpath.split(os.pathsep):
    os.environ["PYTHONPATH"] = SRC_PATH if not existing_pythonpath else SRC_PATH + os.pathsep + existing_pythonpath
