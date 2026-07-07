from typing import Dict, List, Optional


CITY_PROFILES: Dict[str, Dict] = {
    'Riyadh': {
        'base_vehicles'     : 120,
        'weather_conditions': ['clear', 'sandstorm', 'dust'],
        'weather_probs'     : [0.75, 0.15, 0.10],
        'speed_mean'        : 65,
        'weekend'           : ['Friday', 'Saturday'],
        'timezone'          : 'Asia/Riyadh',
        'zones'             : 5
    },
    'NEOM': {
        'base_vehicles'     : 80,
        'weather_conditions': ['clear', 'sandstorm', 'dust'],
        'weather_probs'     : [0.70, 0.20, 0.10],
        'speed_mean'        : 80,
        'weekend'           : ['Friday', 'Saturday'],
        'timezone'          : 'Asia/Riyadh',
        'zones'             : 5
    },
    'Dubai': {
        'base_vehicles'     : 150,
        'weather_conditions': ['clear', 'sandstorm', 'humid'],
        'weather_probs'     : [0.70, 0.20, 0.10],
        'speed_mean'        : 70,
        'weekend'           : ['Friday', 'Saturday'],
        'timezone'          : 'Asia/Dubai',
        'zones'             : 5
    },
    'Karachi': {
        'base_vehicles'     : 200,
        'weather_conditions': ['clear', 'rain', 'fog'],
        'weather_probs'     : [0.65, 0.25, 0.10],
        'speed_mean'        : 45,
        'weekend'           : ['Saturday', 'Sunday'],
        'timezone'          : 'Asia/Karachi',
        'zones'             : 5
    }
}

HOURLY_MULTIPLIERS: Dict[str, Dict[int, float]] = {
    'standard': {
        0: 0.3,  1: 0.2,  2: 0.2,  3: 0.2,  4: 0.3,
        5: 0.5,  6: 0.8,  7: 1.4,  8: 1.5,  9: 1.1,
        10: 1.0, 11: 1.0, 12: 0.9, 13: 1.0, 14: 1.0,
        15: 1.1, 16: 1.3, 17: 1.5, 18: 1.4, 19: 1.1,
        20: 1.0, 21: 1.1, 22: 1.2, 23: 0.7
    },
    'saudi': {
        0: 0.6,  1: 0.5,  2: 0.4,  3: 0.3,  4: 0.4,
        5: 0.6,  6: 0.9,  7: 1.3,  8: 1.4,  9: 1.1,
        10: 1.0, 11: 1.0, 12: 0.5, 13: 0.4, 14: 0.8,
        15: 1.1, 16: 1.3, 17: 1.5, 18: 1.4, 19: 1.2,
        20: 1.4, 21: 1.5, 22: 1.4, 23: 1.1
    },
    'ramadan': {
        0: 1.2,  1: 1.3,  2: 1.0,  3: 0.6,  4: 0.4,
        5: 0.3,  6: 0.3,  7: 0.4,  8: 0.5,  9: 0.6,
        10: 0.6, 11: 0.5, 12: 0.4, 13: 0.4, 14: 0.4,
        15: 0.5, 16: 0.6, 17: 0.5, 18: 1.5, 19: 1.6,
        20: 1.5, 21: 1.4, 22: 1.4, 23: 1.3
    }
}


RAMADAN_IFTAR_HOUR = 18
RAMADAN_PROGRESSION_FACTOR = 0.015


WEATHER_SPEED_IMPACT: Dict[str, float] = {
    'sandstorm': 0.60,
    'fog'      : 0.70,
    'rain'     : 0.80,
    'dust'     : 0.85,
    'humid'    : 0.95,
    'clear'    : 1.00
}

CONGESTION_THRESHOLDS = {
    'Low'     : 0.20,
    'Moderate': 0.40,
    'High'    : 0.60,
    'Critical': 1.00
}

FRIDAY_PRAYER_HOURS: List[int] = [12, 13]
SAUDI_CITIES: List[str]        = ['Riyadh', 'NEOM', 'Jeddah', 'Dammam']

PALETTE = {
    'primary'   : '#1B4F72',
    'secondary' : '#2E86C1',
    'accent'    : '#E67E22',
    'danger'    : '#C0392B',
    'success'   : '#1E8449',
    'neutral'   : '#717D7E',
    'background': '#FDFEFE',
    'grid'      : '#EAECEE'
}

