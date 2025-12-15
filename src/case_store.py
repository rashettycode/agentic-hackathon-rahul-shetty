import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_PATH = Path("data/cases.jsonl")

# Events that should NOT change case state (read-only)
READ_ONLY_EVENTS = {"status_check"}


def load_records() -> List[Dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    with DATA_PATH.open("r", encoding="utf-8") as f:
        out: List[Dict[str, Any]] = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # Skip corrupted lines rather than crashing
                continue
        return out


def append_record(record: Dict[str, Any]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _parse_iso(dt: Any) -> Optional[datetime]:
    """
    Parse ISO8601 datetimes safely.
    Returns None if parsing fails.
    """
    if not dt or not isinstance(dt, str):
        return None
    try:
        # Handles "2025-12-13T14:45:09-05:00"
        return datetime.fromisoformat(dt)
    except Exception:
        return None


def _event_type(rec: Dict[str, Any]) -> str:
    """
    Normalize event_type with backward-compatible defaults.
    """
    et = rec.get("event_type")
    if isinstance(et, str) and et.strip():
        return et.strip()

    # Backward compat: some earlier packets omitted event_type.
    # Treat as case_created only if it looks like a creation packet.
    if "routing" in rec and "entities" in rec and ("request_text" in rec or "summary" in rec):
        return "case_created"

    # Otherwise, unknown / ignore
    return "unknown"


def _records_for_case(case_id: str) -> List[Dict[str, Any]]:
    records = [r for r in load_records() if r.get("case_id") == case_id]
    # Sort by created_at when present; fall back to original order
    records.sort(key=lambda r: (_parse_iso(r.get("created_at")) or datetime.min))
    return records


def case_exists(case_id: str) -> bool:
    """
    True if we have ever created this case_id (a case_created record).
    """
    for rec in reversed(_records_for_case(case_id)):
        if _event_type(rec) == "case_created":
            return True
    return False


def get_case_state(case_id: str) -> Optional[Dict[str, Any]]:
    """
    Build the latest state of a case by replaying events.

    Rules:
    - Start from case_created
    - Apply follow_up entity updates in order (latest wins)
    - Ignore read-only events (e.g., status_check)
    """
    records = _records_for_case(case_id)
    if not records:
        return None

    state: Dict[str, Any] = {}
    saw_create = False

    for rec in records:
        et = _event_type(rec)
        if et in READ_ONLY_EVENTS or et == "unknown":
            continue

        if et == "case_created":
            saw_create = True
            state = {
                "case_id": rec.get("case_id"),
                "case_type": rec.get("case_type"),
                "created_at": rec.get("created_at"),
                "priority": rec.get("priority"),
                "sla_days": rec.get("sla_days"),
                "routing": rec.get("routing"),
                "entities": dict(rec.get("entities") or {}),
                "missing_info": list(rec.get("missing_info") or []),
                # helpful metadata
                "last_updated_at": rec.get("created_at"),
                "last_event_type": "case_created",
            }
            continue

        # If we somehow get follow-ups before create, ignore them
        if et == "follow_up" and not saw_create:
            continue

        if et == "follow_up":
            updates = rec.get("entities_update") or {}
            state.setdefault("entities", {})

            # merge non-null updates
            for k, v in updates.items():
                if v is not None:
                    state["entities"][k] = v

            # update missing info if provided
            if "missing_info_after" in rec:
                state["missing_info"] = list(rec.get("missing_info_after") or [])

            # meta
            state["last_updated_at"] = rec.get("created_at")
            state["last_event_type"] = "follow_up"

    return state or None
