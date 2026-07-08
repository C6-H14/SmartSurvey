"""Sandbox runner: extract from test_sandbox.pdf only.

Usage:
    .venv/Scripts/python.exe -u scripts/run_sandbox.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override INPUT_DIR to point to the single sandbox PDF *file* path
import scripts.run_extraction as re

# Monkey-patch: use sandbox PDF only
re.INPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
# Override glob to only pick up test_sandbox.pdf
import glob as _glob

original_glob = _glob.glob


def sandbox_glob(pattern):
    base = os.path.join(os.path.dirname(__file__), "..", "data")
    sandbox_path = os.path.join(base, "test_sandbox.pdf")
    if os.path.exists(sandbox_path):
        return [sandbox_path]
    return []


_glob.glob = sandbox_glob

# Run the main extraction
re.main()