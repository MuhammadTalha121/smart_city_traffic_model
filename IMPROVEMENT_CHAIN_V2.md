# Smart City Traffic Intelligence — Improvement Chain v2

## Where We Are

PROMPT 001–005 complete:
- Statistical data validation — 5/5 checks passing
- Temporal lag features — RMSE improved 10%
- Anomaly detection — sandstorm spike verified at 5x expected
- Multi-horizon forecasting — XGBoost vs ARIMA compared
- SHAP explainability — plain English summaries, audit trail

PROMPT 006 complete:
- API key authentication — X-API-Key header, 401 on invalid/missing
- Rate limiting — 60/min on /predict, 20/min on /anomalies and /forecast
- CORS, .env, .gitignore, .env.example, generate_key.py

PROMPT 007 complete:
- 20 automated tests across test_data.py, test_model.py, test_api.py
- 85% code coverage
- GitHub Actions CI/CD — runs on every push to main
- Caught 3 silent bugs: wrong column name, duplicate endpoint, wrong function args

PROMPT 008 complete:
- WeatherAdapter — live Riyadh weather from Open-Meteo, no key required
- OpenStreetMapAdapter — Overpass API road network with fallback
- MockIoTAdapter — deterministic sensor simulation
- /data/source GET and POST endpoints — switch source in one API call
- Verified: live weather fetch returns real Riyadh conditions

PROMPT 009 complete:
- src/pipeline.py — compute_drift_score, should_retrain, retrain_model, run_pipeline
- /pipeline/status — drift score and last retrain timestamp
- /pipeline/trigger — manual retrain trigger
- APScheduler — nightly retrain at 03:00 if drift >= 1.3
- pipeline_log.csv confirmed created after first test run

PROMPT 010 complete:
- FastAPI deployed to Railway — live at https://web-production-abfda1.up.railway.app
- Streamlit dashboard deployed — live at https://smartcitytrafficmodel-u2bsdyw2cqxtorno5sscyk.streamlit.app
- DEMO.md created with 6 copy-paste PowerShell commands
- UptimeRobot monitoring /health every 5 minutes
- Live prediction verified: sandstorm scenario returns congestion_score 0.5056, level High

The system is production-ready and publicly accessible.
The next prompts make it research-grade.
The difference: a city can cite this. A government can deploy this.

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
- Lag features must be present in X_row even for live requests —
  approximate with current vehicle_count and 0.0 for std/congestion
- `apply_hourly_patterns()` must be called after `generate_traffic_data()` — it creates
  `congestion_score`. Without it, `add_lag_features()` will raise KeyError
- `train_xgboost()` signature: `train_xgboost(X, y)` — takes separate feature matrix
  and target series, not a full dataframe
- `log_prediction()` signature: `log_prediction(prediction_dict, explanation_dict)`
- `explain_prediction()` returns `{top_factors: [...], plain_english: str}`
- `forecast_congestion()` signature: `forecast_congestion(df, zone, hours_ahead)`
- `detect_anomalies()` returns `anomaly_flag` column, not `is_anomaly`

### Correct lifespan startup sequence
```python
df = generate_traffic_data(city="Riyadh")
df = apply_hourly_patterns(df, city="Riyadh")   # creates congestion_score
df = add_lag_features(df)                        # now congestion_score exists
X, y, feature_cols = prepare_features(df)
model, _, _        = train_xgboost(X, y)
```

---

## PROMPT 007 — Automated Testing Suite ✅ COMPLETE

### What was built
- `tests/test_data.py` — 5 tests: shape, Friday prayer drop, sandstorm, lag nulls, validate
- `tests/test_model.py` — 8 tests: predict_single, congestion levels, anomaly spike,
  forecast horizons, SHAP factors, evaluate_models, log_prediction, compare_baseline
- `tests/test_api.py` — 7 tests: health 200, no key 401, wrong key 401, valid key 200,
  invalid hour 422, anomalies list, forecast three horizons
- `.github/workflows/test.yml` — triggers on push to main, fails if any test fails
- Coverage: 85% total (99% data.py, 78% model.py, 100% config.py)

