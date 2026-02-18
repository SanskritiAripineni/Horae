"""Evaluate retrieval quality across source filters (all/relevant_info/intro_concl/raw)."""

from __future__ import annotations

import argparse
import json
import os
import re
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from langchain_chroma import Chroma

from _bootstrap import bootstrap_local_src

bootstrap_local_src()

from mindful_rag.config import ROOT_DIR, get_env_file, get_experiment
from mindful_rag.embeddings import create_dual_task_embeddings
from mindful_rag.retrieval import RetrievalSettings, production_retrieve


DEFAULT_QUERY_FILE = ROOT_DIR / "configs" / "evaluation" / "source_filter_queries.json"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "data" / "evals"
DEFAULT_EXPERIMENT = "csv_sources"
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
DEFAULT_FILTERS = ["all", "relevant_info", "intro_concl"]
VALID_FILTERS = {"all", "relevant_info", "intro_concl", "raw"}

warnings.filterwarnings(
    "ignore",
    message=r"Relevance scores must be between 0 and 1",
    category=UserWarning,
)


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, parsed))


def _env_float(name: str, default: float, min_value: float, max_value: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        parsed = float(raw)
    except ValueError:
        return default
    return max(min_value, min(max_value, parsed))


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_PATTERN.findall((text or "").lower()))


def _query_overlap_score(query: str, content: str) -> float:
    q = _tokenize(query)
    if not q:
        return 0.0
    c = _tokenize(content)
    if not c:
        return 0.0
    return len(q & c) / len(q)


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(mean(values))


def _parse_filters(raw: str) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for token in [item.strip().lower().replace("-", "_") for item in raw.split(",") if item.strip()]:
        if token not in VALID_FILTERS or token in seen:
            continue
        seen.add(token)
        resolved.append(token)
    return resolved or list(DEFAULT_FILTERS)


def _parse_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() not in {"0", "false", "no", "off", ""}


