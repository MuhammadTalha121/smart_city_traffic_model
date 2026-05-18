import pandas as pd
import numpy as np
from src.config import (
    CITY_PROFILES, HOURLY_MULTIPLIERS, WEATHER_SPEED_IMPACT,
    FRIDAY_PRAYER_HOURS, SAUDI_CITIES
)


def generate_traffic_data(city: str = 'Riyadh', n_days: int = 30,
                           zones: int = 5, seed: int = 42) -> pd.DataFrame:
    """
    Generate hourly synthetic traffic data for a given city.

    Parameters
    ----------
    city   : City name. Supported: Riyadh, NEOM, Dubai, Karachi.
    n_days : Number of days to simulate.
    zones  : Number of city zones.
    seed   : Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame with hourly traffic records per zone.
    """
    np.random.seed(seed)

    profile    = CITY_PROFILES.get(city, list(CITY_PROFILES.values())[0])
    dates      = pd.date_range(start='2025-01-01', periods=n_days * 24, freq='h')
    zones_list = [f'Zone_{i}' for i in range(1, zones + 1)]
    n          = len(dates) * zones

    df = pd.DataFrame({
        'city'         : city,
        'timestamp'    : dates.repeat(zones),
        'zone'         : np.tile(zones_list, len(dates)),
        'vehicle_count': (
            np.random.poisson(lam=profile['base_vehicles'], size=n) +
            np.sin(np.arange(n) / 24) * 50
        ),
        'avg_speed'    : np.random.normal(profile['speed_mean'], 10, n).clip(20, 100),
    })

    df['weather']     = np.random.choice(
        profile['weather_conditions'], size=n, p=profile['weather_probs']
    )
    df['event']       = np.random.choice([0, 1], size=n, p=[0.9, 0.1])
    df['road_type']   = df['zone'].map({
        'Zone_1': 'highway', 'Zone_2': 'arterial', 'Zone_3': 'local',
        'Zone_4': 'arterial', 'Zone_5': 'highway'
    })
    df['day_of_week'] = df['timestamp'].dt.day_name()
    df['hour']        = df['timestamp'].dt.hour
    df['is_weekend']  = df['day_of_week'].isin(profile['weekend']).astype(int)
    df['rush_hour']   = df['hour'].isin([7, 8, 17, 18]).astype(int)

    return df


def apply_hourly_patterns(df: pd.DataFrame, city: str = 'Riyadh',
                           ramadan: bool = False) -> pd.DataFrame:
    """
    Apply city-specific hourly traffic multipliers and Saudi behavioral patterns.

    Parameters
    ----------
    df      : Output of generate_traffic_data()
    city    : City name to determine schedule type
    ramadan : Whether to apply Ramadan traffic schedule

    Returns
    -------
    pd.DataFrame with adjusted vehicle counts and enriched features.
    """
    df = df.copy()

    schedule_key      = 'ramadan' if ramadan else ('saudi' if city in SAUDI_CITIES else 'standard')
    multipliers       = HOURLY_MULTIPLIERS[schedule_key]
    df['hour_multiplier'] = df['hour'].map(multipliers)
    df['vehicle_count']   = (df['vehicle_count'] * df['hour_multiplier']).clip(0, 500)

    for condition, factor in WEATHER_SPEED_IMPACT.items():
        df.loc[df['weather'] == condition, 'avg_speed'] *= factor

    df.loc[df['event'] == 1,     'vehicle_count'] *= 1.5
    df.loc[df['rush_hour'] == 1, 'vehicle_count'] *= 1.2

    if city in SAUDI_CITIES:
        friday_mask = (
            (df['day_of_week'] == 'Friday') &
            (df['hour'].isin(FRIDAY_PRAYER_HOURS))
        )
        df.loc[friday_mask, 'vehicle_count'] *= 0.1
        df['friday_prayer_drop'] = friday_mask.astype(int)
    else:
        df['friday_prayer_drop'] = 0

    df['is_late_night'] = df['hour'].isin([21, 22, 23, 0]).astype(int)
    df['is_ramadan']    = int(ramadan)

    df['avg_speed']     = df['avg_speed'].clip(20, 100)
    df['vehicle_count'] = df['vehicle_count'].clip(0, 500)

    df['congestion_score'] = (
        (df['vehicle_count'] / df['vehicle_count'].max()) *
        (1 - df['avg_speed']  / df['avg_speed'].max())
    ).clip(0, 1)

    return df
