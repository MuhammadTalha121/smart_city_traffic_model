import pandas as pd
import numpy as np
import sklearn
from sklearn import *
from src.config import (
    CITY_PROFILES, HOURLY_MULTIPLIERS, WEATHER_SPEED_IMPACT,
    FRIDAY_PRAYER_HOURS, SAUDI_CITIES,
    HAJJ_INBOUND, HAJJ_PEAK, HAJJ_OUTBOUND, HAJJ_ROUTE_ZONES,
    RECURRING_EVENTS, RAMADAN_IFTAR_HOUR, RAMADAN_PROGRESSION_FACTOR,
)
from typing import List, Dict, Optional, Tuple






def is_school_holiday(city: str, check_date=None) -> bool:
    """
    Return True if check_date falls outside all configured school terms for city
    (i.e., it IS a holiday/break). Returns False (treat as term-time) if city
    has no SCHOOL_TERM_DATES config — unknown cities default to conservative
    assumption (term-time traffic), never synthetic holiday suppression.
    Karachi uses a different academic calendar and is intentionally excluded
    from SCHOOL_TERM_DATES; this function returns False for it.
    """
    from src.config import SCHOOL_TERM_DATES
    from datetime import date as date_type
    import datetime

    if check_date is None:
        check_date = datetime.date.today()
    if isinstance(check_date, datetime.datetime):
        check_date = check_date.date()

    terms = SCHOOL_TERM_DATES.get(city)
    if not terms:
        return False

    for term in terms:
        start = date_type.fromisoformat(term['start'])
        end   = date_type.fromisoformat(term['end'])
        if start <= check_date <= end:
            return False  # inside a term → not a holiday

    return True  # outside all terms → holiday



def get_active_events(city: str, check_date=None) -> List[Dict]:
    """
    Return list of recurring events active on check_date for the given city.

    Handles year-wrap for multi-month events (e.g., Riyadh Season Oct–Mar).
    Single-day events match on month/day only (year-agnostic).
    """
    from src.config import RECURRING_EVENTS
    import datetime

    if check_date is None:
        check_date = datetime.date.today()
    if isinstance(check_date, datetime.datetime):
        check_date = check_date.date()

    events = RECURRING_EVENTS.get(city, [])
    active = []

    for ev in events:
        # Multi-month range (year-wrap aware)
        if 'start_month' in ev and 'end_month' in ev:
            start_m = ev['start_month']
            end_m = ev['end_month']
            current_m = check_date.month
            if start_m <= end_m:
                # Non-wrapping range (e.g., Apr–Jun)
                if start_m <= current_m <= end_m:
                    active.append(ev)
            else:
                # Wrapping range (e.g., Oct–Mar)
                if current_m >= start_m or current_m <= end_m:
                    active.append(ev)
        # Single-day event (month + day)
        elif 'month' in ev and 'day' in ev:
            if check_date.month == ev['month'] and check_date.day == ev['day']:
                active.append(ev)

    return active


def apply_event_multipliers(df: pd.DataFrame, city: str = 'Riyadh',
                            check_date=None) -> pd.DataFrame:
    """
    Apply recurring event multipliers to vehicle_count for active events.

    Multipliers are applied only during the event's configured peak_hours.
    Stacks on top of existing patterns (school holidays, Ramadan, Hajj).
    Vehicle count is clipped to [0, 500] after each multiplier to respect
    IDS limits.

    Must be called AFTER apply_hourly_patterns().
    """
    from src.config import RECURRING_EVENTS

    df = df.copy()

    active_events = get_active_events(city, check_date)
    if not active_events:
        df['event_multiplier'] = 1.0
        df['active_event_names'] = ''
        return df

    # Build a combined multiplier mask per row
    def _row_multiplier(row):
        hour = row['hour']
        mult = 1.0
        names = []
        for ev in active_events:
            if hour in ev.get('peak_hours', []):
                mult *= ev['multiplier']
                names.append(ev['name'])
        return pd.Series([mult, '|'.join(names) if names else ''])

    df[['event_multiplier', 'active_event_names']] = df.apply(_row_multiplier, axis=1)

    # Apply multiplier only where it's > 1.0
    mask = df['event_multiplier'] > 1.0
    df.loc[mask, 'vehicle_count'] = (
        df.loc[mask, 'vehicle_count'] * df.loc[mask, 'event_multiplier']
    ).clip(0, 500)

    return df


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


