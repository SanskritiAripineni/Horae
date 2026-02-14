"""Run one ingestion pipeline by experiment."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.mindful_rag.config import DEFAULT_EXPERIMENT
from src.mindful_rag.ingest_by_type import ingest as ingest_by_type
from src.mindful_rag.ingest_intro_concl import main as ingest_intro_concl
from src.mindful_rag.ingest_raw import main as ingest_raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--experiment",
        choices=["raw", "intro_concl", "by_type"],
        default=DEFAULT_EXPERIMENT,
        help="Select ingestion strategy.",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Only for raw experiment: delete existing DB before ingest.",
    )
    args = parser.parse_args()

    if args.experiment == "raw":
        ingest_raw(reset_db=args.reset_db)
        return
    if args.experiment == "intro_concl":
        if args.reset_db:
            print("Warning: --reset-db is only used by 'raw'; ignoring flag.")
        ingest_intro_concl()
        return
    if args.reset_db:
        print("Warning: --reset-db is only used by 'raw'; ignoring flag.")
    ingest_by_type()


if __name__ == "__main__":
    main()
