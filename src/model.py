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
from src.config import CONGESTION_THRESHOLDS, WEATHER_SPEED_IMPACT, SAUDI_CITIES, NOISE_BASE_DB, NOISE_VEHICLE_COEFFICIENT, NOISE_SPEED_COEFFICIENT, NOISE_ROAD_TYPE_PREMIUM, NOISE_THRESHOLDS


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


def generate_data(city: str = 'Riyadh') -> pd.DataFrame:
    """
    Full pipeline: generate raw data, apply hourly patterns, add lag features.

    generate_traffic_data() alone does not produce congestion_score —
    that column is added by apply_hourly_patterns(). This wrapper exists
    so callers that need a model-ready DataFrame (with congestion_score
    and lag columns), such as src/federated.py, don't have to repeat the
    three-step pipeline.
    """
    from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features

    df = generate_traffic_data(city=city)
    df = apply_hourly_patterns(df, city=city)
    df = add_lag_features(df)
    return df


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



def recommend_tidal_flow(zone: str, hour: int, vehicle_count: float,
                          total_lanes: int = 4) -> Dict:
    """
    Recommend tidal flow lane reversal based on directional traffic asymmetry.

    Directional split is approximated from time-of-day, since the system
    stores total zone volume, not directional counts. Morning hours bias
    inbound, evening hours bias outbound, all other hours assume balance.
    The dominant direction (whichever volume is larger) is compared against
    the secondary direction to produce a symmetric asymmetry ratio that
    correctly triggers in both morning-inbound and evening-outbound surges.
    """
    from src.config import (
        TIDAL_ASYMMETRY_THRESHOLD, TIDAL_MIN_TOTAL_LANES,
        TIDAL_ELIGIBLE_ZONES, MORNING_INBOUND_HOURS, EVENING_OUTBOUND_HOURS
    )

    if hour in MORNING_INBOUND_HOURS:
        inbound_ratio = 0.75
    elif hour in EVENING_OUTBOUND_HOURS:
        inbound_ratio = 0.25
    else:
        inbound_ratio = 0.50

    inbound_volume  = vehicle_count * inbound_ratio
    outbound_volume = vehicle_count * (1 - inbound_ratio)

    dominant_volume  = max(inbound_volume, outbound_volume)
    secondary_volume = max(min(inbound_volume, outbound_volume), 1.0)
    asymmetry_ratio  = dominant_volume / secondary_volume
    direction        = 'inbound' if inbound_volume >= outbound_volume else 'outbound'

    if (asymmetry_ratio < TIDAL_ASYMMETRY_THRESHOLD
            or zone not in TIDAL_ELIGIBLE_ZONES
            or total_lanes < TIDAL_MIN_TOTAL_LANES):
        if zone not in TIDAL_ELIGIBLE_ZONES:
            reason = f'{zone} is not configured for tidal flow control.'
        elif total_lanes < TIDAL_MIN_TOTAL_LANES:
            reason = f'{zone} has only {total_lanes} lanes — minimum {TIDAL_MIN_TOTAL_LANES} required for reversal.'
        else:
            reason = f'Directional asymmetry {asymmetry_ratio:.2f}x is below the {TIDAL_ASYMMETRY_THRESHOLD}x threshold.'
        return {
            'recommended'    : False,
            'zone'           : zone,
            'hour'           : hour,
            'asymmetry_ratio': round(asymmetry_ratio, 3),
            'direction'      : direction,
            'reason'         : reason,
        }

    lanes_to_reverse    = min(int(total_lanes * 0.25), 1)
    throughput_gain_pct = round((lanes_to_reverse / total_lanes) * 100, 1)
    rationale = (
        f'{zone} {direction} demand is {asymmetry_ratio:.2f}x the opposing direction at hour {hour}. '
        f'Reversing {lanes_to_reverse} lane(s) increases {direction} capacity by {throughput_gain_pct}% '
        f'with zero construction cost.'
    )

    return {
        'recommended'        : True,
        'zone'                : zone,
        'hour'                : hour,
        'lanes_to_reverse'    : lanes_to_reverse,
        'asymmetry_ratio'     : round(asymmetry_ratio, 3),
        'direction'           : direction,
        'throughput_gain_pct' : throughput_gain_pct,
        'rationale'           : rationale,
    }



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


