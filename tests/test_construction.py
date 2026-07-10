import pytest
import os
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app import app
from src.construction import (
    add_construction_zone,
    get_active_construction,
    apply_construction_capacity,
    delete_construction_zone,
    _load_construction_zones,
    _save_construction_zones,
    generate_diversion_advisory
)
from src.config import CONSTRUCTION_MIN_CAPACITY_FRACTION, ZONE_ADJACENCY

os.environ.setdefault("API_KEY", "test-key-for-pytest-only")
TEST_KEY = os.environ["API_KEY"]


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_add_construction_zone(tmp_path, monkeypatch):
    monkeypatch.setattr("src.construction.CONSTRUCTION_ZONES_FILE", str(tmp_path / "constructions.json"))
    result = add_construction_zone(
        zone="Zone_1",
        road_name="King Fahd Road",
        start_date="2026-07-10",
        end_date="2026-07-20",
        start_hour=8,
        end_hour=18,
        lanes_closed=1,
        total_lanes=3,
        description="Test roadwork",
    )
    assert "id" in result
    assert result["zone"] == "Zone_1"
    assert result["capacity_multiplier"] == 0.667  # 2/3 lanes open


def test_apply_construction_capacity(tmp_path, monkeypatch):
    monkeypatch.setattr("src.construction.CONSTRUCTION_ZONES_FILE", str(tmp_path / "constructions.json"))
    # Add construction
    add_construction_zone(
        zone="Zone_1",
        road_name="Test Road",
        start_date=(datetime.now().strftime("%Y-%m-%d")),
        end_date=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        start_hour=0,
        end_hour=23,
        lanes_closed=1,
        total_lanes=2,
    )
    # Apply capacity reduction
    reduced = apply_construction_capacity(2200, "Zone_1")
    assert reduced == 1100  # 50% reduction


def test_construction_endpoints(client, tmp_path, monkeypatch):
    monkeypatch.setattr("src.construction.CONSTRUCTION_ZONES_FILE", str(tmp_path / "constructions.json"))

    # Create
    create_resp = client.post(
        "/construction/zones",
        json={
            "zone": "Zone_1",
            "road_name": "Test Road",
            "start_date": "2026-07-10",
            "end_date": "2026-07-20",
            "start_hour": 8,
            "end_hour": 18,
            "lanes_closed": 1,
            "total_lanes": 3,
            "description": "Test",
        },
        headers={"X-API-Key": TEST_KEY},
    )
    assert create_resp.status_code == 200
    data = create_resp.json()
    zone_id = data["construction"]["id"]

    # List
    list_resp = client.get(
        "/construction/zones",
        headers={"X-API-Key": TEST_KEY},
    )
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # Delete
    delete_resp = client.delete(
        f"/construction/zones/{zone_id}",
        headers={"X-API-Key": TEST_KEY},
    )
    assert delete_resp.status_code == 200






def test_diversion_advisory_avoids_construction_zone(tmp_path, monkeypatch):
    monkeypatch.setattr("src.construction.CONSTRUCTION_ZONES_FILE", str(tmp_path / "constructions.json"))
    # Add a construction zone
    add_construction_zone(
        zone="Zone_1",
        road_name="Test Road",
        start_date=datetime.now().strftime("%Y-%m-%d"),
        end_date=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        start_hour=0,
        end_hour=23,
        lanes_closed=1,
        total_lanes=2,
    )
    # Generate advisory
    advisory = generate_diversion_advisory("Zone_1", "Riyadh")
    assert advisory["advisory_type"] == "diversion"
    assert advisory["recommended_alternate_zone"] in ZONE_ADJACENCY["Zone_1"]
    assert "construction" in advisory


def test_freight_schedule_construction_conflict_flag(tmp_path, monkeypatch):
    monkeypatch.setattr("src.construction.CONSTRUCTION_ZONES_FILE", str(tmp_path / "constructions.json"))
    # Add a construction zone
    add_construction_zone(
        zone="Zone_1",
        road_name="Test Road",
        start_date=datetime.now().strftime("%Y-%m-%d"),
        end_date=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
        start_hour=0,
        end_hour=23,
        lanes_closed=1,
        total_lanes=2,
    )
    # Call freight schedule with origin in construction zone
    from src.model import optimise_freight_schedule
    result = optimise_freight_schedule(
        city="Riyadh",
        origin_zone="Zone_1",
        destination_zone="Zone_2",
        vehicle_weight_tonnes=5.0,
        horizon_hours=24,
    )
    assert "construction_conflict" in result
    assert result["construction_conflict"] is True
    # It should still return recommendations (maybe none if all blocked) but flag is set.