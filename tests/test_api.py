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


def test_predict_valid_key_returns_emissions(client):
    """PROMPT 011: /predict response must include an emissions dict."""
    response = client.post(
        "/predict",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "emissions" in data
    emissions = data["emissions"]
    assert "fuel_litres"           in emissions
    assert "co2_kg"                in emissions
    assert "co2_tonnes"            in emissions
    assert "green_initiative_flag" in emissions
    assert emissions["co2_kg"] > 0


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


def test_emissions_summary_endpoint_returns_valid_structure(client):
    """PROMPT 011: /emissions/summary must return the expected response keys."""
    # Make a predict call first so the log exists
    client.post(
        "/predict",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": TEST_KEY},
    )
    response = client.get(
        "/emissions/summary?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "city"                     in data
    assert "total_co2_tonnes"         in data
    assert "green_initiative_events"  in data
    assert "green_initiative_threshold_kg" in data
