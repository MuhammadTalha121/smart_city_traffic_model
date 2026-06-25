import csv
import io
import os
import pytest
from fastapi.testclient import TestClient
from app import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_csv_export_requires_auth(client):
    """Without API key, returns 401."""
    response = client.get("/export/csv")
    assert response.status_code == 401


def test_csv_export_returns_csv(client):
    """With valid key, returns CSV content."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        pytest.skip("API_KEY not set")
    response = client.get("/export/csv", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in response.headers["content-disposition"]


def test_csv_export_filters_by_city(client):
    """Filter by city returns only rows for that city."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        pytest.skip("API_KEY not set")
    response = client.get("/export/csv?city=Riyadh", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    content = response.text
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames and 'city' in reader.fieldnames:
        for row in reader:
            assert row['city'] == 'Riyadh'


def test_csv_export_includes_anomaly_flag(client):
    """When include_anomalies=true, column exists and is 0/1."""
    api_key = os.getenv("API_KEY")
    if not api_key:
        pytest.skip("API_KEY not set")
    response = client.get("/export/csv?include_anomalies=true", headers={"X-API-Key": api_key})
    assert response.status_code == 200
    content = response.text
    reader = csv.DictReader(io.StringIO(content))
    assert reader.fieldnames is not None, "CSV has no header"
    assert 'anomaly_flag' in reader.fieldnames, (
        f"anomaly_flag missing from columns: {reader.fieldnames}"
    )
    for row in list(reader)[:3]:
        assert row['anomaly_flag'] in ('0', '1'), (
            f"unexpected anomaly_flag value: {row['anomaly_flag']}"
        )
