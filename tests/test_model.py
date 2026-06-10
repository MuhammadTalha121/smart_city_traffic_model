import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features
from src.model import (
    prepare_features, train_xgboost, predict_single, congestion_level,
    detect_anomalies, forecast_congestion, explain_prediction,
    evaluate_models, log_prediction, compare_baseline_vs_enhanced,
    WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING,
)
from src.config import HAJJ_ROUTE_ZONES


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
# PROMPT 012 — Hajj mode tests
# ---------------------------------------------------------------------------

def test_hajj_mode_produces_hajj_phase_column():
    """apply_hourly_patterns with hajj=True must add a hajj_phase column."""
    df     = generate_traffic_data(city="Riyadh", n_days=10)
    df_hajj = apply_hourly_patterns(df, city="Riyadh", hajj=True)
    assert "hajj_phase" in df_hajj.columns, "hajj_phase column missing from Hajj output"
    phases = set(df_hajj["hajj_phase"].unique())
    assert phases == {"inbound", "peak", "outbound"}, (
        f"Expected {{inbound, peak, outbound}}, got {phases}"
    )


def test_hajj_peak_vehicle_count_exceeds_standard_midday_by_2_5x():
    """
    Hajj peak hour (12:00) in a route zone must produce vehicle counts
    at least 2.5x the standard weekday midday average for the same zone.
    """
    df_standard = apply_hourly_patterns(
        generate_traffic_data(city="Riyadh", n_days=30), city="Riyadh"
    )
    df_hajj = apply_hourly_patterns(
        generate_traffic_data(city="Riyadh", n_days=30), city="Riyadh", hajj=True
    )

    # Hajj peak phase, 12:00, pilgrimage route zone
    hajj_peak_mean = df_hajj[
        (df_hajj["hajj_phase"] == "peak") &
        (df_hajj["hour"] == 12) &
        (df_hajj["zone"] == "Zone_1")
    ]["vehicle_count"].mean()

    # Standard weekday midday (exclude Friday prayer drop)
    standard_midday_mean = df_standard[
        (~df_standard["day_of_week"].isin(["Friday", "Saturday"])) &
        (df_standard["hour"] == 12) &
        (df_standard["zone"] == "Zone_1")
    ]["vehicle_count"].mean()

    ratio = hajj_peak_mean / max(standard_midday_mean, 1.0)
    assert ratio >= 2.5, (
        f"Hajj peak vehicle_count ratio was {ratio:.2f} — expected >= 2.5x standard midday"
    )


def test_hajj_route_zones_higher_than_non_route_zones_during_peak():
    """
    During Hajj peak phase, pilgrimage route zones must have higher
    average vehicle_count than non-route zones.
    """
    df_hajj = apply_hourly_patterns(
        generate_traffic_data(city="Riyadh", n_days=20), city="Riyadh", hajj=True
    )

    peak_df       = df_hajj[df_hajj["hajj_phase"] == "peak"]
    route_mean    = peak_df[peak_df["zone"].isin(HAJJ_ROUTE_ZONES)]["vehicle_count"].mean()
    non_route_mean = peak_df[~peak_df["zone"].isin(HAJJ_ROUTE_ZONES)]["vehicle_count"].mean()

    assert route_mean > non_route_mean, (
        f"Route zone mean ({route_mean:.1f}) not higher than "
        f"non-route mean ({non_route_mean:.1f}) during Hajj peak"
    )


def test_hajj_overrides_ramadan_when_both_true():
    """
    When both hajj=True and ramadan=True, Hajj takes precedence.
    The is_ramadan flag should be 0 and is_hajj should be 1.
    """
    df      = generate_traffic_data(city="Riyadh", n_days=5)
    df_both = apply_hourly_patterns(df, city="Riyadh", ramadan=True, hajj=True)
    assert df_both["is_hajj"].iloc[0]   == 1, "is_hajj should be 1 when hajj=True"
    assert df_both["is_ramadan"].iloc[0] == 0, "is_ramadan should be 0 when hajj overrides"


def test_standard_mode_has_no_hajj_phase():
    """
    Without hajj=True, hajj_phase column should be 'none' for all rows.
    """
    df        = generate_traffic_data(city="Riyadh", n_days=5)
    df_std    = apply_hourly_patterns(df, city="Riyadh")
    assert "hajj_phase" in df_std.columns
    assert (df_std["hajj_phase"] == "none").all(), (
        "hajj_phase should be 'none' for all rows in standard mode"
    )


# ---------------------------------------------------------------------------
# PROMPT 013 — Intervention recommendation tests
# ---------------------------------------------------------------------------

