import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")
TEST_KEY = os.environ["API_KEY"]

import pytest
from fastapi.testclient import TestClient
from app import app
from src.ab_testing import start_ab_test, evaluate_ab_test, _load_tests, _save_tests


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_ab_tests(tmp_path, monkeypatch):
    """Isolate tests to a temp ab_tests.json."""
    monkeypatch.chdir(tmp_path)
    yield


def test_ab_test_assigns_zones_correctly(client):
    payload = {
        "name": "Test 1",
        "strategy_a": "current",
        "strategy_b": "optimised",
        "zones_a": ["Zone_1", "Zone_2"],
        "zones_b": ["Zone_3", "Zone_4"],
        "duration_hours": 12,
    }
    response = client.post(
        "/experiments/signal-ab/start",
        json=payload,
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "created"
    test_id = data["test_id"]

    # List tests and confirm zone assignment
    list_resp = client.get(
        "/experiments/signal-ab",
        headers={"X-API-Key": TEST_KEY},
    )
    assert list_resp.status_code == 200
    tests = list_resp.json()["tests"]
    found = [t for t in tests if t["test_id"] == test_id]
    assert len(found) == 1
    t = found[0]
    assert t["zones_a"] == ["Zone_1", "Zone_2"]
    assert t["zones_b"] == ["Zone_3", "Zone_4"]


def test_ab_evaluation_returns_winner_with_evidence(client):
    # Start a test
    payload = {
        "name": "Test 2",
        "strategy_a": "current",
        "strategy_b": "optimised",
        "zones_a": ["Zone_1"],
        "zones_b": ["Zone_3"],
        "duration_hours": 1,
    }
    create = client.post(
        "/experiments/signal-ab/start",
        json=payload,
        headers={"X-API-Key": TEST_KEY},
    )
    assert create.status_code == 200
    test_id = create.json()["test_id"]

    # Evaluate using the live city data from app
    resp = client.get(
        f"/experiments/signal-ab/{test_id}/results?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "metrics_a" in data
    assert "metrics_b" in data
    assert "winner" in data
    assert data["winner"] in ("A", "B", "tie", None)
    assert "rationale" in data
    assert isinstance(data["rationale"], str)
    assert len(data["rationale"]) > 0