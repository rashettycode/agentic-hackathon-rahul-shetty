"""
webapp.py

Simple "real form" Flask UI for demo purposes.

User flow:
1) Fill in form fields (optional Case ID for follow-ups)
2) Click Run
3) View:
   - Agent Response (UI banner)
   - Current merged case state (event replay)
   - Plan
   - Case Packet (event)
   - Draft Response

Designed to work locally and on PythonAnywhere.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from flask import Flask, render_template_string, request


# ---------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------

def load_environment() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_path)


load_environment()


# ---------------------------------------------------------------------
# Imports (after env load)
# ---------------------------------------------------------------------

from src.agent import run_agent  # noqa: E402
from src.case_store import append_record, get_case_state  # noqa: E402
from src.executor import pretty_json  # noqa: E402


# ---------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------

app = Flask(__name__)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def build_ui_message(case_packet: Dict[str, Any]) -> str:
    event_type = (case_packet or {}).get("event_type", "case_created")
    case_id = (case_packet or {}).get("case_id")

    if event_type == "status_check" and case_id:
        return f"Status for case {case_id} is shown below."

    if event_type == "follow_up" and case_id:
        return f"Thanks — we’ve added this information to your existing case {case_id}."

    return (case_packet or {}).get("draft_response") or "Thanks for your request. It has been received."


def compose_request_text(
    case_id: str,
    case_type_hint: str,
    location_or_program: str,
    requester_contact: str,
    details: str,
) -> str:
    """
    Convert form fields into the single text block your agent already understands.

    We use labels that your executor can parse deterministically.
    """
    lines = []

    if case_id.strip():
        lines.append(case_id.strip())

    # Optional hint (doesn't break anything if ignored)
    if case_type_hint and case_type_hint != "auto":
        lines.append(f"Case type: {case_type_hint}")

    if location_or_program.strip():
        lines.append(f"Department/program: {location_or_program.strip()}")

    if requester_contact.strip():
        lines.append(f"Contact: {requester_contact.strip()}")

    # Keep details last
    if details.strip():
        lines.append(details.strip())

    return "\n".join(lines).strip()


def build_render_model(result: Dict[str, Any]) -> Dict[str, Any]:
    case_packet: Dict[str, Any] = (result or {}).get("case_packet") or {}
    case_id = case_packet.get("case_id")

    model: Dict[str, Any] = {
        "case_id": case_id,
        "event_type": case_packet.get("event_type", "case_created"),
        "ui_message": build_ui_message(case_packet),
        "plan": (result or {}).get("plan") or {},
        "case_json": pretty_json(case_packet),
        "packet_draft_response": case_packet.get("draft_response")
        or "(none — follow-up/status events may not generate a draft_response)",
        "current_state": get_case_state(case_id) if case_id else None,
    }
    return model


def should_persist_event(case_packet: Dict[str, Any]) -> bool:
    """
    Only persist events that mutate case history.

    Status checks should be READ-only and should NOT be appended to cases.jsonl,
    otherwise you can create “status loops” in event replay.
    """
    event_type = (case_packet or {}).get("event_type", "case_created")
    return event_type not in {"status_check"}


# ---------------------------------------------------------------------
# HTML template (simple enterprise form)
# ---------------------------------------------------------------------

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Workflow Intake Agent (Form Demo)</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; max-width: 980px; }
    .row { display: flex; gap: 12px; margin-top: 10px; }
    .col { flex: 1; }
    label { display:block; font-weight: bold; margin-bottom: 6px; }
    input, select, textarea {
      width: 100%;
      padding: 10px;
      box-sizing: border-box;
    }
    textarea { height: 120px; }
    button { padding: 10px 14px; margin-top: 12px; cursor: pointer; }
    .box { margin-top: 18px; }
    pre { background: #f6f8fa; padding: 12px; overflow-x: auto; }
    .hint { color: #444; font-size: 0.95em; margin-top: 6px; }
    .banner {
      background: #eef6ff;
      border: 1px solid #cfe3ff;
      padding: 12px;
      border-radius: 6px;
    }
    .meta { font-size: 0.85em; color: #555; margin-bottom: 6px; }
  </style>
</head>
<body>
  <h2>Workflow Intake Agent (Form Demo)</h2>

  <div class="hint">
    New case: leave Case ID blank.<br>
    Follow-up: paste a Case ID (e.g., <code>CASE-YYYYMMDD-HHMMSS</code>).<br>
    Status: paste a Case ID + ask “status” in the details.
  </div>

  <form method="post">
    <div class="row">
      <div class="col">
        <label for="case_id">Case ID (optional)</label>
        <input id="case_id" name="case_id" placeholder="CASE-YYYYMMDD-HHMMSS" value="{{ form.case_id }}">
      </div>

      <div class="col">
        <label for="case_type">Case Type (optional)</label>
        <select id="case_type" name="case_type">
          <option value="auto" {% if form.case_type == "auto" %}selected{% endif %}>Auto-detect</option>
          <option value="general" {% if form.case_type == "general" %}selected{% endif %}>General</option>
          <option value="access_request" {% if form.case_type == "access_request" %}selected{% endif %}>Access request</option>
          <option value="security_incident" {% if form.case_type == "security_incident" %}selected{% endif %}>Security incident</option>
          <option value="meeting_request" {% if form.case_type == "meeting_request" %}selected{% endif %}>Meeting request</option>
          <option value="status_request" {% if form.case_type == "status_request" %}selected{% endif %}>Status request</option>
        </select>
      </div>
    </div>

    <div class="row">
      <div class="col">
        <label for="location_or_program">Department / Program</label>
        <input id="location_or_program" name="location_or_program" placeholder="e.g., Service" value="{{ form.location_or_program }}">
      </div>
      <div class="col">
        <label for="requester_contact">Best Contact (email or phone)</label>
        <input id="requester_contact" name="requester_contact" placeholder="e.g., name@email.com or 416-555-1234" value="{{ form.requester_contact }}">
      </div>
    </div>

    <div class="row">
      <div class="col">
        <label for="details">Request details</label>
        <textarea id="details" name="details" placeholder="Write what happened / what you need...">{{ form.details }}</textarea>
      </div>
    </div>

    <button type="submit" name="action" value="run">Run</button>
    <button type="submit" name="action" value="clear" style="margin-left:8px;">Clear</button>
  </form>

  {% if model %}
    <div class="box banner">
      <div class="meta">
        event_type: {{ model.event_type }}
        {% if model.case_id %}| case_id: {{ model.case_id }}{% endif %}
      </div>
      <b>Agent Response</b><br>
      {{ model.ui_message }}
    </div>

    {% if model.current_state %}
      <div class="box">
        <h3>Current Case State (Merged)</h3>
        <pre>{{ model.current_state | tojson(indent=2) }}</pre>
      </div>
    {% endif %}

    <div class="box">
      <h3>Plan</h3>
      <pre>{{ model.plan | tojson(indent=2) }}</pre>
    </div>

    <div class="box">
      <h3>Case Packet (Event)</h3>
      <pre>{{ model.case_json }}</pre>
    </div>

    <div class="box">
      <h3>Draft Response (Packet)</h3>
      <pre>{{ model.packet_draft_response }}</pre>
    </div>
  {% endif %}
</body>
</html>
"""


