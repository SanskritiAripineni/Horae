import chromadb
import sys

db_dir = "chroma_db"
client = chromadb.PersistentClient(path=db_dir)

try:
    collection = client.get_collection(name="research_papers")
    count = collection.count()
    print(f"Collection 'research_papers' exists.")
    print(f"Total documents (chunks): {count}")
    
    if count > 0:
        print("\n--- Sample Document ---")
        # Get one document
        result = collection.peek(limit=1)
        print("Metadata:", result['metadatas'][0])
        print("Content Preview:", result['documents'][0][:200] + "...")
    else:
        print("Collection is empty!")

except Exception as e:
    print(f"Error verification failed: {e}")
