"""IoT Sensor Schema Registry – validates and registers sensor data sources."""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

SENSOR_SCHEMA_V1 = {
    "required_fields": ["timestamp", "zone_id", "vehicle_count", "avg_speed"],
    "optional_fields": ["weather", "road_type", "lane_count"],
    "types": {
        "timestamp": str,
        "zone_id": str,
        "vehicle_count": int,
        "avg_speed": float,
        "weather": str,
        "road_type": str,
        "lane_count": int,
    },
    "ranges": {
        "vehicle_count": [0, 500],
        "avg_speed": [0, 200],
        "lane_count": [1, 6],
    },
    "timestamp_format": "ISO8601",
    "version": "1.0",
}

REGISTRY_PATH = "sensor_registry.json"


def validate_sensor_payload(payload: dict) -> dict:
    """
    Validates incoming sensor data against SENSOR_SCHEMA_V1.

    Returns:
        valid (bool), errors (list), warnings (list), schema_version (str).
    """
    errors = []
    warnings = []
    schema = SENSOR_SCHEMA_V1

    # Check required fields
    for field in schema["required_fields"]:
        if field not in payload:
            errors.append(f"Missing required field: {field}")

    # Check types and ranges for present fields
    for field, value in payload.items():
        if field in schema["types"]:
            expected_type = schema["types"][field]
            if not isinstance(value, expected_type):
                errors.append(f"Field '{field}' should be {expected_type.__name__}, got {type(value).__name__}")
            if field in schema["ranges"]:
                min_val, max_val = schema["ranges"][field]
                if not (min_val <= value <= max_val):
                    errors.append(f"Field '{field}' value {value} outside allowed range [{min_val}, {max_val}]")

    # Warn about unknown fields
    known_fields = set(schema["required_fields"]) | set(schema["optional_fields"])
    for field in payload.keys():
        if field not in known_fields:
            warnings.append(f"Unknown field '{field}' – will be ignored")

    # Validate timestamp format (ISO8601)
    if "timestamp" in payload:
        try:
            datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            errors.append("timestamp must be ISO8601 format (e.g., '2026-07-01T12:00:00Z')")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "schema_version": schema["version"],
    }


def register_sensor(sensor_id: str, zone: str, vendor: str, schema_version: str = "1.0") -> dict:
    """
    Registers a sensor in sensor_registry.json.

    Returns:
        sensor_id, registered_at, schema_version.
    """
    registry = _load_registry()
    entry = {
        "sensor_id": sensor_id,
        "zone": zone,
        "vendor": vendor,
        "schema_version": schema_version,
        "registered_at": datetime.now().isoformat(),
    }
    registry[sensor_id] = entry
    _save_registry(registry)
    return {
        "sensor_id": sensor_id,
        "registered_at": entry["registered_at"],
        "schema_version": schema_version,
    }


def list_registered_sensors() -> List[Dict]:
    """Return all registered sensors."""
    registry = _load_registry()
    return list(registry.values())


def get_sensor(sensor_id: str) -> Optional[Dict]:
    """Return a single sensor by ID, or None if not found."""
    registry = _load_registry()
    return registry.get(sensor_id)


def _load_registry() -> Dict:
    if not os.path.exists(REGISTRY_PATH):
        return {}
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_registry(registry: Dict) -> None:
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)