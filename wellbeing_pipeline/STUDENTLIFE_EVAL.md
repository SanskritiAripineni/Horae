# StudentLife Validation Runbook

The wellbeing pipeline validation script expects the StudentLife dataset to be
available locally. The dataset is not committed to this repository because it is
external research data.

## Dataset Location

Set `STUDENTLIFE_DATASET_ROOT` to the directory that contains the StudentLife
`sensing` and `EMA` folders:

```bash
export STUDENTLIFE_DATASET_ROOT=/path/to/studentlife/dataset
```

Expected structure:

```text
$STUDENTLIFE_DATASET_ROOT/
  sensing/
    phonelock/
    wifi_location/
  EMA/
    response/
      Stress/
      PAM/
```

## Run Validation

From the repository root:

```bash
python3 wellbeing_pipeline/evaluate_studentlife.py
```

To run a smaller smoke test:

```bash
python3 wellbeing_pipeline/evaluate_studentlife.py 5
```

The script prints:

- number of participants and daily rows processed
- sample Layer 3 behavioral prose
- alignment between pipeline risk index and same-day Stress/PAM EMA responses

If the dataset is missing or the path is wrong, the script exits with setup
instructions instead of reporting an empty validation as if it succeeded.

## Paper Wording

For the MobiCom WiP submission, only report StudentLife alignment numbers that
come from a fresh run of this script on the final dataset path. If the dataset
cannot be rerun before submission, describe the StudentLife evaluation as
preliminary and focus the paper on the system contribution, marker design, and
phone-to-LLM scheduling interface.
