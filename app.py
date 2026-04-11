"""
Smart City Traffic Intelligence API
====================================
Production FastAPI backend with XGBoost congestion prediction.
Trains model automatically on first startup if no saved model exists.
"""

import os
import json
import logging
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("traffic-api")

# ─── Constants ────────────────────────────────────────────────────────────────

MODEL_DIR = Path("saved_model")

CITY_PROFILES = {
    "Riyadh":   {"base_vehicles": 250, "speed_limit": 80, "zones": 5, "noise": 40},
    "Dubai":    {"base_vehicles": 300, "speed_limit": 100, "zones": 6, "noise": 35},
    "Karachi":  {"base_vehicles": 350, "speed_limit": 60, "zones": 7, "noise": 50},
}

WEATHER_SPEED_MULTIPLIERS = {
    "clear": 1.0, "rain": 0.75, "fog": 0.65, "sandstorm": 0.60,
}

ROAD_TYPE_SPEED = {"highway": 100, "arterial": 60, "collector": 45, "residential": 30}

HOURLY_MULTIPLIERS = {
    0: 0.15, 1: 0.10, 2: 0.08, 3: 0.07, 4: 0.08, 5: 0.15,
    6: 0.45, 7: 1.00, 8: 1.40, 9: 1.20, 10: 0.90, 11: 0.85,
    12: 0.60, 13: 0.95, 14: 1.00, 15: 1.10, 16: 1.30, 17: 1.50,
    18: 1.35, 19: 1.10, 20: 0.85, 21: 0.70, 22: 0.50, 23: 0.30,
}

FEATURE_COLS = [
    "hour", "vehicle_count", "avg_speed", "is_weekend", "is_late_night",
    "friday_prayer_drop", "is_ramadan", "rush_hour", "is_event",
    "hour_multiplier", "weather_encoded", "road_type_encoded", "city_encoded",
]


# ─── Pydantic schemas ────────────────────────────────────────────────────────

class PredictionInput(BaseModel):
    city: str = "Riyadh"
    zone: str = "Zone_1"
    hour: int = Field(8, ge=0, le=23)
    vehicle_count: int = Field(250, ge=0)
    avg_speed: float = Field(50.0, ge=0)
    weather: str = "clear"
    road_type: str = "arterial"
    rush_hour: int = Field(0, ge=0, le=1)
    is_weekend: int = Field(0, ge=0, le=1)
    is_late_night: int = Field(0, ge=0, le=1)
    event: int = Field(0, ge=0, le=1)
    hour_multiplier: float = Field(1.0, ge=0)
    is_ramadan: int = Field(0, ge=0, le=1)
    friday_prayer_drop: int = Field(0, ge=0, le=1)


class BatchInput(BaseModel):
    predictions: List[PredictionInput]


class PredictionOutput(BaseModel):
    city: str
    zone: str
    hour: int
    weather: str
    congestion_score: float
    congestion_level: str
    recommendation: str


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Smart City Traffic Intelligence API",
    description="Saudi-calibrated traffic congestion prediction for Vision 2030 smart cities.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state: dict = {}


# ─── Data & feature helpers ───────────────────────────────────────────────────

def generate_training_data(n_days=90, seed=42):
    np.random.seed(seed)
    records = []
    for day in range(n_days):
        dow = day % 7
        is_weekend = int(dow in [4, 5])
        for hour in range(24):
            hm = HOURLY_MULTIPLIERS[hour]
            base = CITY_PROFILES["Riyadh"]["base_vehicles"]
            vc = max(10, int(np.random.poisson(base * hm * (0.7 if is_weekend else 1.0))))
            weather = np.random.choice(
                ["clear", "rain", "fog", "sandstorm"], p=[0.70, 0.10, 0.10, 0.10],
            )
            road = np.random.choice(["highway", "arterial", "collector", "residential"])
            sl = ROAD_TYPE_SPEED[road]
            sp = max(5, sl * WEATHER_SPEED_MULTIPLIERS[weather] + np.random.normal(0, 10))
            rush = int(hour in [7, 8, 9, 16, 17, 18] and not is_weekend)
            ln = int(hour in [21, 22, 23])
            fp = int(hour == 12 and dow == 4)
            ev = int(np.random.random() < 0.02)
            cong = min(1.0, max(0.0,
                0.4 * (vc / (base * 1.5))
                + 0.3 * (1 - sp / sl)
                + 0.1 * rush
                + 0.1 * (1 - WEATHER_SPEED_MULTIPLIERS[weather])
                + 0.05 * ev
                - 0.2 * fp
                + np.random.normal(0, 0.05),
            ))
            records.append({
                "hour": hour, "vehicle_count": vc, "avg_speed": round(sp, 1),
                "weather": weather, "road_type": road, "is_weekend": is_weekend,
                "is_late_night": ln, "friday_prayer_drop": fp, "is_ramadan": 0,
                "rush_hour": rush, "is_event": ev, "hour_multiplier": hm,
                "city": "Riyadh", "congestion_score": round(cong, 3),
            })
    return pd.DataFrame(records)


