# Smart City Traffic Intelligence — Improvement Chain v2

## Where We Are

PROMPT 001–005 complete — Portfolio foundation
PROMPT 006 complete — API security
PROMPT 007 complete — 20 tests, 85% coverage, CI/CD
PROMPT 008 complete — Live weather, OSM, mock adapters
PROMPT 009 complete — Drift detection, auto-retraining at 03:00
PROMPT 010 complete — Live Railway API + Streamlit dashboard

Live API:       https://web-production-abfda1.up.railway.app
Live Dashboard: https://smartcitytrafficmodel-u2bsdyw2cqxtorno5sscyk.streamlit.app

The system is production-ready and publicly accessible.
PROMPT 011–020 make it research-grade.
PROMPT 021–030 make it a product a city would pay for.

---

## RESEARCH BASIS FOR PROMPTS 011–030

Every prompt below is grounded in one or more of these sources:

- Almatar (2024) — Smart Transportation Planning in KSA, ResearchGate
- AlQuhtani (2026) — Vision 2030 and Urban Mobility in Riyadh, Wiley Growth and Change
- SWARCO (2024) — Saudi Vision 2030 and Intelligent Mobility
- ScienceDirect (2025) — Urban Transport Planning in Saudi Arabia: Systematic Review
- MDPI Sustainability — Hybrid Adaptive Traffic Lights, Dhahran field trials
- Nature Communications (2024) — Traffic light optimization with low penetration rate vehicles
- Oxford Academic ITS (2025) — Advances in RL for Traffic Signal Control
- Wiley Journal of Engineering (2024) — DRL for intersection optimization
- PLOS ONE (2025) — Deep learning for accident risk prediction
- ScienceDirect (2024) — Machine learning for safe routing
- MDPI Mathematics (2024) — Adaptive Transit Signal Priority, multi-objective DRL
- NIH (2023) — Hajj traffic congestion research
- Najm Insurance Services — 10,000–14,000 daily accident cases
- US DOT ITS JPO (2024) — Annual Modal Research Plans
- ITF-OECD (2024) — Last mile delivery and urban freight
- WHO — 270,000 pedestrian fatalities annually worldwide

---

## COMPLETED PROMPTS 001–010

See PROJECT_CONTEXT_.md for full implementation details.

---

## PROMPT 011 — Emissions and Environmental Impact Layer

```
MISSION: Add CO2 and fuel consumption estimates to every prediction
so the system speaks the language of Vision 2030 and the Saudi
Green Initiative — not just traffic operations.

RESEARCH BASIS:
Urban mobility analyses: 30% of urban air pollution in Saudi cities
comes from traffic congestion. Dhahran field trials (MDPI Sustainability)
demonstrated 16–23% emissions reduction through multi-objective traffic
optimization. Saudi Green Initiative sets national emissions targets all
infrastructure systems must now report against.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 010 complete — system live at public URLs
- All predictions output congestion_score and level only
- Zero environmental output exists anywhere in the system
- Encoding dicts are in src/model.py — not src/config.py
- detect_anomalies() returns anomaly_flag column (int), not is_anomaly
- After any app.py change run tests before pushing to Railway

PROBLEM TO SOLVE:
A city sustainability director asks: "What is the emissions cost
of this congestion event?"
Current answer: silence.
That ends the conversation with a different class of decision-maker —
the one who controls Vision 2030 budgets.

YOUR TASK:
1. Add to src/config.py:
   FUEL_CONSUMPTION_LPH = {
       'Low': 6.5, 'Moderate': 9.2, 'High': 13.8, 'Critical': 18.4
   }
   CO2_KG_PER_LITRE  = 2.31   # standard petrol combustion factor
   AVG_ZONE_AREA_KM2 = 2.5    # average zone coverage

2. Add compute_emissions(congestion_level, vehicle_count,
   duration_hours=1.0) to src/model.py:
   - fuel = FUEL_CONSUMPTION_LPH[level] * (vehicle_count / 100) * duration
   - co2_kg = fuel * CO2_KG_PER_LITRE
   - Returns: {fuel_litres, co2_kg, co2_tonnes}

3. Update /predict — add emissions dict to response and log to CSV

4. Add /emissions/summary endpoint (authenticated):
   GET /emissions/summary?city=Riyadh
   - Reads predictions_log.csv
   - Returns: {total_co2_tonnes, peak_emission_hour,
               peak_emission_zone, period_days}

5. Add 2 tests:
   - test_compute_emissions_returns_valid_output()
   - test_critical_emissions_higher_than_low()

DELIVERABLE:
- compute_emissions() in src/model.py
- /predict includes emissions dict
- /emissions/summary endpoint working
- 2 new tests passing
- Railway auto-deployed via git push

RECRUITER SENTENCE:
"Every prediction quantifies the CO2 cost per zone per hour and
reports against Saudi Green Initiative thresholds."
```

---

## PROMPT 012 — Hajj and Mass Gathering Mode

```
MISSION: Model Hajj season traffic as a named, validated schedule
in the system — the largest recurring predictable traffic event
on earth.

RESEARCH BASIS:
NIH-published research (2023) on Riyadh and Makkah during Hajj
identifies it as the most acute predictable congestion event in
Saudi Arabia. Researchers recommend AI crowd flow modeling
calibrated to Hajj timings. No Western traffic system treats
Hajj as a first-class data concept.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 011 complete — emissions layer exists
- apply_hourly_patterns(df, city, ramadan) already exists
- Add hajj: bool = False as third parameter — do not rename ramadan
- Hajj overrides Ramadan if both flags are True
- After changes to data.py run validate_data() — must pass 5/5

PROBLEM TO SOLVE:
The system models Friday prayer and Ramadan.
Hajj is the largest annual human gathering on earth.
A Vision 2030 traffic system that cannot model Hajj is incomplete.

YOUR TASK:
1. Add to src/config.py:
   HAJJ_DATES = {
       2025: {'start': '2025-06-04', 'end': '2025-06-09'},
       2026: {'start': '2026-05-24', 'end': '2026-05-29'},
   }
   HAJJ_INBOUND  = {0:0.3, 6:1.8, 9:2.2, 12:2.5, 15:2.0, 18:1.8, 21:1.5}
   HAJJ_PEAK     = {0:1.2, 6:2.2, 9:2.8, 12:3.0, 15:2.8, 18:2.5, 21:2.0}
   HAJJ_OUTBOUND = {0:0.8, 6:2.5, 9:2.2, 12:2.0, 15:1.8, 18:1.5, 21:0.9}
   HAJJ_ROUTE_ZONES = ['Zone_1', 'Zone_3']  # pilgrimage route zones, 1.8x

2. Update apply_hourly_patterns() in src/data.py:
   - Add hajj: bool = False parameter
   - Select phase by date offset (day 0–1=inbound, 2–3=peak, 4=outbound)
   - Apply 1.8x multiplier to HAJJ_ROUTE_ZONES
   - Add 'hajj_phase' column to output

3. Add hajj_mode: bool = False to PredictRequest schema in app.py

4. Add /schedule/active endpoint (authenticated):
   GET /schedule/active?city=Riyadh
   Returns: {schedule, next_event, days_until}
   Auto-detects from current date vs HAJJ_DATES

5. Validate: Hajj peak hour vehicle_count >= 2.5x standard Friday midday
   Print PASS/FAIL report

DELIVERABLE:
- HAJJ_DATES and multipliers in src/config.py
- apply_hourly_patterns() accepts hajj=True
- /schedule/active endpoint with countdown
- Statistical validation PASS
- Railway auto-deployed

RECRUITER SENTENCE:
"It has a dedicated Hajj mode — inbound, peak, dispersal phases —
calibrated to pilgrimage route zones. No Western system ships this."
```

