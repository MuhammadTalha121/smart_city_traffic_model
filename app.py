import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Dict
import pandas as pd
from src.model import WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING
from src.reporter import generate_weekly_report
from fastapi.responses import FileResponse
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

from fastapi import WebSocket, WebSocketDisconnect
import asyncio

from src.config import HAJJ_DATES, SAUDI_CITIES
from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features
from src.model import (
    train_xgboost, prepare_features, predict_single,
    detect_anomalies, forecast_congestion, explain_prediction,
    log_prediction, get_intervention, compute_accident_risk,
    compute_signal_timing, compute_emissions, estimate_response_time,
    get_delivery_windows, compute_prediction_interval,
    compute_speed_degradation_index, compute_pedestrian_risk,
)
from src.adapters import get_adapter
from src.pipeline import run_pipeline, compute_drift_score, check_thresholds, deliver_webhook_alert, log_alert
from src.pipeline import run_pipeline, compute_drift_score, log_api_usage, build_key_registry, validate_prediction_input, compute_sla_metrics


load_dotenv()

DAILY_QUOTA_LIMIT = int(os.getenv("DAILY_QUOTA_LIMIT", "10000"))

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

API_KEY         = os.getenv("API_KEY")
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8501,http://localhost:3000",
).split(",")

limiter        = Limiter(key_func=get_remote_address)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
scheduler      = BackgroundScheduler()

VALID_SOURCES = ["weather", "osm", "mock"]


def _get_registry() -> Dict[str, Dict]:
    try:
        return app.state.key_registry
    except AttributeError:
        return {}

def require_api_key(key: str = Depends(api_key_header)) -> Dict:
    """Validate X-API-Key. Returns {key, city, role}."""
    registry = _get_registry()
    if not registry:
        raise HTTPException(status_code=500, detail='Server has no API keys configured.')
    if not key or key not in registry:
        raise HTTPException(status_code=401, detail='Invalid or missing API key.')
    entry = registry[key]
    return {'key': key, 'city': entry['city'], 'role': entry['role']}

def require_admin(auth: Dict = Depends(require_api_key)) -> Dict:
    """Extend require_api_key with admin role enforcement."""
    if auth['role'] != 'admin':
        raise HTTPException(status_code=403, detail='This endpoint requires admin role.')
    return auth

def _assert_city_permitted(auth: Dict, requested_city: str) -> None:
    """Raise 403 if key city scope does not cover requested_city."""
    if auth['city'] == '*':
        return
    if auth['city'].lower() != requested_city.lower():
        raise HTTPException(
            status_code=403,
            detail=f"API key is scoped to '{auth['city']}' — cannot access '{requested_city}'.",
        )


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
    """Train model on Riyadh, generate data for all cities, start scheduler."""
    app.state.key_registry = build_key_registry()
    city_dfs = {}
    for city in ["Riyadh", "NEOM", "Dubai", "Karachi"]:
        df = generate_traffic_data(city=city)
        df = apply_hourly_patterns(df, city=city)
        df = add_lag_features(df)
        city_dfs[city] = df

    # Train on Riyadh as primary model
    X, y, feature_cols = prepare_features(city_dfs["Riyadh"])
    model, _, _        = train_xgboost(X, y)

    app.state.df           = city_dfs["Riyadh"]   # default city for existing endpoints
    app.state.city_dfs     = city_dfs
    app.state.model        = model
    app.state.feature_cols = feature_cols
    app.state.data_source  = "mock"
    app.state.last_retrain = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    scheduler.add_job(_scheduled_pipeline, "cron", hour=3, minute=0)

    def _scheduled_alerts():
        for city, city_df in app.state.city_dfs.items():
            alerts = check_thresholds(city_df, city=city)
            if alerts:
                log_alert(alerts)
                deliver_webhook_alert(alerts, WEBHOOK_URL)
                print(f"[Alert] {len(alerts)} alert(s) fired for {city}")

    scheduler.add_job(_scheduled_alerts, "interval", minutes=15)
    print("[Scheduler] Alert threshold monitoring scheduled every 15 minutes")
    scheduler.add_job(
    lambda: generate_weekly_report(city='Riyadh'),
    'cron', day_of_week='mon', hour=6, minute=0
)

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