# --- Emissions constants (PROMPT 011) ---
FUEL_CONSUMPTION_LPH: Dict[str, float] = {
    'Low'     : 6.5,
    'Moderate': 9.2,
    'High'    : 13.8,
    'Critical': 18.4,
}
CO2_KG_PER_LITRE: float  = 2.31
AVG_ZONE_AREA_KM2: float = 2.5

# --- Hajj schedule constants (PROMPT 012) ---

HAJJ_DATES: Dict[int, Dict[str, str]] = {
    2025: {'start': '2025-06-04', 'end': '2025-06-09'},
    2026: {'start': '2026-05-24', 'end': '2026-05-29'},
}

# Hourly multipliers for each Hajj phase.
# Keys are anchor hours; intermediate hours interpolate via nearest-key lookup
# in apply_hourly_patterns().
HAJJ_INBOUND: Dict[int, float] = {
    0: 0.3, 6: 1.8, 9: 2.2, 12: 2.5, 15: 2.0, 18: 1.8, 21: 1.5
}
HAJJ_PEAK: Dict[int, float] = {
    0: 1.2, 6: 2.2, 9: 2.8, 12: 3.0, 15: 2.8, 18: 2.5, 21: 2.0
}
HAJJ_OUTBOUND: Dict[int, float] = {
    0: 0.8, 6: 2.5, 9: 2.2, 12: 2.0, 15: 1.8, 18: 1.5, 21: 0.9
}

# Zones along pilgrimage routes — receive an additional 1.8x multiplier.
HAJJ_ROUTE_ZONES: List[str] = ['Zone_1', 'Zone_3']


# ---Hajj Crowd Density Gradient ---
HAJJ_CROWD_DENSITY_GRADIENT: Dict[str, Dict[str, float]] = {
    'inbound' : {'Zone_1': 2.2, 'Zone_3': 2.0, 'Zone_2': 1.6, 'Zone_4': 1.3, 'Zone_5': 1.1},
    'peak'    : {'Zone_1': 3.0, 'Zone_3': 2.8, 'Zone_2': 2.2, 'Zone_4': 1.8, 'Zone_5': 1.4},
    'outbound': {'Zone_1': 2.5, 'Zone_3': 2.2, 'Zone_2': 1.8, 'Zone_4': 1.5, 'Zone_5': 1.2},
}
HAJJ_CROWD_WAVE_DELAY_HOURS: Dict[str, int] = {
    'Zone_1': 0, 'Zone_2': 2, 'Zone_3': 1, 'Zone_4': 3, 'Zone_5': 4,
}



# --- Intervention and demand-shifting constants---

METRO_STATIONS: Dict[str, str] = {
    'Zone_1': 'King Abdullah Financial District Station',
    'Zone_2': 'King Fahd Road Station',
    'Zone_3': 'Olaya Station',
    'Zone_4': 'Al Malaz Station',
}

CARPOOL_LANES: List[str] = ['Zone_1', 'Zone_2']

OFF_PEAK_WINDOWS: Dict[str, Dict[str, str]] = {
    'morning': {'recommended': '06:30', 'avoid_until': '09:30'},
    'evening': {'recommended': '15:30', 'avoid_until': '18:30'},
}


# ---------------------------------------------------------------------------
#  — Emergency Vehicle Response Time
# ---------------------------------------------------------------------------

EMERGENCY_STATIONS: Dict[str, Dict] = {
    'Riyadh': {
        'Central': {'zone': 'Zone_1', 'lat': 24.688, 'lon': 46.722},
        'North':   {'zone': 'Zone_3', 'lat': 24.774, 'lon': 46.738},
    },
    'NEOM': {
        'Central': {'zone': 'Zone_1', 'lat': 28.250, 'lon': 35.500},
    },
    'Dubai': {
        'Central': {'zone': 'Zone_1', 'lat': 25.204, 'lon': 55.270},
    },
    'Karachi': {
        'Central': {'zone': 'Zone_1', 'lat': 24.860, 'lon': 67.001},
    },
}

ZONE_DISTANCES_KM: Dict[tuple, float] = {
    ('Zone_1', 'Zone_2'): 3.2,
    ('Zone_1', 'Zone_3'): 5.8,
    ('Zone_1', 'Zone_4'): 7.1,
    ('Zone_1', 'Zone_5'): 9.4,
    ('Zone_2', 'Zone_3'): 4.1,
    ('Zone_2', 'Zone_4'): 5.9,
    ('Zone_2', 'Zone_5'): 8.2,
    ('Zone_3', 'Zone_4'): 3.3,
    ('Zone_3', 'Zone_5'): 6.1,
    ('Zone_4', 'Zone_5'): 4.2,
}

