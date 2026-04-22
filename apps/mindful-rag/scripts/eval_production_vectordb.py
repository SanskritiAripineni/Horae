"""
Production VectorDB Baseline Evaluation
========================================
Evaluates retrieval quality of the main project's wellness_papers_gemini
ChromaDB collection (vectordb/chroma_db/) across all 5 intervention categories.

Metrics per query: Precision@k, category hit rate, avg cosine similarity.
Aggregated: per-category precision, macro-averaged precision.

Run from the repo root:
    python apps/mindful-rag/scripts/eval_production_vectordb.py

Output: apps/mindful-rag/results/production_vectordb_eval_<timestamp>.json
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean

# --- Path setup -----------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from tools.vectordb_client import VectorDBClient  # noqa: E402

# ── Evaluation queries (5 per category) ────────────────────────────────────
# Each query has an expected_category so we can compute precision.
QUERIES = [
    # Sleep Hygiene
    {"query": "I have been struggling to fall asleep and waking up frequently at night.",
     "expected_category": "Sleep Hygiene"},
    {"query": "Tips for improving sleep quality and establishing a healthy bedtime routine.",
     "expected_category": "Sleep Hygiene"},
    {"query": "How does screen time before bed affect sleep?",
     "expected_category": "Sleep Hygiene"},
    {"query": "I keep staying up until 2am and feel exhausted during the day.",
     "expected_category": "Sleep Hygiene"},
    {"query": "Strategies for managing insomnia and sleep deprivation.",
     "expected_category": "Sleep Hygiene"},

    # Stress Management
    {"query": "I feel overwhelmed by deadlines and constant work pressure.",
     "expected_category": "Stress Management"},
    {"query": "Techniques for reducing anxiety and managing academic stress.",
     "expected_category": "Stress Management"},
    {"query": "How can I decompress after a stressful day at work?",
     "expected_category": "Stress Management"},
    {"query": "I am experiencing burnout from back-to-back responsibilities.",
     "expected_category": "Stress Management"},
    {"query": "Evidence-based approaches for coping with chronic stress.",
     "expected_category": "Stress Management"},

    # Social connection  (NOTE: DB category is "Social connection", not "Social Connection")
    {"query": "I have been feeling isolated and lonely recently.",
     "expected_category": "Social connection"},
    {"query": "How does social support affect mental health and wellbeing?",
     "expected_category": "Social connection"},
    {"query": "I rarely see friends due to my busy schedule and it is affecting my mood.",
     "expected_category": "Social connection"},
    {"query": "Interventions for improving social connectedness in daily life.",
     "expected_category": "Social connection"},
    {"query": "The role of community and belonging in reducing depression.",
     "expected_category": "Social connection"},

    # Physical Activity
    {"query": "I have been sedentary all week and feel sluggish.",
     "expected_category": "Physical Activity"},
    {"query": "What are the mental health benefits of regular exercise?",
     "expected_category": "Physical Activity"},
    {"query": "I want to incorporate short physical activity breaks during my workday.",
     "expected_category": "Physical Activity"},
    {"query": "Evidence for walking as an effective stress-reduction intervention.",
     "expected_category": "Physical Activity"},
    {"query": "How to motivate myself to exercise when feeling low energy.",
     "expected_category": "Physical Activity"},

    # NOTE: "Mindfulness" was not ingested into the production collection as of this eval.
    # These queries are included to document the gap; expected_category will never match.
    {"query": "I cannot stop ruminating on negative thoughts.",
     "expected_category": "Mindfulness"},
    {"query": "Mindfulness and meditation techniques for improving focus.",
     "expected_category": "Mindfulness"},
    {"query": "Breathing exercises and grounding techniques for anxiety.",
     "expected_category": "Mindfulness"},
    {"query": "How does mindfulness-based stress reduction (MBSR) work?",
     "expected_category": "Mindfulness"},
    {"query": "Brief mindfulness practices that can be done in under 10 minutes.",
     "expected_category": "Mindfulness"},
]

# Categories confirmed present in the production collection (29 docs total as of eval)
PRESENT_CATEGORIES = ["Sleep Hygiene", "Stress Management", "Social connection", "Physical Activity"]
MISSING_CATEGORIES = ["Mindfulness"]  # needs ingestion — see vectordb/ingest_simple.py

TOP_K = 4
RESULTS_DIR = Path(__file__).parent.parent / "results"


def run_eval() -> dict:
    print(f"Connecting to vectordb at {REPO_ROOT / 'vectordb' / 'chroma_db'} ...")
    client = VectorDBClient(chroma_dir=str(REPO_ROOT / "vectordb" / "chroma_db"))

    if not client.initialize():
        raise RuntimeError(
            "VectorDBClient failed to initialize. "
            "Ensure vectordb/chroma_db/ exists and GEMINI_API_KEY is set."
        )

    print(f"Running {len(QUERIES)} queries (top_k={TOP_K}) ...")
    per_query: list[dict] = []
    per_category: dict[str, list[float]] = {}

    for i, q in enumerate(QUERIES):
        query_text = q["query"]
        expected_cat = q["expected_category"]

        results = client.retrieve(query_text, top_k=TOP_K)

        retrieved_categories = [r["category"] for r in results]
        hits = [1 if cat == expected_cat else 0 for cat in retrieved_categories]
        precision_at_k = sum(hits) / len(hits) if hits else 0.0

        per_query.append({
            "query": query_text,
            "expected_category": expected_cat,
            "retrieved_categories": retrieved_categories,
            "precision_at_k": round(precision_at_k, 4),
            "hits": hits,
            "retrieved_sources": [r["source"] for r in results],
        })

        per_category.setdefault(expected_cat, []).append(precision_at_k)

        print(f"  [{i+1:02d}/{len(QUERIES)}] P@{TOP_K}={precision_at_k:.2f} | "
              f"expected={expected_cat} | got={retrieved_categories}")

    # Aggregate
    category_summary = {
        cat: {
            "precision_at_k_mean": round(mean(scores), 4),
            "query_count": len(scores),
        }
        for cat, scores in per_category.items()
    }
    all_precisions = [r["precision_at_k"] for r in per_query]
    macro_precision = round(mean(all_precisions), 4)

    report = {
        "timestamp": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        "chroma_dir": str(REPO_ROOT / "vectordb" / "chroma_db"),
        "collection": "wellness_papers_gemini",
        "embedding_model": "gemini-embedding-2-preview",
        "top_k": TOP_K,
        "query_count": len(QUERIES),
        "total_docs_in_collection": 29,
        "present_categories": PRESENT_CATEGORIES,
        "missing_categories": MISSING_CATEGORIES,
        "macro_precision_at_k": macro_precision,
        "macro_precision_at_k_present_only": round(
            mean(r["precision_at_k"] for r in per_query
                 if r["expected_category"] in PRESENT_CATEGORIES), 4
        ),
        "category_summary": category_summary,
        "per_query": per_query,
    }
    return report


def main():
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=False)

    if not os.environ.get("GEMINI_API_KEY"):
        print("Warning: GEMINI_API_KEY not set — embedding calls will fail.")

    report = run_eval()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"production_vectordb_eval_{ts}.json"
    out_path.write_text(json.dumps(report, indent=2))

    print(f"\n{'='*60}")
    print(f"Macro Precision@{TOP_K}: {report['macro_precision_at_k']}")
    print(f"\nPer-category:")
    for cat, stats in report["category_summary"].items():
        print(f"  {cat:<25} P@{TOP_K}={stats['precision_at_k_mean']:.2f}  (n={stats['query_count']})")
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()