@app.middleware("http")
async def usage_logging_middleware(request: Request, call_next):
    """
    Log every request to usage_log.csv after processing.

    Captures endpoint, method, hashed API key (first 8 chars),
    HTTP status code, and response time in milliseconds.
    Never logs request body or full API key.
    """
    import time

    start    = time.monotonic()
    response = await call_next(request)
    duration = round((time.monotonic() - start) * 1000, 1)

    raw_key    = request.headers.get("X-API-Key", "anonymous")
    key_hash   = raw_key[:8] if raw_key != "anonymous" else "anonymous"
    endpoint   = request.url.path
    method     = request.method
    status     = response.status_code
    timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_path = "usage_log.csv"
    row = pd.DataFrame([{
        "timestamp"      : timestamp,
        "endpoint"       : endpoint,
        "method"         : method,
        "api_key_hash"   : key_hash,
        "response_code"  : status,
        "response_time_ms": duration,
    }])
    write_header = not os.path.exists(log_path)
    row.to_csv(log_path, mode="a", header=write_header, index=False)

    return response


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


@app.get("/dashboard", response_class=HTMLResponse, tags=["info"])
def dashboard():
    """Serve the operations dashboard. No authentication required."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if not os.path.exists(dashboard_path):
        raise HTTPException(status_code=404, detail="dashboard.html not found at repo root.")
    with open(dashboard_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ---------------------------------------------------------------------------
# Schedule endpoint — authenticated
# ---------------------------------------------------------------------------

@app.get("/schedule/active", tags=["schedule"])
def schedule_active(
    city: str = "Riyadh",
    auth: Dict = Depends(require_api_key),
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
def get_data_source(auth: Dict = Depends(require_api_key)):
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
    auth: Dict = Depends(require_admin),
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
def pipeline_status(auth: Dict = Depends(require_admin)):
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
def pipeline_trigger(auth: Dict = Depends(require_admin)):
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
    auth: Dict = Depends(require_api_key),
):
    """
    Single zone prediction with SHAP explanation. 60 req/min per IP.

    Set hajj_mode=true during Hajj season to activate mass-gathering
    traffic patterns with three phases: inbound, peak, outbound.
    """
    _assert_city_permitted(auth, payload.city)

    p          = payload.model_dump()
    validation = validate_prediction_input(p)
    if not validation["valid"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "Input validation failed.", "errors": validation["errors"]},
        )

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

    prediction_interval = compute_prediction_interval(
        model        = app.state.model,
        X_row        = X_row,
        feature_cols = app.state.feature_cols,
        df           = app.state.city_dfs.get(p["city"], app.state.df),
        zone         = p["zone"],
        n_bootstrap  = 50,
    )


    result["prediction_interval"] = prediction_interval
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

    result["signal_timing"] = compute_signal_timing(
        congestion_score = result["congestion_score"],
        vehicle_count    = p["vehicle_count"],
        hour             = p["hour"],
        is_weekend       = p["is_weekend"],
    )

    result["emissions"] = compute_emissions(
        congestion_level_str = result["congestion_level"],
        vehicle_count        = p["vehicle_count"],
    )

    sdi = compute_speed_degradation_index(
        avg_speed = p["avg_speed"],
        road_type = p["road_type"],
        weather   = p["weather"],
    )
    result["sdi"] = sdi

    pedestrian_risk        = compute_pedestrian_risk(
        vehicle_count = p["vehicle_count"],
        avg_speed     = p["avg_speed"],
        hour          = p["hour"],
        weather       = p["weather"],
        road_type     = p["road_type"],
    )
    result["pedestrian_risk"] = pedestrian_risk
    result["input_warnings"] = validation["warnings"]

    log_prediction(result, explanation, interval_width=prediction_interval["confidence_width"])

    return result


@app.post("/predict/batch", tags=["prediction"])
@limiter.limit("20/minute")
def predict_batch(
    request: Request,
    payload: BatchPredictRequest,
    auth: Dict = Depends(require_api_key),
):
    """Batch prediction for up to 20 zones. 20 req/min per IP."""
    _assert_city_permitted(auth, payload.city)

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
    auth: Dict = Depends(require_api_key),
):
    """Current anomalies across all zones. 20 req/min per IP."""
    _assert_city_permitted(auth, city)
    df         = app.state.city_dfs.get(city, app.state.df)
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
    auth: Dict = Depends(require_api_key),
):
    """
    All zones currently at High or Critical congestion with intervention
    recommendations. Sorted Critical first. 20 req/min per IP.
    """
    from src.model import congestion_level as cl

    df      = app.state.city_dfs.get(city, app.state.df)
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
    auth: Dict = Depends(require_api_key),
):
    """
    All zones ranked by current accident risk score, highest first.
    Includes primary risk factor for each zone. 20 req/min per IP.
    """
    df      = app.state.city_dfs.get(city, app.state.df)
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


@app.get("/signals/recommended", tags=["signals"])
@limiter.limit("20/minute")
def signals_recommended(
    request: Request,
    city:    str = "Riyadh",
    auth: Dict = Depends(require_api_key),
):
    """
    Recommended adaptive signal timing for all zones right now,
    sorted by congestion_score descending. 20 req/min per IP.
    """
    df      = app.state.city_dfs.get(city, app.state.df)
    zones   = df["zone"].unique()
    results = []

    for zone in zones:
        zone_df = df[df["zone"] == zone]
        latest  = zone_df.sort_values("timestamp").iloc[-1]
        score   = float(latest["congestion_score"])
        hour    = int(latest["hour"])
        is_wknd = int(latest.get("is_weekend", 0))
        vehicles = float(latest.get("vehicle_count", 0))

        timing = compute_signal_timing(
            congestion_score = score,
            vehicle_count    = vehicles,
            hour             = hour,
            is_weekend       = is_wknd,
        )
        results.append({
            "zone"            : zone,
            "hour"            : hour,
            "congestion_score": round(score, 4),
            "signal_timing"   : timing,
        })

    results.sort(key=lambda x: x["congestion_score"], reverse=True)

    return {
        "city"       : city,
        "total_zones": len(results),
        "signals"    : results,
    }


@app.get("/emissions/summary", tags=["emissions"])
@limiter.limit("20/minute")
def emissions_summary(
    request: Request,
    city:    str = "Riyadh",
    auth: Dict = Depends(require_api_key),
):
    """
    Aggregated CO2 and fuel summary from the predictions log.
    Reads predictions_log.csv and returns totals, peak hour, peak zone.
    """
    import os

    log_path = "predictions_log.csv"
    if not os.path.exists(log_path):
        return {
            "city"                  : city,
            "total_co2_tonnes"      : 0.0,
            "peak_emission_hour"    : None,
            "peak_emission_zone"    : None,
            "period_days"           : 0,
            "note"                  : "No predictions logged yet.",
        }

    log_df = pd.read_csv(log_path)
    if log_df.empty or "congestion_score" not in log_df.columns:
        return {
            "city"              : city,
            "total_co2_tonnes"  : 0.0,
            "peak_emission_hour": None,
            "peak_emission_zone": None,
            "period_days"       : 0,
        }

    if "city" in log_df.columns:
        log_df = log_df[log_df["city"] == city]

    if log_df.empty:
        return {"city": city, "total_co2_tonnes": 0.0, "peak_emission_hour": None,
                "peak_emission_zone": None, "period_days": 0}

    # Compute co2_kg per logged row using stored level and a default vehicle count
    from src.config import FUEL_CONSUMPTION_LPH, CO2_KG_PER_LITRE

    def _row_co2(row):
        level = row.get("congestion_level", "Low")
        rate  = FUEL_CONSUMPTION_LPH.get(level, FUEL_CONSUMPTION_LPH["Low"])
        return rate * (150 / 100) * CO2_KG_PER_LITRE  # use avg 150 vehicles as default

    log_df["_co2_kg"] = log_df.apply(_row_co2, axis=1)

    total_co2_kg     = log_df["_co2_kg"].sum()
    total_co2_tonnes = round(total_co2_kg / 1000, 6)

    peak_hour = None
    peak_zone = None
    if "hour" in log_df.columns:
        peak_hour = int(log_df.groupby("hour")["_co2_kg"].sum().idxmax())
    if "zone" in log_df.columns:
        peak_zone = str(log_df.groupby("zone")["_co2_kg"].sum().idxmax())

    period_days = 0
    if "timestamp" in log_df.columns:
        try:
            timestamps  = pd.to_datetime(log_df["timestamp"])
            period_days = max(1, (timestamps.max() - timestamps.min()).days)
        except Exception:
            period_days = 1

    return {
        "city"              : city,
        "total_co2_tonnes"  : total_co2_tonnes,
        "peak_emission_hour": peak_hour,
        "peak_emission_zone": peak_zone,
        "period_days"       : period_days,
    }


@app.get("/cities/compare", tags=["multi-city"])
@limiter.limit("20/minute")
def cities_compare(
    request: Request,
    auth: Dict = Depends(require_api_key),
):
    """
    Current traffic snapshot for all configured cities.

    Returns avg_congestion_score, most congested zone, peak hour,
    total anomalies, and avg_risk_score per city.
    Sorted by avg_congestion_score descending.
    """
    from src.model import congestion_level as cl, compute_accident_risk

    results = []

    for city, df in app.state.city_dfs.items():
        avg_congestion = round(float(df["congestion_score"].mean()), 4)

        zone_means  = df.groupby("zone")["congestion_score"].mean()
        max_zone    = str(zone_means.idxmax())

        hour_means  = df.groupby("hour")["congestion_score"].mean()
        peak_hour   = int(hour_means.idxmax())

        anomaly_df      = detect_anomalies(df)
        total_anomalies = int((anomaly_df["anomaly_flag"] == 1).sum())

        # Sample risk score from the latest row of the worst zone
        worst_df  = df[df["zone"] == max_zone].sort_values("timestamp")
        latest    = worst_df.iloc[-1]
        risk      = compute_accident_risk(
            congestion_score = float(latest["congestion_score"]),
            weather          = str(latest["weather"]),
            hour             = int(latest["hour"]),
            is_weekend       = int(latest.get("is_weekend", 0)),
            rush_hour        = int(latest.get("rush_hour", 0)),
        )

        results.append({
            "city"               : city,
            "avg_congestion_score": avg_congestion,
            "max_zone"           : max_zone,
            "peak_hour"          : peak_hour,
            "total_anomalies"    : total_anomalies,
            "avg_risk_score"     : risk["risk_score"],
        })

    results.sort(key=lambda x: x["avg_congestion_score"], reverse=True)

    return {
        "cities"      : results,
        "total_cities": len(results),
    }


@app.get("/forecast", tags=["forecasting"])
@limiter.limit("20/minute")
def forecast(
    request: Request,
    city:    str = "Riyadh",
    zone:    str = "Zone_1",
    auth: Dict = Depends(require_api_key),
):
    """1h / 2h / 3h congestion forecast with confidence intervals."""
    _assert_city_permitted(auth, city)
    city_df   = app.state.city_dfs.get(city, app.state.df)
    df        = city_df[city_df["zone"] == zone]
    forecasts = forecast_congestion(df, zone=zone, hours_ahead=[1, 2, 3])
    return {"city": city, "zone": zone, "forecasts": forecasts}


@app.get("/emergency/response-time", tags=["safety"])
@limiter.limit("20/minute")
def emergency_response_time(
    request: Request,
    city:        str = "Riyadh",
    target_zone: str = "Zone_1",
    auth:        Dict = Depends(require_api_key),
):
    """
    Estimate emergency vehicle response time from all stations to a target zone.

    Uses current congestion level for that zone to compute effective speed,
    calculates travel time from each configured station.
    Flags responses exceeding the WHO 8-minute threshold. 20 req/min per IP.
    """
    from src.config import EMERGENCY_STATIONS

    df      = app.state.city_dfs.get(city, app.state.df)
    zone_df = df[df["zone"] == target_zone]

    if zone_df.empty:
        current_level = "Low"
    else:
        from src.model import congestion_level as cl
        latest_score  = float(zone_df["congestion_score"].iloc[-1])
        current_level = cl(latest_score)

    stations  = EMERGENCY_STATIONS.get(city, EMERGENCY_STATIONS.get("Riyadh", {}))
    estimates = []

    for station_name, station_info in stations.items():
        result                 = estimate_response_time(
            origin_zone      = station_info["zone"],
            target_zone      = target_zone,
            congestion_level = current_level,
            city             = city,
        )
        result["station_name"] = station_name
        estimates.append(result)

    estimates.sort(key=lambda x: x["estimated_minutes"])

    return {
        "city"                      : city,
        "target_zone"               : target_zone,
        "current_congestion_level"  : current_level,
        "fastest_estimated_minutes" : estimates[0]["estimated_minutes"] if estimates else None,
        "who_threshold_mins"        : 8,
        "estimates"                 : estimates,
    }



@app.get("/freight/windows", tags=["freight"])
@limiter.limit("20/minute")
def freight_windows(
    request: Request,
    city:    str = "Riyadh",
    zone:    str = "Zone_1",
    auth: Dict = Depends(require_api_key),
):
    """
    Recommend optimal delivery windows for freight vehicles in a zone.

    Returns hours with low congestion outside restricted and prayer windows.
    Logistics companies use this to schedule deliveries without adding to
    peak congestion. 20 req/min per IP.
    """
    df     = app.state.city_dfs.get(city, app.state.df)
    result = get_delivery_windows(city=city, zone=zone, df=df)

    return {
        "city"                : city,
        "zone"                : zone,
        "recommended_windows" : result["recommended_windows"],
        "avoid_hours"         : result["avoid_hours"],
        "best_hour"           : result["best_hour"],
        "rationale"           : result["rationale"],
    }




@app.get("/history/patterns", tags=["history"])
@limiter.limit("20/minute")
def history_patterns(
    request: Request,
    city:    str = "Riyadh",
    zone:    str = None,
    weather: str = None,
    days:    int = 30,
    auth: Dict = Depends(require_api_key),
):
    """
    Query historical congestion patterns from the predictions audit log.

    Filters by city, zone (optional), weather condition (optional),
    and number of days back. Returns avg congestion, peak hour,
    weather breakdown, and hourly averages. 20 req/min per IP.
    """
    log_path = "predictions_log.csv"

    if not os.path.exists(log_path):
        return {
            "city"               : city,
            "period_days"        : days,
            "total_records"      : 0,
            "avg_congestion_score": None,
            "peak_hour"          : None,
            "peak_congestion"    : None,
            "weather_breakdown"  : {},
            "hourly_averages"    : {},
            "note"               : "No predictions logged yet.",
        }

    log_df = pd.read_csv(log_path)

    if "timestamp" in log_df.columns:
        log_df["timestamp"] = pd.to_datetime(log_df["timestamp"], errors="coerce")
        cutoff  = pd.Timestamp.now() - pd.Timedelta(days=days)
        log_df  = log_df[log_df["timestamp"] >= cutoff]

    if "city" in log_df.columns:
        log_df = log_df[log_df["city"] == city]
    if zone and "zone" in log_df.columns:
        log_df = log_df[log_df["zone"] == zone]
    if weather and "weather" in log_df.columns:
        log_df = log_df[log_df["weather"] == weather]

    if log_df.empty:
        return {
            "city"               : city,
            "period_days"        : days,
            "total_records"      : 0,
            "avg_congestion_score": None,
            "peak_hour"          : None,
            "peak_congestion"    : None,
            "weather_breakdown"  : {},
            "hourly_averages"    : {},
        }

    avg_score = round(float(log_df["congestion_score"].mean()), 4)

    hourly_avg   = {}
    peak_hour    = None
    peak_cong    = None
    if "hour" in log_df.columns:
        ha        = log_df.groupby("hour")["congestion_score"].mean()
        hourly_avg = {int(h): round(float(v), 4) for h, v in ha.items()}
        peak_hour  = int(ha.idxmax())
        peak_cong  = round(float(ha.max()), 4)

    weather_breakdown = {}
    if "weather" in log_df.columns:
        wb = log_df.groupby("weather")["congestion_score"].mean()
        weather_breakdown = {w: round(float(v), 4) for w, v in wb.items()}

    return {
        "city"               : city,
        "zone"               : zone,
        "weather_filter"     : weather,
        "period_days"        : days,
        "total_records"      : len(log_df),
        "avg_congestion_score": avg_score,
        "peak_hour"          : peak_hour,
        "peak_congestion"    : peak_cong,
        "weather_breakdown"  : weather_breakdown,
        "hourly_averages"    : hourly_avg,
    }


@app.get("/history/trend", tags=["history"])
@limiter.limit("20/minute")
def history_trend(
    request: Request,
    city:    str = "Riyadh",
    zone:    str = "Zone_1",
    days:    int = 7,
    auth:    Dict = Depends(require_api_key),
):
    """
    Daily average congestion trend for the past N days.

    Returns dates, daily averages, and trend direction
    (improving / worsening / stable). 20 req/min per IP.
    """
    log_path = "predictions_log.csv"

    if not os.path.exists(log_path):
        return {
            "city"       : city,
            "zone"       : zone,
            "period_days": days,
            "dates"      : [],
            "avg_scores" : [],
            "trend"      : "stable",
            "note"       : "No predictions logged yet.",
        }

    log_df = pd.read_csv(log_path)

    if "timestamp" in log_df.columns:
        log_df["timestamp"] = pd.to_datetime(log_df["timestamp"], errors="coerce")
        cutoff  = pd.Timestamp.now() - pd.Timedelta(days=days)
        log_df  = log_df[log_df["timestamp"] >= cutoff]

    if "city" in log_df.columns:
        log_df = log_df[log_df["city"] == city]
    if "zone" in log_df.columns:
        log_df = log_df[log_df["zone"] == zone]

    if log_df.empty or "timestamp" not in log_df.columns:
        return {
            "city"       : city,
            "zone"       : zone,
            "period_days": days,
            "dates"      : [],
            "avg_scores" : [],
            "trend"      : "stable",
        }

    log_df["date"] = log_df["timestamp"].dt.date
    daily          = log_df.groupby("date")["congestion_score"].mean().sort_index()

    dates      = [str(d) for d in daily.index]
    avg_scores = [round(float(v), 4) for v in daily.values]

    trend = "stable"
    if len(avg_scores) >= 3:
        first_half  = sum(avg_scores[:len(avg_scores)//2]) / max(len(avg_scores)//2, 1)
        second_half = sum(avg_scores[len(avg_scores)//2:]) / max(len(avg_scores) - len(avg_scores)//2, 1)
        delta       = second_half - first_half
        if delta > 0.02:
            trend = "worsening"
        elif delta < -0.02:
            trend = "improving"

    return {
        "city"       : city,
        "zone"       : zone,
        "period_days": days,
        "dates"      : dates,
        "avg_scores" : avg_scores,
        "trend"      : trend,
    }


@app.get("/alerts/history", tags=["monitoring"])
@limiter.limit("20/minute")
def alerts_history(
    request: Request,
    city:    str = "Riyadh",
    hours:   int = 24,
    auth: Dict = Depends(require_api_key),
):
    """
    Return all alerts triggered in the past N hours from the alerts log.

    Reads alerts_log.csv, filters by city and time window.
    Returns total count and full alert list sorted newest first.
    20 req/min per IP.
    """
    log_path = "alerts_log.csv"

    if not os.path.exists(log_path):
        return {
            "city"        : city,
            "hours"       : hours,
            "total_alerts": 0,
            "alerts"      : [],
            "note"        : "No alerts logged yet.",
        }

    log_df = pd.read_csv(log_path)

    if "timestamp" in log_df.columns:
        log_df["timestamp"] = pd.to_datetime(log_df["timestamp"], errors="coerce")
        cutoff = pd.Timestamp.now() - pd.Timedelta(hours=hours)
        log_df = log_df[log_df["timestamp"] >= cutoff]

    if "city" in log_df.columns:
        log_df = log_df[log_df["city"] == city]

    log_df = log_df.sort_values("timestamp", ascending=False)

    return {
        "city"        : city,
        "hours"       : hours,
        "total_alerts": len(log_df),
        "alerts"      : log_df.to_dict(orient="records"),
    }



@app.get("/roads/service-level", tags=["roads"])
@limiter.limit("20/minute")
def roads_service_level(
    request: Request,
    city:    str = "Riyadh",
    auth:    Dict = Depends(require_api_key),
):
    """
    Return HCM Level of Service (A–F) and SDI for all zones.

    Uses the latest avg_speed and road_type per zone from the city DataFrame.
    Sorted by SDI descending (worst service level first).
    20 req/min per IP.
    """
    df      = app.state.city_dfs.get(city, app.state.df)
    results = []

    for zone in df['zone'].unique():
        zone_df = df[df['zone'] == zone]
        if zone_df.empty:
            continue
        latest    = zone_df.iloc[-1]
        avg_speed = float(latest.get('avg_speed', 65))
        road_type = str(latest.get('road_type', 'arterial'))
        weather   = str(latest.get('weather', 'clear'))

        sdi_result = compute_speed_degradation_index(avg_speed, road_type, weather)
        results.append({
            'zone'             : zone,
            'road_type'        : road_type,
            'weather'          : weather,
            **sdi_result,
        })

    results.sort(key=lambda x: x['sdi'], reverse=True)

    return {
        'city'   : city,
        'zones'  : results,
    }



@app.get("/safety/pedestrian", tags=["safety"])
@limiter.limit("20/minute")
def safety_pedestrian(
    request: Request,
    city:    str = "Riyadh",
    auth:    Dict = Depends(require_api_key),
):
    """
    Return all zones ranked by pedestrian risk score, worst first.

    Zones where pedestrian_risk_score > 0.60 are flagged as requiring
    intervention. Uses latest observation per zone. 20 req/min per IP.
    """
    df      = app.state.city_dfs.get(city, app.state.df)
    results = []

    for zone in df['zone'].unique():
        zone_df = df[df['zone'] == zone]
        if zone_df.empty:
            continue

        latest = zone_df.iloc[-1]

        risk = compute_pedestrian_risk(
            vehicle_count = float(latest.get('vehicle_count', 100)),
            avg_speed     = float(latest.get('avg_speed', 65)),
            hour          = int(latest.get('hour', 12)),
            weather       = str(latest.get('weather', 'clear')),
            road_type     = str(latest.get('road_type', 'arterial')),
        )

        results.append({
            'zone'                  : zone,
            'pedestrian_risk_score' : risk['pedestrian_risk_score'],
            'risk_category'         : risk['risk_category'],
            'primary_hazard'        : risk['primary_hazard'],
            'intervention_required' : risk['pedestrian_risk_score'] > 0.60,
        })

    results.sort(key=lambda x: x['pedestrian_risk_score'], reverse=True)

    return {
        'city'   : city,
        'zones'  : results,
    }



@app.get("/analytics/usage", tags=["analytics"])
@limiter.limit("20/minute")
def analytics_usage(
    request: Request,
    days:    int = 30,
    auth:    Dict = Depends(require_admin),
):
    """
    API usage summary for the past N days from usage_log.csv.

    Returns total calls, calls by endpoint, calls by day,
    average response time, and top endpoint. 20 req/min per IP.
    """
    log_path = "usage_log.csv"

    if not os.path.exists(log_path):
        return {
            "period_days"       : days,
            "total_calls"       : 0,
            "calls_by_endpoint" : {},
            "calls_by_day"      : {},
            "avg_response_time_ms": None,
            "top_endpoint"      : None,
        }

    log_df = pd.read_csv(log_path)

    if "timestamp" in log_df.columns:
        log_df["timestamp"] = pd.to_datetime(log_df["timestamp"], errors="coerce")
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        log_df = log_df[log_df["timestamp"] >= cutoff]

    if log_df.empty:
        return {
            "period_days"         : days,
            "total_calls"         : 0,
            "calls_by_endpoint"   : {},
            "calls_by_day"        : {},
            "avg_response_time_ms": None,
            "top_endpoint"        : None,
        }

    calls_by_endpoint = log_df["endpoint"].value_counts().to_dict()
    top_endpoint      = max(calls_by_endpoint, key=calls_by_endpoint.get)

    calls_by_day = {}
    if "timestamp" in log_df.columns:
        log_df["date"] = log_df["timestamp"].dt.date
        calls_by_day   = {str(k): int(v) for k, v in log_df.groupby("date").size().items()}

    avg_rt = None
    if "response_time_ms" in log_df.columns:
        avg_rt = round(float(log_df["response_time_ms"].mean()), 1)

    return {
        "period_days"         : days,
        "total_calls"         : len(log_df),
        "calls_by_endpoint"   : {k: int(v) for k, v in calls_by_endpoint.items()},
        "calls_by_day"        : calls_by_day,
        "avg_response_time_ms": avg_rt,
        "top_endpoint"        : top_endpoint,
    }


@app.get("/analytics/quota", tags=["analytics"])
@limiter.limit("20/minute")
def analytics_quota(
    request: Request,
    auth: Dict = Depends(require_admin),
):
    """
    Today's API call count versus the daily quota limit.

    Warns when usage exceeds 80% of quota. 20 req/min per IP.
    """
    log_path = "usage_log.csv"
    today    = datetime.now().date()

    calls_today = 0
    if os.path.exists(log_path):
        log_df = pd.read_csv(log_path)
        if "timestamp" in log_df.columns:
            log_df["timestamp"] = pd.to_datetime(log_df["timestamp"], errors="coerce")
            calls_today = int((log_df["timestamp"].dt.date == today).sum())

    pct_used = round((calls_today / DAILY_QUOTA_LIMIT) * 100, 1)

    return {
        "date"             : str(today),
        "calls_today"      : calls_today,
        "daily_limit"      : DAILY_QUOTA_LIMIT,
        "pct_used"         : pct_used,
        "quota_warning"    : pct_used >= 80.0,
        "quota_exceeded"   : calls_today >= DAILY_QUOTA_LIMIT,
    }


@app.get("/sla/report", tags=["sla"])
def sla_report(
    days: int  = 30,
    auth: Dict = Depends(require_admin),
):
    """
    Full SLA compliance report for the past N days. Admin only.

    Targets: uptime >= 99%, avg response < 500ms, p95 < 1000ms.
    """
    return compute_sla_metrics(days=days)


@app.get("/sla/current", tags=["sla"])
def sla_current():
    """
    Last 24-hour SLA metrics. Public — no authentication required.

    Used for public status page.
    """
    return compute_sla_metrics(days=1)



@app.get("/data/quality", tags=["monitoring"])
def data_quality(
    city:  str = "Riyadh",
    hours: int = 24,
    auth:  Dict = Depends(require_api_key),
):
    """Summarise input quality flags from the predictions audit log."""
    _assert_city_permitted(auth, city)

    log_path = "predictions_log.csv"

    if not os.path.exists(log_path):
        return {
            "city": city, "hours": hours,
            "total_predictions": 0, "flagged_predictions": 0,
            "flag_rate_pct": 0.0, "common_warnings": [],
            "message": "No predictions logged yet.",
        }

    log_df = pd.read_csv(log_path)
    if "city" in log_df.columns:
        log_df = log_df[log_df["city"] == city]

    if "timestamp" in log_df.columns:
        log_df["timestamp"] = pd.to_datetime(log_df["timestamp"], errors="coerce")
        cutoff = pd.Timestamp.now() - pd.Timedelta(hours=hours)
        log_df = log_df[log_df["timestamp"] >= cutoff]

    total = len(log_df)
    if total == 0:
        return {
            "city": city, "hours": hours,
            "total_predictions": 0, "flagged_predictions": 0,
            "flag_rate_pct": 0.0, "common_warnings": [],
        }

    warning_counts: dict = {}
    flagged = 0
    for _, row in log_df.iterrows():
        result = validate_prediction_input(row.to_dict())
        if result["warnings"] or not result["valid"]:
            flagged += 1
        for w in result["warnings"]:
            warning_counts[w] = warning_counts.get(w, 0) + 1

    common_warnings = [
        {"warning": k, "count": v}
        for k, v in sorted(warning_counts.items(), key=lambda x: -x[1])[:5]
    ]

    return {
        "city"               : city,
        "hours"              : hours,
        "total_predictions"  : total,
        "flagged_predictions": flagged,
        "flag_rate_pct"      : round(flagged / total * 100, 2),
        "common_warnings"    : common_warnings,
    }


@app.post('/reports/weekly', tags=['reports'])
def reports_weekly(
    city: str  = 'Riyadh',
    auth: Dict = Depends(require_admin),
):
    """Generate and return weekly HTML performance report. Admin only."""
    output_path = f'weekly_report_{city.lower()}.html'
    generate_weekly_report(city=city, output_path=output_path)
    return FileResponse(
        path         = output_path,
        media_type   = 'text/html',
        filename     = f'traffic_report_{city.lower()}_weekly.html',
    )





# ---------------------------------------------------------------------------
# WebSocket — real-time zone congestion streaming
# ---------------------------------------------------------------------------

from fastapi import WebSocket, WebSocketDisconnect
import asyncio

@app.websocket("/ws/live/{city}")
async def ws_live(websocket: WebSocket, city: str, api_key: str = ""):
    """
    Stream live congestion snapshots for all zones in a city every 30 seconds.

    Authentication: pass api_key as a query parameter.
    Closes with code 1008 (policy violation) on invalid or missing key.

    Snapshot format per zone:
        {zone, congestion_score, congestion_level, risk_score,
         anomaly_flag, timestamp}
    """
    # --- Auth ---
    resolved_key = _resolve_api_key(api_key)
    if not resolved_key:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        while True:
            snapshot = _build_city_snapshot(city)
            await websocket.send_json(snapshot)
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


def _resolve_api_key(key: str) -> bool:
    """
    Validate a raw key string against the configured key registry.

    Returns True if key is valid, False otherwise.
    Supports both single API_KEY and multi-tenant API_KEYS registry.
    """
    if not key:
        return False

    # Multi-tenant registry (PROMPT 025)
    if hasattr(app.state, "key_registry") and app.state.key_registry:
        return key in app.state.key_registry

    # Single-key fallback
    return key == API_KEY


def _build_city_snapshot(city: str) -> dict:
    """
    Build a current congestion snapshot for all zones in a city.

    Uses app.state.city_dfs if available (PROMPT 016 multi-city),
    falls back to app.state.df filtered by city.
    """
    from datetime import datetime
    from src.model import congestion_level, compute_accident_risk

    try:
        if hasattr(app.state, "city_dfs") and city in app.state.city_dfs:
            df = app.state.city_dfs[city]
        else:
            df = app.state.df[app.state.df["city"] == city]

        if df.empty:
            return {
                "city": city,
                "timestamp": datetime.now().isoformat(),
                "error": f"No data for city: {city}",
                "zones": [],
            }

        latest = (
            df.sort_values("timestamp")
            .groupby("zone")
            .last()
            .reset_index()
        )

        zones = []
        for _, row in latest.iterrows():
            score = float(row.get("congestion_score", 0.0))
            level = congestion_level(score)
            weather = str(row.get("weather", "clear"))
            hour = int(row.get("hour", 0))
            vehicle_count = float(row.get("vehicle_count", 0))
            avg_speed = float(row.get("avg_speed", 60))
            road_type = str(row.get("road_type", "arterial"))
            is_weekend = int(row.get("is_weekend", 0))
            rush_hour = int(row.get("rush_hour", 0))

            risk_result = compute_accident_risk(
                congestion_score=score,
                weather=weather,
                hour=hour,
                is_weekend=is_weekend,
                rush_hour=rush_hour,
            )

            anomaly_flag = int(row.get("anomaly_flag", 0)) if "anomaly_flag" in row else 0

            zones.append({
                "zone": str(row["zone"]),
                "congestion_score": round(score, 4),
                "congestion_level": level,
                "risk_score": risk_result.get("risk_score", 0.0),
                "risk_level": risk_result.get("risk_level", "Safe"),
                "anomaly_flag": anomaly_flag,
                "vehicle_count": round(vehicle_count, 0),
                "avg_speed": round(avg_speed, 1),
                "weather": weather,
                "hour": hour,
            })

        return {
            "city": city,
            "timestamp": datetime.now().isoformat(),
            "zone_count": len(zones),
            "zones": zones,
        }

    except Exception as e:
        return {
            "city": city,
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "zones": [],
        }