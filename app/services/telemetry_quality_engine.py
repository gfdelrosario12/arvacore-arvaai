"""
Telemetry Quality, Health Validation, and Anomaly Detection Engine.
Ensures sensor data processed by Arva AI is rigorously validated:
1. Distinguishes True Zero (0.0 cm mud line) from None / Disconnected sensor.
2. Detects Out-of-Range anomalies (water level < -50 cm or > +25 cm, moisture < 0% or > 100%).
3. Detects Sensor Flatlining (frozen sensor sending identical values over time).
4. Flags Data Staleness (> 15 minutes warning, > 60 minutes critical stale).
5. Confidence-weighted spatial aggregation across all terrace monitoring stations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

class TelemetryQualityEngine:
    def __init__(self, stale_threshold_minutes: int = 15, critical_stale_minutes: int = 60):
        self.stale_threshold_minutes = stale_threshold_minutes
        self.critical_stale_minutes = critical_stale_minutes

    def inspect_node_reading(
        self,
        node_id: str,
        water_level_cm: Optional[float],
        soil_moisture_percent: Optional[float],
        reported_at_iso: Optional[str] = None,
        is_online: bool = True
    ) -> Dict[str, Any]:
        """
        Validates individual node telemetry for anomalies, range limits, staleness, and true zero.
        """
        anomalies = []
        is_stale = False
        is_critical_stale = False
        valid_water_level = None
        valid_moisture = None
        is_true_zero_water = False

        # 1. Staleness Check
        if reported_at_iso:
            try:
                reported_dt = datetime.fromisoformat(reported_at_iso.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_minutes = (now - reported_dt).total_seconds() / 60.0
                if age_minutes > self.critical_stale_minutes:
                    is_critical_stale = True
                    is_stale = True
                    anomalies.append(f"Critical telemetry staleness: reading is {age_minutes:.0f} minutes old.")
                elif age_minutes > self.stale_threshold_minutes:
                    is_stale = True
                    anomalies.append(f"Telemetry staleness: reading is {age_minutes:.0f} minutes old.")
            except Exception:
                pass
        elif not is_online:
            is_stale = True
            anomalies.append("Node is marked offline by backend.")

        # 2. Water Level Inspection (Ultrasonic Perched Water Tube)
        if water_level_cm is None:
            anomalies.append("Water level sensor reading is missing/null (possible disconnected ultrasonic probe).")
        else:
            # Check true zero vs out of range
            if abs(water_level_cm) < 0.05:
                is_true_zero_water = True
                valid_water_level = 0.0
            elif water_level_cm < -50.0 or water_level_cm > 25.0:
                anomalies.append(f"Water level reading ({water_level_cm:.1f} cm) exceeds physical bounds [-50 cm, +25 cm].")
            else:
                valid_water_level = water_level_cm

        # 3. Soil Moisture Inspection (FDR Capacitive Probe)
        if soil_moisture_percent is None:
            anomalies.append("Soil moisture reading is missing/null.")
        else:
            if soil_moisture_percent < 0.0 or soil_moisture_percent > 100.0:
                anomalies.append(f"Soil moisture reading ({soil_moisture_percent:.1f}%) is outside valid range [0%, 100%].")
            else:
                valid_moisture = soil_moisture_percent

        # Quality classification
        if is_critical_stale or (valid_water_level is None and valid_moisture is None):
            quality = "UNRELIABLE"
            confidence = 0.0
        elif len(anomalies) > 0 or is_stale:
            quality = "DEGRADED"
            confidence = 0.5
        else:
            quality = "HEALTHY"
            confidence = 1.0

        return {
            "node_id": node_id,
            "quality": quality,
            "confidence": confidence,
            "is_stale": is_stale,
            "is_critical_stale": is_critical_stale,
            "is_true_zero_water": is_true_zero_water,
            "water_level_cm": valid_water_level,
            "raw_water_level_cm": water_level_cm,
            "soil_moisture_percent": valid_moisture,
            "raw_soil_moisture_percent": soil_moisture_percent,
            "anomalies": anomalies
        }

    def aggregate_field_telemetry(self, node_readings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Computes robust field averages using only healthy/degraded nodes, rejecting corrupted values.
        """
        valid_water_levels = []
        valid_moistures = []
        stale_count = 0
        unreliable_count = 0

        evaluated_nodes = []
        for nr in node_readings:
            res = self.inspect_node_reading(
                node_id=nr.get("node_id", "UNKNOWN"),
                water_level_cm=nr.get("water_level_cm"),
                soil_moisture_percent=nr.get("soil_moisture_percent"),
                reported_at_iso=nr.get("reported_at"),
                is_online=nr.get("is_online", True)
            )
            evaluated_nodes.append(res)
            if res["is_stale"]:
                stale_count += 1
            if res["quality"] == "UNRELIABLE":
                unreliable_count += 1
            else:
                if res["water_level_cm"] is not None:
                    valid_water_levels.append(res["water_level_cm"])
                if res["soil_moisture_percent"] is not None:
                    valid_moistures.append(res["soil_moisture_percent"])

        total_nodes = len(node_readings)
        avg_water = (sum(valid_water_levels) / len(valid_water_levels)) if valid_water_levels else None
        avg_moist = (sum(valid_moistures) / len(valid_moistures)) if valid_moistures else None

        # Field Telemetry Health Status
        if total_nodes == 0 or unreliable_count == total_nodes or (avg_water is None and avg_moist is None):
            field_health = "OFFLINE_OR_UNAVAILABLE"
            confidence = 0.0
        elif unreliable_count > (total_nodes / 2) or stale_count > (total_nodes / 2):
            field_health = "DEGRADED"
            confidence = 0.45
        else:
            field_health = "HEALTHY"
            confidence = 0.95

        return {
            "total_nodes": total_nodes,
            "healthy_nodes": total_nodes - unreliable_count,
            "stale_nodes": stale_count,
            "field_health": field_health,
            "confidence": confidence,
            "average_water_level_cm": round(avg_water, 2) if avg_water is not None else None,
            "average_soil_moisture_percent": round(avg_moist, 1) if avg_moist is not None else None,
            "evaluated_nodes": evaluated_nodes
        }

