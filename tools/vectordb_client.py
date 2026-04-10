"""
VectorDB Client - Wellness Knowledge Retrieval with Gemini Embedding 2.
Uses native PDF embeddings via gemini-embedding-2-preview for superior retrieval quality.
"""

import os
import logging
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds, doubles each attempt

WELLNESS_CATEGORIES = [
    "Sleep Hygiene",
    "Stress Management",
    "Social connection",
    "Physical Activity",
    "Mindfulness"
]

class VectorDBClient:
    """
    Client for retrieving wellness concepts from ChromaDB.

    This VectorDB contains research-backed interventions extracted from 10+
    peer-reviewed papers on: sleep, stress, social health, physical activity,
    and mindfulness. Uses gemini-embedding-2-preview for both document and
    query embeddings, providing superior retrieval quality over text-based
    embedding approaches.
    """

    def __init__(self, chroma_dir: str = "vectordb/chroma_db"):
        self.chroma_dir = Path(chroma_dir)
        self.collection = None
        self._initialized = False
        self._genai_client = None
        self._embedding_model = None
        self._collection_name = None
        logger.info(f"Initialized VectorDBClient with chroma_dir: {chroma_dir}")

    def _load_config(self):
        """Load config lazily to avoid circular imports."""
        if self._embedding_model is None:
            try:
                from config import config
                self._embedding_model = config.EMBEDDING_MODEL
                self._collection_name = config.VECTORDB_COLLECTION
            except ImportError:
                self._embedding_model = "gemini-embedding-2-preview"
                self._collection_name = "wellness_papers_gemini"

    def _get_genai_client(self):
        """Get or create the Gemini API client for query embedding."""
        if self._genai_client is None:
            from google import genai
            from dotenv import load_dotenv
            load_dotenv()

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                try:
                    from config import config
                    api_key = config.GEMINI_API_KEY
                except ImportError:
                    pass

            if not api_key:
                raise ValueError("GEMINI_API_KEY not found in environment or config")

            self._genai_client = genai.Client(api_key=api_key)
        return self._genai_client

    def _is_retryable(self, error: Exception) -> bool:
        """Check if an error is transient and worth retrying."""
        error_str = str(error).lower()
        if any(kw in error_str for kw in [
            "429", "rate", "quota", "500", "502", "503", "504",
            "timeout", "connection", "network", "unavailable",
            "reset", "broken pipe", "eof",
        ]):
            return True
        error_type = type(error).__name__
        if "ServiceUnavailable" in error_type or "ResourceExhausted" in error_type:
            return True
        return False

    def _embed_query(self, text: str) -> List[float]:
        """Embed a text query using Gemini Embedding 2 with retry."""
        self._load_config()
        client = self._get_genai_client()

        last_error: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                result = client.models.embed_content(
                    model=self._embedding_model,
                    contents=text,
                )
                return result.embeddings[0].values
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES and self._is_retryable(e):
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Embedding API call failed (attempt {attempt + 1}/{MAX_RETRIES + 1}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    break

        logger.error(f"Embedding failed after {MAX_RETRIES + 1} attempts: {last_error}")
        raise last_error  # Let caller handle (retrieve() already catches exceptions)

    def initialize(self) -> bool:
        """Initialize ChromaDB connection with retry for transient I/O errors."""
        self._load_config()

        if not self.chroma_dir.exists():
            logger.warning(f"ChromaDB not found at {self.chroma_dir}. Run vectordb/ingest_simple.py first.")
            return False

        for attempt in range(MAX_RETRIES + 1):
            try:
                import chromadb
                client = chromadb.PersistentClient(path=str(self.chroma_dir))
                self.collection = client.get_collection(self._collection_name)
                self._initialized = True
                logger.info(f"VectorDB initialized with {self.collection.count()} documents")
                return True
            except Exception as e:
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"ChromaDB init failed (attempt {attempt + 1}/{MAX_RETRIES + 1}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Failed to initialize VectorDB after {MAX_RETRIES + 1} attempts: {e}")
                    return False

    def retrieve(self, query: str, category: Optional[str] = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve relevant wellness concepts.

        Args:
            query: Search query (e.g., "how to improve sleep")
            category: Optional filter (Sleep Hygiene, Stress Management, etc.)
            top_k: Number of results

        Returns:
            List of concept dictionaries with content and metadata
        """
        if not self._initialized:
            if not self.initialize():
                return []

        try:
            where_filter = {"category": category} if category else None
            query_embedding = self._embed_query(query)
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter
            )

            concepts = []
            for i, doc in enumerate(results['documents'][0]):
                concepts.append({
                    'content': doc,
                    'category': results['metadatas'][0][i].get('category', 'Unknown'),
                    'source': results['metadatas'][0][i].get('filename', 'Unknown')
                })

            logger.info(f"Retrieved {len(concepts)} concepts for query")
            return concepts

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []

    def get_intervention_suggestions(self, phq4_score: int, journal_summary: str = "") -> List[Dict[str, Any]]:
        """
        Get research-backed intervention suggestions based on mental health state.

        Args:
            phq4_score: PHQ-4 score (0-12)
            journal_summary: Optional context from journals

        Returns:
            List of intervention suggestions from research papers
        """
        # Determine priority areas based on severity
        if phq4_score >= 9:
            # Severe - immediate support focus
            queries = ["emotional coping strategies", "social support wellness"]
        elif phq4_score >= 6:
            # Moderate - balanced interventions
            queries = ["stress reduction techniques", "sleep improvement mental health"]
        else:
            # Minimal/Mild - preventive
            queries = ["habit formation daily routine", "mindfulness practice"]

        all_suggestions = []
        for query in queries:
            suggestions = self.retrieve(query, top_k=2)
            all_suggestions.extend(suggestions)

        return all_suggestions[:4]
