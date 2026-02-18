"""Gemini embedding adapters built on the `google-genai` SDK."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from google import genai
from google.genai import types
from langchain_core.embeddings import Embeddings


_TASK_TYPE_ALIASES = {
    "retrieval_document": "RETRIEVAL_DOCUMENT",
    "retrieval_query": "RETRIEVAL_QUERY",
    "semantic_similarity": "SEMANTIC_SIMILARITY",
    "classification": "CLASSIFICATION",
    "clustering": "CLUSTERING",
}
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _normalize_task_type(task_type: str) -> str:
    normalized = str(task_type or "").strip()
    if not normalized:
        return "RETRIEVAL_DOCUMENT"
    alias = _TASK_TYPE_ALIASES.get(normalized.lower())
    return alias if alias else normalized.upper()


def _extract_vector(item: Any) -> list[float]:
    values = getattr(item, "values", None)
    if values is None and isinstance(item, dict):
        values = item.get("values")
    if values is None:
        raise ValueError("Embedding response did not include vector values.")
    return [float(v) for v in values]


def _extract_vectors(result: Any) -> list[list[float]]:
    batch = getattr(result, "embeddings", None)
    if batch is None:
        one = getattr(result, "embedding", None)
        if one is not None:
            batch = [one]
    if batch is None:
        raise ValueError("Embedding response did not include embeddings.")
    return [_extract_vector(item) for item in batch]


class HashingEmbeddings(Embeddings):
    """
    Deterministic local embeddings that require no network/API key.

    This is a pragmatic fallback for ingestion/retrieval continuity when
    remote embedding providers are unavailable.
    """

    def __init__(self, dimension: int = 512):
        self.dimension = max(64, int(dimension))
        self.backend_name = "hashing"

    def _hash_pair(self, token: str) -> tuple[int, float]:
        digest = hashlib.sha1(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % self.dimension
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        return idx, sign

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        tokens = _TOKEN_PATTERN.findall((text or "").lower())
        if not tokens:
            return vec

        for token in tokens:
            idx, sign = self._hash_pair(token)
            vec[idx] += sign

        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0.0:
            vec = [v / norm for v in vec]
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one("" if text is None else str(text)) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(str(text))


class GeminiGenAIEmbeddings(Embeddings):
    """LangChain-compatible embedding adapter using `client.models.embed_content`."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-001",
        task_type: str = "RETRIEVAL_DOCUMENT",
        batch_size: int = 64,
    ):
        self.model = model
        self.task_type = _normalize_task_type(task_type)
        self.batch_size = max(1, int(batch_size))
        self.backend_name = "gemini"
        self._client = genai.Client(api_key=api_key)

    def _embed_batch(self, texts: list[str], task_type: str) -> list[list[float]]:
        if not texts:
            return []
        config = types.EmbedContentConfig(task_type=_normalize_task_type(task_type))
        
        # Retry logic for rate limits
        max_retries = 5
        base_delay = 2.0
        
        for attempt in range(max_retries + 1):
            try:
                result = self._client.models.embed_content(
                    model=self.model,
                    contents=texts,
                    config=config,
                )
                return _extract_vectors(result)
            except Exception as e:
                # Check for 429 using string matching as provided in the error log
                is_rate_limit = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
                if is_rate_limit and attempt < max_retries:
                    sleep_time = base_delay * (2 ** attempt)
                    print(f"Gemini embedding rate limited. Retrying in {sleep_time}s...")
                    import time
                    time.sleep(sleep_time)
                    continue
                if attempt == max_retries:
                    raise e
        return []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        normalized_texts = ["" if text is None else str(text) for text in texts]
        vectors: list[list[float]] = []
        
        import time
        # Add a small delay between batches to be polite to the API
        inter_batch_delay = 0.5 
        
        for start in range(0, len(normalized_texts), self.batch_size):
            chunk = normalized_texts[start : start + self.batch_size]
            vectors.extend(self._embed_batch(chunk, self.task_type))
            if start + self.batch_size < len(normalized_texts):
                time.sleep(inter_batch_delay)
                
        return vectors

    def embed_query(self, text: str) -> list[float]:
        vectors = self._embed_batch([str(text)], task_type="RETRIEVAL_QUERY")
        return vectors[0] if vectors else []


class GeminiDualTaskEmbeddings(Embeddings):
    """Use task-specific Gemini embeddings for document and query operations."""

    def __init__(self, api_key: str, model: str = "gemini-embedding-001"):
        self._doc_embedder = GeminiGenAIEmbeddings(
            api_key=api_key,
            model=model,
            task_type="RETRIEVAL_DOCUMENT",
        )
        self._query_embedder = GeminiGenAIEmbeddings(
            api_key=api_key,
            model=model,
            task_type="RETRIEVAL_QUERY",
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._doc_embedder.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._query_embedder.embed_query(text)


class FallbackEmbeddings(Embeddings):
    """
    Wrap two embedding providers and permanently switch to fallback on failure.
    """

    def __init__(self, primary: Embeddings, fallback: Embeddings):
        self.primary = primary
        self.fallback = fallback
        self._using_fallback = False
        self.backend_name = getattr(primary, "backend_name", "primary")

    def _activate_fallback(self) -> None:
        self._using_fallback = True
        self.backend_name = getattr(self.fallback, "backend_name", "fallback")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self._using_fallback:
            return self.fallback.embed_documents(texts)
        try:
            return self.primary.embed_documents(texts)
        except Exception as e:
            print(f"FallbackEmbeddings: Primary failed with error: {e}")
            self._activate_fallback()
            return self.fallback.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        if self._using_fallback:
            return self.fallback.embed_query(text)
        try:
            return self.primary.embed_query(text)
        except Exception:
            self._activate_fallback()
            return self.fallback.embed_query(text)


def create_document_embeddings(
    api_key: str | None,
    model: str = "gemini-embedding-001",
    task_type: str = "RETRIEVAL_DOCUMENT",
    allow_fallback: bool = True,
) -> Embeddings:
    fallback = HashingEmbeddings()
    if not api_key:
        return fallback if allow_fallback else fallback

    primary = GeminiGenAIEmbeddings(
        api_key=api_key,
        model=model,
        task_type=task_type,
    )
    if not allow_fallback:
        return primary
    return FallbackEmbeddings(primary=primary, fallback=fallback)


def create_dual_task_embeddings(
    api_key: str | None,
    model: str = "gemini-embedding-001",
    allow_fallback: bool = True,
) -> Embeddings:
    fallback = HashingEmbeddings()
    if not api_key:
        return fallback if allow_fallback else fallback

    primary = GeminiDualTaskEmbeddings(api_key=api_key, model=model)
    if not allow_fallback:
        return primary
    return FallbackEmbeddings(primary=primary, fallback=fallback)
