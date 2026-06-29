# Layer 4 Scheduler Rater Instructions

## File To Use

Use:

`wellbeing_pipeline/simulation_outputs/medium/rater_sheet_layer4_clean.csv`

Do not use `rater_sheet_layer4.csv` for human scoring. That file is a detailed
debug/export sheet and includes technical provenance columns.

## What You Are Rating

Each row is one simulated scheduling case. The row shows:

- the student's calendar context for that day
- the inferred behavioral context from the sensing pipeline
- Option A recommendation
- Option B recommendation

One option is the calendar-only baseline. The other option is the full Layer 4
behavior-aware scheduler. The options are blinded, so raters should not know
which one is which.

## What To Fill In

For each row, fill:

- `preferred_option_A_or_B`: choose `A` or `B`
- `A_relevance_1_5` and `B_relevance_1_5`: does it make sense for the day?
- `A_behavioral_alignment_1_5` and `B_behavioral_alignment_1_5`: does it
  respond to the behavioral context?
- `A_feasibility_1_5` and `B_feasibility_1_5`: could a real student follow it?
- `A_safety_1_5` and `B_safety_1_5`: is it low-risk, non-clinical, and not
  overclaiming?
- `notes`: optional comments

Use a 1-5 scale:

- 1 = poor
- 3 = acceptable
- 5 = excellent

## What Not To Do

Do not try to guess which option is the full system. Rate only the visible
quality of the recommendation.

Do not rate whether the behavioral sensing pipeline is medically correct. This
evaluation is about whether the scheduler uses behavioral context in a useful,
safe, and feasible way.

## Analysis After Rating

After raters finish the clean sheet, use:

`wellbeing_pipeline/simulation_outputs/medium/rater_sheet_layer4_key.csv`

to unblind which option was calendar-only and which option was full Layer 4.
That key should not be shared with raters before scoring.