---

## PROMPT 013 — Demand Shifting and Intervention Recommendations

```
MISSION: Move the system from monitoring to intervention —
when congestion is High or Critical, tell commuters what to do,
not just alert operators.

RESEARCH BASIS:
ResearchGate (2026): Saudi researchers modeled reward-based
gamification platforms recommending off-peak departure windows
that reduced peak-hour load. SR 4 billion Riyadh road upgrade
includes dedicated carpooling lanes. Riyadh Metro capacity:
3.6 million passengers daily (RCRC). Research consensus: prediction
without intervention is half a system.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 012 complete — full schedule awareness including Hajj
- Current recommendations target city operators only
- No commuter-facing output exists anywhere in the system

PROBLEM TO SOLVE:
Zone_1 hits Critical at 08:00.
The system tells the operator: "Activate alternate routes."
It tells the commuter: nothing.
The commuter drives into the congestion anyway.

YOUR TASK:
1. Add to src/config.py:
   METRO_STATIONS = {
       'Zone_1': 'King Abdullah Financial District Station',
       'Zone_2': 'King Fahd Road Station',
       'Zone_3': 'Olaya Station',
       'Zone_4': 'Al Malaz Station',
   }
   CARPOOL_LANES   = ['Zone_1', 'Zone_2']
   OFF_PEAK_WINDOWS = {
       'morning': {'recommended': '06:30', 'avoid_until': '09:30'},
       'evening': {'recommended': '15:30', 'avoid_until': '18:30'},
   }

2. Add get_intervention(zone, hour, congestion_level) to src/model.py:
   Returns: {operator_action, commuter_advice, metro_station,
             carpool_available, recommended_departure, urgency}
   Low/Moderate → urgency: Monitor
   High → urgency: Advise, suggest metro or off-peak departure
   Critical → urgency: Intervene, metro + carpool + departure window

3. Include intervention dict in /predict response

4. Add /interventions/active endpoint (authenticated):
   GET /interventions/active?city=Riyadh
   All zones at High or Critical, sorted Critical first

5. Add 2 tests:
   - test_intervention_critical_returns_intervene()
   - test_interventions_endpoint_returns_list()

DELIVERABLE:
- get_intervention() in src/model.py
- /predict includes intervention dict
- /interventions/active endpoint
- 2 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"When a zone hits Critical, it tells commuters which metro station
to use, whether a carpool lane is available, and what departure time
avoids the congestion."
```

---

## PROMPT 014 — Accident Risk Scoring per Zone

```
MISSION: Add an accident risk score to every zone based on
congestion, weather, time, and historical patterns — moving
the system from congestion prediction to safety prediction.

RESEARCH BASIS:
PLOS ONE (2025): CNN-LSTM-GNN model for accident risk prediction
using spatiotemporal vehicle trajectory data. ScienceDirect (2024):
Random Forest + spatial network analysis for safe route identification.
Najm Insurance Services: 10,000–14,000 accident cases daily in KSA.
MDPI (2022): ML and AI review for incident detection in road transport.
The gap is not detecting accidents after they happen — it is scoring
risk before they happen so operators can act preventively.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 013 complete — intervention layer exists
- Current system predicts congestion — not accident probability
- Congestion, weather, hour, and is_weekend are already features
- No new data sources needed — derive risk from existing features

PROBLEM TO SOLVE:
High congestion + sandstorm + rush hour + Friday = very high accident risk.
The system scores congestion accurately.
It does not score danger.
A city safety director needs risk, not just volume.

YOUR TASK:
1. Add compute_accident_risk(congestion_score, weather, hour,
   is_weekend, rush_hour) to src/model.py:
   - Base risk = congestion_score * 0.4
   - Weather multipliers: sandstorm 2.5x, rain 1.8x, fog 1.6x,
     dust 1.4x, humid 1.1x, clear 1.0x
   - Rush hour adds 0.15
   - Late night (21–23) adds 0.12 (Saudi-specific: high speed, low volume)
   - Weekend Friday prayer window subtracts 0.10 (low volume = low risk)
   - Clip result to [0.0, 1.0]
   - Returns: {risk_score, risk_level, primary_risk_factor}
   - Risk levels: Safe < 0.3, Elevated 0.3–0.5,
                  High Risk 0.5–0.7, Critical Risk > 0.7

2. Add risk_score and risk_level to /predict response

3. Add /safety/hotspots endpoint (authenticated):
   GET /safety/hotspots?city=Riyadh
   - Returns zones ranked by current risk_score, highest first
   - Includes primary_risk_factor for each zone

4. Log risk_score to predictions_log.csv

5. Add 2 tests:
   - test_sandstorm_rush_hour_produces_high_risk()
   - test_safety_hotspots_endpoint_returns_ranked_list()

DELIVERABLE:
- compute_accident_risk() in src/model.py
- /predict includes risk_score and risk_level
- /safety/hotspots endpoint working
- 2 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"Every prediction includes an accident risk score — not just
congestion. Sandstorm + rush hour = Critical Risk. The system
flags that before the accident happens."
```

---

## PROMPT 015 — Adaptive Signal Timing Recommendations

```
MISSION: Generate signal timing recommendations per intersection
based on real-time congestion — the core output of adaptive
traffic signal control research.

RESEARCH BASIS:
Oxford Academic ITS (2025): RL-based adaptive signal control
reduces delays and improves throughput. Nature Communications (2024):
traffic light optimization with low vehicle penetration rate.
Wiley Journal of Engineering (2024): DRL for intersection optimization,
metrics include average waiting time and queue length. MDPI Mathematics
(2024): multi-objective DRL balancing delay, fuel, and emissions.
This system cannot deploy actual signal hardware — but it can compute
and output the recommended green phase durations that a connected
signal controller would implement.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 014 complete — accident risk layer exists
- Zones are proxies for intersections in this system
- Current system does not output any signal timing data
- Saudi cities: Vision 2030 smart signal infrastructure being deployed

PROBLEM TO SOLVE:
A traffic engineer asks: "What green phase duration does your
system recommend for Zone_1 right now?"
Current answer: nothing.
Signal timing is the core operational output of traffic intelligence.

YOUR TASK:
1. Add compute_signal_timing(congestion_score, vehicle_count,
   hour, is_weekend) to src/model.py:
   - Base cycle = 90 seconds (standard urban cycle)
   - Green phase proportion scales with congestion_score:
     Low: 0.35 green, Moderate: 0.45, High: 0.55, Critical: 0.65
   - Friday prayer window: reduce to 0.20 green (low demand)
   - Late night: extend to 0.70 green (high speed, low volume)
   - Returns: {cycle_seconds, green_seconds, red_seconds,
               phase_ratio, timing_rationale}

2. Add signal_timing dict to /predict response

3. Add /signals/recommended endpoint (authenticated):
   GET /signals/recommended?city=Riyadh
   - Returns all zones with recommended signal timing right now
   - Sorted by congestion_score descending

4. Add 2 tests:
   - test_critical_congestion_produces_longer_green()
   - test_prayer_window_produces_short_green()

DELIVERABLE:
- compute_signal_timing() in src/model.py
- /predict includes signal_timing dict
- /signals/recommended endpoint working
- 2 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"The system outputs recommended green phase durations per zone —
the direct input for adaptive signal controllers being deployed
under Vision 2030."
```

