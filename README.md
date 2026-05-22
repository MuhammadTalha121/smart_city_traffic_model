# Smart City Traffic Intelligence System

> A production-ready traffic congestion prediction framework for Vision 2030 smart cities.  
> City-configurable. Culturally calibrated. Deployable.

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

- Predicts zone-level congestion scores in real time
- Models Saudi-specific patterns invisible to standard systems:
  - Friday prayer drop (12:00–13:00): ~90% traffic reduction
  - Late-night activity (21:00–23:00): comparable to evening rush hour
  - Ramadan schedule shift: entire daily cycle moves by ~4 hours
  - Sandstorm protocol: most disruptive weather event in Gulf cities
- Provides operational recommendations, not just numbers
- Scales to any city via a single configuration parameter

---

## Architecture

```
smart-city-traffic-model/
├── app.py                          # FastAPI REST API
├── docker-compose.yml              # Container orchestration
├── Dockerfile                      # Container definition
├── requirements.txt
├── README.md
├── PROJECT_CONTEXT.md
│
├── src/
│   ├── config.py                   # City profiles, constants, thresholds
│   ├── data.py                     # Data generation and pattern engineering
│   └── model.py                    # Training, evaluation, prediction logic
│
├── streamlit_app/
│   └── dashboard.py                # Interactive operations dashboard
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
- **Friday prayer (12:00–13:00)** produces the lowest traffic of the entire week across all zones
- **Late-night hours (21:00–23:00)** stay as congested as evening rush — unique to Saudi cities
- **Highway zones** show sharper congestion peaks than arterial or local roads during rush hours

---

## Modeling

| Model | Purpose |
|---|---|
| Linear Regression | Baseline — establishes minimum explainable variance |
| Random Forest | Captures non-linear interactions between features |
| XGBoost | Best performer — congestion regression with feature importance |

All models evaluated on MAE, RMSE, and R² on a held-out test set.  
XGBoost selected for deployment based on comparative evaluation.

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Service info |
| `/health` | GET | Health check |
| `/predict` | POST | Single zone prediction |
| `/predict/batch` | POST | Up to 20 zones simultaneously |

### Sample Request

```json
POST /predict
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

### Sample Response

```json
{
  "city": "Riyadh",
  "zone": "Zone_1",
  "hour": 8,
  "weather": "sandstorm",
  "congestion_score": 0.7823,
  "congestion_level": "Critical",
  "recommendation": "ALERT: Zone_1 critically congested. Sandstorm protocol active — reduce speed limits. Initiate emergency traffic management."
}
```

---

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run API
uvicorn app:app --reload
# → http://127.0.0.1:8000/docs

# Run Dashboard
streamlit run streamlit_app/dashboard.py
# → http://localhost:8501
```

## Running with Docker

```bash
# Build and start both services
docker-compose up --build

# API  → http://localhost:8000/docs
# Dashboard → http://localhost:8501
```

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
- [x] Core Statistical Foundation Validation (PROMPT 001)
- [x] Professional visualization suite
- [x] XGBoost feature importance with business interpretation
- [x] Multi-model evaluation and comparison
- [x] FastAPI REST deployment
- [x] Streamlit operations dashboard
- [x] Docker containerization
- [ ] Real IoT data integration layer
- [ ] Automated retraining pipeline

---

## Tech Stack

`Python 3.11` `FastAPI` `Streamlit` `XGBoost` `Scikit-learn` `Pandas` `NumPy` `Matplotlib` `Seaborn` `Docker` `Pydantic`

---

*Proof of concept targeting Saudi Arabia's Vision 2030 smart city infrastructure.*  
*Built by Muhammad Talha — [GitHub](https://github.com/MuhammadTalha121)*
