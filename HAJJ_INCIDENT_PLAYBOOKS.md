# HAJJ INCIDENT RESPONSE PLAYBOOKS

**Source:** `generate_hajj_playbook()` in `src/model.py`  
**Live endpoint:** `GET /hajj/playbook?incident_type=X&severity=Y&phase=Z` (OPERATOR+)  
**HTML format:** append `&format=html` for printable operator card

---

## Incident Types Covered

| Incident Type | Phases | Steps (critical) | Prayer Constrained |
|---|---|---|---|
| crowd_crush_risk | all | 7 | ✅ Step 5 |
| mass_vehicle_breakdown | all | 6 | ❌ |
| sandstorm_onset | all | 7 | ❌ |
| medical_emergency_convoy | all | 6 | ❌ |

---

## Prayer-Time Constraint Logic

`FRIDAY_PRAYER_HOURS = [12, 13]` (from `src/config.py`)

- **`crowd_crush_risk` Step 5** (forced road closure / pilgrim access suspension) is marked `prayer_time_hold=True`
- If current time falls within hours 12–13 on a Friday, this action must be delayed until ~13:30 local
- `time_limit_minutes` is extended by +60 for held actions
- All other actions in all other playbooks proceed without prayer-time gating (they do not involve forced closures or mass crowd redirection incompatible with Jumu'ah)

---

## CROWD_CRUSH_RISK — Critical / Peak

| Step | Action | Responsible Party | Time Limit | Prayer Hold |
|---|---|---|---|---|
| 1 | Activate crowd density sensors Zone_1 & Zone_3; confirm > 90% utilisation | Traffic Control Operator | 2 min | — |
| 2 | Issue VMS alerts redirecting pilgrims to Zone_2 / Zone_4 | Traffic Control Operator | 3 min | — |
| 3 | Extend green phase Zone_2 & Zone_4 by 30s; reduce pedestrian crossing intervals | Signal Control (auto) | 2 min | — |
| 4 | Notify Hajj Operations Command (MOI); deploy crowd management teams | Incident Commander | 5 min | — |
| 5 | Preemption: suspend non-emergency vehicle access to Zone_3 | OPERATOR + Field Unit | **+60 min if prayer hour** | ⚠️ Yes |
| 6 | Reroute feeder buses away from Zone_1 until density < 75% | Transit Coordinator | 10 min | — |
| 7 | Monitor every 2 min; escalate if cascade depth > 2 | Traffic Control Operator | 30 min | — |

---

## MASS_VEHICLE_BREAKDOWN — Critical / Peak

| Step | Action | Responsible Party | Time Limit |
|---|---|---|---|
| 1 | Confirm stalled vehicles via camera; log zone and lane | Traffic Control Operator | 3 min |
| 2 | Dispatch recovery units; update ETA on dashboard | Incident Commander | 5 min |
| 3 | Activate contraflow if breakdown blocks > 50% of road width | Field Unit + OPERATOR | 6 min |
| 4 | VMS: warn of reduced capacity; suggest Zone_5 bypass | Traffic Control Operator | 3 min |
| 5 | Reroute freight and non-pilgrimage vehicles via Ring Road | Freight Coordinator | 8 min |
| 6 | Confirm clearance; restore signal timing; log to predictions_log | Traffic Control Operator | 60 min |

---

## SANDSTORM_ONSET — Critical / Peak

| Step | Action | Responsible Party | Time Limit |
|---|---|---|---|
| 1 | Confirm via Open-Meteo API flag or RWIS visibility < 200m | System (auto) | 1 min |
| 2 | Apply VSL: reduce speed limits 40% across all zones | Signal Control (auto) | 2 min |
| 3 | Activate hazard lighting / strobe markers on Zone_1 & Zone_3 | Field Unit | 5 min |
| 4 | Issue public advisory via VMS + NCM alert channel | Incident Commander | 5 min |
| 5 | Suspend open-top shuttles and outdoor crowd ops until visibility > 500m | Transit Coordinator | 10 min |
| 6 | Monitor every 10 min; escalate to road closure if visibility < 50m | Traffic Control Operator | 60 min |
| 7 | Staged restoration: Zone_5 → Zone_4 → Zone_2 → Zone_3 → Zone_1 | Incident Commander | 120 min |

---

## MEDICAL_EMERGENCY_CONVOY — Critical / Peak

| Step | Action | Responsible Party | Time Limit |
|---|---|---|---|
| 1 | Receive SRCA convoy request; confirm origin, destination, vehicle count | Traffic Control Operator | 2 min |
| 2 | Run `generate_preemption_plan()`: calculate green wave corridor | System (auto) | 1 min |
| 3 | Activate signal preemption along convoy route; hold cross-traffic red | Signal Control (auto) | 2 min |
| 4 | Broadcast convoy alert via VMS; clear shoulder lanes | Traffic Control Operator | 2 min |
| 5 | Field units deployed at Zone_1/Zone_3 intersection for manual enforcement | Field Unit | 4 min |
| 6 | Confirm convoy cleared; restore normal timing; log event | Traffic Control Operator | 30 min |

---

## Severity Scaling

| Severity | Time Limit Scaling |
|---|---|
| critical | × 0.6 (faster response required) |
| moderate | × 1.0 (baseline) |
| minor | × 1.5 (standard ops tempo) |

*Generate live via `GET /hajj/playbook?incident_type=crowd_crush_risk&severity=critical&phase=peak&format=html`*
