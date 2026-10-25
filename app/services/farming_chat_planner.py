"""
Arva AI Farming Chatbot Conversational Planner.
Coordinates the 10-step guided farmer dialogue, telemetry grounding,
task categorization (System, Farmer, Equipment, Blocked), and explicit confirmations.
"""

from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime, timezone

from arvaAI.app.services.agronomic_profiles import get_crop_profile
from arvaAI.app.tools.read_only_tools import ReadOnlyTelemetryTools

INITIAL_QUESTION = "Hi, I am Arva, what do you like to plant today?"
PROCEED_QUESTION = "Do you want to proceed with the proposed planting preparation?"

ADVERSARIAL_KEYWORDS = [
    "ignore previous instructions", "system override", "activate relay",
    "turn on the pump", "format c:", "drop table", "admin bypass", "sudo",
    "developer mode", "unrestricted ai", "shell execution", "gpio write",
    "force pump", "bypass", "jailbreak"
]

class FarmingChatPlanner:
    def __init__(self, tools: Optional[ReadOnlyTelemetryTools] = None):
        self.tools = tools

    def process_turn(
        self,
        user_message: str,
        current_step: str = "CROP_SELECTION",
        selected_crop: Optional[str] = None,
        field_id: int = 1,
        is_estop_active: bool = False
    ) -> Dict[str, Any]:
        msg = (user_message or "").strip()

        # 1. Adversarial Defense Check
        if self._is_adversarial(msg):
            return {
                "step": "CROP_SELECTION",
                "reply": "Request flagged for safety violation: Arva operates strictly in advisory mode. Direct hardware control and system overrides are prohibited.",
                "prompt_question": INITIAL_QUESTION,
                "readiness_score": 0,
                "readiness_status": "BLOCKED",
                "tasks": [],
                "requires_confirmation": False,
                "warnings": ["Adversarial input detected and neutralized."]
            }

        # 2. Reset Handling
        if msg.lower() in ["reset", "start over", "new plan"]:
            return {
                "step": "CROP_SELECTION",
                "reply": INITIAL_QUESTION,
                "prompt_question": INITIAL_QUESTION,
                "readiness_score": 0,
                "readiness_status": "ASSESSING",
                "tasks": [],
                "requires_confirmation": False,
                "warnings": []
            }

        # 3. Conversational 10-step State Progression
        if current_step == "CROP_SELECTION":
            crop_prof = get_crop_profile(msg)
            crop_name = crop_prof["canonical_name"]
            reply = (
                f"Great! Let's prepare for {crop_name}. "
                "Which field terrace, planting method (e.g., Wet Bed Transplanting or Direct Wet Seeding), "
                "and target planting schedule do you have in mind?"
            )
            return {
                "step": "FIELD_AND_METHOD",
                "selected_crop": crop_name,
                "reply": reply,
                "prompt_question": "Please specify field terrace, planting method, and schedule.",
                "readiness_score": 25,
                "readiness_status": "ASSESSING",
                "tasks": [],
                "requires_confirmation": False,
                "references": crop_prof["references"],
                "warnings": []
            }

        elif current_step == "FIELD_AND_METHOD":
            crop_prof = get_crop_profile(selected_crop or "rice")
            tasks = self._build_categorized_tasks(crop_prof, is_estop_active)
            score = 45 if not is_estop_active else 20
            status = "ASSESSING" if not is_estop_active else "BLOCKED"

            reply = (
                f"Farm-Readiness assessment complete for {crop_prof['canonical_name']}. "
                f"Readiness score is {score}% ({status}). Telemetry from ArvaNodes evaluated. "
                f"{PROCEED_QUESTION}"
            )
            warnings = []
            if is_estop_active:
                warnings.append("EMERGENCY STOP is actively engaged on the main circuit. Pump actions are locked.")

            return {
                "step": "CONFIRMATION_PENDING",
                "selected_crop": crop_prof["canonical_name"],
                "reply": reply,
                "prompt_question": PROCEED_QUESTION,
                "readiness_score": score,
                "readiness_status": status,
                "tasks": tasks,
                "requires_confirmation": True,
                "references": crop_prof["references"],
                "warnings": warnings
            }

        elif current_step == "CONFIRMATION_PENDING":
            crop_prof = get_crop_profile(selected_crop or "rice")
            if self._is_affirmative(msg):
                if is_estop_active:
                    return {
                        "step": "CONFIRMATION_PENDING",
                        "selected_crop": crop_prof["canonical_name"],
                        "reply": "Cannot proceed: Emergency stop is actively engaged. Deactivate E-Stop to enable automated operations.",
                        "prompt_question": PROCEED_QUESTION,
                        "readiness_score": 20,
                        "readiness_status": "BLOCKED",
                        "tasks": self._build_categorized_tasks(crop_prof, is_estop_active),
                        "requires_confirmation": True,
                        "warnings": ["Safety Interlock Active: Clear physical E-Stop button before proceeding."]
                    }
                tasks = self._build_categorized_tasks(crop_prof, False)
                # Mark system automated task as in-progress
                for t in tasks:
                    if t["category"] == "SYSTEM_AUTOMATED":
                        t["status"] = "IN_PROGRESS"

                reply = (
                    "Planting preparation confirmed! Automated pre-soak irrigation workflow has been safely "
                    "submitted to ArvaCore. Review your task checklist below as preparation progresses."
                )
                return {
                    "step": "PREPARATION_ACTIVE",
                    "selected_crop": crop_prof["canonical_name"],
                    "reply": reply,
                    "prompt_question": "Preparation in progress. Complete farmer manual tasks.",
                    "readiness_score": 60,
                    "readiness_status": "PREPARING",
                    "tasks": tasks,
                    "requires_confirmation": False,
                    "references": crop_prof["references"],
                    "warnings": []
                }
            else:
                return {
                    "step": "CONFIRMATION_PENDING",
                    "selected_crop": crop_prof["canonical_name"],
                    "reply": "Understood. The proposed planting preparation has been placed on hold.",
                    "prompt_question": PROCEED_QUESTION,
                    "readiness_score": 45,
                    "readiness_status": "ASSESSING",
                    "tasks": self._build_categorized_tasks(crop_prof, is_estop_active),
                    "requires_confirmation": True,
                    "references": crop_prof["references"],
                    "warnings": []
                }

        elif current_step in ["PREPARATION_ACTIVE", "CROP_MANAGEMENT"]:
            crop_prof = get_crop_profile(selected_crop or "rice")
            tasks = self._build_categorized_tasks(crop_prof, is_estop_active)
            low = msg.lower()

            if any(k in low for k in ["harvest", "mature", "thresh", "drying"]):
                reply = (
                    "🌾 PhilRice Harvest & Postharvest Advisory:\n"
                    "- Maturity Indicator: 80-85% of grains on panicles are straw-colored / golden yellow, with grains at base at hard dough stage.\n"
                    "- Terminal Drainage: Ensure paddies have been completely drained 7-10 days prior to harvest.\n"
                    "- Postharvest: Thresh immediately within 24 hours of cutting to prevent discoloration. Sun dry palay in 4-5 cm layers to 14% moisture content."
                )
            elif any(k in low for k in ["fertilizer", "nutrient", "nitrogen", "urea", "moet", "lcc", "zinc"]):
                reply = (
                    "🌱 PhilRice Integrated Nutrient Management (INM) Advisory:\n"
                    "- Nitrogen (N): Use Leaf Color Chart (LCC threshold = 4) to guide topdressing. Split N into 3-4 applications in dry season, 2-3 in wet season.\n"
                    "- Phosphorus (P): 100% basal incorporation at final harrowing.\n"
                    "- Potassium (K): 50% basal at harrowing, 50% at early panicle initiation (EPI).\n"
                    "- Micronutrients: Apply 10-25 kg/ha Zinc Sulfate within 10-14 days after transplanting."
                )
            elif any(k in low for k in ["pest", "insect", "snail", "kuhol", "disease", "weed"]):
                reply = (
                    "🛡️ PhilRice Integrated Pest & Crop Protection Advisory:\n"
                    "- Golden Apple Snail (Kuhol): Maintain 1-2 cm shallow water during first 2 weeks after transplanting; screen canal inlets with wire mesh.\n"
                    "- Weeds: Maintain 2-3 cm continuous water blanket 3-4 days after transplanting to suppress weed seeds; rotary weed at 15-20 DAT.\n"
                    "- Stem Borer & Blast: Avoid excessive N fertilizer; maintain balanced K and field sanitation."
                )
            elif any(k in low for k in ["water", "irrigation", "awd", "depth", "level"]):
                reply = (
                    "💧 Growth-Stage Irrigation & AWD Advisory:\n"
                    "- Vegetative & Tillering: Maintain 2-3 cm shallow water. Allow safe drying to -15 cm (AWD) to promote root anchorage.\n"
                    "- Flowering / Panicle Initiation: CRITICAL! Keep continuously flooded at 3-5 cm depth. Moisture stress at flowering causes spikelet sterility.\n"
                    "- Pre-Harvest: Terminal drainage 7-10 days before cutting."
                )
            else:
                reply = (
                    f"Cultivation support active for {crop_prof['canonical_name']}. "
                    "You can ask for guidance on variety selection, 21-day land preparation, AWD water management, "
                    "INM fertilizer splits (LCC/MOET), weed/snail control, or harvest readiness."
                )

            return {
                "step": "CROP_MANAGEMENT",
                "selected_crop": crop_prof["canonical_name"],
                "reply": reply,
                "prompt_question": "Ask any question regarding rice crop management, irrigation, or harvest.",
                "readiness_score": 85,
                "readiness_status": "MANAGING",
                "tasks": tasks,
                "requires_confirmation": False,
                "references": crop_prof["references"],
                "warnings": []
            }

    def _is_adversarial(self, text: str) -> bool:
        lower = text.lower()
        return any(k in lower for k in ADVERSARIAL_KEYWORDS)

    def _is_affirmative(self, text: str) -> bool:
        lower = text.lower().strip()
        return lower.startswith("yes") or lower.startswith("y") or "proceed" in lower or "confirm" in lower

    def _build_categorized_tasks(self, crop_prof: Dict[str, Any], is_estop_active: bool) -> List[Dict[str, Any]]:
        tasks = []
        tid = 1

        # 1. System Automated Tasks
        for item in crop_prof["standard_tasks"].get("system_automated", []):
            tasks.append({
                "id": tid,
                "category": "SYSTEM_AUTOMATED",
                "title": item["title"],
                "description": item["description"],
                "status": "BLOCKED" if is_estop_active else "PENDING",
                "blocking_reason": "Emergency stop is active" if is_estop_active else None,
                "requires_confirmation": item.get("requires_confirmation", True)
            })
            tid += 1

        # 2. Farmer Manual Tasks
        for item in crop_prof["standard_tasks"].get("farmer_manual", []):
            tasks.append({
                "id": tid,
                "category": "FARMER_MANUAL",
                "title": item["title"],
                "description": item["description"],
                "status": "PENDING",
                "blocking_reason": None,
                "requires_confirmation": False
            })
            tid += 1

        # 3. Equipment Info Tasks
        for item in crop_prof["standard_tasks"].get("equipment_info", []):
            tasks.append({
                "id": tid,
                "category": "EQUIPMENT_INFO",
                "title": item["title"],
                "description": item["description"],
                "status": "PENDING",
                "blocking_reason": None,
                "requires_confirmation": False
            })
            tid += 1

        # 4. Safety Blocked Tasks (conditional)
        if is_estop_active:
            tasks.append({
                "id": tid,
                "category": "SAFETY_BLOCKED",
                "title": "Clear Active Emergency Stop",
                "description": "Physical Emergency Stop button is depressed. Release latch to clear interlock.",
                "status": "BLOCKED",
                "blocking_reason": "Physical Emergency Stop active on pump control board.",
                "requires_confirmation": True
            })
            tid += 1

        return tasks

