# TASKS.md — Development Progress Tracker

> **Current Sprint**: STS Lab Stabilization & Conversational Calibration  
> **Verification Status**: 23/23 Automated Tests Passing | Frontend Production Build Passing

---

## 1. Completed Tasks (Verified)

### Core Architecture & Media Pipeline
- [x] **Direct Speech-to-Speech (S2S) Engine**: Integrated Google Gemini 3.8 Live API (`gemini-3.8-live`) via `livekit-plugins-google.realtime.RealtimeModel` with native bidirectional 24kHz PCM audio streaming.
- [x] **LiveKit Agent Worker**: Implemented prewarmed worker (`worker.py`) connecting as `sts-simran` with `JobExecutorType.THREAD` and `num_idle_processes=1`.
- [x] **Concurrent Supervisor**: Implemented `run_sts.py` to concurrently spawn, monitor, and auto-restart `token_server.py` and `worker.py`.
- [x] **Dedicated Token Server**: Built HTTP server on port 8001 handling `/token`, `/rooms`, `/health`, and `/duets` with parallel LiveKit room prep and agent dispatch.

### Persona & Conversational Design
- [x] **Simran 22yo South Delhi Persona**: Authored system prompt (`prompt.py`) with urban Hinglish vernacular, 3-gear conversational energy, turn limits (12–22 words), and Trade Rule.
- [x] **2-Attempt Singing Encouragement Flow**: Structured 2-attempt low-pressure encouragement before sign-off (Attempt 1: no perfect singer needed + duet bridge; Attempt 2: post fav song + personal listen/comment promise).
- [x] **Anti-Chit-Chat Excuse Engine**: Implemented strict 2-decline exit rule using authentic personal excuses (Swiggy, chai, client ping, battery low) to gracefully close sessions under 25 words.
- [x] **Silent Tool Execution**: Defined 4 function tools (`save_profile`, `check_available_duets`, `navigate_to_duet`, `navigate_to_recording`) operating silently without conversational announcements.
- [x] **Clean Stage Handover & Bot Power-Off**: Implemented audio track detachment, session closure, and job shutdown (`turn_off_bot`) when user transitions to singing or solo recording.

### Onboarding State Machine & Persistence
- [x] **8-Topic User Discovery Engine**: Implemented `OnboardingTracker` tracking Name, Location, Occupation, Hobbies, Music Taste, Expectations, Duet Attempted, and Coins Guidance.
- [x] **Profile Persistence**: Created `UserProfileStore` storing discovered attributes in `.sts_users.json` with returning-user recognition and customized greetings.
- [x] **Duet Room Registry**: Built `DuetRoomRegistry` matching available live rooms by genre and preventing hallucinations of nonexistent rooms.
- [x] **Contextual Tooltip Engine**: Implemented deduplicated interactive guidance events (`singing_started`, `posting`, `commenting`, `gifting`).
- [x] **Virtual Coin Rewards**: Added 50 welcome coin bonus grant and gift-sending logic (`roxstar.coins_awarded`, `roxstar.coin_balance`).

### Frontend Web Studio
- [x] **2-Pane Studio UI**: Built modern React 19 + TypeScript studio with live audio visualizer (`SimranPresence`, `AudioVisualizer`), stage bar, controls, and telemetry pill.
- [x] **Live Transcripts & State Sync**: Implemented scrolling transcript view for user and Simran turns, backed by WebRTC DataPackets.
- [x] **Discovery Badges**: Added real-time visual tags displaying captured user attributes.
- [x] **One-Click Batch Launchers**: Added `start_backend.bat` and `start_web.bat` for quick local startup on Windows.

### Test Coverage & Verification
- [x] **Automated Test Suite**: Built 23 tests covering all unit functionality and 14 onboarding user journey scenarios (`tests/test_sts_onboarding.py`, `tests/test_sts_onboarding_scenarios.py`).

### Deployment & Containerization
- [x] **Production Multi-Stage Dockerfile**: Multi-stage build compiling React 19 frontend and running Python 3.11 STS supervisor on port 8001/`$PORT`.
- [x] **Koyeb & Cloud Compatibility**: Configured unified full-stack serving in `token_server.py`, dynamic host/port binding in `config.py`, and production origin auto-detection in `tokenService.ts`.

### Documentation & Project Memory
- [x] **Persistent Project Memory System**: Established structured documentation system with [`AGENTS.md`](file:///y:/roxstar/sts_lab/AGENTS.md) and [`README.md`](file:///y:/roxstar/sts_lab/README.md) in the root, and centralized architecture & tracking documents in [`docs/`](file:///y:/roxstar/sts_lab/docs/) (`PROJECT_CONTEXT.md`, `WORKFLOW.md`, `TASKS.md`, `CHANGELOG.md`).

---

## 2. Currently Ongoing Tasks

- [ ] **Voice Parameter Alignment**: Harmonize default voice string between `config.py` (`Leda`) and `web/src/hooks/useStsRoom.ts` (`Sulafat`).

---

## 3. Pending Tasks & Roadmap

### High Priority
- [ ] **Dynamic LiveKit Cloud Webhook / Microservice Sync**: Replace static initial rooms in `DuetRoomRegistry` with live API sync from RoxStar backend services.
- [ ] **Configurable Voice Timbre in Frontend**: Allow switching between Gemini voice options (`Leda`, `Sulafat`, `Puck`, `Aoede`) directly from the web studio settings.
- [ ] **Database Adapter Layer**: Abstract `UserProfileStore` into an interface supporting PostgreSQL / Redis alongside local JSON.

### Medium Priority
- [ ] **Audio Barge-In Client Optimization**: Optimize client-side Web Audio buffer discarding when the user interrupts Simran mid-sentence.
- [ ] **Bilingual Audio Latency Benchmark Dashboard**: Add visual charts to `LatencyCard` logging TTFA (ms) percentiles (p50, p95) over extended voice sessions.
- [ ] **Session Resumption Support**: Implement Gemini Live session resumption token caching so temporary network drops do not reset onboarding progress.

### Low Priority / Exploration
- [ ] **Multi-Agent Room Jamming**: Explore dynamic handoff to a second live agent (e.g., Kabir or another singer) within the same WebRTC room.

---

## 4. Known Bugs, Technical Debt & Blockers

- **Voice Label Mismatch**:
  - *Detail*: `config.py` defaults to `Leda`, while `useStsRoom.ts` displays `Sulafat` in the telemetry pill before backend state syncs.
  - *Impact*: Minor visual inconsistency until backend sends telemetry packet.
- **Python Execution on Windows**:
  - *Detail*: Global `python` or `pytest` may not be registered in system PATH; running via `py -m pytest tests/` or `py run_sts.py` is required.
  - *Impact*: Documented in [`AGENTS.md`](file:///y:/roxstar/sts_lab/AGENTS.md) and [`docs/PROJECT_CONTEXT.md`](file:///y:/roxstar/sts_lab/docs/PROJECT_CONTEXT.md).
- **In-Memory Duet Rooms**:
  - *Detail*: Duet rooms created dynamically during a session exist only in worker memory and reset when the worker restarts.

---

## 5. Next Recommended Development Steps

1. Harmonize default voice parameter between `config.py` and `web/src/hooks/useStsRoom.ts`.
2. Add a lightweight test script to verify token server endpoints (`GET /health`, `POST /token`) in automated CI.