def prepare_features(df):
    df = df.copy()
    w_map = {"clear": 0, "rain": 1, "fog": 2, "sandstorm": 3}
    r_map = {"highway": 0, "arterial": 1, "collector": 2, "residential": 3}
    c_map = {"Riyadh": 0, "Dubai": 1, "Karachi": 2}
    df["weather_encoded"] = df["weather"].map(w_map).fillna(0).astype(int)
    df["road_type_encoded"] = df["road_type"].map(r_map).fillna(1).astype(int)
    df["city_encoded"] = df["city"].map(c_map).fillna(0).astype(int)
    return df[FEATURE_COLS]


# ─── Training ─────────────────────────────────────────────────────────────────

def train_and_save():
    logger.info("Generating training data (90 days)…")
    df = generate_training_data()
    X = prepare_features(df)
    y = df["congestion_score"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42)
    scaler = StandardScaler().fit(Xtr)
    Xtr_s = scaler.transform(Xtr)
    Xte_s = scaler.transform(Xte)
    model = XGBRegressor(
        n_estimators=500, max_depth=6, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
        early_stopping_rounds=50,
    )
    model.fit(Xtr_s, ytr, eval_set=[(Xte_s, yte)], verbose=False)
    preds = model.predict(Xte_s)
    r2 = float(np.corrcoef(yte, preds)[0, 1] ** 2)
    rmse = float(np.sqrt(np.mean((yte - preds) ** 2)))
    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump(model, MODEL_DIR / "model.pkl")
    joblib.dump(scaler, MODEL_DIR / "scaler.pkl")
    (MODEL_DIR / "metadata.json").write_text(json.dumps({"r2": r2, "rmse": rmse}))
    logger.info(f"Model saved — R²={r2:.4f}  RMSE={rmse:.4f}")
    return model, scaler, {"r2": r2, "rmse": rmse}


# ─── Lifecycle ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    mp = MODEL_DIR / "model.pkl"
    sp = MODEL_DIR / "scaler.pkl"
    if mp.exists() and sp.exists():
        state["model"] = joblib.load(mp)
        state["scaler"] = joblib.load(sp)
        meta = json.loads((MODEL_DIR / "metadata.json").read_text())
        state["meta"] = meta
        logger.info(f"Loaded model — R²={meta['r2']:.4f}")
    else:
        logger.info("No saved model found — training now…")
        model, scaler, meta = train_and_save()
        state["model"] = model
        state["scaler"] = scaler
        state["meta"] = meta


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "model_loaded": "model" in state,
        "model_metrics": state.get("meta", {}),
    }


@app.post("/predict", response_model=PredictionOutput)
async def predict(inp: PredictionInput):
    if "model" not in state:
        raise HTTPException(503, "Model not loaded yet — training in progress.")
    row = pd.DataFrame([{
        "hour": inp.hour, "vehicle_count": inp.vehicle_count,
        "avg_speed": inp.avg_speed, "weather": inp.weather,
        "road_type": inp.road_type, "city": inp.city,
        "is_weekend": inp.is_weekend, "is_late_night": inp.is_late_night,
        "friday_prayer_drop": inp.friday_prayer_drop,
        "is_ramadan": inp.is_ramadan, "rush_hour": inp.rush_hour,
        "is_event": inp.event, "hour_multiplier": inp.hour_multiplier,
    }])
    X = state["scaler"].transform(prepare_features(row))
    score = float(np.clip(state["model"].predict(X)[0], 0, 1))
    if score <= 0.30:
        level = "Low"
    elif score <= 0.55:
        level = "Moderate"
    elif score <= 0.75:
        level = "High"
    else:
        level = "Critical"
    rec = _recommend(inp.zone, level, inp.weather)
    return PredictionOutput(
        city=inp.city, zone=inp.zone, hour=inp.hour,
        weather=inp.weather, congestion_score=round(score, 4),
        congestion_level=level, recommendation=rec,
    )


@app.post("/predict/batch")
async def predict_batch(batch: BatchInput):
    if len(batch.predictions) > 20:
        raise HTTPException(400, "Maximum 20 predictions per batch.")
    results = [await predict(p) for p in batch.predictions]
    return {"results": results}


def _recommend(zone, level, weather):
    sandstorm = weather == "sandstorm"
    if level == "Critical":
        r = f"ALERT: {zone} is critically congested."
        if sandstorm:
            r += " Sandstorm protocol active. Initiate emergency traffic management."
        else:
            r += " Deploy emergency traffic management immediately."
    elif level == "High":
        r = f"{zone} has high congestion. Deploy traffic officers to {zone}."
    elif level == "Moderate":
        r = f"{zone} has moderate congestion. Monitor for escalation."
    else:
        r = f"{zone} traffic is flowing normally. No action needed."
    return r
