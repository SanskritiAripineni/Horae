"""
Rigorous Evaluation: Gemini Embedding 2 Native PDF vs Extracted Text
=====================================================================
Two approaches in one script:
  1. Controlled IR comparison  — same model (gemini-embedding-2-preview), different
     input format (native PDF pages vs CSV-extracted text). Metrics: Precision@4,
     MRR, source diversity.
  2. End-to-end RAG with LLM judge — retrieve → generate → evaluate with
     RAGAS-style metrics (faithfulness, context relevance, answer relevance,
     completeness).
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from statistics import mean

import fitz  # PyMuPDF
import pandas as pd
from chromadb import PersistentClient
from dotenv import load_dotenv
from google import genai
from google.genai import types

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from _bootstrap import bootstrap_local_src
bootstrap_local_src()

from mindful_rag.config import ROOT_DIR, INDEX_CSV, PDF_DIR, get_env_file
from mindful_rag.evaluators import (
    faithfulness,
    context_relevance,
    answer_relevance,
    response_completeness,
)

# ── Constants ────────────────────────────────────────────────────────────
QUERY_FILE       = ROOT_DIR / "configs" / "evaluation" / "source_filter_queries.json"
OUTPUT_DIR       = ROOT_DIR / "data" / "evals"
GEMINI_MODEL     = "gemini-embedding-2-preview"
GENERATOR_MODEL  = "gemini-2.5-flash"
CHROMA_TEXT_DIR   = str(ROOT_DIR / "data" / "evals" / "chroma_gemini_text")
CHROMA_NATIVE_DIR = str(ROOT_DIR / "data" / "evals" / "chroma_gemini_native")
TEXT_COLLECTION   = "gemini_text_chunks"
NATIVE_COLLECTION = "gemini_native_pdfs"
MAX_PDF_PAGES     = 6
TOP_K             = 4


def _safe_mean(vals: list[float]) -> float:
    return round(mean(vals), 4) if vals else 0.0


# ── Data loading ─────────────────────────────────────────────────────────

def load_queries() -> list[dict]:
    with QUERY_FILE.open() as f:
        return json.load(f)


def load_index() -> pd.DataFrame:
    return pd.read_csv(INDEX_CSV)


def build_title_to_category(df: pd.DataFrame) -> dict[str, str]:
    """Map paper title (lowered) → category."""
    mapping = {}
    for _, row in df.iterrows():
        title = str(row.get("Paper Title", "")).strip().lower()
        cat = str(row.get("Category (The Folder)", "")).strip()
        if title and cat:
            mapping[title] = cat
    return mapping


def filename_to_category(filename: str, title_map: dict[str, str]) -> str:
    """Best-effort filename → category via fuzzy title match."""
    fn = filename.lower().replace(".pdf", "").replace("-", " ").strip()
    fn_tokens = set(re.findall(r"[a-z0-9]+", fn))
    best_score, best_cat = 0.0, "Unknown"
    for title, cat in title_map.items():
        t_tokens = set(re.findall(r"[a-z0-9]+", title))
        if not t_tokens:
            continue
        score = len(fn_tokens & t_tokens) / max(len(fn_tokens), 1)
        if score > best_score:
            best_score, best_cat = score, cat
    return best_cat if best_score > 0.3 else "Unknown"


# ═════════════════════════════════════════════════════════════════════════
# APPROACH 1: Controlled IR Comparison
# ═════════════════════════════════════════════════════════════════════════

def ingest_text_with_gemini2(client: genai.Client, df: pd.DataFrame) -> None:
    """Ingest CSV-extracted text into ChromaDB using gemini-embedding-2-preview."""
    # Find the ingestion CSV with extracted text
    ingestion_csvs = sorted((ROOT_DIR / "data" / "index").glob("research_index_ingestions_*.csv"))
    if not ingestion_csvs:
        raise FileNotFoundError("No ingestion CSV found. Run build_ingestion_csv.py first.")
    
    ingest_df = pd.read_csv(ingestion_csvs[-1])  # Use the latest
    ingest_df = ingest_df.dropna(subset=["by_type_text"])
    ingest_df = ingest_df[ingest_df["by_type_text"].str.strip() != ""]
    
    print(f"  Ingesting {len(ingest_df)} text chunks with {GEMINI_MODEL}...")
    
    chroma = PersistentClient(path=CHROMA_TEXT_DIR)
    try:
        chroma.delete_collection(TEXT_COLLECTION)
    except Exception:
        pass
    collection = chroma.create_collection(TEXT_COLLECTION, metadata={"hnsw:space": "cosine"})
    
    for idx, row in ingest_df.iterrows():
        text = str(row["by_type_text"]).strip()[:8000]  # Stay within token limit
        title = str(row.get("paper_title", "")).strip()
        category = str(row.get("category", "")).strip()
        
        try:
            emb = client.models.embed_content(
                model=GEMINI_MODEL, contents=text
            ).embeddings[0].values
            
            collection.add(
                embeddings=[emb],
                documents=[text],
                metadatas=[{"source": title, "category": category, "retrieval_source": "gemini_text"}],
                ids=[f"text_{idx}"]
            )
        except Exception as e:
            print(f"    Failed to embed text chunk {idx}: {e}")
        
        # Rate limiting
        if idx % 5 == 0:
            time.sleep(1)
    
    print(f"  Text ingestion complete: {collection.count()} chunks stored.")


def run_ir_comparison(client: genai.Client, queries: list[dict], title_map: dict[str, str]) -> list[dict]:
    """Run the same queries against both collections and compute IR metrics."""
    
    # Open both collections
    text_chroma = PersistentClient(path=CHROMA_TEXT_DIR)
    native_chroma = PersistentClient(path=CHROMA_NATIVE_DIR)
    
    text_coll = text_chroma.get_collection(TEXT_COLLECTION)
    native_coll = native_chroma.get_collection(NATIVE_COLLECTION)
    
    results = []
    
    for q in queries:
        query_text = q["query"]
        expected_cats = {c.lower() for c in q.get("expected_categories", [])}
        
        # Embed query ONCE — same embedding for both conditions
        query_emb = client.models.embed_content(
            model=GEMINI_MODEL, contents=query_text
        ).embeddings[0].values
        
        for label, coll in [("extracted_text", text_coll), ("native_pdf", native_coll)]:
            retrieval = coll.query(query_embeddings=[query_emb], n_results=TOP_K)
            metas = retrieval["metadatas"][0] if retrieval["metadatas"] else []
            distances = retrieval["distances"][0] if retrieval["distances"] else []
            
            # Map retrieved docs to categories
            retrieved_cats = []
            unique_sources = set()
            for m in metas:
                src = str(m.get("source", ""))
                cat = m.get("category", "") or filename_to_category(src, title_map)
                retrieved_cats.append(cat.lower())
                unique_sources.add(src)
            
            # Precision@K: fraction of top-K results from expected category
            precision = sum(1 for c in retrieved_cats if c in expected_cats) / TOP_K if expected_cats else None
            
            # MRR: reciprocal rank of first relevant result
            mrr = 0.0
            for rank, cat in enumerate(retrieved_cats):
                if cat in expected_cats:
                    mrr = 1.0 / (rank + 1)
                    break
            
            # Similarity scores (1 - distance)
            sim_scores = [1.0 - d for d in distances] if distances else []
            
            results.append({
                "query_id": q["id"],
                "method": label,
                "precision_at_k": round(precision, 4) if precision is not None else None,
                "mrr": round(mrr, 4),
                "avg_similarity": round(mean(sim_scores), 4) if sim_scores else 0.0,
                "unique_sources": len(unique_sources),
                "retrieved_categories": retrieved_cats,
            })
        
        time.sleep(0.5)  # Rate limiting
    
    return results


# ═════════════════════════════════════════════════════════════════════════
# APPROACH 2: End-to-End RAG with LLM Judge
# ═════════════════════════════════════════════════════════════════════════

def generate_rag_answer(client: genai.Client, query: str, chunks: list[dict]) -> str:
    """Generate a RAG answer using retrieved chunks as context."""
    context = "\n\n---\n\n".join(
        f"Source: {c.get('source', 'Unknown')}\n{c.get('content', '')[:2000]}"
        for c in chunks
    )
    prompt = f"""You are a wellness research assistant. Answer the following question 
