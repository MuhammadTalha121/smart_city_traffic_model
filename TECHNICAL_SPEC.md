# Smart City Traffic Intelligence System — Technical Specification v5.0.0

> Vision 2030 Smart City Infrastructure · Riyadh · NEOM · Dubai · Karachi

---

## System Architecture
DATA INGESTION          API GATEWAY           PROCESSING CORE

─────────────────       ─────────────────     ─────────────────────────────

Open-Meteo Weather  →   API Key Auth      →   Data Validation (5 checks)

OpenStreetMap OSM   →   Role Enforcement  →   Feature Engineering (lag+roll)

Mock IoT Sensors    →   Rate Limiting     →   XGBoost Model (R²=0.94)

CORS Middleware   →   SHAP Explainability
OUTPUTS

─────────────────────────────────────────────────────────────────────────

Congestion Score (0–1)   │  Accident Risk Score   │  Signal Timing

Emissions / CO2          │  Pedestrian Risk        │  Speed Degradation Index

Intervention Advice      │  Forecast (+1h/2h/3h)  │  Prediction Interval

Emergency Response Time  │  Freight Windows        │  Anomaly Detection
OPERATIONS

─────────────────────────────────────────────────────────────────────────

Drift Detection → Auto-Retrain (03:00)   │  Webhook Alerts (15-min)

Usage Analytics → Quota Management       │  SLA Monitoring

Weekly HTML Reports                      │  WebSocket Streaming

---

## API Endpoints

| Endpoint | Method | Auth | Role | Rate Limit | Description |
|---|---|---|---|---|---|
| `/health` | GET | No | — | — | Health check |
| `/schedule/active` | GET | Yes | operator | — | Active traffic schedule |
| `/predict` | POST | Yes | operator | 60/min | Single zone prediction |
| `/predict/batch` | POST | Yes | operator | 20/min | Up to 20 zones |
| `/anomalies` | GET | Yes | operator | 20/min | Active anomalies |
| `/forecast` | GET | Yes | operator | 20/min | 1h/2h/3h forecast |
| `/interventions/active` | GET | Yes | operator | 20/min | High/Critical zones |
| `/safety/hotspots` | GET | Yes | operator | — | Accident risk ranking |
| `/safety/pedestrian` | GET | Yes | operator | — | Pedestrian risk ranking |
| `/signals/recommended` | GET | Yes | operator | — | Signal timing per zone |
| `/emergency/response-time` | GET | Yes | operator | — | Ambulance ETA |
| `/freight/windows` | GET | Yes | operator | — | Optimal delivery windows |
| `/roads/service-level` | GET | Yes | operator | — | HCM level of service |
| `/cities/compare` | GET | Yes | operator | — | Multi-city snapshot |
| `/history/patterns` | GET | Yes | operator | — | Historical pattern query |
| `/history/trend` | GET | Yes | operator | — | 7-day trend direction |
| `/emissions/summary` | GET | Yes | operator | — | CO2 aggregate report |
| `/alerts/history` | GET | Yes | operator | — | Past threshold alerts |
| `/data/quality` | GET | Yes | operator | — | Input quality metrics |
| `/sla/current` | GET | No | — | — | Last 24h SLA metrics |
| `/data/source` | GET/POST | Yes | admin | — | Switch data adapter |
| `/pipeline/status` | GET | Yes | admin | — | Drift score + retrain status |
| `/pipeline/trigger` | POST | Yes | admin | — | Manual retrain |
| `/analytics/usage` | GET | Yes | admin | 20/min | API usage report |
| `/analytics/quota` | GET | Yes | admin | 20/min | Daily quota status |
| `/sla/report` | GET | Yes | admin | — | Full SLA compliance report |
| `/reports/weekly` | POST | Yes | admin | — | Generate weekly HTML report |
| `/ws/live/{city}` | WS | Yes (query) | operator | — | Live zone stream (30s) |

---

## `/predict` Request Schema

