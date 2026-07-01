"""
Operator Training Mode .

When TRAINING_MODE is active, write-side log functions redirect their
output to *_training.csv sibling files instead of the production logs,
so training exercises never pollute predictions_log.csv, alerts_log.csv,
incidents_log.csv, etc. Read-side behaviour (predictions themselves,
forecasts) is unaffected — only the audit-trail writes are redirected.

Toggling is done via set_training_mode(); log-writing functions check
is_training_mode() at call time by importing src.config as a module
(not `from src.config import TRAINING_MODE`), so the check always sees
the live value rather than one frozen at import time.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import src.config as _cfg

TRAINING_LOG_SUFFIX = "_training"

# Base production log paths this module knows how to redirect/summarise.
TRAINING_LOG_FILES: List[str] = [
    "predictions_log.csv",
    "alerts_log.csv",
    "incidents_log.csv",
    "usage_log.csv",
    "ids_log.csv",
    "scenarios_log.csv",
]


def is_training_mode() -> bool:
    """Return the current training mode flag. Always reads the live value."""
    return bool(getattr(_cfg, "TRAINING_MODE", False))


def set_training_mode(active: bool) -> None:
    """Toggle training mode module-wide."""
    _cfg.TRAINING_MODE = bool(active)


def training_log_path_force(base_path: str) -> str:
    """Always return the training-suffixed variant, regardless of the flag."""
    root, ext = os.path.splitext(base_path)
    if root.endswith(TRAINING_LOG_SUFFIX):
        return base_path
    return f"{root}{TRAINING_LOG_SUFFIX}{ext}"


def training_log_path(base_path: str) -> str:
    """
    Return the training-mode variant of a log path when training mode is
    active, otherwise return base_path unchanged. With the default
    TRAINING_MODE=False this is a no-op, so every existing caller (and
    every test that passes a custom tmp_path log_path) behaves exactly
    as it did before this prompt existed.
    """
    if not is_training_mode():
        return base_path
    return training_log_path_force(base_path)


def clear_training_logs() -> None:
    """
    Delete any existing *_training.csv files so each new session starts
    from a clean slate rather than accumulating counts across sessions.
    """
    for base_path in TRAINING_LOG_FILES:
        path = training_log_path_force(base_path)
        if os.path.exists(path):
            os.remove(path)


def start_session() -> Dict:
    """Begin a new training session: clear stale training logs, then enable training mode."""
    clear_training_logs()
    set_training_mode(True)
    return {
        "session_id": str(uuid.uuid4()),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def end_session(session: Optional[Dict]) -> Dict:
    """
    End the active training session: disable training mode, summarise
    actions taken (row count per training log file), and return the
    summary. Training logs are left on disk for post-session review
    until the next start_session() clears them.
    """
    set_training_mode(False)

    row_counts: Dict[str, int] = {}
    for base_path in TRAINING_LOG_FILES:
        path = training_log_path_force(base_path)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = sum(1 for _ in f)
            row_counts[base_path] = max(0, lines - 1)  # subtract header row
        else:
            row_counts[base_path] = 0

    return {
        "session_id": (session or {}).get("session_id"),
        "started_at": (session or {}).get("started_at"),
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "actions_by_log": row_counts,
        "total_actions": sum(row_counts.values()),
    }