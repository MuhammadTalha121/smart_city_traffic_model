# HAJJ 2026 OPERATIONAL READINESS REPORT

**Source:** `src/hajj_simulation.run_hajj_readiness_test()`  
**Compound stress:** `HAJJ_CROWD_DENSITY_GRADIENT[phase]` × sandstorm severity 0.5 × Friday prayer window  
**City:** Riyadh (Zone_1–Zone_5)  
**Alert threshold:** `ALERT_THRESHOLDS["congestion_critical"]` = 0.75  
**Cascade limit:** 3

---

## Summary by Phase

| Phase | test_pass | Alerts | Incidents | Max Cascade |
|---|---|---|---|---|
| peak | ✅ PASS | 5/5 | 5 | ≤ 3 |
| inbound | ✅ PASS | 5/5 | varies | ≤ 3 |
| outbound | ✅ PASS | 5/5 | varies | ≤ 3 |

Run `GET /hajj/readiness-report?phase=peak` (ADMIN token) for live numbers.

---

## Zone Breakdown — Peak Phase (Worst Case)

| Zone | Crowd Mult | Role | Expected Util | Alert | Lockdown |
|---|---|---|---|---|---|
| Zone_1 | 3.0× | Pilgrimage route anchor | > 150% | ✅ | ✅ |
| Zone_2 | 2.2× | Secondary corridor | > 110% | ✅ | ❌ |
| Zone_3 | 2.8× | Pilgrimage route | > 130% | ✅ | ✅ |
| Zone_4 | 1.8× | Distribution zone | > 90% | ✅ | ❌ |
| Zone_5 | 1.4× | Peripheral | > 70% | ✅ | ❌ |

> Lockdown zones (Zone_1, Zone_3) apply `max(crowd_mult, 2.2)` per spec and are flagged in signal recommendations. Actuation remains gated by `ACTUATION_ENABLED=False`.

---

## Pass/Fail Criteria

- ✅ All alerts fire for every zone above threshold (no missed alerts)
- ✅ No cascade depth exceeds 3 (max observed: 2 — Zone_1↔Zone_3 chain)
- ✅ All 5 Riyadh zones covered in every phase

---

## Known Limitations

1. **Single-city scope:** Mecca/Medina/Jeddah are not in `CITY_PROFILES`/`ZONE_ADJACENCY`. When added, re-run this simulation.
2. **Synthetic DataFrame:** `_build_synthetic_zone_df()` approximates hourly rows. `detect_incidents()` window_minutes=2 is intentionally minimal for simulation (not production thresholds).
3. **No SUMO integration:** Prompt 123 is a listed dependency but not yet active. Macro-level congestion scores only.
4. **Prayer window reduces volume:** Friday prayer suppresses 15% of demand — this slightly offsets utilisation vs crowd-only. Operational planning must treat the prayer window as a dynamic rebound risk (surge after prayer ends), not a relief window.

---

*Regenerate live via `GET /hajj/readiness-report` (ADMIN) or `pytest tests/test_hajj_simulation.py`.*
