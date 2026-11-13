# Prompt for the audit agent (analysis only, no changes)

Copy everything below the line into the agent.

---

You are a senior full-stack and voice-AI engineer. Audit the whole **RoxStar Simran STS Lab** repository and report what is wrong, fragile, misleading, slow, insecure or improvable. **This is an analysis task only. You must not change anything.** Do not assume anything works because a test or a doc says so; verify with real data and real runs, then report.

## 0. STRICT RULE: read-only
- **Do not edit, create, rename or delete any file in the repository**, except for writing one new report file: `docs/AUDIT_REPORT.md`.
- **Do not fix anything**, not even a typo or an obvious one-line bug. Report it instead.
- **Do not commit, push, branch, stash, reset or touch git history.** Do not change `.env`, `requirements.txt`, `package.json`, lockfiles or any config.
- **Do not modify any database** (`sts_lab.db`, Render PostgreSQL, Neon, or any other). Do not run the maintenance script, migrations, deletes or exports against real data. If you need data, build a scratch SQLite file or a throwaway local database **outside the repository** (use a temp or scratchpad directory) and delete it afterwards.
- **Do not call external paid or production services** and do not send user data anywhere. Do not start deploys.
- Running tests, the web build, linters, type checks and the app locally is allowed as long as they do not change tracked files. If a command would change tracked files or generate files inside the repo (for example build output that is not git-ignored), run it on a copy of the repo outside the working directory, or skip it and say so.
- If you think a change is needed to continue, **stop and write it in the report**. Do not make it.
- If you accidentally changed something, say so in the report and restore it exactly.

## 1. What the product is
Roxstar is a karaoke app (like StarMaker). Simran is a voice onboarding host that talks to a new user for about 4 to 5 minutes, learns about them, introduces Roxstar and welcome coins, and guides them into a first duet or solo recording. Stack: LiveKit WebRTC + Google Gemini Live (direct speech-to-speech, never STT->LLM->TTS), Python worker (`worker.py`), state engine (`onboarding.py`), persona prompt (`prompt.py`), token server (`token_server.py`, stdlib HTTP), persistence and admin API (`db/`), React 19 + Vite web app (`web/`) with a `/admin` dashboard (`web/src/admin/`). Deployed on Render (backend, static frontend, PostgreSQL). Local dev uses SQLite (`sts_lab.db`).

## 2. Read first
`AGENTS.md`, `docs/PROJECT_CONTEXT.md`, `docs/TASKS.md`, `docs/ADMIN_DASHBOARD.md`, `docs/CHANGELOG.md`, then `worker.py`, `onboarding.py`, `prompt.py`, `db/*`, `token_server.py`, `web/src/hooks/useStsRoom.ts`, `web/src/admin/*`, `tests/*`.

## 3. Constraints the product must keep (judge proposals against these)
1. Keep direct speech-to-speech for the live conversation; never propose a cascading STT -> LLM -> TTS path for the call itself (an offline speech-to-text for logging only may be proposed as an option).
2. The audio event loop must never block. Note: `UserProfileStore` still writes JSON synchronously from `save_profile`; report it.
3. The DataPacket contract (`roxstar.sts.state`, `.telemetry`, `.transcript`, `roxstar.user_state`, `roxstar.stage_transferred`, `roxstar.bot_turned_off`, and the rest in `docs/PROJECT_CONTEXT.md`) must keep working.
4. Simran's conversation rules in `prompt.py`: 12 to 22 words per turn (handoffs under 25), "aap" only, no "ji" after names, at most one question per turn, the question comes last, she shares nothing about herself unless asked, never comments on any city, asks the city once and saves it, strict 2-decline exit, "no interview tone" rule, tools called silently.
5. The "IF ASKED WHETHER YOU'RE AN AI OR A BOT" section of `prompt.py` currently tells her to deny being an AI. **Do not propose changing it as a prompt tweak.** Report it as an open product and legal question (voice-bot disclosure rules, user trust) for a human to decide.

## 4. Method
1. **Read and trace.** Follow each data path end to end: web name box -> token server -> LiveKit identity -> worker -> recorder -> database -> admin API -> dashboard -> export.
2. **Reproduce with data, read-only.** Using a scratch database outside the repo, replay realistic conversations (Hinglish, one-word answers, skipped `save_profile` calls, refusals, early exits, repeated lines) through the recorder and the admin API. Compare what the dashboard shows with what actually happened. Use a browser to look at `/admin` (every tab, filter, drawer, export button, delete button, light and dark theme, a phone-width viewport), but do not press Delete or export on real data.
3. **Check PostgreSQL behaviour by reading and by a throwaway local instance** (JSON columns, `ilike`, timezone-aware datetimes, pagination, cascades), not only SQLite.
4. **Run the existing checks** (`py -m pytest tests/ -v`, the web build) only where they leave tracked files untouched, and record the exact results. Note that `livekit` is not installed in the local Python, so `worker.py` and `token_server.py` cannot be imported there; state what that prevented you from verifying.
5. Never say something is wrong, or fine, unless you saw it in code or in a run. Say "could not reproduce" or "could not verify" honestly.

## 5. Known problems to verify (leads, not facts)
Some were fixed recently. Confirm the current state of each and report it.

