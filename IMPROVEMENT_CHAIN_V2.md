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
The next prompts make it production-ready, then research-grade.
The difference: a recruiter can run this. A city can deploy this. A researcher can cite this.

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
OpenStreetMap and Open-Meteo both offer free APIs with no key required.
The system has no connector to either.
A proof of concept that ingests real Riyadh weather data is worth
10x more in a recruiter conversation than one that cannot.

YOUR TASK:
1. Create src/adapters.py with:
   a. WeatherAdapter — fetch current weather for Riyadh coordinates
      using Open-Meteo API (free, no key required)
      - Endpoint: https://api.open-meteo.com/v1/forecast
      - Map wind speed > 40 km/h + low visibility → 'sandstorm'
      - Map precipitation > 0 → 'rain'
      - Default → 'clear'
      - Returns DataFrame with columns: city, weather, timestamp
   b. OpenStreetMapAdapter — fetch road segments for Riyadh bounding box
      using Overpass API (free, no key required)
      - Endpoint: https://overpass-api.de/api/interpreter
      - Query: highways within bbox [24.5, 46.5, 24.9, 46.9]
      - Returns DataFrame with columns: road_name, road_type, length_m
   c. MockIoTAdapter — deterministic fallback with configurable noise
      - Mirrors generate_traffic_data() output format exactly
      - Used when real APIs are unavailable or rate-limited
      - noise_level parameter: 0.0 = clean, 1.0 = max variance
2. Each adapter implements:
      def fetch(self, city: str) -> pd.DataFrame
3. Add AdapterFactory:
      def get_adapter(source: str) -> BaseAdapter
      source options: 'weather', 'osm', 'mock'
4. Add /data/source endpoint to app.py (authenticated):
      GET  /data/source → returns currently active source name
      POST /data/source?source=weather → switches active source
5. Confirm live fetch prints real data:
      adapter = get_adapter('weather')
      df = adapter.fetch('Riyadh')
      print(df.head())  # must show real timestamp and weather condition

DELIVERABLE:
- src/adapters.py with three working adapters
- Updated app.py with /data/source GET and POST endpoints
- Terminal output showing live Riyadh weather fetch
- README updated: data sources section with adapter interface docs

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
1. Create src/pipeline.py with these four functions:
   a. compute_drift_score(recent_predictions_df: pd.DataFrame) -> float
      - Load predictions_log.csv, take last 500 rows
      - Compute MAE between congestion_score and a naive baseline
      - Compare against baseline MAE stored at training time
      - Return ratio: 1.0 = stable, 1.3+ = retrain threshold reached
   b. should_retrain(drift_score: float, threshold: float = 1.3) -> bool
      - Pure function: return drift_score >= threshold
   c. retrain_model(city: str) -> dict
      - Call full startup sequence:
        generate → apply_hourly_patterns → add_lag_features →
        prepare_features → train_xgboost
      - Save new model to model.joblib using joblib.dump()
      - Return: {retrained: True, new_r2: float, old_r2: float,
                 timestamp: str}
   d. run_pipeline(city: str) -> dict
      - compute_drift_score → should_retrain → retrain_model if needed
      - Append result row to pipeline_log.csv
      - Return full pipeline result dict
2. Add two endpoints to app.py (both authenticated):
      GET  /pipeline/status → {drift_score, last_retrain, next_scheduled}
      POST /pipeline/trigger → runs run_pipeline('Riyadh') immediately
3. Schedule pipeline using APScheduler:
      pip install apscheduler
      Run run_pipeline('Riyadh') daily at 03:00 local time
      Log "Pipeline complete" to console after each run
4. Test manually:
      POST /pipeline/trigger with valid API key
      Confirm pipeline_log.csv is created with one row

DELIVERABLE:
- src/pipeline.py with all four functions
- Updated app.py with /pipeline/status and /pipeline/trigger
- pipeline_log.csv showing one completed run
- APScheduler confirmed running with console output

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
- PROMPT 009 complete — full automated pipeline with drift detection
- System runs locally — no public URL exists
- A live demo URL in a conversation changes everything

PROBLEM TO SOLVE:
You walk into a company in Riyadh's KAFD district.
They ask: "Can I see it running?"
You open your laptop. That is the wrong answer.
The right answer: you hand them a URL on your phone.

YOUR TASK:
1. Deploy FastAPI to Railway (free tier):
   a. Create railway.toml:
      [build]
      builder = "nixpacks"
      [deploy]
      startCommand = "uvicorn app:app --host 0.0.0.0 --port $PORT"
   b. Set API_KEY and ALLOWED_ORIGINS as Railway environment variables
   c. Confirm GET /health returns 200 at the public Railway URL
   d. Confirm GET /docs renders the full Swagger UI at public URL
