"""
PhilRice Rice Production Knowledge Base & Full Cultivation Cycle Support.
Authoritative source: Philippine Rice Research Institute (PhilRice),
"Philippine Rice Production Training Manual" (2003).

Covers the 12 complete workflow stages:
1. Farm and Rice Variety Profiling (Module 4)
2. Planting Schedule and Readiness Assessment (Module 5 & 6)
3. Land Preparation and Field Leveling (Module 5, 21-day timeline)
4. Seed Preparation and Crop Establishment (Module 6: Wetbed, Dapog, Direct-Wet)
5. Vegetative Growth and Tillering (Module 3 & 7)
6. Weed, Pest, and Disease Monitoring (Modules 10, 11, 12, 13, 14, 15, 16)
7. Nutrient and Fertilizer Management (Module 8: INM, LCC, MOET, Zinc)
8. Growth-Stage-Specific Irrigation and Water Management (Module 7: AWD, critical depths)
9. Reproductive Growth and Flowering (Module 3 & 7)
10. Grain Filling and Maturation (Module 3, 7, 19)
11. Harvest Readiness and Postharvest Management (Module 19)
12. Yield Recording, Postharvest Review, and Next Cropping Cycle (Module 1, 8, 19)
"""

from typing import Dict, Any, List, Optional

RICE_VARIETIES: Dict[str, Dict[str, Any]] = {
    "NSIC Rc 222": {
        "popular_name": "Tubigan 21",
        "ecosystem": "Lowland Irrigated",
        "maturity_days": 106,
        "average_yield_tha": 6.1,
        "max_yield_tha": 10.0,
        "plant_height_cm": 101,
        "tillering_ability": "High",
        "resistance": "Intermediate to blast, bacterial leaf blight, and green leafhopper",
        "eating_quality": "High amylose (24.2%), firm when cooled",
        "recommended_seasons": ["Dry Season", "Wet Season"],
        "recommended_spacing": "20 cm x 20 cm",
        "citation": "PhilRice Varietal Catalog & NSIC Standards"
    },
    "NSIC Rc 160": {
        "popular_name": "Tubigan 14",
        "ecosystem": "Lowland Irrigated",
        "maturity_days": 107,
        "average_yield_tha": 5.6,
        "max_yield_tha": 8.2,
        "plant_height_cm": 96,
        "tillering_ability": "Medium to High",
        "resistance": "Resistant to stem borer, intermediate to blast",
        "eating_quality": "Low amylose (14.8%), soft and aromatic",
        "recommended_seasons": ["Dry Season", "Wet Season"],
        "recommended_spacing": "20 cm x 20 cm",
        "citation": "PhilRice Varietal Catalog & NSIC Standards"
    },
    "PSB Rc 82": {
        "popular_name": "Peñaranda",
        "ecosystem": "Lowland Irrigated",
        "maturity_days": 110,
        "average_yield_tha": 5.4,
        "max_yield_tha": 8.0,
        "plant_height_cm": 100,
        "tillering_ability": "High",
        "resistance": "Moderate resistance to green leafhopper and blast",
        "eating_quality": "Intermediate amylose, good eating quality",
        "recommended_seasons": ["Dry Season", "Wet Season"],
        "recommended_spacing": "20 cm x 20 cm",
        "citation": "PhilRice PSB Catalog (2001)"
    },
    "NSIC Rc 216": {
        "popular_name": "Tubigan 17",
        "ecosystem": "Lowland Irrigated",
        "maturity_days": 112,
        "average_yield_tha": 6.0,
        "max_yield_tha": 9.7,
        "plant_height_cm": 98,
        "tillering_ability": "High",
        "resistance": "Intermediate resistance to bacterial leaf blight and blast",
        "eating_quality": "Intermediate amylose (21.5%), tender",
        "recommended_seasons": ["Dry Season", "Wet Season"],
        "recommended_spacing": "20 cm x 20 cm",
        "citation": "PhilRice Varietal Catalog & NSIC Standards"
    }
}

