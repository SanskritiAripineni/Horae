"""Shared paths and experiment configuration for Mindful RAG."""

from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
PDF_DIR = DATA_DIR / "raw" / "research_papers"
INDEX_CSV = DATA_DIR / "index" / "research_index.csv"
CHROMA_ROOT = DATA_DIR / "chroma"


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    collection_name: str
    chroma_dir: Path
    description: str


EXPERIMENTS: dict[str, ExperimentConfig] = {
    "raw": ExperimentConfig(
        name="raw",
        collection_name="wellness_papers",
        chroma_dir=CHROMA_ROOT / "raw",
        description="Full-text ingestion without section filtering.",
    ),
    "intro_concl": ExperimentConfig(
        name="intro_concl",
        collection_name="wellness_ablation",
        chroma_dir=CHROMA_ROOT / "intro_concl",
        description="Only introduction and conclusion/discussion sections.",
    ),
    "by_type": ExperimentConfig(
        name="by_type",
        collection_name="research_papers",
        chroma_dir=CHROMA_ROOT / "by_type",
        description="Paper-type-aware extraction rules.",
    ),
}

DEFAULT_EXPERIMENT = "by_type"


def get_experiment(name: str | None) -> ExperimentConfig:
    """Return experiment config, falling back to default when unknown."""
    if not name:
        return EXPERIMENTS[DEFAULT_EXPERIMENT]
    return EXPERIMENTS.get(name, EXPERIMENTS[DEFAULT_EXPERIMENT])
