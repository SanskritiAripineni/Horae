# Full-System Layer 4 Simulation Notes

## Why This Exists

The earlier scheduling simulation is useful as a smoke test, but it is not the
full AutoLife scheduling system. Its behavior-aware arm uses simulated sensing,
Layer 1 baseline/coverage, Layer 2 deviations/patterns, and Layer 3 behavioral
state descriptions, then applies deterministic recommendation templates.

For the paper and teammate review, the full-system evaluation should use the
actual Layer 4 scheduler:

simulated behavior and GPS traces -> Layer 1 -> Layer 2 -> Layer 3 -> Layer 4
LLM scheduler reasoning -> blinded rater sheet.

## What Was Added

`wellbeing_pipeline/simulation/run_simulation.py` now has explicit Layer 4
stages:

- `layer4-outputs`: calls `layer4_llm.call_scheduler()` for each behavior-aware
  decision case. It checkpoints `layer4_raw_outputs.jsonl` after every
  completed LLM call, so interrupted runs can resume without repeating finished
  cases.
- `export-layer4-rater-sheet`: exports both a detailed/debug blinded CSV and a
  cleaner human-rating CSV with Option A and Option B side by side.
- `layer4-summary`: summarizes the full-system run and token usage.

The default `--stage all` remains the cheap deterministic smoke test. This is
intentional so synthetic data can be regenerated without accidentally spending
LLM calls.

Layer 4 requests use a 90-second timeout by default. Override it when needed:

```bash
export ANTHROPIC_REQUEST_TIMEOUT_SECONDS=120
```

For a tiny smoke test, limit the number of Layer 4 cases:

```bash
export AUTOLIFE_LAYER4_MAX_CASES=1
python3 wellbeing_pipeline/simulation/run_simulation.py --preset sample --stage layer4-outputs
```

## How To Run The Full-System Evaluation

First regenerate the medium simulation inputs if needed:

```bash
python3 wellbeing_pipeline/simulation/run_simulation.py --preset medium --stage all
```

Then set the Anthropic API key:

```bash
export ANTHROPIC_API_KEY="your_key_here"
```

Optionally override the model:

```bash
export AUTOLIFE_LAYER4_MODEL="claude-sonnet-4-6"
```

Run the full Layer 4 stages:

```bash
python3 wellbeing_pipeline/simulation/run_simulation.py --preset medium --stage layer4-outputs
python3 wellbeing_pipeline/simulation/run_simulation.py --preset medium --stage export-layer4-rater-sheet
python3 wellbeing_pipeline/simulation/run_simulation.py --preset medium --stage layer4-summary
```

## Expected Outputs

These files will be written under
`wellbeing_pipeline/simulation_outputs/medium/`:

- `scheduler_outputs_layer4_blinded.jsonl`
- `layer4_raw_outputs.jsonl`
- `rater_sheet_layer4.csv`
- `rater_sheet_layer4_clean.csv`
- `rater_sheet_layer4_key.csv`
- `simulation_summary_layer4.md`

Use `rater_sheet_layer4_clean.csv` for human scoring. Keep
`rater_sheet_layer4_key.csv` hidden until after ratings are complete because it
contains the condition mapping.

## Correct Paper Framing

Use this wording for the full-system rater sheet:

> Full Layer 1-4 behavior-aware scheduler using simulated longitudinal sensing,
> behavioral-state inference, calendar context, user preferences, and LLM
> scheduling reasoning.

Do not describe the earlier `rater_sheet.csv` as the full LLM scheduler. That
file is:

> Behavior-aware deterministic scheduler using the Layer 1-3 behavioral-state
> pipeline.

## Current Status

The full-system stages have been implemented and run successfully.

Sample run:

- Full Layer 4 behavior-aware calls: 4
- Blinded rater rows: 8
- Output directory: `wellbeing_pipeline/simulation_outputs/sample/`

Medium run:

- Full Layer 4 behavior-aware calls: 15
- Calendar-only baseline outputs: 15
- Blinded rater rows: 30
- Token totals: `input_tokens=18851`, `output_tokens=14914`,
  `cache_read_input_tokens=17055`, `cache_creation_input_tokens=0`
- Output directory: `wellbeing_pipeline/simulation_outputs/medium/`
