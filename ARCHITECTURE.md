# Smart City Traffic Intelligence System — Technical Architecture

> **Production-grade architecture for Vision 2030 smart city infrastructure**  
> Multi-tenant, cloud-native, enterprise-ready traffic prediction platform

---

## System Architecture Diagram

```mermaid
graph TB
    subgraph "🔌 DATA INGESTION LAYER"
        WA["🌐 Weather API<br/>Open-Meteo"]
        IoT["📡 IoT Sensors<br/>Mock Adapter"]
        OSM["🗺️ Road Network<br/>OpenStreetMap"]
    end

    subgraph "🔐 API GATEWAY & AUTH"
        AUTH["API Key Validation<br/>X-API-Key Header"]
        CORS["CORS Middleware<br/>Multi-Origin Support"]
        RATE["Rate Limiter<br/>SlowAPI"]
    end

    subgraph "✅ DATA VALIDATION ENGINE"
        VAL1["KS Test<br/>Coefficient of Variation < 0.60"]
        VAL2["Autocorrelation<br/>Lag-1 > 0.50"]
        VAL3["Cultural Pattern Check<br/>Friday Prayer Drop ≥ 85%"]
        VAL4["Late Night Activity<br/>Ratio ≥ 0.70"]
        VAL5["Weather Impact<br/>Sandstorm 0.35-0.45 reduction"]
    end

    subgraph "🔧 FEATURE ENGINEERING"
        FE1["Temporal Features<br/>hour, day_of_week<br/>rush_hour, weekend"]
        FE2["Domain Features<br/>weather, road_type<br/>event, multiplier"]
        FE3["Lag Features<br/>vehicle_count_lag_1h/2h<br/>congestion_lag_1h"]
        FE4["Rolling Statistics<br/>rolling_mean_3h<br/>rolling_std_3h"]
    end

    subgraph "🤖 MODEL TRAINING PIPELINE"
        ML1["Linear Regression<br/>Baseline | MAE | RMSE | R²"]
        ML2["Random Forest<br/>100 estimators<br/>Non-linear capture"]
        ML3["XGBoost ⭐<br/>n_est=200, depth=5<br/>learning_rate=0.1"]
        EVAL["Model Comparison<br/>Best: XGBoost"]
    end

    subgraph "📊 PREDICTION ENGINE"
        PRED["Single/Batch Prediction<br/>Congestion Score 0-1"]
        LEVELS["Classification Layer<br/>Low | Moderate | High | Critical"]
        SHAP["SHAP Explainability<br/>Top 3 Factors<br/>+ Plain English"]
    end

    subgraph "🚨 ANOMALY DETECTION"
        ANOM["Rolling 7-Day Window<br/>Expected vs Actual"]
        SEVERITY["Anomaly Classifier<br/>4 Severity Levels"]
        REC1["Auto-Recommendations<br/>Severity → Action"]
    end

    subgraph "🔮 MULTI-HORIZON FORECASTING"
        FC1["XGBoost Forecast<br/>+1h, +2h, +3h ahead"]
        FC2["ARIMA Comparison<br/>Horizon Analysis"]
        CONF["Confidence Intervals<br/>Upper/Lower Bounds"]
    end

    subgraph "♻️ EMISSIONS & SUSTAINABILITY"
        EMIS["Fuel Consumption Model<br/>Vehicle-based LPH calculation"]
        CO2["CO2 Estimation<br/>2.31 kg CO2/litre"]
        GREEN["Green Initiative Flag<br/>Threshold: 500 kg CO2/hr"]
    end

    subgraph "📝 AUDIT & LOGGING"
        LOG["Prediction Audit Trail<br/>predictions_log.csv"]
        SCHEMA["Schema:<br/>timestamp, city, zone, hour<br/>weather, score, level, factors<br/>co2_kg, fuel_litres"]
    end

    subgraph "🔄 RETRAINING & DRIFT"
        DRIFT["Drift Score Calculation<br/>Model Performance Monitor"]
        RETRAIN["Automated Retraining<br/>Nightly @ 03:00<br/>Threshold: 1.3 drift"]
        PIPELINE["Pipeline Orchestration<br/>Manual Trigger Available"]
    end

    subgraph "🌍 CITY CONFIGURATION"
        CITY1["Riyadh<br/>Saudi Schedule<br/>Zones: 5"]
        CITY2["NEOM<br/>Saudi Schedule<br/>Zones: 5"]
        CITY3["Dubai<br/>Saudi Schedule<br/>Zones: 5"]
        CITY4["Karachi<br/>Standard Schedule<br/>Zones: 5"]
    end

    subgraph "🏗️ API ENDPOINTS"
        EP1["POST /predict<br/>Single Zone<br/>Rate: 60/min"]
        EP2["POST /predict/batch<br/>Up to 20 Zones<br/>Rate: 20/min"]
        EP3["GET /anomalies<br/>All Active Anomalies<br/>Rate: 20/min"]
        EP4["GET /forecast<br/>1h/2h/3h Ahead<br/>Rate: 20/min"]
    end

    subgraph "📈 DASHBOARDS & UI"
        STREAMLIT["Streamlit Dashboard<br/>5 Interactive Tabs:<br/>• Hourly Patterns<br/>• Zone Analysis<br/>• Weather Impact<br/>• Model Insights<br/>• Forecasting"]
        HTML["HTML Dashboard<br/>Client-Side Rendering<br/>Injected API Key"]
        DOCS["FastAPI Docs<br/>/docs | /redoc"]
    end

    subgraph "🐳 DEPLOYMENT"
        DOCKER["Docker Compose<br/>API Service + Dashboard"]
        CLOUD["Cloud Deployment<br/>Railway | Render"]
        LOCAL["Local Development<br/>Uvicorn + Streamlit"]
    end

    %% Data Flow
    WA --> AUTH
    IoT --> AUTH
    OSM --> AUTH
    
    AUTH --> VAL1 & VAL2 & VAL3 & VAL4 & VAL5
    RATE --> VAL1 & VAL2 & VAL3 & VAL4 & VAL5
    CORS --> VAL1 & VAL2 & VAL3 & VAL4 & VAL5

    VAL1 & VAL2 & VAL3 & VAL4 & VAL5 --> FE1 & FE2 & FE3 & FE4

    FE1 & FE2 & FE3 & FE4 --> ML1 & ML2 & ML3
    ML1 & ML2 & ML3 --> EVAL

    EVAL --> PRED
    PRED --> LEVELS
    LEVELS --> SHAP

    SHAP --> ANOM
    ANOM --> SEVERITY
    SEVERITY --> REC1

    SHAP --> FC1 & FC2
    FC1 & FC2 --> CONF

    LEVELS --> EMIS
    EMIS --> CO2
    CO2 --> GREEN

    SHAP --> LOG
    LOG --> SCHEMA

    SCHEMA --> DRIFT
    DRIFT --> RETRAIN
    RETRAIN --> PIPELINE

    CITY1 & CITY2 & CITY3 & CITY4 -.->|Config| FE1

    PRED --> EP1
    ANOM --> EP3
    CONF --> EP4
    SHAP --> EP2

    EP1 & EP2 & EP3 & EP4 --> STREAMLIT & HTML & DOCS

    STREAMLIT & HTML & DOCS --> DOCKER
    DOCKER --> CLOUD & LOCAL

    PIPELINE -.->|Feedback Loop| EVAL

    style AUTH fill:#e1f5ff
    style RATE fill:#e1f5ff
    style CORS fill:#e1f5ff
    style ML3 fill:#fff9c4
    style EVAL fill:#fff9c4
    style PIPELINE fill:#c8e6c9
    style DRIFT fill:#c8e6c9
    style GREEN fill:#ffccbc
```

