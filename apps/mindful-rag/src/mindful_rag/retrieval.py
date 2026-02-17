"""Production retrieval pipeline with hybrid ranking, deduplication, and fallbacks."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass
class RetrievalSettings:
    """Runtime knobs for retrieval behavior."""

    top_k: int = 4
    fetch_k: int = 24
    mmr_lambda: float = 0.5
    max_per_source: int = 2
    min_hybrid_score: float = 0.05


@dataclass
class RetrievalResult:
    """Output payload from production retrieval."""

    chunks: list[dict[str, Any]]
    stats: dict[str, Any]


@dataclass
class _CandidateChunk:
    """Internal candidate representation used by fusion/reranking."""

    key: str
    content: str
    metadata: dict[str, Any]
    source_key: str
    filename: str
    category: str
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    similarity_rank: int = -1
    mmr_rank: int = -1
    hybrid_score: float = 0.0


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_PATTERN.findall(text.lower()))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_similarity_score(raw_score: Any) -> float:
    """
    Normalize assorted score ranges into [0, 1].

    Chroma relevance scores may already be in [0, 1], but this keeps behavior
    stable when adapters return distance-like values.
    """
    score = _safe_float(raw_score, default=0.0)
    if 0.0 <= score <= 1.0:
        return score
    if score > 1.0:
        return 1.0 / (1.0 + score)
    return 1.0 / (1.0 + abs(score))


def _reciprocal_rank(rank: int) -> float:
    if rank < 0:
        return 0.0
    return 1.0 / (rank + 1)


def _extract_doc_payload(doc: Any) -> tuple[str, dict[str, Any], str, str, str]:
    content = _normalize_text(str(getattr(doc, "page_content", "")))
    metadata = getattr(doc, "metadata", {}) or {}
    metadata = metadata if isinstance(metadata, dict) else {}

    source = str(metadata.get("filename") or metadata.get("source") or "Unknown")
    source_key = source.lower().strip()
    filename = source.replace(".pdf", "")
    category = str(metadata.get("category", "Unknown"))
    return content, metadata, source_key, filename, category


def _candidate_key(content: str, metadata: dict[str, Any], source_key: str) -> str:
    chunk_index = str(metadata.get("chunk_index", "na"))
    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:16]
    return f"{source_key}|{chunk_index}|{digest}"


def _lexical_overlap(query_tokens: set[str], doc_content: str) -> float:
    doc_tokens = _tokenize(doc_content)
    if not query_tokens or not doc_tokens:
        return 0.0
    overlap = len(query_tokens & doc_tokens)
    return overlap / len(query_tokens)


def _upsert_candidate(
    candidates: dict[str, _CandidateChunk],
    doc: Any,
    query_tokens: set[str],
    semantic_score: float,
    similarity_rank: int = -1,
    mmr_rank: int = -1,
) -> None:
    content, metadata, source_key, filename, category = _extract_doc_payload(doc)
    if not content:
        return

    key = _candidate_key(content, metadata, source_key)
    if key not in candidates:
        candidates[key] = _CandidateChunk(
            key=key,
            content=content,
            metadata=metadata,
            source_key=source_key,
            filename=filename,
            category=category,
            lexical_score=_lexical_overlap(query_tokens, content),
        )

    cand = candidates[key]
    cand.semantic_score = max(cand.semantic_score, semantic_score)
    if similarity_rank >= 0:
        cand.similarity_rank = (
            similarity_rank
            if cand.similarity_rank < 0
            else min(cand.similarity_rank, similarity_rank)
        )
    if mmr_rank >= 0:
        cand.mmr_rank = mmr_rank if cand.mmr_rank < 0 else min(cand.mmr_rank, mmr_rank)


def _rank_candidates(
    query: str,
    similarity_docs: list[tuple[Any, Any]],
    mmr_docs: list[Any],
    settings: RetrievalSettings,
) -> list[_CandidateChunk]:
    query_tokens = _tokenize(query)
    candidates: dict[str, _CandidateChunk] = {}

    for idx, pair in enumerate(similarity_docs):
        if not isinstance(pair, tuple) or not pair:
            continue
        doc = pair[0]
        raw_score = pair[1] if len(pair) > 1 else None
        _upsert_candidate(
            candidates=candidates,
            doc=doc,
            query_tokens=query_tokens,
            semantic_score=_normalize_similarity_score(raw_score),
            similarity_rank=idx,
        )

    for idx, doc in enumerate(mmr_docs):
        _upsert_candidate(
            candidates=candidates,
            doc=doc,
            query_tokens=query_tokens,
            # MMR itself does not expose similarity score.
            semantic_score=0.0,
            mmr_rank=idx,
        )

    for cand in candidates.values():
        rank_signal = max(
            _reciprocal_rank(cand.similarity_rank),
            _reciprocal_rank(cand.mmr_rank),
        )
        cand.hybrid_score = (
            (0.55 * cand.semantic_score)
            + (0.30 * rank_signal)
            + (0.15 * cand.lexical_score)
        )

    ranked = sorted(
        candidates.values(),
        key=lambda c: (c.hybrid_score, c.semantic_score, c.lexical_score),
        reverse=True,
    )
    if not ranked:
        return []

    filtered = [c for c in ranked if c.hybrid_score >= settings.min_hybrid_score]
    if not filtered:
        filtered = ranked

    per_source: Counter[str] = Counter()
    selected: list[_CandidateChunk] = []
    selected_keys: set[str] = set()
    for cand in filtered:
        if per_source[cand.source_key] >= max(1, settings.max_per_source):
            continue
        selected.append(cand)
        selected_keys.add(cand.key)
        per_source[cand.source_key] += 1
        if len(selected) >= max(1, settings.top_k):
            break

    if len(selected) < max(1, settings.top_k):
        for cand in filtered:
            if cand.key in selected_keys:
                continue
            selected.append(cand)
            selected_keys.add(cand.key)
            if len(selected) >= max(1, settings.top_k):
                break

    return selected[: max(1, settings.top_k)]


def _safe_similarity_search(
    query: str,
    vectorstore: Any,
    fetch_k: int,
    errors: list[str],
) -> list[tuple[Any, Any]]:
    try:
        return list(vectorstore.similarity_search_with_relevance_scores(query, k=fetch_k))
    except Exception as exc:
        errors.append(f"similarity_search_with_relevance_scores failed: {exc}")
    try:
        docs = list(vectorstore.similarity_search(query, k=fetch_k))
        return [(doc, None) for doc in docs]
    except Exception as exc:
        errors.append(f"similarity_search fallback failed: {exc}")
    return []


def _safe_mmr_search(
    query: str,
    vectorstore: Any,
    top_k: int,
    fetch_k: int,
    mmr_lambda: float,
    errors: list[str],
) -> list[Any]:
    try:
        retriever = vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": top_k,
                "fetch_k": max(fetch_k, top_k),
                "lambda_mult": mmr_lambda,
            },
        )
        return list(retriever.invoke(query))
    except Exception as exc:
        errors.append(f"mmr retriever failed: {exc}")
        return []


def production_retrieve(
    query: str,
    vectorstore: Any,
    settings: RetrievalSettings,
) -> RetrievalResult:
    """
    Hybrid production retrieval:
    1) semantic similarity candidates
    2) MMR diversification candidates
    3) score fusion + lexical rerank
    4) dedup + per-source diversity
    """
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return RetrievalResult(
            chunks=[],
            stats={"query_empty": True, "errors": [], "candidate_count": 0},
        )

    errors: list[str] = []
    fetch_k = max(int(settings.fetch_k), int(settings.top_k), 1)
    top_k = max(int(settings.top_k), 1)

    similarity_docs = _safe_similarity_search(normalized_query, vectorstore, fetch_k, errors)
    mmr_docs = _safe_mmr_search(
        normalized_query,
        vectorstore,
        top_k=top_k,
        fetch_k=fetch_k,
        mmr_lambda=float(settings.mmr_lambda),
        errors=errors,
    )

    ranked = _rank_candidates(
        query=normalized_query,
        similarity_docs=similarity_docs,
        mmr_docs=mmr_docs,
        settings=settings,
    )

    chunks = [
        {
            "content": cand.content,
            "filename": cand.filename,
            "category": cand.category,
            "score": round(cand.hybrid_score, 4),
            "source": cand.source_key,
        }
        for cand in ranked
    ]
    stats = {
        "query_empty": False,
        "used_similarity": bool(similarity_docs),
        "used_mmr": bool(mmr_docs),
        "similarity_candidates": len(similarity_docs),
        "mmr_candidates": len(mmr_docs),
        "final_chunks": len(chunks),
        "errors": errors,
    }
    return RetrievalResult(chunks=chunks, stats=stats)
