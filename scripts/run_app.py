"""Run Streamlit app with an experiment selection."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.mindful_rag.config import DEFAULT_EXPERIMENT, ROOT_DIR, get_experiment


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiment",
        choices=["raw", "intro_concl", "by_type"],
        default=DEFAULT_EXPERIMENT,
        help="Select which vector DB + collection to use.",
    )
    args = parser.parse_args()

    experiment = get_experiment(args.experiment)
    env = os.environ.copy()
    env["RAG_EXPERIMENT"] = experiment.name
    env["CHROMA_DIR"] = str(experiment.chroma_dir)
    env["COLLECTION_NAME"] = experiment.collection_name

    subprocess.run(
        ["streamlit", "run", str(ROOT_DIR / "src" / "mindful_rag" / "app.py")],
        check=True,
        env=env,
    )


if __name__ == "__main__":
    main()
