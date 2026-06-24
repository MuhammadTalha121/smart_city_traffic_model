from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
from src.model import congestion_level, compute_emissions, detect_anomalies
from src.config import CONGESTION_THRESHOLDS, ZONE_CENTROIDS

def to_datex_measurement(
    prediction_dict: Dict[str, Any],
    zone: str,
    city: str,
    timestamp: str
) -> Dict[str, Any]:
    """
    Convert a single prediction dict to a DATEX II‑shaped measurement entry.

    Maps congestion_score, congestion_level, vehicle_count, avg_speed,
    and emissions to the closest fields in the MeasuredDataPublication pattern.

    DATEX II reference: version 2.3, MeasuredDataPublication structure.
    Used fields:
      - measurementSiteReference: zone and city.
      - measuredValue: a list of basicDataValue items:
          * trafficFlow (vehicle_count)
          * averageSpeed (avg_speed)
          * degreeOfCongestion (congestion_score, 0-1)
          * co2Emissions (emissions.co2_kg, as an extension)

    Gaps (unmapped): vehicleType, measurementSiteType, and other DATEX II
    fields requiring more detailed data are omitted.
    """
    emissions = compute_emissions(
        prediction_dict.get('congestion_level', 'Low'),
        prediction_dict.get('vehicle_count', 0),
        1.0
    )

    # Build measurement values list
    measured_values = [
        {
            "valueType": "trafficFlow",
            "value": float(prediction_dict.get('vehicle_count', 0)),
            "unit": "vehiclesPerHour"
        },
        {
            "valueType": "averageSpeed",
            "value": float(prediction_dict.get('avg_speed', 0)),
            "unit": "kmPerHour"
        },
        {
            "valueType": "degreeOfCongestion",
            "value": float(prediction_dict.get('congestion_score', 0)),
            "unit": "ratio"
        },
        {
            "valueType": "co2Emissions",
            "value": emissions['co2_kg'],
            "unit": "kgPerHour"
        }
    ]

    return {
        "measurementSiteReference": {
            "id": zone,
            "city": city
        },
        "measurementTime": timestamp,
        "measuredValue": measured_values,
        "congestionLevel": prediction_dict.get('congestion_level', 'Low')
    }


