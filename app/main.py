"""
Arva AI - FastAPI Microservice Entrypoint.
Provides backend-mediated endpoints for ArvaLink and internal services.
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any

from arvaAI.app.schemas.decision_models import UserQueryRequest
from arvaAI.app.tools.read_only_tools import ReadOnlyTelemetryTools
from arvaAI.app.services.gemini_advisor import ArvaGeminiAdvisor

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Initialize configuration
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "https://api-aquaflow.gladwindr.me/api/v1")
ARVACORE_API_TOKEN = os.getenv("ARVACORE_API_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Initialize Service Components
try:
    tools = ReadOnlyTelemetryTools(BACKEND_BASE_URL, ARVACORE_API_TOKEN)
    advisor = ArvaGeminiAdvisor(tools, GEMINI_API_KEY, GEMINI_MODEL)
except Exception as e:
    tools = None
    advisor = None

app = FastAPI(title="Arva AI Advisory Service", version="1.0.0")

class QueryPayload(BaseModel):
    user_id: str = "anonymous"
    query_text: str
    field_id: int = 1
    role: str = "FARMER"

@app.get("/health")
def health():
    return {
        "status": "UP",
        "service": "arva-ai",
        "model": GEMINI_MODEL,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/api/v1/ai/query")
def api_query(payload: QueryPayload):
    res = handle_query(payload.model_dump())
    if "error" in res:
        raise HTTPException(status_code=500, detail=res)
    return res

def handle_query(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Pure Python handler compatible with standard ASGI/WSGI or FastAPI."""
    try:
        user_req = UserQueryRequest(
            user_id=payload.get("user_id", "anonymous"),
            query_text=payload.get("query_text", ""),
            field_id=payload.get("field_id", 1),
            role=payload.get("role", "FARMER")
        )
        return advisor.evaluate_query(user_req)
    except ValueError as ve:
        return {
            "error": "BAD_REQUEST",
            "message": str(ve),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "error": "INTERNAL_SERVER_ERROR",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

if __name__ == "__main__":
    print("Testing local standalone query...")
    sample_query = {"user_id": "farmer_01", "query_text": "What is the condition of my rice paddies?", "field_id": 1}
    res = handle_query(sample_query)
    import json
    print(json.dumps(res, indent=2))
