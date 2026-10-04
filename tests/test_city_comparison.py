import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")
TEST_KEY = os.environ["API_KEY"]

import pytest
from fastapi.testclient import TestClient
from app import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_city_comparison_covers_all_loaded_cities(client):
    """
    Multi-city comparison must cover every city loaded at startup.
    Currently the app loads: Riyadh, NEOM, Dubai, Karachi.
    """
    response = client.get(
        "/analytics/city-comparison?days=7",
        headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert "cities" in data
    assert len(data["cities"]) >= 4

    cities_returned = {c["city"] for c in data["cities"]}
    for expected in ["Riyadh", "NEOM", "Dubai", "Karachi"]:
        assert expected in cities_returned, f"{expected} not in comparison"

    sample = data["cities"][0]
    for key in [
        "avg_congestion_score",
        "peak_hour",
        "incident_count",
        "incident_rate_per_1000_vehicles",
        "emissions_co2_kg_per_100_vehicles",
        "maintenance_urgency_score",
    ]:
        assert key in sample


def test_comparison_report_generated_as_markdown(client):
    response = client.get(
        "/reports/city-comparison?days=7",
        headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    body = response.text
    assert "# Multi-City Traffic Comparison Report" in body
    assert "Vision 2030" in body
    assert "Riyadh" in body