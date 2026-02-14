"""
Raw Baseline Ingestion Script
==============================
Ingests all 61 research papers WITHOUT any filtering for ablation study.
Includes full text with bibliographies, references, and all sections intact.

Author: Sanskriti
Purpose: Establish 'Raw' baseline performance metrics with noisy data
"""

import os
from typing import Optional
import pandas as pd
import fitz  # PyMuPDF
from pathlib import Path
from dotenv import load_dotenv
from thefuzz import process
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# ============================================================================
# CONFIGURATION
# ============================================================================

CSV_PATH = "research_index.csv"
PDF_FOLDER = "research paperss"  # Note: double 's'
CHROMA_DIR = "chroma_db"
COLLECTION_NAME = "wellness_papers"

# Chunking parameters
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100

# Embedding model (same as app.py for consistency)
EMBEDDING_MODEL = "models/gemini-embedding-001"

# ============================================================================
# STEP 1: LOAD CSV AND PDF FILES
# ============================================================================

def load_csv_data(csv_path: str) -> pd.DataFrame:
    """Load research index CSV and filter out rows without titles."""
    print(f"📄 Loading CSV from: {csv_path}")
    df = pd.read_csv(csv_path)
    
    # Remove rows where Paper Title is missing
    df = df.dropna(subset=['Paper Title'])
    
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
# STEP 2: FUZZY MATCHING
# ============================================================================

def match_title_to_filename(title: str, pdf_files: list[str], threshold: int = 60) -> Optional[str]:
    """
    Use fuzzy matching to find the best PDF filename for a given paper title.
    
    Args:
        title: Paper title from CSV
        pdf_files: List of available PDF filenames
        threshold: Minimum similarity score (0-100)
    
    Returns:
        Best matching filename or None if no good match found
    """
    # Remove .pdf extension for better matching
    pdf_names = [f.replace('.pdf', '') for f in pdf_files]
    
    # Find best match
    result = process.extractOne(title, pdf_names)
    
    if result and result[1] >= threshold:
        # Return the original filename with .pdf extension
        matched_name = result[0]
        matched_file = next(f for f in pdf_files if f.replace('.pdf', '') == matched_name)
        return matched_file
    
    return None


# ============================================================================
# STEP 3: RAW TEXT EXTRACTION (NO FILTERING)
# ============================================================================

def extract_full_text_from_pdf(pdf_path: str) -> str:
    """
    Extract COMPLETE raw text from PDF using PyMuPDF.
    NO filtering - includes references, bibliographies, everything.
    
    Args:
        pdf_path: Full path to PDF file
    
    Returns:
        Complete text content of the PDF
    """
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            full_text += page.get_text()
        
        doc.close()
        return full_text.strip()
    
    except Exception as e:
        print(f"⚠️  Error extracting text from {pdf_path}: {e}")
        return ""


# ============================================================================
# STEP 4: CHUNKING
# ============================================================================

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, chunk_overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into chunks using RecursiveCharacterTextSplitter.
    
    Args:
        text: Full text to chunk
        chunk_size: Maximum size of each chunk
        chunk_overlap: Overlap between consecutive chunks
    
    Returns:
        List of text chunks
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunks = splitter.split_text(text)
    return chunks


# ============================================================================
# STEP 5: VECTOR STORE INGESTION
# ============================================================================

def ingest_to_chromadb(documents: list[dict], embeddings) -> Chroma:
    """
    Ingest document chunks into ChromaDB with metadata.
    
    Args:
        documents: List of dicts with 'text' and 'metadata' keys
        embeddings: Gemini embeddings model
    
    Returns:
        ChromaDB vector store instance
    """
    print(f"\n🔄 Ingesting {len(documents)} chunks into ChromaDB...")
    
    # Extract texts and metadatas
    texts = [doc['text'] for doc in documents]
    metadatas = [doc['metadata'] for doc in documents]
    
    # Create vector store
    vectorstore = Chroma.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas,
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION_NAME
    )
    
    print(f"✓ Successfully ingested {len(documents)} chunks")
    return vectorstore


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main ingestion pipeline for raw baseline experiment."""
    load_dotenv()
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
    print("=" * 70)
    
    # Step 1: Load data
    df = load_csv_data(CSV_PATH)
    pdf_files = get_pdf_files(PDF_FOLDER)
    
    # Step 2: Initialize embeddings
    print(f"\n🤖 Loading embedding model: {EMBEDDING_MODEL}")
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=google_api_key,
        task_type="retrieval_document"
    )
    print("✓ Embedding model loaded")
    
    # Step 3: Process each paper
    all_documents = []
    matched_count = 0
    failed_matches = []
    
    print(f"\n📚 Processing {len(df)} papers...")
    print("-" * 70)
    
    for idx, row in df.iterrows():
        paper_title = row['Paper Title']
        paper_type = row.get('Paper Type', 'Unknown')
        category = row.get('Category (The Folder)', 'Unknown')
        cluster = row.get('Cluster', 'Unknown')
        
        # Fuzzy match to find PDF
        matched_filename = match_title_to_filename(paper_title, pdf_files)
        
        if not matched_filename:
            print(f"❌ No match found for: {paper_title[:60]}...")
            failed_matches.append(paper_title)
            continue
        
        # Extract full text
        pdf_path = os.path.join(PDF_FOLDER, matched_filename)
        full_text = extract_full_text_from_pdf(pdf_path)
        
        if not full_text:
            print(f"⚠️  Empty text for: {matched_filename}")
            continue
        
        # Chunk the text
        chunks = chunk_text(full_text)
        
        # Create document entries with metadata
        for chunk_idx, text_chunk in enumerate(chunks):
            metadata = {
                'filename': matched_filename,
                'paper_title': paper_title,
                'paper_type': paper_type,
                'category': category,
                'cluster': cluster,
                'chunk_index': chunk_idx,
                'total_chunks': len(chunks)
            }
            
            all_documents.append({
                'text': text_chunk,
                'metadata': metadata
            })
        
        matched_count += 1
        print(f"✓ [{matched_count}/{len(df)}] {matched_filename} → {len(chunks)} chunks")
    
    # Step 4: Ingest into ChromaDB
    print("\n" + "=" * 70)
    print(f"INGESTION SUMMARY")
    print("=" * 70)
    print(f"Papers matched: {matched_count}/{len(df)}")
    print(f"Total chunks created: {len(all_documents)}")
    print(f"Failed matches: {len(failed_matches)}")
    
    if failed_matches:
        print("\n⚠️  Papers without matches:")
        for title in failed_matches:
            print(f"  - {title}")
    
    if all_documents:
        vectorstore = ingest_to_chromadb(all_documents, embeddings)
        print("\n✅ RAW BASELINE INGESTION COMPLETE!")
        print(f"📊 Vector database saved to: {CHROMA_DIR}")
    else:
        print("\n❌ No documents to ingest!")
    
    print("=" * 70)


if __name__ == "__main__":
    main()
