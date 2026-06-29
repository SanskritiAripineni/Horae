# StudentLife Construct-Appropriate Outcome Tests

Target commit: `1f1dfb27f0814f1f25f237ed238719750ff616af`
Dataset root: local StudentLife dataset root, not included in this branch. Set `STUDENTLIFE_DATASET_ROOT` before rerunning.

Primary alignment matches the existing stress analysis: pipeline state date equals EMA local response date.
Sleep EMA `hour` and `rate` ask about last night, so a Sleep response on local date D refers to the prior night ending on D. Labeled `*_NEXT_NIGHT_ALIGNMENT` rows test state date D against Sleep response date D+1.
PAM and Stress are momentary responses assigned to their local response date.

All model outcomes are oriented so larger values are worse / in the hypothesized state-present direction. Raw means are also included for interpretability.

## Coverage
| outcome | alignment | participant_days_with_ema | participants_with_ema |
| --- | --- | --- | --- |
| sleep_hours | same_day | 1079 | 47 |
| sleep_hours | next_day | 1048 | 47 |
| sleep_quality | same_day | 1089 | 47 |
| sleep_quality | next_day | 1058 | 47 |
| stress_severity | same_day | 1132 | 46 |
| stress_severity | next_day | 1107 | 46 |
| pam_valence | same_day | 2069 | 47 |
| pam_valence | next_day | 2041 | 47 |

## Comparison Table
| state | role | outcome | alignment | tested_value_oriented | n_yes | n_no | raw_mean_yes | raw_mean_no | mean_yes | mean_no | welch_p | cohen_d | lmm_estimate | lmm_se | lmm_p | lmm_ci_low | lmm_ci_high | random_intercept_variance | icc | lrt_p | n_obs | n_participants | yes_day_participants | participant_corr_median_r | participant_corr_pct_hypothesized_direction | participant_corr_n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| phone-mediated-sleep-delay | PRIMARY | sleep_hours | same_day | -sleep_hours_numeric | 24 | 1055 | 8.292 | 8.885 | -8.292 | -8.885 | 0.258 | 0.2438 | 0.5216 | 0.4778 | 0.275 | -0.4149 | 1.458 | 0.5668 | 0.09987 | 0.2751 | 1079 | 47 | 13 | 0.08857 | 61.54 | 13 |
| phone-mediated-sleep-delay | PRIMARY_NEXT_NIGHT_ALIGNMENT | sleep_hours | next_day | -sleep_hours_numeric | 23 | 1025 | 8.848 | 8.884 | -8.848 | -8.884 | 0.9432 | 0.01504 | 0.05563 | 0.4928 | 0.9101 | -0.9101 | 1.021 | 0.5873 | 0.1009 | 0.9101 | 1048 | 47 | 14 | 0.02206 | 50 | 14 |
| phone-mediated-sleep-delay | SECONDARY | sleep_quality | same_day | sleep_quality_rate | 24 | 1065 | 1.75 | 1.902 | 1.75 | 1.902 | 0.3634 | -0.1857 | -0.1095 | 0.1623 | 0.5 | -0.4276 | 0.2086 | 0.1265 | 0.1777 | 0.5 | 1089 | 47 | 13 | -0.0869 | 38.46 | 13 |
| phone-mediated-sleep-delay | SECONDARY_NEXT_NIGHT_ALIGNMENT | sleep_quality | next_day | sleep_quality_rate | 23 | 1035 | 1.739 | 1.904 | 1.739 | 1.904 | 0.3103 | -0.2057 | -0.1054 | 0.1669 | 0.5278 | -0.4325 | 0.2217 | 0.1241 | 0.1724 | 0.5278 | 1058 | 47 | 14 | -0.0264 | 50 | 14 |
| behavioral-withdrawal | PRIMARY | stress_severity | same_day | stress_severity | 27 | 1105 | 2.432 | 1.799 | 2.432 | 1.799 | 0.001829 | 0.6135 | 0.6775 | 0.2068 | 0.001052 | 0.2722 | 1.083 | 0.2204 | 0.1748 | 0.001082 | 1132 | 46 | 16 | 0.238 | 75 | 16 |
| behavioral-withdrawal | SECONDARY | pam_valence | same_day | -pam_valence | 52 | 2017 | 2.49 | 2.539 | -2.49 | -2.539 | 0.5986 | 0.07201 | 0.06955 | 0.09168 | 0.4481 | -0.1101 | 0.2492 | 0.101 | 0.2013 | 0.4481 | 2069 | 47 | 19 | 0.04825 | 57.89 | 19 |
| circadian-instability | PRIMARY | sleep_quality | same_day | sleep_quality_rate | 6 | 1083 | 2 | 1.898 | 2 | 1.898 | 0.829 | 0.1044 | 0.3153 | 0.3184 | 0.322 | -0.3087 | 0.9393 | 0.1275 | 0.1791 | 0.3221 | 1089 | 47 | 5 | 0.07651 | 60 | 5 |
| circadian-instability | PRIMARY_NEXT_NIGHT_ALIGNMENT | sleep_quality | next_day | sleep_quality_rate | 4 | 1054 | 1.75 | 1.901 | 1.75 | 1.901 | 0.7733 | -0.1671 | 0.1144 | 0.3937 | 0.7714 | -0.6573 | 0.8861 | 0.1247 | 0.1731 | 0.7714 | 1058 | 47 | 3 | -0.0279 | 33.33 | 3 |
| circadian-instability | SECONDARY | sleep_hours | same_day | -sleep_hours_numeric | 6 | 1073 | 8.5 | 8.874 | -8.5 | -8.874 | 0.6811 | 0.1665 | 0.5859 | 0.9393 | 0.5328 | -1.255 | 2.427 | 0.5713 | 0.1005 | 0.5328 | 1079 | 47 | 5 | 0.1226 | 60 | 5 |
| circadian-instability | SECONDARY_NEXT_NIGHT_ALIGNMENT | sleep_hours | next_day | -sleep_hours_numeric | 4 | 1044 | 8 | 8.886 | -8 | -8.886 | 0.3819 | 0.4215 | 1.067 | 1.164 | 0.359 | -1.213 | 3.348 | 0.5886 | 0.1012 | 0.3591 | 1048 | 47 | 3 | 0.06771 | 100 | 3 |
| fragmented-attention-with-sleep-loss | PRIMARY | sleep_hours | same_day | -sleep_hours_numeric | 9 | 1070 | 8.833 | 8.872 | -8.833 | -8.872 | 0.9401 | 0.01961 | 0.1109 | 0.7659 | 0.8849 | -1.39 | 1.612 | 0.5695 | 0.1002 | 0.8849 | 1079 | 47 | 9 | 0.04046 | 66.67 | 9 |
| fragmented-attention-with-sleep-loss | PRIMARY_NEXT_NIGHT_ALIGNMENT | sleep_hours | next_day | -sleep_hours_numeric | 8 | 1040 | 8.25 | 8.888 | -8.25 | -8.888 | 0.1281 | 0.3424 | 0.8774 | 0.8219 | 0.2858 | -0.7335 | 2.488 | 0.5903 | 0.1015 | 0.2859 | 1048 | 47 | 7 | 0.07804 | 85.71 | 7 |
| fragmented-attention-with-sleep-loss | SECONDARY | stress_severity | same_day | stress_severity | 13 | 1119 | 1.977 | 1.812 | 1.977 | 1.812 | 0.6172 | 0.1451 | 0.2325 | 0.2914 | 0.425 | -0.3387 | 0.8036 | 0.2181 | 0.172 | 0.4251 | 1132 | 46 | 11 | 0.09296 | 54.55 | 11 |

