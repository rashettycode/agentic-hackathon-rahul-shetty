"""
agent.py

This module acts as the main coordinator for the agent.

It connects:
- planner.py  → decides what needs to be done
- executor.py → builds the Case Packet
- memory.py   → stores the case for record-keeping

Think of this file as the "traffic controller" of the agent.
"""

from dotenv import load_dotenv

load_dotenv()


from typing import Dict, Any

from .planner import plan_request
from .executor import build_case_packet
from .memory import append_case


def run_agent(user_text: str) -> Dict[str, Any]:
    """
    Run the full agent workflow for a single user request.

    Steps:
    1. Create a plan from the user input
    2. Execute the plan to build a Case Packet
    3. Store the case for auditing or future reference
    4. Return results for display
    """

    # Step 1: Ask the planner to analyze the request
    plan = plan_request(user_text)

    # Step 2: Execute the plan and build a structured case
    case_packet = build_case_packet(user_text, plan)

    # Step 3: Store the case (simple memory / audit log)
    append_case(case_packet)

    # Step 4: Return what the UI or caller needs
    return {
        "plan": {
            "case_type": plan.case_type,
            "steps": plan.steps,
        },
        "case_packet": case_packet,
    }
