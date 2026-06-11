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