# Large Simulation Run

## Configuration

- Participants: 20
- Days per participant: 14
- Passive baseline days: 7
- Scheduler period days: 7
- Max evaluated decision days per participant: 3

## Pipeline Check

- Scheduler-period days with coherent patterns: 116
- Pattern counts: {'phone-mediated-sleep-delay': 44, 'circadian-instability': 41, 'fragmented-attention-with-sleep-loss': 43, 'behavioral-withdrawal': 42}

## Scheduler Output Check

- Calendar-only outputs: 60
- Behavior-aware outputs: 60
- Blinded rater rows: 120

## Initial Read

This run is considered promising if:

1. At least one coherent behavioral pattern emerges from simulated behavior.
2. The behavior-aware scheduler produces a different, pattern-grounded
   recommendation than the calendar-only scheduler.
3. Outputs avoid changing fixed obligations and include safety notes.
4. The rater sheet is understandable enough for a teammate to score.
