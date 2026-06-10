# Smart City Traffic Intelligence System — Project Context

Complete context for any AI assistant, collaborator, or contributor.

---

## Mission

Build a production-ready traffic intelligence system for Vision 2030 smart cities.
Not a generic model — a culturally and behaviorally calibrated system
that reflects how people actually move in Saudi Arabian cities.

---

## Owner

Muhammad Talha — self-taught data scientist, 4 years experience.
GitHub: MuhammadTalha121
Targeting data analyst / ML roles in Riyadh, Saudi Arabia.
No formal degree — portfolio is the credential.
This project is shown to industry leaders as a proof of concept.

---

## Live URLs

| Service | URL |
|---|---|
| API | https://web-production-abfda1.up.railway.app |
| API Docs | https://web-production-abfda1.up.railway.app/docs |

> **Note:** Dashboard is now served directly by FastAPI at `/` as `dashboard.html`.
> Streamlit has been retired. Railway has been retired in favour of Render free tier.
> Update these URLs once Render deployment is live.

---

## Architecture Decisions

| Decision | Reason |
|---|---|
| Modular src/ package | Clean separation of config, data, model — not one giant notebook |
| City profiles in config.py | Single source of truth — adding a city is one dictionary entry |
| FastAPI over Flask | Auto /docs UI, Pydantic validation, async-ready |
| FastAPI-served dashboard.html | Replaces Streamlit — single process, no second service |
| Docker containerization | One command local testing — shows production thinking |
| Render free tier | Replaces Railway (free tier retired) — permanent free tier |
| Self-ping keep-alive | setInterval fetching /health every 14 min — prevents Render sleep |
| Synthetic data | Real IoT data not publicly available for Gulf cities |
| XGBoost as primary model | Best R² in multi-model comparison, interpretable feature importance |
| Business-labeled charts | Employers read charts, not variable names |
| Lag features | Temporal momentum — 1h/2h vehicle count, 1h congestion, 3h rolling stats |
| SHAP explainability | Every prediction auditable — defensible to non-technical stakeholders |
| Anomaly detection | Rolling 7-day baseline — flags unexpected events before they become incidents |
| Multi-horizon forecasting | XGBoost + ARIMA compared at +1h, +2h, +3h per zone |
| Audit trail | Every prediction logged to predictions_log.csv with timestamp and factors |
| API key auth | X-API-Key header via python-dotenv — key never hardcoded |
| Rate limiting | slowapi — 60/min on /predict, 20/min on /anomalies and /forecast |
| Data adapters | WeatherAdapter, OSMAdapter, MockIoTAdapter — swap sources in one API call |
| Drift detection | Rolling MAE comparison — retrains at 03:00 if drift >= 1.3 |
| Hajj mode | Three-phase Hajj traffic model — inbound, peak, dispersal |
| Intervention layer | Commuter metro + carpool + departure advice at High/Critical |
| Accident risk scoring | Congestion × weather × hour × road type — pre-incident risk |
| Adaptive signal timing | Green phase duration per zone — Vision 2030 signal controller input |

---

## Saudi-Specific Design — Never Remove These

- Weekend = Friday + Saturday (not Saturday + Sunday)
- Sandstorm = first-class weather category, 0.60 speed multiplier
- Friday prayer window (12:00–13:00) = 90% vehicle count reduction — statistically verified
- Late-night hours (21:00–23:00) = high multipliers (1.4–1.5), Saudi lifestyle
- Ramadan schedule = entire day shifts ~4 hours, Iftar drives evening peak
- Hajj mode = three traffic phases (inbound/peak/dispersal), pilgrimage route zone multipliers
- Vision 2030 framing throughout all documentation

---

## Code Style Rules

- No inline comments — docstrings only
- Self-explanatory variable names
- Aligned assignment operators
- One focused change per commit
- Commit format: `type: plain description` (feat, fix, docs, style, chore, refactor)

---