### Bugs caught by tests that manual testing missed
- `anomaly_df["is_anomaly"]` → should be `anomaly_df["anomaly_flag"] == 1`
- Duplicate `/predict` endpoint silently overwriting itself
- `forecast_congestion` called with wrong arguments in app.py

---

## PROMPT 008 — Real Data Integration Layer ✅ COMPLETE

### What was built
- `src/adapters.py` with BaseAdapter ABC and three implementations
- WeatherAdapter: Open-Meteo API, classifies wind/precipitation/humidity → system categories
- OpenStreetMapAdapter: Overpass API with Riyadh bbox, fallback to known major roads
- MockIoTAdapter: deterministic simulation matching generate_traffic_data() column format
- `get_adapter(source)` factory function
- `/data/source` GET returns active source
- `/data/source` POST switches source and returns live sample

### Verified output
- weather → rows_fetched: 1, real Riyadh temperature/wind/humidity/visibility
- osm → rows_fetched: 4, King Fahd Road and three arterials (fallback triggered)
- mock → rows_fetched: 5, one row per zone with simulated sensor readings

---

## PROMPT 009 — Automated Retraining Pipeline ✅ COMPLETE

### What was built
- `src/pipeline.py` with four functions:
  - `compute_drift_score()` — reads predictions_log.csv, compares rolling MAE to baseline
  - `should_retrain(drift_score, threshold=1.3)` — pure boolean check
  - `retrain_model(city)` — full regenerate → train → save to model.joblib
  - `run_pipeline(city)` — orchestrates all steps, logs to pipeline_log.csv
- `/pipeline/status` — drift_score, needs_retrain, last_retrain, next_scheduled
- `/pipeline/trigger` — POST to force immediate run
- APScheduler cron job at 03:00 daily

### Verified output
- drift_score: 1.0 (stable, below 1.3 threshold)
- needs_retrain: false
- pipeline_log.csv created with correct columns

---

## PROMPT 010 — Cloud Deployment ✅ COMPLETE

### What was built
- `railway.toml` + `nixpacks.toml` + `Procfile` — Railway deployment config
- `DEMO.md` — 6 copy-paste PowerShell commands for recruiters
- UptimeRobot monitor on /health — pings every 5 minutes to prevent sleep

### Live URLs
- API: https://web-production-abfda1.up.railway.app
- Docs: https://web-production-abfda1.up.railway.app/docs
- Dashboard: https://smartcitytrafficmodel-u2bsdyw2cqxtorno5sscyk.streamlit.app

### Deployment notes for future reference
- Railway does not expand $PORT in railway.toml startCommand directly
- Fix: use `sh -c 'uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}'`
- Or hardcode port 8000 — Railway routes traffic correctly either way
- Streamlit Cloud: set API_KEY in Advanced settings → Secrets
- Railway free tier sleeps after 30min inactivity — UptimeRobot prevents this

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
- PROMPT 010 complete — system is live at public URLs
- API: https://web-production-abfda1.up.railway.app
- Dashboard: https://smartcitytrafficmodel-u2bsdyw2cqxtorno5sscyk.streamlit.app
- Every prediction currently outputs congestion_score and level
- Zero environmental output exists anywhere in the system

CRITICAL IMPLEMENTATION NOTES:
- Encoding dicts live in src/model.py — not src/config.py
- detect_anomalies() returns anomaly_flag column, not is_anomaly
- forecast_congestion(df, zone, hours_ahead) — zone is second arg
- log_prediction(prediction_dict, explanation_dict) — two separate args
- After any change to app.py, run: py -m pytest tests/ -v to confirm
  no regressions before pushing to Railway

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

2. Add compute_emissions(congestion_level, vehicle_count, duration_hours=1.0)
   to src/model.py:
   - Returns: {fuel_litres: float, co2_kg: float, co2_tonnes: float}
   - Formula: fuel = consumption_rate * (vehicle_count / 100) * duration
   - co2_kg = fuel_litres * CO2_KG_PER_LITRE
   - co2_tonnes = co2_kg / 1000

3. Update /predict endpoint in app.py:
   - Call compute_emissions() using congestion_level and vehicle_count
   - Add emissions dict to every prediction response
   - Log co2_kg and fuel_litres to predictions_log.csv

