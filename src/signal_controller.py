"""
NTCIP 1202 Signal Controller Interface (Stub) — PROMPT 121.

Implements a standards-shaped stub interface for sending signal timing
plans to physical traffic controllers via NTCIP 1202 (Traffic Signal
Controllers). This is NOT a real SNMP/NTCIP client — there is no field
hardware in this environment. The stub lets the full actuation pipeline
(safety gating, audit logging, command IDs, confirmation) be built and
tested now; only the transport layer (_send_snmp_set) needs replacing
for a real deployment.

Safety model
------------
ACTUATION_ENABLED defaults to False (src/config.py). No command reaches
even the stub transport unless this flag is explicitly True.
ActuationSafetyGate additionally enforces:
  - cycle_length within [MIN_CYCLE_SECONDS, MAX_CYCLE_SECONDS]
  - zone is known (present in ZONE_ADJACENCY)
  - zone is not in HAJJ_LOCKDOWN_ZONES

Every attempt — sent or rejected — is appended to signal_commands_log.csv.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict
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
    "offset", "status", "reason", "confirmed",
]

MIN_CYCLE_SECONDS = 30
MAX_CYCLE_SECONDS = 180


def _log_command(row: dict) -> None:
    """Append one actuation attempt to signal_commands_log.csv (append-only)."""
    from src.training import training_log_path
    path = Path(training_log_path(SIGNAL_COMMANDS_LOG_PATH))
    is_new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in _LOG_FIELDS})


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
    Simulates NTCIP 1202 SNMP SET commands to a traffic signal controller.

    Real deployment note: replace _send_snmp_set() with an actual SNMP
    client (e.g. pysnmp) against SIGNAL_CONTROLLER_ENDPOINTS[zone] using
    NTCIP 1202 OIDs, respecting NTCIP_TIMEOUT_SECONDS / NTCIP_RETRY_ATTEMPTS.
    Safety gate, logging, and confirmation are transport-agnostic and do
    not change.
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