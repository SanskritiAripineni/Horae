"""
Ablation Study Ingestion Script: ingest_intro_concl.py
------------------------------------------------------
Extracts Introduction and Conclusion/Discussion sections from PDFs.
Filters out most other sections and stores chunks in Chroma.
"""

import hashlib
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Optional

import fitz  # pymupdf
import pandas as pd
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from thefuzz import fuzz, process

from mindful_rag.config import INDEX_CSV, PDF_DIR, get_env_file, get_experiment
from mindful_rag.embeddings import GeminiGenAIEmbeddings

# Configuration
EXPERIMENT = get_experiment("intro_concl")
INTRO_CONCL_INDEX_CSV = INDEX_CSV.parent / "research_index_clean.csv"
LEGACY_INTRO_CONCL_INDEX_CSV = INDEX_CSV.parent / "research_index_intro_concl_dedup.csv"
CSV_PATH = os.getenv(
    "INTRO_CONCL_INDEX_CSV",
    str(
        INTRO_CONCL_INDEX_CSV
        if INTRO_CONCL_INDEX_CSV.exists()
        else (LEGACY_INTRO_CONCL_INDEX_CSV if LEGACY_INTRO_CONCL_INDEX_CSV.exists() else INDEX_CSV)
    ),
)
PDF_SOURCE_DIR = str(PDF_DIR)
CHROMA_DIR = str(EXPERIMENT.chroma_dir)
COLLECTION_NAME = EXPERIMENT.collection_name
EMBEDDING_MODEL = "gemini-embedding-001"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
MIN_EXTRACTED_TEXT_CHARS = 200
MATCH_THRESHOLD = 75

_INTRO_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?\s*)?introduction(?:[:.\s]|$)",
    re.IGNORECASE,
)
_INTRO_STOP_PATTERNS = [
    re.compile(r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?\s*)?methods?(?:[:.\s]|$)", re.IGNORECASE),
    re.compile(
        r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?\s*)?materials?\s+and\s+methods?(?:[:.\s]|$)",
        re.IGNORECASE,
    ),
    re.compile(r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?\s*)?related\s+work(?:[:.\s]|$)", re.IGNORECASE),
    re.compile(r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?\s*)?background(?:[:.\s]|$)", re.IGNORECASE),
    re.compile(
        r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?\s*)?literature\s+review(?:[:.\s]|$)",
        re.IGNORECASE,
    ),
]
_CONCL_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?\s*)?(?:conclusions?|discussion)(?:[:.\s]|$)",
    re.IGNORECASE,
)
_REFERENCES_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?\s*)?(?:references|bibliography|works\s+cited)(?:[:.\s]|$)",
    re.IGNORECASE,
)


