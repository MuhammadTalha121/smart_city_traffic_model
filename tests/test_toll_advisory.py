import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")
TEST_KEY = os.environ["API_KEY"]

import pytest
from datetime import datetime, date
from fastapi.testclient import TestClient
from app import app
from src.model import recommend_toll_rate
from src.config import TOLLED_ZONES, HAJJ_ROUTE_ZONES, HAJJ_DATES, TOLL_EVENT_HOURS, TOLL_OFF_PEAK_HOURS


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_no_toll_on_mecca_medina_routes_during_hajj(monkeypatch):
    """
    During Hajj dates, any zone in HAJJ_ROUTE_ZONES must return zero toll,
    regardless of congestion or events.
    """
    if not HAJJ_ROUTE_ZONES:
        pytest.skip("No HAJJ_ROUTE_ZONES configured.")
    if 2026 not in HAJJ_DATES:
        pytest.skip("No Hajj dates for 2026.")

    hajj_start = date.fromisoformat(HAJJ_DATES[2026]["start"])

    class MockDate(date):
        @classmethod
        def today(cls):
            return hajj_start

    import datetime as _dt
    monkeypatch.setattr(_dt, "date", MockDate)

    for zone in HAJJ_ROUTE_ZONES:
        result = recommend_toll_rate(
            zone=zone,
            city="Riyadh",
            timestamp=datetime(hajj_start.year, hajj_start.month, hajj_start.day, 17, 0, 0),
            event_active=True,
        )
        assert result["recommended_rate_sar"] == 0.0
        assert result["hajj_exempt"] is True


def test_toll_increases_during_peak_event():
    """
    During a peak event hour, the recommended rate must be higher than the
    baseline rate (assuming the zone is not Hajj-exempt at that time).
    """
    if not TOLLED_ZONES:
        pytest.skip("No tolled zones configured.")

    zone = TOLLED_ZONES[0]
    if zone in HAJJ_ROUTE_ZONES:
        pytest.skip(f"Only tolled zone is a Hajj route — cannot test event pricing.")

    peak_hour = TOLL_EVENT_HOURS[0]
    off_peak_hour = TOLL_OFF_PEAK_HOURS[0]

    today = date.today()
    peak_ts = datetime(today.year, today.month, today.day, peak_hour, 0, 0)
    off_ts = datetime(today.year, today.month, today.day, off_peak_hour, 0, 0)

    peak_result = recommend_toll_rate(zone, city="Riyadh", timestamp=peak_ts, event_active=True)
    off_result = recommend_toll_rate(zone, city="Riyadh", timestamp=off_ts, event_active=False)

    assert peak_result["recommended_rate_sar"] > off_result["recommended_rate_sar"]
    assert peak_result["demand_reduction_forecast_pct"] < 0


def test_recommendation_endpoint(client):
    response = client.get(
        "/tolls/recommendation?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "recommendations" in data
    assert data["total_tolled_zones"] == len(TOLLED_ZONES)
    for r in data["recommendations"]:
        assert "recommended_rate_sar" in r
        assert "rationale" in r