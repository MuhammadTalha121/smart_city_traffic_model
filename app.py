import os
import csv
from typing import Optional
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional
import pandas as pd


from src.edge_simulation import EdgeCabinetSimulator
from src.model import WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING, estimate_noise_level, predict_parking_occupancy
from src.reporter import generate_weekly_report
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from src.reporter import generate_api_doc_package

from src.datex_export import generate_datex_payload, generate_csv_data, generate_geojson_payload


from src.siri_export import (
    to_siri_vehicle_activity, to_siri_estimated_timetable, build_siri_service_delivery,
)

from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import time
from src.queue_worker import TelemetryQueue

from fastapi.responses import Response

from src.config import (HAJJ_DATES, SAUDI_CITIES, VSL_HIGHWAY_ZONES, IDS_MAX_SPEED_KMPH, NOISE_BASE_DB,
                         NOISE_THRESHOLDS, ZONE_ADJACENCY, PRIORITY_VEHICLE_SPEED_KMPH, TELEMETRY_QUEUE_MAX_SIZE,
                        TELEMETRY_BATCH_SIZE,
                        TELEMETRY_FLUSH_INTERVAL_S, PARKING_HUBS, LATENCY_SLA_THRESHOLD_MS, METRICS_ENDPOINT,
                        DRT_ELIGIBLE_ZONES, DRT_SHUTTLE_CAPACITY, DRT_MAX_WAIT_MINS, MAX_DATA_AGE_SECONDS,
                        EMISSIONS_ROUTING_WEIGHT)

from src.drt import DRTAllocator

from src.data import (generate_traffic_data, apply_hourly_patterns, add_lag_features,
                       get_active_events, apply_event_multipliers, detect_lineage_faults)
from src.model import (
    train_xgboost, prepare_features, predict_single, congestion_level,
    detect_anomalies, forecast_congestion, explain_prediction,
    log_prediction, get_intervention, compute_accident_risk,
    compute_signal_timing, compute_emissions, estimate_response_time,
    get_delivery_windows, compute_prediction_interval,
    compute_speed_degradation_index, compute_pedestrian_risk,
    compute_last_mile_index, compute_pavement_wear_index,
    compute_cooperative_route, predict_ev_charger_demand, compute_vsl_limit,
    recommend_tidal_flow, compute_crosswalk_timing, compute_thermal_risk,
    compute_thermal_risk, compute_thermal_risk, calculate_egress_plan,
    generate_vms_message, calculate_pareto_routes, estimate_air_quality,
    validate_freight_entry, calculate_evacuation_routes, train_xgboost_quantile, predict_with_confidence,
    validate_vms_message, detect_incidents,
        estimate_incident_clearance_time,
        INCIDENTS_LOG_PATH,
        _SEVERITY_ORDER,
)
from src.ids import SensorIntrusionDetector 


from src.ledger import ViolationLedger, verify_ledger_chain, LedgerIntegrityError
from src.config import VIOLATION_LEDGER_PATH, SLA_TREND_WINDOW_DAYS

from src.adapters import get_adapter, GreenWavePlanner, GreenWavePlanner, is_data_stale
from src.pipeline import run_pipeline, compute_drift_score, check_thresholds, deliver_webhook_alert, log_alert
from src.pipeline import run_pipeline, compute_drift_score, log_api_usage, build_key_registry, validate_prediction_input, compute_sla_metrics
from src.pipeline import read_predictions_log, compute_sla_trend, check_sla_breach_alerts

from src.auth import validate_key, create_key, deactivate_key, rotate_key, init_auth_db



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

VALID_SOURCES = ["weather", "osm", "mock", "micromobility"]


# ── Quota configuration ──
DAILY_QUOTA_LIMIT = int(os.getenv("DAILY_QUOTA_LIMIT", "10000"))
QUOTA_EXEMPT_ENDPOINTS = ["/health", "/sla/current"]

def _write_usage_log(log_data: dict) -> None:
    """Append a single usage log row to usage_log.csv."""
    log_path = "usage_log.csv"
    row = pd.DataFrame([log_data])
    write_header = not os.path.exists(log_path)
    row.to_csv(log_path, mode="a", header=write_header, index=False)

def get_today_usage_for_key(key_hash: str) -> int:
    """
    Count how many requests this API key (first 8 chars) has made today.
    """
    log_path = "usage_log.csv"
    if not os.path.exists(log_path):
        return 0

    try:
        df = pd.read_csv(log_path)
    except Exception:
        return 0

    if "timestamp" not in df.columns or "api_key_hash" not in df.columns:
        return 0

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    today = datetime.now().date()
    today_mask = df["timestamp"].dt.date == today
    key_mask = df["api_key_hash"] == key_hash
    return int(df[today_mask & key_mask].shape[0])

def _get_registry() -> Dict[str, Dict]:
    try:
        return app.state.key_registry
    except AttributeError:
        return {}


        

def require_api_key(key: str = Depends(api_key_header)) -> Dict:
    """
    Validate X-API-Key. Returns {key, role, city_scope}.
    Checks: auth.db, then API_KEY env, then legacy API_KEYS env.
    """
    if not key:
        raise HTTPException(status_code=401, detail="Missing API key")
    
    # 1. Try auth.db (new keys)
    auth_info = validate_key(key)
    if auth_info:
        return {
            'key': key,
            'role': auth_info['role'],          # already uppercase (ADMIN, OPERATOR, READ_ONLY)
            'city_scope': auth_info['city_scope']
        }
    
    # 2. Fallback to single API_KEY from .env
    if key == API_KEY:
        return {
            'key': key,
            'role': 'ADMIN',                    # ← uppercase
            'city_scope': '*'
        }
    
    # 3. Legacy multi-tenant support (API_KEYS env var)
    api_keys_env = os.getenv("API_KEYS", "")
    if api_keys_env:
        for entry in api_keys_env.split(","):
            entry = entry.strip()
            if not entry:
                continue
            parts = entry.split(":")
            if len(parts) >= 3:
                k, city, role = parts[0], parts[1], parts[2]
                if key == k:
                    return {
                        'key': key,
                        'role': role.upper(),   # ← uppercase
                        'city_scope': city
                    }
    
    raise HTTPException(status_code=401, detail="Invalid or missing API key")



def role_required(allowed_roles: List[str]):
    def _check(auth: Dict = Depends(require_api_key)):
        # Compare uppercase
        if auth['role'].upper() not in [r.upper() for r in allowed_roles]:
            raise HTTPException(status_code=403, detail=f"Role '{auth['role']}' not allowed. Required: {allowed_roles}")
        return auth
    return _check





def require_admin(auth: Dict = Depends(require_api_key)) -> Dict:
    """Extend require_api_key with admin role enforcement."""
    if auth['role'].upper() != 'ADMIN':
        raise HTTPException(status_code=403, detail='This endpoint requires admin role.')
    return auth

