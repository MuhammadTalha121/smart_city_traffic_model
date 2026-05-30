# Smart City Traffic Intelligence System

> A production-ready traffic congestion prediction framework for Vision 2030 smart cities.  
> City-configurable. Culturally calibrated. Statistically validated. Deployable.

---

## Problem

Riyadh's population will reach 15–20 million by 2030.  
NEOM, Diriyah, and Qiddiya are being built from scratch — with no historical traffic baseline.

Traditional traffic management systems are:
- **Reactive** — they respond after congestion forms, not before
- **Static** — fixed signal timings with no real-time adaptation
- **Culturally blind** — built on Western behavioral models that don't apply to Saudi cities

This system addresses all three.

---

## What This System Does

- Validates synthetic traffic data against statistical benchmarks before any model trains
- Predicts zone-level congestion scores in real time with SHAP-based explanations
- Detects anomalous traffic events before they become incidents
- Forecasts congestion 1, 2, and 3 hours ahead with confidence intervals
- Models Saudi-specific patterns invisible to standard systems:
  - Friday prayer drop (12:00–13:00): ~90% traffic reduction — statistically verified
  - Late-night activity (21:00–23:00): comparable to evening rush hour
  - Ramadan schedule shift: entire daily cycle moves ~4 hours
  - Sandstorm protocol: 40% speed reduction — most disruptive weather event in Gulf cities
- Authenticates every API call — not an open endpoint
- Rate-limits by IP — prevents abuse without infrastructure changes
- Provides operational recommendations, not just numbers
- Logs every prediction to an auditable trail
- Scales to any city via a single configuration parameter

---

## Architecture

```
smart-city-traffic-model/
├── app.py                          # FastAPI REST API — authenticated, rate-limited
├── generate_key.py                 # Run once to create .env with secure API key
├── .env.example                    # Documents required environment variables
├── .gitignore                      # Excludes .env, predictions_log.csv, *.joblib
├── docker-compose.yml              # Container orchestration
├── Dockerfile                      # Container definition
├── requirements.txt
├── predictions_log.csv             # Audit trail — every prediction logged
├── README.md
├── PROJECT_CONTEXT.md
├── IMPROVEMENT_CHAIN_V2.md
│
├── src/
│   ├── config.py                   # City profiles, constants, thresholds
│   ├── data.py                     # Data generation, pattern engineering, lag features
│   └── model.py                    # Training, evaluation, prediction, anomaly detection,
│                                   # forecasting, SHAP explainability, encoding dicts
│
├── streamlit_app/
│   └── dashboard.py                # Interactive operations dashboard (5 tabs)
│
├── notebook/
│   └── smart_city_traffic_intelligence_system.ipynb
│
└── outputs/
    ├── hourly_pattern_riyadh.png
    ├── zone_congestion_riyadh.png
    ├── weekly_heatmap_riyadh.png
    ├── weather_impact_riyadh.png
    ├── feature_importance_riyadh.png
    └── model_comparison_riyadh.png
```

---

## Visualizations

### Hourly Traffic Pattern — Riyadh
![Hourly Pattern](outputs/hourly_pattern_riyadh.png)

### Weekly Congestion Heatmap
![Weekly Heatmap](outputs/weekly_heatmap_riyadh.png)

### Weather Impact Analysis
![Weather Impact](outputs/weather_impact_riyadh.png)

### Zone Congestion by Hour
![Zone Congestion](outputs/zone_congestion_riyadh.png)

---

## Key Findings

- **Sandstorms** reduce average speed by ~40% — the single biggest traffic disruptor in Riyadh
- **Friday prayer (12:00–13:00)** produces the lowest traffic of the entire week — 90% below weekday average
- **Late-night hours (21:00–23:00)** stay as congested as evening rush — unique to Saudi cities
- **Lag features** (1h, 2h, 3h lookback) capture traffic momentum — RMSE improved 10% over baseline
- **Anomaly detection** correctly flags events at 2x+ expected volume with severity escalation
- **XGBoost beats ARIMA at +1h** forecasting; ARIMA is more stable at +2h and +3h horizons

---

## Modeling Pipeline

| Component | Description |
|---|---|
| Data validation | 5 statistical checks — KS test, autocorrelation, prayer drop, late night, sandstorm |
| Lag features | 1h/2h vehicle count lag, 1h congestion lag, 3h rolling mean and std per zone |
| Linear Regression | Baseline — establishes minimum explainable variance |
| Random Forest | Captures non-linear interactions between features |
| XGBoost | Best performer — selected for deployment |
| Anomaly detection | Rolling 7-day expected vs actual — 4 severity levels |
| Forecasting | XGBoost + ARIMA comparison across 1h, 2h, 3h horizons |
| Explainability | SHAP TreeExplainer — top 3 factors with plain English summary |
| Audit trail | Every prediction logged to predictions_log.csv |

