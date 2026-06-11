from typing import Dict
import os
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.metrics import mean_absolute_error


LOG_PATH      = "predictions_log.csv"
MODEL_PATH    = "model.joblib"
PIPELINE_LOG  = "pipeline_log.csv"
DRIFT_WINDOW  = 500   # number of recent predictions to evaluate
DRIFT_THRESHOLD = 1.3  # retrain if recent MAE is 1.3x the baseline


def compute_drift_score(log_path: str = LOG_PATH) -> float:
    """
    Compare recent prediction MAE against a naive baseline.

    Baseline: predict the mean congestion_score for every row.
    Drift ratio: 1.0 = no drift, 1.3+ = retrain threshold reached.

    Returns 1.0 if the log has fewer than 10 rows — not enough data.
    """
    if not os.path.exists(log_path):
        return 1.0

    df = pd.read_csv(log_path)

    if len(df) < 10:
        return 1.0

    df = df.tail(DRIFT_WINDOW).copy()

    if "congestion_score" not in df.columns:
        return 1.0

    scores = df["congestion_score"].dropna()

    if len(scores) < 10:
        return 1.0

    baseline_pred = np.full(len(scores), scores.mean())
    baseline_mae  = mean_absolute_error(scores, baseline_pred)

    rolling_pred  = scores.shift(1).fillna(scores.mean())
    recent_mae    = mean_absolute_error(scores, rolling_pred)

    if baseline_mae == 0:
        return 1.0

    return round(float(recent_mae / baseline_mae), 4)


def should_retrain(drift_score: float, threshold: float = DRIFT_THRESHOLD) -> bool:
    """Return True when drift has exceeded the acceptable threshold."""
    return drift_score >= threshold


def retrain_model(city: str = "Riyadh") -> dict:
    """
    Regenerate data, retrain XGBoost, and save the new model to disk.

    Returns
    -------
    dict with keys: retrained, new_r2, old_r2, timestamp, model_path
    """
    from sklearn.metrics import r2_score
    from src.data  import generate_traffic_data, apply_hourly_patterns, add_lag_features
    from src.model import prepare_features, train_xgboost

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    old_r2 = _load_saved_r2()

    df = generate_traffic_data(city=city)
    df = apply_hourly_patterns(df, city=city)
    df = add_lag_features(df)

    X, y, _ = prepare_features(df)
    model, X_test, y_test = train_xgboost(X, y)

    y_pred  = model.predict(X_test)
    new_r2  = round(float(r2_score(y_test, y_pred)), 4)

    joblib.dump({"model": model, "r2": new_r2, "timestamp": timestamp}, MODEL_PATH)
    print(f"[Pipeline] Model saved to {MODEL_PATH} — R²: {new_r2}")

    return {
        "retrained"  : True,
        "new_r2"     : new_r2,
        "old_r2"     : old_r2,
        "timestamp"  : timestamp,
        "model_path" : MODEL_PATH,
    }


def run_pipeline(city: str = "Riyadh") -> dict:
    """
    Full pipeline: check drift → retrain if needed → log outcome.

    Always logs to pipeline_log.csv regardless of whether retrain ran.
    """
    timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    drift_score = compute_drift_score()
    retrained   = False
    new_r2      = None
    old_r2      = None

    if should_retrain(drift_score):
        print(f"[Pipeline] Drift score {drift_score} >= {DRIFT_THRESHOLD}. Retraining...")
        result  = retrain_model(city=city)
        retrained = result["retrained"]
        new_r2    = result["new_r2"]
        old_r2    = result["old_r2"]
    else:
        print(f"[Pipeline] Drift score {drift_score} — model stable. No retrain needed.")

    outcome = {
        "timestamp"  : timestamp,
        "city"       : city,
        "drift_score": drift_score,
        "retrained"  : retrained,
        "new_r2"     : new_r2,
        "old_r2"     : old_r2,
    }

    _log_pipeline_run(outcome)
    return outcome


