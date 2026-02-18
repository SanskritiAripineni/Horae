"""Unit tests for production retrieval logic."""

from typing import Optional
import unittest

from _bootstrap import bootstrap_local_src

bootstrap_local_src()

from mindful_rag.retrieval import RetrievalSettings, production_retrieve


class _DummyDoc:
    def __init__(self, content: str, metadata: dict):
        self.page_content = content
        self.metadata = metadata


class _DummyRetriever:
    def __init__(self, docs: list[_DummyDoc]):
        self._docs = docs

    def invoke(self, _query: str) -> list[_DummyDoc]:
        return list(self._docs)


class _DummyVectorStore:
    def __init__(
        self,
        similarity_results=None,
        mmr_results=None,
        similarity_error: Optional[Exception] = None,
    ):
        self._similarity_results = similarity_results or []
        self._mmr_results = mmr_results or []
        self._similarity_error = similarity_error
        self.last_similarity_filter = None
        self.last_mmr_search_kwargs = {}

    def similarity_search_with_relevance_scores(self, _query: str, k: int, filter=None):
        if self._similarity_error:
            raise self._similarity_error
        self.last_similarity_filter = filter
        return list(self._similarity_results)[:k]

    def similarity_search(self, _query: str, k: int, filter=None):
        self.last_similarity_filter = filter
        return [doc for doc, _ in list(self._similarity_results)[:k]]

    def as_retriever(self, search_type: str, search_kwargs: dict):
        _ = search_type
        self.last_mmr_search_kwargs = dict(search_kwargs)
        return _DummyRetriever(self._mmr_results)


class RetrievalPipelineTests(unittest.TestCase):
    def test_deduplicates_overlap_between_similarity_and_mmr(self):
        doc = _DummyDoc(
            "Sleep at a consistent time each night.",
            {"filename": "sleep-paper.pdf", "chunk_index": 0, "category": "Sleep"},
        )
        vectorstore = _DummyVectorStore(
            similarity_results=[(doc, 0.92)],
            mmr_results=[doc],
        )
        settings = RetrievalSettings(top_k=3, fetch_k=10, max_per_source=2, min_hybrid_score=0.0)

        result = production_retrieve("How do I sleep better?", vectorstore, settings)

        self.assertEqual(len(result.chunks), 1)
        self.assertEqual(result.chunks[0]["filename"], "sleep-paper")

    def test_respects_source_diversity_before_fill(self):
        doc_a1 = _DummyDoc("Chunk A1 about sleep timing.", {"filename": "a.pdf", "chunk_index": 1})
        doc_a2 = _DummyDoc("Chunk A2 about sleep hygiene.", {"filename": "a.pdf", "chunk_index": 2})
        doc_b1 = _DummyDoc("Chunk B1 about mindfulness practice.", {"filename": "b.pdf", "chunk_index": 1})
        doc_c1 = _DummyDoc("Chunk C1 about exercise schedule.", {"filename": "c.pdf", "chunk_index": 1})

        vectorstore = _DummyVectorStore(
            similarity_results=[(doc_a1, 0.99), (doc_a2, 0.96), (doc_b1, 0.94), (doc_c1, 0.93)],
            mmr_results=[doc_a1, doc_b1, doc_c1],
        )
        settings = RetrievalSettings(top_k=3, fetch_k=10, max_per_source=1, min_hybrid_score=0.0)

        result = production_retrieve("help me with sleep and stress", vectorstore, settings)
        sources = [chunk["source"] for chunk in result.chunks]

        self.assertEqual(len(result.chunks), 3)
        self.assertEqual(len(set(sources)), 3)

    def test_falls_back_to_mmr_when_similarity_fails(self):
        doc = _DummyDoc(
            "Take a 10-minute wind-down before bed.",
            {"filename": "winddown.pdf", "chunk_index": 3, "category": "Sleep"},
        )
        vectorstore = _DummyVectorStore(
            similarity_results=[],
            mmr_results=[doc],
            similarity_error=RuntimeError("backend unavailable"),
        )
        settings = RetrievalSettings(top_k=2, fetch_k=8, max_per_source=2, min_hybrid_score=0.0)

        result = production_retrieve("bedtime routine", vectorstore, settings)

        self.assertEqual(len(result.chunks), 1)
        self.assertTrue(result.stats["used_mmr"])
        self.assertFalse(result.stats["used_similarity"])
        self.assertTrue(result.stats["errors"])

    def test_forwards_metadata_filter_to_vectorstore(self):
        doc = _DummyDoc(
            "Use a short evening journaling habit.",
            {"filename": "journal.pdf", "chunk_index": 0, "retrieval_source": "intro_concl"},
        )
        vectorstore = _DummyVectorStore(
            similarity_results=[(doc, 0.87)],
            mmr_results=[doc],
        )
        settings = RetrievalSettings(top_k=2, fetch_k=8, max_per_source=2, min_hybrid_score=0.0)
        metadata_filter = {"retrieval_source": "intro_concl"}

        _ = production_retrieve(
            "help me wind down at night",
            vectorstore,
            settings,
            metadata_filter=metadata_filter,
        )

        self.assertEqual(vectorstore.last_similarity_filter, metadata_filter)
        self.assertEqual(vectorstore.last_mmr_search_kwargs.get("filter"), metadata_filter)


if __name__ == "__main__":
    unittest.main()
