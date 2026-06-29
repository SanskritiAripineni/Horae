"""
Central path configuration for the mindful-rag eval framework.
All scripts should import from here rather than hard-coding paths.
"""

from pathlib import Path

# apps/mindful-rag/
ROOT_DIR: Path = Path(__file__).parent.parent.parent

# Research papers directory (PDFs to ingest)
PDF_DIR: Path = ROOT_DIR / "data" / "raw" / "research_papers"

# CSV index of papers (title, category, extracted text)
INDEX_CSV: Path = ROOT_DIR / "data" / "index" / "research_index.csv"


def get_env_file() -> Path:
    """Return the nearest .env file, falling back to the repo root."""
    local_env = ROOT_DIR / ".env"
    if local_env.exists():
        return local_env
    # Walk up to the repo root (.../Multi-Agent-LLM/.env)
    repo_root = ROOT_DIR.parent.parent
    repo_env = repo_root / ".env"
    if repo_env.exists():
        return repo_env
    return local_env  # caller can decide whether to error
