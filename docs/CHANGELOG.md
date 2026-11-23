# CHANGELOG.md — Significant Project Changes

All notable changes, architectural pivots, and major additions to the **RoxStar STS Lab** repository are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---
## 2026-11-23 - Simran text chat: real Gemini replies instead of canned lines
- `text_chat.py`: up to 4 Gemini attempts inside one 20 s budget (`STS_CHAT_TIMEOUT_SEC`, default now 20). 503/timeouts/unusable answers are retried; quota (429), missing model (404) or refused key (401/403) go straight to the backup model `STS_CHAT_FALLBACK_MODEL` (default `gemini-3.1-flash-lite`, `off` = none). Answers carry `attempts`, and canned lines carry `fallback_reason`. `token_server.py` warms the Gemini connection at start (`STS_CHAT_WARMUP`) and builds the shared engine once.
- Found while testing: the Gemini key is on the free tier (15 requests/minute). Production needs a paid key.
- Tests: `tests/test_text_chat_resilience.py` (42 new); 312 pass.

---
## [Unreleased] - 2026-11-13

### Added (RoxStar integration, branch `feat/integrate-simran-onboarding`, Phase 1)
All of this is **off by default**. With `STS_AUTH_MODE` unset the lab behaves exactly as before.
- **Final handoff to a duet post** (2026-11-17, flag `STS_DUET_POST_ID`, empty = off): at the end of the conversation Simran pitches Harshit's "Tum Hi Ho" duet as the one live option (no choice of rooms). Your Phase 4 flow is unchanged: only when the user agrees does she call `navigate_to_duet`, sign off and power off, and the app then opens the post automatically (no button); hesitation and declines follow the prompt (reassure, solo, exit). `check_available_duets` returns that single destination (`DuetRoomRegistry(featured=...)`, wording in `featured_duet_pitch`); `navigate_to_duet` adds `post_id` to the `roxstar.duet_navigation` packet; the web page closes with `{destination: 'duet_post', post_id}` and the app opens that post only if its own backend has it. Optional `STS_DUET_HOST_NAME` / `STS_DUET_SONG_TITLE`. Tests: `tests/test_duet_featured.py`.
- **Real login on the token server** ([`roxstar_auth.py`](file:///y:/roxstar/sts_lab/roxstar_auth.py), [`token_server.py`](file:///y:/roxstar/sts_lab/token_server.py)): with `STS_AUTH_MODE=roxstar`, `POST /token` needs a RoxStar access token (HS256, `exp` required, `type` must be `access`, user id from the `userID` claim). Refresh tokens (valid 365 days), expired, forged, `alg:none` and wrong-secret tokens all get one generic `401`. The server refuses to start in this mode without `JWT_API_KEY`.
- **Private room per user**: the room is always `sts-simran-<userID>` and the LiveKit identity `rx-<userID>`. A room name sent by the browser is ignored, so one user can never enter another's room. `POST /rooms` and the demo `/duets` list are switched off in this mode.
- **No second Simran**: before sending an agent, the server checks the room's existing dispatches. A WebView refresh or double tap re-uses the running Simran instead of starting another.
- **Cost protection**: `STS_MAX_CONCURRENT_SESSIONS` (default 50; extra users get `503 busy`), `STS_USER_SESSIONS_PER_HOUR` (default 3; `429 rate_limited`; refreshes and busy answers do not use the allowance up) in [`session_limits.py`](file:///y:/roxstar/sts_lab/session_limits.py), and `STS_MAX_SESSION_SEC` (default 480): Simran wraps up warmly at the limit and is powered off 60 s later at the latest ([`worker.py`](file:///y:/roxstar/sts_lab/worker.py), new exit reason `time_limit_exit`).
- **Live duet list** ([`onboarding.py`](file:///y:/roxstar/sts_lab/onboarding.py), [`rox_services.py`](file:///y:/roxstar/sts_lab/rox_services.py)): in RoxStar mode `DuetRoomRegistry(strict=True)` has no demo rooms, refreshes from rox-partyroom (2 s timeout, 60 s cache) and `get_room` accepts only an exact id from the live list. If the backend is down or empty, Simran offers solo recording. `navigate_to_duet` refuses an unknown or just-closed room.
- **Popup cancel signal**: after a successful token, the server tells rox-chat in the background that the user opened Simran (1.5 s timeout, 2 retries, never blocks, secret never logged).
- **WebView page** (`/simran`, [`web/src/simran/`](file:///y:/roxstar/sts_lab/web/src/simran/SimranWebViewPage.tsx), [`web/src/bridge.ts`](file:///y:/roxstar/sts_lab/web/src/bridge.ts)): party-room look, one "Talk to Simran" tap (needed for sound and mic permission), friendly screens for busy / rate-limited / no login / mic denied, and `simran.ready` / `simran.close` messages to the app. It closes only after Simran has powered off, hangs up if the app stays in the background for 30 s, and the first close message wins. The login token is kept in memory only; the `?dev_token=` shortcut exists only in dev builds.
- New env vars (placeholders in `.env.example`): `STS_AUTH_MODE`, `JWT_API_KEY`, `STS_MAX_CONCURRENT_SESSIONS`, `STS_USER_SESSIONS_PER_HOUR`, `STS_MAX_SESSION_SEC`, `PARTYROOM_BASE_URL`, `CHAT_BASE_URL`, `SIMRAN_INTERNAL_SECRET`. New dependency: `PyJWT`.
- 170 tests pass (64 existing + 106 new in `test_roxstar_auth.py`, `test_session_limits.py`, `test_duet_registry_remote.py`, `test_rox_services.py`, `test_token_server_roxstar.py`).

### Changed
- `tests/conftest.py` no longer lets tests read a developer's real `.env` (one persistence test was failing on any machine with a live `DATABASE_URL`).
- Not changed on purpose: coins stay static (no wallet writes) and `prompt.py` is untouched. The coin wording, AI-disclosure and voice-data questions are tracked as open items.


## [Unreleased] - 2026-11-11

### Fixed (audit follow-up, 2026-11-12)
- **Auto-captured answers** ([`db/conversation_rules.py`](file:///y:/roxstar/sts_lab/db/conversation_rules.py)): refusals ("Naam nahi batana", "kyun batau", "nahi pata") are no longer stored as name/city/occupation/hobby; fillers like "Haan boliye" and "mein hi" are stripped; "Noida ... par Patna se" keeps the current city; "sunta nahi hoon, gaata hoon" is `singer`; Devanagari question/stage/exit markers added; exit lines need a leaving verb, a bye and no question; the "ye bataiye" flag catches more spellings.
- [`token_server.py`](file:///y:/roxstar/sts_lab/token_server.py): room codes validated, name capped at 64 characters, generic error text to clients, requests with `X-Forwarded-For` are non-local for the admin no-key mode.
- [`worker.py`](file:///y:/roxstar/sts_lab/worker.py): context-window compression and session resumption enabled; data packets from non-human participants ignored; whole-word match for the "back/kahan" recall; chat and transcript text no longer written to logs. [`onboarding.py`](file:///y:/roxstar/sts_lab/onboarding.py): saved values lose brackets/newlines and are capped at 120 characters before reaching the model instructions.
- **Web**: no fake 385 ms TTFT (shows a dash until real data), real voice label, "StarMaker" removed from visible text, mobile-responsive `/admin`.
- **Docker**: `npm ci`, non-root user. **Docs**: word limits, test counts, 12 profile fields, missing packet types, bind address.
- 63 tests pass (5 new regression tests). `prompt.py` was not changed. Still open: the AI-disclosure question, affective dialog (needs the alpha API), dead returning-user recognition, unbacked coin credit, mock stage data, accessibility, CI.

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


---

_Entries from 2026-11-10 and older are in `CHANGELOG_ARCHIVE.md`. Only open it if you need history._
