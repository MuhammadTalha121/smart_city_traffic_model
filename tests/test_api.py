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


def test_safety_hotspots_no_auth_returns_401(client):
    """/safety/hotspots must require authentication."""
    response = client.get("/safety/hotspots?city=Riyadh")
    assert response.status_code == 401


def test_safety_hotspots_returns_ranked_list(client):
    """/safety/hotspots must return all zones ranked by risk_score descending."""
    response = client.get(
        "/safety/hotspots?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "city"        in data
    assert "total_zones" in data
    assert "hotspots"    in data
    assert isinstance(data["hotspots"], list)
    assert len(data["hotspots"]) == data["total_zones"]

    # Verify sorted descending by risk_score
    scores = [h["risk_score"] for h in data["hotspots"]]
    assert scores == sorted(scores, reverse=True), (
        "Hotspots not sorted by risk_score descending"
    )

    # Verify required keys on each hotspot
    for h in data["hotspots"]:
        assert "zone"                in h
        assert "risk_score"          in h
        assert "risk_level"          in h
        assert "primary_risk_factor" in h
        assert 0.0 <= h["risk_score"] <= 1.0


def test_signals_recommended_no_auth_returns_401(client):
    """/signals/recommended must require authentication."""
    response = client.get("/signals/recommended?city=Riyadh")
    assert response.status_code == 401


def test_signals_recommended_returns_all_zones(client):
    """/signals/recommended must return signal timing for all zones sorted by congestion."""
    response = client.get(
        "/signals/recommended?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "city"        in data
    assert "total_zones" in data
    assert "signals"     in data
    assert isinstance(data["signals"], list)
    assert len(data["signals"]) == data["total_zones"]

    # Verify sorted descending by congestion_score
    scores = [s["congestion_score"] for s in data["signals"]]
    assert scores == sorted(scores, reverse=True), (
        "Signals not sorted by congestion_score descending"
    )

    # Verify signal_timing structure on each entry
    for s in data["signals"]:
        st = s["signal_timing"]
        assert "cycle_seconds"    in st
        assert "green_seconds"    in st
        assert "red_seconds"      in st
        assert "phase_ratio"      in st
        assert "timing_rationale" in st
        assert st["cycle_seconds"] == 90
        assert st["green_seconds"] + st["red_seconds"] == 90


# ---------------------------------------------------------------------------
# Multi-city comparison test
# ---------------------------------------------------------------------------

def test_cities_compare_returns_all_configured_cities(client):
    """/cities/compare must return a snapshot for all four configured cities."""
    response = client.get(
        "/cities/compare",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "cities"       in data
    assert "total_cities" in data
    assert data["total_cities"] == 4

    names = {c["city"] for c in data["cities"]}
    assert names == {"Riyadh", "NEOM", "Dubai", "Karachi"}, (
        f"Expected all four cities, got {names}"
    )

    # Verify sorted descending by avg_congestion_score
    scores = [c["avg_congestion_score"] for c in data["cities"]]
    assert scores == sorted(scores, reverse=True)

    # Verify required keys on each city snapshot
    for c in data["cities"]:
        assert "avg_congestion_score" in c
        assert "max_zone"             in c
        assert "peak_hour"            in c
        assert "total_anomalies"      in c
        assert "avg_risk_score"       in c


def test_emergency_response_time_no_auth_returns_401(client):
    response = client.get("/emergency/response-time?city=Riyadh&target_zone=Zone_3")
    assert response.status_code == 401


def test_emergency_response_time_returns_estimates(client):
    response = client.get(
        "/emergency/response-time?city=Riyadh&target_zone=Zone_3",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "target_zone"               in data
    assert "current_congestion_level"  in data
    assert "fastest_estimated_minutes" in data
    assert "who_threshold_mins"        in data
    assert isinstance(data["estimates"], list)
    assert len(data["estimates"]) >= 1

    est = data["estimates"][0]
    assert "station_name"      in est
    assert "origin_zone"       in est
    assert "distance_km"       in est
    assert "estimated_minutes" in est
    assert "congestion_impact" in est

    minutes = [e["estimated_minutes"] for e in data["estimates"]]
    assert minutes == sorted(minutes)



def test_freight_windows_no_auth_returns_401(client):
    response = client.get("/freight/windows?city=Riyadh&zone=Zone_1")
    assert response.status_code == 401


def test_freight_windows_returns_valid_structure(client):
    response = client.get(
        "/freight/windows?city=Riyadh&zone=Zone_1",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "city"                 in data
    assert "zone"                 in data
    assert "recommended_windows"  in data
    assert "avoid_hours"          in data
    assert "best_hour"            in data
    assert "rationale"            in data
    assert isinstance(data["recommended_windows"], list)
    assert isinstance(data["avoid_hours"], list)

    # Restricted hours must not appear in recommended windows
    from src.config import FREIGHT_RESTRICTED_HOURS
    restricted = set(FREIGHT_RESTRICTED_HOURS.get("Riyadh", {}).get("Zone_1", []))
    overlap    = restricted.intersection(set(data["recommended_windows"]))
    assert len(overlap) == 0, f"Recommended windows contain restricted hours: {overlap}"



def test_history_patterns_no_auth_returns_401(client):
    response = client.get("/history/patterns?city=Riyadh")
    assert response.status_code == 401


def test_history_patterns_returns_valid_structure(client):
    # Seed a prediction first so the log exists
    client.post("/predict", json=VALID_PAYLOAD, headers={"X-API-Key": TEST_KEY})

    response = client.get(
        "/history/patterns?city=Riyadh&days=30",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "city"                in data
    assert "period_days"         in data
    assert "total_records"       in data
    assert "avg_congestion_score" in data
    assert "weather_breakdown"   in data
    assert "hourly_averages"     in data


def test_history_trend_no_auth_returns_401(client):
    response = client.get("/history/trend?city=Riyadh&zone=Zone_1")
    assert response.status_code == 401


def test_history_trend_returns_correct_keys(client):
    client.post("/predict", json=VALID_PAYLOAD, headers={"X-API-Key": TEST_KEY})

    response = client.get(
        "/history/trend?city=Riyadh&zone=Zone_1&days=7",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "city"        in data
    assert "zone"        in data
    assert "period_days" in data
    assert "dates"       in data
    assert "avg_scores"  in data
    assert "trend"       in data
    assert data["trend"] in ("improving", "worsening", "stable")
    assert isinstance(data["dates"],      list)
    assert isinstance(data["avg_scores"], list)


def test_predict_returns_prediction_interval(client):
    """PROMPT 020 — /predict response must include a prediction_interval dict."""
    response = client.post(
        "/predict",
        json=VALID_PAYLOAD,
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "prediction_interval" in data
    pi = data["prediction_interval"]
    assert "lower_bound"       in pi
    assert "upper_bound"       in pi
    assert "confidence_width"  in pi
    assert "confidence_level"  in pi
    assert pi["lower_bound"]   <= pi["upper_bound"]
    assert pi["confidence_level"] == "90%"


def test_alerts_history_no_auth_returns_401(client):
    response = client.get("/alerts/history?city=Riyadh&hours=24")
    assert response.status_code == 401


def test_alerts_history_returns_valid_structure(client):
    response = client.get(
        "/alerts/history?city=Riyadh&hours=24",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "city"         in data
    assert "hours"        in data
    assert "total_alerts" in data
    assert "alerts"       in data
    assert isinstance(data["alerts"], list)
    assert data["total_alerts"] == len(data["alerts"])


def test_check_thresholds_returns_list(client):
    """check_thresholds() always returns a list — empty or populated."""
    from src.pipeline import check_thresholds
    from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features

    df = generate_traffic_data(city="Riyadh", n_days=7)
    df = apply_hourly_patterns(df, city="Riyadh")
    df = add_lag_features(df)

    result = check_thresholds(df, city="Riyadh")
    assert isinstance(result, list)


def test_no_alerts_when_all_clear():
    """All-low-congestion data produces no alerts."""
    from src.pipeline import check_thresholds
    import pandas as pd
    import numpy as np

    n = 120
    df = pd.DataFrame({
        'city'            : 'Riyadh',
        'zone'            : np.tile(['Zone_1','Zone_2','Zone_3','Zone_4','Zone_5'], n // 5),
        'timestamp'       : pd.date_range('2025-01-01', periods=n, freq='h'),
        'hour'            : np.tile(range(24), n // 24 + 1)[:n],
        'vehicle_count'   : np.full(n, 10.0),
        'avg_speed'       : np.full(n, 90.0),
        'congestion_score': np.full(n, 0.05),
        'weather'         : 'clear',
        'is_weekend'      : 0,
        'rush_hour'       : 0,
    })

    alerts = check_thresholds(df, city="Riyadh")
    assert isinstance(alerts, list)
    congestion_alerts = [a for a in alerts if a['metric'] == 'congestion_score']
    assert len(congestion_alerts) == 0