"""
Saudi calendar invariant tests (PROMPT 162).

Guard the five core Saudi calibrations against silent drift when
calendar parameters change (Hijri year rollover, Ramadan start date,
Hajj date update, school term update).

Run before every calendar update:
    make test-saudi-calendar
"""
import pytest
from datetime import datetime, date

import pandas as pd


def test_friday_prayer_suppression_active_on_friday_noon():
    """
    Friday prayer hours must produce >=85% vehicle count drop vs weekday
    same hours. Parameterized across SAUDI_CITIES.
    """
    from src.config import FRIDAY_PRAYER_HOURS, SAUDI_CITIES
    from src.data import generate_traffic_data, apply_hourly_patterns

    for city in SAUDI_CITIES:
        df = generate_traffic_data(city=city, n_days=14)
        df = apply_hourly_patterns(df, city=city)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["weekday"] = df["timestamp"].dt.weekday
        df["hour_of_day"] = df["timestamp"].dt.hour

        prayer_hours = [int(h) for h in FRIDAY_PRAYER_HOURS]

        friday_prayer = df[(df["weekday"] == 4) & (df["hour_of_day"].isin(prayer_hours))]
        weekday_same = df[(df["weekday"] != 4) & (df["hour_of_day"].isin(prayer_hours))]

        assert not friday_prayer.empty, f"{city}: no Friday prayer-hour data"
        assert not weekday_same.empty, f"{city}: no weekday prayer-hour data"

        friday_mean = friday_prayer["vehicle_count"].mean()
        weekday_mean = weekday_same["vehicle_count"].mean()
        drop = 1 - (friday_mean / weekday_mean)

        assert drop >= 0.85, (
            f"{city}: Friday prayer drop {drop:.2%} < 85%. "
            f"Friday {friday_mean:.1f} vs weekday {weekday_mean:.1f}."
        )


def test_ramadan_factor_week4_greater_than_week1():
    """
    Iftar-hour vehicle count must be higher in Ramadan week 4 than in week 1
    (progression invariant, PROMPT 116). Same-seed data isolates the
    progression effect from noise.
    """
    from src.config import RAMADAN_IFTAR_HOUR
    from src.data import generate_traffic_data, apply_hourly_patterns

    ramadan_start = pd.Timestamp("2026-02-18")

    def _apply(offset_days: int) -> pd.DataFrame:
        df = generate_traffic_data(city="Riyadh", n_days=7)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["timestamp"] = ramadan_start + pd.Timedelta(days=offset_days) + (
            df["timestamp"] - df["timestamp"].min()
        )
        return apply_hourly_patterns(
            df,
            city="Riyadh",
            ramadan=True,
            ramadan_start_date=ramadan_start,
        )

    df_w1 = _apply(0)
    df_w4 = _apply(21)

    week1_iftar = df_w1[df_w1["timestamp"].dt.hour == RAMADAN_IFTAR_HOUR]["vehicle_count"].mean()
    week4_iftar = df_w4[df_w4["timestamp"].dt.hour == RAMADAN_IFTAR_HOUR]["vehicle_count"].mean()

    assert week4_iftar > week1_iftar, (
        f"Week 4 iftar vehicle count ({week4_iftar:.2f}) should exceed "
        f"Week 1 ({week1_iftar:.2f}). Progression factor not applied?"
    )


def test_hajj_density_gradient_monotone_toward_mecca():
    """
    Hajj peak density gradient must decrease monotonically away from Mecca:
    Zone_1 > Zone_3 > Zone_2 > Zone_4 > Zone_5 (PROMPT 115).
    """
    from src.config import HAJJ_CROWD_DENSITY_GRADIENT

    peak = HAJJ_CROWD_DENSITY_GRADIENT["peak"]
    ordered = ["Zone_1", "Zone_3", "Zone_2", "Zone_4", "Zone_5"]

    for i in range(len(ordered) - 1):
        a, b = ordered[i], ordered[i + 1]
        assert peak[a] > peak[b], (
            f"Gradient not monotone: {a} ({peak[a]}) must exceed {b} ({peak[b]})"
        )


def test_no_toll_on_hajj_pilgrimage_routes():
    """
    During Hajj dates, recommend_toll_rate() must return 0 SAR for every
    zone in HAJJ_ROUTE_ZONES (PROMPT 154 + religious access obligation).
    """
    from src.config import HAJJ_ROUTE_ZONES, HAJJ_DATES
    from src.model import recommend_toll_rate

    if not HAJJ_DATES:
        pytest.skip("HAJJ_DATES not configured — no year to test")

    year = next(iter(HAJJ_DATES))
    hajj_start_str = HAJJ_DATES[year]["start"]
    timestamp = datetime.combine(date.fromisoformat(hajj_start_str), datetime.min.time())

    for zone in HAJJ_ROUTE_ZONES:
        result = recommend_toll_rate(zone=zone, city="Riyadh", timestamp=timestamp)
        assert result["recommended_rate_sar"] == 0.0, (
            f"{zone} on {hajj_start_str} should be toll-exempt, "
            f"got {result['recommended_rate_sar']} SAR"
        )
        assert result["hajj_exempt"] is True, f"{zone}: hajj_exempt should be True"


def test_school_restriction_off_during_ramadan_break():
    """
    School restrictions must be inactive during Ramadan (schools are
    typically closed or on reduced schedule in Saudi Arabia). PROMPT 153's
    get_active_school_restrictions must return an empty list.

    If this test fails, PROMPT 153 does not account for the Ramadan school
    break — a legitimate finding, not a test to soften.
    """
    from src.construction import get_active_school_restrictions

    ramadan_school_hour = datetime(2026, 2, 23, 8, 0)
    restrictions = get_active_school_restrictions(
        timestamp=ramadan_school_hour,
        city="Riyadh",
    )

    assert len(restrictions) == 0, (
        f"School restrictions should be inactive during Ramadan, "
        f"but got {len(restrictions)} active restriction(s). "
        f"PROMPT 153 may not be handling the Ramadan school break — "
        f"this is a real gap, not a test to relax."
    )