**A. Dashboard and data correctness (highest priority)**
- User identity: the web name box used to default to "Rahul" and was stored as the real name, so every user showed as Rahul. A per-browser `visitor_id` and a "Guest" display were added. Check the whole path, including users who type no name, the same name, or change name between calls.
- Percentage bars and rates: profile completeness (8 core fields) and "answers captured" (captured out of asked) were recently redefined. Re-derive them from first principles; check edge cases (no questions asked, early exit, repeated questions, a refused answer); check that every label says exactly what is measured.
- Auto-captured answers (`db/conversation_rules.py`) are heuristics on Hinglish text: topic detection, `clean_answer`, occupation joining. Test many phrasings, wrong transcripts, one-word answers, refusals and late answers. Look for false captures and for auto values overwriting better tool-saved values.
- Funnel phase, exit reason, response time and welcome-coin inference rely on text markers and LiveKit state events that were never run against a live call. Judge how likely they are to be wrong and whether failures show as blank or as wrong numbers.
- Provider metrics were bogus (negative TTFT, 1 to 4 ms, 1000+ tokens per second). Check the filtering and what the dashboard shows when no valid latency exists.
- Admin API and SQL: correctness and performance (`metrics` and `funnel` scan messages in Python; N+1 queries in `list_users`; the sessions list loads messages for each page), pagination totals, filters, search escaping, delete cascades, export size limits, formula-injection protection, time zones (stored UTC, shown local), empty and error states, and behaviour when the API is slow or down.
- Duplicate and near-duplicate Simran lines (the same text twice, or two slightly different versions of one turn) and user turns split into several final segments. Check the merge window and the dedupe logic.
- Admin access: with no `ADMIN_API_KEY` the API is open to loopback only. Judge whether that can be bypassed behind Render's proxy; check logging of deletes and exports; judge whether roles or rate limiting are needed.
- Schema management: there is only `create_all` (no migrations). Judge indexes, retention of transcripts, and backups.

**B. Worker and conversation engine**
- Returning-user recognition is dead code (`UserProfileStore.get_or_create` is never called by `worker.py`), and each session starts from a fresh profile.
- The typed name and saved profile values are inserted into the model's system instruction (prompt-injection risk).
- Data packets from the client (`roxstar.chat`, `roxstar.app_event`, `rejoin_simran`, `send_duet_gift`, `duet_decline`) are accepted from any participant without checking the sender. The substring match on "back" and "kahan" in `roxstar.chat` is fragile.
- `LIVE_SESSION_NOTES` lists affective dialog, language hints, context compression and session resumption as required, but `worker.py` sets none of them. Check what the installed plugin version supports. Note: `AudioTranscriptionConfig(language_codes=...)` is rejected on the Gemini Developer API, so do not recommend it.
- Worker capacity: `load_threshold=inf`, thread executor, one process, no concurrency or cost limit.
- The model sometimes repeats a question after a tool call, speaks twice in a row, or skips `save_profile`. Propose (do not build) a text-mode simulated-user test harness with scripted users (shy, one-word answers, refuses city, asks "aap kahan se ho", declines twice, says yes to a duet, sad user, minor) and the behaviours it should assert.
- The exit and handoff lines in `onboarding.py` must stay in sync with the markers in `db/conversation_rules.py` (for example "Ritika ka phone", "Swiggy"). Report any risk of drift.
- Product promises that nothing backs: "50 welcome coins aa gaye hain" (no real credit) and "main comment bhi karungi" (the bot powers off). List them for the founder.

**C. Web app (user-facing)**
- "StarMaker" in visible text and labels, the fake default 385 ms TTFT, hardcoded voice "Sulafat" (config default is Leda), legacy `Saara`/`Saraah` names, unused components (`QuickPrompts`, `LatencyCard`, `SaaraOrb`, `SaraahPresence`), a 1,300-line `KaraokeStageBar` with mock rooms and gifts, an 840 KB main bundle.
- Accessibility, mobile layout, error and reconnect states, microphone-denied handling, and what the user sees when the backend is asleep (Render free plan).

**D. Backend, security and ops**
- `token_server.py`: unauthenticated `/token` and `/rooms`, client-chosen room and identity, CORS reflecting any origin, a global lock serialising LiveKit calls, error text leaked to clients, a `204` response with a body, no rate limiting.
- Packaging: imports depend on the folder being named `sts_lab` plus `sys.path` edits in several files; `requirements.txt` has floors, not pins; the Dockerfile uses `npm install` and runs as root; `render.yaml` uses the free plan, which sleeps and has temporary disk.
- Logging prints user speech and names. Judge what may be logged. Judge consent, retention, deletion on request and export on request for transcripts (India DPDP Act).
- Observability: structured logs, a health check that includes database status, alerts when the recorder drops operations.

**E. Docs and tests**
- Docs drift: README and `AGENTS.md` test counts and word limits (`AGENTS.md` still says 6 to 14 words), `docs/WORKFLOW.md`, `docs/PROJECT_CONTEXT.md` field list.
- Tests mostly assert that strings exist in the prompt. Judge behaviour-test coverage, missing tests for `worker.py` and `token_server.py`, and the lack of CI.

## 6. Look beyond this list
Read the code with fresh eyes. Anything that is wrong, misleading, slow, insecure, untested or confusing counts. Also list **improvements** (product, conversation quality, analytics, UX, performance, cost) even where nothing is broken.

## 7. Deliverable: one file, `docs/AUDIT_REPORT.md`
1. **Summary** (10 lines): the most important problems and the most valuable improvements.
2. **Findings table**: ID, area, title, severity (blocker / high / medium / low), evidence (file and line, or the data or run that shows it), impact, **proposed fix**, effort (S / M / L), risk of the fix. Mark each as `confirmed`, `could not reproduce` or `could not verify (reason)`.
3. **Improvements list**, ranked by value against effort.
4. **Suggested order of work** (a roadmap a developer can follow), with dependencies.
5. **Decisions needed from a human** (product, legal, founder), including the AI-disclosure question in section 3.5.
6. **What you could not check and why**.
7. **Confirmation that you changed nothing** except this report: list every command you ran that could have touched files and what you did to keep the repository unchanged.

Do not fix anything. Do not say something is confirmed unless you saw it.
