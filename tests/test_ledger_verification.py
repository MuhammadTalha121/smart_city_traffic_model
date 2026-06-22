"""
PROMPT 068 — Ledger Chain Verification and Break-Recovery Procedure.

Save as tests/test_ledger_verification.py. Covers the three required
unit tests plus the two endpoint-level checks named in the prompt's
Your Task / Self-Audit sections. Does not modify or duplicate the
existing PROMPT 049 ledger tests in tests/test_model.py — those
continue to exercise ViolationLedger.verify_chain()'s legacy key names
unchanged.
"""

import os
import csv
import pytest

from src.ledger import ViolationLedger, verify_ledger_chain, LedgerIntegrityError


# ---------------------------------------------------------------------------
# Module-level verify_ledger_chain() — new PROMPT 068 key names
# ---------------------------------------------------------------------------

def test_verify_ledger_chain_detects_no_tampering_on_clean_ledger(tmp_path):
    """A freshly built, untampered chain must verify valid with no break."""
    ledger_path = tmp_path / "clean_ledger.csv"
    ledger = ViolationLedger(path=str(ledger_path))

    ledger.append_violation("veh1", "speeding",  "Zone_1", "2026-06-19T10:00:00", 150.0)
    ledger.append_violation("veh2", "red_light",  "Zone_2", "2026-06-19T10:05:00", 300.0)
    ledger.append_violation("veh3", "parking",    "Zone_1", "2026-06-19T10:10:00", 75.0)

    report = verify_ledger_chain(ledger_path=str(ledger_path))
    assert report["valid"] is True
    assert report["total_rows"] == 3
    assert report["first_break_at_row"] is None