2. Deploy Streamlit to Streamlit Cloud (free):
   a. Push streamlit_app/ to GitHub if not already there
   b. Connect repo at share.streamlit.io
   c. Set API_KEY in Streamlit secrets
   d. Confirm all 5 dashboard tabs load from the public URL
3. Update README top section with both live URLs:
      API:       https://your-app.railway.app/docs
      Dashboard: https://your-app.streamlit.app
4. Create DEMO.md with:
   - Two-sentence description of what the system does
   - 5 copy-paste PowerShell commands hitting the live API
     (health, predict clear, predict sandstorm, anomalies, forecast)
   - Screenshot of dashboard with all 5 tabs visible
   - One paragraph for a recruiter explaining what to look for

DELIVERABLE:
- Live API URL: GET /health returns 200, GET /docs renders
- Live Dashboard URL: all 5 tabs load
- README updated with both URLs
- DEMO.md ready to share with any recruiter

GENERATE NEXT PROMPT:
After completing this mission, look at the research on Saudi traffic.
69% of violations happen between cameras — lane changes, tailgating,
distracted driving. The system predicts congestion but cannot yet
estimate the environmental cost of that congestion.
Write PROMPT 011 targeting that gap.
```

---

## PROMPT 011 — Emissions and Environmental Impact Layer

```
MISSION: Add CO2 and fuel consumption estimates to every prediction
so the system speaks the language of Vision 2030 and the Saudi
Green Initiative — not just traffic operations.

RESEARCH BASIS:
Urban mobility analyses show 30% of urban air pollution in major
Saudi cities comes from traffic congestion. Researchers at Dhahran
demonstrated 16-23% emissions reductions through multi-objective
traffic optimization (MDPI Sustainability Journal). The Saudi Green
Initiative sets national emissions targets that traffic systems must
now report against. A system that only outputs congestion scores
cannot participate in that conversation.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 010 complete — system is live at a public URL
- Every prediction currently outputs congestion_score and level
- Zero environmental output exists anywhere in the system

PROBLEM TO SOLVE:
A city sustainability director asks: "What is the emissions cost
of this congestion event?"
Current answer: silence.
That ends the conversation with an entirely different class of
decision-maker — the one who controls Vision 2030 budgets.

YOUR TASK:
1. Add emissions constants to src/config.py:
   FUEL_CONSUMPTION_LPH = {
       'Low': 6.5,       # litres per 100 vehicles per hour
       'Moderate': 9.2,
       'High': 13.8,
       'Critical': 18.4
   }
   CO2_KG_PER_LITRE = 2.31   # standard petrol combustion factor
   AVG_VEHICLES_PER_ZONE = 250

2. Add compute_emissions(congestion_level, vehicle_count, duration_hours)
   to src/model.py:
   - Returns: {fuel_litres: float, co2_kg: float, co2_tonnes: float}
   - Formula: fuel = consumption_rate * (vehicle_count / 100) * duration
   - co2_kg = fuel_litres * CO2_KG_PER_LITRE

3. Update /predict endpoint in app.py:
   - Call compute_emissions() using congestion_level and vehicle_count
   - Add emissions dict to every prediction response
   - Log emissions fields to predictions_log.csv

4. Update /anomalies endpoint:
   - Add estimated_co2_kg to each anomaly record
   - Flag anomalies where co2_kg > 500 as 'Green Initiative Impact'

5. Add /emissions/summary endpoint (authenticated):
   GET /emissions/summary?city=Riyadh&date=2024-01-15
   - Reads predictions_log.csv
   - Returns: {total_co2_tonnes, peak_emission_hour, peak_emission_zone,
               green_initiative_events}

6. Update Streamlit dashboard:
   - Add emissions gauge to Tab 1 (Hourly Patterns)
   - Show daily CO2 total in Tab 2 (Zone Analysis)
   - Add "Green Initiative Impact" badge to critical anomalies

DELIVERABLE:
- compute_emissions() function in src/model.py
- /predict response includes emissions dict on every call
- /emissions/summary endpoint returning aggregated CO2 data
- Dashboard showing emissions alongside congestion
- Sample response showing co2_kg for a sandstorm prediction

WHAT THIS UNLOCKS IN A RECRUITER CONVERSATION:
"The system doesn't just predict congestion — it quantifies the
emissions cost per zone per hour and flags events that breach
Saudi Green Initiative thresholds. That's a different conversation
with a different budget."
```

---

## PROMPT 012 — Hajj and Mass Gathering Mode

```
MISSION: Model Hajj season traffic — the largest recurring
predictable traffic event on earth — and make it a named,
configurable schedule in the system.

