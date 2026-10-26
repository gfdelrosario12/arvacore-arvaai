import pytest
from app.services.soil_fallback_engine import (
    SoilDataFallbackEngine,
    FallbackDecisionType,
    EvidenceQuality
)


def test_normal_operation_restored_when_valid_soil_telemetry():
    engine = SoilDataFallbackEngine()
    nodes = [
        {"node_id": "ARVANODE-001", "is_online": True, "soil_moisture_percent": 65.0, "water_level_cm": 3.0},
        {"node_id": "ARVANODE-002", "is_online": True, "soil_moisture_percent": 62.0, "water_level_cm": 2.5}
    ]
    res = engine.evaluate_fallback(nodes_telemetry=nodes)
    assert res.is_fallback_active is False
    assert res.evidence_quality == EvidenceQuality.HIGH
    assert res.decision == FallbackDecisionType.IRRIGATION_NOT_RECOMMENDED


def test_fallback_when_soil_data_missing_but_water_level_positive():
    engine = SoilDataFallbackEngine()
    # Missing soil data (None), but ultrasonic confirms standing water (+3.5 cm)
    nodes = [
        {"node_id": "ARVANODE-001", "is_online": True, "soil_moisture_percent": None, "water_level_cm": 3.5},
        {"node_id": "ARVANODE-002", "is_online": True, "soil_moisture_percent": None, "water_level_cm": 4.0}
    ]
    res = engine.evaluate_fallback(nodes_telemetry=nodes)
    assert res.is_fallback_active is True
    assert res.decision == FallbackDecisionType.IRRIGATION_NOT_RECOMMENDED
    assert "Surface Water Present" in res.headline
    assert res.can_auto_irrigate is False
    assert any("Ultrasonic Water Depth" in s for s in res.sources_used)


def test_fallback_when_soil_data_missing_and_water_level_critical_awd():
    engine = SoilDataFallbackEngine()
    # Missing soil data, but ultrasonic confirms water dropped to -15.0 cm (AWD trigger)
    nodes = [
        {"node_id": "ARVANODE-001", "is_online": True, "soil_moisture_percent": None, "water_level_cm": -15.2},
        {"node_id": "ARVANODE-002", "is_online": True, "soil_moisture_percent": None, "water_level_cm": -14.8}
    ]
    res = engine.evaluate_fallback(nodes_telemetry=nodes)
    assert res.is_fallback_active is True
    assert res.decision == FallbackDecisionType.IRRIGATION_RECOMMENDED
    assert "AWD Reflood Trigger Verified" in res.headline
    assert res.requires_farmer_confirmation is True
    assert res.can_auto_irrigate is False


def test_fallback_when_rain_hazard_forecast():
    engine = SoilDataFallbackEngine()
    # Soil missing and low water level, but PAGASA forecasts 30mm rain
    nodes = [
        {"node_id": "ARVANODE-001", "is_online": True, "soil_moisture_percent": None, "water_level_cm": -15.0}
    ]
    forecast = {"pop": 85, "rain_24h_mm": 30.0}
    res = engine.evaluate_fallback(nodes_telemetry=nodes, weather_forecast=forecast)
    assert res.is_fallback_active is True
    assert res.decision == FallbackDecisionType.IRRIGATION_NOT_RECOMMENDED
    assert "Natural Rainfall Anticipated" in res.headline


def test_fallback_rejects_false_zero_and_flags_sensor_failure():
    engine = SoilDataFallbackEngine()
    # Nodes reporting false zero (0.0%) indicating probe disconnection
    nodes = [
        {"node_id": "ARVANODE-001", "is_online": True, "soil_moisture_percent": 0.0, "water_level_cm": None},
        {"node_id": "ARVANODE-002", "is_online": True, "soil_moisture_percent": 0.0, "water_level_cm": None}
    ]
    res = engine.evaluate_fallback(nodes_telemetry=nodes)
    assert res.is_fallback_active is True
    assert res.decision == FallbackDecisionType.SENSOR_FAILURE_TROUBLESHOOTING
    assert "Sensor Disconnection / Hardware Fault" in res.headline
    assert res.can_auto_irrigate is False
