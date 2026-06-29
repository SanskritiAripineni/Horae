# Horae: A Behavior-Aware Agentic Scheduling Framework Grounded in Mobile Sensing

Code and paper artifacts for **Horae**, a behavior-aware agentic scheduling framework grounded in passive mobile sensing and behavioral-science evidence.

Horae studies how an LLM scheduler can use compact behavioral context, rather than raw phone streams or clinical labels, to make small calendar recommendations that respect user preferences and fixed obligations. The system combines mobile sensing summaries, personalized behavioral-state inference, evidence retrieval, calendar context, and memory into a scheduler-facing tool pipeline.


## System Overview
![Horae framework](docs/horae_framework.png)


## Behavioral Sensing Pipeline

![Three-layer pipeline flow](docs/diagrams/three-layer-pipeline-flow.png)

## Behavioral Markers

![Wellbeing sensing biomarkers](docs/diagrams/wellbeing-sensing-biomarkers.png)




## Paper Context

This repository supports a work-in-progress systems paper on agentic scheduling with passive mobile sensing. The paper evaluates two questions:

1. Whether passive phone-derived markers can be summarized into meaningful, personalized behavioral states.
2. Whether those states can change downstream schedule recommendations in a controlled end-to-end simulation.

The checked-in artifacts are intended to make the paper claims inspectable: StudentLife validation summaries, latent simulation logs, payload-size measurements, focused tests, and framework source code are kept together with the scripts that produced them.

The behavioral-science retrieval corpus used by the scheduler is also included. The paper-facing manifest is `apps/mindful-rag/data/index/research_corpus_manifest.csv`, which lists 61 papers and protocols across biological/lifestyle, cognitive/psychological, environmental/social, and meta-strategy clusters. Local PDFs are checked in for 60 manifest entries; the remaining entry is URL-only and recorded in the manifest.

## Repository Contents

- `wellbeing_pipeline/`: layered behavioral sensing pipeline, StudentLife analyses, latent simulation, payload-size measurement, and stored paper artifacts.
- `tools/`: scheduler tools for wellbeing sensing, AutoLife journal parsing, calendar context, feedback, and retrieval.
- `agent.py`, `main.py`, `api.py`: prototype scheduler entrypoints and orchestration code.
- `autolife_android_client/`: mobile prototype source for passive sensing and daily context generation.
- `apps/mindful-rag/`: paper-facing behavioral-science retrieval corpus and Mindful RAG tooling.
- `vectordb/`: lightweight legacy/local vector DB demo with an 18-document PDF subset and CSV map.
- `docs/`: framework documentation and the README figure.
- `tests/`: focused regression tests for the sensing pipeline and simulation logic.


## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest tests/test_latent_simulation.py tests/test_wellbeing_pipeline.py tests/test_wellbeing_sensor.py
```

## Reproducing Analyses

StudentLife raw data must be obtained separately. To rerun StudentLife analyses, set:

```bash
export STUDENTLIFE_DATASET_ROOT=/path/to/studentlife/dataset
```

The stored StudentLife summaries are the canonical paper-branch outputs. They evaluate descriptive alignment with same-day self-reported stress, not causal wellbeing effects.

The latent simulation artifacts in `wellbeing_pipeline/simulation_outputs/latent/` use a fixed seed (`20260627`) with 20 synthetic participants over 42 days. Re-running `wellbeing_pipeline/latent_simulation.py` may make live model API calls unless a compatible local cache is supplied.

Payload-size summaries can be regenerated with:

```bash
python wellbeing_pipeline/measure_payload_sizes.py
```

The retrieval corpus can be inspected without rebuilding vectors:

```bash
python3 - <<'PY'
import csv
from collections import Counter

with open("apps/mindful-rag/data/index/research_corpus_manifest.csv", newline="") as f:
    rows = list(csv.DictReader(f))

print(len(rows), "corpus entries")
print(Counter(row["cluster"] for row in rows))
print(Counter(row["paper_type"] for row in rows))
PY
```

Generated Chroma/vector-store files are intentionally excluded from `main`; rebuild them from the checked-in corpus when needed.

## Claim Boundaries

Horae is a work-in-progress research prototype. The StudentLife analysis supports construct-validity style evidence for behavioral-state summaries; the simulation supports framework feasibility and recommendation-quality analysis. The repository does not establish deployed user benefit or clinical efficacy.

## Citation

Citation information will be added with the paper release.
