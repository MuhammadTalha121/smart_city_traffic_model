# API Changelog

All breaking and additive changes to the Smart City Traffic Intelligence API.


### Added
- **Actuation** — `/signals/actuate`, `/signals/actuation-log`, `/signals/optimise` (NTCIP stub, safety-gated).
- **Simulation** — `/simulation/sumo-status`, `/simulation/run` (SUMO with static fallback).
- **Construction** — `/construction/zones`, `/construction/diversion/{zone}`.
- **Agency gateway** — `/agency/*` (X-Agency-Token authentication).
- **Citizen API** — `/public/traffic-status`, `/public/incidents`, `/public/travel-advisory`, `/public/route-status`, `/public/weather`, `/public/parking-guidance`.
- **Citizen portal** — `/portal` (bilingual Arabic/English).
- **Probabilistic forecasts** — `/predict?probabilistic=true` adds P10/P50/P90 fields.
- **Hajj** — `/hajj/readiness-report`, `/hajj/playbook`.
- **Standards compliance** — DATEX II, SIRI, GTFS-RT schema validation.
- **Disaster recovery** — `/system/health`.
- **Emissions** — `/emissions/zone-report`, `/reports/sustainability`.
- **NLG briefings** — `/briefing/{zone}?language=en|ar`.
- **Multi-city** — `/analytics/city-comparison`, `/reports/city-comparison`.
- **A/B testing** — `/experiments/signal-ab/*`.

### Changed
- OpenAPI spec versioned to **3.1.0**.
- All endpoint docstrings reviewed and enriched.

### Unchanged (backward compatible)
- `/predict` — 11-field response schema preserved.
- `/predict/batch`, `/anomalies`, `/forecast` — unchanged.
- All PROMPTs 001–120 endpoints — unchanged.


Initial production release. See `PROJECT_CONTEXT_V5.md` for details.

---

**Breaking change policy:** `/predict` fields are never removed or renamed. New fields are additive only.