---

## Complete Technical Functionalities

### **1. Data Ingestion & Adapters**
- ✅ **Multi-source adapter pattern** — Weather API, IoT sensors, OpenStreetMap
- ✅ **Configurable data source switching** — Runtime selection without restart
- ✅ **Open-Meteo weather integration** — No API key required, free tier
- ✅ **OpenStreetMap Overpass API** — Road network data ingestion
- ✅ **Mock deterministic data generator** — Always available, reproducible (seed-based)

---

### **2. API Security & Rate Limiting**
- ✅ **API key authentication** — X-API-Key header validation
- ✅ **Rate limiting per endpoint** — 60/min (predict), 20/min (anomalies, forecast)
- ✅ **Per-IP rate limiting** — SlowAPI integration prevents abuse
- ✅ **CORS middleware** — Configurable multi-origin support
- ✅ **Environment-based credential management** — .env with secure key generation
- ✅ **HTTP status codes** — 401 (invalid key), 429 (rate limit exceeded)

---

### **3. Data Validation Engine**
- ✅ **5-point statistical validation suite**:
  - Coefficient of variation (CV < 0.60)
  - Autocorrelation lag-1 (> 0.50)
  - Friday prayer drop (≥ 85% reduction at 12:00-13:00)
  - Late-night activity ratio (≥ 0.70 vs evening peak)
  - Sandstorm speed reduction (0.35-0.45)
