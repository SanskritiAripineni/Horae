"""
Raw Baseline Ingestion Script
==============================
Ingests all 61 research papers WITHOUT any semantic filtering for ablation study.
Includes full text with bibliographies, references, and all sections intact.

Author: Sanskriti
Purpose: Establish 'Raw' baseline performance metrics with noisy data
"""

import argparse
import hashlib
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Optional

import chromadb
import fitz  # PyMuPDF
import pandas as pd
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from thefuzz import fuzz, process

from mindful_rag.config import INDEX_CSV, PDF_DIR, get_env_file, get_experiment
from mindful_rag.embeddings import GeminiGenAIEmbeddings

# ============================================================================
# CONFIGURATION
# ============================================================================

EXPERIMENT = get_experiment("raw")
CSV_PATH = str(INDEX_CSV)
PDF_FOLDER = str(PDF_DIR)
CHROMA_DIR = str(EXPERIMENT.chroma_dir)
COLLECTION_NAME = EXPERIMENT.collection_name

# Chunking parameters
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
MIN_CHUNK_CHARS = 20

# Matching thresholds
MATCH_THRESHOLD = 72
MATCH_MIN_GAP = 5
LOW_CONFIDENCE_MATCH = 80

# Embedding model (same as app.py for consistency)
EMBEDDING_MODEL = "gemini-embedding-001"


# ============================================================================
# STEP 1: LOAD CSV AND PDF FILES
# ============================================================================

def load_csv_data(csv_path: str) -> pd.DataFrame:
    """Load research index CSV and filter out rows without titles."""
    print(f"📄 Loading CSV from: {csv_path}")
    df = pd.read_csv(csv_path)

    # Remove rows where Paper Title is missing
    df = df.dropna(subset=["Paper Title"])

    print(f"✓ Loaded {len(df)} papers from CSV")
    return df


def get_pdf_files(pdf_folder: str) -> list[str]:
    """Get all PDF filenames from the research papers folder."""
    pdf_path = Path(pdf_folder)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF folder not found: {pdf_folder}")

    pdf_files = [f.name for f in pdf_path.glob("*.pdf")]
    print(f"📁 Found {len(pdf_files)} PDF files in '{pdf_folder}'")
    return pdf_files


# ============================================================================
# STEP 2: STRICTER FUZZY MATCHING
# ============================================================================

def normalize_for_match(text: str) -> str:
    """Normalize titles and filenames before strict matching checks."""
    collapsed = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(collapsed.split())


def match_title_to_filename(
    title: str,
    pdf_files: list[str],
    threshold: int = MATCH_THRESHOLD,
    min_gap: int = MATCH_MIN_GAP,
) -> tuple[Optional[str], int, str]:
    """
    Match paper title to PDF filename with stronger acceptance rules.

    Returns:
        (matched_filename, score, method_or_reason)
    """
    if not title or not title.strip():
        return None, 0, "empty_title"

    normalized_title = normalize_for_match(title)
    stem_to_file: dict[str, str] = {Path(f).stem: f for f in pdf_files}

    exact_candidates = [
        filename
        for filename in pdf_files
        if normalize_for_match(Path(filename).stem) == normalized_title
    ]
    if len(exact_candidates) == 1:
        return exact_candidates[0], 100, "exact_normalized"
    if len(exact_candidates) > 1:
        return None, 100, "ambiguous_exact_normalized"

    stems = list(stem_to_file.keys())
    matches = process.extract(title, stems, scorer=fuzz.token_set_ratio, limit=2)
    if not matches:
        return None, 0, "no_candidates"

    best_name, best_score = matches[0][0], int(matches[0][1])
    second_score = int(matches[1][1]) if len(matches) > 1 else 0

    if best_score < threshold:
        return None, best_score, f"score_below_threshold({best_score}<{threshold})"
    if len(matches) > 1 and (best_score - second_score) < min_gap:
        return None, best_score, f"ambiguous_gap({best_score}-{second_score}<{min_gap})"

    return stem_to_file[best_name], best_score, "fuzzy_token_set"


# ============================================================================
# STEP 3: RAW TEXT EXTRACTION (NO FILTERING)
# ============================================================================

def extract_full_text_from_pdf(pdf_path: str) -> str:
    """
    Extract COMPLETE raw text from PDF using PyMuPDF.
    NO filtering - includes references, bibliographies, everything.
    """
    try:
        doc = fitz.open(pdf_path)
        full_text = ""

        for page_num in range(len(doc)):
            page = doc[page_num]
            full_text += page.get_text()

        doc.close()
        return full_text.strip()

    except Exception as exc:
        print(f"⚠️  Error extracting text from {pdf_path}: {exc}")
        return ""


# ============================================================================
# STEP 4: CHUNKING + DOCUMENT ID
# ============================================================================

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into chunks using RecursiveCharacterTextSplitter."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


