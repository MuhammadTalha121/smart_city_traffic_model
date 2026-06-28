from typing import Dict
import os
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.metrics import mean_absolute_error
from src.model import prepare_features, train_xgboost, optimize_hyperparameters
import xgboost as xgb
from sklearn.model_selection import train_test_split

LOG_PATH      = "predictions_log.csv"
MODEL_PATH    = "model.joblib"
MODEL_STAGING_PATH   = "model_staging.joblib"
MODEL_CHANGELOG_PATH = "MODEL_CHANGELOG.md"
PIPELINE_LOG  = "pipeline_log.csv"
DRIFT_WINDOW  = 500   # number of recent predictions to evaluate
DRIFT_THRESHOLD = 1.3  # retrain if recent MAE is 1.3x the baseline


def read_predictions_log(log_path: str = "predictions_log.csv", **read_csv_kwargs) -> pd.DataFrame:
    """
    Defensive read of predictions_log.csv. Falls back to the python
    engine with on_bad_lines='skip' if the file has rows from before a
    schema migration (see log_prediction()) — old malformed rows are
    dropped rather than crashing every caller. New writes can't drift
    again after the log_prediction() fix; this only covers files that
    already drifted on disk before that fix existed.
    """
    if not os.path.exists(log_path):
        return pd.DataFrame()
    try:
        return pd.read_csv(log_path, **read_csv_kwargs)
    except pd.errors.ParserError:
        kwargs = dict(read_csv_kwargs)
        kwargs.pop('engine', None)
        return pd.read_csv(log_path, engine='python', on_bad_lines='skip', **kwargs)


def compute_drift_score(log_path: str = LOG_PATH) -> float:
    """
    Compare recent prediction MAE against a naive baseline.

    Baseline: predict the mean congestion_score for every row.
    Drift ratio: 1.0 = no drift, 1.3+ = retrain threshold reached.

    Returns 1.0 if the log has fewer than 10 rows — not enough data.
    """
    if not os.path.exists(log_path):
        return 1.0

    df = read_predictions_log(log_path)

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


