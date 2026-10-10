import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")

import pytest
import numpy as np


@pytest.fixture(scope="module")
def env():
    from src.rl_environment import RiyadhTrafficEnv
    e = RiyadhTrafficEnv(use_sumo=False, seed=42)
    yield e
    e.close()


def test_env_step_returns_correct_types(env):
    """step() must return (obs, reward, terminated, truncated, info)."""
    obs, info = env.reset(seed=0)
    assert isinstance(obs, np.ndarray)
    assert obs.shape == env.observation_space.shape
    assert obs.dtype == np.float32

    action = env.action_space.sample()
    result = env.step(action)
    assert len(result) == 5, "step() must return a 5-tuple"

    obs2, reward, terminated, truncated, info = result
    assert isinstance(obs2, np.ndarray)
    assert obs2.shape == env.observation_space.shape
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(info, dict)


def test_env_reset_produces_valid_observation(env):
    """reset() must return an observation inside the observation_space."""
    obs, info = env.reset(seed=123)
    assert isinstance(obs, np.ndarray)
    assert env.observation_space.contains(obs), "Observation is outside the declared space"
    assert "engine" in info
    assert "scenario" in info
    assert info["scenario"]["hour"] >= 0
    assert info["scenario"]["hour"] <= 23


def test_observation_includes_saudi_context_flags(env):
    """
    The observation must include the Saudi context flags at the end:
    is_weekend, is_prayer, is_sandstorm, is_hajj, is_peak, plus hour_normalized.
    """
    from src.config import RL_NUM_ZONES

    obs, _ = env.reset(seed=7)
    expected_dim = RL_NUM_ZONES * 3 + 6
    assert obs.shape[0] == expected_dim

    hour_norm = float(obs[-6])
    flags = obs[-5:]
    assert 0.0 <= hour_norm <= 1.0
    for f in flags:
        assert f in (0.0, 1.0), f"Expected binary flag, got {f}"


def test_env_episode_truncates_at_episode_length(env):
    """Running more than episode_length steps should trigger truncation."""
    from src.config import RL_EPISODE_LENGTH_STEPS
    env.reset(seed=1)
    truncated_any = False
    for _ in range(RL_EPISODE_LENGTH_STEPS + 5):
        action = env.action_space.sample()
        _, _, terminated, truncated, _ = env.step(action)
        if truncated:
            truncated_any = True
            break
    assert truncated_any, "Episode did not truncate after episode_length steps"


def test_illegal_action_is_penalised(env):
    """Extending beyond max_green must be flagged as illegal."""
    env.reset(seed=5)
    # Force Zone_1 to max_green
    for _ in range(20):
        obs, reward, terminated, truncated, info = env.step(1)  # extend Zone_1
        if info["illegal_action"]:
            assert "max_green" in info["illegal_reason"]
            return
        if terminated or truncated:
            env.reset(seed=5)
    pytest.fail("Never reached max_green state after 20 extends")


def test_step_returns_finite_reward(env):
    """Rewards must always be finite floats (no NaN, no inf)."""
    env.reset(seed=99)
    for _ in range(20):
        action = env.action_space.sample()
        _, reward, _, _, _ = env.step(action)
        assert isinstance(reward, float)
        assert not np.isnan(reward)
        assert not np.isinf(reward)