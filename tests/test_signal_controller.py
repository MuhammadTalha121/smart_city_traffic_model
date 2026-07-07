import os
import csv
import pytest

os.environ.setdefault("API_KEY", "test-key-for-pytest-only")
TEST_KEY = os.environ["API_KEY"]

import src.config as cfg
from src.signal_controller import NTCIPStubController, ActuationSafetyGate


@pytest.fixture(autouse=True)
def _reset_actuation_flag(monkeypatch):
    monkeypatch.setattr(cfg, "ACTUATION_ENABLED", False)
    yield


def test_actuation_blocked_when_disabled(monkeypatch):
    monkeypatch.setattr("src.signal_controller.ACTUATION_ENABLED", False)
    controller = NTCIPStubController()
    result = controller.send_timing_plan("Zone_1", cycle_length=90, green_phase_seconds=45)
    assert result["status"] == "rejected"
    assert "disabled" in result["reason"].lower()


def test_actuation_blocked_outside_timing_range(monkeypatch):
    monkeypatch.setattr("src.signal_controller.ACTUATION_ENABLED", True)
    controller = NTCIPStubController()
    result = controller.send_timing_plan("Zone_2", cycle_length=250, green_phase_seconds=100)
    assert result["status"] == "rejected"
    assert "outside allowed range" in result["reason"]


def test_actuation_blocked_in_hajj_lockdown_zone(monkeypatch):
    monkeypatch.setattr("src.signal_controller.ACTUATION_ENABLED", True)
    monkeypatch.setattr("src.signal_controller.HAJJ_LOCKDOWN_ZONES", ["Zone_1"])
    controller = NTCIPStubController()
    result = controller.send_timing_plan("Zone_1", cycle_length=90, green_phase_seconds=45)
    assert result["status"] == "rejected"
    assert "lockdown" in result["reason"].lower()


def test_actuation_logged_on_success(tmp_path, monkeypatch):
    log_path = tmp_path / "signal_commands_log.csv"
    monkeypatch.setattr("src.signal_controller.SIGNAL_COMMANDS_LOG_PATH", str(log_path))
    monkeypatch.setattr("src.signal_controller.ACTUATION_ENABLED", True)

    controller = NTCIPStubController()
    result = controller.send_timing_plan("Zone_2", cycle_length=90, green_phase_seconds=45)

    assert result["status"] == "sent"
    assert os.path.exists(log_path)
    with open(log_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["zone"] == "Zone_2"
    assert rows[0]["status"] == "sent"


    
def test_unknown_zone_rejected(monkeypatch):
    monkeypatch.setattr("src.signal_controller.ACTUATION_ENABLED", True)
    controller = NTCIPStubController()
    result = controller.send_timing_plan("Zone_99", cycle_length=90, green_phase_seconds=45)
    assert result["status"] == "rejected"
    assert "unknown zone" in result["reason"].lower()


# ── endpoint tests ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app import app
    with TestClient(app) as c:
        yield c


def test_actuate_endpoint_requires_admin(client):
    from src.auth import create_key
    ro_key = create_key("READ_ONLY", "all")
    response = client.post(
        "/signals/actuate",
        json={"zone": "Zone_1", "cycle_length": 90, "green_phase_seconds": 45},
        headers={"X-API-Key": ro_key},
    )
    assert response.status_code == 403


def test_actuate_endpoint_rejected_when_disabled(client):
    response = client.post(
        "/signals/actuate",
        json={"zone": "Zone_1", "cycle_length": 90, "green_phase_seconds": 45},
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"


def test_actuate_endpoint_cooldown(client, monkeypatch):
    import src.signal_controller as sc
    monkeypatch.setattr(sc, "ACTUATION_ENABLED", True)

    r1 = client.post(
        "/signals/actuate",
        json={"zone": "Zone_2", "cycle_length": 90, "green_phase_seconds": 45},
        headers={"X-API-Key": TEST_KEY},
    )
    assert r1.json()["status"] == "sent"

    r2 = client.post(
        "/signals/actuate",
        json={"zone": "Zone_2", "cycle_length": 90, "green_phase_seconds": 45},
        headers={"X-API-Key": TEST_KEY},
    )
    assert r2.status_code == 429