def retrain_model(city: str = "Riyadh", run_hpo: bool = False) -> dict:
    """
    Regenerate data, retrain XGBoost, and save the new model to disk.
    If run_hpo is True, run Optuna to find best hyperparameters before training.
    """
    from sklearn.metrics import r2_score
    from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features
    from src.model import prepare_features, train_xgboost, optimize_hyperparameters

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    old_r2 = _load_saved_r2()

    df = generate_traffic_data(city=city)
    df = apply_hourly_patterns(df, city=city)
    df = add_lag_features(df)

    X, y, _ = prepare_features(df)

    # If HPO requested, run it
    hpo_result = None
    if run_hpo:
        hpo_result = optimize_hyperparameters(X, y)
        best_params = hpo_result['best_params']
        print(f"[HPO] Best params: {best_params}, CV MAE: {hpo_result['best_cv_mae']}")
    else:
        best_params = {
            'n_estimators': 200,
            'max_depth': 5,
            'learning_rate': 0.1,
            'subsample': 0.8,
        }

    # Train with the chosen hyperparameters
    model = xgb.XGBRegressor(
        n_estimators=best_params['n_estimators'],
        max_depth=best_params['max_depth'],
        learning_rate=best_params['learning_rate'],
        subsample=best_params['subsample'],
        random_state=42,
        eval_metric='rmse',
        early_stopping_rounds=20,
        verbosity=0,
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    y_pred = model.predict(X_test)
    new_r2 = round(float(r2_score(y_test, y_pred)), 4)

    # Save model with metadata
    joblib.dump({"model": model, "r2": new_r2, "timestamp": timestamp, "hpo_used": run_hpo}, MODEL_STAGING_PATH)
    print(f"[Pipeline] Model saved to Staging {MODEL_STAGING_PATH} — R²: {new_r2}")

    return {
        "retrained"  : True,
        "new_r2"     : new_r2,
        "old_r2"     : old_r2,
        "timestamp"  : timestamp,
        "model_path" : MODEL_STAGING_PATH,
        "hpo_used"   : run_hpo,
        "hpo_result" : hpo_result,
    }


def evaluate_staged_model(city: str = "Riyadh") -> dict:
    """
    Compare the staged model against the currently live model on an
    identical freshly generated held-out window for `city`, reusing the
    train/test split pattern from compare_baseline_vs_enhanced() so both
    models are scored on the same data.

    If no live model exists yet (first-ever training), there is nothing
    to regress against, so promotion is recommended unconditionally.

    Returns
    -------
    dict with staged_mae, live_mae, regression, recommendation, reason.
    """
    from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features

    if not os.path.exists(MODEL_STAGING_PATH):
        return {
            "staged_mae": None, "live_mae": None, "regression": False,
            "recommendation": "reject", "reason": "No staged model found.",
        }

    staged_model = joblib.load(MODEL_STAGING_PATH)["model"]

    df = generate_traffic_data(city=city)
    df = apply_hourly_patterns(df, city=city)
    df = add_lag_features(df)
    X, y, _ = prepare_features(df)
    _, X_test, _, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    staged_mae = round(float(mean_absolute_error(y_test, staged_model.predict(X_test))), 4)

    if not os.path.exists(MODEL_PATH):
        return {
            "staged_mae": staged_mae, "live_mae": None, "regression": False,
            "recommendation": "promote",
            "reason": "No live model exists yet — first training is auto-promoted.",
        }

    live_bundle = joblib.load(MODEL_PATH)
    # Defensive: save_model() elsewhere in the codebase dumps a raw model,
    # not a {"model": ...} bundle. Handle both formats found in the repo.
    live_model = live_bundle["model"] if isinstance(live_bundle, dict) else live_bundle
    live_mae   = round(float(mean_absolute_error(y_test, live_model.predict(X_test))), 4)

    regression     = staged_mae > live_mae
    recommendation = "reject" if regression else "promote"

    return {
        "staged_mae": staged_mae, "live_mae": live_mae,
        "regression": regression, "recommendation": recommendation,
        "reason": (
            f"Staged MAE {staged_mae} is worse than live MAE {live_mae}."
            if regression else
            f"Staged MAE {staged_mae} does not regress vs live MAE {live_mae}."
        ),
    }


def promote_staged_model(city: str, drift_score: float, evaluation: dict) -> dict:
    """
    Copy the staged model into the live model slot and append a row to
    MODEL_CHANGELOG.md. Caller must already hold a 'promote' recommendation
    from evaluate_staged_model() — promotion and evaluation are kept as two
    separate, individually auditable steps.
    """
    if evaluation.get("recommendation") != "promote":
        raise ValueError("promote_staged_model called without a 'promote' recommendation.")

    staged_bundle = joblib.load(MODEL_STAGING_PATH)
    timestamp     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    joblib.dump(staged_bundle, MODEL_PATH)

    _append_changelog_entry(
        timestamp=timestamp, city=city, drift_score=drift_score,
        staged_mae=evaluation.get("staged_mae"), live_mae=evaluation.get("live_mae"),
        decision="promoted", decision_maker="automatic",
    )

    return {
        "promoted": True, "timestamp": timestamp,
        "staged_mae": evaluation.get("staged_mae"),
        "live_mae": evaluation.get("live_mae"),
    }


def _append_changelog_entry(timestamp, city, drift_score, staged_mae, live_mae,
                            decision, decision_maker) -> None:
    """Append one human-readable row to MODEL_CHANGELOG.md (committed, not gitignored)."""
    write_header = not os.path.exists(MODEL_CHANGELOG_PATH)
    with open(MODEL_CHANGELOG_PATH, "a", encoding="utf-8") as f:
        if write_header:
            f.write("# Model Changelog\n\n")
            f.write(
                "Auto-appended on every retrain/promotion decision made by the "
                "staged model promotion gate (PROMPT 065). `decision_maker` is "
                "'automatic' unless a human operator approval step is wired in.\n\n"
            )
            f.write("| Timestamp | City | Drift Score | Staged MAE | Live MAE | Decision | Decision Maker |\n")
            f.write("|---|---|---|---|---|---|---|\n")
        f.write(f"| {timestamp} | {city} | {drift_score} | {staged_mae} | {live_mae} | {decision} | {decision_maker} |\n")


def run_pipeline(city: str = "Riyadh") -> dict:
    timestamp   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    drift_score = compute_drift_score()
    retrained   = False
    promoted    = False
    new_r2      = None
    old_r2      = None
    hpo_used    = False
    evaluation  = None

    if should_retrain(drift_score):
        print(f"[Pipeline] Drift score {drift_score} >= {DRIFT_THRESHOLD}. Retraining into staging slot...")
        run_hpo = drift_score >= 1.5
        result  = retrain_model(city=city, run_hpo=run_hpo)
        retrained = result["retrained"]
        new_r2    = result["new_r2"]
        old_r2    = result["old_r2"]
        hpo_used  = result.get("hpo_used", False)

        evaluation = evaluate_staged_model(city=city)
        if evaluation["recommendation"] == "promote":
            promote_staged_model(city=city, drift_score=drift_score, evaluation=evaluation)
            promoted = True
        else:
            print(f"[Pipeline] Staged model rejected: {evaluation['reason']}")
            _append_changelog_entry(
                timestamp=timestamp, city=city, drift_score=drift_score,
                staged_mae=evaluation.get("staged_mae"), live_mae=evaluation.get("live_mae"),
                decision="rejected", decision_maker="automatic",
            )
    else:
        print(f"[Pipeline] Drift score {drift_score} — model stable. No retrain needed.")

    outcome = {
        "timestamp"  : timestamp,
        "city"       : city,
        "drift_score": drift_score,
        "retrained"  : retrained,
        "promoted"   : promoted,
        "new_r2"     : new_r2,
        "old_r2"     : old_r2,
        "hpo_used"   : hpo_used,
        "staged_mae" : evaluation.get("staged_mae") if evaluation else None,
        "live_mae"   : evaluation.get("live_mae") if evaluation else None,
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




def check_incident_alerts(city_df: pd.DataFrame, city: str = "Riyadh") -> list:
    """
    Scans all zones in city_df for traffic incidents using detect_incidents().

    Returns a list of alert dicts with the same schema as check_thresholds()
    for incidents whose severity meets or exceeds
    ALERT_THRESHOLDS["incident_severity_min"].

    Parameters
    ----------
    city_df : pd.DataFrame
        Full city DataFrame from app.state.city_dfs.
    city    : str
        City name for alert payload context.

    Returns
    -------
    list of dicts, one per triggered incident alert.
    """
    from src.model import detect_incidents, estimate_incident_clearance_time
    from src.config import ALERT_THRESHOLDS

    severity_rank = {"Minor": 0, "Moderate": 1, "Major": 2, "Critical": 3}
    min_severity  = ALERT_THRESHOLDS.get("incident_severity_min", "Moderate")
    min_rank      = severity_rank.get(min_severity, 1)
    alerts        = []

    for zone in city_df["zone"].unique():
        zone_df = city_df[city_df["zone"] == zone]
        if zone_df.empty:
            continue

        result = detect_incidents(zone_df, zone=zone, city=city, log=True)

        if result.get("incident_detected"):
            incident_rank = severity_rank.get(result.get("severity"), 0)
            if incident_rank >= min_rank:
                weather   = str(zone_df["weather"].iloc[-1]) if "weather" in zone_df.columns else "Clear"
                road_type = str(zone_df["road_type"].iloc[-1]) if "road_type" in zone_df.columns else "urban"

                clearance = estimate_incident_clearance_time(
                    result.get("severity"),
                    weather,
                    road_type
                )

                alerts.append({
                    "alert_type":             "incident",
                    "city":                   city,
                    "zone":                   zone,
                    "severity":               result.get("severity"),
                    "speed_drop_pct":         result.get("speed_drop_pct"),
                    "confidence":             result.get("confidence"),
                    "recommended_action":     result.get("recommended_action"),
                    "estimated_clearance_mins": clearance,
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


def check_sla_breach_alerts(days: int = 1) -> list:
    """
    Compare current SLA metrics against SLA_TARGETS. SLA is system-level,
    not per-zone, so each alert uses zone='system', city='all' — verified
    safe against deliver_webhook_alert()/log_alert(), both of which treat
    zone/city as opaque strings.
    """
    from src.config import SLA_TARGETS, SLA_BREACH_SEVERITY

    metrics = compute_sla_metrics(days=days)
    if metrics.get('total_requests', 0) == 0:
        return []

    checks = {
        'uptime_pct'     : (metrics.get('uptime_pct'),      SLA_TARGETS['uptime_pct'],      'gte'),
        'avg_response_ms': (metrics.get('avg_response_ms'), SLA_TARGETS['avg_response_ms'], 'lte'),
        'p95_response_ms': (metrics.get('p95_response_ms'), SLA_TARGETS['p95_response_ms'], 'lte'),
        'error_rate_pct' : (metrics.get('error_rate_pct'),  SLA_TARGETS['error_rate_pct'],  'lte'),
    }

    alerts = []
    for metric, (value, target, direction) in checks.items():
        if value is None:
            continue
        breached = (value < target) if direction == 'gte' else (value > target)
        if breached:
            alerts.append({
                'zone'     : 'system',
                'city'     : 'all',
                'metric'   : metric,
                'value'    : value,
                'threshold': target,
                'severity' : SLA_BREACH_SEVERITY[metric],
            })
    return alerts


def compute_sla_trend(window_days: int = 7) -> dict:
    """
    Daily uptime/response-time trend from usage_log.csv over the trailing
    window_days. Needs >= 6 days of data (3 per half); otherwise returns
    'stable' with a note rather than a misleading trend.
    """
    log_path = "usage_log.csv"
    empty = {
        'dates': [], 'uptime_pcts': [], 'avg_response_ms_per_day': [],
        'trend': 'stable', 'trend_delta_pct': 0.0,
    }

    if not os.path.exists(log_path):
        return {**empty, 'note': 'No usage data yet.'}

    log_df = pd.read_csv(log_path)
    if 'timestamp' not in log_df.columns or log_df.empty:
        return {**empty, 'note': 'No usage data yet.'}

    log_df['timestamp'] = pd.to_datetime(log_df['timestamp'], errors='coerce')
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=window_days)
    log_df = log_df[log_df['timestamp'] >= cutoff]
    if log_df.empty:
        return {**empty, 'note': 'No usage data in window.'}

    log_df['date'] = log_df['timestamp'].dt.date
    dates, uptime_pcts, avg_rts = [], [], []

    for date, grp in log_df.groupby('date'):
        total = len(grp)
        successes = int((grp['response_code'] < 400).sum()) if 'response_code' in grp.columns else total
        avg_rt = round(float(grp['response_time_ms'].mean()), 1) if 'response_time_ms' in grp.columns and total else None
        dates.append(str(date))
        uptime_pcts.append(round(successes / total * 100, 3) if total else 100.0)
        avg_rts.append(avg_rt)

    if len(dates) < 6:
        return {
            'dates': dates, 'uptime_pcts': uptime_pcts,
            'avg_response_ms_per_day': avg_rts,
            'trend': 'stable', 'trend_delta_pct': 0.0,
            'note': f'Only {len(dates)} day(s) of data — need >= 6 for a meaningful trend.',
        }

    half = len(uptime_pcts) // 2
    first_avg = sum(uptime_pcts[:half]) / half
    last_avg  = sum(uptime_pcts[-half:]) / half
    delta = round(last_avg - first_avg, 3)
    trend = 'improving' if delta > 0.5 else 'degrading' if delta < -0.5 else 'stable'

    return {
        'dates': dates, 'uptime_pcts': uptime_pcts,
        'avg_response_ms_per_day': avg_rts,
        'trend': trend, 'trend_delta_pct': delta,
    }




# ──— Key registry persistence ─────────────────────────
import json as _json
import uuid as _uuid

KEY_REGISTRY_PATH = "key_registry.json"


def load_key_registry(registry_path: str = KEY_REGISTRY_PATH) -> list:
    """
    Load key registry from JSON file.
    Falls back to API_KEYS env var if file does not exist.
    Returns a list of key dicts with full metadata.
    """
    if os.path.exists(registry_path):
        with open(registry_path, 'r') as f:
            return _json.load(f).get('keys', [])

    # Fallback: seed from API_KEYS env var
    env_registry = build_key_registry()
    keys = []
    for key, info in env_registry.items():
        keys.append({
            'key':        key,
            'city':       info.get('city', '*'),
            'role':       info.get('role', 'operator'),
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'revoked':    False,
            'revoked_at': None,
        })
    save_key_registry(keys, registry_path)
    return keys


def save_key_registry(keys: list, registry_path: str = KEY_REGISTRY_PATH) -> None:
    """Write key list to JSON file."""
    with open(registry_path, 'w') as f:
        _json.dump({'keys': keys}, f, indent=2)


def add_key_to_registry(city: str, role: str,
                         registry_path: str = KEY_REGISTRY_PATH) -> str:
    """Generate a new key, persist it, return the full key (shown once only)."""
    import secrets as _secrets
    new_key = 'sk_live_' + _secrets.token_hex(24)
    keys = load_key_registry(registry_path)
    keys.append({
        'key':        new_key,
        'city':       city,
        'role':       role,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'revoked':    False,
        'revoked_at': None,
    })
    save_key_registry(keys, registry_path)
    return new_key


def revoke_key_from_registry(key_prefix: str,
                              registry_path: str = KEY_REGISTRY_PATH) -> bool:
    """Revoke a key by its first 8 chars. Returns True if found and revoked."""
    keys = load_key_registry(registry_path)
    found = False
    for entry in keys:
        if entry['key'].startswith(key_prefix) and not entry['revoked']:
            entry['revoked']    = True
            entry['revoked_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            found = True
            break
    if found:
        save_key_registry(keys, registry_path)
    return found


def list_registry_keys(registry_path: str = KEY_REGISTRY_PATH) -> list:
    """Return all keys with only the first 8 chars visible — never the full key."""
    keys = load_key_registry(registry_path)
    return [
        {
            'key_prefix': entry['key'][:8],
            'city':       entry['city'],
            'role':       entry['role'],
            'created_at': entry['created_at'],
            'revoked':    entry.get('revoked', False),
            'revoked_at': entry.get('revoked_at'),
        }
        for entry in keys
    ]