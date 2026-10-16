from datetime import datetime, timedelta

from src.pipeline import IncidentEscalationTracker


def _make_tracker_with_incident(severity: str, clearance_mins: float = 10.0):
    tracker = IncidentEscalationTracker()
    detected_at = datetime(2026, 1, 1, 8, 0, 0)
    tracker.register_incident(
        incident_id="inc_test",
        zone="Zone_1",
        city="Riyadh",
        severity=severity,
        estimated_clearance_mins=clearance_mins,
        detected_at=detected_at,
        speed_drop_pct=55.0,
        volume_change_pct=-30.0,
        confidence="High",
    )
    return tracker, detected_at


def test_incident_escalated_after_clearance_timeout():
    tracker, detected_at = _make_tracker_with_incident("Minor", clearance_mins=10.0)
    now = detected_at + timedelta(minutes=20)
    alerts = tracker.check_escalations(now=now)
    assert len(alerts) == 1
    assert alerts[0]["current_severity"] == "Moderate"
    assert alerts[0]["original_severity"] == "Minor"
    assert alerts[0]["metric"] == "incident_escalation"
    assert alerts[0]["zone"] == "Zone_1"
    assert alerts[0]["city"] == "Riyadh"


def test_critical_escalation_triggers_preemption_check():
    tracker, detected_at = _make_tracker_with_incident("Major", clearance_mins=10.0)
    now = detected_at + timedelta(minutes=20)
    alerts = tracker.check_escalations(now=now)
    assert len(alerts) == 1
    assert alerts[0]["current_severity"] == "Critical"
    assert "preemption_plan" in alerts[0]


def test_escalation_is_idempotent_per_level():
    tracker, detected_at = _make_tracker_with_incident("Minor", clearance_mins=10.0)
    now = detected_at + timedelta(minutes=20)
    first = tracker.check_escalations(now=now)
    second = tracker.check_escalations(now=now)
    assert len(first) == 1
    assert len(second) == 0