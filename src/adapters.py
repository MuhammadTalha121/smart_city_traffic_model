import requests
import pandas as pd
import numpy as np
from datetime import datetime
from abc import ABC, abstractmethod


CITY_COORDINATES = {
    'Riyadh': {'lat': 24.7136, 'lon': 46.6753},
    'NEOM'  : {'lat': 28.2500, 'lon': 35.5000},
    'Dubai' : {'lat': 25.2048, 'lon': 55.2708},
    'Karachi': {'lat': 24.8607, 'lon': 67.0011},
}


class BaseAdapter(ABC):
    """Common interface every data adapter must implement."""

    @abstractmethod
    def fetch(self, city: str) -> pd.DataFrame:
        """Fetch data for a city and return a normalised DataFrame."""


class WeatherAdapter(BaseAdapter):
    """
    Fetch current weather for a city using the Open-Meteo API.

    Free, no API key required.
    Endpoint: https://api.open-meteo.com/v1/forecast
    Maps raw meteorological values to the weather categories used
    throughout the system: clear, dust, fog, humid, rain, sandstorm.
    """

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def fetch(self, city: str = 'Riyadh') -> pd.DataFrame:
        """Return a single-row DataFrame with current weather for the city."""
        coords = CITY_COORDINATES.get(city, CITY_COORDINATES['Riyadh'])

        params = {
            'latitude'              : coords['lat'],
            'longitude'             : coords['lon'],
            'current'               : 'temperature_2m,wind_speed_10m,precipitation,relative_humidity_2m,visibility',
            'timezone'              : 'Asia/Riyadh',
            'wind_speed_unit'       : 'kmh',
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data    = response.json()
            current = data.get('current', {})

            wind_speed   = float(current.get('wind_speed_10m', 0))
            precipitation = float(current.get('precipitation', 0))
            humidity     = float(current.get('relative_humidity_2m', 0))
            visibility   = float(current.get('visibility', 10000))
            temperature  = float(current.get('temperature_2m', 30))

            weather = self._classify_weather(
                wind_speed, precipitation, humidity, visibility
            )

            return pd.DataFrame([{
                'city'        : city,
                'timestamp'   : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source'      : 'open-meteo',
                'weather'     : weather,
                'temperature' : temperature,
                'wind_speed'  : wind_speed,
                'precipitation': precipitation,
                'humidity'    : humidity,
                'visibility'  : visibility,
                'fetched_at'  : datetime.now(),
            }])

        except requests.RequestException as e:
            print(f"WeatherAdapter: API call failed ({e}). Falling back to clear.")
            return self._fallback(city)

    def _classify_weather(
        self,
        wind_speed: float,
        precipitation: float,
        humidity: float,
        visibility: float,
    ) -> str:
        """Map meteorological readings to system weather categories."""
        if wind_speed > 40 and visibility < 1000:
            return 'sandstorm'
        if wind_speed > 30 and visibility < 3000:
            return 'dust'
        if precipitation > 0:
            return 'rain'
        if visibility < 2000:
            return 'fog'
        if humidity > 80:
            return 'humid'
        return 'clear'

    def _fallback(self, city: str) -> pd.DataFrame:
        """Return a safe default row when the API is unreachable."""
        return pd.DataFrame([{
            'city'        : city,
            'timestamp'   : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source'      : 'fallback',
            'weather'     : 'clear',
            'temperature' : 35.0,
            'wind_speed'  : 10.0,
            'precipitation': 0.0,
            'humidity'    : 30.0,
            'visibility'  : 10000.0,
            'fetched_at'  : datetime.now(),
        }])


class OpenStreetMapAdapter(BaseAdapter):
    """
    Fetch road network for a city bounding box using the Overpass API.

    Free, no API key required.
    Endpoint: https://overpass-api.de/api/interpreter
    Returns major road segments within the city bounding box.
    """

    BASE_URL    = "https://overpass-api.de/api/interpreter"
    CITY_BBOXES = {
        'Riyadh' : (24.50, 46.50, 24.90, 46.90),
        'NEOM'   : (28.00, 35.20, 28.50, 35.80),
        'Dubai'  : (25.05, 55.05, 25.35, 55.45),
        'Karachi': (24.75, 66.85, 25.05, 67.20),
    }

    def fetch(self, city: str = 'Riyadh') -> pd.DataFrame:
        """Return a DataFrame of road segments for the city."""
        bbox  = self.CITY_BBOXES.get(city, self.CITY_BBOXES['Riyadh'])
        query = f"""
        [out:json][timeout:25];
        (
          way["highway"~"motorway|trunk|primary|secondary"]
          ({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
        );
        out body;
        """

        try:
            response = requests.post(
                self.BASE_URL,
                data={'data': query},
                timeout=30,
            )
            response.raise_for_status()
            elements = response.json().get('elements', [])

            rows = []
            fetched_at = datetime.now()
            for element in elements[:50]:
                tags      = element.get('tags', {})
                highway   = tags.get('highway', 'unknown')
                road_name = tags.get('name', tags.get('name:en', 'Unnamed Road'))
                road_type = self._map_road_type(highway)
                rows.append({
                    'city'     : city,
                    'source'   : 'overpass',
                    'fetched_at': fetched_at,
                    'road_name': road_name,
                    'road_type': road_type,
                    'highway'  : highway,
                    'osm_id'   : element.get('id'),
                })

            if not rows:
                return self._fallback(city)

            return pd.DataFrame(rows)

        except requests.RequestException as e:
            print(f"OpenStreetMapAdapter: API call failed ({e}). Using fallback.")
            return self._fallback(city)

    def _map_road_type(self, highway: str) -> str:
        """Map OSM highway tags to system road type categories."""
        mapping = {
            'motorway'  : 'highway',
            'trunk'     : 'highway',
            'primary'   : 'arterial',
            'secondary' : 'arterial',
            'tertiary'  : 'local',
            'residential': 'local',
        }
        return mapping.get(highway, 'arterial')

    def _fallback(self, city: str) -> pd.DataFrame:
        """Return known major roads when the API is unreachable."""
        roads = {
            'Riyadh': [
                {'road_name': 'King Fahd Road',    'road_type': 'highway'},
                {'road_name': 'King Abdullah Road', 'road_type': 'highway'},
                {'road_name': 'Olaya Street',       'road_type': 'arterial'},
                {'road_name': 'Tahlia Street',      'road_type': 'arterial'},
            ],
            'Dubai': [
                {'road_name': 'Sheikh Zayed Road', 'road_type': 'highway'},
                {'road_name': 'Al Khail Road',     'road_type': 'highway'},
            ],
        }
        rows = roads.get(city, roads['Riyadh'])
        for row in rows:
            row.update({'city': city, 'source': 'fallback', 'highway': 'primary', 'osm_id': None,
                        'fetched_at': datetime.now()})
        return pd.DataFrame(rows)


class MockIoTAdapter(BaseAdapter):
    """
    Simulate IoT sensor readings for a city.

    Mirrors the column structure of generate_traffic_data() exactly.
    Acts as fallback when real APIs are unavailable or rate-limited.
    noise_level: 0.0 = deterministic, 1.0 = maximum variance.
    """

    def __init__(self, noise_level: float = 0.3):
        self.noise_level = float(noise_level)

    def fetch(self, city: str = 'Riyadh') -> pd.DataFrame:
        """Return a single-hour simulated sensor reading for all zones."""
        from src.config import CITY_PROFILES, WEATHER_SPEED_IMPACT

        np.random.seed(int(datetime.now().timestamp()) % 10000)
        profile   = CITY_PROFILES.get(city, list(CITY_PROFILES.values())[0])
        hour      = datetime.now().hour
        fetched_at = datetime.now()
        zones     = ['Zone_1', 'Zone_2', 'Zone_3', 'Zone_4', 'Zone_5']
        rows      = []

        for zone in zones:
            base_vehicles = profile['base_vehicles']
            noise         = np.random.normal(0, base_vehicles * self.noise_level)
            vehicle_count = float(np.clip(base_vehicles + noise, 0, 500))
            avg_speed     = float(np.clip(
                np.random.normal(profile['speed_mean'], 10 * self.noise_level), 20, 100
            ))
            weather = np.random.choice(
                profile['weather_conditions'], p=profile['weather_probs']
            )

            rows.append({
                'city'         : city,
                'timestamp'    : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'fetched_at'   : fetched_at,
                'source'       : 'mock-iot',
                'zone'         : zone,
                'hour'         : hour,
                'vehicle_count': vehicle_count,
                'avg_speed'    : avg_speed,
                'weather'      : weather,
                'road_type'    : 'arterial',
                'is_weekend'   : int(datetime.now().weekday() in [4, 5]),
                'rush_hour'    : int(hour in [7, 8, 17, 18]),
                'is_late_night': int(hour in [21, 22, 23, 0]),
                'event'        : 0,
            })

        return pd.DataFrame(rows)


class MockMicroMobilityAdapter(BaseAdapter):
    """
    Simulate micro-mobility sensor readings (e-scooters and bikes) per zone.

    Generates deterministic-ish counts tied to the current hour so that
    rush-hour zones show higher micro-mobility activity.
    noise_level: 0.0 = deterministic, 1.0 = maximum variance.
    """

    def __init__(self, noise_level: float = 0.2):
        self.noise_level = float(noise_level)

    def fetch(self, city: str = 'Riyadh') -> pd.DataFrame:
        """Return one row per zone with simulated micro-mobility counts."""
        from src.config import LAST_MILE_TRANSFER_ZONES

        np.random.seed(int(datetime.now().timestamp()) % 10000)
        hour  = datetime.now().hour
        zones = ['Zone_1', 'Zone_2', 'Zone_3', 'Zone_4', 'Zone_5']
        rows  = []

        for zone in zones:
            base_scooters = 40 if zone in LAST_MILE_TRANSFER_ZONES else 15
            base_bikes    = 20 if zone in LAST_MILE_TRANSFER_ZONES else 8

            rush_multiplier = 1.5 if hour in [7, 8, 9, 17, 18, 19] else 1.0

            noise_s = np.random.normal(0, base_scooters * self.noise_level)
            noise_b = np.random.normal(0, base_bikes    * self.noise_level)

            active_scooters = int(np.clip(
                (base_scooters + noise_s) * rush_multiplier, 0, 200
            ))
            active_bikes = int(np.clip(
                (base_bikes + noise_b) * rush_multiplier, 0, 100
            ))

            avg_scooter_speed = float(np.clip(
                np.random.normal(14.0, 2.0 * self.noise_level), 8.0, 20.0
            ))

            rows.append({
                'city'              : city,
                'timestamp'         : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'source'            : 'mock-micromobility',
                'zone'              : zone,
                'hour'              : hour,
                'active_scooters'   : active_scooters,
                'active_bikes'      : active_bikes,
                'avg_scooter_speed' : round(avg_scooter_speed, 1),
            })

        return pd.DataFrame(rows)

class GreenWavePlanner:
    """
    Calculates synchronized green-light phase schedules for priority vehicle corridors.

    Ensures an emergency vehicle or priority convoy travels a multi-zone
    route without stopping by computing per-zone green windows aligned
    to estimated arrival times.
    """

    def calculate_green_wave(
        self,
        route: list,
        vehicle_speed_kmph: float,
        departure_time_s: float,
    ) -> dict:
        """
        Generate a per-zone green phase schedule for a priority route.

        Parameters
        ----------
        route              : Ordered list of zone names from origin to destination.
        vehicle_speed_kmph : Travel speed of the priority vehicle in km/h.
        departure_time_s   : Departure time as seconds-since-midnight.

        Returns
        -------
        dict with route, phase_schedule, total_travel_s, stops_avoided.
        """
        from src.config import (
            ZONE_DISTANCE_M, GREEN_WAVE_BUFFER_S, MAX_GREEN_EXTENSION_S
        )

        travel_time_per_zone_s = (ZONE_DISTANCE_M / 1000) / vehicle_speed_kmph * 3600
        phase_schedule = []

        for i, zone in enumerate(route):
            arrival_s   = departure_time_s + (i * travel_time_per_zone_s)
            green_start = arrival_s - GREEN_WAVE_BUFFER_S
            green_end   = arrival_s + GREEN_WAVE_BUFFER_S + MAX_GREEN_EXTENSION_S

            phase_schedule.append({
                "zone"         : zone,
                "arrival_s"    : round(arrival_s, 1),
                "green_start_s": round(max(green_start, 0), 1),
                "green_end_s"  : round(green_end, 1),
            })

        total_travel_s = (len(route) - 1) * travel_time_per_zone_s if len(route) > 1 else 0

        return {
            "route"         : route,
            "phase_schedule": phase_schedule,
            "total_travel_s": round(total_travel_s, 1),
            "stops_avoided" : max(0, len(route) - 1),
        }





def is_data_stale(adapter_source: str, fetched_at) -> bool:
    """
    Return True if fetched_at exceeds MAX_DATA_AGE_SECONDS for the given
    source. A source absent from MAX_DATA_AGE_SECONDS, or mapped to None
    (e.g. 'mock'), is never stale — mock/unconfigured synthetic data has
    no real-world staleness concept since nothing external can go down.
    """
    from src.config import MAX_DATA_AGE_SECONDS

    max_age = MAX_DATA_AGE_SECONDS.get(adapter_source)
    if max_age is None or fetched_at is None:
        return False

    if isinstance(fetched_at, str):
        fetched_at = pd.to_datetime(fetched_at).to_pydatetime()
    elif isinstance(fetched_at, pd.Timestamp):
        fetched_at = fetched_at.to_pydatetime()

    age_seconds = (datetime.now() - fetched_at).total_seconds()
    return age_seconds > max_age



def get_adapter(source: str) -> BaseAdapter:
    """
    Return the correct adapter instance for the requested source.

    Parameters
    ----------
    source : 'weather' | 'osm' | 'mock' | 'micromobility'

    Returns
    -------
    BaseAdapter instance ready to call .fetch(city)
    """
    adapters = {
        'weather'       : WeatherAdapter,
        'osm'           : OpenStreetMapAdapter,
        'mock'          : MockIoTAdapter,
        'micromobility' : MockMicroMobilityAdapter,
    }
    cls = adapters.get(source)
    if cls is None:
        raise ValueError(f"Unknown source '{source}'. Choose from: {list(adapters.keys())}")
    return cls()