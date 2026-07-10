"""Construction zone data model for dynamic road capacity reduction."""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from src.config import (
    CONSTRUCTION_ZONES_FILE,
    CONSTRUCTION_MIN_CAPACITY_FRACTION,
    ZONE_ADJACENCY,
)

VALID_ZONES = list(ZONE_ADJACENCY.keys())


@dataclass
class ConstructionZone:
    """Active or scheduled roadwork."""

    id: str
    zone: str
    road_name: str
    start_date: str          # ISO date (YYYY-MM-DD)
    end_date: str            # ISO date
    start_hour: int          # 0-23
    end_hour: int            # 0-23
    lanes_closed: int        # number of lanes closed
    total_lanes: int         # total lanes originally
    capacity_reduction_pct: float  # 0-100, overrides lanes calculation if set
    description: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_active(self) -> bool:
        """Check if this construction is currently active."""
        from datetime import datetime as dt
        now = dt.now()
        today = now.strftime("%Y-%m-%d")
        current_hour = now.hour
        return self.start_date <= today <= self.end_date and self.start_hour <= current_hour < self.end_hour

    @property
    def capacity_multiplier(self) -> float:
        """
        Return the multiplier to apply to base road capacity.
        If capacity_reduction_pct is set, use it directly.
        Otherwise, calculate from lanes_closed / total_lanes.
        """
        if self.capacity_reduction_pct > 0:
            reduction = self.capacity_reduction_pct / 100.0
        else:
            if self.total_lanes <= 0:
                return 1.0
            reduction = self.lanes_closed / self.total_lanes
        multiplier = max(1.0 - reduction, CONSTRUCTION_MIN_CAPACITY_FRACTION)
        return round(multiplier, 3)


def _load_construction_zones() -> Dict[str, ConstructionZone]:
    """Load construction zones from JSON file."""
    if not os.path.exists(CONSTRUCTION_ZONES_FILE):
        return {}
    try:
        with open(CONSTRUCTION_ZONES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        zones = {}
        for key, value in data.items():
            zones[key] = ConstructionZone(**value)
        return zones
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def _save_construction_zones(zones: Dict[str, ConstructionZone]) -> None:
    """Save construction zones to JSON file."""
    data = {k: asdict(v) for k, v in zones.items()}
    with open(CONSTRUCTION_ZONES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def add_construction_zone(
    zone: str,
    road_name: str,
    start_date: str,
    end_date: str,
    start_hour: int,
    end_hour: int,
    lanes_closed: int = 1,
    total_lanes: int = 2,
    capacity_reduction_pct: float = 0.0,
    description: str = "",
) -> dict:
    """
    Add a new construction zone to the registry.

    Returns:
        dict with construction zone ID and metadata including capacity_multiplier.
    """
    # Validate zone
    if zone not in VALID_ZONES:
        raise ValueError(f"Unknown zone '{zone}'. Valid zones: {VALID_ZONES}")

    # Validate date format and range
    try:
        datetime.fromisoformat(start_date)
        datetime.fromisoformat(end_date)
    except ValueError:
        raise ValueError("start_date and end_date must be ISO format (YYYY-MM-DD)")

    if start_date > end_date:
        raise ValueError("start_date must be before or equal to end_date")

    # Validate hours
    if not (0 <= start_hour <= 23) or not (0 <= end_hour <= 23):
        raise ValueError("start_hour and end_hour must be between 0 and 23")
    if start_hour >= end_hour:
        raise ValueError("start_hour must be less than end_hour")

    # Validate lanes
    if lanes_closed <= 0 or lanes_closed > total_lanes:
        raise ValueError(f"lanes_closed ({lanes_closed}) must be between 1 and total_lanes ({total_lanes})")

    # Generate ID and create zone
    zone_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    construction = ConstructionZone(
        id=zone_id,
        zone=zone,
        road_name=road_name,
        start_date=start_date,
        end_date=end_date,
        start_hour=start_hour,
        end_hour=end_hour,
        lanes_closed=lanes_closed,
        total_lanes=total_lanes,
        capacity_reduction_pct=capacity_reduction_pct,
        description=description,
        created_at=now,
        updated_at=now,
    )

    zones = _load_construction_zones()
    zones[zone_id] = construction
    _save_construction_zones(zones)

    # Return dict with capacity_multiplier included as a computed field
    result = asdict(construction)
    result["capacity_multiplier"] = construction.capacity_multiplier
    return result

def get_active_construction(city: str = None, timestamp: datetime = None) -> List[dict]:
    """
    Return all construction zones active at the given timestamp.
    If timestamp is None, uses current time.
    """
    if timestamp is None:
        from datetime import datetime as dt
        timestamp = dt.now()

    zones = _load_construction_zones()
    active = []
    for zone in zones.values():
        if zone.is_active:
            # Check if zone's city matches (if city filter provided)
            # For now, we assume all zones are in Riyadh or the city passed is used for filtering
            active.append(asdict(zone))
    return active


def apply_construction_capacity(
    base_capacity_vph: float,
    zone: str,
    timestamp: datetime = None
) -> float:
    """
    Apply construction capacity reduction to a zone's base capacity.
    Returns reduced capacity (never below CONSTRUCTION_MIN_CAPACITY_FRACTION * base).
    """
    if timestamp is None:
        from datetime import datetime as dt
        timestamp = dt.now()

    # Find active construction in this zone
    zones = _load_construction_zones()
    for cz in zones.values():
        if cz.zone == zone and cz.is_active:
            multiplier = cz.capacity_multiplier
            reduced = base_capacity_vph * multiplier
            min_capacity = base_capacity_vph * CONSTRUCTION_MIN_CAPACITY_FRACTION
            return max(reduced, min_capacity)

    # No active construction
    return base_capacity_vph


def update_construction_zone(zone_id: str, **kwargs) -> dict:
    """Update an existing construction zone."""
    zones = _load_construction_zones()
    if zone_id not in zones:
        raise ValueError(f"Construction zone '{zone_id}' not found.")

    cz = zones[zone_id]
    for key, value in kwargs.items():
        if hasattr(cz, key) and key not in ("id", "created_at"):
            setattr(cz, key, value)
    cz.updated_at = datetime.now().isoformat()
    _save_construction_zones(zones)
    return asdict(cz)


def delete_construction_zone(zone_id: str) -> bool:
    """Delete a construction zone by ID."""
    zones = _load_construction_zones()
    if zone_id not in zones:
        return False
    del zones[zone_id]
    _save_construction_zones(zones)
    return True


def get_construction_zone(zone_id: str) -> Optional[dict]:
    """Retrieve a single construction zone by ID."""
    zones = _load_construction_zones()
    cz = zones.get(zone_id)
    return asdict(cz) if cz else None