def _load_query_set(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("Query file must be a JSON array.")

    queries: list[dict[str, Any]] = []
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            continue
        query = str(item.get("query", "")).strip()
        if not query:
            continue
        query_id = str(item.get("id", f"q{idx+1}")).strip() or f"q{idx+1}"
        expected_categories = [str(v).strip() for v in item.get("expected_categories", []) if str(v).strip()]
        expected_keywords = [str(v).strip().lower() for v in item.get("expected_keywords", []) if str(v).strip()]
        queries.append(
            {
                "id": query_id,
                "query": query,
                "expected_categories": expected_categories,
                "expected_keywords": expected_keywords,
            }
        )
    if not queries:
        raise ValueError("Query file contained no valid queries.")
    return queries


def _build_settings() -> RetrievalSettings:
    return RetrievalSettings(
        top_k=_env_int("RETRIEVAL_TOP_K", 4, 1, 12),
        fetch_k=_env_int("RETRIEVAL_FETCH_K", 24, 4, 128),
        mmr_lambda=_env_float("RETRIEVAL_MMR_LAMBDA", 0.5, 0.0, 1.0),
        max_per_source=_env_int("RETRIEVAL_MAX_PER_SOURCE", 2, 1, 6),
        min_hybrid_score=_env_float("RETRIEVAL_MIN_SCORE", 0.05, 0.0, 1.0),
    )


def _evaluate_one(
    query_item: dict[str, Any],
    source_filter: str,
    vectorstore: Chroma,
    settings: RetrievalSettings,
) -> dict[str, Any]:
    metadata_filter = None if source_filter == "all" else {"retrieval_source": source_filter}
    result = production_retrieve(
        query=query_item["query"],
        vectorstore=vectorstore,
        settings=settings,
        metadata_filter=metadata_filter,
    )
    chunks = result.chunks
    chunk_scores = [float(chunk.get("score", 0.0)) for chunk in chunks]
    overlap_scores = [_query_overlap_score(query_item["query"], str(chunk.get("content", ""))) for chunk in chunks]

    source_counts = Counter(str(chunk.get("source", "")).strip() for chunk in chunks)
    source_concentration = 0.0
    if chunks and source_counts:
        source_concentration = max(source_counts.values()) / len(chunks)

    combined_text = " ".join(str(chunk.get("content", "")).lower() for chunk in chunks)
    expected_keywords = query_item["expected_keywords"]
    expected_categories = {c.lower() for c in query_item["expected_categories"]}
    retrieved_categories = {
        str(chunk.get("category", "")).strip().lower()
        for chunk in chunks
        if str(chunk.get("category", "")).strip()
    }

    keyword_hits = sum(1 for kw in expected_keywords if kw in combined_text)
    keyword_coverage = (keyword_hits / len(expected_keywords)) if expected_keywords else None
    category_hit = (len(expected_categories & retrieved_categories) > 0) if expected_categories else None

    row = {
        "query_id": query_item["id"],
        "query": query_item["query"],
        "source_filter": source_filter,
        "retrieved_count": len(chunks),
        "avg_chunk_score": round(_safe_mean(chunk_scores), 4),
        "top_chunk_score": round(max(chunk_scores), 4) if chunk_scores else 0.0,
        "avg_query_overlap": round(_safe_mean(overlap_scores), 4),
        "unique_sources": len(source_counts),
        "unique_categories": len(retrieved_categories),
        "source_concentration": round(source_concentration, 4),
        "keyword_hits": keyword_hits,
        "keyword_total": len(expected_keywords),
        "keyword_hit_rate": round(keyword_coverage, 4) if keyword_coverage is not None else None,
        "category_hit": category_hit,
        "expected_categories": ", ".join(query_item["expected_categories"]),
        "expected_keywords": ", ".join(expected_keywords),
        "used_similarity": bool(result.stats.get("used_similarity")),
        "used_mmr": bool(result.stats.get("used_mmr")),
        "similarity_candidates": int(result.stats.get("similarity_candidates", 0)),
        "mmr_candidates": int(result.stats.get("mmr_candidates", 0)),
        "errors_count": len(result.stats.get("errors", [])),
        "errors": " | ".join(result.stats.get("errors", [])),
    }
    return row


def _summarize(rows: list[dict[str, Any]], source_filters: list[str]) -> list[dict[str, Any]]:
    summary_rows: list[dict[str, Any]] = []
    for source_filter in source_filters:
        subset = [row for row in rows if row["source_filter"] == source_filter]
        if not subset:
            continue

        keyword_rows = [row for row in subset if row["keyword_total"] > 0]
        category_rows = [row for row in subset if row["category_hit"] is not None]

        summary_rows.append(
            {
                "source_filter": source_filter,
                "queries": len(subset),
                "queries_with_results": sum(1 for row in subset if row["retrieved_count"] > 0),
                "avg_retrieved_count": round(_safe_mean([float(row["retrieved_count"]) for row in subset]), 4),
                "mean_avg_chunk_score": round(_safe_mean([float(row["avg_chunk_score"]) for row in subset]), 4),
                "mean_top_chunk_score": round(_safe_mean([float(row["top_chunk_score"]) for row in subset]), 4),
                "mean_query_overlap": round(_safe_mean([float(row["avg_query_overlap"]) for row in subset]), 4),
                "mean_unique_sources": round(_safe_mean([float(row["unique_sources"]) for row in subset]), 4),
                "mean_source_concentration": round(
                    _safe_mean([float(row["source_concentration"]) for row in subset]),
                    4,
                ),
                "keyword_hit_rate": round(
                    _safe_mean([float(row["keyword_hit_rate"]) for row in keyword_rows if row["keyword_hit_rate"] is not None]),
                    4,
                ),
                "category_hit_rate": round(
                    _safe_mean([1.0 if bool(row["category_hit"]) else 0.0 for row in category_rows]),
                    4,
                ),
                "queries_with_errors": sum(1 for row in subset if row["errors_count"] > 0),
            }
        )
    return summary_rows


def evaluate(
    experiment_name: str,
    source_filters: list[str],
    query_file: Path,
    output_dir: Path,
    output_prefix: str,
    allow_embedding_fallback: bool,
) -> dict[str, Any]:
    experiment = get_experiment(experiment_name)
    query_set = _load_query_set(query_file)
    settings = _build_settings()

    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment.")

    embeddings = create_dual_task_embeddings(
        api_key=google_api_key,
        model="gemini-embedding-001",
        allow_fallback=allow_embedding_fallback,
    )
    vectorstore = Chroma(
        persist_directory=str(experiment.chroma_dir),
        embedding_function=embeddings,
        collection_name=experiment.collection_name,
    )

    detail_rows: list[dict[str, Any]] = []
    for query_item in query_set:
        for source_filter in source_filters:
            detail_rows.append(
                _evaluate_one(
                    query_item=query_item,
                    source_filter=source_filter,
                    vectorstore=vectorstore,
                    settings=settings,
                )
            )

    summary_rows = _summarize(detail_rows, source_filters=source_filters)

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    details_csv = output_dir / f"{output_prefix}_{stamp}_details.csv"
    summary_csv = output_dir / f"{output_prefix}_{stamp}_summary.csv"
    summary_json = output_dir / f"{output_prefix}_{stamp}_summary.json"

    pd.DataFrame(detail_rows).to_csv(details_csv, index=False)
    pd.DataFrame(summary_rows).to_csv(summary_csv, index=False)

    summary_payload = {
        "experiment": experiment.name,
        "collection_name": experiment.collection_name,
        "chroma_dir": str(experiment.chroma_dir),
        "source_filters": source_filters,
        "query_file": str(query_file),
        "query_count": len(query_set),
        "retrieval_settings": {
            "top_k": settings.top_k,
            "fetch_k": settings.fetch_k,
            "mmr_lambda": settings.mmr_lambda,
            "max_per_source": settings.max_per_source,
            "min_hybrid_score": settings.min_hybrid_score,
        },
        "embedding_backend": getattr(embeddings, "backend_name", "unknown"),
        "outputs": {
            "details_csv": str(details_csv),
            "summary_csv": str(summary_csv),
        },
        "summary_rows": summary_rows,
    }
    with summary_json.open("w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, indent=2)

    summary_payload["outputs"]["summary_json"] = str(summary_json)
    return summary_payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate retrieval quality across source filters and emit side-by-side metrics.",
    )
    parser.add_argument(
        "--experiment",
        default=DEFAULT_EXPERIMENT,
        help="Experiment config name to evaluate (default: csv_sources).",
    )
    parser.add_argument(
        "--source-filters",
        default=",".join(DEFAULT_FILTERS),
        help="Comma-separated source filters: all,relevant_info,intro_concl,raw",
    )
    parser.add_argument(
        "--query-file",
        default=str(DEFAULT_QUERY_FILE),
        help="JSON array of queries with optional expected_categories/expected_keywords.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory to write result artifacts.",
    )
    parser.add_argument(
        "--output-prefix",
        default="source_filter_eval",
        help="Filename prefix for result artifacts.",
    )
    parser.add_argument(
        "--allow-embedding-fallback",
        action="store_true",
        help="Allow local hashing fallback when remote embeddings are unavailable.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(dotenv_path=get_env_file())

    parser = _build_parser()
    args = parser.parse_args(argv)

    source_filters = _parse_filters(args.source_filters)
    query_file = Path(args.query_file).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()

    payload = evaluate(
        experiment_name=args.experiment,
        source_filters=source_filters,
        query_file=query_file,
        output_dir=output_dir,
        output_prefix=str(args.output_prefix).strip() or "source_filter_eval",
        allow_embedding_fallback=(
            bool(args.allow_embedding_fallback)
            or _parse_bool(os.getenv("EVAL_ALLOW_EMBEDDING_FALLBACK"), default=False)
        ),
    )

    print("\nSOURCE FILTER EVALUATION COMPLETE")
    print(f"experiment={payload['experiment']}")
    print(f"query_count={payload['query_count']}")
    print(f"source_filters={','.join(payload['source_filters'])}")
    print(f"embedding_backend={payload['embedding_backend']}")
    print(f"details_csv={payload['outputs']['details_csv']}")
    print(f"summary_csv={payload['outputs']['summary_csv']}")
    print(f"summary_json={payload['outputs']['summary_json']}")
    print("\nSummary:")
    for row in payload["summary_rows"]:
        print(
            f"  - {row['source_filter']}: "
            f"keyword_hit_rate={row['keyword_hit_rate']}, "
            f"category_hit_rate={row['category_hit_rate']}, "
            f"mean_avg_chunk_score={row['mean_avg_chunk_score']}, "
            f"mean_query_overlap={row['mean_query_overlap']}, "
            f"queries_with_results={row['queries_with_results']}/{row['queries']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
