import hashlib
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import pandas as pd
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from thefuzz import fuzz, process

from mindful_rag.config import INDEX_CSV, PDF_DIR, get_env_file, get_experiment
from mindful_rag.embeddings import create_document_embeddings

# Configuration
EXPERIMENT = get_experiment("by_type")
DEFAULT_OUTPUT_INDEX_CSV = INDEX_CSV.parent / "research_index_clean.csv"
INPUT_CSV_PATH = os.getenv("BY_TYPE_INPUT_CSV", str(INDEX_CSV))
OUTPUT_CSV_PATH = os.getenv("BY_TYPE_OUTPUT_CSV", str(DEFAULT_OUTPUT_INDEX_CSV))
PDF_SOURCE_DIR = str(PDF_DIR)
CHROMA_DIR = str(EXPERIMENT.chroma_dir)
COLLECTION_NAME = EXPERIMENT.collection_name
EMBEDDING_MODEL = "gemini-embedding-001"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
MIN_EXTRACTED_TEXT_CHARS = 200
MATCH_THRESHOLD = 75
WRITE_VECTORS = os.getenv("BY_TYPE_WRITE_VECTORS", "1").strip().lower() not in {"0", "false", "no"}
ALLOW_EMBEDDING_FALLBACK = (
    os.getenv("BY_TYPE_ALLOW_EMBEDDING_FALLBACK", "0").strip().lower() not in {"0", "false", "no"}
)

_HEADING_CACHE: dict[str, re.Pattern[str]] = {}
_TYPE_PROTOCOL = {"protocol"}
_TYPE_META = {"meta-analysis"}
_TYPE_CPG = {"clinical practice guideline", "cpg", "theory"}
_REF_HEADINGS = ["references", "bibliography", "works cited"]