---

## Authentication

All endpoints except `/health` require an `X-API-Key` header.

```bash
# Generate your key (run once)
py generate_key.py
# → writes .env with a secure 64-character hex key

# All protected requests require the header
X-API-Key: your_key_here

# Missing or invalid key returns:
# HTTP 401 {"detail": "Invalid or missing API key."}
```

To add production domains, update `ALLOWED_ORIGINS` in `.env`:
```
ALLOWED_ORIGINS=https://traffic.yourdomain.com,https://dashboard.yourdomain.com
```

---

## Rate Limits

| Endpoint | Limit |
|---|---|
| `/predict` | 60 requests / minute / IP |
| `/predict/batch` | 20 requests / minute / IP |
| `/anomalies` | 20 requests / minute / IP |
| `/forecast` | 20 requests / minute / IP |

Exceeded limit returns `HTTP 429` with `Retry-After` header.

---

## API Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/` | GET | No | Service info |
| `/health` | GET | No | Health check |
| `/predict` | POST | Yes | Single zone prediction with SHAP explanation |
| `/predict/batch` | POST | Yes | Up to 20 zones simultaneously |
| `/anomalies` | GET | Yes | All current anomalies across all zones |
| `/forecast` | GET | Yes | 1h, 2h, 3h congestion forecast for a zone |

### Predict — Sample Request

```json
POST /predict
X-API-Key: your_key_here

{
  "city": "Riyadh",
  "zone": "Zone_1",
  "hour": 8,
  "vehicle_count": 320,
  "avg_speed": 35,
  "weather": "sandstorm",
  "road_type": "highway",
  "rush_hour": 1,
  "is_weekend": 0,
  "is_late_night": 0,
  "event": 0,
  "hour_multiplier": 1.4
}
```

### Predict — Sample Response

```json
{
  "city": "Riyadh",
  "zone": "Zone_1",
  "hour": 8,
  "weather": "sandstorm",
  "congestion_score": 0.7823,
  "congestion_level": "Critical",
  "recommendation": "ALERT: Zone_1 critically congested. Sandstorm protocol active — reduce speed limits. Initiate emergency traffic management.",
  "plain_english": "Congestion is primarily driven by average speed (reducing congestion), followed by vehicle count.",
  "explanation": [
    {"factor": "average speed", "direction": "reducing congestion", "impact": 0.1271},
    {"factor": "vehicle count", "direction": "increasing congestion", "impact": 0.0506},
    {"factor": "zone location", "direction": "reducing congestion", "impact": 0.0004}
  ]
}
```

### Anomalies — Sample Response

```json
GET /anomalies?city=Riyadh
X-API-Key: your_key_here

{
  "city": "Riyadh",
  "total_anomalies": 3,
  "anomalies": [
    {
      "zone": "Zone_2",
      "hour": 14,
      "weather": "sandstorm",
      "expected_vehicle_count": 89.4,
      "vehicle_count": 450.0,
      "anomaly_severity": "Critical Anomaly",
      "anomaly_recommendation": "CRITICAL: Zone_2 at 5.0x expected volume. Activate emergency protocol."
    }
  ]
}
```

### Forecast — Sample Response

```json
GET /forecast?city=Riyadh&zone=Zone_1
X-API-Key: your_key_here

{
  "city": "Riyadh",
  "zone": "Zone_1",
  "forecasts": [
    {"hours_ahead": 1, "forecast_hour": 9,  "predicted_score": 0.0412, "lower_bound": 0.0, "upper_bound": 0.1109, "congestion_level": "Low", "recommendation": "Zone_1 is clear. Normal operations."},
    {"hours_ahead": 2, "forecast_hour": 10, "predicted_score": 0.0343, "lower_bound": 0.0, "upper_bound": 0.1040, "congestion_level": "Low", "recommendation": "Zone_1 is clear. Normal operations."},
    {"hours_ahead": 3, "forecast_hour": 11, "predicted_score": 0.0343, "lower_bound": 0.0, "upper_bound": 0.1040, "congestion_level": "Low", "recommendation": "Zone_1 is clear. Normal operations."}
  ]
}
```

---

## Data Validation

Run `validate_data()` to verify all statistical properties before training:

```python
from src.data import validate_data
validate_data(city='Riyadh')
```

```
============================================================
  Data Validation Report — Riyadh
============================================================
                                   Check  Expected  Actual Status
Vehicle count — coefficient of variation    < 0.60  0.3105   PASS
                   Autocorrelation lag-1    > 0.50  0.7393   PASS
  Friday prayer drop (vs weekday midday)   >= 0.85  0.9088   PASS
         Late night / evening peak ratio   >= 0.70  0.7537   PASS
               Sandstorm speed reduction 0.35–0.45  0.3974   PASS
============================================================
  5 / 5 checks passed
============================================================
```

