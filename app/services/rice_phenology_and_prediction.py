"""
Intelligent Rice Cultivation Stage Tracker & Predictive AWD Depletion Engine.
Authoritative grounding:
- PhilRice Philippine Rice Production Training Manual (2003)
- IRRI Alternate Wetting and Drying (AWD) Technical Guidelines
- DA-PhilRice PalayCheck System: 9 Key Checks for Irrigated Lowland Rice

Provides:
1. Dynamic Rice Growth Stage Tracking from planting date & variety maturity.
2. Predictive AWD drying depletion projection (days remaining until -15.0 cm critical threshold).
3. Weather-aware irrigation recommendation & risk prediction (typhoons, high winds, lodging).
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from app.services.philrice_rice_knowledge import (
    RICE_VARIETIES,
    RICE_GROWTH_STAGES_AND_WATER,
    get_rice_variety_profile
)

class RicePhenologyAndPredictionEngine:
    def __init__(self):
        pass

    def determine_growth_stage(
        self,
        variety_name: str,
        days_after_transplanting: Optional[int] = None,
        planting_date_iso: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Determines current rice phenological stage, water requirements, and AWD eligibility.
        """
        variety_profile = get_rice_variety_profile(variety_name)
        maturity_days = variety_profile.get("maturity_days", 106)

        dat = 0
        if days_after_transplanting is not None:
            dat = max(0, days_after_transplanting)
        elif planting_date_iso:
            try:
                # Parse ISO date
                p_date = datetime.fromisoformat(planting_date_iso.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                diff = (now - p_date).days
                dat = max(0, diff)
            except Exception:
                dat = 0

        # Map DAT to phenological stage
        if dat <= 7:
            stage_key = "TRANSPLANTING_RECOVERY"
            is_awd_allowed = False
            awd_reason = "Recovery & rooting: Maintain shallow 1-2 cm water depth to suppress snails and establish root contact."
        elif dat <= 35:
            stage_key = "TILLERING_VEGETATIVE"
            is_awd_allowed = True
            awd_reason = "Active vegetative tillering: AWD safe drying down to -15.0 cm promotes deep root anchorage."
        elif dat <= 50:
            stage_key = "STEM_ELONGATION"
            is_awd_allowed = True
            awd_reason = "Stem elongation: AWD safe drying continues between +5.0 cm and -15.0 cm."
        elif dat <= 65:
            stage_key = "PANICLE_INITIATION_BOOTING"
            is_awd_allowed = False
            awd_reason = "CRITICAL REPRODUCTIVE STAGE: Panicle development underway. Maintain continuous 3-5 cm ponding. Moisture stress causes spikelet sterility."
        elif dat <= 80:
            stage_key = "HEADING_AND_FLOWERING"
            is_awd_allowed = False
            awd_reason = "CRITICAL FLOWERING STAGE: Anthesis and fertilization active. Continuous 3-5 cm ponding required. Zero drying permitted."
        elif dat <= 95:
            stage_key = "MILK_AND_DOUGH_GRAIN"
            is_awd_allowed = True
            awd_reason = "Grain filling: Shallow 2-3 cm or gentle alternate wetting permitted until dough stage."
        else:
            stage_key = "TERMINAL_DRAINAGE_AND_MATURITY"
            is_awd_allowed = False
            awd_reason = "TERMINAL DRAINAGE: Stop irrigation and drain standing water completely 7-10 days before harvest to solidify soil and promote uniform ripening."

        stage_info = RICE_GROWTH_STAGES_AND_WATER.get(stage_key, RICE_GROWTH_STAGES_AND_WATER["TILLERING_VEGETATIVE"])

        return {
            "variety": variety_profile.get("popular_name", variety_name),
            "maturity_days": maturity_days,
            "days_after_transplanting": dat,
            "stage_key": stage_key,
            "stage_name": stage_info["name"],
            "target_water_level_cm": stage_info["target_water_level_cm"],
            "water_guideline": stage_info["water_guideline"],
            "risk_factors": stage_info["risk_factors"],
            "is_awd_allowed": is_awd_allowed,
            "awd_guideline": awd_reason,
            "citation": stage_info["citation"]
        }

    def predict_awd_drying_window(
        self,
        current_water_level_cm: float,
        evapotranspiration_rate_cm_per_day: float = 1.2,
        forecast_rain_mm_3days: float = 0.0,
        safe_drying_limit_cm: float = -15.0
    ) -> Dict[str, Any]:
        """
        Calculates drying rate and projects hours/days until field hits critical -15.0 cm AWD threshold.
        """
        # Net drying rate factoring rainfall (10 mm rain ~ +1.0 cm water depth)
        daily_rain_cm = (forecast_rain_mm_3days / 3.0) / 10.0
        effective_drying_rate_cm_day = max(0.1, evapotranspiration_rate_cm_per_day - daily_rain_cm)

        if current_water_level_cm <= safe_drying_limit_cm:
            return {
                "current_water_level_cm": current_water_level_cm,
                "safe_drying_limit_cm": safe_drying_limit_cm,
                "status": "THRESHOLD_BREACHED",
                "days_remaining_to_threshold": 0.0,
                "hours_remaining_to_threshold": 0.0,
                "action_recommended": "REFLOOD_REQUIRED",
                "urgency": "IMMEDIATE",
                "drying_rate_cm_day": effective_drying_rate_cm_day,
                "explanation": f"Water level has breached safe drying limit ({current_water_level_cm:.1f} cm <= {safe_drying_limit_cm:.1f} cm). Prompt reflooding to +5.0 cm recommended to prevent root stress."
            }

        # Calculate time to reach safe_drying_limit_cm
        water_depth_distance = current_water_level_cm - safe_drying_limit_cm
        days_remaining = water_depth_distance / effective_drying_rate_cm_day
        hours_remaining = days_remaining * 24.0

        urgency = "LOW"
        action = "CONTINUE_SAFE_DRYING"
        if days_remaining <= 1.0:
            urgency = "HIGH"
            action = "PREPARE_REFLOOD"
        elif days_remaining <= 2.5:
            urgency = "MODERATE"
            action = "MONITOR_PERCOLATION"

        return {
            "current_water_level_cm": current_water_level_cm,
            "safe_drying_limit_cm": safe_drying_limit_cm,
            "status": "SAFE_DRYING_IN_PROGRESS",
            "days_remaining_to_threshold": round(days_remaining, 1),
            "hours_remaining_to_threshold": round(hours_remaining, 1),
            "action_recommended": action,
            "urgency": urgency,
            "drying_rate_cm_day": round(effective_drying_rate_cm_day, 2),
            "explanation": (
                f"Perched water level is at {current_water_level_cm:+.1f} cm. "
                f"At current percolation & evapotranspiration rate ({effective_drying_rate_cm_day:.1f} cm/day), "
                f"the field is projected to reach the AWD -15.0 cm reflood trigger in approximately {days_remaining:.1f} days ({hours_remaining:.0f} hours)."
            )
        }

    def evaluate_weather_hazards(
        self,
        crop_stage_key: str,
        max_wind_kmh: float,
        rainfall_24h_mm: float,
        active_cyclone_signal: int
    ) -> List[Dict[str, Any]]:
        """
        Identifies weather hazards specific to rice growth stages (e.g., lodging, washouts, flower sterility).
        """
        hazards = []

        if active_cyclone_signal > 0:
            hazards.append({
                "severity": "CRITICAL",
                "hazard_type": "TROPICAL_CYCLONE",
                "message": f"PAGASA Tropical Cyclone Signal #{active_cyclone_signal} is active. Suspend all automated irrigation and clear field drainage spillways."
            })

        if rainfall_24h_mm >= 30.0:
            hazards.append({
                "severity": "WARNING",
                "hazard_type": "HEAVY_RAINFALL",
                "message": f"Heavy rainfall forecast ({rainfall_24h_mm:.1f} mm/24h). Automated pump irrigation suspended to avoid nutrient runoff and bund erosion."
            })

        if max_wind_kmh >= 45.0:
            if crop_stage_key in ["HEADING_AND_FLOWERING", "MILK_AND_DOUGH_GRAIN", "TERMINAL_DRAINAGE_AND_MATURITY"]:
                hazards.append({
                    "severity": "HIGH",
                    "hazard_type": "LODGING_RISK",
                    "message": f"Strong winds ({max_wind_kmh:.0f} km/h) threaten lodging in mature/flowering rice. Lower standing water to 1-2 cm to reduce plant buoyancy and strengthen root grip."
                })

        return hazards

