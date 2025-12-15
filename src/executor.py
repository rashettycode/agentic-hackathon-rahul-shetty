"""
executor.py

Builds a structured "Case Packet" from:
1) the user's request text
2) the plan produced by planner.py

For v1 (demo):
- Rules are deterministic and easy to audit
- Gemini is used only for entity extraction + optional helper text
- Follow-ups attach to existing case_id
- Status checks are read-only and do NOT mutate the case
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List

from google import genai

# follow-up support (case existence check)
from src.case_store import case_exists


# ---------------------------------------------------------------------
# Text normalization (prevents smart quotes, stray \r, etc.)
# ---------------------------------------------------------------------

_SMART_QUOTES = {
    "“": '"',
    "”": '"',
    "’": "'",
    "‘": "'",
    "—": "-",
    "–": "-",
}


def clean_text(s: str | None) -> str | None:
    if s is None:
        return None
    for k, v in _SMART_QUOTES.items():
        s = s.replace(k, v)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ---------------------------------------------------------------------
# Status intent detection (NEW)
# ---------------------------------------------------------------------

_STATUS_KEYWORDS = [
    "status",
    "progress",
    "update",
    "check status",
    "where is",
    "how long",
    "how many days",
    "eta",
    "time remaining",
    "sla",
]


def is_status_intent(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in _STATUS_KEYWORDS)


# ---------------------------------------------------------------------
# Priority & SLA logic
# ---------------------------------------------------------------------

def priority_from_text(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ["urgent", "asap", "immediately", "today"]):
        return "high"
    if any(word in lowered for word in ["this week", "by friday", "deadline", "next week"]):
        return "medium"
    return "low"


def sla_days(case_type: str, priority: str) -> int:
    if case_type == "status_request":
        return 2 if priority == "high" else 5

    if case_type == "security_incident":
        if priority == "high":
            return 1
        if priority == "medium":
            return 2
        return 5

    if priority == "high":
        return 2
    if priority == "medium":
        return 10
    return 15


# ---------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------

def routing(case_type: str) -> Dict[str, str]:
    routes = {
        "access_request": {"queue": "ServiceDesk-Access", "owner_role": "AccessAdmin"},
        "security_incident": {"queue": "Security-Incident", "owner_role": "SecurityAnalyst"},
        "meeting_request": {"queue": "Admin-Scheduling", "owner_role": "Coordinator"},
        "status_request": {"queue": "Case-Tracking", "owner_role": "IntakeCoordinator"},
        "general": {"queue": "General-Intake", "owner_role": "IntakeCoordinator"},
    }
    return routes.get(case_type, routes["general"])


# ---------------------------------------------------------------------
# Deterministic required fields by type
# ---------------------------------------------------------------------

REQUIRED_BY_TYPE: dict[str, list[str]] = {
    "general": ["location_or_program"],
    "access_request": ["requester_contact", "location_or_program", "system_or_asset", "access_level"],
    "security_incident": ["reporter_contact", "location_or_program", "what_happened", "when_happened", "affected_system"],
    "meeting_request": ["requester_contact", "location_or_program", "purpose", "attendees", "time_window"],
    "status_request": ["case_id"],
}


def effective_required_fields(case_type: str, plan_obj: Any) -> list[str]:
    base = list(REQUIRED_BY_TYPE.get(case_type, REQUIRED_BY_TYPE["general"]))
    plan_fields = list(getattr(plan_obj, "required_fields", []) or [])
    merged = base + [f for f in plan_fields if f not in base]
    return merged


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def extract_case_id(text: str) -> str | None:
    match = re.search(r"\bCASE-\d{8}-\d{6}\b", text or "")
    return match.group(0) if match else None


def make_case_id() -> str:
    return f"CASE-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def strip_code_fences(raw: str) -> str:
    cleaned = (raw or "").strip()
    return cleaned.replace("```json", "").replace("```", "").strip()


def extract_labeled_field(text: str, labels: list[str]) -> str | None:
    if not text:
        return None
    for label in labels:
        pattern = rf"(?im)^\s*{re.escape(label)}\s*[:=\-]\s*(.+?)\s*$"
        m = re.search(pattern, text)
        if m:
            value = m.group(1).strip()
            return value if value else None
    return None


def infer_people_affected(text: str, entities: Dict[str, Any]) -> int | None:
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    if emails:
        return len(set(emails))

    names = entities.get("requester_name")
    if isinstance(names, str) and names.strip():
        parts = [p.strip() for p in names.split(",") if p.strip()]
        if parts:
            return len(parts)

    return None


def post_process_entities(case_type: str, user_text: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    if case_type == "access_request":
        if entities.get("people_affected") in (None, 0):
            inferred = infer_people_affected(user_text, entities)
            if inferred is not None:
                entities["people_affected"] = inferred
    return entities


# ---------------------------------------------------------------------
# Gemini extraction (v1-safe)
# ---------------------------------------------------------------------

def extract_entities_gemini(case_type: str, text: str) -> Dict[str, Any]:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    prompt = f"""
You are an enterprise intake assistant.

