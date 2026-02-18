# Mindful RAG Commands (Simple)

Run all commands from repo root:

```bash
cd /Users/rishisim/Documents/StudioProjects/Multi-Agent-LLM
```

## Daily Commands

```bash
make ingest-by-type
```
- Run by_type ingestion.

```bash
make ingest-intro-concl
```
- Run intro+conclusion ingestion.

```bash
make ingest-raw
```
- Run raw ingestion (full text, reset DB).

```bash
make ingest-all
```
- Run `by_type` + `intro_concl` + `raw` in order.

```bash
make run-by-type
```
- Start app using by_type DB.

```bash
make verify-by-type
```
- Check by_type collection count + sample row.

```bash
make csv-all
```
- Create one timestamped CSV with:
- `by_type_text`
- `intro_concl_text`
- `raw_text`

## Help Commands

```bash
make ingest-help
make run-help
make verify-help
make help
```

## Optional Env Vars

`BY_TYPE_OUTPUT_CSV=/path/file.csv`
- Custom output CSV path for by_type ingestion.

`BY_TYPE_ALLOW_EMBEDDING_FALLBACK=1`
- Allow fallback embeddings if Gemini is unavailable.
- Default is Gemini-only (`0`).