## Outcome Coding
### sleep_hours
- EMA field: `Sleep.hour`
- Coding: 1=<3 hours, 2=3.5, 3=4, ..., 19=12; code 1 is approximated as 2.5 hours.
- Tested/oriented value: `-sleep_hours_numeric`
- Direction: state present -> shorter sleep; larger oriented value means fewer hours.

### sleep_quality
- EMA field: `Sleep.rate`
- Coding: 1=Very good, 2=Fairly good, 3=Fairly bad, 4=Very bad.
- Tested/oriented value: `sleep_quality_rate`
- Direction: state present -> worse sleep quality; larger value means worse quality.

### stress_severity
- EMA field: `Stress.level`
- Coding: 1=A little stressed, 2=Definitely stressed, 3=Stressed out, 4=Feeling good, 5=Feeling great; recoded to severity 1->3, 2->2, 3->1, 4/5->0.
- Tested/oriented value: `stress_severity`
- Direction: state present -> higher stress severity; larger value means worse stress.

### pam_valence
- EMA field: `PAM.picture_idx`
- Coding: 4x4 grid; valence is column ((picture_idx-1) % 4)+1, 1=more negative, 4=more positive.
- Tested/oriented value: `-pam_valence`
- Direction: state present -> lower/more negative valence; larger oriented value means worse affect.

## Timing Summary
- Sleep responses with sleep fields: 1390; median local hour 13.94; p10-p90 12.56-17.60; 8.1% before noon.
- PAM responses: 9040; median local hour 15.50; p10-p90 1.60-21.88.