## Critical Implementation Notes — Read Before Modifying

### Function signatures
- `train_xgboost(X, y)` — takes separate feature matrix and target series
- `prepare_features(df)` — returns (X, y, feature_cols). Always expects `congestion_score`.
  Cannot be used for single-row live inference.
- `explain_prediction(model, X_row_df, feature_names_list)` — X_row must be a DataFrame.
  Returns `{top_factors: [...], plain_english: str}`
- `log_prediction(prediction_dict, explanation_dict)` — two separate arguments
- `predict_single(city, zone, hour, vehicle_count, avg_speed, weather, road_type,
  rush_hour, is_weekend, is_late_night, event, hour_multiplier)` — individual keyword args
- `forecast_congestion(df, zone, hours_ahead)` — zone is second arg, not model
- `detect_anomalies(df)` — returns `anomaly_flag` column (int), not `is_anomaly`
- `apply_hourly_patterns(df, city, ramadan, hajj)` — hajj is third bool param (after ramadan)
- `get_intervention(zone, hour, congestion_level)` — in src/model.py
- `compute_accident_risk(congestion_score, weather, hour, is_weekend, rush_hour)` — in src/model.py
- `compute_signal_timing(congestion_score, vehicle_count, hour, is_weekend)` — in src/model.py

### Where things live
- WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING — in `src/model.py`
- PALETTE, CONGESTION_THRESHOLDS, HOURLY_MULTIPLIERS, WEATHER_SPEED_IMPACT,
  FRIDAY_PRAYER_HOURS, SAUDI_CITIES, HAJJ_DATES, HAJJ_INBOUND, HAJJ_PEAK,
  HAJJ_OUTBOUND, HAJJ_ROUTE_ZONES, METRO_STATIONS, CARPOOL_LANES,
  OFF_PEAK_WINDOWS — in `src/config.py`
- get_adapter(source) factory — in `src/adapters.py`
- compute_drift_score, run_pipeline — in `src/pipeline.py`
- dashboard.html — at repo root alongside app.py

### Correct startup sequence
```python
df = generate_traffic_data(city="Riyadh")
df = apply_hourly_patterns(df, city="Riyadh")   # creates congestion_score
df = add_lag_features(df)                        # requires congestion_score
X, y, feature_cols = prepare_features(df)
model, _, _        = train_xgboost(X, y)
```

### Building X_row for live inference
```python
from src.model import WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING
row = {
    "vehicle_count"        : p["vehicle_count"],
    "avg_speed"            : p["avg_speed"],
    "hour"                 : p["hour"],
    "rush_hour"            : p["rush_hour"],
    "is_weekend"           : p["is_weekend"],
    "is_late_night"        : p["is_late_night"],
    "event"                : p["event"],
    "hour_multiplier"      : p["hour_multiplier"],
    "weather"              : WEATHER_ENCODING.get(p["weather"], 0),
    "road_type"            : ROAD_ENCODING.get(p["road_type"], 0),
    "zone"                 : ZONE_ENCODING.get(p["zone"], 0),
    "day_of_week"          : DAY_ENCODING.get(datetime.now().strftime("%A"), 0),
    "vehicle_count_lag_1h" : p["vehicle_count"],
    "vehicle_count_lag_2h" : p["vehicle_count"],
    "congestion_lag_1h"    : 0.0,
    "rolling_mean_3h"      : p["vehicle_count"],
    "rolling_std_3h"       : 0.0,
}
X_row = pd.DataFrame([row])[app.state.feature_cols]
```

### Render deployment notes
- Render free tier replaces Railway (Railway free tier was retired)
- render.yaml configures the service — uvicorn on $PORT
- Self-ping: `setInterval(() => fetch('/health'), 14 * 60 * 1000)` in dashboard.html
- Set API_KEY and ALLOWED_ORIGINS in Render environment variables dashboard
- Render auto-deploys on every push to main