- ✅ **KS test** — Kolmogorov-Smirnov distribution validation
- ✅ **Pre-training validation gate** — Blocks model training on invalid data
- ✅ **Detailed validation reports** — Pass/fail per check with metrics

---

### **4. Feature Engineering Pipeline**
- ✅ **Temporal features**:
  - Hour of day (0-23), Day of week (Monday-Sunday)
  - Rush hour flag (7,8,17,18), Weekend classifier, Late night identifier (21-23, 0)
  
- ✅ **Domain-specific features**:
  - Weather condition encoding (clear, sandstorm, dust, rain, fog, humid)
  - Road type classification (highway, arterial, local)
  - Special event flag (binary), Hourly traffic multiplier
  
- ✅ **Lag features** — Vehicle count lag-1h/2h, Congestion score lag-1h
  
- ✅ **Rolling statistics** — 3-hour rolling mean & std dev (per zone)
  
- ✅ **City-specific behavioral patterns**:
  - Friday prayer period (12:00-13:00, 90% traffic reduction)
  - Ramadan schedule shift (+4 hours from standard)
  - Sandstorm speed impact (60% of normal), Late-night activity

---

### **5. Machine Learning Models**
- ✅ **Baseline model** — Linear Regression (explainability baseline)
- ✅ **Intermediate model** — Random Forest (n_estimators=100, non-linear interactions)
- ✅ **Production model** — XGBoost (n_estimators=200, max_depth=5, learning_rate=0.1)
- ✅ **Hyperparameter tuning** — Early stopping (20 rounds), subsample=0.8
- ✅ **Model comparison framework** — MAE, RMSE, R² metrics
- ✅ **Train/test split** — 80/20 stratified
- ✅ **Model persistence** — joblib serialization/deserialization

---

### **6. Prediction Engine**
- ✅ **Single zone predictions** — /predict endpoint
- ✅ **Batch predictions** — Up to 20 zones per request (/predict/batch)
- ✅ **Congestion score generation** — 0-1 normalized scale
- ✅ **Classification layer** — Low, Moderate, High, Critical levels
- ✅ **Operational recommendations** — Context-aware directives
- ✅ **Real-time inference** — Sub-100ms latency on standard hardware

---

### **7. Explainability & Interpretability**
- ✅ **SHAP TreeExplainer integration** — Model-agnostic explanation
- ✅ **Top-3 factor extraction** — Feature importance ranking
- ✅ **Direction analysis** — Increasing/reducing congestion impact
- ✅ **Plain English explanations** — Business-readable summaries
- ✅ **Feature importance visualization** — matplotlib/seaborn charts
- ✅ **SHAP value storage** — Audit trail compatibility

---

### **8. Anomaly Detection**
- ✅ **7-day rolling window baseline** — Per zone, per hour
- ✅ **Actual vs expected comparison** — Statistical deviation
- ✅ **Anomaly ratio calculation** — vehicle_count / expected
- ✅ **4-level severity classification**:
  - Normal (< 1.5x), Elevated (1.5-2.0x)
  - Anomalous (2.0-3.0x), Critical Anomaly (≥ 3.0x)
- ✅ **Automatic recommendation generation** — Severity → action mapping
- ✅ **Per-zone, per-hour tracking** — Granular anomaly detection

---

### **9. Multi-Horizon Forecasting**
- ✅ **XGBoost forecasting** — +1h, +2h, +3h ahead predictions
- ✅ **ARIMA model comparison** — statsmodels integration
- ✅ **Confidence intervals** — Upper/lower bounds via residual std
- ✅ **Schedule-aware prediction** — Hourly multipliers applied
- ✅ **Horizon-specific performance** — MAE per horizon comparison
- ✅ **Model selection guidance** — XGBoost for +1h, ARIMA for +2h/+3h