EMERGENCY_SPEED_KMPH: Dict[str, int] = {
    'Low':      75,
    'Moderate': 60,
    'High':     45,
    'Critical': 30,
}

WHO_RESPONSE_THRESHOLD_MINS: int = 8


FREIGHT_RESTRICTED_HOURS: Dict[str, Dict[str, list]] = {
    'Riyadh': {
        'Zone_1': [7, 8, 9, 17, 18, 19],   # KAFD financial district
        'Zone_2': [7, 8, 17, 18],
        'Zone_3': [12, 13],                  # prayer window extra restriction
    },
    'NEOM': {
        'Zone_1': [7, 8, 17, 18],
    },
    'Dubai': {
        'Zone_1': [7, 8, 9, 17, 18, 19],
        'Zone_2': [7, 8, 17, 18],
    },
    'Karachi': {
        'Zone_1': [8, 9, 17, 18],
        'Zone_2': [8, 9, 17, 18],
    },
}



# ---------------------------------------------------------------------------
# — Operator Alert Thresholds
# ---------------------------------------------------------------------------

ALERT_THRESHOLDS: Dict[str, float] = {
    'congestion_critical' : 0.75,
    'risk_critical'       : 0.70,
    'anomaly_ratio'       : 3.0,
    'response_time_mins'  : 8.0,
}

ALERT_THRESHOLDS["incident_severity_min"] = "Moderate"


SLA_TARGETS: Dict[str, float] = {
    'uptime_pct'      : 99.0,
    'avg_response_ms' : 500.0,
    'p95_response_ms' : 1000.0,
    'error_rate_pct'  : 1.0,
}
SLA_BREACH_SEVERITY: Dict[str, str] = {
    'uptime_pct'      : 'Critical',
    'avg_response_ms' : 'Elevated',
    'p95_response_ms' : 'Elevated',
    'error_rate_pct'  : 'High',
}
SLA_TREND_WINDOW_DAYS: int = 7



INCIDENT_SPEED_DROP_THRESHOLD: float = 0.40   # 40% sudden speed drop → suspect incident
INCIDENT_VOLUME_DROP_THRESHOLD: float = 0.30   # 30% volume drop with speed drop → blocked lane
INCIDENT_PERSISTENCE_MINUTES: int    = 10      # must persist N minutes to confirm
INCIDENT_SEVERITY_LEVELS: Dict[str, float] = {
    "Minor":    0.20,   # speed drop 20–40%
    "Moderate": 0.40,   # speed drop 40–60%
    "Major":    0.60,   # speed drop > 60%
    "Critical": 0.80,   # near-zero speed + volume collapse
}



# ---------------------------------------------------------------------------
#  Road Segment Speed Degradation Index
# ---------------------------------------------------------------------------

FREE_FLOW_SPEED_KMPH: Dict[str, int] = {
    'highway' : 100,
    'arterial': 70,
    'local'   : 50,
}


# --- Micro-mobility constants ---

MICROMOBILITY_CAPACITY_SHRINKAGE: float = 0.95
LAST_MILE_TRANSFER_ZONES: List[str]     = ['Zone_1', 'Zone_2', 'Zone_3']



MULTIMODAL_INDEX_WEIGHTS: Dict[str, float] = {
    'vehicle'   : 0.35,
    'last_mile' : 0.30,
    'drt'       : 0.25,
    'pedestrian': 0.10,
}
MULTIMODAL_LEVEL_THRESHOLDS: Dict[str, float] = {
    'Good'    : 0.70,
    'Adequate': 0.50,
    'Stressed': 0.30,
    # below Stressed → Crisis
}




SCOOTER_VELOCITY_THRESHOLD_KMPH: float  = 20.0
BIKE_VELOCITY_THRESHOLD_KMPH: float     = 25.0
GREEN_INITIATIVE_CO2_THRESHOLD_KG: float = 500.0


# --- Pavement wear constants ---