### Docker notes (local testing)
- Dockerfile currently references old Streamlit setup — known outstanding issue
- Fix required: remove Streamlit CMD, expose only port 8000, add dashboard.html route
- docker-compose.yml still has a dashboard service pointing to Streamlit — remove it
- Correct Dockerfile CMD: `uvicorn app:app --host 0.0.0.0 --port 8000`

### TestClient and lifespan
- Use `with TestClient(app) as client:` in a pytest fixture — triggers lifespan startup
- Without the context manager, app.state.df and app.state.model are not set

---

## Current State (Complete through PROMPT 015)

### src/config.py
- PALETTE, CONGESTION_THRESHOLDS, HOURLY_MULTIPLIERS, WEATHER_SPEED_IMPACT
- FRIDAY_PRAYER_HOURS, SAUDI_CITIES, CITY_PROFILES
- HAJJ_DATES, HAJJ_INBOUND, HAJJ_PEAK, HAJJ_OUTBOUND, HAJJ_ROUTE_ZONES
- METRO_STATIONS, CARPOOL_LANES, OFF_PEAK_WINDOWS

### src/data.py
- generate_traffic_data() — Poisson-based synthetic generation per city profile
- apply_hourly_patterns(df, city, ramadan, hajj) — Saudi calibration, Hajj phases, creates congestion_score
- add_lag_features() — 1h/2h vehicle lag, 1h congestion lag, 3h rolling mean/std
- validate_data() — 5 statistical checks, returns PASS/FAIL report table

### src/model.py
- WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING
- prepare_features(), train_xgboost(X, y), evaluate_models()
- congestion_level(), get_recommendation(), predict_single()
- detect_anomalies(), forecast_congestion(df, zone, hours_ahead)
- explain_prediction(model, X_row_df, feature_names) → {top_factors, plain_english}
- log_prediction(prediction_dict, explanation_dict)
- save_model(), load_model(), compare_baseline_vs_enhanced()
- compare_arima_vs_xgboost()
- get_intervention(zone, hour, congestion_level) → {operator_action, commuter_advice,
  metro_station, carpool_available, recommended_departure, urgency}
- compute_accident_risk(congestion_score, weather, hour, is_weekend, rush_hour)
  → {risk_score, risk_level, primary_risk_factor}
- compute_signal_timing(congestion_score, vehicle_count, hour, is_weekend)
  → {cycle_seconds, green_seconds, red_seconds, phase_ratio, timing_rationale}

### src/adapters.py
- BaseAdapter ABC with fetch(city) interface
- WeatherAdapter — Open-Meteo API, classifies to system weather categories
- OpenStreetMapAdapter — Overpass API with Riyadh bbox fallback
- MockIoTAdapter — deterministic simulation, noise_level parameter
- get_adapter(source) — factory: 'weather' | 'osm' | 'mock'

### src/pipeline.py
- compute_drift_score(log_path) — rolling MAE vs baseline, returns ratio
- should_retrain(drift_score, threshold=1.3) — pure boolean
- retrain_model(city) — full pipeline, saves to model.joblib
- run_pipeline(city) — orchestrates all steps, logs to pipeline_log.csv

### app.py (version 5.0.0)
- Lifespan: generate → apply_hourly_patterns → lag features → train
- APScheduler: nightly pipeline at 03:00
- Serves dashboard.html at GET / (FileResponse)
- Self-ping keep-alive embedded in dashboard.html
- Endpoints: /health (public), / (dashboard, public)
- /data/source GET + POST (data adapter switching)
- /pipeline/status GET + /pipeline/trigger POST
- /predict POST (60/min), /predict/batch POST (20/min)
- /anomalies GET (20/min), /forecast GET (20/min)
- /schedule/active GET — returns current schedule (standard/saudi/ramadan/hajj) with countdown
- /interventions/active GET — all zones at High or Critical, sorted Critical first
- /safety/hotspots GET — zones ranked by accident risk_score
- /signals/recommended GET — all zones with recommended signal timing

