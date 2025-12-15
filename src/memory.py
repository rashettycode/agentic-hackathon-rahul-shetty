"""
memory.py

Simple, audit-friendly persistence for Case Packets / Events.

Design goals:
- Zero imports from other project modules (prevents circular imports)
- Append-only JSONL log for auditability (data/cases.jsonl)
- Safe file handling and minimal validation
- Can be replaced later with a DB/queue without changing agent.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DATA_PATH = Path("data/cases.jsonl")


# ---------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------

def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _safe_json_dumps(obj: Dict[str, Any]) -> str:
    """
    Serialize consistently for audit logs.
    - ensure_ascii=False keeps names readable
    - separators makes JSON compact
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def _safe_read_lines(path: Path) -> Iterable[str]:
    if not path.exists():
        return []
    # Ignore bad lines gracefully (enterprise logs tend to get messy)
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def append_case(case_packet: Dict[str, Any], *, path: Path = DATA_PATH) -> None:
    """
    Append a single case event to the JSONL audit log.

    Expected:
      case_packet["event_type"] in {"case_created", "follow_up"} (optional but recommended)
      case_packet["case_id"] present for all events

    This function does not raise on minor issues; it aims to be resilient.
    """
    if not isinstance(case_packet, dict):
        return

    # minimal sanity check
    case_id = case_packet.get("case_id")
    if not isinstance(case_id, str) or not case_id.strip():
        return

    _ensure_parent_dir(path)
    line = _safe_json_dumps(case_packet)

    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_cases(*, path: Path = DATA_PATH, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Load events from JSONL. Useful for debugging.

    limit:
      - None: load all
      - int: load last N events (efficient enough for demo scale)
    """
    lines = list(_safe_read_lines(path))
    if limit is not None and limit > 0:
        lines = lines[-limit:]

    out: List[Dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            # ignore malformed lines
            continue
    return out
