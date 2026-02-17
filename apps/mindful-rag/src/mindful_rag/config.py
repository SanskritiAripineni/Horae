"""Shared paths and experiment configuration for Mindful RAG."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - fallback when optional dep is missing.
    yaml = None


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
PDF_DIR = DATA_DIR / "raw" / "research_papers"
INDEX_CSV = DATA_DIR / "index" / "research_index.csv"
CHROMA_ROOT = DATA_DIR / "chroma"
EXPERIMENTS_DIR = ROOT_DIR / "configs" / "experiments"
REPO_ROOT = ROOT_DIR.parents[1]

ENV_FILE = ROOT_DIR / ".env"
LEGACY_ENV_FILE = REPO_ROOT / ".env"

DEFAULT_EXPERIMENT = "by_type"


@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    collection_name: str
    chroma_dir: Path
    description: str


_FALLBACK_EXPERIMENTS: dict[str, ExperimentConfig] = {
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


def _to_experiment_config(raw: dict, source: Path) -> ExperimentConfig | None:
    name = str(raw.get("name", "")).strip()
    collection_name = str(raw.get("collection_name", "")).strip()
    chroma_dir_value = str(raw.get("chroma_dir", "")).strip()
    description = str(raw.get("description", "")).strip()

    if not (name and collection_name and chroma_dir_value):
        return None

    chroma_dir = Path(chroma_dir_value)
    if not chroma_dir.is_absolute():
        chroma_dir = ROOT_DIR / chroma_dir

    if not description:
        description = f"Loaded from {source.name}"

    return ExperimentConfig(
        name=name,
        collection_name=collection_name,
        chroma_dir=chroma_dir,
        description=description,
    )


@lru_cache(maxsize=1)
def load_experiments() -> dict[str, ExperimentConfig]:
    """Load experiment configs from `configs/experiments/*.yaml`."""
    experiments: dict[str, ExperimentConfig] = {}

    if yaml is not None and EXPERIMENTS_DIR.exists():
        for file_path in sorted(EXPERIMENTS_DIR.glob("*.yaml")):
            try:
                with file_path.open("r", encoding="utf-8") as handle:
                    raw = yaml.safe_load(handle) or {}
            except Exception:
                continue
            if not isinstance(raw, dict):
                continue
            parsed = _to_experiment_config(raw, source=file_path)
            if parsed:
                experiments[parsed.name] = parsed

    if experiments:
        return experiments
    return dict(_FALLBACK_EXPERIMENTS)


def list_experiment_names() -> list[str]:
    """Return known experiment names."""
    return sorted(load_experiments().keys())


def get_env_file() -> Path:
    """Return preferred dotenv path, supporting legacy repo-root location."""
    if ENV_FILE.exists():
        return ENV_FILE
    return LEGACY_ENV_FILE


def get_experiment(name: str | None) -> ExperimentConfig:
    """Return experiment config, falling back to default when unknown."""
    experiments = load_experiments()
    default = experiments.get(DEFAULT_EXPERIMENT)
    if default is None:
        default = next(iter(experiments.values()))

    if not name:
        return default
    return experiments.get(name, default)


# Backward-compatible alias for older imports.
EXPERIMENTS = load_experiments()
