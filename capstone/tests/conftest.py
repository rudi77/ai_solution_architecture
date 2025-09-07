from __future__ import annotations

"""Pytest configuration to ensure imports work when running from the capstone folder.

This adds the repository root to sys.path so that imports like
`from capstone.backend.app.main import app` resolve correctly.
"""

import sys
from pathlib import Path


def _ensure_repo_root_on_syspath() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    path_str = str(repo_root)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


_ensure_repo_root_on_syspath()


