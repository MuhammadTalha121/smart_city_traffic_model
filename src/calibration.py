"""
Synthetic-to-real calibration framework.

Measures deviation between synthetic traffic data and real sensor counts,
and computes/applies per-zone, per-hour multiplicative correction factors.
Calibration is an optional overlay — absence of calibration_factors.json
means the system behaves exactly as before (no synthetic pipeline changes).
"""

import json
import os
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from src.config import CALIBRATION_FACTORS_PATH

REQUIRED_REAL_COLUMNS = {"zone", "hour", "vehicle_count"}


def load_real_counts(filepath: str) -> pd.DataFrame:
    """Load and validate a real traffic count CSV.

    Required columns: zone, hour, vehicle_count.
    Optional: avg_speed, weather, timestamp.
    """
    df = pd.read_csv(filepath)
    missing = REQUIRED_REAL_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["hour"] = df["hour"].astype(int)
    df["vehicle_count"] = df["vehicle_count"].astype(float)
    return df


def _aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse to one mean vehicle_count per zone/hour."""
    return (
        df.groupby(["zone", "hour"])["vehicle_count"]
        .mean()
        .reset_index()
    )


def compute_calibration_error(synthetic_df: pd.DataFrame, real_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Compare aggregated (per zone/hour mean) synthetic vs real vehicle counts.

    Returns mae, mape, r2, calibration_score (0-1, 1=perfect), coverage_pct
    (share of real zone/hour combos matched), matched_rows.
    """
    syn_agg = _aggregate(synthetic_df)
    real_agg = _aggregate(real_df)

    merged = pd.merge(syn_agg, real_agg, on=["zone", "hour"], suffixes=("_synthetic", "_real"))

    if merged.empty:
        return {
            "mae": None, "mape": None, "r2": None,
            "calibration_score": 0.0, "coverage_pct": 0.0, "matched_rows": 0,
        }

    y_true = merged["vehicle_count_real"].values
    y_pred = merged["vehicle_count_synthetic"].values

    mae = mean_absolute_error(y_true, y_pred)
    mape = float(np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1.0))) * 100)
    r2 = r2_score(y_true, y_pred) if len(merged) > 1 else (1.0 if mae == 0 else 0.0)

    calibration_score = max(0.0, min(1.0, 1.0 - (mape / 100)))
    coverage_pct = round(len(merged) / max(len(real_agg), 1) * 100, 2)

    return {
        "mae": round(float(mae), 4),
        "mape": round(mape, 4),
        "r2": round(float(r2), 4),
        "calibration_score": round(calibration_score, 4),
        "coverage_pct": coverage_pct,
        "matched_rows": int(len(merged)),
    }


def compute_calibration_factors(synthetic_df: pd.DataFrame, real_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute per-zone, per-hour multiplicative factors: factor = real / synthetic,
    clipped to [0.5, 2.0] to prevent runaway corrections from sparse real data.
    """
    syn_agg = _aggregate(synthetic_df)
    real_agg = _aggregate(real_df)
    merged = pd.merge(syn_agg, real_agg, on=["zone", "hour"], suffixes=("_synthetic", "_real"))

    if merged.empty:
        return {"factors": {}, "computed_at": pd.Timestamp.now().isoformat(), "zones": 0, "total_entries": 0}

    merged["factor"] = (
        merged["vehicle_count_real"] / merged["vehicle_count_synthetic"].replace(0, np.nan)
    ).fillna(1.0).clip(0.5, 2.0)

    factors: Dict[str, Dict[str, float]] = {}
    for _, row in merged.iterrows():
        zone = str(row["zone"])
        hour = str(int(row["hour"]))
        factors.setdefault(zone, {})[hour] = round(float(row["factor"]), 4)

    return {
        "factors": factors,
        "computed_at": pd.Timestamp.now().isoformat(),
        "zones": len(factors),
        "total_entries": int(len(merged)),
    }


def apply_calibration_factors(df: pd.DataFrame, factors: Dict[str, Dict[str, float]]) -> pd.DataFrame:
    """
    Apply per-zone, per-hour multipliers to vehicle_count. Never mutates input.
    Zones/hours absent from `factors` are left untouched (partial coverage).
    """
    df = df.copy()
    df["calibrated"] = False

    for zone, hour_factors in factors.items():
        zone_mask = df["zone"] == zone
        if not zone_mask.any():
            continue
        for hour_str, factor in hour_factors.items():
            mask = zone_mask & (df["hour"] == int(hour_str))
            if mask.any():
                df.loc[mask, "vehicle_count"] = (df.loc[mask, "vehicle_count"] * factor).clip(0, 500)
                df.loc[mask, "calibrated"] = True

    return df


def save_calibration_factors(factors: Dict[str, Any], filepath: str = CALIBRATION_FACTORS_PATH) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(factors, f, indent=2)


def load_calibration_factors(filepath: str = None) -> Optional[dict]:
    if filepath is None:
        from src.config import CALIBRATION_FACTORS_PATH
        filepath = CALIBRATION_FACTORS_PATH
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            return None
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return None


def generate_calibration_report(synthetic_df: pd.DataFrame, real_df: pd.DataFrame, output_path: str) -> str:
    """Write a markdown calibration report and return its content."""
    metrics = compute_calibration_error(synthetic_df, real_df)
    score = metrics["calibration_score"]

    if metrics["matched_rows"] == 0:
        interpretation = "No overlapping zone/hour combinations found between synthetic and real data."
    elif score >= 0.85:
        interpretation = "Excellent alignment. Synthetic data closely tracks real counts."
    elif score >= 0.70:
        interpretation = "Good alignment. Minor calibration factors recommended."
    elif score >= 0.50:
        interpretation = "Moderate drift. Calibration factors strongly recommended."
    else:
        interpretation = "Significant drift. Synthetic data requires substantial correction."

    report = (
        f"# Calibration Report\n\n"
        f"## Summary\n"
        f"- **Calibration Score**: {score}\n"
        f"- **MAE**: {metrics['mae']}\n"
        f"- **MAPE**: {metrics['mape']}%\n"
        f"- **R²**: {metrics['r2']}\n"
        f"- **Coverage**: {metrics['coverage_pct']}% ({metrics['matched_rows']} zone/hour combos matched)\n\n"
        f"## Interpretation\n{interpretation}\n"
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    return report