using ONLY the provided research context. Be specific and cite sources.

CONTEXT:
{context}

QUESTION: {query}

ANSWER:"""
    
    try:
        response = client.models.generate_content(model=GENERATOR_MODEL, contents=prompt)
        return response.text if response.text else ""
    except Exception as e:
        return f"Generation failed: {e}"


def run_rag_evaluation(client: genai.Client, queries: list[dict], title_map: dict[str, str]) -> list[dict]:
    """End-to-end RAG: retrieve → generate → LLM-judge evaluate."""
    
    # Need GOOGLE_API_KEY for the evaluators (they use their own client)
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    os.environ["GOOGLE_API_KEY"] = api_key  # evaluators.py looks for GOOGLE_API_KEY
    
    text_chroma = PersistentClient(path=CHROMA_TEXT_DIR)
    native_chroma = PersistentClient(path=CHROMA_NATIVE_DIR)
    text_coll = text_chroma.get_collection(TEXT_COLLECTION)
    native_coll = native_chroma.get_collection(NATIVE_COLLECTION)
    
    results = []
    
    for qi, q in enumerate(queries):
        query_text = q["query"]
        print(f"  [{qi+1}/{len(queries)}] RAG eval: {query_text[:60]}...")
        
        query_emb = client.models.embed_content(
            model=GEMINI_MODEL, contents=query_text
        ).embeddings[0].values
        
        for label, coll in [("extracted_text", text_coll), ("native_pdf", native_coll)]:
            retrieval = coll.query(query_embeddings=[query_emb], n_results=TOP_K)
            docs = retrieval["documents"][0] if retrieval["documents"] else []
            metas = retrieval["metadatas"][0] if retrieval["metadatas"] else []
            
            # Build chunks for evaluators
            chunks = []
            for doc, m in zip(docs, metas):
                chunks.append({
                    "content": doc,
                    "filename": str(m.get("source", "Unknown")),
                    "source": str(m.get("source", "Unknown")),
                })
            
            # Generate answer
            answer = generate_rag_answer(client, query_text, chunks)
            
            # Evaluate with LLM judge
            try:
                faith = faithfulness(query_text, answer, chunks)
                ctx_rel = context_relevance(query_text, chunks)
                ans_rel = answer_relevance(query_text, answer)
                completeness = response_completeness(query_text, answer, chunks)
                
                results.append({
                    "query_id": q["id"],
                    "method": label,
                    "faithfulness": faith["score"],
                    "context_relevance": ctx_rel["score"],
                    "answer_relevance": ans_rel["score"],
                    "completeness": completeness["score"],
                    "aggregate": round(mean([
                        faith["score"], ctx_rel["score"],
                        ans_rel["score"], completeness["score"]
                    ]), 4),
                })
            except Exception as e:
                print(f"    Eval failed for {label}: {e}")
                results.append({
                    "query_id": q["id"],
                    "method": label,
                    "error": str(e),
                })
            
            time.sleep(1)  # Rate limiting between eval batches
    
    return results


# ═════════════════════════════════════════════════════════════════════════
# Summarize & Print
# ═════════════════════════════════════════════════════════════════════════

def summarize_ir(results: list[dict]) -> None:
    """Print IR comparison summary."""
    print("\n" + "=" * 80)
    print("APPROACH 1: Controlled IR Comparison (Same Model, Different Input)")
    print("=" * 80)
    
    for method in ["extracted_text", "native_pdf"]:
        rows = [r for r in results if r["method"] == method]
        if not rows:
            continue
        
        p_vals = [r["precision_at_k"] for r in rows if r["precision_at_k"] is not None]
        mrr_vals = [r["mrr"] for r in rows]
        src_vals = [float(r["unique_sources"]) for r in rows]
        sim_vals = [r["avg_similarity"] for r in rows]
        
        print(f"\n  {method}:")
        print(f"    Precision@{TOP_K}:    {_safe_mean(p_vals)}")
        print(f"    MRR:              {_safe_mean(mrr_vals)}")
        print(f"    Avg Similarity:   {_safe_mean(sim_vals)}")
        print(f"    Avg Unique Srcs:  {_safe_mean(src_vals)}")


def summarize_rag(results: list[dict]) -> None:
    """Print RAG evaluation summary."""
    print("\n" + "=" * 80)
    print("APPROACH 2: End-to-End RAG with LLM Judge")
    print("=" * 80)
    
    for method in ["extracted_text", "native_pdf"]:
        rows = [r for r in results if r["method"] == method and "error" not in r]
        if not rows:
            continue
        
        metrics = ["faithfulness", "context_relevance", "answer_relevance", "completeness", "aggregate"]
        print(f"\n  {method}:")
        for m in metrics:
            vals = [r[m] for r in rows if m in r]
            print(f"    {m:<22}: {_safe_mean(vals)}")


# ═════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════

def main() -> int:
    load_dotenv(get_env_file())
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY required.")
    
    os.environ["GOOGLE_API_KEY"] = api_key  # For evaluators
    client = genai.Client(api_key=api_key)
    queries = load_queries()
    df = load_index()
    title_map = build_title_to_category(df)
    
    # ── Step 1: Ingest extracted text with Gemini Embedding 2 ────────────
    text_chroma_path = Path(CHROMA_TEXT_DIR)
    if not text_chroma_path.exists() or not list(text_chroma_path.glob("*")):
        print("STEP 1: Ingesting extracted text with Gemini Embedding 2...")
        os.makedirs(CHROMA_TEXT_DIR, exist_ok=True)
        ingest_text_with_gemini2(client, df)
    else:
        # Check if collection exists
        try:
            tc = PersistentClient(path=CHROMA_TEXT_DIR)
            tc.get_collection(TEXT_COLLECTION)
            print("STEP 1: Text collection already exists. Skipping ingestion.")
        except Exception:
            print("STEP 1: Re-ingesting extracted text with Gemini Embedding 2...")
            os.makedirs(CHROMA_TEXT_DIR, exist_ok=True)
            ingest_text_with_gemini2(client, df)
    
    # Verify native PDF collection exists
    try:
        nc = PersistentClient(path=CHROMA_NATIVE_DIR)
        nc.get_collection(NATIVE_COLLECTION)
        print("Native PDF collection verified.\n")
    except Exception:
        raise RuntimeError("Native PDF collection not found. Run ingest_pdf_gemini.py first.")
    
    # ── Step 2: Controlled IR Comparison ─────────────────────────────────
    print("STEP 2: Running controlled IR comparison...")
    ir_results = run_ir_comparison(client, queries, title_map)
    summarize_ir(ir_results)
    
    # ── Step 3: End-to-End RAG Evaluation ────────────────────────────────
    print("\nSTEP 3: Running end-to-end RAG evaluation (this will take a few minutes)...")
    rag_results = run_rag_evaluation(client, queries, title_map)
    summarize_rag(rag_results)
    
    # ── Save everything ──────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"rigorous_comparison_{stamp}.json"
    
    payload = {
        "timestamp": stamp,
        "model": GEMINI_MODEL,
        "generator_model": GENERATOR_MODEL,
        "query_count": len(queries),
        "top_k": TOP_K,
        "ir_results": ir_results,
        "rag_results": rag_results,
    }
    with out_path.open("w") as f:
        json.dump(payload, f, indent=2, default=str)
    
    print(f"\nAll results saved to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
