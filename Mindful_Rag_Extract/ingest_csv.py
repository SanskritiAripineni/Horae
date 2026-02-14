import pandas as pd
import os
import chromadb
from chromadb.config import Settings
from thefuzz import process
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader
import shutil

# --- Configuration ---
CSV_PATH = "research_index.csv"
PDF_DIR = "research paperss" # Note: double 's' as found in directory
DB_DIR = "chroma_db"

# --- ChromaDB Setup ---
if os.path.exists(DB_DIR):
    shutil.rmtree(DB_DIR)  # Clean start for this script test, or remove this if we want to append. 
    # User said "reset my vector database", so a clean start in the script or pre-script is fine. 
    # But for safety in a script, maybe just creating client is enough if we trust the previous `rm -rf`.
    # Let's just create the client. The user already ran the delete command.

client = chromadb.PersistentClient(path=DB_DIR)
collection = client.get_or_create_collection(name="research_papers")

# --- Helper Functions ---

def get_closest_file(target_title, file_list):
    """
    Finds the closest filename in file_list to the target_title using fuzzy matching.
    Returns (filename, score)
    """
    if not file_list:
        return None, 0
    
    # Simple clean of title for better matching maybe? 
    # For now, just raw matching as requested.
    match = process.extractOne(target_title, file_list)
    return match[0], match[1]

def extract_text_by_type(text, paper_type):
    """
    Extracts text based on Paper Type logic.
    """
    text_lower = text.lower()
    
    # Safety Rule: Stop at References/Bibliography
    for safety_word in ["references", "bibliography"]:
        safety_idx = text_lower.find(safety_word)
        if safety_idx != -1:
            text = text[:safety_idx]
            text_lower = text_lower[:safety_idx]
    
    if paper_type == 'Protocol':
        # Goal: Methods -> Results/Discussion
        start_markers = ['methods', 'intervention']
        end_markers = ['results', 'discussion']
        
        start_idx = -1
        for marker in start_markers:
            idx = text_lower.find(marker)
            if idx != -1:
                if start_idx == -1 or idx < start_idx:
                    start_idx = idx
        
        if start_idx == -1: return "" # Section not found
        
        end_idx = len(text)
        for marker in end_markers:
            idx = text_lower.find(marker, start_idx)
            if idx != -1 and idx < end_idx:
                end_idx = idx
                
        return text[start_idx:end_idx]

    elif paper_type == 'Meta-Analysis':
        # Goal: Abstract + Conclusion/Discussion (Skip Results)
        # Strategy: Extract Abstract, then Extract Conclusion/Discussion. Join them.
        
        extracted_parts = []
        
        # Abstract
        abs_start = text_lower.find('abstract')
        if abs_start != -1:
            # Assume Abstract ends at Introduction or just take a reasonable chunk or look for next section?
            # Standard papers: Abstract is at top. Let's find "Introduction" or "Background" as end of abstract.
            # Or just take first 3000 chars if not sure?
            # The prompt says "Extract ONLY the Abstract and the Conclusion".
            # Let's try to find the end of abstract.
            abs_end_candidates = ['introduction', 'background', 'methods']
            abs_end = len(text)
            for cand in abs_end_candidates:
                idx = text_lower.find(cand, abs_start)
                if idx != -1 and idx < abs_end:
                    abs_end = idx
            extracted_parts.append(text[abs_start:abs_end])
        
        # Conclusion/Discussion
        conc_start_candidates = ['conclusion', 'discussion']
        conc_start = -1
        for cand in conc_start_candidates:
            idx = text_lower.rfind(cand) # Search from end might be safer for Conclusion? Or standard find? 
            # "Discussion" usually comes after Results. "Conclusion" comes at end.
            # Let's use standard find but look for the LAST occurrence or just find these sections.
            # Usually Discussion is a specific header.
            # Let's simple find the first occurrence of these words AFTER 'results' if possible, or just find them.
            # Prompt says: "Skip the 'Results' section entirely."
            # So looking for Discussion/Conclusion makes sense.
            idx = text_lower.find(cand) 
            # Issue: 'Discussion' might be mentioned in Abstract.
            # We want the SECTION Discussion.
            # Naive approach: Find last instance? Or find instance after 'results'?
            # Let's try to find occurance after a significant portion of text?
            # Or just extract everything from 'Discussion' or 'Conclusion' to end.
            if idx != -1:
                 # If we have multiple, we want the Main one, likely towards the end.
                 # But extractOne might find the first.
                 # Let's try to find text *after* 'results' if 'results' exists.
                 results_idx = text_lower.find('results')
                 if results_idx != -1:
                     idx_post_res = text_lower.find(cand, results_idx)
                     if idx_post_res != -1:
                         conc_start = idx_post_res
                 
                 if conc_start == -1: # fallback if logic above fails
                     conc_start = idx

        if conc_start != -1:
            extracted_parts.append(text[conc_start:])
            
        return "\n\n".join(extracted_parts)

    elif paper_type in ['Clinical Practice Guideline', 'CPG', 'Theory']:
        # Goal: Introduction + General Discussion/Summary of Recommendations
        extracted_parts = []
        
        # Introduction
        intro_start = text_lower.find('introduction')
        if intro_start != -1:
            # End of intro? Usually 'Methods' or 'Background'.
            intro_end_candidates = ['methods', 'materials', 'background']
            intro_end = len(text)
            for cand in intro_end_candidates:
                idx = text_lower.find(cand, intro_start)
                if idx != -1 and idx < intro_end:
                    intro_end = idx
            extracted_parts.append(text[intro_start:intro_end])
        
        # General Discussion / Summary
        disc_start_candidates = ['general discussion', 'summary of recommendations', 'discussion', 'summary']
        disc_start = -1
        for cand in disc_start_candidates:
             # Similar logic, find 'Discussion' probably towards end or after Methods/Results
             # For CPG, "Summary of Recommendations" might be anywhere?
             # Let's just find the first occurance?
             idx = text_lower.find(cand)
             if idx != -1:
                 # Check if it's not just a passing mention.
                 # For simplicity, let's take it.
                 # If we find "general discussion", prioritize that.
                 if cand == 'general discussion' or cand == 'summary of recommendations':
                     disc_start = idx
                     break # Found a high priority match
                 if disc_start == -1:
                     disc_start = idx
        
        if disc_start != -1:
            extracted_parts.append(text[disc_start:])
            
        return "\n\n".join(extracted_parts)

    return "" # Default if no type matches or logic fails

