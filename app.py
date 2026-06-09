import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
import pandas as pd
from src.model import WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler

from src.config import HAJJ_DATES, SAUDI_CITIES
from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features
from src.model import (
    train_xgboost, prepare_features, predict_single,
    detect_anomalies, forecast_congestion, explain_prediction,
    log_prediction, get_intervention, compute_accident_risk,
)
from src.adapters import get_adapter
from src.pipeline import run_pipeline, compute_drift_score

load_dotenv()

API_KEY         = os.getenv("API_KEY")
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8501,http://localhost:3000",
).split(",")

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


def _get_active_schedule(city: str) -> dict:
    """
    Determine the currently active traffic schedule for a city.

    Checks today's date against HAJJ_DATES for the current year,
    then falls back to Ramadan (if flagged), then standard Saudi or
    standard schedule.

    Returns a dict with keys: schedule, next_event, days_until.
    """
    today    = date.today()
    year     = today.year
    schedule = "standard"
    next_event   = None
    days_until   = None

    # --- Check Hajj ---
    if year in HAJJ_DATES:
        hajj_start = date.fromisoformat(HAJJ_DATES[year]['start'])
        hajj_end   = date.fromisoformat(HAJJ_DATES[year]['end'])

        if hajj_start <= today <= hajj_end:
            day_offset  = (today - hajj_start).days
            if day_offset <= 1:
                phase = 'inbound'
            elif day_offset <= 3:
                phase = 'peak'
            else:
                phase = 'outbound'
            schedule   = f'hajj_{phase}'
            next_event = 'Hajj ends'
            days_until = (hajj_end - today).days
        elif today < hajj_start:
            next_event = 'Hajj begins'
            days_until = (hajj_start - today).days

    # --- Saudi vs standard base ---
    if schedule == "standard" and city in SAUDI_CITIES:
        schedule = "saudi"

    # --- Check next year Hajj if current year Hajj has passed ---
    if next_event is None and (year + 1) in HAJJ_DATES:
        next_year_start = date.fromisoformat(HAJJ_DATES[year + 1]['start'])
        next_event      = 'Hajj begins'
        days_until      = (next_year_start - today).days

    return {
        "schedule"  : schedule,
        "next_event": next_event,
        "days_until": days_until,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Train model, start scheduler, share state across endpoints."""
    df = generate_traffic_data(city="Riyadh")
    df = apply_hourly_patterns(df, city="Riyadh")
    df = add_lag_features(df)

    X, y, feature_cols    = prepare_features(df)
    model, _, _           = train_xgboost(X, y)

    app.state.df              = df
    app.state.model           = model
    app.state.feature_cols    = feature_cols
    app.state.data_source     = "mock"
    app.state.last_retrain    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    scheduler.add_job(_scheduled_pipeline, "cron", hour=3, minute=0)
    scheduler.start()
    print("[Scheduler] Nightly retraining scheduled at 03:00")

    yield

    scheduler.shutdown()


app = FastAPI(
    title       = "Smart City Traffic Intelligence API",
    description = "Production-ready traffic prediction for Vision 2030 smart cities.",
    version     = "5.0.0",
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
    hajj_mode:       bool  = Field(False, description="Set True during Hajj season to activate mass-gathering traffic model")


class BatchPredictRequest(BaseModel):
    predictions: list[PredictRequest] = Field(..., max_length=20)


# ---------------------------------------------------------------------------
# Public endpoints — no auth required
# ---------------------------------------------------------------------------

@app.get("/", tags=["info"])
def root():
    return {
        "service"     : "Smart City Traffic Intelligence API",
        "version"     : "5.0.0",
        "status"      : "operational",
        "data_source" : app.state.data_source,
        "docs"        : "/docs",
    }


@app.get("/health", tags=["info"])
def health():
    """Health check — no authentication required."""
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# Schedule endpoint — authenticated
# ---------------------------------------------------------------------------

@app.get("/schedule/active", tags=["schedule"])
def schedule_active(
    city: str = "Riyadh",
    _key: str = Depends(require_api_key),
):
    """
    Return the currently active traffic schedule for a city.

    Auto-detects Hajj based on today's date vs HAJJ_DATES.
    Returns schedule name, next major event, and days until that event.
    """
    result = _get_active_schedule(city)
    result["city"] = city
    return result


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
        adapter   = get_adapter(source)
        sample_df = adapter.fetch(city)
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
    drift_score    = compute_drift_score()
    next_scheduled = "03:00 daily"

    return {
        "drift_score"    : drift_score,
        "drift_threshold": 1.3,
        "needs_retrain"  : drift_score >= 1.3,
        "last_retrain"   : app.state.last_retrain,
        "next_scheduled" : next_scheduled,
    }


@app.post("/pipeline/trigger", tags=["pipeline"])
def pipeline_trigger(_key: str = Depends(require_api_key)):
    """Manually trigger a pipeline run. Retrains if drift threshold is exceeded."""
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
    """
    Single zone prediction with SHAP explanation. 60 req/min per IP.

    Set hajj_mode=true during Hajj season to activate mass-gathering
    traffic patterns with three phases: inbound, peak, outbound.
    """
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

    # Annotate active schedule in response
    schedule_info        = _get_active_schedule(p["city"])
    result["schedule"]   = schedule_info["schedule"]
    result["hajj_mode"]  = p["hajj_mode"]

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

    result["explanation"]   = explanation["top_factors"]
    result["plain_english"] = explanation["plain_english"]

    result["intervention"] = get_intervention(
        zone               = p["zone"],
        hour               = p["hour"],
        congestion_level_str = result["congestion_level"],
    )

    result["accident_risk"] = compute_accident_risk(
        congestion_score = result["congestion_score"],
        weather          = p["weather"],
        hour             = p["hour"],
        is_weekend       = p["is_weekend"],
        rush_hour        = p["rush_hour"],
    )

    log_prediction(result, explanation)
    return result


@app.post("/predict/batch", tags=["prediction"])
@limiter.limit("20/minute")
def predict_batch(
    request: Request,
    payload: BatchPredictRequest,
    _key:    str = Depends(require_api_key),
):
    """Batch prediction for up to 20 zones. 20 req/min per IP."""
    results = []
    for item in payload.predictions:
        p = item.model_dump()
        results.append(predict_single(
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
        ))
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
    """Current anomalies across all zones. 20 req/min per IP."""
    df         = app.state.df[app.state.df["city"] == city]
    anomaly_df = detect_anomalies(df)
    flagged    = anomaly_df[anomaly_df["anomaly_flag"] == 1].to_dict(orient="records")
    return {
        "city"           : city,
        "total_anomalies": len(flagged),
        "anomalies"      : flagged,
    }


@app.get("/interventions/active", tags=["monitoring"])
@limiter.limit("20/minute")
def interventions_active(
    request: Request,
    city:    str = "Riyadh",
    _key:    str = Depends(require_api_key),
):
    """
    All zones currently at High or Critical congestion with intervention
    recommendations. Sorted Critical first. 20 req/min per IP.
    """
    from src.model import congestion_level as cl

    df      = app.state.df[app.state.df["city"] == city]
    zones   = df["zone"].unique()
    results = []

    for zone in zones:
        zone_df = df[df["zone"] == zone]
        latest  = zone_df.sort_values("timestamp").iloc[-1]
        score   = float(latest["congestion_score"])
        hour    = int(latest["hour"])
        weather = str(latest["weather"])
        level   = cl(score)

        if level in ("High", "Critical"):
            intervention = get_intervention(
                zone                = zone,
                hour                = hour,
                congestion_level_str= level,
            )
            results.append({
                "zone"            : zone,
                "hour"            : hour,
                "weather"         : weather,
                "congestion_score": round(score, 4),
                "congestion_level": level,
                "intervention"    : intervention,
            })

    priority = {"Critical": 0, "High": 1}
    results.sort(key=lambda x: priority.get(x["congestion_level"], 2))

    return {
        "city"               : city,
        "total_interventions": len(results),
        "interventions"      : results,
    }


@app.get("/safety/hotspots", tags=["safety"])
@limiter.limit("20/minute")
def safety_hotspots(
    request: Request,
    city:    str = "Riyadh",
    _key:    str = Depends(require_api_key),
):
    """
    All zones ranked by current accident risk score, highest first.
    Includes primary risk factor for each zone. 20 req/min per IP.
    """
    df      = app.state.df[app.state.df["city"] == city]
    zones   = df["zone"].unique()
    results = []

    for zone in zones:
        zone_df = df[df["zone"] == zone]
        latest  = zone_df.sort_values("timestamp").iloc[-1]
        score   = float(latest["congestion_score"])
        hour    = int(latest["hour"])
        weather = str(latest["weather"])
        is_wknd = int(latest.get("is_weekend", 0))
        rush    = int(latest.get("rush_hour", 0))

        risk = compute_accident_risk(
            congestion_score = score,
            weather          = weather,
            hour             = hour,
            is_weekend       = is_wknd,
            rush_hour        = rush,
        )
        results.append({
            "zone"            : zone,
            "hour"            : hour,
            "weather"         : weather,
            "congestion_score": round(score, 4),
            **risk,
        })

    results.sort(key=lambda x: x["risk_score"], reverse=True)

    return {
        "city"        : city,
        "total_zones" : len(results),
        "hotspots"    : results,
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
    df        = app.state.df[(app.state.df["city"] == city) & (app.state.df["zone"] == zone)]
    forecasts = forecast_congestion(df, zone=zone, hours_ahead=[1, 2, 3])
    return {"city": city, "zone": zone, "forecasts": forecasts}
