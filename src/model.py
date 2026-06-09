import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
import joblib
from typing import Tuple, Dict
from src.config import CONGESTION_THRESHOLDS, WEATHER_SPEED_IMPACT, SAUDI_CITIES


FEATURE_COLS = [
    'hour', 'vehicle_count', 'avg_speed', 'weather', 'event',
    'road_type', 'rush_hour', 'is_weekend', 'is_late_night',
    'hour_multiplier', 'zone', 'day_of_week',
    'vehicle_count_lag_1h', 'vehicle_count_lag_2h',
    'congestion_lag_1h', 'rolling_mean_3h', 'rolling_std_3h'
]

WEATHER_ENCODING  = {'clear': 0, 'dust': 1, 'fog': 2, 'humid': 3, 'rain': 4, 'sandstorm': 5}
ROAD_ENCODING     = {'arterial': 0, 'highway': 1, 'local': 2}
ZONE_ENCODING     = {'Zone_1': 0, 'Zone_2': 1, 'Zone_3': 2, 'Zone_4': 3, 'Zone_5': 4}
DAY_ENCODING      = {
    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
    'Friday': 4, 'Saturday': 5, 'Sunday': 6
}


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, list]:
    """Encode categoricals and return feature matrix, target, feature names."""
    df = df.copy()

    df['weather']     = df['weather'].map(WEATHER_ENCODING).fillna(0)
    df['road_type']   = df['road_type'].map(ROAD_ENCODING).fillna(0)
    df['zone']        = df['zone'].map(ZONE_ENCODING).fillna(0)
    df['day_of_week'] = df['day_of_week'].map(DAY_ENCODING).fillna(0)

    available = [f for f in FEATURE_COLS if f in df.columns]
    return df[available], df['congestion_score'], available


def train_xgboost(X: pd.DataFrame, y: pd.Series) -> Tuple:
    """Train XGBoost regressor with early stopping."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = xgb.XGBRegressor(
        n_estimators         = 200,
        max_depth            = 5,
        learning_rate        = 0.1,
        subsample            = 0.8,
        random_state         = 42,
        eval_metric          = 'rmse',
        early_stopping_rounds= 20,
        verbosity            = 0
    )

    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    return model, X_test, y_test


def evaluate_models(X: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    """Train and compare Linear Regression, Random Forest, and XGBoost."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    models = {
        'Linear Regression': LinearRegression(),
        'Random Forest'    : RandomForestRegressor(n_estimators=100, random_state=42),
        'XGBoost'          : xgb.XGBRegressor(
                                n_estimators=200, max_depth=5, learning_rate=0.1,
                                subsample=0.8, random_state=42, verbosity=0
                             )
    }

    results = []
    for name, model in models.items():
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        results.append({
            'Model': name,
            'MAE'  : round(mean_absolute_error(y_test, y_pred), 4),
            'RMSE' : round(np.sqrt(mean_squared_error(y_test, y_pred)), 4),
            'R²'   : round(r2_score(y_test, y_pred), 4)
        })

    return pd.DataFrame(results).sort_values('R²', ascending=False).reset_index(drop=True)


def congestion_level(score: float) -> str:
    """Classify congestion score into human-readable level."""
    for level, threshold in CONGESTION_THRESHOLDS.items():
        if score <= threshold:
            return level
    return 'Critical'


def get_recommendation(level: str, zone: str, weather: str, city: str) -> str:
    """Return operational recommendation based on congestion level and context."""
    sandstorm_note = ' Sandstorm protocol active — reduce speed limits.' if weather == 'sandstorm' else ''
    prayer_context = ' Note: Friday prayer period — expect post-prayer surge.' if weather == 'clear' else ''

    recommendations = {
        'Low'     : f'{zone} is clear. Normal operations.',
        'Moderate': f'Monitor {zone}. Consider adaptive signal timing adjustments.',
        'High'    : f'Deploy traffic officers to {zone}. Activate alternate routes.{sandstorm_note}',
        'Critical': f'ALERT: {zone} critically congested.{sandstorm_note} Initiate emergency traffic management.'
    }
    return recommendations[level]


