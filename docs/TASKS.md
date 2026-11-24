# TASKS.md — Development Progress Tracker

> **Current Sprint**: STS Lab Stabilization & Conversational Calibration  
> **Verification Status**: 64/64 Automated Tests Passing | Frontend Production Build Passing

---

## 1. Completed Tasks (Verified)

### Core Architecture & Media Pipeline
- [x] **Audit follow-up fixes (2026-11-12)**: answer-capture heuristics, token server and worker hardening, session resumption and context compression, fake TTFT removed, mobile admin UI, docs drift. See `CHANGELOG.md`.
- [x] **Conversation Persistence, Analytics API & Admin Dashboard (2026-11-11)**: `db/` package, non-blocking recorder wired into `worker.py`, `/api/admin/*` endpoints, `/admin` review UI, 13 new tests. Remaining before production: consent notice and retention policy, Alembic migrations, real Roxstar user ID as identity, restrict CORS. See `docs/ADMIN_DASHBOARD.md` section 7.
- [x] **100% Real-Person Identity & Zero AI Admission**: Enforced non-negotiable rule in `prompt.py` and documentation (`WORKFLOW.md`). Simran acts 100% like a real 22-year-old freelance graphic designer from Delhi with her own life. She never admits to being an AI, bot, virtual host, or software under any circumstance or persistent questioning, playfully laughing it off and steering back to music.
- [x] **Comprehensive Discovery Profile & Sensible First-Interaction Intro**: Expanded `UserDiscoveryProfile` and `save_profile` with `referral_source`, `musical_role`, `singing_comfort`, and `favorite_song` fields alongside `name`, `location`, `occupation`, `hobbies`, `music_taste`, `expectations`, `duet_attempted`, and `coins_explained`. Replaced Phase 3 "saw other rooms" question with authentic Roxstar community introduction.
- [x] **Strict Turn-Taking & Non-Blocking Silent Tools**: Configured `RealtimeModel` with `tool_behavior=genai_types.Behavior.NON_BLOCKING` and updated `save_profile` to return a short confirmation string (`reply_required=True`, so Gemini speaks its reply immediately instead of the turn being silently suppressed; see the 2026-11-11 CHANGELOG fix). Eliminated multi-turn runaway speech and prohibited post-tool thinking fillers (`"Hmm... ruko, soch rahi hoon"`).
- [x] **Direct Speech-to-Speech (S2S) Engine**: Integrated Google Gemini 3.8 Live API (`gemini-3.8-live`) via `livekit-plugins-google.realtime.RealtimeModel` with native bidirectional 24kHz PCM audio streaming.
- [x] **LiveKit Agent Worker**: Implemented prewarmed worker (`worker.py`) connecting as `sts-simran` with `JobExecutorType.THREAD` and `num_idle_processes=1`.
- [x] **Concurrent Supervisor**: Implemented `run_sts.py` to concurrently spawn, monitor, and auto-restart `token_server.py` and `worker.py`.
- [x] **Dedicated Token Server**: Built HTTP server on port 8001 handling `/token`, `/rooms`, `/health`, and `/duets` with parallel LiveKit room prep and agent dispatch.

