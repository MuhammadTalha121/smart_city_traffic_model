import pytest
from fastapi.testclient import TestClient
from app import app
from src.model import calculate_zone_emissions

TEST_KEY = "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780"

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_emissions_increase_with_congestion():
    # Test that emissions increase when speed decreases
    em1 = calculate_zone_emissions("Zone_1", "Riyadh", 100, 60)
    em2 = calculate_zone_emissions("Zone_1", "Riyadh", 100, 20)
    assert em2["co2_kg"] > em1["co2_kg"]

def test_fleet_composition_sums_to_one():
    from src.config import FLEET_COMPOSITION_RIYADH
    total = sum(FLEET_COMPOSITION_RIYADH.values())
    assert abs(total - 1.0) < 0.001

def test_zone_emissions_report_endpoint(client):
    response = client.get(
        "/emissions/zone-report?city=Riyadh",
        headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert "zones" in data
    assert len(data["zones"]) > 0
    assert "total_co2_kg" in data
    assert "avg_efficiency_rating" in data
    zone = data["zones"][0]
    assert "co2_kg" in zone
    assert "nox_g" in zone
    assert "efficiency_rating" in zone