CROP_ESTABLISHMENT_METHODS: Dict[str, Dict[str, Any]] = {
    "WETBED": {
        "name": "Wetbed Transplanting",
        "seeding_rate_kg_per_ha": (20.0, 40.0),
        "recommended_seeding_rate_kg_per_ha": 30.0,
        "seedbed_area_m2_per_ha": 400.0,
        "soaking_hours": 24,
        "incubation_hours": (24, 36),
        "seedling_age_transplanting_days": (20, 21),
        "hills_per_m2": 25,
        "seedlings_per_hill": (2, 3),
        "planting_depth_cm": (1.5, 3.0),
        "spacing_cm": "20 cm x 20 cm in straight rows",
        "citation": "PhilRice Training Manual (2003), Module 6, pp. 60-65."
    },
    "DAPOG": {
        "name": "Dapog Transplanting",
        "seeding_rate_kg_per_ha": (45.0, 65.0),
        "recommended_seeding_rate_kg_per_ha": 55.0,
        "seedbed_area_m2_per_ha": 60.0,
        "soaking_hours": 24,
        "incubation_hours": (36, 48),
        "seedling_age_transplanting_days": (9, 14),
        "hills_per_m2": 25,
        "seedlings_per_hill": (3, 4),
        "planting_depth_cm": (1.5, 2.0),
        "spacing_cm": "20 cm x 20 cm",
        "citation": "PhilRice Training Manual (2003), Module 6, Table V, pp. 62-63."
    },
    "DIRECT_WET": {
        "name": "Direct Wet Seeding (Broadcast or Drum Seeder)",
        "seeding_rate_kg_per_ha": (60.0, 80.0),
        "recommended_seeding_rate_kg_per_ha": 70.0,
        "seedbed_area_m2_per_ha": 0.0,
        "soaking_hours": 24,
        "incubation_hours": (24, 24),
        "seedling_age_transplanting_days": (0, 0),
        "hills_per_m2": 0,
        "seedlings_per_hill": (0, 0),
        "planting_depth_cm": (0.0, 0.5),
        "spacing_cm": "Broadcast or 20 cm row drum seeder",
        "citation": "PhilRice Training Manual (2003), Module 6, Section XVI-XIX, pp. 65-66."
    }
}

