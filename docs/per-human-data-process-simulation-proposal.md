# Per-Human Data Process Simulation Proposal

## Core Question

For the paper, the simulation should test this question:

> When the scheduler receives behavioral sensing context inferred from realistic raw data, does it make more appropriate calendar suggestions than a scheduler that only sees the calendar?

The goal is not to prove that the system can perfectly predict stress, mood, or adherence. The goal is to test whether a behavior-aware scheduling agent makes better calendar recommendations when it is given the same kind of imperfect, passive, longitudinal data that the real framework would receive.

## Recommended Direction

The strongest version of the simulation is a per-human longitudinal simulation rather than isolated one-day scenarios.

Each simulated participant should have:

- The same overall date range, for example 4 weeks.
- A stable latent profile, including routine, sleep tendency, mobility pattern, social tendency, work or school load, and openness to schedule suggestions.
- A realistic calendar over the full period.
- Raw passive sensing traces generated from that latent profile.
- AutoLife-style lifestyle summaries or journals generated from the same underlying life pattern.
- Imperfect adherence to scheduler suggestions after the observation period.

This better matches the real use case. The framework is not usually handed a clean label like "phone-mediated sleep delay." It receives raw and semi-structured evidence over time, infers behavioral state, and uses that state to decide what calendar recommendation is appropriate.

## Simulation Philosophy

The simulation should start from humans, not from labels.

Instead of writing a scenario that directly says:

```text
This user has delayed sleep onset and late-night phone use.
```

we should generate a person whose underlying traits and schedule make that pattern emerge:

```text
Person A:
- Evening chronotype
- High academic workload
- High late-night phone tendency
- Moderate schedule flexibility
- Low morning energy after short sleep
```

From that latent profile, the simulator renders the raw observations:

```text
Latent person profile
        ↓
Daily lifestyle and obligations
        ↓
Calendar events
        ↓
Sleep, mobility, screen, and social behavior
        ↓
GPS traces and phone sensing logs
        ↓
AutoLife summaries / journals
        ↓
Behavioral marker extraction
        ↓
Layer 2 and Layer 3 behavioral state inference
        ↓
Scheduler recommendation
        ↓
Partial or imperfect user adherence
        ↓
Next days of behavior and calendar state
```

This makes the simulation realistic because the scheduler is evaluated on the information it would actually have, not on hidden oracle labels.

## Date Range

Use a shared 4-week window for all simulated humans.

Recommended default:

```text
28 simulated days per participant
Days 1-7: passive observation only
Days 8-28: scheduler suggestions are shown, with imperfect adherence
```

Alternative stronger setup:

```text
28 simulated days per participant
Days 1-14: passive observation only
Days 15-28: scheduler suggestions are shown, with imperfect adherence
```

The 1-week observation version gives more intervention days. The 2-week observation version gives the behavioral pipeline more baseline context before the scheduler starts intervening. For a WiP paper, the 1-week observation setup is probably enough unless the pipeline requires more history for stable baselines.

## Simulated Participants

Each participant should be generated from a compact latent profile.

Example latent dimensions:

| Dimension | Example Values |
|---|---|
| Chronotype | morning, neutral, evening |
| Sleep regularity | stable, moderately variable, unstable |
| Workload | light, moderate, heavy |
| Schedule flexibility | low, medium, high |
| Mobility pattern | campus-centered, work-centered, mixed, restricted |
| Social rhythm | regular, clustered, irregular |
| Phone use tendency | low, moderate, high, late-night heavy |
| Adherence tendency | high, medium, low, context-dependent |
| Stress sensitivity | low, medium, high |

These dimensions should not be exposed directly to the scheduler. They are hidden ground truth used to generate realistic raw data and to evaluate whether the resulting recommendation was appropriate.

## Generated Raw Data

The simulation should generate the raw inputs that the framework would typically receive in a realistic deployment.

### Calendar Data

Each person gets a full 4-week calendar containing fixed and flexible events.

Fixed events:

```text
class, lab, work shift, exam, required meeting, doctor appointment
```

Flexible events:

```text
study block, workout, errands, admin tasks, optional work session, social plan, meal prep
```

The scheduler should be allowed to suggest changes mainly to flexible events. Fixed events should usually be protected.

### Behavioral Sensing Data

Generate daily behavioral markers from the latent person and their day-by-day lifestyle.

Relevant markers:

- Sleep onset time.
- Sleep duration.
- Sleep regularity.
- Total screen time.
- Late-night screen time.
- App switching or attention fragmentation.
- Mobility entropy.
- Location revisit ratio.
- Social rhythm regularity.
- Communication reciprocity, if supported by the simulated data model.

These markers should include noise, missingness, and occasional sensor error. This is important because the real pipeline will not receive perfect data.

### GPS and Location Traces

GPS traces should be generated after the higher-level lifestyle pattern is known.

For example:

```text
Latent routine:
Morning class, afternoon library, evening gym

Generated GPS:
Home → classroom building → library → gym → home
```

Then add realistic imperfections:

- Missing pings.
- Coarse location samples.
- Small spatial jitter.
- Periods of no signal.
- Occasional ambiguous locations.

This lets the pipeline infer mobility and routine from realistic sensor traces rather than from perfect labels.

### AutoLife Inputs

The simulation should also generate AutoLife-style summaries or journals from the same underlying day.

Example:

```text
The user spent most of the afternoon near the library and had a long study period.
They returned home later than usual and used their phone frequently after midnight.
```

These summaries should be consistent with the sensor traces but not perfectly complete. They should sound like realistic passive lifestyle summaries, not hand-written explanations of the hidden ground truth.

## Scheduler Intervention and Adherence

The first part of the simulation is observation only. After that, the scheduler begins making suggestions.

