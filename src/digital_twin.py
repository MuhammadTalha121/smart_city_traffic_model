"""Digital Twin State Sync – immutable snapshots of city traffic states."""

import uuid
from datetime import datetime
from typing import Dict, Optional
import pandas as pd

from src.simulator import apply_scenario


MAX_TWINS_PER_CITY = 10


class DigitalTwinState:
    """
    An immutable snapshot of one city's traffic state at a specific timestamp.
    Modifications produce a new state.
    """

    def __init__(self, city: str, snapshot_df: pd.DataFrame, timestamp: Optional[str] = None):
        self.city = city
        self.snapshot_df = snapshot_df.copy(deep=True)  # ensure immutability
        self.timestamp = timestamp or datetime.now().isoformat()

    def apply_intervention(self, intervention: dict) -> "DigitalTwinState":
        """
        Returns a NEW DigitalTwinState with the intervention applied.
        Never mutates self.
        """
        modified_df = apply_scenario(self.snapshot_df, intervention)
        return DigitalTwinState(
            city=self.city,
            snapshot_df=modified_df,
            timestamp=datetime.now().isoformat()
        )

    def to_dict(self) -> dict:
        """Serializable representation for API responses."""
        return {
            "city": self.city,
            "timestamp": self.timestamp,
            "zone_count": self.snapshot_df["zone"].nunique() if "zone" in self.snapshot_df.columns else 0,
            "row_count": len(self.snapshot_df),
            # Include a summary of congestion per zone (optional)
            "summary": {
                "avg_congestion": float(self.snapshot_df["congestion_score"].mean()) if "congestion_score" in self.snapshot_df.columns else None,
                "max_congestion": float(self.snapshot_df["congestion_score"].max()) if "congestion_score" in self.snapshot_df.columns else None,
            }
        }

    def __repr__(self):
        return f"DigitalTwinState(city={self.city}, timestamp={self.timestamp}, rows={len(self.snapshot_df)})"


def create_twin(city: str, app_state) -> DigitalTwinState:
    """
    Factory to create a twin from the current live city state.
    Also enforces the per‑city limit (max 10 twins) by evicting the oldest.
    """
    city_df = app_state.city_dfs.get(city)
    if city_df is None:
        raise ValueError(f"City '{city}' not found in app state.")

    # Ensure the digital_twins dict exists
    if not hasattr(app_state, "digital_twins"):
        app_state.digital_twins = {}

    # Group by city to enforce limit
    twins_by_city = {cid: {} for cid in app_state.city_dfs.keys()}
    for tid, twin in app_state.digital_twins.items():
        twins_by_city.setdefault(twin.city, {})[tid] = twin

    city_twins = twins_by_city.get(city, {})
    # Evict oldest if limit reached
    if len(city_twins) >= MAX_TWINS_PER_CITY:
        # Sort by timestamp (oldest first)
        sorted_twins = sorted(city_twins.items(), key=lambda kv: kv[1].timestamp)
        oldest_tid = sorted_twins[0][0]
        del app_state.digital_twins[oldest_tid]
        print(f"[DigitalTwin] Evicted oldest twin {oldest_tid} for {city} (limit {MAX_TWINS_PER_CITY})")

    # Create new twin
    twin = DigitalTwinState(city, city_df)
    twin_id = str(uuid.uuid4())
    app_state.digital_twins[twin_id] = twin
    return twin_id, twin


import uuid

