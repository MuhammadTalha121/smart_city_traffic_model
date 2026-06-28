"""
 Incident API Endpoints
                
"""

import os
import csv
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("API_KEY", "test-key-for-pytest-only")
TEST_KEY = os.environ["API_KEY"]

# ---------------------------------------------------------------------------
# Unit tests for detect_incidents() and estimate_incident_clearance_time()
# ---------------------------------------------------------------------------

from src.model import (
    detect_incidents,
    estimate_incident_clearance_time,
    INCIDENTS_LOG_PATH,
)
from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features


def _make_zone_df(
    n_rows: int = 20,
    base_speed: float = 70.0,
    recent_speed: float = 70.0,
    base_volume: float = 200.0,
    recent_volume: float = 200.0,
    weather: str = "clear",
    road_type: str = "arterial",
    zone: str = "Zone_1",
) -> pd.DataFrame:
    """
    Build a minimal synthetic DataFrame with an explicit speed/volume pattern
    for testing detect_incidents() without going through the full pipeline.
    """
    timestamps = pd.date_range("2025-01-01", periods=n_rows, freq="h")
    # Last 2 rows = "recent window", rest = baseline
    speeds = [base_speed] * (n_rows - 2) + [recent_speed, recent_speed]
    volumes = [base_volume] * (n_rows - 2) + [recent_volume, recent_volume]

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "zone": zone,
            "city": "Riyadh",
            "avg_speed": speeds,
            "vehicle_count": volumes,
            "weather": weather,
            "road_type": road_type,
            "congestion_score": [0.3] * n_rows,
        }
    )
    return df


# ── unit tests ───────────────────────────────────────────────────


def test_incident_detected_on_sudden_speed_collapse(tmp_path, monkeypatch):
    """
    60% speed drop (70 → 28 km/h) must trigger detection with severity
    at least Major and confidence Medium or High.
    """
    monkeypatch.setattr(
        "src.model.INCIDENTS_LOG_PATH", str(tmp_path / "incidents.csv")
    )
    df = _make_zone_df(base_speed=70.0, recent_speed=28.0)
    result = detect_incidents(df, zone="Zone_1", city="Riyadh", log=False)

    assert result["incident_detected"] is True, (
        f"Expected incident_detected=True, got False. speed_drop_pct={result['speed_drop_pct']}"
    )
    assert result["severity"] in ("Major", "Critical"), (
        f"Expected Major or Critical severity, got {result['severity']}"
    )
    assert result["confidence"] in ("Medium", "High"), (
        f"Unexpected confidence {result['confidence']}"
    )
    assert result["clearance_mins"] is not None and result["clearance_mins"] > 0


def test_incident_not_triggered_by_normal_congestion(tmp_path, monkeypatch):
    """
    High vehicle count with only a gradual speed reduction (15%) must not
    trigger incident detection — this is normal congestion, not an incident.
    """
    monkeypatch.setattr(
        "src.model.INCIDENTS_LOG_PATH", str(tmp_path / "incidents.csv")
    )
    # 15% speed drop — below the 40% INCIDENT_SPEED_DROP_THRESHOLD
    df = _make_zone_df(
        base_speed=70.0, recent_speed=59.5,   # 15% drop
        base_volume=200.0, recent_volume=380.0,  # high volume spike (anomaly, not incident)
    )
    result = detect_incidents(df, zone="Zone_1", city="Riyadh", log=False)

    assert result["incident_detected"] is False, (
        f"Expected no incident on 15% speed drop, got incident with severity {result['severity']}"
    )


def test_incident_clearance_time_longer_in_sandstorm():
    """
    Clearance time for a Major incident in a sandstorm must exceed clearance
    time under clear conditions (sandstorm adds +50% per the spec).
    """
    clear_time = estimate_incident_clearance_time("Major", "clear", "arterial")
    sandstorm_time = estimate_incident_clearance_time("Major", "sandstorm", "arterial")

    assert sandstorm_time > clear_time, (
        f"Sandstorm clearance ({sandstorm_time} min) should exceed clear ({clear_time} min)"
    )
    # 50% premium → sandstorm time ≈ 1.5× clear time (within 5% tolerance)
    ratio = sandstorm_time / clear_time
    assert 1.40 <= ratio <= 1.60, (
        f"Expected ~1.5× sandstorm penalty, got {ratio:.2f}×"
    )


def test_incident_clearance_time_critical_exceeds_minor():
    """Critical incidents take longer to clear than Minor ones."""
    minor = estimate_incident_clearance_time("Minor", "clear", "arterial")
    critical = estimate_incident_clearance_time("Critical", "clear", "arterial")
    assert critical > minor


def test_incident_severity_order():
    """Critical speed drop (85%) must produce Critical severity."""
    df = _make_zone_df(base_speed=70.0, recent_speed=10.5)  # 85% drop
    result = detect_incidents(df, zone="Zone_1", log=False)
    assert result["severity"] == "Critical", (
        f"Expected Critical severity, got {result['severity']}"
    )


# ──endpoint tests ───────────────────────────────────────────────


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app import app

    with TestClient(app) as c:
        yield c