RESEARCH BASIS:
NIH-published research (2023) specifically addresses Riyadh and
Makkah traffic during Hajj, identifying it as the single most
acute predictable congestion event in Saudi Arabia. Researchers
recommend AI-based crowd flow modeling calibrated to Hajj timings.
No Western traffic system ships with Hajj as a first-class concept.
This system does.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 011 complete — emissions layer exists
- Ramadan schedule is already modeled in apply_hourly_patterns()
- Hajj produces a categorically different traffic pattern:
  inbound surge → stationary dense crowds → outbound dispersal
  This is not a Ramadan shift — it is a different behavioral model

PROBLEM TO SOLVE:
The system models Friday prayer and Ramadan.
Those are weekly and annual recurring events.
Hajj is the largest annual human gathering on earth.
A traffic system for Vision 2030 smart cities that cannot
model Hajj is missing the single most operationally critical
event in Saudi traffic planning.

YOUR TASK:
1. Add HAJJ_SCHEDULE to src/config.py:
   - Hajj spans 5 days (8–12 Dhul Hijja) — add approximate
     Gregorian date ranges for 2025 and 2026
   - Define hourly multipliers for three phases:
     HAJJ_INBOUND  = {0:0.3, 6:1.8, 12:2.5, 18:2.0, 21:1.5}
     HAJJ_PEAK     = {0:1.2, 6:2.2, 12:3.0, 18:2.8, 21:2.0}
     HAJJ_OUTBOUND = {0:0.8, 6:2.5, 12:2.0, 18:1.5, 21:0.9}
   - Add HAJJ_ROUTE_ZONES = ['Zone_1', 'Zone_3'] — zones on
     pilgrimage routes get 1.8x additional multiplier

2. Update apply_hourly_patterns() in src/data.py:
   - Add hajj: bool = False parameter
   - When hajj=True, select phase based on day offset (0=inbound,
     2=peak, 4=outbound) and apply HAJJ_ROUTE_ZONES multiplier
   - Hajj overrides Ramadan schedule if both flags are True
   - Add 'hajj_phase' column to output DataFrame

3. Update /predict endpoint in app.py:
   - Add optional hajj_mode: bool = False to PredictRequest schema
   - Pass to predict logic — document in /docs

4. Add /schedule/active endpoint (authenticated):
   GET /schedule/active?city=Riyadh
   - Returns which schedule is currently active:
     {schedule: 'hajj_peak' | 'ramadan' | 'friday_prayer' | 'standard',
      next_event: str, days_until: int}
   - Auto-detects based on current date

5. Validate Hajj model statistically:
   - Run validate_data() equivalent on Hajj-mode data
   - Confirm peak hour multiplier produces vehicle_count
     at least 2.5x standard Friday midday volume
   - Print validation report — must show PASS

DELIVERABLE:
- HAJJ_SCHEDULE constants in src/config.py
- apply_hourly_patterns() accepts hajj=True with three phases
- /predict accepts hajj_mode parameter
- /schedule/active returns current schedule with countdown
- Validation report confirming Hajj model is statistically distinct
  from standard and Ramadan schedules

WHAT THIS UNLOCKS IN A RECRUITER CONVERSATION:
"The system has a dedicated Hajj mode with three traffic phases —
inbound, peak, and dispersal — calibrated to pilgrimage route zones.
No Western traffic system ships with this. This one does."
```

---

## PROMPT 013 — Demand Shifting and Intervention Recommendations

```
MISSION: Move the system from monitoring to intervention —
when congestion is High or Critical, tell decision-makers
not just what is happening but what to do about it before
it gets worse.

RESEARCH BASIS:
Academic teams published in ResearchGate modeled reward-based
gamification platforms for Saudi commuters that analyze historical
traffic curves and recommend off-peak departure windows, reducing
peak-hour load. The SR 4 billion Riyadh road upgrade includes
dedicated carpooling lanes. Riyadh Metro is designed to absorb
3.6 million passengers per day. The research consensus is clear:
prediction alone is not enough — systems must recommend modal
shift and departure timing to be operationally useful.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 012 complete — Hajj mode exists, full schedule awareness
- Current recommendations are operational alerts to city staff
- No output targets commuters or recommends behavioral change
- The system knows peak hours, knows congestion level, knows
  zones — it has everything needed to recommend intervention

PROBLEM TO SOLVE:
Zone_1 hits Critical at 08:00.
The system tells the operator: "Activate alternate routes."
It tells the commuter: nothing.
The commuter drives into the congestion anyway.
Prediction without intervention is half a system.