PAVEMENT_WEAR_COEFFICIENT_STANDARD: float = 1.0
PAVEMENT_WEAR_COEFFICIENT_HEAVY: float    = 3.5
BASE_HEAT_DEGRADATION_FACTOR: float       = 1.15
HEAT_THRESHOLD_CELSIUS: float             = 38.0
PAVEMENT_RISK_THRESHOLDS: Dict[str, float] = {
    'Low'     : 30.0,
    'Moderate': 55.0,
    'High'    : 75.0,
}





# --- V2X cooperative routing constants---

ZONE_ADJACENCY: Dict[str, List[str]] = {
    'Zone_1': ['Zone_2', 'Zone_3'],
    'Zone_2': ['Zone_1', 'Zone_4'],
    'Zone_3': ['Zone_1', 'Zone_5'],
    'Zone_4': ['Zone_2', 'Zone_5'],
    'Zone_5': ['Zone_3', 'Zone_4'],
}
AV_PENETRATION_SCENARIOS: List[float] = [0.10, 0.30, 0.50]
COOPERATIVE_ROUTING_INTERVAL_S: int   = 300

SCENARIO_VEHICLE_COUNT_CLIP_MAX = 500
SCENARIO_SPEED_CLIP_MIN         = 5.0
SCENARIO_SPEED_CLIP_MAX         = 120.0



# --- EV charging constants  ---

EV_FAST_CHARGING_STATIONS: Dict[str, Dict] = {
    'Olaya_Hub'  : {'chargers': 12, 'grid_capacity_kw': 1500},
    'KAFD_East'  : {'chargers': 24, 'grid_capacity_kw': 3000},
    'MBS_Road'   : {'chargers': 8,  'grid_capacity_kw': 1000},
}
CHARGE_RATE_KW: float           = 150.0
PEAK_GRID_LOAD_THRESHOLD: float = 0.85




# --- Dynamic congestion pricing constants ---
BASE_TOLL_RATE_SAR: float         = 5.0
MAX_DYNAMIC_TOLL_SAR: float       = 35.0
TOLL_CONGESTION_MULTIPLIER: float = 6.0
TOLL_EXEMPT_VEHICLES: List[str]   = ['emergency', 'public_bus']
TOLLED_ZONES: List[str]           = ['Zone_1', 'Zone_2']
TOLL_DAILY_CEILING_SAR: float = 120.0
TOLL_CIRCUIT_BREAKER_THRESHOLD: float = 0.90
TOLL_CIRCUIT_BREAKER_REDUCTION: float = 0.50


# --- Transit Signal Priority constants  ---
TSP_GREEN_EXTENSION_MAX_S: int   = 15
TSP_DETECTION_RANGE_M: float     = 150.0
TSP_MIN_PASSENGER_COUNT: int     = 10
BUS_PRIORITY_WEIGHT: float       = 2.5


# --- Variable Speed Limit constants 
VSL_DEFAULT_SPEED_KMPH: int          = 120
VSL_MINIMUM_SPEED_KMPH: int          = 40
VSL_STEP_SIZE_KMPH: int              = 10
VISIBILITY_CLEAR_THRESHOLD_M: int    = 1000
VISIBILITY_DANGER_THRESHOLD_M: int   = 500
VISIBILITY_EXTREME_THRESHOLD_M: int  = 200
VSL_HIGHWAY_ZONES: List[str]         = ['Zone_1', 'Zone_2']



# ── Sensor Intrusion Detection System ──────────────────────────
IDS_MAX_SPEED_KMPH             = 180.0
IDS_MAX_VEHICLE_COUNT          = 500
IDS_NEIGHBORHOOD_VARIANCE_STD  = 3.5
IDS_ZERO_TRAFFIC_SUSPECT_HOURS = [7, 8, 9, 17, 18, 19]
IDS_STRIKE_LIMIT               = 3



#──  Noise Pollution Estimation ─────────────────────────────────
NOISE_BASE_DB                   = 40.0
NOISE_VEHICLE_COEFFICIENT       = 0.15
NOISE_SPEED_COEFFICIENT         = 0.08
NOISE_HEAVY_VEHICLE_COEFFICIENT = 0.35
NOISE_ROAD_TYPE_PREMIUM = {
    'highway': 5.0, 'arterial': 2.0, 'local': 0.0
}
NOISE_THRESHOLDS = {
    'Acceptable': 55.0, 'Elevated': 65.0, 'Harmful': 75.0
}


# ---------------------------------------------------------------------------
# Tidal flow constants — 
# ---------------------------------------------------------------------------