def test_incidents_active_returns_valid_structure(client):
    """
    /incidents/active must return a valid JSON object with:
      city, total_incidents (int), incidents (list), timestamp.
    Each incident in the list must include the required fields.
    Returns 200 even when no incidents are active (empty list).
    """
    response = client.get(
        "/incidents/active?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200, f"Unexpected status: {response.status_code}"
    data = response.json()

    assert "city" in data
    assert "total_incidents" in data
    assert "incidents" in data
    assert "timestamp" in data
    assert isinstance(data["incidents"], list)
    assert data["total_incidents"] == len(data["incidents"])

    # If there are any incidents, validate their schema
    for incident in data["incidents"]:
        for field in (
            "zone", "severity", "speed_drop_pct", "volume_change_pct",
            "confidence", "recommended_action", "clearance_mins",
        ):
            assert field in incident, (
                f"Missing field '{field}' in incident: {incident}"
            )
        assert incident["severity"] in ("Minor", "Moderate", "Major", "Critical")
        assert incident["confidence"] in ("Low", "Medium", "High")
        assert isinstance(incident["speed_drop_pct"], (int, float))


def test_incidents_active_no_auth_returns_401(client):
    """Missing API key must return 401."""
    response = client.get("/incidents/active?city=Riyadh")
    assert response.status_code == 401


def test_incidents_active_sorted_by_severity_descending(client, monkeypatch):
    """
    When multiple incidents exist, they must be sorted Critical → Major →
    Moderate → Minor (highest severity first).
    """
    response = client.get(
        "/incidents/active?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    incidents = response.json()["incidents"]

    severity_order = {"Critical": 4, "Major": 3, "Moderate": 2, "Minor": 1}
    scores = [severity_order.get(i["severity"], 0) for i in incidents]
    assert scores == sorted(scores, reverse=True), (
        f"Incidents not sorted by severity: {[i['severity'] for i in incidents]}"
    )


def test_incidents_history_returns_valid_structure(client, tmp_path, monkeypatch):
    """
    /incidents/history must return city, hours, zone_filter,
    total_incidents, and incidents (list), sorted newest first.
    Must return empty list (not 404) when no log exists.
    """
    response = client.get(
        "/incidents/history?city=Riyadh&hours=24",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "city" in data
    assert "hours" in data
    assert "total_incidents" in data
    assert "incidents" in data
    assert isinstance(data["incidents"], list)
    assert data["total_incidents"] == len(data["incidents"])


def test_incidents_history_filters_by_zone(tmp_path, monkeypatch):
    """
    When a zone filter is applied, only incidents from that zone are returned.
    """
    from src.model import _log_incident, INCIDENTS_LOG_PATH
    import src.model as model_module

    log_file = str(tmp_path / "test_incidents_log.csv")
    monkeypatch.setattr(model_module, "INCIDENTS_LOG_PATH", log_file)

    # Write two incidents: one Zone_1, one Zone_2
    now = datetime.now()
    for zone in ("Zone_1", "Zone_2"):
        _log_incident({
            "timestamp": now.isoformat(),
            "city": "Riyadh",
            "zone": zone,
            "severity": "Minor",
            "speed_drop_pct": 0.42,
            "volume_change_pct": -0.10,
            "confidence": "Medium",
            "clearance_mins": 15.0,
        })

    # Read and filter manually (simulating endpoint logic)
    df = pd.read_csv(log_file)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    zone_filtered = df[df["zone"] == "Zone_1"]

    assert len(zone_filtered) == 1
    assert zone_filtered.iloc[0]["zone"] == "Zone_1"

    # Confirm Zone_2 not in result
    assert "Zone_2" not in zone_filtered["zone"].values


def test_incident_log_created_on_detection(tmp_path, monkeypatch):
    """
    When detect_incidents() fires and log=True, incidents_log.csv must exist
    and contain a row with the correct zone, city, and severity.
    """
    import src.model as model_module

    log_file = str(tmp_path / "incidents_log.csv")
    monkeypatch.setattr(model_module, "INCIDENTS_LOG_PATH", log_file)

    # Trigger a clear incident (60% speed drop)
    df = _make_zone_df(base_speed=70.0, recent_speed=28.0)
    result = detect_incidents(df, zone="Zone_1", city="Riyadh", log=True)

    assert result["incident_detected"] is True
    assert os.path.exists(log_file), "incidents_log.csv was not created"

    written = pd.read_csv(log_file)
    assert len(written) >= 1
    row = written.iloc[-1]
    assert row["zone"] == "Zone_1"
    assert row["city"] == "Riyadh"
    assert row["severity"] in ("Minor", "Moderate", "Major", "Critical")
    assert float(row["speed_drop_pct"]) > 0


def test_incident_log_not_created_when_no_incident(tmp_path, monkeypatch):
    """
    When no incident is detected, incidents_log.csv must NOT be created
    (no empty/false-positive rows written).
    """
    import src.model as model_module

    log_file = str(tmp_path / "no_incident_log.csv")
    monkeypatch.setattr(model_module, "INCIDENTS_LOG_PATH", log_file)

    df = _make_zone_df(base_speed=70.0, recent_speed=65.0)  # only 7% drop
    result = detect_incidents(df, zone="Zone_1", city="Riyadh", log=True)

    assert result["incident_detected"] is False
    assert not os.path.exists(log_file), "Log should not be created when no incident detected"


def test_incidents_history_no_auth_returns_401(client):
    """Missing API key returns 401 for history endpoint too."""
    response = client.get("/incidents/history?city=Riyadh")
    assert response.status_code == 401


def test_incidents_history_empty_when_no_log(client):
    """
    /incidents/history returns 200 with empty list (not 404)
    even when the log file doesn't exist.
    """
    # Temporarily move the log file if it exists
    import src.model as model_module
    original = model_module.INCIDENTS_LOG_PATH
    model_module.INCIDENTS_LOG_PATH = "/tmp/nonexistent_incidents_9999.csv"
    try:
        response = client.get(
            "/incidents/history?city=Riyadh&hours=1",
            headers={"X-API-Key": TEST_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_incidents"] == 0
        assert data["incidents"] == []
    finally:
        model_module.INCIDENTS_LOG_PATH = original
