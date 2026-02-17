"""Shared local import bootstrap for script compatibility."""

from __future__ import annotations

import sys
from pathlib import Path


def bootstrap_local_src() -> None:
    """Allow script execution without editable install."""
    root = Path(__file__).resolve().parents[1]
    src_dir = root / "src"
    src_str = str(src_dir)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