TIDAL_ASYMMETRY_THRESHOLD: float = 2.5
TIDAL_MIN_TOTAL_LANES: int       = 4
TIDAL_ELIGIBLE_ZONES: List[str]  = ['Zone_1', 'Zone_2']
MORNING_INBOUND_HOURS: List[int]  = [6, 7, 8, 9]
EVENING_OUTBOUND_HOURS: List[int] = [16, 17, 18, 19]



# ---------------------------------------------------------------------------
# Tidal flow constants —
# ---------------------------------------------------------------------------

TIDAL_ASYMMETRY_THRESHOLD: float = 2.5
TIDAL_MIN_TOTAL_LANES: int       = 4
TIDAL_ELIGIBLE_ZONES: List[str]  = ['Zone_1', 'Zone_2']
MORNING_INBOUND_HOURS: List[int]  = [6, 7, 8, 9]
EVENING_OUTBOUND_HOURS: List[int] = [16, 17, 18, 19]

# == – Green Wave Corridor Planner =====
EMERGENCY_SPEED_KMPH = {
    'Low': 80,
    'Moderate': 60,
    'High': 40,
    'Critical': 25,
}

# New constant for green wave
PRIORITY_VEHICLE_SPEED_KMPH = 80.0   
GREEN_WAVE_BUFFER_S = 30
ZONE_DISTANCE_M = 500
MAX_GREEN_EXTENSION_S = 45




# ===== – Pedestrian Safety Index Extension =====
PEDESTRIAN_BASE_WALK_TIME_S   = 12
PEDESTRIAN_MAX_WALK_TIME_S    = 35
PEDESTRIAN_CLEARANCE_MIN_S    = 7
PEDESTRIAN_CROWD_MULTIPLIER   = 1.5



# ===== – Extreme Heat Infrastructure Risk Assessment =====
SURFACE_TEMP_OFFSET_CELSIUS    = 12.0
ASPHALT_CRITICAL_TEMP_CELSIUS  = 55.0
HEAT_RISK_THRESHOLDS = {
    'Low': 45.0,
    'Elevated': 50.0,
    'High': 55.0,
    'Critical': 60.0
}



# =====– Extreme Heat Infrastructure Risk Assessment =====
SURFACE_TEMP_OFFSET_CELSIUS    = 12.0
ASPHALT_CRITICAL_TEMP_CELSIUS  = 55.0
HEAT_RISK_THRESHOLDS = {
    'Low': 45.0,
    'Elevated': 50.0,
    'High': 55.0,
    'Critical': 60.0
}




# ===== – Mass Event Egress Optimizer =====
MASS_EVENT_VENUES = {
    'Boulevard_World':   {'capacity_vehicles': 7000, 'congestion_factor': 1.9},
    'Boulevard_Riyadh':  {'capacity_vehicles': 5000, 'congestion_factor': 1.7},
    'King_Fahd_Stadium': {'capacity_vehicles': 10000, 'congestion_factor': 2.1},
}
EGRESS_STAGED_WINDOWS_MINS = [10, 15, 20, 30, 40, 60]
EGRESS_HIGHWAY_CAPACITY_PER_MIN = 150   # vehicles per minute at normal load


# =====– Variable Message Sign Content Generator =====
VMS_LINE_MAX_CHARS   = 24
VMS_MAX_LINES        = 3
VMS_UPDATE_INTERVAL_S = 300
VMS_METRO_STATIONS = {
    'Zone_1': 'KAFD METRO',
    'Zone_2': 'KING FAHD STN',
    'Zone_3': 'OLAYA STN',
}


# Semantic validation rules
VMS_FORBIDDEN_PATTERNS: List[str] = [
    'UNKNOWN', 'NONE', 'N/A', 'NULL', 'ERROR', 'NAN'
]
VMS_MAX_WORDS: int = 12        # highway sign readability at 100 km/h
VMS_REQUIRED_ACTION_VERBS: List[str] = [
    'REDUCE', 'SLOW', 'DIVERT', 'CAUTION', 'PROCEED', 'AVOID', 'USE'
]




# =====– Role-Based Access Control =====
USER_ROLES = {
    'READ_ONLY': ['predict', 'anomalies', 'forecast',
                  'health', 'emissions', 'noise', 'vms'],
    'OPERATOR' : ['*'],   # all endpoints
    'ADMIN'    : ['*'],   # all endpoints + key management
}
API_KEY_TTL_HOURS = 72



