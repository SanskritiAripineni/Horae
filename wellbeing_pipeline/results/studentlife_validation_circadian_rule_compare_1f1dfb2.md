# StudentLife Circadian Rule Comparison

Target commit: `1f1dfb27f0814f1f25f237ed238719750ff616af`
Dataset root: local StudentLife dataset root, not included in this branch. Set `STUDENTLIFE_DATASET_ROOT` before rerunning.

Scalar-risk binary row uses `risk_index > median risk_index among stress-labeled warm days` for that version.

## Original (circadian_min_markers=1)

Warm rows: 4367; participants: 49; stress days: 1132; circadian fire count: 127

### Ablation Table
| label | n_yes | n_no | mean_yes | mean_no | p | cohen_d |
| --- | --- | --- | --- | --- | --- | --- |
| any single deviation | 733 | 399 | 1.81156 | 1.81929 | 0.912113 | -0.00689442 |
| scalar risk index > stress-day median (1) | 467 | 665 | 1.89952 | 1.75443 | 0.0300057 | 0.130649 |
| any coherent pattern | 117 | 1015 | 2.03091 | 1.78932 | 0.0192392 | 0.223519 |
| confident coherent pattern (coverage >= 0.45) | 51 | 1081 | 2.15261 | 1.79832 | 0.0152398 | 0.336361 |

### Per-State Stress Table
| state | fire_count | n_stress_days | n_stress_no | mean_stress_yes | mean_stress_no | p | cohen_d |
| --- | --- | --- | --- | --- | --- | --- | --- |
| phone-mediated-sleep-delay | 36 | 24 | 1108 | 1.86458 | 1.8132 | 0.802175 | 0.0488247 |
| behavioral-withdrawal | 91 | 27 | 1105 | 2.4321 | 1.79919 | 0.00182924 | 0.613467 |
| circadian-instability | 127 | 57 | 1075 | 1.92105 | 1.80863 | 0.442934 | 0.102724 |
| fragmented-attention-with-sleep-loss | 17 | 13 | 1119 | 1.97692 | 1.8124 | 0.617189 | 0.145103 |

### Distinct Participant Counts
| bucket | stress_day_count | distinct_participants |
| --- | --- | --- |
| confident_pattern_stress_days | 51 | 20 |
| withdrawal_stress_days | 27 | 16 |
| any_pattern_stress_days | 117 | 30 |

### Per-Participant Spearman
| median_r | mean_r | percent_positive | n_participants | participant_n_min | participant_n_max |
| --- | --- | --- | --- | --- | --- |
| 0 | 0.00835599 | 47.5 | 40 | 10 | 63 |

## Tightened (circadian_min_markers=2)

Warm rows: 4367; participants: 49; stress days: 1132; circadian fire count: 17

### Ablation Table
| label | n_yes | n_no | mean_yes | mean_no | p | cohen_d |
| --- | --- | --- | --- | --- | --- | --- |
| any single deviation | 733 | 399 | 1.81156 | 1.81929 | 0.912113 | -0.00689442 |
| scalar risk index > stress-day median (1) | 459 | 673 | 1.90104 | 1.75512 | 0.0294405 | 0.131424 |
| any coherent pattern | 69 | 1063 | 2.10797 | 1.79522 | 0.0172525 | 0.29076 |
| confident coherent pattern (coverage >= 0.45) | 24 | 1108 | 2.26181 | 1.80459 | 0.027667 | 0.442045 |

### Per-State Stress Table
| state | fire_count | n_stress_days | n_stress_no | mean_stress_yes | mean_stress_no | p | cohen_d |
| --- | --- | --- | --- | --- | --- | --- | --- |
| phone-mediated-sleep-delay | 36 | 24 | 1108 | 1.86458 | 1.8132 | 0.802175 | 0.0488247 |
| behavioral-withdrawal | 91 | 27 | 1105 | 2.4321 | 1.79919 | 0.00182924 | 0.613467 |
| circadian-instability | 17 | 8 | 1124 | 2.16667 | 1.81178 | 0.386426 | 0.322429 |
| fragmented-attention-with-sleep-loss | 17 | 13 | 1119 | 1.97692 | 1.8124 | 0.617189 | 0.145103 |

### Distinct Participant Counts
| bucket | stress_day_count | distinct_participants |
| --- | --- | --- |
| confident_pattern_stress_days | 24 | 14 |
| withdrawal_stress_days | 27 | 16 |
| any_pattern_stress_days | 69 | 27 |

### Per-Participant Spearman
| median_r | mean_r | percent_positive | n_participants | participant_n_min | participant_n_max |
| --- | --- | --- | --- | --- | --- |
| 0 | 0.00356662 | 47.5 | 40 | 10 | 63 |
