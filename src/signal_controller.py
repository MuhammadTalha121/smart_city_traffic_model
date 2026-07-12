"""
NTCIP 1202 Signal Controller Interface (Stub) — PROMPT 121.
Actuator Feedback Loop & Confirmation —.

Implements a standards-shaped stub interface for sending signal timing
plans to physical traffic controllers via NTCIP 1202 (Traffic Signal
Controllers), plus a closed-loop confirmation mechanism that verifies
commands were actually applied and escalates when they are not.

Safety model
------------
ACTUATION_ENABLED defaults to False (src/config.py). No command reaches
even the stub transport unless this flag is explicitly True.
ActuationSafetyGate additionally enforces:
  - cycle_length within [MIN_CYCLE_SECONDS, MAX_CYCLE_SECONDS]
  - zone is known (present in ZONE_ADJACENCY)
  - zone is not in HAJJ_LOCKDOWN_ZONES

Confirmation model 
--------------------------------
30 seconds after a command reports "sent", confirm_actuation() polls
verify_timing_applied(). If it fails, one retry is scheduled 15 seconds
later. If both attempts fail, the command is logged UNCONFIRMED and an
alert is escalated through the existing check_thresholds()/
deliver_webhook_alert() pipeline — Critical severity for
emergency_preemption-purpose commands, Elevated otherwise. Escalations
are deduplicated per (zone, purpose) within a 15-minute window to avoid
notification fatigue.

Every attempt — sent, rejected, error, confirmed, or unconfirmed — is
appended to signal_commands_log.csv.
"""

import csv
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import uuid

from src.config import (
    ACTUATION_ENABLED,
    SIGNAL_CONTROLLER_ENDPOINTS,
    HAJJ_LOCKDOWN_ZONES,
    ZONE_ADJACENCY,
)

SIGNAL_COMMANDS_LOG_PATH = "signal_commands_log.csv"
_LOG_FIELDS = [
    "command_id", "timestamp", "zone", "cycle_length", "green_phase_seconds",
    "offset", "status", "reason", "confirmed", "attempt_count", "last_error_message",
]

MIN_CYCLE_SECONDS = 30
MAX_CYCLE_SECONDS = 180

# ──  — confirmation timing ──────────────────────────
CONFIRMATION_DELAY_S = 30
CONFIRMATION_RETRY_DELAY_S = 15
MAX_CONFIRMATION_ATTEMPTS = 2
_ALERT_DEDUP_WINDOW_S = 900  # 15 minutes

# Per (zone, purpose) -> last escalation datetime. Module-level, in-process
# only (mirrors the pattern in app.py's _last_alert_sent for congestion/
# incident alerts, kept local here since signal_controller.py must not
# import app.py — that would create a circular import).
_last_escalation_sent: Dict[str, datetime] = {}


import portalocker

def _log_command(row: dict) -> None:
    from src.training import training_log_path
    path = training_log_path(SIGNAL_COMMANDS_LOG_PATH)

    # Schema migration check
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "r", encoding="utf-8") as f:
            existing_header = f.readline().strip().split(",")
        missing_cols = [c for c in _LOG_FIELDS if c not in existing_header]
        if missing_cols:
            import pandas as pd
            existing_df = pd.read_csv(path, engine="python", on_bad_lines="skip")
            for col in missing_cols:
                existing_df[col] = ""
            with open(path, "w", encoding="utf-8") as f_out:
                portalocker.lock(f_out, portalocker.LOCK_EX)
                existing_df.to_csv(f_out, index=False)
                portalocker.unlock(f_out)

    is_new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        portalocker.lock(f, portalocker.LOCK_EX)
        writer = csv.DictWriter(f, fieldnames=_LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in _LOG_FIELDS})
        portalocker.unlock(f)


