"""Ingest PDFs natively using Gemini Embedding 2 via google-genai."""

import argparse
import io
import os
from pathlib import Path

import fitz  # PyMuPDF - already installed in the project
from chromadb import PersistentClient
from dotenv import load_dotenv
from google import genai
from google.genai import types

from _bootstrap import bootstrap_local_src
bootstrap_local_src()

from mindful_rag.config import PDF_DIR, ROOT_DIR, get_env_file

# Set up constants
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    load_dotenv(get_env_file())
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

DEFAULT_CHROMA_DIR = str(ROOT_DIR / "data" / "evals" / "chroma_gemini_native")
COLLECTION_NAME = "gemini_native_pdfs"
MODEL_NAME = "gemini-embedding-2-preview"
MAX_PDF_PAGES = 6 # current API limit for native PDF embedding

def get_client() -> genai.Client:
    return genai.Client(api_key=GEMINI_API_KEY)

def init_chroma(persist_dir: str):
    client = PersistentClient(path=persist_dir)
    # Delete if exists to start fresh for evaluation
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    return collection

def embed_pdf_chunk(client: genai.Client, pdf_bytes: bytes):
    """Embeds a PDF document chunk (must be <= 6 pages)."""
    result = client.models.embed_content(
        model=MODEL_NAME,
        contents=[
            types.Part.from_bytes(
                data=pdf_bytes,
                mime_type='application/pdf',
            ),
        ]
    )
    return result.embeddings[0].values

def split_pdf_into_chunks(pdf_path: Path, max_pages: int = 6) -> list[bytes]:
    """Splits a PDF into chunks of at most `max_pages` pages and returns them as bytes."""
    chunk_bytes_list = []
    try:
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)
        
        for start_idx in range(0, total_pages, max_pages):
            end_idx = min(start_idx + max_pages, total_pages)
            
            # Create a new PDF with just the pages for this chunk
            chunk_doc = fitz.open()
            chunk_doc.insert_pdf(doc, from_page=start_idx, to_page=end_idx - 1)
            
            chunk_bytes_list.append(chunk_doc.tobytes())
            chunk_doc.close()
            
        doc.close()
    except Exception as e:
        print(f"Error splitting PDF {pdf_path.name}: {e}")
        
    return chunk_bytes_list

def ingest_pdfs(pdf_dir: Path, chroma_collection):
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {pdf_dir}")
        return

    print(f"Found {len(pdf_files)} PDFs. Starting native Gemini ingestion...")
    genai_client = get_client()

    for idx, pdf_path in enumerate(pdf_files):
        print(f"[{idx+1}/{len(pdf_files)}] Processing {pdf_path.name}...")
        
        chunks = split_pdf_into_chunks(pdf_path, MAX_PDF_PAGES)
        if not chunks:
           print(f"  -> Failed to read or split {pdf_path.name}")
           continue
           
        for chunk_idx, chunk_bytes in enumerate(chunks):
            try:
                embedding = embed_pdf_chunk(genai_client, chunk_bytes)
                
                # Store in Chroma (using a unique ID per chunk)
                chroma_collection.add(
                    embeddings=[embedding],
                    documents=[f"Native PDF chunk {chunk_idx+1}/{len(chunks)} of {pdf_path.name}"],
                    metadatas=[{"source": pdf_path.name, "retrieval_source": "gemini_native", "chunk_idx": chunk_idx}],
                    ids=[f"native_pdf_{idx}_chunk_{chunk_idx}"]
                )
                print(f"  -> Success: Stored chunk {chunk_idx+1}/{len(chunks)} ({len(embedding)}-dimensional vector).")
            except Exception as e:
                print(f"  -> Failed to embed chunk {chunk_idx+1} of {pdf_path.name}: {e}")

    print("Ingestion complete!")

def main():
    parser = argparse.ArgumentParser(description="Ingest PDFs natively with Gemini Embedding 2.")
    parser.add_argument("--chroma-dir", default=DEFAULT_CHROMA_DIR, help="Chroma DB path")
    args = parser.parse_args()

    persist_dir = args.chroma_dir
    os.makedirs(persist_dir, exist_ok=True)
    
    if not GEMINI_API_KEY:
         raise ValueError("GEMINI_API_KEY environment variable is missing.")

    collection = init_chroma(persist_dir)
    ingest_pdfs(PDF_DIR, collection)

if __name__ == "__main__":
    main()