def _normalize_for_match(text: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(collapsed.split())


def _normalize_paper_type(paper_type: str) -> str:
    return " ".join(str(paper_type).strip().lower().split())


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _heading_pattern(label: str) -> re.Pattern[str]:
    key = label.lower()
    cached = _HEADING_CACHE.get(key)
    if cached is not None:
        return cached
    pattern = re.compile(
        rf"(?:^|\n)\s*(?:\d+(?:\.\d+)*\.?\s*)?{re.escape(key)}(?:[:.\s]|$)",
        re.IGNORECASE,
    )
    _HEADING_CACHE[key] = pattern
    return pattern


def _find_heading(text_lower: str, labels: list[str], start_pos: int = 0) -> int:
    best_idx = -1
    for label in labels:
        match = _heading_pattern(label).search(text_lower, pos=max(0, start_pos))
        idx = match.start() if match else -1
        if idx == -1:
            idx = text_lower.find(label.lower(), max(0, start_pos))
        if idx != -1 and (best_idx == -1 or idx < best_idx):
            best_idx = idx
    return best_idx


def _trim_references(full_text: str) -> str:
    lower = full_text.lower()
    ref_idx = _find_heading(lower, _REF_HEADINGS)
    if ref_idx == -1:
        return full_text
    return full_text[:ref_idx]


def _extract_range(full_text: str, start_labels: list[str], end_labels: list[str], start_pos: int = 0) -> str:
    lower = full_text.lower()
    start_idx = _find_heading(lower, start_labels, start_pos=start_pos)
    if start_idx == -1:
        return ""
    end_idx = _find_heading(lower, end_labels, start_pos=start_idx + 1)
    if end_idx == -1:
        end_idx = len(full_text)
    if end_idx <= start_idx:
        return ""
    return _clean_text(full_text[start_idx:end_idx])


def extract_text_by_type(full_text: str, paper_type: str) -> str:
    """Extract relevant text from a PDF based on paper type."""
    text = _trim_references(full_text)
    text_lower = text.lower()
    paper_type_norm = _normalize_paper_type(paper_type)

    if paper_type_norm in _TYPE_PROTOCOL:
        # Keep the implementation/method details and stop before findings synthesis.
        return _extract_range(
            text,
            start_labels=["methods", "method", "intervention", "protocol"],
            end_labels=["results", "discussion", "findings", "conclusion"],
        )

    if paper_type_norm in _TYPE_META:
        extracted_parts: list[str] = []

        abstract_text = _extract_range(
            text,
            start_labels=["abstract"],
            end_labels=["introduction", "background", "methods", "materials and methods"],
        )
        if abstract_text:
            extracted_parts.append(abstract_text)

        results_idx = _find_heading(text_lower, ["results"])
        concl_text = _extract_range(
            text,
            start_labels=["conclusion", "conclusions", "discussion"],
            end_labels=_REF_HEADINGS,
            start_pos=max(0, results_idx),
        )
        if concl_text:
            extracted_parts.append(concl_text)

        return "\n\n".join(part for part in extracted_parts if part)

    if paper_type_norm in _TYPE_CPG:
        extracted_parts = []
        intro_text = _extract_range(
            text,
            start_labels=["introduction"],
            end_labels=["methods", "method", "materials", "background", "related work"],
        )
        if intro_text:
            extracted_parts.append(intro_text)

        summary_text = _extract_range(
            text,
            start_labels=[
                "general discussion",
                "summary of recommendations",
                "discussion",
                "summary",
                "conclusion",
                "conclusions",
            ],
            end_labels=_REF_HEADINGS,
        )
        if summary_text:
            extracted_parts.append(summary_text)

        return "\n\n".join(part for part in extracted_parts if part)

    return ""


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


def extract_full_text(pdf_path: str) -> str:
    """Extract full PDF text before type-specific filtering."""
    try:
        doc = fitz.open(pdf_path)
        full_text = "".join(page.get_text() for page in doc)
        doc.close()
        return full_text
    except Exception as exc:
        print(f"Failed to load PDF {pdf_path}: {exc}")
        return ""


def _build_chunk_id(filename: str, chunk_index: int, chunk_text: str) -> str:
    stem = _normalize_for_match(Path(filename).stem).replace(" ", "-")
    digest = hashlib.sha1(f"{filename}|{chunk_index}|{chunk_text}".encode("utf-8")).hexdigest()[:16]
    return f"{stem}-{chunk_index:04d}-{digest}"


def _build_output_row(
    row: pd.Series,
    fallback_id: int,
    match_score: int,
    match_method: str,
    relevant_info: str,
) -> dict[str, object]:
    intro_chars_raw = _pick_text(row, ["intro_chars"])
    concl_chars_raw = _pick_text(row, ["conclusion_chars"])

    return {
        "id": _pick_text(row, ["id", "ID"], default=str(fallback_id)),
        "paper_title": _pick_text(row, ["paper_title", "title", "Paper Title"], default="Untitled"),
        "cluster": _pick_text(row, ["cluster", "Cluster"]),
        "category": _pick_text(row, ["category", "Category (The Folder)"]),
        "paper_type": _pick_text(row, ["paper_type", "Paper Type"], default="Unknown"),
        "main_mechanism": _pick_text(row, ["main_mechanism", "Main Mechanism (Tags)"]),
        "filename_link": _pick_text(row, ["filename_link", "Filename/Link"]),
        "match_score": match_score,
        "match_method": match_method,
        "relevant_info": relevant_info,
        "intro_concl": _pick_text(row, ["intro_concl"]),
        "intro_chars": intro_chars_raw if intro_chars_raw else "",
        "conclusion_chars": concl_chars_raw if concl_chars_raw else "",
    }


def ingest():
    load_dotenv(dotenv_path=get_env_file())
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if WRITE_VECTORS and not google_api_key and not ALLOW_EMBEDDING_FALLBACK:
        print("Error: GOOGLE_API_KEY not found in environment.")
        print("Add GOOGLE_API_KEY to your .env or enable BY_TYPE_ALLOW_EMBEDDING_FALLBACK=1.")
        return

    if not os.path.exists(INPUT_CSV_PATH):
        print(f"Error: Input CSV not found at {INPUT_CSV_PATH}")
        return

    if not os.path.exists(PDF_SOURCE_DIR):
        print(f"Error: PDF folder not found at {PDF_SOURCE_DIR}")
        return

    df = pd.read_csv(INPUT_CSV_PATH)
    pdf_files = [f for f in os.listdir(PDF_SOURCE_DIR) if f.lower().endswith(".pdf")]

    print(f"Using input CSV: {INPUT_CSV_PATH}")
    print(f"Will write output CSV: {OUTPUT_CSV_PATH}")
    print(f"Index contains {len(df)} papers.")
    print(f"Found {len(pdf_files)} PDFs in {PDF_SOURCE_DIR}.")

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    output_rows: list[dict[str, object]] = []
    all_chunks: list[dict[str, object]] = []
    seen_chunk_ids: set[str] = set()
    vectorized_sources: set[str] = set()
    source_cache: dict[str, dict[str, object]] = {}
    stats = Counter()

    for idx, row in df.iterrows():
        title = _pick_text(row, ["paper_title", "title", "Paper Title"], default="Untitled")
        paper_type = _pick_text(row, ["paper_type", "Paper Type"], default="Unknown")
        category = _pick_text(row, ["category", "Category (The Folder)"], default="General")
        cluster = _pick_text(row, ["cluster", "Cluster"])
        mechanism = _pick_text(row, ["main_mechanism", "Main Mechanism (Tags)"])
        existing_relevant = _pick_text(row, ["relevant_info"])

        print(f"\n[{idx + 1}/{len(df)}] Processing: {title[:50]}...")

        matched_filename, match_score, match_method = find_pdf_match(title, pdf_files)

        if not matched_filename:
            print(f"  x PDF not found ({match_method})")
            stats["missing_match"] += 1
            output_rows.append(
                _build_output_row(
                    row=row,
                    fallback_id=idx + 1,
                    match_score=match_score,
                    match_method=match_method,
                    relevant_info=existing_relevant,
                )
            )
            continue

        print(f"  > Match: {matched_filename} (score={match_score}, method={match_method})")

        cached = source_cache.get(matched_filename)
        if cached is not None:
            extracted_text = str(cached.get("relevant_info", ""))
            extracted_len = int(cached.get("extracted_chars", 0))
            stats["reused_source_rows"] += 1
        else:
            pdf_path = os.path.join(PDF_SOURCE_DIR, matched_filename)
            full_text = extract_full_text(pdf_path)
            if not full_text:
                print("  x Empty PDF text, skipping extraction.")
                stats["empty_pdf_text"] += 1
                output_rows.append(
                    _build_output_row(
                        row=row,
                        fallback_id=idx + 1,
                        match_score=match_score,
                        match_method=match_method,
                        relevant_info=existing_relevant,
                    )
                )
                continue

            extracted_text = _clean_text(extract_text_by_type(full_text, paper_type))
            extracted_len = len(extracted_text)
            source_cache[matched_filename] = {
                "relevant_info": extracted_text,
                "extracted_chars": extracted_len,
            }

        print(f"  > Relevant info length: {extracted_len} chars")

        if extracted_len < MIN_EXTRACTED_TEXT_CHARS:
            print("  x Extraction too short, keeping existing relevant_info for this row.")
            stats["short_extraction"] += 1
            output_rows.append(
                _build_output_row(
                    row=row,
                    fallback_id=idx + 1,
                    match_score=match_score,
                    match_method=match_method,
                    relevant_info=existing_relevant,
                )
            )
            continue

        output_rows.append(
            _build_output_row(
                row=row,
                fallback_id=idx + 1,
                match_score=match_score,
                match_method=match_method,
                relevant_info=extracted_text,
            )
        )
        stats["relevant_info_populated"] += 1

        if matched_filename in vectorized_sources:
            continue
        vectorized_sources.add(matched_filename)

        chunks = splitter.split_text(extracted_text)
        if not chunks:
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
            "extracted_chars": extracted_len,
            "extraction_strategy": "by_type",
        }

        for chunk_idx, chunk_text in enumerate(chunks):
            cleaned_chunk = _clean_text(chunk_text)
            if not cleaned_chunk:
                continue
            chunk_id = _build_chunk_id(matched_filename, chunk_idx, cleaned_chunk)
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
        stats["processed_papers"] += 1
        stats["chunks_created"] += len(chunks)
        print(f"  > Prepared {len(chunks)} chunks.")

    output_df = pd.DataFrame(output_rows)
    output_df.to_csv(OUTPUT_CSV_PATH, index=False)
    print(f"\nWrote cleaned index with relevant_info to: {OUTPUT_CSV_PATH}")

    if WRITE_VECTORS:
        if os.path.exists(CHROMA_DIR):
            shutil.rmtree(CHROMA_DIR)

        if all_chunks:
            print(f"\nEmbedding and storing to {CHROMA_DIR} with {EMBEDDING_MODEL}...")
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
            vectorstore.add_texts(
                texts=[item["text"] for item in all_chunks],
                metadatas=[item["metadata"] for item in all_chunks],
                ids=[item["id"] for item in all_chunks],
            )
            print(f"  -> Embedding backend used: {getattr(embeddings, 'backend_name', 'unknown')}")
        else:
            print("\nNo extracted chunks available; skipping vector store write.")

    print("\nINGESTION SUMMARY")
    print(f"  Papers in index: {len(df)}")
    print(f"  Papers with populated relevant_info: {stats['relevant_info_populated']}")
    print(f"  Papers used for vectors: {stats['processed_papers']}")
    print(f"  Missing matches: {stats['missing_match']}")
    print(f"  Empty PDF text: {stats['empty_pdf_text']}")
    print(f"  Short extractions: {stats['short_extraction']}")
    print(f"  Reused rows for duplicate matched source: {stats['reused_source_rows']}")
    print(f"  Duplicate chunks skipped: {stats['duplicate_chunks']}")
    print(f"  Total chunks stored: {len(all_chunks)}")
    print("INGESTION COMPLETE.")


def main():
    ingest()


if __name__ == "__main__":
    main()
