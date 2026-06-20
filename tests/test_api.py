import os
import pytest
from fastapi.testclient import TestClient




if not os.environ.get("API_KEY"):
    os.environ["API_KEY"] = "test-key-for-pytest-only"

TEST_KEY = os.environ.get("TEST_API_KEY", "test-key-for-pytest-only")

TEST_KEY = os.environ["API_KEY"]

from app import app
from src.config import CONGESTION_THRESHOLDS


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



def test_roads_service_level_no_auth_returns_401(client):
    response = client.get("/roads/service-level?city=Riyadh")
    assert response.status_code == 401


def test_roads_service_level_returns_all_zones(client):
    response = client.get(
        "/roads/service-level?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "city"  in data
    assert "zones" in data
    assert len(data["zones"]) == 5

    for z in data["zones"]:
        assert "zone"              in z
        assert "sdi"               in z
        assert "level_of_service"  in z
        assert "free_flow_speed"   in z
        assert "current_speed"     in z
        assert "speed_loss_kmph"   in z
        assert z["level_of_service"] in ('A', 'B', 'C', 'D', 'E', 'F')
        assert 0.0 <= z["sdi"] <= 1.0

    # Sorted by SDI descending
    sdis = [z["sdi"] for z in data["zones"]]
    assert sdis == sorted(sdis, reverse=True)



def test_safety_pedestrian_no_auth_returns_401(client):
    response = client.get("/safety/pedestrian?city=Riyadh")
    assert response.status_code == 401


def test_safety_pedestrian_returns_ranked_zones(client):
    response = client.get(
        "/safety/pedestrian?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "city"  in data
    assert "zones" in data
    assert len(data["zones"]) == 5

    for z in data["zones"]:
        assert "zone"                   in z
        assert "pedestrian_risk_score"  in z
        assert "risk_category"          in z
        assert "primary_hazard"         in z
        assert "intervention_required"  in z
        assert z["risk_category"] in ('Safe', 'Moderate', 'Dangerous', 'Critical')
        assert 0.0 <= z["pedestrian_risk_score"] <= 1.0

    scores = [z["pedestrian_risk_score"] for z in data["zones"]]
    assert scores == sorted(scores, reverse=True)


def test_usage_log_created_after_request(client):
    """After any authenticated request, usage_log.csv must exist."""
    import os
    client.get("/health")
    client.post("/predict", json=VALID_PAYLOAD, headers={"X-API-Key": TEST_KEY})
    assert os.path.exists("usage_log.csv")


def test_analytics_usage_no_auth_returns_401(client):
    response = client.get("/analytics/usage?days=30")
    assert response.status_code == 401


def test_analytics_usage_returns_valid_structure(client):
    client.post("/predict", json=VALID_PAYLOAD, headers={"X-API-Key": TEST_KEY})

    response = client.get(
        "/analytics/usage?days=30",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "period_days"          in data
    assert "total_calls"          in data
    assert "calls_by_endpoint"    in data
    assert "calls_by_day"         in data
    assert "avg_response_time_ms" in data
    assert "top_endpoint"         in data
    assert data["total_calls"]    >= 0


def test_analytics_quota_returns_valid_structure(client):
    response = client.get(
        "/analytics/quota",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "date"           in data
    assert "calls_today"    in data
    assert "daily_limit"    in data
    assert "pct_used"       in data
    assert "quota_warning"  in data
    assert "quota_exceeded" in data
    assert data["daily_limit"] == 10000
    assert isinstance(data["quota_warning"],  bool)
    assert isinstance(data["quota_exceeded"], bool)



def test_websocket_rejects_invalid_key(client):
    """WebSocket must close with 1008 on invalid or missing API key."""
    with pytest.raises(Exception):
        # fastapi TestClient raises on abnormal WebSocket close
        with client.websocket_connect("/ws/live/Riyadh?api_key=totally-wrong-key") as ws:
            ws.receive_json()



def test_out_of_range_vehicle_count_returns_422(client):
    """PROMPT 028 — vehicle_count > 500 must be rejected."""
    bad_payload = {**VALID_PAYLOAD, "vehicle_count": 9999}
    response = client.post("/predict", json=bad_payload, headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 422


def test_invalid_weather_returns_422(client):
    """PROMPT 028 — unknown weather condition must be rejected."""
    bad_payload = {**VALID_PAYLOAD, "weather": "tornado"}
    response = client.post("/predict", json=bad_payload, headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 422


def test_valid_input_includes_no_warnings(client):
    """PROMPT 028 — clean input must produce empty input_warnings list."""
    response = client.post("/predict", json=VALID_PAYLOAD, headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 200
    assert response.json().get("input_warnings", []) == []




def test_sla_report_returns_valid_structure(client):
    """PROMPT 029 — /sla/report must return expected SLA keys."""
    response = client.get("/sla/report?days=30", headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 200
    data = response.json()
    assert "uptime_pct"      in data
    assert "sla_uptime_met"  in data
    assert "avg_response_ms" in data
    assert "met_all_slas"    in data
    assert "total_requests"  in data


def test_sla_current_is_public(client):
    """PROMPT 029 — /sla/current must be accessible without authentication."""
    response = client.get("/sla/current")
    assert response.status_code == 200
    assert "uptime_pct" in response.json()


def test_last_mile_endpoint_returns_zones(client):
    response = client.get(
        "/mobility/last-mile?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "zones" in data
    assert len(data["zones"]) == 5
    for z in data["zones"]:
        assert "last_mile_index"  in z
        assert "active_scooters"  in z
        assert "interpretation"   in z




def test_v2x_cooperative_route_returns_valid_path(client):
    response = client.post(
        "/v2x/cooperative-route",
        json={"city": "Riyadh", "origin_zone": "Zone_1",
              "destination_zone": "Zone_4", "penetration_rate": 0.30},
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["route"][0]  == "Zone_1"
    assert data["route"][-1] == "Zone_4"
    assert "improvement_pct" in data





# ======  – Green Wave API endpoint tests (corrected) ======

def test_green_wave_endpoint_returns_200(client):
    """Valid route returns green wave schedule."""
    payload = {
        "city": "Riyadh",
        "route": ["Zone_1", "Zone_2"],
        "vehicle_speed_kmph": 60.0,
        "priority_level": "emergency"
    }
    response = client.post(
        "/control/green-wave",
        json=payload,
        headers={"X-API-Key": TEST_KEY}   # <-- added
    )
    assert response.status_code == 200
    data = response.json()
    assert "phase_schedule" in data
    assert len(data["phase_schedule"]) == 2
    assert data["stops_avoided"] == 1
    assert data["city"] == "Riyadh"
    assert data["priority_level"] == "emergency"


def test_green_wave_invalid_route_returns_400(client):
    """Non‑adjacent zones must return HTTP 400 with a clear error."""
    payload = {
        "city": "Riyadh",
        "route": ["Zone_1", "Zone_4"],   # not adjacent
        "vehicle_speed_kmph": 60.0,
        "priority_level": "emergency"
    }
    response = client.post(
        "/control/green-wave",
        json=payload,
        headers={"X-API-Key": TEST_KEY}   # <-- added
    )
    assert response.status_code == 400
    assert "Non-adjacent" in response.text or "discontinuity" in response.text.lower()


def test_green_wave_missing_route_returns_422(client):
    """Missing 'route' field should trigger Pydantic validation error."""
    payload = {
        "city": "Riyadh",
        "vehicle_speed_kmph": 60.0,
        "priority_level": "emergency"
    }
    response = client.post(
        "/control/green-wave",
        json=payload,
        headers={"X-API-Key": TEST_KEY}   # <-- added
    )
    assert response.status_code == 422   # validation error



# ===== – Crosswalk timing API tests =====

def test_crosswalk_timing_endpoint_returns_200(client):
    """Valid request returns crosswalk timing for all zones."""
    response = client.get(
        "/pedestrian/crosswalk-timing?city=Riyadh&schedule=standard",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "zones" in data
    assert isinstance(data["zones"], dict)
    # Check that at least one zone has the required keys
    for zone, timing in data["zones"].items():
        assert "walk_time_s" in timing
        assert "mutcd_compliant" in timing
        assert 7 <= timing["walk_time_s"] <= 35

def test_crosswalk_timing_no_auth_returns_401(client):
    """Missing API key must return 401."""
    response = client.get("/pedestrian/crosswalk-timing?city=Riyadh")
    assert response.status_code == 401




# =====  – Heat Risk API tests =====

def test_heat_risk_endpoint_returns_200(client):
    """Valid city returns thermal risk for all zones."""
    response = client.get(
        "/infrastructure/heat-risk?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "zones" in data
    assert "air_temp_celsius" in data
    for zone, risk in data["zones"].items():
        assert "surface_temp_celsius" in risk
        assert "maintenance_alert" in risk
        assert isinstance(risk["maintenance_alert"], bool)

def test_heat_risk_no_auth_returns_401(client):
    """Missing API key must return 401."""
    response = client.get("/infrastructure/heat-risk?city=Riyadh")
    assert response.status_code == 401





# ===== – Heat Risk API tests =====

def test_heat_risk_endpoint_returns_200(client):
    """Valid city returns thermal risk for all zones."""
    response = client.get(
        "/infrastructure/heat-risk?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "zones" in data
    assert "air_temp_celsius" in data
    for zone, risk in data["zones"].items():
        assert "surface_temp_celsius" in risk
        assert "maintenance_alert" in risk
        assert isinstance(risk["maintenance_alert"], bool)

def test_heat_risk_no_auth_returns_401(client):
    """Missing API key must return 401."""
    response = client.get("/infrastructure/heat-risk?city=Riyadh")
    assert response.status_code == 401




# =====  – Mass Event Egress API tests =====

def test_egress_plan_endpoint_returns_200(client):
    """GET /events/egress-plan returns a valid egress plan."""
    response = client.get(
        "/events/egress-plan?venue_id=Boulevard_World&total_vehicles=5000",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data['venue_id'] == 'Boulevard_World'
    assert data['total_vehicles'] == 5000
    assert 'recommended_window_mins' in data
    assert data['status'] == 'OK - Staged egress plan generated.'

def test_active_surge_endpoint_returns_200(client):
    """POST /events/active-surge returns an egress plan."""
    payload = {
        "venue_id": "King_Fahd_Stadium",
        "total_vehicles": 8000,
        "current_highway_load_pct": 0.3,
    }
    response = client.post(
        "/events/active-surge",
        json=payload,
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data['venue_id'] == 'King_Fahd_Stadium'
    assert data['total_vehicles'] == 8000
    assert data['recommended_window_mins'] is not None

def test_egress_plan_invalid_venue_returns_400(client):
    """Invalid venue_id should return 400."""
    response = client.get(
        "/events/egress-plan?venue_id=InvalidVenue&total_vehicles=100",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 400
    assert "Unknown venue_id" in response.text




# =====  – VMS API tests =====

def test_vms_active_boards_endpoint_returns_200(client):
    """GET /vms/active-boards returns VMS content for all zones."""
    response = client.get(
        "/vms/active-boards?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "boards" in data
    assert "total_boards" in data
    assert "all_zones_low" in data
    for board in data["boards"]:
        assert "zone" in board
        assert "vms" in board
        assert "lines" in board["vms"]
        assert "compliant" in board["vms"]

def test_vms_active_boards_no_auth_returns_401(client):
    """Missing API key must return 401."""
    response = client.get("/vms/active-boards?city=Riyadh")
    assert response.status_code == 401

def test_vms_only_shows_non_low_messages(client):
    """When at least one zone is not Low, Low zones are filtered out."""
    response = client.get(
        "/vms/active-boards?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    if not data["all_zones_low"]:
        for board in data["boards"]:
            assert board["congestion_level"] != "Low"






# ===== – RBAC tests =====
from src.auth import create_key, validate_key

def test_read_only_key_blocked_from_pipeline_trigger(client):
    """READ_ONLY key should get 403 on /pipeline/trigger."""
    # Create a READ_ONLY key
    ro_key = create_key('READ_ONLY', 'all')
    response = client.post(
        "/pipeline/trigger",
        headers={"X-API-Key": ro_key},
    )
    assert response.status_code == 403
    assert "not allowed" in response.text

def test_admin_key_accesses_all_endpoints(client):
    """ADMIN key should access /pipeline/trigger."""
    admin_key = create_key('ADMIN', 'all')
    response = client.post(
        "/pipeline/trigger",
        headers={"X-API-Key": admin_key},
    )
    assert response.status_code == 200



def test_expired_key_returns_401(client):
    """Non-existent or invalid key returns 401."""
    response = client.get(
        "/anomalies?city=Riyadh",
        headers={"X-API-Key": "invalid_key"},
    )
    assert response.status_code == 401





# ===== Ledger API tests =====

def test_verify_ledger_returns_valid(client):
    """The /citations/verify-ledger endpoint returns a valid report for an OPERATOR/ADMIN."""
    response = client.get("/citations/verify-ledger", headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 200
    data = response.json()
    # It should be valid (empty or not)
    assert "valid" in data
    assert "total_blocks" in data
    assert "first_invalid_block" in data


def test_violations_endpoint_returns_list(client):
    """The /citations/violations endpoint returns a list of violations, optionally filtered."""
    response = client.get("/citations/violations", headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 200
    data = response.json()
    assert "violations" in data
    assert isinstance(data["violations"], list)

    # Test zone filter
    response = client.get("/citations/violations?zone=Zone_1", headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 200
    data = response.json()
    assert all(v["zone"] == "Zone_1" for v in data["violations"])





# =====  Parking API tests =====

def test_parking_occupancy_forecast_returns_garages(client):
    """GET /parking/occupancy-forecast returns a list of garages with forecasts."""
    response = client.get(
        "/parking/occupancy-forecast?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "city" in data
    assert "garages" in data
    assert isinstance(data["garages"], list)
    # Should have at least the configured garages
    from src.config import PARKING_HUBS
    assert len(data["garages"]) == len(PARKING_HUBS)
    for g in data["garages"]:
        assert "garage_id" in g
        assert "forecast_1h" in g
        assert "forecast_2h" in g
        assert "forecast_3h" in g
        assert "current_fill_rate" in g
        assert "status" in g
        assert 0.0 <= g["forecast_1h"] <= 1.0


def test_parking_routing_recommendation_returns_garage(client):
    """GET /parking/routing-recommendation returns the best garage for a zone."""
    response = client.get(
        "/parking/routing-recommendation?zone=Zone_1&city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "recommended_garage" in data
    assert "garage_zone" in data
    assert "current_fill_rate" in data
    assert "available_capacity" in data
    # The recommended garage should be in Zone_1 (since there are garages there)
    from src.config import PARKING_HUBS
    # Zone_1 garages: Gar_Olaya, so we expect that one
    assert data["recommended_garage"] == "Gar_Olaya"








# ===== Edge Simulation API tests =====

def test_edge_cabinet_status_returns_list(client):
    """GET /edge/cabinet-status returns status for all cabinets."""
    response = client.get(
        "/edge/cabinet-status?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "cabinets" in data
    assert isinstance(data["cabinets"], list)
    # Should have at least 5 zones
    assert len(data["cabinets"]) >= 5
    for c in data["cabinets"]:
        assert "zone_id" in c
        assert "online" in c
        assert "mode" in c
        assert "local_queue_len" in c


def test_edge_simulation_go_offline_returns_failover_plan(client):
    """POST /edge/simulation with go_offline returns a failover plan."""
    response = client.post(
        "/edge/simulation",
        json={"action": "go_offline", "zone_id": "Zone_1"},
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "go_offline"
    assert "result" in data
    result = data["result"]
    assert result["online"] is False
    assert "failover_plan" in result
    assert "main_green_s" in result["failover_plan"]

    # Also test restore
    response = client.post(
        "/edge/simulation",
        json={"action": "restore", "zone_id": "Zone_1"},
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["online"] is True


def test_edge_p2p_coordination_adjusts_for_neighbor_queue(client):
    """When a neighbor queue is high, p2p coordination adjusts phases."""
    # First set a neighbor queue
    response = client.post(
        "/edge/simulation",
        json={
            "action": "status",
            "zone_id": "Zone_1",
            "neighbor_queues": {"Zone_2": 60}
        },
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "p2p_coordination" in data
    p2p = data["p2p_coordination"]
    # The main green should be reduced (default 40, reduced to 30)
    assert p2p["adjusted_phases"]["main_green_s"] == 30




# =====  HPO API tests =====

def test_hpo_history_endpoint_returns_list(client):
    """GET /pipeline/hpo-history should return a list of HPO runs (admin only)."""
    # It may be empty if no HPO run, but should return 200 and proper structure.
    response = client.get(
        "/pipeline/hpo-history",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "hpo_runs" in data
    assert "total" in data
    assert isinstance(data["hpo_runs"], list)





# ===== Pareto routing API tests =====

def test_pareto_recommendations_returns_routes(client):
    """POST /routing/pareto-recommendations returns top routes with scores."""
    payload = {
        "city": "Riyadh",
        "origin_zone": "Zone_1",
        "destination_zone": "Zone_4",
        "time_weight": 0.5,
        "emission_weight": 0.3,
        "cost_weight": 0.2,
    }
    response = client.post(
        "/routing/pareto-recommendations",
        json=payload,
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "routes" in data
    assert isinstance(data["routes"], list)
    assert len(data["routes"]) >= 1
    assert "recommended_for" in data
    assert "fastest" in data["recommended_for"]
    assert "cleanest" in data["recommended_for"]
    assert "cheapest" in data["recommended_for"]
    for r in data["routes"]:
        assert "route" in r
        assert "utility" in r
        assert isinstance(r["route"], list)






# ===== Air quality API tests =====

def test_air_quality_endpoint_returns_zones(client):
    """GET /environment/air-quality returns AQI estimates for all zones."""
    response = client.get(
        "/environment/air-quality?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert "zones" in data
    assert "wind_speed_kmh" in data
    assert "weather" in data
    assert isinstance(data["zones"], list)
    for z in data["zones"]:
        assert "zone" in z
        assert "pm25_concentration" in z
        assert "aqi_category" in z
        assert "who_guideline_exceeded" in z
        assert z["aqi_category"] in ('Good', 'Moderate', 'Unhealthy', 'Hazardous')


    


# =====  Freight geofencing API tests =====

def test_freight_validate_compliant_returns_200(client):
    """POST /freight/validate returns compliant status for valid entry."""
    payload = {
        "zone": "Zone_1",
        "hour": 22,
        "vehicle_weight_tonnes": 4.0,
        "is_weekend": 0,
        "vehicle_id_hash": "abc12345"
    }
    response = client.post(
        "/freight/validate",
        json=payload,
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Compliant"





# ===== Evacuation Routing =====

def test_evacuation_requires_operator_role(client):
    """READ_ONLY key should get 403 on /emergency/evacuate."""
    from src.auth import create_key
    ro_key = create_key('READ_ONLY', 'all')
    payload = {
        "city": "Riyadh",
        "hazard_zones": ["Zone_1", "Zone_3"],
        "total_vehicles": 4000
    }
    response = client.post(
        "/emergency/evacuate",
        json=payload,
        headers={"X-API-Key": ro_key},
    )
    assert response.status_code == 403
    assert "not allowed" in response.text


def test_evacuation_returns_valid_plan(client):
    """Valid request should return a complete evacuation plan."""
    payload = {
        "city": "Riyadh",
        "hazard_zones": ["Zone_1", "Zone_3"],
        "total_vehicles": 4000
    }
    response = client.post(
        "/emergency/evacuate",
        json=payload,
        headers={"X-API-Key": TEST_KEY},  # ADMIN key
    )
    assert response.status_code == 200
    data = response.json()
    assert "hazard_zones" in data
    assert "total_vehicles" in data
    assert "evacuation_plan" in data
    assert "recommended_departure_order" in data
    assert "city" in data
    assert data["city"] == "Riyadh"
    assert len(data["evacuation_plan"]) == 2  # two safe points
    for plan in data["evacuation_plan"]:
        assert "safe_point" in plan
        assert "route" in plan
        assert "allocated_vehicles" in plan
        assert "estimated_clearance_mins" in plan
        assert "corridor_overloaded" in plan
        assert isinstance(plan["route"], list)
        assert plan["route"][0] in ["Zone_1", "Zone_3"]
        assert plan["route"][-1] in ["Zone_4", "Zone_5"]
    # Allocations should sum to 4000
    total_alloc = sum(p["allocated_vehicles"] for p in data["evacuation_plan"])
    assert total_alloc == 4000