---

## PROMPT 016 — Multi-City Comparative Dashboard

```
MISSION: Extend the system to compare traffic conditions across
all configured cities simultaneously in a single dashboard view.

RESEARCH BASIS:
ScienceDirect (2025) systematic review of Saudi transport planning:
multi-city comparison is essential for policy decisions across
Riyadh, NEOM, Dubai, and Jeddah. Vision 2030 transport policy
requires cross-city benchmarking to allocate infrastructure
investment. Currently the system trains on Riyadh only and the
dashboard shows one city at a time.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 015 complete — signal timing layer exists
- src/config.py already has SAUDI_CITIES and city profiles
- Riyadh, NEOM, Dubai, Karachi are configured
- Dashboard currently has 5 tabs showing only Riyadh data
- Streamlit is live at the dashboard URL

PROBLEM TO SOLVE:
A government planner asks: "How does Riyadh compare to NEOM
right now in terms of congestion and risk?"
Current answer: not possible in one view.

YOUR TASK:
1. Update lifespan in app.py to generate data for all cities:
   - Generate + apply_hourly_patterns + lag features for each city
   - Store in app.state.city_dfs dict keyed by city name

2. Add /cities/compare endpoint (authenticated):
   GET /cities/compare
   Returns current snapshot for all cities:
   {city, avg_congestion_score, max_zone, peak_hour,
    total_anomalies, avg_risk_score}
   Sorted by avg_congestion_score descending

3. Add Tab 6 to Streamlit dashboard: City Comparison
   - Bar chart: average congestion by city
   - Bar chart: total anomalies by city
   - Table: peak zone per city with risk level
   - Refresh button to pull latest from /cities/compare

4. Update /predict to accept any configured city, not just Riyadh

5. Add 1 test:
   - test_cities_compare_returns_all_configured_cities()

DELIVERABLE:
- app.state.city_dfs populated for all cities at startup
- /cities/compare endpoint returning all city snapshots
- Dashboard Tab 6 showing multi-city comparison
- Test passing
- Railway and Streamlit auto-deployed

RECRUITER SENTENCE:
"The dashboard compares Riyadh, NEOM, Dubai, and Karachi
simultaneously — one view for a government planner."
```

---

## PROMPT 017 — Incident Response Time Estimator

```
MISSION: Estimate emergency vehicle response time to any zone
based on current traffic conditions — a direct operational output
for city emergency services.

RESEARCH BASIS:
PLOS ONE (2024): MIPSSTW model for emergency vehicle routing under
complex traffic conditions on highway incidents. Research conclusion:
ambulance priority does not guarantee no delay when traffic is
critical — response time estimation is a separate calculation.
Intelligent Transportation Systems literature (arxiv 2021):
multi-agent models for ensuring emergency vehicles arrive as quickly
as possible. This is a documented gap between prediction systems
and operational emergency services.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 016 complete — multi-city comparison exists
- System has congestion_score per zone per hour
- No emergency services integration exists
- Cannot interface with real dispatch systems — compute estimates only

PROBLEM TO SOLVE:
A city emergency director asks: "How long will it take an ambulance
to reach Zone_3 from the central station right now?"
Current answer: nothing.
Every minute of response time delay costs lives.
The Saudi Red Crescent Authority needs this number.

YOUR TASK:
1. Add to src/config.py:
   EMERGENCY_STATIONS = {
       'Riyadh': {
           'Central': {'zone': 'Zone_1', 'lat': 24.688, 'lon': 46.722},
           'North':   {'zone': 'Zone_3', 'lat': 24.774, 'lon': 46.738},
       }
   }
   ZONE_DISTANCES_KM = {
       ('Zone_1','Zone_2'): 3.2, ('Zone_1','Zone_3'): 5.8,
       ('Zone_1','Zone_4'): 7.1, ('Zone_1','Zone_5'): 9.4,
       ('Zone_2','Zone_3'): 4.1, ('Zone_2','Zone_4'): 5.9,
       ('Zone_2','Zone_5'): 8.2, ('Zone_3','Zone_4'): 3.3,
       ('Zone_3','Zone_5'): 6.1, ('Zone_4','Zone_5'): 4.2,
   }
   EMERGENCY_SPEED_KMPH = {
       'Low': 75, 'Moderate': 60, 'High': 45, 'Critical': 30
   }

2. Add estimate_response_time(origin_zone, target_zone,
   congestion_level) to src/model.py:
   - Look up distance from ZONE_DISTANCES_KM
   - Apply emergency speed from EMERGENCY_SPEED_KMPH
   - Add 2 min base overhead
   - Returns: {origin_zone, target_zone, distance_km,
               estimated_minutes, congestion_impact, warning}
   - Warning if estimated_minutes > 8 (WHO recommended threshold)

3. Add /emergency/response-time endpoint (authenticated):
   GET /emergency/response-time?city=Riyadh&target_zone=Zone_3
   Returns response time estimates from all stations to target zone

4. Add 2 tests:
   - test_critical_congestion_increases_response_time()
   - test_response_time_endpoint_returns_estimates()

DELIVERABLE:
- estimate_response_time() in src/model.py
- /emergency/response-time endpoint
- 2 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"It estimates emergency vehicle response time to any zone under
current traffic conditions — and flags when it exceeds the WHO
8-minute threshold."
```

---

## PROMPT 018 — Freight and Delivery Window Optimizer

