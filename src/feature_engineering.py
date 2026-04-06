import pandas as pd
import numpy as np


HOURLY_TRAFFIC_MULTIPLIERS = {
    'standard': {
        0: 0.3, 1: 0.2, 2: 0.2, 3: 0.2, 4: 0.3,
        5: 0.5, 6: 0.8, 7: 1.4, 8: 1.5, 9: 1.1,
        10: 1.0, 11: 1.0, 12: 0.9, 13: 1.0, 14: 1.0,
        15: 1.1, 16: 1.3, 17: 1.5, 18: 1.4, 19: 1.1,
        20: 1.0, 21: 1.1, 22: 1.2, 23: 0.7
    },
    'saudi': {
        0: 0.6, 1: 0.5, 2: 0.4, 3: 0.3, 4: 0.4,
        5: 0.6, 6: 0.9, 7: 1.3, 8: 1.4, 9: 1.1,
        10: 1.0, 11: 1.0, 12: 0.5, 13: 0.4, 14: 0.8,
        15: 1.1, 16: 1.3, 17: 1.5, 18: 1.4, 19: 1.2,
        20: 1.4, 21: 1.5, 22: 1.4, 23: 1.1
    },
    'ramadan': {
        0: 1.2, 1: 1.3, 2: 1.0, 3: 0.6, 4: 0.4,
        5: 0.3, 6: 0.3, 7: 0.4, 8: 0.5, 9: 0.6,
        10: 0.6, 11: 0.5, 12: 0.4, 13: 0.4, 14: 0.4,
        15: 0.5, 16: 0.6, 17: 0.5, 18: 1.5, 19: 1.6,
        20: 1.5, 21: 1.4, 22: 1.4, 23: 1.3
    }
}

FRIDAY_PRAYER_HOURS = [12, 13]


def get_traffic_schedule(city='Riyadh'):
    """Return the hourly multiplier schedule appropriate for the city."""
    saudi_cities = ['Riyadh', 'Dubai', 'Jeddah', 'NEOM', 'Dammam']
    return 'saudi' if city in saudi_cities else 'standard'


def apply_hourly_patterns(df, city='Riyadh', ramadan=False):
    """
    Apply city-specific hourly traffic multipliers to vehicle counts.

    Parameters
    ----------
    df      : pd.DataFrame - Output of generate_traffic_data()
    city    : str          - City name to determine schedule type
    ramadan : bool         - Whether to apply Ramadan traffic schedule

    Returns
    -------
    pd.DataFrame with adjusted vehicle_count and new temporal features
    """
    df = df.copy()

    schedule_key = 'ramadan' if ramadan else get_traffic_schedule(city)
    multipliers  = HOURLY_TRAFFIC_MULTIPLIERS[schedule_key]

    df['hour']             = df['timestamp'].dt.hour
    df['hour_multiplier']  = df['hour'].map(multipliers)
    df['vehicle_count']    = (df['vehicle_count'] * df['hour_multiplier']).clip(0, 500)

    if city in ['Riyadh', 'Jeddah', 'NEOM', 'Dammam']:
        friday_prayer_mask = (
            (df['day_of_week'] == 'Friday') &
            (df['hour'].isin(FRIDAY_PRAYER_HOURS))
        )
        df.loc[friday_prayer_mask, 'vehicle_count'] *= 0.1 # During Friday Prayer the Traffic significantly dropped to zero, so i modify it,
        df['friday_prayer_drop'] = friday_prayer_mask.astype(int)

    df['is_ramadan']    = int(ramadan)
    df['is_late_night'] = df['hour'].isin([21, 22, 23, 0]).astype(int)

    df['congestion_score'] = (
        (df['vehicle_count'] / df['vehicle_count'].max()) *
        (1 - df['avg_speed']  / df['avg_speed'].max())
    ).clip(0, 1)

    return df



riyadh_df  = generate_traffic_data(city='Riyadh')
riyadh_df  = apply_hourly_patterns(riyadh_df, city='Riyadh', ramadan=False)

ramadan_df = generate_traffic_data(city='Riyadh')
ramadan_df = apply_hourly_patterns(ramadan_df, city='Riyadh', ramadan=True)

print("Standard schedule sample:")
print(riyadh_df[['timestamp', 'hour', 'hour_multiplier', 'vehicle_count', 'friday_prayer_drop']].head(24))

print("\nRamadan schedule sample:")
print(ramadan_df[['timestamp', 'hour', 'hour_multiplier', 'vehicle_count']].head(24))
