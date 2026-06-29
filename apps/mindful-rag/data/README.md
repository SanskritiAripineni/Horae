# Behavioral-Science Retrieval Corpus

This directory contains the paper-facing retrieval corpus used by Horae's behavioral-science guidance layer.

- `index/research_corpus_manifest.csv`: reviewer-readable manifest with 61 papers and protocols.
- `index/research_index.csv`: compact source index consumed by existing RAG scripts.
- `index/research_index_clean.csv`: source ingestion snapshot with extracted text fields used by the RAG experiments.
- `raw/research_papers/`: recovered local PDF set for the corpus.

The manifest is the easiest file to inspect. It records each entry's title, cluster, category, paper type, local PDF path when available, and source URL when available.

Corpus summary:

- 61 manifest entries.
- 15 biological/lifestyle entries.
- 17 cognitive/psychological entries.
- 19 environmental/social entries.
- 10 meta-strategy entries.
- 13 clinical-practice-guideline entries, 22 meta-analysis entries, and 26 protocol entries.
- 60 entries have a local PDF path; one self-determination-theory entry is URL-only.
- One local PDF path points to the legacy `vectordb/research_papers/` subset because that was the recovered source for the corresponding implementation-intentions entry.

Generated vector stores are not checked in. Rebuild them from the manifest and raw PDFs when needed.
