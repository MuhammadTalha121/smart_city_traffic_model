import pytest
from fastapi.testclient import TestClient
from app import app

TEST_KEY = "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780"

@pytest.fixture(scope="module")
def client():
    """Create a TestClient with lifespan startup."""
    with TestClient(app) as c:
        yield c

def test_fleet_status_returns_vehicles(client):
    response = client.get(
        "/freight/fleet-status?city=Riyadh",
        headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert "vehicles" in data
    assert data["total_vehicles"] > 0
    vehicle = data["vehicles"][0]
    assert "vehicle_id" in vehicle
    assert "current_zone" in vehicle
    assert "status" in vehicle

def test_fleet_reroute_valid_vehicle(client):
    response = client.post(
        "/freight/reroute/F-1001?city=Riyadh",
        headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["vehicle_id"] == "F-1001"
    assert "new_route" in data
    assert "original_route" in data
    assert "estimated_time_savings_min" in data

def test_fleet_reroute_invalid_vehicle(client):
    response = client.post(
        "/freight/reroute/INVALID?city=Riyadh",
        headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 404
    assert "not found" in response.text.lower()