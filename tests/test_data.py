import pytest
import pandas as pd
from src.data import (
    generate_traffic_data,
    apply_hourly_patterns,
    add_lag_features,
    validate_data,
)
from src.config import FRIDAY_PRAYER_HOURS


def test_generate_returns_correct_shape():
    df = generate_traffic_data(city="Riyadh", n_days=7, zones=5)
    assert len(df) == 7 * 24 * 5
    assert set(["city", "zone", "hour", "vehicle_count", "avg_speed", "weather"]).issubset(df.columns)


def test_friday_prayer_drop_exceeds_85_percent():
    df = generate_traffic_data(city="Riyadh", n_days=30)
    df = apply_hourly_patterns(df, city="Riyadh")

    friday_prayer = df[
        (df["day_of_week"] == "Friday") &
        (df["hour"].isin(FRIDAY_PRAYER_HOURS))
    ]["vehicle_count"].mean()

    weekday_midday = df[
        (~df["day_of_week"].isin(["Friday", "Saturday"])) &
        (df["hour"].isin(FRIDAY_PRAYER_HOURS))
    ]["vehicle_count"].mean()

    drop_pct = (weekday_midday - friday_prayer) / weekday_midday
    assert drop_pct >= 0.85, f"Friday prayer drop was {drop_pct:.4f} — expected >= 0.85"


def test_sandstorm_speed_reduction_in_range():
    df = generate_traffic_data(city="Riyadh", n_days=30)
    df = apply_hourly_patterns(df, city="Riyadh")

    clear_speed     = df[df["weather"] == "clear"]["avg_speed"].mean()
    sandstorm_speed = df[df["weather"] == "sandstorm"]["avg_speed"].mean()
    reduction       = (clear_speed - sandstorm_speed) / clear_speed

    assert 0.35 <= reduction <= 0.45, f"Sandstorm speed reduction was {reduction:.4f} — expected 0.35–0.45"


def test_lag_features_no_nulls_after_dropna():
    df = generate_traffic_data(city="Riyadh", n_days=30)
    df = apply_hourly_patterns(df, city="Riyadh")
    df = add_lag_features(df)

    lag_cols = [
        "vehicle_count_lag_1h", "vehicle_count_lag_2h",
        "congestion_lag_1h", "rolling_mean_3h", "rolling_std_3h"
    ]
    assert df[lag_cols].isnull().sum().sum() == 0, "Lag features contain nulls after dropna"


def test_validate_data_all_pass():
    report = validate_data(city="Riyadh", n_days=30)
    failed = report[report["Status"] == "FAIL"]
    assert len(failed) == 0, f"Validation failed on: {failed['Check'].tolist()}"





def test_repeated_speed_values_flagged_as_caching_fault():
    from src.data import detect_lineage_faults

    df = pd.DataFrame({
        'zone'         : ['Zone_1'] * 5,
        'timestamp'    : pd.date_range('2026-01-01', periods=5, freq='h'),
        'avg_speed'    : [60.0, 60.0, 60.0, 60.0, 45.0],
        'vehicle_count': [100, 105, 98, 110, 120],
    })
    result = detect_lineage_faults(df, source='weather')

    repeat_faults = [f for f in result['faults'] if f['type'] == 'repeated_value']
    assert len(repeat_faults) >= 1, "Expected a repeated_value fault for 4 identical avg_speed readings"
    assert repeat_faults[0]['rows_affected'] == 4


def test_nonzero_volume_with_zero_speed_flagged_as_sensor_fault():
    from src.data import detect_lineage_faults

    df = pd.DataFrame({
        'zone'         : ['Zone_1'] * 3,
        'timestamp'    : pd.date_range('2026-01-01', periods=3, freq='h'),
        'avg_speed'    : [0.0, 55.0, 50.0],
        'vehicle_count': [150, 100, 95],
    })
    result = detect_lineage_faults(df, source='mock')

    sensor_faults = [f for f in result['faults'] if f['type'] == 'sensor_fault']
    assert len(sensor_faults) == 1
    assert sensor_faults[0]['rows_affected'] == 1






def test_all_five_cultural_calibrations_still_pass_after_full_chain(capsys):
    """
    Consolidate the five core Saudi cultural calibrations into one test.
    This delegates to validate_data() and verifies that all 5 checks pass.
    """
    from src.data import validate_data
    validate_data(city='Riyadh')
    captured = capsys.readouterr()
    # The output should contain the final summary line.
    assert "5 / 5 checks passed" in captured.out, "Cultural calibrations are not all passing"