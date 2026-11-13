"""Pytest configuration for standalone sts_lab test suite."""

import sys
from pathlib import Path

# Ensure parent directory is on sys.path so "import sts_lab.xxx" always resolves cleanly
tests_dir = Path(__file__).resolve().parent
sts_lab_dir = tests_dir.parent
parent_dir = sts_lab_dir.parent

for p in (str(parent_dir), str(sts_lab_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Tests must never read the developer's real .env (it can hold live database and API credentials,
# and would make results depend on whose machine they run on). config.py calls load_dotenv() when it is
# imported, so we turn that into a no-op BEFORE any test module imports it.
import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *args, **kwargs: False

