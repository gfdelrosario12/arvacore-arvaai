import unittest
from arvaAI.app.services.farming_chat_planner import FarmingChatPlanner
from arvaAI.app.services.philrice_rice_knowledge import (
    RICE_VARIETIES,
    CROP_ESTABLISHMENT_METHODS,
    RICE_GROWTH_STAGES_AND_WATER,
    NUTRIENT_MANAGEMENT_GUIDELINES,
    PEST_WEED_DISEASE_GUIDELINES,
    HARVEST_AND_POSTHARVEST_GUIDELINES,
    get_rice_variety_profile,
    get_establishment_method,
)

class TestPhilRiceFullRiceCultivation(unittest.TestCase):
    def setUp(self):
        self.planner = FarmingChatPlanner()

    def test_rice_varieties_knowledge(self):
        self.assertIn("NSIC Rc 222", RICE_VARIETIES)
        self.assertIn("NSIC Rc 160", RICE_VARIETIES)
        self.assertIn("PSB Rc 82", RICE_VARIETIES)

        profile = get_rice_variety_profile("Tubigan 21")
        self.assertEqual(profile["maturity_days"], 106)

    def test_establishment_methods(self):
        wetbed = get_establishment_method("WETBED")
        self.assertEqual(wetbed["recommended_seeding_rate_kg_per_ha"], 30.0)
        self.assertEqual(wetbed["seedbed_area_m2_per_ha"], 400.0)

        dapog = get_establishment_method("dapog")
        self.assertEqual(dapog["seedbed_area_m2_per_ha"], 60.0)

        direct = get_establishment_method("direct seeding")
        self.assertEqual(direct["seedbed_area_m2_per_ha"], 0.0)

    def test_growth_stages_and_critical_flowering_depth(self):
        flowering = RICE_GROWTH_STAGES_AND_WATER["HEADING_AND_FLOWERING"]
        self.assertEqual(flowering["target_water_level_cm"], (3.0, 5.0))
        self.assertIn("MUST remain continuously submerged", flowering["water_guideline"])

        maturity = RICE_GROWTH_STAGES_AND_WATER["TERMINAL_DRAINAGE_AND_MATURITY"]
        self.assertEqual(maturity["target_water_level_cm"], 0.0)
        self.assertIn("drain all standing surface water 7 to 10 days before expected harvest", maturity["water_guideline"])

    def test_conversational_cultivation_support_flow(self):
        # 1. Step 1: Crop selection
        res1 = self.planner.process_turn("Lowland Rice", current_step="CROP_SELECTION")
        self.assertEqual(res1["step"], "FIELD_AND_METHOD")
        self.assertIn("NSIC Rc 222", res1["selected_crop"])

        # 2. Step 2: Method and Field specification
        res2 = self.planner.process_turn(
            "Terrace 1, Wet Bed Transplanting, in 3 weeks",
            current_step="FIELD_AND_METHOD",
            selected_crop=res1["selected_crop"]
        )
        self.assertEqual(res2["step"], "CONFIRMATION_PENDING")
        self.assertTrue(res2["requires_confirmation"])
        self.assertTrue(any("T-21 Days" in t["title"] for t in res2["tasks"]))

        # 3. Step 3: Affirmative Confirmation
        res3 = self.planner.process_turn(
            "Yes, proceed with preparation",
            current_step="CONFIRMATION_PENDING",
            selected_crop=res2["selected_crop"]
        )
        self.assertEqual(res3["step"], "PREPARATION_ACTIVE")
        self.assertFalse(res3["requires_confirmation"])

        # 4. Cultivation queries: Fertilizer
        res4 = self.planner.process_turn(
            "When should I apply urea fertilizer?",
            current_step="PREPARATION_ACTIVE",
            selected_crop=res3["selected_crop"]
        )
        self.assertEqual(res4["step"], "CROP_MANAGEMENT")
        self.assertIn("Leaf Color Chart", res4["reply"])
        self.assertIn("Zinc Sulfate", res4["reply"])

        # 5. Cultivation queries: Pest & Snail
        res5 = self.planner.process_turn(
            "How do I control golden kuhol snails?",
            current_step="CROP_MANAGEMENT",
            selected_crop=res3["selected_crop"]
        )
        self.assertIn("Golden Apple Snail", res5["reply"])
        self.assertIn("1-2 cm shallow water", res5["reply"])

        # 6. Cultivation queries: Harvest
        res6 = self.planner.process_turn(
            "When is the crop ready to harvest?",
            current_step="CROP_MANAGEMENT",
            selected_crop=res3["selected_crop"]
        )
        self.assertIn("80-85% of grains", res6["reply"])
        self.assertIn("Terminal Drainage", res6["reply"])

if __name__ == "__main__":
    unittest.main()
