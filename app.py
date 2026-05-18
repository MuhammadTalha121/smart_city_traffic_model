from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, List
from src.model import predict_single

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
    Predict congestion score for a single zone and return
    level classification with operational recommendation.
    """
    try:
        return predict_single(
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
