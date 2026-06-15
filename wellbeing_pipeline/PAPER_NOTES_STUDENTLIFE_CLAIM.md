# Paper Notes: StudentLife Validation Claim

## Bottom Line

The StudentLife retrospective validation is complete for the current WiP paper
scope.

The result is strong enough to support a construct-validity claim:

> Coherent, coverage-aware behavioral states inferred from passive phone sensing
> show preliminary external alignment with same-day self-report, and outperform
> simpler representations such as isolated deviations or a scalar risk score.

Do not frame this as stress prediction, clinical diagnosis, or deployed
intervention effectiveness.

## Best Paper Claim

Use wording close to:

> In a retrospective StudentLife analysis, coherent behavioral states detected
> by our pipeline showed significant external alignment with same-day
> self-report. Coverage-filtered coherent patterns outperformed simpler
> ablations such as any deviation and scalar risk index, supporting our design
> choice to represent passive sensing as interpretable behavioral states rather
> than isolated sensor anomalies.

Shorter version:

> StudentLife results provide preliminary evidence that multi-signal behavioral
> states capture meaningful behavioral variation better than raw deviation
> counts or scalar risk scores.

## Key Numbers

Dataset summary:

```text
Participants:                 49
Warm-baseline daily rows:      4,367
Days with Stress EMA:          1,132
Days with PAM EMA:             2,069
Days with any coherent pattern: 263
Days with confident pattern:    98
```

Strongest overall result:

```text
Any confident coherent pattern:
  stress on pattern days:      2.153
  stress on non-pattern days:  1.798
  difference:                 +0.354
  p-value:                     0.015
  Cohen's d:                   0.336
```

Strongest individual pattern:

```text
Behavioral withdrawal:
  stress on pattern days:      2.432
  stress on non-pattern days:  1.799
  difference:                 +0.633
  p-value:                     0.002
  Cohen's d:                   0.613
```

Ablation comparison:

```text
Any deviation:                 p = 0.912
Risk index:                    p = 0.108
Any coherent pattern:          p = 0.019
Confident coherent pattern:    p = 0.015
```

## How Strong Is This?

For a MobiCom WiP paper, this is good supporting evidence.

Interpretation:

- `p = 0.002` for behavioral withdrawal is statistically strong.
- `d = 0.613` is a medium effect size, which is meaningful in behavioral data.
- `p = 0.015` for confident coherent patterns is significant.
- `d = 0.336` is small-to-moderate, useful but not a final-proof result.
- The ablation result is especially important because simpler methods do not
  work: isolated deviations and scalar risk score are weak, while coherent
  behavioral states are stronger.

Best characterization:

> Preliminary but meaningful construct-validity evidence.

Avoid saying:

- "accurate stress prediction"
- "detects mental health"
- "diagnoses wellbeing"
- "proves intervention effectiveness"
- "all patterns are equally supported"

## What The Result Means

The pipeline works better when it waits for multiple behavioral signals to line
up into a coherent state.

Example:

```text
Lower mobility entropy + more time at top frequent places
→ behavioral withdrawal
```

That coherent state had higher same-day self-reported stress in StudentLife.
This supports the design choice to give the scheduler interpretable behavioral
context rather than raw sensor values or a single risk number.

## What Is Complete

Complete for StudentLife:

- Dataset downloaded locally from Kaggle.
- Dataset path wired through `STUDENTLIFE_DATASET_ROOT` / local symlink.
- Full retrospective validation run on 49 participants.
- Pattern-specific analysis.
- Coverage-filtered analysis.
- Within-person comparison.
- Ablation against simpler signals.
- Marker coverage/missingness table.
- Paper-ready summary and CSV outputs.

Main result files:

- `wellbeing_pipeline/results/studentlife_validation_2026-06-15_summary.md`
- `wellbeing_pipeline/results/studentlife_validation_2026-06-15_patterns.csv`
- `wellbeing_pipeline/results/studentlife_validation_2026-06-15_coverage_filtered_patterns.csv`
- `wellbeing_pipeline/results/studentlife_validation_2026-06-15_ablations.csv`
- `wellbeing_pipeline/results/studentlife_validation_2026-06-15_within_person.csv`
- `wellbeing_pipeline/results/studentlife_validation_2026-06-15_marker_coverage.csv`

## What Is Not Complete

Separate from StudentLife, not required for this validation:

- Scheduler simulation/human-rating evaluation.
- Live user deployment.
- IRB field study.
- Proof that recommendations improve wellbeing.

These can be framed as next steps or added as a small scenario-based evaluation
if time allows.
