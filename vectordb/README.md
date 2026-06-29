# VectorDB Demo Corpus

This directory is the lightweight legacy/local vector DB path used for quick retrieval experiments.

- `paper_map.csv`: 18-row CSV map with filename, category, and short text content.
- `research_papers/`: matching local PDFs for those 18 rows.
- `ingest_csv.py`: local HuggingFace embedding ingestion from `paper_map.csv`.
- `ingest_simple.py`: Gemini native-PDF embedding ingestion from `research_papers/`.

The full paper-facing 61-entry retrieval corpus is in `apps/mindful-rag/data/index/research_corpus_manifest.csv`. Use that manifest for paper/reviewer claims. Generated `chroma_db/` stores are intentionally not checked into `main`.
