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