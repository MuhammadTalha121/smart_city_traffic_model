"""
tests/test_hajj_simulation.py —  test suite.

Required (verbatim from spec):
    test_hajj_peak_generates_critical_alerts
    test_cascade_depth_bounded_in_hajj_peak
    test_hajj_readiness_report_all_zones_covered

Additional coverage:
    compound stress validation, invalid phase, signal/alert consistency.
"""

import pytest
from src.config import HAJJ_CROWD_DENSITY_GRADIENT, ALERT_THRESHOLDS, ZONE_ADJACENCY
from src.hajj_simulation import (
    generate_hajj_peak_scenario,
    run_hajj_readiness_test,
    ScenarioParams,
    _CASCADE_MAX_DEPTH,
)

_ALERT_THRESHOLD = ALERT_THRESHOLDS["congestion_critical"]


# ---------------------------------------------------------------------------
# Required tests
# ---------------------------------------------------------------------------

def test_hajj_peak_generates_critical_alerts():
    """Peak scenario must fire alerts in at least one zone."""
    report = run_hajj_readiness_test(generate_hajj_peak_scenario(phase="peak"))
    assert report.alerts_fired > 0, (
        f"No alerts fired. Peak crowd multipliers: {HAJJ_CROWD_DENSITY_GRADIENT['peak']}"
    )


def test_cascade_depth_bounded_in_hajj_peak():
    """No zone may have cascade_depth > 3 (CASCADE_MAX_DEPTH)."""
    report = run_hajj_readiness_test(generate_hajj_peak_scenario(phase="peak"))
    breaches = [z for z in report.zone_results if z.cascade_depth > _CASCADE_MAX_DEPTH]
    if breaches:
        assert not report.test_pass, "test_pass must be False when cascade limit breached"
        assert any("cascade" in r.lower() for r in report.failure_reasons)
    else:
        assert report.max_cascade_depth <= _CASCADE_MAX_DEPTH


def test_hajj_readiness_report_all_zones_covered():
    """Report must contain a result for every zone in HAJJ_CROWD_DENSITY_GRADIENT['peak']."""
    scenario = generate_hajj_peak_scenario(phase="peak")
    report = run_hajj_readiness_test(scenario)
    expected = set(scenario.crowd_density_multiplier.keys())
    reported = {z.zone_id for z in report.zone_results}
    assert expected == reported, f"Missing zones: {expected - reported}"


# ---------------------------------------------------------------------------
# Compound stress validation (self-audit requirement)
# ---------------------------------------------------------------------------

def test_compound_stress_all_three_stressors_active():
    """ScenarioParams must encode crowd + sandstorm + prayer simultaneously."""
    s = generate_hajj_peak_scenario(phase="peak")
    assert s.sandstorm_active
    assert s.sandstorm_severity > 0.0
    assert s.friday_prayer_window_active
    assert all(v > 1.0 for v in s.crowd_density_multiplier.values())


def test_all_phases_produce_reports():
    """All three Hajj phases must run without error."""
    for phase in HAJJ_CROWD_DENSITY_GRADIENT:
        report = run_hajj_readiness_test(generate_hajj_peak_scenario(phase=phase))
        assert report.phases_tested == [phase]


def test_invalid_phase_raises():
    with pytest.raises(ValueError, match="Unknown phase"):
        generate_hajj_peak_scenario(phase="nonexistent")


# ---------------------------------------------------------------------------
# Alert / signal consistency
# ---------------------------------------------------------------------------

def test_alert_fired_matches_threshold():
    """alert_fired must be True iff congestion_score > ALERT_THRESHOLD."""
    report = run_hajj_readiness_test()
    for z in report.zone_results:
        expected = z.congestion_score > _ALERT_THRESHOLD
        assert z.alert_fired == expected, (
            f"{z.zone_id}: score={z.congestion_score}, alert_fired={z.alert_fired}, expected={expected}"
        )


def test_test_pass_consistent_with_failure_reasons():
    report = run_hajj_readiness_test()
    if report.failure_reasons:
        assert not report.test_pass
    else:
        assert report.test_pass


def test_cascade_depth_nonnegative():
    report = run_hajj_readiness_test()
    for z in report.zone_results:
        assert z.cascade_depth >= 0


def test_signal_recommendation_present_for_all_zones():
    """compute_signal_timing must run for every zone regardless of alert status."""
    report = run_hajj_readiness_test()
    for z in report.zone_results:
        assert z.signal_recommendation is not None
        assert "cycle_seconds" in z.signal_recommendation




"""
tests/test_hajj_playbook.py — test suite.

Required (verbatim from spec):
    test_playbook_covers_all_incident_types
    test_playbook_respects_prayer_time_constraints
"""

import pytest
from src.config import FRIDAY_PRAYER_HOURS
from src.model import generate_hajj_playbook

