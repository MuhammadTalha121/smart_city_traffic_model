import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")
TEST_KEY = os.environ["API_KEY"]

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app import app
from src.model import predict_pedestrian_crossing_demand, compute_adaptive_signal_timing


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_crossing_demand_high_after_prayer():
    friday_after_prayer = datetime(2026, 10, 9, 12, 5, 0)
    result = predict_pedestrian_crossing_demand(
        zone="Zone_1",
        city="Riyadh",
        timestamp=friday_after_prayer,
    )
    assert result["demand_level"] == "High"
    assert result["recommended_pedestrian_phase_extension_seconds"] > 0
    assert "prayer" in result["rationale"].lower()


def test_pedestrian_phase_extended_when_demand_high():
    timing = compute_adaptive_signal_timing(
        zone="Zone_1",
        vehicle_count=300,
        queue_length_estimate=0.5,
        adjacent_zone_scores={"Zone_2": 0.3},
        hour=12,
        is_weekend=1,
    )
    assert "pedestrian_demand" in timing
    assert "pedestrian_phase_extension_seconds" in timing
    assert timing["pedestrian_phase_extension_seconds"] >= 0


def test_crossing_demand_endpoint(client):
    response = client.get(
        "/pedestrian/crossing-demand?zone=Zone_1&city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["zone"] == "Zone_1"
    assert data["demand_level"] in ("Low", "Medium", "High")
    assert "recommended_pedestrian_phase_extension_seconds" in data