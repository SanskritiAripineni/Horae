# Large Full-System Layer 4 Simulation Run

## Configuration

- Participants: 20
- Days per participant: 14
- Participant-days: 280
- Passive baseline days: 7
- Passive baseline participant-days: 140
- Scheduler-period days per participant: 7
- Scheduler-period participant-days: 140
- Max evaluated decision days per participant: 3

## End-to-End Path

Simulated phone behavior and GPS traces -> Layer 1 personal baseline and marker
coverage -> Layer 2 deviations and coherent patterns -> Layer 3 structured and
prose behavioral state -> Layer 4 LLM scheduler reasoning with calendar context,
user preferences, and safety prompt -> blinded rater sheet.

## Output Check

- Decision cases: 60
- Calendar-only baseline outputs: 60
- Full Layer 4 behavior-aware outputs: 60
- Full Layer 4 outputs with suggestions: 60
- Full Layer 4 outputs also containing questions: 47
- Blinded rater rows: 120

## Layer 4 API Use

- Token totals: {'input_tokens': 77165, 'output_tokens': 60173, 'cache_read_input_tokens': 67083, 'cache_creation_input_tokens': 1137}

## Paper Interpretation

This run supports the claim that the complete AutoLife scheduling pipeline can
turn passive sensing states into calendar recommendations. It should be reported
separately from the deterministic smoke test. The behavior-aware condition here
uses the full Layer 1-4 system; the calendar-only condition is a deterministic
baseline used for blinded comparison.
