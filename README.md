# STS Lab: Gemini 3.8 Live Speech-to-Speech Architecture

Standalone implementation of Simran — Roxstar's AI Onboarding & Musical Buddy voice host powered directly by **Google Gemini 3.8 Live API** (Speech-to-Speech) and **LiveKit Cloud**.

---

## Architecture Overview

```
STS Lab Standalone
├── AGENTS.md              # AI Agent Development Guidelines & Rules
├── config.py              # Configuration & Voice Setting (Leda, 24kHz Opus)
├── token_server.py        # Token Dispatcher on http://127.0.0.1:8001
├── worker.py              # LiveKit Agent Worker (native Gemini Live multimodal session)
├── prompt.py              # Simran 22yo South Delhi Persona & Conversational Funnels
├── onboarding.py          # State Machine, User Discovery Profile & Stage Tracking
├── run_sts.py             # Concurrent Supervisor (Token Server + Worker)
├── requirements.txt       # Pinned Python Dependencies
├── .env                   # LiveKit and Gemini API Credentials
├── docs/                  # Architecture & System Documentation
│   ├── PROJECT_CONTEXT.md # Architecture, data flows, and tech decisions
│   ├── WORKFLOW.md        # End-to-end onboarding workflows & sequence diagrams
│   ├── TASKS.md           # Implementation progress & roadmap tracker
│   └── CHANGELOG.md       # Chronological record of major changes
├── tests/                 # 23-scenario Pytest Suite
└── web/                   # 2-Pane Clean React/TypeScript Studio Stage
```

---

## Documentation System

- [`AGENTS.md`](file:///y:/roxstar/sts_lab/AGENTS.md) — Persistent AI agent development guidelines, coding conventions, and guardrails
- [`docs/PROJECT_CONTEXT.md`](file:///y:/roxstar/sts_lab/docs/PROJECT_CONTEXT.md) — Full technical architecture, data flows, module responsibilities, and data contracts
- [`docs/WORKFLOW.md`](file:///y:/roxstar/sts_lab/docs/WORKFLOW.md) — Conversational funnels, sequence diagrams, and product lifecycle
- [`docs/TASKS.md`](file:///y:/roxstar/sts_lab/docs/TASKS.md) — Task completion tracker, ongoing work, known debt, and next steps
- [`docs/CHANGELOG.md`](file:///y:/roxstar/sts_lab/docs/CHANGELOG.md) — Record of architectural pivots and feature milestones

---

## Quickstart

### 1. Python Backend Setup

```bash
# 1. Create and activate a Python 3.11+ virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Ensure your .env credentials are populated
# LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, GEMINI_API_KEY
```

### 2. Frontend Setup

```bash
cd web
npm install
cd ..
```

---

## Running the Application

### 1. Launch Backend (Supervisor)
In terminal 1:
```bash
python run_sts.py
```
This launches:
* **STS Token Server**: `http://127.0.0.1:8001`
* **LiveKit Agent Worker**: `sts-simran` connected to LiveKit Cloud.

### 2. Launch Web Stage
In terminal 2:
```bash
npm --prefix web run dev
```
Open **`http://127.0.0.1:5175/`** in your browser to interact with Simran on live voice.

---

## Running Verification Tests

```bash
pytest tests/ -v
```
All 23 user scenarios and state tests will execute and pass.

