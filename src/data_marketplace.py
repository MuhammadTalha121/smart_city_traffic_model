"""Data Marketplace Export — PDPL-validated, anonymised historical traffic exports (PROMPT 160)."""

import csv
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from src.config import MARKETPLACE_EXPORTS_LOG, MARKETPLACE_MIN_AGGREGATION_MINUTES


class DataMarketplaceExport:
    """
    Generates anonymised, aggregated CSV exports from predictions_log.csv.

    Guarantees:
      - No row-level (per-prediction) data leaves the system
      - Aggregation window is >= MARKETPLACE_MIN_AGGREGATION_MINUTES
      - Every export is logged to marketplace_exports_log.csv
    """

    def __init__(self, output_dir: str = "marketplace_exports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_anonymised_export(
        self,
        city: str,
        date_from: str,
        date_to: str,
        granularity_minutes: int = 15,
        predictions_path: str = "predictions_log.csv",
    ) -> Dict:
        """
        Build an aggregated CSV export for a city and date range.

        Returns:
            {request_id, path, row_count, city, date_from, date_to,
             granularity_minutes, generated_at} on success
            or {'error': str} if validation fails.
        """
        if granularity_minutes < MARKETPLACE_MIN_AGGREGATION_MINUTES:
            return {
                "error": (
                    f"granularity_minutes={granularity_minutes} is below the "
                    f"PDPL minimum of {MARKETPLACE_MIN_AGGREGATION_MINUTES}."
                )
            }

        if not os.path.exists(predictions_path):
            return {"error": f"{predictions_path} not found."}

        try:
            df = pd.read_csv(predictions_path, engine="python", on_bad_lines="skip")
        except Exception as e:
            return {"error": f"Failed to read {predictions_path}: {e}"}

        if df.empty or "timestamp" not in df.columns or "city" not in df.columns:
            return {"error": "predictions_log.csv is empty or missing required columns."}

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])
        df = df[df["city"] == city]

        try:
            start = pd.Timestamp(date_from)
            end   = pd.Timestamp(date_to) + pd.Timedelta(days=1)
        except Exception as e:
            return {"error": f"Invalid date range: {e}"}

        df = df[(df["timestamp"] >= start) & (df["timestamp"] < end)]

        if df.empty:
            return {"error": f"No data for city='{city}' in range {date_from}..{date_to}."}

        df["window_start"] = df["timestamp"].dt.floor(f"{granularity_minutes}min")

        agg = df.groupby(["zone", "window_start"]).agg(
            congestion_score=("congestion_score", "mean"),
            congestion_level=("congestion_level", lambda x: x.mode().iloc[0] if not x.mode().empty else "Unknown"),
            co2_kg=("co2_kg", "sum"),
            fuel_litres=("fuel_litres", "sum"),
            prediction_count=("congestion_score", "count"),
        ).reset_index()

        agg = agg[agg["prediction_count"] > 0].copy()
        agg["city"] = city
        agg["window_minutes"] = granularity_minutes
        agg["congestion_score"] = agg["congestion_score"].round(4)
        agg["co2_kg"] = agg["co2_kg"].round(4)
        agg["fuel_litres"] = agg["fuel_litres"].round(4)

        request_id = f"exp_{uuid.uuid4().hex[:12]}"
        filename = f"{request_id}_{city}_{date_from}_{date_to}.csv"
        out_path = os.path.join(self.output_dir, filename)
        agg.to_csv(out_path, index=False)

        if not self.validate_export_for_pdpl(out_path):
            os.remove(out_path)
            return {"error": "Export failed PDPL validation and was discarded."}

        self._log_export(request_id, city, date_from, date_to, granularity_minutes, len(agg), out_path)

        return {
            "request_id": request_id,
            "path": out_path,
            "row_count": len(agg),
            "city": city,
            "date_from": date_from,
            "date_to": date_to,
            "granularity_minutes": granularity_minutes,
            "generated_at": datetime.now().isoformat(),
        }

    def validate_export_for_pdpl(self, export_path: str) -> bool:
        """
        Confirm the export contains only aggregated data at or above the
        PDPL minimum window. Returns True if compliant, False otherwise.
        """
        if not os.path.exists(export_path):
            return False
        try:
            df = pd.read_csv(export_path)
        except Exception:
            return False

        if "window_minutes" not in df.columns:
            return False
        if (df["window_minutes"] < MARKETPLACE_MIN_AGGREGATION_MINUTES).any():
            return False

        forbidden_columns = {"timestamp", "top_factor_1", "plain_english"}
        if forbidden_columns.intersection(df.columns):
            return False

        return True

    def _log_export(
        self,
        request_id: str,
        city: str,
        date_from: str,
        date_to: str,
        granularity_minutes: int,
        row_count: int,
        path: str,
    ) -> None:
        file_exists = os.path.isfile(MARKETPLACE_EXPORTS_LOG)
        row = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "city": city,
            "date_from": date_from,
            "date_to": date_to,
            "granularity_minutes": granularity_minutes,
            "row_count": row_count,
            "path": path,
        }
        with open(MARKETPLACE_EXPORTS_LOG, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)