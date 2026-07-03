# tests/test_sensor_registry.py
import pytest
from src.sensor_registry import validate_sensor_payload, register_sensor, list_registered_sensors

def test_valid_sensor_payload_passes_schema():
    payload = {
        "timestamp": "2026-07-01T12:00:00Z",
        "zone_id": "Zone_1",
        "vehicle_count": 150,
        "avg_speed": 45.5,
        "weather": "clear",
        "road_type": "arterial",
    }
    result = validate_sensor_payload(payload)
    assert result["valid"] is True
    assert result["errors"] == []
    assert result["schema_version"] == "1.0"

def test_missing_required_field_fails_validation():
    payload = {
        "timestamp": "2026-07-01T12:00:00Z",
        "zone_id": "Zone_1",
        "vehicle_count": 150,
        # missing avg_speed
    }
    result = validate_sensor_payload(payload)
    assert result["valid"] is False
    assert "Missing required field: avg_speed" in result["errors"]

def test_sensor_registration_persists_to_registry_file(tmp_path, monkeypatch):
    monkeypatch.setattr("src.sensor_registry.REGISTRY_PATH", str(tmp_path / "registry.json"))
    result = register_sensor("sensor_001", "Zone_1", "Acme")
    assert result["sensor_id"] == "sensor_001"
    assert result["registered_at"] is not None
    sensors = list_registered_sensors()
    assert len(sensors) == 1
    assert sensors[0]["zone"] == "Zone_1"