---

### **10. Emissions & Sustainability Tracking**
- ✅ **Fuel consumption model**:
  - Low: 6.5 L/100 vehicles/hr
  - Moderate: 9.2 L/100 vehicles/hr
  - High: 13.8 L/100 vehicles/hr
  - Critical: 18.4 L/100 vehicles/hr
- ✅ **CO2 emission calculation** — 2.31 kg CO2/litre (IPCC standard)
- ✅ **Green Initiative flagging** — 500 kg CO2/hr threshold
- ✅ **Zone-level emissions aggregation** — Per-zone CO2 tracking
- ✅ **Time-period emissions summary** — Daily, hourly breakdown

---

### **11. Audit & Compliance Logging**
- ✅ **Prediction audit trail** — predictions_log.csv immutable store
- ✅ **Log schema**:
  - Timestamp (ISO 8601), City, Zone, Hour
  - Weather condition, Congestion score & level
  - Top 3 factors, Plain English explanation
  - CO2 kg, Fuel litres
- ✅ **CSV persistence** — Append-only mode for compliance
- ✅ **Retroactive emissions calculation** — If missing
- ✅ **Peak hour/zone analysis** — Derived from audit logs

---

### **12. Model Drift & Automated Retraining**
- ✅ **Drift score calculation** — Model performance degradation metric
- ✅ **Drift threshold** — 1.3x trigger for retraining
- ✅ **Nightly retraining scheduler** — 03:00 UTC daily (APScheduler)
- ✅ **Manual pipeline trigger** — /pipeline/trigger endpoint
- ✅ **Last retrain timestamp tracking** — Persistence across restarts
- ✅ **Automated data refresh** — New data ingestion before retrain

---

### **13. City Configuration & Multi-Tenancy**
- ✅ **City profile system** — Single parameter scales to new cities:
  - Riyadh (Saudi, 5 zones, sandstorm focus)
  - NEOM (Saudi, 5 zones, sandstorm focus)
  - Dubai (Saudi, 5 zones, sandstorm/humidity)
  - Karachi (Standard, 5 zones, rain/fog)
- ✅ **Schedule switching** — Saudi vs standard timezone handling
- ✅ **Weekend definition** — Fri-Sat vs Sat-Sun
- ✅ **Weather-specific multipliers** — Per city calibration
- ✅ **Timezone support** — Asia/Riyadh, Asia/Dubai, Asia/Karachi
- ✅ **New city onboarding** — Single config dict entry required

---

### **14. REST API Architecture**
- ✅ **FastAPI framework** — Async, auto-documentation
- ✅ **6 core endpoints**:
  - `GET /health` (no auth, health check)
  - `GET /api/info` (no auth, service info)
  - `POST /predict` (authenticated, 60/min rate limit)
  - `POST /predict/batch` (authenticated, 20/min rate limit)
  - `GET /anomalies` (authenticated, 20/min rate limit)
  - `GET /forecast` (authenticated, 20/min rate limit)
- ✅ **Data source management**:
  - `GET /data/source` (read active)
  - `POST /data/source` (switch source)
- ✅ **Pipeline control**:
  - `GET /pipeline/status` (drift info)
  - `POST /pipeline/trigger` (manual retrain)
- ✅ **Emissions reporting** — `GET /emissions/summary` (aggregate CO2)
- ✅ **Pydantic request validation** — Auto-schema generation
- ✅ **Lifespan context manager** — Startup/shutdown hooks

---

### **15. Dashboard & Visualization**
- ✅ **Streamlit interactive dashboard** (5 tabs):
  - Hourly Patterns (vehicle count + congestion by hour)
  - Zone Analysis (weekly heatmap + anomalies)
  - Weather Impact (speed/congestion vs condition)
  - Model Insights (comparison, feature importance, SHAP)
  - Forecasting (1h/2h/3h with confidence bands)
- ✅ **HTML dashboard** — Client-side rendering with injected API key
- ✅ **FastAPI auto-docs** — /docs Swagger, /redoc ReDoc
- ✅ **matplotlib/Seaborn visualizations** — Publication-grade charts
- ✅ **Traffic light indicators** — Congestion level colors

---

