import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")
TEST_KEY = os.environ["API_KEY"]

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app import app
from src.construction import get_active_school_restrictions
from src.model import compute_vsl_limit


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_school_restriction_active_during_arrival_window():
    """A weekday at 07:10 must trigger the arrival-window restriction for Zone_3."""
    monday_7am = datetime(2026, 10, 5, 7, 10, 0)
    active = get_active_school_restrictions(timestamp=monday_7am, city="Riyadh")
    assert len(active) >= 1
    zones = {s["zone"] for s in active}
    assert "Zone_3" in zones
    for s in active:
        if s["zone"] == "Zone_3":
            assert s["active_window"] == "arrival"
            assert s["speed_limit_kmph"] == 30
            assert s["heavy_vehicle_restricted"] is True


def test_school_restriction_inactive_off_hours():
    """Weekday at 10:00 is outside any school window — no restrictions."""
    monday_mid_morning = datetime(2026, 10, 5, 10, 0, 0)
    active = get_active_school_restrictions(timestamp=monday_mid_morning, city="Riyadh")
    assert active == []


def test_school_restriction_inactive_on_friday():
    """Friday must have no school restrictions, even during window hours."""
    friday_7am = datetime(2026, 10, 9, 7, 10, 0)
    active = get_active_school_restrictions(timestamp=friday_7am, city="Riyadh")
    assert active == []


def test_vsl_school_zone_caps_speed():
    """compute_vsl_limit with school_zone=True must cap speed to 30 km/h."""
    result = compute_vsl_limit(
        weather="clear",
        visibility_m=10000,
        avg_speed_kmph=80,
        school_zone=True,
    )
    assert result["recommended_speed_kmph"] == 30
    assert result["school_zone_active"] is True
    assert "School zone" in result["reduction_reason"]


def test_vsl_without_school_zone_unaffected():
    """Without school_zone, VSL must return the normal limit for clear weather."""
    result = compute_vsl_limit(
        weather="clear",
        visibility_m=10000,
        avg_speed_kmph=80,
    )
    assert result["recommended_speed_kmph"] == 120
    assert result["school_zone_active"] is False


def test_school_zones_endpoint_returns_all(client):
    response = client.get(
        "/safety/school-zones",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for z in data["zones"]:
        assert "zone" in z
        assert "name" in z
        assert "speed_limit_kmph" in z
        assert "active" in z