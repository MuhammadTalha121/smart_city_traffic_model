import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")
TEST_KEY = os.environ["API_KEY"]

import pytest
from fastapi.testclient import TestClient
from app import app
from src.signal_controller import SPaTBroadcaster
from src.config import SPAT_PROTOCOL


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_spat_message_format_correct():
    """The message must include all expected SPaT fields."""
    broadcaster = SPaTBroadcaster()
    message = broadcaster.generate_spat_message(
        zone="Zone_1",
        current_phase="green",
        time_remaining_s=15,
    )

    assert message["protocol"] == SPAT_PROTOCOL
    assert message["zone"] == "Zone_1"
    assert message["intersection_id"].startswith("RUH-Zone1")
    assert "timestamp_ms" in message
    assert "cycle_seconds" in message
    assert "phases" in message
    assert len(message["phases"]) == 2

    phase = message["phases"][0]
    for field in [
        "phase_id", "phase_state", "start_time_ms",
        "min_end_time_ms", "max_end_time_ms", "likely_end_time_ms",
    ]:
        assert field in phase, f"Missing SPaT phase field: {field}"

    assert phase["phase_state"] == "protected-Movement-Allowed"
    assert phase["likely_end_time_ms"] > phase["start_time_ms"]
    assert phase["max_end_time_ms"] >= phase["likely_end_time_ms"]


def test_spat_broadcast_writes_to_log(tmp_path, monkeypatch):
    """broadcast_spat must append a row to the log file."""
    monkeypatch.chdir(tmp_path)
    broadcaster = SPaTBroadcaster()
    broadcaster.broadcast_spat(
        zone="Zone_2",
        current_phase="yellow",
        time_remaining_s=2,
    )
    assert os.path.exists("spat_broadcast_log.csv")
    with open("spat_broadcast_log.csv", "r", encoding="utf-8") as f:
        content = f.read()
    assert "Zone_2" in content
    assert "yellow" in content


def test_spat_red_phase_state():
    """Red phase must map to stop-And-Remain."""
    broadcaster = SPaTBroadcaster()
    message = broadcaster.generate_spat_message(
        zone="Zone_3",
        current_phase="red",
        time_remaining_s=40,
    )
    assert message["phases"][0]["phase_state"] == "stop-And-Remain"


def test_spat_endpoint_accessible_without_auth(client):
    """V2X broadcasts are public — no API key required."""
    response = client.get("/v2x/spat/Zone_1?city=Riyadh")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["city"] == "Riyadh"
    assert "message" in data
    msg = data["message"]
    assert msg["zone"] == "Zone_1"
    assert "phases" in msg
    assert msg["broadcast_mode"] == "stub"


def test_spat_endpoint_rejects_unknown_city(client):
    response = client.get("/v2x/spat/Zone_1?city=Atlantis")
    assert response.status_code == 404