"""
VectorDB Client - Wellness Knowledge Retrieval (Python 3.9 Compatible)
Uses ChromaDB's native embedding for similarity search.
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

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
    and mindfulness. When the agent detects mental health risk, it queries
    this database to find evidence-based suggestions.
    """
    
    def __init__(self, chroma_dir: str = "vectordb/chroma_db"):
        self.chroma_dir = Path(chroma_dir)
        self.collection = None
        self._initialized = False
        logger.info(f"Initialized VectorDBClient with chroma_dir: {chroma_dir}")
    
    def initialize(self) -> bool:
        """Initialize ChromaDB connection."""
        try:
            import chromadb
            
            if not self.chroma_dir.exists():
                logger.warning(f"ChromaDB not found at {self.chroma_dir}. Run vectordb/ingest_simple.py first.")
                return False
            
            client = chromadb.PersistentClient(path=str(self.chroma_dir))
            self.collection = client.get_collection("wellness_papers")
            self._initialized = True
            logger.info(f"VectorDB initialized with {self.collection.count()} documents")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize VectorDB: {e}")
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
            results = self.collection.query(
                query_texts=[query],
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
