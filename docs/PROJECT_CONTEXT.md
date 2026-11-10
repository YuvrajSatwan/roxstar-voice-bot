# PROJECT_CONTEXT.md — Project Knowledge & Architecture

> **Repository**: RoxStar Speech-to-Speech (STS) Lab  
> **Status**: Production-ready Prototype  
> **Last Updated**: November 2026

---

## 1. Project Purpose & Primary Functionality

**STS Lab** is a high-performance, low-latency AI Voice Companion prototype built for **RoxStar**, an India-born social singing and karaoke platform.

The system powers **Simran**, a 22-year-old female music host and digital companion from South Delhi. Simran guides new users through real-time conversational onboarding, discovers their musical tastes, introduces app features (duet rooms, solo recording, community posting, and free daily coin gifting), and gracefully transitions the user to singing before powering down her voice agent to leave the stage completely to the user.

---

## 2. Technology Stack

| Domain | Technology / Library | Purpose |
| :--- | :--- | :--- |
| **Speech-to-Speech AI** | Google Gemini 3.8 Live API (`gemini-3.8-live`) | Direct multimodal native speech-to-speech without cascading STT/TTS |
| **Media Routing** | LiveKit Cloud & LiveKit WebRTC | Low-latency audio transport, room orchestration, and data channel messaging |
| **Agent Framework** | `livekit-agents` (1.8+), `livekit-plugins-google` | Realtime agent session, tool bindings, and worker thread lifecycle |
| **Backend Language** | Python 3.11+ (Runtime: Python 3.14 on Windows) | Asynchronous backend services and state engine |
| **Backend HTTP API** | Python `ThreadingHTTPServer` / `BaseHTTPRequestHandler` | Concurrent room provisioning and token minting on port 8001 |
| **Frontend UI** | React 19, TypeScript, Vite 8 | Two-pane interactive studio stage, audio visualizers, and state badges |
| **Frontend Media** | `livekit-client` (2.22+) | WebRTC audio track publishing, audio level analysis, and data listener |
| **Persistence** | Local JSON store (`.sts_users.json`) | Returning user profile memory across sessions |
| **Test Suite** | Pytest 9.x, `pytest-asyncio`, `anyio` | 21 end-to-end state and onboarding scenario tests |

---

## 3. High-Level Architecture & Data Flow

```mermaid
flowchart TD
    subgraph Browser ["Client Web Browser (:5175)"]
        UI["React Web Studio UI"]
        RTC["WebRTC Audio Engine & Visualizer"]
    end

    subgraph Backend ["STS Lab Local Services"]
        Supervisor["Supervisor (run_sts.py)"]
        TokenServer["Token Server (:8001)"]
        Worker["LiveKit STS Worker (worker.py)"]
        Engine["State & Discovery Engine (onboarding.py)"]
        Prompt["Persona Engine (prompt.py)"]
    end

    subgraph Cloud ["External Cloud Platforms"]
        LiveKitCloud["LiveKit Cloud (WebRTC Router)"]
        GeminiLive["Google Gemini 3.8 Live API (WebSocket PCM)"]
    end

    Supervisor -->|Spawns & Auto-restarts| TokenServer
    Supervisor -->|Spawns & Auto-restarts| Worker

    UI -->|1. POST /token (User: Rahul)| TokenServer
    TokenServer -->|2. Concurrent Room Creation & Agent Dispatch| LiveKitCloud
    TokenServer -->|3. Return JWT Token + Room Code| UI

    UI -->|4. Connect via WebRTC| LiveKitCloud
    Worker -->|5. Accept Job & Join Room| LiveKitCloud
    Worker <-->|6. Bi-directional PCM Audio (24kHz Opus)| GeminiLive
    Worker -->|7. DataPackets: Telemetry, State, Transcripts| LiveKitCloud
    LiveKitCloud -->|8. Real-time Audio Stream & Waveform| RTC
    Worker <-->|9. Track Discovered Fields & Transitions| Engine
    Worker --- Prompt
```

---

## 4. Major Modules & Responsibilities

### Backend Components

