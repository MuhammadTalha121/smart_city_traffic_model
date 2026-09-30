import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")
TEST_KEY = os.environ["API_KEY"]

import pytest
from datetime import date
from fastapi.testclient import TestClient
from app import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_briefing_generated_in_english(client):
    response = client.get(
        "/briefing/Zone_1?city=Riyadh&language=en",
        headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 200
    data = response.json()
    assert "briefing" in data
    briefing = data["briefing"]
    assert "Congestion in Zone_1" in briefing
    assert "Primary factors:" in briefing
    assert "Recommended action:" in briefing


def test_briefing_generated_in_arabic(client):
    response = client.get(
        "/briefing/Zone_1?city=Riyadh&language=ar",
        headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 200
    briefing = response.json()["briefing"]
    assert "الازدحام في Zone_1" in briefing
    assert "العوامل الرئيسية:" in briefing
    assert "الإجراء الموصى به:" in briefing


def test_hajj_prefix_present_during_hajj_period(client, monkeypatch):
    from src.config import HAJJ_DATES
    year = 2026
    if year not in HAJJ_DATES:
        pytest.skip(f"No Hajj dates for {year} in config.")
    hajj_start = date.fromisoformat(HAJJ_DATES[year]["start"])

    class MockDate(date):
        @classmethod
        def today(cls):
            return hajj_start

    import datetime
    monkeypatch.setattr(datetime, "date", MockDate)

    response = client.get(
        "/briefing/Zone_1?city=Riyadh&language=en",
        headers={"X-API-Key": TEST_KEY}
    )
    assert response.status_code == 200
    briefing = response.json()["briefing"]
    assert "Hajj season active." in briefing