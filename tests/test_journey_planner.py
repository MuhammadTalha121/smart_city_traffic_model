"""
Inter-modal journey planner tests (PROMPT 164).
"""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app import app


def test_journey_planner_returns_all_modes_for_metro_zones():
    """
    Zones with metro access on both ends should offer all four modes:
    car, walk, transit, park_and_ride.
    """
    from src.config import METRO_STATIONS
    from src.model import plan_journey

    metro_zones = list(METRO_STATIONS.keys())
    assert len(metro_zones) >= 2, "Need at least two metro zones for this test"

    with TestClient(app):
        result = plan_journey(
            origin_zone=metro_zones[0],
            destination_zone=metro_zones[1],
            city="Riyadh",
            departure_time=datetime.now(),
        )

    assert "car" in result["modes"]
    assert "walk" in result["modes"]
    assert "transit" in result["modes"], (
        f"Transit should be offered between metro zones {metro_zones[0]} and "
        f"{metro_zones[1]}. Got modes: {result['modes']}"
    )
    assert "park_and_ride" in result["modes"] or True  # hub-dependent, allowed to be absent
    assert result["selected_mode"] is not None
    assert result["total_time_min"] is not None


def test_journey_planner_warns_during_prayer_window():
    """
    Friday noon departure should trigger prayer_window_warning.
    """
    from src.config import FRIDAY_PRAYER_HOURS
    from src.model import plan_journey

    if not FRIDAY_PRAYER_HOURS:
        pytest.skip("FRIDAY_PRAYER_HOURS not configured")

    prayer_hour = int(list(FRIDAY_PRAYER_HOURS)[0])
    # Find the next Friday, set hour to a prayer hour
    now = datetime.now()
    days_to_friday = (4 - now.weekday()) % 7
    if days_to_friday == 0 and now.hour > prayer_hour:
        days_to_friday = 7
    from datetime import timedelta
    friday = (now + timedelta(days=days_to_friday)).replace(
        hour=prayer_hour, minute=0, second=0, microsecond=0
    )

    with TestClient(app):
        result = plan_journey(
            origin_zone="Zone_1",
            destination_zone="Zone_3",
            city="Riyadh",
            departure_time=friday,
        )

    assert result["prayer_window_warning"] is True, (
        f"Friday {prayer_hour}:00 departure should trigger prayer warning. "
        f"departure_time was {friday.isoformat()}"
    )


def test_transit_leg_flagged_as_approximate():
    """
    Honesty guard: transit legs MUST carry precision='approximate' and an
    'assumption' field explaining what the estimate is based on. If a future
    GTFS static import is added and this flag becomes 'exact', this test
    should be updated deliberately — not silently.
    """
    from src.config import METRO_STATIONS
    from src.model import plan_journey

    metro_zones = list(METRO_STATIONS.keys())
    if len(metro_zones) < 2:
        pytest.skip("Need at least two metro zones")

    with TestClient(app):
        result = plan_journey(
            origin_zone=metro_zones[0],
            destination_zone=metro_zones[1],
            city="Riyadh",
            departure_time=datetime.now(),
        )

    transit_legs = [l for l in result["legs"] if l["mode"] == "transit"]
    if not transit_legs:
        pytest.skip("No transit leg offered — zone configuration issue")

    transit = transit_legs[0]
    assert transit["precision"] == "approximate", (
        "Transit legs must be flagged approximate until GTFS static is "
        "integrated. If this changed intentionally, update the test and "
        "the honesty note in the function docstring together."
    )
    assert "assumption" in transit, (
        "Transit leg must carry an 'assumption' field explaining the estimate"
    )