class ActuationSafetyGate:
    """Pre-transport safety checks for signal actuation commands."""

    def check(self, zone: str, cycle_length: float) -> Dict:
        if not ACTUATION_ENABLED:
            return {"allowed": False, "reason": "Actuation disabled (ACTUATION_ENABLED=False)."}

        if zone not in ZONE_ADJACENCY:
            return {"allowed": False, "reason": f"Unknown zone '{zone}'."}

        if zone in HAJJ_LOCKDOWN_ZONES:
            return {"allowed": False, "reason": f"Zone '{zone}' is under Hajj lockdown — actuation blocked."}

        if not (MIN_CYCLE_SECONDS <= cycle_length <= MAX_CYCLE_SECONDS):
            return {
                "allowed": False,
                "reason": (
                    f"cycle_length {cycle_length}s outside allowed range "
                    f"[{MIN_CYCLE_SECONDS}, {MAX_CYCLE_SECONDS}]."
                ),
            }

        return {"allowed": True, "reason": "OK"}


class NTCIPStubController:
    """
    Simulates NTCIP 1202 SNMP SET/GET commands to a traffic signal controller.

    Real deployment note: replace _send_snmp_set() / verify_timing_applied()
    with an actual SNMP client (e.g. pysnmp) against
    SIGNAL_CONTROLLER_ENDPOINTS[zone] using NTCIP 1202 OIDs. Safety gate,
    logging, and confirmation are transport-agnostic and do not change.
    """

    def __init__(self):
        self.safety_gate = ActuationSafetyGate()

    def _send_snmp_set(self, endpoint: str, plan: dict) -> bool:
        """Stub transport. Always succeeds."""
        return True

    def send_timing_plan(
        self,
        zone: str,
        cycle_length: float,
        green_phase_seconds: float,
        offset: float = 0.0,
    ) -> Dict:
        """
        Validate via ActuationSafetyGate, then (if allowed) send through
        the stub transport. Every attempt is logged regardless of outcome.

        Returns dict with status ("sent"|"rejected"|"error"), reason, command_id.
        """
        command_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        gate_result = self.safety_gate.check(zone, cycle_length)

        if not gate_result["allowed"]:
            _log_command({
                "command_id": command_id, "timestamp": timestamp, "zone": zone,
                "cycle_length": cycle_length, "green_phase_seconds": green_phase_seconds,
                "offset": offset, "status": "rejected", "reason": gate_result["reason"],
                "confirmed": "",
            })
            return {"status": "rejected", "reason": gate_result["reason"], "command_id": command_id}

        endpoint = SIGNAL_CONTROLLER_ENDPOINTS.get(zone)
        if not endpoint:
            reason = f"No controller endpoint configured for zone '{zone}'."
            _log_command({
                "command_id": command_id, "timestamp": timestamp, "zone": zone,
                "cycle_length": cycle_length, "green_phase_seconds": green_phase_seconds,
                "offset": offset, "status": "error", "reason": reason, "confirmed": "",
            })
            return {"status": "error", "reason": reason, "command_id": command_id}

        try:
            plan = {
                "cycle_length": cycle_length,
                "green_phase_seconds": green_phase_seconds,
                "offset": offset,
            }
            success = self._send_snmp_set(endpoint, plan)
            status = "sent" if success else "error"
            reason = "Command transmitted to controller." if success else "Transport failure."
        except Exception as e:
            status = "error"
            reason = f"Transport exception: {e}"

        _log_command({
            "command_id": command_id, "timestamp": timestamp, "zone": zone,
            "cycle_length": cycle_length, "green_phase_seconds": green_phase_seconds,
            "offset": offset, "status": status, "reason": reason, "confirmed": "",
        })

        return {"status": status, "reason": reason, "command_id": command_id}

    def verify_timing_applied(self, zone: str, expected_plan: dict) -> bool:
        """
        Stub always returns True (no real controller to query). Real
        implementation: SNMP GET against the controller's current
        timing OIDs, compared to expected_plan.
        """
        return True


# ---------------------------------------------------------------------------
# — Actuator Feedback Loop & Confirmation
# ---------------------------------------------------------------------------