def run_what_if_on_twin(twin: DigitalTwinState, scenario: dict, hours_ahead: int = 3, app_state=None) -> dict:
    """
    Apply scenario to a twin, run forecasts, and store the modified twin.
    Returns comparison dict including the modified twin's ID.
    """
    from src.model import forecast_congestion

    # Apply scenario to create a new twin
    modified_twin = twin.apply_intervention(scenario)

    # Store the modified twin if app_state is provided
    modified_twin_id = None
    if app_state is not None:
        if not hasattr(app_state, "digital_twins"):
            app_state.digital_twins = {}
        # Generate a new ID
        new_id = str(uuid.uuid4())
        app_state.digital_twins[new_id] = modified_twin
        modified_twin_id = new_id

    # Get zones
    zones = twin.snapshot_df["zone"].unique().tolist() if "zone" in twin.snapshot_df.columns else []

    baseline_forecasts = {}
    scenario_forecasts = {}
    impact_delta = {}

    for zone in zones:
        baseline_df = twin.snapshot_df[twin.snapshot_df["zone"] == zone]
        scenario_df = modified_twin.snapshot_df[modified_twin.snapshot_df["zone"] == zone]

        if baseline_df.empty or scenario_df.empty:
            continue

        hours_list = list(range(1, hours_ahead + 1))
        b_pred = forecast_congestion(baseline_df, zone, hours_list)
        s_pred = forecast_congestion(scenario_df, zone, hours_list)

        b_scores = [p["predicted_score"] for p in b_pred]
        s_scores = [p["predicted_score"] for p in s_pred]

        baseline_forecasts[zone] = b_scores
        scenario_forecasts[zone] = s_scores

        avg_delta = sum(s_scores) / len(s_scores) - sum(b_scores) / len(b_scores) if b_scores and s_scores else 0.0
        impact_delta[zone] = round(avg_delta, 4)

    worst_impact_zone = max(impact_delta, key=impact_delta.get) if impact_delta else ""
    max_delta = impact_delta.get(worst_impact_zone, 0.0)

    if max_delta > 0.15:
        recommendation = f"Critical impact in {worst_impact_zone}: congestion worsens by {max_delta:.2f}. Deploy diversion."
    elif max_delta > 0.05:
        recommendation = f"Moderate impact in {worst_impact_zone}: congestion worsens by {max_delta:.2f}. Monitor closely."
    elif max_delta < -0.05:
        recommendation = f"Positive impact in {worst_impact_zone}: congestion improves by {abs(max_delta):.2f}. Scenario beneficial."
    else:
        recommendation = "Minimal net impact across all zones. No immediate action required."

    return {
        "baseline_twin_id": getattr(twin, "twin_id", "unknown"),
        "modified_twin_id": modified_twin_id,
        "modified_twin_metadata": modified_twin.to_dict(),
        "baseline_forecasts": baseline_forecasts,
        "scenario_forecasts": scenario_forecasts,
        "impact_delta": impact_delta,
        "worst_impact_zone": worst_impact_zone,
        "recommendation": recommendation,
    }


def compare_twins(twin_a: DigitalTwinState, twin_b: DigitalTwinState) -> dict:
    """Compare two twins by their latest congestion score per zone."""
    if twin_a.city != twin_b.city:
        raise ValueError(f"Twins must be from the same city: {twin_a.city} vs {twin_b.city}")

    zones = set(twin_a.snapshot_df["zone"].unique()) & set(twin_b.snapshot_df["zone"].unique())

    if not zones:
        return {"error": "No common zones found."}

    delta = {}
    for zone in zones:
        a_df = twin_a.snapshot_df[twin_a.snapshot_df["zone"] == zone]
        b_df = twin_b.snapshot_df[twin_b.snapshot_df["zone"] == zone]

        if a_df.empty or b_df.empty:
            continue

        # Get the latest congestion score for each zone (most recent timestamp)
        a_latest = a_df.sort_values("timestamp").iloc[-1] if "timestamp" in a_df.columns else a_df.iloc[-1]
        b_latest = b_df.sort_values("timestamp").iloc[-1] if "timestamp" in b_df.columns else b_df.iloc[-1]

        a_score = float(a_latest.get("congestion_score", 0.0))
        b_score = float(b_latest.get("congestion_score", 0.0))

        delta[zone] = round(b_score - a_score, 4)

    worst_zone = max(delta, key=delta.get) if delta else ""
    best_zone = min(delta, key=delta.get) if delta else ""

    return {
        "twin_a_id": getattr(twin_a, "twin_id", "unknown"),
        "twin_b_id": getattr(twin_b, "twin_id", "unknown"),
        "city": twin_a.city,
        "delta_per_zone": delta,
        "worst_affected_zone": worst_zone,
        "best_affected_zone": best_zone,
        "summary": f"{len(delta)} zones compared. Worst: {worst_zone} ({delta.get(worst_zone, 0):.2f}). Best: {best_zone} ({delta.get(best_zone, 0):.2f})."
    }