YOUR TASK:
1. Add METRO_STATIONS and CARPOOL_LANES to src/config.py:
   METRO_STATIONS = {
       'Zone_1': 'King Abdullah Financial District Station',
       'Zone_2': 'King Fahd Road Station',
       'Zone_3': 'Olaya Station',
       'Zone_4': 'Al Malaz Station',
   }
   CARPOOL_LANES = ['Zone_1', 'Zone_2']  # zones with dedicated lanes
   OFF_PEAK_WINDOWS = {
       'morning': {'recommended_departure': '06:30', 'avoid_until': '09:30'},
       'evening': {'recommended_departure': '15:30', 'avoid_until': '18:30'},
   }

2. Add get_intervention(zone, hour, congestion_level, schedule) to src/model.py:
   - Returns a structured intervention dict:
     {
       operator_action: str,     # existing recommendation
       commuter_advice: str,     # new — plain language for public
       metro_station: str,       # nearest station if zone has one
       carpool_available: bool,  # whether carpool lane exists
       recommended_departure: str,  # off-peak window suggestion
       intervention_urgency: str    # 'Monitor' | 'Advise' | 'Intervene'
     }
   - Logic:
     Low/Moderate → Monitor, standard advice
     High → Advise, suggest metro or off-peak departure
     Critical → Intervene, strong modal shift push + carpool lane

3. Update /predict response to include intervention dict alongside
   existing congestion_score and explanation fields

4. Add /interventions/active endpoint (authenticated):
   GET /interventions/active?city=Riyadh
   - Returns all zones currently at High or Critical with their
     full intervention recommendation
   - Sorted by urgency: Critical first

5. Update Streamlit dashboard Tab 2 (Zone Analysis):
   - Add intervention column to zone comparison table
   - Show commuter_advice in plain text under each anomaly
   - Highlight carpool_available zones in green

DELIVERABLE:
- get_intervention() in src/model.py
- /predict response includes full intervention dict
- /interventions/active endpoint returning prioritized list
- Dashboard Tab 2 shows commuter_advice and metro station
- Sample response showing Critical zone with metro recommendation

WHAT THIS UNLOCKS IN A RECRUITER CONVERSATION:
"When a zone hits Critical, the system doesn't just alert operators —
it tells commuters which metro station to use, whether a carpool lane
is available, and what departure time avoids the congestion entirely.
That's demand management, not just monitoring."
```

---

## THE TRAJECTORY

```
PROMPT 001–005  : Portfolio foundation (COMPLETE)
                  Validated data · Lag features · Anomaly detection
                  Forecasting · Explainability · Audit trail

PROMPT 006      : Security layer (COMPLETE)
                  API key auth · Rate limiting · CORS · .env

PROMPT 007      : Regression safety
                  16 automated tests · 80%+ coverage · CI/CD

PROMPT 008      : Real world data
                  Live weather fetch · OSM road network · Mock fallback

PROMPT 009      : Self-improving system
                  Drift detection · Auto-retraining at 03:00

PROMPT 010      : Public deployment
                  Live Railway URL · Live Streamlit URL · DEMO.md

PROMPT 011      : Environmental layer (research-grounded)
                  CO2 per prediction · Green Initiative thresholds
                  Emissions summary endpoint

PROMPT 012      : Hajj mode (Saudi-exclusive feature)
                  Three traffic phases · Pilgrimage route zones
                  Schedule auto-detection

PROMPT 013      : Demand intervention (research-grounded)
                  Commuter advice · Metro station routing
                  Carpool lane awareness · Off-peak departure windows

PROMPT 014–020  : Product and company layer (future)
                  Multi-city dashboard · Government reporting
                  Enterprise contracts · White-label deployment
```

---

## WHAT EACH PROMPT UNLOCKS IN A RECRUITER CONVERSATION

| Prompt | What you can say | Status |
|---|---|---|
| 006 | "The API is authenticated and rate-limited — not an open endpoint." | ✅ Done |
| 007 | "Every push runs 16 automated tests with 80%+ coverage." | Pending |
| 008 | "It fetches live Riyadh weather from Open-Meteo right now." | Pending |
| 009 | "It detects model drift and retrains itself automatically at 3AM." | Pending |
| 010 | "Here's the URL — you can test it on your phone right now." | Pending |
| 011 | "Every prediction includes CO2 output — it reports against Green Initiative targets." | Pending |
| 012 | "It has a dedicated Hajj mode with three traffic phases. No Western system has this." | Pending |
| 013 | "When a zone hits Critical, it tells commuters which metro station to use." | Pending |

Each prompt adds one sentence you could not say before.
That sentence is what gets you the meeting.
