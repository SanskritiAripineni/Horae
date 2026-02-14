"""
Ablation Study Ingestion Script: ingest_intro_concl.py
------------------------------------------------------
Strictly extracts 'Introduction' and 'Conclusion/Discussion' sections from PDFs.
Filters out everything else (Methods, Results, etc.).
Uses fuzzy matching to link CSV titles to PDF filenames.
"""

import os
import re
from typing import Optional
import pandas as pd
import fitz  # pymupdf
from dotenv import load_dotenv
from thefuzz import process
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from src.mindful_rag.config import INDEX_CSV, PDF_DIR, ROOT_DIR, get_experiment

# Configuration
EXPERIMENT = get_experiment("intro_concl")
CSV_PATH = str(INDEX_CSV)
PDF_SOURCE_DIR = str(PDF_DIR)
CHROMA_DIR = str(EXPERIMENT.chroma_dir)
COLLECTION_NAME = EXPERIMENT.collection_name
EMBEDDING_MODEL = "models/gemini-embedding-001"

def clean_text(text: str) -> str:
    """Basic text cleaning."""
    return re.sub(r'\s+', ' ', text).strip()

def find_pdf_path(title: str, pdf_files: list[str]) -> Optional[str]:
    """Fuzzy match paper title to PDF filenames."""
    if not isinstance(title, str) or not title.strip():
        return None
    
    # Simple direct match first
    # Fuzzy match
    match, score = process.extractOne(title, pdf_files)
    if score > 80:  # Threshold
        return os.path.join(PDF_SOURCE_DIR, match)
    return None

def extract_sections(pdf_path: str) -> str:
    """
    Surgical extraction of Introduction and Conclusion.
    Returns combined text string.
    """
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        return ""

    # Normalize roughly for searching headers
    # We keep original text for content, but use lower case for finding indices
    text_lower = full_text.lower()
    
    # --- FIND INTRODUCTION ---
    # Look for "introduction" on its own line or with small number followed by it
    intro_matches = list(re.finditer(r'(?:^|\n)(?:\d\.?\s*)?introduction(?:[:\.]|\s|$)', text_lower))
    
    intro_text = ""
    if intro_matches:
        start_idx = intro_matches[0].end()
        
        # heuristic for end of introduction: look for next common section
        # "2. Methods", "Methods", "Related Work", "Background", "Literature Review"
        stop_patterns = [
            r'(?:^|\n)(?:\d\.?\s*)?methods',
            r'(?:^|\n)(?:\d\.?\s*)?related work',
            r'(?:^|\n)(?:\d\.?\s*)?literature review',
            r'(?:^|\n)(?:\d\.?\s*)?background',
            r'(?:^|\n)(?:\d\.?\s*)?materials? and methods'
        ]
        
        end_idx = len(text_lower)
        for pat in stop_patterns:
            match = re.search(pat, text_lower[start_idx:])
            if match:
                # found a stopping section
                end_idx = start_idx + match.start()
                break
        
        intro_text = full_text[start_idx:end_idx]
        print(f"  > Extracted Introduction ({len(intro_text)} chars)")
    else:
        print("  ! No Introduction found")

    # --- FIND CONCLUSION / DISCUSSION ---
    # Look for Conclusion or Discussion
    # We want to capture until References
    concl_matches = list(re.finditer(r'(?:^|\n)(?:\d\.?\s*)?(?:conclusion|discussion)s?(?:[:\.]|\s|$)', text_lower))
    
    concl_text = ""
    if concl_matches:
        # If multiple, take the last one likely (often there is a Discussion AND Conclusion, we want both if possible, or start from the first one found after the middle)
        # To be safe, let's take the *last* major header match that isn't the abstract or something.
        # Actually, let's find the first instance that appears in the latter half of the doc?
        # Or just find the first match after the intro?
        
        # Let's try to find "Conclusion" or "Discussion" that is NOT followed by specific text indicating it's part of a sentence
        # The regex above handles line starts, so it should be a header.
        
        # We pick the match that is closest to the end, but before references
        valid_matches = [m for m in concl_matches if m.start() > len(text_lower) * 0.5] # Must be in second half
        
        if valid_matches:
            start_idx = valid_matches[0].end() # Start from the first valid one found in 2nd half
            
            # Find References to stop
            ref_match = re.search(r'(?:^|\n)(?:\d\.?\s*)?(?:references|bibliography|works cited)', text_lower[start_idx:])
            
            end_idx = len(text_lower)
            if ref_match:
                end_idx = start_idx + ref_match.start()
            
            concl_text = full_text[start_idx:end_idx]
            print(f"  > Extracted Conclusion/Discussion ({len(concl_text)} chars)")
        else:
            print("  ! No Conclusion/Discussion found in 2nd half")
    else:
        print("  ! No Conclusion/Discussion found")

    combined = f"--- INTRODUCTION ---\n{clean_text(intro_text)}\n\n--- CONCLUSION/DISCUSSION ---\n{clean_text(concl_text)}"
    return combined

def main():
    load_dotenv(dotenv_path=ROOT_DIR / ".env")
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

    # Load CSV
    df = pd.read_csv(CSV_PATH)
    pdf_files = [f for f in os.listdir(PDF_SOURCE_DIR) if f.lower().endswith('.pdf')]
    
    documents = []
    
    print(f"Index contains {len(df)} papers.")
    print(f"Found {len(pdf_files)} PDFs in {PDF_SOURCE_DIR}.")
    
    for idx, row in df.iterrows():
        title = row.get('Paper Title', '')  # Adjust column name if needed
        paper_type = row.get('Paper Type', 'Unknown')
        category = row.get('Category (The Folder)', 'General')
        
        print(f"\n[{idx+1}/{len(df)}] Processing: {title[:50]}...")
        
        pdf_path = find_pdf_path(title, pdf_files)
        
        if not pdf_path:
            print("  x PDF not found (fuzzy match failed)")
            continue
            
        # Extract content
        extracted_text = extract_sections(pdf_path)
        
        if len(extracted_text) < 200: # Threshold for "mostly empty"
            print("  x Extraction too short, skipping.")
            continue
            
        # Create Document
        doc = Document(
            page_content=extracted_text,
            metadata={
                'filename': os.path.basename(pdf_path),
                'paper_type': paper_type,
                'category': category,
                'title': title
            }
        )
        documents.append(doc)

    if not documents:
        print("No documents processed. Exiting.")
        return

    # Chunking
    print("\nSplitting text...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    docs = text_splitter.split_documents(documents)
    print(f"Created {len(docs)} chunks.")

    # Embedding
    print(f"Embedding and storing to {CHROMA_DIR} with {EMBEDDING_MODEL}...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=google_api_key,
        task_type="retrieval_document"
    )
    
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION_NAME
    )
    
    print("INGESTION COMPLETE.")

if __name__ == "__main__":
    main()
