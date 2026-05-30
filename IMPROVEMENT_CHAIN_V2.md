# Smart City Traffic Intelligence — Improvement Chain v2

## Where We Are

PROMPT 001–005 complete:
- Statistical data validation — 5/5 checks passing
- Temporal lag features — RMSE improved 10%
- Anomaly detection — sandstorm spike verified at 5x expected
- Multi-horizon forecasting — XGBoost vs ARIMA compared
- SHAP explainability — plain English summaries, audit trail

PROMPT 006 complete:
- API key authentication — X-API-Key header required on all endpoints except /health
- Rate limiting — /predict: 60 req/min, /anomalies + /forecast: 20 req/min per IP
- CORS — localhost:8501 and localhost:3000 allowed in development
- .env + .gitignore + .env.example added to repo
- Verified: no key → 401, /health → 200 no key, valid key → prediction with SHAP

The system is portfolio-ready.
The next 9 prompts make it production-ready.
The difference: a recruiter can run this. A city can deploy this.

---

## PROMPT 006 — Security Layer ✅ COMPLETE

### What was built
- `python-dotenv` loads API_KEY and ALLOWED_ORIGINS from `.env` at startup
- `APIKeyHeader` dependency on all endpoints except `/` and `/health`
- `slowapi` rate limiter: 60/min on `/predict`, 20/min on `/anomalies`, `/forecast`, `/predict/batch`
- CORS middleware with configurable origins via `.env`
- `generate_key.py` — run once to write a 64-char hex key to `.env`
- `.env.example` — safe to commit, shows structure without real values
- `.gitignore` — excludes `.env`, `predictions_log.csv`, `pipeline_log.csv`, `*.joblib`

### Key implementation details for future prompts
- Encoding dictionaries (WEATHER_ENCODING, ROAD_ENCODING, ZONE_ENCODING, DAY_ENCODING)
  live in `src/model.py` — not `src/config.py`
- `prepare_features()` always expects `congestion_score` as target — cannot be used
  for single-row inference. Build X_row manually using the encoding dicts from model.py
- Lag features (vehicle_count_lag_1h, vehicle_count_lag_2h, congestion_lag_1h,
  rolling_mean_3h, rolling_std_3h) must be present in X_row even for live requests —
  approximate with current vehicle_count and 0.0 for std/congestion
- `apply_hourly_patterns()` must be called after `generate_traffic_data()` — it creates
  `congestion_score`. Without it, `add_lag_features()` will raise KeyError
- `train_xgboost()` signature: `train_xgboost(X, y)` — takes separate feature matrix
  and target series, not a full dataframe
- `log_prediction()` signature: `log_prediction(prediction_dict, explanation_dict)`
- `explain_prediction()` signature: `explain_prediction(model, X_row_df, feature_names_list)`
  returns `{top_factors: [...], plain_english: str}`

### Correct lifespan startup sequence
```python
df = generate_traffic_data(city="Riyadh")
df = apply_hourly_patterns(df, city="Riyadh")   # creates congestion_score
df = add_lag_features(df)                        # now congestion_score exists
X, y, feature_cols = prepare_features(df)
model, _, _        = train_xgboost(X, y)
```

### Verified test results
- `POST /predict` no key → 401 Invalid or missing API key
- `GET /health` no key → 200 {"status":"healthy"}
- `POST /predict` valid key → 200 with congestion_score, congestion_level,
  recommendation, explanation, plain_english

---

## PROMPT 007 — Automated Testing Suite

