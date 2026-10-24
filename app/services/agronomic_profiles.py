"""
Agronomic knowledge base and crop requirement profiles for Arva AI Farming Chatbot.
Traceable references: IRRI AWD Technical Guidelines, DA-PhilRice Varietal Guides, BSWM.
"""

from typing import Dict, Any, List

CROP_PROFILES: Dict[str, Dict[str, Any]] = {
    "rice": {
        "canonical_name": "Lowland Rice (NSIC Rc 222)",
        "variety": "NSIC Rc 222 (Tubigan 21)",
        "family": "Poaceae",
        "category": "CEREAL",
        "optimal_temperature_min": 22.0,
        "optimal_temperature_max": 33.0,
        "water_management": "Alternate Wetting and Drying (AWD)",
        "safe_drying_limit_cm": -15.0,
        "reflood_depth_cm": 5.0,
        "presoak_water_layer_cm": 3.0,
        "critical_flowering_depth_cm": 3.0,
        "maturity_days": 106,
        "references": [
            "IRRI Alternate Wetting and Drying (AWD) Technical Protocol (2020)",
            "DA-PhilRice NSIC Rc 222 Management Guide (2023)",
            "Philippine Rice Research Institute (PhilRice) PalayCheck System"
        ],
        "standard_tasks": {
            "system_automated": [
                {
                    "title": "Pre-Irrigation Land Soaking",
                    "description": "Deliver controlled 3.0 cm perched water layer across terrace zones via ArvaCore automated valves.",
                    "requires_confirmation": True
                },
                {
                    "title": "Ultrasonic Perched Water Zero-Point Calibration",
                    "description": "Calibrate ultrasonic sensor baseline relative to field mud line across all 6 ArvaNodes.",
                    "requires_confirmation": False
                }
            ],
            "farmer_manual": [
                {
                    "title": "Plowing and Primary Harrowing",
                    "description": "Incorporate weeds and stubble at 15-20 cm depth to break hardpan and improve puddling.",
                    "requires_confirmation": False
                },
                {
                    "title": "Perimeter Bund Repair & Sealing",
                    "description": "Plaster perimeter bunds with mud to prevent water leakage during drying cycles.",
                    "requires_confirmation": False
                },
                {
                    "title": "Field Leveling",
                    "description": "Ensure uniform water distribution so no high spots dry prematurely.",
                    "requires_confirmation": False
                }
            ],
            "equipment_info": [
                {
                    "title": "Certified Seed Germination Test",
                    "description": "Confirm seed germination rate is >85% before seedbed establishment.",
                    "requires_confirmation": False
                },
                {
                    "title": "Tractor / Hand Rotavator Availability",
                    "description": "Verify availability of rotavator equipment for secondary puddling.",
                    "requires_confirmation": False
                }
            ]
        }
    },
    "corn": {
        "canonical_name": "Hybrid Yellow Corn",
        "variety": "Yellow Hybrid (Pioneer/Dekalb)",
        "family": "Poaceae",
        "category": "GRAIN",
        "optimal_temperature_min": 20.0,
        "optimal_temperature_max": 32.0,
        "water_management": "Furrow / Drip (Aerated Soil)",
        "safe_drying_limit_cm": 0.0,
        "target_soil_moisture_min": 50.0,
        "target_soil_moisture_max": 75.0,
        "maturity_days": 115,
        "references": [
            "DA-BAR Corn Production Guide (2022)",
            "FAO Irrigation and Drainage Paper 56: Crop Evapotranspiration"
        ],
        "standard_tasks": {
            "system_automated": [
                {
                    "title": "Pre-Planting Moisture Top-Up",
                    "description": "Light automated furrow wetting to achieve 60% soil moisture field capacity.",
                    "requires_confirmation": True
                }
            ],
            "farmer_manual": [
                {
                    "title": "Deep Plowing and Furrow Construction",
                    "description": "Prepare 75 cm spaced furrows to promote taproot aeration.",
                    "requires_confirmation": False
                },
                {
                    "title": "Basal Fertilizer Application",
                    "description": "Apply complete fertilizer (14-14-14) along planting rows.",
                    "requires_confirmation": False
                }
            ],
            "equipment_info": [
                {
                    "title": "Corn Planter / Seed Drill Calibration",
                    "description": "Verify seed drop rate of 2 seeds per hill at 20 cm spacing.",
                    "requires_confirmation": False
                }
            ]
        }
    },
    "eggplant": {
        "canonical_name": "Eggplant (Dumaguete Long Purple)",
        "variety": "Dumaguete Long Purple",
        "family": "Solanaceae",
        "category": "VEGETABLE",
        "optimal_temperature_min": 22.0,
        "optimal_temperature_max": 32.0,
        "water_management": "Bed / Furrow Irrigated",
        "safe_drying_limit_cm": 0.0,
        "target_soil_moisture_min": 55.0,
        "target_soil_moisture_max": 80.0,
        "maturity_days": 90,
        "references": [
            "PCARRD Vegetable Production Guide: Eggplant",
            "East-West Seed Solanaceous Management Standard"
        ],
        "standard_tasks": {
            "system_automated": [
                {
                    "title": "Raised Bed Drip Line Pressure Test",
                    "description": "Check emitter uniformity and line pressure across all zone manifolds.",
                    "requires_confirmation": True
                }
            ],
            "farmer_manual": [
                {
                    "title": "Raised Bed Formation and Plastic Mulching",
                    "description": "Construct 1-meter wide raised beds and install silver-black mulch.",
                    "requires_confirmation": False
                },
                {
                    "title": "Seedling Hardening",
                    "description": "Withhold water 5 days prior to transplanting 30-day-old seedlings.",
                    "requires_confirmation": False
                }
            ],
            "equipment_info": [
                {
                    "title": "Trellis Bamboo Poles and Twine",
                    "description": "Prepare 1.5m bamboo stakes for plant support against lodging.",
                    "requires_confirmation": False
                }
            ]
        }
    }
}

def get_crop_profile(crop_input: str) -> Dict[str, Any]:
    query = (crop_input or "").lower()
    if any(k in query for k in ["rice", "palay", "nsic", "tubigan"]):
        return CROP_PROFILES["rice"]
    elif any(k in query for k in ["corn", "maize", "mais"]):
        return CROP_PROFILES["corn"]
    elif any(k in query for k in ["eggplant", "talong"]):
        return CROP_PROFILES["eggplant"]
    return CROP_PROFILES["rice"]