```
MISSION: Recommend optimal delivery windows for freight vehicles
by zone and hour — reducing the urban freight congestion that
accounts for 15–25% of city traffic volume.

RESEARCH BASIS:
ITF-OECD (2024): Last Mile Delivery report — delivery vehicles
spend over 1 hour per day cruising for parking; 28% of trip time
wasted. ScienceDirect (2024): Dynamic Freight Management using
real-time traffic data reduces congestion and emissions in cities.
ScienceDirect (2022): curbside freight interventions reduce
externalities. Saudi Arabia: e-commerce growth driving sharp
increase in urban delivery vehicles in Riyadh's commercial zones.
Freight vehicles in the wrong zone at the wrong hour make
congestion significantly worse.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 017 complete — emergency response layer exists
- System knows congestion per zone per hour
- No freight-specific output exists anywhere in the system
- Cannot integrate with logistics company APIs — recommend windows only

PROBLEM TO SOLVE:
A logistics company asks: "When should our trucks deliver to Zone_2
to avoid adding to peak congestion?"
Current answer: nothing.
The system has all the data needed to answer this.

YOUR TASK:
1. Add FREIGHT_RESTRICTED_HOURS to src/config.py:
   FREIGHT_RESTRICTED_HOURS = {
       'Riyadh': {
           'Zone_1': [7, 8, 9, 17, 18, 19],   # KAFD financial district
           'Zone_2': [7, 8, 17, 18],
           'Zone_3': [12, 13],                  # prayer window extra restriction
       }
   }

2. Add get_delivery_windows(city, zone, df) to src/model.py:
   - Find hours where congestion_score < 0.35 for that zone
   - Exclude FREIGHT_RESTRICTED_HOURS
   - Exclude Friday prayer window for Saudi cities
   - Returns: {recommended_windows: list of hours,
               avoid_hours: list of hours,
               best_hour: int,
               rationale: str}

3. Add /freight/windows endpoint (authenticated):
   GET /freight/windows?city=Riyadh&zone=Zone_2
   Returns delivery window recommendations for that zone

4. Add 1 test:
   - test_freight_windows_excludes_restricted_hours()

DELIVERABLE:
- get_delivery_windows() in src/model.py
- /freight/windows endpoint working
- 1 new test passing
- Railway auto-deployed

RECRUITER SENTENCE:
"Logistics companies can query the optimal delivery window for
any zone — avoiding peak congestion and freight-restricted hours."
```

---

## PROMPT 019 — Historical Pattern Analysis API

```
MISSION: Build a historical query layer that lets operators and
planners retrieve traffic patterns for any past date, day type,
or weather condition — the foundation of evidence-based planning.

RESEARCH BASIS:
US DOT ITS JPO (2024): evidence-based transportation planning
requires historical data access for policy decisions. ScienceDirect
(2025) Saudi transport review: lack of historical data access is
a documented gap in KSA traffic management. Almatar (2024):
absence of longitudinal traffic records prevents robust policy
evaluation. The system logs every prediction — that log is a
growing historical record. Currently it is unqueryable.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 018 complete — freight window layer exists
- predictions_log.csv grows with every API call
- The log has: timestamp, city, zone, hour, weather,
  congestion_score, congestion_level
- No endpoint exists to query historical patterns from the log

PROBLEM TO SOLVE:
A transport planner asks: "What was average congestion in Zone_1
on sandstorm days in the past 30 days?"
Current answer: nothing.
The data exists. It is just not queryable.

YOUR TASK:
1. Add /history/patterns endpoint (authenticated):
   GET /history/patterns?city=Riyadh&zone=Zone_1&weather=sandstorm
                        &days=30
   - Reads predictions_log.csv
   - Filters by city, zone (optional), weather (optional), days back
   - Returns: {period_days, total_records, avg_congestion_score,
               peak_hour, peak_congestion, weather_breakdown,
               hourly_averages}

2. Add /history/trend endpoint (authenticated):
   GET /history/trend?city=Riyadh&zone=Zone_1&days=7
   - Returns daily average congestion_score for the past N days
   - Used to visualise trend direction (improving/worsening)
   - Returns: {dates: list, avg_scores: list, trend: 'improving' |
               'worsening' | 'stable'}

3. Add Trend chart to Streamlit dashboard Tab 4 (Model Insights):
   - 7-day trend line per zone from /history/trend
   - Shows whether congestion is improving or worsening

4. Add 2 tests:
   - test_history_patterns_returns_valid_structure()
   - test_history_trend_returns_correct_keys()

DELIVERABLE:
- /history/patterns and /history/trend endpoints
- Dashboard Tab 4 updated with trend chart
- 2 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"Planners can query historical congestion patterns by zone,
weather, and time period — and see whether conditions are
improving or worsening over the past 7 days."
```

---

## PROMPT 020 — Confidence Interval and Uncertainty Quantification

```
MISSION: Add prediction confidence intervals to every output so
operators know when to trust the model and when to apply human
judgement.

RESEARCH BASIS:
US DOT ITS JPO (2024): decision-support systems must communicate
uncertainty to operators. IEEE Transactions on ITS (2025): reliable
uncertainty quantification is a key gap in deployed traffic prediction
systems. Traffic engineering practice: a model that gives a point
estimate with no uncertainty measure is operationally dangerous —
operators cannot calibrate their response. The XGBoost model
currently outputs point predictions with no confidence measure.
The forecasting module already computes confidence intervals using
residual standard deviation — this needs to extend to single
predictions.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 019 complete — historical query layer exists
- explain_prediction() returns SHAP factors — no uncertainty
- forecast_congestion() already computes lower_bound / upper_bound
  using residual_std from historical zone data — that logic is reusable
- XGBoost does not natively produce prediction intervals — bootstrap
  or quantile regression are the documented approaches

PROBLEM TO SOLVE:
An operator sees: congestion_score: 0.62, level: High.
They do not know if the model is confident or guessing.
A 0.62 ± 0.03 is very different from 0.62 ± 0.25.
Deploying a system without uncertainty communication is
not production-grade — it is dangerous.

YOUR TASK:
1. Add compute_prediction_interval(model, X_row, feature_cols,
   df, zone, n_bootstrap=50) to src/model.py:
   - Bootstrap: resample training subset 50 times, get prediction
     distribution, return 5th and 95th percentile
   - Returns: {lower_bound, upper_bound, confidence_width,
               confidence_level: '90%'}

2. Add prediction_interval to /predict response

3. Add interval_width to predictions_log.csv logging

4. Update Streamlit dashboard Tab 5 (Forecasting):
   - Show single-prediction confidence interval as error bar
     alongside the existing forecast confidence band

5. Add 2 tests:
   - test_prediction_interval_lower_less_than_upper()
   - test_wide_interval_on_uncertain_inputs()

DELIVERABLE:
- compute_prediction_interval() in src/model.py
- /predict includes prediction_interval dict
- Dashboard Tab 5 updated with error bar
- 2 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"Every prediction includes a 90% confidence interval — operators
know exactly how certain the model is before acting on it."
```

---

## PROMPT 021 — Operator Alert and Notification System