# =========
VIOLATION_LEDGER_PATH = 'violation_ledger.csv'
LEDGER_GENESIS_HASH = 'MUNICIPAL_VIOLATIONS_GENESIS'
HASH_ALGORITHM = 'sha256'

# PROMPT 068 — Ledger Chain Verification and Break-Recovery Procedure.
# When True (default, recommended), ViolationLedger.append_violation()
# re-verifies the existing chain before every write and refuses to append
# (raises LedgerIntegrityError) if the chain is already broken — see the
# BREAK-RECOVERY PROCEDURE in src/ledger.py's module docstring for the
# rationale and the documented denial-of-service tradeoff this implies.
# Set False only for local debugging of an already-known-broken ledger;
# never in a deployment that issues real citations.
LEDGER_FREEZE_ON_BREAK = True



# ==========
TELEMETRY_QUEUE_MAX_SIZE   = 10000
TELEMETRY_BATCH_SIZE       = 50
TELEMETRY_FLUSH_INTERVAL_S = 5



# =====  =====
PARKING_HUBS = {
    'Gar_Olaya': {'capacity': 1500, 'zone': 'Zone_1'},
    'Gar_KAFD': {'capacity': 2500, 'zone': 'Zone_2'},
    'Gar_Tahlia': {'capacity': 800, 'zone': 'Zone_3'},
}
PARKING_OCCUPANCY_WARNING = 0.85
PARKING_OCCUPANCY_CRITICAL = 0.95



# ==========
HEARTBEAT_TIMEOUT_S   = 10
OFFLINE_CYCLE_LENGTH_S = 90
DEFAULT_OFFLINE_PHASES = {
    'main_green_s'  : 40,
    'cross_green_s' : 30,
    'pedestrian_s'  : 12,
}



# ==========
HPO_N_TRIALS      = 20
HPO_CV_FOLDS      = 3
HPO_TIMEOUT_S     = 300  # 5 minutes max
HPO_DB_PATH       = 'optuna_studies.db'
HPO_SEARCH_SPACE  = {
    'n_estimators' : (100, 400),
    'max_depth'    : (3, 8),
    'learning_rate': (0.01, 0.3),
    'subsample'    : (0.6, 1.0),
}



# ==========
PARETO_DEFAULT_WEIGHTS = {
    'time_weight': 0.40,
    'emission_weight': 0.30,
    'cost_weight': 0.30,
}

EMISSIONS_ROUTING_WEIGHT: float = 0.0



# ==========
PM25_FACTOR_G_PER_VEHICLE_KM  = 0.015
NOX_FACTOR_G_PER_VEHICLE_KM   = 0.085
ZONE_ROAD_LENGTH_KM           = 0.5
WIND_DISPERSION_FACTOR        = 0.70
AQI_THRESHOLDS = {
    'Good'      : 12.0,
    'Moderate'  : 35.4,
    'Unhealthy' : 55.4,
    'Hazardous' : 150.4,
}


# ===== =====
GEOFENCED_RESTRICTED_ZONES = {
    'Zone_1': {'max_weight_tonnes': 5.0,
               'restricted_hours': list(range(7, 22))},
    'Zone_3': {'max_weight_tonnes': 3.5,
               'restricted_hours': list(range(7, 10)) +
                                   list(range(12, 14)) +
                                   list(range(17, 20))},
}
HEAVY_VEHICLE_WEIGHT_LIMIT_TONNES = 5.0
VIOLATION_PENALTY_SAR             = 1000.0
PRAYER_TIME_RESTRICTIONS          = FRIDAY_PRAYER_HOURS   # reuse existing constant





# =====  Evacuation Routing =====
EVACUATION_SAFE_POINTS = {
    'Safe_North': {'zone': 'Zone_5', 'capacity': 5000},
    'Safe_South': {'zone': 'Zone_4', 'capacity': 3000},
}
ZONE_ROAD_CAPACITY_VPH = 1800  # vehicles per hour per zone

# ===== — Data Quality / Lineage Fault Detection =====
DATA_QUALITY_REPEAT_VALUE_THRESHOLD: int    = 3     # same value N consecutive readings = suspect
DATA_QUALITY_SPEED_FLOOR_KMPH: float        = 5.0   # below this at non-zero volume = sensor fault
DATA_QUALITY_VOLUME_SPIKE_MULTIPLIER: float = 4.0   # >4x rolling mean = spike flag