4. Update /anomalies endpoint:
   - Add estimated_co2_kg to each anomaly record
   - Flag anomalies where co2_kg > 500 as 'Green Initiative Impact'

5. Add /emissions/summary endpoint (authenticated):
   GET /emissions/summary?city=Riyadh
   - Reads predictions_log.csv
   - Returns: {total_co2_tonnes, peak_emission_hour, peak_emission_zone,
               green_initiative_events, period_days}

6. Add test to tests/test_model.py:
   - test_compute_emissions_returns_valid_output()
   - test_emissions_critical_higher_than_low()

DELIVERABLE:
- compute_emissions() in src/model.py
- /predict response includes emissions dict on every call
- /emissions/summary endpoint returning aggregated CO2 data
- 2 new passing tests
- Live API at Railway URL returning emissions data

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
- Live URLs:
  API: https://web-production-abfda1.up.railway.app
  Dashboard: https://smartcitytrafficmodel-u2bsdyw2cqxtorno5sscyk.streamlit.app
- Ramadan schedule is already modeled in apply_hourly_patterns()
- Hajj produces a categorically different traffic pattern:
  inbound surge → stationary dense crowds → outbound dispersal

CRITICAL IMPLEMENTATION NOTES:
- apply_hourly_patterns() already has ramadan: bool parameter
- Add hajj: bool = False as a third parameter — do not rename ramadan
- Hajj overrides Ramadan if both True
- After changes to data.py, run validate_data() — must still pass 5/5
- Push to Railway after local tests pass — Railway auto-deploys on push

PROBLEM TO SOLVE:
The system models Friday prayer and Ramadan.
Hajj is the largest annual human gathering on earth.
A traffic system for Vision 2030 smart cities that cannot
model Hajj is missing the single most operationally critical
event in Saudi traffic planning.

YOUR TASK:
1. Add HAJJ_SCHEDULE to src/config.py:
   - Hajj spans 5 days (8–12 Dhul Hijja) — add Gregorian date ranges:
     2025: June 4–9, 2026: May 24–29
   - Define hourly multipliers for three phases:
     HAJJ_INBOUND  = {0:0.3, 6:1.8, 12:2.5, 18:2.0, 21:1.5}
     HAJJ_PEAK     = {0:1.2, 6:2.2, 12:3.0, 18:2.8, 21:2.0}
     HAJJ_OUTBOUND = {0:0.8, 6:2.5, 12:2.0, 18:1.5, 21:0.9}
   - Add HAJJ_ROUTE_ZONES = ['Zone_1', 'Zone_3']

2. Update apply_hourly_patterns() in src/data.py:
   - Add hajj: bool = False parameter after ramadan
   - When hajj=True, select phase based on day offset (0=inbound,
     2=peak, 4=outbound)
   - Apply 1.8x multiplier to HAJJ_ROUTE_ZONES
   - Add 'hajj_phase' column to output DataFrame
   - Hajj overrides Ramadan schedule if both flags are True

3. Update PredictRequest in app.py:
   - Add optional hajj_mode: bool = False field

4. Add /schedule/active endpoint (authenticated):
   GET /schedule/active?city=Riyadh
   - Returns: {schedule, next_event, days_until}
   - Auto-detects based on current date against HAJJ_SCHEDULE dates

5. Validate statistically:
   - Confirm Hajj peak hour vehicle_count >= 2.5x standard Friday midday
   - Print PASS/FAIL validation report

DELIVERABLE:
- HAJJ_SCHEDULE in src/config.py
- apply_hourly_patterns() accepts hajj=True with three phases
- /predict accepts hajj_mode parameter
- /schedule/active returns current schedule with countdown
- Validation report showing PASS

WHAT THIS UNLOCKS IN A RECRUITER CONVERSATION:
"It has a dedicated Hajj mode with three traffic phases —
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
- Live URLs:
  API: https://web-production-abfda1.up.railway.app
  Dashboard: https://smartcitytrafficmodel-u2bsdyw2cqxtorno5sscyk.streamlit.app
- Current recommendations are operational alerts to city staff only
- No output targets commuters or recommends behavioral change