def build_chunk_id(filename: str, chunk_index: int, chunk_text_value: str) -> str:
    """Build deterministic chunk IDs so reruns do not create duplicates."""
    file_stem = normalize_for_match(Path(filename).stem).replace(" ", "-")
    digest = hashlib.sha1(
        f"{filename}|{chunk_index}|{chunk_text_value}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{file_stem}-{chunk_index:04d}-{digest}"


def validate_document_batch(documents: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Validate chunk payload before DB write and drop invalid rows."""
    stats = {
        "invalid_structure": 0,
        "empty_or_tiny_text": 0,
        "duplicate_ids_in_batch": 0,
    }
    seen_ids: set[str] = set()
    valid_docs: list[dict] = []

    for doc in documents:
        doc_id = str(doc.get("id", "")).strip()
        text = str(doc.get("text", "")).strip()
        metadata = doc.get("metadata")

        if not doc_id or not isinstance(metadata, dict):
            stats["invalid_structure"] += 1
            continue
        if len(text) < MIN_CHUNK_CHARS:
            stats["empty_or_tiny_text"] += 1
            continue
        if doc_id in seen_ids:
            stats["duplicate_ids_in_batch"] += 1
            continue

        seen_ids.add(doc_id)
        valid_docs.append({"id": doc_id, "text": text, "metadata": metadata})

    return valid_docs, stats


# ============================================================================
# STEP 5: VECTOR STORE INGESTION + VALIDATION
# ============================================================================

def get_collection_count() -> int:
    """Return chunk count for raw collection (0 if missing)."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(name=COLLECTION_NAME)
        return collection.count()
    except Exception:
        return 0


def fetch_existing_ids(batch_size: int = 1000) -> set[str]:
    """Collect existing chunk IDs so reruns can skip already-indexed chunks."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception:
        return set()

    total = collection.count()
    ids: set[str] = set()

    for offset in range(0, total, batch_size):
        batch = collection.get(limit=batch_size, offset=offset, include=["metadatas"])
        ids.update(batch.get("ids", []))

    return ids


def ingest_to_chromadb(documents: list[dict], embeddings, reset_db: bool = False) -> dict[str, int | bool]:
    """
    Ingest document chunks into ChromaDB with deterministic IDs.

    - Optional DB reset for clean rebuilds.
    - Duplicate protection across reruns via stable chunk IDs.
    - Post-ingest validation using collection counts.
    """
    if reset_db and os.path.exists(CHROMA_DIR):
        print(f"\n🧹 Reset requested. Removing existing DB at: {CHROMA_DIR}")
        shutil.rmtree(CHROMA_DIR)

    existing_ids = set() if reset_db else fetch_existing_ids()
    existing_count = len(existing_ids)

    new_documents = [doc for doc in documents if doc["id"] not in existing_ids]
    skipped_existing = len(documents) - len(new_documents)

    print(f"\n🔄 Preparing ingestion for {len(documents)} validated chunks...")
    print(f"   Existing chunks in DB: {existing_count}")
    print(f"   Skipped (already indexed): {skipped_existing}")
    print(f"   New chunks to write: {len(new_documents)}")

    if new_documents:
        vectorstore = Chroma(
            persist_directory=CHROMA_DIR,
            embedding_function=embeddings,
            collection_name=COLLECTION_NAME,
        )
        vectorstore.add_texts(
            texts=[doc["text"] for doc in new_documents],
            metadatas=[doc["metadata"] for doc in new_documents],
            ids=[doc["id"] for doc in new_documents],
        )

    final_count = get_collection_count()
    expected_min = existing_count + len(new_documents)
    validation_ok = final_count >= expected_min

    return {
        "existing_count": existing_count,
        "attempted_count": len(documents),
        "newly_written_count": len(new_documents),
        "skipped_existing_count": skipped_existing,
        "final_count": final_count,
        "validation_ok": validation_ok,
    }


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main(reset_db: bool = False) -> None:
    """Main ingestion pipeline for raw baseline experiment."""
    load_dotenv(dotenv_path=get_env_file())
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("Error: GOOGLE_API_KEY not found in environment.")
        print("Add GOOGLE_API_KEY=your-google-api-key-here to your .env file.")
        return

    print("=" * 70)
    print("RAW BASELINE INGESTION - ABLATION STUDY")
    print("=" * 70)
    print("Mode: FULL TEXT (No filtering, includes all sections)")
    print(f"Chunk Size: {CHUNK_SIZE} | Overlap: {CHUNK_OVERLAP}")
    print(f"Match Threshold: {MATCH_THRESHOLD} | Min Gap: {MATCH_MIN_GAP}")
    print(f"Reset Existing DB: {'Yes' if reset_db else 'No'}")
    print("=" * 70)

    # Step 1: Load data
    df = load_csv_data(CSV_PATH)
    pdf_files = get_pdf_files(PDF_FOLDER)

    # Step 2: Initialize embeddings
    print(f"\n🤖 Loading embedding model: {EMBEDDING_MODEL}")
    embeddings = GeminiGenAIEmbeddings(
        api_key=google_api_key,
        model=EMBEDDING_MODEL,
        task_type="RETRIEVAL_DOCUMENT",
    )
    print("✓ Embedding model loaded")

    # Step 3: Process each paper
    all_documents: list[dict] = []
    matched_count = 0
    failed_matches: list[str] = []
    failed_reasons: Counter[str] = Counter()
    low_confidence_matches = 0

    print(f"\n📚 Processing {len(df)} papers...")
    print("-" * 70)

    for _, row in df.iterrows():
        paper_title = str(row.get("Paper Title", "")).strip()
        paper_type = row.get("Paper Type", "Unknown")
        category = row.get("Category (The Folder)", "Unknown")
        cluster = row.get("Cluster", "Unknown")

        matched_filename, match_score, match_method = match_title_to_filename(
            paper_title,
            pdf_files,
            threshold=MATCH_THRESHOLD,
            min_gap=MATCH_MIN_GAP,
        )

        if not matched_filename:
            print(f"❌ No confident match: {paper_title[:60]}... [{match_method}]")
            failed_matches.append(paper_title)
            failed_reasons[match_method] += 1
            continue

        if match_score < LOW_CONFIDENCE_MATCH:
            low_confidence_matches += 1

        pdf_path = os.path.join(PDF_FOLDER, matched_filename)
        full_text = extract_full_text_from_pdf(pdf_path)
        if not full_text:
            print(f"⚠️  Empty text for: {matched_filename}")
            failed_reasons["empty_pdf_text"] += 1
            continue

        chunks = chunk_text(full_text)
        if not chunks:
            print(f"⚠️  No chunks produced for: {matched_filename}")
            failed_reasons["no_chunks"] += 1
            continue

        for chunk_idx, text_chunk in enumerate(chunks):
            metadata = {
                "filename": matched_filename,
                "paper_title": paper_title,
                "paper_type": paper_type,
                "category": category,
                "cluster": cluster,
                "chunk_index": chunk_idx,
                "total_chunks": len(chunks),
                "match_method": match_method,
                "match_score": match_score,
            }
            cleaned_chunk = text_chunk.strip()
            chunk_id = build_chunk_id(matched_filename, chunk_idx, cleaned_chunk)
            all_documents.append(
                {
                    "id": chunk_id,
                    "text": cleaned_chunk,
                    "metadata": metadata,
                }
            )

        matched_count += 1
        print(
            f"✓ [{matched_count}/{len(df)}] {matched_filename} "
            f"(score={match_score}) → {len(chunks)} chunks"
        )

    # Step 4: Validate + ingest into ChromaDB
    valid_documents, batch_stats = validate_document_batch(all_documents)
    match_rate = (matched_count / len(df)) if len(df) else 0.0

    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    print(f"Papers matched: {matched_count}/{len(df)} ({match_rate:.1%})")
    print(f"Low-confidence matches (<{LOW_CONFIDENCE_MATCH}): {low_confidence_matches}")
    print(f"Total chunks created: {len(all_documents)}")
    print(f"Valid chunks after validation: {len(valid_documents)}")
    print(f"Validation drops: {batch_stats}")
    print(f"Failed matches: {len(failed_matches)}")

    if failed_reasons:
        print("\nFailure reasons:")
        for reason, count in failed_reasons.most_common():
            print(f"  - {reason}: {count}")

    if failed_matches:
        print("\n⚠️  Papers without confident matches:")
        for title in failed_matches:
            print(f"  - {title}")

    if valid_documents:
        db_stats = ingest_to_chromadb(valid_documents, embeddings, reset_db=reset_db)
        print("\nDB Write Summary:")
        print(f"  - Existing chunks before write: {db_stats['existing_count']}")
        print(f"  - New chunks written: {db_stats['newly_written_count']}")
        print(f"  - Skipped existing chunks: {db_stats['skipped_existing_count']}")
        print(f"  - Final collection count: {db_stats['final_count']}")
        print(f"  - Ingest validation: {'PASS' if db_stats['validation_ok'] else 'FAIL'}")
        if not db_stats["validation_ok"]:
            print("  - Validation check failed: final count lower than expected minimum.")
        print("\n✅ RAW BASELINE INGESTION COMPLETE!")
        print(f"📊 Vector database saved to: {CHROMA_DIR}")
    else:
        print("\n❌ No valid documents to ingest!")

    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Delete existing raw experiment DB before ingestion.",
    )
    args = parser.parse_args()
    main(reset_db=args.reset_db)