Case type: {case_type}

Extract relevant fields from the request.
Return ONLY valid JSON.
Use null for unknown values.

Expected keys:
requester_name
requester_contact
deadline
location_or_program
system_or_asset
access_level
people_affected
approver
what_happened
when_happened
affected_system
reporter_contact
purpose
attendees
time_window

Request:
{text}
""".strip()

    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return _parse_json_safely(response.text or "")


# ---------------------------------------------------------------------
# Stub extraction (deterministic fallback)
# ---------------------------------------------------------------------

def extract_entities_stub(case_type: str, text: str) -> Dict[str, Any]:
    entities: Dict[str, Any] = {
        "requester_name": None,
        "requester_contact": None,
        "deadline": None,
        "location_or_program": None,
    }

    # deterministic parsing for routing fields
    loc = extract_labeled_field(
        text,
        labels=[
            "department/program",
            "department",
            "program",
            "program area",
            "program-area",
            "location",
            "site",
            "branch",
            "contact",
        ],
    )
    if loc and "contact" not in (loc.lower() if isinstance(loc, str) else ""):
        entities["location_or_program"] = loc

    contact = extract_labeled_field(text, labels=["contact", "email", "phone"])
    if contact:
        entities["requester_contact"] = contact

    if case_type == "access_request":
        entities.update({"system_or_asset": None, "access_level": None, "people_affected": None, "approver": None})
    elif case_type == "security_incident":
        entities.update({"what_happened": None, "when_happened": None, "affected_system": None, "reporter_contact": None})
    elif case_type == "meeting_request":
        entities.update({"purpose": None, "attendees": None, "time_window": None})
    elif case_type == "status_request":
        entities.update({"case_id": extract_case_id(text)})

    return entities


# ---------------------------------------------------------------------
# Schema normalization
# ---------------------------------------------------------------------

COMMON_KEYS: set[str] = {"requester_name", "requester_contact", "deadline", "location_or_program"}

CASE_KEYS: dict[str, set[str]] = {
    "access_request": {"system_or_asset", "access_level", "people_affected", "approver"},
    "security_incident": {"what_happened", "when_happened", "affected_system", "reporter_contact"},
    "meeting_request": {"purpose", "attendees", "time_window"},
    "status_request": {"case_id"},
    "general": set(),
}

SCHEMA_DEFAULTS: dict[str, dict[str, Any]] = {
    "access_request": {"system_or_asset": None, "access_level": None, "people_affected": None, "approver": None},
    "security_incident": {"what_happened": None, "when_happened": None, "affected_system": None, "reporter_contact": None},
    "meeting_request": {"purpose": None, "attendees": None, "time_window": None},
    "status_request": {"case_id": None},
    "general": {},
}


def _coerce_to_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v if v else None
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = [str(v).strip() for v in value if str(v).strip()]
        return ", ".join(parts) if parts else None
    if isinstance(value, dict):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    return str(value)


def _coerce_people_affected(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, list):
        return len(value)
    if isinstance(value, str):
        digits = re.findall(r"\d+", value)
        if digits:
            try:
                n = int(digits[0])
                return n if n >= 0 else None
            except Exception:
                return None
    return None


def normalize_entities(case_type: str, entities: Dict[str, Any]) -> Dict[str, Any]:
    allowed = set(COMMON_KEYS) | set(CASE_KEYS.get(case_type, set()))
    cleaned: Dict[str, Any] = {}

    for k, v in (entities or {}).items():
        if k in allowed:
            cleaned[k] = v

    for k, default in SCHEMA_DEFAULTS.get(case_type, {}).items():
        cleaned.setdefault(k, default)

    for k in list(cleaned.keys()):
        if k == "people_affected":
            cleaned[k] = _coerce_people_affected(cleaned.get(k))
        else:
            cleaned[k] = _coerce_to_str(cleaned.get(k))

    return cleaned


def _parse_json_safely(text: str) -> Dict[str, Any]:
    raw = strip_code_fences(text or "").strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


# ---------------------------------------------------------------------
# Missing info + clarifying question
# ---------------------------------------------------------------------

def find_missing(required_fields: List[str], entities: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    for field in required_fields:
        value = entities.get(field)
        if value is None:
            missing.append(field)
        elif isinstance(value, str) and value.strip().lower() in {"", "unknown"}:
            missing.append(field)
    return missing


def build_clarifying_question(missing_fields: List[str]) -> str:
    parts: list[str] = []
    if "location_or_program" in missing_fields:
        parts.append("which department or program area this relates to")
    if "requester_contact" in missing_fields:
        parts.append("the best contact email or phone number")
    if "deadline" in missing_fields:
        parts.append("any deadline or event date")
    if "system_or_asset" in missing_fields:
        parts.append("which system or asset you need access to")
    if "access_level" in missing_fields:
        parts.append("what access level you require")
    if "what_happened" in missing_fields:
        parts.append("what happened")
    if "when_happened" in missing_fields:
        parts.append("when it happened")
    if "affected_system" in missing_fields:
        parts.append("which system was affected")
    if "purpose" in missing_fields:
        parts.append("the purpose of the meeting/request")
    if "attendees" in missing_fields:
        parts.append("who should attend")
    if "time_window" in missing_fields:
        parts.append("your preferred time window")

    if not parts:
        return "To route this correctly, could you provide: " + ", ".join(missing_fields) + "?"

    if len(parts) == 1:
        return f"Could you confirm {parts[0]}?"
    return f"To route this correctly, could you confirm {', '.join(parts[:-1])}, and {parts[-1]}?"


# ---------------------------------------------------------------------
# Gemini add-ons (question + summary)
# ---------------------------------------------------------------------

def gemini_clarifying_question(case_type: str, missing_fields: List[str], user_text: str) -> str | None:
    if not missing_fields:
        return None

    fallback = build_clarifying_question(missing_fields)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return fallback

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
You write a single, polite clarifying question for an enterprise intake form.

Case type: {case_type}
Missing fields: {", ".join(missing_fields)}

Rules:
- Output ONE sentence ending with a question mark.
- Mention all missing fields in natural language.
- Do NOT add extra questions or extra commentary.
- Do NOT invent values.

User request:
{user_text}
""".strip()
        resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        out = clean_text(strip_code_fences(resp.text or "")) or ""
        out = out.splitlines()[0].strip() if out else ""
        return out if out.endswith("?") else fallback
    except Exception:
        return fallback


