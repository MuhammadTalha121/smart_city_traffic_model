# app.py
# Run locally: uvicorn app:app --reload
# Test: http://127.0.0.1:8000/docs

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
import numpy as np
import pandas as pd
import joblib
from typing import Literal


app = FastAPI(
    title       = "Smart City Traffic Intelligence API",
    description = "Predict congestion scores for any city zone in real time.",
    version     = "1.0.0"
)


# ── Request / Response Schemas ───────────────────────────────────────────────

class TrafficInput(BaseModel):
    city        : str                                          = Field(..., example="Riyadh")
    zone        : Literal["Zone_1","Zone_2","Zone_3","Zone_4","Zone_5"]
    hour        : int                                          = Field(..., ge=0, le=23)
    vehicle_count: float                                       = Field(..., ge=0, le=500)
    avg_speed   : float                                        = Field(..., ge=20, le=100)
    weather     : Literal["clear","sandstorm","dust","fog","rain","humid"]
    road_type   : Literal["highway","arterial","local"]
    rush_hour   : Literal[0, 1]
    is_weekend  : Literal[0, 1]
    is_late_night: Literal[0, 1]
    event       : Literal[0, 1]
    hour_multiplier: float                                     = Field(..., ge=0.0, le=2.0)

    @validator('hour')
    def validate_hour(cls, v):
        if not 0 <= v <= 23:
            raise ValueError('Hour must be between 0 and 23')
        return v


class CongestionOutput(BaseModel):
    city             : str
    zone             : str
    hour             : int
    weather          : str
    congestion_score : float
    congestion_level : str
    recommendation   : str


# ── Helper Functions ─────────────────────────────────────────────────────────

WEATHER_SPEED_IMPACT = {
    'sandstorm': 0.60, 'fog': 0.70, 'rain': 0.80,
    'dust': 0.85, 'humid': 0.95, 'clear': 1.00
}

ZONE_ENCODING = {
    'Zone_1': 0, 'Zone_2': 1, 'Zone_3': 2, 'Zone_4': 3, 'Zone_5': 4
}

WEATHER_ENCODING = {
    'clear': 0, 'dust': 1, 'fog': 2,
    'humid': 3, 'rain': 4, 'sandstorm': 5
}

ROAD_ENCODING = {
    'arterial': 0, 'highway': 1, 'local': 2
}


def compute_congestion_score(vehicle_count, avg_speed,
                             max_vehicles=500, max_speed=100):
    """Reproduce the congestion formula used during training."""
    return float(
        np.clip(
            (vehicle_count / max_vehicles) * (1 - avg_speed / max_speed),
            0, 1
        )
    )


def congestion_level(score):
    """Classify congestion score into human-readable level."""
    if score < 0.2:
        return 'Low'
    elif score < 0.4:
        return 'Moderate'
    elif score < 0.6:
        return 'High'
    else:
        return 'Critical'


def get_recommendation(level, zone, weather):
    """Return actionable recommendation based on congestion level."""
    recommendations = {
        'Low'     : f"{zone} is clear. Normal operations.",
        'Moderate': f"Monitor {zone}. Consider signal timing adjustments.",
        'High'    : f"Deploy traffic officers to {zone}. Activate alternate routes.",
        'Critical': f"ALERT: {zone} is critically congested. "
                    f"{'Sandstorm protocol active. ' if weather == 'sandstorm' else ''}"
                    f"Initiate emergency traffic management."
    }
    return recommendations[level]


def build_feature_vector(data: TrafficInput) -> pd.DataFrame:
    """Convert API input into model-ready feature vector."""
    return pd.DataFrame([{
        'hour'           : data.hour,
        'vehicle_count'  : data.vehicle_count,
        'avg_speed'      : data.avg_speed,
        'weather'        : WEATHER_ENCODING.get(data.weather, 0),
        'event'          : data.event,
        'road_type'      : ROAD_ENCODING.get(data.road_type, 0),
        'rush_hour'      : data.rush_hour,
        'is_weekend'     : data.is_weekend,
        'is_late_night'  : data.is_late_night,
        'hour_multiplier': data.hour_multiplier,
        'zone'           : ZONE_ENCODING.get(data.zone, 0),
        'day_of_week'    : 0
    }])


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "message": "Smart City Traffic Intelligence API",
        "docs"   : "/docs",
        "version": "1.0.0"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/predict", response_model=CongestionOutput)
def predict_congestion(data: TrafficInput):
    """
    Predict congestion score for a given zone and conditions.
    Returns score, level classification, and operational recommendation.
    """
    try:
        adjusted_speed = data.avg_speed * WEATHER_SPEED_IMPACT.get(data.weather, 1.0)
        score          = compute_congestion_score(data.vehicle_count, adjusted_speed)
        level          = congestion_level(score)
        recommendation = get_recommendation(level, data.zone, data.weather)

        return CongestionOutput(
            city             = data.city,
            zone             = data.zone,
            hour             = data.hour,
            weather          = data.weather,
            congestion_score = round(score, 4),
            congestion_level = level,
            recommendation   = recommendation
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/batch")
def predict_batch(inputs: list[TrafficInput]):
    """
    Predict congestion for multiple zones simultaneously.
    Useful for city-wide dashboard updates.
    """
    if len(inputs) > 20:
        raise HTTPException(
            status_code=400,
            detail="Batch limit is 20 records per request."
        )
    return [predict_congestion(item) for item in inputs]