```
MISSION: Build an alert system that proactively notifies operators
when zones breach predefined thresholds — instead of requiring
operators to poll the API manually.

RESEARCH BASIS:
US DOT ITS JPO (2024): proactive alerting is a defined requirement
for production ITS deployment. SWARCO (2024): Saudi Vision 2030
smart city rollout requires automated operator notification systems.
WSP (2024): modern traffic management centers require push-based
alerting, not pull-based monitoring. Current system: entirely
pull-based — operators must call /anomalies to find out what is
happening. A Critical zone could persist for hours unnoticed.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 020 complete — uncertainty quantification exists
- The scheduler already runs every night — same mechanism works
  for threshold monitoring every 15 minutes
- No notification infrastructure exists
- Use webhook delivery — most widely supported, no third-party
  dependency required

PROBLEM TO SOLVE:
Zone_2 goes Critical at 14:30.
No operator is looking at the dashboard at 14:30.
No alert fires.
The city does not know for 90 minutes.

YOUR TASK:
1. Add ALERT_THRESHOLDS to src/config.py:
   ALERT_THRESHOLDS = {
       'congestion_critical' : 0.75,
       'risk_critical'       : 0.70,
       'anomaly_ratio'       : 3.0,   # 3x expected volume
       'response_time_mins'  : 8,
   }

2. Add check_thresholds(df, city) to src/pipeline.py:
   - Runs detect_anomalies() on current df
   - Computes risk scores for all zones
   - Returns list of triggered alerts with zone, metric, value, threshold

3. Add deliver_webhook_alert(alerts, webhook_url) to src/pipeline.py:
   - POST JSON payload to WEBHOOK_URL from .env
   - Payload: {timestamp, city, alerts: list}
   - Fail silently if WEBHOOK_URL not set (not required for local dev)

4. Add to APScheduler in app.py:
   - Run check_thresholds every 15 minutes
   - If alerts triggered, call deliver_webhook_alert

5. Add WEBHOOK_URL to .env.example with documentation

6. Add /alerts/history endpoint (authenticated):
   GET /alerts/history?city=Riyadh&hours=24
   - Returns all alerts triggered in the past N hours from log

7. Add 2 tests:
   - test_check_thresholds_returns_list()
   - test_no_alerts_when_all_clear()

DELIVERABLE:
- check_thresholds() and deliver_webhook_alert() in src/pipeline.py
- 15-minute scheduler job in app.py
- /alerts/history endpoint
- WEBHOOK_URL in .env.example
- 2 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"The system monitors all zones every 15 minutes and fires webhook
alerts automatically when any zone breaches critical thresholds —
no operator needs to be watching."
```

---

## PROMPT 022 — Road Segment Speed Degradation Index

```
MISSION: Compute a speed degradation index per road type and zone
that quantifies how much weather and congestion are reducing
throughput below free-flow speed — a standard traffic engineering
metric.

RESEARCH BASIS:
Traffic engineering: the Speed Reduction Index (SRI) is a standard
measure used by DOTs worldwide to quantify service degradation.
Highway Capacity Manual (HCM): free-flow speed degradation is the
primary metric for level of service classification. Nature Scientific
Reports (2025): ML-based adaptive traffic prediction uses speed
deviation from free-flow as a core feature. Saudi-specific: sandstorm
conditions produce the largest speed degradation events in Gulf
cities — verified at 40% reduction in this system's own validated data.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 021 complete — alerting system exists
- avg_speed is already a feature in the model
- WEATHER_SPEED_IMPACT already contains speed multipliers per condition
- FREE_FLOW_SPEED is implicitly 100 km/h (max clip) in the system

PROBLEM TO SOLVE:
A road engineer asks: "What is the current level of service on
Zone_1's highway segment?"
Level of service requires a speed degradation calculation.
Current system: outputs congestion_score but no speed index.

YOUR TASK:
1. Add FREE_FLOW_SPEED_KMPH to src/config.py:
   FREE_FLOW_SPEED_KMPH = {
       'highway' : 100, 'arterial': 70, 'local': 50
   }

2. Add compute_speed_degradation_index(avg_speed, road_type,
   weather) to src/model.py:
   - SDI = (free_flow - avg_speed) / free_flow
   - Clip to [0.0, 1.0]
   - Level of service: A < 0.10, B 0.10–0.20, C 0.20–0.35,
                       D 0.35–0.50, E 0.50–0.70, F > 0.70
   - Returns: {sdi, level_of_service, free_flow_speed,
               current_speed, speed_loss_kmph}

3. Add sdi and level_of_service to /predict response

4. Add /roads/service-level endpoint (authenticated):
   GET /roads/service-level?city=Riyadh
   Returns all zones with current SDI and level of service
   Sorted by SDI descending

5. Add 2 tests:
   - test_sandstorm_produces_high_sdi()
   - test_service_level_endpoint_returns_all_zones()

DELIVERABLE:
- compute_speed_degradation_index() in src/model.py
- /predict includes sdi and level_of_service
- /roads/service-level endpoint
- 2 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"Every prediction includes a level of service rating — A through F —
using the Highway Capacity Manual classification. That's the language
of traffic engineers."
```

---

## PROMPT 023 — Pedestrian Safety Score per Zone

```
MISSION: Add a pedestrian safety score to high-risk zones based
on congestion, vehicle count, speed, and time of day — addressing
the documented gap between vehicle-centric traffic systems and
vulnerable road user protection.

RESEARCH BASIS:
WHO: 270,000 pedestrian fatalities annually worldwide. arXiv (2026):
AI systems detecting vulnerable road users and adjusting signal
timing in real time. PMC (2024): ML for pedestrian crossing
prediction in intelligent transportation systems. Frontiers in
Robotics and AI (2024): intersection safety for vulnerable road users.
Saudi-specific context: pedestrian infrastructure in Riyadh is
underdeveloped relative to vehicle infrastructure — Vision 2030
explicitly targets pedestrian-friendly urban design.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 022 complete — road service level exists
- Vehicle count, speed, hour, weather are all existing features
- Late night hours in Saudi cities: high speed, lower volume —
  documented as higher pedestrian risk even with low congestion
- Cannot detect actual pedestrians — score risk from traffic features

PROBLEM TO SOLVE:
A city urban planning director asks: "Which zones are most
dangerous for pedestrians right now?"
Current system: silent on pedestrian safety entirely.
Congestion and pedestrian risk are different things.

YOUR TASK:
1. Add compute_pedestrian_risk(vehicle_count, avg_speed, hour,
   weather, road_type) to src/model.py:
   - Base risk = (vehicle_count / 500) * (avg_speed / 100)
   - Highway = 1.4x multiplier (higher speed = higher severity)
   - Local road = 0.8x (lower speed)
   - Late night (21–23): 1.3x (high speed, low visibility, reduced caution)
   - Sandstorm: 1.5x (zero visibility for both drivers and pedestrians)
   - Rain / fog: 1.3x
   - Friday prayer (12–13): 0.6x (minimal vehicle activity)
   - Clip to [0.0, 1.0]
   - Returns: {pedestrian_risk_score, risk_category, primary_hazard}
   - Categories: Safe < 0.25, Moderate 0.25–0.50,
                 Dangerous 0.50–0.75, Critical > 0.75

2. Add pedestrian_risk to /predict response

3. Add /safety/pedestrian endpoint (authenticated):
   GET /safety/pedestrian?city=Riyadh
   Returns all zones ranked by pedestrian_risk_score, worst first
   Flags zones where pedestrian_risk > 0.60 as requiring intervention

4. Add 2 tests:
   - test_sandstorm_late_night_produces_high_pedestrian_risk()
   - test_pedestrian_endpoint_returns_ranked_zones()

DELIVERABLE:
- compute_pedestrian_risk() in src/model.py
- /predict includes pedestrian_risk
- /safety/pedestrian endpoint
- 2 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"The system scores pedestrian risk separately from vehicle
congestion — sandstorm at night in a highway zone is Critical
for pedestrians even when vehicle volume is low."
```

