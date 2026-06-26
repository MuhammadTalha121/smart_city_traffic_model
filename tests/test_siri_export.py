import os
import pytest
from fastapi.testclient import TestClient
from app import app
from src.siri_export import to_siri_vehicle_activity, to_siri_estimated_timetable
from src.model import compute_signal_timing


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_to_siri_vehicle_activity_includes_required_fields():
    trip = {"shuttle_id": "DRT_0", "passengers": 4, "route": ["Zone_4", "Zone_2", "Zone_1"],
            "estimated_wait_mins": 5, "estimated_journey_mins": 12}
    result = to_siri_vehicle_activity(trip)
    assert "RecordedAtTime" in result
    journey = result["MonitoredVehicleJourney"]
    assert journey["VehicleRef"] == "DRT_0"
    assert journey["MonitoredCall"]["StopPointRef"] == "Zone_4"
    assert journey["MonitoredCall"]["DestinationDisplay"] == "Zone_1"
    assert "Longitude" in journey["VehicleLocation"]


def test_to_siri_estimated_timetable_includes_required_fields():
    timing = compute_signal_timing(congestion_score=0.5, vehicle_count=200, hour=8, is_weekend=0)
    result = to_siri_estimated_timetable("Zone_1", timing)
    journey = result["EstimatedVehicleJourney"]
    call = journey["EstimatedCalls"]["EstimatedCall"][0]
    assert call["StopPointRef"] == "Zone_1"
    assert "ExpectedArrivalTime" in call
    assert "ArrivalStatus" in call


def test_siri_export_requires_auth(client):
    response = client.get("/export/siri?city=Riyadh")
    assert response.status_code == 401


def test_siri_export_returns_valid_structure(client):
    api_key = os.getenv("API_KEY")
    if not api_key:
        pytest.skip("API_KEY not set in environment")
    response = client.get("/export/siri?city=Riyadh", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    delivery = data["Siri"]["ServiceDelivery"]
    assert "ResponseTimestamp" in delivery
    assert "EstimatedTimetableDelivery" in delivery  # always populated (per-zone signal data exists)


def test_siri_export_unknown_city_returns_404(client):
    api_key = os.getenv("API_KEY")
    if not api_key:
        pytest.skip("API_KEY not set in environment")
    response = client.get("/export/siri?city=Atlantis", headers={"X-API-Key": api_key})
    assert response.status_code == 404