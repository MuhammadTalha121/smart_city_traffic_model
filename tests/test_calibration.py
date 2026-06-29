import os
import pandas as pd
import pytest
from fastapi.testclient import TestClient

if not os.environ.get("API_KEY"):
    os.environ["API_KEY"] = "test-key-for-pytest-only"
TEST_KEY = os.environ["API_KEY"]

from app import app
from src.auth import create_key
from src.calibration import (
    compute_calibration_error,
    compute_calibration_factors,
    apply_calibration_factors,
    save_calibration_factors,
    load_calibration_factors,
    generate_calibration_report,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ---- Unit tests ----

def test_calibration_error_is_zero_when_synthetic_matches_real():
    df = pd.DataFrame({
        "zone": ["Zone_1", "Zone_1", "Zone_2"],
        "hour": [8, 9, 8],
        "vehicle_count": [100.0, 120.0, 80.0],
    })
    metrics = compute_calibration_error(df, df.copy())
    assert metrics["mae"] == 0.0
    assert metrics["mape"] == 0.0
    assert metrics["calibration_score"] == 1.0
    assert metrics["matched_rows"] == 3


def test_calibration_factors_reduce_mae_on_second_application():
    synthetic_df = pd.DataFrame({
        "zone": ["Zone_1", "Zone_1", "Zone_2"],
        "hour": [8, 9, 8],
        "vehicle_count": [100.0, 120.0, 80.0],
    })
    real_df = pd.DataFrame({
        "zone": ["Zone_1", "Zone_1", "Zone_2"],
        "hour": [8, 9, 8],
        "vehicle_count": [120.0, 144.0, 96.0],
    })

    initial_mae = compute_calibration_error(synthetic_df, real_df)["mae"]

    factors = compute_calibration_factors(synthetic_df, real_df)
    calibrated_df = apply_calibration_factors(synthetic_df, factors["factors"])
    calibrated_mae = compute_calibration_error(calibrated_df, real_df)["mae"]

    assert calibrated_mae < initial_mae


def test_apply_calibration_factors_ignores_unknown_zones():
    df = pd.DataFrame({"zone": ["Zone_1"], "hour": [8], "vehicle_count": [100.0]})
    factors = {"Zone_1": {"8": 1.2}, "Zone_99": {"8": 1.5}}
    result = apply_calibration_factors(df, factors)
    assert result.loc[0, "vehicle_count"] == 120.0
    assert result.loc[0, "calibrated"] is True or result.loc[0, "calibrated"] == True


def test_save_and_load_calibration_factors_roundtrip(tmp_path):
    factors = {"factors": {"Zone_1": {"8": 1.15}}, "computed_at": "x", "zones": 1, "total_entries": 1}
    path = str(tmp_path / "cal.json")
    save_calibration_factors(factors, path)
    loaded = load_calibration_factors(path)
    assert loaded["factors"]["Zone_1"]["8"] == 1.15


def test_load_calibration_factors_missing_returns_none():
    assert load_calibration_factors("does_not_exist.json") is None


def test_generate_calibration_report_writes_file(tmp_path):
    synthetic_df = pd.DataFrame({"zone": ["Zone_1"], "hour": [8], "vehicle_count": [100.0]})
    real_df = pd.DataFrame({"zone": ["Zone_1"], "hour": [8], "vehicle_count": [120.0]})
    output_path = str(tmp_path / "report.md")
    content = generate_calibration_report(synthetic_df, real_df, output_path)
    assert os.path.exists(output_path)
    assert "Calibration Score" in content


# ---- API tests ----

def test_calibration_status_no_auth_returns_401(client):
    response = client.get("/calibration/status")
    assert response.status_code == 401


@pytest.fixture(autouse=True)
def _isolate_calibration_file():
    """Snapshot/restore calibration_factors.json so tests never depend on
    or pollute whatever is sitting in the project root."""
    path = "calibration_factors.json"
    backup = None
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            backup = f.read()
    yield
    if backup is not None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(backup)
    elif os.path.exists(path):
        os.remove(path)

def test_calibration_status_admin_returns_200(client):
    save_calibration_factors({
        "factors": {"Zone_1": {"8": 1.1}},
        "computed_at": "2026-01-01T00:00:00",
        "zones": 1,
        "total_entries": 1,
        "metrics": {"calibration_score": 0.9},
    })
    response = client.get("/calibration/status", headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 200
    data = response.json()
    assert data["calibrated"] is True
    assert data["metrics"]["calibration_score"] == 0.9


def test_calibration_upload_endpoint_requires_admin(client):
    ro_key = create_key("READ_ONLY", "all")
    csv_bytes = b"zone,hour,vehicle_count\nZone_1,8,100\n"
    response = client.post(
        "/calibration/upload",
        headers={"X-API-Key": ro_key},
        files={"file": ("real.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 403


def test_calibration_upload_no_auth_returns_401(client):
    response = client.post(
        "/calibration/upload",
        files={"file": ("real.csv", b"zone,hour,vehicle_count\nZone_1,8,100\n", "text/csv")},
    )
    assert response.status_code == 401


def test_calibration_upload_rejects_non_csv(client):
    response = client.post(
        "/calibration/upload",
        headers={"X-API-Key": TEST_KEY},
        files={"file": ("real.txt", b"not a csv", "text/plain")},
    )
    assert response.status_code == 422


def test_calibration_upload_succeeds_with_valid_csv(client):
    csv_bytes = b"zone,hour,vehicle_count\nZone_1,8,300\nZone_2,8,150\n"
    response = client.post(
        "/calibration/upload?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
        files={"file": ("real.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "metrics" in data
    assert os.path.exists("calibration_factors.json")