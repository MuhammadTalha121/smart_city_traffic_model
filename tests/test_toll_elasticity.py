"""
Toll price elasticity calibration tests (PROMPT 165).
"""
import pytest
from datetime import datetime


def test_elasticity_negative():
    """
    If any zone's elasticity is reported as calibrated, it must be a
    meaningful negative value, not 0.0. A 0.0 or positive elasticity
    indicates the circularity between proxy price and congestion has
    overwhelmed the regression — the implementation must fall back to
    TOLL_ELASTICITY_DEFAULT rather than report a degenerate value.
    """
    from src.model import calibrate_toll_elasticity
    from src.data import generate_traffic_data, apply_hourly_patterns
    from src.config import TOLLED_ZONES, TOLL_ELASTICITY_DEFAULT

    df = generate_traffic_data(city="Riyadh", n_days=30)
    df = apply_hourly_patterns(df, city="Riyadh")

    result = calibrate_toll_elasticity(df)

    for zone in TOLLED_ZONES:
        elasticity = result["elasticity_by_zone"][zone]

        # Always check the clip bounds
        assert elasticity <= 0.0, (
            f"{zone}: positive elasticity {elasticity} is economically impossible"
        )
        assert elasticity >= -1.5, (
            f"{zone}: elasticity {elasticity} out of clip range [-1.5, 0]"
        )

        # If this zone was calibrated (not default), require meaningful signal
        if elasticity != TOLL_ELASTICITY_DEFAULT:
            assert abs(elasticity) >= 0.01, (
                f"{zone}: 'calibrated' elasticity {elasticity} is effectively "
                f"zero — should have fallen back to "
                f"TOLL_ELASTICITY_DEFAULT ({TOLL_ELASTICITY_DEFAULT}). "
                f"Circularity guard is not working."
            )


def test_toll_recommendation_uses_calibrated_elasticity():
    """
    After set_calibrated_toll_elasticity(), recommend_toll_rate must use
    the calibrated value rather than TOLL_ELASTICITY_DEFAULT.
    """
    from fastapi.testclient import TestClient
    from app import app
    from src.model import recommend_toll_rate, set_calibrated_toll_elasticity
    from src.config import TOLLED_ZONES, TOLL_EVENT_HOURS, TOLL_ELASTICITY_DEFAULT
    import src.model as model_module

    if not TOLLED_ZONES:
        pytest.skip("No tolled zones configured")

    zone = TOLLED_ZONES[0]
    peak_hour = TOLL_EVENT_HOURS[0]
    ts = datetime.now().replace(hour=peak_hour, minute=0, second=0, microsecond=0)

    forced_elasticity = -1.2  # clearly different from default -0.35

    with TestClient(app):
        # Baseline: no calibration
        model_module._CALIBRATED_TOLL_ELASTICITY = None
        baseline = recommend_toll_rate(
            zone, city="Riyadh", timestamp=ts, event_active=True
        )

        # Calibrated: forced value
        set_calibrated_toll_elasticity({zone: forced_elasticity})
        try:
            calibrated = recommend_toll_rate(
                zone, city="Riyadh", timestamp=ts, event_active=True
            )
        finally:
            model_module._CALIBRATED_TOLL_ELASTICITY = None

    baseline_pct   = baseline["demand_reduction_forecast_pct"]
    calibrated_pct = calibrated["demand_reduction_forecast_pct"]

    if baseline_pct == 0.0 and calibrated_pct == 0.0:
        pytest.skip(
            "Both elasticities produced zero demand reduction — price was at "
            "baseline for this zone/hour, cannot distinguish. "
            "This is a data-availability limit, not a bug."
        )

    assert calibrated_pct != baseline_pct, (
        f"Calibrated elasticity ({forced_elasticity}) should produce different "
        f"demand reduction than default ({TOLL_ELASTICITY_DEFAULT}). "
        f"Baseline={baseline_pct}, Calibrated={calibrated_pct}. "
        f"Cache is not being consulted."
    )