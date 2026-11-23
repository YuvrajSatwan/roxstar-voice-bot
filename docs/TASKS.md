# TASKS.md — Development Progress Tracker

> **Current Sprint**: STS Lab Stabilization & Conversational Calibration  
> **Verification Status**: 64/64 Automated Tests Passing | Frontend Production Build Passing

---

## 1. Completed Tasks (Verified)

_The full list of completed tasks is in `TASKS_ARCHIVE.md`. Only open it if you need history._


## 2. Currently Ongoing Tasks

- [x] **RoxStar integration, Phase 1 (2026-11-13, branch `feat/integrate-simran-onboarding`)**: login check, private per-user room, no second Simran, capacity / per-user / session-length limits, live duet list adapter (strict mode), popup-cancel call, and the `/simran` WebView page with its app bridge. 170 tests pass; frontend builds. Details in `CHANGELOG.md` and `PROJECT_CONTEXT.md` section 11.
- [ ] **Next phases (other repos, each needs approval)**: rox-partyroom `active-duets` endpoint, rox-chat welcome message / queue / popup / `session-started` endpoint, Rox-Auth-K8s enqueue helper, mobile WebView work.


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

