import os
import pytest
import pandas as pd
from datetime import datetime, timedelta
from src.model import check_and_reschedule_maintenance, notify_maintenance_crew
from src.adapters import RWISAdapter
from src.config import RWIS_MOISTURE_RESCHEDULE_THRESHOLD, RWIS_VISIBILITY_RESCHEDULE_THRESHOLD_M

def test_maintenance_rescheduled_when_visibility_low(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Mock RWISAdapter.fetch_all_zones to return low visibility
    original_fetch = RWISAdapter.fetch_all_zones
    def mock_fetch(self, zones):
        return {
            "Zone_1": {
                "pavement_temp_c": 38.0,
                "moisture_level": 0.1,
                "visibility_m": 300,
                "black_ice_risk": False,
            }
        }
    monkeypatch.setattr(RWISAdapter, "fetch_all_zones", mock_fetch)

    # We need a dummy schedule; generate_maintenance_schedule will be called inside.
    # It relies on app state, so we'll mock it to return a predefined schedule.
    import src.model
    original_generate = src.model.generate_maintenance_schedule
    def mock_generate(city, planning_horizon_days=7):
        return {
            "city": city,
            "generated_at": datetime.now().isoformat(),
            "horizon_days": planning_horizon_days,
            "total_zones": 1,
            "zones": [
                {
                    "zone": "Zone_1",
                    "wear_index": 2.5,
                    "risk_level": "Moderate",
                    "los": "C",
                    "vc_ratio": 0.45,
                    "urgency": "Medium",
                    "recommended_window": {
                        "start": (datetime.now() + timedelta(hours=2)).isoformat(),
                        "end": (datetime.now() + timedelta(hours=6)).isoformat(),
                    },
                    "expected_congestion_during_work": 0.2,
                    "reason": "Test",
                    "deferred": False,
                    "status": "scheduled",
                }
            ]
        }
    monkeypatch.setattr(src.model, "generate_maintenance_schedule", mock_generate)

    # Call rescheduler
    rescheduled = check_and_reschedule_maintenance("Riyadh")

    assert len(rescheduled) == 1
    assert rescheduled[0]["zone"] == "Zone_1"
    assert "visibility" in rescheduled[0]["reason"].lower()
    assert "new_window" in rescheduled[0]
    # Check that notification log was created
    assert os.path.exists("maintenance_notifications.csv")
    df = pd.read_csv("maintenance_notifications.csv")
    assert len(df) == 1
    assert df.iloc[0]["zone"] == "Zone_1"

    # Restore original functions
    monkeypatch.undo()

def test_maintenance_not_rescheduled_in_clear_conditions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # Mock RWISAdapter with clear conditions
    original_fetch = RWISAdapter.fetch_all_zones
    def mock_fetch(self, zones):
        return {
            "Zone_1": {
                "pavement_temp_c": 38.0,
                "moisture_level": 0.0,
                "visibility_m": 10000,
                "black_ice_risk": False,
            }
        }
    monkeypatch.setattr(RWISAdapter, "fetch_all_zones", mock_fetch)

    import src.model
    original_generate = src.model.generate_maintenance_schedule
    def mock_generate(city, planning_horizon_days=7):
        return {
            "city": city,
            "generated_at": datetime.now().isoformat(),
            "horizon_days": planning_horizon_days,
            "total_zones": 1,
            "zones": [
                {
                    "zone": "Zone_1",
                    "wear_index": 2.5,
                    "risk_level": "Moderate",
                    "los": "C",
                    "vc_ratio": 0.45,
                    "urgency": "Medium",
                    "recommended_window": {
                        "start": (datetime.now() + timedelta(hours=2)).isoformat(),
                        "end": (datetime.now() + timedelta(hours=6)).isoformat(),
                    },
                    "expected_congestion_during_work": 0.2,
                    "reason": "Test",
                    "deferred": False,
                    "status": "scheduled",
                }
            ]
        }
    monkeypatch.setattr(src.model, "generate_maintenance_schedule", mock_generate)

    rescheduled = check_and_reschedule_maintenance("Riyadh")
    assert len(rescheduled) == 0
    # Notification log should not exist or be empty
    if os.path.exists("maintenance_notifications.csv"):
        df = pd.read_csv("maintenance_notifications.csv")
        assert len(df) == 0

    monkeypatch.undo()

def test_notify_maintenance_crew_creates_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    event = {
        "zone": "Zone_1",
        "original_window": {"start": "2026-09-09T10:00:00", "end": "2026-09-09T14:00:00"},
        "new_window": {"start": "2026-09-10T10:00:00", "end": "2026-09-10T14:00:00"},
        "reason": "Test",
    }
    notify_maintenance_crew(event)
    assert os.path.exists("maintenance_notifications.csv")
    df = pd.read_csv("maintenance_notifications.csv")
    assert len(df) == 1
    assert df.iloc[0]["zone"] == "Zone_1"