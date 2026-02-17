import os
import shutil
from typing import Optional

import pandas as pd
import fitz  # PyMuPDF
from dotenv import load_dotenv
from thefuzz import process
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from mindful_rag.config import INDEX_CSV, PDF_DIR, get_env_file, get_experiment

# --- Configuration ---
EXPERIMENT = get_experiment("by_type")
CSV_PATH = str(INDEX_CSV)
PDF_SOURCE_DIR = str(PDF_DIR)
DB_DIR = str(EXPERIMENT.chroma_dir)
COLLECTION_NAME = EXPERIMENT.collection_name
EMBEDDING_MODEL = "models/gemini-embedding-001"


def get_closest_file(target_title: str, file_list: list[str]) -> tuple[Optional[str], int]:
    """
    Find the closest filename in file_list to target_title using fuzzy matching.
    Returns (filename, score).
    """
    if not file_list:
        return None, 0

    match = process.extractOne(target_title, file_list)
    if not match:
        return None, 0

    return match[0], match[1]


def extract_text_by_type(text: str, paper_type: str) -> str:
    """Extract text using the paper-type-specific rules."""
    text_lower = text.lower()

    # Safety rule: stop at references/bibliography
    for safety_word in ["references", "bibliography"]:
        safety_idx = text_lower.find(safety_word)
        if safety_idx != -1:
            text = text[:safety_idx]
            text_lower = text_lower[:safety_idx]

    if paper_type == "Protocol":
        start_markers = ["methods", "intervention"]
        end_markers = ["results", "discussion"]

        start_idx = -1
        for marker in start_markers:
            idx = text_lower.find(marker)
            if idx != -1 and (start_idx == -1 or idx < start_idx):
                start_idx = idx

        if start_idx == -1:
            return ""

        end_idx = len(text)
        for marker in end_markers:
            idx = text_lower.find(marker, start_idx)
            if idx != -1 and idx < end_idx:
                end_idx = idx

        return text[start_idx:end_idx]

    if paper_type == "Meta-Analysis":
        extracted_parts = []

        abs_start = text_lower.find("abstract")
        if abs_start != -1:
            abs_end_candidates = ["introduction", "background", "methods"]
            abs_end = len(text)
            for cand in abs_end_candidates:
                idx = text_lower.find(cand, abs_start)
                if idx != -1 and idx < abs_end:
                    abs_end = idx
            extracted_parts.append(text[abs_start:abs_end])

        conc_start = -1
        results_idx = text_lower.find("results")
        for cand in ["conclusion", "discussion"]:
            idx = text_lower.find(cand, results_idx if results_idx != -1 else 0)
            if idx != -1:
                conc_start = idx
                break

        if conc_start != -1:
            extracted_parts.append(text[conc_start:])

        return "\n\n".join(extracted_parts)

    if paper_type in ["Clinical Practice Guideline", "CPG", "Theory"]:
        extracted_parts = []

        intro_start = text_lower.find("introduction")
        if intro_start != -1:
            intro_end_candidates = ["methods", "materials", "background"]
            intro_end = len(text)
            for cand in intro_end_candidates:
                idx = text_lower.find(cand, intro_start)
                if idx != -1 and idx < intro_end:
                    intro_end = idx
            extracted_parts.append(text[intro_start:intro_end])

        disc_start = -1
        for cand in ["general discussion", "summary of recommendations", "discussion", "summary"]:
            idx = text_lower.find(cand)
            if idx != -1:
                disc_start = idx
                if cand in ["general discussion", "summary of recommendations"]:
                    break

        if disc_start != -1:
            extracted_parts.append(text[disc_start:])

        return "\n\n".join(extracted_parts)

    return ""


def extract_full_text(pdf_path: str) -> str:
    """Extract full PDF text before type-specific filtering."""
    try:
        doc = fitz.open(pdf_path)
        full_text = []
        for page in doc:
            full_text.append(page.get_text())
        doc.close()
        return "\n".join(full_text)
    except Exception as exc:
        print(f"Failed to load PDF {pdf_path}: {exc}")
        return ""


def ingest():
    load_dotenv(dotenv_path=get_env_file())
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("Error: GOOGLE_API_KEY not found in environment.")
        print("Add GOOGLE_API_KEY=your-google-api-key-here to your .env file.")
        return

    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV not found at {CSV_PATH}")
        return

    if not os.path.exists(PDF_SOURCE_DIR):
        print(f"Error: PDF folder not found at {PDF_SOURCE_DIR}")
        return

    # Reset vector DB so all vectors are recreated with Gemini embeddings.
    if os.path.exists(DB_DIR):
        shutil.rmtree(DB_DIR)

    df = pd.read_csv(CSV_PATH)
    pdf_files = [f for f in os.listdir(PDF_SOURCE_DIR) if f.lower().endswith(".pdf")]

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    all_documents: list[Document] = []
    count_ingested = 0

    for _, row in df.iterrows():
        title = str(row.get("Paper Title", ""))
        p_type = str(row.get("Paper Type", "")).strip()

        matched_filename, score = get_closest_file(title, pdf_files)
        if score < 60 or not matched_filename:
            print(f"Skipping '{title}': No good match found (Best: {matched_filename}, Score: {score})")
            continue

        pdf_path = os.path.join(PDF_SOURCE_DIR, matched_filename)
        print(f"Processing: '{title}' -> '{matched_filename}' (Score: {score}) | Type: {p_type}")

        full_text = extract_full_text(pdf_path)
        if not full_text:
            continue

        extracted_text = extract_text_by_type(full_text, p_type)
        if not extracted_text or len(extracted_text) < 50:
            print(f"Warning: Low extracted text length for {matched_filename}.")
            continue

        chunks = text_splitter.split_text(extracted_text)
        metadata_base = {
            "paper_type": p_type,
            "category": str(row.get("Category (The Folder)", "")),
            "cluster": str(row.get("Cluster", "")),
            "main_mechanism": str(row.get("Main Mechanism (Tags)", "")),
            "source": matched_filename,
        }

        for chunk_idx, chunk_text in enumerate(chunks):
            chunk_metadata = {
                **metadata_base,
                "chunk_index": chunk_idx,
                "total_chunks": len(chunks),
            }
            all_documents.append(Document(page_content=chunk_text, metadata=chunk_metadata))

        count_ingested += 1
        print(f"  -> Prepared {len(chunks)} chunks.")

    if not all_documents:
        print("\nNo documents to ingest.")
        return

    print(f"\nEmbedding with {EMBEDDING_MODEL} and writing to '{DB_DIR}/'...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=google_api_key,
        task_type="retrieval_document"
    )

    Chroma.from_documents(
        documents=all_documents,
        embedding=embeddings,
        persist_directory=DB_DIR,
        collection_name=COLLECTION_NAME
    )

    print(f"\nFinished. Total papers processed: {count_ingested}")
    print(f"Total chunks ingested: {len(all_documents)}")


if __name__ == "__main__":
    ingest()