def _load_saved_r2() -> float:
    """Load R² from the saved model file. Returns 0.0 if no model exists."""
    if not os.path.exists(MODEL_PATH):
        return 0.0
    try:
        saved = joblib.load(MODEL_PATH)
        return float(saved.get("r2", 0.0))
    except Exception:
        return 0.0


def _log_pipeline_run(outcome: dict) -> None:
    """Append one row to pipeline_log.csv."""
    log_df       = pd.DataFrame([outcome])
    write_header = not os.path.exists(PIPELINE_LOG)
    log_df.to_csv(PIPELINE_LOG, mode="a", header=write_header, index=False)



def check_thresholds(df: pd.DataFrame, city: str = 'Riyadh') -> list:
    """
    Evaluate all zones against alert thresholds and return triggered alerts.

    Checks congestion_score, anomaly_ratio, and accident risk score.
    Returns an empty list when all zones are within normal bounds.

    Parameters
    ----------
    df   : Full city DataFrame from app.state.city_dfs.
    city : City name for alert payload context.

    Returns
    -------
    list of dicts, one per triggered alert: zone, metric, value, threshold.
    """
    from src.model import detect_anomalies, compute_accident_risk, congestion_level
    from src.config import ALERT_THRESHOLDS

    alerts  = []
    zone_df = detect_anomalies(df)

    for zone in df['zone'].unique():
        z = zone_df[zone_df['zone'] == zone]
        if z.empty:
            continue

        latest = z.iloc[-1]

        congestion_score = float(latest.get('congestion_score', 0))
        if congestion_score >= ALERT_THRESHOLDS['congestion_critical']:
            alerts.append({
                'zone'     : zone,
                'city'     : city,
                'metric'   : 'congestion_score',
                'value'    : round(congestion_score, 4),
                'threshold': ALERT_THRESHOLDS['congestion_critical'],
                'severity' : 'Critical',
            })

        anomaly_ratio = float(latest.get('anomaly_ratio', 0) or 0)
        if anomaly_ratio >= ALERT_THRESHOLDS['anomaly_ratio']:
            alerts.append({
                'zone'     : zone,
                'city'     : city,
                'metric'   : 'anomaly_ratio',
                'value'    : round(anomaly_ratio, 2),
                'threshold': ALERT_THRESHOLDS['anomaly_ratio'],
                'severity' : 'Anomalous',
            })

        weather   = str(latest.get('weather', 'clear'))
        hour      = int(latest.get('hour', 0))
        is_weekend= int(latest.get('is_weekend', 0))
        rush_hour = int(latest.get('rush_hour', 0))

        risk = compute_accident_risk(
            congestion_score = congestion_score,
            weather          = weather,
            hour             = hour,
            is_weekend       = is_weekend,
            rush_hour        = rush_hour,
        )
        if risk['risk_score'] >= ALERT_THRESHOLDS['risk_critical']:
            alerts.append({
                'zone'     : zone,
                'city'     : city,
                'metric'   : 'accident_risk_score',
                'value'    : risk['risk_score'],
                'threshold': ALERT_THRESHOLDS['risk_critical'],
                'severity' : risk['risk_level'],
            })

    return alerts


def deliver_webhook_alert(alerts: list, webhook_url: str) -> bool:
    """
    POST alert payload to a webhook URL.

    Fails silently if WEBHOOK_URL is not set or the request fails.
    The payload is a JSON object with timestamp, city (from first alert),
    and the full alerts list.

    Parameters
    ----------
    alerts      : List returned by check_thresholds().
    webhook_url : Target URL from WEBHOOK_URL env var.

    Returns
    -------
    True if delivery succeeded, False otherwise.
    """
    import requests as req

    if not webhook_url or not alerts:
        return False

    payload = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'city'     : alerts[0].get('city', 'Unknown'),
        'alerts'   : alerts,
    }

    try:
        response = req.post(webhook_url, json=payload, timeout=10)
        response.raise_for_status()
        print(f"[Alert] Webhook delivered — {len(alerts)} alert(s) sent.")
        return True
    except Exception as e:
        print(f"[Alert] Webhook delivery failed: {e}")
        return False