def _assert_city_permitted(auth: Dict, requested_city: str) -> None:
    """Raise 403 if key city scope does not cover requested_city."""
    city_scope = auth.get('city') or auth.get('city_scope', '*')
    # Treat both '*' and 'all' as wildcards
    if city_scope in ('*', 'all'):
        return
    if city_scope.lower() != requested_city.lower():
        raise HTTPException(
            status_code=403,
            detail=f"API key is scoped to '{city_scope}' — cannot access '{requested_city}'.",
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

        # --- Recurring Events ---
    from src.data import get_active_events
    active_events = get_active_events(city, today)

    return {
        "schedule"     : schedule,
        "next_event"   : next_event,
        "days_until"   : days_until,
        "active_events": [
            {
                "name"       : ev["name"],
                "multiplier" : ev["multiplier"],
                "peak_hours" : ev["peak_hours"],
            }
            for ev in active_events
        ],
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Train model on Riyadh, generate data for all cities, start scheduler."""
    init_auth_db()
    app.state.key_registry = build_key_registry()
    city_dfs = {}
    for city in ["Riyadh", "NEOM", "Dubai", "Karachi"]:
        df = generate_traffic_data(city=city)
        df = apply_hourly_patterns(df, city=city)
        df = apply_event_multipliers(df, city=city)
        df = add_lag_features(df)
        city_dfs[city] = df

    # Train on Riyadh as primary model
    X, y, feature_cols = prepare_features(city_dfs["Riyadh"])
    model, _, _        = train_xgboost(X, y)
    quantile_models = train_xgboost_quantile(X, y)
    app.state.quantile_models = quantile_models
    app.state.df           = city_dfs["Riyadh"]   # default city for existing endpoints
    app.state.city_dfs     = city_dfs
    app.state.model        = model
    app.state.feature_cols = feature_cols
    app.state.data_source  = "mock"
    app.state.data_source_fetched_at = datetime.now()
    app.state.last_retrain = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    app.state.last_drt_allocation = {}

    scheduler.add_job(_scheduled_pipeline, "cron", hour=3, minute=0)

        # Deduplication cache for alerts: key -> last_sent_timestamp
    app.state._last_alert_sent = {}

    def _scheduled_alerts():
        from src.pipeline import check_incident_alerts

        for city, city_df in app.state.city_dfs.items():
            # --- Congestion alerts ---
            congestion_alerts = check_thresholds(city_df, city=city)

            # --- Incident alerts ---
            incident_alerts = check_incident_alerts(city_df, city=city)

            # --- Combine and deduplicate ---
            all_alerts = congestion_alerts + incident_alerts
            fresh_alerts = []

            for alert in all_alerts:
                alert_type = alert.get("alert_type", "congestion")
                severity = alert.get("severity", alert.get("metric", "Unknown"))
                key = f"{alert_type}:{city}:{alert['zone']}:{severity}"
                last_sent = app.state._last_alert_sent.get(key)
                now = datetime.now(timezone.utc)

                if last_sent is None or (now - last_sent).total_seconds() > 900:
                    app.state._last_alert_sent[key] = now
                    fresh_alerts.append(alert)

            # --- Log and deliver ---
            if fresh_alerts:
                log_alert(fresh_alerts)

                # Build combined payload for webhook
                payload = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "city": city,
                    "congestion_alerts": [
                        a for a in fresh_alerts if a.get("alert_type") != "incident"
                    ],
                    "incident_alerts": [
                        a for a in fresh_alerts if a.get("alert_type") == "incident"
                    ],
                }
                deliver_webhook_alert(payload["congestion_alerts"] + payload["incident_alerts"], WEBHOOK_URL)
                print(f"[Alert] {len(fresh_alerts)} alert(s) fired for {city} "
                      f"({len(payload['congestion_alerts'])} congestion, "
                      f"{len(payload['incident_alerts'])} incident)")

        # --- SLA breach alerts (separate loop, no dedup needed) ---
        sla_alerts = check_sla_breach_alerts(days=1)
        if sla_alerts:
            log_alert(sla_alerts)
            deliver_webhook_alert(sla_alerts, WEBHOOK_URL)
            print(f"[Alert] {len(sla_alerts)} SLA breach alert(s) fired")

    scheduler.add_job(_scheduled_alerts, "interval", minutes=15)
    print("[Scheduler] Alert threshold monitoring scheduled every 15 minutes")
    scheduler.add_job(
    lambda: generate_weekly_report(city='Riyadh'),
    'cron', day_of_week='mon', hour=6, minute=0
)

    scheduler.start()
    print("[Scheduler] Nightly retraining scheduled at 03:00")

    telemetry_queue = TelemetryQueue()
    # Define a state getter that returns the needed attributes
    def _get_state():
        return app.state
    telemetry_queue.start_worker(_get_state)
    app.state.telemetry_queue = telemetry_queue

        # ===== Edge cabinet simulators =====
    from src.edge_simulation import EdgeCabinetSimulator
    from src.config import ZONE_ADJACENCY
    edge_cabinets = {}
    for zone, neighbors in ZONE_ADJACENCY.items():
        edge_cabinets[zone] = EdgeCabinetSimulator(zone, neighbors)
    app.state.edge_cabinets = edge_cabinets

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


@app.exception_handler(LedgerIntegrityError)
async def ledger_integrity_error_handler(request: Request, exc: LedgerIntegrityError):
    """
    PROMPT 068 — ALERT step of the break-recovery procedure. Surfaces a
    frozen ledger as a clear, structured HTTP 503 instead of a generic
    500, so the failure (and the exact first_break_at_row to investigate)
    is visible in the API response rather than swallowed by a citation
    write that silently failed.
    """
    return JSONResponse(
        status_code=503,
        content={
            "error"  : "LEDGER_CHAIN_BROKEN",
            "message": str(exc),
            "report" : exc.report,
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["GET", "POST"],
    allow_headers     = ["*"],
)

# Add security scheme for OpenAPI docs
# app.security_schemes = {
#     "apiKey": {
#         "type": "apiKey",
#         "in": "header",
#         "name": "X-API-Key",
#     }
# }



# ===== Prometheus Metrics =====
from prometheus_client import REGISTRY

def _counter(name, doc, labels):
    try:
        return Counter(name, doc, labels)
    except ValueError:
        return REGISTRY._names_to_collectors[name]

def _histogram(name, doc, labels, buckets=None):
    try:
        return Histogram(name, doc, labels, **({"buckets": buckets} if buckets else {}))
    except ValueError:
        return REGISTRY._names_to_collectors[name]

def _gauge(name, doc):
    try:
        return Gauge(name, doc)
    except ValueError:
        return REGISTRY._names_to_collectors[name]

REQUEST_COUNT     = _counter('api_requests_total', 'Total API requests', ['endpoint', 'method', 'status_code'])
REQUEST_LATENCY   = _histogram('api_request_duration_seconds', 'API request latency in seconds', ['endpoint'], buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0])
DRIFT_SCORE_GAUGE = _gauge('model_drift_score', 'Current model drift score')
QUEUE_DEPTH_GAUGE = _gauge('telemetry_queue_depth', 'Current telemetry queue depth')




@app.middleware("http")
async def usage_logging_middleware(request: Request, call_next):
    """
    Log every request to usage_log.csv and enforce daily per‑key quota.
    """
    import time

    raw_key  = request.headers.get("X-API-Key", "anonymous")
    key_hash = raw_key[:8] if raw_key != "anonymous" else "anonymous"
    endpoint = request.url.path
    method   = request.method
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Quota check (skip for exempt endpoints and anonymous) ──
    if endpoint not in QUOTA_EXEMPT_ENDPOINTS and raw_key != "anonymous":
        today_usage = get_today_usage_for_key(key_hash)
        if today_usage >= DAILY_QUOTA_LIMIT:
            # Log the blocked request (status 429) before returning
            _write_usage_log({
                "timestamp": timestamp,
                "endpoint": endpoint,
                "method": method,
                "api_key_hash": key_hash,
                "response_code": 429,
                "response_time_ms": 0,  # no processing time
            })

            # Calculate seconds until midnight
            now = datetime.now()
            seconds_until_midnight = (
                (24 - now.hour - 1) * 3600 +
                (60 - now.minute - 1) * 60 +
                (60 - now.second)
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "DAILY_QUOTA_EXCEEDED",
                    "message": f"Daily quota of {DAILY_QUOTA_LIMIT} requests exceeded.",
                    "retry_after": "tomorrow 00:00",
                    "key_prefix": key_hash,
                    "calls_today": today_usage,
                },
                headers={"Retry-After": str(seconds_until_midnight)}
            )

    # ── Process request ──
    start = time.monotonic()
    response = await call_next(request)
    duration = round((time.monotonic() - start) * 1000, 1)

    # ── Log the successful (or other) request ──
    _write_usage_log({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "endpoint": endpoint,
        "method": method,
        "api_key_hash": key_hash,
        "response_code": response.status_code,
        "response_time_ms": duration,
    })

    return response



@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    endpoint = request.url.path
    method = request.method

    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    REQUEST_COUNT.labels(endpoint=endpoint, method=method, status_code=response.status_code).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)

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
    school_holiday: bool = Field(False, description="Set True during school holiday periods to apply term-break demand pattern")


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
        app.state.data_source_fetched_at = (
            sample_df['fetched_at'].iloc[0]
            if 'fetched_at' in sample_df.columns and not sample_df.empty
            else datetime.now()
        )


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
    DRIFT_SCORE_GAUGE.set(drift_score) 
    next_scheduled = "03:00 daily"

    return {
        "drift_score"    : drift_score,
        "drift_threshold": 1.3,
        "needs_retrain"  : drift_score >= 1.3,
        "last_retrain"   : app.state.last_retrain,
        "next_scheduled" : next_scheduled,
    }


@app.post("/pipeline/trigger", tags=["pipeline"])
def pipeline_trigger(auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN']))):
    print(f"[Pipeline] Manual trigger at {datetime.now()}")
    result = run_pipeline(city="Riyadh")

    if result["promoted"]:
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

    active_source = app.state.data_source
    fetched_at    = getattr(app.state, "data_source_fetched_at", None)
    if is_data_stale(active_source, fetched_at):
        age_seconds = (datetime.now() - fetched_at).total_seconds()
        raise HTTPException(
            status_code=503,
            detail={
                "error"          : "STALE_DATA_FEED",
                "message"        : f"Active data source '{active_source}' has not refreshed within its staleness threshold.",
                "data_source"    : active_source,
                "age_seconds"    : round(age_seconds, 1),
                "max_age_seconds": MAX_DATA_AGE_SECONDS.get(active_source),
            },
        )

    p          = payload.model_dump()
    validation = validate_prediction_input(p)
    if not validation["valid"]:
        raise HTTPException(
            status_code=422,
            detail={"message": "Input validation failed.", "errors": validation["errors"]},
        )

    p      = payload.model_dump()


    # ──  IDS validation ─────────────────────────────────────────
    _ids_detector = SensorIntrusionDetector()

    _zone_df = app.state.df[app.state.df["zone"] == p["zone"]] \
               if "zone" in app.state.df.columns else app.state.df

    _zone_mean = float(_zone_df["vehicle_count"].mean()) \
                 if not _zone_df.empty else 150.0
    _zone_std  = float(_zone_df["vehicle_count"].std()) \
                 if not _zone_df.empty and len(_zone_df) > 1 else 50.0

    _ids_result = _ids_detector.validate_reading(
        zone                 = p["zone"],
        hour                 = p["hour"],
        vehicle_count        = p["vehicle_count"],
        avg_speed            = p["avg_speed"],
        zone_historical_mean = _zone_mean,
        zone_historical_std  = _zone_std,
        is_weekend           = p["is_weekend"],
    )

    if _ids_result["risk_level"] != "Clean":
        _log_ids_event(_ids_result, p)

    if _ids_result["risk_level"] == "Blocked":
        raise HTTPException(
            status_code=422,
            detail={
                "error":      "IDS_BLOCKED",
                "message":    "Sensor reading blocked: physically impossible values detected.",
                "ids_report": _ids_result,
            },
        )
    # ── end IDS ───────────────────────────────────────────────────────────


    active_events = get_active_events(p["city"])
    event_mult = 1.0
    for ev in active_events:
        if p["hour"] in ev.get('peak_hours', []):
            event_mult *= ev['multiplier']
    adjusted_vehicle_count = min(p["vehicle_count"] * event_mult, 500)

    result = predict_single(
        city            = p["city"],
        zone            = p["zone"],
        hour            = p["hour"],
        vehicle_count   = adjusted_vehicle_count,
        avg_speed       = p["avg_speed"],
        weather         = p["weather"],
        road_type       = p["road_type"],
        rush_hour       = p["rush_hour"],
        is_weekend      = p["is_weekend"],
        is_late_night   = p["is_late_night"],
        event           = p["event"],
        hour_multiplier = p["hour_multiplier"],
    )

    # Annotate active events in response
    result["active_events"] = [
        {"name": ev["name"], "multiplier": ev["multiplier"], "peak_hours": ev["peak_hours"]}
        for ev in active_events
    ]

    # Annotate active schedule in response
    schedule_info        = _get_active_schedule(p["city"])
    result["schedule"]   = schedule_info["schedule"]
    result["hajj_mode"]  = p["hajj_mode"]
    result["school_holiday_mode"] = p["school_holiday"]

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

    confidence = predict_with_confidence(app.state.quantile_models, X_row)
    result["confidence"] = {
        "confidence_low"  : confidence["confidence_low"],
        "confidence_high" : confidence["confidence_high"],
        "confidence_level": confidence["confidence_level"],
    }

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

    result["noise_estimate"] = estimate_noise_level(
        vehicle_count = p["vehicle_count"],
        avg_speed     = p["avg_speed"],
        road_type     = p["road_type"],
        hour          = p["hour"],
    )
    

    log_prediction(result, explanation, interval_width=prediction_interval["confidence_width"],
                   data_source=app.state.data_source)
    if _ids_result["risk_level"] == "Suspicious":
        result["ids_warning"] = {
            "flags":      _ids_result["flags"],
            "risk_level": _ids_result["risk_level"],
            "message":    "Sensor reading accepted with anomaly flags. Verify sensor hardware.",
        }
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
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
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
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
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
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
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
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
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





# ---------------------------------------------------------------------------
# Tidal flow control endpoints — authenticated
# ---------------------------------------------------------------------------

@app.get("/control/tidal-reversals", tags=["control"])
def tidal_reversals(
    city: str = "Riyadh",
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """Tidal flow lane reversal recommendations for eligible zones at current demand."""
    df              = app.state.df[app.state.df["city"] == city]
    recommendations = []

    for zone in TIDAL_ELIGIBLE_ZONES:
        zone_df = df[df["zone"] == zone].sort_values("timestamp")
        if zone_df.empty:
            continue
        latest = zone_df.iloc[-1]
        result = recommend_tidal_flow(
            zone          = zone,
            hour          = int(latest["hour"]),
            vehicle_count = float(latest["vehicle_count"]),
        )
        if result["recommended"]:
            recommendations.append(result)

    return {
        "city"                  : city,
        "total_recommendations" : len(recommendations),
        "recommendations"       : recommendations,
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

    log_df = read_predictions_log(log_path)
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
    auth:        Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
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

    log_df = read_predictions_log(log_path)

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

    log_df = read_predictions_log(log_path)

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
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
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
        vehicle_count = float(latest.get('vehicle_count', 100.0))

        sdi_result = compute_speed_degradation_index(avg_speed, road_type, weather, vehicle_count)
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



@app.get("/vsl/active-limits", tags=["safety"])
def vsl_active_limits(
    city: str = "Riyadh",
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """
    Recommend variable speed limits for highway zones based on
    current visibility conditions from WeatherAdapter.
 
    Falls back to clear/10000m visibility if the weather API
    is unreachable.
    """
    _assert_city_permitted(auth, city)
 
    try:
        weather_df   = get_adapter("weather").fetch(city)
        weather      = str(weather_df["weather"].iloc[0])
        visibility_m = float(weather_df["visibility"].iloc[0])
    except Exception:
        weather, visibility_m = "clear", 10000.0
 
    df = app.state.city_dfs.get(city, app.state.df)
 
    results = []
    for zone in VSL_HIGHWAY_ZONES:
        zone_df   = df[df["zone"] == zone]
        avg_speed = float(zone_df["avg_speed"].iloc[-1]) if not zone_df.empty else 65.0
 
        vsl = compute_vsl_limit(
            weather        = weather,
            visibility_m   = visibility_m,
            avg_speed_kmph = avg_speed,
        )
 
        results.append({
            "zone": zone,
            **vsl,
        })
 
    return {
        "city"           : city,
        "current_weather": weather,
        "visibility_m"   : round(visibility_m, 1),
        "zones"          : results,
    }




@app.get("/safety/pedestrian", tags=["safety"])
@limiter.limit("20/minute")
def safety_pedestrian(
    request: Request,
    city:    str = "Riyadh",
    auth:    Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
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




@app.post("/reports/api-docs", dependencies=[Depends(require_admin)])
async def generate_api_docs():
    """
    Generate a self-contained HTML government API documentation package.
    Requires ADMIN role.
    Returns the HTML file as a download.
    """
    try:
        output_path = generate_api_doc_package(output_dir="reports")
        return FileResponse(
            output_path,
            media_type="text/html",
            filename="api_documentation.html"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Documentation generation failed: {str(e)}")






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
    """Full SLA compliance report. Admin only. Now includes trend + breach_alerts."""
    metrics = compute_sla_metrics(days=days)
    metrics["trend"] = compute_sla_trend(window_days=SLA_TREND_WINDOW_DAYS)
    metrics["breach_alerts"] = check_sla_breach_alerts(days=days)
    return metrics


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
    auth:  Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """
    Summarise input quality flags from the predictions audit log, plus
    upstream lineage faults (PROMPT 087) detected on the active data
    source's current traffic DataFrame.
    """
    _assert_city_permitted(auth, city)

    active_source  = app.state.data_source
    lineage_df     = app.state.city_dfs.get(city, app.state.df)
    lineage_result = detect_lineage_faults(lineage_df, active_source)

    log_path = "predictions_log.csv"

    if not os.path.exists(log_path):
        return {
            "city": city, "hours": hours,
            "total_predictions": 0, "flagged_predictions": 0,
            "flag_rate_pct": 0.0, "common_warnings": [],
            "active_source"  : active_source,
            "lineage_faults" : lineage_result,
            "message": "No predictions logged yet.",
        }

    log_df = read_predictions_log(log_path)
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
            "active_source"  : active_source,
            "lineage_faults" : lineage_result,
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
        "active_source"      : active_source,
        "lineage_faults"     : lineage_result,
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



@app.get('/reports/latest', tags=['reports'])
def reports_latest(
    city: str = 'Riyadh',
    auth: Dict = Depends(require_admin),
):
    """Generate and return the latest weekly PDF report. Admin only. Local file only."""
    from src.reporter import generate_weekly_report_pdf

    output_path = f'reports/weekly_report_{city.lower()}.pdf'
    generate_weekly_report_pdf(city=city, output_path=output_path)
    return FileResponse(
        path=output_path,
        media_type='application/pdf',
        filename=f'traffic_report_{city.lower()}_weekly.pdf',
    )



@app.get("/export/datex", tags=["export"])
@limiter.limit("20/minute")
def export_datex(
    request: Request,
    city: str = "Riyadh",
    format: str = "json",
    auth: Dict = Depends(require_api_key),
):
    """
    Export traffic data in a DATEX II‑shaped JSON structure.

    This is a minimal translation layer to demonstrate interoperability
    with systems expecting DATEX II (CEN/ISO standard for traffic data
    exchange). It covers:
      - MeasuredDataPublication: per‑zone traffic flow, speed, congestion,
        and CO₂ emissions.
      - SituationPublication: active anomalies (incidents/hotspots).

    This is NOT a full DATEX II implementation; many fields (vehicle type,
    measurement site type, detailed geometry, etc.) are not mapped due to
    data limitations. Use this as a proof of interoperability.

    Query parameters:
      - city: Riyadh (default) or other configured city.
      - format: only 'json' is supported; 'xml' may be added later.

    Authentication required (X-API-Key header).
    Rate limit: 20 requests per minute.
    """
    if format.lower() != "json":
        # For now, only JSON is supported; we could return 400 or a note.
        # We'll return the JSON with a warning.
        pass

    payload = generate_datex_payload(city)
    # If format is xml, we could convert using xmltodict, but we'll keep as JSON.
    return payload





from src.datex_export import generate_geojson_payload
from fastapi import Query, HTTPException

@app.get("/export/geojson", tags=["export"])
@limiter.limit("20/minute")
def export_geojson(
    request: Request,
    city: str = "Riyadh",
    auth: Dict = Depends(require_api_key),
):
    """
    Export traffic data as a GeoJSON FeatureCollection.

    Each zone is a Point feature with properties:
      - zone, congestion_score, congestion_level,
        vehicle_count, avg_speed, co2_kg_per_hour, timestamp.

    This is directly loadable into QGIS, ArcGIS, Leaflet, Google Maps,
    and other GIS platforms. No conversion needed.

    Authentication required (X-API-Key header).
    Rate limit: 20 requests per minute.
    """
    payload = generate_geojson_payload(city)
    return JSONResponse(content=payload, media_type="application/geo+json")



@app.get("/export/csv", tags=["export"])
@limiter.limit("10/minute")
def export_csv(
    request: Request,
    city: Optional[str] = None,
    zone: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    include_anomalies: bool = False,
    auth: Dict = Depends(require_api_key),
):
    """
    Export historical traffic data as CSV for offline analytics.

    Query parameters:
      - city: filter by city name (e.g., Riyadh)
      - zone: filter by zone name (e.g., Zone_1)
      - start_date: ISO date (YYYY-MM-DD) – inclusive
      - end_date: ISO date (YYYY-MM-DD) – inclusive
      - include_anomalies: if true, adds an anomaly_flag column (1=anomalous)

    Returns a CSV file download.

    Authentication required (X-API-Key header).
    Rate limit: 10 requests per minute.
    """
    from datetime import datetime

    from io import StringIO

    df = generate_csv_data(city, zone, start_date, end_date, include_anomalies)

    # Force-add FIRST, before any empty check
    if include_anomalies and 'anomaly_flag' not in df.columns:
        df = df.copy()
        df['anomaly_flag'] = 0

    # Only 404 if genuinely no data AND no anomaly header was requested
    if df.empty and not include_anomalies:
        raise HTTPException(status_code=404, detail="No data found for the given filters.")

    output = StringIO()
    df.to_csv(output, index=False)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=traffic_data_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
        }
    )



@app.get("/export/siri", tags=["export"])
@limiter.limit("20/minute")
def export_siri(
    request: Request,
    city: str = "Riyadh",
    include_vehicles: bool = True,
    include_timetable: bool = True,
    auth: Dict = Depends(require_api_key),
):
    """
    SIRI-shaped export (SIRI-VM VehicleActivity + SIRI-ET EstimatedTimetableDelivery).
    Not a full SIRI implementation — see src/siri_export.py module docstring for scope.
    """
    if city not in app.state.city_dfs:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found.")
    _assert_city_permitted(auth, city)

    vehicle_activities = []
    if include_vehicles:
        cached = getattr(app.state, "last_drt_allocation", {}).get(city, {})
        for trip in cached.get("trips", []):
            vehicle_activities.append(to_siri_vehicle_activity(trip))

    estimated_journeys = []
    if include_timetable:
        df = app.state.city_dfs[city]
        for zone in sorted(df["zone"].unique()):
            zone_rows = df[df["zone"] == zone].sort_values("timestamp")
            if zone_rows.empty:
                continue
            latest = zone_rows.iloc[-1]
            timing = compute_signal_timing(
                congestion_score=float(latest["congestion_score"]),
                vehicle_count=float(latest.get("vehicle_count", 0)),
                hour=int(latest["hour"]),
                is_weekend=int(latest.get("is_weekend", 0)),
            )
            estimated_journeys.append(to_siri_estimated_timetable(zone, timing))

    return build_siri_service_delivery(
        vehicle_activities, estimated_journeys, producer_ref=f"SmartCityTraffic-{city}",
    )





@app.get("/mobility/last-mile", tags=["mobility"])
def last_mile_efficiency(
    city: str  = "Riyadh",
    auth: Dict = Depends(require_api_key),
):
    """
    Return last-mile modal shift index per zone.

    Fetches live micro-mobility counts from MockMicroMobilityAdapter,
    computes last_mile_index per zone, and returns an interpretation.
    Only zones in LAST_MILE_TRANSFER_ZONES receive the congestion bonus.
    """
    from src.config import LAST_MILE_TRANSFER_ZONES
    _assert_city_permitted(auth, city)

    adapter = get_adapter("micromobility")
    mm_df   = adapter.fetch(city)

    df      = app.state.city_dfs.get(city, app.state.df)
    latest  = (
        df.sort_values("timestamp")
          .groupby("zone")
          .last()
          .reset_index()
    )

    results = []
    for _, row in latest.iterrows():
        zone  = str(row["zone"])
        score = float(row.get("congestion_score", 0.0))
        level = congestion_level(score)
        vc    = float(row.get("vehicle_count", 1.0))

        mm_row = mm_df[mm_df["zone"] == zone]
        scooters = int(mm_row["active_scooters"].values[0]) if not mm_row.empty else 0
        bikes    = int(mm_row["active_bikes"].values[0])    if not mm_row.empty else 0

        index = compute_last_mile_index(vc, scooters, bikes, level, zone)

        if   index >= 0.6: interpretation = "Good modal shift"
        elif index >= 0.3: interpretation = "Partial modal shift"
        else:              interpretation = "Low modal shift"

        results.append({
            "zone"            : zone,
            "last_mile_index" : index,
            "interpretation"  : interpretation,
            "active_scooters" : scooters,
            "active_bikes"    : bikes,
            "vehicle_count"   : round(vc, 0),
            "congestion_level": level,
            "transfer_zone"   : zone in LAST_MILE_TRANSFER_ZONES,
        })

    results.sort(key=lambda x: -x["last_mile_index"])

    return {
        "city"   : city,
        "zones"  : results,
        "summary": {
            "transfer_zones"            : LAST_MILE_TRANSFER_ZONES,
            "avg_last_mile_index"       : round(
                sum(r["last_mile_index"] for r in results) / max(len(results), 1), 4
            ),
        },
    }




@app.get("/infrastructure/maintenance-priority", tags=["infrastructure"])
def maintenance_priority(
    city: str  = "Riyadh",
    auth: Dict = Depends(require_api_key),
):
    """
    Rank all zones by predicted pavement wear index.

    Fetches current temperature from WeatherAdapter, computes wear index
    per zone using latest congestion scores, returns zones sorted
    worst-first with maintenance priority and estimated intervention window.
    """
    _assert_city_permitted(auth, city)

    try:
        weather_df  = get_adapter("weather").fetch(city)
        temperature = float(weather_df["temperature"].iloc[0])
    except Exception:
        temperature = 38.0

    df     = app.state.city_dfs.get(city, app.state.df)
    latest = (
        df.sort_values("timestamp")
          .groupby("zone")
          .last()
          .reset_index()
    )

    results = []
    for _, row in latest.iterrows():
        zone   = str(row["zone"])
        vc     = float(row.get("vehicle_count", 100.0))
        cs     = float(row.get("congestion_score", 0.0))

        wear = compute_pavement_wear_index(
            vehicle_count       = vc,
            congestion_score    = cs,
            temperature_celsius = temperature,
        )
        wear["zone"] = zone
        results.append(wear)

    results.sort(key=lambda x: -x["wear_index"])

    return {
        "city"              : city,
        "temperature_celsius": round(temperature, 1),
        "zones_ranked"      : results,
        "data_source"       : "WeatherAdapter + live congestion",
    }




class CooperativeRouteRequest(BaseModel):
    city             : str   = "Riyadh"
    origin_zone      : str   = Field(..., json_schema_extra={"example": "Zone_1"})
    destination_zone : str   = Field(..., json_schema_extra={"example": "Zone_4"})
    penetration_rate : float = Field(0.30, ge=0.01, le=1.0)



@app.post("/v2x/cooperative-route", tags=["v2x"])
def cooperative_route(
    body: CooperativeRouteRequest,
    auth: Dict = Depends(require_api_key),
):
    """
    Simulate V2X cooperative routing between two zones.

    Builds a congestion_map from the latest zone scores in app.state,
    then runs weighted Dijkstra at the requested penetration_rate and
    compares it against selfish (near-zero cooperation) routing.
    """
    _assert_city_permitted(auth, body.city)

    df     = app.state.city_dfs.get(body.city, app.state.df)
    latest = (
        df.sort_values("timestamp")
          .groupby("zone")
          .last()
          .reset_index()
    )

    congestion_map = {
        str(row["zone"]): float(row.get("congestion_score", 0.1))
        for _, row in latest.iterrows()
    }

    if body.origin_zone not in congestion_map:
        raise HTTPException(status_code=422, detail=f"Unknown origin_zone: {body.origin_zone}")
    if body.destination_zone not in congestion_map:
        raise HTTPException(status_code=422, detail=f"Unknown destination_zone: {body.destination_zone}")

    result = compute_cooperative_route(
        origin_zone      = body.origin_zone,
        destination_zone = body.destination_zone,
        congestion_map   = congestion_map,
        penetration_rate = body.penetration_rate,
    )

    return {
        "city"            : body.city,
        "penetration_rate": body.penetration_rate,
        **result,
    }





@app.get('/toll/active-pricing')
def toll_active_pricing(city: str = 'Riyadh'):
    """Public endpoint — no auth. Returns current toll for all tolled zones with ceiling info."""
    from src.config import TOLLED_ZONES
    from src.model import calculate_dynamic_toll_with_ceiling, congestion_level
    import datetime

    df = app.state.df
    now = datetime.datetime.utcnow().isoformat()
    results = []
    for zone in TOLLED_ZONES:
        zone_df = df[df['zone'] == zone]
        score = float(zone_df['congestion_score'].mean()) if not zone_df.empty else 0.3
        toll_result = calculate_dynamic_toll_with_ceiling(zone, score, daily_toll_accumulated=0.0)
        results.append({
            'zone'            : zone,
            'toll_sar'        : toll_result['toll_amount'],
            'congestion_level': congestion_level(score),
            'last_updated'    : now,
            'ceiling_applied' : toll_result['ceiling_applied'],
            'reason'          : toll_result['reason'],
        })
    return {'city': city, 'tolled_zones': results}


@app.post('/toll/estimate')
def toll_estimate(payload: dict, api_key: str = Depends(require_api_key)):
    """Authenticated. Returns estimated toll for a journey with ceiling info."""
    from src.model import calculate_dynamic_toll_with_ceiling, congestion_level

    origin      = payload.get('origin_zone', 'Zone_1')
    destination = payload.get('destination_zone', 'Zone_2')
    vehicle     = payload.get('vehicle_type', 'passenger')
    hour        = int(payload.get('hour', 8))

    df = app.state.df
    def zone_score(z):
        zdf = df[df['zone'] == z]
        return float(zdf['congestion_score'].mean()) if not zdf.empty else 0.3

    origin_score = zone_score(origin)
    dest_score   = zone_score(destination)

    origin_result = calculate_dynamic_toll_with_ceiling(origin, origin_score, 0.0, vehicle)
    dest_result   = calculate_dynamic_toll_with_ceiling(destination, dest_score, 0.0, vehicle)

    total_toll = round(origin_result['toll_amount'] + dest_result['toll_amount'], 2)
    total_ceiling_applied = origin_result['ceiling_applied'] or dest_result['ceiling_applied']

    return {
        'origin_zone'          : origin,
        'destination_zone'     : destination,
        'vehicle_type'         : vehicle,
        'hour'                 : hour,
        'origin_toll_sar'      : origin_result['toll_amount'],
        'origin_ceiling_applied': origin_result['ceiling_applied'],
        'origin_reason'        : origin_result['reason'],
        'destination_toll_sar' : dest_result['toll_amount'],
        'dest_ceiling_applied' : dest_result['ceiling_applied'],
        'dest_reason'          : dest_result['reason'],
        'total_toll_sar'       : total_toll,
        'total_ceiling_applied': total_ceiling_applied,
        'congestion_level'     : congestion_level(max(origin_score, dest_score)),
    }





class ChargeLoadRequest(BaseModel):
    station_id             : str
    arriving_vehicles      : float = Field(..., ge=0)




@app.get("/grid/charger-status", tags=["grid"])
def charger_status(auth: Dict = Depends(require_api_key)):
    """Return predicted grid load status for all EV charging stations."""
    from src.config import EV_FAST_CHARGING_STATIONS

    results = []
    for station_id, sdata in EV_FAST_CHARGING_STATIONS.items():
        assumed_active = int(sdata['chargers'] * 0.6)
        status = predict_ev_charger_demand(
            station_id             = station_id,
            arrival_rate_per_hour  = assumed_active * 1.2,
            current_active_chargers= assumed_active,
        )
        status['total_chargers'] = sdata['chargers']
        results.append(status)

    results.sort(key=lambda x: -x['grid_load_pct'])
    return {'stations': results}


@app.post("/grid/optimize-charge-load", tags=["grid"])
def optimize_charge_load(
    body: ChargeLoadRequest,
    auth: Dict = Depends(require_api_key),
):
    """
    Return load-shifting recommendation for an EV charging station.

    Uses arriving_vehicles as arrival_rate_per_hour and assumes
    70% of chargers are currently active.
    """
    from src.config import EV_FAST_CHARGING_STATIONS

    if body.station_id not in EV_FAST_CHARGING_STATIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown station_id '{body.station_id}'. "
                   f"Valid: {list(EV_FAST_CHARGING_STATIONS.keys())}",
        )

    station         = EV_FAST_CHARGING_STATIONS[body.station_id]
    assumed_active  = int(station['chargers'] * 0.7)

    result = predict_ev_charger_demand(
        station_id             = body.station_id,
        arrival_rate_per_hour  = body.arriving_vehicles,
        current_active_chargers= assumed_active,
    )

    if result['overload_risk']:
        action = f"Redirect incoming vehicles to {result['recommended_redirect_to']}"
    else:
        action = "No action required — grid load within threshold"

    return {**result, 'recommended_action': action}




@app.post('/signals/tsp-actuation')
def tsp_actuation(payload: dict, api_key: str = Depends(role_required(['OPERATOR', 'ADMIN']))):
    """TSP green extension decision for an approaching bus."""
    from src.model import evaluate_transit_priority
    return evaluate_transit_priority(
        bus_distance_m          = float(payload.get('bus_distance_m', 200)),
        current_green_remaining_s = float(payload.get('current_green_remaining_s', 30)),
        passenger_count         = int(payload.get('passenger_count', 0)),
    ) | {
        'zone': payload.get('zone', 'unknown'),
    }



import math

@app.get('/federated/params')
def federated_params(api_key: str = Depends(role_required(['OPERATOR', 'ADMIN']))):
    from src.federated import extract_shareable_params
    params = extract_shareable_params(app.state.model)
    
    # Recursively replace NaN with None for JSON compliance
    def clean_nans(obj):
        if isinstance(obj, dict):
            return {k: clean_nans(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_nans(v) for v in obj]
        elif isinstance(obj, float) and math.isnan(obj):
            return None
        else:
            return obj
    
    params = clean_nans(params)
    return params


@app.post('/federated/aggregate')
def federated_aggregate(payload: dict, api_key: str = Depends(role_required(['OPERATOR', 'ADMIN']))):
    """Aggregate params from multiple cities — flags for next retrain."""
    from src.federated import simulate_aggregation
    city_params = payload.get('city_params', [])
    if not city_params:
        raise HTTPException(status_code=422, detail='city_params list required')
    result = simulate_aggregation(city_params)
    # Store result for next pipeline run
    app.state.pending_aggregation = result
    return {'status': 'aggregated', 'result': result}





import csv as _csv
from pathlib import Path as _Path
from datetime import datetime as _dt

IDS_LOG_PATH = "ids_log.csv"
_IDS_FIELDS  = ["timestamp", "zone", "hour", "risk_level", "flags",
                 "vehicle_count", "avg_speed"]


def _log_ids_event(ids_result: dict, request) -> None:
    """Append one IDS event row to ids_log.csv."""
    path    = _Path(IDS_LOG_PATH)
    is_new  = not path.exists()
    with open(path, "a", newline="") as f:
        writer = _csv.DictWriter(f, fieldnames=_IDS_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "timestamp":     _dt.utcnow().isoformat(),
            "zone":          ids_result["zone"],
            "hour":          ids_result["hour"],
            "risk_level":    ids_result["risk_level"],
            "flags":         "|".join(ids_result["flags"]),
            "vehicle_count": request.vehicle_count,
            "avg_speed":     request.avg_speed,
        })


@app.get("/ids/alerts", tags=["security"])
async def ids_alerts(
    city: str = "Riyadh",
    api_key: str = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """Return last 100 IDS events from ids_log.csv."""
    path = _Path(IDS_LOG_PATH)
    if not path.exists():
        return {"city": city, "alerts": [], "total": 0}

    import pandas as pd
    df = pd.read_csv(path)
    # Most recent first, cap at 100
    alerts = df.tail(100).iloc[::-1].to_dict(orient="records")
    return {
        "city":   city,
        "alerts": alerts,
        "total":  len(df),
    }




@app.get("/environment/noise-map", tags=["environment"])
async def noise_map(
    city: str = "Riyadh",
    auth: Dict = Depends(require_api_key),
):
    """
    PROMPT 041 — Returns noise estimates for all zones at current hour,
    sorted loudest to quietest.
    """
    _assert_city_permitted(auth, city)
    hour    = datetime.now().hour
    df      = app.state.city_dfs.get(city, app.state.df)
    results = []

    for zone in df["zone"].unique() if "zone" in df.columns \
                else [p["zone"] for p in [{}]]:
        zone_df   = df[df["zone"] == zone] if "zone" in df.columns else df
        avg_speed = float(zone_df["avg_speed"].mean()) \
                    if "avg_speed" in zone_df.columns else 60.0
        vehicle_count = int(zone_df["vehicle_count"].mean()) \
                        if "vehicle_count" in zone_df.columns else 100
        road_type = str(zone_df["road_type"].mode()[0]) \
                    if "road_type" in zone_df.columns else "arterial"

        noise = estimate_noise_level(
            vehicle_count = vehicle_count,
            avg_speed     = avg_speed,
            road_type     = road_type,
            hour          = hour,
        )
        results.append({"zone": zone, **noise})

    results.sort(key=lambda x: x["noise_db"], reverse=True)
    return {"city": city, "hour": hour, "zones": results}




class GreenWaveRequest(BaseModel):
    city:               str         = Field("Riyadh")
    route:              list[str]   = Field(..., min_length=2)
    vehicle_speed_kmph: float       = Field(PRIORITY_VEHICLE_SPEED_KMPH, gt=0)
    priority_level:     str         = Field("emergency")   # 'emergency' | 'vip'


@app.post("/control/green-wave", tags=["control"])
def green_wave(
    payload: GreenWaveRequest,
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """
    Calculate a synchronized green-wave phase schedule for a priority vehicle corridor.
    Returns per-zone green windows so the vehicle travels without stopping.
    """
    # Validate that every consecutive zone pair is adjacent
    for i in range(len(payload.route) - 1):
        src, dst = payload.route[i], payload.route[i + 1]
        if dst not in ZONE_ADJACENCY.get(src, []):
            raise HTTPException(
                status_code=400,
                detail=f"Non-adjacent zones in route: {src} → {dst}. "
                       f"Adjacent to {src}: {ZONE_ADJACENCY.get(src, [])}",
            )

    from datetime import datetime as _dt
    now = _dt.now()
    departure_s = now.hour * 3600 + now.minute * 60 + now.second

    planner = GreenWavePlanner()
    result  = planner.calculate_green_wave(
        route              = payload.route,
        vehicle_speed_kmph = payload.vehicle_speed_kmph,
        departure_time_s   = float(departure_s),
    )

    result["city"]           = payload.city
    result["priority_level"] = payload.priority_level
    result["generated_at"]   = now.strftime("%Y-%m-%d %H:%M:%S")

    return result



class CrosswalkTimingParams(BaseModel):
    city: str = "Riyadh"
    schedule: str = "standard"




@app.get("/pedestrian/crosswalk-timing", tags=["pedestrian"])
@limiter.limit("20/minute")
async def crosswalk_timing(
    request: Request,                    
    city: str = "Riyadh",
    schedule: str = "standard",
    _key: str = Depends(require_api_key),
):
    """
    Return crosswalk walk‑time recommendations for all zones in the city.
    Schedule can be 'standard', 'friday_prayer', 'hajj', or 'event'.
    """
    # Validate city exists
    if city not in app.state.city_dfs:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found.")

    df = app.state.city_dfs[city]

    zones = sorted(df['zone'].unique())
    result = {}

    for zone in zones:
        zone_rows = df[df['zone'] == zone].sort_values('timestamp')
        if len(zone_rows) == 0:
            continue
        latest = zone_rows.iloc[-1]
        score = latest['congestion_score']

        timing = compute_crosswalk_timing(
            zone=zone,
            hour=int(latest['hour']),
            congestion_score=float(score),
            schedule=schedule,
        )
        result[zone] = timing

    return {
        "city": city,
        "schedule": schedule,
        "zones": result,
    }






@app.get("/infrastructure/heat-risk", tags=["infrastructure"])
@limiter.limit("20/minute")
async def heat_risk(
    request: Request,
    city: str = "Riyadh",
    _key: str = Depends(require_api_key),
):
    # Validate city exists
    if city not in app.state.city_dfs:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found.")

    # Fetch weather data – ensure scalars
    from src.adapters import get_adapter
    weather_adapter = get_adapter('weather')
    try:
        weather_data = weather_adapter.fetch(city)
        # Extract scalars robustly
        if hasattr(weather_data, 'iloc'):  # pandas Series/DataFrame
            air_temp = float(weather_data['temperature_celsius'].iloc[0]) if 'temperature_celsius' in weather_data else 35.0
            weather_condition = str(weather_data['weather'].iloc[0]) if 'weather' in weather_data else 'clear'
        else:  # dict
            air_temp = float(weather_data.get('temperature_celsius', 35.0))
            weather_condition = str(weather_data.get('weather', 'clear'))
    except Exception:
        air_temp = 35.0
        weather_condition = 'clear'

    df = app.state.city_dfs[city]
    zones = sorted(df['zone'].unique())
    result = {}

    for zone in zones:
        zone_rows = df[df['zone'] == zone].sort_values('timestamp')
        if len(zone_rows) == 0:
            continue
        latest = zone_rows.iloc[-1]
        road_type = latest.get('road_type', 'arterial')
        # Ensure road_type is a scalar string
        if hasattr(road_type, 'iloc'):
            road_type = road_type.iloc[0]
        road_type = str(road_type)

        risk = compute_thermal_risk(
            air_temp_celsius=air_temp,
            weather=weather_condition,
            road_type=road_type,
        )
        result[zone] = risk

    return {
        "city": city,
        "air_temp_celsius": air_temp,
        "weather": weather_condition,
        "zones": result,
    }





@app.get("/events/egress-plan", tags=["events"])
@limiter.limit("20/minute")
async def egress_plan(
    request: Request,
    venue_id: str,
    total_vehicles: int,
    current_highway_load_pct: float = 0.0,
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """
    Generate a staged egress plan for a mass event venue.
    """
    try:
        plan = calculate_egress_plan(venue_id, total_vehicles, current_highway_load_pct)
        return plan
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/events/active-surge", tags=["events"])
@limiter.limit("20/minute")
async def active_surge(
    request: Request,
    payload: dict,   # Body: {venue_id, total_vehicles, current_highway_load_pct}
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """
    Immediate egress recommendation for a surge event.
    """
    venue_id = payload.get('venue_id')
    total_vehicles = payload.get('total_vehicles')
    current_highway_load_pct = payload.get('current_highway_load_pct', 0.0)

    if not venue_id or not total_vehicles:
        raise HTTPException(status_code=400, detail="Missing venue_id or total_vehicles")

    try:
        plan = calculate_egress_plan(venue_id, total_vehicles, current_highway_load_pct)
        return plan
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))





@app.get("/vms/active-boards", tags=["vms"])
@limiter.limit("20/minute")
async def vms_active_boards(
    request: Request,
    city: str = "Riyadh",
    _key: str = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """
    Return VMS content for all zones.
    Only shows non-Low messages unless all zones are Low.
    """
    # Validate city exists
    if city not in app.state.city_dfs:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found.")

    df = app.state.city_dfs[city]
    zones = sorted(df['zone'].unique())

    results = []
    all_low = True

    for zone in zones:
        zone_rows = df[df['zone'] == zone].sort_values('timestamp')
        if len(zone_rows) == 0:
            continue

        latest = zone_rows.iloc[-1]
        score = float(latest.get('congestion_score', 0.0))
        level = congestion_level(score)
        weather = str(latest.get('weather', 'clear'))

        # Estimate delay based on congestion level
        delay_map = {'Low': 0, 'Moderate': 5, 'High': 15, 'Critical': 30}
        delay = delay_map.get(level, 0)

        msg = generate_vms_message(zone, level, weather, delay)

                # ---- Semantic validation ----
        validation = validate_vms_message(msg["lines"])
        if not validation["valid"]:
            # Log the failure (we'll print for now, but could log to a file)
            print(f"[VMS] Validation failed for zone {zone}: {validation['errors']}")
            # Fallback to a safe message
            safe_lines = ["CHECK TRAFFIC", "DRIVE SAFE", ""]
            msg = generate_vms_message(zone, "Low", "clear", 0)  # reuse generator with low congestion
            # But to be safe, manually set a fixed fallback:
            msg = {
                "lines": safe_lines,
                "char_counts": [len(l) for l in safe_lines],
                "compliant": True,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "validation_errors": validation["errors"],
                "fallback": True,
            }
        else:
            # Add validation warnings even if valid (so operators see them)
            if validation["warnings"]:
                msg["validation_warnings"] = validation["warnings"]
        # ---------------------------------

        # Track if all zones are Low
        if level != 'Low':
            all_low = False

        results.append({
            "zone": zone,
            "congestion_level": level,
            "weather": weather,
            "vms": msg,
        })

    # If all zones are Low, show all messages (including Low)
    # Otherwise, filter out Low messages
    if not all_low:
        results = [r for r in results if r["congestion_level"] != "Low"]

    # Sort by congestion level priority: Critical > High > Moderate > Low
    priority = {'Critical': 0, 'High': 1, 'Moderate': 2, 'Low': 3}
    results.sort(key=lambda x: priority.get(x["congestion_level"], 4))

    return {
        "city": city,
        "total_boards": len(results),
        "all_zones_low": all_low,
        "boards": results,
    }



@app.post("/auth/keys", tags=["auth"])
def create_api_key(
    role: str = "READ_ONLY",
    city_scope: str = "all",
    auth: Dict = Depends(role_required(['ADMIN'])),
):
    """Create a new API key with specified role and city scope. Admin only."""
    if role not in ['READ_ONLY', 'OPERATOR', 'ADMIN']:
        raise HTTPException(status_code=422, detail=f"Invalid role: {role}")
    plain_key = create_key(role, city_scope)
    return {"api_key": plain_key, "role": role, "city_scope": city_scope}

@app.delete("/auth/keys", tags=["auth"])
def delete_api_key(
    key: str,
    auth: Dict = Depends(role_required(['ADMIN'])),
):
    """Deactivate an existing API key. Admin only."""
    if deactivate_key(key):
        return {"status": "deactivated"}
    else:
        raise HTTPException(status_code=404, detail="Key not found or already inactive")




# ── Admin key management endpoints ───────────────────
from src.pipeline import (
    add_key_to_registry, revoke_key_from_registry, list_registry_keys
)


class AdminKeyRequest(BaseModel):
    city: str = Field("Riyadh", description="City scope for the key")
    role: str = Field("OPERATOR", description="OPERATOR or ADMIN")


@app.post("/admin/keys", tags=["admin"])
def admin_create_key(
    body: AdminKeyRequest,
    auth: Dict = Depends(require_admin),
):
    """
    Create a new API key. Returns the full key once — store it immediately.
    ADMIN role required.
    """
    if body.role.upper() not in ("OPERATOR", "ADMIN"):
        raise HTTPException(status_code=400, detail="role must be OPERATOR or ADMIN")
    new_key = add_key_to_registry(city=body.city, role=body.role.upper())
    return {
        "api_key":  new_key,
        "city":     body.city,
        "role":     body.role.upper(),
        "warning":  "Store this key now. It will not be shown again.",
    }


@app.delete("/admin/keys/{key_prefix}", tags=["admin"])
def admin_revoke_key(
    key_prefix: str,
    auth: Dict = Depends(require_admin),
):
    """
    Revoke a key by its first 8 characters.
    ADMIN role required.
    """
    revoked = revoke_key_from_registry(key_prefix)
    if not revoked:
        raise HTTPException(status_code=404, detail="Key not found or already revoked.")
    return {"revoked": True, "key_prefix": key_prefix}


@app.get("/admin/keys", tags=["admin"])
def admin_list_keys(
    auth: Dict = Depends(require_admin),
):
    """
    List all keys — masked to first 8 chars only.
    ADMIN role required.
    """
    return {"keys": list_registry_keys()}






@app.post("/auth/rotate", tags=["auth"])
def rotate_api_key(
    key: str,
    auth: Dict = Depends(role_required(['ADMIN'])),
):
    """Rotate an existing key (generate new one, deactivate old). Admin only."""
    new_key = rotate_key(key)
    if new_key:
        return {"new_api_key": new_key}
    else:
        raise HTTPException(status_code=404, detail="Key not found or invalid")






# ===== Tamper-Evident Violation Audit Ledger =====

@app.get("/citations/verify-ledger", tags=["citations"])
async def verify_ledger(auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN']))):
    """
    Verify the integrity of the violation ledger.
    Requires OPERATOR or ADMIN role.
    """
    ledger = ViolationLedger()
    report = ledger.verify_chain()
    return report


@app.get("/ledger/verify", tags=["citations"])
async def ledger_verify(auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN']))):
    """
    PROMPT 068 — on-demand ledger chain verification at its own
    /ledger/verify path. Functionally identical to /citations/verify-ledger
    (kept unchanged above for backward compatibility with existing tests
    and clients) but returns verify_ledger_chain()'s PROMPT 068 key names
    (valid, total_rows, first_break_at_row) instead of the legacy
    (valid, total_blocks, first_invalid_block) shape. Role requirement
    matches /citations/verify-ledger: PROMPT 067's endpoint-sensitivity
    audit did not introduce a separate AUDITOR role, so this stays on the
    existing OPERATOR/ADMIN set rather than inventing one ad hoc here.
    """
    return verify_ledger_chain()


@app.get("/citations/violations", tags=["citations"])
async def get_violations(
    zone: Optional[str] = None,
    limit: int = 100,
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """
    Return recent violation records, optionally filtered by zone.
    Returns at most `limit` records (default 100), ordered by block number descending.
    """
    ledger = ViolationLedger()
    if not os.path.exists(ledger.path) or os.path.getsize(ledger.path) == 0:
        return {"violations": []}

    with open(ledger.path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Filter by zone if provided
    if zone:
        rows = [r for r in rows if r['zone'] == zone]

    # Sort descending by block_number (most recent first)
    rows.sort(key=lambda r: int(r['block_number']), reverse=True)

    # Limit
    rows = rows[:limit]

    return {"violations": rows}





class TelemetryReading(BaseModel):
    city: str = Field("Riyadh", description="City name")
    zone: str = Field("Zone_1", description="Zone identifier")
    hour: int = Field(..., ge=0, le=23, description="Hour of day")
    vehicle_count: float = Field(..., gt=0, description="Number of vehicles")
    avg_speed: float = Field(..., gt=0, description="Average speed (km/h)")
    weather: str = Field("clear", description="Weather condition")
    road_type: str = Field("arterial", description="Road type")
    rush_hour: int = Field(0, ge=0, le=1, description="Is rush hour?")
    is_weekend: int = Field(0, ge=0, le=1, description="Is weekend?")
    is_late_night: int = Field(0, ge=0, le=1, description="Is late night?")
    event: int = Field(0, ge=0, le=1, description="Event flag")
    hour_multiplier: float = Field(1.0, gt=0, description="Hourly traffic multiplier")

class TelemetryIngestRequest(BaseModel):
    readings: List[TelemetryReading] = Field(..., max_length=1000, description="List of sensor readings")

@app.post("/telemetry/ingest", tags=["telemetry"])
@limiter.limit("60/minute")
async def telemetry_ingest(
    request: Request,
    payload: TelemetryIngestRequest,
    auth: Dict = Depends(require_api_key),
):
    """
    Ingest a batch of sensor readings asynchronously.
    Each reading is enqueued for background processing.
    Returns counts of enqueued and dropped readings, and current queue depth.
    """
    telemetry_queue = getattr(app.state, 'telemetry_queue', None)
    if telemetry_queue is None:
        raise HTTPException(status_code=503, detail="Telemetry queue not initialized")

    enqueued = 0
    dropped = 0
    for reading in payload.readings:
        # Convert to dict
        rd = reading.dict()
        if telemetry_queue.enqueue(rd):
            enqueued += 1
        else:
            dropped += 1

    return {
        "enqueued": enqueued,
        "dropped": dropped,
        "queue_depth": telemetry_queue.queue_depth(),
        "status": "ok"
    }

@app.get("/telemetry/status", tags=["telemetry"])
async def telemetry_status(
    auth: Dict = Depends(require_api_key),
):
    """
    Return the current status of the telemetry queue and worker.
    """
    telemetry_queue = getattr(app.state, 'telemetry_queue', None)
    if telemetry_queue is None:
        raise HTTPException(status_code=503, detail="Telemetry queue not initialized")
    
    QUEUE_DEPTH_GAUGE.set(telemetry_queue.queue_depth())

    return {
        "queue_depth": telemetry_queue.queue_depth(),
        "worker_active": telemetry_queue.is_worker_active(),
        "processed_today": telemetry_queue.processed_today(),
        "queue_max_size": TELEMETRY_QUEUE_MAX_SIZE,
        "batch_size": TELEMETRY_BATCH_SIZE,
        "flush_interval_s": TELEMETRY_FLUSH_INTERVAL_S,
    }




# ===== Parking Occupancy Prediction =====

@app.get("/parking/occupancy-forecast", tags=["parking"])
@limiter.limit("20/minute")
async def parking_occupancy_forecast(
    request: Request,
    city: str = "Riyadh",
    auth: Dict = Depends(require_api_key),
):
    """
    Return 3‑hour parking occupancy forecast for all garages in the city.

    Uses the latest congestion score for each garage's zone.
    """
    _assert_city_permitted(auth, city)

    df = app.state.city_dfs.get(city, app.state.df)
    if df is None:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found.")

    # Get the latest row per zone
    latest = df.sort_values('timestamp').groupby('zone').last().reset_index()

    results = []
    for garage_id, info in PARKING_HUBS.items():
        zone = info['zone']
        zone_row = latest[latest['zone'] == zone]
        if zone_row.empty:
            # fallback: use city-wide average
            congestion = float(df['congestion_score'].mean())
            hour = datetime.now().hour
        else:
            congestion = float(zone_row.iloc[0]['congestion_score'])
            hour = int(zone_row.iloc[0]['hour'])

        # Simulate current fill rate based on congestion (0.3–0.9)
        # We'll set current_fill_rate = 0.3 + congestion * 0.6
        current_fill = 0.3 + congestion * 0.6
        current_fill = min(current_fill, 0.95)

        forecast = predict_parking_occupancy(
            garage_id=garage_id,
            current_fill_rate=current_fill,
            congestion_score=congestion,
            hour=hour,
        )
        forecast['zone'] = zone
        forecast['capacity'] = info['capacity']
        results.append(forecast)

    # Sort by current fill rate descending (most full first)
    results.sort(key=lambda x: x['current_fill_rate'], reverse=True)

    return {
        "city": city,
        "timestamp": datetime.now().isoformat(),
        "garages": results,
    }


@app.get("/parking/routing-recommendation", tags=["parking"])
@limiter.limit("20/minute")
async def parking_routing_recommendation(
    request: Request,
    zone: str,
    city: str = "Riyadh",
    auth: Dict = Depends(require_api_key),
):
    """
    Return the garage with the most available capacity near the requested zone.

    Considers garages whose 'zone' matches the requested zone first.
    If no garage exists in that zone, returns the garage with lowest occupancy.
    """
    _assert_city_permitted(auth, city)

    df = app.state.city_dfs.get(city, app.state.df)
    if df is None:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found.")

    # Get latest row per zone
    latest = df.sort_values('timestamp').groupby('zone').last().reset_index()

    # Build list of garages with current fill rate
    garage_data = []
    for garage_id, info in PARKING_HUBS.items():
        g_zone = info['zone']
        zone_row = latest[latest['zone'] == g_zone]
        if zone_row.empty:
            congestion = float(df['congestion_score'].mean())
        else:
            congestion = float(zone_row.iloc[0]['congestion_score'])
        current_fill = 0.3 + congestion * 0.6
        current_fill = min(current_fill, 0.95)
        garage_data.append({
            'garage_id': garage_id,
            'zone': g_zone,
            'current_fill': current_fill,
            'capacity': info['capacity'],
            'available': 1.0 - current_fill,
        })

    # First, filter by zone if any garage matches
    zone_garages = [g for g in garage_data if g['zone'] == zone]
    if zone_garages:
        # Pick the one with most available capacity
        best = max(zone_garages, key=lambda x: x['available'])
    else:
        # No garage in that zone; pick the overall least full
        best = min(garage_data, key=lambda x: x['current_fill'])

    return {
        "city": city,
        "requested_zone": zone,
        "recommended_garage": best['garage_id'],
        "garage_zone": best['zone'],
        "current_fill_rate": round(best['current_fill'], 3),
        "available_capacity": round(best['available'] * best['capacity']),
        "capacity": best['capacity'],
    }




# ===== Edge Failover Simulation =====



# ===== Edge Failover Simulation =====

@app.get("/edge/cabinet-status", tags=["edge"])
async def edge_cabinet_status(
    city: str = "Riyadh",
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """Return simulated status of all edge controllers in the city."""
    cabinets = getattr(app.state, 'edge_cabinets', {})
    statuses = []
    for zone, cabinet in cabinets.items():
        status = cabinet.get_status()
        status['zone'] = zone
        statuses.append(status)

    return {
        "city": city,
        "total_cabinets": len(statuses),
        "cabinets": statuses,
    }


class EdgeSimulationRequest(BaseModel):
    action: str = Field(..., description="One of: go_offline, restore, status")
    zone_id: str = Field(..., description="Zone identifier (e.g., Zone_1)")
    neighbor_queues: Optional[Dict[str, int]] = Field(None, description="Neighbor zone -> queue length")


@app.post("/edge/simulation", tags=["edge"])
async def edge_simulation(
    payload: EdgeSimulationRequest,
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """Simulate edge controller failover actions."""
    cabinets = getattr(app.state, 'edge_cabinets', {})
    cabinet = cabinets.get(payload.zone_id)
    if cabinet is None:
        raise HTTPException(status_code=404, detail=f"Unknown zone_id: {payload.zone_id}")

    response = {
        "zone_id": payload.zone_id,
        "action": payload.action,
    }

    if payload.action == "go_offline":
        result = cabinet.simulate_heartbeat_loss()
        response["result"] = result
    elif payload.action == "restore":
        result = cabinet.restore_heartbeat()
        response["result"] = result
    elif payload.action == "status":
        response["result"] = cabinet.get_status()
    else:
        raise HTTPException(status_code=422, detail="Invalid action. Use: go_offline, restore, status")

    if payload.neighbor_queues is not None:
        p2p = cabinet.compute_p2p_coordination(payload.neighbor_queues)
        response["p2p_coordination"] = p2p

    return response




@app.get("/pipeline/hpo-history", tags=["pipeline"])
async def hpo_history(
    limit: int = 10,
    auth: Dict = Depends(require_admin),
):
    """
    Return the last N HPO runs from the Optuna SQLite database.
    Admin only.
    """
    import optuna
    from src.config import HPO_DB_PATH

    if not os.path.exists(HPO_DB_PATH):
        return {"hpo_runs": [], "total": 0}

    storage = f"sqlite:///{HPO_DB_PATH}"
    try:
        study = optuna.load_study(storage=storage, study_name=None)  # loads the latest study? Actually we need to list studies.
        # We need to get all studies. Better: use optuna.study.get_all_study_summaries
        summaries = optuna.get_all_study_summaries(storage)
        # Sort by start time descending
        summaries_sorted = sorted(summaries, key=lambda s: s.start_time, reverse=True)
        # Take limit
        summaries_sorted = summaries_sorted[:limit]
        results = []
        for s in summaries_sorted:
            results.append({
                "study_name": s.study_name,
                "n_trials": s.n_trials,
                "best_trial": {
                    "value": s.best_trial.value,
                    "params": s.best_trial.params,
                },
                "start_time": s.start_time.isoformat() if s.start_time else None,
            })
        return {"hpo_runs": results, "total": len(summaries)}
    except Exception as e:
        # If no study exists, return empty
        return {"hpo_runs": [], "total": 0, "error": str(e)}





# ===== Pareto-Optimal Multi-Criteria Routing =====

class ParetoRouteRequest(BaseModel):
    city: str = Field("Riyadh")
    origin_zone: str = Field(..., description="Starting zone")
    destination_zone: str = Field(..., description="Destination zone")
    time_weight: Optional[float] = Field(None, ge=0, le=1)
    emission_weight: Optional[float] = Field(None, ge=0, le=1)
    cost_weight: Optional[float] = Field(None, ge=0, le=1)
    emissions_weight: float = Field(
        EMISSIONS_ROUTING_WEIGHT, ge=0,
        description="PROMPT 079: penalises routes through zones with high aggregate CO2. Opt-in, default 0.0.",
    )

@app.post("/routing/pareto-recommendations", tags=["routing"])
@limiter.limit("20/minute")
async def pareto_recommendations(
    request: Request,
    payload: ParetoRouteRequest,
    auth: Dict = Depends(require_api_key),
):
    _assert_city_permitted(auth, payload.city)

    df = app.state.city_dfs.get(payload.city, app.state.df)
    if df is None:
        raise HTTPException(status_code=404, detail=f"City '{payload.city}' not found.")

    latest = df.sort_values('timestamp').groupby('zone').last().reset_index()
    congestion_map = {
        str(row['zone']): float(row['congestion_score'])
        for _, row in latest.iterrows()
    }

    if payload.origin_zone not in congestion_map:
        raise HTTPException(status_code=422, detail=f"Unknown origin_zone: {payload.origin_zone}")
    if payload.destination_zone not in congestion_map:
        raise HTTPException(status_code=422, detail=f"Unknown destination_zone: {payload.destination_zone}")

    weights = {}
    if payload.time_weight is not None:
        weights['time_weight'] = payload.time_weight
    if payload.emission_weight is not None:
        weights['emission_weight'] = payload.emission_weight
    if payload.cost_weight is not None:
        weights['cost_weight'] = payload.cost_weight

    if weights:
        total = sum(weights.values())
        if total != 0:
            weights = {k: v/total for k, v in weights.items()}

    zone_emissions_map = None
    if payload.emissions_weight > 0:
        from src.model import compute_equity_summary
        equity = compute_equity_summary(city=payload.city, days=7)
        zone_emissions_map = {
            z['zone']: z['total_co2_kg'] for z in equity.get('zones', [])
        }

    result = calculate_pareto_routes(
        origin_zone=payload.origin_zone,
        destination_zone=payload.destination_zone,
        congestion_map=congestion_map,
        weights=weights if weights else None,
        zone_emissions_map=zone_emissions_map,
        emissions_weight=payload.emissions_weight,
    )
    result['city'] = payload.city
    return result






# ===== Air Quality Index =====

@app.get("/environment/air-quality", tags=["environment"])
@limiter.limit("20/minute")
async def air_quality(
    request: Request,
    city: str = "Riyadh",
    auth: Dict = Depends(require_api_key),
):
    """
    Estimate PM2.5 and NOx concentrations per zone.
    Uses live wind speed from WeatherAdapter and current traffic data.
    """
    _assert_city_permitted(auth, city)

    df = app.state.city_dfs.get(city, app.state.df)
    if df is None:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found.")

    # Fetch wind speed from WeatherAdapter
    try:
        weather_df = get_adapter("weather").fetch(city)
        wind_speed = float(weather_df.get('wind_speed', 10.0))
        weather_condition = str(weather_df.get('weather', 'clear'))
    except Exception:
        wind_speed = 10.0
        weather_condition = 'clear'

    # Get latest row per zone
    latest = df.sort_values('timestamp').groupby('zone').last().reset_index()

    results = []
    for _, row in latest.iterrows():
        vc = float(row.get('vehicle_count', 100))
        avg_speed = float(row.get('avg_speed', 60))
        weather = str(row.get('weather', weather_condition))

        aq = estimate_air_quality(
            vehicle_count=vc,
            avg_speed=avg_speed,
            wind_speed_kmh=wind_speed,
            weather=weather,
        )
        aq['zone'] = str(row['zone'])
        results.append(aq)

    # Sort worst to best by PM2.5 concentration
    results.sort(key=lambda x: x['pm25_concentration'], reverse=True)

    return {
        "city": city,
        "wind_speed_kmh": round(wind_speed, 1),
        "weather": weather_condition,
        "zones": results,
    }




# ===== Freight Geofencing =====

class FreightValidationRequest(BaseModel):
    zone: str = Field(..., description="Zone identifier")
    hour: int = Field(..., ge=0, le=23, description="Hour of day")
    vehicle_weight_tonnes: float = Field(..., gt=0, description="Vehicle weight in tonnes")
    is_weekend: int = Field(0, ge=0, le=1, description="Is weekend?")
    vehicle_id_hash: str = Field(..., min_length=8, description="Hashed vehicle identifier")


@app.post("/freight/validate", tags=["freight"])
@limiter.limit("20/minute")
async def validate_freight(
    request: Request,
    payload: FreightValidationRequest,
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """
    Validate if a freight vehicle entry complies with zone restrictions.
    Returns compliance status or citation details.
    """
    result = validate_freight_entry(
        zone=payload.zone,
        hour=payload.hour,
        vehicle_weight_tonnes=payload.vehicle_weight_tonnes,
        is_weekend=payload.is_weekend,
        vehicle_id_hash=payload.vehicle_id_hash,
    )
    return result


@app.get("/citations/freight-infractions", tags=["citations"])
@limiter.limit("20/minute")
async def freight_infractions(
    request: Request,
    zone: Optional[str] = None,
    limit: int = 50,
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """
    Return recent freight violations from the audit ledger.
    Filters by zone if provided, sorted newest first.
    """
    ledger = ViolationLedger()
    if not os.path.exists(ledger.path) or os.path.getsize(ledger.path) == 0:
        return {"infractions": [], "total": 0}

    with open(ledger.path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if zone:
        rows = [r for r in rows if r['zone'] == zone]

    rows.sort(key=lambda r: int(r['block_number']), reverse=True)
    rows = rows[:limit]

    return {"infractions": rows, "total": len(rows)}





# =====  Evacuation Routing =====

class EvacuationRequest(BaseModel):
    city: str = Field("Riyadh")
    hazard_zones: List[str] = Field(..., description="List of zone IDs to evacuate")
    total_vehicles: int = Field(..., gt=0, description="Total number of vehicles fleeing")
EvacuationRequest.model_rebuild()

@app.post("/emergency/evacuate", tags=["emergency"])
@limiter.limit("10/minute")
async def emergency_evacuate(
    request: Request,
    payload: EvacuationRequest,
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """
    Generate capacity‑aware evacuation routes for multiple hazard zones.

    Requires OPERATOR or ADMIN role.
    Returns a plan with allocations, routes, clearance times, and corridor overload flags.
    """
    _assert_city_permitted(auth, payload.city)

    # Build congestion map from latest data
    df = app.state.city_dfs.get(payload.city)
    if df is None:
        raise HTTPException(status_code=404, detail=f"City '{payload.city}' not found.")

    latest = df.sort_values('timestamp').groupby('zone').last().reset_index()
    congestion_map = {str(row['zone']): float(row['congestion_score']) for _, row in latest.iterrows()}

    # Validate hazard zones exist
    for zone in payload.hazard_zones:
        if zone not in congestion_map:
            raise HTTPException(status_code=422, detail=f"Unknown hazard zone: {zone}")

    try:
        plan = calculate_evacuation_routes(
            hazard_zones=payload.hazard_zones,
            total_vehicles=payload.total_vehicles,
            congestion_map=congestion_map,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    plan['city'] = payload.city
    return plan




@app.get(METRICS_ENDPOINT, tags=["monitoring"])
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)




# ===== Demand-Responsive Transit (DRT) =====

@app.get("/transit/drt-status", tags=["transit"])
@limiter.limit("20/minute")
async def drt_status(
    request: Request,
    city: str = "Riyadh",
    auth: Dict = Depends(role_required(['OPERATOR', 'ADMIN'])),
):
    """
    Return simulated DRT availability and queue status.
    """
    _assert_city_permitted(auth, city)

    df = app.state.city_dfs.get(city)
    if df is None:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found.")

    avg_congestion = float(df['congestion_score'].mean())
    available = max(1, int(10 - avg_congestion * 8))

    queue_status = {}
    for zone in DRT_ELIGIBLE_ZONES:
        zone_df = df[df['zone'] == zone]
        if not zone_df.empty:
            vc = float(zone_df['vehicle_count'].mean())
            q = int(vc * 0.05 + 2)
        else:
            q = 0
        queue_status[zone] = {'queue_length': q, 'estimated_wait_mins': min(5 + q, DRT_MAX_WAIT_MINS)}

    return {
        "city": city,
        "available_shuttles": available,
        "eligible_zones": DRT_ELIGIBLE_ZONES,
        "queue_status": queue_status,
        "shuttle_capacity": DRT_SHUTTLE_CAPACITY,
    }


class DRTRequest(BaseModel):
    origin_zone: str = Field(..., description="Pickup zone")
    destination_zone: str = Field(..., description="Dropoff zone")
    passenger_count: int = Field(1, ge=1, le=DRT_SHUTTLE_CAPACITY)
    city: str = Field("Riyadh")


@app.post("/transit/request-shuttle", tags=["transit"])
@limiter.limit("20/minute")
async def request_shuttle(
    request: Request,
    payload: DRTRequest,
    auth: Dict = Depends(require_api_key),
):
    """
    Request a DRT shuttle. The allocator groups requests with similar destinations.
    """
    _assert_city_permitted(auth, payload.city)

    df = app.state.city_dfs.get(payload.city)
    if df is None:
        raise HTTPException(status_code=404, detail=f"City '{payload.city}' not found.")

    zones = set(df['zone'].unique())
    if payload.origin_zone not in zones:
        raise HTTPException(status_code=422, detail=f"Unknown origin_zone: {payload.origin_zone}")
    if payload.destination_zone not in zones:
        raise HTTPException(status_code=422, detail=f"Unknown destination_zone: {payload.destination_zone}")

    # ---- Initialise state attributes if missing ----
    if not hasattr(app.state, 'drt_pending_requests'):
        app.state.drt_pending_requests = []
    if not hasattr(app.state, 'last_drt_allocation'):
        app.state.last_drt_allocation = {}

    # ---- Add request to pending queue ----
    app.state.drt_pending_requests.append({
        'origin_zone': payload.origin_zone,
        'destination_zone': payload.destination_zone,
        'passengers': payload.passenger_count,
    })

    # ---- Compute available shuttles ----
    avg_congestion = float(df['congestion_score'].mean())
    available = max(1, int(10 - avg_congestion * 8))

    # ---- Build congestion map ----
    latest = df.sort_values('timestamp').groupby('zone').last().reset_index()
    congestion_map = {str(row['zone']): float(row['congestion_score']) for _, row in latest.iterrows()}

    # ---- Allocate – this defines `result` ----
    allocator = DRTAllocator()
    result = allocator.allocate(
        requests=app.state.drt_pending_requests,
        available_shuttles=available,
        congestion_map=congestion_map,
    )

    # ---- Store result (now defined) ----
    app.state.last_drt_allocation[payload.city] = result

    # ---- Clear pending requests ----
    app.state.drt_pending_requests = []

    return {
        "city": payload.city,
        **result,
    }

@app.get("/equity/summary", tags=["equity"])
@limiter.limit("20/minute")
async def equity_summary(
    request: Request,
    city: str = "Riyadh",
    days: int = 30,
    auth: Dict = Depends(require_admin),
):
    """
    Return a per-zone equity summary for toll revenue, CO2 emissions,
    and freight citations over the trailing N days.

    Includes a correlational emissions-delta flag for Pareto-optimal routes.
    """
    from src.model import compute_equity_summary
    result = compute_equity_summary(city=city, days=days)
    return result





@app.get("/incidents/active", tags=["incidents"])
@limiter.limit("20/minute")
def incidents_active(
    request: Request,
    city: str = "Riyadh",
    auth: Dict = Depends(role_required(["OPERATOR", "ADMIN"])),
):
    """
    Return all currently detected incidents across all zones for a city,
    sorted by severity descending (Critical first).
 
    Runs detect_incidents() live against the latest city DataFrame —
    no caching, always reflects current conditions.
 
    Each incident entry includes: zone, severity, speed_drop_pct,
    volume_change_pct, confidence, recommended_action, clearance_mins,
    and timestamp.
 
    Returns an empty list (not 404) when no incidents are detected.
    Rate limit: 20 req/min per IP. Role: OPERATOR or ADMIN.
    """
    _assert_city_permitted(auth, city)
 
    df = app.state.city_dfs.get(city, app.state.df)
    zones = df["zone"].unique() if "zone" in df.columns else []
 
    active = []
    for zone in zones:
        result = detect_incidents(df, zone=zone, city=city, log=True)
        if result["incident_detected"]:
            active.append(result)
 
    # Sort Critical → Major → Moderate → Minor
    active.sort(
        key=lambda x: _SEVERITY_ORDER.get(x.get("severity", "Minor"), 0),
        reverse=True,
    )
 
    return {
        "city": city,
        "total_incidents": len(active),
        "incidents": active,
        "timestamp": datetime.now().isoformat(),
    }
 
 
@app.get("/incidents/history", tags=["incidents"])
@limiter.limit("20/minute")
def incidents_history(
    request: Request,
    city: str = "Riyadh",
    hours: int = 24,
    zone: Optional[str] = None,
    auth: Dict = Depends(role_required(["OPERATOR", "ADMIN"])),
):
    """
    Return historical incidents from incidents_log.csv for the past N hours.
 
    Filters by city (required) and optionally by zone. Results are sorted
    newest first. Returns an empty list when the log doesn't exist yet.
 
    Parameters:
      city  — Target city (default Riyadh).
      hours — Look-back window in hours (default 24).
      zone  — Optional zone filter (e.g. Zone_1).
 
    Rate limit: 20 req/min per IP. Role: OPERATOR or ADMIN.
    """
    _assert_city_permitted(auth, city)
 
    log_path = INCIDENTS_LOG_PATH
 
    if not os.path.exists(log_path):
        return {
            "city": city,
            "hours": hours,
            "zone_filter": zone,
            "total_incidents": 0,
            "incidents": [],
            "note": "No incidents logged yet.",
        }
 
    log_df = pd.read_csv(log_path)
 
    # --- Time filter ---
    if "timestamp" in log_df.columns:
        log_df["timestamp"] = pd.to_datetime(log_df["timestamp"], errors="coerce")
        cutoff = pd.Timestamp.now() - pd.Timedelta(hours=hours)
        log_df = log_df[log_df["timestamp"] >= cutoff]
 
    # --- City filter ---
    if "city" in log_df.columns:
        log_df = log_df[log_df["city"] == city]
 
    # --- Zone filter (optional) ---
    if zone and "zone" in log_df.columns:
        log_df = log_df[log_df["zone"] == zone]
 
    # Newest first
    if "timestamp" in log_df.columns:
        log_df = log_df.sort_values("timestamp", ascending=False)
 
    records = log_df.to_dict(orient="records")
    # Convert Timestamp objects to strings for JSON serialisation
    for r in records:
        if hasattr(r.get("timestamp"), "isoformat"):
            r["timestamp"] = r["timestamp"].isoformat()
 
    return {
        "city": city,
        "hours": hours,
        "zone_filter": zone,
        "total_incidents": len(records),
        "incidents": records,
    }












# ---------------------------------------------------------------------------
# WebSocket — real-time zone congestion streaming
# ---------------------------------------------------------------------------

from fastapi import WebSocket, WebSocketDisconnect
import asyncio

@app.websocket("/ws/live/{city}")
async def ws_live(websocket: WebSocket, city: str, api_key: str = ""):
    # --- Auth ---
    auth_info = _resolve_api_key(api_key)
    if not auth_info:
        await websocket.close(code=1008)
        return

    if auth_info['role'].upper() not in ['OPERATOR', 'ADMIN']:
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


def _resolve_api_key(key: str) -> Optional[Dict]:
    """
    Validate a raw key string against the configured key registry,
    the SQLite auth DB, or the master API_KEY.

    Returns the auth info dict {key, role, city_scope} if valid,
    otherwise None.
    """
    if not key:
        return None

    # 1. Multi-tenant registry (from lifespan)
    if hasattr(app.state, "key_registry") and app.state.key_registry:
        if key in app.state.key_registry:
            return {
                'key': key,
                'role': app.state.key_registry[key].get('role', 'READ_ONLY'),
                'city_scope': app.state.key_registry[key].get('city_scope', '*')
            }

    # 2. SQLite auth.db (via validate_key)
    auth_info = validate_key(key)
    if auth_info:
        return {
            'key': key,
            'role': auth_info['role'],
            'city_scope': auth_info['city_scope']
        }

    # 3. Single master key fallback
    if key == API_KEY:
        return {
            'key': key,
            'role': 'ADMIN',
            'city_scope': '*'
        }

    return None


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
    