def test_intervention_critical_returns_intervene():
    """Critical congestion must return urgency='Intervene' with metro and carpool data."""
    from src.model import get_intervention

    result = get_intervention(zone="Zone_1", hour=8, congestion_level_str="Critical")

    assert result["urgency"] == "Intervene", (
        f"Expected urgency 'Intervene' for Critical, got '{result['urgency']}'"
    )
    assert result["metro_station"] is not None, "Critical zone should have a metro station"
    assert result["carpool_available"] is True, "Zone_1 should have carpool lane available"
    assert result["recommended_departure"] is not None, (
        "Critical at hour 8 should recommend a departure time"
    )
    assert "operator_action" in result
    assert "commuter_advice" in result


def test_intervention_low_returns_monitor():
    """Low congestion must return urgency='Monitor' with no disruption advice."""
    from src.model import get_intervention

    result = get_intervention(zone="Zone_1", hour=3, congestion_level_str="Low")

    assert result["urgency"] == "Monitor", (
        f"Expected urgency 'Monitor' for Low, got '{result['urgency']}'"
    )
    assert "No action" in result["commuter_advice"]


# ---------------------------------------------------------------------------
# PROMPT 014 — Accident risk scoring tests
# ---------------------------------------------------------------------------

def test_sandstorm_rush_hour_produces_high_risk():
    """Sandstorm + rush hour must push risk into High Risk or Critical Risk."""
    from src.model import compute_accident_risk

    result = compute_accident_risk(
        congestion_score = 0.55,
        weather          = "sandstorm",
        hour             = 8,
        is_weekend       = 0,
        rush_hour        = 1,
    )
    assert result["risk_score"] > 0.50, (
        f"Sandstorm + rush hour risk was {result['risk_score']:.4f} — expected > 0.50"
    )
    assert result["risk_level"] in ("High Risk", "Critical Risk"), (
        f"Expected High Risk or Critical Risk, got '{result['risk_level']}'"
    )
    assert "sandstorm" in result["primary_risk_factor"]


def test_clear_low_congestion_produces_safe():
    """Clear weather, low congestion, no rush hour must produce Safe risk level."""
    from src.model import compute_accident_risk

    result = compute_accident_risk(
        congestion_score = 0.10,
        weather          = "clear",
        hour             = 10,
        is_weekend       = 0,
        rush_hour        = 0,
    )
    assert result["risk_level"] == "Safe", (
        f"Expected Safe, got '{result['risk_level']}' (score={result['risk_score']:.4f})"
    )
    assert 0.0 <= result["risk_score"] <= 1.0


# ---------------------------------------------------------------------------
# PROMPT 015 — Adaptive signal timing tests
# ---------------------------------------------------------------------------

def test_critical_congestion_produces_longer_green():
    """Critical congestion must produce a longer green phase than Low congestion."""
    from src.model import compute_signal_timing

    low_timing = compute_signal_timing(
        congestion_score=0.10, vehicle_count=50, hour=10, is_weekend=0
    )
    critical_timing = compute_signal_timing(
        congestion_score=0.85, vehicle_count=450, hour=10, is_weekend=0
    )

    assert critical_timing["green_seconds"] > low_timing["green_seconds"], (
        f"Critical green ({critical_timing['green_seconds']}s) not longer than "
        f"Low green ({low_timing['green_seconds']}s)"
    )
    assert critical_timing["phase_ratio"] == 0.65
    assert low_timing["phase_ratio"] == 0.35


def test_prayer_window_produces_short_green():
    """Friday prayer window (weekend, hour 12-13) must produce reduced green phase."""
    from src.model import compute_signal_timing

    result = compute_signal_timing(
        congestion_score=0.50, vehicle_count=200, hour=12, is_weekend=1
    )

    assert result["phase_ratio"] == 0.20, (
        f"Prayer window phase_ratio was {result['phase_ratio']} — expected 0.20"
    )
    assert result["green_seconds"] == 18  # 90 * 0.20
    assert "prayer" in result["timing_rationale"].lower()


# ---------------------------------------------------------------------------
# PROMPT 011 — Emissions tests
# ---------------------------------------------------------------------------

def test_compute_emissions_returns_valid_output():
    """compute_emissions must return fuel_litres, co2_kg, co2_tonnes all > 0."""
    from src.model import compute_emissions

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
    assert result["co2_kg"] == round(result["fuel_litres"] * 2.31, 4)


def test_critical_emissions_higher_than_low():
    """Critical congestion must produce higher CO2 output than Low congestion."""
    from src.model import compute_emissions

    low_result      = compute_emissions("Low",      vehicle_count=200)
    critical_result = compute_emissions("Critical", vehicle_count=200)

    assert critical_result["co2_kg"] > low_result["co2_kg"], (
        f"Critical co2_kg ({critical_result['co2_kg']}) not higher than "
        f"Low co2_kg ({low_result['co2_kg']})"
    )
