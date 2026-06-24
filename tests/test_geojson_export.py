import os
import pytest
from fastapi.testclient import TestClient
from app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_geojson_export_requires_auth(client):
    """Without API key, endpoint returns 401."""
    response = client.get("/export/geojson?city=Riyadh")
    assert response.status_code == 401


def test_geojson_export_returns_feature_collection(client):
    """With valid key, returns FeatureCollection with features list."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        pytest.skip("API_KEY not set in environment")
    response = client.get("/export/geojson?city=Riyadh", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    assert isinstance(data["features"], list)


def test_geojson_properties_contain_required_fields(client):
    """Each feature's properties include all required fields."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        pytest.skip("API_KEY not set")
    response = client.get("/export/geojson?city=Riyadh", headers={"X-API-Key": api_key})
    data = response.json()
    if data["features"]:
        feature = data["features"][0]
        assert "geometry" in feature
        assert "properties" in feature
        props = feature["properties"]
        required = [
            "zone",
            "congestion_score",
            "congestion_level",
            "vehicle_count",
            "avg_speed",
            "co2_kg_per_hour",
            "timestamp"
        ]
        for key in required:
            assert key in props