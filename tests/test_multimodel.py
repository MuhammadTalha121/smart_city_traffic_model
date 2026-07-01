import os
import pytest

os.environ.setdefault("API_KEY", "test-key-for-pytest-only")
TEST_KEY = os.environ["API_KEY"]

from src.model import compute_multimodal_index

VALID_PAYLOAD = {
    "city"           : "Riyadh",
    "zone"           : "Zone_1",
    "hour"           : 8,
    "vehicle_count"  : 300,
    "avg_speed"      : 40.0,
    "weather"        : "clear",
    "road_type"      : "highway",
    "rush_hour"      : 1,
    "is_weekend"     : 0,
    "is_late_night"  : 0,
    "event"          : 0,
    "hour_multiplier": 1.4,
}


# ── unit tests ───────────────────────────────────────────────────

def test_high_vehicle_congestion_with_good_drt_produces_adequate_level():
    """High vehicle congestion (0.85) offset by DRT availability + decent
    last-mile options + low pedestrian risk should land in Adequate, not
    Stressed/Crisis — DRT is enough to meaningfully lift the score."""
    result = compute_multimodal_index(
        zone="Zone_1",
        vehicle_congestion_score=0.85,
        last_mile_index=0.6,
        drt_available=True,
        pedestrian_risk_score=0.2,
    )
    assert result["mobility_level"] == "Adequate", (
        f"Expected Adequate, got {result['mobility_level']} "
        f"(score={result['mobility_score']})"
    )
    assert 0.50 <= result["mobility_score"] < 0.70


def test_same_congestion_without_drt_is_worse():
    """Removing DRT availability under identical conditions must not
    improve (and should typically worsen) the mobility level."""
    with_drt = compute_multimodal_index(
        zone="Zone_1", vehicle_congestion_score=0.85,
        last_mile_index=0.6, drt_available=True, pedestrian_risk_score=0.2,
    )
    without_drt = compute_multimodal_index(
        zone="Zone_1", vehicle_congestion_score=0.85,
        last_mile_index=0.6, drt_available=False, pedestrian_risk_score=0.2,
    )
    assert without_drt["mobility_score"] < with_drt["mobility_score"]
    assert without_drt["bottleneck"] == "drt_availability"


def test_bottleneck_identifies_correct_constraint():
    """When DRT is unavailable and last-mile options are poor, DRT (larger
    weight, zero value) should be identified as the bottleneck over a
    smaller-weight component."""
    result = compute_multimodal_index(
        zone="Zone_2",
        vehicle_congestion_score=0.3,
        last_mile_index=0.5,
        drt_available=False,
        pedestrian_risk_score=0.1,
    )
    assert result["bottleneck"] == "drt_availability"
    assert "demand-responsive transit" in result["bottleneck_reason"].lower()


def test_low_congestion_full_alternatives_produces_good():
    """Low congestion, strong last-mile, DRT available, low pedestrian
    risk must produce Good with all three alternatives listed."""
    result = compute_multimodal_index(
        zone="Zone_3",
        vehicle_congestion_score=0.05,
        last_mile_index=0.8,
        drt_available=True,
        pedestrian_risk_score=0.05,
    )
    assert result["mobility_level"] == "Good"
    assert result["mobility_score"] >= 0.70
    assert set(result["alternatives"]) == {
        "DRT shuttle", "Micro-mobility (scooter/bike)", "Walking"
    }


def test_worst_case_produces_crisis_with_no_alternatives():
    """Maximum congestion, no last-mile, no DRT, high pedestrian risk
    must produce Crisis with an empty alternatives list."""
    result = compute_multimodal_index(
        zone="Zone_4",
        vehicle_congestion_score=1.0,
        last_mile_index=0.0,
        drt_available=False,
        pedestrian_risk_score=1.0,
    )
    assert result["mobility_level"] == "Crisis"
    assert result["mobility_score"] < 0.30
    assert result["alternatives"] == []


def test_mobility_score_bounded_zero_to_one():
    result = compute_multimodal_index(
        zone="Zone_5", vehicle_congestion_score=0.5,
        last_mile_index=0.5, drt_available=True, pedestrian_risk_score=0.5,
    )
    assert 0.0 <= result["mobility_score"] <= 1.0


# ── /predict integration ────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app import app
    with TestClient(app) as c:
        yield c


def test_multimodal_index_in_predict_response(client):
    """/predict must include an additive mobility_index dict and
    mobility_score, without breaking any existing response field."""
    response = client.post("/predict", json=VALID_PAYLOAD, headers={"X-API-Key": TEST_KEY})
    assert response.status_code == 200
    data = response.json()

    assert "mobility_index" in data
    assert "mobility_score" in data
    mi = data["mobility_index"]
    assert "mobility_level" in mi
    assert "bottleneck" in mi
    assert "alternatives" in mi
    assert mi["mobility_level"] in ("Good", "Adequate", "Stressed", "Crisis")
    assert 0.0 <= data["mobility_score"] <= 1.0

    # Existing fields must remain intact (additive-only, INV-1)
    assert "congestion_score" in data
    assert "explanation" in data


# ── /mobility/multimodal-status endpoint ────────────────────────

def test_multimodal_status_no_auth_returns_401(client):
    response = client.get("/mobility/multimodal-status?city=Riyadh")
    assert response.status_code == 401


def test_multimodal_status_returns_all_zones(client):
    response = client.get(
        "/mobility/multimodal-status?city=Riyadh",
        headers={"X-API-Key": TEST_KEY},
    )
    assert response.status_code == 200
    data = response.json()

    assert "zones" in data
    assert "summary" in data
    assert len(data["zones"]) == 5

    scores = [z["mobility_score"] for z in data["zones"]]
    assert scores == sorted(scores), "Zones must be sorted worst-first (ascending mobility_score)"

    for z in data["zones"]:
        assert "zone" in z
        assert "mobility_level" in z
        assert "bottleneck" in z
        assert "alternatives" in z
        assert "components" in z