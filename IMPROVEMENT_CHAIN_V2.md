# Smart City Traffic Intelligence — Improvement Chain v2

## Where We Are

PROMPT 001–005 complete:
- Statistical data validation — 5/5 checks passing
- Temporal lag features — RMSE improved 10%
- Anomaly detection — sandstorm spike verified at 5x expected
- Multi-horizon forecasting — XGBoost vs ARIMA compared
- SHAP explainability — plain English summaries, audit trail

The system is portfolio-ready.
The next 10 prompts make it production-ready.
The difference: a recruiter can run this. A city can deploy this.

---

## PROMPT 006 — Security Layer

```
MISSION: Add API authentication and rate limiting so the system
is not an open endpoint anyone can abuse.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 001-005 complete — full ML pipeline with explainability
- Current API has zero authentication — any caller gets full access
- A government infrastructure demo cannot have an unsecured API

PROBLEM TO SOLVE:
A city IT director asks: "Who can call this API?"
Current answer: anyone. That ends the conversation.

YOUR TASK:
1. Add API key authentication to app.py:
   a. Generate a secure API key using secrets.token_hex(32)
   b. Store it in a .env file — never hardcode
   c. All endpoints except /health require X-API-Key header
   d. Invalid key returns 401 with clear error message
2. Add rate limiting:
   a. pip install slowapi
   b. Limit /predict to 60 requests per minute per IP
   c. Limit /anomalies and /forecast to 20 requests per minute
   d. Return 429 with retry-after header when exceeded
3. Add CORS configuration:
   a. Allow only localhost:8501 (Streamlit) and localhost:3000 in development
   b. Document how to add production domains
4. Add .env.example to repo — never commit .env itself
5. Update .gitignore to exclude .env and predictions_log.csv

DELIVERABLE:
- Updated app.py with auth + rate limiting
- .env.example file
- Updated .gitignore
- Test: curl with no key returns 401, curl with key returns prediction

GENERATE NEXT PROMPT:
After completing this mission, identify what a DevOps engineer
would call the biggest deployment risk in this system.
Write PROMPT 007 targeting that risk.
```

---

## PROMPT 007 — Automated Testing Suite

```
MISSION: Build a test suite that catches regressions before
they reach production.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 006 complete — API is secured
- Zero automated tests exist — every change is manually verified
- Manual testing does not scale and misses edge cases

PROBLEM TO SOLVE:
You change one line in data.py.
The Friday prayer drop silently breaks.
You don't notice until a recruiter runs a demo.

YOUR TASK:
1. pip install pytest pytest-cov
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
   c. tests/test_api.py:
      - test_health_endpoint_returns_200()
      - test_predict_endpoint_valid_input()
      - test_predict_endpoint_invalid_hour()
      - test_anomalies_endpoint_returns_list()
      - test_forecast_endpoint_returns_forecasts()
3. Run: pytest tests/ --cov=src --cov-report=term-missing
4. Achieve minimum 80% code coverage
5. Add GitHub Actions workflow .github/workflows/test.yml:
   - Triggers on every push to main
   - Runs pytest automatically
   - Fails the push if any test fails

DELIVERABLE:
- tests/ directory with 15 passing tests
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

PROMPT 006–007  : Production hardening
                  API security · Automated testing · CI/CD

PROMPT 008–009  : Real world connectivity
                  Live data adapters · Drift detection · Auto-retraining

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

| Prompt | What you can say |
|---|---|
| 006 | "The API is authenticated and rate-limited — not an open endpoint." |
| 007 | "Every push runs 15 automated tests with 80%+ coverage." |
| 008 | "It can ingest real weather data from Open-Meteo right now, live." |
| 009 | "It detects model drift and retrains itself automatically at 3AM." |
| 010 | "Here's the URL — you can test it on your phone right now." |

Each prompt adds one sentence you could not say before.
That sentence is what gets you the meeting.