### /predict response shape (PROMPT 015 state) — 10 fields
```
congestion_score, congestion_level, recommendation, explanation,
plain_english, schedule, hajj_mode, intervention, accident_risk, signal_timing
```

### dashboard.html
- Lives at repo root alongside app.py
- Single-file, self-contained — Chart.js, DM Sans/DM Mono/Playfair Display
- Deep navy / amber aesthetic
- Six tabs: Overview, Zones, Weather, Forecasting, Safety, Signals
- Self-ping: setInterval fetching /health every 14 minutes (Render keep-alive)

### tests/ — 40 tests passing
- test_data.py — 5 tests
- test_model.py — 19 tests
- test_api.py — 16 tests (using `with TestClient(app) as client:` fixture)
- .github/workflows/test.yml — CI/CD on push to main

### Infrastructure
- render.yaml — Render free tier deployment config
- nixpacks.toml — build config for Render/Railway
- Procfile — fallback start command
- Dockerfile + docker-compose.yml — local container option (Streamlit references outstanding — known issue)
- requirements.txt — >= versions for cross-platform compatibility
- .env — API_KEY + ALLOWED_ORIGINS (never committed)
- .env.example — safe to commit
- .gitignore — excludes .env, *.csv logs, *.joblib, __pycache__
- generate_key.py — one-time key generation
- DEMO.md — copy-paste commands for recruiters

---

## Known Outstanding Infrastructure Issues

| Issue | Location | Fix Required |
|---|---|---|
| Dockerfile CMD still launches Streamlit | Dockerfile | Replace CMD with single uvicorn command, remove Streamlit |
| docker-compose.yml has dashboard service | docker-compose.yml | Remove dashboard service, keep only api service |
| Live URLs in DEMO.md point to Railway | DEMO.md | Update to Render URL once deployed |
| PROJECT_CONTEXT_.md live URLs | This file | Update once Render URL is confirmed |

---

## Validated Statistical Properties — Riyadh

| Check | Expected | Actual | Status |
|---|---|---|---|
| Vehicle count coefficient of variation | < 0.60 | 0.3105 | PASS |
| Autocorrelation lag-1 | > 0.50 | 0.7393 | PASS |
| Friday prayer drop vs weekday midday | >= 0.85 | 0.9088 | PASS |
| Late night / evening peak ratio | >= 0.70 | 0.7537 | PASS |
| Sandstorm speed reduction | 0.35–0.45 | 0.3974 | PASS |

---

## Completed Prompts

| Prompt | Feature | Status |
|---|---|---|
| 001–005 | Portfolio foundation — data, model, anomaly detection, forecasting, SHAP | ✅ |
| 006 | API auth, rate limiting, CORS, .env | ✅ |
| 007 | 20 tests, 85% coverage, CI/CD | ✅ |
| 008 | Live weather, OSM, mock adapters, /data/source | ✅ |
| 009 | Drift detection, auto-retraining, /pipeline endpoints | ✅ |
| 010 | Cloud deployment, dashboard, DEMO.md, keep-alive | ✅ |
| 011 | Emissions and CO2 layer | ⚠️ Scaffolded — constants in config.py, compute_emissions not yet built |
| 012 | Hajj mode — inbound/peak/dispersal, /schedule/active | ✅ |
| 013 | Intervention layer — metro, carpool, departure, /interventions/active | ✅ |
| 014 | Accident risk scoring — /safety/hotspots | ✅ |
| 015 | Adaptive signal timing — /signals/recommended | ✅ |

> PROMPT 011 status: `FUEL_CONSUMPTION_LPH`, `CO2_KG_PER_LITRE`, `AVG_ZONE_AREA_KM2`
> are scaffolded in src/config.py. `compute_emissions()` function and /predict integration
> are not yet built. This prompt must be completed before PROMPT 016.

