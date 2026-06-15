# Simulation Smoke Test Notes

## Status

The first longitudinal simulation smoke test is complete and promising.

This is not the final paper-scale simulation. It is a small end-to-end check
that verifies the planned process works before scaling.

## Sample Configuration

```text
Participants: 2
Days per participant: 7
Passive baseline days: 3
Scheduler period days: 4
Evaluated decision cases: 4
Scheduler outputs: 8
```

## What Was Generated

The sample run generated:

- simulated participant profiles
- 7-day calendars
- 15-minute GPS/location traces
- daily behavioral markers
- AutoLife-style summaries
- Layer 1/2/3 inferred behavioral states
- calendar-only scheduler inputs
- behavior-aware scheduler inputs
- blinded scheduler outputs
- simulated adherence log
- rater sheet
- simulation summary

## Smoke Test Results

The sample generated coherent behavioral states from simulated behavior rather
than directly assigning clean labels.

Observed pattern counts:

```text
phone-mediated-sleep-delay: 3
fragmented-attention-with-sleep-loss: 3
circadian-instability: 2
behavioral-withdrawal: 3
```

The behavior-aware scheduler produced different, pattern-grounded
recommendations than the calendar-only scheduler.

Example:

```text
Calendar-only:
  Keep study block flexible and add a 15-minute buffer before it.

Behavior-aware:
  Move optional work session out of the late evening if possible.

Reason:
  Recent later sleep onset and elevated late-night phone use suggest protecting
  the evening wind-down period.
```

Behavioral withdrawal example:

```text
Calendar-only:
  Keep study block flexible and add a 15-minute buffer before it.

Behavior-aware:
  Add a short outdoor or campus walk before study block.

Reason:
  Recent mobility became more restricted and concentrated around the same
  places, so a low-burden restorative movement block may fit.
```

## Initial Interpretation

The sample is promising because:

1. Simulated behavior produced coherent states through the real Layer 1/2/3
   pipeline.
2. Behavior-aware outputs were meaningfully different from calendar-only
   outputs.
3. Recommendations targeted flexible events and avoided fixed obligations.
4. Outputs included safety notes and avoided clinical claims.
5. The rater sheet is understandable enough for teammate evaluation.

## Next Step

Scale from the smoke test to a medium pilot:

```text
5 simulated participants
14 days per participant
7 baseline days
7 scheduler days
2-3 evaluated decision days per participant
```

If the medium pilot remains plausible, scale to the WiP version:

```text
10 simulated participants
28 days per participant
14 baseline days
14 scheduler days
5 evaluated decision days per participant
```
