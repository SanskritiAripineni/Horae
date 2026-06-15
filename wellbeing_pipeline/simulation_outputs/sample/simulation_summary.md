# Sample Simulation Smoke Test

## Configuration

- Participants: 2
- Days per participant: 7
- Passive baseline days: 3
- Scheduler period days: 4

## Pipeline Check

- Scheduler-period days with coherent patterns: 6
- Pattern counts: {'phone-mediated-sleep-delay': 3, 'fragmented-attention-with-sleep-loss': 3, 'circadian-instability': 2, 'behavioral-withdrawal': 3}

## Scheduler Output Check

- Calendar-only outputs: 4
- Behavior-aware outputs: 4
- Blinded rater rows: 8

## Initial Read

This smoke test is considered promising if:

1. At least one coherent behavioral pattern emerges from simulated behavior.
2. The behavior-aware scheduler produces a different, pattern-grounded
   recommendation than the calendar-only scheduler.
3. Outputs avoid changing fixed obligations and include safety notes.
4. The rater sheet is understandable enough for a teammate to score.