def _escalate_unconfirmed_actuation(zone: str, command_id: str, expected_plan: dict) -> None:
    """
    Fire an alert through the existing alerting pipeline (check_thresholds
    / deliver_webhook_alert infrastructure, PROMPT 085) when an actuation
    command cannot be confirmed as applied by the field controller.

    Severity: Critical if expected_plan['purpose'] == 'emergency_preemption',
    else Elevated for routine timing commands. Deduplicated per
    (zone, purpose) within _ALERT_DEDUP_WINDOW_S to avoid notification
    fatigue on a persistently unreachable controller.
    """
    from src.pipeline import deliver_webhook_alert, log_alert

    purpose = expected_plan.get("purpose", "routine")
    severity = "Critical" if purpose == "emergency_preemption" else "Elevated"

    dedup_key = f"actuation_unconfirmed:{zone}:{purpose}"
    now = datetime.now()
    last_sent = _last_escalation_sent.get(dedup_key)
    if last_sent is not None and (now - last_sent).total_seconds() < _ALERT_DEDUP_WINDOW_S:
        return
    _last_escalation_sent[dedup_key] = now

    alert = {
        "zone": zone,
        "city": expected_plan.get("city", "Riyadh"),
        "metric": "actuation_confirmation",
        "value": command_id,
        "threshold": "CONFIRMED",
        "severity": severity,
    }

    try:
        log_alert([alert])
    except Exception:
        pass
    webhook_url = os.getenv("WEBHOOK_URL", "")
    try:
        deliver_webhook_alert([alert], webhook_url)
    except Exception:
        pass


def confirm_actuation(
    command_id: str,
    zone: str,
    expected_plan: dict,
    attempt: int = 1,
) -> None:
    """
    Verify a previously sent actuation was applied by the field controller.

    Intended to be scheduled via threading.Timer(CONFIRMATION_DELAY_S, ...)
    immediately after a "sent" result from NTCIPStubController.send_timing_plan().
    On failure, retries once after CONFIRMATION_RETRY_DELAY_S. After
    MAX_CONFIRMATION_ATTEMPTS failed attempts, logs UNCONFIRMED and
    escalates via _escalate_unconfirmed_actuation(). Intermediate failed
    attempts (before retries are exhausted) are not logged — only the
    final CONFIRMED or UNCONFIRMED outcome is written, per design.

    This function is safe to call directly in tests (synchronous) — the
    threading.Timer scheduling for the *first* call is the caller's
    responsibility (see POST /signals/actuate in app.py).
    """
    controller = NTCIPStubController()
    timestamp = datetime.now().isoformat()
    error_message = ""

    try:
        applied = controller.verify_timing_applied(zone, expected_plan)
        if not applied:
            error_message = "Controller reported mismatched or no timing plan."
    except Exception as e:
        applied = False
        error_message = f"Verification exception: {e}"

    if applied:
        _log_command({
            "command_id": command_id, "timestamp": timestamp, "zone": zone,
            "cycle_length": expected_plan.get("cycle_length", ""),
            "green_phase_seconds": expected_plan.get("green_phase_seconds", ""),
            "offset": expected_plan.get("offset", ""),
            "status": "CONFIRMED", "reason": "Timing plan verified applied.",
            "confirmed": True, "attempt_count": attempt, "last_error_message": "",
        })
        return

    if attempt < MAX_CONFIRMATION_ATTEMPTS:
        timer = threading.Timer(
            CONFIRMATION_RETRY_DELAY_S,
            confirm_actuation,
            args=(command_id, zone, expected_plan, attempt + 1),
        )
        timer.daemon = True
        timer.start()
        return

    # Retries exhausted — declare UNCONFIRMED and escalate.
    _log_command({
        "command_id": command_id, "timestamp": timestamp, "zone": zone,
        "cycle_length": expected_plan.get("cycle_length", ""),
        "green_phase_seconds": expected_plan.get("green_phase_seconds", ""),
        "offset": expected_plan.get("offset", ""),
        "status": "UNCONFIRMED", "reason": error_message or "Confirmation timed out.",
        "confirmed": False, "attempt_count": attempt, "last_error_message": error_message,
    })
    _escalate_unconfirmed_actuation(zone, command_id, expected_plan)


def schedule_confirmation(command_id: str, zone: str, expected_plan: dict) -> threading.Timer:
    """
    Schedule the first confirmation check CONFIRMATION_DELAY_S seconds from
    now. Returns the Timer object (daemonized so it never blocks process
    shutdown). Callers (e.g. POST /signals/actuate) should invoke this
    exactly once per successfully "sent" command.
    """
    timer = threading.Timer(CONFIRMATION_DELAY_S, confirm_actuation, args=(command_id, zone, expected_plan))
    timer.daemon = True
    timer.start()
    return timer