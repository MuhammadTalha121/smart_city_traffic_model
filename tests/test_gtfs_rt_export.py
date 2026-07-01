import os
import pytest
from fastapi.testclient import TestClient
from app import app
from src.gtfs_rt_export import to_gtfs_vehicle_position, to_gtfs_trip_update

os.environ.setdefault("API_KEY", "test-key-for-pytest-only")
TEST_KEY = os.environ["API_KEY"]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_gtfs_vehicle_position_includes_required_fields():
    trip = {
        "shuttle_id": "DRT_0",
        "passengers": 4,
        "route": ["Zone_4", "Zone_2", "Zone_1"],
        "estimated_wait_mins": 5,
        "estimated_journey_mins": 12,
    }
    result = to_gtfs_vehicle_position(trip)
    assert result["id"] == "vehicle-DRT_0"
    v = result["vehicle"]
    assert v["trip"]["trip_id"] == "DRT-DRT_0"
    assert "latitude" in v["position"] and "longitude" in v["position"]
    assert v["vehicle"]["id"] == "DRT_0"
    assert "timestamp" in v


def test_gtfs_trip_update_maps_congestion_to_delay():
    forecast = {
        "hours_ahead": 1, "forecast_hour": 9, "predicted_score": 0.7,
        "lower_bound": 0.6, "upper_bound": 0.8, "congestion_level": "Critical",
    }
    result = to_gtfs_trip_update(forecast, "Zone_1")
    stu = result["trip_update"]["stop_time_update"][0]
    assert stu["stop_id"] == "Zone_1"
    assert stu["arrival"]["delay"] == 360
    assert stu["arrival"]["uncertainty"] > 0


def test_gtfs_rt_endpoint_no_auth_returns_401(client):
    response = client.get("/export/gtfs-rt?city=Riyadh")
    assert response.status_code == 401


def test_gtfs_rt_endpoint_returns_valid_structure(client):
    response = client.get(
        "/export/gtfs-rt?city=Riyadh", headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["header"]["gtfs_realtime_version"] == "2.0"
    assert "entity" in data and isinstance(data["entity"], list)
    assert "gapNote" in data
    assert "not GTFS-RT compliant" in data["gapNote"]


def test_gtfs_rt_unknown_city_returns_404(client):
    response = client.get(
        "/export/gtfs-rt?city=Atlantis", headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 404