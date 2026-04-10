"""
Tests for tools/vectordb_client.py — ChromaDB wellness retrieval.

ChromaDB and Gemini embedding calls are mocked. Tests cover:
- initialize() success and failure
- retrieve() with and without category filters
- get_intervention_suggestions() with various PHQ-4 score ranges
- Graceful degradation when ChromaDB directory is missing
"""

import sys
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

from tools.vectordb_client import VectorDBClient, WELLNESS_CATEGORIES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_collection(documents, metadatas):
    """Return a mock ChromaDB collection whose .query() returns the given data."""
    col = MagicMock()
    col.count.return_value = len(documents)
    col.query.return_value = {
        "documents": [documents],
        "metadatas": [metadatas],
    }
    return col


def _patched_client(tmp_path, documents=None, metadatas=None):
    """Create a VectorDBClient with a mocked ChromaDB backend."""
    docs = documents or ["Sleep is important for health."]
    metas = metadatas or [{"category": "Sleep Hygiene", "filename": "sleep_study.pdf"}]

    client = VectorDBClient(chroma_dir=str(tmp_path))
    client.collection = _mock_collection(docs, metas)
    client._initialized = True

    # Mock the embedding call so it never hits the real API
    client._embed_query = MagicMock(return_value=[0.1] * 3072)
    return client


# ---------------------------------------------------------------------------
# initialize
# ---------------------------------------------------------------------------

class TestInitialize:

    def test_returns_false_when_dir_missing(self, tmp_path):
        client = VectorDBClient(chroma_dir=str(tmp_path / "nonexistent"))
        assert client.initialize() is False

    def test_returns_true_on_success(self, tmp_path):
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()

        mock_col = MagicMock()
        mock_col.count.return_value = 42
        mock_persistent = MagicMock()
        mock_persistent.get_collection.return_value = mock_col

        mock_chromadb_mod = MagicMock()
        mock_chromadb_mod.PersistentClient.return_value = mock_persistent

        client = VectorDBClient(chroma_dir=str(chroma_dir))
        client._embedding_model = "test-model"
        client._collection_name = "test_col"

        with patch.dict(sys.modules, {"chromadb": mock_chromadb_mod}):
            result = client.initialize()

        assert result is True
        assert client._initialized is True
        assert client.collection is mock_col

    def test_returns_false_on_chromadb_error(self, tmp_path):
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()

        mock_chromadb_mod = MagicMock()
        mock_chromadb_mod.PersistentClient.side_effect = Exception("corrupt db")

        client = VectorDBClient(chroma_dir=str(chroma_dir))
        client._embedding_model = "test-model"
        client._collection_name = "test_col"

        with patch.dict(sys.modules, {"chromadb": mock_chromadb_mod}), \
             patch("time.sleep"):  # skip retry delays
            assert client.initialize() is False


# ---------------------------------------------------------------------------
# retrieve
# ---------------------------------------------------------------------------

class TestRetrieve:

    def test_basic_retrieval(self, tmp_path):
        client = _patched_client(tmp_path)

        results = client.retrieve("sleep tips", top_k=1)
        assert len(results) == 1
        assert results[0]["category"] == "Sleep Hygiene"
        assert "Sleep is important" in results[0]["content"]
        assert results[0]["source"] == "sleep_study.pdf"

    def test_category_filter_passed_to_query(self, tmp_path):
        client = _patched_client(tmp_path)

        client.retrieve("stress", category="Stress Management", top_k=2)
        call_kwargs = client.collection.query.call_args[1]
        assert call_kwargs["where"] == {"category": "Stress Management"}

    def test_no_filter_when_category_is_none(self, tmp_path):
        client = _patched_client(tmp_path)

        client.retrieve("anything")
        call_kwargs = client.collection.query.call_args[1]
        assert call_kwargs["where"] is None

    def test_returns_empty_when_not_initialized(self, tmp_path):
        client = VectorDBClient(chroma_dir=str(tmp_path / "nope"))
        client._initialized = False
        # Also make initialize fail
        client.initialize = MagicMock(return_value=False)

        results = client.retrieve("query")
        assert results == []

    def test_returns_empty_on_query_exception(self, tmp_path):
        client = _patched_client(tmp_path)
        client.collection.query.side_effect = RuntimeError("network error")

        results = client.retrieve("query")
        assert results == []

    def test_multiple_results(self, tmp_path):
        docs = ["doc one", "doc two", "doc three"]
        metas = [
            {"category": "Sleep Hygiene", "filename": "a.pdf"},
            {"category": "Stress Management", "filename": "b.pdf"},
            {"category": "Mindfulness", "filename": "c.pdf"},
        ]
        client = _patched_client(tmp_path, documents=docs, metadatas=metas)

        results = client.retrieve("query", top_k=3)
        assert len(results) == 3
        categories = {r["category"] for r in results}
        assert "Sleep Hygiene" in categories
        assert "Stress Management" in categories


# ---------------------------------------------------------------------------
# get_intervention_suggestions
# ---------------------------------------------------------------------------

class TestGetInterventionSuggestions:

    def test_severe_score_queries_coping_and_social(self, tmp_path):
        client = _patched_client(tmp_path)
        suggestions = client.get_intervention_suggestions(phq4_score=10)

        # With score >= 9, the method calls retrieve twice
        assert client._embed_query.call_count == 2
        assert len(suggestions) <= 4

    def test_moderate_score_queries_stress_and_sleep(self, tmp_path):
        client = _patched_client(tmp_path)
        suggestions = client.get_intervention_suggestions(phq4_score=7)

        assert client._embed_query.call_count == 2

    def test_mild_score_queries_habits_and_mindfulness(self, tmp_path):
        client = _patched_client(tmp_path)
        suggestions = client.get_intervention_suggestions(phq4_score=2)

        assert client._embed_query.call_count == 2

    def test_limits_to_four_results(self, tmp_path):
        # Return 3 docs per query (6 total) — should be capped at 4
        docs = ["a", "b", "c"]
        metas = [
            {"category": "X", "filename": "x.pdf"},
            {"category": "Y", "filename": "y.pdf"},
            {"category": "Z", "filename": "z.pdf"},
        ]
        client = _patched_client(tmp_path, documents=docs, metadatas=metas)
        suggestions = client.get_intervention_suggestions(phq4_score=10)
        assert len(suggestions) <= 4

    def test_journal_summary_parameter_accepted(self, tmp_path):
        """The journal_summary parameter is accepted even if not directly used in queries."""
        client = _patched_client(tmp_path)
        # Should not raise
        suggestions = client.get_intervention_suggestions(
            phq4_score=5,
            journal_summary="User is feeling stressed about exams"
        )
        assert isinstance(suggestions, list)


# ---------------------------------------------------------------------------
# WELLNESS_CATEGORIES constant
# ---------------------------------------------------------------------------

class TestWellnessCategories:

    def test_expected_categories_present(self):
        expected = {"Sleep Hygiene", "Stress Management", "Social connection",
                    "Physical Activity", "Mindfulness"}
        assert set(WELLNESS_CATEGORIES) == expected
