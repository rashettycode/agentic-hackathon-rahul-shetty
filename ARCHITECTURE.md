## 2. `ARCHITECTURE.md`

```markdown
# Architecture Overview

# Architecture Overview

This project is a lightweight enterprise intake agent with:
- a simple Flask form UI
- a planner that classifies the request
- an executor that builds a structured case event (case_created or follow_up)
- an append-only event log (JSONL) + event replay to reconstruct current case state

---

## High-Level Diagram

+-------------------+ +--------------------+
| Flask Web UI | POST | Agent Core |
| (src/webapp.py) +-------->+ (src/agent.py) |
| - form fields | | - orchestrates |
| - UI banner | | - returns outputs |
+---------+----------+ +----+-----------+---+
| | |
| | |
| v v
| +-------------+ +--------------+
| | Planner | | Executor |
| |(planner.py) | | (executor.py) |
| | - case_type | | - entities |
| | - steps | | - routing |
| +------+------+ | - event_type |
| | +------+--------+
| | |
| v v
| (plan object) (case event dict)
| |
v v
+-------------------+ +----------------------+
| UI Output & Debug | | Case Store |
| - Agent Response | | (case_store.py) |
| - Plan | | - append_record() |
| - Case Event JSON | | - cases.jsonl log |
| - Replay State |<--------------------+ - get_case_state() |
+-------------------+ replay +----------------------+


---

## Components

### 1) User Interface
**Implementation:** Flask (src/webapp.py)

**Responsibilities**
- Collect structured inputs (Case ID optional, department/program, contact, details)
- Convert form fields into a single labeled text block (`compose_request_text`)
- Show:
  - Agent Response banner (user-facing message)
  - Plan (debug)
  - Case Event (debug)
  - Current Case State (merged via event replay)

**Key design choice**
- The UI is intentionally thin. It does not “decide” case logic.
  It just gathers inputs and displays outputs.

---

### 2) Agent Core

#### Agent Orchestrator (src/agent.py)
- Calls the planner to classify the request
- Calls the executor to build a case event
- Returns `plan` + `case_packet` to the UI

#### Planner (src/planner.py)
- Produces:
  - `case_type` (general, access_request, security_incident, meeting_request, status_request)
  - `steps` (simple, judge-friendly plan)

#### Executor (src/executor.py)
- Extracts entities (deterministic stub by default, Gemini for selected types)
- Computes routing, priority, SLA
- Detects follow-ups:
  - If request includes `CASE-YYYYMMDD-HHMMSS` and that case exists → emits `event_type="follow_up"`
  - Otherwise → emits `event_type="case_created"`

**Outputs**
- A single event record (append-only) for storage and replay:
  - case_created: full packet with entities/missing_info/routing/draft_response
  - follow_up: entities_update + missing_info_after (+ metadata)

---

### 3) Tools / APIs

#### Google Gemini (optional)
**Used for**
- entity extraction on certain case types (access/security/meeting)
- optional summarization + clarifying question

**Fallback behavior**
- If GEMINI_API_KEY is missing or Gemini fails, system falls back to deterministic rules/stubs.

---

### 4) Memory / Persistence

#### Case Store (src/case_store.py)
- Append-only JSONL log: `data/cases.jsonl`
- `append_record(event)` writes one event per line
- `get_case_state(case_id)` rebuilds the latest state by replaying events in order:
  - start at case_created
  - apply follow_up updates
  - latest values win

**Why JSONL**
- Easy to audit
- Easy to inspect in a hackathon demo
- No database dependency

---

### 5) Observability & Safety

- Each event includes an `audit` block:
  - tools used (gemini vs rules/stub)
  - flags (e.g., gemini_failed)
- Deterministic required-fields logic ensures consistent behavior
- Status checks should be read-only (avoid writing status checks into the event log)

## 6) Design Principles

- Append-only event log (auditability)
- Deterministic fallbacks when LLMs fail
- Thin UI, thick executor
- Replayable state instead of mutable records
