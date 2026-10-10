import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")
TEST_KEY = os.environ["API_KEY"]

import pytest
from fastapi.testclient import TestClient
from app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def trained_model(tmp_path_factory):
    """
    Train a very short PPO model once for the whole test module.
    Uses n_timesteps=1000 so tests stay fast.
    """
    os.environ["RL_PPO_MODEL_DIR"] = str(
        tmp_path_factory.mktemp("rl_models") / "ppo_test"
    )
    from src.rl_agent import train_ppo_agent
    import src.config as cfg
    cfg.RL_PPO_MODEL_DIR = os.environ["RL_PPO_MODEL_DIR"]
    path = train_ppo_agent(n_timesteps=1000, save_path=os.environ["RL_PPO_MODEL_DIR"])
    assert os.path.exists(path + ".zip")
    return path


def test_ppo_agent_trains_without_error(trained_model):
    """Trainer must produce a .zip model file."""
    assert os.path.exists(trained_model + ".zip")


def test_evaluation_returns_improvement_pct(trained_model):
    """evaluate_rl_agent must return both metrics and an improvement number."""
    from src.rl_agent import evaluate_rl_agent
    result = evaluate_rl_agent(agent_path=trained_model, n_episodes=3)
    assert "ppo" in result
    assert "heuristic" in result
    assert "improvement_pct" in result
    assert isinstance(result["improvement_pct"], float)
    assert result["n_episodes"] == 3
    assert "mean_total_reward" in result["ppo"]
    assert "mean_total_reward" in result["heuristic"]


def test_rl_recommendation_gated_by_actuation_flag(trained_model):
    """RL recommendation must include the experimental and gating flags."""
    from src.rl_agent import rl_recommend_timing
    import src.config as cfg
    cfg.RL_PPO_MODEL_DIR = trained_model

    result = rl_recommend_timing(zone="Zone_1", city="Riyadh")
    assert result["experimental"] is True
    assert result["model_loaded"] is True
    assert "actuation_permitted" in result
    # ACTUATION_ENABLED defaults to False
    assert result["actuation_permitted"] is False


def test_agent_performance_endpoint_returns_status(client):
    response = client.get(
        "/rl/agent-performance",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "no_evaluation")


def test_recommend_timing_endpoint(client):
    response = client.post(
        "/rl/recommend-timing/Zone_1?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["zone"] == "Zone_1"
    assert data["experimental"] is True
    assert "actuation_permitted" in data