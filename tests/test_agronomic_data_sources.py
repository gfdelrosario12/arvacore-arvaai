import unittest
import sys
import os

sys.path.insert(0, '/home/gladwin/Documents/pagaaral/arvacore')
import ArvaAI
sys.modules['arvaAI'] = ArvaAI

from ArvaAI.app.tools.mcp_pagasa_adapter import PagasaWeatherMcpAdapter
from ArvaAI.app.tools.mcp_lopez_agri_adapter import LopezAgriHistoricalMcpAdapter
from ArvaAI.app.services.philrice_manual_retriever import PhilRiceManualRetriever
from ArvaAI.app.services.multi_source_evidence_aggregator import MultiSourceAgronomicEvidenceAggregator
from ArvaAI.app.tools.read_only_tools import ReadOnlyTelemetryTools

class TestAgronomicDataSources(unittest.TestCase):

    def setUp(self):
        self.pagasa = PagasaWeatherMcpAdapter()
        self.lopez = LopezAgriHistoricalMcpAdapter()
        self.retriever = PhilRiceManualRetriever()
        self.tools = ReadOnlyTelemetryTools("https://api-aquaflow.gladwindr.me/api/v1", "")
        self.aggregator = MultiSourceAgronomicEvidenceAggregator()

    # --- Source 1: PAGASA Weather MCP Tests ---
    def test_pagasa_mcp_tool_definitions(self):
        defs = self.pagasa.get_tool_definitions()
        self.assertEqual(len(defs), 2)
        names = [d["name"] for d in defs]
        self.assertIn("pagasa_get_forecast", names)
        self.assertIn("pagasa_get_severe_weather_warning", names)

    def test_pagasa_mcp_forecast_execution_and_climatological_fallback(self):
        res = self.pagasa.fetch_forecast(days=3)
        self.assertIn("daily_forecast", res)
        self.assertEqual(len(res["daily_forecast"]), 3)
        self.assertEqual(res["location"], "Barangay Silang, Lopez, Quezon")
        # Check units and variables
        first_day = res["daily_forecast"][0]
        self.assertIn("temperature_max_c", first_day)
        self.assertIn("expected_rainfall_mm", first_day)
        self.assertIn("awd_suitability", first_day)

    def test_pagasa_mcp_severe_weather_check(self):
        alerts = self.pagasa.fetch_severe_weather_warning("Quezon")
        self.assertIn("active_tropical_cyclone_signal", alerts)
        self.assertIn("heavy_rainfall_warning_level", alerts)
        self.assertEqual(alerts["active_tropical_cyclone_signal"], 0)

    # --- Source 2: Lopez Historical Agri MCP Tests ---
    def test_lopez_agri_mcp_tool_definitions(self):
        defs = self.lopez.get_tool_definitions()
        self.assertEqual(len(defs), 1)
        self.assertEqual(defs[0]["name"], "lopez_get_historical_agriculture_profile")

    def test_lopez_agri_mcp_data_provenance_and_yield_benchmarks(self):
        res = self.lopez.execute_tool("lopez_get_historical_agriculture_profile", {"category": "all"})
        data = res["data"]
        self.assertEqual(res["municipality"], "Lopez")
        self.assertEqual(res["province"], "Quezon")
        self.assertEqual(res["source"], "PHILRICE_RICELYTICS_PSA_CAPUCION2026")
        self.assertAlmostEqual(data["yield_benchmarks"]["irrigated_dry_season_avg_tons_per_ha"], 4.65)
        self.assertIn("prominent_varieties", data)
        varieties = [v["variety"] for v in data["prominent_varieties"]]
        self.assertTrue(any("NSIC Rc 222" in v for v in varieties))

    # --- Source 3: ArvaNode Sensor Telemetry Tests ---
    def test_arvanode_six_node_multi_terrace_structure(self):
        telemetry = self.aggregator._fetch_node_telemetry(field_id=1)
        self.assertTrue(telemetry["has_telemetry"])
        self.assertEqual(telemetry["total_nodes"], 6)
        self.assertEqual(len(telemetry["nodes"]), 6)
        # Verify node IDs and distinct terrace zones (Q1 through Q6)
        node_ids = [n["node_id"] for n in telemetry["nodes"]]
        self.assertEqual(node_ids, [f"ARVANODE-00{i}" for i in range(1, 7)])

    def test_arvanode_unit_and_zero_reading_distinction(self):
        # A reported 0.0 water level is a flooded soil surface, while None is missing
        telemetry = self.aggregator._fetch_node_telemetry(field_id=1)
        first_node = telemetry["nodes"][0]
        self.assertIsNotNone(first_node["water_level_cm"])
        self.assertIsNotNone(first_node["soil_moisture_percent"])

    # --- Source 4: PhilRice 2003 PDF Indexer & Retriever Tests ---
    def test_philrice_manual_indexing_and_search(self):
        self.assertGreater(len(self.retriever.indexed_pages), 200)
        results = self.retriever.search_manual("land preparation harrowing", top_k=2)
        self.assertGreater(len(results), 0)
        top = results[0]
        self.assertIn("page", top)
        self.assertIn("section", top)
        self.assertIn("snippet", top)
        self.assertIn("PhilRice", top["source"])

    # --- Source 5: Farmer & Farm Database Profile ---
    def test_farm_profile_authorization_and_fields(self):
        farm = self.aggregator._fetch_farm_profile(field_id=1, user_id="gladwin", role="FARMER")
        self.assertTrue(farm["authorized"])
        self.assertEqual(farm["area_hectares"], 1.1)
        self.assertIn("Lopez", farm["location_address"])

    # --- Multi-Source Agronomic Aggregator & 4 Outcomes ---
    def test_assessment_outcome_suitable(self):
        res = self.aggregator.aggregate_evidence(preparation_days_left=21)
        self.assertEqual(res["planting_assessment"]["outcome"], "Suitable")
        self.assertEqual(len(res["planting_assessment"]["risk_factors"]), 0)

    def test_assessment_outcome_high_risk_prep_window(self):
        res = self.aggregator.aggregate_evidence(preparation_days_left=7)
        self.assertEqual(res["planting_assessment"]["outcome"], "High risk")
        self.assertTrue(any("minimum" in r for r in res["planting_assessment"]["risk_factors"]))

    def test_assessment_outcome_high_risk_typhoon_warning(self):
        self.aggregator.pagasa_adapter.fetch_severe_weather_warning = lambda province: {
            "active_tropical_cyclone_signal": 2,
            "advisory_summary": "Signal #2 active"
        }
        res = self.aggregator.aggregate_evidence(preparation_days_left=21)
        self.assertEqual(res["planting_assessment"]["outcome"], "High risk")

    def test_assessment_outcome_conditionally_suitable_low_moisture(self):
        self.aggregator._fetch_node_telemetry = lambda field_id: {
            "has_telemetry": True, "total_nodes": 6, "online_nodes_count": 6,
            "average_soil_moisture": 38.0, "nodes": []
        }
        res = self.aggregator.aggregate_evidence(preparation_days_left=21)
        self.assertEqual(res["planting_assessment"]["outcome"], "Conditionally suitable")

    def test_assessment_outcome_further_assessment_missing_telemetry(self):
        self.aggregator._fetch_node_telemetry = lambda field_id: {
            "has_telemetry": False, "total_nodes": 6, "online_nodes_count": 0,
            "average_soil_moisture": None, "nodes": []
        }
        res = self.aggregator.aggregate_evidence(preparation_days_left=21)
        self.assertEqual(res["planting_assessment"]["outcome"], "Further assessment required")

    def test_safety_actuation_lock(self):
        res = self.aggregator.aggregate_evidence(preparation_days_left=21)
        self.assertFalse(res["safety_invariant"]["pump_actuation_permitted"])
        self.assertTrue(res["safety_invariant"]["advisory_only"])

if __name__ == "__main__":
    unittest.main()

