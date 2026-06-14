# Smart City Traffic Intelligence — Integration Guide

---

## 1. Requesting API Access

Contact the system administrator to receive an API key.

Keys are scoped by city and role:
- **operator** — access to prediction, forecast, anomaly, and monitoring endpoints
- **admin** — full access including pipeline control, analytics, and reports

---

## 2. Authentication

Include the API key in every request header:
X-API-Key: your_key_here

Missing or invalid key returns `HTTP 401`.
Wrong city scope returns `HTTP 403`.

---

## 3. Making Your First Prediction

**Python:**
```python
import requests

response = requests.post(
    "https://your-deployment-url/predict",
    headers={"X-API-Key": "your_key_here"},
    json={
        "city": "Riyadh",
        "zone": "Zone_1",
        "hour": 8,
        "vehicle_count": 320,
        "avg_speed": 40,
        "weather": "clear",
        "road_type": "highway",
        "rush_hour": 1,
        "is_weekend": 0,
        "is_late_night": 0,
        "event": 0,
        "hour_multiplier": 1.4
    }
)
print(response.json())
```

**PowerShell:**
```powershell
Invoke-WebRequest -Uri "https://your-deployment-url/predict" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{"X-API-Key" = "your_key_here"} `
  -Body '{"city":"Riyadh","zone":"Zone_1","hour":8,"vehicle_count":320,"avg_speed":40,"weather":"clear","road_type":"highway","rush_hour":1,"is_weekend":0,"is_late_night":0,"event":0,"hour_multiplier":1.4}'
```

---

## 4. Rate Limit Handling

When you exceed the rate limit you receive `HTTP 429` with a `Retry-After` header.

```python
import time

def predict_with_retry(payload, headers, max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            time.sleep(retry_after)
            continue
        return response
    raise Exception("Rate limit exceeded after retries.")
```

---

## 5. Webhook Alert Setup

To receive proactive alerts when zones breach critical thresholds:

1. Set `WEBHOOK_URL` in your environment to your endpoint URL.
2. The system POSTs JSON every time an alert fires (checked every 15 minutes).

Payload format:
```json
{
  "timestamp": "2025-06-04 14:30:00",
  "city": "Riyadh",
  "alerts": [
    {
      "zone": "Zone_1",
      "metric": "congestion_score",
      "value": 0.82,
      "threshold": 0.75,
      "severity": "Critical"
    }
  ]
}
```

---

## 6. WebSocket Real-Time Feed

Connect to receive live zone updates every 30 seconds:

```python
import websocket, json

def on_message(ws, message):
    data = json.loads(message)
    for zone in data["zones"]:
        print(zone["zone"], zone["congestion_level"], zone["risk_level"])

ws = websocket.WebSocketApp(
    "wss://your-deployment-url/ws/live/Riyadh?api_key=your_key_here",
    on_message=on_message
)
ws.run_forever()
```

---

## 7. Hajj Mode

During Hajj season, set `hajj_mode: true` in predict requests to activate the mass-gathering traffic model with three phases — inbound, peak, and outbound.

The `/schedule/active` endpoint auto-detects whether Hajj is currently active based on today's date.

---

## 8. Error Codes

| Code | Meaning |
|---|---|
| 401 | Invalid or missing API key |
| 403 | Key not scoped for requested city or endpoint |
| 422 | Input validation failed (see `errors` field in response) |
| 429 | Rate limit exceeded |
| 500 | Server configuration error |
| 502 | External data adapter unavailable |