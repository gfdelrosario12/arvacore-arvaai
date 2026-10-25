# OpenSpec: PhilRice Full-Cycle Rice Cultivation & Agricultural Intelligence Support

## 1. Context & Standard Reference
- **Authoritative Source**: Philippine Rice Research Institute (PhilRice), *Philippine Rice Production Training Manual* (2003).
- **Core Ecosystem**: ArvaCore (Edge Controller & Hub), ArvaNode (Ultrasonic Water Depth & Soil Moisture Nodes), ArvaNet (Gateway & Spring Boot Cloud Backend), ArvaLink (Flutter UI Console), ArvaAI (Gemini-grounded Microservice).
- **Target Application**: 1.1-Hectare Rice Farm, Barangay Silang, Lopez, Quezon, Philippines.

## 2. Supported Cultivation Workflow (12 Stages)

| Stage | PhilRice Grounding | Agronomic & Hydrological Rules | System & Safety Boundary |
|---|---|---|---|
| **1. Variety Profiling** | Module 4 | NSIC Rc 222 (Tubigan 21, 106d), NSIC Rc 160 (Tubigan 14, 107d), PSB Rc 82 (Peñaranda, 110d). High tillering, pest resistance, known harvest window. | Advisory profiling; no actuators. |
| **2. Planting Schedule & Readiness** | Modules 5 & 6 | Strict 21-day preparation requirement. Dates <14 days rejected (`NOT_RECOMMENDED`) due to toxic decomposition gases. | Deterministic evaluator in Backend & AI Planner. |
| **3. Land Preparation** | Module 5 | T-21 days primary plowing & bund repair; 5-7 days submergence (3-5 cm); T-14 days 1st harrowing; T-7 days 2nd crosswise harrowing; T-1 day plank leveling. | Task checklist generated with explicit prerequisites. |
| **4. Crop Establishment** | Module 6 | Wetbed (30 kg/ha, 400 m² bed, 24h soak, 24-36h incubation, 20-21d seedling); Dapog (55 kg/ha, 60 m² bed, 9-14d seedling); Direct-Wet (70 kg/ha drum seeder). | Calculates seed mass and bed dimensions. |
| **5. Vegetative & Tillering** | Modules 3 & 7 | Maintain shallow 2-3 cm depth. Avoid >5 cm ponding (inhibits tillers). AWD safe drying to -15 cm stimulates root anchorage. | Telemetry monitoring via ArvaNodes. |
| **6. Weeds, Pests & Diseases** | Modules 10, 12, 14, 16 | Golden Apple Snail (1-2 cm shallow water at 1-14 DAT, wire mesh screens); Weeds (thin water blanket + rotary weeding 15-20 DAT); Stem Borer & Blast (balanced N & K). | Actionable farmer advice & risk triggers. |
| **7. Nutrient Management (INM)** | Module 8 | Nitrogen split 3-4x (Dry Season) / 2-3x (Wet Season) guided by Leaf Color Chart (LCC threshold = 4); 100% P basal; 50% K basal + 50% at Early Panicle Initiation (EPI); 10-25 kg/ha Zinc Sulfate at 10-14 DAT. | Diagnostic advice with safety limits (max 40 kg N/ha per topdress). |
| **8. AWD Water Management** | Module 7 | Safe drying threshold = -15.0 cm relative to mud line. Reflood depth = +5.0 cm. | Verified ArvaNode ultrasonic telemetry; Zero-trust confirmation. |
| **9. Reproductive & Flowering** | Modules 3 & 7 | CRITICAL SENSITIVE STAGE: Suspend AWD. Maintain continuous 3-5 cm ponded water from PI through flowering (DAT 50-80). Zero drying permitted. | System alerts if drying detected at flowering. |
| **10. Grain Filling & Ripening** | Modules 3 & 7 | Milk to dough grain development requires shallow 2-3 cm water or saturation. | Monitored until terminal cutoff. |
| **11. Harvest Readiness** | Module 19 | 80-85% grains straw-colored/yellow; base grains in hard dough; kernels clear and translucent. Optimal timing: 28-34 days after heading (DS) / 30-42 days (WS). | Terminal drainage commanded 7-10 days prior to harvest. |
| **12. Postharvest & Next Cycle** | Modules 1, 8, 19 | Thresh within 24h; dry in 4-5 cm sun layers to 14% moisture (max 43.3°C for seeds, 54.4°C for milling). Store on pallets. Retain straw for K recycling. 30-day synchronous fallow rest. | Yield recording and cycle initialization. |

## 3. Safety & Security Invariant
- Direct pump actuation is strictly prohibited through conversational AI prompts.
- All physical valve and pump state changes require explicit Operator authorization via ArvaLink console with E-Stop interlocking.

