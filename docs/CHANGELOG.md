# CHANGELOG.md — Significant Project Changes

All notable changes, architectural pivots, and major additions to the **RoxStar STS Lab** repository are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] - 2026-11-11

### Added
- **Interview-tone fix + dashboard completion (2026-11-12)**:
  - [`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py): new "NO INTERVIEW TONE" rule. Simran no longer leads questions with "ye bataiye / aur ye bataiye", does not repeat the same connector, ties questions to what the user said, and never asks on three turns in a row. Removed the "bataiye" examples that taught the model the phrase.
  - Recorder ([`db/recorder.py`](file:///y:/roxstar/sts_lab/db/recorder.py), [`db/conversation_rules.py`](file:///y:/roxstar/sts_lab/db/conversation_rules.py)): (1) when the model skips `save_profile`, the user's answer to the question Simran just asked is stored and shown as "(auto)"; (2) funnel phase and the 2-decline exit are also read from Simran's lines; (3) auto-flags for repeated lines and "ye bataiye" lead-ins; (4) bogus latency (negative, a few ms, empty generations) is dropped and a measured "user stops -> Simran starts" response time is recorded; (5) the 50 welcome coins are stored when she announces them.
  - Identity: the web client sends a per-browser `visitor_id`, so two people typing the same name are separate users ([`token_server.py`](file:///y:/roxstar/sts_lab/token_server.py), [`tokenService.ts`](file:///y:/roxstar/sts_lab/web/src/services/tokenService.ts)). The `~suffix` is never shown as a name.
  - Dashboard: user profile drawer (all fields, completeness, every conversation), profile card inside the replay, unique users and profile completeness KPIs, session count and last call per user, Refresh button, users CSV/JSON export, delete conversation, "(auto)" pills, new flag reasons. New endpoints `GET /api/admin/users/{id}`, `POST /api/admin/sessions/{id}/delete`, export `kind: "users"`.
  - [`db/maintenance.py`](file:///y:/roxstar/sts_lab/db/maintenance.py) (`py -m sts_lab.db.maintenance`) repairs old rows (bad latency, turn counts, phase, exit reason, flags). The page now talks to the backend it was served from, and to port 8001 only under the Vite dev server (5175).
  - 57 tests pass (35 existing + 22 persistence).
- **Conversation Persistence Engine, Analytics API and Admin Review Dashboard** (see [`docs/ADMIN_DASHBOARD.md`](file:///y:/roxstar/sts_lab/docs/ADMIN_DASHBOARD.md)):
  - New `db/` package: async SQLAlchemy models (`users`, `sessions`, `messages`), SQLite for local dev and PostgreSQL via `DATABASE_URL`, an idempotent repository, and a `SessionRecorder` whose methods only enqueue work. One background task writes in order, so the audio event loop never awaits database I/O. If the database is down the agent keeps running; writes retry with backoff in a bounded in-memory queue.
  - [`worker.py`](file:///y:/roxstar/sts_lab/worker.py) now records final user and Simran turns, per-turn TTFT / tokens per second, captured profile fields, welcome-coin balance, funnel stage and exit reason (`duet_handoff`, `solo_handoff`, `two_decline_exit`, `user_disconnected`, `abandoned`). No prompt, tool or DataPacket was changed.
  - [`token_server.py`](file:///y:/roxstar/sts_lab/token_server.py) serves `/api/admin/*` (metrics, funnel, sessions, session detail, users, flag, review, CSV/JSON export), protected by `X-Admin-Key` (`ADMIN_API_KEY`; unset disables the API). CSV export neutralises spreadsheet formula injection.
  - New `/admin` dashboard in `web/src/admin/` (code-split): KPI cards, drop-off funnel, daily trend, conversation replay with latency badges and flagging, user explorer, export, light/dark theme.
  - New `tests/test_persistence.py` (13 tests: schema and turn logging, metric attachment, rapid turns without loop stalls, DB outage and recovery, queue overflow, exit reasons, stage inference, admin auth, filters, flagging, export). New dependencies: `sqlalchemy[asyncio]`, `aiosqlite`, `asyncpg`. New env vars: `DATABASE_URL`, `STS_DB_ENABLED`, `ADMIN_API_KEY`.

### Changed
- **Neon PostgreSQL support**: `db/database.py` now accepts libpq-style URLs as issued by Neon (`sslmode`, `channel_binding`), converting them for `asyncpg`, and disables asyncpg's statement cache so Neon's pooled (`-pooler`) endpoints work. Added a regression test (50 tests passing). `.dockerignore` now also excludes `.env.local` and `.sts_users.json`. The Neon CLI also added `neon.ts`, a root `package.json` (Neon config packages only) and `.neon` (gitignored).
- **Render deployment**: [`render.yaml`](file:///y:/roxstar/sts_lab/render.yaml) now declares `DATABASE_URL` and `ADMIN_API_KEY` as `sync: false` placeholders so Render prompts for them in the dashboard (values are never stored in the repo). Without a permanent `DATABASE_URL`, conversations go to a local SQLite file that Render wipes on every redeploy.

### Fixed
- **Housekeeping (voice label, stale docs)**: Frontend voice fallbacks/labels changed from `Sulafat` to `Leda` to match `config.py` (display only; the backend still reports the real voice). Removed two unused prompt-alias imports and a stale persona docstring in `worker.py` (the aliases stay in `prompt.py`). Corrected `TASKS.md` / `PROJECT_CONTEXT.md` (test count, `save_profile` return behaviour, persistence layer, directory tree, duplicate decision numbering).
- **Missing Bot Response After User Input (Unresponsive Turn Bug)**:
  - **Root Cause Identified from Live Server Logs**: `save_profile` was returning `None` (`-> None`), which LiveKit marked as `reply_required=False`. With `tool_behavior=NON_BLOCKING`, LiveKit sent `tool_response_scheduling=SILENT` ("do not interrupt or trigger generation") to Gemini 3.8 Live API. Whenever the user provided their name, city, or occupation, Gemini executed `save_profile` and suppressed audio generation completely, forcing the user to speak a second time before Simran would reply.
  - **Tool Return & Response Scheduling**: Updated `save_profile` in [`worker.py`](file:///y:/roxstar/sts_lab/worker.py) to return a confirmation string (`return f"Saved {field}='{value}'. Now respond to the user immediately."`), setting `reply_required=True` so Gemini generates its spoken response without delay.
  - **Interruption Threshold Tuning**: Reduced `turn_handling.interruption.min_duration` from `0.7s` to `0.35s` and set `min_consecutive_speech_delay=0.0` in [`worker.py`](file:///y:/roxstar/sts_lab/worker.py), preventing natural 1-word user answers (*"Yuvi"*, *"Rahul"*, *"Haan"*) right as the greeting finishes from being discarded as false interruptions.
  - **Prompt Directive**: Added explicit rule in [`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py) enforcing that Simran must respond immediately to every user utterance and never wait for the user to speak twice.

### Changed
- **100% Real-Person Identity & Zero AI Admission (Non-Negotiable Guardrail)**:
  - Enforced critical non-negotiable rule in [`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py): Simran must NEVER admit, mention, or state that she is an AI, bot, virtual host, assistant, software, or computer system under ANY circumstance or pressure.
  - Simran acts 100% like a real person with her own real life in Delhi (freelance graphic designer, DU graduate, lives with family, mom calls for chai, client deadlines, struggles with tangled earphones, music enthusiast).
  - When asked, teased, joked with, or persistently questioned ("robot ho kya?", "AI lag rahi ho", "sach batao bot ho na?", "tum insaan ho ya AI?"), she playfully laughs it off and brushes it aside like a genuine 22-year-old girl (*"Haha arre main koi robot thodi hoon! Bilkul real hoon, Delhi se. Chalo faltu baatein chhodiye, ye bataiye loop pe kaunsa gaana chal raha hai?"*), smoothly pivoting back to music without getting defensive or breaking character.
  - Updated [`docs/WORKFLOW.md`](file:///y:/roxstar/sts_lab/docs/WORKFLOW.md) section 5 guardrail 3 to document the strict 100% Human Persona Guardrail and Zero AI Admission policy.
  - Updated automated scenario test 23 in [`tests/test_sts_onboarding_scenarios.py`](file:///y:/roxstar/sts_lab/tests/test_sts_onboarding_scenarios.py) (`test_scenario_23_ai_status_never_admitted_and_100_percent_human`).
  - 34/34 pytest tests passing; frontend build passing.

## [Unreleased] - 2026-11-10

### Changed
- **Production Voice Polish (human, not AI, not overacted)** — wording and tone only, no change to the funnel, tools, state machine or 2-decline exit:
  - **City is asked and saved again** (Phase 1: Name -> City -> Job -> Hobbies, matching `WORKFLOW.md`). Simran asks "Aap kahan se ho?" once after the name, saves it via `save_profile(location)`, acknowledges neutrally, and never comments on any city. Delhi is revealed only after the user shares their city or asks. A single refusal no longer skips the remaining Phase 1 topics; two refusals go to Phase 2.
  - **Removed forced high energy**: [`worker.py`](file:///y:/roxstar/sts_lab/worker.py) no longer tells the model to speak with "VERY HIGH ENERGY" or to recite a scripted greeting. Opening is bright but easy (Gear 2). Gear 3 is kept for real peaks only.
  - **Fixed "tum" slips** in return/rejoin hints (`tumne`, `Oye!`, "super cheerful"); everything stays on "aap" with soft forms (`kijiyega`, `dijiyega`).
  - **Handoff and sign-off lines** in [`onboarding.py`](file:///y:/roxstar/sts_lab/onboarding.py) rewritten calmer and varied (no "Zabardast / aag laga dena" chorus, no digits, no dashes, fixed the broken Ritika line). Tool results now tell the model to say them in its own words instead of reading them verbatim.
  - **Prompt cleanup** in [`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py): duplicated rules (`ji`, `aap`, disclosure, city) merged into one place each, fewer all-caps shouts, em dashes removed from spoken example lines, canned per-genre praise turned into short seeds, opener angles made gender-neutral, pitchy Phase 3 copy ("24/7", "bina judgment", "insider tip") replaced with plain lines.
  - **Laughter**: instruction changed from spelled-out "haha yaar / hehe" on ~25% of turns to a rare, real laugh (~1 in 6 turns).
  - **AI disclosure**: Simran never volunteers that she is an AI. A passing tease ("robot ho kya?") gets a light, short sidestep back to music, without claiming to be human. A sincere question ("do you really want to know", asked twice, or clearly important) gets one calm honest line, and she never claims to be human. Requested change was "never say she is an AI in any situation"; the sincere-question honesty was kept on purpose so users are never deceived about talking to an AI. The in-app AI label is a founder decision (see founder questions).
  - **Welcome coins**: the facts section now states the 50 one-time welcome coins as the only allowed amount (it previously contradicted the 50-coin line in Phase 3).
  - **Duet data**: removed the duplicate `Tum Hi Ho` room (now `Arijit Unplugged` / Kabir / `Channa Mereya`), cleaned spoken song titles (no brackets or diacritics), and removed hardcoded example songs from the `check_available_duets` tool result.
  - **Event hints and tooltip copy** made plain and brief (tooltip titles unchanged).
  - Added scenario tests 21 (city asked, saved, never commented on) and 22 (spoken lines short, on "aap", free of digits/dashes/overacted fillers, clean duet data). 33/33 pytest tests passing; web build passing.

### Added
- **Phase 3 First-Interaction Alignment & Comprehensive Field Capture**:
  - Replaced illogical Phase 3 question (*"Roxstar pe live stages dekhe abhi tak ya seedha is room mein connect hue?"*) with an authentic first-time app introduction (*"Waise Roxstar pe log bina kisi judgment ke 24/7 live jam karte hain aur duets gaate hain. Aap yahan bas chill karke gaane sunne aaye ho ya khud bhi try karne?"*), recognizing that upon fresh app download, the call with Simran is the user's very first interaction.
  - Analyzed all conversational questions asked by Simran and expanded the user discovery engine with 4 useful profile fields:
    - `referral_source`: Discovers how the user found Roxstar (friend recommendation, Instagram reel, ad, Play Store).
    - `musical_role`: Discovers whether they are primarily a listener, singer, hummer, or both.
    - `singing_comfort`: Discovers comfort level (bathroom singer, sings with friends, performer, shy).
    - `favorite_song`: Discovers loop song or favorite track on repeat (e.g. "Kesariya", "Tum Hi Ho").
  - Configured silent background capture: if the user answers, save field silently; if they skip, decline, or don't mention something, simply let it be without interrogation or re-asking.
  - Added automated scenario test `test_scenario_20_comprehensive_input_fields_capture_and_first_interaction_sensible_intro` (31/31 pytest tests passing).
- **Multi-Turn Runaway Speech & Speaking Without User Input**:
  - Identified root causes of Simran speaking back-to-back turns without waiting for user input:
    1. `save_profile` was returning `'{"status": "saved"}'` with default blocking tool behavior, which caused LiveKit to request a model reply (`reply_required=True`), prompting Gemini to generate unprompted filler turns like `"Hmm... ruko, soch rahi hoon."`.
    2. Phase 3 & Phase 4 prompt text lacked turn delimiters, causing the LLM to rush through the live stages question, coins gift, and duet pitch in a single burst.
    3. Old prompt guidelines stated `"A bot does question, answer, question, answer. A person does not."` with `"FILLER 5% — 'Hmm... ruko, soch rahi hoon.'"`, actively instructing the LLM to speak unprompted.
  - Implemented comprehensive fixes:
    - Set `tool_behavior=genai_types.Behavior.NON_BLOCKING` on `RealtimeModel` in `worker.py`.
    - Made `save_profile` return `None` (`reply_required=False`), enabling LiveKit's automatic `tool_response_scheduling=SILENT` so background tool executions never trigger speech.
    - Updated `check_available_duets` tool description to forbid pre-emptive invocation before Phase 4.
    - Filtered out stray thinking filler artifacts (`"Hmm... ruko, soch rahi hoon"`) in `on_item`.
    - Replaced harmful turn-shape prompt rules with **STRICT TURN-TAKING**: strictly ONE Simran turn per user input, mandatory silence after each turn, and unskippable pauses between Phase 3 Turn 1, Turn 2, and Phase 4.
  - Added automated test scenario `test_scenario_19_strict_single_turn_and_no_unprompted_speech` (30/30 pytest tests passing).

### Added
- **Formality Calibration — Elimination of 'ji' with User Names**:
  - Enforced strict non-negotiable rule forbidding the use of "ji" with user names (e.g. NEVER say "Yuvi ji", "Rahul ji", "[Name] ji").
  - Configured Simran to address users directly by their first name alone ("Yuvi!", "Rahul!", "[Name]!"), maintaining a relaxed, friendly 22-year-old peer-to-peer vibe while preserving respectful "aap" pronouns.
  - Cleaned all opening greeting variations and reaction phrases to avoid formal "Haan ji" or "Hello ji" (replaced with natural "Haan", "Hey", "Hello").
  - Added automated test scenario `test_scenario_18_no_formal_ji_with_names` (29/29 pytest tests passing).
- **Phase 2 Music Opener ("Aap Gaane Sunte Ho Ya Gaate Ho?") & Adaptive Branching**:
  - Reframed the very first question of Phase 2 (Musical Soul) around the user's core intent: *"Chalo ab thodi gaano ki baat karte hain — waise aap gaane sirf sunte ho ya khud bhi gaate ho?"* (or *"Waise aap gaane sirf sunte ho ya khud bhi gunguna lete ho?"*).
  - Engineered distinct adaptive paths based on user response:
    - **Path A (Pure Listener)**: Validates the joy of listening (*"Sunne ka bhi alag hi maza hai! Accha music ho toh mood ekdum fresh ho jaata hai"*), explores loop songs and specific genres (Arijit, Punjabi, Retro, Kishore, K-pop, Bhajan, Indie), and shares Simran's late-night listening vibe via the Trade Rule.
    - **Path B (Singer / Hummer)**: Validates warmly, transitions into the bathroom singer confession (*"Aap purely bathroom singer ho ya doston ke saamne bhi mic pakad lete ho?"*), and bonds over performance anxiety before asking about their favorite singing tracks.
    - **Path C (Refusal / Decline)**: Smoothly acknowledges (*"Bilkul theek hai, koi baat nahi!"*) and advances straight to Phase 3 without pushing.
  - Adjusted Phase 3 to eliminate redundant listener-vs-singer questioning, focusing cleanly on live stage exploration and the 50 Welcome Coins perk.
  - Added automated scenario test `test_scenario_17_phase_2_sunte_ho_ya_gaate_ho_adaptive_branching` bringing the test suite to 28 passing tests.
- **Natural Laugh Lab & Laughter On/Off Controls**:
  - Implemented authentic Indian girl laughter guidelines in `prompt.py`: spontaneous giggles (`"hehe"`), warm breathy chuckles (`"haha yaar"`), and dramatic teasing laughs (`"haha haaye!"`) sprinkled in ~25% of playful turns.
  - Added full **Turned-Off Laughter** mode: when disabled, Simran maintains a warm, calm, polite conversational tone with zero laughter sounds or chuckles.
  - Created dedicated interactive **Natural Laugh Lab** (`web/src/components/NaturalLaughDemo.tsx`):
    - Master Laughter Toggle (`[😄 Natural Laugh: ACTIVE]` / `[😐 Laughter: TURNED OFF]`).
    - 5 Curated Audio Sample Cards with 1-click audio playback: Sarojini Bargain Chuckle, Bathroom Singer Giggle, Sarcastic Haaye Laugh, Late-Night Chai Giggler, and Laugh Turned OFF (Clean & Composed).
    - Custom Phrase Test Bench: type any custom line, choose laugh prefix (`haha`, `hehe`, or none), and play voice audio with real-time waveform animation.
    - Live Call Sync: synchronizes laughter mode preference over LiveKit DataPackets (`roxstar.set_laugh_mode` / `roxstar.laugh_mode_updated`) directly into the active WebRTC room.
  - Added unit test `test_laugh_mode_toggle_and_summary_context` and scenario test `test_scenario_16_user_toggles_laugh_mode` (27/27 pytest tests passing).
- **Delhi-Only Identity & Zero-Commentary On Other Cities**:
  - Anchored Simran's origin and identity strictly in Delhi: when swapping names, she introduces herself as Simran from Delhi (`"Oho [Name]! Main Simran, Delhi se. Waise aap kya karte ho — job ya college?"`).
  - Completely removed city probing and eliminated commentary, evaluations, and stereotypes on other cities (no clichés about Mumbai trains, Bangalore traffic, or Pune weather).
- **Thinking Stall Fix on Tool Completion**:
  - Removed `tool_response_scheduling=SILENT` from `RealtimeModel` in `worker.py`. Setting `SILENT` caused Gemini Live API to suppress verbal response scheduling after tool executions (like `save_profile`), leaving the session hanging in `thinking` indefinitely. Reverted to standard `WHEN_IDLE` scheduling so Simran naturally speaks her reply immediately after capturing user details.
- **Unbuffered Subprocess Logging**:
  - Configured `PYTHONUNBUFFERED=1` and `-u` flags in `run_sts.py` ensuring real-time log flushing across child worker processes.
- **Curious Follow-Up on Generic Occupation Answers**:
  - Enhanced Simran's conversational funnel in `prompt.py` with explicit generic occupation follow-up rules: when users provide broad answers (e.g. "business", "job", "college", "student", "freelancing", "startup", "office"), Simran will not rush past to hobbies or music. Instead, she reacts with genuine interest and asks exactly one natural follow-up question (e.g. "Business mein kya karte ho?", "College mein kya padh rahe ho?", "Job kis field mein hai aapki?") before sharing her own design work and advancing.
  - Implemented `is_generic_occupation()` in `onboarding.py` and added automatic `OCCUPATION NOTE` context guidance in `OnboardingTracker.get_summary_context()` that stays active until concrete occupation details are discovered.
  - Added unit test `test_generic_occupation_detection_and_followup_hint` and scenario test `test_scenario_15_user_generic_occupation_followup` (25/25 tests passing).
- **Dynamic Procedural 3D Simplex Turbulence & Non-Repetitive Speaking Orb Styles**:
  - Implemented 3D simplex procedural noise (`snoise`) in GLSL inside `SpeakingOrb.tsx` and `web/public/speaking-orb.js`, creating organic, non-repetitive fluid eddies so no two frames or audio swells look identical.
  - Added non-linear orbital rotation with dynamic velocity modulation, variable X/Y inclination wobbles, and random per-particle drift vectors (`aDrift`).
  - Curated and implemented 3 distinct visual styles:
    - **`✨ Astral` (Astral Stardust - Recommended Best)**: Deep cosmic stardust cloud with fluid turbulence, StarMaker Royal Purple core shifting to vibrant Hot Pink with bright Electric Cyan acoustic sparkles and upward traveling syllable rings.
    - **`🌟 Plasma` (Bioluminescent Plasma Core)**: Energetic solar/plasma orb with coronal mass ejections and radiant flares reacting to vocal dynamics.
    - **`🎵 Sonic` (Cyber Sonic Wave)**: Harmonic acoustic latitude rings undulating like a futuristic 3D equalizer.
  - Added interactive visual style switcher pill bar (`✨ Astral`, `🌟 Plasma`, `🎵 Sonic`) in `SimranPresence.tsx` with persistent user selection via `localStorage` (`roxstar_orb_style`).
- **Sticky Controls & Viewport Lock**:
  - Locked main studio container to `100vh`/`100dvh` with `overflow: hidden`, wrapping scrollable content in `.stage-content-scroll` while docking `.stage-controls` with sticky positioning at the bottom.
  - Fixed mobile & desktop layout so the Mic On/Off toggle, Call button, and stage visualizers fit within the screen without requiring vertical page scrolling.
- **True StarMaker Brand Aesthetics (Clean White Canvas, Royal Purple & Hot Pink)**:
  - Redesigned the entire web studio UI under Lead UI/UX direction to adhere to StarMaker's authentic brand color balance: 60% Pure White canvas (`#ffffff`), 30% Royal/Electric Purple (`#7c3aed`), and 10% High-Energy Hot Pink (`#ff2e93`), with Golden Amber (`#f59e0b`) for coin wallets and rewards.
  - Updated all cards, modals, composer inputs, badges, and performer containers to pure white surfaces with soft lavender depth (`rgba(124, 58, 237, 0.12)`) and high-contrast obsidian-plum typography (`#1f1633`).
  - Preserved high-contrast dark monitor frames for synchronized teleprompter screens (`#18112c`) so glowing lyrics and the animated bouncing ball (`🎵`) stand out with maximum legibility.
- **Speaking Orb (Signal/Aqualang Specification)**:
  - Created [`web/src/components/SpeakingOrb.tsx`](file:///y:/roxstar/sts_lab/web/src/components/SpeakingOrb.tsx) and standalone zero-dependency [`web/public/speaking-orb.js`](file:///y:/roxstar/sts_lab/web/public/speaking-orb.js):
    - 12,000 Fibonacci sphere WebGL particles on desktop (6,000 on mobile/touch).
    - Custom vertex & fragment shaders with StarMaker pink-to-purple additive luminous glow.
    - Real-time vocal swell responding to audio amplitude.
    - Traveling lit rings from bottom to top with every syllable during speech.
    - Particle-landed live captions with `aria-live="polite"` and word-by-word glowing highlights.
    - Full Web Component `<speaking-orb>` API supporting `say(text, {audio})`, `listen()`, `state`, `level`, `rest`, and `end` events.
  - Integrated `SpeakingOrb` into [`SimranPresence.tsx`](file:///y:/roxstar/sts_lab/web/src/components/SimranPresence.tsx) and [`SimranOrb.tsx`](file:///y:/roxstar/sts_lab/web/src/components/SimranOrb.tsx).

- **StarMaker-Inspired Live Karaoke Stage Experience**:
  - Transformed the web studio UI into an immersive StarMaker karaoke atmosphere with deep obsidian stage background (`#090714`), neon violet and pink accents, and high-energy interactive components.
  - **Seamless Stage Redirection**: When user clicks "Join Duet" or "Solo Record" (or when Simran directs via `navigatedDuetRoom` or `navigatedSoloRecording`), the interface redirects directly into the full-featured StarMaker Live Duet Stage or Solo Recording Studio.
  - **Dynamic Free Coins Celebration Popup**: Auto-detects coin mentions in Simran's voice speech transcript (e.g. "coin", "coins", "daily login bonus") and instantly bursts the StarMaker Gold Coin Celebration Modal with spinning 3D coin, sunburst rays, and "+50 Coins" reward notification.
  - **Interactive Floating Gifts Particle System**: Added interactive gift dock with 🌹 Rose (5 C), 🎙️ Golden Mic (10 C), 👑 VIP Crown (25 C), and 🚀 Star Rocket (50 C). Tapping gifts triggers multi-emoji floating particles ascending the stage with sway and fading trails (`@keyframes floatGiftUp`), live audience reaction broadcasts, and wallet balance deductions.
  - **Synchronized Teleprompter with Bouncing Karaoke Ball**: Added animated bouncing musical ball (`🎵`) jumping along the active lyrics track with glowing line highlights and Web Audio harmonic chord synthesizer.
  - **Real-Time Vocal Pitch Rating Meter**: Added StarMaker vocal performance badges (`SSS`, `SS`, `S`, `A`) with real-time percentage and shimmering neon gradient meter.
  - **VIP Front-Row Cheer Pod**: Positioned Simran with a VIP avatar in the front row of the live stage, displaying synchronized real-time cheer quotes as the user sings.
  - **Mobile Responsiveness & Segmented View Switcher**: Designed mobile layouts (`100dvh`, zero horizontal overflow) with top segmented switcher (`[🎤 Studio Stage]` / `[💬 Simran & Chat]`), unread speaking pulse badges, touch targets >= 44px, and smooth slide-up bottom sheets for modals.

### Fixed
- **Anti-Repetition & False-Interruption Remediation**:
  - Identified and eliminated the root causes of the bot occasionally repeating itself:
    - **False Interruption Auto-Resume Disabled**: Configured `turn_handling={"interruption": {"enabled": True, "min_duration": 0.7, "resume_false_interruption": False}, "preemptive_generation": {"enabled": False}}` in `AgentSession`. This prevents ambient mic noise or micro-coughs from triggering false interruptions that previously replayed the agent's turn from the beginning.
    - **Gemini Live Config Sanitization**: Removed `presence_penalty` and `frequency_penalty` from `RealtimeModel` because the Gemini Live bidirectional WebSocket endpoint strictly disallows penalty parameters in its generation config with error `1007 presence_penalty not supported in generation config`. Anti-repetition is instead handled via VAD interruption calibration and strict prompt guardrails.
    - **Opening Greeting Deduplication Guard**: Added `has_greeted` state latch in `worker.py` to prevent race conditions between automatic ambient audio VAD and `session.generate_reply()`.
    - **Post-Tool-Call Continuity Prompting**: Changed `save_profile()` tool response to `"Field saved silently. Do not repeat the previous question; smoothly advance to the next topic."` to prevent re-asking funnel questions after tool runs.
    - **Prompt Anti-Repetition Guardrails**: Added explicit rules in [`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py) forbidding re-introductions ("Main Simran"), repeating questions, or echoing user turns.
    - **Audio Track Detach & Hardware Echo Cancellation**: Enforced `track.detach()` before attaching audio tracks in `useStsRoom.ts`, and enforced explicit browser echo cancellation and noise suppression in `setMicrophoneEnabled` to prevent acoustic loopback.

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

