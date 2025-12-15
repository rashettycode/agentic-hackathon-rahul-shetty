"""
debug_audit.py

Small debugging helper to diagnose Gemini + agent issues.

What it checks:
1) Is GEMINI_API_KEY loaded?
2) Can we call Gemini directly?
3) Does the agent run and what does the audit say?

Run:
    python -m src.debug_audit
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from src.agent import run_agent


def load_environment() -> None:
    """
    Load .env for local development.

    This allows GEMINI_API_KEY to be available when running this script.
    """
    load_dotenv()


def check_env() -> None:
    """Print whether GEMINI_API_KEY is visible to Python."""
    key_present = bool(os.getenv("GEMINI_API_KEY"))
    print(f"GEMINI_API_KEY loaded: {key_present}")


def check_gemini_direct() -> None:
    """
    Try a direct Gemini call.

    If this fails, the agent will also fail and fallback to stub.
    """
    try:
        from google import genai  # import here so the script still runs without it

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say hello in one short sentence.",
        )
        print("Gemini direct call: OK")
        print(f"Gemini says: {response.text.strip()}")
    except Exception as exc:
        print("Gemini direct call: FAILED")
        print(f"Error: {repr(exc)}")


def run_agent_test() -> None:
    """Run the agent once and print key debug fields."""
    test_request = (
        "Please grant read-only access to the Shared Finance folder for John Doe "
        "(john.doe@example.com) and Jane Roe (jane.roe@example.com). "
        "The approver is Mary Smith. Access is required by next Friday."
    )

    result = run_agent(test_request)
    packet = result.get("case_packet", {})
    audit = packet.get("audit", {})

    print("\n--- Agent Test ---")
    print(f"case_type: {packet.get('case_type')}")
    print(f"tools_used: {audit.get('tools_used')}")
    print(f"flags: {audit.get('flags')}")
    print(f"missing_info: {packet.get('missing_info')}")
    print(f"entities: {packet.get('entities')}")


def main() -> None:
    load_environment()
    check_env()
    check_gemini_direct()
    run_agent_test()


if __name__ == "__main__":
    main()