RICE_GROWTH_STAGES_AND_WATER: Dict[str, Dict[str, Any]] = {
    "GERMINATION_EMERGENCE": {
        "stage_code": "STAGE_0",
        "name": "Germination to Emergence (Stage 0)",
        "days_after_sowing": (0, 3),
        "target_water_level_cm": 0.0,
        "water_guideline": "Saturated soil without standing water to ensure adequate oxygen for coleoptile and radicle.",
        "risk_factors": "Submerged seeds during early germination suffer oxygen starvation and poor establishment.",
        "citation": "PhilRice Module 3, p. 40; Module 7, p. 71."
    },
    "SEEDLING": {
        "stage_code": "STAGE_1",
        "name": "Seedling Nursery (Stage 1)",
        "days_after_sowing": (4, 21),
        "target_water_level_cm": (2.0, 3.0),
        "water_guideline": "Maintain 2-3 cm pond water once emerged to keep seedbed soil soft for effortless seedling pulling without root breakage.",
        "risk_factors": "Hard dry seedbed soil causes severe root detachment during pulling, delaying recovery after transplanting.",
        "citation": "PhilRice Module 6, p. 61; Module 7, Section VII.A, p. 71."
    },
    "TRANSPLANTING_RECOVERY": {
        "stage_code": "STAGE_1B",
        "name": "Transplanting Recovery (Week 1 Post-Transplant)",
        "days_after_transplanting": (0, 7),
        "target_water_level_cm": (1.0, 2.0),
        "water_guideline": "Maintain soil saturation or shallow 1-2 cm depth to establish soil-root contact, protect against Golden Apple Snail feeding, and facilitate recovery.",
        "risk_factors": "Deep water (>5 cm) drowns short seedlings and encourages golden apple snails; drying causes wilting.",
        "citation": "PhilRice Module 7, Section VII.B, p. 71; Module 16, p. 168."
    },
    "TILLERING_VEGETATIVE": {
        "stage_code": "STAGE_2",
        "name": "Tillering & Vegetative Phase (Stage 2)",
        "days_after_transplanting": (8, 35),
        "target_water_level_cm": (2.0, 3.0),
        "water_guideline": "Maintain shallow 2-3 cm water depth. Occasional safe drying down to -15 cm (AWD) stimulates deeper root growth, firm root anchorage, and prevents excessive non-bearing tillers.",
        "risk_factors": "Deep ponded water (>5 cm) drastically inhibits active tiller emergence.",
        "citation": "PhilRice Module 3, p. 42; Module 7, Section VII.C & Figure 7.1, p. 71."
    },
    "STEM_ELONGATION": {
        "stage_code": "STAGE_3",
        "name": "Stem Elongation (Stage 3)",
        "days_after_transplanting": (36, 50),
        "target_water_level_cm": (3.0, 5.0),
        "water_guideline": "Gradually increase water depth to 3-5 cm. AWD cycles continue safely between 5 cm reflood and -15 cm drying.",
        "risk_factors": "Severe drought below -15 cm inhibits internode elongation.",
        "citation": "PhilRice Module 3, p. 43; Module 7, p. 72."
    },
    "PANICLE_INITIATION_BOOTING": {
        "stage_code": "STAGE_4",
        "name": "Panicle Initiation to Booting (Stage 4)",
        "days_after_transplanting": (51, 65),
        "target_water_level_cm": (3.0, 5.0),
        "water_guideline": "CRITICAL STAGE: Keep continuously flooded at 3-5 cm depth. Suspend AWD safe drying. The plant is highly vulnerable to moisture stress.",
        "risk_factors": "Water deficit during panicle development causes high spikelet sterility and drastically reduces potential panicle size.",
        "citation": "PhilRice Module 3, p. 43; Module 7, p. 75."
    },
    "HEADING_AND_FLOWERING": {
        "stage_code": "STAGE_5_6",
        "name": "Heading and Flowering (Stages 5 & 6)",
        "days_after_transplanting": (66, 80),
        "target_water_level_cm": (3.0, 5.0),
        "water_guideline": "CRITICAL SENSITIVE STAGE: Field MUST remain continuously submerged under 3-5 cm ponded water. Zero drying allowed.",
        "risk_factors": "Drought stress at anthesis/flowering prevents pollen dehiscence and fertilization, creating whiteheads and blank grains.",
        "citation": "PhilRice Module 3, p. 44; Module 7, p. 75 (Item 5)."
    },
    "MILK_AND_DOUGH_GRAIN": {
        "stage_code": "STAGE_7_8",
        "name": "Milk and Dough Grain Ripening (Stages 7 & 8)",
        "days_after_transplanting": (81, 95),
        "target_water_level_cm": (2.0, 3.0),
        "water_guideline": "Maintain shallow 2-3 cm water or alternate wetting. Translocation of starch from leaves to grain occurs actively.",
        "risk_factors": "Complete drying too early causes chalky and shriveled grains with low milling recovery.",
        "citation": "PhilRice Module 3, p. 45; Module 7, p. 71."
    },
    "TERMINAL_DRAINAGE_AND_MATURITY": {
        "stage_code": "STAGE_9",
        "name": "Mature Grain & Terminal Drainage (Stage 9)",
        "days_after_transplanting": (96, 106),
        "target_water_level_cm": 0.0,
        "water_guideline": "TERMINAL DRAINAGE: Stop irrigation and drain all standing surface water 7 to 10 days before expected harvest. Induces uniform ripening and solidifies field ground for mechanical harvesting.",
        "risk_factors": "Standing water during harvest delays operations, causes grain discoloration, sprouting on the panicle, and increases shattering losses.",
        "citation": "PhilRice Module 3, p. 45; Module 7, Section VII.D, p. 71; Module 19, p. 189."
    }
}

