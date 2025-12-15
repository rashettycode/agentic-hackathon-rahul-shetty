

# Agentic AI App Hackathon — Workflow Intake Agent

Welcome to our submission for the **Agentic AI App Hackathon**.

This project demonstrates an **enterprise-style agentic intake system** that transforms unstructured requests into structured, auditable case records using a hybrid of deterministic logic and Google Gemini.

The system is designed to be:
- Traceable
- Deterministic where it matters
- Augmented (not replaced) by LLMs
- Suitable for real-world operational workflows

---

## 📋 Submission Checklist

- [x] All code in `src/` runs without errors  
- [x] `ARCHITECTURE.md` contains a clear diagram and explanation  
- [x] `EXPLANATION.md` covers planning, tools, memory, and limitations  
- [ ] `DEMO.md` links to a 3–5 min demo video 

---

## 🚀 Getting Started

### 1. Clone / Fork this repository

> **Important:**  
> Fork name **must match the  name** exactly

```bash
git clone https://github.com/<your-team-name>/<repo-name>.git
cd <repo-name>


### 2.Set up the environment

Create a virtual environment and install dependencies:
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

Create a .env file:
GEMINI_API_KEY=your_api_key_here

### 3. Run the app locally
python -m src.webapp

Open your browser at: http://127.0.0.1:5000

What This App Does

The Workflow Intake Agent helps organizations handle inbound requests such as:

General inquiries

Access requests

Security incidents

Meeting requests

Case status checks

It converts free-form input into structured case events that can be audited, replayed, and extended.

## 📂 Folder Layout
.
├── src/
│ ├── agent.py # Agent orchestrator (planner → executor → memory)
│ ├── planner.py # Request classification & required-field planning
│ ├── executor.py # Case Packet construction (deterministic + Gemini)
│ ├── case_store.py # Event store (append-only) + event replay
│ ├── debug_audit.py # Debug & audit helpers for inspecting case history
│ ├── webapp.py # Flask-based form UI (demo interface)
│
├── data/
│ └── cases.jsonl # Event-sourced case history (append-only)
│
├── ARCHITECTURE.md # System architecture & component diagram
├── EXPLANATION.md # Technical design and agent workflow
├── DEMO.md # Demo video link & timestamps
├── requirements.txt
└── README.md


## High-Level Architecture

**Key idea:**  
Cases are not mutable records — they are **event streams**.

- New requests create a `case_created` event  
- Follow-ups append `follow_up` events  
- Current case state is rebuilt via **event replay**

This enables:

- Full audit trails  
- Safe updates  
- Deterministic debugging  

---

## 🧪 How Gemini Is Used (and Why)

Google Gemini is used **selectively**, not blindly.

### Gemini assists with:
- Entity extraction from natural language  
- Polite clarifying questions when information is missing  
- Short summaries and “next steps” text  

### Gemini is **NOT** used for:
- Case routing  
- SLA calculation  
- Priority decisions  
- Case ID handling  

All critical decisions have **deterministic fallbacks**, ensuring reliability even if the LLM fails.

---

## 🏅 Alignment with Judging Criteria

### ✅ Technical Excellence
- Deterministic core logic  
- Clear separation of concerns  
- Graceful LLM failure handling  
- Event-sourced state management  

### ✅ Solution Architecture & Documentation
- Modular, readable codebase  
- Clear agent workflow  
- Explicit trade-offs documented  
- Reproducible setup  

### ✅ Innovative Gemini Integration
- Gemini augments human-friendly behavior  
- Used where language understanding adds real value  
- Avoids over-reliance on LLMs  

### ✅ Societal Impact & Novelty
- Applicable to government, healthcare, and enterprise intake  
- Improves transparency and response handling  
- Reduces lost or ambiguous requests  
- Demonstrates responsible agent design  

---

## ⚠️ Known Limitations

- No authentication or role-based access (demo scope)  
- JSONL storage is not horizontally scalable  
- UI is intentionally minimal  
- Case-type detection is conservative by design  

(See `EXPLANATION.md` for details.)

---

## 🎥 Demo Video

5 minute walkthrough video
https://www.canva.com/design/DAG7gXS9D2I/awRhpu-vKV2HpUKM-O8GTQ/edit

---

## 📌 Final Note

This project prioritizes **clarity, auditability, and correctness** over speculative autonomy.  
It demonstrates how agentic systems can be designed responsibly for real operational environments.

Thank you for reviewing our submission.





