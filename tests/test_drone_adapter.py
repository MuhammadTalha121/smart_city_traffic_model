import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")
TEST_KEY = os.environ["API_KEY"]

import pytest
from fastapi.testclient import TestClient
from app import app
from src.adapters import DroneMonitoringAdapter, BaseAdapter, get_adapter
from src.model import fuse_sensor_readings


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_drone_adapter_follows_base_abc():
    """DroneMonitoringAdapter must inherit from BaseAdapter."""
    adapter = DroneMonitoringAdapter()
    assert isinstance(adapter, BaseAdapter)
    assert hasattr(adapter, "fetch") and callable(adapter.fetch)


def test_drone_fetch_returns_all_zones():
    """fetch_all_zones must return one row per zone (5 zones)."""
    adapter = DroneMonitoringAdapter()
    df = adapter.fetch_all_zones("Riyadh")
    assert len(df) == 5
    assert set(df["zone"]) == {"Zone_1", "Zone_2", "Zone_3", "Zone_4", "Zone_5"}


def test_drone_reading_has_required_fields():
    """Each reading must include confidence, altitude, and coverage radius."""
    reading = DroneMonitoringAdapter().fetch_drone_counts("Zone_1", "Riyadh")
    for field in [
        "zone", "city", "vehicle_count", "timestamp",
        "altitude_m", "coverage_radius_m", "confidence", "source",
    ]:
        assert field in reading, f"Missing field: {field}"
    assert 0.0 <= reading["confidence"] <= 1.0
    assert reading["altitude_m"] > 0
    assert reading["coverage_radius_m"] > 0


def test_drone_adapter_merges_with_loop_detector():
    """
    Confidence-weighted fusion of a loop reading and a drone reading
    must produce a value between the two inputs.
    """
    loop = {"source": "loop_detector", "vehicle_count": 240, "confidence": 0.90}
    drone = {"source": "drone_mock", "vehicle_count": 210, "confidence": 0.85}

    fused = fuse_sensor_readings([loop, drone])

    assert fused["sources_used"] == 2
    assert fused["fused_count"] > 210
    assert fused["fused_count"] < 240
    assert fused["total_confidence"] == pytest.approx(1.75, rel=1e-3)


def test_drone_low_confidence_count_downweighted():
    """
    A high-confidence loop reading must dominate a low-confidence drone
    reading in the fusion.
    """
    loop = {"source": "loop_detector", "vehicle_count": 300, "confidence": 0.95}
    drone = {"source": "drone_mock", "vehicle_count": 100, "confidence": 0.20}

    fused = fuse_sensor_readings([loop, drone])

    assert fused["fused_count"] > 270
    assert fused["sources_used"] == 2


def test_drone_sandstorm_confidence_penalised(monkeypatch):
    """
    When weather is sandstorm, drone confidence must drop significantly.
    """
    from src.config import DRONE_MOCK_CONFIDENCE_BASE, DRONE_WEATHER_CONFIDENCE_PENALTY

    class MockWeatherAdapter(BaseAdapter):
        def fetch(self, city="Riyadh"):
            import pandas as pd
            return pd.DataFrame([{"weather": "sandstorm"}])

    import src.adapters as adap_module
    original = adap_module.get_adapter
    monkeypatch.setattr(
        adap_module, "get_adapter",
        lambda s: MockWeatherAdapter() if s == "weather" else original(s),
    )

    reading = DroneMonitoringAdapter().fetch_drone_counts("Zone_1", "Riyadh")
    expected_max = DRONE_MOCK_CONFIDENCE_BASE * DRONE_WEATHER_CONFIDENCE_PENALTY["sandstorm"]
    assert reading["confidence"] <= expected_max + 1e-6


def test_get_adapter_accepts_drone_key():
    """get_adapter('drone') must return a DroneMonitoringAdapter."""
    adapter = get_adapter("drone")
    assert isinstance(adapter, DroneMonitoringAdapter)


def test_drone_status_endpoint(client):
    response = client.get(
        "/sensors/drone-status?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_zones"] == 5
    for r in data["readings"]:
        assert "confidence" in r
        assert "vehicle_count" in r


def test_fused_count_endpoint(client):
    response = client.get(
        "/sensors/fused-count?zone=Zone_1&city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "fused" in data
    assert "fused_count" in data["fused"]
    assert data["fused"]["sources_used"] >= 1