---

## PROMPT 024 — API Usage Analytics and Quota Management

```
MISSION: Track API usage per key, per endpoint, per day — giving
operators visibility into how the system is being used and the
foundation for multi-tenant billing.

RESEARCH BASIS:
Production API management standard: every production API needs
usage analytics before it can be sold to multiple clients.
Without usage data, there is no basis for pricing, SLA monitoring,
or capacity planning. This is not a traffic engineering problem —
it is the infrastructure problem that stands between a demo and
a product a city would pay for.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 023 complete — pedestrian safety layer exists
- Current system: one API key, no usage tracking
- Rate limiting exists (slowapi) but logs nothing permanently
- Moving toward multi-tenant: different cities, different keys

PROBLEM TO SOLVE:
A government client asks: "How many API calls did we make last month?
What endpoints did we use most?"
Current answer: nothing.
Without this, the system cannot be sold to multiple clients.

YOUR TASK:
1. Create usage_log.csv — logged alongside predictions_log.csv
   Columns: timestamp, endpoint, method, api_key_hash (first 8 chars),
            response_code, response_time_ms

2. Add log_api_usage(endpoint, method, key, status, duration) to
   src/pipeline.py — appends one row to usage_log.csv

3. Add usage logging middleware to app.py:
   - Intercepts every request after processing
   - Logs endpoint, method, hashed key, status, duration
   - Does not log request body (privacy)

4. Add /analytics/usage endpoint (authenticated):
   GET /analytics/usage?days=30
   - Reads usage_log.csv
   - Returns: {total_calls, calls_by_endpoint, calls_by_day,
               avg_response_time_ms, top_endpoint}

5. Add /analytics/quota endpoint (authenticated):
   GET /analytics/quota
   - Returns calls today vs daily limit (default 10,000)
   - Warns if > 80% of quota used

6. Add 2 tests:
   - test_usage_log_created_after_request()
   - test_analytics_endpoint_returns_valid_structure()

DELIVERABLE:
- Usage middleware in app.py
- log_api_usage() in src/pipeline.py
- /analytics/usage and /analytics/quota endpoints
- 2 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"The system tracks usage per endpoint per day — the foundation
for billing multiple city clients."
```

---

## PROMPT 025 — Multi-Tenant API Key Management

```
MISSION: Support multiple API keys with different permissions and
city access — making the system ready to serve multiple clients
simultaneously.

RESEARCH BASIS:
Production SaaS standard: multi-tenancy is the architectural
requirement that separates a single-client system from a product.
Vision 2030 context: multiple city authorities (Riyadh, NEOM,
KAEC, Diriyah) would each need isolated access with different
permissions. This is the last architectural gap before the system
can be sold as a service.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 024 complete — usage analytics exist
- Current system: one API_KEY from .env, full access
- Clients: city operators (read-only predictions), admins
  (pipeline trigger, data source switching), system owners (all)

PROBLEM TO SOLVE:
A second city wants to onboard.
There is no way to give them their own key with their own
city access without giving them access to everything.

YOUR TASK:
1. Replace single API_KEY with a key registry in .env:
   API_KEYS = key1:Riyadh:operator,key2:NEOM:operator,key3:*:admin
   Format: key:city_scope:role
   city_scope * = all cities
   Roles: operator (predict, forecast, anomalies),
          admin (+ pipeline, data source, analytics)

2. Add parse_key_registry(env_value) to src/pipeline.py:
   Returns dict: {key: {city, role}}

3. Update require_api_key() in app.py:
   - Load registry at startup
   - Return {key, city, role} on valid auth
   - 401 on invalid key

4. Add city_scope enforcement to all endpoints:
   - /predict: verify payload city matches key's city_scope
   - /anomalies: filter by key's city_scope
   - /forecast: filter by key's city_scope
   - Admin endpoints: require role == 'admin'

5. Update .env.example with API_KEYS format

6. Add 3 tests:
   - test_operator_key_blocked_from_admin_endpoint()
   - test_wrong_city_key_blocked_from_other_city()
   - test_admin_key_accesses_all_cities()

DELIVERABLE:
- Key registry replacing single API_KEY
- City scope and role enforcement on all endpoints
- .env.example updated
- 3 new tests passing
- Railway env vars updated

RECRUITER SENTENCE:
"Each city client gets their own API key scoped to their city —
operators cannot access other cities' data or admin endpoints."
```

---

## PROMPT 026 — Automated Performance Report Generator

```
MISSION: Generate a structured weekly PDF or HTML performance
report for city operators — documenting congestion trends, peak
events, anomalies, emissions, and system health.

RESEARCH BASIS:
US DOT ITS JPO (2024): automated reporting is a defined requirement
for government ITS contracts. Saudi government procurement: reports
are mandatory deliverables in smart city infrastructure contracts.
Almatar (2024): absence of standardized reporting is identified as
a gap in Saudi transport management. A city paying for a traffic
intelligence system requires regular documentation — not just
a dashboard.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 025 complete — multi-tenant key management exists
- predictions_log.csv, pipeline_log.csv, usage_log.csv all exist
- Historical query endpoints from PROMPT 019 can be reused
- Output format: HTML report (no external PDF library needed)

PROBLEM TO SOLVE:
A city director asks: "Can you give me a weekly report I can
present to the municipal council?"
Current answer: nothing.
Without reports, the system cannot fulfil a government contract.

YOUR TASK:
1. Create src/reporter.py with:
   generate_weekly_report(city, output_path) -> str:
   - Reads predictions_log.csv for the past 7 days
   - Reads pipeline_log.csv for drift events
   - Reads usage_log.csv for API activity
   - Generates an HTML report with:
     a. Executive summary: total predictions, peak zone, peak hour
     b. Congestion trend chart (embedded base64 matplotlib image)
     c. Top 5 anomaly events with timestamp and severity
     d. Emissions summary: total CO2, worst zone
     e. System health: drift score, last retrain, API uptime
     f. Saudi Green Initiative compliance section

2. Add /reports/weekly endpoint (authenticated, admin role):
   POST /reports/weekly?city=Riyadh
   - Calls generate_weekly_report()
   - Returns the HTML as a file download response

3. Add 1 test:
   - test_weekly_report_generates_valid_html()

DELIVERABLE:
- src/reporter.py with generate_weekly_report()
- /reports/weekly endpoint
- 1 test passing
- Railway auto-deployed

RECRUITER SENTENCE:
"The system generates a weekly HTML performance report — ready
for a municipal council presentation — automatically."
```

