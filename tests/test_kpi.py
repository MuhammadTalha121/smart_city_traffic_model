from fastapi.testclient import TestClient

from app import app
from src.model import calculate_v2030_kpi_status


def test_kpi_covers_all_three_targets():
    result = calculate_v2030_kpi_status(city="Riyadh")
    assert result["city"] == "Riyadh"
    assert "kpis" in result and len(result["kpis"]) == 3
    names = {k["name"] for k in result["kpis"]}
    assert names == {"road_fatality_reduction", "emissions_reduction", "smart_city_index"}


def test_kpi_fatality_reduction_calculated_from_incidents():
    result = calculate_v2030_kpi_status(city="Riyadh")
    fatality = next(k for k in result["kpis"] if k["name"] == "road_fatality_reduction")
    assert fatality["status"] == "Data Not Available"
    assert fatality["current_pct"] is None
    assert "proxy_metrics" in fatality
    assert "incidents_logged" in fatality["proxy_metrics"]