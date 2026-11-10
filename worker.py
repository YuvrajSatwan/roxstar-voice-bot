"""LiveKit STS Worker: Powered by Google Gemini 3.8 Live API.

Direct speech-to-speech without traditional cascaded STT->LLM->TTS steps.
Single persona: Simran (AI Sathi & Tech Consultant) with 'Sulafat' voice.
"""

from __future__ import annotations

import asyncio
import json
import logging
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
from livekit.agents.voice.room_io import RoomOutputOptions
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
    SAARA_ONBOARDING_SYSTEM_PROMPT,
    SARAAH_STS_SYSTEM_PROMPT,
)
from sts_lab.onboarding import (
    DuetRoomRegistry,
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

    await ctx.room.local_participant.set_name("Simran")
    await ctx.room.local_participant.set_attributes({
        "roxstar.role": "bot",
        "roxstar.persona": "sathi",
        "roxstar.mode": "sts",
        "roxstar.model": settings.model,
        "roxstar.voice": settings.voice,
    })

    background_tasks: set[asyncio.Task[None]] = set()

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
    for p in ctx.room.remote_participants.values():
        if is_human_participant(p):
            initial_user = p.identity or p.name or "Guest"
            break
    profile = UserDiscoveryProfile(user_id=initial_user)
    tracker = OnboardingTracker(profile=profile, store=store)
    logger.info("Initialized fresh OnboardingTracker for new visitor user=%s", tracker.profile.user_id)

    # State tracking for Simran sign-off and turning off the bot
    sign_off_state = {
        "in_progress": False,
        "speech_started": False,
        "turned_off": False,
        "reason": "",
    }
    has_greeted = False

    # Tools definition for Simran
    @llm.function_tool(
        description="Silently save a discovered user profile field (name, location, occupation, hobbies, music_taste, expectations, duet_attempted, coins_explained). Never mention this tool aloud."
    )
    async def save_profile(field: str, value: str) -> str:
        clean_val = value.strip().lower()
        if clean_val in {"unknown", "not specified", "none", "n/a", "undefined", "not mentioned"}:
            return '{"status": "ignored"}'
        success = tracker.save_field(field, value)
        if success:
            publish_data({
                "type": "roxstar.user_state",
                "profile": tracker.profile.to_dict(),
                "discovered": list(tracker.discovered_topics),
            })
            if field.strip().lower() == "coins_explained":
                bal, freshly_awarded = tracker.award_welcome_coins(50)
                if freshly_awarded:
                    publish_data({
                        "type": "roxstar.coins_awarded",
                        "amount": 50,
                        "balance": bal,
                        "reason": "Welcome Gift & Daily Login Bonus",
                    })
            return '{"status": "saved"}'
        return '{"status": "unrecognized"}'

    @llm.function_tool(
        description="Check real-time available duet rooms in RoxStar before recommending a duet to the user."
    )
    async def check_available_duets(genre: str | None = None) -> str:
        rooms = tracker.duet_registry.list_available(genre)
        if not rooms:
            return "No duet rooms currently available."
        formatted = [
            f"Option {i+1}: {r.host_name} is live singing '{r.song_title}' (Room ID: {r.room_id}, Genre: {r.genre})"
            for i, r in enumerate(rooms[:2])
        ]
        return (
            "Available famous live duet rooms:\n" + "\n".join(formatted) +
            "\nINSTRUCTION: Ask the user which of these 2 famous songs they want to sing (e.g. Aman singing 'Kesariya' or Rhea singing 'Tum Hi Ho')!"
        )

    @llm.function_tool(
        description="Direct the user to a specific duet room on their screen when they express interest in joining a duet. Pass room_id ('duet-kesariya' or 'duet-tum-hi-ho')."
    )
    async def navigate_to_duet(room_id: str) -> str:
        logger.info("Directing user to duet room: %s", room_id)
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
            f"Sign off warmly using this exact situation handoff reason/excuse: '{handoff_excuse}'. "
            f"Wish them good luck, say goodbye, and exit permanently so they can jam freely! "
            f"Your onboarding work is done and the bot will power off right after this turn."
        )

    @llm.function_tool(
        description="Direct the user to the recording studio on their screen when they agree to record a song solo or sing on mic. Pass song_title (e.g. 'Tum Hi Ho' or 'Kesariya')."
    )
    async def navigate_to_recording(song_title: str = "Tum Hi Ho") -> str:
        logger.info("Directing user to solo recording stage: %s", song_title)
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
            f"Sign off warmly using this exact situation handoff reason/excuse: '{handoff_excuse}'. "
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
            temperature=0.7,
            tool_response_scheduling=genai_types.FunctionResponseScheduling.SILENT,
        )
        logger.info("RealtimeModel initialized with silent tool scheduling & audio transcriptions enabled (api_version=v1beta)")
    except Exception as e:
        logger.warning("Could not set transcription config (%s), falling back to basic init", e)
        realtime_model = RealtimeModel(
            model=settings.model,
            voice=settings.voice,
            instructions=full_instructions,
            api_key=settings.gemini_api_key,
            api_version="v1beta",
            temperature=0.7,
            tool_response_scheduling=genai_types.FunctionResponseScheduling.SILENT,
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
                "min_duration": 0.7,
                "resume_false_interruption": False,
            },
            "preemptive_generation": {
                "enabled": False,
            },
        },
        min_consecutive_speech_delay=0.15,
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
            ttfa_ms = round(m.ttft * 1000, 1) if m.ttft is not None else None
            logger.info("STS Metrics: ttft=%s ms, tokens/sec=%s", ttfa_ms, m.tokens_per_second)
            publish_data({
                "type": "roxstar.sts.telemetry",
                "ttfa_ms": ttfa_ms,
                "duration_s": round(m.duration, 2) if m.duration else None,
                "tokens_per_second": round(m.tokens_per_second, 1) if m.tokens_per_second else None,
                "model": settings.model,
                "voice": settings.voice,
            })

    @session.on("agent_state_changed")
    def on_state(ev: AgentStateChangedEvent) -> None:
        logger.info("Agent state changed: %s", ev.new_state)
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
        text = getattr(ev, "transcript", None) or getattr(ev, "text", "")
        if text and text.strip():
            logger.info("User transcribed: %s (final=%s)", text, ev.is_final)
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
            # Filter out non-speech artifacts, empty lines, and markdown dashes
            if not raw_text or raw_text in {"---", "--", "-", "...", "null", "none"}:
                logger.info("Filtered non-speech assistant artifact item: %r", raw_text)
                return
            now = time.time()
            if raw_text == last_assistant_item["text"] and (now - last_assistant_item["time"]) < 6.0:
                logger.info("Deduplicated identical consecutive assistant turn within 6s: %r", raw_text)
                return
            last_assistant_item["text"] = raw_text
            last_assistant_item["time"] = now
            logger.info("Simran item: %s", raw_text)
            publish_data({
                "type": "roxstar.sts.transcript",
                "speaker": "Simran",
                "text": raw_text,
                "is_final": True,
            })

    @ctx.room.on("data_received")
    def on_data_received(dp: rtc.DataPacket) -> None:
        try:
            raw = dp.data.decode("utf-8")
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "roxstar.chat":
                text = str(data.get("text", "")).strip()
                if text:
                    logger.info("Received user chat text: %s", text)
                    if tracker.is_simran_away:
                        lower_text = text.lower()
                        if "simran" in lower_text or "saara" in lower_text or "saraah" in lower_text or "kahan" in lower_text or "back" in lower_text:
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
                                user_input=(
                                    f"{text}\n[EVENT: You were away for chai/client work and user called you back! "
                                    f"Return enthusiastically: 'Haan haan main aa gayi! Chai pee ke ready! Kaisa raha duet?' Keep strictly under 18 words!]"
                                )
                            )
                        else:
                            logger.info("Simran is away from stage; suppressing chat response to keep spotlight on user.")
                            return
                    elif tracker.should_sign_off():
                        excuse = tracker.get_random_excuse()
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
                            user_input=(
                                f"{text}\n[SYSTEM ALERT - CRITICAL: User has declined/deflected {tracker.action_nudge_count} times! "
                                f"YOUR VERY NEXT TURN MUST BE YOUR EXIT EXCUSE. Keep it strictly under 25 words! "
                                f"DO NOT ASK ANY QUESTION! DO NOT CONTINUE SMALL TALK! "
                                f"React in one short phrase to what they just said, use this authentic excuse: '{excuse}', say goodbye, and exit! "
                                f"Your work is done and the bot will power off right after this turn.]"
                            )
                        )
                    else:
                        session.generate_reply(
                            user_input=f"{text}\n[SYSTEM: Natural, warm, and friendly! Speak with an unhurried, smiling tone. Keep reply in natural conversational sweet spot (12-22 words): 1 genuine reaction + 1 relatable detail or question. Let the topic breathe!]"
                        )

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
                        user_input=(
                            "[EVENT: User just returned from their duet stage session and recalled you! "
                            "React with high excitement and friendly South Delhi warmth: 'Oye! Kaisa raha duet?! Mummy ne mast adrak chai di, ab batao kaisa gaaya tumne!' "
                            "Keep it strictly under 18 words, super cheerful!]"
                        )
                    )

                tooltip, hint = tracker.process_app_event(action, data)
                if tooltip:
                    logger.info("Dispatching contextual tooltip: %s", tooltip["id"])
                    publish_data({"type": "roxstar.tooltip", **tooltip})
                if hint:
                    session.generate_reply(user_input=hint)
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
                        user_input=(
                            f"[CRITICAL: User has declined/deflected action {tracker.action_nudge_count} times! "
                            f"YOUR VERY NEXT TURN MUST BE YOUR EXIT EXCUSE. Keep it strictly under 25 words! "
                            f"DO NOT ASK ANY QUESTION! DO NOT CONTINUE SMALL TALK! "
                            f"Wrap up warmly using this natural excuse: '{excuse}', say goodbye, and exit! "
                            f"Your work is done and the bot will power off right after this turn.]"
                        )
                    )
                else:
                    session.generate_reply(
                        user_input=(
                            "The user hesitated or declined the duet suggestion. Deliver Encouragement Attempt 2 warmly in natural Hindi: "
                            "tell them they can sing and post their favourite song whenever they feel like it, and promise "
                            "you will wait for their song, listen to it, and comment on it "
                            "(e.g. 'Arre koi baat nahi! Jab bhi mann kare na, bas apna favourite gaana gaa kar post kar dena. Main pakka sunungi aur comment bhi karungi!'). "
                            "Keep it under 22 words, warm, natural, and encouraging."
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

    logger.info("Starting AgentSession in room (sync_transcription=False for zero audio stutter)...")
    await session.start(
        agent,
        room=ctx.room,
        room_output_options=RoomOutputOptions(
            sync_transcription=False,
            audio_sample_rate=24000,
        ),
    )
    logger.info("Simran STS AgentSession active in room %s", ctx.room.name)

    # Initial state sync to frontend
    publish_data({
        "type": "roxstar.user_state",
        "profile": tracker.profile.to_dict(),
        "discovered": list(tracker.discovered_topics),
    })

    # Trigger opening line natively for a visitor with minimum latency
    async def send_greeting() -> None:
        nonlocal has_greeted
        await asyncio.sleep(0.08)  # minimal 80ms buffer for initial WebRTC track link
        if has_greeted or sign_off_state["in_progress"] or sign_off_state["turned_off"]:
            return
        has_greeted = True
        try:
            if tracker.profile.is_returning and tracker.profile.name:
                logger.info("Triggering personalized warm welcome for returning user: %s", tracker.profile.name)
                session.generate_reply(
                    user_input=(
                        f"User '{tracker.profile.name}' is a returning friend! Speak with VERY HIGH ENERGY, big enthusiasm, and excitement! "
                        f"Greet them warmly by name: 'Arre {tracker.profile.name}! Wapas aa gaye! Aaj kaunsa gaana loop pe chal raha hai?' "
                        "(IMPORTANT: pronounce 'Main' naturally as Hindi मैं / mein, NEVER as English word 'may')"
                    )
                )
            else:
                logger.info("Triggering signature opening line for new visitor (asking user name first)")
                session.generate_reply(
                    user_input=(
                        "Speak with VERY HIGH ENERGY, big enthusiasm, and a joyful, beaming, excited voice! "
                        "Ask the user's name first without telling your own name yet: "
                        "'Heyy! Ek aur secret singer room mein aa gaya! Naam kya hai aapka?' "
                        "(CRITICAL: DO NOT say your name 'Simran' in this opening greeting. Ask the user's name first. Pronounce 'Main' naturally as Hindi मैं / mein, NEVER as English word 'may')"
                    )
                )
        except Exception as exc:
            logger.warning("Greeting via generate_reply failed: %s", exc)

    greeting_task = asyncio.create_task(send_greeting())
    background_tasks.add(greeting_task)
    greeting_task.add_done_callback(background_tasks.discard)

    def has_humans() -> bool:
        return any(is_human_participant(p) for p in ctx.room.remote_participants.values())

    async def auto_disconnect_watcher() -> None:
        await asyncio.sleep(60.0)
        while True:
            if not has_humans():
                logger.info("No humans in room %s, shutting down job", ctx.room.name)
                ctx.shutdown(reason="room_empty")
                break
            await asyncio.sleep(15.0)

    watcher_task = asyncio.create_task(auto_disconnect_watcher())

    async def on_shutdown() -> None:
        watcher_task.cancel()
        greeting_task.cancel()
        await session.aclose()
        await realtime_model.aclose()

    ctx.add_shutdown_callback(on_shutdown)


def main() -> None:
    settings = StsSettings.load()
    logger.info("Starting STS Worker for agent_name=%s (prewarmed, low-latency)...", settings.agent_name)
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name=settings.agent_name,
            num_idle_processes=1,
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