def _normalize_for_match(text: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(collapsed.split())


def clean_text(text: str) -> str:
    """Basic text cleaning."""
    return re.sub(r"\s+", " ", text).strip()


def _pick_text(row: pd.Series, keys: list[str], default: str = "") -> str:
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


def _pick_int(row: pd.Series, keys: list[str], default: int = 0) -> int:
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return default


def find_pdf_match(title: str, pdf_files: list[str]) -> tuple[Optional[str], int, str]:
    """Find best PDF match for a title using exact-normalized then fuzzy matching."""
    if not isinstance(title, str) or not title.strip():
        return None, 0, "empty_title"

    normalized_title = _normalize_for_match(title)
    stem_map = {f: _normalize_for_match(Path(f).stem) for f in pdf_files}
    exact = [name for name, stem in stem_map.items() if stem == normalized_title]
    if len(exact) == 1:
        return exact[0], 100, "exact_normalized"
    if len(exact) > 1:
        return None, 100, "ambiguous_exact"

    if not pdf_files:
        return None, 0, "no_pdfs"

    match = process.extractOne(query=title, choices=pdf_files, scorer=fuzz.token_set_ratio)
    if not match:
        return None, 0, "no_candidates"

    filename, score = str(match[0]), int(match[1])
    if score < MATCH_THRESHOLD:
        return None, score, f"score_below_threshold({score}<{MATCH_THRESHOLD})"
    return filename, score, "fuzzy_token_set"


def _extract_intro(full_text: str, text_lower: str) -> str:
    intro = _INTRO_PATTERN.search(text_lower)
    if not intro:
        return ""

    start_idx = intro.end()
    end_idx = len(text_lower)
    for pattern in _INTRO_STOP_PATTERNS:
        stop = pattern.search(text_lower, pos=start_idx)
        if stop and stop.start() < end_idx:
            end_idx = stop.start()
    return clean_text(full_text[start_idx:end_idx])


def _extract_conclusion(full_text: str, text_lower: str) -> str:
    matches = list(_CONCL_PATTERN.finditer(text_lower))
    if not matches:
        return ""

    halfway = len(text_lower) * 0.5
    start_match = next((m for m in matches if m.start() >= halfway), matches[-1])
    start_idx = start_match.end()

    ref_match = _REFERENCES_PATTERN.search(text_lower, pos=start_idx)
    end_idx = ref_match.start() if ref_match else len(text_lower)
    return clean_text(full_text[start_idx:end_idx])


def extract_sections(pdf_path: str) -> tuple[str, int, int]:
    """Extract introduction and conclusion/discussion; return combined text + section sizes."""
    try:
        doc = fitz.open(pdf_path)
        full_text = "".join(page.get_text() for page in doc)
        doc.close()
    except Exception as exc:
        print(f"Error reading {pdf_path}: {exc}")
        return "", 0, 0

    text_lower = full_text.lower()
    intro_text = _extract_intro(full_text, text_lower)
    concl_text = _extract_conclusion(full_text, text_lower)

    combined = (
        f"--- INTRODUCTION ---\n{intro_text}\n\n"
        f"--- CONCLUSION/DISCUSSION ---\n{concl_text}"
    )
    return combined, len(intro_text), len(concl_text)


def _build_chunk_id(filename: str, chunk_index: int, chunk_text: str) -> str:
    stem = _normalize_for_match(Path(filename).stem).replace(" ", "-")
    digest = hashlib.sha1(f"{filename}|{chunk_index}|{chunk_text}".encode("utf-8")).hexdigest()[:16]
    return f"{stem}-{chunk_index:04d}-{digest}"


def main():
    load_dotenv(dotenv_path=get_env_file())
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("Error: GOOGLE_API_KEY not found in environment.")
        print("Add GOOGLE_API_KEY=your-google-api-key-here to your .env file.")
        return

    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return

    if not os.path.exists(PDF_SOURCE_DIR):
        print(f"Error: {PDF_SOURCE_DIR} not found.")
        return

    # Keep this experiment deterministic and idempotent like by_type.
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)

    df = pd.read_csv(CSV_PATH)
    pdf_files = [f for f in os.listdir(PDF_SOURCE_DIR) if f.lower().endswith(".pdf")]

    all_chunks: list[dict] = []
    seen_chunk_ids: set[str] = set()
    seen_sources: set[str] = set()
    stats = Counter()

    print(f"Using index CSV: {CSV_PATH}")
    print(f"Index contains {len(df)} papers.")
    print(f"Found {len(pdf_files)} PDFs in {PDF_SOURCE_DIR}.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    for idx, row in df.iterrows():
        title = _pick_text(row, ["paper_title", "title", "Paper Title"], default="Untitled")
        paper_type = _pick_text(row, ["paper_type", "Paper Type"], default="Unknown")
        category = _pick_text(row, ["category", "Category (The Folder)"], default="General")
        cluster = _pick_text(row, ["cluster", "Cluster"])
        mechanism = _pick_text(row, ["main_mechanism", "Main Mechanism (Tags)"])
        source_pdf_hint = _pick_text(row, ["source_pdf", "Matched PDF", "source", "filename"])

        print(f"\n[{idx + 1}/{len(df)}] Processing: {title[:50]}...")

        if source_pdf_hint and source_pdf_hint in pdf_files:
            matched_filename = source_pdf_hint
            match_score = _pick_int(row, ["match_score", "Match Score"], default=100)
            match_method = _pick_text(
                row,
                ["match_method", "Match Method"],
                default="provided_source",
            )
        else:
            matched_filename, match_score, match_method = find_pdf_match(title, pdf_files)
        if not matched_filename:
            print(f"  x PDF not found ({match_method})")
            stats["missing_match"] += 1
            continue

        if matched_filename in seen_sources:
            print(f"  x Skipping duplicate source mapping for '{matched_filename}'.")
            stats["duplicate_source_rows"] += 1
            continue
        seen_sources.add(matched_filename)

        pdf_path = os.path.join(PDF_SOURCE_DIR, matched_filename)
        extracted_text, intro_len, concl_len = extract_sections(pdf_path)

        print(f"  > Match: {matched_filename} (score={match_score}, method={match_method})")
        print(f"  > Sections: intro={intro_len} chars, conclusion={concl_len} chars")

        if len(clean_text(extracted_text)) < MIN_EXTRACTED_TEXT_CHARS:
            print("  x Extraction too short, skipping.")
            stats["short_extraction"] += 1
            continue

        chunks = splitter.split_text(extracted_text)
        if not chunks:
            print("  x No chunks generated, skipping.")
            stats["no_chunks"] += 1
            continue

        base_metadata = {
            "filename": matched_filename,
            "source": matched_filename,
            "paper_type": paper_type,
            "category": category,
            "cluster": cluster,
            "main_mechanism": mechanism,
            "title": title,
            "match_score": match_score,
            "match_method": match_method,
            "extracted_intro_chars": intro_len,
            "extracted_conclusion_chars": concl_len,
        }

        for chunk_idx, chunk_text in enumerate(chunks):
            cleaned = clean_text(chunk_text)
            if not cleaned:
                continue
            chunk_id = _build_chunk_id(matched_filename, chunk_idx, cleaned)
            if chunk_id in seen_chunk_ids:
                stats["duplicate_chunks"] += 1
                continue
            seen_chunk_ids.add(chunk_id)
            metadata = {
                **base_metadata,
                "chunk_index": chunk_idx,
                "total_chunks": len(chunks),
            }
            all_chunks.append(
                {
                    "id": chunk_id,
                    "text": cleaned,
                    "metadata": metadata,
                }
            )

        stats["processed_papers"] += 1
        stats["chunks_created"] += len(chunks)
        print(f"  > Prepared {len(chunks)} chunks.")

    if not all_chunks:
        print("No documents processed. Exiting.")
        return

    print(f"\nEmbedding and storing to {CHROMA_DIR} with {EMBEDDING_MODEL}...")
    embeddings = GeminiGenAIEmbeddings(
        api_key=google_api_key,
        model=EMBEDDING_MODEL,
        task_type="RETRIEVAL_DOCUMENT",
    )

    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
    )
    vectorstore.add_texts(
        texts=[item["text"] for item in all_chunks],
        metadatas=[item["metadata"] for item in all_chunks],
        ids=[item["id"] for item in all_chunks],
    )

    print("\nINGESTION SUMMARY")
    print(f"  Papers in index: {len(df)}")
    print(f"  Papers processed: {stats['processed_papers']}")
    print(f"  Missing/low-confidence matches: {stats['missing_match']}")
    print(f"  Duplicate source rows skipped: {stats['duplicate_source_rows']}")
    print(f"  Duplicate chunks skipped: {stats['duplicate_chunks']}")
    print(f"  Short extractions: {stats['short_extraction']}")
    print(f"  No chunks: {stats['no_chunks']}")
    print(f"  Total chunks stored: {len(all_chunks)}")
    print("INGESTION COMPLETE.")


if __name__ == "__main__":
    main()
