# Codex Sanity-Check Ratings For Layer 4 Scheduler

## Important Limitation

These are not independent human-rater results. They are a quick Codex sanity
check to see whether the blinded sheet behaves as expected. Use this for internal
inspection only; do not report it as human validation in the paper.

## Preference Result

- Cases rated: 15
- Preferred full Layer 4 option: 15/15
- Preferred calendar-only baseline: 0/15

## Mean Scores

| Condition | Relevance | Behavioral alignment | Feasibility | Safety |
|---|---:|---:|---:|---:|
| Full Layer 4 | 4.87 | 4.87 | 4.33 | 5.00 |
| Calendar-only baseline | 3.00 | 1.00 | 5.00 | 5.00 |

## Case-Level Preferences After Unblinding

| Case | Preferred option | Unblinded condition | Note |
|---|---|---|---|
| S001 | A | Full Layer 4 | A directly protects the late-evening work block tied to sleep delay; B is safe but generic. |
| S002 | A | Full Layer 4 | A addresses late work and wind-down timing; B only adds a generic buffer. |
| S003 | B | Full Layer 4 | B targets the optional evening work session and late screen use; A is not behavior-specific. |
| S004 | A | Full Layer 4 | A adds a low-burden change-of-scenery block aligned with narrowed mobility. |
| S005 | B | Full Layer 4 | B directly responds to restricted mobility with a brief outdoor/change-of-scene prompt. |
| S006 | A | Full Layer 4 | A is specific to mobility narrowing; B is a generic calendar buffer. |
| S007 | B | Full Layer 4 | B offers a consistent wind-down anchor for circadian instability; A does not use behavior context. |
| S008 | A | Full Layer 4 | A caps late optional work and adds a stable wind-down block; B is generic. |
| S009 | B | Full Layer 4 | B maps clearly to delayed sleep and evening schedule; A is not behavior-aware. |
| S010 | A | Full Layer 4 | A adds a sleep-protective wind-down block, though less directly tied than some other cases. |
| S011 | A | Full Layer 4 | A targets sustained late-night screen use and shorter sleep; B is generic. |
| S012 | A | Full Layer 4 | A directly responds to severe sleep loss and late screen use; B is safe but weak. |
| S013 | B | Full Layer 4 | B targets the late optional work session and screen-related sleep delay. |
| S014 | B | Full Layer 4 | B responds to both late-night screen use and evening workload; A is generic. |
| S015 | B | Full Layer 4 | B is clearly grounded in sustained sleep delay and late-night screen use. |

## Readout

The sanity-check ratings strongly favor the full Layer 4 behavior-aware scheduler.
The main reason is behavioral alignment: the full-system option usually names the
specific inferred pattern and proposes a targeted calendar adjustment, while the
calendar-only baseline is usually safe but generic.

This is useful as an internal check that the rater sheet is coherent. The next
real validation step is to collect ratings from people who did not generate the
outputs and do not see the key file before scoring.
