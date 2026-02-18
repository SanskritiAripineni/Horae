"""Ingest text directly from CSV columns for retrieval-source experiments."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF
import pandas as pd
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from mindful_rag.config import INDEX_CSV, PDF_DIR, get_env_file, get_experiment
from mindful_rag.embeddings import create_document_embeddings

# Configuration
PDF_SOURCE_DIR = str(PDF_DIR)


EXPERIMENT = get_experiment("csv_sources")
DEFAULT_INPUT_CSV = INDEX_CSV.parent / "research_index_clean.csv"
CHROMA_DIR = str(EXPERIMENT.chroma_dir)
COLLECTION_NAME = EXPERIMENT.collection_name
EMBEDDING_MODEL = "gemini-embedding-001"
CHUNK_SIZE = int(os.getenv("CSV_SOURCES_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CSV_SOURCES_CHUNK_OVERLAP", "100"))
MIN_SOURCE_TEXT_CHARS = int(os.getenv("CSV_SOURCES_MIN_CHARS", "120"))
WRITE_VECTORS = os.getenv("CSV_SOURCES_WRITE_VECTORS", "1").strip().lower() not in {"0", "false", "no"}
ALLOW_EMBEDDING_FALLBACK = (
    os.getenv("CSV_SOURCES_ALLOW_EMBEDDING_FALLBACK", "0").strip().lower() not in {"0", "false", "no"}
)

SOURCE_COLUMN_ALIASES: dict[str, list[str]] = {
    "relevant_info": ["relevant_info", "by_type_text"],
    "intro_concl": ["intro_concl", "intro_concl_text"],
    "raw": ["raw_text"],
}
SOURCE_TOKEN_ALIASES = {
    "relevant": "relevant_info",
    "relevant_info": "relevant_info",
    "by_type": "relevant_info",
    "by_type_text": "relevant_info",
    "intro": "intro_concl",
    "intro_concl": "intro_concl",
    "intro_conclusion": "intro_concl",
    "intro_concl_text": "intro_concl",
    "raw": "raw",
    "raw_text": "raw",
}


def extract_full_text(pdf_path: str) -> str:
    """Extract full PDF text."""
    try:
        doc = fitz.open(pdf_path)
        full_text = "".join(page.get_text() for page in doc)
        doc.close()
        return full_text
    except Exception as exc:
        print(f"Failed to load PDF {pdf_path}: {exc}")
        return ""


def _default_input_csv_path() -> Path:
    if DEFAULT_INPUT_CSV.parent.exists():
        snapshots = sorted(DEFAULT_INPUT_CSV.parent.glob("research_index_ingestions_*.csv"))
        if snapshots:
            return snapshots[-1]
    if DEFAULT_INPUT_CSV.exists():
        return DEFAULT_INPUT_CSV
    return INDEX_CSV


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _pick_text(row: pd.Series, keys: Iterable[str], default: str = "") -> str:
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return default


def _normalize_source_token(token: str) -> str:
    key = str(token or "").strip().lower().replace("-", "_")
    return SOURCE_TOKEN_ALIASES.get(key, "")


def resolve_source_modes(source_modes: list[str] | None) -> list[str]:
    if source_modes:
        tokens = source_modes
    else:
        raw = os.getenv("CSV_SOURCES_COLUMNS", "relevant_info,intro_concl")
        tokens = [item.strip() for item in raw.split(",")]

    resolved: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        mode = _normalize_source_token(token)
        if not mode or mode in seen:
            continue
        seen.add(mode)
        resolved.append(mode)

    if resolved:
        return resolved
    return ["relevant_info", "intro_concl"]


def _build_chunk_id(row_id: str, retrieval_source: str, chunk_index: int, chunk_text: str) -> str:
    digest = hashlib.sha1(
        f"{row_id}|{retrieval_source}|{chunk_index}|{chunk_text}".encode("utf-8")
    ).hexdigest()[:16]
    row_key = re.sub(r"[^a-z0-9]+", "-", row_id.lower()).strip("-") or "row"
    return f"{row_key}-{retrieval_source}-{chunk_index:04d}-{digest}"


def ingest(source_modes: list[str] | None = None) -> None:
    load_dotenv(dotenv_path=get_env_file())
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if google_api_key:
        print(f"Loaded GOOGLE_API_KEY: {google_api_key[:4]}... (present)")
    else:
        print("Error: GOOGLE_API_KEY is missing/empty!")

    if WRITE_VECTORS and not google_api_key and not ALLOW_EMBEDDING_FALLBACK:
        print("Error: GOOGLE_API_KEY not found in environment.")
        print("Add GOOGLE_API_KEY to your .env or set CSV_SOURCES_ALLOW_EMBEDDING_FALLBACK=1.")
        return

    input_csv_path = os.getenv("CSV_SOURCES_INPUT_CSV", str(_default_input_csv_path()))

    if not os.path.exists(input_csv_path):
        print(f"Error: Input CSV not found at {input_csv_path}")
        return

    selected_sources = resolve_source_modes(source_modes)
    df = pd.read_csv(input_csv_path)
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    print(f"Using input CSV: {input_csv_path}")
    print(f"Experiment DB: {CHROMA_DIR}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Selected retrieval sources: {', '.join(selected_sources)}")
    print(f"Rows in CSV: {len(df)}")

    all_chunks: list[dict[str, object]] = []
    seen_chunk_ids: set[str] = set()
    stats = Counter()

    for idx, row in df.iterrows():
        row_id = _pick_text(row, ["id", "ID"], default=str(idx + 1))
        title = _pick_text(row, ["paper_title", "title", "Paper Title"], default="Untitled")
        category = _pick_text(row, ["category", "Category (The Folder)"], default="General")
        cluster = _pick_text(row, ["cluster", "Cluster"])
        paper_type = _pick_text(row, ["paper_type", "Paper Type"], default="Unknown")
        mechanism = _pick_text(row, ["main_mechanism", "Main Mechanism (Tags)"])
        filename = _pick_text(
            row,
            ["matched_pdf", "source_pdf", "filename", "filename_link", "Filename/Link"],
            default=f"{row_id}.pdf",
        )

        row_indexed = False
        for source in selected_sources:
            if source == "raw":
                # Special handling for raw: read from PDF directly
                pdf_path = os.path.join(PDF_SOURCE_DIR, filename)
                if not os.path.exists(pdf_path):
                     stats[f"{source}_pdf_not_found"] += 1
                     continue
                source_text = _clean_text(extract_full_text(pdf_path))
            else:
                source_text = _clean_text(_pick_text(row, SOURCE_COLUMN_ALIASES[source]))
            
            if len(source_text) < MIN_SOURCE_TEXT_CHARS:
                stats[f"{source}_too_short"] += 1
                continue

            chunks = splitter.split_text(source_text)
            if not chunks:
                stats[f"{source}_no_chunks"] += 1
                continue

            stats[f"{source}_rows"] += 1
            stats[f"{source}_chunks"] += len(chunks)
            row_indexed = True

            base_metadata = {
                "filename": filename,
                "source": filename,
                "paper_type": paper_type,
                "category": category,
                "cluster": cluster,
                "main_mechanism": mechanism,
                "title": title,
                "row_id": row_id,
                "retrieval_source": source,
                "extraction_strategy": "csv_sources",
                "source_chars": len(source_text),
            }

            for chunk_idx, chunk_text in enumerate(chunks):
                cleaned_chunk = _clean_text(chunk_text)
                if not cleaned_chunk:
                    continue
                chunk_id = _build_chunk_id(
                    row_id=row_id,
                    retrieval_source=source,
                    chunk_index=chunk_idx,
                    chunk_text=cleaned_chunk,
                )
                if chunk_id in seen_chunk_ids:
                    stats["duplicate_chunks"] += 1
                    continue
                seen_chunk_ids.add(chunk_id)
                all_chunks.append(
                    {
                        "id": chunk_id,
                        "text": cleaned_chunk,
                        "metadata": {
                            **base_metadata,
                            "chunk_index": chunk_idx,
                            "total_chunks": len(chunks),
                        },
                    }
                )

        if row_indexed:
            stats["rows_indexed"] += 1
        else:
            stats["rows_without_sources"] += 1

    if WRITE_VECTORS:
        if os.path.exists(CHROMA_DIR):
            shutil.rmtree(CHROMA_DIR)

        if all_chunks:
            embeddings = create_document_embeddings(
                api_key=google_api_key,
                model=EMBEDDING_MODEL,
                task_type="RETRIEVAL_DOCUMENT",
                allow_fallback=ALLOW_EMBEDDING_FALLBACK,
            )
            vectorstore = Chroma(
                persist_directory=CHROMA_DIR,
                collection_name=COLLECTION_NAME,
                embedding_function=embeddings,
            )
            batch_size = 5000
            total_chunks = len(all_chunks)
            print(f"  -> Sending {total_chunks} chunks in batches of {batch_size}...")
            
            for i in range(0, total_chunks, batch_size):
                batch = all_chunks[i : i + batch_size]
                vectorstore.add_texts(
                    texts=[item["text"] for item in batch],
                    metadatas=[item["metadata"] for item in batch],
                    ids=[item["id"] for item in batch],
                )
                print(f"     Processed batch {i // batch_size + 1}/{(total_chunks + batch_size - 1) // batch_size}")
            print(f"Embedding backend: {getattr(embeddings, 'backend_name', 'unknown')}")
        else:
            print("No chunks prepared; skipping vector write.")

    print("\nCSV SOURCES INGEST SUMMARY")
    print(f"  Indexed rows: {stats['rows_indexed']}")
    print(f"  Rows without selected sources: {stats['rows_without_sources']}")
    for source in selected_sources:
        print(f"  {source} rows used: {stats[f'{source}_rows']}")
        print(f"  {source} chunks created: {stats[f'{source}_chunks']}")
    print(f"  Duplicate chunks skipped: {stats['duplicate_chunks']}")
    print(f"  Total chunks stored: {len(all_chunks)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest retrieval text from selected CSV columns.")
    parser.add_argument(
        "--sources",
        default="",
        help="Comma-separated source names: relevant_info,intro_concl,raw",
    )
    args = parser.parse_args(argv)
    source_modes = [item.strip() for item in args.sources.split(",") if item.strip()]
    ingest(source_modes=source_modes or None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
