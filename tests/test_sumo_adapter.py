import pytest
import os
from fastapi.testclient import TestClient
from app import app

os.environ.setdefault("API_KEY", "test-key-for-pytest-only")
TEST_KEY = os.environ["API_KEY"]


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    with TestClient(app) as c:
        yield c


def test_sumo_status_endpoint_returns_structure(client):
    """GET /simulation/sumo-status should return availability and config."""
    response = client.get("/simulation/sumo-status", headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 200
    data = response.json()
    assert "available" in data
    assert "engine" in data
    assert "binary" in data


def test_simulation_run_returns_engine_flag(client):
    """POST /simulation/run should return engine flag (static or sumo)."""
    response = client.post(
        "/simulation/run",
        json={
            "city": "Riyadh",
            "scenario": {"zone_closures": ["Zone_1"]},
            "duration_minutes": 10,
        },
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    # Engine can be "sumo", "static", or "sumo_fallback"
    assert data["engine"] in ("sumo", "static", "sumo_fallback")
    assert "zones" in data
    assert isinstance(data["zones"], list)
    # Check that each zone has the required fields
    for zone_data in data["zones"]:
        assert "zone" in zone_data
        assert "avg_speed_kmh" in zone_data
        assert "queue_length_vehicles" in zone_data
        assert "throughput_vph" in zone_data


def test_simulation_run_invalid_scenario_key(client):
    """Invalid scenario keys should return 422."""
    response = client.post(
        "/simulation/run",
        json={
            "city": "Riyadh",
            "scenario": {"invalid_key": "value"},
        },
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 422


def test_simulation_run_city_not_found(client):
    """Unknown city should return 404."""
    response = client.post(
        "/simulation/run",
        json={
            "city": "InvalidCity",
            "scenario": {},
        },
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 404