def _resolve_hajj_multiplier(hour: int, phase_dict: dict) -> float:
    """
    Return the Hajj multiplier for a given hour by finding the
    nearest anchor hour in the phase dictionary.
    """
    anchors = sorted(phase_dict.keys())
    # Find the closest anchor hour (round down, then take nearest)
    lower   = max((a for a in anchors if a <= hour), default=anchors[0])
    return phase_dict[lower]




def apply_hajj_crowd_gradient(df: pd.DataFrame, phase: str) -> pd.DataFrame:
    """
    PROMPT 115 — Applies zone-specific Hajj crowd density gradient with
    temporal wave delay on top of the base hourly pattern already applied
    by apply_hourly_patterns().

    Replaces the uniform 1.8x HAJJ_ROUTE_ZONES multiplier with a gradient
    that is stronger near pilgrimage routes and weaker in outer zones.
    The wave delay shifts which hour's multiplier is applied per zone,
    modelling the crowd surge propagating outward over time.
    """
    from src.config import (
        HAJJ_CROWD_DENSITY_GRADIENT, HAJJ_CROWD_WAVE_DELAY_HOURS,
        HAJJ_INBOUND, HAJJ_PEAK, HAJJ_OUTBOUND,
    )

    PHASE_MAPS = {
        'inbound' : HAJJ_INBOUND,
        'peak'    : HAJJ_PEAK,
        'outbound': HAJJ_OUTBOUND,
    }
    phase_map = PHASE_MAPS.get(phase, HAJJ_PEAK)
    gradient  = HAJJ_CROWD_DENSITY_GRADIENT.get(phase, HAJJ_CROWD_DENSITY_GRADIENT['peak'])

    df = df.copy()

    for zone, delay in HAJJ_CROWD_WAVE_DELAY_HOURS.items():
        mask = df['zone'] == zone

        # Effective hour: use what Zone_1 was experiencing `delay` hours ago
        effective_hours = (df.loc[mask, 'hour'] - delay) % 24

        # Look up base multiplier at the effective hour (nearest anchor)
        anchors = sorted(phase_map.keys())

        def _mult(h):
            lower = max((a for a in anchors if a <= h), default=anchors[0])
            return phase_map[lower]

        base_mults = effective_hours.map(_mult)

        zone_gradient = gradient.get(zone, 1.0)

        df.loc[mask, 'vehicle_count'] = (
            df.loc[mask, 'vehicle_count'] * base_mults.values * zone_gradient
        ).clip(0, 500)

    return df



