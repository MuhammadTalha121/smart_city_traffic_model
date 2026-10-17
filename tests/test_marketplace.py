import os
import tempfile

import pytest

from src.data_marketplace import DataMarketplaceExport


@pytest.fixture
def sample_predictions_csv(tmp_path):
    """Minimal predictions_log.csv with two cities and two zones, hourly rows."""
    path = tmp_path / "predictions_log.csv"
    path.write_text(
        "timestamp,city,zone,hour,weather,congestion_score,congestion_level,"
        "top_factor_1,top_factor_2,top_factor_3,plain_english,"
        "co2_kg,fuel_litres,interval_width,data_source\n"
        "2026-01-15 08:00:00,Riyadh,Zone_1,8,clear,0.42,Moderate,a,b,c,text,10.5,3.2,0.1,mock\n"
        "2026-01-15 09:00:00,Riyadh,Zone_1,9,clear,0.51,High,d,e,f,text,12.0,3.8,0.1,mock\n"
        "2026-01-15 08:00:00,Riyadh,Zone_2,8,clear,0.30,Moderate,g,h,i,text,8.0,2.5,0.1,mock\n"
        "2026-01-15 08:00:00,Jeddah,Zone_1,8,clear,0.55,High,j,k,l,text,14.0,4.4,0.1,mock\n",
        encoding="utf-8",
    )
    return str(path)


def test_export_granularity_minimum_15_minutes(tmp_path, sample_predictions_csv):
    exporter = DataMarketplaceExport(output_dir=str(tmp_path / "out"))
    result = exporter.generate_anonymised_export(
        city="Riyadh",
        date_from="2026-01-15",
        date_to="2026-01-15",
        granularity_minutes=5,
        predictions_path=sample_predictions_csv,
    )
    assert "error" in result
    assert "below the PDPL minimum" in result["error"]


def test_export_pdpl_validated_before_release(tmp_path, sample_predictions_csv):
    exporter = DataMarketplaceExport(output_dir=str(tmp_path / "out"))
    result = exporter.generate_anonymised_export(
        city="Riyadh",
        date_from="2026-01-15",
        date_to="2026-01-15",
        granularity_minutes=15,
        predictions_path=sample_predictions_csv,
    )
    assert "error" not in result, result
    out_path = result["path"]
    assert os.path.exists(out_path)

    import pandas as pd
    df = pd.read_csv(out_path)
    assert "timestamp" not in df.columns
    assert "top_factor_1" not in df.columns
    assert "plain_english" not in df.columns
    assert (df["window_minutes"] >= 15).all()
    assert set(df["city"].unique()) == {"Riyadh"}
    assert exporter.validate_export_for_pdpl(out_path) is True