# --- Main Ingestion Logic ---

def ingest():
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV not found at {CSV_PATH}")
        return

    if not os.path.exists(PDF_DIR):
        print(f"Error: PDF folder not found at {PDF_DIR}")
        return

    df = pd.read_csv(CSV_PATH)
    pdf_files = [f for f in os.listdir(PDF_DIR) if f.lower().endswith('.pdf')]
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    
    count_ingested = 0
    
    for index, row in df.iterrows():
        title = str(row.get('Paper Title', ''))
        p_type = str(row.get('Paper Type', '')).strip()
        
        # Fuzzy Match
        matched_filename, score = get_closest_file(title, pdf_files)
        
        if score < 60: # Threshold to avoid bad matches
            print(f"Skipping '{title}': No good match found (Best: {matched_filename}, Score: {score})")
            continue
            
        pdf_path = os.path.join(PDF_DIR, matched_filename)
        print(f"Processing: '{title}' -> '{matched_filename}' (Score: {score}) | Type: {p_type}")
        
        # Load PDF Text
        try:
            loader = PyPDFLoader(pdf_path)
            pages = loader.load()
            full_text = "\n".join([p.page_content for p in pages])
        except Exception as e:
            print(f"Failed to load PDF {matched_filename}: {e}")
            continue
            
        # Surgical Extraction
        extracted_text = extract_text_by_type(full_text, p_type)
        
        if not extracted_text or len(extracted_text) < 50:
             print(f"Warning: Low extracted text length for {matched_filename}. Check extraction logic.")
             # print(full_text[:500]) # Debug
             continue
             
        # Chunking
        chunks = text_splitter.create_documents([extracted_text])
        
        # Metadata
        # Columns: clusters, `Paper Type`, `Category`, paper type, `Main Mechanism`
        # Note: CSV seems to have 'Cluster', 'Category (The Folder)', 'Main Mechanism (Tags)'
        # Let's normalize keys
        metadata = {
            "paper_type": p_type,
            "category": str(row.get('Category (The Folder)', '')),
            "cluster": str(row.get('Cluster', '')),
            "main_mechanism": str(row.get('Main Mechanism (Tags)', '')),
            "source": matched_filename
        }
        
        # Add to Chroma
        # Using simpler collection.add with ids, embeddings (auto), metadatas, documents
        ids = [f"{matched_filename}_chk_{i}" for i in range(len(chunks))]
        docs = [c.page_content for c in chunks]
        metadatas = [metadata for _ in range(len(chunks))]
        
        collection.add(
            documents=docs,
            metadatas=metadatas,
            ids=ids
        )
        count_ingested += 1
        print(f"  -> Ingested {len(chunks)} chunks.")

    print(f"\nFinished. Total papers processed: {count_ingested}")

if __name__ == "__main__":
    ingest()