NUTRIENT_MANAGEMENT_GUIDELINES: Dict[str, Any] = {
    "framework": "Integrated Nutrient Management (INM)",
    "diagnostic_tools": ["Minus-One Element Technique (MOET)", "Leaf Color Chart (LCC)", "Soil Test Kit (STK)"],
    "macronutrients": {
        "nitrogen": {
            "symbol": "N",
            "role": "Increases plant height, tillering, leaf area, and spikelet count.",
            "basal_rule": "Apply basal N only in transplanted rice if soil fertility is low (<3 t/ha unfertilized). Limit basal N to <=40 kg N/ha. Incorporate before final harrowing.",
            "split_schedule_dry_season": [
                "Split 1: Basal at final harrowing (0-14 DAT)",
                "Split 2: Mid-tillering (21-28 DAT)",
                "Split 3: Panicle Initiation (50-55 DAT)",
                "Split 4: Early flowering (optional if LCC < 4)"
            ],
            "split_schedule_wet_season": [
                "Split 1: Basal at final harrowing",
                "Split 2: Mid-tillering",
                "Split 3: Panicle Initiation"
            ],
            "leaf_color_chart_threshold": 4,
            "application_caution": "Do not topdress when leaves are wet to prevent leaf burn; avoid topdressing before heavy downpours.",
            "citation": "PhilRice Module 8, pp. 81-83."
        },
        "phosphorus": {
            "symbol": "P",
            "role": "Stimulates early root growth, tillering, and early uniform flowering.",
            "rule": "Apply 100% of P fertilizer as basal at final harrowing or early vegetative stage. P is immobile and acts as a long-term investment.",
            "citation": "PhilRice Module 8, pp. 84-85."
        },
        "potassium": {
            "symbol": "K",
            "role": "Improves lodging resistance, enhances grain filling, and provides disease resistance.",
            "rule": "Apply 50% basal at final harrowing and remaining 50% at early Panicle Initiation (EPI). Straw retention returns 80% of absorbed K.",
            "citation": "PhilRice Module 8, pp. 86-89."
        },
        "zinc": {
            "symbol": "Zn",
            "role": "Essential micronutrient; deficiency causes brown spots on older leaves, stunted tillering, and delayed maturity.",
            "rule": "Apply 10-25 kg/ha zinc sulfate within 10-14 days after transplanting, or dip seedling roots in 2% ZnO suspension.",
            "citation": "PhilRice Module 8, Section XIII, pp. 87, 89."
        }
    }
}

