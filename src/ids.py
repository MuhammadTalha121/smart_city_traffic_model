"""
— Sensor Intrusion Detection System
Validates incoming IoT telemetry against physical plausibility
constraints before readings reach the prediction engine.
"""

from src.config import (
    IDS_MAX_SPEED_KMPH,
    IDS_MAX_VEHICLE_COUNT,
    IDS_NEIGHBORHOOD_VARIANCE_STD,
    IDS_ZERO_TRAFFIC_SUSPECT_HOURS,
)


class SensorIntrusionDetector:
    """
    Validates a single sensor reading against:
      1. Physical impossibility (speed, volume ceilings)
      2. Contextual suspicion (zero traffic during rush hour)
      3. Statistical outlier (deviation from zone historical mean)

    risk_level:
      'Clean'      — no flags
      'Suspicious' — soft flags only; prediction proceeds with warning
      'Blocked'    — any IMPOSSIBLE flag; prediction rejected (422)
    """

    def validate_reading(
        self,
        zone: str,
        hour: int,
        vehicle_count: int,
        avg_speed: float,
        zone_historical_mean: float,
        zone_historical_std: float,
        is_weekend: bool,
    ) -> dict:
        flags: list[str] = []

        # ── Check 1: physically impossible speed ───────────────────────────
        if avg_speed > IDS_MAX_SPEED_KMPH:
            flags.append("SPEED_IMPOSSIBLE")

        # ── Check 2: physically impossible volume ──────────────────────────
        if vehicle_count > IDS_MAX_VEHICLE_COUNT:
            flags.append("VOLUME_IMPOSSIBLE")

        # ── Check 3: suspicious zero during rush hours (weekday only) ──────
        if (
            vehicle_count == 0
            and hour in IDS_ZERO_TRAFFIC_SUSPECT_HOURS
            and not is_weekend
        ):
            flags.append("SUSPICIOUS_ZERO")

        # ── Check 4: statistical outlier vs zone historical baseline ────────
        # Guard: if std is 0 or unknown, skip to avoid division artefacts
        if zone_historical_std > 0:
            deviation = abs(vehicle_count - zone_historical_mean)
            if deviation > IDS_NEIGHBORHOOD_VARIANCE_STD * zone_historical_std:
                flags.append("STATISTICAL_OUTLIER")

        # ── Determine risk level ────────────────────────────────────────────
        impossible_flags = {"SPEED_IMPOSSIBLE", "VOLUME_IMPOSSIBLE"}
        has_impossible   = bool(impossible_flags & set(flags))

        if has_impossible:
            risk_level = "Blocked"
        elif flags:
            risk_level = "Suspicious"
        else:
            risk_level = "Clean"

        return {
            "valid":      risk_level != "Blocked",
            "flags":      flags,
            "risk_level": risk_level,
            "zone":       zone,
            "hour":       hour,
        }