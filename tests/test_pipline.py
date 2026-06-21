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