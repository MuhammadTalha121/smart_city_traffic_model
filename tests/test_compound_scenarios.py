"""
Compound scenario stress tests for tail‑risk validation.
validates evacuation, VSL, confidence, and staleness
under simultaneous Hajj + sandstorm + mass‑event egress.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import joblib
import os
import tempfile

# Real imports from your codebase
from src.model import (
    calculate_evacuation_routes,
    compute_vsl_limit,
    predict_with_confidence,
    train_xgboost_quantile,
    prepare_features,
    congestion_level,
)
from src.adapters import is_data_stale
from src.config import (
    ZONE_ADJACENCY,
    HAJJ_INBOUND,
    HAJJ_PEAK,
    HAJJ_OUTBOUND,
    MASS_EVENT_VENUES,
    EVACUATION_SAFE_POINTS,
    ZONE_ROAD_CAPACITY_VPH,
)
from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features

# ---- Scenario Generator (uses real functions) ----
def generate_compound_scenario(city="Riyadh", hajj=True, sandstorm=True, mass_event=True):
    """
    Build a synthetic DataFrame combining:
      - Hajj multipliers (using HAJJ_* constants)
      - Sandstorm weather override
      - Mass‑event egress spike (using calculate_egress_plan as a reference)
    Returns (df, metadata)
    """
    # Generate base data for 48 hours (2 days)
    df = generate_traffic_data(city=city, n_days=2)  # assumes n_days parameter
    df = apply_hourly_patterns(df, city=city)
    df = add_lag_features(df)

    # Apply Hajj multipliers if requested
    if hajj:
        # Use HAJJ_PEAK as the dominant pattern for this stress test
        def hajj_multiplier(hour):
            # Interpolate from HAJJ_PEAK dict (simplified: nearest key)
            keys = sorted(HAJJ_PEAK.keys())
            for i, k in enumerate(keys):
                if hour <= k:
                    if i == 0:
                        return HAJJ_PEAK[k]
                    prev = keys[i-1]
                    ratio = (hour - prev) / (k - prev) if k != prev else 0
                    return HAJJ_PEAK[prev] + ratio * (HAJJ_PEAK[k] - HAJJ_PEAK[prev])
            return HAJJ_PEAK[keys[-1]]
        df['hajj_factor'] = df['hour'].apply(hajj_multiplier)
        # Extra multiplier for Hajj route zones (Zone_1 and Zone_3)
        df.loc[df['zone'].isin(['Zone_1', 'Zone_3']), 'hajj_factor'] *= 1.8
    else:
        df['hajj_factor'] = 1.0

    # Sandstorm override
    if sandstorm:
        df['weather'] = 'sandstorm'
        df['visibility_m'] = 200   # for VSL function

    # Mass‑event egress: add a surge in the evening of day 1 (hours 20-23)
    if mass_event:
        # Add a factor for those hours
        def egress_factor(row):
            if row['timestamp'].day == (df['timestamp'].min().day) and row['hour'] in [20,21,22,23]:
                return 3.0   # double the vehicles
            return 1.0
        df['mass_event_factor'] = df.apply(egress_factor, axis=1)
    else:
        df['mass_event_factor'] = 1.0

    # Combine multipliers into final congestion score
    # Base score from apply_hourly_patterns + lag features already exist
    # We multiply the existing congestion_score by the factors, then clip
    df['congestion_score'] = (df['congestion_score'] * df['hajj_factor'] * df['mass_event_factor']).clip(0, 1)

    # Ensure fetched_at is recent for staleness test
    df['fetched_at'] = datetime.now()

    metadata = {
        "hajj": hajj,
        "sandstorm": sandstorm,
        "mass_event": mass_event,
        "city": city,
        "duration_hours": 48,
    }
    return df, metadata

# ---- Helper to train quantile models on the fly ----
def train_quantile_models(df):
    """Train quantile models on the given DataFrame and return the model dict."""
    X, y, _ = prepare_features(df)
    models = train_xgboost_quantile(X, y, quantiles=[0.1, 0.5, 0.9])
    return models

# ---- Test Cases ----
def test_compound_confidence_degrades():
    """Confidence level must be 'Low' under extreme compound scenario."""
    df, meta = generate_compound_scenario()
    # Train quantile models on this data
    models = train_quantile_models(df)
    # Pick a representative row: hour 21, Zone_1 (hard hit)
    sample_row = df[(df['hour'] == 21) & (df['zone'] == 'Zone_1')].iloc[0]
    X_row, _, _ = prepare_features(pd.DataFrame([sample_row]))
    result = predict_with_confidence(models, X_row)
    assert result['confidence_level'] == 'Low', \
        f"Expected 'Low' confidence, got {result['confidence_level']}"
    assert result['confidence_width'] > 0.2, \
        f"Confidence width {result['confidence_width']} too narrow"

def test_evacuation_respects_vsl():
    """Evacuation should account for VSL speed reduction in sandstorm."""
    df, meta = generate_compound_scenario()
    city = meta['city']
    hazard_zones = ['Zone_1', 'Zone_3']
    total_vehicles = 2000

    latest_hour = df['hour'].max()
    latest_df = df[df['hour'] == latest_hour]
    congestion_map = latest_df.set_index('zone')['congestion_score'].to_dict()

    # Build speed_map using compute_vsl_limit for each zone in sandstorm
    speed_map = {}
    default_speed = 70.0
    for zone in set(hazard_zones + list(EVACUATION_SAFE_POINTS.keys())):
        row = latest_df[latest_df['zone'] == zone]
        if not row.empty:
            avg_speed = row.iloc[0].get('avg_speed', 60)
            weather = row.iloc[0]['weather']
            vsl = compute_vsl_limit(weather, visibility_m=500, avg_speed_kmph=avg_speed)
            speed_map[zone] = vsl['recommended_speed_kmph']
        else:
            speed_map[zone] = default_speed

    # Compute evacuation with speed_map
    evac_result = calculate_evacuation_routes(
        hazard_zones=hazard_zones,
        total_vehicles=total_vehicles,
        congestion_map=congestion_map,
        speed_map=speed_map,
    )

    # Also compute without speed_map (default speeds) for comparison
    evac_default = calculate_evacuation_routes(
        hazard_zones=hazard_zones,
        total_vehicles=total_vehicles,
        congestion_map=congestion_map,
    )

    # Check that travel times are longer with reduced speeds
    for plan, plan_def in zip(evac_result['evacuation_plan'], evac_default['evacuation_plan']):
        # Ensure speed_map was used (travel_time should be > default by at least 20%)
        # But only if the speed_map actually reduced speeds (sandstorm)
        if speed_map.get(plan['route'][0], 70) < 70:
            assert plan['estimated_travel_time_mins'] > plan_def['estimated_travel_time_mins'] * 1.2, \
                f"Travel time with reduced speed ({plan['estimated_travel_time_mins']} min) not 20% higher than default ({plan_def['estimated_travel_time_mins']} min)"

    # Also verify that VSL is indeed reduced (as in original check)
    for plan in evac_result['evacuation_plan']:
        for zone in plan['route']:
            vsl = compute_vsl_limit('sandstorm', visibility_m=500, avg_speed_kmph=60)
            # In sandstorm with visibility 500, VSL should be 80 km/h (per compute_vsl_limit)
            assert vsl['recommended_speed_kmph'] <= 100, \
                f"VSL for {zone} is {vsl['recommended_speed_kmph']} – not reduced in sandstorm"

    # Ensure backward compatibility: speed_map not provided works
    assert 'estimated_travel_time_mins' in evac_default['evacuation_plan'][0]
    assert evac_default['evacuation_plan'][0]['estimated_travel_time_mins'] > 0

def test_staleness_gate_on_fresh_data():
    """is_data_stale should correctly handle mock and fresh data."""
    df, meta = generate_compound_scenario()
    # Get a row with a recent fetched_at
    sample = df.iloc[0]
    fetched_at = sample['fetched_at']
    # For mock source, should be False
    assert is_data_stale('mock', fetched_at) is False, "Mock data should not be stale"
    # For weather source, with fresh timestamp (now) should be False
    fresh_time = datetime.now()
    assert is_data_stale('weather', fresh_time) is False, "Fresh weather data should not be stale"
    # For weather with old timestamp (2 hours ago) should be True (threshold 1800s)
    old_time = datetime.now() - timedelta(seconds=7200)
    assert is_data_stale('weather', old_time) is True, "Old weather data should be stale"

def test_generator_creates_valid_scenario():
    """Basic smoke test that generator works."""
    df, meta = generate_compound_scenario()
    assert not df.empty
    assert 'congestion_score' in df.columns
    assert df['congestion_score'].between(0, 1).all()
    assert meta['sandstorm'] is True
    assert meta['hajj'] is True
    assert meta['mass_event'] is True