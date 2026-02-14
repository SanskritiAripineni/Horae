"""Verify a Chroma collection for a selected experiment."""

import argparse
import sys
from pathlib import Path

import chromadb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.mindful_rag.config import DEFAULT_EXPERIMENT, get_experiment


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiment",
        choices=["raw", "intro_concl", "by_type"],
        default=DEFAULT_EXPERIMENT,
        help="Experiment DB to inspect.",
    )
    args = parser.parse_args()

    experiment = get_experiment(args.experiment)
    client = chromadb.PersistentClient(path=str(experiment.chroma_dir))

    try:
        collection = client.get_collection(name=experiment.collection_name)
        count = collection.count()
        print(f"Collection '{experiment.collection_name}' exists.")
        print(f"Total documents (chunks): {count}")
        if count > 0:
            result = collection.peek(limit=1)
            print("\n--- Sample Document ---")
            print("Metadata:", result["metadatas"][0])
            print("Content Preview:", result["documents"][0][:200] + "...")
        else:
            print("Collection is empty.")
    except Exception as exc:
        print(f"Verification failed: {exc}")


if __name__ == "__main__":
    main()
