"""
hajj_simulation.py — Hajj 2026 Full Operational Readiness Simulation (Prompt 137).

Pipes a compound stress scenario (crowd density + sandstorm + Friday prayer window)
through the existing model pipeline:
    generate_hajj_peak_scenario()
    → capacity degradation
    → congestion score estimation
    → detect_incidents()
    → compute_signal_timing()
    → cascade depth (BFS on ZONE_ADJACENCY)
    → HajjReadinessReport

Depends on: src/config.py (existing constants), src/model.py (detect_incidents,
compute_signal_timing, congestion_level).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from src.config import (
    HAJJ_CROWD_DENSITY_GRADIENT,
    HAJJ_LOCKDOWN_ZONES,
    ZONE_ADJACENCY,
    ALERT_THRESHOLDS,
    ROAD_CAPACITY_VPH,
    WEATHER_SPEED_IMPACT,
)

_CASCADE_MAX_DEPTH = 3   # per Prompt 137 spec; not currently in config.py


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScenarioParams:
    """Parameters for a single Hajj compound-stress scenario."""
    scenario_id: str
    year: int
    phase: str
    crowd_density_multiplier: Dict[str, float]   # per-zone from HAJJ_CROWD_DENSITY_GRADIENT
    sandstorm_active: bool
    sandstorm_severity: float                     # 0.0–1.0
    friday_prayer_window_active: bool
    cities: List[str]
    timestamp_utc: str


@dataclass
class ZoneResult:
    """Per-zone result from the readiness simulation."""
    zone_id: str
    city: str
    congestion_score: float
    congestion_level: str
    utilisation_pct: float
    alert_fired: bool
    incident_result: Dict
    cascade_depth: int
    signal_recommendation: Dict


@dataclass
class HajjReadinessReport:
    """Aggregate report produced by run_hajj_readiness_test()."""
    scenario_id: str
    phases_tested: List[str]
    alerts_fired: int
    incidents_detected: int
    signals_recommended: int
    bottleneck_zones: List[str]
    max_cascade_depth: int
    zone_results: List[ZoneResult]
    test_pass: bool
    failure_reasons: List[str]
    generated_at_utc: str


# ---------------------------------------------------------------------------
# Scenario generation
# ---------------------------------------------------------------------------

def generate_hajj_peak_scenario(year: int = 2026, phase: str = "peak") -> ScenarioParams:
    """
    Build a compound worst-case Hajj scenario using HAJJ_CROWD_DENSITY_GRADIENT.

    Compound stress: per-zone crowd density multipliers (from the gradient dict) +
    moderate sandstorm (severity=0.5) + Friday prayer window simultaneously active.

    Args:
        year:  Hajj year (default 2026).
        phase: Key in HAJJ_CROWD_DENSITY_GRADIENT — 'inbound', 'peak', 'outbound'.

    Returns:
        ScenarioParams fully populated.
    """
    if phase not in HAJJ_CROWD_DENSITY_GRADIENT:
        raise ValueError(
            f"Unknown phase '{phase}'. Valid phases: {list(HAJJ_CROWD_DENSITY_GRADIENT.keys())}"
        )

    return ScenarioParams(
        scenario_id=str(uuid.uuid4()),
        year=year,
        phase=phase,
        crowd_density_multiplier=HAJJ_CROWD_DENSITY_GRADIENT[phase],
        sandstorm_active=True,
        sandstorm_severity=0.5,
        friday_prayer_window_active=True,
        cities=["Riyadh"],
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_synthetic_zone_df(
    zone: str,
    crowd_multiplier: float,
    sandstorm_active: bool,
    sandstorm_severity: float,
    friday_prayer_active: bool,
    base_capacity_vph: int = 1600,
) -> pd.DataFrame:
    """
    Build a minimal synthetic DataFrame compatible with detect_incidents().

    8 rows of baseline + 2 rows of peak-scenario conditions.
    Speed degradation uses existing WEATHER_SPEED_IMPACT['sandstorm'].
    """
    weather = "sandstorm" if sandstorm_active else "clear"
    speed_factor = WEATHER_SPEED_IMPACT.get(weather, 1.0)
    if sandstorm_active:
        speed_factor *= (1.0 - sandstorm_severity * 0.20)

    baseline_speed = 65.0
    baseline_volume = base_capacity_vph * 0.65
    base_ts = datetime(2026, 5, 24, 6, 0, 0)

    rows = []
    for i in range(8):
        rows.append({
            "zone": zone,
            "timestamp": base_ts.replace(hour=6 + i),
            "vehicle_count": baseline_volume,
            "avg_speed": baseline_speed,
            "congestion_score": 0.35,
            "weather": "clear",
            "hour": 6 + i,
            "is_weekend": 1,
        })

    effective_capacity = base_capacity_vph * (
        1.0 - sandstorm_severity * 0.40 if sandstorm_active else 1.0
    )
    peak_volume = baseline_volume * crowd_multiplier
    if friday_prayer_active:
        peak_volume *= 0.85

    congestion_score = min(peak_volume / max(effective_capacity, 1.0), 2.0)
    peak_speed = max(baseline_speed * speed_factor * (1.0 - max(congestion_score - 1.0, 0) * 0.3), 5.0)

    for i in range(2):
        rows.append({
            "zone": zone,
            "timestamp": base_ts.replace(hour=14 + i),
            "vehicle_count": peak_volume,
            "avg_speed": peak_speed,
            "congestion_score": congestion_score,
            "weather": weather,
            "hour": 14 + i,
            "is_weekend": 1,
        })

    return pd.DataFrame(rows)


def _compute_cascade_depth(
    zone_id: str,
    zone_congestion_map: Dict[str, float],
    alert_threshold: float,
) -> int:
    """BFS through ZONE_ADJACENCY counting how many adjacent alerted zones chain from zone_id."""
    if zone_congestion_map.get(zone_id, 0.0) <= alert_threshold:
        return 0

    visited = {zone_id}
    frontier = [zone_id]
    depth = 0

    while frontier and depth <= _CASCADE_MAX_DEPTH:
        next_frontier = []
        for z in frontier:
            for neighbour in ZONE_ADJACENCY.get(z, []):
                if neighbour not in visited:
                    visited.add(neighbour)
                    if zone_congestion_map.get(neighbour, 0.0) > alert_threshold:
                        next_frontier.append(neighbour)
        if next_frontier:
            depth += 1
        frontier = next_frontier

    return depth


# ---------------------------------------------------------------------------
# Main simulation runner
# ---------------------------------------------------------------------------

def run_hajj_readiness_test(
    scenario: Optional[ScenarioParams] = None,
) -> HajjReadinessReport:
    """
    Execute the full Hajj readiness pipeline against the compound scenario.

    Pipeline:
        1. generate_hajj_peak_scenario() if no scenario provided
        2. Per zone: synthetic DataFrame → detect_incidents()
        3. compute_signal_timing() per zone
        4. BFS cascade depth via ZONE_ADJACENCY
        5. Aggregate → HajjReadinessReport

    Pass criteria:
        1. Every zone above congestion_critical threshold must have alert_fired=True.
        2. No zone cascade_depth > 3.
        3. All scenario cities represented in zone_results.
    """
    from src.model import detect_incidents, compute_signal_timing, congestion_level as get_level

    if scenario is None:
        scenario = generate_hajj_peak_scenario(year=2026, phase="peak")

    alert_threshold: float = ALERT_THRESHOLDS["congestion_critical"]   # 0.75
    arterial_capacity = ROAD_CAPACITY_VPH.get("arterial", 1600)

    zones = list(scenario.crowd_density_multiplier.keys())
    zone_congestion_map: Dict[str, float] = {}
    zone_results: List[ZoneResult] = []

    # --- Pass 1: per-zone metrics ---
    for zone_id in zones:
        crowd_mult = scenario.crowd_density_multiplier[zone_id]
        if zone_id in HAJJ_LOCKDOWN_ZONES:
            crowd_mult = max(crowd_mult, 2.2)

        df = _build_synthetic_zone_df(
            zone=zone_id,
            crowd_multiplier=crowd_mult,
            sandstorm_active=scenario.sandstorm_active,
            sandstorm_severity=scenario.sandstorm_severity,
            friday_prayer_active=scenario.friday_prayer_window_active,
            base_capacity_vph=arterial_capacity,
        )

        peak_row = df.iloc[-1]
        congestion_score = float(peak_row["congestion_score"])
        zone_congestion_map[zone_id] = congestion_score

        alert_fired = congestion_score > alert_threshold

        incident_result = detect_incidents(
            df=df,
            zone=zone_id,
            window_minutes=2,
            city="Riyadh",
            log=False,
        )

        signal_rec = compute_signal_timing(
            congestion_score=congestion_score,
            vehicle_count=float(peak_row["vehicle_count"]),
            hour=int(peak_row["hour"]),
            is_weekend=int(peak_row["is_weekend"]),
        )
        signal_rec["zone"] = zone_id
        signal_rec["hajj_lockdown"] = zone_id in HAJJ_LOCKDOWN_ZONES

        zone_results.append(ZoneResult(
            zone_id=zone_id,
            city="Riyadh",
            congestion_score=round(congestion_score, 4),
            congestion_level=get_level(congestion_score),
            utilisation_pct=round(congestion_score * 100.0, 2),
            alert_fired=alert_fired,
            incident_result=incident_result,
            cascade_depth=0,
            signal_recommendation=signal_rec,
        ))

    # --- Pass 2: cascade depth ---
    for zr in zone_results:
        zr.cascade_depth = _compute_cascade_depth(zr.zone_id, zone_congestion_map, alert_threshold)

    # --- Aggregate ---
    alerts_fired = sum(1 for z in zone_results if z.alert_fired)
    incidents_detected = sum(1 for z in zone_results if z.incident_result.get("incident_detected"))
    bottleneck_zones = [z.zone_id for z in zone_results if z.utilisation_pct >= 90.0]
    max_cascade_depth = max((z.cascade_depth for z in zone_results), default=0)

    # --- Pass/fail evaluation ---
    failure_reasons: List[str] = []

    missed = [z.zone_id for z in zone_results if z.congestion_score > alert_threshold and not z.alert_fired]
    if missed:
        failure_reasons.append(f"Alert not fired for zones above threshold: {missed}")

    breaches = [z.zone_id for z in zone_results if z.cascade_depth > _CASCADE_MAX_DEPTH]
    if breaches:
        failure_reasons.append(f"Cascade depth > {_CASCADE_MAX_DEPTH} in: {breaches}")

    missing_cities = set(scenario.cities) - {z.city for z in zone_results}
    if missing_cities:
        failure_reasons.append(f"Cities not covered: {missing_cities}")

    return HajjReadinessReport(
        scenario_id=scenario.scenario_id,
        phases_tested=[scenario.phase],
        alerts_fired=alerts_fired,
        incidents_detected=incidents_detected,
        signals_recommended=len(zone_results),
        bottleneck_zones=bottleneck_zones,
        max_cascade_depth=max_cascade_depth,
        zone_results=zone_results,
        test_pass=len(failure_reasons) == 0,
        failure_reasons=failure_reasons,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
    )