1. **[`run_sts.py`](file:///y:/roxstar/sts_lab/run_sts.py)** — *Supervisor*:
   - Concurrently spawns the Token Server and Worker as child subprocesses.
   - Monitors exit codes every 2 seconds and auto-restarts failed processes.
   - Handles graceful termination on `KeyboardInterrupt`.

2. **[`token_server.py`](file:///y:/roxstar/sts_lab/token_server.py)** — *Authentication & Dispatcher*:
   - Listens on `http://127.0.0.1:8001`.
   - Endpoints:
     - `GET /health` & `GET /`: Healthcheck returning service state, model, and active voice.
     - `GET /duets`: Lists active duet rooms from the registry.
     - `POST /token`: Concurrently provisions the LiveKit room (`ensure_room_and_dispatch`) and issues a signed JWT token with a 2-hour TTL.
     - `POST /rooms`: Creates a unique room code (`sts-simran-xxxx`).

3. **[`worker.py`](file:///y:/roxstar/sts_lab/worker.py)** — *LiveKit STS Worker*:
   - Connects to LiveKit as agent `sts-simran`.
   - Prewarms SSL context, `anyio`, and `google.genai` packages to eliminate cold-start delay.
   - Initialises `RealtimeModel` with Gemini 3.8 Live API, configuring audio transcription and temperature (0.7).
   - Exposes 4 LLM function tools:
     - `save_profile(field, value)`: Silently accumulates user info.
     - `check_available_duets(genre)`: Queries available rooms from `DuetRoomRegistry`.
     - `navigate_to_duet(room_id)`: Dispatches UI navigation event, triggers Simran's signoff excuse, and shuts down bot.
     - `navigate_to_recording(song_title)`: Dispatches solo recording event, triggers handoff excuse, and shuts down bot.
   - Handles client data events (`roxstar.chat`, `roxstar.app_event`, `roxstar.duet_decline`, `roxstar.user_identity`).
   - Implements `turn_off_bot()`: flushes final audio (1.2s buffer), detaches input audio, closes sessions cleanly, and shuts down the job context.

4. **[`onboarding.py`](file:///y:/roxstar/sts_lab/onboarding.py)** — *State Machine & Persistence*:
   - `UserDiscoveryProfile`: Dataclass tracking 8 canonical fields (`name`, `location`, `occupation`, `hobbies`, `music_taste`, `expectations`, `duet_attempted`, `coins_explained`).
   - `UserProfileStore`: Lightweight JSON persistence (`.sts_users.json`) recognizing returning users.
   - `DuetRoomRegistry`: In-memory registry of live duet rooms (`duet-kesariya`, `duet-tum-hi-ho`, `duet-bollywood-90s`, etc.).
   - `OnboardingTracker`: Manages session discovery state, tooltip deduplication, coin balances (50 welcome coins), action nudge counter, and signoff excuse selection.

5. **[`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py)** — *Persona & System Prompt*:
   - Defines Simran's 22-year-old South Delhi persona, urban Hinglish vernacular, 3 conversational gears (Gear 3 excited, Gear 2 default warm, Gear 1 soft/shy), turn limits (6–14 words), Trade Rule, and strict 2-decline exit rule.
   - Contains session tuning directives (`LIVE_SESSION_NOTES`) for Google Gemini 3.8 Live API.

6. **[`config.py`](file:///y:/roxstar/sts_lab/config.py)** — *Configuration*:
   - Loads environment variables into immutable `StsSettings` dataclass.

### Frontend Components (`web/src/`)

- **[`App.tsx`](file:///y:/roxstar/sts_lab/web/src/App.tsx)**: Main shell orchestrating the 2-pane studio layout, top navigation, error banners, and contextual tooltip overlay.
- **[`hooks/useStsRoom.ts`](file:///y:/roxstar/sts_lab/web/src/hooks/useStsRoom.ts)**: Core WebRTC state hook managing connection, audio analyser levels, DataPacket listeners, transcript accumulation, and UI stage transitions.
- **[`components/SimranPresence.tsx`](file:///y:/roxstar/sts_lab/web/src/components/SimranPresence.tsx)**: Dynamic avatar displaying Simran's state (`idle`, `listening`, `speaking`, `away`) and orb visualizer.
- **[`components/KaraokeStageBar.tsx`](file:///y:/roxstar/sts_lab/web/src/components/KaraokeStageBar.tsx)**: Interactive stage controls for solo recording, duet navigation, coin gifting, and stage handoff.
- **[`components/DiscoveryProfileBadge.tsx`](file:///y:/roxstar/sts_lab/web/src/components/DiscoveryProfileBadge.tsx)**: Live visualization of discovered user profile attributes.
- **[`components/TranscriptView.tsx`](file:///y:/roxstar/sts_lab/web/src/components/TranscriptView.tsx)**: Real-time scrolling transcript for user, Simran, and system events.
- **[`components/Controls.tsx`](file:///y:/roxstar/sts_lab/web/src/components/Controls.tsx)**: Mic mute, room join/leave buttons, and audio level meters.

---

## 5. Directory Structure

```
y:\roxstar\sts_lab\
├── AGENTS.md                  # Development guidelines for AI coding agents
├── README.md                  # Project overview and quickstart guide
├── config.py                  # Environment config and settings dataclass
├── token_server.py            # HTTP token minting & room dispatch (Port 8001)
├── worker.py                  # LiveKit Agent Worker (Gemini 3.8 Live API)
├── prompt.py                  # Persona definition & conversational constraints
├── onboarding.py              # State machine, profile store & duet registry
├── run_sts.py                 # Concurrency supervisor for backend services
├── requirements.txt           # Pinned Python backend dependencies
├── .env.example               # Template for environment variables
├── start_backend.bat          # Windows batch launcher for Python supervisor
├── start_web.bat              # Windows batch launcher for Vite web client
├── docs/                      # Centralized documentation directory
│   ├── PROJECT_CONTEXT.md     # Architecture, data flow, and system context
│   ├── WORKFLOW.md            # System workflow, sequences, and product funnels
│   ├── TASKS.md               # Development progress and roadmap tracker
│   └── CHANGELOG.md           # Chronological log of meaningful updates
├── tests/                     # Automated Pytest suite
│   ├── conftest.py            # Path setup for standalone tests
│   ├── test_sts_onboarding.py # State machine & profile unit tests
│   └── test_sts_onboarding_scenarios.py # 12 user journey scenario tests
└── web/                       # React 19 + TypeScript + Vite frontend
    ├── package.json           # Frontend dependencies & scripts
    ├── vite.config.ts         # Vite bundler configuration
    ├── index.html             # HTML entry point
    └── src/
        ├── App.tsx            # Main UI container
        ├── index.css          # Design tokens & studio styling
        ├── hooks/
        │   └── useStsRoom.ts  # WebRTC Room & DataPacket hook
        ├── services/
        │   └── tokenService.ts# API client for token_server.py
        └── components/        # UI components (presence, audio, transcript, controls)
```

---

## 6. Application Entry Points & Startup

### Backend Services
```bash
# Start Token Server (:8001) and LiveKit Worker concurrently via Supervisor:
python run_sts.py
# (Or on Windows: start_backend.bat)
```

### Web Studio Frontend
```bash
# Start Vite development server (:5175):
npm --prefix web run dev
# (Or on Windows: start_web.bat)
```

### Running Test Verification
```bash
# Execute full scenario and unit test suite:
py -m pytest tests/ -v

# Verify frontend production build:
npm --prefix web run build
```

---

## 7. Data Contracts & Event Protocol

Backend and Frontend communicate over LiveKit reliable DataPackets via JSON strings:

| Event Type (`type`) | Source | Purpose | Payload Fields |
| :--- | :--- | :--- | :--- |
| `roxstar.sts.state` | Worker | Agent activity state | `state`: `"idle" \| "listening" \| "thinking" \| "speaking"` |
| `roxstar.sts.telemetry` | Worker | Real-time latency metrics | `ttfa_ms`, `tokens_per_second`, `duration_s`, `model`, `voice` |
| `roxstar.sts.transcript`| Worker | Live transcribed speech | `speaker`, `text`, `is_final` |
| `roxstar.user_state` | Worker | Discovered profile updates | `profile`: dict, `discovered`: string[] |
| `roxstar.coins_awarded` | Worker | Free coin gift notification| `amount`, `balance`, `reason` |
| `roxstar.tooltip` | Worker | In-app contextual guidance | `id`, `title`, `message`, `target` |
| `roxstar.stage_transferred`| Worker | Simran handoff notification | `reason`, `room_id`, `song_title` |
| `roxstar.bot_turned_off`| Worker | Bot power-off event | `reason`, `message` |
| `roxstar.chat` | Web UI | User text fallback turn | `text` |
| `roxstar.app_event` | Web UI | In-app user interactions | `action` (e.g. `singing_started`, `send_duet_gift`) |
| `roxstar.duet_decline` | Web UI | User declined duet | *(empty)* |
| `roxstar.user_identity`| Web UI | Initial user name sync | `name` |

---

## 8. Key Architectural Decisions & Rationale

1. **Direct Speech-to-Speech (S2S) Architecture**:
   - *Decision*: Route native audio directly through Google Gemini 3.8 Live API without intermediate Whisper STT or ElevenLabs/Google TTS.
   - *Rationale*: Eliminates cascading pipeline latency, achieving ~300–400ms time-to-first-audio (TTFA) and authentic conversational pacing.
2. **Prewarmed Worker Initialization**:
   - *Decision*: Initialize SSL context and pre-import heavy modules (`google.genai`, `anyio`) during worker boot using `num_idle_processes=1`.
   - *Rationale*: Slashes the initial room connection and greeting delay by 5–6 seconds on cold starts.
3. **Anti-Chit-Chat Excuse Engine (2-Decline Guardrail)**:
   - *Decision*: Track user action invitations (`action_nudge_count`). After two declines or deflections, Simran makes a realistic excuse (e.g., Swiggy/parcel arrived, mummy yelling for chai, urgent client ping) and wraps up under 25 words.
   - *Rationale*: Prevents costly, open-ended chit-chat and avoids awkward bot-like refusals while maintaining a 100% human South Delhi personality.
4. **Paced 4–5 Minute Engagement Flow**:
   - *Decision*: Target 4–5 minute interaction time using 12–22 word conversational turns, multi-turn topic unpacking (exploring favourite artists and singing comfort before pitching duets), and strict unprompted location withholding (Simran never reveals her city unless directly asked).
   - *Rationale*: Rushing to pitch a duet on turn 5 leads to 90-second drop-offs; letting personal rapport and musical safety build first increases duet conversion rates.
4. **Clean Bot Power-Off on Handover**:
   - *Decision*: When the user enters a duet room or solo recording studio, the bot detaches its audio input, publishes state updates, and cleanly shuts down its session.
   - *Rationale*: Ensures the user has 100% microphone ownership on stage without the model listening, interrupting, or consuming unnecessary tokens.
5. **Silent Function Tool Execution**:
   - *Decision*: Tools like `save_profile()` never return spoken text to the user.
   - *Rationale*: Announcing data capture (e.g., "I have saved your city as Pune") breaks the conversational illusion and acts as an instant bot tell.

---

## 9. Configuration & Environment Variables

Stored in `.env` (copy from [`.env.example`](file:///y:/roxstar/sts_lab/.env.example)):

| Variable | Required | Default | Purpose |
| :--- | :---: | :--- | :--- |
| `LIVEKIT_URL` | Yes | — | WebSocket URL for LiveKit Cloud (`wss://...`) |
| `LIVEKIT_API_KEY` | Yes | — | LiveKit API Key for room & participant management |
| `LIVEKIT_API_SECRET` | Yes | — | LiveKit API Secret for signing JWT tokens |
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API Key for Gemini 3.8 Live API |
| `STS_AGENT_NAME` | No | `sts-simran` | Worker registration name in LiveKit dispatch |
| `STS_MODEL` | No | `gemini-3.8-live` | Target Gemini Live model identifier |
| `STS_VOICE` | No | `Leda` | Target Gemini voice timbre (options: `Leda`, `Puck`, `Aoede`, etc.) |
| `STS_PORT` | No | `8001` | Local port for `token_server.py` |

---

## 10. Known Limitations & Technical Constraints

- **Single Active Agent Per Room**: The worker runs as a dedicated agent per room. Multi-bot conversations (e.g. Kabir + Simran simultaneously) require the legacy cascade setup or multi-worker routing.
- **Local JSON Store**: User profiles are saved in `.sts_users.json` on local disk; a production migration would require a distributed database (e.g. PostgreSQL or Redis).
- **Static Duet Registry**: Duet rooms are currently populated in-memory in `DuetRoomRegistry` with mock hosts (Aman, Rhea, Kabir); production requires connecting to RoxStar's live backend room service.
- **Windows Command Convention**: On Windows systems without a virtualenv added to PATH, execute Python commands using `py -m pytest` or `py run_sts.py`.

