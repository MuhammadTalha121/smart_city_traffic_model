import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns




CITY_PROFILES = {
    'Riyadh': {
        'base_vehicles': 120,
        'weather_conditions': ['clear', 'sandstorm', 'dust'],
        'weather_probs': [0.75, 0.15, 0.10],
        'speed_mean': 65,
        'weekend': ['Friday', 'Saturday']
    },
    'Dubai': {
        'base_vehicles': 150,
        'weather_conditions': ['clear', 'sandstorm', 'humid'],
        'weather_probs': [0.70, 0.20, 0.10],
        'speed_mean': 70,
        'weekend': ['Friday', 'Saturday']
    },
    'Karachi': {
        'base_vehicles': 200,
        'weather_conditions': ['clear', 'rain', 'fog'],
        'weather_probs': [0.65, 0.25, 0.10],
        'speed_mean': 45,
        'weekend': ['Saturday', 'Sunday']
    },
    'default': {
        'base_vehicles': 100,
        'weather_conditions': ['clear', 'rain', 'fog'],
        'weather_probs': [0.70, 0.20, 0.10],
        'speed_mean': 60,
        'weekend': ['Saturday', 'Sunday']
    }
}

WEATHER_SPEED_IMPACT = {
    'sandstorm': 0.60,
    'fog'      : 0.70,
    'rain'     : 0.80,
    'dust'     : 0.85,
    'humid'    : 0.95,
    'clear'    : 1.00
}


def generate_traffic_data(city='Riyadh', n_days=30, zones=5, seed=42):
    """
    Generate hourly synthetic traffic data for a given city.

    Parameters
    ----------
    city   : str - City name. Profiles available: Riyadh, Dubai, Karachi.
                   Falls back to default profile if not found.
    n_days : int - Number of days to simulate.
    zones  : int - Number of city zones.
    seed   : int - Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame with hourly traffic records per zone.
    """
    np.random.seed(seed)

    profile    = CITY_PROFILES.get(city, CITY_PROFILES['default'])
    dates      = pd.date_range(start='2025-01-01', periods=n_days * 24, freq='h')
    zones_list = [f'Zone_{i}' for i in range(1, zones + 1)]
    n          = len(dates) * zones

    df = pd.DataFrame({
        'city'         : city,
        'timestamp'    : dates.repeat(zones),
        'zone'         : np.tile(zones_list, len(dates)),
        'vehicle_count': np.random.poisson(lam=profile['base_vehicles'], size=n) + np.sin(np.arange(n) / 24) * 50,
        'avg_speed'    : np.random.normal(profile['speed_mean'], 10, n).clip(20, 100),
    })

    df['weather']     = np.random.choice(profile['weather_conditions'], size=n, p=profile['weather_probs'])
    df['event']       = np.random.choice([0, 1], size=n, p=[0.9, 0.1])
    df['road_type']   = df['zone'].map({'Zone_1': 'highway', 'Zone_2': 'arterial', 'Zone_3': 'local', 'Zone_4': 'arterial', 'Zone_5': 'highway'})
    df['day_of_week'] = df['timestamp'].dt.day_name()
    df['rush_hour']   = df['timestamp'].dt.hour.isin([7, 8, 17, 18]).astype(int)
    df['is_weekend']  = df['day_of_week'].isin(profile['weekend']).astype(int)

    for condition, factor in WEATHER_SPEED_IMPACT.items():
        df.loc[df['weather'] == condition, 'avg_speed'] *= factor

    df.loc[df['event'] == 1,     'vehicle_count'] *= 1.5
    df.loc[df['rush_hour'] == 1, 'vehicle_count'] *= 1.2

    df['avg_speed']     = df['avg_speed'].clip(20, 100)
    df['vehicle_count'] = df['vehicle_count'].clip(0, 500)

    df['congestion_score'] = (
        (df['vehicle_count'] / df['vehicle_count'].max()) *
        (1 - df['avg_speed']  / df['avg_speed'].max())
    ).clip(0, 1)

    return df


riyadh_df = generate_traffic_data(city='Riyadh')
print(riyadh_df.shape)
print(riyadh_df.head())