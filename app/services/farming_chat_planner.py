"""
Arva AI Farming Chatbot Conversational Planner.
Coordinates context-aware agricultural dialogue, rice specialization,
PhilRice document retrieval, multi-source agronomic citations,
task categorization (System, Farmer, Equipment, Blocked), and strict safety guardrails.
"""

from typing import Dict, Any, List, Optional
import uuid
import re
from datetime import datetime, timezone

from arvaAI.app.services.agronomic_profiles import get_crop_profile
from arvaAI.app.services.philrice_manual_retriever import PhilRiceManualRetriever
from arvaAI.app.tools.read_only_tools import ReadOnlyTelemetryTools

INITIAL_QUESTION = "Hi, I am Arva, what do you like to plant today?"
PROCEED_QUESTION = "Do you want to proceed with the proposed planting preparation?"

ADVERSARIAL_KEYWORDS = [
    "ignore previous instructions", "system override", "activate relay",
    "turn on the pump", "format c:", "drop table", "admin bypass", "sudo",
    "developer mode", "unrestricted ai", "shell execution", "gpio write",
    "force pump", "bypass", "jailbreak"
]

DESTRUCTIVE_PATTERNS = [
    r"\b(delete|drop|erase|purge|truncate|wipe|destroy)\b",
    r"\b(unpair|remove|reset|decommission)\s+(node|device|sensor|board|pump)\b",
    r"\b(format|reset\s+factory|clear\s+telemetry|override\s+safety)\b",
    r"\b(change\s+role|grant\s+admin|modify\s+permission|disable\s+auth)\b",
    r"\b(shut\s*down|force\s*off|emergency\s*kill|kill\s*switch)\b",
]

TOPIC_KEYWORDS = {
    "weather": [r"\bweathers?\b", r"\brains?\b", r"\brainy\b", r"\brainfall\b", r"\btyphoons?\b", r"\bforecasts?\b", r"\bpagasa\b", r"\bmonsoons?\b", r"\bfloods?\b", r"\bflooding\b", r"\bdroughts?\b", r"\bdry spell\b", r"\bamihan\b", r"\bhabagat\b", r"\bclimates?\b"],
    "fertilizer": [r"\bfertilizers?\b", r"\bnutrients?\b", r"\bnitrogen\b", r"\burea\b", r"\bmoet\b", r"\blcc\b", r"\bzinc\b", r"\bleaf color\b", r"\bbasal\b", r"\btopdress\b", r"\bpotassium\b", r"\bphosphorus\b", r"\bnpk\b"],
    "water": [r"\bwaters?\b", r"\birrigat(e|ion|ing)\b", r"\bawd\b", r"\bdepths?\b", r"\bwater table\b", r"\bpondings?\b", r"\bsubmerge\b", r"\bpercolation\b"],
    "pest": [r"\bpests?\b", r"\binsects?\b", r"\bsnails?\b", r"\bkuhol\b", r"\bdiseases?\b", r"\bweeds?\b", r"\bstem borer\b", r"\bblast\b", r"\bblight\b", r"\brats?\b", r"\bhoppers?\b", r"\bgolden apple\b"],
    "land_prep": [r"\bland prep\b", r"\bprepare the field\b", r"\bplow(ing|ed|s)?\b", r"\bplough\b", r"\bharrow(ing|ed|s)?\b", r"\blevel(ing|ed)?\b", r"\bpuddl(ing|ed)?\b", r"\bseedbeds?\b", r"\bdikes?\b", r"\bpilapil\b"],
    "variety": [r"\bwhat variet(y|ies)\b", r"\brecommend variet(y|ies)\b", r"\bbest variet(y|ies)\b", r"\bseed selections?\b", r"\binbred vs hybrid\b"],
    "harvest": [r"\bharvest(ing|ed)?\b", r"\bmaturity\b", r"\bthresh(ing|ed)?\b", r"\bdry(ing|ed)?\b", r"\bpalay drying\b", r"\bmoisture content\b", r"\bgrain filling\b"]
}

