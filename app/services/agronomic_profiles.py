"""
Agronomic knowledge base and crop requirement profiles for Arva AI Farming Chatbot.
Traceable references: IRRI AWD Technical Guidelines, DA-PhilRice Varietal Guides, BSWM.
Enforces rice-only crop profiles (PhilRice PalayCheck System).
"""

from typing import Dict, Any, List
from app.services.philrice_rice_knowledge import (
    RICE_VARIETIES,
    CROP_ESTABLISHMENT_METHODS,
    RICE_GROWTH_STAGES_AND_WATER,
    NUTRIENT_MANAGEMENT_GUIDELINES,
    PEST_WEED_DISEASE_GUIDELINES,
    HARVEST_AND_POSTHARVEST_GUIDELINES,
    get_rice_variety_profile,
    get_establishment_method,
)

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
            "PhilRice Philippine Rice Production Training Manual (2003)",
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
                    "title": "Plowing and Primary Harrowing (T-21 Days)",
                    "description": "Incorporate weeds and stubble at 15-20 cm depth to break hardpan and improve puddling.",
                    "requires_confirmation": False
                },
                {
                    "title": "Perimeter Bund Repair & Sealing",
                    "description": "Plaster perimeter bunds with mud to prevent water leakage during drying cycles.",
                    "requires_confirmation": False
                },
                {
                    "title": "First Harrowing and Residue Decomposition (T-14 Days)",
                    "description": "Pass comb-tooth harrow along plowing pattern after 5-7 days of soil submergence.",
                    "requires_confirmation": False
                },
                {
                    "title": "Second Harrowing (T-7 Days)",
                    "description": "Crosswise harrowing to eradicate sprouted weeds and puddle topsoil thoroughly.",
                    "requires_confirmation": False
                },
                {
                    "title": "Field Leveling with Wooden Plank (T-1 Day)",
                    "description": "Ensure uniform water distribution so no high spots dry prematurely or harbor snails.",
                    "requires_confirmation": False
                }
            ],
            "equipment_info": [
                {
                    "title": "Certified Seed Germination Test (>85%)",
                    "description": "Confirm seed germination rate is >85% before seedbed establishment.",
                    "requires_confirmation": False
                },
                {
                    "title": "Seedbed Preparation & 24h Soaking / 24-36h Incubation",
                    "description": "Submerge seeds in water 24h, incubate on slotted wooden pallets for 24-36h.",
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
    "nsic_rc_160": {
        "canonical_name": "Lowland Rice (NSIC Rc 160)",
        "variety": "NSIC Rc 160 (Tubigan 14)",
        "family": "Poaceae",
        "category": "CEREAL",
        "optimal_temperature_min": 22.0,
        "optimal_temperature_max": 33.0,
        "water_management": "Alternate Wetting and Drying (AWD)",
        "safe_drying_limit_cm": -15.0,
        "reflood_depth_cm": 5.0,
        "presoak_water_layer_cm": 3.0,
        "critical_flowering_depth_cm": 3.0,
        "maturity_days": 107,
        "references": [
            "PhilRice Philippine Rice Production Training Manual (2003)",
            "IRRI Alternate Wetting and Drying (AWD) Technical Protocol (2020)",
            "DA-PhilRice NSIC Rc 160 Management Guide (2023)",
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
                    "title": "Plowing and Primary Harrowing (T-21 Days)",
                    "description": "Incorporate weeds and stubble at 15-20 cm depth to break hardpan and improve puddling.",
                    "requires_confirmation": False
                },
                {
                    "title": "Perimeter Bund Repair & Sealing",
                    "description": "Plaster perimeter bunds with mud to prevent water leakage during drying cycles.",
                    "requires_confirmation": False
                },
                {
                    "title": "First Harrowing and Residue Decomposition (T-14 Days)",
                    "description": "Pass comb-tooth harrow along plowing pattern after 5-7 days of soil submergence.",
                    "requires_confirmation": False
                },
                {
                    "title": "Second Harrowing (T-7 Days)",
                    "description": "Crosswise harrowing to eradicate sprouted weeds and puddle topsoil thoroughly.",
                    "requires_confirmation": False
                },
                {
                    "title": "Field Leveling with Wooden Plank (T-1 Day)",
                    "description": "Ensure uniform water distribution so no high spots dry prematurely or harbor snails.",
                    "requires_confirmation": False
                }
            ],
            "equipment_info": [
                {
                    "title": "Certified Seed Germination Test (>85%)",
                    "description": "Confirm seed germination rate is >85% for NSIC Rc 160 before seedbed establishment.",
                    "requires_confirmation": False
                },
                {
                    "title": "Seedbed Preparation & 24h Soaking / 24-36h Incubation",
                    "description": "Submerge seeds in water 24h, incubate on slotted wooden pallets for 24-36h.",
                    "requires_confirmation": False
                }
            ]
        }
    },
    "psb_rc_82": {
        "canonical_name": "Lowland Rice (PSB Rc 82)",
        "variety": "PSB Rc 82 (Peñaranda)",
        "family": "Poaceae",
        "category": "CEREAL",
        "optimal_temperature_min": 22.0,
        "optimal_temperature_max": 33.0,
        "water_management": "Alternate Wetting and Drying (AWD)",
        "safe_drying_limit_cm": -15.0,
        "reflood_depth_cm": 5.0,
        "presoak_water_layer_cm": 3.0,
        "critical_flowering_depth_cm": 3.0,
        "maturity_days": 110,
        "references": [
            "PhilRice Philippine Rice Production Training Manual (2003)",
            "IRRI Alternate Wetting and Drying (AWD) Technical Protocol (2020)",
            "PhilRice PSB Rc 82 Varietal Profile"
        ],
        "standard_tasks": {
            "system_automated": [
                {
                    "title": "Pre-Irrigation Land Soaking",
                    "description": "Deliver controlled 3.0 cm perched water layer across terrace zones via ArvaCore automated valves.",
                    "requires_confirmation": True
                }
            ],
            "farmer_manual": [
                {
                    "title": "Plowing and Primary Harrowing (T-21 Days)",
                    "description": "Incorporate weeds and stubble at 15-20 cm depth.",
                    "requires_confirmation": False
                },
                {
                    "title": "Perimeter Bund Repair & Sealing",
                    "description": "Plaster perimeter bunds with mud to prevent water leakage.",
                    "requires_confirmation": False
                }
            ],
            "equipment_info": [
                {
                    "title": "Certified Seed Germination Test (>85%)",
                    "description": "Confirm seed germination rate is >85% before seedbed establishment.",
                    "requires_confirmation": False
                }
            ]
        }
    },
    "nsic_rc_216": {
        "canonical_name": "Lowland Rice (NSIC Rc 216)",
        "variety": "NSIC Rc 216 (Tubigan 17)",
        "family": "Poaceae",
        "category": "CEREAL",
        "optimal_temperature_min": 22.0,
        "optimal_temperature_max": 33.0,
        "water_management": "Alternate Wetting and Drying (AWD)",
        "safe_drying_limit_cm": -15.0,
        "reflood_depth_cm": 5.0,
        "presoak_water_layer_cm": 3.0,
        "critical_flowering_depth_cm": 3.0,
        "maturity_days": 112,
        "references": [
            "PhilRice Philippine Rice Production Training Manual (2003)",
            "IRRI Alternate Wetting and Drying (AWD) Technical Protocol (2020)",
            "PhilRice NSIC Rc 216 Varietal Profile"
        ],
        "standard_tasks": {
            "system_automated": [
                {
                    "title": "Pre-Irrigation Land Soaking",
                    "description": "Deliver controlled 3.0 cm perched water layer across terrace zones via ArvaCore automated valves.",
                    "requires_confirmation": True
                }
            ],
            "farmer_manual": [
                {
                    "title": "Plowing and Primary Harrowing (T-21 Days)",
                    "description": "Incorporate weeds and stubble at 15-20 cm depth.",
                    "requires_confirmation": False
                }
            ],
            "equipment_info": [
                {
                    "title": "Certified Seed Germination Test (>85%)",
                    "description": "Confirm seed germination rate is >85% before seedbed establishment.",
                    "requires_confirmation": False
                }
            ]
        }
    }
}

def get_crop_profile(crop_input: str) -> Dict[str, Any]:
    """
    Returns the authoritative rice crop profile.
    Arva AI strictly enforces Philippine rice cultivation under the PhilRice PalayCheck System.
    """
    query = (crop_input or "").lower()
    if "160" in query:
        return CROP_PROFILES["nsic_rc_160"]
    elif "82" in query:
        return CROP_PROFILES["psb_rc_82"]
    elif "216" in query:
        return CROP_PROFILES["nsic_rc_216"]
    return CROP_PROFILES["rice"]
