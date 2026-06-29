from datetime import date

from wellbeing_pipeline.latent_simulation import (
    DEFAULT_SEED,
    MARKER_SPECS,
    addresses_expected_lever,
    calendar_only_state,
    evaluate_arm,
    generate_calendar,
    generate_marker_days,
    run_layers_1_to_3,
    sample_profiles,
    summarize_conditional_quality,
    summarize_lever_credit_by_detection,
    user_preferences,
)


def test_sample_profiles_is_seeded_and_covers_all_states_for_full_run():
    profiles_a = sample_profiles(20, DEFAULT_SEED)
    profiles_b = sample_profiles(20, DEFAULT_SEED)

    assert [p.predisposed_pattern for p in profiles_a] == [
        p.predisposed_pattern for p in profiles_b
    ]
    assert len({p.predisposed_pattern for p in profiles_a}) == 4
    assert all(0.10 <= p.missing_rate <= 0.20 for p in profiles_a)


def test_generated_marker_days_match_layer1_schema_and_run_pipeline():
    profile = sample_profiles(4, DEFAULT_SEED)[0]
    calendars = generate_calendar([profile], n_days=42, start_date=date(2026, 3, 2), seed=DEFAULT_SEED)
    raw_days, hidden_daily, hidden_episodes = generate_marker_days(
        profile,
        calendars[profile.participant_id],
        n_days=42,
        start_date=date(2026, 3, 2),
        seed=DEFAULT_SEED,
    )

    expected_keys = {"date", "_coverage", *MARKER_SPECS.keys()}
    assert set(raw_days[0].keys()) == expected_keys
    assert set(raw_days[0]["_coverage"].keys()) == set(MARKER_SPECS.keys())
    assert len(hidden_daily) == 42
    assert 1 <= len(hidden_episodes) <= 3
    assert any(ep["overlaps_decision_days"] for ep in hidden_episodes)

    states = run_layers_1_to_3({profile.participant_id: raw_days})
    decision_state = states[(profile.participant_id, 29)]["state"]["structured"]

    assert decision_state["baseline_state"]["warm"] is True
    assert decision_state["baseline_state"]["days_of_history"] == 29
    assert "state_scores" not in str(decision_state)
    assert "adherence_tendency" not in str(decision_state)


def test_calendar_only_state_contains_no_behavioral_evidence():
    state = calendar_only_state("2026-03-30", 29)["structured"]

    assert state["deviations"] == []
    assert state["coherent_patterns"] == []
    assert state["coverage_notes"] == []
    assert state["baseline_state"]["overall_confidence"] == "no-behavioral-state-provided"


def test_programmatic_checks_distinguish_flexible_and_fixed_targets():
    events = [
        {
            "title": "class",
            "event_type": "class",
            "fixed": True,
            "start": "09:00",
            "end": "10:15",
        },
        {
            "title": "optional work session",
            "event_type": "optional_work_session",
            "fixed": False,
            "start": "21:00",
            "end": "22:30",
        },
    ]
    good = {
        "salience_reasoning": "Late-night screen use and later sleep onset are the main issue.",
        "suggestions": [
            {
                "change": "Cap the optional work session at 21:45 and add a wind-down block.",
                "rationale": "Protects sleep from late-night screen spillover.",
                "grounded_in": ["phone-mediated-sleep-delay", "late_night_screen_min"],
                "start_time": "21:45",
                "end_time": "22:00",
            }
        ],
    }
    bad = {
        "salience_reasoning": "Make the morning easier.",
        "suggestions": [
            {
                "change": "Move class from 09:00 to 10:00.",
                "rationale": "More sleep.",
                "grounded_in": [],
                "start_time": "10:00",
                "end_time": "11:00",
            }
        ],
    }

    assert addresses_expected_lever("phone-mediated-sleep-delay", good)
    good_eval = evaluate_arm(
        "behavior_aware",
        "phone-mediated-sleep-delay",
        0.5,
        good,
        events,
        received_relevant_evidence=True,
    )
    bad_eval = evaluate_arm(
        "behavior_aware",
        "phone-mediated-sleep-delay",
        0.5,
        bad,
        events,
        received_relevant_evidence=True,
    )

    assert good_eval["all_three_pass"] is True
    assert bad_eval["flexible_event_pass"] is False