### **16. Containerization & Deployment**
- ✅ **Docker Compose orchestration** — API + Dashboard services
- ✅ **Dockerfile production image** — Multi-stage optimized builds
- ✅ **Environment variable injection** — .env support
- ✅ **Health check endpoints** — Kubernetes-ready
- ✅ **Cloud-ready deployment**:
  - Railway.app support
  - Render.com support
  - AWS ECS/Lambda compatible
- ✅ **Local dev setup** — Uvicorn + Streamlit parallel

---

### **17. Data Processing & Transformation**
- ✅ **Pandas DataFrames** — Efficient tabular processing
- ✅ **NumPy vectorized operations** — 30-day simulation in seconds
- ✅ **Scikit-learn preprocessing** — LabelEncoder for categoricals
- ✅ **Synthetic data generation** — Poisson + sinusoidal patterns
- ✅ **Data interpolation** — Filling lag features with rolling transforms
- ✅ **Normalization/clipping** — vehicle_count 0-500, speed 20-100

---

### **18. Statistical & Mathematical Operations**
- ✅ **Coefficient of variation** — Data spread measurement
- ✅ **Autocorrelation analysis** — Temporal dependency detection
- ✅ **Rolling statistics** — 3-hour window mean/std
- ✅ **Confidence interval estimation** — Residual std-based bounds
- ✅ **Anomaly detection thresholds** — 2x expected → flagged
- ✅ **Emissions calculations** — Fuel LPH × vehicle count × hours × CO2 factor

---

### **19. Error Handling & Validation**
- ✅ **HTTP exception handling** — 401, 429, 502 status codes
- ✅ **Pydantic validation** — Type checking, field bounds
- ✅ **Graceful adapter fallback** — Mock data if external API fails
- ✅ **NaN/null handling** — fillna with appropriate strategies
- ✅ **Division by zero protection** — replace with np.nan before division
- ✅ **Try-except blocks** — ARIMA fitting failures handled

---

### **20. Performance Optimization**
- ✅ **In-memory model caching** — Loaded at startup, reused per request
- ✅ **Vectorized feature engineering** — groupby + transform operations
- ✅ **Early stopping** — XGBoost overfitting prevention
- ✅ **Batch prediction efficiency** — Up to 20 predictions per request
- ✅ **Async API** — FastAPI with async/await
- ✅ **Sub-100ms inference latency** — Tested on standard hardware

---

## Tech Stack

| Category | Technologies |
|----------|---------------|
| **Language** | Python 3.11 |
| **Web Framework** | FastAPI, Uvicorn |
| **ML/AI** | XGBoost, Scikit-learn, SHAP, Statsmodels |
| **Data Processing** | Pandas, NumPy |
| **Visualization** | Matplotlib, Seaborn, Streamlit |
| **Authentication** | python-dotenv, APIKeyHeader |
| **Rate Limiting** | SlowAPI |
| **Scheduling** | APScheduler |
| **Serialization** | joblib, Pydantic |
| **Deployment** | Docker, Docker Compose |
| **API Documentation** | Swagger UI, ReDoc |

---

## Getting Started

### Local Development
```bash
pip install -r requirements.txt
python generate_key.py
python -m uvicorn app:app --reload
streamlit run streamlit_app/dashboard.py
```

### Docker Deployment
```bash
docker-compose up --build
# API       → http://localhost:8000/docs
# Dashboard → http://localhost:8501
```

### Cloud Deployment
- Railway: https://railway.app
- Render: https://render.com
- AWS ECS/Lambda

---

## API Usage

### Authentication
```bash
X-API-Key: your_secure_key_here
```

### Single Prediction
```bash
curl -X POST http://localhost:8000/predict \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Riyadh",
    "zone": "Zone_1",
    "hour": 8,
    "vehicle_count": 320,
    "avg_speed": 35,
    "weather": "clear",
    "road_type": "highway",
    "rush_hour": 1,
    "is_weekend": 0,
    "is_late_night": 0,
    "event": 0,
    "hour_multiplier": 1.4
  }'
```

---

## Monitoring & Observability

- **Drift Score**: `/pipeline/status` — Real-time model performance tracking
- **Audit Logs**: `predictions_log.csv` — Complete prediction history
- **Emissions Summary**: `/emissions/summary` — CO2 tracking & green initiative
- **Health Check**: `/health` — Service availability verification

---

*Architecture documentation for Smart City Traffic Intelligence System v4.1.0*