def predict_single(city: str, zone: str, hour: int, vehicle_count: float,
                   avg_speed: float, weather: str, road_type: str,
                   rush_hour: int, is_weekend: int, is_late_night: int,
                   event: int, hour_multiplier: float) -> Dict:
    """Compute congestion prediction from raw inputs without a trained model."""
    adjusted_speed = avg_speed * WEATHER_SPEED_IMPACT.get(weather, 1.0)
    score          = float(np.clip(
        (vehicle_count / 500) * (1 - adjusted_speed / 100), 0, 1
    ))
    level          = congestion_level(score)
    recommendation = get_recommendation(level, zone, weather, city)

    return {
        'city'            : city,
        'zone'            : zone,
        'hour'            : hour,
        'weather'         : weather,
        'congestion_score': round(score, 4),
        'congestion_level': level,
        'recommendation'  : recommendation
    }


def save_model(model, path: str = 'model.joblib'):
    joblib.dump(model, path)


def load_model(path: str = 'model.joblib'):
    return joblib.load(path)


def compare_baseline_vs_enhanced(city: str = 'Riyadh') -> pd.DataFrame:
    """
    Train XGBoost with and without lag features and print improvement table.
    """
    from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features

    df_base     = apply_hourly_patterns(generate_traffic_data(city=city), city=city)
    df_enhanced = add_lag_features(df_base.copy())

    rows = []
    for label, df in [('Baseline', df_base), ('Enhanced (lag features)', df_enhanced)]:
        X, y, _ = prepare_features(df)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        model = xgb.XGBRegressor(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            subsample=0.8, random_state=42, verbosity=0
        )
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        rows.append({
            'Model': label,
            'R²'   : round(r2_score(y_test, y_pred), 4),
            'MAE'  : round(mean_absolute_error(y_test, y_pred), 4),
            'RMSE' : round(np.sqrt(mean_squared_error(y_test, y_pred)), 4),
        })

    report = pd.DataFrame(rows)
    baseline_r2  = report.loc[report['Model'] == 'Baseline', 'R²'].values[0]
    enhanced_r2  = report.loc[report['Model'] == 'Enhanced (lag features)', 'R²'].values[0]
    improvement  = round((enhanced_r2 - baseline_r2) / max(baseline_r2, 1e-9) * 100, 2)

    print("\n" + "=" * 60)
    print("  Baseline vs Enhanced — XGBoost Comparison")
    print("=" * 60)
    print(report.to_string(index=False))
    print(f"\n  R² improvement with lag features: {improvement}%")
    print("=" * 60 + "\n")

    return report


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect anomalous traffic conditions per zone and hour.

    Anomaly defined as actual vehicle count exceeding 200% of
    rolling 7-day mean for that zone and hour combination.

    Returns
    -------
    pd.DataFrame with anomaly_flag and anomaly_severity columns added.
    """
    df = df.copy().sort_values(['zone', 'timestamp']).reset_index(drop=True)

    df['expected_vehicle_count'] = (
        df.groupby(['zone', 'hour'])['vehicle_count']
          .transform(lambda x: x.shift(1).rolling(window=7, min_periods=1).mean())
    )
    df['expected_congestion'] = (
        df.groupby(['zone', 'hour'])['congestion_score']
          .transform(lambda x: x.shift(1).rolling(window=7, min_periods=1).mean())
    )

    df['anomaly_ratio'] = df['vehicle_count'] / df['expected_vehicle_count'].replace(0, np.nan)
    df['anomaly_flag']  = (df['anomaly_ratio'] >= 2.0).astype(int)

    def severity(ratio):
        if   pd.isna(ratio)  : return 'Normal'
        elif ratio < 1.5     : return 'Normal'
        elif ratio < 2.0     : return 'Elevated'
        elif ratio < 3.0     : return 'Anomalous'
        else                 : return 'Critical Anomaly'

    df['anomaly_severity'] = df['anomaly_ratio'].apply(severity)

    def anomaly_recommendation(row):
        if row['anomaly_severity'] == 'Normal'          : return 'No action required.'
        if row['anomaly_severity'] == 'Elevated'        : return f"Monitor {row['zone']} closely — traffic building above expected levels."
        if row['anomaly_severity'] == 'Anomalous'       : return f"Dispatch traffic officers to {row['zone']}. Investigate cause immediately."
        if row['anomaly_severity'] == 'Critical Anomaly': return f"CRITICAL: {row['zone']} at {row['anomaly_ratio']:.1f}x expected volume. Activate emergency protocol."
        return 'No action required.'

    df['anomaly_recommendation'] = df.apply(anomaly_recommendation, axis=1)

    return df


def forecast_congestion(df: pd.DataFrame, zone: str,
                         hours_ahead: list = [1, 2, 3]) -> list:
    """
    Forecast congestion score for a zone at 1, 2, and 3 hours ahead.

    Uses historical patterns for that zone and hour combination.
    Returns predicted score, confidence interval, level, and recommendation.
    """
    from src.config import HOURLY_MULTIPLIERS, CITY_PROFILES

    zone_df  = df[df['zone'] == zone].sort_values('timestamp').copy()
    forecasts = []

    current_hour  = int(zone_df['hour'].iloc[-1])
    current_score = float(zone_df['congestion_score'].iloc[-1])
    city          = zone_df['city'].iloc[0] if 'city' in zone_df.columns else 'Riyadh'
    weather       = zone_df['weather'].iloc[-1] if 'weather' in zone_df.columns else 'clear'

    schedule = 'saudi' if city in SAUDI_CITIES else 'standard'
    multipliers = HOURLY_MULTIPLIERS[schedule]

    residuals = []
    for h in range(1, 8):
        past_hour = (current_hour - h) % 24
        past_vals = zone_df[zone_df['hour'] == past_hour]['congestion_score']
        if len(past_vals) >= 2:
            residuals.extend(list(past_vals.diff().dropna().abs()))

    residual_std = float(np.std(residuals)) if residuals else 0.02

    for h in hours_ahead:
        future_hour    = (current_hour + h) % 24
        hour_mult      = multipliers.get(future_hour, 1.0)
        current_mult   = multipliers.get(current_hour, 1.0)
        scale          = hour_mult / max(current_mult, 0.01)
        predicted      = float(np.clip(current_score * scale, 0, 1))
        lower          = float(np.clip(predicted - residual_std, 0, 1))
        upper          = float(np.clip(predicted + residual_std, 0, 1))
        level          = congestion_level(predicted)
        recommendation = get_recommendation(level, zone, weather, city)

        forecasts.append({
            'hours_ahead'     : h,
            'forecast_hour'   : future_hour,
            'predicted_score' : round(predicted, 4),
            'lower_bound'     : round(lower, 4),
            'upper_bound'     : round(upper, 4),
            'congestion_level': level,
            'recommendation'  : recommendation
        })

    return forecasts


def compare_arima_vs_xgboost(city: str = 'Riyadh', zone: str = 'Zone_1') -> pd.DataFrame:
    """
    Compare ARIMA and XGBoost on 1h, 2h, 3h forecast horizon for a single zone.

    Returns comparison table with MAE per horizon per model.
    """
    from statsmodels.tsa.arima.model import ARIMA
    from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features

    df       = apply_hourly_patterns(generate_traffic_data(city=city), city=city)
    df       = add_lag_features(df)
    zone_df  = df[df['zone'] == zone].sort_values('timestamp').reset_index(drop=True)
    series   = zone_df['congestion_score'].values

    split    = int(len(series) * 0.8)
    train    = series[:split]
    test     = series[split:]

    rows = []
    for horizon in [1, 2, 3]:
        arima_preds  = []
        xgb_preds    = []
        actuals      = []

        X_all, y_all, _ = prepare_features(zone_df)
        X_train = X_all.iloc[:split]
        y_train = y_all.iloc[:split]
        xgb_model = xgb.XGBRegressor(
            n_estimators=200, max_depth=5, learning_rate=0.1,
            subsample=0.8, random_state=42, verbosity=0
        )
        xgb_model.fit(X_train, y_train)

        for i in range(len(test) - horizon):
            actual = test[i + horizon]
            actuals.append(actual)

            try:
                arima_model  = ARIMA(train, order=(2, 1, 2))
                arima_fit    = arima_model.fit()
                arima_fc     = arima_fit.forecast(steps=horizon)
                arima_preds.append(float(np.clip(arima_fc.iloc[-1], 0, 1)))
            except Exception:
                arima_preds.append(float(np.mean(train)))

            xgb_input = X_all.iloc[split + i: split + i + 1]
            xgb_fc    = float(xgb_model.predict(xgb_input)[0])
            xgb_preds.append(np.clip(xgb_fc, 0, 1))

        rows.append({
            'Horizon'   : f'+{horizon}h',
            'ARIMA MAE' : round(mean_absolute_error(actuals, arima_preds), 4),
            'XGBoost MAE': round(mean_absolute_error(actuals, xgb_preds), 4),
        })

    report = pd.DataFrame(rows)
    print("\n" + "=" * 60)
    print(f"  ARIMA vs XGBoost — Forecast Comparison ({zone})")
    print("=" * 60)
    print(report.to_string(index=False))
    print("=" * 60 + "\n")
    return report


def explain_prediction(model, X_row: pd.DataFrame, feature_names: list) -> Dict:
    """
    Generate SHAP-based explanation for a single prediction.

    Returns top 3 contributing factors with direction and plain English summary.
    """
    import shap

    explainer  = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_row)

    shap_series = pd.Series(shap_values[0], index=feature_names)
    shap_abs    = shap_series.abs().sort_values(ascending=False)
    top_3       = shap_abs.head(3).index.tolist()

    business_labels = {
        'avg_speed'            : 'average speed',
        'vehicle_count'        : 'vehicle count',
        'hour'                 : 'time of day',
        'hour_multiplier'      : 'hourly traffic weight',
        'rush_hour'            : 'rush hour period',
        'is_late_night'        : 'late night activity',
        'is_weekend'           : 'weekend pattern',
        'weather'              : 'weather condition',
        'road_type'            : 'road type',
        'zone'                 : 'zone location',
        'event'                : 'special event',
        'day_of_week'          : 'day of week',
        'vehicle_count_lag_1h' : 'traffic 1 hour ago',
        'vehicle_count_lag_2h' : 'traffic 2 hours ago',
        'congestion_lag_1h'    : 'congestion 1 hour ago',
        'rolling_mean_3h'      : '3-hour traffic average',
        'rolling_std_3h'       : 'traffic volatility'
    }

    factors = []
    for feat in top_3:
        impact    = float(shap_series[feat])
        direction = 'increasing congestion' if impact > 0 else 'reducing congestion'
        factors.append({
            'factor'   : business_labels.get(feat, feat),
            'direction': direction,
            'impact'   : round(abs(impact), 4)
        })

    top_factor   = factors[0]['factor']
    top_dir      = factors[0]['direction']
    second       = factors[1]['factor'] if len(factors) > 1 else ''
    plain_english = (
        f"Congestion is primarily driven by {top_factor} ({top_dir})"
        f"{f', followed by {second}' if second else ''}."
    )

    return {
        'top_factors'  : factors,
        'plain_english': plain_english
    }


def compute_accident_risk(
    congestion_score: float,
    weather: str,
    hour: int,
    is_weekend: int,
    rush_hour: int,
) -> Dict:
    """
    Compute an accident risk score for a zone based on traffic conditions.

    Risk factors applied in order:
    - Base risk scales with congestion_score (40% weight)
    - Weather multiplier: sandstorm 2.5x, rain 1.8x, fog 1.6x,
      dust 1.4x, humid 1.1x, clear 1.0x
    - Rush hour adds 0.15 (high density + high speed variance)
    - Late night (21–23) adds 0.12 (Saudi-specific: high speed, low volume)
    - Friday prayer window (12–13, weekend) subtracts 0.10 (minimal vehicles)

    Risk levels:
    - Safe        < 0.30
    - Elevated   0.30–0.50
    - High Risk  0.50–0.70
    - Critical   > 0.70

    Returns
    -------
    dict with risk_score, risk_level, primary_risk_factor
    """
    WEATHER_RISK_MULTIPLIERS = {
        'sandstorm': 2.5,
        'rain'     : 1.8,
        'fog'      : 1.6,
        'dust'     : 1.4,
        'humid'    : 1.1,
        'clear'    : 1.0,
    }

    base_risk  = congestion_score * 0.4
    weather_mult = WEATHER_RISK_MULTIPLIERS.get(weather, 1.0)
    risk       = base_risk * weather_mult

    if rush_hour:
        risk += 0.15
    if hour in (21, 22, 23):
        risk += 0.12
    if is_weekend and hour in (12, 13):
        risk -= 0.10

    risk = float(np.clip(risk, 0.0, 1.0))

    # Determine primary risk factor
    if weather in ('sandstorm', 'rain', 'fog', 'dust'):
        primary_risk_factor = f'{weather} conditions'
    elif rush_hour:
        primary_risk_factor = 'rush hour density'
    elif hour in (21, 22, 23):
        primary_risk_factor = 'late night high-speed activity'
    elif congestion_score > 0.5:
        primary_risk_factor = 'high congestion volume'
    else:
        primary_risk_factor = 'standard traffic conditions'

    if risk < 0.30:
        risk_level = 'Safe'
    elif risk < 0.50:
        risk_level = 'Elevated'
    elif risk < 0.70:
        risk_level = 'High Risk'
    else:
        risk_level = 'Critical Risk'

    return {
        'risk_score'         : round(risk, 4),
        'risk_level'         : risk_level,
        'primary_risk_factor': primary_risk_factor,
    }


def compute_signal_timing(
    congestion_score: float,
    vehicle_count: float,
    hour: int,
    is_weekend: int,
) -> Dict:
    """
    Compute recommended adaptive signal timing for a zone.

    Base cycle is 90 seconds (standard urban cycle).
    Green phase proportion scales with congestion level:
    - Low      → 0.35 green
    - Moderate → 0.45 green
    - High     → 0.55 green
    - Critical → 0.65 green

    Saudi-specific overrides:
    - Friday prayer window (12–13, weekend): 0.20 green — minimal demand
    - Late night (21–23): 0.70 green — high speed, low volume, maximise throughput

    Returns
    -------
    dict with cycle_seconds, green_seconds, red_seconds,
    phase_ratio, timing_rationale
    """
    CYCLE_SECONDS = 90

    level = congestion_level(congestion_score)

    BASE_GREEN_RATIOS = {
        'Low'     : 0.35,
        'Moderate': 0.45,
        'High'    : 0.55,
        'Critical': 0.65,
    }

    phase_ratio = BASE_GREEN_RATIOS[level]
    rationale   = f'{level} congestion — standard {int(phase_ratio * 100)}% green phase'

    # Saudi overrides take precedence over congestion-based ratio
    if is_weekend and hour in (12, 13):
        phase_ratio = 0.20
        rationale   = 'Friday prayer window — minimal demand, reduced green phase'
    elif hour in (21, 22, 23):
        phase_ratio = 0.70
        rationale   = 'Late night — high speed, low volume; extended green for throughput'

    green_seconds = round(CYCLE_SECONDS * phase_ratio)
    red_seconds   = CYCLE_SECONDS - green_seconds

    return {
        'cycle_seconds'   : CYCLE_SECONDS,
        'green_seconds'   : green_seconds,
        'red_seconds'     : red_seconds,
        'phase_ratio'     : round(phase_ratio, 2),
        'timing_rationale': rationale,
    }


def get_intervention(zone: str, hour: int, congestion_level_str: str) -> Dict:
    """
    Return demand-shifting and intervention recommendations for a zone.

    Three urgency tiers:
    - Monitor  (Low / Moderate) — no action needed
    - Advise   (High)           — suggest metro or off-peak departure
    - Intervene (Critical)      — metro + carpool + departure window

    Parameters
    ----------
    zone               : e.g. 'Zone_1'
    hour               : 0–23
    congestion_level_str: 'Low' | 'Moderate' | 'High' | 'Critical'

    Returns
    -------
    dict with keys: operator_action, commuter_advice, metro_station,
                    carpool_available, recommended_departure, urgency
    """
    from src.config import METRO_STATIONS, CARPOOL_LANES, OFF_PEAK_WINDOWS

    metro_station    = METRO_STATIONS.get(zone)
    carpool_available = zone in CARPOOL_LANES

    # Determine relevant off-peak window by hour
    if 6 <= hour <= 11:
        window = OFF_PEAK_WINDOWS['morning']
    elif 14 <= hour <= 20:
        window = OFF_PEAK_WINDOWS['evening']
    else:
        window = None

    recommended_departure = window['recommended'] if window else None

    if congestion_level_str in ('Low', 'Moderate'):
        urgency          = 'Monitor'
        operator_action  = f'{zone} operating within normal parameters. No intervention required.'
        commuter_advice  = 'No action needed. Roads are clear.'

    elif congestion_level_str == 'High':
        urgency         = 'Advise'
        metro_hint      = f' Consider {metro_station}.' if metro_station else ''
        departure_hint  = (
            f" Recommended departure: {window['recommended']} to avoid congestion until {window['avoid_until']}."
            if window else ''
        )
        operator_action = (
            f'Monitor {zone} closely. Prepare to activate alternate routes '
            f'and adaptive signal timing.'
        )
        commuter_advice = (
            f'High congestion in {zone}.{metro_hint}{departure_hint}'
        )

    else:  # Critical
        urgency         = 'Intervene'
        metro_hint      = f' Take {metro_station} to bypass congestion.' if metro_station else ''
        carpool_hint    = f' Carpool lane active in {zone}.' if carpool_available else ''
        departure_hint  = (
            f" Depart at {window['recommended']} or wait until after {window['avoid_until']}."
            if window else ''
        )
        operator_action = (
            f'CRITICAL: Deploy traffic officers to {zone}. Activate alternate routes, '
            f'carpool lanes, and emergency signal override.'
        )
        commuter_advice = (
            f'Critical congestion in {zone}.{metro_hint}{carpool_hint}{departure_hint}'
        )

    return {
        'urgency'              : urgency,
        'operator_action'      : operator_action,
        'commuter_advice'      : commuter_advice,
        'metro_station'        : metro_station,
        'carpool_available'    : carpool_available,
        'recommended_departure': recommended_departure,
    }


def log_prediction(prediction: Dict, explanation: Dict, log_path: str = 'predictions_log.csv'):
    """
    Append a prediction and its explanation to the audit log CSV.
    """
    import os
    from datetime import datetime

    row = {
        'timestamp'      : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'city'           : prediction.get('city'),
        'zone'           : prediction.get('zone'),
        'hour'           : prediction.get('hour'),
        'weather'        : prediction.get('weather'),
        'congestion_score': prediction.get('congestion_score'),
        'congestion_level': prediction.get('congestion_level'),
        'top_factor_1'   : explanation['top_factors'][0]['factor'] if len(explanation['top_factors']) > 0 else '',
        'top_factor_2'   : explanation['top_factors'][1]['factor'] if len(explanation['top_factors']) > 1 else '',
        'top_factor_3'   : explanation['top_factors'][2]['factor'] if len(explanation['top_factors']) > 2 else '',
        'plain_english'  : explanation.get('plain_english', '')
    }

    log_df     = pd.DataFrame([row])
    write_header = not os.path.exists(log_path)
    log_df.to_csv(log_path, mode='a', header=write_header, index=False)