# ===== HCM Demand-Flow Ratio =====
# NOTE: distinct from ZONE_ROAD_CAPACITY_VPH (1800, a single flat value used
# only by calculate_evacuation_routes() for corridor flow during evacuation
# planning). ROAD_CAPACITY_VPH is per-road-type and used for steady-state
# HCM v/c-ratio LOS classification — different purpose, not a duplicate.
HCM_LOS_VC_THRESHOLDS: Dict[str, float] = {
    'A': 0.35,
    'B': 0.54,
    'C': 0.72,
    'D': 0.88,
    'E': 1.00,
    # > 1.00 → F
}
ROAD_CAPACITY_VPH: Dict[str, int] = {
    'highway' : 2200,
    'arterial': 1600,
    'local'   : 800,
}

# HCM practice: never plan to 100% of modelled capacity – apply 85% margin
EVACUATION_CAPACITY_MARGIN: float = 0.85


# ===== Prometheus Instrumentation =====
LATENCY_SLA_THRESHOLD_MS = 500
METRICS_ENDPOINT         = '/metrics'



# ==== Demand-Responsive Transit (DRT) =====
DRT_SHUTTLE_CAPACITY      = 12
DRT_MAX_WAIT_MINS         = 15
DRT_MAX_DETOUR_FACTOR     = 1.35
DRT_ELIGIBLE_ZONES        = ['Zone_4', 'Zone_5']


CONFIDENCE_WIDTH_THRESHOLDS: Dict[str, float] = {
    'High'  : 0.15,   # width <= 0.15 -> High confidence
    'Medium': 0.30,   # width <= 0.30 -> Medium confidence
    # anything wider -> Low
}



# ==== Data Feed Staleness ====
# Maximum age, in seconds, before a data source's last fetch is treated
# as stale. /predict refuses with HTTP 503 rather than serving a
# prediction built on expired external data once this threshold is
# exceeded. 'mock' is intentionally None — synthetic/deterministic mock
# data is generated fresh on every call and has no real-world staleness
# concept, since there is no external feed that can go down.





# Approximate centroids for Riyadh zones (longitude, latitude)
ZONE_CENTROIDS = {
    'Zone_1': [46.70, 24.75],
    'Zone_2': [46.75, 24.70],
    'Zone_3': [46.65, 24.65],
    'Zone_4': [46.80, 24.70],
    'Zone_5': [46.70, 24.60],
}



SCHOOL_TERM_DATES: Dict[str, List[Dict]] = {
    'Riyadh': [
        {'term': 'T1', 'start': '2025-08-25', 'end': '2025-11-15'},
        {'term': 'T2', 'start': '2025-11-29', 'end': '2026-02-28'},
        {'term': 'T3', 'start': '2026-03-08', 'end': '2026-06-05'},
    ],
    'Dubai': [
        {'term': 'T1', 'start': '2025-08-25', 'end': '2025-11-15'},
        {'term': 'T2', 'start': '2025-11-29', 'end': '2026-02-28'},
        {'term': 'T3', 'start': '2026-03-08', 'end': '2026-06-05'},
    ],
}
SCHOOL_HOLIDAY_MULTIPLIERS: Dict[int, float] = {
    7: 0.6, 8: 0.7, 9: 1.0, 14: 1.2, 15: 1.2, 16: 1.1, 17: 1.3, 18: 1.3
}





RECURRING_EVENTS: Dict[str, List[Dict]] = {
    'Riyadh': [
        {
            'name'       : 'Riyadh Season',
            'start_month': 10,
            'end_month'  : 3,       # year-wrap: Oct of year N to Mar of year N+1
            'multiplier' : 1.4,
            'peak_hours' : [19, 20, 21, 22],
        },
        {
            'name'      : 'National Day',
            'month'     : 9,
            'day'       : 23,
            'multiplier': 1.6,
            'peak_hours': [18, 19, 20, 21, 22],
        },
        {
            'name'      : 'Founding Day',
            'month'     : 2,
            'day'       : 22,
            'multiplier': 1.3,
            'peak_hours': [17, 18, 19, 20],
        },
    ],
    'NEOM'   : [],
    'Dubai'  : [],
    'Karachi': [],
}





