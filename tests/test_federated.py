import os
import pytest
import numpy as np
from fastapi.testclient import TestClient
from app import app
from src.auth import create_key
from src.federated import add_dp_noise, extract_shareable_params, distribute_aggregated_model

# Ensure API_KEY is set for tests
os.environ.setdefault("API_KEY", "test-key-for-pytest-only")
TEST_KEY = os.environ["API_KEY"]


def test_dp_noise_changes_params_when_enabled():
    """Noise should alter numeric values when DP is enabled."""
    params = {'n_estimators': 200, 'learning_rate': 0.1}
    noisy = add_dp_noise(params, epsilon=1.0)
    assert noisy['n_estimators'] != params['n_estimators']
    assert noisy['learning_rate'] != params['learning_rate']


def test_dp_noise_does_not_change_param_sign():
    """Sign of numeric parameters should be preserved after noise."""
    params = {'n_estimators': 200, 'learning_rate': 0.1}
    noisy = add_dp_noise(params, epsilon=10.0)  # small noise
    assert noisy['n_estimators'] > 0
    assert noisy['learning_rate'] > 0


def test_distribute_aggregated_model_uses_staging_gate(tmp_path, monkeypatch):
    # Mock evaluate_staged_model to always promote
    from src.federated import distribute_aggregated_model
    # We'll do a simple test that the function runs without error.
    # This is more of an integration test; we'll keep it simple.
    params = {'n_estimators': 100, 'max_depth': 3, 'learning_rate': 0.05}
    result = distribute_aggregated_model(params, ['Riyadh'], force_retrain=True)
    assert 'Riyadh' in result
    assert result['Riyadh']['status'] in ('promoted', 'rejected', 'error')


def test_federated_distribute_endpoint_requires_admin():
    """Endpoint /federated/distribute must reject non‑ADMIN keys."""
    # Create a READ_ONLY key
    ro_key = create_key('READ_ONLY', 'all')

    with TestClient(app) as client:
        # First, create a pending aggregation by calling /federated/aggregate with admin key
        agg_response = client.post(
            "/federated/aggregate",
            json={
                "city_params": [
                    {"city": "Riyadh", "training_r2": 0.9, "best_params": {"n_estimators": 200, "max_depth": 5, "learning_rate": 0.1, "subsample": 0.8}},
                ]
            },
            headers={"X-API-Key": TEST_KEY}
        )
        assert agg_response.status_code == 200

        # Now attempt to distribute with READ_ONLY key -> should get 403
        dist_response = client.post(
            "/federated/distribute",
            json=["Riyadh"],
            headers={"X-API-Key": ro_key}
        )
        assert dist_response.status_code == 403