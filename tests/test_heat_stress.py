"""
Heat stress (WBGT) tests
"""
import pytest
from datetime import datetime


def test_heat_stress_extreme_above_35_wbgt():
    """
    Extreme heat conditions (45°C + 80% humidity) must produce
    wbgt_c > 35 and risk_level == 'Extreme'.
    """
    from src.model import calculate_heat_stress_index

    result = calculate_heat_stress_index(
        temp_c=45.0,
        humidity_pct=80.0,
        wind_speed_kmh=5.0,
    )

    assert result["wbgt_c"] > 35.0, (
        f"Expected WBGT > 35 for 45°C/80% RH, got {result['wbgt_c']}"
    )
    assert result["risk_level"] == "Extreme", (
        f"Expected 'Extreme' risk at WBGT {result['wbgt_c']}, got '{result['risk_level']}'"
    )
    assert result["method"] == "indoor_wbgt_approximation"
    assert len(result["limitations"]) == 3, (
        "Every WBGT result must carry all three limitations — "
        "this is the honesty contract for the estimate"
    )


def test_heat_stress_alert_fires_in_summer():
    """
    The endpoint must report in_summer_season=True when the current
    month is June–September, and False otherwise.

    The scheduler-driven alert is separate — this tests the flag
    that the scheduler will consult, not the scheduler itself.
    """
    from fastapi.testclient import TestClient
    from app import app
    from src.config import HEAT_STRESS_MONTHS

    current_month = datetime.now().month
    expected_flag = current_month in HEAT_STRESS_MONTHS

    with TestClient(app) as client:
        resp = client.get("/public/heat-stress-advisory?city=Riyadh")

        if resp.status_code == 503:
            pytest.skip(
                "Weather adapter unavailable — likely no network. "
                "The endpoint is working correctly (returned 503 as designed); "
                "cannot test the flag without live weather data."
            )

        assert resp.status_code == 200, (
            f"Endpoint returned {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()

    assert "in_summer_season" in data
    assert data["in_summer_season"] == expected_flag, (
        f"Current month {current_month} — expected in_summer_season={expected_flag}, "
        f"got {data['in_summer_season']}. HEAT_STRESS_MONTHS={HEAT_STRESS_MONTHS}"
    )
    assert "risk_level" in data
    assert data["risk_level"] in ("Low", "Moderate", "High", "Extreme")
    assert "recommended_action" in data
    assert len(data["recommended_action"]) > 10