| Field | Type | Required | Range | Description |
|---|---|---|---|---|
| `city` | string | No | Riyadh, NEOM, Dubai, Karachi | Target city |
| `zone` | string | No | Zone_1 – Zone_5 | City zone |
| `hour` | int | Yes | 0–23 | Hour of day |
| `vehicle_count` | float | Yes | 0–500 | Vehicles in zone |
| `avg_speed` | float | Yes | 20–100 | Average speed km/h |
| `weather` | string | No | clear, dust, fog, humid, rain, sandstorm | Weather condition |
| `road_type` | string | No | highway, arterial, local | Road classification |
| `rush_hour` | int | No | 0–1 | Rush hour flag |
| `is_weekend` | int | No | 0–1 | Weekend flag (Fri–Sat for Saudi) |
| `is_late_night` | int | No | 0–1 | Late night flag (21:00–00:00) |
| `event` | int | No | 0–1 | Special event flag |
| `hour_multiplier` | float | No | 0.05–3.0 | Hourly traffic weight |
| `hajj_mode` | bool | No | true/false | Activate Hajj traffic model |

---

## `/predict` Response Fields

| Field | Type | Unit | Description |
|---|---|---|---|
| `congestion_score` | float | 0–1 | Zone congestion level |
| `congestion_level` | string | — | Low / Moderate / High / Critical |
| `recommendation` | string | — | Operator action |
| `schedule` | string | — | Active traffic schedule |
| `hajj_mode` | bool | — | Whether Hajj mode was active |
| `explanation` | array | — | Top 3 SHAP factors |
| `plain_english` | string | — | Plain language summary |
| `prediction_interval` | object | — | lower_bound, upper_bound, confidence_width |
| `intervention` | object | — | Commuter advice, metro station, carpool |
| `accident_risk` | object | — | risk_score (0–1), risk_level, primary_risk_factor |
| `signal_timing` | object | — | cycle_seconds, green_seconds, phase_ratio |
| `emissions` | object | — | fuel_litres, co2_kg, co2_tonnes, green_initiative_flag |
| `sdi` | object | — | Speed Degradation Index, level_of_service (A–F) |
| `pedestrian_risk` | object | — | pedestrian_risk_score, risk_category |
| `input_warnings` | array | — | Plausibility warnings on input values |

---

## Saudi-Specific Calibration

| Pattern | Implementation | Validated |
|---|---|---|
| Friday prayer drop (12:00–13:00) | 90% vehicle count reduction | ✅ 90.88% measured |
| Weekend definition | Friday + Saturday | ✅ |
| Sandstorm speed impact | 40% speed reduction | ✅ 39.74% measured |
| Late-night activity (21:00–23:00) | 1.4–1.5x multiplier | ✅ ratio 0.7537 |
| Ramadan schedule | Full daily cycle +4h shift | ✅ |
| Hajj mode | Inbound / Peak / Outbound phases | ✅ 2.5x peak verified |

---

## Statistical Validation Results

| Check | Expected | Actual | Status |
|---|---|---|---|
| Vehicle count coefficient of variation | < 0.60 | 0.3105 | PASS |
| Autocorrelation lag-1 | > 0.50 | 0.7393 | PASS |
| Friday prayer drop vs weekday midday | ≥ 0.85 | 0.9088 | PASS |
| Late night / evening peak ratio | ≥ 0.70 | 0.7537 | PASS |
| Sandstorm speed reduction | 0.35–0.45 | 0.3974 | PASS |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| API Framework | FastAPI 0.110+, Uvicorn |
| ML Models | XGBoost 2.0+, Scikit-learn, Statsmodels |
| Explainability | SHAP TreeExplainer |
| Data | Pandas, NumPy |
| Auth / Security | python-dotenv, APIKeyHeader, slowapi |
| Scheduling | APScheduler |
| Containerisation | Docker, Docker Compose |
| Deployment | Render / Railway |
| Testing | pytest, pytest-cov (80 tests, 85%+ coverage) |