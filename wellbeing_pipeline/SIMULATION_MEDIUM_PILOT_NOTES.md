# Simulation Medium Pilot Notes

## Status

The medium longitudinal simulation pilot is complete and promising.

This run scales the smoke test from 2 participants to 5 participants while
preserving the staged simulation process:

```text
profiles → calendars → sensing → AutoLife summaries → Layer 1/2/3 pipeline
→ scheduler inputs → blinded scheduler outputs → adherence → rater sheet
```

## Configuration

```text
Participants: 5
Days per participant: 14
Passive baseline days: 7
Scheduler period days: 7
Max evaluated decision days per participant: 3
```

## Generated Data

The medium run produced:

```text
70 daily calendars
70 raw daily behavior records
70 AutoLife-style summaries
6,720 GPS/location samples at 15-minute intervals
70 inferred behavioral-state records
15 evaluated decision cases
30 blinded scheduler outputs
30 rater-sheet rows
```

## Pipeline Output

Scheduler-period days with coherent patterns:

```text
29
```

Pattern counts:

```text
phone-mediated-sleep-delay: 11
circadian-instability: 9
fragmented-attention-with-sleep-loss: 10
behavioral-withdrawal: 11
```

Pattern days were balanced across participants:

```text
P001: 6
P002: 6
P003: 5
P004: 6
P005: 6
```

## Scheduler Output Check

Calendar-only scheduler:

```text
add_buffer: 15
```

Behavior-aware scheduler:

```text
reduce_evening_load: 6
suggest_break: 3
protect_sleep: 3
reschedule: 3
```

This is the desired behavior for the pilot: the calendar-only condition mostly
produces generic low-burden calendar advice, while the behavior-aware condition
changes the recommendation based on the inferred behavioral state.

## Example Behavior-Aware Recommendations

Phone-mediated sleep delay:

```text
Move optional work session out of the late evening if possible.
```

Behavioral withdrawal:

```text
Add a short outdoor or campus walk before study block.
```

Circadian instability:

```text
Keep study block at a consistent daytime slot and avoid moving it later.
```

Fragmented attention with sleep loss:

```text
Move the most demanding part of study block earlier in the day.
```

## Initial Interpretation

The medium pilot is promising because:

1. The simulator generated multiple participant archetypes over time.
2. The existing Layer 1/2/3 behavior pipeline detected coherent states from
   generated longitudinal behavior.
3. Pattern days were not dominated by one participant.
4. Behavior-aware recommendations differed from calendar-only recommendations
   in pattern-specific ways.
5. Recommendations targeted flexible events and included safety notes.
6. The rater sheet is ready for teammate review.

## Caveat

This pilot still uses deterministic rule-based scheduler outputs. That is
intentional for this stage because it lets us verify data flow and evaluation
format before using LLM/API-generated recommendations or human ratings.

## Next Step

Use the medium rater sheet for a small human review, or scale to the full WiP
simulation:

```text
10 simulated participants
28 days per participant
14 passive baseline days
14 scheduler-period days
5 evaluated decision days per participant
```

Before scaling, the main improvement should be to add slightly more variation
within each participant's repeated recommendations so raters do not see the same
action repeated too often.