PROBLEM TO SOLVE:
Zone_1 hits Critical at 08:00.
The system tells the operator: "Activate alternate routes."
It tells the commuter: nothing.
The commuter drives into the congestion anyway.
Prediction without intervention is half a system.

YOUR TASK:
1. Add to src/config.py:
   METRO_STATIONS = {
       'Zone_1': 'King Abdullah Financial District Station',
       'Zone_2': 'King Fahd Road Station',
       'Zone_3': 'Olaya Station',
       'Zone_4': 'Al Malaz Station',
   }
   CARPOOL_LANES = ['Zone_1', 'Zone_2']
   OFF_PEAK_WINDOWS = {
       'morning': {'recommended_departure': '06:30', 'avoid_until': '09:30'},
       'evening': {'recommended_departure': '15:30', 'avoid_until': '18:30'},
   }

2. Add get_intervention(zone, hour, congestion_level) to src/model.py:
   - Returns: {operator_action, commuter_advice, metro_station,
               carpool_available, recommended_departure, intervention_urgency}
   - Low/Moderate → Monitor
   - High → Advise, suggest metro or off-peak departure
   - Critical → Intervene, metro + carpool + departure window

3. Update /predict response to include intervention dict

4. Add /interventions/active endpoint (authenticated):
   GET /interventions/active?city=Riyadh
   - All zones at High or Critical, sorted Critical first

5. Add 2 tests:
   - test_get_intervention_critical_returns_intervene()
   - test_interventions_endpoint_returns_list()

DELIVERABLE:
- get_intervention() in src/model.py
- /predict includes intervention dict
- /interventions/active endpoint
- 2 new passing tests
- Live Railway API returning intervention data

WHAT THIS UNLOCKS IN A RECRUITER CONVERSATION:
"When a zone hits Critical, the system tells commuters which metro
station to use, whether a carpool lane is available, and what
departure time avoids the congestion entirely. That's demand
management, not just monitoring."
```

---

## THE TRAJECTORY

```
PROMPT 001–005  : Portfolio foundation (COMPLETE)
                  Validated data · Lag features · Anomaly detection
                  Forecasting · Explainability · Audit trail

PROMPT 006      : Security layer (COMPLETE)
                  API key auth · Rate limiting · CORS · .env

PROMPT 007      : Regression safety (COMPLETE)
                  20 tests · 85% coverage · CI/CD · 3 bugs caught

PROMPT 008      : Real world data (COMPLETE)
                  Live weather · OSM roads · Mock fallback

PROMPT 009      : Self-improving system (COMPLETE)
                  Drift detection · Auto-retraining at 03:00

PROMPT 010      : Public deployment (COMPLETE)
                  Railway API live · Streamlit dashboard live
                  UptimeRobot monitoring · DEMO.md

PROMPT 011      : Environmental layer (next)
                  CO2 per prediction · Green Initiative thresholds

PROMPT 012      : Hajj mode (Saudi-exclusive)
                  Three traffic phases · Pilgrimage route zones

PROMPT 013      : Demand intervention (research-grounded)
                  Commuter advice · Metro routing · Carpool lanes

PROMPT 014–020  : Product and company layer (future)
                  Multi-city dashboard · Government reporting
                  Enterprise contracts · White-label deployment
```

---

## WHAT EACH PROMPT UNLOCKS IN A RECRUITER CONVERSATION

| Prompt | What you can say | Status |
|---|---|---|
| 006 | "The API is authenticated and rate-limited — not an open endpoint." | ✅ Done |
| 007 | "Every push runs 20 automated tests with 85% coverage." | ✅ Done |
| 008 | "It fetches live Riyadh weather from Open-Meteo right now." | ✅ Done |
| 009 | "It detects model drift and retrains itself automatically at 3AM." | ✅ Done |
| 010 | "Here's the URL — you can test it on your phone right now." | ✅ Done |
| 011 | "Every prediction includes CO2 output — reports against Green Initiative targets." | Pending |
| 012 | "It has a dedicated Hajj mode with three traffic phases. No Western system has this." | Pending |
| 013 | "When a zone hits Critical, it tells commuters which metro station to use." | Pending |

Each prompt adds one sentence you could not say before.
That sentence is what gets you the meeting.
