from typing import Dict, List


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

# --- Intervention and demand-shifting constants (PROMPT 013) ---

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