The user should not always follow the suggestions. Adherence should be simulated as part of the data-generating process.

Example adherence behavior:

| Suggestion Type | High-Adherence User | Medium-Adherence User | Low-Adherence User |
|---|---:|---:|---:|
| Move flexible study block earlier | Often follows | Sometimes follows | Rarely follows |
| Protect sleep by moving optional work | Often follows | Sometimes follows | Rarely follows |
| Cancel social plan | Sometimes follows | Rarely follows | Almost never follows |
| Move fixed class or required meeting | Almost never follows | Almost never follows | Almost never follows |

Adherence should depend on burden and context. A low-burden suggestion, such as moving a study block by 30 minutes, should be more likely to be followed than a high-burden suggestion, such as cancelling a social plan.

This gives the later experiments a useful target: the pipeline can look back at past behavior and infer whether the user actually adhered to prior schedule suggestions.

## Experimental Conditions

Run each participant and day under two scheduler conditions.

### Calendar-Only Scheduler

The baseline scheduler receives:

- Calendar context.
- User preferences.
- Fixed versus flexible event constraints.

It does not receive behavioral sensing state.

### Behavior-Aware Scheduler

The behavior-aware scheduler receives:

- Calendar context.
- User preferences.
- Fixed versus flexible event constraints.
- Behavioral state inferred by the pipeline from realistic raw data.
- Relevant confidence or coverage information.

The key is that the behavior-aware scheduler should receive inferred behavioral context, not the simulator's hidden ground truth.

## Example Scheduler Input

```json
{
  "date": "2026-03-12",
  "participant_id": "P014",
  "calendar": [
    {
      "time": "08:30",
      "event": "class",
      "flexibility": "fixed"
    },
    {
      "time": "10:00",
      "event": "project meeting",
      "flexibility": "fixed"
    },
    {
      "time": "15:00",
      "event": "study block",
      "flexibility": "flexible"
    },
    {
      "time": "21:00",
      "event": "optional work session",
      "flexibility": "flexible"
    }
  ],
  "user_preferences": [
    "Do not move classes.",
    "Avoid cancelling meetings.",
    "Prefer changes under 30 minutes.",
    "Protect sleep when possible."
  ],
  "behavioral_state": {
    "pattern": "phone-mediated sleep delay",
    "evidence": [
      "sleep onset shifted later than participant baseline",
      "late-night screen use increased",
      "morning obligations begin before 9 AM"
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

The calendar-only condition should receive the same input with `behavioral_state` removed.

## Expected Scheduler Output

```json
{
  "recommendation": "Move the optional work session from 9:00 PM to 5:00 PM.",
  "reason": "Recent late-night screen use and delayed sleep onset suggest that protecting the evening wind-down period is likely to help.",
  "calendar_action": "reschedule",
  "target_event": "optional work session",
  "burden": "low",
  "confidence": "medium",
  "safety_note": "No fixed obligations were changed."
}
```

## What to Measure

The evaluation should measure recommendation quality, not just state detection.

Possible metrics:

| Metric | Meaning |
|---|---|
| Relevance | Does the suggestion match the user's situation? |
| Behavioral alignment | Does it respond appropriately to the inferred behavioral pattern? |
| Calendar feasibility | Is the suggested change realistic given the calendar? |
| Burden | Does it avoid unnecessary disruption? |
| Safety | Does it avoid overreaching or risky claims? |
| Specificity | Is the recommendation concrete enough to act on? |
| Adherence sensitivity | Does the scheduler adapt when the user has not followed prior suggestions? |

For human evaluation, 2-3 raters can blindly compare outputs from the two conditions.

For simulator-based evaluation, the hidden latent profile can also be used as a consistency check:

- Did the suggestion address the actual simulated cause of the problem?
- Did it target a flexible event rather than a fixed obligation?
- Was the suggestion low enough burden for this participant's adherence profile?
- Did the next recommendation adapt if the user ignored the previous one?

## Main Result To Report

The paper can report a table like:

| Condition | Relevance | Behavioral Alignment | Feasibility | Safety | Overall Preferred |
|---|---:|---:|---:|---:|---:|
| Calendar-only | 3.4 | 2.8 | 4.1 | 4.3 | 35% |
| Behavior-aware | 4.2 | 4.3 | 4.0 | 4.4 | 65% |

Expected claim:

> In a longitudinal per-human simulation, behavior-aware scheduling recommendations were rated as more relevant and behaviorally aligned than calendar-only recommendations, without reducing feasibility or safety. This suggests that interpretable passive-sensing states can improve the contextual relevance of calendar assistance.

## Why This Is Better Than Isolated Scenarios

The earlier scenario-based design is useful and simple, but it risks making the behavioral state look too clean. A per-human simulation is stronger because:

- It tests the whole data process, not only the final scheduler prompt.
- It gives every participant realistic history.
- It lets the pipeline infer state from raw data rather than receiving labels.
- It supports adherence modeling after suggestions begin.
- It lets later experiments test whether the system notices when a user did not follow prior recommendations.
- It better matches the real deployment setting, where the framework receives raw data, calendars, journals, and noisy behavioral evidence over time.

## Practical WiP Version

For a manageable WiP paper, use:

```text
20 simulated participants
28 days per participant
7 passive observation days
21 scheduler-exposed days
2 scheduler conditions: calendar-only and behavior-aware
2-3 blind human raters
```

This yields enough recommendation examples for comparison without making the simulation too large.

If time is tight, reduce to:

```text
10 simulated participants
28 days per participant
Evaluate only selected decision days, such as 5-8 high-signal days per participant
```

That still preserves the key design principle: simulate people over time, generate realistic raw inputs, infer behavioral state through the pipeline, and evaluate whether that state improves scheduling.
