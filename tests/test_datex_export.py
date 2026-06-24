import os
import pytest
from fastapi.testclient import TestClient
from app import app
from src.datex_export import to_datex_measurement, generate_datex_payload
from src.model import congestion_level


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_to_datex_measurement_includes_required_fields():
    """Check that the measurement dict has the expected top-level keys."""
    pred = {
        'congestion_score': 0.75,
        'congestion_level': 'High',
        'vehicle_count': 350,
        'avg_speed': 45,
    }
    result = to_datex_measurement(pred, 'Zone_1', 'Riyadh', '2025-01-01T00:00:00')
    assert 'measurementSiteReference' in result
    assert 'measurementTime' in result
    assert 'measuredValue' in result
    assert 'congestionLevel' in result
    # Check measuredValue list length and keys
    assert len(result['measuredValue']) == 4
    for item in result['measuredValue']:
        assert 'valueType' in item
        assert 'value' in item
        assert 'unit' in item


def test_generate_datex_payload_returns_valid_structure():
    """Check that the full payload has the expected structure."""
    # This relies on app.state being populated; the test client lifecycle
    # should have run the lifespan and set up city_dfs.
    payload = generate_datex_payload('Riyadh')
    assert 'publicationCreator' in payload
    assert 'publicationTime' in payload
    assert 'publicationType' in payload
    assert 'measurements' in payload
    assert isinstance(payload['measurements'], list)
    # If data exists, check a measurement structure
    if payload['measurements']:
        m = payload['measurements'][0]
        assert 'measurementSiteReference' in m
        assert 'measuredValue' in m


def test_datex_export_endpoint_requires_auth(client):
    """Without API key, endpoint returns 401."""
    response = client.get("/export/datex?city=Riyadh")
    assert response.status_code == 401


def test_datex_export_endpoint_returns_valid_structure(client):
    """With valid API key, returns 200 and valid structure."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        pytest.skip("API_KEY not set in environment")
    response = client.get("/export/datex?city=Riyadh", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    data = response.json()
    assert "publicationCreator" in data
    assert "measurements" in data
    # Check that measurements list is present
    assert isinstance(data["measurements"], list)