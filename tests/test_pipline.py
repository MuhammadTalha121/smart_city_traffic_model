import os
import joblib
import numpy as np
import pytest

from src import pipeline as pipeline_module
from src.pipeline import evaluate_staged_model, promote_staged_model


class _DummyModel:
    def __init__(self, const_pred):
        self.const_pred = const_pred

    def predict(self, X):
        return np.full(len(X), self.const_pred)


def _patch_paths(monkeypatch, tmp_path):
    staging  = str(tmp_path / "model_staging.joblib")
    live     = str(tmp_path / "model.joblib")
    changelog = str(tmp_path / "MODEL_CHANGELOG.md")
    monkeypatch.setattr(pipeline_module, "MODEL_STAGING_PATH", staging)
    monkeypatch.setattr(pipeline_module, "MODEL_PATH", live)
    monkeypatch.setattr(pipeline_module, "MODEL_CHANGELOG_PATH", changelog)
    return staging, live, changelog


def test_staged_model_does_not_overwrite_live_model_immediately(tmp_path, monkeypatch):
    staging, live, _ = _patch_paths(monkeypatch, tmp_path)

    joblib.dump({"model": _DummyModel(1.0), "r2": 0.5, "timestamp": "t0", "hpo_used": False}, live)
    joblib.dump({"model": _DummyModel(0.0), "r2": 0.9, "timestamp": "t1", "hpo_used": False}, staging)

    live_mtime_before = os.path.getmtime(live)
    evaluation = evaluate_staged_model(city="Riyadh")

    assert evaluation["recommendation"] in ("promote", "reject")
    assert os.path.getmtime(live) == live_mtime_before  # evaluation must never write


def test_promote_rejects_when_staged_mae_is_worse(tmp_path, monkeypatch):
    staging, live, _ = _patch_paths(monkeypatch, tmp_path)

    from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features
    from src.model import prepare_features

    df = generate_traffic_data(city="Riyadh", n_days=10)
    df = apply_hourly_patterns(df, city="Riyadh")
    df = add_lag_features(df)
    _, y_true, _ = prepare_features(df)
    true_mean = float(y_true.mean())

    joblib.dump({"model": _DummyModel(true_mean), "r2": 0.9, "timestamp": "t0", "hpo_used": False}, live)
    joblib.dump({"model": _DummyModel(true_mean + 0.9), "r2": 0.1, "timestamp": "t1", "hpo_used": False}, staging)

    evaluation = evaluate_staged_model(city="Riyadh")
    assert evaluation["regression"] is True
    assert evaluation["recommendation"] == "reject"

    with pytest.raises(ValueError):
        promote_staged_model(city="Riyadh", drift_score=1.4, evaluation=evaluation)

    assert joblib.load(live)["timestamp"] == "t0"  # untouched


def test_changelog_entry_created_on_promotion(tmp_path, monkeypatch):
    staging, live, changelog = _patch_paths(monkeypatch, tmp_path)

    joblib.dump({"model": _DummyModel(0.3), "r2": 0.8, "timestamp": "t1", "hpo_used": False}, staging)

    evaluation = evaluate_staged_model(city="Riyadh")
    assert evaluation["recommendation"] == "promote"  # no live model yet

    result = promote_staged_model(city="Riyadh", drift_score=1.4, evaluation=evaluation)
    assert result["promoted"] is True
    assert os.path.exists(live)
    assert os.path.exists(changelog)

    content = open(changelog, encoding="utf-8").read()
    assert "Model Changelog" in content
    assert "Riyadh" in content
    assert "promoted" in content




# ===== Optuna HPO staging-gate verification =====

def test_optuna_hpo_writes_to_staging_not_live_path(tmp_path, monkeypatch):
    """run_hpo=True must write only to the staging slot, identical to the
    non-HPO path — confirms there is no second write path to model.joblib."""
    staging, live, _ = _patch_paths(monkeypatch, tmp_path)

    joblib.dump({"model": _DummyModel(0.5), "r2": 0.5, "timestamp": "t0", "hpo_used": False}, live)
    live_mtime_before = os.path.getmtime(live)

    def fake_optimize(X, y):
        return {
            "best_params": {"n_estimators": 100, "max_depth": 3,
                             "learning_rate": 0.1, "subsample": 0.8},
            "best_cv_mae": 0.05, "n_trials_run": 1, "study_name": "fake_study",
        }
    monkeypatch.setattr("src.model.optimize_hyperparameters", fake_optimize)

    from src.pipeline import retrain_model
    result = retrain_model(city="Riyadh", run_hpo=True)

    assert result["hpo_used"] is True
    assert result["model_path"] == staging
    assert os.path.exists(staging)
    assert os.path.getmtime(live) == live_mtime_before, (
        "HPO retrain must never write directly to the live model path"
    )