def gemini_summary_next_steps(case_type: str, user_text: str, missing_fields: List[str]) -> Dict[str, str]:
    cleaned = clean_text(user_text) or ""
    fallback_summary = f"Summary: {cleaned[:180]}{'...' if len(cleaned) > 180 else ''}"
    fallback_next = (
        "Next steps: provide " + ", ".join(missing_fields) + "."
        if missing_fields
        else "Next steps: your request can be routed for processing."
    )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"summary": fallback_summary, "next_steps": fallback_next}

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
Write two lines only.

Line 1 starts with 'Summary:' and is a single sentence describing the request in <= 20 words.
Line 2 starts with 'Next steps:' and is a single sentence. If there are missing fields, ask for them; otherwise state it will be processed.

Case type: {case_type}
Missing fields: {", ".join(missing_fields) if missing_fields else "none"}

User request:
{user_text}
""".strip()
        resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        out_lines = (clean_text(strip_code_fences(resp.text or "")) or "").splitlines()
        summary = next((l for l in out_lines if l.lower().startswith("summary:")), fallback_summary).strip()
        nexts = next((l for l in out_lines if l.lower().startswith("next steps:")), fallback_next).strip()
        return {"summary": summary, "next_steps": nexts}
    except Exception:
        return {"summary": fallback_summary, "next_steps": fallback_next}


# ---------------------------------------------------------------------
# Unified extraction entry point
# ---------------------------------------------------------------------

def extract_entities(case_type: str, text: str) -> tuple[Dict[str, Any], str, str | None]:
    if case_type == "status_request":
        return extract_entities_stub(case_type, text), "rules/stub", None

    if case_type in {"access_request", "security_incident", "meeting_request"}:
        try:
            return extract_entities_gemini(case_type, text), "gemini", None
        except Exception as exc:
            return extract_entities_stub(case_type, text), "rules/stub", repr(exc)

    return extract_entities_stub(case_type, text), "rules/stub", None


# ---------------------------------------------------------------------
# Draft response
# ---------------------------------------------------------------------

def draft_response(case_type: str, missing_info: List[str]) -> str:
    if case_type == "status_request":
        if missing_info:
            return (
                "Thanks for checking in. Please share your case ID "
                "(example: CASE-YYYYMMDD-HHMMSS) so we can confirm the current status."
            )
        return "Thanks for checking in. We will review the current status and provide an update."

    if not missing_info:
        return (
            "Thanks for your request. It has been received and will be processed "
            "according to the applicable service standard."
        )

    return (
        "Thanks for your request. To proceed, please provide the following details: "
        + ", ".join(missing_info)
        + "."
    )


# ---------------------------------------------------------------------
# Case Packet assembly (case_created OR follow_up OR status_check)
# ---------------------------------------------------------------------

def build_case_packet(user_text: str, plan_obj: Any) -> Dict[str, Any]:
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    case_type = getattr(plan_obj, "case_type", "general") or "general"

    user_text_clean = clean_text(user_text) or ""

    priority = priority_from_text(user_text_clean)
    sla = sla_days(case_type, priority)
    route = routing(case_type)

    referenced_case_id = extract_case_id(user_text_clean)
    exists = bool(referenced_case_id and case_exists(referenced_case_id))

    # ✅ NEW: status check is read-only and does not mutate case
    if exists and is_status_intent(user_text_clean):
        return {
            "event_type": "status_check",
            "case_id": referenced_case_id,
            "created_at": created_at,
            "summary": f"Summary: Status check requested for case {referenced_case_id}.",
            "next_steps": "Next steps: This case is currently being processed within the applicable service standard.",
            "case_type": case_type,
            "priority": priority,
            "sla_days": sla,
            "routing": {**route, "notes": "v1 demo routing"},
            "audit": {
                "tools_used": ["rules/status"],
                "flags": [],
                "notes": "read-only status check",
            },
        }

    # 1) Extract
    entities_raw, tool_used, gemini_error = extract_entities(case_type, user_text_clean)

    # 2) Normalize -> postprocess -> normalize
    entities = normalize_entities(case_type, entities_raw)
    entities = post_process_entities(case_type, user_text_clean, entities)
    entities = normalize_entities(case_type, entities)

    # 3) Missing fields
    required_fields = effective_required_fields(case_type, plan_obj)
    missing_info = find_missing(required_fields, entities)

    # 4) Helper text
    clarifying_question = gemini_clarifying_question(case_type, missing_info, user_text_clean)
    summary_block = gemini_summary_next_steps(case_type, user_text_clean, missing_info)

    flags: List[str] = []
    if gemini_error:
        flags.append(f"gemini_failed: {gemini_error}")

    # ✅ follow-up event (mutates / updates)
    if exists:
        return {
            "event_type": "follow_up",
            "case_id": referenced_case_id,
            "created_at": created_at,
            "message": user_text_clean,
            "case_type": case_type,
            "entities_update": entities,
            "missing_info_after": missing_info,
            "summary": clean_text(summary_block.get("summary")),
            "next_steps": clean_text(summary_block.get("next_steps")),
            "clarifying_question": clean_text(clarifying_question) if clarifying_question else None,
            "audit": {
                "tools_used": [tool_used],
                "flags": flags,
                "notes": "follow-up appended",
            },
        }

    # ✅ create new case
    return {
        "event_type": "case_created",
        "case_id": make_case_id(),
        "created_at": created_at,
        "summary": clean_text(summary_block.get("summary")),
        "next_steps": clean_text(summary_block.get("next_steps")),
        "clarifying_question": clean_text(clarifying_question) if clarifying_question else None,
        "request_text": user_text_clean,
        "case_type": case_type,
        "priority": priority,
        "sla_days": sla,
        "entities": entities,
        "missing_info": missing_info,
        "plan": getattr(plan_obj, "steps", []) or [],
        "draft_response": clean_text(draft_response(case_type, missing_info)),
        "routing": {**route, "notes": "v1 demo routing"},
        "audit": {
            "tools_used": [tool_used],
            "flags": flags,
            "notes": "v1 packet created",
        },
    }


def pretty_json(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)
