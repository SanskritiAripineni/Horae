# Multi-Agent-LLM

Repository root now uses an app-scoped layout.

## Active App

- `apps/mindful-rag/`: Student wellness RAG app and ingestion pipelines.

## Quick Start

```bash
cd apps/mindful-rag
pip install -r requirements.txt
pip install -e .
```

Or from repo root:

```bash
make install
```

## Run

From repository root:

```bash
make ingest-by-type
make run-by-type
make verify-by-type
make ingest-csv-sources
make run-csv-sources
make eval-csv-sources
```

`ingest-csv-sources` uses the latest `apps/mindful-rag/data/index/research_index_ingestions_*.csv` snapshot by default (create/update with `make csv-all`).

Other useful targets:

```bash
make ingest-intro-concl
make ingest-raw
make ingest-all
make csv-all
```

`eval-csv-sources` writes detailed and summary metrics under `apps/mindful-rag/data/evals/`.

## Root Tasks

```bash
make help
make check
```
