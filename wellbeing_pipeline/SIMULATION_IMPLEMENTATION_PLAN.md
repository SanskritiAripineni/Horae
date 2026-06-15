# Longitudinal Behavior-Aware Scheduling Simulation

Short name: **LBAS Simulation**

## Core Goal

Test whether giving the scheduling agent inferred behavioral context improves
calendar recommendations compared with using calendar context alone.

The simulation does **not** try to prove:

- stress prediction
- clinical wellbeing detection
- perfect adherence
- real-world intervention efficacy

Instead, it evaluates whether a behavior-aware scheduler makes better
recommendations when it receives the same kind of imperfect, longitudinal
behavioral context the real framework would generate.

## High-Level Design

Each simulated participant goes through three phases:

```text
Phase 1: Simulated person generation
Phase 2: Passive baseline recording
Phase 3: Agent recommendation period
```

Recommended WiP setup:

```text
10 simulated people
28 simulated days per person
Days 1-14: passive sensing only, no suggestions
Days 15-28: scheduler suggestions begin
5 evaluated decision days per person
```

This yields:

```text
50 evaluated decision cases
100 scheduler outputs
```

Each decision case has two scheduler outputs:

1. Calendar-only scheduler output.
2. Behavior-aware scheduler output.

## Phase 1: Simulated Person Generation

Each simulated person receives a hidden latent profile. The scheduler never sees
this hidden profile directly.

Example profile:

```json
{
  "participant_id": "P003",
  "chronotype": "evening",
  "sleep_regularity": "unstable",
  "workload": "heavy",
  "schedule_flexibility": "medium",
  "mobility_pattern": "campus-centered",
  "social_rhythm": "irregular",
  "phone_use_tendency": "late-night-heavy",
  "adherence_tendency": "medium",
  "stress_sensitivity": "high"
}
```

Latent dimensions:

| Dimension | Example Values |
|---|---|
| Chronotype | morning, neutral, evening |
| Sleep regularity | stable, moderately variable, unstable |
| Workload | light, moderate, heavy |
| Schedule flexibility | low, medium, high |
| Mobility pattern | campus-centered, work-centered, mixed, restricted |
| Social rhythm | regular, clustered, irregular |
| Phone use tendency | low, moderate, high, late-night-heavy |
| Adherence tendency | high, medium, low, context-dependent |
| Stress sensitivity | low, medium, high |

## Phase 2: Passive Baseline Recording

For the first 14 days, the simulator generates daily life data. The scheduler
does not make suggestions during this phase. The goal is to establish a
personal baseline.

Daily simulated data includes:

1. Calendar events.
2. GPS/location sensing every 15 minutes.
3. Phone/screen sensing.
4. Sleep behavior.
5. AutoLife-style daily summary.
6. Behavioral markers extracted by the existing pipeline.

### Calendar Data

Each person receives a 28-day calendar containing fixed and flexible events.

Fixed events:

```text
class
lab
work shift
exam
required meeting
doctor appointment
```

Flexible events:

```text
study block
workout
errands
admin tasks
optional work session
social plan
meal prep
```

The scheduler should mostly modify flexible events. Fixed events should usually
be protected.

### GPS And Location Sensing

Generate one GPS/location sample every 15 minutes.

Example point:

```json
{
  "timestamp": "2026-03-03T14:15:00",
  "lat": 42.7301,
  "lon": -73.6788,
  "semantic_place": "library",
  "accuracy_m": 35,
  "missing": false
}
```

Possible semantic places:

```text
home/dorm
classroom
library
gym
dining hall
workplace
social venue
clinic
outdoor space
```

Noise and missingness should be included:

- missing pings
- coarse samples
- spatial jitter
- periods of no signal
- occasional ambiguous locations

### Phone And Screen Sensing

Generate screen/phone behavior across the day:

- unlock periods
- late-night screen minutes
- total screen minutes
- app switching rate
- app categories
- missingness/noise

### Sleep Behavior

Sleep is generated from chronotype, workload, phone use tendency, and previous
day burden.

