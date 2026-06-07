import os
from contextlib import asynccontextmanager
from pathlib import Path
import pandas as pd
from datetime import datetime
from src.model import WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler

from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features
from src.model import (
    train_xgboost, prepare_features, predict_single,
    detect_anomalies, forecast_congestion, explain_prediction,
    log_prediction, compute_emissions,
)
from src.adapters import get_adapter
from src.pipeline import run_pipeline, compute_drift_score
from src.config import GREEN_INITIATIVE_CO2_THRESHOLD_KG

load_dotenv()

API_KEY         = os.getenv("API_KEY")
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000",
).split(",")

# Dashboard HTML path — sits next to app.py
DASHBOARD_PATH = Path(__file__).parent / "dashboard.html"

limiter        = Limiter(key_func=get_remote_address)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
scheduler      = BackgroundScheduler()

VALID_SOURCES = ["weather", "osm", "mock"]


def require_api_key(key: str = Depends(api_key_header)):
    """Validate the X-API-Key header on every protected endpoint."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Server has no API key configured.")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return key


def _scheduled_pipeline():
    """Run nightly pipeline and print outcome to console."""
    print(f"[Scheduler] Running nightly pipeline at {datetime.now()}")
    result = run_pipeline(city="Riyadh")
    print(f"[Scheduler] Pipeline complete — drift: {result['drift_score']}, retrained: {result['retrained']}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Train model, start scheduler, share state across endpoints."""
    df = generate_traffic_data(city="Riyadh")
    df = apply_hourly_patterns(df, city="Riyadh")
    df = add_lag_features(df)

    X, y, feature_cols = prepare_features(df)
    model, _, _        = train_xgboost(X, y)

    app.state.df           = df
    app.state.model        = model
    app.state.feature_cols = feature_cols
    app.state.data_source  = "mock"
    app.state.last_retrain = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    scheduler.add_job(_scheduled_pipeline, "cron", hour=3, minute=0)
    scheduler.start()
    print("[Scheduler] Nightly retraining scheduled at 03:00")

    yield

    scheduler.shutdown()


app = FastAPI(
    title       = "Smart City Traffic Intelligence API",
    description = "Production-ready traffic prediction for Vision 2030 smart cities.",
    version     = "4.1.0",
    lifespan    = lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["GET", "POST"],
    allow_headers     = ["*"],
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class PredictRequest(BaseModel):
    city:            str   = Field("Riyadh")
    zone:            str   = Field("Zone_1")
    hour:            int   = Field(..., ge=0, le=23)
    vehicle_count:   float = Field(..., gt=0)
    avg_speed:       float = Field(..., gt=0)
    weather:         str   = Field("clear")
    road_type:       str   = Field("arterial")
    rush_hour:       int   = Field(0, ge=0, le=1)
    is_weekend:      int   = Field(0, ge=0, le=1)
    is_late_night:   int   = Field(0, ge=0, le=1)
    event:           int   = Field(0, ge=0, le=1)
    hour_multiplier: float = Field(1.0, gt=0)


class BatchPredictRequest(BaseModel):
    predictions: list[PredictRequest] = Field(..., max_length=20)


# ---------------------------------------------------------------------------
# Dashboard — no auth required
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, tags=["dashboard"])
def dashboard_root():
    """
    Serve the dashboard at root so the Render URL opens straight to the UI.
    The API key is injected into the HTML at serve time so the dashboard
    can call protected endpoints without exposing the key in the client URL.
    """
    if not DASHBOARD_PATH.exists():
        return HTMLResponse(
            content="<h2>dashboard.html not found — place it next to app.py</h2>",
            status_code=404,
        )

    html = DASHBOARD_PATH.read_text(encoding="utf-8")

    # Inject the API key so the dashboard JS can call /predict etc.
    # The key is embedded in a JS variable scoped to the page — never
    # appears in the URL or network logs as a query parameter.
    injection = f"""
<script>
  // Injected at serve time — not committed to source control
  window.__DASHBOARD_KEY__ = "{API_KEY or ''}";
</script>
"""
    html = html.replace("</head>", injection + "</head>", 1)

    # Replace the placeholder API_KEY reader with the injected value
    html = html.replace(
        "const API_KEY  = document.cookie.replace(/(?:(?:^|.*;\\s*)dk\\s*=\\s*([^;]*).*$)|^.*$/, '$1') || '';",
        "const API_KEY  = window.__DASHBOARD_KEY__ || '';",
    )

    return HTMLResponse(content=html)


@app.get("/dashboard", response_class=HTMLResponse, tags=["dashboard"])
def dashboard_alias():
    """Alias so /dashboard also works alongside the root route."""
    return dashboard_root()


# ---------------------------------------------------------------------------
# Public info endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["info"])
def health():
    """Health check — no authentication required. Used by self-ping."""
    return {"status": "healthy", "version": "4.1.0"}


