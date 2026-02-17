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
python apps/mindful-rag/scripts/ingest.py --experiment by_type
python apps/mindful-rag/scripts/run_app.py --experiment by_type
python apps/mindful-rag/scripts/verify_chroma.py --experiment by_type
```

Or from `apps/mindful-rag`:

```bash
mindful-rag ingest --experiment by_type
mindful-rag run-app --experiment by_type
mindful-rag verify-chroma --experiment by_type
```

## Root Tasks

```bash
make help
make check
```
