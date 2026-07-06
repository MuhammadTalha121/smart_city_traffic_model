"""What-If Scenario Simulator for traffic impact analysis."""


import json
import os
import uuid
from datetime import datetime



import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any

from src.config import (
    WEATHER_SPEED_IMPACT,
    SCENARIO_VEHICLE_COUNT_CLIP_MAX,
    SCENARIO_SPEED_CLIP_MIN,
    SCENARIO_SPEED_CLIP_MAX,
)

SCENARIOS_LOG_PATH = "scenarios_log.csv"


def _log_scenario(city: str, scenario: dict, hours_ahead: int, result: dict) -> None:
    """Append-only log of scenario runs to scenarios_log.csv. Never raises."""
    try:
        row = {
            "timestamp": datetime.now().isoformat(),
            "session_id": str(uuid.uuid4()),
            "city": city,
            "scenario_summary": json.dumps(scenario)[:2000],
            "worst_impact_zone": result.get("worst_impact_zone", ""),
            "max_delta": result.get("impact_delta", {}).get(result.get("worst_impact_zone", ""), 0.0),
            "hours_ahead": hours_ahead,
            "recommendation": result.get("recommendation", ""),
        }
        from src.training import training_log_path
        log_path = training_log_path(SCENARIOS_LOG_PATH)
        log_df = pd.DataFrame([row])
        write_header = not os.path.exists(log_path)
        log_df.to_csv(log_path, mode="a", header=write_header, index=False)
    except Exception:
        pass


def apply_scenario(df: pd.DataFrame, scenario: dict) -> pd.DataFrame:
    """Apply a what-if scenario to a traffic DataFrame without mutating input.

    Scenario keys:
      - zone_closures:    List[str]          → vehicle_count = 0
      - speed_reductions: Dict[str, float]   → zone → factor (e.g. 0.5 = halve speed)
      - demand_shifts:    Dict[str, float]   → zone → multiplier
      - event_override:   Optional[str]      → weather override for all rows
    """
    result = df.copy(deep=True)

    zone_closures    = scenario.get("zone_closures", [])
    speed_reductions = scenario.get("speed_reductions", {})
    demand_shifts    = scenario.get("demand_shifts", {})
    event_override   = scenario.get("event_override", None)

    for zone in zone_closures:
        mask = result["zone"] == zone
        result.loc[mask, "vehicle_count"] = 0

    for zone, factor in speed_reductions.items():
        mask = result["zone"] == zone
        result.loc[mask, "avg_speed"] *= factor
        result.loc[mask, "avg_speed"] = result.loc[mask, "avg_speed"].clip(
            lower=SCENARIO_SPEED_CLIP_MIN, upper=SCENARIO_SPEED_CLIP_MAX
        )

    for zone, multiplier in demand_shifts.items():
        mask = result["zone"] == zone
        result.loc[mask, "vehicle_count"] *= multiplier
        result.loc[mask, "vehicle_count"] = result.loc[mask, "vehicle_count"].clip(
            lower=0, upper=SCENARIO_VEHICLE_COUNT_CLIP_MAX
        )

    if event_override is not None:
        result["weather"] = event_override
        if event_override in WEATHER_SPEED_IMPACT:
            impact = WEATHER_SPEED_IMPACT[event_override]
            result["avg_speed"] *= impact
            result["avg_speed"] = result["avg_speed"].clip(
                lower=SCENARIO_SPEED_CLIP_MIN, upper=SCENARIO_SPEED_CLIP_MAX
            )

    # --- Recompute congestion_score based on modified vehicle_count and avg_speed ---
    max_vehicles = result["vehicle_count"].max()
    max_speed = result["avg_speed"].max()
    if max_vehicles > 0 and max_speed > 0:
        result["congestion_score"] = (
            (result["vehicle_count"] / max_vehicles) *
            (1 - result["avg_speed"] / max_speed)
        ).clip(0, 1)
    else:
        result["congestion_score"] = 0.0

    return result


def run_scenario(city: str, scenario: dict, hours_ahead: int = 3) -> dict:
    """Run baseline + scenario forecasts and compute impact delta."""
    from app import app
    from src.model import forecast_congestion

    city_df = app.state.city_dfs.get(city)
    if city_df is None:
        raise ValueError(f"City '{city}' not found in app.state.city_dfs")

    zones = city_df["zone"].unique().tolist()

    baseline_df = city_df
    scenario_df = apply_scenario(city_df, scenario)

    baseline_forecasts = {}
    scenario_forecasts = {}
    impact_delta       = {}

    for zone in zones:
        zone_baseline = baseline_df[baseline_df["zone"] == zone]
        zone_scenario = scenario_df[scenario_df["zone"] == zone]

        if zone_baseline.empty or zone_scenario.empty:
            continue

        hours_list = list(range(1, hours_ahead + 1))
        b_pred = forecast_congestion(zone_baseline, zone, hours_list)
        s_pred = forecast_congestion(zone_scenario, zone, hours_list)

        b_scores = [p["predicted_score"] for p in b_pred]
        s_scores = [p["predicted_score"] for p in s_pred]

        baseline_forecasts[zone] = b_scores
        scenario_forecasts[zone] = s_scores

        avg_delta = (
            sum(s_scores) / len(s_scores) - sum(b_scores) / len(b_scores)
            if b_scores and s_scores else 0.0
        )
        impact_delta[zone] = round(avg_delta, 4)

    worst_impact_zone = max(impact_delta, key=impact_delta.get) if impact_delta else ""
    max_delta = impact_delta.get(worst_impact_zone, 0.0)

    if max_delta > 0.15:
        recommendation = (
            f"Critical impact in {worst_impact_zone}: congestion worsens by {max_delta:.2f}. "
            "Deploy diversion and signal retiming."
        )
    elif max_delta > 0.05:
        recommendation = (
            f"Moderate impact in {worst_impact_zone}: congestion worsens by {max_delta:.2f}. "
            "Monitor closely and prepare contingency."
        )
    elif max_delta < -0.05:
        recommendation = (
            f"Positive impact in {worst_impact_zone}: congestion improves by {abs(max_delta):.2f}. "
            "Scenario is beneficial."
        )
    else:
        recommendation = "Minimal net impact across all zones. No immediate action required."

    

    _log_scenario(city, scenario, hours_ahead, {
        "worst_impact_zone": worst_impact_zone,
        "impact_delta": impact_delta,
        "recommendation": recommendation,
    })

    return {
        "baseline_forecasts": baseline_forecasts,
        "scenario_forecasts": scenario_forecasts,
        "impact_delta": impact_delta,
        "worst_impact_zone": worst_impact_zone,
        "recommendation": recommendation,
    }






