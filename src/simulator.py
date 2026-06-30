"""What-If Scenario Simulator for traffic impact analysis."""


import json
import os
import uuid
from datetime import datetime

import pandas as pd

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
        log_df = pd.DataFrame([row])
        write_header = not os.path.exists(SCENARIOS_LOG_PATH)
        log_df.to_csv(SCENARIOS_LOG_PATH, mode="a", header=write_header, index=False)
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