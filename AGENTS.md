# AGENTS.md — Development Guidelines & Instructions for AI Agents

> **Audience**: AI Coding Agents & Engineers working in this repository.  
> **Mission**: Maintain, extend, and test the RoxStar Simran Speech-to-Speech (STS) Lab without introducing architectural drift, duplicate code, or security risks.

---

## 1. Operating Rules & Pre-Flight Protocol

Before beginning any substantial development task:

1. **Read Core Context First**:
   - [`AGENTS.md`](file:///y:/roxstar/sts_lab/AGENTS.md) (this file)
   - [`docs/PROJECT_CONTEXT.md`](file:///y:/roxstar/sts_lab/docs/PROJECT_CONTEXT.md) (architecture, data flows, and decisions)
   - [`docs/TASKS.md`](file:///y:/roxstar/sts_lab/docs/TASKS.md) (current task state and roadmap)
2. **Inspect Existing Implementations**:
   - Check existing helper methods, models, and hooks before writing new code.
   - Never assume functionality is missing without inspecting [`worker.py`](file:///y:/roxstar/sts_lab/worker.py), [`onboarding.py`](file:///y:/roxstar/sts_lab/onboarding.py), or [`web/src/hooks/useStsRoom.ts`](file:///y:/roxstar/sts_lab/web/src/hooks/useStsRoom.ts).
3. **Keep Edits Scoped**:
   - Restrict modifications strictly to the files necessary for the user's task.
   - Do not reformat, refactor, or reorganize unrelated files.
   - Preserve existing code comments, docstrings, and backward-compatibility aliases.

---

## 2. Technical Stack & Environment Conventions

### Python Backend
- **Python Version**: 3.11+ (Runtime on Windows uses the `py` launcher: `py -m ...`).
- **Core Frameworks**: `livekit-agents` (1.8.x), `livekit-plugins-google` (1.8.x), `google-genai` (2.24.x).
- **Async Runtime**: Standard `asyncio`. Heavy libraries (`ssl`, `anyio`, `google.genai`) are prewarmed in `prewarm()`.
- **System Path**: Every entrypoint script (`run_sts.py`, `worker.py`, `token_server.py`, `tests/conftest.py`) ensures the project root and parent are in `sys.path`. Maintain this pattern.

### Web Frontend
- **Framework**: React 19, TypeScript, Vite 8.
- **WebRTC Client**: `livekit-client` (`Room`, `createAudioAnalyser`).
- **Styling**: Vanilla CSS in [`web/src/index.css`](file:///y:/roxstar/sts_lab/web/src/index.css) using design tokens (dark studio theme).

---

## 3. Architecture Constraints & Guardrails

1. **Direct Speech-to-Speech (S2S) Only**:
   - Do NOT introduce cascading `STT -> LLM -> TTS` pipelines. Audio flows bi-directionally between Gemini 3.8 Live API and LiveKit WebRTC via `RealtimeModel`.
2. **Real-Time DataPacket Contract**:
   - Communication between the backend worker and the web client must use LiveKit DataPackets (`publish_data` / `room.on("data_received")`).
   - Message payloads are JSON-encoded dictionaries containing `type` and `timestamp`.
   - Standard event types include `roxstar.sts.state`, `roxstar.sts.telemetry`, `roxstar.sts.transcript`, `roxstar.user_state`, `roxstar.stage_transferred`, and `roxstar.bot_turned_off`.
3. **Persona & Guardrails Integrity**:
   - Simran's persona prompt in [`prompt.py`](file:///y:/roxstar/sts_lab/prompt.py) requires strict conversational constraints:
     - Short turns (6–14 words, max 18).
     - Handoff / exit excuses strictly under 25 words.
     - Maximum 1 question per turn; only ~50% of turns contain questions.
     - Trade Rule: Share personal Delhi details before asking user questions.
     - Strict 2-decline exit rule: wrap up warmly and turn off bot after 2 declined actions.
   - Do not bloat or rewrite the system prompt without verifying token budget (~25 tokens/sec audio accumulation).
4. **Tool Definitions**:
   - Backend LLM tools in [`worker.py`](file:///y:/roxstar/sts_lab/worker.py) use `@llm.function_tool`.
   - Tool execution must remain **silent** from the user's perspective (never announce or narrate function calls aloud).
5. **Clean Bot Shutdown**:
   - When transferring to duet or solo recording, or when exiting after repeated declines, the bot must detach session input audio, close the session, and shut down the job context so the user owns the microphone.

---

## 4. Verification & Testing Requirements

Every backend or state modification **must** be verified before completing the task:

```bash
# 1. Run Python unit & scenario test suite (21 scenarios)
py -m pytest tests/ -v

# 2. Verify Frontend build
npm --prefix web run build
```

- **Rule**: Never mark a task as completed or tell the user tests pass unless they were executed and reported 0 failures.
- When adding new state transitions, add a corresponding test scenario in [`tests/test_sts_onboarding_scenarios.py`](file:///y:/roxstar/sts_lab/tests/test_sts_onboarding_scenarios.py).

---

## 5. Security & Sensitive Information

- **Secrets Management**: LiveKit keys (`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`), Gemini keys (`GEMINI_API_KEY`), and server URLs are loaded from `.env` via `config.py`.
- **Never Commit Secrets**: Do not log, print, hardcode, or write secrets into Markdown, code, or test files.
- **Safe Template**: If new environment variables are added, update [`.env.example`](file:///y:/roxstar/sts_lab/.env.example) with placeholder values only.

---

## 6. Documentation Maintenance

Whenever substantial architectural changes, new dependencies, or new tools are introduced:
1. Update [`docs/PROJECT_CONTEXT.md`](file:///y:/roxstar/sts_lab/docs/PROJECT_CONTEXT.md) with architectural adjustments.
2. Update [`docs/TASKS.md`](file:///y:/roxstar/sts_lab/docs/TASKS.md) to reflect completed, ongoing, and pending work.
3. Add a dated entry to [`docs/CHANGELOG.md`](file:///y:/roxstar/sts_lab/docs/CHANGELOG.md).

