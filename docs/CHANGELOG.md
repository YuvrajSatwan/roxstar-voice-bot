# CHANGELOG.md — Significant Project Changes

All notable changes, architectural pivots, and major additions to the **RoxStar STS Lab** repository are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] - 2026-11-10

### Changed
- **Complete Project & Persona Rename to Simran**:
  - Rebranded the persona, backend agent, configs, tests, and web UI across the entire codebase from Saara / Saraah to **Simran**:
    - **Configuration & Worker**: Updated default agent name to `sts-simran`, room generator to `sts-simran-`, and participant name to `Simran` with `roxstar.simran_rejoined` event support.
    - **Prompts & Persona**: Updated [`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py) to define `SIMRAN_ONBOARDING_SYSTEM_PROMPT` while retaining backward-compatible aliases for existing imports (`SAARA_ONBOARDING_SYSTEM_PROMPT`, `SARAAH_STS_SYSTEM_PROMPT`).
    - **State Engine**: Updated [`onboarding.py`](file:///y:/roxstar/sts_lab/onboarding.py) with `SIMRAN_SIGNOFF_EXCUSES`, `SIMRAN_DUET_HANDOFF_EXCUSES`, `SIMRAN_SOLO_HANDOFF_EXCUSES`, and `is_simran_away` properties with full backward-compatibility accessors.
    - **Web Frontend**: Updated [`App.tsx`](file:///y:/roxstar/sts_lab/web/src/App.tsx), [`index.html`](file:///y:/roxstar/sts_lab/web/index.html), [`package.json`](file:///y:/roxstar/sts_lab/web/package.json), created [`SimranPresence.tsx`](file:///y:/roxstar/sts_lab/web/src/components/SimranPresence.tsx) and [`SimranOrb.tsx`](file:///y:/roxstar/sts_lab/web/src/components/SimranOrb.tsx), updated `useStsRoom.ts`, `Controls.tsx`, `QuickPrompts.tsx`, and `TranscriptView.tsx`.
    - **Documentation**: Updated `README.md`, `AGENTS.md`, `docs/PROJECT_CONTEXT.md`, `docs/WORKFLOW.md`, and `docs/TASKS.md`.
    - **Verification**: Verified with `py -m pytest tests/ -v` (23/23 tests passing) and `npm --prefix web run build` (0 build errors).

### Added
- **Natural Hindi Branching for YES vs NO Responses Post-Convincing**:
  - Implemented explicit branching in [`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py) for post-convincing responses:
    - **When user says YES**: Saara enthusiastically celebrates in natural Hindi (*"Yeh hui na baat! Room khul raha hai screen pe, main mic chhodti hoon taaki tum dono mast jam karo. Aag laga dena, bye!"*), immediately calls `navigate_to_duet` or `navigate_to_recording`, and cleanly powers off.
    - **When user says NO**: Saara delivers Attempt 2 warm reassurance (*"Arre koi baat nahi! Jab bhi mann kare na, bas apna favourite gaana gaa kar post kar dena. Main pakka sunungi aur comment bhi karungi!"*), or triggers the 2-decline sign-off with zero pressure if declined twice.
  - Updated duet and solo stage handoff excuses in [`onboarding.py`](file:///y:/roxstar/sts_lab/onboarding.py) to celebrate the user's singing decision rather than making work excuses.
  - Added automated test scenario `test_scenario_14_user_says_yes_after_convincing` in [`tests/test_sts_onboarding_scenarios.py`](file:///y:/roxstar/sts_lab/tests/test_sts_onboarding_scenarios.py) (23/23 tests passing).
- **2-Attempt Singing Encouragement Flow Before Sign-Off**:
  - Implemented a two-step conversational encouragement journey in [`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py) for users who hesitate or state they cannot sing ("nahi aata", "sharm aati hai"):
    - **Attempt 1**: Warm reassurance that Roxstar is zero-pressure and no perfect singer is needed, offering Duet as a fun way to blend their voice with someone else.
    - **Attempt 2**: If the user acknowledges or hesitates further, warmly encourages them to record/post their favourite song whenever they feel like it, with Saara's personal promise to wait for their song, listen to it, and comment on it.
  - Aligned sign-off logic in [`onboarding.py`](file:///y:/roxstar/sts_lab/onboarding.py) and [`worker.py`](file:///y:/roxstar/sts_lab/worker.py) so that the strict 2-decline exit triggers only after these two warm encouragements.
  - Added automated test scenario `test_scenario_13_user_says_cannot_sing_two_attempt_encouragement` in [`tests/test_sts_onboarding_scenarios.py`](file:///y:/roxstar/sts_lab/tests/test_sts_onboarding_scenarios.py) (22/22 tests passing).

---

## [1.2.0] - 2026-11-09

### Added
- **Render Infrastructure as Code (render.yaml Blueprint)**:
  - Added [`render.yaml`](file:///y:/roxstar/sts_lab/render.yaml) defining both backend web service (`roxstar-backend`) and static frontend site (`roxstar-frontend`).
  - Added [`setup.py`](file:///y:/roxstar/sts_lab/setup.py) to support `pip install -e .` on Render and standard Python environments.
  - Added in-memory package aliasing in [`run_sts.py`](file:///y:/roxstar/sts_lab/run_sts.py) to guarantee `import sts_lab.xxx` resolution across all cloud hosting paths.
  - Added support for `VITE_TOKEN_URL` in [`web/src/services/tokenService.ts`](file:///y:/roxstar/sts_lab/web/src/services/tokenService.ts).
- **Production Containerization & Koyeb Deployment Architecture**:
  - Created multi-stage [`Dockerfile`](file:///y:/roxstar/sts_lab/Dockerfile) bundling React 19 + Vite frontend build with Python 3.11 STS backend worker & token server.
  - Added [`.dockerignore`](file:///y:/roxstar/sts_lab/.dockerignore) to prevent copying local virtualenvs, node_modules, and git history into container builds.
  - Added static SPA serving directly into [`token_server.py`](file:///y:/roxstar/sts_lab/token_server.py) with path traversal protection and MIME type resolution, allowing full-stack execution from a single Koyeb container.
  - Enabled dynamic host and port binding (`PORT`, `STS_PORT`, `STS_HOST`) in [`config.py`](file:///y:/roxstar/sts_lab/config.py) and [`token_server.py`](file:///y:/roxstar/sts_lab/token_server.py).
  - Updated [`web/src/services/tokenService.ts`](file:///y:/roxstar/sts_lab/web/src/services/tokenService.ts) to automatically adapt between local dev, separate Vercel/Koyeb URLs (`VITE_STS_TOKEN_URL`), and unified single-container origin.

---

## [1.1.0] - 2026-11-05

### Changed
- **User-First Opening Greeting**:
  - Configured Saara to ask the user's name first in [`worker.py`](file:///y:/roxstar/sts_lab/worker.py#L584-L593) without announcing her name in the opening turn. She introduces herself as Saara only after the user shares their name.
- **4–5 Minute Natural Conversational Pacing**:
  - Expanded conversational turn length from 6–14 words to **12–22 words** sweet spot (max 26–28 for stories/handoffs) in [`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py) and [`worker.py`](file:///y:/roxstar/sts_lab/worker.py).
  - Paced the funnel into 5 chapters over ~4–5 minutes: Personal Connection (0:00–1:45) -> Musical Soul & Bathroom Singer Check (1:45–3:15) -> RoxStar Insider Coins Perk (3:15–4:00) -> Activation Pitch (4:00–4:45) -> Clean Handover/Exit (4:45–5:00).
  - **Strict Location Rule**: Enforced that Saara must NEVER volunteer or state where she is from (Delhi) unless the user explicitly asks.
  - Added the "Bathroom Singer vs Stage Star" psychological safety check to break user performance anxiety before pitching duet rooms.

### Added
- **Persistent Project Documentation System**:
  - Added [`AGENTS.md`](file:///y:/roxstar/sts_lab/AGENTS.md): Development guidelines, architectural guardrails, coding standards, and pre-flight protocols for future AI coding agents.
  - Added [`docs/PROJECT_CONTEXT.md`](file:///y:/roxstar/sts_lab/docs/PROJECT_CONTEXT.md): System architecture, data flow diagrams, module responsibilities, API contracts, and key technical decisions.
  - Added [`docs/WORKFLOW.md`](file:///y:/roxstar/sts_lab/docs/WORKFLOW.md): Conversational funnels, sequence diagrams, and product onboarding journey.
  - Added [`docs/TASKS.md`](file:///y:/roxstar/sts_lab/docs/TASKS.md): Verified task tracker, current sprint status, roadmap, known bugs, and next steps.
  - Added [`docs/CHANGELOG.md`](file:///y:/roxstar/sts_lab/docs/CHANGELOG.md): Chronological history of major architectural milestones.
  - Organized documentation into project root (`AGENTS.md`, `README.md`) and centralized [`docs/`](file:///y:/roxstar/sts_lab/docs/) folder.

---

## [1.0.0] - 2026-11-05

### Added
- **Direct Speech-to-Speech (S2S) Architecture**:
  - Replaced cascaded STT -> LLM -> TTS pipeline with native bi-directional audio streaming via Google Gemini 3.8 Live API (`gemini-3.8-live`) and `livekit-plugins-google.realtime.RealtimeModel`.
  - Achieved sub-second voice latency (~300–400ms TTFA) over 24kHz Opus WebRTC audio tracks.
  - Affected files: [`worker.py`](file:///y:/roxstar/sts_lab/worker.py), [`config.py`](file:///y:/roxstar/sts_lab/config.py).

- **Worker Prewarming & Concurrency Supervisor**:
  - Added `prewarm()` in `worker.py` to pre-cache SSL trust stores, `anyio`, and Google GenAI libraries at boot.
  - Configured `num_idle_processes=1` to keep a hot thread runner ready, reducing initial greeting delay by 5–6 seconds.
  - Created [`run_sts.py`](file:///y:/roxstar/sts_lab/run_sts.py) supervisor to manage concurrent lifecycles of `token_server.py` and `worker.py` with auto-restart.
  - Added Windows quick-launch scripts [`start_backend.bat`](file:///y:/roxstar/sts_lab/start_backend.bat) and [`start_web.bat`](file:///y:/roxstar/sts_lab/start_web.bat).

- **Onboarding State Engine & Local Persistence**:
  - Implemented 8-topic user discovery lifecycle (`UserDiscoveryProfile`) in [`onboarding.py`](file:///y:/roxstar/sts_lab/onboarding.py).
  - Added [`UserProfileStore`](file:///y:/roxstar/sts_lab/onboarding.py) with `.sts_users.json` local storage to recognize returning users and personalize greetings.
  - Built [`DuetRoomRegistry`](file:///y:/roxstar/sts_lab/onboarding.py) supporting live room lookup by genre.
  - Added deduplicated tooltip guidance events and virtual coin granting (50 welcome coins).

- **Persona Engine & Anti-Chit-Chat Guardrail**:
  - Authored Saara persona in [`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py) (22yo South Delhi media graduate, urban Hinglish, 3 conversational gears, turn length 6–14 words, Trade Rule).
  - Implemented the **2-Decline Excuse Engine**: after 2 action declines/deflections, Saara makes an authentic personal excuse (Swiggy/parcel arrived, mummy yelling for chai, urgent client ping, low battery) and signs off under 25 words.
  - Added silent function tools: `save_profile`, `check_available_duets`, `navigate_to_duet`, and `navigate_to_recording`.
  - Implemented `turn_off_bot()` in [`worker.py`](file:///y:/roxstar/sts_lab/worker.py) to detach audio input, close sessions, and cleanly shut down the job context when handing off the stage to the user.

- **Standalone Web Studio Frontend**:
  - Created React 19 + TypeScript frontend on Vite 8 ([`web/`](file:///y:/roxstar/sts_lab/web/)).
  - Implemented 2-pane studio UI with dynamic orb presence visualizer ([`SaaraOrb.tsx`](file:///y:/roxstar/sts_lab/web/src/components/SaaraOrb.tsx)), real-time transcripts ([`TranscriptView.tsx`](file:///y:/roxstar/sts_lab/web/src/components/TranscriptView.tsx)), interactive stage controls ([`KaraokeStageBar.tsx`](file:///y:/roxstar/sts_lab/web/src/components/KaraokeStageBar.tsx)), discovery badges ([`DiscoveryProfileBadge.tsx`](file:///y:/roxstar/sts_lab/web/src/components/DiscoveryProfileBadge.tsx)), and latency telemetry pills.

- **Automated Verification Suite**:
  - Implemented 21 automated tests across unit and end-to-end user scenarios ([`tests/test_sts_onboarding.py`](file:///y:/roxstar/sts_lab/tests/test_sts_onboarding.py), [`tests/test_sts_onboarding_scenarios.py`](file:///y:/roxstar/sts_lab/tests/test_sts_onboarding_scenarios.py)).
  - Covered scenarios: new user onboarding, skipped questions, topic switches, live singing start, unposted recordings, song publication, available duets, declined duets, empty duet rooms, free coin inquiries, returning users, and talkative user sign-off.

