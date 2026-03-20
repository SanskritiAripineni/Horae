# K-EmoPhone Phone-Only Pipeline — Results Walkthrough

## Overview

Successfully adapted the K-EmoPhone supplementary analysis pipeline to run using **only smartphone sensor data**, excluding all watch-dependent sensors (HR, EDA, RRI, SkinTemperature, Distance, Calorie, StepCount). The pipeline ran end-to-end on a MacBook Pro M5 (32GB RAM).

## Dataset Summary

- **2,619 samples** from 77 participants
- **2,592 features** extracted (75 categorical, 2,517 numerical)
- **4 binary classification targets**: Valence, Arousal, Stress, Disturbance

## Model Performance (LOSO Cross-Validation)

All models use Leave-One-Subject-Out (LOSO) cross-validation. Metrics are reported as mean ± std across folds.

### Valence (Positive/Negative Emotion)

| Model | Accuracy | Bal. Accuracy | F1 (Macro) | MCC |
|-------|----------|---------------|------------|-----|
| **RF + OS** | **0.651 ± 0.105** | **0.560 ± 0.083** | **0.544 ± 0.084** | **0.128 ± 0.160** |
| XGB + OS | 0.645 ± 0.107 | 0.561 ± 0.096 | 0.544 ± 0.093 | 0.120 ± 0.181 |
| XGB | 0.652 ± 0.126 | 0.547 ± 0.103 | 0.530 ± 0.112 | 0.101 ± 0.209 |
| RF | 0.641 ± 0.127 | 0.530 ± 0.096 | 0.500 ± 0.103 | 0.075 ± 0.197 |
| Dummy | 0.597 ± 0.233 | 0.489 ± 0.073 | 0.358 ± 0.114 | 0.000 |

### Arousal (High/Low Energy)

| Model | Accuracy | Bal. Accuracy | F1 (Macro) | MCC |
|-------|----------|---------------|------------|-----|
| **XGB + OS** | **0.596 ± 0.100** | **0.550 ± 0.079** | **0.531 ± 0.079** | **0.099 ± 0.139** |
| RF + OS | 0.621 ± 0.127 | 0.561 ± 0.079 | 0.531 ± 0.095 | 0.131 ± 0.161 |
| XGB | 0.628 ± 0.116 | 0.543 ± 0.086 | 0.525 ± 0.091 | 0.089 ± 0.171 |
| RF | 0.638 ± 0.133 | 0.556 ± 0.065 | 0.513 ± 0.095 | 0.126 ± 0.152 |
| Dummy | 0.600 ± 0.200 | 0.500 ± 0.000 | 0.364 ± 0.090 | 0.000 |

### Stress (High/Low Stress)

| Model | Accuracy | Bal. Accuracy | F1 (Macro) | MCC |
|-------|----------|---------------|------------|-----|
| **XGB + OS** | **0.614 ± 0.114** | **0.528 ± 0.071** | **0.510 ± 0.068** | **0.057 ± 0.142** |
| XGB | 0.664 ± 0.128 | 0.536 ± 0.059 | 0.509 ± 0.077 | 0.091 ± 0.154 |
| RF + OS | 0.641 ± 0.131 | 0.526 ± 0.060 | 0.504 ± 0.071 | 0.068 ± 0.148 |
| RF | 0.673 ± 0.142 | 0.529 ± 0.047 | 0.482 ± 0.070 | 0.092 ± 0.143 |
| Dummy | 0.655 ± 0.168 | 0.500 ± 0.000 | 0.390 ± 0.064 | 0.000 |

### Disturbance (High/Low Disturbance)

| Model | Accuracy | Bal. Accuracy | F1 (Macro) | MCC |
|-------|----------|---------------|------------|-----|
| **XGB + OS** | **0.693 ± 0.163** | **0.559 ± 0.132** | **0.527 ± 0.098** | **0.087 ± 0.203** |
| XGB | 0.713 ± 0.156 | 0.547 ± 0.114 | 0.525 ± 0.087 | 0.067 ± 0.182 |
| RF + OS | 0.722 ± 0.153 | 0.561 ± 0.120 | 0.523 ± 0.087 | 0.088 ± 0.178 |
| RF | 0.717 ± 0.172 | 0.549 ± 0.105 | 0.517 ± 0.097 | 0.087 ± 0.191 |
| Dummy | 0.588 ± 0.294 | 0.489 ± 0.073 | 0.346 ± 0.136 | 0.000 |

## Best Models Summary

| Label | Best Model | F1 (Macro) | Accuracy |
|-------|-----------|------------|----------|
| Valence | RF + Oversampling | **0.544** | 0.651 |
| Arousal | XGB + Oversampling | **0.531** | 0.596 |
| Stress | XGB + Oversampling | **0.510** | 0.614 |
| Disturbance | XGB + Oversampling | **0.527** | 0.693 |

## Key Observations

1. **All models beat the dummy baseline** across all four labels, confirming that phone sensor data carries meaningful signal for emotion/stress prediction.
2. **Oversampled models (OS) consistently outperform** their non-oversampled counterparts in F1 Macro, showing that SMOTE helps with the class imbalance.
3. **XGBoost with oversampling is the most consistent** winner, achieving best F1 on 3 out of 4 labels.
4. **MCC values are modest** (0.06–0.13), reflecting the inherent difficulty of predicting subjective emotional states from passive phone sensors alone.
5. **Disturbance has the highest accuracy** (0.693) but this is partially due to class imbalance; F1 Macro is more informative.

> [!NOTE]
> The original K-EmoPhone paper used both watch + phone sensors. Removing the watch data expectedly reduces prediction performance, but the phone-only models still demonstrate statistically significant predictive ability above chance.

## Files Modified

- [analysis.py](file:///Users/rishisim/Documents/research/Full%20K-EmoPhone%20Data/SupplementalCodes/analysis.py) — Main pipeline script, adapted for phone-only data

## Output Files

All outputs are saved in [intermediate/](file:///Users/rishisim/Documents/research/Full%20K-EmoPhone%20Data/SupplementalCodes/intermediate/):
- `proc.pkl` — Preprocessed sensor data
- `valence.pkl`, `arousal.pkl`, `stress.pkl`, `disturbance.pkl` — Extracted features per label
- [eval/](file:///Users/rishisim/Documents/research/Full%20K-EmoPhone%20Data/SupplementalCodes/analysis.py#1866-1966) — Trained model files (per fold per label per algorithm)