```
MISSION: Build a test suite that catches regressions before
they reach production.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 006 complete — API is secured with key auth and rate limiting
- Zero automated tests exist — every change is manually verified
- Manual testing does not scale and misses edge cases

CRITICAL IMPLEMENTATION NOTES (read before writing any test):
- Encoding dicts live in src/model.py: WEATHER_ENCODING, ROAD_ENCODING,
  ZONE_ENCODING, DAY_ENCODING — not src/config.py
- prepare_features() requires congestion_score column — cannot be used
  for single-row inference. Tests for the API must build X_row manually
- apply_hourly_patterns() must be called before add_lag_features()
- train_xgboost() takes (X, y) not a full dataframe
- log_prediction() takes (prediction_dict, explanation_dict)
- Lag feature columns must be present even for single-request tests —
  use current vehicle_count as approximation for lag values

PROBLEM TO SOLVE:
You change one line in data.py.
The Friday prayer drop silently breaks.
You don't notice until a recruiter runs the demo.

YOUR TASK:
1. pip install pytest pytest-cov httpx
2. Create tests/ directory with:
   a. tests/test_data.py:
      - test_generate_returns_correct_shape()
      - test_friday_prayer_drop_exceeds_85_percent()
      - test_sandstorm_speed_reduction_in_range()
      - test_lag_features_no_nulls_after_dropna()
      - test_validate_data_all_pass()
   b. tests/test_model.py:
      - test_predict_single_returns_valid_score()
      - test_congestion_level_boundaries()
      - test_anomaly_detection_flags_spike()
      - test_forecast_returns_three_horizons()
      - test_explain_prediction_returns_three_factors()
   c. tests/test_api.py — use FastAPI TestClient:
      - test_health_endpoint_no_auth_returns_200()
      - test_predict_no_key_returns_401()
      - test_predict_wrong_key_returns_401()
      - test_predict_valid_key_returns_prediction()
      - test_anomalies_endpoint_returns_list()
      - test_forecast_endpoint_returns_forecasts()
      - test_rate_limit_returns_429_after_threshold()
3. Set TEST_API_KEY environment variable for test_api.py
4. Run: pytest tests/ --cov=src --cov-report=term-missing
5. Achieve minimum 80% code coverage
6. Add GitHub Actions workflow .github/workflows/test.yml:
   - Triggers on every push to main
   - Sets API_KEY as a GitHub Actions secret
   - Runs pytest automatically
   - Fails the push if any test fails

DELIVERABLE:
- tests/ directory with 16 passing tests
- Coverage report showing ≥80%
- .github/workflows/test.yml
- Badge in README: tests passing

GENERATE NEXT PROMPT:
After completing this mission, identify what prevents this system
from connecting to real traffic data sources.
Write PROMPT 008 targeting that gap.
```

---

## PROMPT 008 — Real Data Integration Layer

```
MISSION: Build a data adapter layer that can ingest real traffic
data from open APIs and replace synthetic generation seamlessly.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 007 complete — test suite passing
- All current data is synthetic — no real world signals
- The system architecture already supports swapping data sources

PROBLEM TO SOLVE:
OpenStreetMap, TomTom, and HERE Maps all offer free traffic APIs.
The system has no connector to any of them.
A proof of concept that can ingest real data is worth 10x more
to a recruiter than one that cannot.

YOUR TASK:
1. Create src/adapters.py with:
   a. OpenStreetMapAdapter — fetch road network for a bounding box
      using the Overpass API (free, no key required)
   b. WeatherAdapter — fetch current weather for city coordinates
      using Open-Meteo API (free, no key required)
   c. MockIoTAdapter — simulate sensor readings with configurable
      noise level — acts as fallback when real APIs are unavailable
2. Each adapter implements a common interface:
   def fetch(city: str) -> pd.DataFrame
3. Add an AdapterFactory:
   def get_adapter(source: str) -> BaseAdapter
   source options: 'osm', 'weather', 'mock'
4. Add /data/source endpoint to app.py:
   - Returns which data source is currently active
   - Allows switching between mock and real in one API call
5. Test live fetch:
   adapter = get_adapter('weather')
   df = adapter.fetch('Riyadh')
   print(df.head())

DELIVERABLE:
- src/adapters.py with three adapters
- Updated app.py with /data/source endpoint
- Live weather fetch working and printing real Riyadh data
- README updated with data source documentation

GENERATE NEXT PROMPT:
After completing this mission, identify what a data engineer
would build next to make this system self-improving over time.
Write PROMPT 009 targeting that capability.
```

---

## PROMPT 009 — Automated Retraining Pipeline

