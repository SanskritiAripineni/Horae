# StudentLife LMM Clustered Analysis

Commit: 1f1dfb27f0814f1f25f237ed238719750ff616af
Outcome: same-day stress_severity. MixedLMs use ML with a random intercept per participant_id.

## Dataset Check

- Warm rows: 4367
- Stress rows: 1132
- Participants: 49
- Any coherent pattern stress days: 117
- Confident coherent pattern stress days: 51
- Behavioral-withdrawal stress days: 27

## Comparison

| predictor | pooled_result_type | pooled_estimate | pooled_p | lmm_estimate | lmm_se | lmm_p | lmm_ci95_low | lmm_ci95_high | random_intercept_variance | icc | lrt_p_vs_intercept | n_observations | n_participants | n_yes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| any_coherent_pattern | Welch diff | 0.2416 | 0.0192 | 0.2127 | 0.1050 | 0.0427 | 0.0070 | 0.4184 | 0.2177 | 0.1721 | 0.0429 | 1132 | 46 | 117.0000 |
| confident_coherent_pattern | Welch diff | 0.3543 | 0.0152 | 0.2733 | 0.1526 | 0.0732 | -0.0257 | 0.5723 | 0.2166 | 0.1712 | 0.0734 | 1132 | 46 | 51.0000 |
| risk_index | Spearman r | 0.0478 | 0.1078 | 0.0344 | 0.0151 | 0.0232 | 0.0047 | 0.0641 | 0.2162 | 0.1712 | 0.0233 | 1132 | 46 |  |
| behavioral_withdrawal | Welch diff | 0.6329 | 0.0018 | 0.6775 | 0.2068 | 0.0011 | 0.2722 | 1.0827 | 0.2204 | 0.1748 | 0.0011 | 1132 | 46 | 27.0000 |

## Per-Participant Spearman Distribution

| predictor | spearman_median_r | spearman_pct_positive | spearman_n_participants |
| --- | --- | --- | --- |
| any_coherent_pattern | 0.0677 | 60.0000 | 30 |
| confident_coherent_pattern | 0.0971 | 70.0000 | 20 |
| risk_index | 0.0079 | 50.0000 | 44 |
| behavioral_withdrawal | 0.2380 | 75.0000 | 16 |

## Output Files

- `wellbeing_pipeline/results/studentlife_lmm_clustered_1f1dfb2_comparison.csv`
- `wellbeing_pipeline/results/studentlife_lmm_clustered_1f1dfb2_per_participant_spearman.csv`
- `wellbeing_pipeline/results/studentlife_lmm_clustered_1f1dfb2_fit_attempts.csv`
