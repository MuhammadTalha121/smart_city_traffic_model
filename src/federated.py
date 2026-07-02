import datetime
import numpy as np
from src.config import FEDERATED_DP_EPSILON, FEDERATED_DP_ENABLED
from src.model import train_xgboost, prepare_features, generate_data


def add_dp_noise(params: dict, epsilon: float) -> dict:
    """
    Add Laplace noise to numeric parameters for differential privacy.

    Noise scale = 1 / epsilon (sensitivity assumed to be 1).
    Returns a new dict; original is unchanged.
    """
    noisy = {}
    scale = 1.0 / max(epsilon, 1e-9)
    for key, value in params.items():
        if isinstance(value, (int, float)):
            noise = np.random.laplace(0, scale)
            noisy[key] = value + noise
        else:
            noisy[key] = value
    return noisy


def extract_shareable_params(model) -> dict:
    """Returns hyperparameters and performance stats — no training data.
    If FEDERATED_DP_ENABLED is True, adds Laplace noise to numeric hyperparameters.
    """
    from sklearn.metrics import r2_score

    params = model.get_params()
    df          = generate_data('Riyadh')
    X, y, _     = prepare_features(df)
    preds  = model.predict(X)
    r2     = float(r2_score(y, preds))

    # Safe hyperparameters to share (numeric only)
    safe_params = {
        'n_estimators': params.get('n_estimators', 200),
        'max_depth': params.get('max_depth', 5),
        'learning_rate': params.get('learning_rate', 0.1),
        'subsample': params.get('subsample', 0.8),
        'colsample_bytree': params.get('colsample_bytree', 1.0),
        'reg_alpha': params.get('reg_alpha', 0.0),
        'reg_lambda': params.get('reg_lambda', 1.0),
    }

    if FEDERATED_DP_ENABLED:
        noisy_params = add_dp_noise(safe_params, FEDERATED_DP_EPSILON)
        return {
            'best_params': noisy_params,
            'n_estimators_used': int(round(noisy_params.get('n_estimators', 200))),
            'training_r2': round(r2, 4),
            'city': 'Riyadh',
            'timestamp': datetime.datetime.now(datetime.UTC).isoformat(),
            'dp_applied': True,
            'dp_epsilon': FEDERATED_DP_EPSILON,
        }
    else:
        return {
            'best_params': safe_params,
            'n_estimators_used': params.get('n_estimators', 200),
            'training_r2': round(r2, 4),
            'city': 'Riyadh',
            'timestamp': datetime.datetime.now(datetime.UTC).isoformat(),
            'dp_applied': False,
        }


def simulate_aggregation(city_params: list) -> dict:
    """Weighted average of hyperparameters — weight = training_r2."""
    if not city_params:
        return {}

    total_weight = sum(p['training_r2'] for p in city_params)
    if total_weight == 0:
        return city_params[0]['best_params']

    agg = {}
    numeric_keys = ['n_estimators', 'max_depth', 'learning_rate',
                    'subsample', 'reg_alpha', 'reg_lambda', 'colsample_bytree']

    for key in numeric_keys:
        values = [p['best_params'].get(key) for p in city_params
                  if p['best_params'].get(key) is not None]
        if not values:
            continue
        weights = [p['training_r2'] for p in city_params
                   if p['best_params'].get(key) is not None]
        agg[key] = round(
            sum(v * w for v, w in zip(values, weights)) / sum(weights), 6
        )

    # n_estimators and max_depth must be int
    for int_key in ['n_estimators', 'max_depth']:
        if int_key in agg:
            agg[int_key] = int(round(agg[int_key]))

    avg_r2 = sum(p['training_r2'] for p in city_params) / len(city_params)
    return {
        'aggregated_params': agg,
        'source_cities'    : [p.get('city', 'unknown') for p in city_params],
        'avg_training_r2'  : round(avg_r2, 4),
        'timestamp': datetime.datetime.now(datetime.UTC).isoformat(),
    }


def apply_aggregated_params(model, aggregated_params: dict):
    """Rebuild model with aggregated hyperparameters if they improve R²."""
    import xgboost as xgb
    from sklearn.metrics import r2_score

    df      = generate_data('Riyadh')
    X, y, _ = prepare_features(df)
    current_r2 = float(r2_score(y, model.predict(X)))

    incoming_r2 = aggregated_params.get('avg_training_r2', 0)
    if incoming_r2 <= current_r2:
        return model  # no improvement — keep current model

    params = aggregated_params.get('aggregated_params', {})
    new_model = xgb.XGBRegressor(**params, random_state=42, verbosity=0)
    new_model.fit(X, y)
    return new_model


def distribute_aggregated_model(
    aggregated_params: dict,
    cities: list,
    force_retrain: bool = False,
) -> dict:
    """
    Distribute aggregated parameters to each city via the staging gate.

    For each city:
      - Generate fresh data.
      - Initialise XGBoost with aggregated_params.
      - Train on city data.
      - Save to staging slot.
      - Evaluate against live model (if exists).
      - Promote if evaluation passes.

    Returns per‑city results with status (promoted/rejected).
    """
    from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features, add_cross_zone_lag_features
    from src.model import prepare_features
    from src.pipeline import evaluate_staged_model, promote_staged_model
    import joblib
    import os
    from datetime import datetime

    results = {}

    for city in cities:
        print(f"[Federated] Distributing to {city}...")
        try:
            # Generate data for this city
            df = generate_traffic_data(city=city, n_days=30)
            df = apply_hourly_patterns(df, city=city)
            df = add_lag_features(df)
            df = add_cross_zone_lag_features(df)
            X, y, _ = prepare_features(df)

            # Initialise model with aggregated params
            # Remove any metadata keys that might be present
            params = aggregated_params.copy()
            for key in ['city', 'training_r2', 'dp_applied', 'dp_epsilon']:
                params.pop(key, None)

            import xgboost as xgb
            from sklearn.model_selection import train_test_split

            model = xgb.XGBRegressor(
                **params,
                random_state=42,
                eval_metric='rmse',
                early_stopping_rounds=20,
                verbosity=0,
            )
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
            model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

            # Save to staging slot (bundle with metadata)
            from src.pipeline import MODEL_STAGING_PATH
            joblib.dump({
                "model": model,
                "r2": 0.0,
                "timestamp": datetime.now().isoformat(),
                "hpo_used": False,
                "source": "federated_aggregation"
            }, MODEL_STAGING_PATH)

            # Evaluate staged model against live model
            eval_result = evaluate_staged_model(city=city)
            if eval_result["recommendation"] == "promote":
                # Promote
                promote_result = promote_staged_model(
                    city=city,
                    drift_score=1.0,  # not used for changelog here, but required
                    evaluation=eval_result,
                )
                results[city] = {
                    "status": "promoted",
                    "staged_mae": eval_result.get("staged_mae"),
                    "live_mae": eval_result.get("live_mae"),
                    "reason": "Evaluation passed.",
                }
            else:
                results[city] = {
                    "status": "rejected",
                    "staged_mae": eval_result.get("staged_mae"),
                    "live_mae": eval_result.get("live_mae"),
                    "reason": eval_result.get("reason", "Staged model regressed."),
                }
        except Exception as e:
            results[city] = {"status": "error", "error": str(e)}

    return results