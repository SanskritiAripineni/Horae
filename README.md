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
```

Other useful targets:

```bash
make ingest-intro-concl
make ingest-raw
make ingest-all
make csv-all
```

## Root Tasks

```bash
make help
make check
```
