import pytest
import time
import os
import pandas as pd
from fastapi.testclient import TestClient
from app import app
from src.digital_twin import DigitalTwinState, create_twin
from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features

# Ensure API_KEY is set for tests
os.environ.setdefault("API_KEY", "test-key-for-pytest-only")
TEST_KEY = os.environ["API_KEY"]


def test_digital_twin_is_immutable_after_intervention():
    """apply_intervention must return a new state, not mutate the original."""
    df = generate_traffic_data(city="Riyadh", n_days=1)
    df = apply_hourly_patterns(df, city="Riyadh")
    df = add_lag_features(df)

    twin = DigitalTwinState("Riyadh", df)
    intervention = {"zone_closures": ["Zone_1"]}
    new_twin = twin.apply_intervention(intervention)

    # Original unchanged
    assert "Zone_1" in twin.snapshot_df["zone"].values
    assert not (twin.snapshot_df[twin.snapshot_df["zone"] == "Zone_1"]["vehicle_count"] == 0).all()

    # New twin has changes
    assert "Zone_1" in new_twin.snapshot_df["zone"].values
    assert (new_twin.snapshot_df[new_twin.snapshot_df["zone"] == "Zone_1"]["vehicle_count"] == 0).all()

    # They are different objects
    assert twin is not new_twin


def test_twin_create_does_not_mutate_city_dfs():
    """Creating a twin must not alter the live city_df."""
    with TestClient(app) as client:
        # Get original city_df length
        city_df = app.state.city_dfs["Riyadh"]
        original_len = len(city_df)

        # Create twin
        response = client.post(
            "/twin/create?city=Riyadh",
            headers={"X-API-Key": TEST_KEY}
        )
        assert response.status_code == 200

        # city_df unchanged
        assert len(app.state.city_dfs["Riyadh"]) == original_len


def test_twin_stored_and_retrievable_by_id():
    """Twins must be stored and retrievable via /twin/list."""
    with TestClient(app) as client:
        # Create twin
        create_resp = client.post(
            "/twin/create?city=Riyadh",
            headers={"X-API-Key": TEST_KEY}
        )
        assert create_resp.status_code == 200
        twin_id = create_resp.json()["twin_id"]

        # List twins
        list_resp = client.get(
            "/twin/list?city=Riyadh",
            headers={"X-API-Key": TEST_KEY}
        )
        assert list_resp.status_code == 200
        twins = list_resp.json()["twins"]
        assert len(twins) == 1
        assert twins[0]["twin_id"] == twin_id


def test_twin_limit_enforced(monkeypatch):
    """Maximum twins per city enforced; oldest evicted when limit exceeded."""
    # Reduce limit to 3 for faster testing
    monkeypatch.setattr("src.digital_twin.MAX_TWINS_PER_CITY", 3)

    with TestClient(app) as client:
        # Create 3 twins (limit is 3)
        for i in range(3):
            resp = client.post(
                "/twin/create?city=Riyadh",
                headers={"X-API-Key": TEST_KEY}
            )
            assert resp.status_code == 200
            time.sleep(0.1)

        # List – should have 3
        list_resp = client.get(
            "/twin/list?city=Riyadh",
            headers={"X-API-Key": TEST_KEY}
        )
        assert list_resp.status_code == 200
        twins = list_resp.json()["twins"]
        assert len(twins) == 3

        # Wait a bit
        time.sleep(1)

        # Create 4th twin – should evict the oldest
        resp = client.post(
            "/twin/create?city=Riyadh",
            headers={"X-API-Key": TEST_KEY}
        )
        assert resp.status_code == 200

        # List – should still have 3 (oldest evicted)
        list_resp = client.get(
            "/twin/list?city=Riyadh",
            headers={"X-API-Key": TEST_KEY}
        )
        assert list_resp.status_code == 200
        twins = list_resp.json()["twins"]
        assert len(twins) == 3