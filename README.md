# Mindful RAG Scheduler

Single-project structure for the student wellness RAG app and ablation pipelines.

## Folder Layout

```text
src/mindful_rag/
  app.py
  config.py
  evaluators.py
  ingest_raw.py
  ingest_intro_concl.py
  ingest_by_type.py
scripts/
  run_app.py
  ingest.py
  verify_chroma.py
  demo_evaluators.py
tests/
  test_evaluators.py
configs/experiments/
  raw.yaml
  intro_concl.yaml
  by_type.yaml
data/
  raw/research_papers/*.pdf
  index/research_index.csv
  chroma/raw/
  chroma/intro_concl/
  chroma/by_type/
```

## Setup

1. Install dependencies:
   `pip install -r requirements.txt`
2. Create `.env` in project root:
   - `GOOGLE_API_KEY=...`

## Run

- Ingest vectors:
  - `python scripts/ingest.py --experiment raw`
  - `python scripts/ingest.py --experiment raw --reset-db` (optional clean rebuild)
  - `python scripts/ingest.py --experiment intro_concl`
  - `python scripts/ingest.py --experiment by_type`

- Launch app:
  - `python scripts/run_app.py --experiment by_type`
  - Optional retrieval tuning via env:
    - `RETRIEVAL_TOP_K` (default `4`)
    - `RETRIEVAL_FETCH_K` (default `24`)
    - `RETRIEVAL_MAX_PER_SOURCE` (default `2`)
    - `RETRIEVAL_MMR_LAMBDA` (default `0.5`)
    - `RETRIEVAL_MIN_SCORE` (default `0.05`)

- Verify DB:
  - `python scripts/verify_chroma.py --experiment by_type`