```
MISSION: Build a pipeline that detects model drift and retrains
automatically when prediction quality degrades.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 008 complete — real data adapters exist
- Model was trained once on static data — never updated
- In production, traffic patterns shift: new roads open,
  Ramadan changes demand, population grows

PROBLEM TO SOLVE:
A model trained in January predicts poorly by June.
No one notices because there is no drift monitoring.
The city loses trust in the system silently.

YOUR TASK:
1. Create src/pipeline.py with:
   a. compute_drift_score(recent_predictions_df) -> float
      - Compares recent MAE against baseline MAE from training
      - Returns drift ratio: 1.0 = no drift, 2.0 = doubled error
   b. should_retrain(drift_score: float, threshold: float = 1.3) -> bool
   c. retrain_model(city: str) -> dict
      - Regenerates data, retrains XGBoost, saves new model.joblib
      - Returns: {retrained: bool, new_r2: float, old_r2: float}
   d. run_pipeline(city: str) -> dict
      - Checks drift → retrains if needed → logs outcome
2. Add /pipeline/status endpoint to app.py:
   - Returns current drift score and last retrain timestamp
3. Add /pipeline/trigger endpoint (POST):
   - Manually triggers retrain
   - Requires API key authentication
4. Schedule pipeline to run daily using APScheduler:
   pip install apscheduler
   Run automatically at 03:00 every night
5. Log all pipeline runs to pipeline_log.csv

DELIVERABLE:
- src/pipeline.py with full drift detection and retraining
- Updated app.py with pipeline endpoints
- pipeline_log.csv after one test run
- Scheduler running and confirmed with print output

GENERATE NEXT PROMPT:
After completing this mission, identify what would make this
system visible and deployable to a real government client.
Write PROMPT 010 targeting that requirement.
```

---

## PROMPT 010 — Cloud Deployment + Public Demo URL

```
MISSION: Deploy the full system to the cloud so it has a real
public URL that can be shared with any recruiter or client.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 009 complete — full automated pipeline
- System runs locally — no public URL exists
- A live demo URL in a conversation changes everything

PROBLEM TO SOLVE:
You walk into a company in Riyadh's KAFD district.
They ask: "Can I see it running?"
You open your laptop. That is the wrong answer.
The right answer: you hand them a URL on your phone.

YOUR TASK:
1. Deploy FastAPI to Railway (free tier):
   a. Create railway.toml with correct start command
   b. Set environment variables for API key via Railway dashboard
   c. Confirm /health returns 200 at public URL
   d. Confirm /docs renders at public URL
2. Deploy Streamlit dashboard to Streamlit Cloud (free):
   a. Push streamlit_app/ to GitHub
   b. Connect repo to share.streamlit.io
   c. Confirm dashboard loads with all 5 tabs
3. Update README with live URLs:
   - API: https://your-app.railway.app/docs
   - Dashboard: https://your-app.streamlit.app
4. Add a DEMO.md file:
   - 5 curl examples hitting the live API
   - Screenshots of live dashboard
   - Instructions for recruiter to test it themselves
5. Add live URL badges to README top section

DELIVERABLE:
- Live API URL returning real predictions
- Live dashboard URL showing all 5 tabs
- Updated README with both URLs and badges
- DEMO.md with recruiter-ready instructions

GENERATE NEXT PROMPT:
After completing this mission, think about what separates
a deployed proof of concept from a real product a city would pay for.
Write PROMPT 011 targeting the most critical product gap.
```

---

## THE TRAJECTORY

```
PROMPT 001–005  : Portfolio foundation (COMPLETE)
                  Validated data · Lag features · Anomaly detection
                  Forecasting · Explainability · Audit trail

PROMPT 006      : Security layer (COMPLETE)
                  API key auth · Rate limiting · CORS · .env

PROMPT 007–008  : Production hardening + real world connectivity
                  Automated testing · CI/CD · Live data adapters

PROMPT 009      : Self-improving system
                  Drift detection · Auto-retraining

PROMPT 010      : Public deployment
                  Live URL · Recruiter-ready demo

PROMPT 011–015  : Product layer (future)
                  Multi-city dashboard · User accounts · Billing
                  Government reporting · SLA monitoring

PROMPT 016–020  : Company layer (future)
                  Enterprise contracts · White-label deployment
                  Custom city onboarding · Support tier
```

---

## WHAT EACH PROMPT UNLOCKS IN A RECRUITER CONVERSATION

| Prompt | What you can say | Status |
|---|---|---|
| 006 | "The API is authenticated and rate-limited — not an open endpoint." | ✅ Done |
| 007 | "Every push runs 16 automated tests with 80%+ coverage." | Pending |
| 008 | "It can ingest real weather data from Open-Meteo right now, live." | Pending |
| 009 | "It detects model drift and retrains itself automatically at 3AM." | Pending |
| 010 | "Here's the URL — you can test it on your phone right now." | Pending |

Each prompt adds one sentence you could not say before.
That sentence is what gets you the meeting.
