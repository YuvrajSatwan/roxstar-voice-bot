# ADMIN_DASHBOARD.md — Conversation Persistence & Admin Review

Every Simran call is now stored in a database (users, sessions, turn-by-turn messages with latency), and a password-protected dashboard at `/admin` lets founders and engineers replay calls, read funnel drop-off, and flag turns for prompt fixes.

---

## 1. How it works

```
worker.py (audio loop)                db/ package                          token_server.py (:8001)
  on transcript / metrics / tool ───▶ SessionRecorder (in-memory queue) ─▶ /api/admin/*  ─▶ web /admin
  (O(1), never awaits the DB)         one background task writes in order      │
                                      SQLAlchemy async ─▶ SQLite | PostgreSQL ◀┘
```

* **Zero blocked audio loop.** Every `recorder.record_*()` call only appends to an `asyncio.Queue` and returns. One background task drains the queue and performs the async writes (`aiosqlite` / `asyncpg`). The test `test_rapid_turns_never_block_the_event_loop` pushes 600 turns while a heartbeat checks the loop never stalls.
* **Outage safe.** If the database is down the agent keeps talking. Writes retry with exponential backoff while operations wait in a bounded in-memory queue (5,000). When the queue is full new operations are dropped and counted in the log. On session end the recorder waits up to 8 s, then gives up with a warning.
* **Same persona, same S2S, same DataPackets.** No prompt, tool, or DataPacket was changed. Set `STS_DB_ENABLED=false` to turn logging off completely.

## 2. Setup

```bash
pip install -r requirements.txt          # adds sqlalchemy[asyncio], aiosqlite, asyncpg
```

Add to `.env` (see `.env.example`):

| Variable | Purpose |
| :--- | :--- |
| `DATABASE_URL` | Default: the SQLite file `sts_lab.db` in the project folder. For production: `postgresql://user:pw@host:5432/roxstar_sts` (rewritten to `asyncpg` automatically). |
| `STS_DB_ENABLED` | `true` (default) or `false` to disable logging. |
| `ADMIN_API_KEY` | Optional in development. Empty: the dashboard opens with no key, but only for requests from the same machine (anyone else gets `403`). Set: every request needs `X-Admin-Key`. **Set it before exposing the server.** |

Run as usual (`python run_sts.py`, `npm --prefix web run dev`) and open `http://127.0.0.1:5175/admin`. With no `ADMIN_API_KEY` it opens straight away; with one, enter the key. In the Docker/Render build the same page is served by the token server at `/admin`.

Tables are created automatically on first use (`create_all`). **There is no migration tool yet.** Before the first schema change in production, add Alembic and generate a baseline from `db/models.py`.

## 3. Schema

| Table | Key columns |
| :--- | :--- |
| `users` | `id` (uuid hex), `identity` (unique, LiveKit identity), `name`, `location`, `occupation`, `hobbies` (JSON), `music_taste` (JSON), `favorite_song`, `musical_role`, `singing_comfort`, `referral_source`, `expectations`, `coin_balance`, `is_onboarded`, `created_at`, `updated_at` |
| `sessions` | `id`, `room_name`, `user_id`, `started_at`, `ended_at`, `duration_seconds`, `exit_reason` (`duet_handoff`, `solo_handoff`, `two_decline_exit`, `user_disconnected`, `abandoned`), `final_stage` (1 to 4), `avg_ttft_ms`, `total_turns`, `model`, `voice`, `feedback_rating` (1 to 5), `admin_notes` |
| `messages` | `id`, `session_id`, `turn_index`, `speaker` (`Simran` / `User`), `transcript`, `timestamp`, `ttft_ms`, `tokens_per_second`, `audio_duration_seconds`, `profile_fields_captured` (JSON), `flagged_issue`, `admin_tag`, `flag_note` |

The "funnel analytics" is computed on read (`db/analytics.py`: `funnel()`, `metrics()`) from these tables, so there is nothing to keep in sync. p50/p95 latency come from `messages.ttft_ms`.

**Stage rules** (`db/recorder.py: infer_stage`): Phase 2 once music fields are saved, Phase 3 once `expectations` or `coins_explained` is saved, Phase 4 once the duet pitch tool runs or a handoff happens.

**Exit reasons**: handoff tools set `duet_handoff` / `solo_handoff`; the chat/decline sign-off sets `two_decline_exit`; otherwise the call is `abandoned` (no user turns, or under 15 s) or `user_disconnected`.

## 4. Admin API

If `ADMIN_API_KEY` is set, all requests need header `X-Admin-Key: <ADMIN_API_KEY>`. If it is empty, only requests from this machine are accepted. `GET /api/admin/auth-mode` (no key needed) tells the UI which mode is active.