def compute_emissions(
    congestion_level_str: str,
    vehicle_count: float,
    duration_hours: float = 1.0,
) -> Dict:
    """
    Estimate fuel consumption and CO2 emissions for a zone.

    Formula:
    - fuel_litres = FUEL_CONSUMPTION_LPH[level] * (vehicle_count / 100) * duration
    - co2_kg      = fuel_litres * CO2_KG_PER_LITRE
    - co2_tonnes  = co2_kg / 1000

    Returns
    -------
    dict with fuel_litres, co2_kg, co2_tonnes
    """
    from src.config import FUEL_CONSUMPTION_LPH, CO2_KG_PER_LITRE

    rate         = FUEL_CONSUMPTION_LPH.get(congestion_level_str, FUEL_CONSUMPTION_LPH['Low'])
    fuel_litres  = rate * (vehicle_count / 100) * duration_hours
    co2_kg       = fuel_litres * CO2_KG_PER_LITRE
    co2_tonnes   = co2_kg / 1000

    return {
        'fuel_litres': round(fuel_litres, 4),
        'co2_kg'     : round(co2_kg, 4),
        'co2_tonnes' : round(co2_tonnes, 6),
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


def log_prediction(prediction: Dict, explanation: Dict, log_path: str = 'predictions_log.csv', interval_width: float = None):
    """
    Append a prediction and its explanation to the audit log CSV.
    """
    import os
    from datetime import datetime

    row = {
        'timestamp'       : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'city'            : prediction.get('city'),
        'zone'            : prediction.get('zone'),
        'hour'            : prediction.get('hour'),
        'weather'         : prediction.get('weather'),
        'congestion_score': prediction.get('congestion_score'),
        'congestion_level': prediction.get('congestion_level'),
        'top_factor_1'    : explanation['top_factors'][0]['factor'] if len(explanation['top_factors']) > 0 else '',
        'top_factor_2'    : explanation['top_factors'][1]['factor'] if len(explanation['top_factors']) > 1 else '',
        'top_factor_3'    : explanation['top_factors'][2]['factor'] if len(explanation['top_factors']) > 2 else '',
        'plain_english'   : explanation.get('plain_english', ''),
        'co2_kg'          : prediction.get('emissions', {}).get('co2_kg', ''),
        'fuel_litres'     : prediction.get('emissions', {}).get('fuel_litres', ''),
        'interval_width'  : interval_width if interval_width is not None else '',
    }

    log_df     = pd.DataFrame([row])
    write_header = not os.path.exists(log_path)
    log_df.to_csv(log_path, mode='a', header=write_header, index=False)


def estimate_response_time(
    origin_zone: str,
    target_zone: str,
    congestion_level: str,
    city: str = 'Riyadh',
) -> Dict:
    """
    Estimate emergency vehicle travel time between two zones.

    Parameters
    ----------
    origin_zone      : Zone where the emergency station is located.
    target_zone      : Zone where the incident occurred.
    congestion_level : Current congestion level on the route.
    city             : City name (for context in warnings).

    Returns
    -------
    dict with distance_km, estimated_minutes, congestion_impact, warning.
    """
    from src.config import (
        ZONE_DISTANCES_KM, EMERGENCY_SPEED_KMPH, WHO_RESPONSE_THRESHOLD_MINS
    )

    BASE_OVERHEAD_MINS = 2.0

    if origin_zone == target_zone:
        return {
            'origin_zone'       : origin_zone,
            'target_zone'       : target_zone,
            'distance_km'       : 0.0,
            'estimated_minutes' : round(BASE_OVERHEAD_MINS, 1),
            'congestion_impact' : congestion_level,
            'warning'           : None,
        }

    key         = tuple(sorted([origin_zone, target_zone]))
    distance_km = ZONE_DISTANCES_KM.get(key)

    if distance_km is None:
        distance_km = float(
            sum(ZONE_DISTANCES_KM.values()) / len(ZONE_DISTANCES_KM)
        )

    speed_kmph  = EMERGENCY_SPEED_KMPH.get(congestion_level, 60)
    travel_mins = (distance_km / speed_kmph) * 60
    total_mins  = round(travel_mins + BASE_OVERHEAD_MINS, 1)

    warning = None
    if total_mins > WHO_RESPONSE_THRESHOLD_MINS:
        warning = (
            f"Response time {total_mins} min exceeds WHO "
            f"{WHO_RESPONSE_THRESHOLD_MINS}-min threshold. "
            f"Consider dispatching from nearest available unit."
        )

    return {
        'origin_zone'       : origin_zone,
        'target_zone'       : target_zone,
        'distance_km'       : round(distance_km, 1),
        'estimated_minutes' : total_mins,
        'congestion_impact' : congestion_level,
        'warning'           : warning,
    }



def get_delivery_windows(city: str, zone: str, df: pd.DataFrame) -> Dict:
    """
    Recommend optimal freight delivery windows for a zone.

    Logic:
    - Find hours where mean congestion_score < 0.35 for that zone
    - Exclude FREIGHT_RESTRICTED_HOURS for that city/zone
    - Exclude Friday prayer window (12–13) for Saudi cities
    - Return recommended windows, hours to avoid, best single hour, rationale

    Parameters
    ----------
    city : City name.
    zone : Zone name.
    df   : Full traffic DataFrame for that city (from app.state.city_dfs).

    Returns
    -------
    dict with recommended_windows, avoid_hours, best_hour, rationale.
    """
    from src.config import FREIGHT_RESTRICTED_HOURS, FRIDAY_PRAYER_HOURS, SAUDI_CITIES

    zone_df = df[df['zone'] == zone]

    hourly_congestion = (
        zone_df.groupby('hour')['congestion_score'].mean().to_dict()
    )

    restricted = set(
        FREIGHT_RESTRICTED_HOURS
        .get(city, {})
        .get(zone, [])
    )

    if city in SAUDI_CITIES:
        for h in FRIDAY_PRAYER_HOURS:
            restricted.add(h)

    recommended_windows = sorted([
        h for h, score in hourly_congestion.items()
        if score < 0.35 and h not in restricted
    ])

    avoid_hours = sorted(list(restricted))

    if recommended_windows:
        best_hour = min(
            recommended_windows,
            key=lambda h: hourly_congestion.get(h, 1.0)
        )
        rationale = (
            f"Hour {best_hour:02d}:00 has the lowest average congestion "
            f"({hourly_congestion.get(best_hour, 0):.3f}) outside restricted windows."
        )
    else:
        best_hour = None
        rationale = (
            "No unrestricted low-congestion window found. "
            "Consider early morning (02:00–05:00) or negotiate access."
        )

    return {
        'recommended_windows': recommended_windows,
        'avoid_hours'        : avoid_hours,
        'best_hour'          : best_hour,
        'rationale'          : rationale,
    }

def compute_prediction_interval(
    model,
    X_row: pd.DataFrame,
    feature_cols: list,
    df: pd.DataFrame,
    zone: str,
    n_bootstrap: int = 50,
) -> Dict:
    """
    Estimate a 90% prediction interval for a single inference using bootstrap.

    Resamples a subsample of the training data n_bootstrap times, trains
    a lightweight XGBoost on each, predicts for X_row, and returns the
    5th and 95th percentile of the prediction distribution.

    Parameters
    ----------
    model        : Trained XGBoost model (used for feature column reference only).
    X_row        : Single-row DataFrame prepared for inference.
    feature_cols : Feature column list from prepare_features().
    df           : Full city DataFrame (source of bootstrap samples).
    zone         : Zone name to filter bootstrap samples.
    n_bootstrap  : Number of bootstrap iterations (default 50).

    Returns
    -------
    dict with lower_bound, upper_bound, confidence_width, confidence_level.
    """
    from src.data import apply_hourly_patterns, add_lag_features

    zone_df = df[df['zone'] == zone].copy()

    if len(zone_df) < 20:
        score = float(model.predict(X_row)[0])
        return {
            'lower_bound'      : round(max(0.0, score - 0.05), 4),
            'upper_bound'      : round(min(1.0, score + 0.05), 4),
            'confidence_width' : 0.10,
            'confidence_level' : '90%',
        }

    available = [f for f in feature_cols if f in zone_df.columns]
    if 'congestion_score' not in zone_df.columns:
        return {
            'lower_bound'      : 0.0,
            'upper_bound'      : 1.0,
            'confidence_width' : 1.0,
            'confidence_level' : '90%',
        }

    X_pool = zone_df[available].copy()
    X_pool = X_pool.apply(pd.to_numeric, errors='coerce').fillna(0)

    y_pool = zone_df['congestion_score'].copy()

    sample_size = min(200, len(X_pool))
    preds       = []

    for _ in range(n_bootstrap):
        idx     = np.random.choice(len(X_pool), size=sample_size, replace=True)
        X_b     = X_pool.iloc[idx]
        X_b = X_b.apply(pd.to_numeric, errors='coerce').fillna(0)

        y_b     = y_pool.iloc[idx]

        boot_model = xgb.XGBRegressor(
            n_estimators = 50,
            max_depth    = 4,
            learning_rate= 0.1,
            subsample    = 0.8,
            random_state = np.random.randint(0, 10000),
            verbosity    = 0,
        )
        boot_model.fit(X_b, y_b, verbose=False)
        pred = float(boot_model.predict(X_row[available])[0])
        preds.append(np.clip(pred, 0.0, 1.0))

    lower = round(float(np.percentile(preds, 5)),  4)
    upper = round(float(np.percentile(preds, 95)), 4)
    width = round(upper - lower, 4)

    return {
        'lower_bound'      : lower,
        'upper_bound'      : upper,
        'confidence_width' : width,
        'confidence_level' : '90%',
    }



def compute_speed_degradation_index(
    avg_speed: float,
    road_type: str,
    weather:   str,
) -> Dict:
    """
    Compute the Speed Degradation Index (SDI) and HCM Level of Service.

    SDI = (free_flow_speed - avg_speed) / free_flow_speed, clipped to [0, 1].
    LOS classification follows the Highway Capacity Manual thresholds.

    Parameters
    ----------
    avg_speed : Current average speed in km/h.
    road_type : One of highway, arterial, local.
    weather   : Current weather condition (used for context in output only).

    Returns
    -------
    dict with sdi, level_of_service, free_flow_speed, current_speed, speed_loss_kmph.
    """
    from src.config import FREE_FLOW_SPEED_KMPH

    free_flow   = FREE_FLOW_SPEED_KMPH.get(road_type, 70)
    sdi         = float(np.clip((free_flow - avg_speed) / free_flow, 0.0, 1.0))
    speed_loss  = round(max(0.0, free_flow - avg_speed), 1)

    if   sdi < 0.10: los = 'A'
    elif sdi < 0.20: los = 'B'
    elif sdi < 0.35: los = 'C'
    elif sdi < 0.50: los = 'D'
    elif sdi < 0.70: los = 'E'
    else           : los = 'F'

    return {
        'sdi'             : round(sdi, 4),
        'level_of_service': los,
        'free_flow_speed' : free_flow,
        'current_speed'   : round(float(avg_speed), 1),
        'speed_loss_kmph' : speed_loss,
    }


def compute_pedestrian_risk(
    vehicle_count: float,
    avg_speed:     float,
    hour:          int,
    weather:       str,
    road_type:     str,
) -> Dict:
    """
    Score pedestrian danger for a zone based on traffic and environmental features.

    Base risk = (vehicle_count / 500) * (avg_speed / 100)
    Multipliers applied in order: road_type, time-of-day, weather, prayer window.
    Result clipped to [0.0, 1.0].

    Risk categories:
      Safe      < 0.25
      Moderate  0.25–0.50
      Dangerous 0.50–0.75
      Critical  > 0.75

    Parameters
    ----------
    vehicle_count : Number of vehicles in the zone.
    avg_speed     : Average speed in km/h.
    hour          : Hour of day (0–23).
    weather       : Weather condition string.
    road_type     : One of 'highway', 'arterial', 'local'.

    Returns
    -------
    dict with pedestrian_risk_score, risk_category, primary_hazard.
    """
    base_risk = (vehicle_count / 500.0) * (avg_speed / 100.0)

    road_multipliers = {'highway': 1.4, 'arterial': 1.0, 'local': 0.8}
    base_risk *= road_multipliers.get(road_type, 1.0)

    if hour in [21, 22, 23]:
        base_risk *= 1.3
        time_hazard = 'late_night_high_speed'
    elif hour in [7, 8, 17, 18]:
        base_risk *= 1.1
        time_hazard = 'rush_hour_volume'
    else:
        time_hazard = None

    weather_multipliers = {
        'sandstorm': 1.5,
        'fog'      : 1.3,
        'rain'     : 1.3,
        'dust'     : 1.2,
        'humid'    : 1.0,
        'clear'    : 1.0,
    }
    base_risk *= weather_multipliers.get(weather, 1.0)

    if hour in [12, 13]:
        base_risk *= 0.6
        time_hazard = 'prayer_window_low_traffic'

    score = float(np.clip(base_risk, 0.0, 1.0))

    if   score < 0.25: category = 'Safe'
    elif score < 0.50: category = 'Moderate'
    elif score < 0.75: category = 'Dangerous'
    else:              category = 'Critical'

    if weather in ('sandstorm', 'fog', 'rain'):
        primary_hazard = f'{weather}_visibility_reduction'
    elif time_hazard:
        primary_hazard = time_hazard
    elif road_type == 'highway':
        primary_hazard = 'high_speed_road'
    else:
        primary_hazard = 'vehicle_volume'

    return {
        'pedestrian_risk_score': round(score, 4),
        'risk_category'        : category,
        'primary_hazard'       : primary_hazard,
    }




def compute_last_mile_index(
    vehicle_count:    float,
    active_scooters:  int,
    active_bikes:     int,
    congestion_level: str,
    zone:             str,
) -> float:
    """
    Score last-mile modal shift efficiency for a zone.

    Base score = (active_scooters + active_bikes) / max(vehicle_count, 1).
    A bonus of +0.15 is added when the zone is a designated transfer hub
    and congestion is High or Critical — indicating micro-mobility is
    absorbing demand that would otherwise worsen congestion.

    Returns float clipped to [0.0, 1.0]. Higher = better modal shift.
    """
    from src.config import LAST_MILE_TRANSFER_ZONES

    base_score = (active_scooters + active_bikes) / max(vehicle_count, 1.0)

    if zone in LAST_MILE_TRANSFER_ZONES and congestion_level in ('High', 'Critical'):
        base_score += 0.15

    return round(float(np.clip(base_score, 0.0, 1.0)), 4)



def compute_pavement_wear_index(
    vehicle_count:      float,
    congestion_score:   float,
    temperature_celsius: float,
    heavy_vehicle_pct:  float = 0.10,
) -> Dict:
    """
    Estimate pavement wear index for a zone based on traffic load and heat.

    Formula
    -------
    base_wear    = vehicle_count * (1 + heavy_vehicle_pct * PAVEMENT_WEAR_COEFFICIENT_HEAVY)
    heat_mult    = BASE_HEAT_DEGRADATION_FACTOR if temp > HEAT_THRESHOLD_CELSIUS else 1.0
    wear_index   = (base_wear * congestion_score * heat_mult) / 100
    intervention = max(1, int(100 / max(wear_index, 0.1)))

    Parameters
    ----------
    vehicle_count        : Number of vehicles in the zone.
    congestion_score     : Current congestion score 0–1.
    temperature_celsius  : Current air temperature in Celsius.
    heavy_vehicle_pct    : Fraction of heavy vehicles (default 0.10).

    Returns
    -------
    dict with wear_index, risk_level, maintenance_priority,
    estimated_months_to_intervention.
    """
    from src.config import (
        PAVEMENT_WEAR_COEFFICIENT_HEAVY,
        BASE_HEAT_DEGRADATION_FACTOR,
        HEAT_THRESHOLD_CELSIUS,
        PAVEMENT_RISK_THRESHOLDS,
    )

    base_wear     = vehicle_count * (1 + heavy_vehicle_pct * PAVEMENT_WEAR_COEFFICIENT_HEAVY)
    heat_mult     = BASE_HEAT_DEGRADATION_FACTOR if temperature_celsius > HEAT_THRESHOLD_CELSIUS else 1.0
    wear_index    = round((base_wear * congestion_score * heat_mult) / 100, 3)
    months        = max(1, int(100 / max(wear_index, 0.1)))

    if   wear_index < PAVEMENT_RISK_THRESHOLDS['Low']     : risk = 'Low'
    elif wear_index < PAVEMENT_RISK_THRESHOLDS['Moderate'] : risk = 'Moderate'
    elif wear_index < PAVEMENT_RISK_THRESHOLDS['High']     : risk = 'High'
    else                                                   : risk = 'Critical'

    priority_map = {
        'Low'     : 'Schedule routine inspection',
        'Moderate': 'Plan preventive maintenance within 3 months',
        'High'    : 'Schedule resurfacing within 1 month',
        'Critical': 'URGENT: Immediate structural assessment required',
    }

    return {
        'wear_index'                      : wear_index,
        'risk_level'                      : risk,
        'maintenance_priority'            : priority_map[risk],
        'estimated_months_to_intervention': months,
        'heat_factor_applied'             : heat_mult > 1.0,
        'temperature_celsius'             : round(temperature_celsius, 1),
    }



def compute_cooperative_route(
    origin_zone:      str,
    destination_zone: str,
    congestion_map:   Dict[str, float],
    penetration_rate: float = 0.30,
) -> Dict:
    """
    Simulate V2X cooperative routing between two zones.

    Uses weighted Dijkstra where edge_weight = congestion_score
    of the destination zone * (1 / penetration_rate).
    Selfish route is computed at penetration_rate=0.01 (near-zero
    cooperation) to represent individual Waze-style routing.

    Parameters
    ----------
    origin_zone      : Starting zone string e.g. 'Zone_1'.
    destination_zone : Target zone string.
    congestion_map   : {zone: congestion_score} for all zones.
    penetration_rate : Fraction of V2X-enabled vehicles (0–1).

    Returns
    -------
    dict with route, total_weight, selfish_route, selfish_weight,
    improvement_pct.
    """
    import heapq
    from src.config import ZONE_ADJACENCY

    def _dijkstra(origin: str, destination: str, rate: float) -> tuple:
        """Return (total_weight, path) using weighted Dijkstra."""
        heap     = [(0.0, origin, [origin])]
        visited  = set()

        while heap:
            cost, node, path = heapq.heappop(heap)
            if node in visited:
                continue
            visited.add(node)
            if node == destination:
                return cost, path
            for neighbour in ZONE_ADJACENCY.get(node, []):
                if neighbour not in visited:
                    edge_weight = congestion_map.get(neighbour, 0.1) / max(rate, 0.01)
                    heapq.heappush(heap, (cost + edge_weight, neighbour, path + [neighbour]))

        return float('inf'), []

    coop_weight,   coop_route    = _dijkstra(origin_zone, destination_zone, penetration_rate)
    selfish_weight, selfish_route = _dijkstra(origin_zone, destination_zone, 0.01)

    if selfish_weight > 0:
        improvement_pct = round(
            (selfish_weight - coop_weight) / selfish_weight * 100, 2
        )
    else:
        improvement_pct = 0.0

    return {
        'route'          : coop_route,
        'total_weight'   : round(coop_weight, 4),
        'selfish_route'  : selfish_route,
        'selfish_weight' : round(selfish_weight, 4),
        'improvement_pct': improvement_pct,
    }

    
def predict_ev_charger_demand(
    station_id:             str,
    arrival_rate_per_hour:  float,
    current_active_chargers: int,
) -> Dict:
    """
    Estimate grid load and queue wait time for an EV fast-charge station.

    grid_load     = (current_active_chargers * CHARGE_RATE_KW) /
                    station['grid_capacity_kw']
    queue_minutes = max(0, (arrival_rate_per_hour - station['chargers']) * 5)
    overload_risk = grid_load > PEAK_GRID_LOAD_THRESHOLD

    recommended_redirect_to is the station with the lowest grid_load_pct
    among all stations excluding station_id.

    Parameters
    ----------
    station_id              : Key from EV_FAST_CHARGING_STATIONS.
    arrival_rate_per_hour   : Vehicles arriving per hour.
    current_active_chargers : Number of chargers currently in use.

    Returns
    -------
    dict with station_id, grid_load_pct, queue_minutes,
    overload_risk, recommended_redirect_to.
    """
    from src.config import EV_FAST_CHARGING_STATIONS, CHARGE_RATE_KW, PEAK_GRID_LOAD_THRESHOLD

    station = EV_FAST_CHARGING_STATIONS.get(station_id)
    if station is None:
        raise ValueError(f"Unknown station_id '{station_id}'.")

    grid_load     = (current_active_chargers * CHARGE_RATE_KW) / station['grid_capacity_kw']
    grid_load     = round(float(np.clip(grid_load, 0.0, 1.0)), 4)
    queue_minutes = max(0, (arrival_rate_per_hour - station['chargers']) * 5)
    overload_risk = grid_load > PEAK_GRID_LOAD_THRESHOLD

    other_loads = {}
    for sid, sdata in EV_FAST_CHARGING_STATIONS.items():
        if sid == station_id:
            continue
        assumed_active  = sdata['chargers'] * 0.5
        other_load      = (assumed_active * CHARGE_RATE_KW) / sdata['grid_capacity_kw']
        other_loads[sid] = round(float(other_load), 4)

    recommended_redirect_to = min(other_loads, key=other_loads.get) if other_loads else None

    return {
        'station_id'              : station_id,
        'grid_load_pct'           : grid_load,
        'queue_minutes'           : int(queue_minutes),
        'overload_risk'           : overload_risk,
        'recommended_redirect_to' : recommended_redirect_to,
    }



def calculate_dynamic_toll(zone: str, congestion_score: float, vehicle_type: str = 'passenger') -> float:
    """Return dynamic toll in SAR for a zone and vehicle type."""
    from src.config import (TOLL_EXEMPT_VEHICLES, TOLLED_ZONES,
                            BASE_TOLL_RATE_SAR, TOLL_CONGESTION_MULTIPLIER,
                            MAX_DYNAMIC_TOLL_SAR)
    if vehicle_type in TOLL_EXEMPT_VEHICLES:
        return 0.0
    if zone not in TOLLED_ZONES:
        return 0.0
    toll = BASE_TOLL_RATE_SAR * (1 + congestion_score * TOLL_CONGESTION_MULTIPLIER)
    return round(min(toll, MAX_DYNAMIC_TOLL_SAR), 2)


def evaluate_transit_priority(bus_distance_m: float,
                               current_green_remaining_s: float,
                               passenger_count: int) -> dict:
    """Return TSP green extension decision."""
    from src.config import (TSP_DETECTION_RANGE_M, TSP_MIN_PASSENGER_COUNT,
                            BUS_PRIORITY_WEIGHT, TSP_GREEN_EXTENSION_MAX_S)
    if bus_distance_m > TSP_DETECTION_RANGE_M:
        return {
            'extension_granted_s': 0,
            'priority_score': 0.0,
            'phase_change_requested': False,
            'rationale': 'Bus outside detection range',
        }
    if passenger_count < TSP_MIN_PASSENGER_COUNT:
        return {
            'extension_granted_s': 0,
            'priority_score': 0.0,
            'phase_change_requested': False,
            'rationale': 'Passenger count below TSP threshold',
        }
    priority_score = (passenger_count * BUS_PRIORITY_WEIGHT) / max(bus_distance_m, 1)
    extension_s    = min(int(priority_score), TSP_GREEN_EXTENSION_MAX_S)
    return {
        'extension_granted_s':    extension_s,
        'priority_score':         round(priority_score, 3),
        'phase_change_requested': bus_distance_m < 50,
        'rationale': f'{passenger_count} passengers at {bus_distance_m:.0f}m — {extension_s}s extension granted',
    }



def compute_vsl_limit(
    weather:        str,
    visibility_m:   float,
    avg_speed_kmph: float,
) -> Dict:
    """
    Recommend a variable speed limit for a highway zone based on
    current visibility and weather conditions.
 
    Visibility-based reduction steps:
    - clear weather and visibility > VISIBILITY_CLEAR_THRESHOLD_M (1000m):
      VSL_DEFAULT_SPEED_KMPH (120)
    - visibility < 1000m: 100
    - visibility < 500m : 80
    - visibility < 300m : 60
    - visibility < 200m : VSL_MINIMUM_SPEED_KMPH (40)
 
    Result is floored to the nearest VSL_STEP_SIZE_KMPH and never goes
    below VSL_MINIMUM_SPEED_KMPH.
 
    Parameters
    ----------
    weather        : Current weather condition string.
    visibility_m   : Current visibility in metres.
    avg_speed_kmph : Current average zone speed — included in the
                     response for operator context.
 
    Returns
    -------
    dict with recommended_speed_kmph, reduction_reason, warning_message,
    enforcement_recommended, current_avg_speed_kmph.
    """
    from src.config import (
        VSL_DEFAULT_SPEED_KMPH, VSL_MINIMUM_SPEED_KMPH, VSL_STEP_SIZE_KMPH,
        VISIBILITY_CLEAR_THRESHOLD_M,
    )
 
    if weather == 'clear' and visibility_m > VISIBILITY_CLEAR_THRESHOLD_M:
        recommended = VSL_DEFAULT_SPEED_KMPH
        reason      = 'Clear visibility — default highway limit applies'
    elif visibility_m < 200:
        recommended = VSL_MINIMUM_SPEED_KMPH
        reason      = f'Extreme low visibility ({visibility_m:.0f}m) — minimum safe speed'
    elif visibility_m < 300:
        recommended = 60
        reason      = f'Severe visibility reduction ({visibility_m:.0f}m) — sandstorm/fog protocol'
    elif visibility_m < 500:
        recommended = 80
        reason      = f'Significant visibility reduction ({visibility_m:.0f}m)'
    elif visibility_m < VISIBILITY_CLEAR_THRESHOLD_M:
        recommended = 100
        reason      = f'Reduced visibility ({visibility_m:.0f}m)'
    else:
        recommended = VSL_DEFAULT_SPEED_KMPH
        reason      = 'Visibility within normal range'
 
    recommended = (int(recommended) // VSL_STEP_SIZE_KMPH) * VSL_STEP_SIZE_KMPH
    recommended = max(VSL_MINIMUM_SPEED_KMPH, recommended)
 
    reduction                = VSL_DEFAULT_SPEED_KMPH - recommended
    enforcement_recommended  = reduction > 40
 
    if recommended < VSL_DEFAULT_SPEED_KMPH:
        warning_message = f'Reduce speed to {recommended} km/h — {reason.lower()}.'
    else:
        warning_message = 'Normal highway speed limit in effect.'
 
    return {
        'recommended_speed_kmph' : recommended,
        'reduction_reason'       : reason,
        'warning_message'        : warning_message,
        'enforcement_recommended': enforcement_recommended,
        'current_avg_speed_kmph' : round(float(avg_speed_kmph), 1),
    }
 


def estimate_noise_level(
    vehicle_count: int,
    avg_speed: float,
    road_type: str,
    hour: int,
) -> dict:
    """
    PROMPT 041 — Estimates traffic noise in dB per zone.
    Based on simplified FHWA TNM inputs: volume, speed, road class.
    WHO daytime limit: 53 dB.
    """
    night_hours    = list(range(23, 24)) + list(range(0, 6))
    night_reduction = -5.0 if hour in night_hours else 0.0

    noise_db = (
        NOISE_BASE_DB
        + vehicle_count * NOISE_VEHICLE_COEFFICIENT
        + avg_speed     * NOISE_SPEED_COEFFICIENT
        + NOISE_ROAD_TYPE_PREMIUM.get(road_type, 0.0)
        + night_reduction
    )
    noise_db = round(min(noise_db, 95.0), 1)

    # Classify using thresholds (ascending)
    noise_level = "Acceptable"
    for level, threshold in sorted(NOISE_THRESHOLDS.items(),
                                   key=lambda x: x[1]):
        if noise_db >= threshold:
            noise_level = level

    return {
        "noise_db"             : noise_db,
        "noise_level"          : noise_level,
        "who_guideline_exceeded": noise_db > 53.0,
    }



# ===== – Pedestrian crosswalk timing =====

def compute_crosswalk_timing(
    zone: str,
    hour: int,
    congestion_score: float,
    schedule: str = 'standard',
) -> Dict:
    """
    Recommend dynamic pedestrian crosswalk walk time based on schedule context.

    Parameters
    ----------
    zone              : Zone identifier (used for context only, not in formula).
    hour              : Hour of day (0–23).
    congestion_score  : Current congestion score (0–1) for the zone.
    schedule          : 'standard' | 'friday_prayer' | 'hajj' | 'event'

    Returns
    -------
    dict with walk_time_s, crowd_factor, schedule_used, mutcd_compliant.
    """
    from src.config import (
        PEDESTRIAN_BASE_WALK_TIME_S,
        PEDESTRIAN_MAX_WALK_TIME_S,
        PEDESTRIAN_CLEARANCE_MIN_S,
        PEDESTRIAN_CROWD_MULTIPLIER,
    )

    # Determine crowd factor
    crowd_factor = PEDESTRIAN_CROWD_MULTIPLIER if schedule in ('friday_prayer', 'hajj', 'event') else 1.0

    base_time = PEDESTRIAN_BASE_WALK_TIME_S * crowd_factor
    congestion_adjustment = congestion_score * 10
    walk_time = base_time + congestion_adjustment

    # Clamp to allowed range
    walk_time = max(walk_time, PEDESTRIAN_CLEARANCE_MIN_S)
    walk_time = min(walk_time, PEDESTRIAN_MAX_WALK_TIME_S)

    return {
        'walk_time_s': round(walk_time, 1),
        'crowd_factor': round(crowd_factor, 2),
        'schedule_used': schedule,
        'mutcd_compliant': walk_time >= PEDESTRIAN_CLEARANCE_MIN_S,
    }




# ===== – Extreme Heat Infrastructure Risk Assessment =====

def compute_thermal_risk(
    air_temp_celsius: float,
    weather: str,
    road_type: str,
) -> Dict:
    """
    Estimate asphalt surface temperature and thermal risk for a zone.

    Surface temperature = air_temp + offset (12°C) with adjustments:
    - Sandstorm: -3°C (dust reduces solar absorption)
    - Highway: +2°C (darker surface absorbs more heat)
    - Other road types: no adjustment

    Risk score is the proportion above the critical asphalt temperature (55°C),
    capped at 1.0. Maintenance alert triggered when surface_temp > 55°C.

    Parameters
    ----------
    air_temp_celsius : Current air temperature in Celsius.
    weather          : Weather condition string (e.g., 'clear', 'sandstorm').
    road_type        : One of 'highway', 'arterial', 'local'.

    Returns
    -------
    dict with surface_temp_celsius, air_temp_celsius, risk_score,
         risk_level, maintenance_alert.
    """
    from src.config import SURFACE_TEMP_OFFSET_CELSIUS, ASPHALT_CRITICAL_TEMP_CELSIUS, HEAT_RISK_THRESHOLDS

    # Start with offset
    surface_temp = air_temp_celsius + SURFACE_TEMP_OFFSET_CELSIUS

    # Weather adjustment
    if weather == 'sandstorm':
        surface_temp -= 3.0   # dust reduces solar absorption

    # Road type adjustment
    if road_type == 'highway':
        surface_temp += 2.0   # darker asphalt absorbs more heat

    # Risk score: how far above critical temperature
    risk_score = max(0.0, (surface_temp - ASPHALT_CRITICAL_TEMP_CELSIUS) / 10.0)
    risk_score = min(risk_score, 1.0)

    # Determine risk level
    if surface_temp < HEAT_RISK_THRESHOLDS['Low']:
        risk_level = 'Low'
    elif surface_temp < HEAT_RISK_THRESHOLDS['Elevated']:
        risk_level = 'Elevated'
    elif surface_temp < HEAT_RISK_THRESHOLDS['High']:
        risk_level = 'High'
    else:
        risk_level = 'Critical'

    maintenance_alert = surface_temp > ASPHALT_CRITICAL_TEMP_CELSIUS

    return {
        'surface_temp_celsius': round(surface_temp, 1),
        'air_temp_celsius': round(air_temp_celsius, 1),
        'risk_score': round(risk_score, 4),
        'risk_level': risk_level,
        'maintenance_alert': maintenance_alert,
    }