---

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Generate API key (run once)
py generate_key.py

# Validate data
py -c "from src.data import validate_data; validate_data(city='Riyadh')"

# Run API
py -m uvicorn app:app --reload
# → http://127.0.0.1:8000/docs

# Run Dashboard
streamlit run streamlit_app/dashboard.py
# → http://localhost:8501
```

## Running with Docker

```bash
# Build and start both services
docker-compose up --build

# API       → http://localhost:8000/docs
# Dashboard → http://localhost:8501
```

## Testing the API (PowerShell)

```powershell
# Health check — no key required
Invoke-WebRequest -Uri "http://localhost:8000/health"

# No key → 401
Invoke-WebRequest -Uri "http://localhost:8000/predict" -Method POST `
  -ContentType "application/json" `
  -Body '{"city":"Riyadh","zone":"Zone_1","hour":8,"vehicle_count":320,"avg_speed":35,"weather":"clear","road_type":"highway","rush_hour":1,"is_weekend":0,"is_late_night":0,"event":0,"hour_multiplier":1.4}'

# Valid key → prediction
$key = (Get-Content .env | Where-Object { $_ -match "^API_KEY=" }) -replace "^API_KEY=",""
Invoke-WebRequest -Uri "http://localhost:8000/predict" -Method POST `
  -ContentType "application/json" `
  -Headers @{"X-API-Key" = $key} `
  -Body '{"city":"Riyadh","zone":"Zone_1","hour":8,"vehicle_count":320,"avg_speed":35,"weather":"clear","road_type":"highway","rush_hour":1,"is_weekend":0,"is_late_night":0,"event":0,"hour_multiplier":1.4}'
```

---

## Dashboard Tabs

| Tab | What It Shows |
|---|---|
| Hourly Patterns | Vehicle count and congestion score by hour — Friday prayer drop visible |
| Zone Analysis | Weekly heatmap + zone comparison table + anomaly detection log |
| Weather Impact | Speed and congestion distribution by weather condition |
| Model Insights | Model comparison, feature importance, SHAP explainability, audit trail |
| Forecasting | 1h/2h/3h congestion forecast with confidence band and traffic light indicators |

---

## Cities Supported

| City | Weekend | Key Weather | Schedule |
|---|---|---|---|
| Riyadh | Fri–Sat | Sandstorm, Dust | Saudi |
| NEOM | Fri–Sat | Sandstorm, Dust | Saudi |
| Dubai | Fri–Sat | Sandstorm, Humid | Saudi |
| Karachi | Sat–Sun | Rain, Fog | Standard |

Adding a new city requires one dictionary entry in `src/config.py`.

---

## Roadmap

- [x] City-agnostic data generation pipeline
- [x] Saudi-specific hourly patterns (prayer, late-night, Ramadan)
- [x] Weather impact analysis with sandstorm modeling
- [x] Statistical data validation — 5 checks, 5/5 passing
- [x] Temporal lag features — 1h/2h vehicle count, 1h congestion, 3h rolling stats
- [x] Baseline vs enhanced model comparison with improvement metrics
- [x] Professional visualization suite with business labels
- [x] XGBoost feature importance — lag features ranked
- [x] Multi-model evaluation — Linear Regression, Random Forest, XGBoost
- [x] Anomaly detection — 4 severity levels, sandstorm spike verified at 5x
- [x] Multi-horizon forecasting — XGBoost vs ARIMA at +1h, +2h, +3h
- [x] SHAP explainability — top 3 factors with plain English summary
- [x] Prediction audit trail — every prediction logged to CSV
- [x] FastAPI REST deployment — /predict, /batch, /anomalies, /forecast
- [x] Streamlit operations dashboard — 5 interactive tabs
- [x] Docker containerization
- [x] API key authentication — X-API-Key header, 401 on invalid/missing
- [x] Rate limiting — 60/min on /predict, 20/min on /anomalies and /forecast
- [x] CORS configuration — localhost in dev, configurable for production
- [ ] Automated test suite with CI/CD
- [ ] Real IoT data integration layer
- [ ] Automated retraining pipeline
- [ ] Cloud deployment (Railway / Render / AWS)
- [ ] Multi-city comparative dashboard
- [ ] Vehicle-to-Infrastructure (V2I) data simulation

---

## Tech Stack

`Python 3.11` `FastAPI` `Streamlit` `XGBoost` `Scikit-learn` `SHAP` `Statsmodels` `Pandas` `NumPy` `Matplotlib` `Seaborn` `Docker` `Pydantic` `slowapi` `python-dotenv`

---

*Proof of concept targeting Saudi Arabia's Vision 2030 smart city infrastructure.*  
*Built by Muhammad Talha — [GitHub](https://github.com/MuhammadTalha121)*
