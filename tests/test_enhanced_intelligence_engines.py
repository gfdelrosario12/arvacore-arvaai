"""
Tests for enhanced Arva AI intelligence engines:
1. Rice Phenology & Prediction Engine (12 growth stages, AWD depletion projection, weather hazard analysis).
2. Telemetry Quality Engine (anomaly detection, staleness, out-of-range bounds, true-zero preservation).
3. Rice Planting Readiness Engine (multi-factor readiness evaluation, insufficient data handling).
"""

import unittest
from datetime import datetime, timezone, timedelta

from app.services.rice_phenology_and_prediction import RicePhenologyAndPredictionEngine
from app.services.telemetry_quality_engine import TelemetryQualityEngine
from app.services.rice_planting_readiness_engine import RicePlantingReadinessEngine

class TestEnhancedIntelligenceEngines(unittest.TestCase):
    def setUp(self):
        self.phenology_engine = RicePhenologyAndPredictionEngine()
        self.quality_engine = TelemetryQualityEngine()
        self.readiness_engine = RicePlantingReadinessEngine()

    # --- 1. Rice Phenology & Predictive AWD Tests ---
    def test_growth_stage_determination_vegetative_vs_flowering(self):
        # DAT 20 -> Tillering vegetative (AWD allowed)
        veg = self.phenology_engine.determine_growth_stage("NSIC Rc 222", days_after_transplanting=20)
        self.assertEqual(veg["stage_key"], "TILLERING_VEGETATIVE")
        self.assertTrue(veg["is_awd_allowed"])
        self.assertIn("AWD safe drying", veg["awd_guideline"])

        # DAT 70 -> Heading / Flowering (Critical stage, AWD prohibited)
        flower = self.phenology_engine.determine_growth_stage("NSIC Rc 222", days_after_transplanting=70)
        self.assertEqual(flower["stage_key"], "HEADING_AND_FLOWERING")
        self.assertFalse(flower["is_awd_allowed"])
        self.assertIn("Zero drying permitted", flower["awd_guideline"])

        # DAT 100 -> Terminal drainage
        term = self.phenology_engine.determine_growth_stage("NSIC Rc 222", days_after_transplanting=100)
        self.assertEqual(term["stage_key"], "TERMINAL_DRAINAGE_AND_MATURITY")
        self.assertFalse(term["is_awd_allowed"])
        self.assertIn("TERMINAL DRAINAGE", term["awd_guideline"])

    def test_predict_awd_drying_window_projection(self):
        # Current water: -5.0 cm, drying rate: 1.2 cm/day, limit: -15.0 cm.
        # Distance = 10.0 cm -> ~8.3 days.
        proj = self.phenology_engine.predict_awd_drying_window(
            current_water_level_cm=-5.0,
            evapotranspiration_rate_cm_per_day=1.2,
            forecast_rain_mm_3days=0.0,
            safe_drying_limit_cm=-15.0
        )
        self.assertEqual(proj["status"], "SAFE_DRYING_IN_PROGRESS")
        self.assertGreater(proj["days_remaining_to_threshold"], 7.0)
        self.assertEqual(proj["action_recommended"], "CONTINUE_SAFE_DRYING")

        # Threshold breached test: -15.5 cm
        breach = self.phenology_engine.predict_awd_drying_window(
            current_water_level_cm=-15.5,
            safe_drying_limit_cm=-15.0
        )
        self.assertEqual(breach["status"], "THRESHOLD_BREACHED")
        self.assertEqual(breach["action_recommended"], "REFLOOD_REQUIRED")
        self.assertEqual(breach["urgency"], "IMMEDIATE")

    def test_weather_hazard_evaluation_cyclone_and_wind(self):
        hazards = self.phenology_engine.evaluate_weather_hazards(
            crop_stage_key="HEADING_AND_FLOWERING",
            max_wind_kmh=55.0,
            rainfall_24h_mm=35.0,
            active_cyclone_signal=1
        )
        types = [h["hazard_type"] for h in hazards]
        self.assertIn("TROPICAL_CYCLONE", types)
        self.assertIn("HEAVY_RAINFALL", types)
        self.assertIn("LODGING_RISK", types)

    # --- 2. Telemetry Quality & Anomaly Detection Tests ---
    def test_telemetry_quality_true_zero_vs_out_of_range(self):
        # True zero water level (0.0 cm mud line)
        t_zero = self.quality_engine.inspect_node_reading(
            node_id="ARVANODE-001",
            water_level_cm=0.0,
            soil_moisture_percent=70.0
        )
        self.assertTrue(t_zero["is_true_zero_water"])
        self.assertEqual(t_zero["quality"], "HEALTHY")
        self.assertEqual(t_zero["water_level_cm"], 0.0)

        # Out-of-range ultrasonic reading (-65 cm)
        corrupted = self.quality_engine.inspect_node_reading(
            node_id="ARVANODE-002",
            water_level_cm=-65.0,
            soil_moisture_percent=55.0
        )
        self.assertIsNone(corrupted["water_level_cm"])
        self.assertEqual(corrupted["quality"], "DEGRADED")
        self.assertTrue(any("exceeds physical bounds" in a for a in corrupted["anomalies"]))

    def test_telemetry_quality_critical_staleness(self):
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        stale_reading = self.quality_engine.inspect_node_reading(
            node_id="ARVANODE-003",
            water_level_cm=-5.0,
            soil_moisture_percent=60.0,
            reported_at_iso=old_time
        )
        self.assertTrue(stale_reading["is_critical_stale"])
        self.assertEqual(stale_reading["quality"], "UNRELIABLE")
        self.assertEqual(stale_reading["confidence"], 0.0)

    def test_field_telemetry_aggregation_rejects_corrupted(self):
        nodes = [
            {"node_id": "ARVANODE-001", "water_level_cm": -10.0, "soil_moisture_percent": 65.0},
            {"node_id": "ARVANODE-002", "water_level_cm": -12.0, "soil_moisture_percent": 63.0},
            {"node_id": "ARVANODE-003", "water_level_cm": -99.0, "soil_moisture_percent": 150.0}, # Corrupted
        ]
        agg = self.quality_engine.aggregate_field_telemetry(nodes)
        self.assertEqual(agg["total_nodes"], 3)
        self.assertEqual(agg["healthy_nodes"], 2)
        # Average should ignore corrupted ARVANODE-003: (-10 + -12)/2 = -11.0
        self.assertAlmostEqual(agg["average_water_level_cm"], -11.0)
        self.assertAlmostEqual(agg["average_soil_moisture_percent"], 64.0)

    # --- 3. Planting Readiness & Insufficient Data Handling ---
    def test_planting_readiness_insufficient_data(self):
        # Empty telemetry and empty weather forecast
        res = self.readiness_engine.evaluate_readiness(
            variety_name="NSIC Rc 222",
            establishment_method="Wetbed Transplanting",
            preparation_days_left=21,
            weather_forecast={"daily_forecast": []},
            severe_weather_alert={},
            telemetry_summary={"total_nodes": 0, "field_health": "OFFLINE_OR_UNAVAILABLE"},
            farm_profile={}
        )
        self.assertEqual(res["outcome"], "Further assessment required")
        self.assertIn("Insufficient data", res["summary"])
        self.assertGreater(len(res["missing_information"]), 0)

    def test_planting_readiness_high_risk_prep_window(self):
        res = self.readiness_engine.evaluate_readiness(
            variety_name="NSIC Rc 222",
            establishment_method="Wetbed Transplanting",
            preparation_days_left=8, # Less than 14 days minimum
            weather_forecast={"daily_forecast": [{"rainfall_amount_mm": 0.0}]},
            severe_weather_alert={},
            telemetry_summary={"total_nodes": 6, "field_health": "HEALTHY", "average_soil_moisture_percent": 65.0},
            farm_profile={}
        )
        self.assertEqual(res["outcome"], "High risk")
        self.assertTrue(any("minimum" in r for r in res["risks"]))

if __name__ == "__main__":
    unittest.main()

