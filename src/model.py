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
    'hour_multiplier', 'zone', 'day_of_week'
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
