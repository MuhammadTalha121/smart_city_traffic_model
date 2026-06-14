# Smart City Traffic Intelligence — Security Policy

---

## Authentication

All protected endpoints require an `X-API-Key` header.

Keys are provisioned by the system administrator and scoped to:
- A specific city (e.g. Riyadh) or all cities (`*`)
- A role: `operator` or `admin`

Keys should be treated as secrets. Do not commit keys to version control.

---

## Key Rotation

To rotate a key:
1. Generate a new key: `python generate_key.py`
2. Update the `API_KEYS` environment variable on the deployment platform
3. Notify affected client systems of the new key
4. Remove the old key from the registry

---

## Data in Transit

All traffic between clients and the API is encrypted via HTTPS, enforced by the deployment platform (Render / Railway).

WebSocket connections use WSS.

---

## Data Logged

The system logs the following per request to `usage_log.csv`:
- Timestamp
- Endpoint path
- HTTP method
- First 8 characters of the API key hash (not the full key)
- HTTP response code
- Response time in milliseconds

**No request bodies are logged. No personally identifiable information is collected.**

---

## Prediction Audit Trail

Every prediction is logged to `predictions_log.csv` with:
- Timestamp, city, zone, hour, weather
- Congestion score and level
- Top 3 SHAP factors
- CO2 and fuel estimates

This log is append-only and used for drift detection and SLA reporting.

---

## No PII Policy

This system processes traffic sensor data only. It does not collect, store, or process any personally identifiable information.

---

## Dependency Security

Dependencies are specified with minimum version constraints (`>=`) in `requirements.txt`. Review and update dependencies regularly using:

```bash
pip list --outdated
```