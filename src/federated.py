import datetime
from src.model import train_xgboost, prepare_features, generate_data

def extract_shareable_params(model) -> dict:
    """Returns hyperparameters and performance stats — no training data."""
    from sklearn.metrics import r2_score
    import numpy as np

    params = model.get_params()
    df          = generate_data('Riyadh')
    X, y, _     = prepare_features(df)
    preds  = model.predict(X)
    r2     = float(r2_score(y, preds))

    return {
        'best_params'      : params,
        'n_estimators_used': params.get('n_estimators', 200),
        'training_r2'      : round(r2, 4),
        'city'             : 'Riyadh',
        'timestamp': datetime.datetime.now(datetime.UTC).isoformat(),
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
                    'subsample', 'reg_alpha', 'reg_lambda']

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