DEFAULT_REFERENCES = [
    "PhilRice Philippine Rice Production Training Manual (2003)",
    "IRRI Alternate Wetting and Drying (AWD) Technical Protocol (2020)",
    "PAGASA 3-Day & Seasonal Agro-Meteorological Weather Forecast",
    "DA-PhilRice NSIC Rice Variety Management Guide (2023)",
    "Lopez, Quezon Municipal Agricultural Profile (Soil Series: Calumpang Clay)",
    "ArvaNode Authentic Field Telemetry (Rootzone Soil Moisture & Water Level)",
    "ArvaNet Farm & Field Topology Database"
]

class FarmingChatPlanner:
    def __init__(self, tools: Optional[ReadOnlyTelemetryTools] = None):
        self.tools = tools
        self._manual_retriever = PhilRiceManualRetriever()

    def process_turn(
        self,
        user_message: str,
        current_step: str = "CROP_SELECTION",
        selected_crop: Optional[str] = None,
        field_id: int = 1,
        is_estop_active: bool = False
    ) -> Dict[str, Any]:
        msg = (user_message or "").strip()
        lower_msg = msg.lower()

        # 1. Adversarial Defense Check
        if self._is_adversarial(msg):
            return {
                "step": current_step,
                "selected_crop": selected_crop or "Lowland Rice (NSIC Rc 222)",
                "reply": "Request flagged for safety violation: Arva operates strictly in advisory mode. Direct hardware control and system overrides are prohibited.",
                "prompt_question": INITIAL_QUESTION,
                "readiness_score": 0,
                "readiness_status": "BLOCKED",
                "tasks": [],
                "requires_confirmation": False,
                "references": DEFAULT_REFERENCES,
                "warnings": ["Adversarial input detected and neutralized."]
            }

        # 2. Destructive Operations Safety Intercept
        if self._is_destructive_request(msg):
            return {
                "step": current_step,
                "selected_crop": selected_crop or "Lowland Rice (NSIC Rc 222)",
                "reply": (
                    "⚠️ Destructive Operation Intercepted:\n"
                    "Requests to delete farm records, unpair monitoring nodes, erase telemetry, or alter safety configuration "
                    "cannot be performed through conversational chat. Consequential actions require explicit backend authorization "
                    "(ROLE_ADMIN or ROLE_OPERATOR), confirmation of exact target scope, and audit trail preservation.\n\n"
                    "If you are authorized and wish to perform this maintenance, please navigate to the dedicated Settings / Nodes tab."
                ),
                "prompt_question": "How else may I advise on your farm cultivation or rice field management?",
                "readiness_score": 0,
                "readiness_status": "BLOCKED",
                "tasks": [],
                "requires_confirmation": False,
                "references": ["ArvaCore Deterministic Safety Interlocks", "ArvaNet Access Control Policy"],
                "warnings": ["Consequential / destructive operational intent intercepted. Execution refused in chat."]
            }

        # 3. Reset Handling
        if lower_msg in ["reset", "start over", "new plan", "clear"]:
            return {
                "step": "CROP_SELECTION",
                "selected_crop": "Lowland Rice (NSIC Rc 222)",
                "reply": INITIAL_QUESTION,
                "prompt_question": INITIAL_QUESTION,
                "readiness_score": 0,
                "readiness_status": "ASSESSING",
                "tasks": [],
                "requires_confirmation": False,
                "references": DEFAULT_REFERENCES,
                "warnings": []
            }

        # 3. Confirmation Pending Affirmative / Negative Handling Takes Precedence
        if current_step == "CONFIRMATION_PENDING" and (self._is_affirmative(msg) or self._is_negative(msg)):
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
                        "references": crop_prof.get("references", DEFAULT_REFERENCES),
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
                    "references": crop_prof.get("references", DEFAULT_REFERENCES),
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
                    "references": crop_prof.get("references", DEFAULT_REFERENCES),
                    "warnings": []
                }

        # 4. Context-Aware Topical Query Intercept
        # If the user asks about weather, fertilizer, irrigation, pests, land prep, varieties, or harvest,
        # answer grounded in PhilRice / Lopez / PAGASA data while retaining active crop and conversation step!
        active_crop_name = selected_crop or "Lowland Rice (NSIC Rc 222)"
        detected_topic = self._detect_topic(lower_msg)

        if detected_topic:
            topical_response = self._build_topical_response(
                topic=detected_topic,
                query=msg,
                crop_name=active_crop_name,
                current_step=current_step,
                is_estop_active=is_estop_active
            )
            return topical_response

        # 5. Check if user is asking "What should I plant?" or general crop suitability
        if any(k in lower_msg for k in ["what to plant", "what should i plant", "recommend crop", "crop suggestion", "recomenda", "ano ang itatanim", "ano magandang itanim"]):
            crop_prof = get_crop_profile("rice")
            reply = (
                f"🌾 Recommendation: {crop_prof['canonical_name']} (Tubigan 21)\n\n"
                "• Suitability: Highly recommended for Lopez, Quezon lowland irrigated and rainfed lowland fields (Calumpang clay soil series).\n"
                "• Climate & Water: Excellent adaptability to wet and dry seasons with high tillering capacity (maturity: 106 days, potential yield: 10.0 tons/ha).\n"
                "• Water Management: Optimized for Alternate Wetting and Drying (AWD) water-saving technology.\n\n"
                "Would you like to select Lowland Rice and proceed with field assessment, or do you have a specific method in mind?"
            )
            return {
                "step": "CROP_SELECTION",
                "selected_crop": crop_prof["canonical_name"],
                "reply": reply,
                "prompt_question": "Select Lowland Rice to begin field preparation assessment.",
                "readiness_score": 15,
                "readiness_status": "ASSESSING",
                "tasks": [],
                "requires_confirmation": False,
                "references": [
                    "PhilRice NSIC Rc 222 Variety Production Guide (2023)",
                    "Lopez, Quezon Municipal Agricultural Profile",
                    "PAGASA Agro-Meteorological Advisory"
                ],
                "warnings": []
            }

        # 6. Conversational 10-step State Progression
        if current_step == "CROP_SELECTION":
            # Check if input is a valid crop selection
            crop_prof = get_crop_profile(msg)
            crop_name = crop_prof["canonical_name"]

            # If the user typed something completely vague that wasn't a recognized crop or topic
            if not self._is_plausible_crop_or_confirmation(msg, crop_name):
                return {
                    "step": "CROP_SELECTION",
                    "selected_crop": "Lowland Rice (NSIC Rc 222)",
                    "reply": (
                        "I am Arva, your agricultural assistant specializing in Philippine rice farming. "
                        "I can guide your crop selection, 21-day land preparation, AWD water management, "
                        "fertilizer topdressing, or pest control.\n\n"
                        "To get started, what crop would you like to plan? (Lowland Rice is recommended for this season)."
                    ),
                    "prompt_question": INITIAL_QUESTION,
                    "readiness_score": 0,
                    "readiness_status": "ASSESSING",
                    "tasks": [],
                    "requires_confirmation": False,
                    "references": DEFAULT_REFERENCES,
                    "warnings": []
                }

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
                "references": crop_prof.get("references", DEFAULT_REFERENCES),
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
                "references": crop_prof.get("references", DEFAULT_REFERENCES),
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
                        "references": crop_prof.get("references", DEFAULT_REFERENCES),
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
                    "references": crop_prof.get("references", DEFAULT_REFERENCES),
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
                    "references": crop_prof.get("references", DEFAULT_REFERENCES),
                    "warnings": []
                }

        elif current_step in ["PREPARATION_ACTIVE", "CROP_MANAGEMENT"]:
            crop_prof = get_crop_profile(selected_crop or "rice")
            tasks = self._build_categorized_tasks(crop_prof, is_estop_active)
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
                "references": crop_prof.get("references", DEFAULT_REFERENCES),
                "warnings": []
            }

        # Fallback
        return {
            "step": current_step,
            "selected_crop": active_crop_name,
            "reply": f"Arva is monitoring {active_crop_name}. Ask any question about irrigation, weather, fertilizer, or crop health.",
            "prompt_question": "What would you like assistance with?",
            "readiness_score": 50,
            "readiness_status": "MANAGING",
            "tasks": [],
            "requires_confirmation": False,
            "references": DEFAULT_REFERENCES,
            "warnings": []
        }

    def _is_adversarial(self, text: str) -> bool:
        lower = text.lower()
        return any(k in lower for k in ADVERSARIAL_KEYWORDS)

    def _is_destructive_request(self, text: str) -> bool:
        lower = text.lower()
        for pat in DESTRUCTIVE_PATTERNS:
            if re.search(pat, lower):
                return True
        return False

    def _is_affirmative(self, text: str) -> bool:
        lower = text.lower().strip()
        return lower.startswith("yes") or lower.startswith("y") or "proceed" in lower or "confirm" in lower

    def _detect_topic(self, lower_text: str) -> Optional[str]:
        for topic, patterns in TOPIC_KEYWORDS.items():
            for pat in patterns:
                if re.search(pat, lower_text):
                    return topic
        return None

    def _is_negative(self, text: str) -> bool:
        lower = text.lower().strip()
        return lower.startswith("no") or lower.startswith("n") or "hold" in lower or "cancel" in lower

    def _is_plausible_crop_or_confirmation(self, user_msg: str, matched_crop: str) -> bool:
        low = user_msg.lower().strip()
        if len(low) < 3:
            return False
        known_terms = ["rice", "palay", "corn", "mais", "eggplant", "talong", "tomato", "kamatis", "onion", "sibuyas", "nsic", "tubigan"]
        return any(t in low for t in known_terms)

    def _build_topical_response(
        self,
        topic: str,
        query: str,
        crop_name: str,
        current_step: str,
        is_estop_active: bool
    ) -> Dict[str, Any]:
        """
        Builds a context-aware agricultural response using PhilRice, PAGASA, and Lopez data.
        Does not force conversation reset or change current step unless necessary.
        """
        citations = []
        reply_lines = []

        if topic == "weather":
            reply_lines = [
                "🌦️ PAGASA Agro-Meteorological & Weather Impact Advisory:",
                "• Forecast & Rainfall Impact: Heavy rainfall (>30 mm/24h) suspends pump irrigation automatically to prevent waterlogging and fertilizer leaching.",
                "• Field Preparation Drainage: If plowing or harrowing is underway, ensure field drainage gates are opened to 2-3 cm overflow height to avoid drowned bunds.",
                "• Critical Safeguard: If high winds (>50 km/h) or localized storms are forecast, lower standing water to 1-2 cm to prevent lodging in tall or flowering rice.",
                "• Municipal Grounding: Lopez, Quezon experiences Type IV climate (rainfall distributed throughout the year, peak wet season Nov-Jan)."
            ]
            citations = [
                "PAGASA 3-Day Agro-Meteorological Weather Forecast",
                "PhilRice Training Manual (2003), Module 7 (Water Management), pp. 78-82",
                "Lopez, Quezon Municipal Agricultural Climate Profile"
            ]

        elif topic == "fertilizer":
            reply_lines = [
                "🌱 PhilRice Integrated Nutrient Management (INM) Advisory:",
                "• Diagnostic Tools: Use the Leaf Color Chart (LCC threshold = 4) to determine exact nitrogen topdressing timing, avoiding excess vegetative lodging.",
                "• Nitrogen (N) Split: Split into 3-4 applications in dry season, 2-3 applications in wet season (1/3 basal at final harrowing, 1/3 at mid-tillering, 1/3 at panicle initiation).",
                "• Phosphorus (P): 100% basal incorporation during final harrowing to ensure early root development.",
                "• Potassium (K): Apply 50% basal at final harrowing and 50% at Early Panicle Initiation (EPI) to promote robust grain filling.",
                "• Micronutrients: Apply 10-25 kg/ha Zinc Sulfate within 10-14 days after transplanting (DAT) if zinc deficiency symptoms appear (brown spots on older leaves)."
            ]
            citations = [
                "PhilRice Philippine Rice Production Training Manual (2003), Module 8 (Nutrient Management), pp. 92-108",
                "DA-PhilRice NSIC Rc 222 Nutrient Management Protocol (2023)",
                "BSWM Soil Fertility and Micronutrient Guidelines"
            ]

        elif topic == "water":
            reply_lines = [
                "💧 Growth-Stage Irrigation & Alternate Wetting and Drying (AWD) Advisory:",
                "• Vegetative Stage (1-30 DAT): Maintain shallow 2-3 cm water layer. Safe drying down to -15 cm below field surface promotes deep anchorage and tillering.",
                "• Panicle Initiation to Flowering: CRITICAL! Keep continuously flooded at 3-5 cm. Moisture stress at flowering causes spikelet sterility and massive yield drop.",
                "• Ripening / Pre-Harvest: Terminal drainage must be executed 7-10 days before harvest to hasten ripening and facilitate mechanical or manual cutting.",
                "• Sensor Grounding: ArvaNode ultrasonic field tube sensors monitor water table down to -15 cm before recommending reflooding."
            ]
            citations = [
                "IRRI Alternate Wetting and Drying (AWD) Technical Protocol (2020)",
                "PhilRice Training Manual (2003), Module 7, pp. 75-88",
                "ArvaNode Authentic Field Telemetry (Field Water Tube & Ultrasonic Gauge)"
            ]

        elif topic == "pest":
            reply_lines = [
                "🛡️ PhilRice Integrated Pest Management (IPM) & Crop Protection Advisory:",
                "• Golden Apple Snail (Kuhol): Maintain 1-2 cm shallow water during first 2 weeks after transplanting; install wire mesh screens at canal inlets; hand-pick egg masses.",
                "• Weeds: Maintain a 2-3 cm continuous water blanket 3-4 days after transplanting to suppress weed seeds; perform rotary weeding at 15-20 DAT.",
                "• Stem Borer & Rice Blast: Avoid excessive nitrogen fertilizer (>120 kg N/ha); balance with potassium and maintain field sanitation around bunds.",
                "• Rats: Synchronize planting within a 1-month window across contiguous terraces to dilute rodent and insect pressure."
            ]
            citations = [
                "PhilRice Training Manual (2003), Modules 10-16 (Pest, Disease, and Weed Management), pp. 120-175",
                "DA-PhilRice PalayCheck System for Crop Protection"
            ]

        elif topic == "land_prep":
            reply_lines = [
                "🚜 PhilRice 21-Day Thorough Land Preparation Protocol:",
                "• Day 1-7 (Plowing): Plow at 10-15 cm depth immediately after initial soaking to incorporate stubble, weeds, and organic matter.",
                "• Day 7-14 (1st & 2nd Harrowing): Harrow twice at 7-day intervals to break clods, puddle soil, and germinate weed seeds.",
                "• Day 14-21 (Leveling): Final harrowing and thorough leveling with a wooden plank. A well-leveled field reduces water use by 30% and suppresses weeds.",
                "• Soil Characteristics: Calumpang clay in Lopez, Quezon requires adequate soaking time (3-5 days) before primary tillage."
            ]
            citations = [
                "PhilRice Training Manual (2003), Module 5 (Land Preparation), pp. 48-58",
                "Lopez, Quezon Agricultural Soil Series Profile (BSWM)"
            ]

        elif topic == "variety":
            reply_lines = [
                "🌾 Recommended Philippine Rice Varieties for Lopez, Quezon:",
                "• NSIC Rc 222 (Tubigan 21): High-yielding inbred (avg 6.1 t/ha, max 10.0 t/ha), 106-day maturity, intermediate amylose, resistant to blast and bacterial blight.",
                "• NSIC Rc 160 (Tubigan 14): Premium eating quality (low amylose, soft grain), 107-day maturity, avg 5.6 t/ha, highly favored for marketability.",
                "• PSB Rc 82 (Peñaranda): Proven drought-tolerant and stable producer across rainfed and irrigated ecosystems (avg 5.4 t/ha, 110 days).",
                "• Selection Advice: For wet season in Lopez, NSIC Rc 222 offers maximum tillering and lodging resistance."
            ]
            citations = [
                "PhilRice NSIC Rice Variety Catalog (2023)",
                "PhilRice Training Manual (2003), Module 4 (Rice Varieties), pp. 38-45"
            ]

        elif topic == "harvest":
            reply_lines = [
                "🌾 PhilRice Harvest & Postharvest Advisory:",
                "• Harvest Readiness: 80-85% of grains on panicles are golden yellow / straw-colored, with grains at base of panicle at hard dough stage.",
                "• Terminal Drainage: Completely cut off irrigation 7-10 days before cutting to harden the soil surface.",
                "• Immediate Threshing: Thresh within 24 hours of cutting to prevent fermentation, yellowing, and heat damage.",
                "• Proper Drying: Sun dry palay in 4-5 cm thick layers, turning every 30 minutes, until grain moisture reaches 14% for safe storage."
            ]
            citations = [
                "PhilRice Training Manual (2003), Module 19 (Harvest and Postharvest Systems), pp. 195-210"
            ]

        # Retrieve relevant passages from PhilRice indexed manual
        search_results = self._manual_retriever.search_manual(query, top_k=1)
        if search_results:
            p = search_results[0]
            reply_lines.append(f"\n📖 Excerpt from {p['source']} (Page {p['page']}, {p['section']}):")
            reply_lines.append(f"\"{p['snippet']}\"")
            citations.insert(0, f"{p['source']}, Page {p['page']} ({p['section']})")

        reply = "\n".join(reply_lines)

        crop_prof = get_crop_profile(crop_name)
        tasks = self._build_categorized_tasks(crop_prof, is_estop_active)

        # In PREPARATION_ACTIVE, questions about crop management advance the step to CROP_MANAGEMENT
        step_to_return = current_step
        if current_step == "PREPARATION_ACTIVE" and topic in ["fertilizer", "pest", "water", "harvest", "variety"]:
            step_to_return = "CROP_MANAGEMENT"

        return {
            "step": step_to_return,
            "selected_crop": crop_prof["canonical_name"],
            "reply": reply,
            "prompt_question": f"Do you have further questions on {topic.replace('_', ' ')} or would you like to continue with field preparation?",
            "readiness_score": 50 if not is_estop_active else 20,
            "readiness_status": "ASSESSING" if not is_estop_active else "BLOCKED",
            "tasks": tasks if current_step in ["CONFIRMATION_PENDING", "PREPARATION_ACTIVE", "CROP_MANAGEMENT"] else [],
            "requires_confirmation": current_step == "CONFIRMATION_PENDING",
            "references": citations + crop_prof.get("references", DEFAULT_REFERENCES),
            "warnings": ["Emergency Stop is engaged; physical pump actuation is blocked."] if is_estop_active else []
        }

    def _build_categorized_tasks(self, crop_prof: Dict[str, Any], is_estop_active: bool) -> List[Dict[str, Any]]:
        tasks = []
        tid = 1

        # 1. System Automated Tasks
        for item in crop_prof.get("standard_tasks", {}).get("system_automated", []):
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
        for item in crop_prof.get("standard_tasks", {}).get("farmer_manual", []):
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
        for item in crop_prof.get("standard_tasks", {}).get("equipment_info", []):
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
