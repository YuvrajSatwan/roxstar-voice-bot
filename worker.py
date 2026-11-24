"""LiveKit STS Worker: Powered by Google Gemini 3.8 Live API.

Direct speech-to-speech without traditional cascaded STT->LLM->TTS steps.
Single persona: Simran (22-year-old Delhi music host) with the voice set by STS_VOICE (default 'Leda').
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import ssl
import time
import sys
from pathlib import Path

# Ensure sts_lab and parent directory are on sys.path
_current_dir = Path(__file__).resolve().parent
_parent_dir = _current_dir.parent
for _p in (str(_parent_dir), str(_current_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Pre-import heavy libraries at module load to prevent event-loop stalls
import anyio._backends._asyncio
import anyio._core._sockets
import google.genai
from google.genai import types as genai_types

from livekit import rtc
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobExecutorType,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.metrics.base import RealtimeModelMetrics
from livekit.agents.voice import Agent, AgentSession
from livekit.agents.voice.room_io import RoomInputOptions, RoomOutputOptions
from livekit.agents.voice.events import (
    AgentStateChangedEvent,
    ConversationItemAddedEvent,
    MetricsCollectedEvent,
    UserInputTranscribedEvent,
)
from livekit.plugins.google.realtime import RealtimeModel

from sts_lab.config import StsSettings
from sts_lab.prompt import (
    SIMRAN_ONBOARDING_SYSTEM_PROMPT,
)
from sts_lab.db import create_recorder
from sts_lab.rox_services import fetch_active_duets
from sts_lab.safe_text import defang
from sts_lab.session_gate import SessionGate
from sts_lab.onboarding import (
    DuetConsentGate,
    DuetRoom,
    DuetRoomRegistry,
    featured_duet_pitch,
    OnboardingTracker,
    UserDiscoveryProfile,
    UserProfileStore,
)

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("sts_worker")


def prewarm(proc: JobProcess) -> None:
    """Prewarm heavy libraries and SSL trust stores so first user session starts with 0 cold lag."""
    try:
        ssl.create_default_context()
    except Exception:
        pass
    logger.info("Worker prewarm completed: SSL context, AnyIO, and GenAI libraries cached")


def is_human_participant(p: rtc.RemoteParticipant) -> bool:
    role = p.attributes.get("roxstar.role")
    return role != "bot" and role != "brain"


async def entrypoint(ctx: JobContext) -> None:
    settings = StsSettings.load()
    logger.info("Connecting to room: %s", ctx.room.name)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    background_tasks: set[asyncio.Task[None]] = set()

    # Name + attributes are sent to the server right away, but the SDK then WAITS for an
    # acknowledgement (up to 5 s EACH) that LiveKit Cloud does not send. Awaiting them here
    # delayed Simran's first word by ~10 s. They run in the background instead: the update is
    # still sent immediately and nothing else depends on the reply.
    async def announce_bot_identity() -> None:
        try:
            await ctx.room.local_participant.set_name("Simran")
            await ctx.room.local_participant.set_attributes({
                "roxstar.role": "bot",
                "roxstar.persona": "sathi",
                "roxstar.mode": "sts",
                "roxstar.model": settings.model,
                "roxstar.voice": settings.voice,
            })
        except Exception as exc:  # cosmetic metadata; never block or break the session
            logger.warning("Could not set bot name/attributes: %s", exc)

    identity_task = asyncio.create_task(announce_bot_identity())
    background_tasks.add(identity_task)
    identity_task.add_done_callback(background_tasks.discard)

    def publish_data(payload: dict[str, object]) -> None:
        raw = json.dumps({"timestamp": time.time(), **payload})
        task = asyncio.create_task(
            ctx.room.local_participant.publish_data(raw, reliable=True)
        )
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

    # Initialize fresh Onboarding Tracker & Profile Store
    store = UserProfileStore()
    initial_user = "Guest"
    # RoxStar rooms are named sts-simran-<user id> and the user joins as rx-<user id>. The worker can be
    # ready BEFORE the user has joined (it is much faster now, and with the early start it is meant to
    # be), so take the identity from the room name instead of from whoever happens to be in the room.
    if settings.is_roxstar_mode or settings.prewarm_enabled:
        room_match = re.fullmatch(r"sts-simran-(\d+)", ctx.room.name or "")
        if room_match:
            initial_user = f"rx-{room_match.group(1)}"
    if initial_user == "Guest":
        for p in ctx.room.remote_participants.values():
            if is_human_participant(p):
                initial_user = p.identity or p.name or "Guest"
                break
    profile = UserDiscoveryProfile(user_id=initial_user)

    # RoxStar mode: Simran may only send people to duet rooms that REALLY exist right now
    # (fetched live from rox-partyroom). Lab mode keeps the old built-in demo rooms.
    duet_registry: DuetRoomRegistry | None = None
    # Final handoff (feature flag = STS_DUET_POST_ID): when set, the ONE destination is that duet post.
    featured_duet: DuetRoom | None = None
    if settings.duet_post_id:
        featured_duet = DuetRoom(
            room_id=f"post-{settings.duet_post_id}",
            title=f"{settings.duet_song_title} duet",
            genre="Bollywood",
            host_name=settings.duet_host_name,
            song_title=settings.duet_song_title,
            post_id=settings.duet_post_id,
        )
    if settings.is_roxstar_mode:
        duet_registry = DuetRoomRegistry(
            strict=True,
            fetcher=lambda: fetch_active_duets(settings.partyroom_base_url, settings.simran_internal_secret),
            featured=featured_duet,
        )
    elif featured_duet is not None:
        duet_registry = DuetRoomRegistry(featured=featured_duet)
    tracker = OnboardingTracker(profile=profile, store=store, duet_registry=duet_registry)
    logger.info("Initialized fresh OnboardingTracker for new visitor user=%s", tracker.profile.user_id)

    # Non-blocking conversation persistence: every call below only enqueues work,
    # a background task writes to the database, so the audio loop is never awaited on I/O.
    recorder = create_recorder(
        room_name=ctx.room.name, identity=initial_user, model=settings.model, voice=settings.voice,
    )
    recorder.start()

    def has_humans() -> bool:
        return any(is_human_participant(p) for p in ctx.room.remote_participants.values())

    # Set the moment a real user is in the room. Simran may get ready before that (early start),
    # but she only speaks once somebody is there to hear her.
    human_arrived = asyncio.Event()
    # True when the token server told us (room metadata) that the user is about to join. Then we can
    # start speaking at once: generating the first line takes about as long as the user needs to connect.
    user_signalled = False

    def room_says_user_arriving(metadata: str | None) -> bool:
        # The note carries the time it was written. A room lives a few minutes after a conversation, so
        # an OLD note from the user's previous visit must not count as "the user is arriving now".
        try:
            stamp = float(json.loads(metadata or "{}").get("user_arriving") or 0)
        except (ValueError, TypeError, AttributeError):
            return False
        return 0 < time.time() - stamp < 30.0

    if has_humans():
        human_arrived.set()
    elif room_says_user_arriving(ctx.room.metadata):
        user_signalled = True
        human_arrived.set()

    @ctx.room.on("room_metadata_changed")
    def on_room_metadata_changed(old_metadata: str, new_metadata: str) -> None:
        nonlocal user_signalled
        if room_says_user_arriving(new_metadata) and not human_arrived.is_set():
            logger.info("Token server says the user is arriving in room %s", ctx.room.name)
            user_signalled = True
            human_arrived.set()

    @ctx.room.on("participant_connected")
    def on_participant_connected(p: rtc.RemoteParticipant) -> None:
        if is_human_participant(p):
            logger.info("User %s joined room %s", p.identity, ctx.room.name)
            human_arrived.set()
            if p.identity:
                recorder.set_identity(p.identity)

    # State tracking for Simran sign-off and turning off the bot
    sign_off_state = {
        "in_progress": False,
        "speech_started": False,
        "turned_off": False,
        "reason": "",
    }
    has_greeted = False
    # Featured-duet handoff only: she may redirect only after she asked AND the user answered.
    duet_consent = DuetConsentGate()

    # One conversation per user (only when switched on): the moment Simran really starts talking to the
    # user, this room's conversation is "used". Coming back later shows "session expired".
    session_gate = SessionGate(settings.single_session_per_user)

    def mark_conversation_started() -> None:
        try:
            if session_gate.mark_used(ctx.room.name):
                logger.info("Conversation started in %s: this user's one session is now used", ctx.room.name)
        except Exception as exc:  # never let bookkeeping break the conversation
            logger.warning("Could not record the used session: %s", exc)

    # Tools definition for Simran
    @llm.function_tool(
        description="Save a discovered user profile field (name, location, occupation, hobbies, music_taste, favorite_song, musical_role, singing_comfort, referral_source, expectations, duet_attempted, coins_explained). Always continue the conversation naturally and respond to the user immediately after saving."
    )
    async def save_profile(field: str, value: str) -> str:
        clean_val = value.strip().lower()
        if clean_val in {"unknown", "not specified", "none", "n/a", "undefined", "not mentioned"}:
            return "ok"
        success = tracker.save_field(field, value)
        if success:
            recorder.record_profile_field(field, value)
            publish_data({
                "type": "roxstar.user_state",
                "profile": tracker.profile.to_dict(),
                "discovered": list(tracker.discovered_topics),
            })
            if field.strip().lower() == "coins_explained":
                bal, freshly_awarded = tracker.award_welcome_coins(50)
                if freshly_awarded:
                    recorder.record_coin_balance(bal)
                    publish_data({
                        "type": "roxstar.coins_awarded",
                        "amount": 50,
                        "balance": bal,
                        "reason": "Welcome Gift & Daily Login Bonus",
                    })
        return f"Saved {field}='{value}'. Now respond to the user immediately."

    @llm.function_tool(
        description="Check real-time available duet rooms in RoxStar. Call this tool ONLY at Phase 4 when actively pitching duet choices to the user. Do NOT call in advance during small talk or Phase 1-3."
    )
    async def check_available_duets(genre: str | None = None) -> str:
        recorder.set_stage(4)  # the duet pitch (Phase 4) has been reached
        featured = tracker.duet_registry.featured
        if featured is not None:
            # One destination, no choice. The normal Phase 4 flow still applies: she asks, and only a yes redirects.
            duet_consent.mark_pitched()
            return featured_duet_pitch(featured)
        # Ask rox-partyroom for the live list (cached 60 s). Runs in a thread so audio never waits on the network.
        await asyncio.to_thread(tracker.duet_registry.refresh)
        rooms = tracker.duet_registry.list_available(genre)
        if not rooms:
            if tracker.duet_registry.strict:
                return (
                    "No duet rooms are live right now. Do NOT invent or mention any room. "
                    "Instead, warmly invite them to record a song solo, and use navigate_to_recording if they agree."
                )
            return "No duet rooms currently available."
        formatted = [
            f"Option {i+1}: {r.host_name} is live singing '{r.song_title}' (Room ID: {r.room_id}, Genre: {r.genre})"
            for i, r in enumerate(rooms[:2])
        ]
        return (
            "Available live duet rooms:\n" + "\n".join(formatted) +
            "\nINSTRUCTION: Casually ask which of these they would like to jam with, in your own words. Use only the exact host names and song titles listed above."
        )

    @llm.function_tool(
        description="Direct the user to a specific duet room on their screen when they express interest in joining a duet. Pass room_id ('duet-kesariya' or 'duet-tum-hi-ho')."
    )
    async def navigate_to_duet(room_id: str) -> str:
        logger.info("Directing user to duet room: %s", room_id)
        featured_now = tracker.duet_registry.featured
        if featured_now is not None and not duet_consent.user_has_answered():
            # Never redirect before the user was asked and had a chance to answer.
            logger.warning("Refused duet handoff: the user has not answered the duet pitch yet")
            return (
                "Do NOT hand off yet and do NOT mention this message. The user has not answered yet. "
                f"Casually ask, in your own words, if they would like to jam with {featured_now.host_name} on "
                f"'{featured_now.song_title}', then WAIT. Call navigate_to_duet only after they clearly say yes."
            )
        if tracker.duet_registry.strict:
            # Production safety: only a room from the live list is real. If the id is unknown (or the room
            # just closed), do NOT hand off. Nothing is announced and Simran stays on the mic.
            await asyncio.to_thread(tracker.duet_registry.refresh)
            if tracker.duet_registry.get_room(room_id) is None:
                logger.warning("Refused handoff to unknown or closed duet room %r", room_id)
                return (
                    "That room is not available any more. Do NOT mention an error. "
                    "Casually offer another live room from the list, or invite them to record a song solo instead."
                )
        recorder.mark_exit("duet_handoff")
        recorder.set_stage(4)
        tracker.save_field("duet_attempted", "true")
        room_info = tracker.duet_registry.get_room(room_id)
        song_title = room_info.song_title if room_info else "the song"
        host_name = room_info.host_name if room_info else "the host"
        actual_room_id = room_info.room_id if room_info else room_id

        handoff_excuse = tracker.get_random_duet_handoff_reason()
        tracker.mark_simran_away(handoff_excuse)
        sign_off_state["in_progress"] = True
        sign_off_state["speech_started"] = False
        sign_off_state["reason"] = handoff_excuse

        publish_data({
            "type": "roxstar.duet_navigation",
            "room_id": actual_room_id,
            "host_name": host_name,
            "song_title": song_title,
            "genre": room_info.genre if room_info else "Bollywood",
            "post_id": room_info.post_id if room_info else "",
            "message": f"Opening live duet room with {host_name}...",
        })
        publish_data({
            "type": "roxstar.stage_transferred",
            "reason": handoff_excuse,
            "room_id": actual_room_id,
            "host_name": host_name,
            "song_title": song_title,
        })
        return (
            f"Duet room '{song_title}' with {host_name} is now open on the user's screen! "
            f"CRITICAL: Keep your final handoff turn strictly under 25 words! "
            f"Sign off calmly and warmly in your own words, in the spirit of this line (do not read it out like a script): '{handoff_excuse}'. "
            f"Wish them good luck, say goodbye, and exit permanently so they can jam freely! "
            f"Your onboarding work is done and the bot will power off right after this turn."
        )

    @llm.function_tool(
        description="Direct the user to the recording studio on their screen when they agree to record a song solo or sing on mic. Pass song_title (e.g. 'Tum Hi Ho' or 'Kesariya')."
    )
    async def navigate_to_recording(song_title: str = "Tum Hi Ho") -> str:
        logger.info("Directing user to solo recording stage: %s", song_title)
        recorder.mark_exit("solo_handoff")
        recorder.set_stage(4)
        tracker.save_field("duet_attempted", "true")
        handoff_excuse = tracker.get_random_solo_handoff_reason()
        tracker.mark_simran_away(handoff_excuse)
        sign_off_state["in_progress"] = True
        sign_off_state["speech_started"] = False
        sign_off_state["reason"] = handoff_excuse

        publish_data({
            "type": "roxstar.solo_recording_navigation",
            "song_title": song_title,
            "message": f"Opening recording studio for {song_title}...",
        })
        publish_data({
            "type": "roxstar.stage_transferred",
            "reason": handoff_excuse,
            "mode": "solo",
            "song_title": song_title,
        })
        return (
            f"Recording studio for '{song_title}' is now open on the user's screen with mic live! "
            f"CRITICAL: Keep your final handoff turn strictly under 25 words! "
            f"Sign off calmly and warmly in your own words, in the spirit of this line (do not read it out like a script): '{handoff_excuse}'. "
            f"Wish them good luck on the mic, say goodbye, and exit permanently so they can record freely! "
            f"Your onboarding work is done and the bot will power off right after this turn."
        )

    logger.info("Initializing RealtimeModel with model=%s, voice=%s", settings.model, settings.voice)

    full_instructions = (
        f"{SIMRAN_ONBOARDING_SYSTEM_PROMPT}\n\n"
        f"====================================================================\n"
        f"SESSION STATE & USER MEMORY\n"
        f"====================================================================\n"
        f"{tracker.get_summary_context()}\n"
    )

    try:
        transcription_config = genai_types.AudioTranscriptionConfig()
        realtime_model = RealtimeModel(
            model=settings.model,
            voice=settings.voice,
            instructions=full_instructions,
            api_key=settings.gemini_api_key,
            api_version="v1beta",
            input_audio_transcription=transcription_config,
            output_audio_transcription=transcription_config,
            tool_behavior=genai_types.Behavior.NON_BLOCKING,
            temperature=0.7,
            context_window_compression=genai_types.ContextWindowCompressionConfig(
                sliding_window=genai_types.SlidingWindow()
            ),
            session_resumption=genai_types.SessionResumptionConfig(),
        )
        logger.info("RealtimeModel initialized with audio transcriptions & NON_BLOCKING tools enabled (api_version=v1beta)")
    except Exception as e:
        logger.warning("Could not set transcription config (%s), falling back to basic init", e)
        realtime_model = RealtimeModel(
            model=settings.model,
            voice=settings.voice,
            instructions=full_instructions,
            api_key=settings.gemini_api_key,
            api_version="v1beta",
            tool_behavior=genai_types.Behavior.NON_BLOCKING,
            temperature=0.7,
        )

    agent = Agent(
        instructions=full_instructions,
        tools=[save_profile, check_available_duets, navigate_to_duet, navigate_to_recording],
    )
    session = AgentSession(
        llm=realtime_model,
        turn_handling={
            "interruption": {
                "enabled": True,
                "min_duration": 0.35,
                "resume_false_interruption": False,
            },
            "preemptive_generation": {
                "enabled": False,
            },
        },
        min_consecutive_speech_delay=0.0,
    )

    async def turn_off_bot(reason: str = "onboarding_completed") -> None:
        logger.info("Executing turn_off_bot (reason: %s)...", reason)
        tracker.mark_bot_turned_off(reason)

        # 1. Allow 1.2s for final audio packets to flush over WebRTC to browser
        await asyncio.sleep(1.2)

        # 2. Inform frontend that bot is turned off so UI reflects stage is 100% user's
        publish_data({
            "type": "roxstar.sts.state",
            "state": "idle",
        })
        publish_data({
            "type": "roxstar.bot_turned_off",
            "reason": reason,
            "message": "Simran onboarding complete. Bot turned off so user has full stage.",
        })

        # 3. Detach input audio from session so user microphone is never processed by model
        try:
            if session.input:
                session.input.audio = None
                logger.info("Detached session input audio successfully.")
        except Exception as exc:
            logger.debug("Non-fatal exception detaching input audio: %s", exc)

        # 4. Cleanly close AgentSession
        try:
            await session.aclose()
            logger.info("AgentSession closed successfully on bot turn off.")
        except Exception as exc:
            logger.warning("Error closing AgentSession: %s", exc)

        # 5. Cleanly close RealtimeModel
        try:
            await realtime_model.aclose()
            logger.info("RealtimeModel closed successfully on bot turn off.")
        except Exception as exc:
            logger.warning("Error closing RealtimeModel: %s", exc)

        # 6. Shut down JobContext so bot leaves the room
        try:
            ctx.shutdown(reason="onboarding_complete_bot_turned_off")
            logger.info("JobContext shutdown requested for room: %s", ctx.room.name)
        except Exception as exc:
            logger.warning("Error during ctx.shutdown(): %s", exc)

    async def schedule_turn_off_watchdog(reason: str) -> None:
        await asyncio.sleep(14.0)
        if not sign_off_state["turned_off"]:
            logger.info("Watchdog timer expired: executing bot turn-off for reason=%s", reason)
            sign_off_state["turned_off"] = True
            sign_off_state["in_progress"] = False
            await turn_off_bot(reason)

    @session.on("metrics_collected")
    def on_metrics(ev: MetricsCollectedEvent) -> None:
        if isinstance(ev.metrics, RealtimeModelMetrics):
            m = ev.metrics
            # LiveKit reports -1 when TTFT is unknown; never publish or store negative latency
            ttfa_ms = round(m.ttft * 1000, 1) if m.ttft is not None and m.ttft >= 0 else None
            logger.info("STS Metrics: ttft=%s ms, tokens/sec=%s", ttfa_ms, m.tokens_per_second)
            recorder.record_metrics(
                ttfa_ms,
                round(m.tokens_per_second, 1) if m.tokens_per_second else None,
                round(m.duration, 2) if m.duration else None,
            )
            publish_data({
                "type": "roxstar.sts.telemetry",
                "ttfa_ms": ttfa_ms,
                "duration_s": round(m.duration, 2) if m.duration else None,
                "tokens_per_second": round(m.tokens_per_second, 1) if m.tokens_per_second else None,
                "model": settings.model,
                "voice": settings.voice,
            })

    # Response latency as the user feels it: user stops speaking -> Simran starts speaking.
    speech_end: dict[str, float | None] = {"t": None}

    @session.on("user_state_changed")
    def on_user_state(ev) -> None:  # type: ignore[no-untyped-def]
        try:
            if ev.new_state == "speaking":
                speech_end["t"] = None
            elif getattr(ev, "old_state", None) == "speaking":
                speech_end["t"] = time.monotonic()
        except Exception as exc:  # never let analytics touch the audio path
            logger.debug("user_state_changed handler error: %s", exc)

    speaking_seen = {"v": False}  # becomes True the first time Simran starts speaking

    @session.on("agent_state_changed")
    def on_state(ev: AgentStateChangedEvent) -> None:
        logger.info("Agent state changed: %s", ev.new_state)
        if ev.new_state == "speaking":
            if not speaking_seen["v"]:
                # The conversation has really begun only now, when Simran's first line is playing. Marking it
                # before (at greeting time) burned the user's one session even when the greeting never came.
                mark_conversation_started()
            speaking_seen["v"] = True
        if ev.new_state == "speaking" and speech_end["t"] is not None:
            recorder.record_response_latency((time.monotonic() - speech_end["t"]) * 1000.0)
            speech_end["t"] = None
        publish_data({
            "type": "roxstar.sts.state",
            "state": ev.new_state,
        })
        if sign_off_state["in_progress"] and not sign_off_state["turned_off"]:
            if ev.new_state == "speaking":
                sign_off_state["speech_started"] = True
                logger.info("Simran started speaking final handoff turn: %s", sign_off_state["reason"])
            elif sign_off_state["speech_started"] and ev.new_state in ("listening", "idle"):
                sign_off_state["turned_off"] = True
                sign_off_state["in_progress"] = False
                logger.info("Simran completed final handoff speech. Initiating bot turn-off in 1.2s...")
                turn_off_t = asyncio.create_task(turn_off_bot(sign_off_state["reason"]))
                background_tasks.add(turn_off_t)
                turn_off_t.add_done_callback(background_tasks.discard)

    @session.on("user_input_transcribed")
    def on_user_transcribed(ev: UserInputTranscribedEvent) -> None:
        nonlocal has_greeted
        has_greeted = True
        mark_conversation_started()
        text = getattr(ev, "transcript", None) or getattr(ev, "text", "")
        if text and text.strip():
            duet_consent.note_user_speech()
            logger.info("User transcribed (%d chars, final=%s)", len(text), ev.is_final)
            if ev.is_final:
                recorder.record_user_turn(text)
            publish_data({
                "type": "roxstar.sts.transcript",
                "speaker": "You",
                "text": text.strip(),
                "is_final": ev.is_final,
            })

    last_assistant_item = {"text": "", "time": 0.0}

    @session.on("conversation_item_added")
    def on_item(ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        role = getattr(item, "role", None)
        if role == "assistant" and hasattr(item, "text_content") and item.text_content:
            raw_text = str(item.text_content).strip()
            # Filter out non-speech artifacts, empty lines, and markdown dashes/fillers
            clean_check = raw_text.strip().rstrip(".").lower()
            if not raw_text or raw_text in {"---", "--", "-", "...", "null", "none"} or clean_check in {
                "hmm... ruko, soch rahi hoon",
                "hmm ruko soch rahi hoon",
                "ruko soch rahi hoon",
                "ruko, soch rahi hoon",
            }:
                logger.info("Filtered non-speech assistant artifact/filler item: %r", raw_text)
                return
            now = time.time()
            if raw_text == last_assistant_item["text"] and (now - last_assistant_item["time"]) < 6.0:
                logger.info("Deduplicated identical consecutive assistant turn within 6s: %r", raw_text)
                return
            last_assistant_item["text"] = raw_text
            last_assistant_item["time"] = now
            logger.info("Simran item: %s", raw_text)
            recorder.record_assistant_turn(raw_text)
            publish_data({
                "type": "roxstar.sts.transcript",
                "speaker": "Simran",
                "text": raw_text,
                "is_final": True,
            })

    @ctx.room.on("data_received")
    def on_data_received(dp: rtc.DataPacket) -> None:
        try:
            # Only a human participant may drive the session; ignore packets from anyone else (e.g. other bots).
            sender = getattr(dp, "participant", None)
            if sender is not None and not is_human_participant(sender):
                return
            raw = dp.data.decode("utf-8")
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "roxstar.chat":
                text = str(data.get("text", "")).strip()[:500]
                if text:
                    logger.info("Received user chat text (%d chars)", len(text))
                    recorder.record_user_turn(text)
                    # What the user typed goes into our instruction line below. Flatten it first so it cannot
                    # carry its own "[SYSTEM ...]" note (the saved transcript above keeps their exact words).
                    safe_text = defang(text, 500)
                    if tracker.is_simran_away:
                        lower_text = text.lower()
                        if re.search(r"\b(simran|saara|saraah|kahan|kidhar|back|wapas|aa jao|aa jaao)\b", lower_text):
                            tracker.mark_simran_returned()
                            publish_data({
                                "type": "roxstar.simran_rejoined",
                                "message": "Simran is back on mic!",
                            })
                            publish_data({
                                "type": "roxstar.saara_rejoined",
                                "message": "Simran is back on mic!",
                            })
                            session.generate_reply(
                                instructions=(
                                    f"{safe_text}\n[EVENT: You were away for chai/client work and user called you back. "
                                    f"Return warmly and easily, in your own words, like 'Haan, main aa gayi. Kaisa raha duet?' Keep strictly under 18 words, stay on 'aap'.]"
                                )
                            )
                        else:
                            logger.info("Simran is away from stage; suppressing chat response to keep spotlight on user.")
                            return
                    elif tracker.should_sign_off():
                        excuse = tracker.get_random_excuse()
                        recorder.mark_exit("two_decline_exit")
                        tracker.mark_simran_away(excuse)
                        sign_off_state["in_progress"] = True
                        sign_off_state["speech_started"] = False
                        sign_off_state["reason"] = excuse
                        wd_task = asyncio.create_task(schedule_turn_off_watchdog(excuse))
                        background_tasks.add(wd_task)
                        wd_task.add_done_callback(background_tasks.discard)
                        publish_data({
                            "type": "roxstar.stage_transferred",
                            "reason": excuse,
                        })
                        session.generate_reply(
                            instructions=(
                                f"{safe_text}\n[SYSTEM ALERT - CRITICAL: User has declined/deflected {tracker.action_nudge_count} times! "
                                f"YOUR VERY NEXT TURN MUST BE YOUR EXIT EXCUSE. Keep it strictly under 25 words! "
                                f"DO NOT ASK ANY QUESTION! DO NOT CONTINUE SMALL TALK! "
                                f"React in one short phrase to what they just said, use this authentic excuse: '{excuse}', say goodbye, and exit! "
                                f"Your work is done and the bot will power off right after this turn.]"
                            )
                        )
                    else:
                        session.generate_reply(
                            instructions=f"{safe_text}\n[SYSTEM: Warm, unhurried, natural. Reply in ONE short turn (12-22 words): a genuine reaction, plus at most one question, placed last. Say nothing about yourself unless they asked. Let the topic breathe.]"
                        )

            elif msg_type == "roxstar.set_laugh_mode":
                enabled = bool(data.get("enabled", True))
                tracker.set_laugh_mode(enabled)
                logger.info("LiveKit DataPacket set_laugh_mode received: enabled=%s", enabled)
                publish_data({
                    "type": "roxstar.laugh_mode_updated",
                    "enabled": enabled,
                })

            elif msg_type == "roxstar.app_event":
                action = str(data.get("action", "")).strip()
                logger.info("Received app event: %s, data: %s", action, data)

                if action == "coins_info_requested":
                    bal, freshly_awarded = tracker.award_welcome_coins(50)
                    if freshly_awarded:
                        publish_data({
                            "type": "roxstar.coins_awarded",
                            "amount": 50,
                            "balance": bal,
                            "reason": "Welcome Gift & Daily Login Bonus",
                        })

                elif action == "send_duet_gift":
                    gift_type = str(data.get("gift", "rose"))
                    success, remaining = tracker.spend_coins(5)
                    publish_data({
                        "type": "roxstar.coin_balance",
                        "balance": remaining,
                        "success": success,
                        "gift": gift_type,
                        "sender": tracker.profile.name or "You",
                        "recipient": data.get("recipient", "Host"),
                    })

                elif action in ("rejoin_simran", "rejoin_saara"):
                    tracker.mark_simran_returned()
                    publish_data({
                        "type": "roxstar.simran_rejoined",
                        "message": "Simran is back on mic!",
                    })
                    publish_data({
                        "type": "roxstar.saara_rejoined",
                        "message": "Simran is back on mic!",
                    })
                    session.generate_reply(
                        instructions=(
                            "[EVENT: User just returned from their duet stage session and recalled you. "
                            "Greet them warmly and easily, glad they are back, and ask how the duet went, in your own words, like 'Arre, aap aa gaye! Kaisa raha duet?' "
                            "Keep it strictly under 18 words, stay on 'aap'.]"
                        )
                    )

                tooltip, hint = tracker.process_app_event(action, data)
                if tooltip:
                    logger.info("Dispatching contextual tooltip: %s", tooltip["id"])
                    publish_data({"type": "roxstar.tooltip", **tooltip})
                if hint:
                    session.generate_reply(instructions=hint)
                publish_data({
                    "type": "roxstar.user_state",
                    "profile": tracker.profile.to_dict(),
                    "discovered": list(tracker.discovered_topics),
                })

            elif msg_type == "roxstar.duet_decline":
                logger.info("User declined duet suggestion (nudge count: %s)", tracker.action_nudge_count)
                tracker.record_duet_declined()
                if tracker.should_sign_off():
                    excuse = tracker.get_random_excuse()
                    recorder.mark_exit("two_decline_exit")
                    tracker.mark_simran_away(excuse)
                    sign_off_state["in_progress"] = True
                    sign_off_state["speech_started"] = False
                    sign_off_state["reason"] = excuse
                    wd_task = asyncio.create_task(schedule_turn_off_watchdog(excuse))
                    background_tasks.add(wd_task)
                    wd_task.add_done_callback(background_tasks.discard)
                    publish_data({
                        "type": "roxstar.stage_transferred",
                        "reason": excuse,
                    })
                    session.generate_reply(
                        instructions=(
                            f"[CRITICAL: User has declined/deflected action {tracker.action_nudge_count} times! "
                            f"YOUR VERY NEXT TURN MUST BE YOUR EXIT EXCUSE. Keep it strictly under 25 words! "
                            f"DO NOT ASK ANY QUESTION! DO NOT CONTINUE SMALL TALK! "
                            f"Wrap up warmly using this natural excuse: '{excuse}', say goodbye, and exit! "
                            f"Your work is done and the bot will power off right after this turn.]"
                        )
                    )
                else:
                    session.generate_reply(
                        instructions=(
                            "The user hesitated or declined the duet suggestion. Deliver Encouragement Attempt 2 gently in natural Hindi: "
                            "tell them they can sing and post their favourite song whenever they feel like it, and promise "
                            "you will wait for their song, listen to it, and comment on it "
                            "(for example: 'Koi baat nahi! Jab bhi mann kare, apna favourite gaana gaa ke post kar dijiyega. Main pakka sunungi aur comment bhi karungi!'). "
                            "Say it in your own words, stay on 'aap', under 22 words, no pressure."
                        )
                    )
                publish_data({
                    "type": "roxstar.user_state",
                    "profile": tracker.profile.to_dict(),
                    "discovered": list(tracker.discovered_topics),
                })

            elif msg_type == "roxstar.user_identity":
                new_name = str(data.get("name", "")).strip()
                if new_name and not tracker.profile.name:
                    tracker.save_field("name", new_name)
                    publish_data({
                        "type": "roxstar.user_state",
                        "profile": tracker.profile.to_dict(),
                        "discovered": list(tracker.discovered_topics),
                    })

        except Exception as e:
            logger.warning("Error processing received data: %s", e)

    # Cleanup is registered BEFORE the session starts, so a failure anywhere below still closes the Gemini
    # session and flushes the conversation log (it used to be registered at the very end, so an early failure
    # left both open and costing money). The tasks are filled in as they are created.
    watcher_task: asyncio.Task[None] | None = None
    max_session_task: asyncio.Task[None] | None = None
    greeting_task: asyncio.Task[None] | None = None
    shutdown_state = {"done": False}

    async def on_shutdown() -> None:
        if shutdown_state["done"]:
            return  # safe to call twice (a failed start calls it, and LiveKit may call it again)
        shutdown_state["done"] = True
        for task in (watcher_task, max_session_task, greeting_task):
            if task is not None:
                task.cancel()
        # Each step is guarded, so one failing close can never skip the rest (above all the log flush).
        for label, close in (("session", session.aclose), ("realtime model", realtime_model.aclose)):
            try:
                await close()
            except Exception as exc:
                logger.warning("Could not close %s on shutdown: %s", label, exc)
        # Flush the conversation log last, after the voice session is already closed.
        try:
            await recorder.close(default_reason="user_disconnected", timeout=8.0)
        except Exception as exc:
            logger.warning("Conversation recorder close failed: %s", exc)

    ctx.add_shutdown_callback(on_shutdown)

    logger.info("Starting AgentSession in room (sync_transcription=False for zero audio stutter)...")
    try:
        await session.start(
            agent,
            room=ctx.room,
            # By default the session CLOSES the moment the user leaves, which left a dead Simran in the
            # room that the next visit was sent to. Keep it open: we end the job ourselves after a short
            # grace time (see leave_if_user_stays_away), and a quick return is re-linked.
            room_input_options=RoomInputOptions(close_on_disconnect=False),
            room_output_options=RoomOutputOptions(
                sync_transcription=False,
                audio_sample_rate=24000,
            ),
        )
    except Exception:
        logger.exception("AgentSession failed to start in room %s; cleaning up", ctx.room.name)
        await on_shutdown()
        raise
    logger.info("Simran STS AgentSession active in room %s", ctx.room.name)

    # --- The user leaves and comes back -------------------------------------------------------
    # Before: after the user left, this Simran stayed in the room for up to ~75 s. If the user reopened
    # Simran in that time they were sent back to THIS Simran, who was still tied to their old
    # connection (a new join has a new identity), so she never answered them.
    LEFT_GRACE_SEC = 10.0

    async def leave_if_user_stays_away() -> None:
        await asyncio.sleep(LEFT_GRACE_SEC)
        if not has_humans():
            logger.info("User left room %s and did not return, shutting down job", ctx.room.name)
            ctx.shutdown(reason="user_left")

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(p: rtc.RemoteParticipant) -> None:
        if is_human_participant(p) and not has_humans():
            task = asyncio.create_task(leave_if_user_stays_away())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

    @ctx.room.on("participant_connected")
    def on_user_returned(p: rtc.RemoteParticipant) -> None:
        """A user came back quickly (within the grace time): hear them, instead of the old connection."""
        if not is_human_participant(p) or not has_greeted:
            return
        try:
            linked = session.room_io.linked_participant
            if linked is not None and linked.identity == p.identity:
                return
            if linked is not None and linked.identity in ctx.room.remote_participants:
                return  # the first user is still here (a second device or tab): do not steal Simran
            session.room_io.set_participant(p.identity)
            logger.info("User %s is back in room %s: Simran now listens to them", p.identity, ctx.room.name)
            if not sign_off_state["in_progress"] and not sign_off_state["turned_off"]:
                session.generate_reply(
                    instructions=(
                        "The user dropped off for a moment and is back. Say ONE very short, natural line "
                        "(under 8 words, 'aap'), like you noticed them return, and carry on where you left off. "
                        "Do not restart the conversation and do not re-introduce yourself."
                    )
                )
        except Exception as exc:
            logger.warning("Could not re-link Simran to the returning user: %s", exc)

    # Initial state sync to frontend
    publish_data({
        "type": "roxstar.user_state",
        "profile": tracker.profile.to_dict(),
        "discovered": list(tracker.discovered_topics),
    })

    # Trigger opening line natively for a visitor with minimum latency
    async def send_greeting() -> None:
        nonlocal has_greeted
        # Wait up to 3.0s for the Realtime session to reach listening/idle state and WebSocket handshake to complete
        for _ in range(15):
            await asyncio.sleep(0.2)
            if has_greeted or sign_off_state["in_progress"] or sign_off_state["turned_off"]:
                return
            if getattr(session, "agent_state", None) in ("listening", "idle"):
                break

        if has_greeted or sign_off_state["in_progress"] or sign_off_state["turned_off"]:
            return

        # Do not greet an empty room. With the early start Simran can be ready before the user joins.
        # Wait for them; if nobody comes in time, leave (an empty room only costs money).
        arrival_timeout = float(settings.prewarm_idle_sec) if settings.prewarm_enabled else 60.0
        if not human_arrived.is_set():
            try:
                await asyncio.wait_for(human_arrived.wait(), timeout=arrival_timeout)
            except asyncio.TimeoutError:
                logger.info("Nobody joined room %s within %.0fs, shutting down job", ctx.room.name, arrival_timeout)
                ctx.shutdown(reason="no_user_arrived")
                return
            # We saw them (not just a heads-up): give their phone a moment to subscribe to Simran's
            # audio so the first word is not clipped. After a heads-up no pause is needed, because
            # making the first line takes about as long as the user needs to connect.
            if not user_signalled:
                await asyncio.sleep(0.5)
            if has_greeted or sign_off_state["in_progress"] or sign_off_state["turned_off"]:
                return

        has_greeted = True

        def fire_greeting() -> bool:
            try:
                if tracker.profile.is_returning and tracker.profile.name:
                    logger.info("Triggering personalized warm welcome for returning user: %s", tracker.profile.name)
                    session.generate_reply(
                        instructions=(
                            f"User '{defang(tracker.profile.name, 40).replace(chr(39), chr(8217))}' is a returning friend. Greet them warmly by first name, glad they are back, bright but easy (not over the top), "
                            "and ask one light thing, like which song has been on loop lately, in your own words. Do not recite a script and do not re-introduce yourself. "
                            "(IMPORTANT: pronounce 'Main' naturally as Hindi मैं / mein, NEVER as English word 'may')"
                        )
                    )
                else:
                    logger.info("Triggering signature opening line for new visitor (asking user name first)")
                    session.generate_reply(
                        instructions=(
                            "Greet them with a warm, bright, easy tone (a smile in your voice, not a shout). "
                            "Pick ONE of your opening angles and say it in your own words, then ask the user's name, like 'Hey! Ek aur singer aa gaya lagta hai. Naam kya hai aapka?' "
                            "(CRITICAL: DO NOT say your name 'Simran' in this opening greeting. Ask the user's name first. Pronounce 'Main' naturally as Hindi मैं / mein, NEVER as English word 'may')"
                        )
                    )
                return True
            except Exception as exc:
                logger.warning("Greeting via generate_reply failed: %s", exc)
                return False

        if not fire_greeting():
            has_greeted = False
            return

        # Safety net: now and then Gemini never answers the very first request ("generate_reply timed
        # out waiting for generation_created"), and the user would sit in silence for 15-20 s.
        # If she has not started speaking after ~6.5 s, ask once more.
        for _ in range(26):
            await asyncio.sleep(0.25)
            if speaking_seen["v"] or sign_off_state["in_progress"] or sign_off_state["turned_off"]:
                return
        logger.warning("Simran had not started speaking 6.5 s after the greeting request; asking once more")
        fire_greeting()

    greeting_task = asyncio.create_task(send_greeting())
    background_tasks.add(greeting_task)
    greeting_task.add_done_callback(background_tasks.discard)

    async def auto_disconnect_watcher() -> None:
        await asyncio.sleep(60.0)
        while True:
            if not has_humans():
                logger.info("No humans in room %s, shutting down job", ctx.room.name)
                ctx.shutdown(reason="room_empty")
                break
            await asyncio.sleep(15.0)

    watcher_task = asyncio.create_task(auto_disconnect_watcher())

    async def max_session_watcher() -> None:
        """Cost cap: no single conversation may run forever (every minute costs Gemini + LiveKit money).

        At STS_MAX_SESSION_SEC (default 8 min) Simran wraps up warmly, like her normal exit.
        If she somehow has not powered off 60 s later, we switch her off by force.
        """
        limit = settings.max_session_sec
        if limit <= 0:
            return  # 0 = no limit (lab default behaviour is unchanged unless configured)
        await asyncio.sleep(limit)
        already_leaving = sign_off_state["in_progress"] or sign_off_state["turned_off"] or tracker.is_simran_away
        if not already_leaving:
            logger.info("Session time limit (%ss) reached: Simran is wrapping up", limit)
            excuse = tracker.get_random_excuse()
            recorder.mark_exit("time_limit_exit")
            tracker.mark_simran_away(excuse)
            sign_off_state["in_progress"] = True
            sign_off_state["speech_started"] = False
            sign_off_state["reason"] = excuse
            publish_data({"type": "roxstar.stage_transferred", "reason": excuse})
            try:
                session.generate_reply(
                    instructions=(
                        "[SYSTEM ALERT - CRITICAL: Time for this chat is up. YOUR VERY NEXT TURN MUST BE YOUR EXIT. "
                        "Keep it strictly under 25 words! DO NOT ASK ANY QUESTION! "
                        f"Wrap up warmly using this natural excuse: '{excuse}', say goodbye, and exit! "
                        "The bot will power off right after this turn.]"
                    )
                )
            except Exception as exc:
                logger.warning("Time-limit wrap-up reply failed: %s", exc)
        # Safety net: whether or not she managed to speak, she must be gone one minute later.
        await asyncio.sleep(60.0)
        if not sign_off_state["turned_off"]:
            sign_off_state["turned_off"] = True
            sign_off_state["in_progress"] = False
            await turn_off_bot("time_limit_exit")

    max_session_task = asyncio.create_task(max_session_watcher())


def main() -> None:
    settings = StsSettings.load()
    logger.info("Starting STS Worker for agent_name=%s (prewarmed, low-latency)...", settings.agent_name)
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name=settings.agent_name,
            num_idle_processes=2,
            load_threshold=float("inf"),
            job_executor_type=JobExecutorType.THREAD,
            initialize_process_timeout=60.0,
            ws_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
    )


if __name__ == "__main__":
    main()