---

## PROMPT 027 — Real-Time WebSocket Streaming Endpoint

```
MISSION: Add a WebSocket endpoint that streams live congestion
updates every 30 seconds — enabling real-time dashboard updates
without polling.

RESEARCH BASIS:
ITS architecture standard: real-time traffic management centers
require push-based data streams, not request-response polling.
SWARCO (2024): Vision 2030 smart city infrastructure requires
continuous data streams to command-and-control centers. Current
system: Streamlit dashboard refreshes only when the user manually
triggers it or sets a fixed timer. A command center screen cannot
rely on manual refresh.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 026 complete — automated reporting exists
- FastAPI natively supports WebSockets — no new dependency
- app.state.df is updated at startup — stream the current
  congestion snapshot from that data every 30 seconds
- Streamlit does not support WebSocket clients natively —
  the endpoint is for external command center integrations

PROBLEM TO SOLVE:
A traffic operations center has a wall screen showing Zone_1.
It updates every 5 minutes via polling.
A congestion event develops in 2 minutes.
The screen does not update.
Real-time means real-time.

YOUR TASK:
1. Add WebSocket endpoint to app.py:
   @app.websocket("/ws/live/{city}")
   - On connect: send current congestion snapshot for all zones
   - Every 30 seconds: resend updated snapshot
   - Snapshot format per zone: {zone, congestion_score, level,
     risk_score, anomaly_flag, timestamp}
   - Disconnect cleanly on client close

2. Add WebSocket authentication:
   - Accept api_key as query parameter: /ws/live/Riyadh?api_key=xxx
   - Close with code 1008 if invalid

3. Create a minimal test HTML file tests/ws_test.html:
   - Opens WebSocket to localhost
   - Displays live zone updates in a table
   - For manual testing only — not part of pytest suite

4. Add 1 test:
   - test_websocket_rejects_invalid_key()

DELIVERABLE:
- /ws/live/{city} WebSocket endpoint in app.py
- API key authentication on WebSocket
- tests/ws_test.html for manual testing
- 1 test passing
- Railway auto-deployed

RECRUITER SENTENCE:
"The system streams live zone congestion via WebSocket every
30 seconds — ready for integration with a traffic operations
command center."
```

---

## PROMPT 028 — Data Quality Monitoring and Validation Pipeline

```
MISSION: Monitor incoming data quality in real time and flag
degraded or anomalous sensor readings before they corrupt
predictions — the production data engineering standard.

RESEARCH BASIS:
Emerald ITS Journal (2025): data quality is identified as the
primary unresolved problem in deployed AI transportation systems.
US DOT ITS JPO (2024): data quality validation is a mandatory
component of ITS deployment standards. Nature Scientific Reports
(2025): ML-based traffic prediction systems fail silently on
bad data — quality checks are a prerequisite for trust.
The system currently assumes all incoming data is valid.
A single bad sensor reading (vehicle_count = 50,000) would
produce a nonsensical prediction logged to the audit trail.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 027 complete — WebSocket streaming exists
- validate_data() already checks statistical properties of
  the synthetic training data — not incoming predictions
- The /predict endpoint accepts user-supplied values with
  only Pydantic type validation — no range or plausibility checks

PROBLEM TO SOLVE:
A caller sends vehicle_count: 5000 for a local road zone.
The system accepts it, logs it, makes a nonsensical prediction.
The audit trail is now corrupted.
No alert fires.

YOUR TASK:
1. Add validate_prediction_input(payload_dict) to src/pipeline.py:
   Checks:
   - vehicle_count: 0–500 for this system (clip range from config)
   - avg_speed: 20–100 km/h (clip range from config)
   - hour_multiplier: 0.05–3.0 (reasonable range)
   - weather: must be in WEATHER_ENCODING keys
   - zone: must be in ZONE_ENCODING keys
   - road_type: must be in ROAD_ENCODING keys
   Returns: {valid: bool, warnings: list, errors: list}

2. Update /predict in app.py:
   - Call validate_prediction_input() before processing
   - If errors: return 422 with validation detail
   - If warnings only: process but add warnings to response

3. Add /data/quality endpoint (authenticated):
   GET /data/quality?city=Riyadh&hours=24
   - Reads predictions_log.csv for past N hours
   - Returns: {total_predictions, flagged_predictions,
               flag_rate_pct, common_warnings}

4. Add 3 tests:
   - test_out_of_range_vehicle_count_returns_422()
   - test_invalid_weather_returns_422()
   - test_valid_input_includes_no_warnings()

DELIVERABLE:
- validate_prediction_input() in src/pipeline.py
- /predict returns 422 on invalid input with clear detail
- /data/quality endpoint
- 3 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"The system validates every incoming prediction request against
plausibility ranges before processing — bad sensor data cannot
corrupt the audit trail."
```

---

## PROMPT 029 — SLA Monitoring and Uptime Reporting

```
MISSION: Track system uptime, response latency, and SLA compliance —
the contractual requirement for any government infrastructure contract.

RESEARCH BASIS:
Saudi government procurement standard: IT infrastructure contracts
require documented SLA compliance reporting. US DOT ITS JPO (2024):
SLA monitoring is a defined operational requirement for deployed ITS.
SWARCO (2024): smart city infrastructure contracts specify uptime
minimums and response time SLAs. Without SLA documentation, the
system cannot enter a government procurement process.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 028 complete — data quality monitoring exists
- usage_log.csv already records response_time_ms per request
- UptimeRobot monitors /health externally
- No internal SLA calculation exists anywhere in the system

PROBLEM TO SOLVE:
A procurement officer asks: "What was your system uptime last month?
What is your average response time? Do you meet a 99% uptime SLA?"
Current answer: nothing provable.
Without documented SLA performance, the contract does not proceed.

YOUR TASK:
1. Add compute_sla_metrics(days=30) to src/pipeline.py:
   - Reads usage_log.csv
   - Computes: uptime_pct (requests with status 200 / total),
     avg_response_ms, p95_response_ms, p99_response_ms,
     total_requests, error_rate_pct
   - SLA targets: uptime >= 99.0%, avg_response < 500ms,
     p95_response < 1000ms
   - Returns: {period_days, uptime_pct, sla_uptime_met,
               avg_response_ms, p95_response_ms,
               sla_response_met, error_rate_pct, total_requests}

2. Add /sla/report endpoint (authenticated, admin role):
   GET /sla/report?days=30
   - Calls compute_sla_metrics()
   - Returns full SLA compliance report
   - Includes: met_all_slas: bool

3. Add /sla/current endpoint (public):
   GET /sla/current
   - Returns last 24h SLA metrics without authentication
   - Used for public status page

4. Add 2 tests:
   - test_sla_report_returns_valid_structure()
   - test_sla_current_is_public()

DELIVERABLE:
- compute_sla_metrics() in src/pipeline.py
- /sla/report and /sla/current endpoints
- 2 new tests passing
- Railway auto-deployed

RECRUITER SENTENCE:
"The system generates SLA compliance reports — uptime percentage,
p95 response time, error rate — the contractual documentation a
government procurement requires."
```

