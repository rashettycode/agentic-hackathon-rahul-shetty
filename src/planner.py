"""
planner.py

This module is responsible for planning.
It takes a user request and decides:
- what type of case it is
- what steps are required
- what information is required to proceed
"""

from dataclasses import dataclass
from typing import List


@dataclass
class Plan:
    """
    Simple data structure that represents a plan.

    case_type: what kind of request this is
    steps: ordered list of actions to take
    required_fields: information needed to complete the request
    """
    case_type: str
    steps: List[str]
    required_fields: List[str]


# Supported case types
CASE_TYPES = [
    "access_request",
    "security_incident",
    "meeting_request",
    "status_request",
    "general",
]


# Required information for each case type
REQUIRED_FIELDS = {
    "access_request": [
        "system_or_asset",
        "access_level",
        "people_affected",
        "approver",
    ],
    "security_incident": [
        "what_happened",
        "when_happened",
        "affected_system",
        "reporter_contact",
    ],
    "meeting_request": [
        "purpose",
        "attendees",
        "time_window",
    ],
    # A status request usually needs a case ID to look up the request.
    "status_request": [
        "case_id",
    ],
    "general": [],
}


# Default planning steps for each case type
DEFAULT_STEPS = {
    "access_request": [
        "Classify request",
        "Extract key fields",
        "Check missing required fields",
        "Set routing and SLA",
        "Draft acknowledgement",
    ],
    "security_incident": [
        "Classify request",
        "Extract incident details",
        "Check missing required fields",
        "Set routing and SLA",
        "Draft acknowledgement",
    ],
    "meeting_request": [
        "Classify request",
        "Extract meeting details",
        "Check missing required fields",
        "Set routing and SLA",
        "Draft acknowledgement",
    ],
    "status_request": [
        "Classify request",
        "Extract case ID (if provided)",
        "Check missing required fields",
        "Draft status response",
    ],
    "general": [
        "Classify request",
        "Summarize request",
        "Draft acknowledgement",
    ],
}


def simple_classify(text: str) -> str:
    """
    Very simple keyword-based classifier.

    This avoids complexity and makes behaviour easy to understand.
    Later, this can be replaced with an LLM-based classifier.
    """
    text = text.lower()

    if any(word in text for word in ["access", "permission", "grant", "shared drive", "folder"]):
        return "access_request"

    if any(word in text for word in ["security", "incident", "breach", "phishing", "lost device"]):
        return "security_incident"

    if any(word in text for word in ["meeting", "schedule", "invite", "calendar"]):
        return "meeting_request"

    # Status / approval follow-up questions
    if any(word in text for word in ["status", "approved", "approval", "update", "where is"]):
        return "status_request"

    return "general"


def plan_request(user_text: str) -> Plan:
    """
    Create a plan for the given user request.

    Steps:
    1. Classify the request
    2. Select the appropriate steps and required fields
    3. Return a Plan object
    """
    case_type = simple_classify(user_text)

    return Plan(
        case_type=case_type,
        steps=DEFAULT_STEPS[case_type],
        required_fields=REQUIRED_FIELDS[case_type],
    )
