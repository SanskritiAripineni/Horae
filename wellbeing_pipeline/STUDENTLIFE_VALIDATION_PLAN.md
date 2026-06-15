# StudentLife Validation Plan

## Recommendation

Use the complete-but-scoped retrospective validation package for the MobiCom WiP
submission:

1. Pattern-specific StudentLife analysis.
2. Coverage-filtered analysis.
3. Within-person comparisons.
4. Ablations against simpler signals.
5. Marker coverage/missingness reporting.

This is stronger than a simple aggregate test and more feasible than a live user
study before the deadline.

## Why This Is The Right Scope

The paper should evaluate construct validity, not stress-prediction accuracy.
The construct is:

> Passive phone sensing can produce interpretable behavioral states that reflect
> meaningful changes in routine, sleep, mobility, and attention.

The StudentLife dataset supplies real phone-sensing traces plus same-day
self-report signals. Those labels are external alignment checks, not the target
the app is trying to predict.

## What The Analysis Tests

| Analysis | Purpose |
|---|---|
| Pattern-specific results | Shows which behavioral states have external support |
| Coverage-filtered results | Tests only days with usable sensor evidence |
| Within-person results | Compares pattern vs non-pattern days for the same participant |
| Ablations | Tests whether coherent patterns beat simpler signals |
| Marker coverage | Shows which sensing dimensions are reliable or sparse |

## Current Paper-Ready Result

The strongest result is coverage-filtered coherent patterns:

```text
Any confident coherent pattern:
  stress on pattern days:     2.153
  stress on non-pattern days: 1.798
  difference:                 +0.354
  p-value:                    0.015
  Cohen's d:                  0.336
```

This supports the claim that coherent behavioral states align with external
self-report better than simple deviation counts or a raw scalar risk score.

The strongest individual pattern is behavioral withdrawal:

```text
Behavioral withdrawal:
  stress on pattern days:     2.432
  stress on non-pattern days: 1.799
  difference:                 +0.633
  p-value:                    0.002
  Cohen's d:                  0.613
```

## What Not To Claim

Do not claim:

- stress prediction accuracy
- clinical wellbeing detection
- deployed intervention effectiveness
- that every sensor marker has complete coverage

## What To Claim

Use language like:

> In a retrospective StudentLife analysis, coherent behavioral states detected
> by our passive-sensing pipeline showed modest external alignment with
> same-day self-reported stress. Coverage-filtered coherent patterns outperformed
> simpler ablations such as any deviation and scalar risk index, supporting our
> design choice to represent behavior as interpretable multi-signal states.

## Optional Next Step

After this retrospective validation, add a small scheduler usefulness evaluation:

- 20 scenarios
- two scheduler conditions: calendar-only vs behavior-aware
- 2-3 human raters
- ratings for relevance, feasibility, safety, burden, and specificity

This is useful if time allows, but it is not required for the StudentLife
validation result to be credible.
