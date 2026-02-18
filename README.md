# Mindful RAG

Repository root now uses an app-scoped layout.

## Demo

![Demo of Mindful RAG](demo.mov)

## Purpose & Features

Mindful RAG is a student wellness application designed to provide insightful answers derived from a curated index of research papers and textbooks. It leverages RAG (Retrieval-Augmented Generation) to ground its responses in verified sources.

**Key Features:**
- **Topic-Based Retrieval:** Ingests and retrieves content based on document types and topics.
- **Source Comparison:** Compare answers derived from different source filters (e.g., Intro/Conclusion vs. Full Text).
- **Evaluation Framework:** Built-in tools to evaluate retrieval quality and answer accuracy.
- **Streamlit Interface:** User-friendly web interface for interacting with the RAG pipeline.

## Quick Start

To get up and running quickly:

### 1. Install Dependencies
From the repository root:
```bash
make install
```

### 2. Ingest Data
Ingest the default CSV sources (required for the app to work):
```bash
make ingest-csv-sources
```

### 3. Run the App
Launch the Streamlit application:
```bash
make run-csv-sources
```
The app will open at `http://localhost:8501`.

## Detailed Commands

Run all commands from the repository root.

### Ingestion Pipelines

| Command | Description |
| :--- | :--- |
| `make ingest-by-type` | Run `by_type` ingestion. |
| `make ingest-intro-concl` | Run `intro` + `conclusion` ingestion. |
| `make ingest-raw` | Run raw ingestion (full text, resets DB). |
| `make ingest-all` | Run all ingestion pipelines in order. |
| `make csv-all` | Create a timestamped CSV with text from all sources. |

### Running & Verification

| Command | Description |
| :--- | :--- |
| `make run-by-type` | Start app using the `by_type` DB. |
| `make verify-by-type` | Check `by_type` collection count and sample row. |
| `make eval-csv-sources` | Evaluate retrieval quality across source filters. Writes metrics to `apps/mindful-rag/data/evals/`. |

### Helper Commands

```bash
make help           # Show all commands
make ingest-help    # Show ingest CLI flags
make run-help       # Show run-app CLI flags
make verify-help    # Show verify-chroma CLI flags
```

## Configuration

**Optional Environment Variables:**
- `BY_TYPE_OUTPUT_CSV=/path/file.csv`: Custom output CSV path for `by_type` ingestion.
- `BY_TYPE_ALLOW_EMBEDDING_FALLBACK=1`: Allow fallback embeddings if Gemini is unavailable (default: `0`).

## Navigation

- `apps/mindful-rag/`: Source code for the application and pipelines.
