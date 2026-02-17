"""CLI entrypoint for Mindful RAG workflows."""

from __future__ import annotations

import argparse
import os
import subprocess
from typing import Sequence

from mindful_rag.config import (
    DEFAULT_EXPERIMENT,
    ROOT_DIR,
    get_experiment,
    list_experiment_names,
)


def _experiment_choices() -> list[str]:
    choices = list_experiment_names()
    if not choices:
        return [DEFAULT_EXPERIMENT]
    return choices


def run_ingest_command(experiment_name: str, reset_db: bool = False) -> int:
    """Run an ingestion strategy by experiment name."""
    if experiment_name == "raw":
        from mindful_rag.ingest_raw import main as ingest_raw

        ingest_raw(reset_db=reset_db)
        return 0

    if experiment_name == "intro_concl":
        from mindful_rag.ingest_intro_concl import main as ingest_intro_concl

        if reset_db:
            print("Warning: --reset-db is only used by 'raw'; ignoring flag.")
        ingest_intro_concl()
        return 0

    from mindful_rag.ingest_by_type import ingest as ingest_by_type

    if reset_db:
        print("Warning: --reset-db is only used by 'raw'; ignoring flag.")
    ingest_by_type()
    return 0


def run_app_command(experiment_name: str) -> int:
    """Run Streamlit app with the selected experiment runtime settings."""
    experiment = get_experiment(experiment_name)
    env = os.environ.copy()
    env["RAG_EXPERIMENT"] = experiment.name
    env["CHROMA_DIR"] = str(experiment.chroma_dir)
    env["COLLECTION_NAME"] = experiment.collection_name
    src_dir = str(ROOT_DIR / "src")
    if env.get("PYTHONPATH"):
        env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = src_dir

    subprocess.run(
        ["streamlit", "run", str(ROOT_DIR / "src" / "mindful_rag" / "app.py")],
        check=True,
        env=env,
    )
    return 0


def verify_chroma_command(experiment_name: str) -> int:
    """Inspect collection existence and sample data for an experiment DB."""
    import chromadb

    experiment = get_experiment(experiment_name)
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
    return 0


def _handle_ingest(args: argparse.Namespace) -> int:
    return run_ingest_command(experiment_name=args.experiment, reset_db=args.reset_db)


def _handle_run_app(args: argparse.Namespace) -> int:
    return run_app_command(experiment_name=args.experiment)


def _handle_verify(args: argparse.Namespace) -> int:
    return verify_chroma_command(experiment_name=args.experiment)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mindful-rag")
    subparsers = parser.add_subparsers(dest="command", required=True)

    experiment_choices = _experiment_choices()

    ingest_parser = subparsers.add_parser("ingest", help="Run one ingestion pipeline.")
    ingest_parser.add_argument(
        "--experiment",
        choices=experiment_choices,
        default=DEFAULT_EXPERIMENT,
        help="Select ingestion strategy.",
    )
    ingest_parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Only for raw experiment: delete existing DB before ingest.",
    )
    ingest_parser.set_defaults(handler=_handle_ingest)

    app_parser = subparsers.add_parser("run-app", help="Launch the Streamlit app.")
    app_parser.add_argument(
        "--experiment",
        choices=experiment_choices,
        default=DEFAULT_EXPERIMENT,
        help="Select which vector DB + collection to use.",
    )
    app_parser.set_defaults(handler=_handle_run_app)

    verify_parser = subparsers.add_parser("verify-chroma", help="Inspect an experiment collection.")
    verify_parser.add_argument(
        "--experiment",
        choices=experiment_choices,
        default=DEFAULT_EXPERIMENT,
        help="Experiment DB to inspect.",
    )
    verify_parser.set_defaults(handler=_handle_verify)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))
