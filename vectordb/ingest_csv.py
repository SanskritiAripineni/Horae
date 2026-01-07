"""
Ingest CSV Script for Student Wellness RAG Application
-------------------------------------------------------
Loads paper_map.csv, cleans text, embeds content using local HuggingFace model,
and saves vectors to ChromaDB.
"""

import pandas as pd
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.schema import Document


def load_and_clean_csv(csv_path: str) -> pd.DataFrame:
    """Load CSV and drop rows with empty text content."""
    df = pd.read_csv(csv_path)
    
    # Drop rows where text_content is empty or NaN
    df = df.dropna(subset=['text_content'])
    df = df[df['text_content'].str.strip() != '']
    
    # Clean any extra whitespace
    df['text_content'] = df['text_content'].str.strip()
    df['filename'] = df['filename'].str.strip()
    df['category'] = df['category'].str.strip()
    
    print(f"Loaded {len(df)} rows after cleaning.")
    return df


def create_documents(df: pd.DataFrame) -> list[Document]:
    """Convert DataFrame rows to LangChain Document objects with metadata."""
    documents = []
    
    for _, row in df.iterrows():
        doc = Document(
            page_content=row['text_content'],
            metadata={
                'filename': row['filename'],
                'category': row['category']
            }
        )
        documents.append(doc)
    
    return documents


def create_embeddings_and_store(documents: list[Document], persist_directory: str):
    """Embed documents using local HuggingFace model and store in ChromaDB."""
    
    # Initialize local embedding model (no API key needed)
    print("Loading local embedding model 'all-MiniLM-L6-v2'...")
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )
    
    # Create ChromaDB vector store
    print(f"Creating ChromaDB vector store at '{persist_directory}'...")
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=persist_directory,
        collection_name="wellness_papers"
    )
    
    return vectorstore


def main():
    csv_path = "paper_map.csv"
    chroma_dir = "chroma_db"
    
    # Step 1: Load and clean CSV
    print("=" * 50)
    print("STEP 1: Loading and cleaning CSV...")
    print("=" * 50)
    df = load_and_clean_csv(csv_path)
    
    # Step 2: Create Document objects
    print("\n" + "=" * 50)
    print("STEP 2: Creating Document objects...")
    print("=" * 50)
    documents = create_documents(df)
    print(f"Created {len(documents)} documents.")
    
    # Step 3: Embed and store in ChromaDB
    print("\n" + "=" * 50)
    print("STEP 3: Embedding and storing in ChromaDB...")
    print("=" * 50)
    vectorstore = create_embeddings_and_store(documents, chroma_dir)
    
    # Final summary
    print("\n" + "=" * 50)
    print("INGESTION COMPLETE!")
    print("=" * 50)
    print(f"✓ Number of chunks created: {len(documents)}")
    print(f"✓ Vector store saved to: '{chroma_dir}/'")
    print(f"✓ Categories found: {df['category'].unique().tolist()}")


if __name__ == "__main__":
    main()


