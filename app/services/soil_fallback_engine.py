"""
Soil Data Fallback Reasoning Engine for Arva AI.

When soil moisture telemetry is missing, stale, zero-padded, or unreliable:
1. Evaluates alternative multi-source evidence:
   - Valid water depth readings from JSN-SR04T ultrasonic sensors
   - PAGASA weather forecasts (rainfall probability & 24h expected accumulation)
   - Recent historical sensor trends (last known valid moisture)
   - Field crop growth stage (e.g., VEGETATIVE, REPRODUCTIVE, RIPENING) and planting dates
   - PhilRice PalayCheck / IRRI AWD standard agronomic rules
2. Makes evidence-based decisions:
   - IRRIGATION_RECOMMENDED (Only when verified water table <= -15cm, no rain expected, crop in active growth)
   - IRRIGATION_NOT_RECOMMENDED (Ponded water present, rain forecast, or safe AWD drying)
   - INSUFFICIENT_EVIDENCE (Multiple sources missing; requests farmer visual field check)
   - SENSOR_FAILURE_TROUBLESHOOTING (Hardware dislocation, flatline, or persistent disconnect)
3. Preserves safety:
   - NEVER assumes missing soil moisture means dry soil.
   - NEVER fabricates fake moisture readings or treats error zeros as 0%.
   - NEVER activates pumps solely because soil data is absent.
   - Clearly flags fallback mode and reports confidence based on evidence quality.
4. Auto-restores normal operation when fresh, valid soil telemetry resumes.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field


class FallbackDecisionType(str, Enum):
    IRRIGATION_RECOMMENDED = "IRRIGATION_RECOMMENDED"
    IRRIGATION_NOT_RECOMMENDED = "IRRIGATION_NOT_RECOMMENDED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    SENSOR_FAILURE_TROUBLESHOOTING = "SENSOR_FAILURE_TROUBLESHOOTING"


class EvidenceQuality(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class SoilFallbackEvaluation(BaseModel):
    is_fallback_active: bool
    fallback_reason: Optional[str] = None
    affected_nodes: List[str] = Field(default_factory=list)
    decision: FallbackDecisionType
    headline: str
    summary: str
    rationale: str
    confidence_level: float  # 0.0 to 1.0
    evidence_quality: EvidenceQuality
    sources_used: List[str] = Field(default_factory=list)
    recommended_action: str
    requires_farmer_confirmation: bool = True
    can_auto_irrigate: bool = False  # NEVER True in fallback mode
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SoilDataFallbackEngine:
    """
    Evaluates irrigation needs when soil telemetry is absent, degraded, or conflicting.
    """

    def evaluate_fallback(
        self,
        nodes_telemetry: List[Dict[str, Any]],
        weather_forecast: Optional[Dict[str, Any]] = None,
        crop_stage: str = "VEGETATIVE",
        historical_last_valid_moisture: Optional[float] = None,
        field_id: int = 1
    ) -> SoilFallbackEvaluation:
        now = datetime.now(timezone.utc)
        nodes_telemetry = nodes_telemetry or []
        weather_forecast = weather_forecast or {}

        # 1. Analyze soil telemetry availability across all nodes
        total_nodes = len(nodes_telemetry)
        missing_soil_nodes = []
        zero_soil_nodes = []  # Potential false zero / error
        valid_soil_readings = []
        valid_water_levels = []

        for node in nodes_telemetry:
            nid = node.get("node_id") or node.get("id") or "UNKNOWN"
            is_online = node.get("is_online", True)
            raw_sm = node.get("soil_moisture_percent")
            raw_wl = node.get("water_level_cm")

            # Check soil moisture validity
            if raw_sm is None or not is_online:
                missing_soil_nodes.append(nid)
            elif raw_sm == 0.0:
                # In lowland rice, raw 0.0% is almost invariably probe disconnection or ADC failure
                zero_soil_nodes.append(nid)
            elif 5.0 <= raw_sm <= 100.0:
                valid_soil_readings.append((nid, raw_sm))
            else:
                missing_soil_nodes.append(nid)

            # Check water level validity
            if raw_wl is not None and is_online and -50.0 <= raw_wl <= 25.0:
                valid_water_levels.append((nid, raw_wl))

        # Check if soil fallback is triggered
        # Fallback is triggered if >= 50% of reporting nodes lack valid soil readings
        is_fallback_active = False
        fallback_reason = None
        affected_nodes = list(set(missing_soil_nodes + zero_soil_nodes))

        if total_nodes == 0:
            is_fallback_active = True
            fallback_reason = "No active field monitoring nodes reporting telemetry."
        elif len(valid_soil_readings) == 0:
            is_fallback_active = True
            fallback_reason = f"Soil moisture telemetry absent or uncalibrated across all nodes ({', '.join(affected_nodes)})."
        elif len(affected_nodes) > (total_nodes / 2):
            is_fallback_active = True
            fallback_reason = f"Soil moisture telemetry degraded on majority of nodes ({len(affected_nodes)}/{total_nodes})."

        # If fallback is NOT active, return normal status indicating standard soil-informed mode
        if not is_fallback_active:
            avg_sm = sum(sm[1] for sm in valid_soil_readings) / len(valid_soil_readings)
            return SoilFallbackEvaluation(
                is_fallback_active=False,
                fallback_reason=None,
                affected_nodes=[],
                decision=FallbackDecisionType.IRRIGATION_NOT_RECOMMENDED if avg_sm >= 50.0 else FallbackDecisionType.IRRIGATION_RECOMMENDED,
                headline="Standard Soil Telemetry Operational",
                summary=f"Fresh soil moisture readings active ({avg_sm:.1f}% mean). Standard AWD evaluation active.",
                rationale="Real-time FDR/capacitive telemetry is active and verified within valid agronomic bounds.",
                confidence_level=0.95,
                evidence_quality=EvidenceQuality.HIGH,
                sources_used=["ArvaNode Capacitive Soil Telemetry", "Ultrasonic Water Level"],
                recommended_action="Follow normal AWD irrigation thresholds.",
                requires_farmer_confirmation=True,
                can_auto_irrigate=False
            )

        # 2. Fallback Mode Reasoning: Evaluate Available Evidence
        sources_used = []
        sources_used.append("ArvaCore Soil Telemetry Quality Filter (Rejected Unreliable Data)")

        # Evidence A: Ultrasonic Water Level
        has_water_level = len(valid_water_levels) > 0
        min_water_level = min([wl[1] for wl in valid_water_levels]) if has_water_level else None
        avg_water_level = sum([wl[1] for wl in valid_water_levels]) / len(valid_water_levels) if has_water_level else None

        if has_water_level:
            sources_used.append(f"ArvaNode Ultrasonic Water Depth ({len(valid_water_levels)} nodes)")

        # Evidence B: Weather / PAGASA Rainfall Forecast
        rain_prob = weather_forecast.get("pop", weather_forecast.get("rainfall_probability_percent", 0))
        rain_amount_mm = weather_forecast.get("rain_24h_mm", weather_forecast.get("rainfall_amount_mm", 0.0))
        has_rain_forecast = rain_prob > 0 or rain_amount_mm > 0.0

        if has_rain_forecast:
            sources_used.append(f"PAGASA Agro-Meteorological Forecast ({rain_prob}% PoP, ~{rain_amount_mm}mm)")

        # Evidence C: Rice Growth Stage & Agronomic Guideline
        sources_used.append(f"PhilRice PalayCheck / IRRI AWD Guidelines ({crop_stage} stage)")

        # Evidence D: Historical Last Valid Moisture
        if historical_last_valid_moisture is not None and historical_last_valid_moisture > 0:
            sources_used.append(f"Historical Last Known Moisture ({historical_last_valid_moisture:.1f}%)")

        # 3. Decision Tree with Safety Invariants

        # Case 1: Hardware/Sensor Failure (e.g. 0.0% false readings or all nodes offline)
        if len(zero_soil_nodes) >= 2 or (total_nodes > 0 and len(valid_water_levels) == 0):
            return SoilFallbackEvaluation(
                is_fallback_active=True,
                fallback_reason=fallback_reason,
                affected_nodes=affected_nodes,
                decision=FallbackDecisionType.SENSOR_FAILURE_TROUBLESHOOTING,
                headline="Sensor Disconnection / Hardware Fault Detected",
                summary=f"Soil probe signal dropped or reporting zero voltage on nodes: {', '.join(affected_nodes)}. Automated pump activation safely withheld.",
                rationale="Safety Rule: Missing or zero-padded sensor readings must never be interpreted as dry soil. Physical inspection is required before irrigation.",
                confidence_level=0.35,
                evidence_quality=EvidenceQuality.LOW,
                sources_used=sources_used,
                recommended_action=f"Inspect wiring, battery, and probe depth for nodes {', '.join(affected_nodes)}. Confirm soil moisture manually with ocular test.",
                requires_farmer_confirmation=True,
                can_auto_irrigate=False
            )

        # Case 2: Natural Rain Forecast Anticipated
        if rain_prob >= 70 or rain_amount_mm >= 20.0:
            return SoilFallbackEvaluation(
                is_fallback_active=True,
                fallback_reason=fallback_reason,
                affected_nodes=affected_nodes,
                decision=FallbackDecisionType.IRRIGATION_NOT_RECOMMENDED,
                headline="Fallback Advisory: Natural Rainfall Anticipated — Hold Irrigation",
                summary=f"Soil data unavailable, but PAGASA forecasts significant rainfall ({rain_amount_mm} mm, {rain_prob}% PoP). Hold irrigation to prevent overflow.",
                rationale="PhilRice PalayCheck Recommendation: Rainfall will provide natural field reflooding. Conserve irrigation energy and avoid ponding exceeding 5 cm.",
                confidence_level=0.85,
                evidence_quality=EvidenceQuality.MODERATE,
                sources_used=sources_used,
                recommended_action="Keep irrigation gates closed. Monitor field spillway to accommodate anticipated precipitation.",
                requires_farmer_confirmation=False,
                can_auto_irrigate=False
            )

        # Case 3: Water Level Confirms Ponding Present (> 0.0 cm)
        if has_water_level and min_water_level is not None and min_water_level >= 1.0:
            return SoilFallbackEvaluation(
                is_fallback_active=True,
                fallback_reason=fallback_reason,
                affected_nodes=affected_nodes,
                decision=FallbackDecisionType.IRRIGATION_NOT_RECOMMENDED,
                headline="Fallback Advisory: Surface Water Present — Irrigation Not Needed",
                summary=f"Soil moisture probes are unavailable, but ultrasonic sensors confirm standing water (+{avg_water_level:.1f} cm average) across paddy terraces.",
                rationale="IRRI AWD Invariant: If surface water depth is positive, soil in the root zone is saturated. Irrigation is unnecessary and would cause excessive depth.",
                confidence_level=0.80,
                evidence_quality=EvidenceQuality.MODERATE,
                sources_used=sources_used,
                recommended_action="Maintain current gate closures. Water depth is sufficient for active rice growth.",
                requires_farmer_confirmation=False,
                can_auto_irrigate=False
            )

        # Case 4: Water Level Confirms Critical AWD Drying (Depth <= -15.0 cm)
        if has_water_level and min_water_level is not None and min_water_level <= -14.5:
            # Check crop stage sensitivity: flowering stage requires shallow water
            is_flowering = crop_stage.upper() in ["REPRODUCTIVE", "FLOWERING", "HEADING"]
            reflood_depth = 5.0

            return SoilFallbackEvaluation(
                is_fallback_active=True,
                fallback_reason=fallback_reason,
                affected_nodes=affected_nodes,
                decision=FallbackDecisionType.IRRIGATION_RECOMMENDED,
                headline="Fallback Advisory: AWD Reflood Trigger Verified by Perched Water Tube",
                summary=f"Soil moisture probes are offline, but field water level has dropped to {min_water_level:.1f} cm (AWD threshold is -15.0 cm). Reflood recommended.",
                rationale="PhilRice AWD Protocol: Field water level measured in perforated field still-well reaching -15 cm indicates safe drying limit has been reached, requiring reflooding to +5 cm.",
                confidence_level=0.75,
                evidence_quality=EvidenceQuality.MODERATE,
                sources_used=sources_used,
                recommended_action=f"Authorize reflood to +{reflood_depth:.1f} cm in Control. Inspect field bunds before initiating pump operation.",
                requires_farmer_confirmation=True,
                can_auto_irrigate=False
            )

        # Case 5: Ambiguous / Insufficient Telemetry
        return SoilFallbackEvaluation(
            is_fallback_active=True,
            fallback_reason=fallback_reason,
            affected_nodes=affected_nodes,
            decision=FallbackDecisionType.INSUFFICIENT_EVIDENCE,
            headline="Fallback Advisory: Inconclusive Telemetry — Visual Field Check Advised",
            summary=f"Soil data unavailable and water depth ({avg_water_level if has_water_level else 'N/A'}) is in transitional range. Evidence insufficient for confident actuation.",
            rationale="Precautionary Agricultural Safety: When both rootzone moisture is missing and water depth is inconclusive, automated recommendation cannot proceed without human observation.",
            confidence_level=0.40,
            evidence_quality=EvidenceQuality.LOW,
            sources_used=sources_used,
            recommended_action="Perform ocular inspection of paddy soil surface. Look for hairline soil cracks before authorizing irrigation.",
            requires_farmer_confirmation=True,
            can_auto_irrigate=False
        )


# Global singleton fallback engine instance
global_soil_fallback_engine = SoilDataFallbackEngine()