# ---------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------

@app.route("/", methods=["GET", "POST"])
def home():
    # Keep form values sticky
    form = {
        "case_id": "",
        "case_type": "auto",
        "location_or_program": "",
        "requester_contact": "",
        "details": "",
    }
    model: Optional[Dict[str, Any]] = None

    if request.method == "POST":
        action = request.form.get("action", "run")

        if action == "clear":
            return render_template_string(HTML_TEMPLATE, form=form, model=None)

        # Read fields
        form["case_id"] = (request.form.get("case_id") or "").strip()
        form["case_type"] = (request.form.get("case_type") or "auto").strip()
        form["location_or_program"] = (request.form.get("location_or_program") or "").strip()
        form["requester_contact"] = (request.form.get("requester_contact") or "").strip()
        form["details"] = (request.form.get("details") or "").strip()

        # Convert form -> existing agent input text
        user_text = compose_request_text(
            case_id=form["case_id"],
            case_type_hint=form["case_type"],
            location_or_program=form["location_or_program"],
            requester_contact=form["requester_contact"],
            details=form["details"],
        )

        if user_text:
            result = run_agent(user_text)

            # Persist event for replay — BUT NOT status checks
            case_packet = (result or {}).get("case_packet") or {}
            if should_persist_event(case_packet):
                append_record(case_packet)

            # View model
            model = build_render_model(result)

    return render_template_string(HTML_TEMPLATE, form=form, model=model)


if __name__ == "__main__":
    app.run(debug=True)