### Persona & Conversational Design
- [x] **Elimination of 'ji' Formality with User Names**: Enforced non-negotiable rule forbidding "ji" attached to user names (no "Yuvi ji", "Rahul ji", "[Name] ji"). Simran addresses users directly by first name ("Yuvi!", "Rahul!"), preserving friendly peer intimacy while retaining respectful "aap" pronouns.
- [x] **Phase 2 Music Opener ("Aap Gaane Sunte Ho Ya Gaate Ho?") & Adaptive Branching**: Replaced generic Phase 2 opener with the core question *"Chalo ab thodi gaano ki baat karte hain — waise aap gaane sirf sunte ho ya khud bhi gaate ho?"*, branching organically for pure listeners (genre/loop song validation + listening habits) versus singers/hummers (bathroom singer check + performance anxiety bond). Removed duplicate questioning in Phase 3.
- [x] **Natural Laughter & Laughter-Off Mode**: Authored authentic Hindi laughter guidelines in `prompt.py` (spontaneous giggles `"hehe"`, warm breathy chuckles `"haha yaar"`, dramatic teasing laughs `"haha haaye!"`). Added full Turned-Off Laughter mode in `OnboardingTracker` allowing users to suppress laughter for a calm, composed tone.
- [x] **Simran 22yo Delhi Persona (Delhi-Only Identity)**: Authored system prompt (`prompt.py`) with urban Hinglish vernacular, 3-gear conversational energy, turn limits (12–22 words), Trade Rule, and strict Delhi-only identity (`"Main Simran, Delhi se"`). Prohibits commentary, critiques, or clichés about any city. City probing was restored on 2026-11-10: Simran asks the user's city once in Phase 1 and saves it silently (`save_profile(location)`), and reveals Delhi only if the user asks (About-You Rule: she shares nothing about herself unless asked).
- [x] **Production Voice Polish (2026-11-10)**: Calmer greeting and handoffs, "aap"-only register, deduplicated prompt rules, no volunteering of AI status (honest one-line answer only to sincere questions), cleaned duet data. See `CHANGELOG.md`.
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
- [x] **Interactive Natural Laugh Lab & Controls Modal**: Implemented dedicated Natural Laugh Lab (`NaturalLaughDemo.tsx`) featuring master laughter toggling (`Natural Laugh ON` vs `Turned OFF`), 5 curated Hindi voice sample cards with audio playback (Sarojini Bargain Chuckle, Bathroom Singer Giggle, Sarcastic Haaye Laugh, Late-Night Chai Giggler, and Laugh Turned OFF), custom phrase speech tester, and live WebRTC session synchronization (`roxstar.set_laugh_mode`).
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

- [x] **Voice Parameter Alignment (2026-11-11)**: Frontend fallback/display voice labels now default to `Leda`, matching `config.py`. The backend still reports the real voice via telemetry.

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

- **Open from the 2026-11-12 audit**: AI-disclosure wording in `prompt.py` (product/legal decision); returning-user recognition is dead code (`UserProfileStore.get_or_create` is never called by the worker); `"50 welcome coins"` and "I will comment" are not backed by a real credit or action; `KaraokeStageBar` uses mock rooms, gifts and a random pitch score; modals lack focus handling and there is no reduced-motion support; no mic-denied cleanup or token-server timeout in `useStsRoom.ts`; `list_users` N+1 queries; no migrations, CI or pinned dependencies; synchronous JSON write in `save_profile`; no consent notice or retention policy.

- **Voice Label Mismatch** (resolved 2026-11-11):
  - *Detail*: UI fallback labels were `Sulafat` while `config.py` defaults to `Leda`; all UI defaults are now `Leda`.
  - *Impact*: None remaining.
- **Python Execution on Windows**:
  - *Detail*: Global `python` or `pytest` may not be registered in system PATH; running via `py -m pytest tests/` or `py run_sts.py` is required.
  - *Impact*: Documented in [`AGENTS.md`](file:///y:/roxstar/sts_lab/AGENTS.md) and [`docs/PROJECT_CONTEXT.md`](file:///y:/roxstar/sts_lab/docs/PROJECT_CONTEXT.md).
- **In-Memory Duet Rooms**:
  - *Detail*: Duet rooms created dynamically during a session exist only in worker memory and reset when the worker restarts.

---

## 5. Next Recommended Development Steps

1. Add a lightweight test script to verify token server endpoints (`GET /health`, `POST /token`) in automated CI.
2. Before production: lock down CORS (currently reflects any `Origin`), and make sure the admin API's no-key localhost mode cannot be reached through a reverse proxy (set `ADMIN_API_KEY`).
3. Lazy-load the speaking-orb code to shrink the ~843 kB main bundle.

