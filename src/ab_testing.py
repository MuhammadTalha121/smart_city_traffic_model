"""
A/B testing framework for signal timing strategies (PROMPT 149).

Allows operators to run two strategies (A vs B) on parallel zone groups
and evaluate them objectively on congestion, throughput, and incident rate.
"""
import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

AB_TESTS_PATH = "ab_tests.json"


def _load_tests() -> Dict[str, dict]:
    """Load all A/B tests from disk."""
    if not os.path.exists(AB_TESTS_PATH):
        return {}
    try:
        with open(AB_TESTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


def _save_tests(tests: Dict[str, dict]) -> None:
    """Persist all A/B tests to disk."""
    with open(AB_TESTS_PATH, "w", encoding="utf-8") as f:
        json.dump(tests, f, indent=2)


class SignalABTest:
    """
    Represents a single A/B test between two signal timing strategies.
    """

    def __init__(
        self,
        test_id: str,
        name: str,
        strategy_a: str,
        strategy_b: str,
        zones_a: List[str],
        zones_b: List[str],
        duration_hours: int,
        start_time: str,
    ):
        self.test_id = test_id
        self.name = name
        self.strategy_a = strategy_a
        self.strategy_b = strategy_b
        self.zones_a = zones_a
        self.zones_b = zones_b
        self.duration_hours = duration_hours
        self.start_time = start_time

    def end_time(self) -> str:
        start = datetime.fromisoformat(self.start_time)
        return (start + timedelta(hours=self.duration_hours)).isoformat()

    def status(self, now: Optional[datetime] = None) -> str:
        now = now or datetime.now()
        start = datetime.fromisoformat(self.start_time)
        end = datetime.fromisoformat(self.end_time())
        if now < start:
            return "scheduled"
        if now < end:
            return "running"
        return "complete"

    def to_dict(self) -> dict:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "strategy_a": self.strategy_a,
            "strategy_b": self.strategy_b,
            "zones_a": self.zones_a,
            "zones_b": self.zones_b,
            "duration_hours": self.duration_hours,
            "start_time": self.start_time,
            "end_time": self.end_time(),
            "status": self.status(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SignalABTest":
        return cls(
            test_id=data["test_id"],
            name=data["name"],
            strategy_a=data["strategy_a"],
            strategy_b=data["strategy_b"],
            zones_a=data["zones_a"],
            zones_b=data["zones_b"],
            duration_hours=data["duration_hours"],
            start_time=data["start_time"],
        )


def start_ab_test(
    name: str,
    strategy_a: str,
    strategy_b: str,
    zones_a: List[str],
    zones_b: List[str],
    duration_hours: int = 24,
) -> str:
    """
    Create and register a new A/B test.

    Parameters
    ----------
    name : str
    strategy_a : str
        Human-readable name of strategy A (e.g. "current adaptive timing").
    strategy_b : str
        Human-readable name of strategy B (e.g. "simulation-optimised").
    zones_a : List[str]
        Zones assigned to strategy A.
    zones_b : List[str]
        Zones assigned to strategy B.
    duration_hours : int
        How long the test should run.

    Returns
    -------
    str
        The new test_id.
    """
    if not zones_a or not zones_b:
        raise ValueError("Both zones_a and zones_b must be non-empty.")
    if set(zones_a) & set(zones_b):
        raise ValueError("zones_a and zones_b must be disjoint.")

    test_id = str(uuid.uuid4())
    test = SignalABTest(
        test_id=test_id,
        name=name,
        strategy_a=strategy_a,
        strategy_b=strategy_b,
        zones_a=zones_a,
        zones_b=zones_b,
        duration_hours=duration_hours,
        start_time=datetime.now().isoformat(),
    )

    tests = _load_tests()
    tests[test_id] = test.to_dict()
    _save_tests(tests)

    return test_id


def evaluate_ab_test(test_id: str, city_df) -> Dict:
    """
    Evaluate the A/B test using live data from the given city DataFrame.

    Compares A and B groups on:
      - average delay proxy (mean congestion_score, higher = worse)
      - average throughput (mean vehicle_count, higher = better)
      - incident rate (fraction of rows flagged as anomalous, lower = better)

    Winner is decided by a weighted score:
      score = 0.5 * (1 - avg_congestion) + 0.3 * throughput_norm + 0.2 * (1 - incident_rate)

    Parameters
    ----------
    test_id : str
    city_df : pd.DataFrame
        The city DataFrame used for evaluation.

    Returns
    -------
    dict
        Test metadata plus A/B metrics, winner, evidence, and rationale.
    """
    tests = _load_tests()
    if test_id not in tests:
        raise ValueError(f"A/B test '{test_id}' not found.")

    test = SignalABTest.from_dict(tests[test_id])

    def group_metrics(zones: List[str]) -> Dict:
        zone_df = city_df[city_df["zone"].isin(zones)]
        if zone_df.empty:
            return {
                "avg_congestion": None,
                "avg_throughput": None,
                "incident_rate": None,
                "samples": 0,
            }

        avg_congestion = float(zone_df["congestion_score"].mean())
        avg_throughput = float(zone_df["vehicle_count"].mean())

        if "anomaly_flag" in zone_df.columns:
            incident_rate = float((zone_df["anomaly_flag"] == 1).mean())
        else:
            incident_rate = 0.0

        return {
            "avg_congestion": round(avg_congestion, 4),
            "avg_throughput": round(avg_throughput, 2),
            "incident_rate": round(incident_rate, 4),
            "samples": len(zone_df),
        }

    metrics_a = group_metrics(test.zones_a)
    metrics_b = group_metrics(test.zones_b)

    def weighted_score(m: Dict) -> Optional[float]:
        if m["avg_congestion"] is None:
            return None
        throughput_norm = min(m["avg_throughput"] / 500.0, 1.0)
        return round(
            0.5 * (1 - m["avg_congestion"])
            + 0.3 * throughput_norm
            + 0.2 * (1 - m["incident_rate"]),
            4,
        )

    score_a = weighted_score(metrics_a)
    score_b = weighted_score(metrics_b)

    if score_a is None or score_b is None:
        winner = None
        rationale = "Insufficient data to evaluate one or both groups."
    elif abs((score_a or 0) - (score_b or 0)) < 0.01:
        winner = "tie"
        rationale = f"Scores within 0.01 — no significant winner (A={score_a}, B={score_b})."
    elif (score_a or 0) > (score_b or 0):
        winner = "A"
        rationale = (
            f"Strategy A ({test.strategy_a}) scored {score_a} vs B scored {score_b}. "
            f"A shows {round((score_a - score_b) * 100, 2)}% higher weighted score."
        )
    else:
        winner = "B"
        rationale = (
            f"Strategy B ({test.strategy_b}) scored {score_b} vs A scored {score_a}. "
            f"B shows {round((score_b - score_a) * 100, 2)}% higher weighted score."
        )

    return {
        "test_id": test.test_id,
        "name": test.name,
        "status": test.status(),
        "start_time": test.start_time,
        "end_time": test.end_time(),
        "duration_hours": test.duration_hours,
        "strategy_a": test.strategy_a,
        "strategy_b": test.strategy_b,
        "zones_a": test.zones_a,
        "zones_b": test.zones_b,
        "metrics_a": metrics_a,
        "metrics_b": metrics_b,
        "weighted_score_a": score_a,
        "weighted_score_b": score_b,
        "winner": winner,
        "rationale": rationale,
    }


def list_ab_tests() -> List[Dict]:
    """Return all registered A/B tests (metadata only)."""
    return list(_load_tests().values())