def test_optuna_promotion_requires_evaluate_staged_model_approval(tmp_path, monkeypatch):
    """An HPO-sourced staged model that regresses must be rejected by the
    same gate as a non-HPO model — HPO origin grants no bypass."""
    staging, live, _ = _patch_paths(monkeypatch, tmp_path)

    from src.data import generate_traffic_data, apply_hourly_patterns, add_lag_features
    from src.model import prepare_features

    df = generate_traffic_data(city="Riyadh", n_days=10)
    df = apply_hourly_patterns(df, city="Riyadh")
    df = add_lag_features(df)
    _, y_true, _ = prepare_features(df)
    true_mean = float(y_true.mean())

    joblib.dump({"model": _DummyModel(true_mean), "r2": 0.9,
                 "timestamp": "t0", "hpo_used": False}, live)
    joblib.dump({"model": _DummyModel(true_mean + 0.9), "r2": 0.1,
                 "timestamp": "t1", "hpo_used": True}, staging)

    evaluation = evaluate_staged_model(city="Riyadh")
    assert evaluation["recommendation"] == "reject"

    with pytest.raises(ValueError):
        promote_staged_model(city="Riyadh", drift_score=1.6, evaluation=evaluation)

    assert joblib.load(live)["timestamp"] == "t0"





from unittest.mock import patch, MagicMock
import pytest
import pandas as pd
from src.pipeline import check_incident_alerts
from src.config import ALERT_THRESHOLDS


def test_incident_alert_fires_on_moderate_severity():
    """
    Moderate severity incidents must generate alerts.
    """
    mock_df = pd.DataFrame({
        "zone": ["Zone_1", "Zone_1"],
        "weather": ["Clear", "Clear"],
        "road_type": ["urban", "urban"],
        "vehicle_count": [100, 50],
        "avg_speed": [60, 30],
        "hour": [8, 8],
    })

    # Patch where detect_incidents is actually defined: src.model
    with patch("src.model.detect_incidents") as mock_detect, \
         patch("src.model.estimate_incident_clearance_time") as mock_clearance:

        mock_detect.return_value = {
            "incident_detected": True,
            "severity": "Moderate",
            "speed_drop_pct": 0.45,
            "volume_change_pct": -0.35,
            "confidence": "High",
            "recommended_action": "Dispatch roadside assistance; monitor",
        }
        mock_clearance.return_value = 30

        alerts = check_incident_alerts(mock_df, city="Riyadh")

        assert len(alerts) == 1
        assert alerts[0]["severity"] == "Moderate"
        assert alerts[0]["alert_type"] == "incident"
        assert alerts[0]["estimated_clearance_mins"] == 30
        assert alerts[0]["city"] == "Riyadh"
        assert alerts[0]["zone"] == "Zone_1"


def test_incident_alert_suppressed_for_minor_severity():
    """
    Minor incidents must be detected but not elevated to alerts.
    """
    mock_df = pd.DataFrame({
        "zone": ["Zone_1", "Zone_1"],
        "weather": ["Clear", "Clear"],
        "road_type": ["urban", "urban"],
        "vehicle_count": [100, 90],
        "avg_speed": [60, 50],
        "hour": [8, 8],
    })

    with patch("src.model.detect_incidents") as mock_detect:

        mock_detect.return_value = {
            "incident_detected": True,
            "severity": "Minor",
            "speed_drop_pct": 0.25,
            "volume_change_pct": -0.15,
            "confidence": "Medium",
            "recommended_action": "Monitor situation",
        }

        alerts = check_incident_alerts(mock_df, city="Riyadh")

        assert len(alerts) == 0


def test_incident_alert_included_in_webhook_payload():
    """
    Verify that check_incident_alerts returns proper structure that can be
    combined with congestion alerts into a unified payload.
    """
    from src.pipeline import check_incident_alerts, check_thresholds

    # Mock DataFrame with timestamp column (required by detect_anomalies)
    mock_df = pd.DataFrame({
        "zone": ["Zone_1", "Zone_1"],
        "timestamp": pd.to_datetime(["2024-01-01 08:00", "2024-01-01 09:00"]),
        "weather": ["Clear", "Clear"],
        "road_type": ["urban", "urban"],
        "vehicle_count": [100, 50],
        "avg_speed": [60, 30],
        "hour": [8, 9],
        "congestion_score": [0.3, 0.5],
    })

    with patch("src.model.detect_incidents") as mock_detect, \
         patch("src.model.estimate_incident_clearance_time") as mock_clearance:

        mock_detect.return_value = {
            "incident_detected": True,
            "severity": "Major",
            "speed_drop_pct": 0.55,
            "volume_change_pct": -0.40,
            "confidence": "High",
            "recommended_action": "Close lane 2",
        }
        mock_clearance.return_value = 45

        incident_alerts = check_incident_alerts(mock_df, city="Riyadh")

        # Verify structure matches what _scheduled_alerts expects
        assert len(incident_alerts) == 1
        assert incident_alerts[0]["alert_type"] == "incident"
        assert incident_alerts[0]["severity"] == "Major"

        # Simulate payload construction (same as _scheduled_alerts)
        payload = {
            "congestion_alerts": [],  # No congestion alerts in this test
            "incident_alerts": incident_alerts,
        }

        assert "incident_alerts" in payload
        assert len(payload["incident_alerts"]) == 1
        assert payload["incident_alerts"][0]["severity"] == "Major"
        assert len(payload["congestion_alerts"]) == 0