def log_alert(alerts: list, log_path: str = 'alerts_log.csv') -> None:
    """
    Append triggered alerts to alerts_log.csv for /alerts/history queries.

    Parameters
    ----------
    alerts   : List returned by check_thresholds().
    log_path : Path to the alerts log CSV.
    """
    if not alerts:
        return

    rows = []
    for alert in alerts:
        rows.append({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'city'     : alert.get('city'),
            'zone'     : alert.get('zone'),
            'metric'   : alert.get('metric'),
            'value'    : alert.get('value'),
            'threshold': alert.get('threshold'),
            'severity' : alert.get('severity'),
        })

    log_df       = pd.DataFrame(rows)
    write_header = not os.path.exists(log_path)
    log_df.to_csv(log_path, mode='a', header=write_header, index=False)




def parse_key_registry(env_value: str) -> Dict[str, Dict]:
    """Parse API_KEYS env var into a registry dict. Format: key:city:role,key:city:role"""
    registry = {}
    if not env_value:
        return registry
    for entry in env_value.split(','):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(':')
        if len(parts) != 3:
            print(f"[KeyRegistry] Skipping malformed entry: {entry!r}")
            continue
        key, city, role = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not key:
            continue
        if role not in ('operator', 'admin'):
            role = 'operator'
        registry[key] = {'city': city, 'role': role}
    return registry


def build_key_registry() -> Dict[str, Dict]:
    """Build registry from API_KEYS. Falls back to legacy API_KEY as wildcard admin."""
    api_keys_env = os.getenv('API_KEYS', '').strip()
    if api_keys_env:
        return parse_key_registry(api_keys_env)
    legacy_key = os.getenv('API_KEY', '').strip()
    if legacy_key:
        return {legacy_key: {'city': '*', 'role': 'admin'}}
    return {}




from typing import Dict

USAGE_LOG = "usage_log.csv"


def log_api_usage(endpoint: str, method: str, key: str,
                  status: int, duration_ms: float) -> None:
    """Append one usage record to usage_log.csv. Stores only first 8 chars of key."""
    row = {
        'timestamp'       : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'endpoint'        : endpoint,
        'method'          : method,
        'api_key_hash'    : key[:8] if key else 'anonymous',
        'response_code'   : status,
        'response_time_ms': round(duration_ms, 2),
    }
    log_df       = pd.DataFrame([row])
    write_header = not os.path.exists(USAGE_LOG)
    log_df.to_csv(USAGE_LOG, mode='a', header=write_header, index=False)


def parse_key_registry(env_value: str) -> Dict[str, Dict]:
    """Parse API_KEYS env var. Format: key:city:role,key:city:role"""
    registry = {}
    if not env_value:
        return registry
    for entry in env_value.split(','):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(':')
        if len(parts) != 3:
            print(f"[KeyRegistry] Skipping malformed entry: {entry!r}")
            continue
        key, city, role = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not key:
            continue
        if role not in ('operator', 'admin'):
            role = 'operator'
        registry[key] = {'city': city, 'role': role}
    return registry


