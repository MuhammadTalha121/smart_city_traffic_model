"""
Deep RL signal control agent .

Trains a PPO agent on the RiyadhTrafficEnv  and evaluates
it against a heuristic baseline. This is an EXPERIMENTAL model — the
RL recommendation is never actuated unless ACTUATION_ENABLED is True.

Dependencies:
    stable-baselines3 >= 2.0
    gymnasium >= 0.29
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import CheckpointCallback
    _SB3_AVAILABLE = True
except ImportError:
    PPO = None
    CheckpointCallback = None
    _SB3_AVAILABLE = False

from src.rl_environment import RiyadhTrafficEnv


RL_PERFORMANCE_PATH = "rl_performance.json"


def _require_sb3() -> None:
    if not _SB3_AVAILABLE:
        raise ImportError(
            "stable-baselines3 is required for RL training. "
            "Install with: pip install stable-baselines3"
        )


def train_ppo_agent(
    n_timesteps: Optional[int] = None,
    save_path: Optional[str] = None,
    seed: int = 42,
) -> str:
    """
    Train a PPO agent on RiyadhTrafficEnv.

    Parameters
    ----------
    n_timesteps : int, optional
        Total environment steps. Defaults to RL_PPO_DEFAULT_TIMESTEPS.
    save_path : str, optional
        Where to save the final model. Defaults to RL_PPO_MODEL_DIR.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    str
        Path to the saved model (without extension).
    """
    _require_sb3()
    from src.config import (
        RL_PPO_DEFAULT_TIMESTEPS,
        RL_PPO_CHECKPOINT_FREQ,
        RL_PPO_LEARNING_RATE,
        RL_PPO_N_STEPS,
        RL_PPO_BATCH_SIZE,
        RL_PPO_N_EPOCHS,
        RL_PPO_GAMMA,
        RL_PPO_MODEL_DIR,
    )

    n_timesteps = n_timesteps or RL_PPO_DEFAULT_TIMESTEPS
    save_path = save_path or RL_PPO_MODEL_DIR

    os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
    os.makedirs("rl_checkpoints", exist_ok=True)

    env = RiyadhTrafficEnv(use_sumo=False, seed=seed)

    model = PPO(
        policy="MlpPolicy",
        env=env,
        learning_rate=RL_PPO_LEARNING_RATE,
        n_steps=RL_PPO_N_STEPS,
        batch_size=RL_PPO_BATCH_SIZE,
        n_epochs=RL_PPO_N_EPOCHS,
        gamma=RL_PPO_GAMMA,
        verbose=0,
        seed=seed,
    )

    checkpoint_cb = CheckpointCallback(
        save_freq=RL_PPO_CHECKPOINT_FREQ,
        save_path="rl_checkpoints",
        name_prefix="ppo_signal_agent",
    )

    model.learn(total_timesteps=n_timesteps, callback=checkpoint_cb)
    model.save(save_path)
    env.close()

    return save_path


def _heuristic_policy(obs: np.ndarray, num_zones: int = 5) -> int:
    """
    A simple rule-based policy for baseline comparison.

    Extends green on the zone with the highest queue. If no zone is
    above 0.3, holds. This mirrors the spirit of PROMPT 107's
    adaptive timing without the full simulation.
    """
    queues = obs[:num_zones]
    worst = int(np.argmax(queues))
    if queues[worst] > 0.30:
        return 1 + worst  # extend green
    return 0  # hold


def evaluate_rl_agent(
    agent_path: Optional[str] = None,
    n_episodes: Optional[int] = None,
    seed: int = 123,
) -> Dict:
    """
    Evaluate PPO vs a heuristic policy on the same environment.

    Parameters
    ----------
    agent_path : str, optional
        Path to the saved PPO model. Defaults to RL_PPO_MODEL_DIR.
    n_episodes : int, optional
        Number of evaluation episodes per policy. Defaults to
        RL_EVAL_EPISODES.
    seed : int
        Base seed for evaluation scenarios.

    Returns
    -------
    dict
        {
            "ppo": {...metrics...},
            "heuristic": {...metrics...},
            "improvement_pct": float,
            "evaluated_at": str,
            "n_episodes": int,
        }
    """
    _require_sb3()
    from src.config import RL_PPO_MODEL_DIR, RL_EVAL_EPISODES

    agent_path = agent_path or RL_PPO_MODEL_DIR
    n_episodes = n_episodes or RL_EVAL_EPISODES

    env_ppo = RiyadhTrafficEnv(use_sumo=False, seed=seed)
    env_heur = RiyadhTrafficEnv(use_sumo=False, seed=seed)

    model = PPO.load(agent_path, env=env_ppo)

    def _run_episode(env, policy_fn) -> Dict:
        obs, _ = env.reset()
        total_reward = 0.0
        total_queue = 0.0
        steps = 0
        done = False
        while not done:
            action = policy_fn(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward
            total_queue += info.get("mean_queue", 0.0)
            steps += 1
            done = terminated or truncated
        return {
            "total_reward": total_reward,
            "mean_queue": total_queue / max(steps, 1),
            "steps": steps,
        }

    ppo_results = []
    heur_results = []

    for i in range(n_episodes):
        obs, _ = env_ppo.reset(seed=seed + i)
        def ppo_policy(o, _model=model):
            action, _ = _model.predict(o, deterministic=True)
            return int(action)
        ppo_results.append(_run_episode(env_ppo, ppo_policy))

        obs, _ = env_heur.reset(seed=seed + i)
        heur_results.append(_run_episode(env_heur, _heuristic_policy))

    env_ppo.close()
    env_heur.close()

    def _aggregate(results: List[Dict]) -> Dict:
        rewards = [r["total_reward"] for r in results]
        queues = [r["mean_queue"] for r in results]
        return {
            "mean_total_reward": round(float(np.mean(rewards)), 4),
            "std_total_reward": round(float(np.std(rewards)), 4),
            "mean_queue": round(float(np.mean(queues)), 4),
            "n_episodes": len(results),
        }

    ppo_agg = _aggregate(ppo_results)
    heur_agg = _aggregate(heur_results)

    reward_ppo = ppo_agg["mean_total_reward"]
    reward_heur = heur_agg["mean_total_reward"]
    if abs(reward_heur) > 1e-6:
        improvement_pct = round((reward_ppo - reward_heur) / abs(reward_heur) * 100, 2)
    else:
        improvement_pct = 0.0

    result = {
        "ppo": ppo_agg,
        "heuristic": heur_agg,
        "improvement_pct": improvement_pct,
        "n_episodes": n_episodes,
        "evaluated_at": datetime.now().isoformat(),
    }

    with open(RL_PERFORMANCE_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


def load_latest_performance() -> Optional[Dict]:
    """Load the last saved performance report, if any."""
    if not os.path.exists(RL_PERFORMANCE_PATH):
        return None
    try:
        with open(RL_PERFORMANCE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return None


def rl_recommend_timing(zone: str, city: str = "Riyadh") -> Dict:
    """
    Use the trained PPO agent to recommend a signal timing action for a zone.

    This is a recommendation only — the returned dict includes an
    'experimental' flag, and actuation requires ACTUATION_ENABLED=True
    through the PROMPT 121 interface.

    Parameters
    ----------
    zone : str
    city : str

    Returns
    -------
    dict
        {
            "zone": str,
            "city": str,
            "action": int,
            "action_label": str,
            "experimental": True,
            "actuation_permitted": bool,
            "model_loaded": bool,
        }
    """
    _require_sb3()
    from src.config import RL_PPO_MODEL_DIR, ACTUATION_ENABLED, RL_NUM_ZONES

    model_path = RL_PPO_MODEL_DIR
    zip_path = model_path + ".zip"
    if not os.path.exists(zip_path):
        return {
            "zone": zone,
            "city": city,
            "action": None,
            "action_label": "no_model",
            "experimental": True,
            "actuation_permitted": False,
            "model_loaded": False,
        }

    env = RiyadhTrafficEnv(use_sumo=False, seed=0)
    model = PPO.load(model_path, env=env)
    obs, _ = env.reset(seed=0)
    action, _ = model.predict(obs, deterministic=True)
    action = int(action)
    env.close()

    if action == 0:
        label = "hold"
    elif 1 <= action <= RL_NUM_ZONES:
        label = f"extend_green_{zone if action == ZONE_INDEX_MAP.get(zone, -1) + 1 else f'zone_{action}'}"
    else:
        label = f"reduce_green_zone_{action - RL_NUM_ZONES}"

    return {
        "zone": zone,
        "city": city,
        "action": action,
        "action_label": label,
        "experimental": True,
        "actuation_permitted": bool(ACTUATION_ENABLED),
        "model_loaded": True,
    }


ZONE_INDEX_MAP = {
    "Zone_1": 0,
    "Zone_2": 1,
    "Zone_3": 2,
    "Zone_4": 3,
    "Zone_5": 4,
}