# =====  Calibration Trigger Tests =====

import json

def test_pipeline_triggers_calibration_when_score_below_threshold(tmp_path, monkeypatch):
    """calibration_triggered=True when calibration_score < threshold and retrain fires."""
    staging, live, changelog = _patch_paths(monkeypatch, tmp_path)

    # Write a calibration_factors.json with low score
    cal_path = tmp_path / "calibration_factors.json"
    cal_data = {
        "factors": {"Zone_1": {"8": 1.10}},
        "computed_at": "2026-01-01T00:00:00",
        "zones": 1,
        "total_entries": 1,
        "metrics": {
            "mae": 10.0, "mape": 5.0, "r2": 0.5,
            "calibration_score": 0.05,   # below CALIBRATION_DRIFT_THRESHOLD=0.15
            "coverage_pct": 100.0, "matched_rows": 1,
        },
        "city": "Riyadh",
    }
    cal_path.write_text(json.dumps(cal_data))
    monkeypatch.setattr(pipeline_module, "MODEL_CHANGELOG_PATH", str(tmp_path / "MODEL_CHANGELOG.md"))

    import src.config as cfg_module
    original_path = cfg_module.CALIBRATION_FACTORS_PATH
    monkeypatch.setattr(cfg_module, "CALIBRATION_FACTORS_PATH", str(cal_path))

    # Force retrain to trigger: monkeypatch should_retrain to always return True
    monkeypatch.setattr(pipeline_module, "should_retrain", lambda score, threshold=1.3: True)
    # Also monkeypatch compute_drift_score so no CSV read needed
    monkeypatch.setattr(pipeline_module, "compute_drift_score", lambda log_path="predictions_log.csv": 1.5)

    result = pipeline_module.run_pipeline(city="Riyadh")
    assert result["calibration_triggered"] is True


def test_pipeline_skips_calibration_when_no_real_data_present(tmp_path, monkeypatch):
    """calibration_triggered=False and no exception when calibration_factors.json is absent."""
    staging, live, changelog = _patch_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline_module, "MODEL_CHANGELOG_PATH", str(tmp_path / "MODEL_CHANGELOG.md"))

    import src.config as cfg_module
    absent_path = str(tmp_path / "calibration_factors_absent.json")  # does not exist
    monkeypatch.setattr(cfg_module, "CALIBRATION_FACTORS_PATH", absent_path)

    # Don't trigger retrain — just check that the field is present and False
    monkeypatch.setattr(pipeline_module, "should_retrain", lambda score, threshold=1.3: False)
    monkeypatch.setattr(pipeline_module, "compute_drift_score", lambda log_path="predictions_log.csv": 1.0)

    result = pipeline_module.run_pipeline(city="Riyadh")
    assert result["calibration_triggered"] is False
    assert "calibration_triggered" in result


def test_calibration_trigger_logged_in_model_changelog(tmp_path, monkeypatch):
    """MODEL_CHANGELOG.md contains a calibration note after a triggered run."""
    staging, live, changelog = _patch_paths(monkeypatch, tmp_path)

    cal_path = tmp_path / "calibration_factors.json"
    cal_data = {
        "factors": {},
        "computed_at": "2026-01-01T00:00:00",
        "zones": 0,
        "total_entries": 0,
        "metrics": {
            "mae": 20.0, "mape": 10.0, "r2": 0.3,
            "calibration_score": 0.08,
            "coverage_pct": 0.0, "matched_rows": 0,
        },
        "city": "Riyadh",
    }
    cal_path.write_text(json.dumps(cal_data))

    import src.config as cfg_module
    monkeypatch.setattr(cfg_module, "CALIBRATION_FACTORS_PATH", str(cal_path))
    monkeypatch.setattr(pipeline_module, "MODEL_CHANGELOG_PATH", changelog)
    monkeypatch.setattr(pipeline_module, "should_retrain", lambda score, threshold=1.3: True)
    monkeypatch.setattr(pipeline_module, "compute_drift_score", lambda log_path="predictions_log.csv": 1.5)

    pipeline_module.run_pipeline(city="Riyadh")

    assert os.path.exists(changelog)
    content = open(changelog, encoding="utf-8").read()
    assert "calibration" in content.lower()