def test_calendar_only_generic_sleep_guess_does_not_count_as_latent_lever():
    generic_calendar_only = {
        "salience_reasoning": "The calendar has late evening load.",
        "suggestions": [
            {
                "change": "Add a wind-down block after the late study block.",
                "rationale": "A buffer before bed is helpful after late calendar events.",
                "grounded_in": ["calendar"],
                "start_time": "22:00",
                "end_time": "22:20",
            }
        ],
    }

    assert (
        addresses_expected_lever(
            "phone-mediated-sleep-delay",
            generic_calendar_only,
            arm="calendar_only",
        )
        is False
    )


def test_behavior_aware_without_relevant_evidence_uses_calendar_only_basis():
    generic_behavior_aware = {
        "salience_reasoning": "The calendar has late evening load.",
        "suggestions": [
            {
                "change": "Add a wind-down block after the late study block.",
                "rationale": "A buffer before bed is helpful after late calendar events.",
                "grounded_in": ["calendar"],
                "start_time": "22:00",
                "end_time": "22:20",
            }
        ],
    }

    assert (
        addresses_expected_lever(
            "phone-mediated-sleep-delay",
            generic_behavior_aware,
            arm="behavior_aware",
            received_relevant_evidence=False,
        )
        is False
    )


def test_conditional_quality_summarizes_detected_cases_only():
    rows = [
        {
            "case_id": "P001-D29",
            "arm": "behavior_aware",
            "pipeline_detected_predisposed_pattern": True,
            "lever_pass": True,
            "flexible_event_pass": True,
            "burden_pass": True,
            "specificity_pass": True,
            "high_burden_change": False,
            "burden_score": 1.0,
            "all_three_pass": True,
        },
        {
            "case_id": "P001-D29",
            "arm": "calendar_only",
            "pipeline_detected_predisposed_pattern": True,
            "lever_pass": False,
            "flexible_event_pass": True,
            "burden_pass": True,
            "specificity_pass": False,
            "high_burden_change": False,
            "burden_score": 1.2,
            "all_three_pass": False,
        },
        {
            "case_id": "P001-D30",
            "arm": "behavior_aware",
            "pipeline_detected_predisposed_pattern": False,
            "lever_pass": True,
            "flexible_event_pass": True,
            "burden_pass": True,
            "specificity_pass": True,
            "high_burden_change": False,
            "burden_score": 1.0,
            "all_three_pass": True,
        },
        {
            "case_id": "P001-D30",
            "arm": "calendar_only",
            "pipeline_detected_predisposed_pattern": False,
            "lever_pass": True,
            "flexible_event_pass": True,
            "burden_pass": True,
            "specificity_pass": True,
            "high_burden_change": False,
            "burden_score": 1.0,
            "all_three_pass": True,
        },
    ]

    summary = summarize_conditional_quality(rows)

    assert summary["n_cases"] == 1
    assert summary["behavior_aware"]["specificity_rate"] == 1.0
    assert summary["calendar_only"]["specificity_rate"] == 0.0


def test_lever_credit_summary_is_weighted_by_detection_subset():
    rows = [
        {
            "arm": "behavior_aware",
            "lever_pass": True,
            "received_relevant_evidence": True,
        },
        {
            "arm": "behavior_aware",
            "lever_pass": True,
            "received_relevant_evidence": True,
        },
        {
            "arm": "behavior_aware",
            "lever_pass": False,
            "received_relevant_evidence": False,
        },
        {
            "arm": "behavior_aware",
            "lever_pass": False,
            "received_relevant_evidence": False,
        },
    ]

    summary = summarize_lever_credit_by_detection(rows)["behavior_aware"]

    assert summary["overall"] == 0.5
    assert summary["detected_or_marker_evidence_subset"] == 1.0
    assert summary["non_detected_subset"] == 0.0
    assert summary["weighted_reconstruction"] == 0.5
    assert summary["weighted_matches_overall"] is True
    assert summary["overall_between_subsets"] is True


def test_user_preferences_do_not_include_hidden_profile_traits():
    prefs = user_preferences()
    rendered = str(prefs)
    for hidden_key in ("chronotype", "workload", "adherence_tendency", "stress_sensitivity"):
        assert hidden_key not in rendered
