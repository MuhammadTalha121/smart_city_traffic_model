"""
SIRI-shaped export for public transport data (CEN/TS 15531).

Scope: SIRI-VM VehicleActivity (from DRT trips) and a SIRI-ET-shaped
EstimatedTimetableDelivery derived from the existing per-zone signal
timing snapshot (compute_signal_timing) plus evaluate_transit_priority().
This is a SIRI-shaped export, not a full SIRI implementation — no XML,
no publish/subscribe, no SIRI-SX/FM/CA.

Known limitation: DRT has no persistent fleet-position state in this
system (DRTAllocator.allocate() runs per-request and its result is not
retained). VehicleActivity is therefore sourced from the most recent
allocation cached on app.state.last_drt_allocation by
/transit/request-shuttle; if no allocation has run yet, the vehicle
list is empty rather than synthesised.

Similarly, TSP has no event log — evaluate_transit_priority() is a
stateless per-call calculation. EstimatedTimetableDelivery here is
derived from a representative bus_distance_m assumption
(TSP_DETECTION_RANGE_M / 2), explicitly labelled as a snapshot
estimate, not a live detection event.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

from src.config import ZONE_CENTROIDS, TSP_DETECTION_RANGE_M
from src.model import evaluate_transit_priority, compute_signal_timing

SIRI_NAMESPACE = "http://www.siri.org.uk/siri"
SIRI_VERSION = "2.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _add_seconds(iso_time: str, seconds: float) -> str:
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        return (dt + timedelta(seconds=seconds)).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (ValueError, TypeError):
        return iso_time


def to_siri_vehicle_activity(trip: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map one DRTAllocator trip dict (shuttle_id, passengers, route,
    estimated_wait_mins, estimated_journey_mins) to SIRI VehicleActivity.
    """
    route = trip.get("route", [])
    origin_zone = route[0] if route else "UNKNOWN"
    dest_zone = route[-1] if route else "UNKNOWN"
    lon, lat = ZONE_CENTROIDS.get(origin_zone, [46.7, 24.7])
    now = _now()

    monitored_journey = {
        "LineRef": f"DRT-{trip.get('shuttle_id', 'UNKNOWN')}",
        "DirectionRef": "1",
        "FramedVehicleJourneyRef": {
            "DataFrameRef": now[:10],
            "DatedVehicleJourneyRef": trip.get("shuttle_id", "UNKNOWN"),
        },
        "VehicleLocation": {"Longitude": lon, "Latitude": lat},
        "VehicleRef": trip.get("shuttle_id", "UNKNOWN"),
        "MonitoredCall": {
            "StopPointRef": origin_zone,
            "VisitNumber": 1,
            "VehicleAtStop": False,
            "DestinationDisplay": dest_zone,
            "ExpectedDepartureTime": _add_seconds(now, trip.get("estimated_wait_mins", 0) * 60),
        },
        "Occupancy": trip.get("passengers", 0),
    }
    return {"RecordedAtTime": now, "MonitoredVehicleJourney": monitored_journey}


def to_siri_estimated_timetable(zone: str, signal_timing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map one zone's compute_signal_timing() output + a representative
    evaluate_transit_priority() check into a SIRI EstimatedTimetableDelivery
    EstimatedVehicleJourney entry. bus_distance_m is a fixed snapshot
    assumption (half of TSP_DETECTION_RANGE_M), not a live detection.
    """
    now = _now()
    tsp = evaluate_transit_priority(
        bus_distance_m=TSP_DETECTION_RANGE_M / 2,
        current_green_remaining_s=signal_timing.get("green_seconds", 0),
        passenger_count=20,
    )
    offset = -tsp["extension_granted_s"] if tsp["extension_granted_s"] else 0
    status = "early" if offset < 0 else "onTime"

    estimated_journey = {
        "LineRef": f"TSP-{zone}",
        "DirectionRef": "1",
        "FramedVehicleJourneyRef": {
            "DataFrameRef": now[:10],
            "DatedVehicleJourneyRef": f"TSP-{zone}-{now[:10]}",
        },
        "EstimatedCalls": {
            "EstimatedCall": [{
                "StopPointRef": zone,
                "Order": 1,
                "AimedArrivalTime": now,
                "ExpectedArrivalTime": _add_seconds(now, offset),
                "ArrivalStatus": status,
            }]
        },
        "PriorityExtensionSeconds": tsp["extension_granted_s"],
    }
    return {"RecordedAtTime": now, "EstimatedVehicleJourney": estimated_journey}


def build_siri_service_delivery(
    vehicle_activities: List[Dict[str, Any]],
    estimated_journeys: List[Dict[str, Any]],
    producer_ref: str,
) -> Dict[str, Any]:
    now = _now()
    delivery: Dict[str, Any] = {"ResponseTimestamp": now, "ProducerRef": producer_ref}

    if vehicle_activities:
        delivery["VehicleMonitoringDelivery"] = {"VehicleActivity": vehicle_activities}

    if estimated_journeys:
        delivery["EstimatedTimetableDelivery"] = {
            "EstimatedJourneyVersionFrame": {
                "RecordedAtTime": now,
                "EstimatedVehicleJourney": [j["EstimatedVehicleJourney"] for j in estimated_journeys],
            }
        }

    return {"Siri": {"xmlns": SIRI_NAMESPACE, "version": SIRI_VERSION, "ServiceDelivery": delivery}}