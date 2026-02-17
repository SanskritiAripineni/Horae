# Mindful RAG Scheduler

Student wellness RAG app plus ingestion/ablation pipelines.

## Folder Layout

```text
src/mindful_rag/
  __main__.py
  cli.py
  app.py
  config.py
  retrieval.py
  evaluators.py
  ingest_raw.py
  ingest_intro_concl.py
  ingest_by_type.py
scripts/
  _bootstrap.py
  run_app.py
  ingest.py
  verify_chroma.py
  demo_evaluators.py
tests/
  conftest.py
  test_retrieval.py
  test_evaluators.py
configs/experiments/
  raw.yaml
  intro_concl.yaml
  by_type.yaml
data/
  raw/research_papers/*.pdf
  index/research_index.csv
  chroma/<experiment_name>/
pyproject.toml
```

## Setup

1. Install dependencies:
   - `pip install -r requirements.txt`
   - `pip install -e .`
2. Create `.env` in project root:
   - `GOOGLE_API_KEY=...`

## Run

- Ingest vectors:
  - `mindful-rag ingest --experiment raw`
  - `mindful-rag ingest --experiment raw --reset-db` (optional clean rebuild)
  - `mindful-rag ingest --experiment intro_concl`
  - `mindful-rag ingest --experiment by_type`

- Launch app:
  - `mindful-rag run-app --experiment by_type`
  - Optional retrieval tuning via env:
    - `RETRIEVAL_TOP_K` (default `4`)
    - `RETRIEVAL_FETCH_K` (default `24`)
    - `RETRIEVAL_MAX_PER_SOURCE` (default `2`)
    - `RETRIEVAL_MMR_LAMBDA` (default `0.5`)
    - `RETRIEVAL_MIN_SCORE` (default `0.05`)

- Verify DB:
  - `mindful-rag verify-chroma --experiment by_type`

Legacy wrappers in `scripts/` still work and forward to the new CLI.
