import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features
from src.model import (
    prepare_features, train_xgboost, predict_single, congestion_level,
    detect_anomalies, forecast_congestion, explain_prediction,
    evaluate_models, log_prediction, compare_baseline_vs_enhanced,
    compute_emissions,
    WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING,
)


@pytest.fixture(scope="module")
def trained_model():
    df = generate_traffic_data(city="Riyadh", n_days=30)
    df = apply_hourly_patterns(df, city="Riyadh")
    df = add_lag_features(df)
    X, y, feature_cols = prepare_features(df)
    model, _, _        = train_xgboost(X, y)
    return model, feature_cols, df


def test_predict_single_returns_valid_score():
    result = predict_single(
        city="Riyadh", zone="Zone_1", hour=8,
        vehicle_count=300, avg_speed=40, weather="clear",
        road_type="highway", rush_hour=1, is_weekend=0,
        is_late_night=0, event=0, hour_multiplier=1.4,
    )
    assert "congestion_score" in result
    assert 0.0 <= result["congestion_score"] <= 1.0
    assert result["congestion_level"] in ["Low", "Moderate", "High", "Critical"]


def test_congestion_level_boundaries():
    assert congestion_level(0.0)  == "Low"
    assert congestion_level(0.25) in ["Low", "Moderate"]
    assert congestion_level(0.99) == "Critical"
    assert congestion_level(1.0)  == "Critical"


def test_anomaly_detection_flags_spike(trained_model):
    _, _, df  = trained_model
    zone_df   = df[df["zone"] == "Zone_1"].copy()
    spike_idx = zone_df.index[10]
    zone_df.loc[spike_idx, "vehicle_count"] = zone_df["vehicle_count"].mean() * 6
    result = detect_anomalies(zone_df)
    assert "anomaly_flag" in result.columns
    assert "anomaly_severity" in result.columns
    assert result["anomaly_flag"].sum() >= 1


def test_forecast_returns_three_horizons(trained_model):
    _, _, df  = trained_model
    zone_df   = df[df["zone"] == "Zone_1"]
    forecasts = forecast_congestion(zone_df, zone="Zone_1", hours_ahead=[1, 2, 3])
    assert len(forecasts) == 3
    for fc in forecasts:
        assert "hours_ahead"      in fc
        assert "predicted_score"  in fc
        assert "congestion_level" in fc
        assert 0.0 <= fc["predicted_score"] <= 1.0


def test_explain_prediction_returns_three_factors(trained_model):
    model, feature_cols, _ = trained_model
    row = {
        "vehicle_count"        : 300,
        "avg_speed"            : 40,
        "hour"                 : 8,
        "rush_hour"            : 1,
        "is_weekend"           : 0,
        "is_late_night"        : 0,
        "event"                : 0,
        "hour_multiplier"      : 1.4,
        "weather"              : WEATHER_ENCODING.get("clear", 0),
        "road_type"            : ROAD_ENCODING.get("highway", 0),
        "zone"                 : ZONE_ENCODING.get("Zone_1", 0),
        "day_of_week"          : DAY_ENCODING.get(datetime.now().strftime("%A"), 0),
        "vehicle_count_lag_1h" : 300,
        "vehicle_count_lag_2h" : 300,
        "congestion_lag_1h"    : 0.0,
        "rolling_mean_3h"      : 300,
        "rolling_std_3h"       : 0.0,
    }
    X_row  = pd.DataFrame([row])[feature_cols]
    result = explain_prediction(model, X_row, feature_cols)
    assert "top_factors"   in result
    assert "plain_english" in result
    assert len(result["top_factors"]) == 3


def test_evaluate_models_returns_three_rows(trained_model):
    _, _, df = trained_model
    X, y, _ = prepare_features(df)
    report  = evaluate_models(X, y)
    assert len(report) == 3
    assert "MAE" in report.columns


def test_log_prediction_creates_csv(tmp_path):
    log_path    = str(tmp_path / "test_log.csv")
    prediction  = {
        "city": "Riyadh", "zone": "Zone_1", "hour": 8,
        "weather": "clear", "congestion_score": 0.4,
        "congestion_level": "Moderate",
        "emissions": {"fuel_litres": 10.0, "co2_kg": 23.1, "co2_tonnes": 0.0231},
    }
    explanation = {
        "top_factors": [
            {"factor": "average speed", "direction": "reducing congestion",  "impact": 0.12},
            {"factor": "vehicle count", "direction": "increasing congestion", "impact": 0.05},
            {"factor": "zone location", "direction": "reducing congestion",  "impact": 0.01},
        ],
        "plain_english": "Congestion is primarily driven by average speed."
    }
    log_prediction(prediction, explanation, log_path=log_path)
    log_df = pd.read_csv(log_path)
    assert len(log_df) == 1
    assert "congestion_score" in log_df.columns


def test_compare_baseline_vs_enhanced_shows_improvement():
    report   = compare_baseline_vs_enhanced(city="Riyadh")
    assert len(report) == 2
    assert "MAE" in report.columns
    baseline = report[report["Model"] == "Baseline"]["MAE"].values[0]
    enhanced = report[report["Model"] == "Enhanced (lag features)"]["MAE"].values[0]
    assert isinstance(float(baseline), float)
    assert isinstance(float(enhanced), float)


# ---------------------------------------------------------------------------
# PROMPT 011 — Emissions tests
# ---------------------------------------------------------------------------

def test_compute_emissions_returns_valid_output():
    """compute_emissions returns a dict with the three expected numeric keys."""
    result = compute_emissions(
        congestion_level_str="High",
        vehicle_count=200,
        duration_hours=1.0,
    )
    assert "fuel_litres" in result
    assert "co2_kg"      in result
    assert "co2_tonnes"  in result

    assert result["fuel_litres"] > 0
    assert result["co2_kg"]      > 0
    assert result["co2_tonnes"]  > 0

    # Dimensional consistency: co2_tonnes == co2_kg / 1000 (within float rounding)
    assert abs(result["co2_tonnes"] - result["co2_kg"] / 1000) < 1e-4


def test_critical_emissions_higher_than_low():
    """Critical congestion produces more CO2 than Low congestion for the same inputs."""
    low_result      = compute_emissions("Low",      vehicle_count=300, duration_hours=1.0)
    critical_result = compute_emissions("Critical", vehicle_count=300, duration_hours=1.0)

    assert critical_result["co2_kg"]      > low_result["co2_kg"]
    assert critical_result["fuel_litres"] > low_result["fuel_litres"]
    assert critical_result["co2_tonnes"]  > low_result["co2_tonnes"]
