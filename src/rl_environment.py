"""
Reinforcement Learning environment wrapper.

Wraps the SUMO microsimulation as an OpenAI Gymnasium-compatible
environment for training RL signal control agents.

The environment is simulation-only. Real actuation requires the NTCIP
interface.

When SUMO is unavailable, a synthetic queue-dynamics model is used so
the environment remains fully functional for training and testing.
"""
import os
import sys
import random
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
    _GYM_ENGINE = "gymnasium"
except ImportError:
    try:
        import gym
        from gym import spaces
        _GYM_ENGINE = "gym"
    except ImportError:
        gym = None
        spaces = None
        _GYM_ENGINE = None

if gym is not None:
    _BaseEnv = gym.Env
else:
    _BaseEnv = object

def _step_result(obs, reward, terminated, truncated, info):
    """Normalize step() output to a 5-tuple regardless of gym vs gymnasium."""
    return (obs, reward, terminated, truncated, info)


def _reset_result(obs, info):
    """Normalize reset() output to a (obs, info) 2-tuple."""
    return (obs, info)


class RiyadhTrafficEnv(_BaseEnv):
    """
    Gymnasium-compatible RL environment for Riyadh signal control.

    Observation (21-dim Box, all values in [0, 1]):
      - queue_lengths[5]        normalized queue per zone
      - avg_speeds[5]           speed / RL_SPEED_NORMALIZATION_KMPH
      - congestion_scores[5]    already in [0, 1]
      - hour_normalized         hour / 23
      - is_weekend              0 or 1
      - is_prayer               0 or 1
      - is_sandstorm            0 or 1
      - is_hajj                 0 or 1
      - is_peak_hour            0 or 1

    Action (Discrete(11)):
      0        = hold
      1 to 5   = extend green in Zone_1 .. Zone_5
      6 to 10  = reduce green in Zone_1 .. Zone_5

    Reward:
      -mean(queue_normalized) - 0.5 * mean(congestion_score)
      + RL_THROUGHPUT_BONUS_WEIGHT * throughput_proxy
      - RL_ILLEGAL_ACTION_PENALTY if action was converted to hold

    Safety:
      - Extend/reduce actions are clamped to [RL_MIN_GREEN_SECONDS, RL_MAX_GREEN_SECONDS]
      - An extend at max, or reduce at min, is converted to hold and penalised
    """

    metadata = {"render_modes": []}

    def __init__(self, use_sumo: Optional[bool] = None, seed: Optional[int] = None):
        if gym is None or spaces is None:
            raise ImportError(
                "RiyadhTrafficEnv requires 'gymnasium' or 'gym'. "
                "Install with: pip install gymnasium"
            )

        from src.config import (
            RL_NUM_ZONES,
            RL_EPISODE_LENGTH_STEPS,
            RL_GREEN_STEP_SECONDS,
            RL_MIN_GREEN_SECONDS,
            RL_MAX_GREEN_SECONDS,
            RL_INITIAL_GREEN_SECONDS,
            RL_QUEUE_NORMALIZATION,
            RL_SPEED_NORMALIZATION_KMPH,
            RL_ILLEGAL_ACTION_PENALTY,
            RL_THROUGHPUT_BONUS_WEIGHT,
            RL_PRAYER_HOURS,
            RL_PEAK_HOURS,
        )

        self.num_zones = RL_NUM_ZONES
        self.episode_length = RL_EPISODE_LENGTH_STEPS
        self.green_step = RL_GREEN_STEP_SECONDS
        self.min_green = RL_MIN_GREEN_SECONDS
        self.max_green = RL_MAX_GREEN_SECONDS
        self.initial_green = RL_INITIAL_GREEN_SECONDS
        self.queue_norm = RL_QUEUE_NORMALIZATION
        self.speed_norm = RL_SPEED_NORMALIZATION_KMPH
        self.illegal_penalty = RL_ILLEGAL_ACTION_PENALTY
        self.throughput_weight = RL_THROUGHPUT_BONUS_WEIGHT
        self.prayer_hours = set(RL_PRAYER_HOURS)
        self.peak_hours = set(RL_PEAK_HOURS)

        self.use_sumo = self._resolve_sumo(use_sumo)
        self.sumo = None
        if self.use_sumo:
            try:
                from src.sumo_adapter import SUMOAdapter
                self.sumo = SUMOAdapter()
                if not self.sumo.is_available():
                    self.use_sumo = False
                    self.sumo = None
            except Exception:
                self.use_sumo = False
                self.sumo = None

        obs_dim = self.num_zones * 3 + 6
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(obs_dim,), dtype=np.float32,
        )
        self.action_space = spaces.Discrete(1 + self.num_zones * 2)

        self.zone_names = [f"Zone_{i+1}" for i in range(self.num_zones)]
        self._rng = random.Random(seed)
        self._np_rng = np.random.default_rng(seed)

        self.green_durations: Dict[str, int] = {}
        self.step_count = 0
        self._mock_queues: np.ndarray = np.zeros(self.num_zones, dtype=np.float32)
        self._mock_speeds: np.ndarray = np.zeros(self.num_zones, dtype=np.float32)
        self._mock_congestion: np.ndarray = np.zeros(self.num_zones, dtype=np.float32)
        self._hour: int = 8
        self._is_weekend: int = 0
        self._is_sandstorm: int = 0
        self._is_hajj: int = 0
        self._is_prayer: int = 0
        self._is_peak: int = 0

    def _resolve_sumo(self, use_sumo: Optional[bool]) -> bool:
        """Decide whether to use SUMO or the synthetic fallback."""
        if use_sumo is False:
            return False
        try:
            from src.sumo_adapter import SUMOAdapter
            if use_sumo is True:
                return True
            return SUMOAdapter().is_available()
        except Exception:
            return False

    def reset(self, seed: Optional[int] = None, options: Optional[dict] = None):
        """Reset environment to a Saudi-calibrated starting state."""
        if seed is not None:
            self._rng.seed(seed)
            self._np_rng = np.random.default_rng(seed)

        self.step_count = 0
        self.green_durations = {z: self.initial_green for z in self.zone_names}

        scenario = self._pick_scenario()
        self._hour = scenario["hour"]
        self._is_weekend = scenario["is_weekend"]
        self._is_sandstorm = scenario["is_sandstorm"]
        self._is_hajj = scenario["is_hajj"]
        self._is_prayer = scenario["is_prayer"]
        self._is_peak = scenario["is_peak"]

        base_queue = self._np_rng.uniform(0.10, 0.35, size=self.num_zones)
        if self._is_sandstorm:
            base_queue += 0.15
        if self._is_hajj:
            base_queue += 0.10
        if self._is_peak:
            base_queue += 0.10
        self._mock_queues = np.clip(base_queue, 0.0, 1.0).astype(np.float32)

        base_speed = 1.0 - self._mock_queues * 0.6
        self._mock_speeds = np.clip(base_speed, 0.1, 1.0).astype(np.float32)
        self._mock_congestion = np.clip(self._mock_queues * 0.9, 0.0, 1.0).astype(np.float32)

        obs = self._build_observation()
        info = {
            "engine": "sumo" if self.use_sumo else "synthetic",
            "scenario": scenario,
        }
        return _reset_result(obs, info)

    def _pick_scenario(self) -> Dict[str, Any]:
        """Randomly choose a Saudi-calibrated scenario."""
        hour = self._rng.choice([6, 7, 8, 9, 12, 13, 14, 17, 18, 19, 21, 22])
        is_weekend = 1 if self._rng.random() < 0.30 else 0
        is_sandstorm = 1 if self._rng.random() < 0.15 else 0
        is_hajj = 1 if self._rng.random() < 0.10 else 0
        is_prayer = 1 if (hour in self.prayer_hours and is_weekend) else 0
        is_peak = 1 if hour in self.peak_hours else 0
        return {
            "hour": int(hour),
            "is_weekend": is_weekend,
            "is_sandstorm": is_sandstorm,
            "is_hajj": is_hajj,
            "is_prayer": is_prayer,
            "is_peak": is_peak,
        }

    def _build_observation(self) -> np.ndarray:
        """Assemble the observation vector."""
        queues = self._mock_queues.astype(np.float32)
        speeds = self._mock_speeds.astype(np.float32)
        congestion = self._mock_congestion.astype(np.float32)

        hour_norm = np.float32(self._hour / 23.0)
        extras = np.array([
            float(self._is_weekend),
            float(self._is_prayer),
            float(self._is_sandstorm),
            float(self._is_hajj),
            float(self._is_peak),
        ], dtype=np.float32)

        obs = np.concatenate([queues, speeds, congestion, [hour_norm], extras])
        return np.clip(obs, 0.0, 1.0).astype(np.float32)

    def _apply_action(self, action: int) -> Tuple[bool, Optional[str]]:
        """
        Apply an action to the green durations dict.

        Returns (was_illegal, illegal_reason).
        """
        if action == 0:
            return False, None

        if 1 <= action <= self.num_zones:
            zone = self.zone_names[action - 1]
            current = self.green_durations[zone]
            proposed = current + self.green_step
            if proposed > self.max_green:
                return True, f"extend beyond max_green on {zone}"
            self.green_durations[zone] = proposed
            return False, None

        if self.num_zones + 1 <= action <= self.num_zones * 2:
            zone = self.zone_names[action - self.num_zones - 1]
            current = self.green_durations[zone]
            proposed = current - self.green_step
            if proposed < self.min_green:
                return True, f"reduce below min_green on {zone}"
            self.green_durations[zone] = proposed
            return False, None

        return True, "unknown action index"

    def _advance_simulation(self, illegal: bool) -> Tuple[float, float]:
        """
        Advance the synthetic queue model by one step.

        Returns (throughput_proxy, reward_components_summary) as floats.
        """
        green_ratios = np.array([
            self.green_durations[z] / max(self.max_green, 1)
            for z in self.zone_names
        ], dtype=np.float32)

        demand_growth = np.full(self.num_zones, 0.04, dtype=np.float32)
        if self._is_peak:
            demand_growth += 0.02
        if self._is_sandstorm:
            demand_growth += 0.01

        drain = green_ratios * 0.10

        self._mock_queues = np.clip(self._mock_queues + demand_growth - drain, 0.0, 1.0)
        self._mock_congestion = np.clip(self._mock_queues * 0.9, 0.0, 1.0)
        speed_target = 1.0 - self._mock_queues * 0.6
        if self._is_sandstorm:
            speed_target = speed_target * 0.6
        self._mock_speeds = np.clip(
            0.7 * self._mock_speeds + 0.3 * speed_target, 0.05, 1.0
        ).astype(np.float32)

        throughput_proxy = float(np.mean(green_ratios) * (1.0 - float(np.mean(self._mock_queues))))
        return throughput_proxy, 0.0

    def step(self, action: int):
        """Run one environment step."""
        if not self.action_space.contains(action):
            raise ValueError(f"Action {action} not in action_space.")

        illegal, reason = self._apply_action(int(action))
        throughput_proxy, _ = self._advance_simulation(illegal)

        mean_queue = float(np.mean(self._mock_queues))
        mean_congestion = float(np.mean(self._mock_congestion))

        reward = -mean_queue - 0.5 * mean_congestion
        reward += self.throughput_weight * throughput_proxy
        if illegal:
            reward -= self.illegal_penalty

        self.step_count += 1
        terminated = False
        truncated = self.step_count >= self.episode_length

        obs = self._build_observation()
        info = {
            "step": self.step_count,
            "mean_queue": round(mean_queue, 4),
            "mean_congestion": round(mean_congestion, 4),
            "throughput_proxy": round(throughput_proxy, 4),
            "illegal_action": illegal,
            "illegal_reason": reason,
            "green_durations": dict(self.green_durations),
        }
        return _step_result(obs, float(reward), terminated, truncated, info)

    def render(self, mode: str = "human"):
        """Rendering is not implemented — the environment is headless."""
        return None

    def close(self):
        """Release resources."""
        if self.sumo is not None:
            try:
                self.sumo = None
            except Exception:
                pass


def _run_cli_test() -> None:
    """Run a short random-action sanity check on the environment."""
    env = RiyadhTrafficEnv(use_sumo=False, seed=0)
    obs, info = env.reset(seed=0)
    print(f"Reset OK. Engine: {info['engine']}  obs_dim: {obs.shape[0]}")
    total_reward = 0.0
    for i in range(10):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        print(
            f"Step {i+1}: action={action}  reward={reward:.4f}  "
            f"mean_queue={info['mean_queue']:.3f}  illegal={info['illegal_action']}"
        )
        if terminated or truncated:
            obs, info = env.reset()
    print(f"10 random steps complete. Total reward: {total_reward:.4f}")
    env.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RiyadhTrafficEnv CLI")
    parser.add_argument("--test-env", action="store_true", help="Run 10 random steps")
    args = parser.parse_args()
    if args.test_env:
        _run_cli_test()
    else:
        parser.print_help()