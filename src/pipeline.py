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
