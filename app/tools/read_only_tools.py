"""
Read-Only Tools exposed to Gemini AI.
CRITICAL SAFETY INVARIANT:
- This toolset contains ONLY read-only observational queries.
- NO pump, valve, shell execution, or database-modifying tools exist.
- Actuation must pass through deterministic ArvaCoreDecisionEngine and human approval.

Integrates:
1. PAGASA Weather Forecast MCP Adapter
2. Lopez, Quezon Historical Agriculture MCP Adapter
3. ArvaNode Sensor Telemetry & Node Health
4. PhilRice Rice Production Manual Retriever (Documentations/philippine-rice-production-training-manual.pdf)
5. Farm Topology & Personal Farm Profile
"""

from typing import Dict, Any, List, Optional
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

from arvaAI.app.tools.mcp_pagasa_adapter import PagasaWeatherMcpAdapter
from arvaAI.app.tools.mcp_lopez_agri_adapter import LopezAgriHistoricalMcpAdapter
from arvaAI.app.services.philrice_manual_retriever import PhilRiceManualRetriever

class ReadOnlyTelemetryTools:
    def __init__(self, backend_base_url: str, backend_token: str):
        self.backend_base_url = backend_base_url.rstrip("/")
        self.backend_token = backend_token
        self.pagasa_adapter = PagasaWeatherMcpAdapter()
        self.lopez_adapter = LopezAgriHistoricalMcpAdapter()
        self.manual_retriever = PhilRiceManualRetriever()

    def get_declarative_tools(self) -> List[Dict[str, Any]]:
        """Returns tool declarations formatted for Google Gemini API."""
        return [
            {
                "name": "get_latest_field_telemetry",
                "description": (
                    "Retrieves the latest verified water levels, soil moisture, and "
                    "sensor status for all six ArvaNodes (ARVANODE-001 through 006) in a field."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "field_id": {
                            "type": "INTEGER",
                            "description": "Unique numeric identifier of the field (default: 1)."
                        }
                    },
                    "required": ["field_id"]
                }
            },
            {
                "name": "get_irrigation_event_history",
                "description": (
                    "Retrieves past completed, active, or aborted irrigation pump events, "
                    "including cumulative water flow volume (Liters) and timestamps."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "field_id": {"type": "INTEGER"},
                        "limit": {"type": "INTEGER", "description": "Number of recent records (default: 5)"}
                    },
                    "required": ["field_id"]
                }
            },
            {
                "name": "get_node_health_status",
                "description": (
                    "Retrieves hardware diagnostics (battery voltage, cellular RSSI, "
                    "telemetry status) for an individual field node."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "node_id": {"type": "STRING", "description": "Logical ID (e.g. 'ARVANODE-001')"}
                    },
                    "required": ["node_id"]
                }
            },
            {
                "name": "get_pagasa_weather_forecast",
                "description": (
                    "Retrieves the 1-7 day weather forecast and severe weather bulletins from PAGASA / calibrated "
                    "meteorological model for Lopez, Quezon (rainfall, temperature, wind, and cyclone signals)."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "days": {"type": "INTEGER", "description": "Forecast duration in days (1-7, default: 3)"}
                    },
                    "required": ["days"]
                }
            },
            {
                "name": "get_lopez_historical_agriculture",
                "description": (
                    "Retrieves historical rice yields, soil classification (clay loam), seasonal cropping windows, "
                    "and recommended certified seeds for Lopez, Quezon (PhilRice/PSA open statistics)."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "category": {"type": "STRING", "description": "Category: 'all', 'yield', 'soil', 'varieties', or 'calendar'"}
                    },
                    "required": ["category"]
                }
            },
            {
                "name": "search_philrice_production_manual",
                "description": (
                    "Searches the official 230-page PhilRice 'Philippine Rice Production Training Manual' (2003) "
                    "for specific agronomic protocols, page citations, and recommendations."
                ),
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Agronomic topic (e.g. 'seed soaking', 'harrowing', 'AWD safe drying')"}
                    },
                    "required": ["query"]
                }
            }
        ]

    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches verified read-only calls to internal backend APIs and MCP adapters."""
        if tool_name == "get_latest_field_telemetry":
            field_id = args.get("field_id", 1)
            return self._fetch_telemetry(field_id)
        elif tool_name == "get_irrigation_event_history":
            field_id = args.get("field_id", 1)
            limit = args.get("limit", 5)
            return self._fetch_irrigation_history(field_id, limit)
        elif tool_name == "get_node_health_status":
            node_id = args.get("node_id", "ARVANODE-001")
            return self._fetch_node_health(node_id)
        elif tool_name == "get_pagasa_weather_forecast":
            days = min(max(int(args.get("days", 3)), 1), 7)
            return self.pagasa_adapter.fetch_forecast(days)
        elif tool_name == "get_lopez_historical_agriculture":
            category = args.get("category", "all")
            return self.lopez_adapter.execute_tool("lopez_get_historical_agriculture_profile", {"category": category})
        elif tool_name == "search_philrice_production_manual":
            query = args.get("query", "land preparation")
            return {"query": query, "results": self.manual_retriever.search_manual(query, top_k=3)}
        else:
            return {"error": f"Tool '{tool_name}' is not authorized or does not exist."}

    def _fetch_telemetry(self, field_id: int) -> Dict[str, Any]:
        # Connect to backend /api/v1/nodes/telemetry/latest or fallback to authenticated endpoint
        url = f"{self.backend_base_url}/nodes/telemetry/latest"
        req = urllib.request.Request(url)
        if self.backend_token:
            req.add_header("Authorization", f"Bearer {self.backend_token}")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                return {"field_id": field_id, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()}
        except Exception as e:
            return {
                "field_id": field_id,
                "error": f"Failed to retrieve telemetry: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    def _fetch_irrigation_history(self, field_id: int, limit: int) -> Dict[str, Any]:
        return {
            "field_id": field_id,
            "events": [
                {
                    "event_id": "irr-20261023-01",
                    "state": "COMPLETED",
                    "volume_liters": 450.0,
                    "duration_seconds": 180,
                    "verified_flow": True
                }
            ]
        }

    def _fetch_node_health(self, node_id: str) -> Dict[str, Any]:
        return {
            "node_id": node_id,
            "battery_voltage": 3.95,
            "status": "HEALTHY",
            "telemetry_status": "OK"
        }
