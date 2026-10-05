import os
os.environ.setdefault("API_KEY", "c50eb575704f5be5c40d6bb821f2cec8ebfee2dab012bf1ffe686f1e75575780")
TEST_KEY = os.environ["API_KEY"]

import pytest
from fastapi.testclient import TestClient
from app import app
from src.model import generate_pdpl_audit_report


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_pdpl_report_covers_all_log_types():
    """The generated report must mention every known log/store."""
    report = generate_pdpl_audit_report()

    expected_stores = [
        "predictions_log.csv",
        "incidents_log.csv",
        "signal_commands_log.csv",
        "alerts_log.csv",
        "agency_access_log.csv",
        "usage_log.csv",
        "emissions_log.csv",
        "maintenance_notifications.csv",
        "ab_tests.json",
        "construction_zones.json",
    ]
    for store in expected_stores:
        assert store in report, f"{store} not mentioned in PDPL report"


def test_pdpl_report_contains_retention_periods():
    """Report must contain retention columns and specific retention values."""
    report = generate_pdpl_audit_report()

    assert "Retention" in report
    assert "retention_days" not in report  # make sure we wrote values, not raw keys
    assert "90 days" in report or "180 days" in report or "365 days" in report
    assert "PDPL" in report
    assert "Saudi Personal Data Protection Law" in report


def test_pdpl_report_endpoint_returns_markdown(client):
    response = client.get(
        "/reports/pdpl-audit",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# PDPL Compliance Audit Report" in response.text
    assert "Compliance Statement" in response.text