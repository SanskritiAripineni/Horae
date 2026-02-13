# PDF Embedding Process - End to End

## Overview
The system converts research papers (PDFs) into searchable vector embeddings stored in ChromaDB, which are then used for semantic search in your RAG (Retrieval-Augmented Generation) application.

---

## Phase 1: Data Preparation 📋

### Input Sources
1. **[research_index.csv](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/research_index.csv)** - Contains metadata about 61 research papers:
   - Paper Title, Paper Type (Protocol/Meta-Analysis/CPG)
   - Category (Sleep Hygiene, Physical Activity, Dietary habits, etc.)
   - Cluster information
   
2. **`research paperss/`** folder - Contains the actual PDF files

### Step 1.1: Load CSV Data
[ingest_raw.py:41-50](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/ingest_raw.py#L41-L50)
- Reads the CSV file
- Filters out rows without paper titles
- Returns a DataFrame with metadata

### Step 1.2: Scan PDF Directory
[ingest_raw.py:53-61](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/ingest_raw.py#L53-L61)
- Scans the folder for all `.pdf` files
- Returns list of filenames

---

## Phase 2: Fuzzy Matching 🔍

### Step 2.1: Match Titles to Files
[ingest_raw.py:68-92](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/ingest_raw.py#L68-L92)

**Problem**: CSV paper titles don't exactly match PDF filenames

**Solution**: Uses `thefuzz` library for fuzzy string matching

**Process**:
1. Removes `.pdf` extension from filenames
2. Compares CSV title against all PDF names
3. Returns best match if similarity score ≥ 60%

**Example**: 
- CSV Title: `"Circadian rhythm disruption and mental health"`
- PDF Filename: `"Circadianrhythmdisruptionandmentalhealth.pdf"`
- Match Score: ~95% ✓

---

## Phase 3: Text Extraction 📄

### Step 3.1: Extract Full Text
[ingest_raw.py:99-123](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/ingest_raw.py#L99-L123)

- Uses **PyMuPDF (fitz)** library
- Iterates through every page of the PDF
- Extracts raw text using `page.get_text()`

> [!IMPORTANT]
> In the "raw" version, NO filtering is applied. Includes references, bibliographies, headers, footers. This is for baseline comparison in your ablation study.

---

## Phase 4: Text Chunking ✂️

### Step 4.1: Split into Chunks
[ingest_raw.py:130-150](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/ingest_raw.py#L130-L150)

Uses **LangChain's RecursiveCharacterTextSplitter**

**Parameters**:
- `chunk_size=1000` characters
- `chunk_overlap=100` characters (maintains context between chunks)

**Splitting Strategy** (in order of preference):
1. Double newlines (`\n\n`) - paragraph breaks
2. Single newlines (`\n`) - line breaks
3. Periods with space (`. `) - sentence breaks
4. Spaces (` `) - word breaks
5. Characters (`""`) - character-level fallback

**Why chunking?**
- Embedding models have token limits
- Smaller chunks = more precise semantic search
- Overlap prevents context loss at boundaries

---

## Phase 5: Embedding Generation 🧠

### Step 5.1: Initialize Embedding Model
[ingest_raw.py:206-212](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/ingest_raw.py#L206-L212)

**Model**: `all-MiniLM-L6-v2` (HuggingFace)
- Lightweight (80MB)
- 384-dimensional vectors
- Optimized for semantic similarity
- Runs on CPU (no GPU needed)

**Configuration**:
- `device='cpu'` - runs locally
- `normalize_embeddings=True` - enables cosine similarity

### Step 5.2: Create Document Objects
[ingest_raw.py:248-262](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/ingest_raw.py#L248-L262)

For each text chunk, creates a document with:

**Text**: The actual chunk content

**Metadata**:
- `filename` - PDF filename
- `paper_title` - Original title from CSV
- `paper_type` - Protocol/Meta-Analysis/CPG
- `category` - Sleep Hygiene, Physical Activity, etc.
- `cluster` - Research cluster grouping
- `chunk_index` - Position in document
- `total_chunks` - Total chunks for this paper

---

## Phase 6: Vector Store Ingestion 💾

### Step 6.1: Store in ChromaDB
[ingest_raw.py:157-184](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/ingest_raw.py#L157-L184)

Uses **ChromaDB** as the vector database

**Process**:
1. Separates texts and metadata
2. Calls `Chroma.from_texts()` which:
   - Generates embeddings for each chunk (using the HuggingFace model)
   - Stores embeddings + metadata in ChromaDB
   - Persists to disk at `chroma_db/`
3. Creates collection named `"wellness_papers"`

**Storage Structure**:
```
chroma_db/
├── chroma.sqlite3        # Metadata database
├── embeddings/           # Vector embeddings
└── index/                # Search indices
```

---

## Phase 7: Query Time (Retrieval) 🔎

### Step 7.1: Query Processing

When a user asks a question:

**1. Classify Intent** - [app.py:106-115](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/app.py#L106-L115)
- Embed user query and compare to category embeddings
- Uses cosine similarity to find best matching category

**2. Retrieve Chunks** - [app.py:122-141](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/app.py#L122-L141)
- Embed the user's query
- Search ChromaDB for top 3 most similar chunks
- Filter by detected category
- Returns chunks with metadata

**3. Generate Response** - [app.py:148-178](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/app.py#L148-L178)
- Pass retrieved chunks to OpenAI GPT-4o-mini
- LLM generates evidence-based wellness plan

---

## Key Technical Details 🔧

| Component | Details |
|-----------|---------|
| **Embedding Model** | all-MiniLM-L6-v2 (HuggingFace) |
| **Embedding Dimensions** | 384 |
| **Similarity Metric** | Cosine similarity |
| **Vector Database** | ChromaDB |
| **Chunk Size** | 1000 characters |
| **Chunk Overlap** | 100 characters |
| **LLM** | GPT-4o-mini (OpenAI) |

**Total Pipeline**:
```
PDF → Text Extraction → Chunking → Embedding → ChromaDB → Query → LLM Response
```

**Performance**:
- ~61 papers processed
- Thousands of chunks created
- Sub-second retrieval time
- Local embeddings (no API calls for embedding)

---

## Why This Architecture? 💡

1. **Local Embeddings**: Fast, free, private (HuggingFace model)
2. **ChromaDB**: Lightweight, persistent, easy to use
3. **Metadata Filtering**: Enables category-specific search
4. **Chunking**: Balances context vs. precision
5. **Fuzzy Matching**: Handles filename inconsistencies

This is a classic **RAG (Retrieval-Augmented Generation)** pipeline optimized for research paper Q&A!

---

## Source Traceability 🔍

### Metadata Attached to Every Chunk

Each chunk stores rich metadata:

```python
metadata = {
    'filename': matched_filename,           # e.g., "Circadianrhythm...pdf"
    'paper_title': paper_title,             # Full title from CSV
    'paper_type': paper_type,               # Protocol/Meta-Analysis/CPG
    'category': category,                   # Sleep Hygiene, etc.
    'cluster': cluster,                     # Research cluster
    'chunk_index': chunk_idx,               # Position: 0, 1, 2...
    'total_chunks': len(chunks)             # Total chunks in this paper
}
```

### What You Can Trace

✅ **Exact PDF file** - via `filename`  
✅ **Original paper title** - via `paper_title`  
✅ **Chunk position** - via `chunk_index` (e.g., chunk 3 of 15)  
✅ **Paper category** - via `category`  
✅ **Paper type** - via `paper_type`

### Current Usage in Your App

The app retrieves filename and category - [app.py:134-141](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/app.py#L134-L141):

```python
return [
    {
        'content': doc.page_content,
        'filename': doc.metadata.get('filename', 'Unknown').replace('.pdf', ''),
        'category': doc.metadata.get('category', 'Unknown'),
    }
    for doc, score in results
]
```

And displays it in the LLM response - [app.py:158-159](file:///Applications/Spring%202026/Project/Mindful_Rag_pdf/app.py#L158-L159):
```python
context_parts.append(f"Source {i} ({chunk['filename']}):\n{chunk['content']}")
```

### Potential Enhancements

You have access to even more metadata that you're **not currently displaying**:

- **`chunk_index`** - Show which part of the paper (e.g., "Chunk 3/15")
- **`paper_title`** - Show the full academic title
- **`paper_type`** - Indicate if it's a Protocol, Meta-Analysis, or CPG
- **Direct link** - Reconstruct the full path: `research paperss/{filename}`

**Example Enhanced Display**:
```python
{
    'content': doc.page_content,
    'filename': doc.metadata.get('filename', 'Unknown'),
    'paper_title': doc.metadata.get('paper_title', 'Unknown'),
    'chunk_position': f"{doc.metadata.get('chunk_index', 0) + 1}/{doc.metadata.get('total_chunks', '?')}",
    'paper_type': doc.metadata.get('paper_type', 'Unknown'),
    'category': doc.metadata.get('category', 'Unknown'),
}
```

Then display: 
> **Source 1**: "Circadian rhythm disruption and mental health" (Meta-Analysis, Chunk 2/8)

---

## Summary

**Full source traceability is preserved!** Every chunk "remembers" where it came from, which paper, and even its position within that paper. You can always trace back to the original PDF and even locate the approximate section within it.
