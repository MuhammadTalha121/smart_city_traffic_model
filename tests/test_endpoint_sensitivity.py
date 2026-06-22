import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture(scope="module")
def admin_key(client):
    import os
    key = os.getenv("API_KEY", "test-admin-key")
    return key

@pytest.fixture(scope="module")
def readonly_key(client, admin_key):
    response = client.post(
        "/auth/keys",
        params={"role": "READ_ONLY", "city_scope": "*"},
        headers={"X-API-Key": admin_key}
    )
    assert response.status_code == 200, f"Failed to create READ_ONLY key: {response.text}"
    key = response.json()["api_key"]
    resp = client.get("/schedule/active", headers={"X-API-Key": key})
    assert resp.status_code == 200, f"READ_ONLY key is invalid: {resp.text}"
    return key

@pytest.fixture(scope="module")
def operator_key(client, admin_key):
    response = client.post(
        "/auth/keys",
        params={"role": "OPERATOR", "city_scope": "*"},
        headers={"X-API-Key": admin_key}
    )
    assert response.status_code == 200, f"Failed to create OPERATOR key: {response.text}"
    key = response.json()["api_key"]
    resp = client.get("/schedule/active", headers={"X-API-Key": key})
    assert resp.status_code == 200, f"OPERATOR key is invalid: {resp.text}"
    return key

OPERATOR_ENDPOINTS = [
    ("/anomalies", "GET", {"city": "Riyadh"}),
    ("/interventions/active", "GET", {"city": "Riyadh"}),
    ("/safety/hotspots", "GET", {"city": "Riyadh"}),
    ("/signals/recommended", "GET", {"city": "Riyadh"}),
    ("/emergency/response-time", "GET", {"target_zone": "Zone_1", "city": "Riyadh"}),
    ("/alerts/history", "GET", {"city": "Riyadh"}),
    ("/vsl/active-limits", "GET", {"city": "Riyadh"}),
    ("/safety/pedestrian", "GET", {"city": "Riyadh"}),
    ("/data/quality", "GET", {"city": "Riyadh"}),
    ("/signals/tsp-actuation", "POST", {"zone": "Zone_1", "bus_distance_m": 200, "current_green_remaining_s": 30, "passenger_count": 10}),
    ("/federated/params", "GET", {}),
    ("/federated/aggregate", "POST", {
        "city_params": [
            {
                "city": "Riyadh",
                "weights": [1, 2, 3],
                "training_r2": 0.85,
                "best_params": {
                    "n_estimators": 200,
                    "max_depth": 6,
                    "learning_rate": 0.1,
                    "subsample": 0.8,
                    "reg_alpha": 0.1,
                    "reg_lambda": 1.0
                }
            },
            {
                "city": "NEOM",
                "weights": [0.5, 1, 1.5],
                "training_r2": 0.78,
                "best_params": {
                    "n_estimators": 150,
                    "max_depth": 5,
                    "learning_rate": 0.15,
                    "subsample": 0.9,
                    "reg_alpha": 0.05,
                    "reg_lambda": 0.8
                }
            }
        ]
    }),
    ("/ids/alerts", "GET", {"city": "Riyadh"}),
    ("/vms/active-boards", "GET", {"city": "Riyadh"}),
    ("/citations/violations", "GET", {"limit": 5}),
    ("/edge/cabinet-status", "GET", {"city": "Riyadh"}),
    ("/freight/validate", "POST", {
        "zone": "Zone_1",
        "hour": 10,
        "vehicle_weight_tonnes": 5.0,
        "is_weekend": 0,
        "vehicle_id_hash": "abc12345"
    }),
    ("/citations/freight-infractions", "GET", {"limit": 5}),
    ("/transit/drt-status", "GET", {"city": "Riyadh"}),
]

@pytest.mark.parametrize("endpoint,method,params", OPERATOR_ENDPOINTS)
def test_operator_endpoints_reject_readonly(client, readonly_key, endpoint, method, params):
    if method == "GET":
        response = client.get(endpoint, params=params, headers={"X-API-Key": readonly_key})
    else:
        response = client.post(endpoint, json=params, headers={"X-API-Key": readonly_key})
    assert response.status_code == 403, f"{method} {endpoint} should return 403 for READ_ONLY, got {response.status_code}"

@pytest.mark.parametrize("endpoint,method,params", OPERATOR_ENDPOINTS)
def test_operator_endpoints_allow_operator(client, operator_key, endpoint, method, params):
    if method == "GET":
        response = client.get(endpoint, params=params, headers={"X-API-Key": operator_key})
    else:
        response = client.post(endpoint, json=params, headers={"X-API-Key": operator_key})
    assert response.status_code != 403, f"{method} {endpoint} should not be forbidden for OPERATOR, got {response.status_code}"

def test_websocket_requires_operator(client, readonly_key):
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect(f"/ws/live/Riyadh?api_key={readonly_key}"):
            pass
    assert excinfo.value.code == 1008, f"Expected close code 1008, got {excinfo.value.code}"

def test_websocket_allows_operator(client, operator_key):
    with client.websocket_connect(f"/ws/live/Riyadh?api_key={operator_key}") as websocket:
        data = websocket.receive_json()
        assert "zones" in data
        assert "city" in data