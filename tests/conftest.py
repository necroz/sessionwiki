"""Pytest config for sessionwiki tests.

Makes sure the `sessionwiki` package is importable regardless of where pytest is
invoked from.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root (which contains the `sessionwiki/` package dir) is on
# sys.path when pytest is run from anywhere.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
SNAPSHOTS_DIR = REPO_ROOT / "tests" / "snapshots"
