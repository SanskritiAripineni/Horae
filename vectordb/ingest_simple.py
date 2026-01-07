"""
Simple VectorDB Ingestion - Python 3.9 Compatible
Uses ChromaDB with its default embedding function.
"""

import pandas as pd
import chromadb
from pathlib import Path

def main():
    csv_path = "paper_map.csv"
    chroma_dir = "chroma_db"
    
    print("=" * 50)
    print("Loading and cleaning CSV...")
    print("=" * 50)
    
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=['text_content'])
    df = df[df['text_content'].str.strip() != '']
    df['text_content'] = df['text_content'].str.strip()
    df['filename'] = df['filename'].str.strip()
    df['category'] = df['category'].str.strip()
    print(f"Loaded {len(df)} rows after cleaning.")
    
    print("\n" + "=" * 50)
    print("Creating ChromaDB collection...")
    print("=" * 50)
    
    # Use ChromaDB's default embedding function (no external deps)
    client = chromadb.PersistentClient(path=chroma_dir)
    
    # Delete existing collection if it exists
    try:
        client.delete_collection("wellness_papers")
    except:
        pass
    
    collection = client.create_collection(
        name="wellness_papers",
        metadata={"hnsw:space": "cosine"}
    )
    
    # Add documents
    documents = df['text_content'].tolist()
    metadatas = [{"filename": row['filename'], "category": row['category']} 
                 for _, row in df.iterrows()]
    ids = [f"doc_{i}" for i in range(len(documents))]
    
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    print("\n" + "=" * 50)
    print("INGESTION COMPLETE!")
    print("=" * 50)
    print(f"✓ Number of chunks: {len(documents)}")
    print(f"✓ Vector store: '{chroma_dir}/'")
    print(f"✓ Categories: {df['category'].unique().tolist()}")

if __name__ == "__main__":
    main()