def test_verify_ledger_chain_detects_modified_row(tmp_path):
    """Tampering with a stored field must be detected at the correct row."""
    ledger_path = tmp_path / "tampered_ledger.csv"
    ledger = ViolationLedger(path=str(ledger_path))

    ledger.append_violation("veh1", "speeding",  "Zone_1", "2026-06-19T10:00:00", 150.0)
    ledger.append_violation("veh2", "red_light",  "Zone_2", "2026-06-19T10:05:00", 300.0)

    # Tamper with the first row's violation_type without recomputing hashes
    with open(ledger_path, 'r', newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    rows[0]['violation_type'] = 'tampered'
    with open(ledger_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    report = verify_ledger_chain(ledger_path=str(ledger_path))
    assert report["valid"] is False
    assert report["total_rows"] == 2
    assert report["first_break_at_row"] == 1


def test_verify_ledger_chain_empty_ledger_is_valid(tmp_path):
    """An empty/never-written ledger path must report valid with 0 rows."""
    ledger_path = tmp_path / "never_written.csv"
    report = verify_ledger_chain(ledger_path=str(ledger_path))
    assert report["valid"] is True
    assert report["total_rows"] == 0
    assert report["first_break_at_row"] is None


# ---------------------------------------------------------------------------
# Write-freeze behavior — append_violation() refuses to write on a broken chain
# ---------------------------------------------------------------------------

def test_ledger_write_refused_when_chain_already_broken(tmp_path):
    """append_violation() must refuse to write onto a broken chain."""
    ledger_path = tmp_path / "broken_ledger.csv"
    ledger = ViolationLedger(path=str(ledger_path))

    ledger.append_violation("veh1", "speeding", "Zone_1", "2026-06-19T10:00:00", 150.0)

    # Break the chain by corrupting the stored block_hash directly
    # (so previous_hash chaining still looks fine, but the row's own
    # hash no longer matches its block_data — a different break mode
    # than test_verify_ledger_chain_detects_modified_row above).
    with open(ledger_path, 'r', newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    rows[0]['block_hash'] = 'corrupted_hash_value'
    with open(ledger_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(LedgerIntegrityError) as exc_info:
        ledger.append_violation("veh2", "red_light", "Zone_2", "2026-06-19T11:00:00", 300.0)

    assert exc_info.value.report["valid"] is False
    assert exc_info.value.report["first_break_at_row"] == 1

    # The refused write must not have been appended — file still has 1 row
    with open(ledger_path, 'r', newline='', encoding='utf-8') as f:
        rows_after = list(csv.DictReader(f))
    assert len(rows_after) == 1


def test_ledger_freeze_can_be_disabled_via_config_flag(tmp_path, monkeypatch):
    """
    LEDGER_FREEZE_ON_BREAK=False is documented as a debugging-only escape
    hatch. Confirm it actually bypasses the freeze (and that this is an
    explicit, monkeypatched opt-out in the test, not the production default).
    """
    import src.ledger as ledger_module
    monkeypatch.setattr(ledger_module, "LEDGER_FREEZE_ON_BREAK", False)

    ledger_path = tmp_path / "freeze_disabled.csv"
    ledger = ViolationLedger(path=str(ledger_path))
    ledger.append_violation("veh1", "speeding", "Zone_1", "2026-06-19T10:00:00", 150.0)

    with open(ledger_path, 'r', newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    rows[0]['block_hash'] = 'corrupted_hash_value'
    with open(ledger_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    # With the freeze disabled, this must NOT raise — it appends onto the
    # broken chain (the documented, debugging-only tradeoff).
    ledger.append_violation("veh2", "red_light", "Zone_2", "2026-06-19T11:00:00", 300.0)

    with open(ledger_path, 'r', newline='', encoding='utf-8') as f:
        rows_after = list(csv.DictReader(f))
    assert len(rows_after) == 2


# ---------------------------------------------------------------------------
# Backward compatibility — ViolationLedger.verify_chain() legacy key names
# ---------------------------------------------------------------------------

def test_verify_chain_legacy_keys_still_present_and_consistent(tmp_path):
    """
    verify_chain() must keep its original key names (total_blocks,
    first_invalid_block) so /citations/verify-ledger and the PROMPT 049
    tests in tests/test_model.py are unaffected by this prompt.
    """
    ledger_path = tmp_path / "legacy_check.csv"
    ledger = ViolationLedger(path=str(ledger_path))
    ledger.append_violation("veh1", "speeding", "Zone_1", "2026-06-19T10:00:00", 150.0)

    legacy = ledger.verify_chain()
    modern = verify_ledger_chain(ledger_path=str(ledger_path))

    assert legacy["valid"] == modern["valid"]
    assert legacy["total_blocks"] == modern["total_rows"]
    assert legacy["first_invalid_block"] == modern["first_break_at_row"]


# ---------------------------------------------------------------------------
# API-level — GET /ledger/verify and the LedgerIntegrityError 503 handler
# ---------------------------------------------------------------------------

if not os.environ.get("API_KEY"):
    os.environ["API_KEY"] = "test-key-for-pytest-only"
TEST_KEY = os.environ["API_KEY"]

try:
    from fastapi.testclient import TestClient
    from app import app

    @pytest.fixture(scope="module")
    def client():
        with TestClient(app) as c:
            yield c

    def test_ledger_verify_endpoint_returns_new_key_names(client):
        response = client.get("/ledger/verify", headers={"X-API-Key": TEST_KEY})
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "total_rows" in data
        assert "first_break_at_row" in data

    def test_ledger_verify_no_auth_returns_401(client):
        response = client.get("/ledger/verify")
        assert response.status_code == 401

    def test_ledger_verify_read_only_role_blocked(client):
        from src.auth import create_key
        ro_key = create_key('READ_ONLY', 'all')
        response = client.get("/ledger/verify", headers={"X-API-Key": ro_key})
        assert response.status_code == 403

except ImportError:
    # app.py's full dependency stack (xgboost, shap, apscheduler, etc.)
    # is not installed in every environment this file might run in.
    # The unit tests above (src.ledger only) still run; these three
    # API-level tests are skipped rather than erroring the whole module.
    pass
