"""
Apples-to-apples comparison: Gemini Embedding 2 (native PDF) vs CSV-extracted baselines.

Produces a unified table of metrics computed the SAME way for all approaches.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from statistics import mean

import pandas as pd
from chromadb import PersistentClient
from dotenv import load_dotenv

import sys, os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(__file__)))
from _bootstrap import bootstrap_local_src
bootstrap_local_src()

from mindful_rag.config import ROOT_DIR, get_env_file

# ── paths ────────────────────────────────────────────────────────────────
QUERY_FILE       = ROOT_DIR / "configs" / "evaluation" / "source_filter_queries.json"
INDEX_CSV        = ROOT_DIR / "data" / "index" / "research_index.csv"
GEMINI_CHROMA    = str(ROOT_DIR / "data" / "evals" / "chroma_gemini_native")
GEMINI_COLL      = "gemini_native_pdfs"
GEMINI_MODEL     = "gemini-embedding-2-preview"
OUTPUT_DIR       = ROOT_DIR / "data" / "evals"

# ── helpers ──────────────────────────────────────────────────────────────
TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall((text or "").lower()))


def _safe_mean(vals: list[float]) -> float:
    return round(mean(vals), 4) if vals else 0.0


def load_queries() -> list[dict]:
    with QUERY_FILE.open() as f:
        return json.load(f)


def build_filename_to_category() -> dict[str, str]:
    """Map PDF filename stems → category from the research index."""
    df = pd.read_csv(INDEX_CSV)
    mapping: dict[str, str] = {}
    for _, row in df.iterrows():
        title = str(row.get("Paper Title", "")).strip()
        category = str(row.get("Category (The Folder)", "")).strip()
        if title and category:
            # The PDF filenames are approximately the paper titles
            mapping[title.lower()] = category
    return mapping


def fuzzy_category_lookup(filename: str, mapping: dict[str, str]) -> str | None:
    """Best-effort: find category for a retrieved PDF by fuzzy-matching title."""
    fn_lower = filename.lower().replace(".pdf", "").replace("-", " ").strip()
    fn_tokens = _tokenize(fn_lower)
    best_score, best_cat = 0.0, None
    for title_lower, cat in mapping.items():
        title_tokens = _tokenize(title_lower)
        if not title_tokens:
            continue
        overlap = len(fn_tokens & title_tokens) / max(len(fn_tokens), 1)
        if overlap > best_score:
            best_score = overlap
            best_cat = cat
    return best_cat if best_score > 0.35 else None


# ── Gemini native evaluation ────────────────────────────────────────────
def evaluate_gemini_native(queries: list[dict], cat_map: dict[str, str]) -> list[dict]:
    """Re-evaluate the Gemini native collection with the SAME metrics as the baseline."""
    from google import genai

    load_dotenv(get_env_file())
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    chroma = PersistentClient(path=GEMINI_CHROMA)
    collection = chroma.get_collection(GEMINI_COLL)

    rows: list[dict] = []
    for q in queries:
        query_text = q["query"]
        expected_cats = {c.lower() for c in q.get("expected_categories", [])}
        expected_kws  = [kw.lower() for kw in q.get("expected_keywords", [])]

        # embed the query
        emb = client.models.embed_content(
            model=GEMINI_MODEL, contents=query_text
        ).embeddings[0].values

        result = collection.query(query_embeddings=[emb], n_results=4)
        docs       = result["documents"][0]     if result["documents"]     else []
        metas      = result["metadatas"][0]     if result["metadatas"]     else []
        distances  = result["distances"][0]     if result["distances"]     else []

        # Convert cosine distance → similarity score (1 - distance)
        sim_scores = [1.0 - d for d in distances]

        # map filenames → categories
        retrieved_cats: set[str] = set()
        filenames: list[str] = []
        for m in metas:
            fn = str(m.get("source", ""))
            filenames.append(fn)
            cat = fuzzy_category_lookup(fn, cat_map)
            if cat:
                retrieved_cats.add(cat.lower())

        # keyword coverage: check if keywords appear in the PDF filenames
        # (since we don't store extracted text in the native collection)
        combined_text = " ".join(fn.lower() for fn in filenames)
        kw_hits = sum(1 for kw in expected_kws if kw in combined_text)

        source_counts = Counter(filenames)
        source_conc = (max(source_counts.values()) / len(docs)) if docs and source_counts else 0.0

        rows.append({
            "query_id": q["id"],
            "source_filter": "gemini_native_pdf",
            "retrieved_count": len(docs),
            "avg_sim_score": _safe_mean(sim_scores),
            "top_sim_score": round(max(sim_scores), 4) if sim_scores else 0.0,
            "unique_sources": len(source_counts),
            "source_concentration": round(source_conc, 4),
            "keyword_hits": kw_hits,
            "keyword_total": len(expected_kws),
            "keyword_hit_rate": round(kw_hits / len(expected_kws), 4) if expected_kws else None,
            "category_hit": len(expected_cats & retrieved_cats) > 0 if expected_cats else None,
        })

    return rows


# ── Load baseline results ───────────────────────────────────────────────
def load_baseline(csv_path: Path) -> list[dict]:
    df = pd.read_csv(csv_path)
    rows: list[dict] = []
    for _, r in df.iterrows():
        rows.append({
            "query_id": r["query_id"],
            "source_filter": r["source_filter"],
            "retrieved_count": int(r["retrieved_count"]),
            "avg_sim_score": round(float(r["avg_chunk_score"]), 4),
            "top_sim_score": round(float(r["top_chunk_score"]), 4),
            "unique_sources": int(r["unique_sources"]),
            "source_concentration": round(float(r["source_concentration"]), 4),
            "keyword_hits": int(r["keyword_hits"]),
            "keyword_total": int(r["keyword_total"]),
            "keyword_hit_rate": round(float(r["keyword_hit_rate"]), 4) if pd.notna(r["keyword_hit_rate"]) else None,
            "category_hit": r["category_hit"] if pd.notna(r["category_hit"]) else None,
        })
    return rows


# ── Summarise ────────────────────────────────────────────────────────────
def summarise(rows: list[dict]) -> dict:
    kw_rows  = [r for r in rows if r["keyword_total"]  > 0]
    cat_rows = [r for r in rows if r["category_hit"] is not None]
    return {
        "source_filter": rows[0]["source_filter"],
        "queries": len(rows),
        "queries_with_results": sum(1 for r in rows if r["retrieved_count"] > 0),
        "avg_sim_score": _safe_mean([r["avg_sim_score"] for r in rows]),
        "top_sim_score": _safe_mean([r["top_sim_score"] for r in rows]),
        "mean_unique_sources": _safe_mean([float(r["unique_sources"]) for r in rows]),
        "mean_source_concentration": _safe_mean([float(r["source_concentration"]) for r in rows]),
        "keyword_hit_rate": _safe_mean([float(r["keyword_hit_rate"]) for r in kw_rows if r["keyword_hit_rate"] is not None]),
        "category_hit_rate": _safe_mean([1.0 if r["category_hit"] else 0.0 for r in cat_rows]),
    }


# ── Main ─────────────────────────────────────────────────────────────────
def main() -> int:
    load_dotenv(get_env_file())
    queries = load_queries()
    cat_map = build_filename_to_category()

    # 1. Baseline
    baseline_csv = ROOT_DIR / "data" / "evals" / "source_filter_eval_20260217_192619_details.csv"
    baseline_rows = load_baseline(baseline_csv)

    # 2. Gemini native
    print("Evaluating Gemini Embedding 2 (native PDF)...")
    gemini_rows = evaluate_gemini_native(queries, cat_map)

    # 3. Group & summarise
    all_rows = baseline_rows + gemini_rows
    groups: dict[str, list[dict]] = {}
    for r in all_rows:
        groups.setdefault(r["source_filter"], []).append(r)

    summaries = [summarise(v) for v in groups.values()]
    order = ["all", "relevant_info", "intro_concl", "gemini_native_pdf"]
    summaries.sort(key=lambda s: order.index(s["source_filter"]) if s["source_filter"] in order else 99)

    # 4. Print comparison table
    print("\n" + "=" * 90)
    print("UNIFIED COMPARISON — Same Metrics Across All Methods")
    print("=" * 90)
    header = f"{'Method':<22} {'AvgSim':>8} {'TopSim':>8} {'KW Hit%':>8} {'Cat Hit%':>9} {'UniqSrc':>8} {'SrcConc':>8}"
    print(header)
    print("-" * 90)
    for s in summaries:
        line = (
            f"{s['source_filter']:<22} "
            f"{s['avg_sim_score']:>8.4f} "
            f"{s['top_sim_score']:>8.4f} "
            f"{s['keyword_hit_rate']:>8.4f} "
            f"{s['category_hit_rate']:>9.4f} "
            f"{s['mean_unique_sources']:>8.4f} "
            f"{s['mean_source_concentration']:>8.4f}"
        )
        print(line)
    print("=" * 90)

    # 5. Save JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"unified_comparison_{stamp}.json"
    payload = {
        "methods": [s["source_filter"] for s in summaries],
        "summaries": summaries,
        "detail_rows": all_rows,
    }
    # Convert bools for JSON
    for r in payload["detail_rows"]:
        if isinstance(r.get("category_hit"), (bool,)):
            r["category_hit"] = bool(r["category_hit"])
    with out_path.open("w") as f:
        json.dump(payload, f, indent=2, default=str)

    print(f"\nSaved to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
