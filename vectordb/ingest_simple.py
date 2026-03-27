"""
VectorDB Ingestion - Native PDF Embedding with Gemini Embedding 2.

Embeds research PDFs natively using gemini-embedding-2-preview for superior
retrieval quality, while also extracting text for downstream LLM consumption.
Uses paper_map.csv for category metadata mapping.
"""

import os
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF
import pandas as pd
import chromadb
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import config

# Constants
RESEARCH_DIR = Path(__file__).parent / "research_papers"
CSV_PATH = Path(__file__).parent / "paper_map.csv"
CHROMA_DIR = Path(__file__).parent / "chroma_db"
MAX_PDF_PAGES = 6  # Gemini API limit for native PDF embedding
RATE_LIMIT_DELAY = 0.5  # seconds between API calls


def get_category_mapping(csv_path: Path) -> dict:
    """Load filename -> category mapping from paper_map.csv."""
    df = pd.read_csv(csv_path)
    df["filename"] = df["filename"].str.strip()
    df["category"] = df["category"].str.strip()
    return dict(zip(df["filename"], df["category"]))


def split_pdf_into_chunks(pdf_path: Path, max_pages: int = MAX_PDF_PAGES) -> list:
    """Split a PDF into chunks of at most max_pages pages.

    Returns list of (chunk_bytes, extracted_text) tuples.
    """
    chunks = []
    try:
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)

        for start_idx in range(0, total_pages, max_pages):
            end_idx = min(start_idx + max_pages, total_pages)

            # Create PDF chunk bytes
            chunk_doc = fitz.open()
            chunk_doc.insert_pdf(doc, from_page=start_idx, to_page=end_idx - 1)
            chunk_bytes = chunk_doc.tobytes()
            chunk_doc.close()

            # Extract text from same pages for LLM consumption
            text_parts = []
            for page_idx in range(start_idx, end_idx):
                page_text = doc[page_idx].get_text()
                if page_text.strip():
                    text_parts.append(page_text.strip())
            extracted_text = "\n\n".join(text_parts)

            chunks.append((chunk_bytes, extracted_text))

        doc.close()
    except Exception as e:
        print(f"  Error splitting PDF {pdf_path.name}: {e}")

    return chunks


def embed_pdf_chunk(client: genai.Client, pdf_bytes: bytes) -> list:
    """Embed a PDF chunk natively using Gemini Embedding 2."""
    result = client.models.embed_content(
        model=config.EMBEDDING_MODEL,
        contents=[
            types.Part.from_bytes(
                data=pdf_bytes,
                mime_type="application/pdf",
            ),
        ],
    )
    return result.embeddings[0].values


def main():
    # Load API key
    load_dotenv()
    api_key = config.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing.")

    print("=" * 60)
    print("VectorDB Ingestion - Native PDF Embedding")
    print(f"Model: {config.EMBEDDING_MODEL}")
    print(f"Collection: {config.VECTORDB_COLLECTION}")
    print("=" * 60)

    # Load category mapping
    category_map = get_category_mapping(CSV_PATH)
    print(f"\nLoaded {len(category_map)} category mappings from paper_map.csv")

    # Discover PDFs
    pdf_files = sorted(RESEARCH_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {RESEARCH_DIR}")
        return
    print(f"Found {len(pdf_files)} PDFs in {RESEARCH_DIR.name}/")

    # Initialize ChromaDB
    print(f"\nInitializing ChromaDB at {CHROMA_DIR}...")
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        chroma_client.delete_collection(config.VECTORDB_COLLECTION)
    except Exception:
        pass
    collection = chroma_client.create_collection(
        name=config.VECTORDB_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    # Initialize Gemini client
    genai_client = genai.Client(api_key=api_key)

    # Process each PDF
    total_chunks = 0
    failed_chunks = 0

    for pdf_idx, pdf_path in enumerate(pdf_files):
        category = category_map.get(pdf_path.name, "Unknown")
        if category == "Unknown":
            print(f"\n[{pdf_idx+1}/{len(pdf_files)}] WARNING: No category for {pdf_path.name}, using 'Unknown'")
        else:
            print(f"\n[{pdf_idx+1}/{len(pdf_files)}] {pdf_path.name} [{category}]")

        chunks = split_pdf_into_chunks(pdf_path)
        if not chunks:
            print(f"  -> Failed to read or split PDF")
            continue

        for chunk_idx, (chunk_bytes, extracted_text) in enumerate(chunks):
            try:
                # Get native PDF embedding from Gemini
                embedding = embed_pdf_chunk(genai_client, chunk_bytes)

                # Sanitize filename for ID
                safe_name = pdf_path.stem.replace(" ", "_").replace(",", "")[:50]
                doc_id = f"pdf_{safe_name}_chunk_{chunk_idx}"

                # Store with both embedding and extracted text
                collection.add(
                    embeddings=[embedding],
                    documents=[extracted_text if extracted_text else f"PDF chunk {chunk_idx+1}/{len(chunks)} of {pdf_path.name}"],
                    metadatas=[{
                        "filename": pdf_path.name,
                        "category": category,
                        "chunk_idx": chunk_idx,
                        "retrieval_source": "gemini_native",
                    }],
                    ids=[doc_id],
                )

                total_chunks += 1
                print(f"  -> Chunk {chunk_idx+1}/{len(chunks)}: {len(embedding)}-dim vector, {len(extracted_text)} chars text")

                # Rate limiting
                time.sleep(RATE_LIMIT_DELAY)

            except Exception as e:
                failed_chunks += 1
                print(f"  -> FAILED chunk {chunk_idx+1}/{len(chunks)}: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("INGESTION COMPLETE!")
    print("=" * 60)
    print(f"  Total chunks stored: {total_chunks}")
    print(f"  Failed chunks: {failed_chunks}")
    print(f"  Collection: {config.VECTORDB_COLLECTION}")
    print(f"  ChromaDB path: {CHROMA_DIR}")

    # Verify
    count = collection.count()
    print(f"  Verified collection count: {count}")


if __name__ == "__main__":
    main()