PEST_WEED_DISEASE_GUIDELINES: Dict[str, Any] = {
    "snails": {
        "name": "Golden Apple Snail (Pomacea canaliculata) / Golden Kuhol",
        "damage": "Voraciously feeds on succulent base of seedlings from 1 to 15 DAT.",
        "management": [
            "Maintain shallow water depth (1-2 cm) during the first 2 weeks after transplanting to restrict snail mobility.",
            "Place bamboo stakes or twigs around water inlets/bunds to attract egg clustering for manual collection.",
            "Install wire mesh screens (wire screen or nylon mesh) at irrigation canal inlets to prevent snail entry.",
            "Construct small micro-trenches along bund borders where snails concentrate during drawdown for hand collection."
        ],
        "citation": "PhilRice Module 16, pp. 166-173."
    },
    "weeds": {
        "classes": ["Grasses (Echinochloa crus-galli)", "Sedges (Cyperus difformis)", "Broadleaves (Monochoria vaginalis)"],
        "integrated_weed_management": [
            "Thorough 21-day land preparation with 5-7 day submergence to germinate and eradicate volunteer seeds.",
            "Maintain a uniform thin water blanket (2-3 cm) starting 3-4 days post-transplant; weeds cannot germinate under flooded puddle.",
            "Use mechanical rotary weeders along straight rows at 15-20 DAT and 30-35 DAT.",
            "Apply pre-emergence or early post-emergence selective herbicide under recommended ponded or saturated moisture conditions."
        ],
        "citation": "PhilRice Module 14, pp. 151-158."
    },
    "insects": {
        "yellow_stem_borer": {
            "symptoms": "'Deadheart' at vegetative stage; 'Whitehead' (empty bleached panicle) at reproductive stage.",
            "control": "Synchronous community planting; avoid excessive nitrogen fertilizer; conserve trichogramma egg parasitoids; light trapping of adult moths."
        },
        "brown_planthopper": {
            "symptoms": "'Hopperburn' - circular patches of dry brown plants due to plant sap extraction.",
            "control": "Implement AWD alternate wetting and drying; intermittent aeration disrupts nymph habitats; avoid broad-spectrum pyrethroid sprays."
        },
        "citation": "PhilRice Module 10, pp. 101-110."
    },
    "diseases": {
        "bacterial_leaf_blight": {
            "causal_agent": "Xanthomonas oryzae pv. oryzae",
            "symptoms": "Water-soaked lesions on leaf margins turning wavy yellow and gray-white.",
            "management": "Use resistant varieties (NSIC Rc 222, Rc 216); avoid over-application of nitrogen; maintain clean drainage."
        },
        "rice_blast": {
            "causal_agent": "Magnaporthe oryzae",
            "symptoms": "Spindle-shaped diamond lesions with gray center and brown margins on leaves and panicle neck.",
            "management": "Avoid dense spacing; balance NPK application; prevent prolonged drought stress."
        },
        "citation": "PhilRice Module 12, pp. 123-138."
    },
    "rats": {
        "control": "Community rat campaigns; maintain clean narrow dikes (<30 cm wide); plaster burrows; deploy Trap Barrier System (TBS) around early planted rice.",
        "citation": "PhilRice Module 15, pp. 159-165."
    }
}

HARVEST_AND_POSTHARVEST_GUIDELINES: Dict[str, Any] = {
    "harvest_maturity_indicators": [
        "80-85% of grains on the upper portion of panicles have turned yellowish/straw colored.",
        "Grains at the panicle base are in the hard dough stage.",
        "Clear, firm, and translucent hulled kernels upon grain peeling.",
        "Optimal harvest window: 28-34 days after heading (Dry Season) or 30-42 days after heading (Wet Season)."
    ],
    "threshing": [
        "Thresh immediately within 24 hours of cutting to prevent fungal development and grain discoloration ('skin drying' delays cause cracking).",
        "Axial flow mechanical threshers or foot pedal threshers minimize grain damage."
    ],
    "drying": [
        "Target moisture content: 14% or below for safe storage; 12% for long-term grain preservation.",
        "Maximum air temperature: 43.3°C for seed grain preservation; 54.4°C maximum for commercial milling.",
        "Sun drying layer: Spread palay evenly at 4-5 cm layer thickness and turn grains every 30-45 minutes."
    ],
    "storage_and_next_cycle": [
        "Store in clean, disinfected bodega on raised wooden pallets 15-20 cm above floor and away from walls.",
        "Yield recording: Measure clean dry weight (kg) per hectare to calculate yield in tons/ha.",
        "Fallow period: Maintain 30-day synchronous field rest; shallow dry tillage to mulch cracks before next cropping cycle."
    ],
    "citation": "PhilRice Training Manual (2003), Module 19, pp. 188-196."
}

def get_rice_variety_profile(variety_name: str) -> Dict[str, Any]:
    for key, val in RICE_VARIETIES.items():
        if key.lower() in variety_name.lower() or val["popular_name"].lower() in variety_name.lower():
            return val
    return RICE_VARIETIES["NSIC Rc 222"]

def get_establishment_method(method_name: str) -> Dict[str, Any]:
    norm = (method_name or "").upper().replace(" ", "_").replace("-", "_")
    if "DAPOG" in norm:
        return CROP_ESTABLISHMENT_METHODS["DAPOG"]
    elif "DIRECT" in norm or "WET_SEED" in norm or "DRUM" in norm:
        return CROP_ESTABLISHMENT_METHODS["DIRECT_WET"]
    return CROP_ESTABLISHMENT_METHODS["WETBED"]
