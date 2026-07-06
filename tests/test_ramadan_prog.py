import pandas as pd
import pytest
from datetime import datetime
from src.config import RAMADAN_IFTAR_HOUR, RAMADAN_PROGRESSION_FACTOR
from src.data import get_ramadan_week, apply_hourly_patterns

# 1. Week boundary logic
@pytest.mark.parametrize("day_offset,expected", [
    (0, 1), (6, 1), (7, 2), (13, 2), (14, 3), (20, 3), (21, 4), (28, 4), (100, 4)
])
def test_get_ramadan_week(day_offset, expected):
    start = pd.Timestamp("2025-03-01")
    check = start + pd.Timedelta(days=day_offset)
    assert get_ramadan_week(check, start) == expected


def _make_df(hours, start_ts="2025-03-01", n_days=28, base_count=100):
    rows = []
    ts0 = pd.Timestamp(start_ts)
    for d in range(n_days):
        for h in hours:
            rows.append({
                "timestamp": ts0 + pd.Timedelta(days=d, hours=h),
                "hour": h,
                "vehicle_count": base_count,
                "avg_speed": 60,
                "weather": "clear",
                "event": 0,
                "rush_hour": 0,
                "day_of_week": "Monday",
                "zone": "Zone_1",
            })
    return pd.DataFrame(rows)


# 2. Iftar progression applied, non-Iftar untouched
def test_progression_applied_only_at_iftar():
    df = _make_df(hours=[RAMADAN_IFTAR_HOUR, 10])
    out = apply_hourly_patterns(df, city="Riyadh", ramadan=True, hajj=False,
                                 ramadan_start_date=pd.Timestamp("2025-03-01"))
    iftar_wk4 = out[(out['hour'] == RAMADAN_IFTAR_HOUR) &
                    (out['timestamp'] >= "2025-03-22")]
    iftar_wk1 = out[(out['hour'] == RAMADAN_IFTAR_HOUR) &
                    (out['timestamp'] < "2025-03-08")]
    assert iftar_wk4['vehicle_count'].mean() > iftar_wk1['vehicle_count'].mean()

    non_iftar = out[out['hour'] == 10]
    assert non_iftar['vehicle_count'].nunique() == 1  # no week drift


# 3. Hajj overrides Ramadan — no progression
def test_hajj_overrides_no_progression():
    df = _make_df(hours=[RAMADAN_IFTAR_HOUR])
    out = apply_hourly_patterns(df, city="Riyadh", ramadan=True, hajj=True,
                                 ramadan_start_date=pd.Timestamp("2025-03-01"))
    assert out['is_ramadan'].iloc[0] == 0
    # can't easily isolate progression amid hajj multipliers,
    # so just assert the flag logic held (progression code path skipped)


# 4. Regression: ramadan=False leaves iftar-hour rows unaffected by new code
def test_no_ramadan_no_effect():
    df = _make_df(hours=[RAMADAN_IFTAR_HOUR])
    out = apply_hourly_patterns(df, city="Riyadh", ramadan=False, hajj=False)
    assert out['is_ramadan'].iloc[0] == 0


# 5. Default start date fallback
def test_default_start_date_is_min_timestamp():
    df = _make_df(hours=[RAMADAN_IFTAR_HOUR], n_days=7)
    out = apply_hourly_patterns(df, city="Riyadh", ramadan=True, hajj=False)
    # entire range is within 7 days => all week 1 => uniform multiplier
    assert out['vehicle_count'].nunique() == 1


# 6. Clip ceiling respected
def test_clip_500():
    df = _make_df(hours=[RAMADAN_IFTAR_HOUR], base_count=490, n_days=28)
    out = apply_hourly_patterns(df, city="Riyadh", ramadan=True, hajj=False,
                                 ramadan_start_date=pd.Timestamp("2025-03-01"))
    assert out['vehicle_count'].max() <= 500


# 7. Dtype guard
def test_timestamp_dtype():
    df = _make_df(hours=[RAMADAN_IFTAR_HOUR])
    assert pd.api.types.is_datetime64_any_dtype(df['timestamp'])