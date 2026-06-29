# Horae WIP Paper Code

This branch contains the public, paper-focused code and artifacts for the Horae work-in-progress paper on agentic scheduling grounded in passive mobile sensing and behavioral science.

The branch is intentionally narrow: it keeps source, focused tests, documentation, figures, result summaries, and reproduction entrypoints that support the paper. It excludes paper PDFs, raw StudentLife data, local phone logs, vector database binaries, caches, build products, editor state, and API keys.

## Included

- Core agent skeleton and wellbeing tools: `agent.py`, `tools/`, `memory/`
- Behavioral sensing and scheduling pipeline: `wellbeing_pipeline/`
- StudentLife validation scripts and summarized outputs
- Latent simulation outputs used for paper-facing simulation claims
- Payload-size summary artifacts
- Mobile prototype source under `autolife_android_client/`, with local IDE/build state removed
- Lightweight RAG/vector source under `apps/mindful-rag/` and `vectordb/`, without ingested PDFs or binary vector stores

## Not Included

- StudentLife raw dataset files
- Paper PDFs and draft manuscripts
- Chroma/vector DB binary stores
- Raw phone logs and scratch outputs
- Cache directories
- Local IDE, Gradle, Kotlin, Xcode user state, and build outputs
- API keys, credentials, and local secret config files

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest tests/test_latent_simulation.py tests/test_wellbeing_pipeline.py tests/test_wellbeing_sensor.py
```

## Paper Artifact Map

| Paper evidence | Local artifact |
| --- | --- |
| StudentLife circadian-rule comparison and tightened descriptive alignment table | `wellbeing_pipeline/results/studentlife_validation_circadian_rule_compare_1f1dfb2.md` |
| StudentLife mixed-effects/random-intercept checks | `wellbeing_pipeline/results/studentlife_lmm_clustered_1f1dfb2_summary.md` |
| StudentLife construct/outcome supplemental summaries | `wellbeing_pipeline/results/studentlife_construct_outcomes_tight_circadian_1f1dfb2_summary.md` |
| Latent simulation aggregate metrics | `wellbeing_pipeline/simulation_outputs/latent/summary.json` |
| Latent simulation detection and restraint checks | `wellbeing_pipeline/simulation_outputs/latent/detection_sensitivity.json`, `wellbeing_pipeline/simulation_outputs/latent/normal_day_restraint.json` |
| Latent simulation blinded rater sheet and scored preferences | `wellbeing_pipeline/simulation_outputs/latent/rater_sheet_scored_with_arm.csv` |
| Payload-size comparison | `wellbeing_pipeline/simulation_outputs/payload_size/payload_size_report.json` |
| Framework diagrams | `docs/architecture_diagram.png`, `docs/excalidraw_framework.png`, `wellbeing_pipeline/figures/` |

## Reproduction Notes

StudentLife raw data is not redistributed here. To rerun StudentLife analyses, obtain the dataset separately and set:

```bash
export STUDENTLIFE_DATASET_ROOT=/path/to/studentlife/dataset
```

The checked-in StudentLife artifacts are the canonical local outputs for the paper branch. They are descriptive validation artifacts, not causal evidence of wellbeing benefit.

The latent simulation outputs in `wellbeing_pipeline/simulation_outputs/latent/` are stored as paper artifacts. Re-running `wellbeing_pipeline/latent_simulation.py` may make live model API calls unless a compatible local cache is supplied, and cache contents are intentionally excluded from this public branch.

For payload-size summaries:

```bash
python wellbeing_pipeline/measure_payload_sizes.py
```

## Claim Boundaries

This branch supports a paper-code release for review and reproduction of reported artifacts. StudentLife analyses should be described as descriptive alignment with self-reported stress labels. Simulation outputs should be described as framework and recommendation-quality evidence, not as demonstrated clinical efficacy or user-outcome improvement.