Daily sleep fields:

```text
sleep onset
wake time
sleep duration
sleep regularity contribution
```

### AutoLife-Style Summary

Generate one daily summary from the same underlying simulated behavior.

Example:

```text
The user spent most of the afternoon near the library, returned home later than
usual, and had frequent phone activity after midnight.
```

The summary should be consistent with the simulated sensor data, but it should
not reveal hidden ground-truth labels directly.

### Behavioral Marker Extraction

The simulation should map generated behavior into the same markers used by the
existing wellbeing pipeline:

```text
sleep_onset_hour
sleep_duration_hours
sleep_regularity_index
late_night_screen_min
total_screen_min
app_switching_rate
mobility_entropy
location_revisit_ratio
social_rhythm_metric
comm_reciprocity
```

Coverage should also be generated for every marker so the downstream agent can
discount low-confidence claims.

## Phase 3: Agent Recommendation Period

Days 15-28 continue generating sensing data. The scheduler now receives daily
calendar context and may make recommendations.

Daily process:

```text
raw simulated sensing
        ↓
marker extraction
        ↓
personal baseline comparison
        ↓
coherent pattern detection
        ↓
Layer 3 behavioral state generation
        ↓
scheduler recommendation
        ↓
simulated adherence
        ↓
next-day calendar and behavior update
```

## Scheduler Conditions

Each evaluated decision day is run under two conditions.

### Condition A: Calendar-Only Scheduler

The scheduler receives:

```json
{
  "calendar": "...",
  "user_preferences": "...",
  "fixed_flexible_constraints": "..."
}
```

It does not receive behavioral state.

### Condition B: Behavior-Aware Scheduler

The scheduler receives:

```json
{
  "calendar": "...",
  "user_preferences": "...",
  "fixed_flexible_constraints": "...",
  "behavioral_state": {
    "pattern": "phone-mediated-sleep-delay",
    "evidence": [
      "sleep onset shifted later",
      "late-night screen use increased"
    ],
    "confidence": "medium",
    "coverage": {
      "sleep": "high",
      "screen": "medium",
      "mobility": "high"
    }
  }
}
```

The behavior-aware scheduler receives inferred pipeline output, not hidden
simulator ground truth.

## Expected Scheduler Output

Both scheduler conditions should output the same schema:

```json
{
  "recommendation": "Move the optional work session from 9 PM to 5 PM.",
  "calendar_action": "reschedule",
  "target_event": "optional work session",
  "reason": "Protecting evening wind-down may help after repeated late sleep onset.",
  "burden": "low",
  "confidence": "medium",
  "safety_note": "No fixed obligations were changed."
}
```

Allowed `calendar_action` values:

```text
reschedule
keep
add_buffer
protect_sleep
suggest_break
move_to_daytime
reduce_evening_load
```

## Adherence Simulation

After a recommendation is generated, the simulated participant may or may not
follow it.

Adherence depends on:

- participant adherence tendency
- recommendation burden
- fixed vs flexible event type
- time of day
- how disruptive the suggestion is
- whether prior suggestions were ignored

Example probabilities:

| Suggestion Type | High-Adherence User | Medium-Adherence User | Low-Adherence User |
|---|---:|---:|---:|
| Move flexible study block by <= 30 minutes | 80% | 55% | 25% |
| Move optional work away from late night | 75% | 50% | 20% |
| Add short break or buffer | 85% | 60% | 35% |
| Cancel social plan | 35% | 15% | 5% |
| Move fixed class or required meeting | 2% | 1% | 0% |

This is important because real users will not always follow calendar
suggestions. The simulation should model imperfect adherence instead of assuming
obedience.

## Evaluation

The evaluation compares recommendation quality, not wellbeing outcomes.

Human raters compare calendar-only and behavior-aware outputs blindly.

Metrics:

| Metric | Question |
|---|---|
| Relevance | Does the suggestion match the situation? |
| Behavioral alignment | Does it respond appropriately to inferred behavioral state? |
| Calendar feasibility | Is the suggestion realistic given the calendar? |
| Safety | Does it avoid risky or overreaching claims? |
| Burden | Does it avoid unnecessary disruption? |
| Specificity | Is the suggestion concrete enough to act on? |
| Overall preference | Which output is better overall? |

Recommended rating scale:

```text
1 = poor
2 = weak
3 = acceptable
4 = good
5 = excellent
```

## Recommended WiP Sample Size

Start with:

```text
10 simulated people
28 days per person
14 baseline days
14 scheduler days
5 evaluated decision days per person
2 scheduler conditions
2-3 human raters
```

This gives:

```text
50 evaluated decision cases
100 scheduler outputs
```

If time allows, expand to:

```text
20 simulated people
5 evaluated days per person
100 evaluated decision cases
200 scheduler outputs
```

## Proposed File Structure

Add a new simulation folder:

```text
wellbeing_pipeline/simulation/
```

Planned files:

```text
profiles.py
calendar_generator.py
sensor_generator.py
autolife_summary_generator.py
run_pipeline.py
scheduler_conditions.py
adherence_model.py
run_simulation.py
evaluation_export.py
```

### `profiles.py`

Generates latent simulated participants.

### `calendar_generator.py`

Creates 28-day calendars with fixed and flexible events.

### `sensor_generator.py`

Creates GPS points every 15 minutes, screen events, sleep behavior, and
noise/missingness.

### `autolife_summary_generator.py`

Creates AutoLife-style daily summaries from simulated behavior.

### `run_pipeline.py`

Feeds simulated daily records into Layer 1, Layer 2, and Layer 3 behavior
sensing.

### `scheduler_conditions.py`

Builds calendar-only and behavior-aware scheduler inputs.

### `adherence_model.py`

Simulates whether the user follows each suggestion.

### `run_simulation.py`

Runs the simulation end-to-end.

### `evaluation_export.py`

Exports blinded rater sheets and analysis files.

## Expected Output Files

The simulation should save:

```text
wellbeing_pipeline/simulation_outputs/
  participants.json
  daily_calendars.jsonl
  raw_gps_15min.jsonl
  daily_behavior_markers.csv
  autolife_summaries.jsonl
  inferred_behavior_states.jsonl
  scheduler_inputs_calendar_only.jsonl
  scheduler_inputs_behavior_aware.jsonl
  scheduler_outputs_blinded.jsonl
  rater_sheet.csv
  simulation_summary.md
```

## Expected Paper Table

The paper can report a table like:

| Condition | Relevance | Behavioral Alignment | Feasibility | Safety | Preferred |
|---|---:|---:|---:|---:|---:|
| Calendar-only | 3.4 | 2.8 | 4.2 | 4.4 | 35% |
| Behavior-aware | 4.2 | 4.3 | 4.1 | 4.4 | 65% |

Expected claim:

> In a longitudinal simulation, behavior-aware scheduling recommendations were
> rated as more relevant and behaviorally aligned than calendar-only
> recommendations, without reducing feasibility or safety.

## Implementation Order

1. Create or switch to a simulation branch.
2. Implement simulated person profile generator.
3. Implement 28-day calendar generator.
4. Implement daily behavior generator.
5. Generate 15-minute GPS/location traces.
6. Convert generated behavior into the existing pipeline marker format.
7. Run existing Layer 1, Layer 2, and Layer 3 behavior inference.
8. Create scheduler inputs for both conditions.
9. Produce deterministic rule-based scheduler outputs first.
10. Export blinded rater sheet.
11. Have 2-3 people rate the outputs.
12. Analyze ratings and create final table.

## Recommended Paper Strategy

For the WiP paper, combine:

```text
StudentLife retrospective validation
+ 10-person longitudinal simulation
+ optional 2-3 human raters
```

This gives:

- real-data evidence from StudentLife
- full-system process evidence from simulation
- scheduler usefulness evidence from ratings

The 40-person live deployment can be framed as future work or the next study.