INCIDENTS_LOG_PATH = "incidents_log.csv"
PREDICTIONS_LOG_PATH = "predictions_log.csv"

def replay_incident(incident_id: int, speed_multiplier: float = 1.0) -> Dict[str, Any]:
    """
    Replay a historical incident as a training scenario.

    Parameters
    ----------
    incident_id : int
        0‑based row index in incidents_log.csv (after header).
    speed_multiplier : float
        Playback speed multiplier (client‑side, returned for reference).

    Returns
    -------
    dict
        {
            "incident": {timestamp, city, zone, severity, clearance_mins},
            "frames": [ {timestamp, zone, hour, vehicle_count, avg_speed,
                         congestion_score, congestion_level}, ... ],
            "speed_multiplier": float,
            "total_frames": int
        }

    Raises
    ------
    ValueError
        If incident_id is out of range or required files are missing.
    """
    # 1. Read incidents log
    if not os.path.exists(INCIDENTS_LOG_PATH):
        raise ValueError("incidents_log.csv not found – no incidents to replay.")

    inc_df = pd.read_csv(INCIDENTS_LOG_PATH)
    if incident_id < 0 or incident_id >= len(inc_df):
        raise ValueError(f"incident_id {incident_id} out of range (0..{len(inc_df)-1})")

    inc_row = inc_df.iloc[incident_id]
    city = inc_row["city"]
    zone = inc_row["zone"]
    severity = inc_row["severity"]
    clearance_mins = float(inc_row["clearance_mins"])
    inc_timestamp_str = inc_row["timestamp"]
    inc_timestamp = pd.to_datetime(inc_timestamp_str)

    # 2. Load predictions log
    if not os.path.exists(PREDICTIONS_LOG_PATH):
        raise ValueError("predictions_log.csv not found – cannot reconstruct zone states.")

    pred_df = pd.read_csv(PREDICTIONS_LOG_PATH)
    # Ensure timestamp column is datetime
    pred_df["timestamp"] = pd.to_datetime(pred_df["timestamp"], errors="coerce")
    pred_df = pred_df.dropna(subset=["timestamp"])

    # 3. Filter predictions for same city and zone, within time window
    # Window: 30 min before incident to 15 min after clearance
    start_time = inc_timestamp - timedelta(minutes=30)
    end_time = inc_timestamp + timedelta(minutes=clearance_mins + 15)

    mask = (
        (pred_df["city"] == city) &
        (pred_df["zone"] == zone) &
        (pred_df["timestamp"] >= start_time) &
        (pred_df["timestamp"] <= end_time)
    )
    filtered = pred_df[mask].copy()
    filtered = filtered.sort_values("timestamp")

    if filtered.empty:
        # Fallback: if no predictions in window, return a single frame using the incident row itself
        # We'll construct a minimal frame from the incident data (but we lack vehicle_count/avg_speed)
        # So we'll raise an error or return a placeholder.
        raise ValueError("No prediction records found for the incident time window.")

    # 4. Build frames
    frames = []
    # We need vehicle_count and avg_speed – get from app.state.city_dfs if available
    city_df = None
    try:
        # Avoid circular import by importing app inside function
        from app import app
        if hasattr(app.state, "city_dfs") and city in app.state.city_dfs:
            city_df = app.state.city_dfs[city]
    except Exception:
        pass

    for _, row in filtered.iterrows():
        ts = row["timestamp"]
        hour = int(row.get("hour", ts.hour))
        congestion_score = float(row["congestion_score"])
        congestion_level = str(row["congestion_level"])

        # Attempt to get vehicle_count and avg_speed from city_df for that zone and hour
        vehicle_count = None
        avg_speed = None
        if city_df is not None:
            zone_rows = city_df[(city_df["zone"] == zone) & (city_df["hour"] == hour)]
            if not zone_rows.empty:
                # Use the first matching row (should be one per hour)
                vehicle_count = float(zone_rows.iloc[0]["vehicle_count"])
                avg_speed = float(zone_rows.iloc[0]["avg_speed"])

        frames.append({
            "timestamp": ts.isoformat(),
            "zone": zone,
            "hour": hour,
            "vehicle_count": vehicle_count,
            "avg_speed": avg_speed,
            "congestion_score": congestion_score,
            "congestion_level": congestion_level,
        })

    # 5. Prepare result
    return {
        "incident": {
            "timestamp": inc_timestamp.isoformat(),
            "city": city,
            "zone": zone,
            "severity": severity,
            "clearance_mins": clearance_mins,
        },
        "frames": frames,
        "speed_multiplier": speed_multiplier,
        "total_frames": len(frames),
    }