---

## PROMPT 030 — Government API Documentation and Onboarding Package

```
MISSION: Produce a formal API documentation package, onboarding
guide, and integration specification — the documents a city IT
department needs before they can procure and deploy the system.

RESEARCH BASIS:
Saudi government digital transformation: Vision 2030 digital
infrastructure projects require formal technical documentation
for procurement. US DOT ITS JPO (2024): formal interface
specifications are mandatory for ITS deployment. Real-world
constraint: no government IT department will deploy a system
without formal documentation, regardless of technical quality.
The system is technically complete at PROMPT 029. PROMPT 030
is the documentation that unlocks procurement.

CONTEXT:
- Read PROJECT_CONTEXT.md and IMPROVEMENT_CHAIN_V2.md
- PROMPT 029 complete — SLA monitoring exists
- /docs already provides Swagger UI auto-generated from FastAPI
- DEMO.md exists for recruiters
- No formal government-facing documentation exists

PROBLEM TO SOLVE:
A city IT department receives the system for procurement review.
They need: API specification, data dictionary, integration guide,
security documentation, SLA terms.
Current state: only Swagger UI and DEMO.md.
Government procurement requires more.

YOUR TASK:
1. Create TECHNICAL_SPEC.md:
   a. System architecture diagram (ASCII — no images needed)
   b. All endpoints with request/response schemas, auth requirements,
      rate limits, error codes
   c. Data dictionary: every field in every response with type,
      range, unit, and description
   d. Saudi-specific calibration documentation:
      Friday prayer, Ramadan, Hajj, sandstorm protocols
   e. Statistical validation results (5/5 checks, actual values)

2. Create INTEGRATION_GUIDE.md:
   a. Step-by-step integration for a city IT team
   b. Authentication: how to request and use API keys
   c. Rate limit handling: retry logic with Retry-After header
   d. Webhook setup for alert delivery
   e. WebSocket connection for real-time feeds
   f. Example integration code in Python and PowerShell

3. Create SECURITY_POLICY.md:
   a. Authentication mechanism
   b. Data retention: what is logged, how long
   c. Data in transit: HTTPS enforced by Railway
   d. No PII collected policy
   e. Key rotation procedure

4. Create SLA_TERMS.md:
   a. Uptime commitment: 99% monthly
   b. Response time: avg < 500ms, p95 < 1000ms
   c. Planned maintenance: 03:00–04:00 daily (retraining window)
   d. Incident response: alert within 15 minutes of breach
   e. Exclusions: Ramadan/Hajj demand spikes

5. Update README.md top section with links to all four documents

DELIVERABLE:
- TECHNICAL_SPEC.md
- INTEGRATION_GUIDE.md
- SECURITY_POLICY.md
- SLA_TERMS.md
- README updated with document links
- All files committed and pushed to GitHub

RECRUITER SENTENCE:
"Here is the technical specification, integration guide, security
policy, and SLA terms. Your IT department can begin procurement
review today."
```

---

## THE TRAJECTORY

```
PROMPT 001–005  : Portfolio foundation (COMPLETE)
PROMPT 006      : Security layer (COMPLETE)
PROMPT 007      : Automated testing (COMPLETE)
PROMPT 008      : Real data adapters (COMPLETE)
PROMPT 009      : Drift detection + auto-retraining (COMPLETE)
PROMPT 010      : Cloud deployment — live URLs (COMPLETE)

PROMPT 011      : Emissions and CO2 layer
PROMPT 012      : Hajj mode — Saudi exclusive
PROMPT 013      : Demand intervention — commuter advice
PROMPT 014      : Accident risk scoring
PROMPT 015      : Adaptive signal timing recommendations
PROMPT 016      : Multi-city comparative dashboard
PROMPT 017      : Emergency vehicle response time estimator
PROMPT 018      : Freight delivery window optimizer
PROMPT 019      : Historical pattern analysis API
PROMPT 020      : Prediction confidence intervals

PROMPT 021      : Operator alert and webhook notification
PROMPT 022      : Road segment speed degradation index (HCM)
PROMPT 023      : Pedestrian safety score
PROMPT 024      : API usage analytics and quota management
PROMPT 025      : Multi-tenant key management
PROMPT 026      : Automated weekly HTML report generator
PROMPT 027      : WebSocket real-time streaming endpoint
PROMPT 028      : Data quality monitoring and validation
PROMPT 029      : SLA monitoring and uptime reporting
PROMPT 030      : Government documentation package
```

---

## WHAT EACH PROMPT UNLOCKS IN A RECRUITER CONVERSATION

| Prompt | Sentence | Status |
|---|---|---|
| 006 | "Authenticated and rate-limited — not an open endpoint." | ✅ Done |
| 007 | "20 automated tests, 85% coverage, CI/CD on every push." | ✅ Done |
| 008 | "Fetches live Riyadh weather from Open-Meteo right now." | ✅ Done |
| 009 | "Detects drift and retrains itself automatically at 3AM." | ✅ Done |
| 010 | "Here's the URL — test it on your phone right now." | ✅ Done |
| 011 | "Every prediction includes CO2 output against Green Initiative targets." | Pending |
| 012 | "Has a dedicated Hajj mode — inbound, peak, dispersal phases." | Pending |
| 013 | "Tells commuters which metro station to use when a zone hits Critical." | Pending |
| 014 | "Scores accident risk per zone — not just congestion volume." | Pending |
| 015 | "Outputs green phase durations — direct input for adaptive signal controllers." | Pending |
| 016 | "Compares Riyadh, NEOM, Dubai simultaneously in one dashboard view." | Pending |
| 017 | "Estimates ambulance response time under current traffic — flags WHO threshold breaches." | Pending |
| 018 | "Tells logistics companies the optimal delivery window per zone." | Pending |
| 019 | "Planners can query historical patterns by zone, weather, and date range." | Pending |
| 020 | "Every prediction includes a 90% confidence interval." | Pending |
| 021 | "Fires webhook alerts automatically when any zone breaches critical thresholds." | Pending |
| 022 | "Reports level of service A–F using Highway Capacity Manual classification." | Pending |
| 023 | "Scores pedestrian danger separately from vehicle congestion." | Pending |
| 024 | "Tracks API usage per endpoint per day — foundation for billing." | Pending |
| 025 | "Each city client has a scoped API key — Riyadh cannot access NEOM data." | Pending |
| 026 | "Generates a weekly HTML report ready for a municipal council presentation." | Pending |
| 027 | "Streams live zone congestion via WebSocket — for traffic operations command centers." | Pending |
| 028 | "Validates every incoming request against plausibility ranges — bad data cannot corrupt the audit trail." | Pending |
| 029 | "Generates SLA compliance reports — the contractual documentation government procurement requires." | Pending |
| 030 | "Here is the technical specification, integration guide, security policy, and SLA terms. Procurement can begin today." | Pending |