@app.get("/api/info", tags=["info"])
def api_info():
    """Machine-readable service info — no auth required."""
    return {
        "service"    : "Smart City Traffic Intelligence API",
        "version"    : "4.1.0",
        "status"     : "operational",
        "data_source": app.state.data_source,
        "docs"       : "/docs",
        "dashboard"  : "/",
    }


# ---------------------------------------------------------------------------
# Data source endpoints — authenticated
# ---------------------------------------------------------------------------

@app.get("/data/source", tags=["data"])
def get_data_source(_key: str = Depends(require_api_key)):
    """Return the currently active data source."""
    return {
        "active_source": app.state.data_source,
        "available"    : VALID_SOURCES,
        "description"  : {
            "weather": "Open-Meteo live weather API — no key required",
            "osm"    : "OpenStreetMap Overpass API — road network data",
            "mock"   : "Deterministic IoT sensor simulation — always available",
        }
    }


@app.post("/data/source", tags=["data"])
def set_data_source(
    request: Request,
    source:  str = "mock",
    city:    str = "Riyadh",
    _key:    str = Depends(require_api_key),
):
    """Switch the active data source and fetch a sample from it."""
    if source not in VALID_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source '{source}'. Choose from: {VALID_SOURCES}"
        )
    try:
        adapter        = get_adapter(source)
        sample_df      = adapter.fetch(city)
        app.state.data_source = source
        return {
            "active_source": source,
            "city"         : city,
            "rows_fetched" : len(sample_df),
            "columns"      : list(sample_df.columns),
            "sample"       : sample_df.head(3).to_dict(orient="records"),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Adapter fetch failed: {str(e)}")


# ---------------------------------------------------------------------------
# Pipeline endpoints — authenticated
# ---------------------------------------------------------------------------

@app.get("/pipeline/status", tags=["pipeline"])
def pipeline_status(_key: str = Depends(require_api_key)):
    """Return current drift score and last retrain timestamp."""
    drift_score = compute_drift_score()
    return {
        "drift_score"    : drift_score,
        "drift_threshold": 1.3,
        "needs_retrain"  : drift_score >= 1.3,
        "last_retrain"   : app.state.last_retrain,
        "next_scheduled" : "03:00 daily",
    }


@app.post("/pipeline/trigger", tags=["pipeline"])
def pipeline_trigger(_key: str = Depends(require_api_key)):
    """Manually trigger a pipeline run."""
    print(f"[Pipeline] Manual trigger at {datetime.now()}")
    result = run_pipeline(city="Riyadh")
    if result["retrained"]:
        app.state.last_retrain = result["timestamp"]
    return result


# ---------------------------------------------------------------------------
# Prediction endpoints — authenticated
# ---------------------------------------------------------------------------

@app.post("/predict", tags=["prediction"])
@limiter.limit("60/minute")
def predict(
    request: Request,
    payload: PredictRequest,
    _key:    str = Depends(require_api_key),
):
    """Single zone prediction with SHAP explanation and emissions estimate."""
    p      = payload.model_dump()
    result = predict_single(
        city            = p["city"],
        zone            = p["zone"],
        hour            = p["hour"],
        vehicle_count   = p["vehicle_count"],
        avg_speed       = p["avg_speed"],
        weather         = p["weather"],
        road_type       = p["road_type"],
        rush_hour       = p["rush_hour"],
        is_weekend      = p["is_weekend"],
        is_late_night   = p["is_late_night"],
        event           = p["event"],
        hour_multiplier = p["hour_multiplier"],
    )

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

    X_row       = pd.DataFrame([row])[app.state.feature_cols]
    explanation = explain_prediction(app.state.model, X_row, app.state.feature_cols)

    emissions = compute_emissions(
        congestion_level_str = result["congestion_level"],
        vehicle_count        = p["vehicle_count"],
        duration_hours       = 1.0,
    )
    emissions["green_initiative_flag"] = emissions["co2_kg"] > GREEN_INITIATIVE_CO2_THRESHOLD_KG

    result["explanation"]   = explanation["top_factors"]
    result["plain_english"] = explanation["plain_english"]
    result["emissions"]     = emissions

    log_prediction(result, explanation)
    return result


@app.post("/predict/batch", tags=["prediction"])
@limiter.limit("20/minute")
def predict_batch(
    request: Request,
    payload: BatchPredictRequest,
    _key:    str = Depends(require_api_key),
):
    """Batch prediction for up to 20 zones."""
    results = []
    for item in payload.predictions:
        p = item.model_dump()
        r = predict_single(
            city            = p["city"],
            zone            = p["zone"],
            hour            = p["hour"],
            vehicle_count   = p["vehicle_count"],
            avg_speed       = p["avg_speed"],
            weather         = p["weather"],
            road_type       = p["road_type"],
            rush_hour       = p["rush_hour"],
            is_weekend      = p["is_weekend"],
            is_late_night   = p["is_late_night"],
            event           = p["event"],
            hour_multiplier = p["hour_multiplier"],
        )
        r["emissions"] = compute_emissions(
            congestion_level_str = r["congestion_level"],
            vehicle_count        = p["vehicle_count"],
        )
        results.append(r)
    return {"city": payload.predictions[0].city, "results": results}


# ---------------------------------------------------------------------------
# Monitoring endpoints — authenticated
# ---------------------------------------------------------------------------

@app.get("/anomalies", tags=["monitoring"])
@limiter.limit("20/minute")
def anomalies(
    request: Request,
    city:    str = "Riyadh",
    _key:    str = Depends(require_api_key),
):
    """Current anomalies across all zones."""
    df         = app.state.df[app.state.df["city"] == city]
    anomaly_df = detect_anomalies(df)
    flagged    = anomaly_df[anomaly_df["anomaly_flag"] == 1].copy()

    records = []
    for rec in flagged.to_dict(orient="records"):
        level    = rec.get("congestion_level", "High") if "congestion_level" in rec else "High"
        count    = rec.get("vehicle_count", 100)
        em       = compute_emissions(level, count)
        rec["estimated_co2_kg"]        = em["co2_kg"]
        rec["green_initiative_impact"] = em["co2_kg"] > GREEN_INITIATIVE_CO2_THRESHOLD_KG
        records.append(rec)

    return {
        "city"           : city,
        "total_anomalies": len(records),
        "anomalies"      : records,
    }


@app.get("/forecast", tags=["forecasting"])
@limiter.limit("20/minute")
def forecast(
    request: Request,
    city:    str = "Riyadh",
    zone:    str = "Zone_1",
    _key:    str = Depends(require_api_key),
):
    """1h / 2h / 3h congestion forecast with confidence intervals."""
    df        = app.state.df[
        (app.state.df["city"] == city) & (app.state.df["zone"] == zone)
    ]
    forecasts = forecast_congestion(df, zone=zone, hours_ahead=[1, 2, 3])
    return {"city": city, "zone": zone, "forecasts": forecasts}


# ---------------------------------------------------------------------------
# Emissions endpoints — authenticated
# ---------------------------------------------------------------------------

@app.get("/emissions/summary", tags=["emissions"])
def emissions_summary(
    city: str = "Riyadh",
    _key: str = Depends(require_api_key),
):
    """Aggregate CO2 emissions summary from the predictions audit log."""
    log_path = "predictions_log.csv"

    if not os.path.exists(log_path):
        return {
            "city"                         : city,
            "message"                      : "No predictions logged yet.",
            "total_co2_tonnes"             : 0.0,
            "peak_emission_hour"           : None,
            "peak_emission_zone"           : None,
            "green_initiative_events"      : 0,
            "period_days"                  : 0,
            "green_initiative_threshold_kg": GREEN_INITIATIVE_CO2_THRESHOLD_KG,
        }

    log_df = pd.read_csv(log_path)
    if "city" in log_df.columns:
        log_df = log_df[log_df["city"] == city]

    if log_df.empty:
        return {
            "city"                         : city,
            "message"                      : f"No predictions logged for {city}.",
            "total_co2_tonnes"             : 0.0,
            "peak_emission_hour"           : None,
            "peak_emission_zone"           : None,
            "green_initiative_events"      : 0,
            "period_days"                  : 0,
            "green_initiative_threshold_kg": GREEN_INITIATIVE_CO2_THRESHOLD_KG,
        }

    if "co2_kg" not in log_df.columns or log_df["co2_kg"].isna().all():
        log_df["co2_kg"] = log_df.apply(
            lambda r: compute_emissions(
                str(r.get("congestion_level", "Low")),
                float(r.get("vehicle_count", 100)) if "vehicle_count" in log_df.columns else 100.0,
            )["co2_kg"],
            axis=1,
        )

    log_df["co2_kg"] = pd.to_numeric(log_df["co2_kg"], errors="coerce").fillna(0)

    total_co2_tonnes = round(log_df["co2_kg"].sum() / 1000, 6)
    green_events     = int((log_df["co2_kg"] > GREEN_INITIATIVE_CO2_THRESHOLD_KG).sum())

    peak_hour = None
    if "hour" in log_df.columns:
        peak_hour = int(log_df.groupby("hour")["co2_kg"].mean().idxmax())

    peak_zone = None
    if "zone" in log_df.columns:
        peak_zone = str(log_df.groupby("zone")["co2_kg"].sum().idxmax())

    period_days = 0
    if "timestamp" in log_df.columns:
        try:
            ts = pd.to_datetime(log_df["timestamp"], errors="coerce").dropna()
            if len(ts) > 1:
                period_days = int((ts.max() - ts.min()).days) + 1
        except Exception:
            pass

    return {
        "city"                         : city,
        "total_co2_tonnes"             : total_co2_tonnes,
        "peak_emission_hour"           : peak_hour,
        "peak_emission_zone"           : peak_zone,
        "green_initiative_events"      : green_events,
        "period_days"                  : period_days,
        "green_initiative_threshold_kg": GREEN_INITIATIVE_CO2_THRESHOLD_KG,
    }