---

## Pending Prompts

| Prompt | Feature |
|---|---|
| 011 | Complete emissions layer — compute_emissions(), /predict integration, /emissions/summary |
| 016 | Multi-city comparative dashboard |
| 017 | Emergency vehicle response time estimator |
| 018 | Freight delivery window optimizer |
| 019 | Historical pattern analysis API |
| 020 | Prediction confidence intervals |
| 021 | Operator alert and webhook notification |
| 022 | Road segment speed degradation index (HCM) |
| 023 | Pedestrian safety score |
| 024 | API usage analytics and quota management |
| 025 | Multi-tenant key management |
| 026 | Automated weekly HTML report generator |
| 027 | WebSocket real-time streaming endpoint |
| 028 | Data quality monitoring and validation |
| 029 | SLA monitoring and uptime reporting |
| 030 | Government documentation package |

---

## Recruiter Sentences Unlocked

| Prompt | Sentence |
|---|---|
| 006 | "Authenticated and rate-limited — not an open endpoint." |
| 007 | "20 automated tests, 85% coverage, CI/CD on every push." |
| 008 | "Fetches live Riyadh weather from Open-Meteo right now." |
| 009 | "Detects drift and retrains itself automatically at 3AM." |
| 010 | "Here's the URL — test it on your phone right now." |
| 012 | "Dedicated Hajj mode — inbound/peak/dispersal phases, pilgrimage route zones. No Western system ships this." |
| 013 | "When Critical, tells commuters which metro station to use, carpool lane status, departure time." |
| 014 | "Accident risk score per zone — sandstorm+rush = Critical Risk before the accident happens." |
| 015 | "Outputs green phase durations per zone — direct input for Vision 2030 adaptive signal controllers." |

---

## How to Run

```bash
# Generate API key (run once)
py generate_key.py

# Validate data
py -c "from src.data import validate_data; validate_data(city='Riyadh')"

# Run tests
py -m pytest tests/ --cov=src --cov-report=term-missing -v

# Local API
py -m uvicorn app:app --reload
# → http://127.0.0.1:8000/docs
# → http://127.0.0.1:8000  (dashboard)

# Docker (note: Dockerfile has known Streamlit issue — fix before using)
docker-compose up --build
```

---

## Instructions for AI Assistant

1. Never remove Saudi-specific behavioral patterns — they are the core differentiator
2. Keep src/ modular — config, data, model, adapters, pipeline stay separate
3. dashboard.html lives at repo root alongside app.py — never move it
4. All charts use PALETTE from config.py — no hardcoded colors
5. Recommendations must be operational and specific — not generic data science output
6. Update README roadmap checkboxes when new features are added
7. requirements.txt uses >= not == for cross-platform compatibility
8. Docker exposes port 8000 only — Streamlit is retired
9. validate_data() must pass 5/5 before any model changes are committed
10. Every new prediction endpoint must log to predictions_log.csv via log_prediction()
11. SHAP explanation must be included in any new /predict variant
12. Encoding dicts are in src/model.py — never assume they are in src/config.py
13. prepare_features() cannot be used for live single-row inference — build X_row manually
14. apply_hourly_patterns() must always be called between generate_traffic_data()
    and add_lag_features() — it creates the congestion_score column both depend on
15. detect_anomalies() returns anomaly_flag (int), not is_anomaly
16. forecast_congestion(df, zone, hours_ahead) — zone is second positional arg
17. After any app.py change, run tests locally before pushing — Render auto-deploys
18. TestClient tests must use `with TestClient(app) as client:` to trigger lifespan
19. The self-ping keep-alive (14-min /health fetch) must remain in dashboard.html
20. PROMPT 011 must be completed before starting PROMPT 016
21. apply_hourly_patterns() signature is now (df, city, ramadan, hajj) — hajj is the fourth arg
22. /predict response has 10 fields as of PROMPT 015 — emissions field not yet added