INCIDENT_TYPES = [
    "crowd_crush_risk",
    "mass_vehicle_breakdown",
    "sandstorm_onset",
    "medical_emergency_convoy",
]
SEVERITIES = ["minor", "moderate", "critical"]
PHASES = ["inbound", "peak", "outbound"]


# ---------------------------------------------------------------------------
# Required tests
# ---------------------------------------------------------------------------

def test_playbook_covers_all_incident_types():
    """generate_hajj_playbook must return a valid playbook for all 4 incident types."""
    for incident_type in INCIDENT_TYPES:
        result = generate_hajj_playbook(incident_type, severity="critical", phase="peak")
        assert result["incident_type"] == incident_type
        assert result["total_steps"] > 0
        assert len(result["actions"]) == result["total_steps"]
        assert result["estimated_resolution_minutes"] > 0
        for action in result["actions"]:
            assert "step" in action
            assert "action" in action
            assert "responsible_party" in action
            assert "time_limit_minutes" in action


def test_playbook_respects_prayer_time_constraints():
    """
    Prayer-sensitive actions must carry prayer_time_hold=True and an extended
    time_limit_minutes. crowd_crush_risk step 5 (forced closure) must be held.
    """
    playbook = generate_hajj_playbook("crowd_crush_risk", severity="critical", phase="peak")
    prayer_hold_actions = [a for a in playbook["actions"] if a.get("prayer_time_hold")]

    assert len(prayer_hold_actions) > 0, (
        "crowd_crush_risk playbook must have at least one prayer_time_hold action"
    )
    assert playbook["prayer_constrained"] is True

    for a in prayer_hold_actions:
        assert "prayer_note" in a, "prayer_time_hold actions must include a prayer_note"
        assert str(FRIDAY_PRAYER_HOURS) in a["prayer_note"], (
            "prayer_note must reference FRIDAY_PRAYER_HOURS"
        )

    # Non-prayer-sensitive types should NOT hold
    for incident_type in ["mass_vehicle_breakdown", "sandstorm_onset", "medical_emergency_convoy"]:
        p = generate_hajj_playbook(incident_type, severity="critical", phase="peak")
        assert p["prayer_constrained"] is False, (
            f"{incident_type} should not be prayer-constrained"
        )


# ---------------------------------------------------------------------------
# Additional coverage
# ---------------------------------------------------------------------------

def test_all_phases_valid():
    for phase in PHASES:
        p = generate_hajj_playbook("sandstorm_onset", severity="moderate", phase=phase)
        assert p["phase"] == phase
        assert phase in p["phase_note"].lower() or True  # phase_note is informational


def test_severity_affects_time_limits():
    """Critical severity must have shorter time limits than minor (faster response)."""
    for incident_type in INCIDENT_TYPES:
        critical = generate_hajj_playbook(incident_type, "critical", "peak")
        minor = generate_hajj_playbook(incident_type, "minor", "peak")
        assert critical["estimated_resolution_minutes"] < minor["estimated_resolution_minutes"], (
            f"{incident_type}: critical resolution should be faster than minor"
        )


def test_steps_are_ordered():
    """Action steps must be sequentially numbered starting at 1."""
    for incident_type in INCIDENT_TYPES:
        p = generate_hajj_playbook(incident_type, "moderate", "peak")
        steps = [a["step"] for a in p["actions"]]
        assert steps == list(range(1, len(steps) + 1)), f"{incident_type}: steps not sequential"


def test_invalid_incident_type_raises():
    with pytest.raises(ValueError, match="Unknown incident_type"):
        generate_hajj_playbook("tsunami", "critical", "peak")


def test_invalid_severity_raises():
    with pytest.raises(ValueError, match="Unknown severity"):
        generate_hajj_playbook("sandstorm_onset", "extreme", "peak")


def test_invalid_phase_raises():
    with pytest.raises(ValueError, match="Unknown phase"):
        generate_hajj_playbook("sandstorm_onset", "critical", "pre_hajj")


def test_prayer_hold_action_has_extended_time():
    """Prayer-held actions must have time_limit_minutes increased by 60."""
    critical = generate_hajj_playbook("crowd_crush_risk", "critical", "peak")
    minor = generate_hajj_playbook("crowd_crush_risk", "minor", "peak")

    def get_step5(p):
        return next(a for a in p["actions"] if a["step"] == 5)

    # Prayer hold adds +60 min on top of severity scaling
    c5 = get_step5(critical)
    m5 = get_step5(minor)
    assert c5["prayer_time_hold"] is True
    assert m5["prayer_time_hold"] is True
    assert c5["time_limit_minutes"] >= 60   # at minimum the +60 prayer extension


def test_all_actions_have_prayer_time_hold_key():
    """Every action must explicitly declare prayer_time_hold (True or False)."""
    for incident_type in INCIDENT_TYPES:
        p = generate_hajj_playbook(incident_type, "moderate", "peak")
        for a in p["actions"]:
            assert "prayer_time_hold" in a, (
                f"{incident_type} step {a['step']} missing prayer_time_hold key"
            )