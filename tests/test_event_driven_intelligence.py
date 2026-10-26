import unittest
from app.services.event_driven_intelligence import EventDrivenArvaEngine, FarmEvent

class EventDrivenArvaEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = EventDrivenArvaEngine(cooldown_minutes=5)

    def test_detects_low_water_level_and_generates_dynamic_questions(self):
        nodes = [
            {"node_id": "NODE-01", "is_online": True, "water_level_cm": 0.5, "soil_moisture_percent": 55.0},
            {"node_id": "NODE-02", "is_online": True, "water_level_cm": 1.2, "soil_moisture_percent": 60.0},
        ]
        result = self.engine.analyze_farm_state(
            nodes_telemetry=nodes,
            zones=[],
            crop_stage="VEGETATIVE"
        )
        events = result["active_events"]
        self.assertTrue(any(e["event_type"] == "WATER_LEVEL_DROP" for e in events))
        
        advisory = result["primary_advisory"]
        self.assertIn("AWD Reflood Trigger", advisory["headline"])
        self.assertEqual(advisory["proposal_type"], "REFLOOD_PROPOSAL")

        questions = result["dynamic_questions"]
        self.assertTrue(any("growth stage" in q.lower() or "irrigation" in q.lower() for q in questions))

    def test_detects_heavy_rain_forecast_and_defers_irrigation(self):
        nodes = [
            {"node_id": "NODE-01", "is_online": True, "water_level_cm": 0.5, "soil_moisture_percent": 52.0},
        ]
        weather = {
            "rainfall_probability_percent": 85,
            "rainfall_amount_mm": 25.0
        }
        result = self.engine.analyze_farm_state(
            nodes_telemetry=nodes,
            zones=[],
            weather_forecast=weather,
            crop_stage="VEGETATIVE"
        )
        events = result["active_events"]
        self.assertTrue(any(e["event_type"] == "RAIN_FORECAST" for e in events))

        advisory = result["primary_advisory"]
        self.assertIn("Rain Expected", advisory["headline"])
        self.assertEqual(advisory["proposal_type"], "DEFER_IRRIGATION")

        questions = result["dynamic_questions"]
        self.assertTrue(any("forecast" in q.lower() for q in questions))

    def test_emergency_stop_blocks_all_proposals(self):
        nodes = [
            {"node_id": "NODE-01", "is_online": True, "water_level_cm": 0.2, "soil_moisture_percent": 42.0},
        ]
        result = self.engine.analyze_farm_state(
            nodes_telemetry=nodes,
            zones=[],
            is_estop_active=True
        )
        advisory = result["primary_advisory"]
        self.assertEqual(advisory["urgency"], "CRITICAL")
        self.assertIn("Emergency Stop", advisory["headline"])

        questions = result["dynamic_questions"]
        self.assertTrue(any("check before attempting irrigation" in q.lower() for q in questions))

    def test_conflicting_readings_detected(self):
        nodes = [
            {"node_id": "NODE-01", "is_online": True, "water_level_cm": 1.0},
            {"node_id": "NODE-02", "is_online": True, "water_level_cm": 11.5},
        ]
        result = self.engine.analyze_farm_state(nodes_telemetry=nodes, zones=[])
        events = result["active_events"]
        self.assertTrue(any(e["event_type"] == "READINGS_CONFLICT" for e in events))

        questions = result["dynamic_questions"]
        self.assertTrue(any("different conditions" in q.lower() for q in questions))

    def test_missing_or_stale_data_question_generation(self):
        nodes = [
            {"node_id": "NODE-01", "is_online": False},
            {"node_id": "NODE-02", "is_online": True, "last_seen": "2020-01-01T00:00:00Z"},
        ]
        result = self.engine.analyze_farm_state(nodes_telemetry=nodes, zones=[])
        questions = result["dynamic_questions"]
        self.assertTrue(any("missing sensor data" in q.lower() or "troubleshoot" in q.lower() for q in questions))