| Method and path | Purpose |
| :--- | :--- |
| `GET /api/admin/metrics?days=30` | KPIs: total calls, completion (reached Phase 4), duet and solo conversion, 2-decline and abandoned rates, avg duration, TTFT p50/p95, flagged turns, exit reason counts |
| `GET /api/admin/funnel?days=30` | Stage counts with drop-off % and a per-day trend (calls, conversion, TTFT p50/p95) |
| `GET /api/admin/sessions?page&page_size&exit_reason&q&role&date_from&date_to&flagged` | Paginated sessions (`q` searches name, identity, room) |
| `GET /api/admin/sessions/{id}` | Full timeline with per-turn latency, captured fields and flags |
| `GET /api/admin/users?page&city&role&song&q` | Users plus breakdowns (roles, top cities, top songs) |
| `POST /api/admin/messages/{id}/flag` | Body `{"reason": "latency_spike\|hallucination\|persona_break\|missed_turn\|too_long\|interrupted\|other", "flagged": true, "note": "..."}` |
| `POST /api/admin/sessions/{id}/review` | Body `{"notes": "...", "rating": 1-5}` |
| `POST /api/admin/export` | Body `{"format": "csv\|json", "flagged_only": false, ...session filters}`. CSV cells that start with `= + - @` are prefixed with `'` to block spreadsheet formula injection. |

## 5. Dashboard

* **Overview:** six KPI cards, the Phase 1 to 4 funnel with drop-off percentages (red at 30% or more), exit reasons, and a daily trend table.
* **Conversations:** filters, pagination, CSV/JSON export, and a replay drawer with chat bubbles, `⚡ TTFT` badges, pills for fields captured on each turn, a flag menu with reasons, reviewer notes, and a 1 to 5 rating.
* **Users:** city, role and song filters with clickable breakdown lists.
* Light and dark theme toggle. The key is kept in `sessionStorage` (cleared when the tab closes). The admin bundle is code-split, so the user studio is unchanged.

## 6. Tests

```bash
py -m pytest tests/ -v            # includes tests/test_persistence.py (13 tests)
npm --prefix web run build
```

## 6b. How the data is made reliable

* **Profile fields.** The model sometimes skips `save_profile`. The recorder reads which question Simran just asked (city, work, free time, how they found Roxstar, listener or singer, and so on) and, if no tool call arrives within 4 seconds or the call ends, stores the user's short answer. These are shown as `field: value (auto)` and are only as accurate as the transcript. Tool captures show without the label.
* **Funnel phase and exit.** Phase 2, 3 and 4 are inferred from fields and from Simran's own lines; an exit excuse such as "Ritika ka phone..., bye!" is recorded as `two_decline_exit` even though no backend tool ran.
* **Response time.** The dashboard shows the time from the user finishing to Simran starting, measured in `worker.py` from the `user_state_changed` and `agent_state_changed` events. If LiveKit does not emit those events with your setup the column stays empty rather than showing wrong numbers. The provider's own TTFT (negative or a few milliseconds) is discarded.
* **Auto flags.** Lines repeated word for word and "ye bataiye" style lead-ins are flagged automatically, so prompt fixes can be checked in the Flagged filter.
* **Users.** Each browser gets a random visitor id, so the users table separates people who typed the same name. In the real app, pass the Roxstar user id as the identity instead.
* **Repairing old rows:** `py -m sts_lab.db.maintenance` (safe to rerun; it never edits transcripts or profile data).

## 7. Production notes and known limits

0. **User transcripts are approximate.** The text for user turns comes from Gemini's separate input transcription, not from what the model "hears". Simran understands the audio directly, so she can answer correctly even when a stored user line is wrong (typical for Hinglish: wrong words, or Devanagari versus Roman script). `language_codes` hints are not available on the Gemini Developer API (the SDK rejects them), so accuracy cannot be tuned there. For exact text, run a dedicated speech-to-text over saved audio for logging only.

1. **This stores personal data** (voice transcripts, names, cities). Show a consent notice in the app, decide a retention period (for example delete transcripts after 90 days), restrict who has the admin key, and check the DPDP Act position with legal before launch. Set `STS_DB_ENABLED=false` if consent is not in place yet.
2. **`identity` is the typed name today**, so two people called "Rahul" share one `users` row. Switch to the Roxstar user ID when it exists (`token_server.py` sets the identity).
3. **No session resume.** A reconnect creates a new session row.
4. **Exit detection from voice.** The 2-decline exit is only labelled `two_decline_exit` when the backend triggers it (chat or decline event). If the model ends the call on its own from voice, the session is labelled `user_disconnected` or `abandoned`.
5. **Aggregations run in Python** so they work on SQLite and PostgreSQL. This is fine up to tens of thousands of sessions per month; move the rollups to SQL views beyond that.
6. **The legacy `.sts_users.json` store is unchanged** and still does small synchronous writes from `save_profile`. Remove it once the database is the source of truth for returning users (this also fixes the dead returning-user recognition noted in the project review).
7. **CORS** on the token server still reflects any origin. The admin routes are protected by the key, but restrict origins before going public.
