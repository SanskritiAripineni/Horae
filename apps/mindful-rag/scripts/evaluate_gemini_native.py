"""Evaluate native Gemini Embeddings against the test queries."""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from chromadb import PersistentClient
from dotenv import load_dotenv

from _bootstrap import bootstrap_local_src
bootstrap_local_src()

from mindful_rag.config import ROOT_DIR, get_env_file

DEFAULT_QUERY_FILE = ROOT_DIR / "configs" / "evaluation" / "source_filter_queries.json"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "evals"
DEFAULT_CHROMA_DIR = str(ROOT_DIR / "data" / "evals" / "chroma_gemini_native")
COLLECTION_NAME = "gemini_native_pdfs"
MODEL_NAME = "gemini-embedding-2-preview"

def load_queries(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def evaluate_embeddings(queries: list[dict], collection):
    from google import genai
    
    # We need to embed the query first to do the retrieval 
    client = genai.Client()
    
    results = []
    
    for q in queries:
        query_text = q["query"]
        expected_categories = set(c.lower() for c in q.get("expected_categories", []))
        
        try:
            # 1. Embed the query using the text embedding method
            query_embedding = client.models.embed_content(
                model=MODEL_NAME,
                contents=query_text
            ).embeddings[0].values
            
            # 2. Retrieve top 4 from ChromaDB
            retrieval = collection.query(
                query_embeddings=[query_embedding],
                n_results=4
            )
            
            # 3. Analyze results
            retrieved_docs = retrieval['documents'][0] if retrieval['documents'] else []
            retrieved_metadatas = retrieval['metadatas'][0] if retrieval['metadatas'] else []
            retrieved_distances = retrieval['distances'][0] if retrieval['distances'] else []
            
            # Since native PDFs don't extract the "category" metadata (unless we manually mapped it during ingestion),
            # we will just check if we hit any documents and record the distances.
            # In a full production system, we'd map filename -> category during ingestion for exact comparison.
            
            hit_files = [str(m.get("source", "")) for m in retrieved_metadatas]
            
            results.append({
                "query_id": q["id"],
                "query": query_text,
                "retrieved_count": len(retrieved_docs),
                "top_retrieved_files": hit_files,
                "best_distance": float(retrieved_distances[0]) if retrieved_distances else None,
                "avg_distance": sum(retrieved_distances)/len(retrieved_distances) if retrieved_distances else None
            })
            print(f"Query: {query_text[:50]}... -> Retrieved {len(retrieved_docs)} docs.")
            
        except Exception as e:
            print(f"Failed query '{query_text[:20]}...': {e}")
            results.append({
                "query_id": q["id"],
                "error": str(e)
            })
            
    return results

def main():
    parser = argparse.ArgumentParser(description="Evaluate Native Gemini PDF Embeddings")
    parser.add_argument("--query-file", default=str(DEFAULT_QUERY_FILE))
    parser.add_argument("--chroma-dir", default=DEFAULT_CHROMA_DIR)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    
    load_dotenv(get_env_file())
    if not os.getenv("GEMINI_API_KEY"):
         raise ValueError("GEMINI_API_KEY environment variable is missing.")

    print(f"Loading queries from {args.query_file}")
    queries = load_queries(Path(args.query_file))
    
    print(f"Connecting to ChromaDB at {args.chroma_dir}")
    client = PersistentClient(path=args.chroma_dir)
    try:
        collection = client.get_collection(COLLECTION_NAME)
    except Exception as e:
        print(f"Error getting collection (did you run ingest_pdf_gemini.py?): {e}")
        return

    print("Evaluating queries using Native PDF Embeddings...")
    results = evaluate_embeddings(queries, collection)
    
    # Save results
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"gemini_native_eval_{stamp}.json"
    
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nEvaluation complete. Results saved to {out_file}")
    
    # Quick summary
    successes = [r for r in results if "error" not in r and r.get("retrieved_count", 0) > 0]
    print(f"Summary: {len(successes)}/{len(queries)} queries returned results.")

if __name__ == "__main__":
    main()
