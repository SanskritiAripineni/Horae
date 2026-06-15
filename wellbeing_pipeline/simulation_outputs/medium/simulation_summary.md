# Medium Simulation Run

## Configuration

- Participants: 5
- Days per participant: 14
- Passive baseline days: 7
- Scheduler period days: 7
- Max evaluated decision days per participant: 3

## Pipeline Check

- Scheduler-period days with coherent patterns: 29
- Pattern counts: {'phone-mediated-sleep-delay': 11, 'circadian-instability': 9, 'fragmented-attention-with-sleep-loss': 10, 'behavioral-withdrawal': 11}

## Scheduler Output Check

- Calendar-only outputs: 15
- Behavior-aware outputs: 15
- Blinded rater rows: 30

## Initial Read

This run is considered promising if:

1. At least one coherent behavioral pattern emerges from simulated behavior.
2. The behavior-aware scheduler produces a different, pattern-grounded
   recommendation than the calendar-only scheduler.
3. Outputs avoid changing fixed obligations and include safety notes.
4. The rater sheet is understandable enough for a teammate to score.
