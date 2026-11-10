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
- [x] **Curious Follow-Up on Generic Occupation Answers**: Engineered natural conversation deepening when users give generic occupation responses (e.g., "business", "job", "college", "student", "freelance", "startup"). Instead of instantly jumping to hobbies or music, Simran asks exactly one natural, curious follow-up ("Business mein kya karte ho?", "College mein kya padh rahe ho?", "Job kis field mein hai?") before sharing her design work and advancing. Backed by `is_generic_occupation()` detection and dynamic LLM context guidance in `OnboardingTracker`.
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
- [x] **Dynamic Procedural 3D Simplex Noise & Non-Repetitive Orb Styles**: Explored and engineered non-repetitive organic motion for the 12,000 particle Speaking Orb using procedural 3D simplex curl turbulence (`snoise`) and non-linear orbital dynamics. Curated 3 distinctive visual styles:
  - **`✨ Astral` (Astral Stardust - Recommended Best)**: Deep cosmic stardust cloud with fluid turbulence, StarMaker Royal Purple core shifting to vibrant Hot Pink with bright Electric Cyan acoustic sparkles and upward traveling syllable rings.
  - **`🌟 Plasma` (Bioluminescent Plasma Core)**: Energetic solar/plasma orb with coronal mass ejections and radiant flares reacting to vocal dynamics.
  - **`🎵 Sonic` (Cyber Sonic Wave)**: Harmonic acoustic latitude rings undulating like a futuristic 3D equalizer.
  Added interactive style picker pills in `SimranPresence.tsx` with persistent `localStorage` memory and synchronized Web Component support in `web/public/speaking-orb.js`.
- [x] **Viewport Lock & Sticky Mic Controls**: Fixed studio layout to lock to `100vh`/`100dvh` with sticky bottom controls (`stage-controls`), ensuring the Mic On/Off toggle, Call button, and stage visualizers fit within the screen without requiring vertical page scrolling on desktop or mobile.
- [x] **StarMaker True Brand Aesthetic (White Canvas + Royal Purple + Hot Pink)**: Redesigned the entire web studio UI adopting StarMaker's authentic color hierarchy: 60% pure white canvas (`#ffffff`), 30% royal/electric purple (`#7c3aed`), and 10% high-energy hot pink (`#ff2e93`), with golden accents for coin rewards. Replaced legacy dark modals and cards with radiant white surfaces, lavender borders, and crisp high-contrast obsidian-plum typography.
- [x] **Speaking Orb (12,000 Particle WebGL Voice Assistant Face)**: Implemented the complete Aqualang/Signal Speaking Orb specification in `SpeakingOrb.tsx` and standalone `web/public/speaking-orb.js`: 12,000 particles (6,000 touch), real-time voice swell, traveling bottom-to-top lit rings on syllables, particle-landed live captions with `aria-live="polite"` and word-by-word highlights, and full `<speaking-orb>` Web Component API (`say(text, {audio})`, `listen()`, `state`, `level`, `rest`, and `end` events).
- [x] **StarMaker-Inspired Live Stage Experience**: Transformed web studio into a polished StarMaker karaoke experience with deep obsidian stage atmosphere (`#090714`), glassmorphic panels, and glowing neon accents.
- [x] **Seamless Live Duet & Solo Stage Redirection**: Seamlessly redirects the main view to the StarMaker Live Stage or Solo Recording Studio upon joining or receiving navigation triggers.
- [x] **Dynamic Free Coin Reward Celebration**: Auto-detects coin mentions in Simran's voice speech and triggers a celebratory StarMaker Gold Coin popup with spinning 3D coin, sunburst rays, and instant bonus claiming.
- [x] **Interactive Floating Gifts Particle System**: Implemented live stage gift launcher supporting 🌹 Rose (5 C), 🎙️ Golden Mic (10 C), 👑 VIP Crown (25 C), and 🚀 Star Rocket (50 C) with animated floating emoji shower and audience reaction ticker.
- [x] **Synchronized Karaoke Teleprompter**: Synchronized multi-part lyrics with bouncing musical ball (`🎵`), glowing active-line highlight, and harmonic Web Audio chord synthesizer.
- [x] **Real-Time Vocal Pitch Rating Meter**: StarMaker vocal grading badges (`SSS`, `SS`, `S`, `A`) with dynamic accuracy percentage and neon gradient meter.
- [x] **VIP Front-Row Cheer Pod**: Embedded Simran in the front-row VIP seat with live cheering speech bubble synchronized with ongoing speech turns.
- [x] **Full Mobile Responsiveness & Segmented Switcher**: Designed mobile layout (`100dvh`, no horizontal overflow) with top segmented switcher (`[🎤 Studio Stage]` / `[💬 Simran & Chat]`), notification indicators, touch-optimized buttons (>=44px), and slide-up bottom sheets.
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

