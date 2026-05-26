from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, List
from src.data  import generate_traffic_data, apply_hourly_patterns
from src.model import predict_single, detect_anomalies, forecast_congestion, explain_prediction, log_prediction

app = FastAPI(
    title       = "Smart City Traffic Intelligence API",
    description = "Real-time congestion prediction for Vision 2030 smart cities.",
    version     = "1.0.0"
)


class TrafficInput(BaseModel):
    city          : str                                                              = Field(..., example="Riyadh")
    zone          : Literal["Zone_1", "Zone_2", "Zone_3", "Zone_4", "Zone_5"]
    hour          : int                                                              = Field(..., ge=0, le=23)
    vehicle_count : float                                                            = Field(..., ge=0, le=500)
    avg_speed     : float                                                            = Field(..., ge=20, le=100)
    weather       : Literal["clear", "sandstorm", "dust", "fog", "rain", "humid"]
    road_type     : Literal["highway", "arterial", "local"]
    rush_hour     : Literal[0, 1]
    is_weekend    : Literal[0, 1]
    is_late_night : Literal[0, 1]
    event         : Literal[0, 1]
    hour_multiplier: float                                                           = Field(..., ge=0.0, le=2.0)


class CongestionOutput(BaseModel):
    city             : str
    zone             : str
    hour             : int
    weather          : str
    congestion_score : float
    congestion_level : str
    recommendation   : str


@app.get("/")
def root():
    return {
        "service": "Smart City Traffic Intelligence API",
        "version": "1.0.0",
        "docs"   : "/docs",
        "health" : "/health"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/predict", response_model=CongestionOutput)
def predict(data: TrafficInput):
    """
    Predict congestion score for a single zone.
    Returns level, recommendation, SHAP explanation, and plain English summary.
    Logs every prediction to predictions_log.csv.
    """
    try:
        from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features
        from src.config import HOURLY_MULTIPLIERS

        result = predict_single(
            city            = data.city,
            zone            = data.zone,
            hour            = data.hour,
            vehicle_count   = data.vehicle_count,
            avg_speed       = data.avg_speed,
            weather         = data.weather,
            road_type       = data.road_type,
            rush_hour       = data.rush_hour,
            is_weekend      = data.is_weekend,
            is_late_night   = data.is_late_night,
            event           = data.event,
            hour_multiplier = data.hour_multiplier
        )

        try:
            df          = apply_hourly_patterns(generate_traffic_data(city=data.city), city=data.city)
            df          = add_lag_features(df)
            X, y, feats = __import__('src.model', fromlist=['prepare_features']).prepare_features(df)
            xgb_model, _, _ = __import__('src.model', fromlist=['train_xgboost']).train_xgboost(X, y)
            sample      = X.iloc[[-1]]
            explanation = explain_prediction(xgb_model, sample, feats)
            log_prediction(result, explanation)
            result['explanation']   = explanation['top_factors']
            result['plain_english'] = explanation['plain_english']
        except Exception:
            result['explanation']   = []
            result['plain_english'] = 'Explanation unavailable.'

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/predict/batch")
def predict_batch(inputs: List[TrafficInput]):
    """
    Predict congestion for up to 20 zones simultaneously.
    Designed for city-wide dashboard updates.
    """
    if len(inputs) > 20:
        raise HTTPException(status_code=400, detail="Batch limit is 20 records per request.")
    return [predict(item) for item in inputs]


@app.get("/anomalies")
def get_anomalies(city: str = "Riyadh", n_days: int = 30):
    """
    Return all detected anomalies across all zones.
    Includes severity classification and recommended action.
    """
    try:
        df = generate_traffic_data(city=city, n_days=n_days)
        df = apply_hourly_patterns(df, city=city)
        df = detect_anomalies(df)

        anomalies = df[df['anomaly_flag'] == 1][[
            'zone', 'hour', 'weather',
            'expected_vehicle_count', 'vehicle_count',
            'anomaly_severity', 'anomaly_recommendation'
        ]].copy()

        anomalies['expected_vehicle_count'] = anomalies['expected_vehicle_count'].round(1)
        anomalies['vehicle_count']          = anomalies['vehicle_count'].round(1)

        return {
            "city"          : city,
            "total_anomalies": len(anomalies),
            "anomalies"     : anomalies.to_dict(orient='records')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/forecast")
def get_forecast(
    city   : str = "Riyadh",
    zone   : str = "Zone_1",
    n_days : int = 30
):
    """
    Forecast congestion 1h, 2h, and 3h ahead for a given zone.
    Returns predicted score, confidence interval, level, and recommendation.
    """
    try:
        from src.data import generate_traffic_data, apply_hourly_patterns
        df        = generate_traffic_data(city=city, n_days=n_days)
        df        = apply_hourly_patterns(df, city=city)
        forecasts = forecast_congestion(df, zone=zone, hours_ahead=[1, 2, 3])
        return {"city": city, "zone": zone, "forecasts": forecasts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))