def validate_prediction_input(payload: dict) -> dict:
    """
    Validate an incoming prediction payload against plausibility ranges.

    Checks vehicle_count, avg_speed, hour_multiplier, weather, zone,
    and road_type. Returns valid (bool), warnings (list), errors (list).
    """
    from src.model import WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING

    errors   = []
    warnings = []

    vehicle_count = payload.get("vehicle_count")
    if vehicle_count is not None:
        if vehicle_count < 0 or vehicle_count > 500:
            errors.append(f"vehicle_count {vehicle_count} out of range [0, 500].")
        elif vehicle_count > 450:
            warnings.append(f"vehicle_count {vehicle_count} is unusually high (> 450).")

    avg_speed = payload.get("avg_speed")
    if avg_speed is not None:
        if avg_speed < 20 or avg_speed > 100:
            errors.append(f"avg_speed {avg_speed} out of range [20, 100].")

    hour_multiplier = payload.get("hour_multiplier")
    if hour_multiplier is not None:
        if hour_multiplier < 0.05 or hour_multiplier > 3.0:
            errors.append(f"hour_multiplier {hour_multiplier} out of range [0.05, 3.0].")

    weather = payload.get("weather")
    if weather is not None and weather not in WEATHER_ENCODING:
        errors.append(f"weather '{weather}' not in {list(WEATHER_ENCODING.keys())}.")

    zone = payload.get("zone")
    if zone is not None and zone not in ZONE_ENCODING:
        errors.append(f"zone '{zone}' not in {list(ZONE_ENCODING.keys())}.")

    road_type = payload.get("road_type")
    if road_type is not None and road_type not in ROAD_ENCODING:
        errors.append(f"road_type '{road_type}' not in {list(ROAD_ENCODING.keys())}.")

    return {
        "valid"   : len(errors) == 0,
        "warnings": warnings,
        "errors"  : errors,
    }



def compute_sla_metrics(days: int = 30) -> dict:
    """
    Compute SLA compliance metrics from usage_log.csv.

    SLA targets:
        uptime    >= 99.0%   (successful requests / total)
        avg_response < 500ms
        p95_response < 1000ms

    Returns period_days, uptime_pct, sla_uptime_met, avg_response_ms,
    p95_response_ms, p99_response_ms, sla_response_met, error_rate_pct,
    total_requests, met_all_slas.
    """
    log_path = "usage_log.csv"

    empty = {
        "period_days"      : days,
        "total_requests"   : 0,
        "uptime_pct"       : 100.0,
        "sla_uptime_met"   : True,
        "avg_response_ms"  : None,
        "p95_response_ms"  : None,
        "p99_response_ms"  : None,
        "sla_response_met" : True,
        "error_rate_pct"   : 0.0,
        "met_all_slas"     : True,
        "message"          : "No usage data yet.",
    }

    if not os.path.exists(log_path):
        return empty

    log_df = pd.read_csv(log_path)

    if "timestamp" in log_df.columns:
        log_df["timestamp"] = pd.to_datetime(log_df["timestamp"], errors="coerce")
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        log_df = log_df[log_df["timestamp"] >= cutoff]

    if log_df.empty:
        return empty

    total       = len(log_df)
    errors      = int((log_df["response_code"] >= 500).sum()) if "response_code" in log_df.columns else 0
    successes   = int((log_df["response_code"] < 400).sum()) if "response_code" in log_df.columns else total
    uptime_pct  = round(successes / total * 100, 3)
    error_pct   = round(errors / total * 100, 3)

    avg_rt = p95_rt = p99_rt = None
    if "response_time_ms" in log_df.columns:
        rt = log_df["response_time_ms"].dropna()
        if len(rt):
            avg_rt = round(float(rt.mean()), 1)
            p95_rt = round(float(rt.quantile(0.95)), 1)
            p99_rt = round(float(rt.quantile(0.99)), 1)

    sla_uptime   = uptime_pct >= 99.0
    sla_response = (avg_rt is not None and avg_rt < 500) and (p95_rt is not None and p95_rt < 1000)
    met_all      = sla_uptime and sla_response

    return {
        "period_days"      : days,
        "total_requests"   : total,
        "uptime_pct"       : uptime_pct,
        "sla_uptime_met"   : sla_uptime,
        "avg_response_ms"  : avg_rt,
        "p95_response_ms"  : p95_rt,
        "p99_response_ms"  : p99_rt,
        "sla_response_met" : sla_response,
        "error_rate_pct"   : error_pct,
        "met_all_slas"     : met_all,
    }