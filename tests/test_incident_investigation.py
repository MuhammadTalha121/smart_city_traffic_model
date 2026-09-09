import os
import pytest
from fastapi.testclient import TestClient
from app import app
from src.model import reconstruct_incident_timeline

TEST_KEY = "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780"

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_timeline_covers_all_log_sources(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import pandas as pd
    from datetime import datetime

    # Incidents log
    inc_df = pd.DataFrame([{
        "timestamp": datetime.now().isoformat(),
        "city": "Riyadh",
        "zone": "Zone_1",
        "severity": "Major",
        "speed_drop_pct": 0.65,
        "volume_change_pct": -0.55,
        "confidence": "High",
        "clearance_mins": 69.0,
    }])
    inc_df.to_csv("incidents_log.csv", index=False)

    # Predictions log
    pred_df = pd.DataFrame([{
        "timestamp": datetime.now().isoformat(),
        "city": "Riyadh",
        "zone": "Zone_1",
        "congestion_score": 0.7,
        "congestion_level": "High",
        "top_factor_1": "speed",
        "top_factor_2": "volume",
        "top_factor_3": "hour",
        "plain_english": "High congestion",
    }])
    pred_df.to_csv("predictions_log.csv", index=False)

    # Signal commands log
    sig_df = pd.DataFrame([{
        "timestamp": datetime.now().isoformat(),
        "zone": "Zone_1",
        "cycle_seconds": 90,
        "green_seconds": 45,
        "status": "sent",
        "command_id": "cmd-123",
        "purpose": "routine",
    }])
    sig_df.to_csv("signal_commands_log.csv", index=False)

    # Alerts log
    alert_df = pd.DataFrame([{
        "timestamp": datetime.now().isoformat(),
        "city": "Riyadh",
        "zone": "Zone_1",
        "alert_type": "congestion",
        "severity": "High",
        "metric": "congestion_score",
        "threshold": 0.6,
    }])
    alert_df.to_csv("alerts_log.csv", index=False)

    # Call the function
    timeline = reconstruct_incident_timeline(0, "Riyadh")
    assert "events" in timeline
    # We expect at least one event of each of the three types: prediction, signal_command, alert
    assert len(timeline["events"]) >= 3
    event_types = {e["event_type"] for e in timeline["events"]}
    assert "prediction" in event_types
    assert "signal_command" in event_types
    assert "alert" in event_types

def test_incident_report_generated_as_markdown(client):
    response = client.get(
        "/incidents/investigate/0?city=Riyadh",
        headers={"X-API-Key": TEST_KEY}
    )
    if response.status_code == 404:
        pytest.skip("No incident at index 0; run the system with incidents first.")
    assert response.status_code == 200
    data = response.json()
    assert "report_path" in data
    assert os.path.exists(data["report_path"])
    with open(data["report_path"], "r") as f:
        content = f.read()
    assert "## Timeline" in content
    assert "## Contributing Factors" in content
    assert "## Signal Actions" in content
    assert "## Alerts Fired" in content