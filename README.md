# Arva AI: Decision-Support Agent Microservice

**Framework:** Python 3.10+ (FastAPI / Pure Python ASGI Compatible)  
**AI Model:** Google Gemini API (`gemini-2.5-flash` / `gemini-2.5-flash-lite`)  
**SDK:** `google-genai`  
**Architecture Model:** Backend-Mediated Advisory Agent  

---

## 1. System Responsibilities & Core Principles

Arva AI is an expert agricultural companion designed to assist rice farmers in managing Alternate Wetting and Drying (AWD) water regimes across six terraced field parcels (Pitaks 1 to 6).
- **Grounded Telemetry Interpretation**: Retrieves live sensor readings exclusively via authorized backend interfaces.
- **Evidence-Based Agronomics**: Contextualizes desiccation trends against IRRI and PhilRice AWD guidelines.
- **Strict Safety Invariant**: The agent possesses **zero direct actuation authority**. It cannot energize relays, bypass safety interlocks, or override emergency stop commands. All recommended actions require explicit farmer confirmation via ArvaLink and pass through the deterministic `ArvaCoreDecisionEngine`.

---

## 2. Environment Variables & Configuration

| Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google Gemini API Key | Stored in backend vault |
| `GEMINI_MODEL` | Gemini Model Identifier | `gemini-2.5-flash` |
| `BACKEND_BASE_URL` | ArvaNet Backend Base API | `https://api-aquaflow.gladwindr.me/api/v1` |
| `ARVACORE_API_TOKEN`| Internal Service JWT Bearer Token | `secret_service_token` |
| `MAX_TOOL_ROUNDS` | Maximum tool execution rounds | `4` |
| `REQUEST_TIMEOUT_SECONDS` | API request timeout | `15` |
| `MAX_USER_PROMPT_LEN` | Bounded user prompt length | `500` characters |

---

## 3. Read-Only Tool Namespace

The agent is exposed strictly to read-only observational tools:
- `get_latest_field_telemetry(field_id: int)`
- `get_irrigation_event_history(field_id: int, limit: int)`
- `get_node_health_status(node_id: str)`

Attempts to execute unlisted tools (e.g. `activate_pump_relay`, `override_safety`) are rejected by design.

---

## 4. Testing & Verification

Run the test suite verifying prompt injection defenses, input sanitization, and safety invariants:
```bash
PYTHONPATH=. python3 -m unittest arvaAI/tests/test_ai_safety_and_advisor.py
```
