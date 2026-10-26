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

## 3. Core Agronomic & Intelligence Architecture

Arva AI is strictly scoped to Philippine **Rice Cultivation** under the DA-PhilRice PalayCheck System and IRRI AWD protocols.

### 3.1 Specialized Engines
1. **Rice Planting Readiness Engine** (`app/services/rice_planting_readiness_engine.py`):
   - Multi-factor evaluation across variety, 21-day land preparation timeline, weather advisories, soil moisture, and perched water table depth.
   - Deterministic 4-outcome state machine: `Suitable`, `Conditionally suitable`, `Further assessment required` (with explicit Insufficient Data handling), and `High risk`.
2. **Rice Phenology & AWD Depletion Engine** (`app/services/rice_phenology_and_prediction.py`):
   - 12 phenological growth stages tracking (seedling, vegetative tillering, stem elongation, panicle initiation, flowering, grain filling, terminal drainage).
   - Dynamic AWD eligibility enforcement (AWD safe drying suspended during panicle initiation & flowering).
   - Predictive drying window projection calculating depletion rates (cm/day) and projected days/hours to -15.0 cm threshold.
   - Weather hazard analysis (tropical cyclone signals, lodging risk in mature rice, rainfall washouts).
3. **Telemetry Quality & Anomaly Engine** (`app/services/telemetry_quality_engine.py`):
   - Detects out-of-range anomalies (water level < -50 cm or > +25 cm; moisture < 0% or > 100%).
   - Flags telemetry staleness (> 15 min warning, > 60 min critical stale).
   - Preserves True Zero (0.0 cm surface water) while detecting disconnected/null sensors.
   - Computes confidence-weighted terrace averages across all 6 ArvaNodes.
4. **Multi-Source Evidence Aggregator** (`app/services/multi_source_evidence_aggregator.py`):
   - Integrates PAGASA weather MCP adapter, Lopez agricultural profile MCP adapter, ArvaNode telemetry, indexed PhilRice training manual, and authenticated farm database records.

---

## 4. Read-Only Tool Namespace

The agent is exposed strictly to read-only observational tools:
- `get_latest_field_telemetry(field_id: int)`
- `get_irrigation_event_history(field_id: int, limit: int)`
- `get_node_health_status(node_id: str)`

Attempts to execute unlisted tools (e.g. `activate_pump_relay`, `override_safety`) are rejected by design.

---

## 4. Testing & Verification

Run the test suite verifying prompt injection defenses, input sanitization, and safety invariants:
```bash
PYTHONPATH=. python3 -m unittest discover -s tests
```
