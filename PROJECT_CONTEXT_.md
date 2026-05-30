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

These are hard-won facts discovered during PROMPT 006 implementation.
Every future prompt must respect them.

### Function signatures
- `train_xgboost(X, y)` — takes separate feature matrix and target series, not a dataframe
- `prepare_features(df)` — returns (X, y, feature_cols). Always expects `congestion_score`
  column. Cannot be used for single-row live inference.
- `explain_prediction(model, X_row_df, feature_names_list)` — X_row must be a DataFrame,
  not a dict. Returns `{top_factors: [...], plain_english: str}`
- `log_prediction(prediction_dict, explanation_dict)` — two separate arguments
- `predict_single(city, zone, hour, vehicle_count, avg_speed, weather, road_type,
  rush_hour, is_weekend, is_late_night, event, hour_multiplier)` — individual keyword args

### Where things live
- WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING — in `src/model.py`
- PALETTE, CONGESTION_THRESHOLDS, HOURLY_MULTIPLIERS, WEATHER_SPEED_IMPACT,
  FRIDAY_PRAYER_HOURS, SAUDI_CITIES — in `src/config.py`

### Correct startup sequence for app.py lifespan
```python
df = generate_traffic_data(city="Riyadh")
df = apply_hourly_patterns(df, city="Riyadh")   # creates congestion_score
df = add_lag_features(df)                        # requires congestion_score
X, y, feature_cols = prepare_features(df)
model, _, _        = train_xgboost(X, y)
```
Skipping `apply_hourly_patterns()` causes KeyError: congestion_score in add_lag_features.

### Building X_row for live inference
`prepare_features()` cannot be used for a single live request because it requires
`congestion_score`. Build X_row manually:
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
    "vehicle_count_lag_1h" : p["vehicle_count"],   # approximation
    "vehicle_count_lag_2h" : p["vehicle_count"],   # approximation
    "congestion_lag_1h"    : 0.0,
    "rolling_mean_3h"      : p["vehicle_count"],   # approximation
    "rolling_std_3h"       : 0.0,
}
X_row = pd.DataFrame([row])[app.state.feature_cols]
```

---

## Current State (Complete)

### src/config.py
- All constants, city profiles, thresholds
- PALETTE, CONGESTION_THRESHOLDS, HOURLY_MULTIPLIERS, WEATHER_SPEED_IMPACT
- FRIDAY_PRAYER_HOURS, SAUDI_CITIES

### src/data.py
- generate_traffic_data() — Poisson-based synthetic generation per city profile
- apply_hourly_patterns() — Saudi behavioral calibration, prayer drop, sandstorm,
  creates congestion_score column
- add_lag_features() — 1h/2h vehicle lag, 1h congestion lag, 3h rolling mean/std
- validate_data() — 5 statistical checks, returns PASS/FAIL report table

### src/model.py
- WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING — encoding dicts
- prepare_features() — categorical encoding, feature matrix construction
- train_xgboost(X, y) — XGBoost with early stopping, returns (model, X_test, y_test)
- evaluate_models() — Linear Regression, Random Forest, XGBoost comparison
- congestion_level() — score to human-readable level classification
- get_recommendation() — operational recommendation per level and context
- predict_single() — single prediction from raw inputs, returns full result dict
- compare_baseline_vs_enhanced() — lag feature improvement measurement
- detect_anomalies() — rolling 7-day expected vs actual, 4 severity levels
- forecast_congestion() — multi-horizon forecast with confidence intervals
- compare_arima_vs_xgboost() — ARIMA vs XGBoost MAE at +1h, +2h, +3h
- explain_prediction(model, X_row_df, feature_names) — SHAP TreeExplainer,
  returns {top_factors: [...], plain_english: str}
- log_prediction(prediction_dict, explanation_dict) — appends to predictions_log.csv

### app.py
- FastAPI with lifespan startup: generate → apply_hourly_patterns → lag features →
  prepare_features → train_xgboost
- Authentication: X-API-Key header via APIKeyHeader dependency
- Rate limiting: slowapi — 60/min /predict, 20/min /anomalies + /forecast + /batch
- CORS: configurable via ALLOWED_ORIGINS in .env
- 6 endpoints: /, /health (public), /predict, /predict/batch, /anomalies, /forecast
- /predict builds X_row manually for SHAP — does not call prepare_features
- Imports pandas as pd and datetime at top level

### streamlit_app/dashboard.py
- 5 interactive tabs
- Anomaly alert banner at top when any zone is flagged
- Tab 1 — Hourly Patterns: vehicle count and congestion by hour
- Tab 2 — Zone Analysis: weekly heatmap + zone comparison + anomaly log
- Tab 3 — Weather Impact: speed and congestion distribution by weather
- Tab 4 — Model Insights: model comparison + feature importance + SHAP panel + audit trail
- Tab 5 — Forecasting: +1h/+2h/+3h chart with confidence band + traffic light cards

### Infrastructure
- Dockerfile + docker-compose.yml — containerized deployment
- requirements.txt — unpinned versions for cross-platform compatibility
- .env — API_KEY + ALLOWED_ORIGINS (never committed)
- .env.example — safe to commit, documents required variables
- .gitignore — excludes .env, predictions_log.csv, pipeline_log.csv, *.joblib
- generate_key.py — run once to generate .env with secure 64-char hex key
- predictions_log.csv — audit trail, auto-created on first prediction
- README.md — full documentation with architecture, API examples, validation output, roadmap
- IMPROVEMENT_CHAIN_V2.md — prompt chain targeting production deployment

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

- API authentication — X-API-Key header, 401 on invalid/missing key (PROMPT 006)
- Rate limiting — slowapi, per-IP, per-endpoint limits (PROMPT 006)
- CORS configuration — localhost only in dev, configurable for production (PROMPT 006)
- .env + .gitignore + .env.example (PROMPT 006)

## Pending

- Automated test suite with CI/CD (PROMPT 007)
- Real data adapters — OpenStreetMap, Open-Meteo weather API (PROMPT 008)
- Drift detection and automated nightly retraining (PROMPT 009)
- Cloud deployment — public URL on Railway + Streamlit Cloud (PROMPT 010)

---

## How to Run

```bash
# Generate API key (run once)
py generate_key.py

# Validate data first
py -c "from src.data import validate_data; validate_data(city='Riyadh')"

# Local
pip install -r requirements.txt
py -m uvicorn app:app --reload              # API → localhost:8000/docs
streamlit run streamlit_app/dashboard.py   # Dashboard → localhost:8501

# Docker
docker-compose up --build
```

## Testing the API

```powershell
# Health check (no key required)
Invoke-WebRequest -Uri "http://localhost:8000/health"

# No key → 401
Invoke-WebRequest -Uri "http://localhost:8000/predict" -Method POST `
  -ContentType "application/json" `
  -Body '{"city":"Riyadh","zone":"Zone_1","hour":8,...}'

# Valid key → prediction
$key = (Get-Content .env | Where-Object { $_ -match "^API_KEY=" }) -replace "^API_KEY=",""
Invoke-WebRequest -Uri "http://localhost:8000/predict" -Method POST `
  -ContentType "application/json" `
  -Headers @{"X-API-Key" = $key} `
  -Body '{"city":"Riyadh","zone":"Zone_1","hour":8,"vehicle_count":320,"avg_speed":35,"weather":"clear","road_type":"highway","rush_hour":1,"is_weekend":0,"is_late_night":0,"event":0,"hour_multiplier":1.4}'
```

---

## Instructions for AI Assistant

1. Never remove Saudi-specific behavioral patterns — they are the core differentiator
2. Keep src/ modular — config, data, model stay separate
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
