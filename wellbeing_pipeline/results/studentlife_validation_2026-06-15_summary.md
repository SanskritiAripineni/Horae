# StudentLife Construct-Validity Analysis (2026-06-15)

This analysis evaluates whether coherent behavioral states from the passive
sensing pipeline align with external self-report signals in StudentLife. It is
not a stress-prediction benchmark.

## Dataset Summary

| Quantity | Value |
|---|---:|
| Warm-baseline daily rows | 4367 |
| Participants | 49 |
| Days with Stress EMA | 1132 |
| Days with PAM EMA | 2069 |
| Days with any coherent pattern | 263 |
| Days with confident coherent pattern | 98 |

## Pattern-Specific Alignment With Stress

| label | n_yes | mean_yes | mean_no | diff_yes_minus_no | diff_ci95_low | diff_ci95_high | welch_p | cohen_d |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| behavioral-withdrawal | 27 | 2.432 | 1.799 | 0.633 | 0.151 | 1.006 | 0.002 | 0.613 |
| any coherent pattern | 117 | 2.031 | 1.789 | 0.242 | 0.011 | 0.427 | 0.019 | 0.224 |
| fragmented-attention-with-sleep-loss | 13 | 1.977 | 1.812 | 0.165 | -0.537 | 0.743 | 0.617 | 0.145 |
| circadian-instability | 57 | 1.921 | 1.809 | 0.112 | -0.193 | 0.381 | 0.443 | 0.103 |
| phone-mediated-sleep-delay | 24 | 1.865 | 1.813 | 0.051 | -0.417 | 0.498 | 0.802 | 0.049 |

## Coverage-Filtered Pattern Alignment

Pattern days are retained here only when required marker coverage is at least
0.45.

| label | n_yes | mean_yes | mean_no | diff_yes_minus_no | diff_ci95_low | diff_ci95_high | welch_p | cohen_d |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| behavioral-withdrawal (required coverage >= 0.45) | 27 | 2.432 | 1.799 | 0.633 | 0.151 | 1.006 | 0.002 | 0.613 |
| any coherent pattern (required coverage >= 0.45) | 51 | 2.153 | 1.798 | 0.354 | 0.130 | 0.531 | 0.015 | 0.336 |
| circadian-instability (required coverage >= 0.45) | 47 | 1.989 | 1.807 | 0.183 | -0.189 | 0.428 | 0.269 | 0.165 |
| fragmented-attention-with-sleep-loss (required coverage >= 0.45) | 11 | 1.973 | 1.813 | 0.160 | -0.528 | 0.774 | 0.663 | 0.139 |
| phone-mediated-sleep-delay (required coverage >= 0.45) | 18 | 1.847 | 1.814 | 0.033 | -0.416 | 0.468 | 0.882 | 0.032 |

## Ablation Against Simpler Signals

| label | n_yes | mean_yes | mean_no | diff_yes_minus_no | welch_p | cohen_d | spearman_r | spearman_p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| any deviation | 733 | 1.812 | 1.819 | -0.008 | 0.912 | -0.007 |  |  |
| any coherent pattern | 117 | 2.031 | 1.789 | 0.242 | 0.019 | 0.224 |  |  |
| any confident coherent pattern | 51 | 2.153 | 1.798 | 0.354 | 0.015 | 0.336 |  |  |
| n_dev | 1132 |  |  |  | 0.280 |  | 0.032 | 0.280 |
| n_pat | 1132 |  |  |  | 0.028 |  | 0.065 | 0.028 |
| risk_index | 1132 |  |  |  | 0.108 |  | 0.048 | 0.108 |

## Within-Person Pattern Comparison

For each participant with both pattern and non-pattern stress days, this compares
their own mean stress on pattern days vs their own non-pattern days.

| label | n_participants_with_both | n_positive | percent_positive | median_within_person_diff | mean_within_person_diff | sign_test_p |
| --- | --- | --- | --- | --- | --- | --- |
| any coherent pattern | 22 | 13 | 59.091 | 0.191 | 0.253 | 0.523 |
| phone-mediated-sleep-delay | 9 | 5 | 55.556 | 0.239 | 0.096 | 1.000 |
| behavioral-withdrawal | 6 | 4 | 66.667 | 0.413 | 0.490 | 0.688 |
| circadian-instability | 10 | 4 | 40.000 | -0.131 | -0.023 | 0.754 |
| fragmented-attention-with-sleep-loss | 2 | 2 | 100.000 | 1.351 | 1.351 | 0.500 |

## Marker Coverage

| marker | domain | mean_coverage | days_any_coverage_pct | days_medium_or_high_pct | days_high_pct |
| --- | --- | --- | --- | --- | --- |
| sleep_onset_hour | sleep | 0.357 | 35.745 | 35.745 | 35.745 |
| sleep_duration_hours | sleep | 0.357 | 35.745 | 35.745 | 35.745 |
| sleep_regularity_index | sleep | 0.157 | 31.005 | 17.861 | 5.816 |
| late_night_screen_min | screen | 0.291 | 40.417 | 30.662 | 22.899 |
| total_screen_min | screen | 0.388 | 54.889 | 41.539 | 29.540 |
| app_switching_rate | screen | 0.593 | 59.286 | 59.286 | 59.286 |
| mobility_entropy | mobility | 0.521 | 57.293 | 53.561 | 48.958 |
| location_revisit_ratio | mobility | 0.521 | 57.293 | 53.561 | 48.958 |
| social_rhythm_metric | social | 0.671 | 71.468 | 70.048 | 63.110 |
| comm_reciprocity | social | 0.261 | 26.128 | 26.128 | 26.128 |

## Paper-Ready Interpretation

The strongest defensible claim is that the pipeline produces interpretable
behavioral states that show preliminary external alignment with self-report.
Avoid claiming stress prediction accuracy. The most relevant evidence is whether
coherent pattern days, especially coverage-filtered pattern days, have higher
same-day stress than non-pattern days and whether coherent patterns outperform
simpler ablations such as any deviation or a scalar risk index.
