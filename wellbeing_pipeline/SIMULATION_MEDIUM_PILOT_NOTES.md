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
add_buffer: 10
keep: 5
```

Behavior-aware scheduler:

```text
protect_sleep: 4
reduce_evening_load: 3
reschedule: 3
move_to_daytime: 2
suggest_break: 2
add_buffer: 1
```

Recommendation diversity:

```text
Calendar-only: 3 unique recommendations out of 15
Behavior-aware: 12 unique recommendations out of 15
```

This is the desired behavior for the pilot: the calendar-only condition mostly
produces generic low-burden calendar advice, while the behavior-aware condition
changes the recommendation based on the inferred behavioral state.

## Example Behavior-Aware Recommendations

Phone-mediated sleep delay:

```text
Shorten optional work session and set a firm evening stop time.
Move optional work session out of the late evening if possible.
Move the planning portion of optional work session to the afternoon.
```

Behavioral withdrawal:

```text
Add a short outdoor or campus walk before study block.
Move part of study block to a public campus location such as the library.
Pair study block with a brief meal or coffee stop away from the usual location.
```

Circadian instability:

```text
Keep study block at a consistent daytime slot and avoid moving it later.
Anchor study block around the same time as earlier in the week.
Avoid adding late-day tasks after study block.
```

Fragmented attention with sleep loss:

```text
Move the most demanding part of study block earlier in the day.
Split study block into two shorter focus blocks.
Move lower-priority tasks out of that block.
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
6. Behavior-aware recommendations now have enough within-pattern variation for
   human review.
7. The rater sheet is ready for teammate review.

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

The repeated recommendation issue from the first medium run has been addressed.
The next decision is whether to use the medium rater sheet for teammate review
or scale to the full WiP simulation first.
