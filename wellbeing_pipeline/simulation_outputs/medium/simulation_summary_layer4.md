# Medium Full-System Layer 4 Simulation Run

## Configuration

- Participants: 5
- Days per participant: 14
- Passive baseline days: 7
- Max evaluated decision days per participant: 3

## End-to-End Path

Simulated phone behavior and GPS traces -> Layer 1 personal baseline and marker
coverage -> Layer 2 deviations and coherent patterns -> Layer 3 structured and
prose behavioral state -> Layer 4 LLM scheduler reasoning with calendar context,
user preferences, and safety prompt -> blinded rater sheet.

## Output Check

- Calendar-only baseline outputs: 15
- Full Layer 4 behavior-aware outputs: 15
- Full Layer 4 outputs with suggestions: 15
- Full Layer 4 outputs also containing questions: 11
- Blinded rater rows: 30

## Layer 4 API Use

- Token totals: {'input_tokens': 18851, 'output_tokens': 14914, 'cache_read_input_tokens': 17055, 'cache_creation_input_tokens': 0}

## Paper Interpretation

This run supports the claim that the complete AutoLife scheduling pipeline can
turn passive sensing states into calendar recommendations. It should be reported
separately from the deterministic smoke test. The behavior-aware condition here
uses the full Layer 1-4 system; the calendar-only condition is a deterministic
baseline used for blinded comparison.
