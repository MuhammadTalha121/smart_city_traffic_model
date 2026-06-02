# Live Demo — Smart City Traffic Intelligence System

> A production-ready traffic prediction system for Vision 2030 smart cities.  
> Culturally calibrated to Saudi Arabia. Authenticated. Self-retraining.

---

## Live URLs

| Service | URL |
|---|---|
| API Documentation | https://smart-city-traffic-model.up.railway.app/docs |
| API Health Check | https://smart-city-traffic-model.up.railway.app/health |
| Dashboard | https://muhammadtalha121-smart-city-traffic.streamlit.app |

---

## Test the API in 60 Seconds

### 1. Health check — no key required
```powershell
Invoke-WebRequest -Uri "https://smart-city-traffic-model.up.railway.app/health"
```

### 2. Predict congestion — sandstorm scenario
```powershell
Invoke-WebRequest -Uri "https://smart-city-traffic-model.up.railway.app/predict" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{"X-API-Key" = "YOUR_KEY"} `
  -Body '{"city":"Riyadh","zone":"Zone_1","hour":8,"vehicle_count":320,"avg_speed":35,"weather":"sandstorm","road_type":"highway","rush_hour":1,"is_weekend":0,"is_late_night":0,"event":0,"hour_multiplier":1.4}'
```

### 3. Predict congestion — Friday prayer window
```powershell
Invoke-WebRequest -Uri "https://smart-city-traffic-model.up.railway.app/predict" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{"X-API-Key" = "YOUR_KEY"} `
  -Body '{"city":"Riyadh","zone":"Zone_1","hour":12,"vehicle_count":30,"avg_speed":80,"weather":"clear","road_type":"highway","rush_hour":0,"is_weekend":1,"is_late_night":0,"event":0,"hour_multiplier":0.1}'
```

### 4. Get current anomalies
```powershell
Invoke-WebRequest -Uri "https://smart-city-traffic-model.up.railway.app/anomalies?city=Riyadh" `
  -Headers @{"X-API-Key" = "YOUR_KEY"}
```

### 5. Get 1h / 2h / 3h forecast
```powershell
Invoke-WebRequest -Uri "https://smart-city-traffic-model.up.railway.app/forecast?city=Riyadh&zone=Zone_1" `
  -Headers @{"X-API-Key" = "YOUR_KEY"}
```

### 6. Check model drift score
```powershell
Invoke-WebRequest -Uri "https://smart-city-traffic-model.up.railway.app/pipeline/status" `
  -Headers @{"X-API-Key" = "YOUR_KEY"}
```

---

## What to Look For

**In the /predict response:**
- `congestion_score` — 0.0 to 1.0, zone-level congestion
- `congestion_level` — Low / Moderate / High / Critical
- `recommendation` — operational action for traffic operators
- `explanation` — top 3 SHAP factors driving the prediction
- `plain_english` — what's causing congestion in plain language

**Saudi-specific signals:**
- Send `hour: 12, is_weekend: 1` → Friday prayer drop, very low congestion
- Send `weather: sandstorm` → sandstorm protocol activates, Critical level
- Send `hour: 22, is_late_night: 1` → late-night Saudi activity pattern

**In the /pipeline/status response:**
- `drift_score: 1.0` — model is stable
- `needs_retrain: false` — no action needed
- `next_scheduled: 03:00 daily` — automatic nightly check

---

## What This System Does That Standard Systems Don't

| Standard System | This System |
|---|---|
| Reacts after congestion forms | Predicts 1–3 hours before |
| Western behavioral model | Friday prayer, Ramadan, sandstorm calibrated |
| Black box output | SHAP explanation on every prediction |
| Static model | Detects drift, retrains automatically at 3AM |
| Open endpoint | Authenticated, rate-limited API |

---

*Built by Muhammad Talha — [GitHub](https://github.com/MuhammadTalha121/smart_city_traffic_model)*
