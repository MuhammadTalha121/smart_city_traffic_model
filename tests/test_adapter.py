# tests/test_adapters.py (extend)
from src.adapters import RealSensorAdapter, MockIoTAdapter
import pandas as pd
import pytest

def test_real_sensor_adapter_falls_back_to_mock_when_endpoint_empty(monkeypatch):
    monkeypatch.setattr("src.adapters.REAL_SENSOR_ENDPOINTS", {"Riyadh": ""})
    adapter = RealSensorAdapter()
    df = adapter.fetch("Riyadh")
    # Should return mock data, not raise
    assert isinstance(df, pd.DataFrame)
    assert "vehicle_count" in df.columns
    assert len(df) == 5  # 5 zones

def test_real_sensor_adapter_validates_payload_before_returning(monkeypatch):
    # Mock requests.get to return a valid payload
    import requests
    class MockResponse:
        def json(self):
            return [{
                "timestamp": "2026-07-01T12:00:00Z",
                "zone_id": "Zone_1",
                "vehicle_count": 150,
                "avg_speed": 45.5,
                "weather": "clear",
                "road_type": "arterial",
            }]
        def raise_for_status(self):
            pass
    monkeypatch.setattr(requests, "get", lambda url, timeout: MockResponse())
    monkeypatch.setattr("src.adapters.REAL_SENSOR_ENDPOINTS", {"Riyadh": "http://fake.endpoint"})
    adapter = RealSensorAdapter()
    df = adapter.fetch("Riyadh")
    assert len(df) == 1
    assert df.iloc[0]["zone"] == "Zone_1"
    assert df.iloc[0]["vehicle_count"] == 150

def test_invalid_real_sensor_payload_returns_fallback_not_exception(monkeypatch):
    import requests
    # Invalid payload: missing avg_speed
    class MockResponse:
        def json(self):
            return [{
                "timestamp": "2026-07-01T12:00:00Z",
                "zone_id": "Zone_1",
                "vehicle_count": 150,
                # avg_speed missing
            }]
        def raise_for_status(self):
            pass
    monkeypatch.setattr(requests, "get", lambda url, timeout: MockResponse())
    monkeypatch.setattr("src.adapters.REAL_SENSOR_ENDPOINTS", {"Riyadh": "http://fake.endpoint"})
    # Also need to patch MockIoTAdapter to return a predictable DataFrame
    from src.adapters import MockIoTAdapter
    original_fetch = MockIoTAdapter.fetch
    def mock_fetch(self, city):
        return pd.DataFrame([{"vehicle_count": 100, "avg_speed": 50, "zone": "Zone_1"}])
    monkeypatch.setattr(MockIoTAdapter, "fetch", mock_fetch)
    adapter = RealSensorAdapter()
    df = adapter.fetch("Riyadh")
    # Should fall back to mock
    assert df.iloc[0]["vehicle_count"] == 100