"""
GTFS-RT shaped export (PROMPT 100).

Scope: VehiclePositions and TripUpdates feed entity types only. Alerts,
Shapes, and Trip Modifications are out of scope.

This is a "GTFS-RT shaped" JSON export, NOT a GTFS-RT compliant feed:
  - Real GTFS-RT is serialized as binary Protocol Buffers (FeedMessage),
    not JSON. Protobuf encoding is explicitly deferred (see gapNote).
  - A real feed requires a companion GTFS Static feed (routes.txt,
    trips.txt, stops.txt) to resolve trip_id/stop_id/route_id against.
    This system has no static GTFS feed, so trip_id/stop_id values here
    are synthesized (e.g. "DRT-{shuttle_id}", zone names as stop_id)
    rather than referencing a real GTFS Static dataset.

Specification reference: GTFS-Realtime Reference, gtfs_realtime_version
"2.0", FeedMessage = FeedHeader + repeated FeedEntity, where each
FeedEntity carries at most one of {vehicle, trip_update, alert}
(https://gtfs.org/documentation/realtime/reference/, Google's 2015
combined-feed-entity proposal). VehiclePosition fields used here:
trip{trip_id, schedule_relationship}, position{latitude, longitude,
bearing, speed}, timestamp, vehicle{id}. TripUpdate fields used here:
trip{trip_id, schedule_relationship}, stop_time_update[]{stop_id,
arrival{delay, uncertainty}}, timestamp.

Data sources:
  - VehiclePosition: app.state.last_drt_allocation (PROMPT 059 DRT
    trips). Same known limitation as src/siri_export.py — DRT has no
    persistent fleet-position state, so this reflects the most recent
    allocation, not live GPS. If no allocation has run yet, the
    vehicle list is empty rather than synthesized.
  - TripUpdate: forecast_congestion() per zone (src/model.py),
    +1h horizon. "Delay" is a derived proxy from predicted congestion
    level, not a measured schedule deviation — clearly labeled as such
    in the gapNote, since GTFS-RT delay semantics assume a real
    schedule to deviate from, which this system does not have.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from src.config import ZONE_CENTROIDS, ZONE_DISTANCES_KM

GTFS_RT_VERSION = "2.0"

# Congestion level -> synthetic schedule delay proxy, in seconds.
# Not a measured delay (no real schedule exists) — a deliberate stand-in
# so downstream GTFS-RT consumers (e.g. Google Maps ingestion testing)
# see directionally correct behavior: worse congestion -> larger delay.
_CONGESTION_DELAY_SECONDS = {
    "Low": 0,
    "Moderate": 60,
    "High": 180,
    "Critical": 360,
}


def _now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def to_gtfs_vehicle_position(drt_record: dict) -> dict:
    """
    Maps one DRTAllocator trip dict (shuttle_id, passengers, route,
    estimated_wait_mins, estimated_journey_mins) to a GTFS-RT
    VehiclePosition-shaped FeedEntity.

    Position is taken from the trip's origin zone centroid (the
    DRT shuttle's current/starting point); speed is derived from the
    route's total distance over estimated_journey_mins where both are
    available, else omitted (None) rather than fabricated.
    """
    route = drt_record.get("route", [])
    shuttle_id = drt_record.get("shuttle_id", "UNKNOWN")
    origin_zone = route[0] if route else "Zone_1"
    lon, lat = ZONE_CENTROIDS.get(origin_zone, [46.7, 24.7])

    journey_mins = drt_record.get("estimated_journey_mins")
    speed_mps = None
    if journey_mins and journey_mins > 0 and len(route) > 1:
        total_km = 0.0
        for i in range(len(route) - 1):
            key = tuple(sorted([route[i], route[i + 1]]))
            total_km += ZONE_DISTANCES_KM.get(key, 0.0)
        if total_km > 0:
            speed_mps = round((total_km * 1000) / (journey_mins * 60), 2)

    return {
        "id": f"vehicle-{shuttle_id}",
        "vehicle": {
            "trip": {
                "trip_id": f"DRT-{shuttle_id}",
                "schedule_relationship": "ADDED",
            },
            "position": {
                "latitude": lat,
                "longitude": lon,
                "bearing": None,
                "speed": speed_mps,
            },
            "vehicle": {
                "id": shuttle_id,
                "label": f"DRT Shuttle {shuttle_id}",
            },
            "occupancy_status": (
                "FEW_SEATS_AVAILABLE"
                if drt_record.get("passengers", 0) > 0
                else "EMPTY"
            ),
            "timestamp": _now_epoch(),
        },
    }


def to_gtfs_trip_update(forecast_record: dict, zone: str) -> dict:
    """
    Maps one forecast_congestion() entry (hours_ahead, forecast_hour,
    predicted_score, congestion_level, ...) for a given zone into a
    GTFS-RT TripUpdate-shaped FeedEntity with a single StopTimeUpdate.

    delay is a congestion-level-derived proxy (see module docstring),
    NOT a measured schedule deviation. uncertainty is derived from the
    forecast's confidence band (upper_bound - lower_bound) scaled into
    seconds, consistent with GTFS-RT's uncertainty semantics (wider
    band = less certain prediction).
    """
    level = forecast_record.get("congestion_level", "Low")
    delay_s = _CONGESTION_DELAY_SECONDS.get(level, 0)

    band = forecast_record.get("upper_bound", 0.0) - forecast_record.get("lower_bound", 0.0)
    uncertainty_s = int(round(band * 600))  # 0-1 confidence band -> 0-600s proxy

    hours_ahead = forecast_record.get("hours_ahead", 1)

    return {
        "id": f"tripupdate-{zone}-{hours_ahead}h",
        "trip_update": {
            "trip": {
                "trip_id": f"ROUTE-{zone}",
                "schedule_relationship": "SCHEDULED",
            },
            "stop_time_update": [
                {
                    "stop_id": zone,
                    "arrival": {
                        "delay": delay_s,
                        "uncertainty": uncertainty_s,
                    },
                }
            ],
            "timestamp": _now_epoch(),
        },
    }


def generate_gtfs_rt_feed(city: str) -> dict:
    """
    Full GTFS-RT shaped feed for a city: VehiclePositions (from the
    last DRT allocation) + TripUpdates (from +1h congestion forecast
    per zone). Returns a single combined FeedMessage-shaped dict per
    Google's 2015 combined-entity proposal, rather than two separate
    feeds, since this system already serves one JSON endpoint.
    """
    from app import app
    from src.model import forecast_congestion

    entities: List[Dict[str, Any]] = []

    # --- VehiclePositions from last DRT allocation ---
    drt_cache = getattr(app.state, "last_drt_allocation", {}).get(city, {})
    for trip in drt_cache.get("trips", []):
        entities.append(to_gtfs_vehicle_position(trip))

    # --- TripUpdates from +1h forecast per zone ---
    city_df = app.state.city_dfs.get(city) if hasattr(app.state, "city_dfs") else None
    if city_df is not None:
        for zone in sorted(city_df["zone"].unique()):
            zone_df = city_df[city_df["zone"] == zone]
            if zone_df.empty:
                continue
            forecasts = forecast_congestion(zone_df, zone=zone, hours_ahead=[1])
            if forecasts:
                entities.append(to_gtfs_trip_update(forecasts[0], zone))

    return {
        "header": {
            "gtfs_realtime_version": GTFS_RT_VERSION,
            "incrementality": "FULL_DATASET",
            "timestamp": _now_epoch(),
        },
        "entity": entities,
        "gapNote": (
            "GTFS-RT SHAPED export, not GTFS-RT compliant. Differences from "
            "the official spec: (1) serialized as JSON, not binary Protocol "
            "Buffers; (2) no companion GTFS Static feed exists, so trip_id/"
            "stop_id values are synthesized rather than resolved against "
            "routes.txt/trips.txt/stops.txt; (3) TripUpdate.delay is a "
            "congestion-level-derived proxy, not a measured deviation from "
            "a real published schedule, since no such schedule exists in "
            "this system; (4) VehiclePosition reflects the most recent DRT "
            "allocation snapshot, not continuous live GPS telemetry."
        ),
    }
