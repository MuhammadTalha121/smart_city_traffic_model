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






# ── — Actuator Feedback Loop & Confirmation ───────────────

import time
import src.signal_controller as sc
from src.signal_controller import confirm_actuation


@pytest.fixture(autouse=True)
def _reset_escalation_dedup():
    sc._last_escalation_sent.clear()
    yield
    sc._last_escalation_sent.clear()


def test_confirmed_actuation_updates_log(tmp_path, monkeypatch):
    log_path = tmp_path / "signal_commands_log.csv"
    monkeypatch.setattr(sc, "SIGNAL_COMMANDS_LOG_PATH", str(log_path))
    monkeypatch.setattr(sc.NTCIPStubController, "verify_timing_applied", lambda self, zone, plan: True)

    confirm_actuation("cmd-1", "Zone_2", {"cycle_length": 90, "green_phase_seconds": 45, "offset": 0})

    with open(log_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["status"] == "CONFIRMED"
    assert rows[0]["confirmed"] == "True"
    assert rows[0]["zone"] == "Zone_2"


def test_failed_confirmation_triggers_alert(tmp_path, monkeypatch):
    log_path = tmp_path / "signal_commands_log.csv"
    monkeypatch.setattr(sc, "SIGNAL_COMMANDS_LOG_PATH", str(log_path))
    monkeypatch.setattr(sc.NTCIPStubController, "verify_timing_applied", lambda self, zone, plan: False)
    monkeypatch.setattr(sc, "CONFIRMATION_RETRY_DELAY_S", 0.01)

    alerts_fired = []
    monkeypatch.setattr("src.pipeline.deliver_webhook_alert", lambda alerts, url: alerts_fired.append(alerts))
    monkeypatch.setattr("src.pipeline.log_alert", lambda alerts: None)

    confirm_actuation("cmd-2", "Zone_2", {"cycle_length": 90, "green_phase_seconds": 45, "offset": 0})
    time.sleep(0.3)  # allow retry timer to fire and exhaust

    with open(log_path) as f:
        rows = list(csv.DictReader(f))
    statuses = [r["status"] for r in rows]
    assert "UNCONFIRMED" in statuses
    assert len(alerts_fired) == 1
    assert alerts_fired[0][0]["severity"] == "Elevated"


def test_emergency_preemption_failure_escalates_critical(tmp_path, monkeypatch):
    log_path = tmp_path / "signal_commands_log.csv"
    monkeypatch.setattr(sc, "SIGNAL_COMMANDS_LOG_PATH", str(log_path))
    monkeypatch.setattr(sc.NTCIPStubController, "verify_timing_applied", lambda self, zone, plan: False)
    monkeypatch.setattr(sc, "CONFIRMATION_RETRY_DELAY_S", 0.01)

    alerts_fired = []
    monkeypatch.setattr("src.pipeline.deliver_webhook_alert", lambda alerts, url: alerts_fired.append(alerts))
    monkeypatch.setattr("src.pipeline.log_alert", lambda alerts: None)

    confirm_actuation(
        "cmd-3", "Zone_2",
        {"cycle_length": 90, "green_phase_seconds": 45, "offset": 0, "purpose": "emergency_preemption"},
    )
    time.sleep(0.3)

    assert alerts_fired[0][0]["severity"] == "Critical"


def test_escalation_deduplicated_within_window(tmp_path, monkeypatch):
    log_path = tmp_path / "signal_commands_log.csv"
    monkeypatch.setattr(sc, "SIGNAL_COMMANDS_LOG_PATH", str(log_path))
    monkeypatch.setattr(sc.NTCIPStubController, "verify_timing_applied", lambda self, zone, plan: False)
    monkeypatch.setattr(sc, "CONFIRMATION_RETRY_DELAY_S", 0.01)

    alerts_fired = []
    monkeypatch.setattr("src.pipeline.deliver_webhook_alert", lambda alerts, url: alerts_fired.append(alerts))
    monkeypatch.setattr("src.pipeline.log_alert", lambda alerts: None)

    confirm_actuation("cmd-4", "Zone_2", {"cycle_length": 90, "green_phase_seconds": 45, "offset": 0})
    time.sleep(0.3)
    confirm_actuation("cmd-5", "Zone_2", {"cycle_length": 90, "green_phase_seconds": 45, "offset": 0})
    time.sleep(0.3)

    assert len(alerts_fired) == 1  # second escalation deduplicated within 15-min window


def test_confirmation_success_after_one_retry(tmp_path, monkeypatch):
    """First check fails, retry succeeds -> only one CONFIRMED row, no escalation."""
    log_path = tmp_path / "signal_commands_log.csv"
    monkeypatch.setattr(sc, "SIGNAL_COMMANDS_LOG_PATH", str(log_path))
    monkeypatch.setattr(sc, "CONFIRMATION_RETRY_DELAY_S", 0.01)

    call_count = {"n": 0}
    def flaky_verify(self, zone, plan):
        call_count["n"] += 1
        return call_count["n"] >= 2  # fails first, succeeds second

    monkeypatch.setattr(sc.NTCIPStubController, "verify_timing_applied", flaky_verify)

    alerts_fired = []
    monkeypatch.setattr("src.pipeline.deliver_webhook_alert", lambda alerts, url: alerts_fired.append(alerts))
    monkeypatch.setattr("src.pipeline.log_alert", lambda alerts: None)

    confirm_actuation("cmd-6", "Zone_2", {"cycle_length": 90, "green_phase_seconds": 45, "offset": 0})
    time.sleep(0.3)

    with open(log_path) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["status"] == "CONFIRMED"
    assert len(alerts_fired) == 0


# ── endpoint tests ──────────────────────────────────────────────

def test_actuation_log_endpoint_no_auth_returns_401(client):
    response = client.get("/signals/actuation-log")
    assert response.status_code == 401


def test_actuation_log_endpoint_returns_valid_structure(client):
    response = client.get("/signals/actuation-log", headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "commands" in data
    assert isinstance(data["commands"], list)


def test_actuation_log_endpoint_requires_operator_or_admin(client):
    from src.auth import create_key
    ro_key = create_key("READ_ONLY", "all")
    response = client.get("/signals/actuation-log", headers={"X-API-Key": ro_key})
    assert response.status_code == 403


def test_actuate_endpoint_schedules_confirmation_on_success(client, monkeypatch):
    """When ACTUATION_ENABLED and send succeeds, schedule_confirmation must be called."""
    import src.signal_controller as sc_module
    import app as app_module

    monkeypatch.setattr(sc_module, "ACTUATION_ENABLED", True)

    scheduled = []
    monkeypatch.setattr(
        app_module, "schedule_confirmation",
        lambda command_id, zone, plan: scheduled.append((command_id, zone, plan)),
    )

    response = client.post(
        "/signals/actuate",
        json={"zone": "Zone_4", "cycle_length": 90, "green_phase_seconds": 45, "purpose": "routine"},
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert len(scheduled) == 1
    assert scheduled[0][1] == "Zone_4"
    assert scheduled[0][2]["purpose"] == "routine"