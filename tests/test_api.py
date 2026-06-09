import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("API_KEY", "test-key-for-pytest-only")

from app import app

TEST_KEY = os.environ["API_KEY"]

VALID_PAYLOAD = {
    "city"           : "Riyadh",
    "zone"           : "Zone_1",
    "hour"           : 8,
    "vehicle_count"  : 300,
    "avg_speed"      : 40.0,
    "weather"        : "clear",
    "road_type"      : "highway",
    "rush_hour"      : 1,
    "is_weekend"     : 0,
    "is_late_night"  : 0,
    "event"          : 0,
    "hour_multiplier": 1.4,
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint_no_auth_returns_200(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_predict_no_key_returns_401(client):
    response = client.post("/predict", json=VALID_PAYLOAD)
    assert response.status_code == 401


def test_predict_wrong_key_returns_401(client):
    response = client.post(
        "/predict",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": "totally-wrong-key"},
    )
    assert response.status_code == 401


def test_predict_valid_key_returns_prediction(client):
    response = client.post(
        "/predict",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "congestion_score"  in data
    assert "congestion_level"  in data
    assert "explanation"       in data
    assert "plain_english"     in data
    assert 0.0 <= data["congestion_score"] <= 1.0


def test_predict_includes_schedule_and_hajj_mode(client):
    """Predict response must include schedule string and hajj_mode flag."""
    payload  = {**VALID_PAYLOAD, "hajj_mode": False}
    response = client.post(
        "/predict",
        json=payload,
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "schedule"  in data, "schedule key missing from /predict response"
    assert "hajj_mode" in data, "hajj_mode key missing from /predict response"
    assert isinstance(data["schedule"],  str)
    assert isinstance(data["hajj_mode"], bool)


def test_predict_invalid_hour_returns_422(client):
    bad_payload = {**VALID_PAYLOAD, "hour": 25}
    response = client.post(
        "/predict",
        json=bad_payload,
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 422


def test_anomalies_endpoint_returns_list(client):
    response = client.get(
        "/anomalies?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_anomalies" in data
    assert "anomalies"       in data
    assert isinstance(data["anomalies"], list)


def test_forecast_endpoint_returns_three_horizons(client):
    response = client.get(
        "/forecast?city=Riyadh&zone=Zone_1",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "forecasts" in data
    assert len(data["forecasts"]) == 3
    for fc in data["forecasts"]:
        assert "hours_ahead"      in fc
        assert "predicted_score"  in fc
        assert "congestion_level" in fc


def test_schedule_active_no_auth_returns_401(client):
    """schedule/active must require authentication."""
    response = client.get("/schedule/active?city=Riyadh")
    assert response.status_code == 401


def test_schedule_active_returns_valid_structure(client):
    """schedule/active must return schedule, next_event, days_until, city."""
    response = client.get(
        "/schedule/active?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "schedule"   in data, "schedule key missing"
    assert "city"       in data, "city key missing"
    assert "next_event" in data, "next_event key missing"
    assert "days_until" in data, "days_until key missing"
    assert isinstance(data["schedule"], str)
    assert data["city"] == "Riyadh"


def test_interventions_active_no_auth_returns_401(client):
    """/interventions/active must require authentication."""
    response = client.get("/interventions/active?city=Riyadh")
    assert response.status_code == 401


def test_interventions_active_returns_list(client):
    """/interventions/active must return a list of interventions with required keys."""
    response = client.get(
        "/interventions/active?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "city"                in data
    assert "total_interventions" in data
    assert "interventions"       in data
    assert isinstance(data["interventions"], list)

    for item in data["interventions"]:
        assert item["congestion_level"] in ("High", "Critical"), (
            f"Unexpected level '{item['congestion_level']}' in /interventions/active"
        )
        iv = item["intervention"]
        assert "urgency"               in iv
        assert "operator_action"       in iv
        assert "commuter_advice"       in iv
        assert "metro_station"         in iv
        assert "carpool_available"     in iv
        assert "recommended_departure" in iv
