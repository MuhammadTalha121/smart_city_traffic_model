import os
import pytest
from fastapi.testclient import TestClient
from app import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

TEST_KEY = os.environ.get("API_KEY", "test-key-for-pytest-only")
HEADERS  = {"X-API-Key": TEST_KEY}

def test_vsl_endpoint_returns_zone_list(client):
    r = client.get("/vsl/active-limits?city=Riyadh", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "zones" in data
    for z in data["zones"]:
        assert "recommended_speed_kmph" in z
        assert "enforcement_recommended" in z

def test_parking_endpoint_returns_garages(client):
    r = client.get("/parking/occupancy-forecast?city=Riyadh", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "garages" in data
    for g in data["garages"]:
        assert "forecast_1h" in g
        assert "current_fill_rate" in g

def test_drt_status_returns_eligible_zones(client):
    r = client.get("/transit/drt-status?city=Riyadh", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "available_shuttles" in data
    assert "queue_status" in data

def test_vms_endpoint_returns_boards(client):
    r = client.get("/vms/active-boards?city=Riyadh", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "boards" in data
    assert "all_zones_low" in data

def test_telemetry_status_returns_queue_info(client):
    r = client.get("/telemetry/status", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "queue_depth" in data
    assert "worker_active" in data

def test_sla_current_is_public(client):
    r = client.get("/sla/current")
    assert r.status_code == 200
    assert "uptime_pct" in r.json()