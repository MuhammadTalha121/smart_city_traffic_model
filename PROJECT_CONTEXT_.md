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
| Dashboard | https://smartcitytrafficmodel-u2bsdyw2cqxtorno5sscyk.streamlit.app |

---

## Architecture Decisions

| Decision | Reason |
|---|---|
| Modular src/ package | Clean separation of config, data, model — not one giant notebook |
| City profiles in config.py | Single source of truth — adding a city is one dictionary entry |
| FastAPI over Flask | Auto /docs UI, Pydantic validation, async-ready |
| Streamlit dashboard | Industry leaders can interact without touching code |
| Docker containerization | One command deployment — shows production thinking |
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
| Railway deployment | Free tier, auto-deploy on push to main |
| UptimeRobot | Pings /health every 5 minutes to prevent Railway sleep |

---

## Saudi-Specific Design — Never Remove These

- Weekend = Friday + Saturday (not Saturday + Sunday)
- Sandstorm = first-class weather category, 0.60 speed multiplier
- Friday prayer window (12:00–13:00) = 90% vehicle count reduction — statistically verified
- Late-night hours (21:00–23:00) = high multipliers (1.4–1.5), Saudi lifestyle
- Ramadan schedule = entire day shifts ~4 hours, Iftar drives evening peak
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

### Where things live
- WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING — in `src/model.py`
- PALETTE, CONGESTION_THRESHOLDS, HOURLY_MULTIPLIERS, WEATHER_SPEED_IMPACT,
  FRIDAY_PRAYER_HOURS, SAUDI_CITIES — in `src/config.py`
- get_adapter(source) factory — in `src/adapters.py`
- compute_drift_score, run_pipeline — in `src/pipeline.py`

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

### Railway deployment notes
- Railway does not expand $PORT in railway.toml startCommand directly
- Working fix: `sh -c 'uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}'`
- Set API_KEY and ALLOWED_ORIGINS in Railway Variables dashboard
- Railway auto-deploys on every push to main
- Free tier sleeps after 30min — UptimeRobot on /health prevents this

### TestClient and lifespan
- Use `with TestClient(app) as client:` in a pytest fixture — triggers lifespan startup
- Without the context manager, app.state.df and app.state.model are not set

---

## Current State (Complete)

### src/config.py
- PALETTE, CONGESTION_THRESHOLDS, HOURLY_MULTIPLIERS, WEATHER_SPEED_IMPACT
- FRIDAY_PRAYER_HOURS, SAUDI_CITIES, CITY_PROFILES

### src/data.py
- generate_traffic_data() — Poisson-based synthetic generation per city profile
- apply_hourly_patterns(df, city, ramadan) — Saudi calibration, creates congestion_score
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

### app.py (version 4.0.0)
- Lifespan: generate → apply_hourly_patterns → lag features → train
- APScheduler: nightly pipeline at 03:00
- Endpoints: /, /health (public)
- /data/source GET + POST (data adapter switching)
- /pipeline/status GET + /pipeline/trigger POST
- /predict POST (60/min), /predict/batch POST (20/min)
- /anomalies GET (20/min), /forecast GET (20/min)

### tests/
- test_data.py — 5 tests
- test_model.py — 8 tests (including compare_baseline_vs_enhanced)
- test_api.py — 7 tests (using `with TestClient(app) as client:` fixture)
- Total: 20 tests, 85% coverage
- .github/workflows/test.yml — CI/CD on push to main

### Infrastructure
- railway.toml + nixpacks.toml + Procfile — Railway deployment
- Dockerfile + docker-compose.yml — local container option
- requirements.txt — unpinned for cross-platform, pinned for Railway
- .env — API_KEY + ALLOWED_ORIGINS (never committed)
- .env.example — safe to commit
- .gitignore — excludes .env, *.csv logs, *.joblib, __pycache__
- generate_key.py — one-time key generation
- DEMO.md — 6 copy-paste commands for recruiters

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

## Completed

- PROMPT 006 — API auth, rate limiting, CORS, .env
- PROMPT 007 — 20 tests, 85% coverage, CI/CD
- PROMPT 008 — Live weather, OSM, mock adapters, /data/source
- PROMPT 009 — Drift detection, auto-retraining, /pipeline endpoints
- PROMPT 010 — Railway deployment, Streamlit dashboard, DEMO.md, UptimeRobot

## Pending

- PROMPT 011 — Emissions and CO2 layer
- PROMPT 012 — Hajj and mass gathering mode
- PROMPT 013 — Demand intervention and commuter recommendations

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

# Local Dashboard
streamlit run streamlit_app/dashboard.py
# → http://localhost:8501

# Docker
docker-compose up --build
```

---

## Instructions for AI Assistant

1. Never remove Saudi-specific behavioral patterns — they are the core differentiator
2. Keep src/ modular — config, data, model, adapters, pipeline stay separate
3. Dashboard has 5 tabs: Hourly Patterns → Zone Analysis → Weather Impact → Model Insights → Forecasting
4. All charts use PALETTE from config.py — no hardcoded colors
5. Recommendations must be operational and specific — not generic data science output
6. Update README roadmap checkboxes when new features are added
7. requirements.txt uses >= not == for cross-platform compatibility
8. Docker exposes port 8000 (API) and 8501 (Streamlit)
9. validate_data() must pass 5/5 before any model changes are committed
10. Every new prediction endpoint must log to predictions_log.csv via log_prediction()
11. SHAP explanation must be included in any new /predict variant
12. Follow IMPROVEMENT_CHAIN_V2.md for next development priorities
13. Encoding dicts are in src/model.py — never assume they are in src/config.py
14. prepare_features() cannot be used for live single-row inference — build X_row manually
15. apply_hourly_patterns() must always be called between generate_traffic_data()
    and add_lag_features() — it creates the congestion_score column both depend on
16. detect_anomalies() returns anomaly_flag (int), not is_anomaly
17. forecast_congestion(df, zone, hours_ahead) — zone is second positional arg
18. After any app.py change, run tests locally before pushing — Railway auto-deploys
19. TestClient tests must use `with TestClient(app) as client:` to trigger lifespan