def get_ramadan_week(check_date, ramadan_start_date) -> int:
    days_since_start = (check_date - ramadan_start_date).days
    week = (days_since_start // 7) + 1
    return min(max(week, 1), 4)



def apply_hourly_patterns(df: pd.DataFrame, city: str = 'Riyadh',
                           ramadan: bool = False,
                           hajj: bool = False,
                           school_holiday: bool = False,
                           ramadan_start_date: pd.Timestamp = None) -> pd.DataFrame:
    """
    Apply city-specific hourly traffic multipliers and Saudi behavioral patterns.

    Parameters
    ----------
    df      : Output of generate_traffic_data()
    city    : City name to determine schedule type
    ramadan : Whether to apply Ramadan traffic schedule
    hajj    : Whether to apply Hajj mass-gathering schedule.
              Hajj overrides Ramadan when both are True.

    Returns
    -------
    pd.DataFrame with adjusted vehicle counts and enriched features.
    """
    df = df.copy()

    # --- Determine base schedule ---
    if hajj:
        # Hajj overrides Ramadan; use saudi base multipliers and then
        # apply Hajj phase-specific adjustments below.
        schedule_key = 'saudi'
    elif ramadan:
        schedule_key = 'ramadan'
    else:
        schedule_key = 'saudi' if city in SAUDI_CITIES else 'standard'

    multipliers           = HOURLY_MULTIPLIERS[schedule_key]
    df['hour_multiplier'] = df['hour'].map(multipliers)
    df['vehicle_count']   = (df['vehicle_count'] * df['hour_multiplier']).clip(0, 500)

    if ramadan and not hajj:
        start = ramadan_start_date if ramadan_start_date is not None else df['timestamp'].min()
        iftar_mask = df['hour'] == RAMADAN_IFTAR_HOUR
        if iftar_mask.any():
            weeks = df.loc[iftar_mask, 'timestamp'].apply(
                lambda ts: get_ramadan_week(ts, start)
            )
            progression = 1 + (weeks - 1) * RAMADAN_PROGRESSION_FACTOR
            df.loc[iftar_mask, 'vehicle_count'] = (
                df.loc[iftar_mask, 'vehicle_count'] * progression
            ).clip(0, 500)


    # --- Hajj phase overlays ---
    if hajj:
        # The synthetic data always starts 2025-01-01.
        # We simulate three Hajj phases across the dataset rows using
        # the row index offset modulo 5 (5-day event cycle).
        # Phase mapping: day offset 0–1 → inbound, 2–3 → peak, 4 → outbound.
        PHASE_MAPS = {
            'inbound' : HAJJ_INBOUND,
            'peak'    : HAJJ_PEAK,
            'outbound': HAJJ_OUTBOUND,
        }

        def _day_offset_to_phase(day_offset: int) -> str:
            if day_offset <= 1:
                return 'inbound'
            elif day_offset <= 3:
                return 'peak'
            else:
                return 'outbound'

        # Compute day offset within the 5-day cycle based on timestamp
        day_series   = (df['timestamp'] - df['timestamp'].min()).dt.days % 5
        df['hajj_phase'] = day_series.map(_day_offset_to_phase)

        # Apply Hajj hourly multiplier on top of existing vehicle_count
        def _hajj_mult(row):
            phase_dict = PHASE_MAPS[row['hajj_phase']]
            return _resolve_hajj_multiplier(row['hour'], phase_dict)

        hajj_multipliers  = df.apply(_hajj_mult, axis=1)
        df['vehicle_count'] = (df['vehicle_count'] * hajj_multipliers).clip(0, 500)

        # PROMPT 115: replace uniform 1.8x with zone-specific gradient + wave delay
        # Phase is derived from hajj_phase column already set on the row
        for _phase in ('inbound', 'peak', 'outbound'):
            _phase_mask = df['hajj_phase'] == _phase
            if not _phase_mask.any():
                continue
            df.loc[_phase_mask] = apply_hajj_crowd_gradient(
                df.loc[_phase_mask].copy(), _phase
            )
    else:
        df['hajj_phase'] = 'none'

    # --- Weather speed impact ---
    for condition, factor in WEATHER_SPEED_IMPACT.items():
        df.loc[df['weather'] == condition, 'avg_speed'] *= factor

    df.loc[df['event'] == 1,     'vehicle_count'] *= 1.5
    df.loc[df['rush_hour'] == 1, 'vehicle_count'] *= 1.2

    # --- Saudi-specific patterns ---
    if city in SAUDI_CITIES and not hajj:
        # Friday prayer drop is suppressed during Hajj (crowds override prayer routing)
        friday_mask = (
            (df['day_of_week'] == 'Friday') &
            (df['hour'].isin(FRIDAY_PRAYER_HOURS))
        )
        df.loc[friday_mask, 'vehicle_count'] *= 0.1
        df['friday_prayer_drop'] = friday_mask.astype(int)
    else:
        df['friday_prayer_drop'] = 0

    
    # --- School holiday demand shift ---
    # Hajj takes priority over school holiday (mass-gathering overrides all).
    # school_holiday suppresses the 07:00–08:00 school-run spike and boosts midday.
    if school_holiday and not hajj:
        from src.config import SCHOOL_HOLIDAY_MULTIPLIERS
        for hour_val, mult in SCHOOL_HOLIDAY_MULTIPLIERS.items():
            mask = df['hour'] == hour_val
            df.loc[mask, 'vehicle_count'] = (
                df.loc[mask, 'vehicle_count'] * mult
            ).clip(0, 500)
    df['is_school_holiday'] = int(school_holiday and not hajj)

    df['is_late_night'] = df['hour'].isin([21, 22, 23, 0]).astype(int)
    df['is_ramadan']    = int(ramadan and not hajj)
    df['is_hajj']       = int(hajj)

    df['avg_speed']     = df['avg_speed'].clip(20, 100)
    df['vehicle_count'] = df['vehicle_count'].clip(0, 500)

    df['congestion_score'] = (
        (df['vehicle_count'] / df['vehicle_count'].max()) *
        (1 - df['avg_speed']  / df['avg_speed'].max())
    ).clip(0, 1)

    return df


def validate_data(city: str = 'Riyadh', n_days: int = 30) -> pd.DataFrame:
    """
    Run statistical validation checks on synthetic traffic data.

    Returns
    -------
    pd.DataFrame with columns: Check | Expected | Actual | Status
    """
    from scipy import stats

    df = generate_traffic_data(city=city, n_days=n_days)
    df = apply_hourly_patterns(df, city=city)
    df = apply_event_multipliers(df, city=city)

    results = []

    def record(check, expected, actual, passed):
        results.append({
            'Check'   : check,
            'Expected': expected,
            'Actual'  : round(float(actual), 4),
            'Status'  : 'PASS' if passed else 'FAIL'
        })

     # --- KS test: vehicle count distribution is unimodal and reasonable
    df_raw      = generate_traffic_data(city=city, n_days=n_days)
    profile     = CITY_PROFILES[city]
    mean_count  = df_raw['vehicle_count'].mean()
    std_count   = df_raw['vehicle_count'].std()
    cv          = std_count / mean_count
    record('Vehicle count — coefficient of variation', '< 0.60', cv, cv < 0.60)

    # --- Autocorrelation: lag-1 hourly temporal correlation
    zone_one   = df[df['zone'] == 'Zone_1'].sort_values('timestamp')
    autocorr   = zone_one['vehicle_count'].autocorr(lag=1)
    record('Autocorrelation lag-1', '> 0.50', autocorr, autocorr > 0.50)

    # --- Friday prayer drop
    friday_prayer = df[
        (df['day_of_week'] == 'Friday') &
        (df['hour'].isin(FRIDAY_PRAYER_HOURS))
    ]['vehicle_count'].mean()

    weekday_midday = df[
        (~df['day_of_week'].isin(['Friday', 'Saturday'])) &
        (df['hour'].isin(FRIDAY_PRAYER_HOURS))
    ]['vehicle_count'].mean()

    prayer_drop_pct = (weekday_midday - friday_prayer) / weekday_midday
    record('Friday prayer drop (vs weekday midday)', '>= 0.85', prayer_drop_pct, prayer_drop_pct >= 0.85)

    # --- Late night activity vs evening peak
    late_night_mean = df[df['hour'].isin([21, 22, 23])]['vehicle_count'].mean()
    evening_peak    = df[df['hour'] == 17]['vehicle_count'].mean()
    late_night_ratio = late_night_mean / evening_peak
    record('Late night / evening peak ratio', '>= 0.70', late_night_ratio, late_night_ratio >= 0.70)

    # --- Sandstorm speed reduction
    clear_speed     = df[df['weather'] == 'clear']['avg_speed'].mean()
    sandstorm_speed = df[df['weather'] == 'sandstorm']['avg_speed'].mean()
    speed_reduction = (clear_speed - sandstorm_speed) / clear_speed
    record('Sandstorm speed reduction', '0.35–0.45', speed_reduction, 0.35 <= speed_reduction <= 0.45)

    report = pd.DataFrame(results)

    print("\n" + "=" * 60)
    print(f"  Data Validation Report — {city}")
    print("=" * 60)
    print(report.to_string(index=False))
    print("=" * 60)
    passed = (report['Status'] == 'PASS').sum()
    print(f"  {passed} / {len(report)} checks passed")
    print("=" * 60 + "\n")

    return report




def detect_lineage_faults(df: pd.DataFrame, source: str) -> dict:
    """
    Input-pipeline health monitoring for adapter-sourced traffic data.

    Distinct from validate_data() (statistical distribution validation of
    the *synthetic generation process*) and detect_anomalies() in
    src/model.py (operational *traffic-pattern* anomaly detection on
    congestion/volume). This function instead asks whether the data
    itself looks like it came from a healthy sensor/API feed: repeated
    identical readings (caching fault — e.g. Open-Meteo returning the
    same value for hours, which is a feed problem, not real atmospheric
    stability), physically implausible speed/volume combinations (stuck
    sensor), and short-window volume spikes (ingestion-quality issue,
    not the same signal as detect_anomalies()'s 7-day expected-vs-actual
    comparison).

    Parameters
    ----------
    df     : DataFrame with at least zone, timestamp, avg_speed,
             vehicle_count.
    source : Active data source name (e.g. 'weather', 'osm', 'mock'),
             carried through into the report only.

    Returns
    -------
    dict with source, faults (list of {type, rows_affected, description}),
    quality_score (0.0-1.0).
    """
    from src.config import (
        DATA_QUALITY_REPEAT_VALUE_THRESHOLD,
        DATA_QUALITY_SPEED_FLOOR_KMPH,
        DATA_QUALITY_VOLUME_SPIKE_MULTIPLIER,
    )

    required = {'zone', 'timestamp', 'avg_speed', 'vehicle_count'}
    if df is None or df.empty or not required.issubset(df.columns):
        return {'source': source, 'faults': [], 'quality_score': 1.0}

    df = df.copy().sort_values(['zone', 'timestamp']).reset_index(drop=True)
    faults = []
    flagged_row_idx = set()

    # --- 1. Repeated identical avg_speed values (caching fault) ---
    for zone, zone_df in df.groupby('zone'):
        zone_df = zone_df.sort_values('timestamp')
        speeds  = zone_df['avg_speed'].values
        idxs    = zone_df.index.values

        run_start = 0
        for i in range(1, len(speeds) + 1):
            if i < len(speeds) and speeds[i] == speeds[run_start]:
                continue
            run_len = i - run_start
            if run_len >= DATA_QUALITY_REPEAT_VALUE_THRESHOLD:
                affected = list(idxs[run_start:i])
                flagged_row_idx.update(affected)
                faults.append({
                    'type'         : 'repeated_value',
                    'rows_affected': len(affected),
                    'description'  : (
                        f"{zone}: avg_speed repeated identical value "
                        f"({speeds[run_start]}) for {run_len} consecutive readings — "
                        f"possible caching fault rather than real atmospheric stability."
                    ),
                })
            run_start = i

    # --- 2. Non-zero volume with near-zero speed (sensor fault) ---
    sensor_fault_mask = (
        (df['avg_speed'] < DATA_QUALITY_SPEED_FLOOR_KMPH) & (df['vehicle_count'] > 0)
    )
    if sensor_fault_mask.any():
        affected = list(df.index[sensor_fault_mask])
        flagged_row_idx.update(affected)
        faults.append({
            'type'         : 'sensor_fault',
            'rows_affected': len(affected),
            'description'  : (
                f"avg_speed below {DATA_QUALITY_SPEED_FLOOR_KMPH} km/h with nonzero "
                f"vehicle_count in {len(affected)} row(s) — physically implausible, "
                f"likely a stuck or faulty speed sensor."
            ),
        })

    # --- 3. Volume spike vs recent rolling mean (ingestion spike) ---
    df['_rolling_mean'] = (
        df.groupby('zone')['vehicle_count']
          .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
    )
    spike_mask = (
        df['_rolling_mean'].notna() &
        (df['_rolling_mean'] > 0) &
        (df['vehicle_count'] > DATA_QUALITY_VOLUME_SPIKE_MULTIPLIER * df['_rolling_mean'])
    )
    if spike_mask.any():
        affected = list(df.index[spike_mask])
        flagged_row_idx.update(affected)
        faults.append({
            'type'         : 'volume_spike',
            'rows_affected': len(affected),
            'description'  : (
                f"vehicle_count exceeded {DATA_QUALITY_VOLUME_SPIKE_MULTIPLIER}x the "
                f"3-reading rolling mean in {len(affected)} row(s) — flagged as an "
                f"ingestion-quality spike, distinct from detect_anomalies()'s "
                f"traffic-pattern anomaly detection."
            ),
        })

    total_rows    = len(df)
    quality_score = (
        round(max(0.0, 1.0 - len(flagged_row_idx) / total_rows), 4) if total_rows else 1.0
    )

    return {
        'source'       : source,
        'faults'       : faults,
        'quality_score': quality_score,
    }







def validate_hajj_data(city: str = 'Riyadh', n_days: int = 30) -> pd.DataFrame:
    """
    Validate that Hajj mode produces statistically distinct traffic patterns.

    Checks that Hajj peak hour vehicle_count is at least 2.5x the standard
    Friday midday average — confirming the phase multipliers are applied correctly.

    Returns
    -------
    pd.DataFrame with columns: Check | Expected | Actual | Status
    """
    df_standard = apply_event_multipliers(
        apply_hourly_patterns(
            generate_traffic_data(city=city, n_days=n_days), city=city
        ), city=city
    )
    df_hajj = apply_event_multipliers(
        apply_hourly_patterns(
            generate_traffic_data(city=city, n_days=n_days), city=city, hajj=True
        ), city=city
    )

    results = []

    def record(check, expected, actual, passed):
        results.append({
            'Check'   : check,
            'Expected': expected,
            'Actual'  : round(float(actual), 4),
            'Status'  : 'PASS' if passed else 'FAIL'
        })

    # Hajj peak phase (days 2–3), peak hour 12 — zone with route multiplier
    hajj_peak_rows = df_hajj[
        (df_hajj['hajj_phase'] == 'peak') &
        (df_hajj['hour'] == 12) &
        (df_hajj['zone'] == 'Zone_1')
    ]
    hajj_peak_mean = hajj_peak_rows['vehicle_count'].mean() if len(hajj_peak_rows) > 0 else 0.0

    friday_midday_mean = df_standard[
        (df_standard['day_of_week'] == 'Friday') &
        (df_standard['hour'].isin(FRIDAY_PRAYER_HOURS))
    ]['vehicle_count'].mean()

    # Friday midday has prayer drop — compare against standard weekday midday instead
    weekday_midday_mean = df_standard[
        (~df_standard['day_of_week'].isin(['Friday', 'Saturday'])) &
        (df_standard['hour'] == 12)
    ]['vehicle_count'].mean()

    ratio = hajj_peak_mean / max(weekday_midday_mean, 1.0)
    record(
        'Hajj peak hour (Zone_1, 12:00) vs standard weekday midday',
        '>= 2.5x',
        ratio,
        ratio >= 2.5
    )

    # Check that hajj_phase column exists
    has_phase_col = 'hajj_phase' in df_hajj.columns
    record(
        'hajj_phase column present in output',
        'True',
        float(has_phase_col),
        has_phase_col
    )

    # Check three distinct phases exist
    phases        = set(df_hajj['hajj_phase'].unique()) - {'none'}
    all_phases    = phases == {'inbound', 'peak', 'outbound'}
    record(
        'All three Hajj phases present (inbound, peak, outbound)',
        'True',
        float(all_phases),
        all_phases
    )

    # Route zones should have higher vehicle_count than non-route zones during peak
    peak_route     = df_hajj[
        (df_hajj['hajj_phase'] == 'peak') & (df_hajj['zone'].isin(HAJJ_ROUTE_ZONES))
    ]['vehicle_count'].mean()
    peak_non_route = df_hajj[
        (df_hajj['hajj_phase'] == 'peak') & (~df_hajj['zone'].isin(HAJJ_ROUTE_ZONES))
    ]['vehicle_count'].mean()
    route_higher   = peak_route > peak_non_route
    record(
        'Hajj route zones higher than non-route zones during peak',
        'True',
        float(route_higher),
        route_higher
    )

    report = pd.DataFrame(results)

    print("\n" + "=" * 60)
    print(f"  Hajj Mode Validation Report — {city}")
    print("=" * 60)
    print(report.to_string(index=False))
    print("=" * 60)
    passed = (report['Status'] == 'PASS').sum()
    print(f"  {passed} / {len(report)} checks passed")
    print("=" * 60 + "\n")

    return report


def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add temporal lag and rolling features per zone.

    Requires df to be sorted by zone and timestamp.
    Must be called after apply_hourly_patterns().
    """
    df = df.copy().sort_values(['zone', 'timestamp']).reset_index(drop=True)

    df['vehicle_count_lag_1h'] = df.groupby('zone')['vehicle_count'].shift(1)
    df['vehicle_count_lag_2h'] = df.groupby('zone')['vehicle_count'].shift(2)
    df['congestion_lag_1h']    = df.groupby('zone')['congestion_score'].shift(1)
    df['rolling_mean_3h']      = (
        df.groupby('zone')['vehicle_count']
          .transform(lambda x: x.shift(1).rolling(3).mean())
    )
    df['rolling_std_3h']       = (
        df.groupby('zone')['vehicle_count']
          .transform(lambda x: x.shift(1).rolling(3).std())
    )

    df = df.dropna(subset=[
        'vehicle_count_lag_1h', 'vehicle_count_lag_2h',
        'congestion_lag_1h', 'rolling_mean_3h', 'rolling_std_3h'
    ]).reset_index(drop=True)

    return df



def add_cross_zone_lag_features(df: pd.DataFrame, lag_hours: list = [1, 2]) -> pd.DataFrame:
    """
    Adds generic adjacent-zone lag features per ZONE_ADJACENCY:
      adjacent_congestion_lag_{h}h    — mean congestion_score of this row's
                                         adjacent zones, h hours ago
      adjacent_vehicle_count_lag_{h}h — mean vehicle_count of adjacent
                                         zones, h hours ago

    Generic (not neighbor-name-specific) because ZONE_ADJACENCY has
    asymmetric degree — a literal per-neighbor column name would be
    meaningless/sparse for zones that don't share that neighbor.

    Must be called AFTER add_lag_features().

    Missing values (series start, or a zone absent from ZONE_ADJACENCY)
    are filled with the row's own current value.
    """
    from src.config import ZONE_ADJACENCY

    df = df.copy().sort_values(['timestamp', 'zone']).reset_index(drop=True)

    pivot_cong = df.pivot_table(index='timestamp', columns='zone',
                                 values='congestion_score', aggfunc='first')
    pivot_vol  = df.pivot_table(index='timestamp', columns='zone',
                                 values='vehicle_count', aggfunc='first')

    # Precompute neighbor lists once (avoid dict lookup per row)
    neighbor_map = {
        zone: [n for n in ZONE_ADJACENCY.get(zone, []) if n in pivot_cong.columns]
        for zone in df['zone'].unique()
    }

    for h in lag_hours:
        cong_lag = pivot_cong.shift(h)
        vol_lag  = pivot_vol.shift(h)
        cong_col = f'adjacent_congestion_lag_{h}h'
        vol_col  = f'adjacent_vehicle_count_lag_{h}h'

        # Vectorized: compute mean-of-neighbors per zone, then map back via merge
        cong_means = {}
        vol_means  = {}
        for zone, neighbors in neighbor_map.items():
            if not neighbors:
                cong_means[zone] = pd.Series(dtype=float)
                vol_means[zone]  = pd.Series(dtype=float)
                continue
            cong_means[zone] = cong_lag[neighbors].mean(axis=1)
            vol_means[zone]  = vol_lag[neighbors].mean(axis=1)

        df[cong_col] = df.apply(
            lambda r: cong_means[r['zone']].get(r['timestamp'], np.nan), axis=1
        )
        df[vol_col] = df.apply(
            lambda r: vol_means[r['zone']].get(r['timestamp'], np.nan), axis=1
        )

        df[cong_col] = df[cong_col].fillna(df['congestion_score'])
        df[vol_col]  = df[vol_col].fillna(df['vehicle_count'])

    return df


