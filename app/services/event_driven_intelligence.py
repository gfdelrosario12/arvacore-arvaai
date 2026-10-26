"""
Arva AI Event-Driven Agronomic Intelligence Engine.
Evaluates real-time farm events, telemetry changes, anomalies, weather forecasts,
and rice growth stages to generate prioritized advisories and dynamic, context-aware suggested questions.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

class FarmEvent:
    def __init__(
        self,
        event_type: str,
        severity: str,
        summary: str,
        field_id: int = 1,
        node_id: Optional[str] = None,
        zone_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ):
        self.event_type = event_type  # e.g., 'WATER_LEVEL_DROP', 'WATER_LEVEL_EXCESS', 'SOIL_DRYING', 'SENSOR_STALE', 'PUMP_ACTIVE', 'RAIN_FORECAST', 'IRRIGATION_BLOCKED'
        self.severity = severity      # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
        self.summary = summary
        self.field_id = field_id
        self.node_id = node_id
        self.zone_code = zone_code
        self.details = details or {}
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "severity": self.severity,
            "summary": self.summary,
            "field_id": self.field_id,
            "node_id": self.node_id,
            "zone_code": self.zone_code,
            "details": self.details,
            "timestamp": self.timestamp.isoformat()
        }


class EventDrivenArvaEngine:
    """
    Evaluates real-time telemetry, historical trends, and farm state
    to produce deduplicated event-driven advisories and contextual questions.
    """

    def __init__(self, cooldown_minutes: int = 10):
        self.cooldown_minutes = cooldown_minutes
        self._last_event_timestamps: Dict[str, datetime] = {}

    def analyze_farm_state(
        self,
        nodes_telemetry: List[Dict[str, Any]],
        zones: List[Dict[str, Any]],
        weather_forecast: Optional[Dict[str, Any]] = None,
        is_pump_running: bool = False,
        is_estop_active: bool = False,
        crop_stage: str = "VEGETATIVE",
        field_id: int = 1
    ) -> Dict[str, Any]:
        """
        Processes farm data, detects significant events, and returns:
        1. active_events: List of detected FarmEvents
        2. primary_advisory: Grounded advisory object for Home & Sensors
        3. dynamic_questions: Context-aware questions for Arva Chat & Sensors
        """
        events: List[FarmEvent] = []
        now = datetime.now(timezone.utc)

        # 1. Safety Blocked & E-Stop Interlock Check
        if is_estop_active:
            events.append(FarmEvent(
                event_type="IRRIGATION_BLOCKED",
                severity="CRITICAL",
                summary="Physical Emergency Stop is active. Automated and manual pump commands are physically interlocked.",
                field_id=field_id
            ))

        # 2. Check Stale Telemetry & Missing Nodes
        stale_nodes = []
        offline_nodes = []
        valid_water_levels = []
        valid_moistures = []

        for node in nodes_telemetry:
            nid = node.get("node_id") or node.get("id") or "UNKNOWN"
            is_online = node.get("is_online", False)
            last_seen_iso = node.get("last_seen") or node.get("last_seen_at") or node.get("last_telemetry_at")
            
            if not is_online:
                offline_nodes.append(nid)
            elif last_seen_iso:
                try:
                    last_seen_dt = datetime.fromisoformat(str(last_seen_iso).replace("Z", "+00:00"))
                    age_min = (now - last_seen_dt).total_seconds() / 60.0
                    if age_min >= 15:
                        stale_nodes.append((nid, age_min))
                except Exception:
                    pass

            wl = node.get("water_level_cm")
            sm = node.get("soil_moisture_percent")
            if wl is not None:
                valid_water_levels.append((nid, float(wl), node.get("zone_code") or node.get("assigned_zone_code")))
            if sm is not None:
                valid_moistures.append((nid, float(sm), node.get("zone_code") or node.get("assigned_zone_code")))

        if offline_nodes:
            events.append(FarmEvent(
                event_type="NODE_OFFLINE",
                severity="HIGH",
                summary=f"{len(offline_nodes)} monitoring node(s) offline ({', '.join(offline_nodes[:3])}). Telemetry coverage degraded.",
                field_id=field_id,
                details={"offline_nodes": offline_nodes}
            ))

        if stale_nodes:
            events.append(FarmEvent(
                event_type="SENSOR_STALE",
                severity="MEDIUM",
                summary=f"{len(stale_nodes)} monitoring node(s) reporting delayed telemetry (>15 min).",
                field_id=field_id,
                details={"stale_nodes": [s[0] for s in stale_nodes]}
            ))

        # 3. Water Level Dynamics (PhilRice & IRRI AWD Thresholds)
        # Rice Vegetative / AWD standard: safe depth between 2.0 cm and 5.0 cm, reflood trigger when water drops below mudline (-15 cm or < 0 cm in pond)
        if valid_water_levels:
            depths = [w[1] for w in valid_water_levels]
            min_depth = min(depths)
            max_depth = max(depths)
            avg_depth = sum(depths) / len(depths)

            # Check for excessive water depth (> 10.0 cm)
            if max_depth > 10.0:
                excess_nodes = [w[0] for w in valid_water_levels if w[1] > 10.0]
                events.append(FarmEvent(
                    event_type="WATER_LEVEL_EXCESS",
                    severity="MEDIUM",
                    summary=f"Excessive water ponding ({max_depth:.1f} cm) detected at {', '.join(excess_nodes)}. Suppresses active rice tillering.",
                    field_id=field_id,
                    details={"max_depth_cm": max_depth, "nodes": excess_nodes}
                ))
            # Check for falling / low water level needing AWD replenishment
            elif min_depth < 0.0 or (min_depth < 2.0 and crop_stage == "VEGETATIVE"):
                low_nodes = [w[0] for w in valid_water_levels if w[1] < 2.0]
                events.append(FarmEvent(
                    event_type="WATER_LEVEL_DROP",
                    severity="HIGH",
                    summary=f"Paddy water level has reached low threshold ({min_depth:.1f} cm) at {', '.join(low_nodes)}. Irrigation replenishment required.",
                    field_id=field_id,
                    details={"min_depth_cm": min_depth, "nodes": low_nodes}
                ))

            # Check for conflicting node readings (e.g. difference > 8 cm across terraces)
            if (max_depth - min_depth) >= 8.0:
                events.append(FarmEvent(
                    event_type="READINGS_CONFLICT",
                    severity="MEDIUM",
                    summary=f"Significant spatial variance across paddy terraces: {min_depth:.1f} cm to {max_depth:.1f} cm ({max_depth - min_depth:.1f} cm delta).",
                    field_id=field_id,
                    details={"min_depth": min_depth, "max_depth": max_depth, "delta": max_depth - min_depth}
                ))

        # 4. Soil Moisture Checks
        if valid_moistures:
            moisture_vals = [m[1] for m in valid_moistures]
            min_moisture = min(moisture_vals)
            if min_moisture < 50.0:
                events.append(FarmEvent(
                    event_type="SOIL_DRYING",
                    severity="HIGH",
                    summary=f"Critical rootzone desiccation ({min_moisture:.1f}% moisture) detected. Field requires immediate irrigation replenishment.",
                    field_id=field_id,
                    details={"min_moisture": min_moisture}
                ))

        # 5. Weather Forecast Interaction (PAGASA rain forecast)
        has_upcoming_heavy_rain = False
        if weather_forecast:
            rain_prob = weather_forecast.get("rainfall_probability_percent", 0)
            rain_amount = weather_forecast.get("rainfall_amount_mm", 0.0)
            if rain_prob >= 70 or rain_amount >= 15.0:
                has_upcoming_heavy_rain = True
                events.append(FarmEvent(
                    event_type="RAIN_FORECAST",
                    severity="MEDIUM",
                    summary=f"PAGASA agro-meteorological advisory: High rain probability ({rain_prob}%, ~{rain_amount:.1f} mm expected). Adjust irrigation schedule.",
                    field_id=field_id,
                    details={"rain_prob": rain_prob, "rain_amount_mm": rain_amount}
                ))

        # 6. Irrigation Running State
        if is_pump_running:
            events.append(FarmEvent(
                event_type="PUMP_ACTIVE",
                severity="LOW",
                summary="Central field irrigation pump is actively delivering water.",
                field_id=field_id
            ))

        # Deduplicate & cooldown events
        filtered_events = self._filter_cooldown_events(events, now)

        # Determine Primary Advisory & Dynamic Questions
        primary_advisory = self._build_primary_advisory(
            events=filtered_events,
            valid_water_levels=valid_water_levels,
            valid_moistures=valid_moistures,
            is_pump_running=is_pump_running,
            is_estop_active=is_estop_active,
            has_upcoming_heavy_rain=has_upcoming_heavy_rain,
            crop_stage=crop_stage
        )

        dynamic_questions = self.generate_dynamic_questions(
            events=filtered_events,
            valid_water_levels=valid_water_levels,
            valid_moistures=valid_moistures,
            has_upcoming_heavy_rain=has_upcoming_heavy_rain,
            is_pump_running=is_pump_running,
            is_estop_active=is_estop_active,
            stale_nodes=[s[0] for s in stale_nodes],
            offline_nodes=offline_nodes,
            crop_stage=crop_stage
        )

        return {
            "timestamp": now.isoformat(),
            "field_id": field_id,
            "crop_stage": crop_stage,
            "active_events": [e.to_dict() for e in filtered_events],
            "primary_advisory": primary_advisory,
            "dynamic_questions": dynamic_questions
        }

    def _filter_cooldown_events(self, events: List[FarmEvent], now: datetime) -> List[FarmEvent]:
        filtered = []
        for ev in events:
            key = f"{ev.field_id}_{ev.event_type}"
            last_ts = self._last_event_timestamps.get(key)
            # Critical events always pass through; otherwise respect cooldown
            if ev.severity == "CRITICAL" or not last_ts or (now - last_ts).total_seconds() >= (self.cooldown_minutes * 60):
                self._last_event_timestamps[key] = now
                filtered.append(ev)
            else:
                # Maintain in filtered if high severity
                if ev.severity == "HIGH":
                    filtered.append(ev)
        return filtered

    def _build_primary_advisory(
        self,
        events: List[FarmEvent],
        valid_water_levels: List[tuple],
        valid_moistures: List[tuple],
        is_pump_running: bool = False,
        is_estop_active: bool = False,
        has_upcoming_heavy_rain: bool = False,
        crop_stage: str = "VEGETATIVE"
    ) -> Dict[str, Any]:
        """Synthesizes the single most prominent advisory card for Home & Sensors."""
        if is_estop_active:
            return {
                "headline": "Emergency Stop Engaged — Physical Actuation Blocked",
                "summary": "Central irrigation control is locked in safe mode. ArvaNode monitoring stations continue continuous telemetry acquisition.",
                "proposal_type": "CLEAR_ESTOP_CHECK",
                "target_zone": "Central Pump Station",
                "urgency": "CRITICAL",
                "requires_confirmation": True,
                "rationale": "Hardware emergency interlock takes precedence over automated and manual watering schedules."
            }

        # Check critical soil dryness
        soil_dry_event = next((e for e in events if e.event_type == "SOIL_DRYING"), None)
        if soil_dry_event:
            return {
                "headline": "Rootzone Desiccation Alert — Reflood Recommended",
                "summary": soil_dry_event.summary,
                "proposal_type": "REFLOOD_PROPOSAL",
                "target_zone": "Affected Paddy Terraces",
                "urgency": "HIGH",
                "requires_confirmation": True,
                "rationale": "IRRI AWD guidelines require immediate replenishing once soil moisture drops below 50% to prevent root death."
            }

        # Check water drop event
        water_drop_event = next((e for e in events if e.event_type == "WATER_LEVEL_DROP"), None)
        if water_drop_event:
            if has_upcoming_heavy_rain:
                return {
                    "headline": "AWD Standby — Rain Expected to Refill Terraces",
                    "summary": "Water depth is low, but PAGASA forecasts significant rainfall. Defer pump operation to prevent overflow and conserve energy.",
                    "proposal_type": "DEFER_IRRIGATION",
                    "target_zone": "All Paddy Terraces",
                    "urgency": "MEDIUM",
                    "requires_confirmation": False,
                    "rationale": "Utilizing forecast precipitation reduces diesel/electricity pumping costs by up to 35% in accordance with PhilRice PalayCheck."
                }
            return {
                "headline": "AWD Reflood Trigger Reached (-15 cm threshold)",
                "summary": water_drop_event.summary,
                "proposal_type": "REFLOOD_PROPOSAL",
                "target_zone": "Lowest Elevation Terrace",
                "urgency": "HIGH",
                "requires_confirmation": True,
                "rationale": "Field water has receded to the AWD threshold. Apply 3-5 cm shallow flood to maintain rice tillering."
            }

        # Check water excess event
        excess_event = next((e for e in events if e.event_type == "WATER_LEVEL_EXCESS"), None)
        if excess_event:
            return {
                "headline": "Paddy Water Depth Exceeds Optimum (>10 cm)",
                "summary": excess_event.summary,
                "proposal_type": "DRAINAGE_CHECK",
                "target_zone": "Spillway & Drainage Outlets",
                "urgency": "MEDIUM",
                "requires_confirmation": False,
                "rationale": "Deep water (>5 cm) retards tillering and increases vulnerability to lodging and golden apple snail damage."
            }

        # Node offline / stale event
        offline_event = next((e for e in events if e.event_type == "NODE_OFFLINE"), None)
        if offline_event:
            return {
                "headline": "Telemetry Coverage Warning — Offline Node Detected",
                "summary": offline_event.summary,
                "proposal_type": "NODE_DIAGNOSTICS",
                "target_zone": "Device Registry",
                "urgency": "MEDIUM",
                "requires_confirmation": False,
                "rationale": "AWD rule confidence requires multi-node agreement across all paddy terraces."
            }

        # Default healthy / standby condition
        return {
            "headline": "Paddy Hydrology Within Safe AWD Boundaries",
            "summary": "All monitoring nodes report water levels and rootzone soil moisture within safe AWD drying boundaries. Central pump remains on standby.",
            "proposal_type": "NONE",
            "target_zone": None,
            "urgency": "LOW",
            "requires_confirmation": False,
            "rationale": "Controlled drying during vegetative stage encourages deeper root proliferation and suppresses methane emissions."
        }

    def generate_dynamic_questions(
        self,
        events: List[FarmEvent],
        valid_water_levels: List[tuple],
        valid_moistures: List[tuple],
        has_upcoming_heavy_rain: bool = False,
        is_pump_running: bool = False,
        is_estop_active: bool = False,
        stale_nodes: Optional[List[str]] = None,
        offline_nodes: Optional[List[str]] = None,
        crop_stage: str = "VEGETATIVE"
    ) -> List[str]:
        """
        Dynamically generates 4-6 prioritized, context-aware agricultural questions
        reflecting real-time farm conditions and recent events.
        """
        questions: List[str] = []
        event_types = {e.event_type for e in events}

        # 1. Emergency Stop / Irrigation Blocked
        if is_estop_active or "IRRIGATION_BLOCKED" in event_types:
            questions.append("What should I check before attempting irrigation again?")
            questions.append("How does the emergency stop affect automated AWD scheduling?")

        # 2. Water Drop / Low Level
        if "WATER_LEVEL_DROP" in event_types:
            questions.append("Is the current water depth appropriate for this crop's growth stage?")
            questions.append("Should I run irrigation now or wait for the AWD reflood window?")

        # 3. Water Excess / High Level
        if "WATER_LEVEL_EXCESS" in event_types:
            questions.append("Should I take action to manage the current water level?")
            questions.append("Will excessive water depth suppress tillering or attract snails?")

        # 4. Critical Soil Dryness
        if "SOIL_DRYING" in event_types:
            questions.append("Do the current soil conditions indicate that irrigation may be needed?")
            questions.append("How much water volume is required to restore field saturation?")

        # 5. Rain Forecast
        if has_upcoming_heavy_rain or "RAIN_FORECAST" in event_types:
            questions.append("Should I adjust my irrigation plan based on the PAGASA rain forecast?")
            questions.append("Will expected rainfall cause paddy flooding or runoff?")

        # 6. Conflicting Node Readings
        if "READINGS_CONFLICT" in event_types:
            questions.append("Why are the monitoring nodes reporting different conditions?")
            questions.append("Does the elevation delta between terraces explain the water variance?")

        # 7. Stale or Missing Telemetry
        if (stale_nodes and len(stale_nodes) > 0) or (offline_nodes and len(offline_nodes) > 0) or "SENSOR_STALE" in event_types or "NODE_OFFLINE" in event_types:
            questions.append("How does the missing sensor data affect my farm assessment?")
            questions.append("What steps should I take to troubleshoot offline ArvaNodes?")

        # 8. Pump Active
        if is_pump_running or "PUMP_ACTIVE" in event_types:
            questions.append("How long should the pump run to achieve optimal +3 to +5 cm depth?")
            questions.append("When should I close the central distribution valve?")

        # 9. Baseline / Calm state questions (if fewer than 4 events occurred)
        if len(questions) < 4:
            questions.append("What should I monitor next to maintain crop health?")
            questions.append("What PhilRice fertilizer guidelines apply to this rice stage?")
            questions.append("How does the current AWD cycle compare to historical Lopez averages?")
            questions.append("What information would improve this recommendation?")

        # Return top 5 distinct questions
        distinct = []
        for q in questions:
            if q not in distinct:
                distinct.append(q)
            if len(distinct) >= 5:
                break

        return distinct