def to_datex_situation(anomaly_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert an anomaly record to a simplified DATEX II SituationPublication entry.

    Maps to SituationPublication with:
      - situationId: unique per record (zone + timestamp)
      - situationType: "incident" or "advisory"
      - situationTime: timestamp
      - description: anomaly_severity and recommendation
      - location: zone

    Gaps: detailed geo-coordinates, lane closures, etc. are not present.
    """
    return {
        "situationId": f"{anomaly_record.get('zone', 'unknown')}_{anomaly_record.get('timestamp', '')}",
        "situationType": "incident" if anomaly_record.get('anomaly_severity') in ('Anomalous', 'Critical Anomaly') else "advisory",
        "situationTime": anomaly_record.get('timestamp', datetime.now().isoformat()),
        "description": anomaly_record.get('anomaly_recommendation', 'No recommendation'),
        "location": {
            "zone": anomaly_record.get('zone', 'unknown')
        },
        "severity": anomaly_record.get('anomaly_severity', 'Normal')
    }


def generate_datex_payload(city: str) -> Dict[str, Any]:
    """
    Generate a full DATEX II‑shaped payload for a given city.

    Combines:
      - MeasuredDataPublication: one entry per zone with latest congestion,
        speed, flow, emissions.
      - SituationPublication: list of active anomalies (if any) from the
        latest data.

    Returns a dictionary with top-level keys:
      - publicationCreator: "Smart City Traffic Intelligence API"
      - publicationTime: ISO timestamp
      - publicationType: "MeasuredDataPublication"
      - measurements: list of measurement entries (from to_datex_measurement)
      - situations: list of situation entries (from to_datex_situation)
    """
    from app import app  # to access app.state
    df = app.state.city_dfs.get(city)
    if df is None:
        # fallback: use default df
        df = app.state.df

    if df is None or df.empty:
        return {
            "publicationCreator": "Smart City Traffic Intelligence API",
            "publicationTime": datetime.now().isoformat(),
            "publicationType": "MeasuredDataPublication",
            "measurements": [],
            "situations": [],
            "note": "No data available for the requested city."
        }

    # Get latest row per zone
    latest = df.sort_values('timestamp').groupby('zone').last().reset_index()

    # Compute anomalies on the full city DataFrame (for situation export)
    anomaly_df = detect_anomalies(df)
    active_anomalies = anomaly_df[anomaly_df['anomaly_flag'] == 1].to_dict(orient='records')

    measurements = []
    for _, row in latest.iterrows():
        # Build a prediction dict from the row
        pred_dict = {
            'congestion_score': row.get('congestion_score', 0),
            'congestion_level': congestion_level(row.get('congestion_score', 0)),
            'vehicle_count': row.get('vehicle_count', 0),
            'avg_speed': row.get('avg_speed', 0),
            # emissions will be computed inside to_datex_measurement
        }
        zone = str(row['zone'])
        timestamp = row.get('timestamp', datetime.now().isoformat())
        measurements.append(to_datex_measurement(pred_dict, zone, city, timestamp))

    situations = [to_datex_situation(rec) for rec in active_anomalies]

    return {
        "publicationCreator": "Smart City Traffic Intelligence API",
        "publicationTime": datetime.now().isoformat(),
        "publicationType": "MeasuredDataPublication",
        "measurements": measurements,
        "situations": situations,
        "coveredFields": [
            "trafficFlow (vehicle_count)",
            "averageSpeed (avg_speed)",
            "degreeOfCongestion (congestion_score)",
            "co2Emissions (emissions.co2_kg)",
            "congestionLevel (congestion_level)",
            "anomaly situation (from detect_anomalies)"
        ],
        "gapNote": "This is a DATEX II‑shaped export, not a full implementation. Many DATEX II fields (e.g., vehicleType, measurementSiteType, detailed geo-coordinates) are not mapped due to data limitations."
    }





def generate_geojson_payload(city: str) -> dict:
    """
    Generate a GeoJSON FeatureCollection for the given city.

    Each zone becomes a Point feature with properties:
      - zone, congestion_score, congestion_level,
        vehicle_count, avg_speed, co2_kg_per_hour, timestamp.

    Compatible with QGIS, ArcGIS, Leaflet, Google Maps.
    """
    from app import app
    from src.config import ZONE_CENTROIDS
    from datetime import datetime

    df = app.state.city_dfs.get(city)
    if df is None:
        df = app.state.df

    if df is None or df.empty:
        return {
            "type": "FeatureCollection",
            "features": [],
            "note": "No data available for the requested city.",
            "generated_at": datetime.now().isoformat(),
            "city": city
        }

    latest = df.sort_values('timestamp').groupby('zone').last().reset_index()

    features = []
    for _, row in latest.iterrows():
        zone = str(row['zone'])
        coords = ZONE_CENTROIDS.get(zone, [0.0, 0.0])

        level = congestion_level(row.get('congestion_score', 0))
        em = compute_emissions(level, row.get('vehicle_count', 0), 1.0)

        # Convert timestamp to string
        ts = row.get('timestamp', datetime.now())
        if hasattr(ts, 'isoformat'):
            timestamp_str = ts.isoformat()
        else:
            timestamp_str = str(ts)

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": coords
            },
            "properties": {
                "zone": zone,
                "congestion_score": float(row.get('congestion_score', 0)),
                "congestion_level": level,
                "vehicle_count": float(row.get('vehicle_count', 0)),
                "avg_speed": float(row.get('avg_speed', 0)),
                "co2_kg_per_hour": em['co2_kg'],
                "timestamp": timestamp_str
            }
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
        "generated_at": datetime.now().isoformat(),
        "city": city
    }