#  MQTT Interface
import os as _os
MQTT_BROKER_HOST: str  = _os.getenv('MQTT_BROKER_HOST', '')
MQTT_BROKER_PORT: int  = int(_os.getenv('MQTT_BROKER_PORT', '1883'))
MQTT_TOPIC_PREFIX: str = 'smart_city/traffic'
MQTT_ENABLED: bool     = bool(_os.getenv('MQTT_BROKER_HOST', ''))





INCIDENT_SPEED_DROP_THRESHOLD: float = 0.40
# 40% sudden speed drop relative to zone baseline → suspect incident
 
INCIDENT_VOLUME_DROP_THRESHOLD: float = 0.30
# 30% volume drop coinciding with speed drop → blocked lane (raises confidence)
 
INCIDENT_PERSISTENCE_MINUTES: int = 10
# Condition must persist at least N minutes before an incident is confirmed.
# For hourly synthetic data this is enforced structurally (window_rows ≥ 1).
 
INCIDENT_SEVERITY_LEVELS: Dict[str, float] = {
    "Minor":    0.20,   # speed drop 20–40 %
    "Moderate": 0.40,   # speed drop 40–60 %
    "Major":    0.60,   # speed drop 60–80 %
    "Critical": 0.80,   # near-zero speed + volume collapse
}





# ==== Synthetic-to-Real Calibration  ====
CALIBRATION_DRIFT_THRESHOLD: float = 0.15   
CALIBRATION_FACTORS_PATH: str = "calibration_factors.json"


# ==== Operator Training Mode  ====
# When True, all write-side audit logs (predictions, alerts, incidents,
# usage, IDS, scenarios) redirect to *_training.csv sibling files instead
# of production logs. Mutated at runtime via src.training.set_training_mode()
# — never import this name directly (`from src.config import TRAINING_MODE`)
# or you'll freeze a stale copy; always go through src.training.
TRAINING_MODE: bool = False




# ── Adaptive Signal Control ──────────────
ADAPTIVE_QUEUE_THRESHOLD: float = 0.60
ADAPTIVE_MAX_GREEN_EXTENSION_S: int = 15
ADAPTIVE_SPILLBACK_REDUCTION_FACTOR: float = 0.20
ADAPTIVE_MIN_GREEN_S: int = 10



FEDERATED_DP_EPSILON: float = 1.0
FEDERATED_DP_ENABLED: bool = False

import os


# ── Real Sensor Adapter ──────────────
REAL_SENSOR_ENDPOINTS: Dict[str, str] = {
    "Riyadh": os.getenv("RIYADH_SENSOR_ENDPOINT", ""),
    "NEOM":   os.getenv("NEOM_SENSOR_ENDPOINT", ""),
}


MAX_DATA_AGE_SECONDS: Dict[str, Optional[float]] = {
    'weather': 1800,
    'osm'    : 3600,
    'mock'   : None,
    'real'   : 60,   # real sensor data must be refreshed every minute
}



MAX_DATA_AGE_SECONDS: Dict[str, Optional[float]] = {
    'weather'         : 1800,
    'weather_nowcast' : 900,   # 15 min — forecasts are time-sensitive
    'osm'             : 3600,
    'mock'            : None,
    'real'            : 60,
}




# ── Maintenance Scheduler  ──────────────
MAINTENANCE_DEFAULT_HORIZON_DAYS = 7
MAINTENANCE_LOW_DEMAND_THRESHOLD = 0.3
MAINTENANCE_WINDOW_HOURS = 4





# ==== — Signal Controller Interface (NTCIP Stub) ====
SIGNAL_CONTROLLER_ENDPOINTS: Dict[str, str] = {
    "Zone_1": "tcp://127.0.0.1:8881",
    "Zone_2": "tcp://127.0.0.1:8882",
    "Zone_3": "tcp://127.0.0.1:8883",
    "Zone_4": "tcp://127.0.0.1:8884",
    "Zone_5": "tcp://127.0.0.1:8885",
}
NTCIP_TIMEOUT_SECONDS: int = 5
NTCIP_RETRY_ATTEMPTS: int = 3
ACTUATION_ENABLED: bool = False  # SAFETY: must be explicitly True in production config

# Zones locked from actuation during Hajj (pilgrimage route protection).
# Reuses HAJJ_ROUTE_ZONES as the base set — kept as a separate name per
# spec so lockdown policy can diverge from routing definitions later.
HAJJ_LOCKDOWN_ZONES: List[str] = list(HAJJ_ROUTE_ZONES)

ACTUATION_COOLDOWN_SECONDS: int = 60  # min interval between actuations per zone