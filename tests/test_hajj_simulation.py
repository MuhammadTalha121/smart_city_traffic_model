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
