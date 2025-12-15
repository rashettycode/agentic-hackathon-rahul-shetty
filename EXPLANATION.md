# Technical Explanation

This document explains how the Workflow Intake Agent processes requests, how its components interact, and how decisions can be traced and audited.

---

## 1. Agent Workflow

The agent follows a deterministic, auditable workflow designed for enterprise intake and case management scenarios.

### Step-by-step flow

1. **Receive user input**  
   - Input is received either as free text (early demo) or via a structured form UI.
   - Follow-up requests include an existing `CASE-YYYYMMDD-HHMMSS` identifier.

2. **(Optional) Retrieve relevant memory**  
   - If a Case ID is detected, the system checks whether it already exists using an append-only event log.
   - Existing cases are never overwritten; all updates are appended as events.

3. **Plan sub-tasks**  
   - The planner classifies the request into a case type (e.g., general, access request, status request).
   - It determines required fields and a high-level execution plan.

4. **Execute and extract information**  
   - The executor performs deterministic parsing first.
   - Gemini is optionally used for entity extraction and natural-language summarization.
   - If Gemini fails or is unavailable, the system falls back to rule-based extraction.

5. **Generate case event**  
   - Either:
     - `case_created` (new case), or
     - `follow_up` (existing case update)
   - Missing information is detected and bundled into a single clarifying question.

6. **Persist and replay state**  
   - Events are appended to an on-disk JSONL store.
   - The current case state is reconstructed via event replay.

7. **Return output**  
   - UI response (human-facing)
   - Structured Case Packet (machine-facing)
   - Current merged case state (audit-facing)

---

## 2. Key Modules

### Planner (`planner.py`)
- Classifies incoming requests into a case type.
- Determines required fields and execution steps.
- Keeps logic simple and deterministic for auditability.

**Responsibility:** *What kind of case is this, and what information is required?*

---

### Executor (`executor.py`)
- Core intelligence of the system.
- Handles:
  - Text normalization
  - Entity extraction (Gemini + deterministic fallback)
  - Missing-field detection
  - Priority and SLA calculation
  - Routing decisions
  - Case packet construction
- Supports both new cases and follow-ups.

**Responsibility:** *Turn raw input into a structured, enterprise-ready Case Packet.*

---

### Memory / Case Store (`case_store.py`)
- Implements an append-only event log using JSON Lines.
- Supports:
  - Case existence checks
  - Event persistence
  - Event replay to rebuild current state

**Responsibility:** *Auditability, traceability, and replayable state.*

---

### Agent Coordinator (`agent.py`)
- Orchestrates planner → executor → memory.
- Keeps control flow explicit and testable.
- Acts as the “traffic controller” for the system.

**Responsibility:** *Glue code that coordinates the workflow.*

---

### Web UI (`webapp.py`)
- Thin Flask-based UI.
- Converts form input into agent-compatible text.
- Displays:
  - Agent response
  - Case events
  - Merged case state
  - Draft responses

**Responsibility:** *Presentation only — no business logic.*

---

## 3. Tool Integration

### Google Gemini API
Used selectively for:
- Entity extraction
- Natural-language summaries
- Polite bundled clarifying questions

**Design choice:**  
Gemini enhances usability but is never required for correctness.  
All critical paths have deterministic fallbacks.

---

### Deterministic Rule Engine
Used for:
- Case ID detection
- Required-field enforcement
- Priority and SLA calculation
- Routing decisions

This ensures predictable behavior even when LLMs fail.

---

## 4. Observability & Testing

### Observability
- All case mutations are stored as immutable events.
- Event replay allows judges to trace:
  - What changed
  - When it changed
  - Why it changed

### Debugging & Traceability
- Each Case Packet includes:
  - Tools used
  - Flags for failures
  - Notes for auditing

### Testing Strategy
- Manual test scenarios:
  - New case creation
  - Follow-up submission
  - Missing-field clarification
  - Status request
- Replay testing by inspecting `cases.jsonl`.

## 4. Observability & Testing

### Event Logging
All case activity is recorded as **append-only events** in `data/cases.jsonl`.

- `case_created` events represent new intake requests
- `follow_up` events capture additional user-provided information
- Current case state is reconstructed using **event replay**

This provides a complete audit trail for every case.

### Debug & Audit Tools

- **`debug_audit.py`**
  - Contains helper functions for inspecting stored case events
  - Enables developers and judges to:
    - Review raw events
    - Rebuild case state deterministically
    - Verify follow-up handling logic

The debug module is **read-only** and never alters stored data, ensuring
audit integrity.

### Error Handling & Safety
- Gemini failures fall back to deterministic rules
- Invalid or incomplete inputs trigger clarifying questions
- Status checks are handled as read-only operations to prevent event loops

This observability approach makes agent behavior transparent, explainable,
and easy to validate during demos or reviews.


---

## 5. Known Limitations

- No authentication or access control (demo scope).
- On-disk JSONL storage is not horizontally scalable.
- Case type detection is intentionally conservative.
- Long or highly ambiguous inputs may still require clarification.
- UI is minimal and designed for demonstration, not production UX.

---

## Summary

This system demonstrates how agent-based workflows can be built with:
- Deterministic guarantees
- Auditability
- Controlled LLM usage
- Enterprise-aligned design principles

It prioritizes correctness, transparency, and maintainability over speculative autonomy.
