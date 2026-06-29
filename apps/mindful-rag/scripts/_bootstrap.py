"""Bootstrap: add src/ to sys.path so mindful_rag can be imported from scripts/."""

import sys
from pathlib import Path


def bootstrap_local_src() -> None:
    src = Path(__file__).parent.parent / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
