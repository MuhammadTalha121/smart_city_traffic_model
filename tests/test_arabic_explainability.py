def test_arabic_briefing_contains_no_english_feature_names():
    """
    generate_operator_briefing(..., language='ar') must not leak English
    feature labels. If this test fails, a SHAP feature lacks an Arabic
    entry — fix the dictionary, do not weaken the test.
    """
    import pytest
    from fastapi.testclient import TestClient
    from app import app

    try:
        from src.auth import create_key
        operator_key = create_key("OPERATOR", city_scope="Riyadh")
    except Exception as e:
        pytest.skip(f"Could not create operator key for test: {e}")

    english_substrings = [
        "average speed", "vehicle count", "time of day",
        "hourly traffic weight", "rush hour period", "late night activity",
        "weekend pattern", "weather condition", "road type",
        "zone location", "special event", "day of week",
        "traffic 1 hour ago", "traffic 2 hours ago",
        "congestion 1 hour ago", "3-hour traffic average",
        "traffic volatility", "adjacent zone congestion",
        "adjacent zone traffic",
    ]

    with TestClient(app) as client:
        resp = client.get(
            "/briefing/Zone_1?city=Riyadh&language=ar",
            headers={"X-API-Key": operator_key},
        )
        assert resp.status_code == 200, (
            f"Briefing endpoint returned {resp.status_code}: {resp.text[:300]}"
        )

        body = resp.json().get("briefing", "")
        leaks = [s for s in english_substrings if s.lower() in body.lower()]

        assert not leaks, (
            f"Arabic briefing contains English feature names: {leaks}\n"
            f"Briefing was: {body!r}"
        )