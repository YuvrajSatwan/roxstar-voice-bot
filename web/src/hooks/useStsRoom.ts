import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AudioTrack,
  ConnectionState,
  RemoteParticipant,
  RemoteTrack,
  RemoteTrackPublication,
  Room,
  RoomEvent,
  Track,
  createAudioAnalyser,
} from 'livekit-client';
import { requestStsSession, type StsSession } from '../services/tokenService';

export interface StsTelemetry {
  ttfaMs?: number;
  tokensPerSec?: number;
  durationS?: number;
  model?: string;
  voice?: string;
  lastUpdated?: number;
}

export interface TranscriptItem {
  id: string;
  speaker: 'Simran' | 'Saraah' | 'You' | 'System';
  text: string;
  time: string;
  isFinal: boolean;
}

export interface TooltipData {
  id: string;
  title: string;
  message: string;
  target?: string;
}

export interface UserDiscoveryProfile {
  user_id: string;
  name?: string;
  location?: string;
  occupation?: string;
  hobbies: string[];
  music_taste: string[];
  expectations?: string;
  duet_attempted?: boolean;
  coins_explained?: boolean;
  is_returning?: boolean;
}

export interface CoinsAwardedEvent {
  amount: number;
  balance: number;
  reason: string;
}

export type SimranState = 'idle' | 'listening' | 'thinking' | 'speaking';
export type SaraahState = SimranState;

export function useStsRoom() {
  const [session, setSession] = useState<StsSession | null>(null);
  const [connectionState, setConnectionState] = useState<ConnectionState>(ConnectionState.Disconnected);
  const [isMuted, setIsMuted] = useState(false);
  const [simranState, setSimranState] = useState<SimranState>('idle');
  const [telemetry, setTelemetry] = useState<StsTelemetry>({
    model: 'gemini-3.8-live',
    voice: 'Sulafat',
  });
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [activeTooltip, setActiveTooltip] = useState<TooltipData | null>(null);
  const [userProfile, setUserProfile] = useState<UserDiscoveryProfile | null>(null);
  const [discoveredTopics, setDiscoveredTopics] = useState<string[]>([]);
  const [navigatedDuetRoom, setNavigatedDuetRoom] = useState<string | null>(null);
  const [navigatedSoloRecording, setNavigatedSoloRecording] = useState<string | null>(null);

  // Pillar 2 & 3: Simran stage handover and coins reward states
  const [isSimranAway, setIsSimranAway] = useState(false);
  const [simranAwayReason, setSimranAwayReason] = useState<string | null>(null);
  const [coinBalance, setCoinBalance] = useState(0);
  const [coinsAwardedEvent, setCoinsAwardedEvent] = useState<CoinsAwardedEvent | null>(null);
  const [laughEnabled, setLaughEnabled] = useState<boolean>(() => {
    try {
      const saved = localStorage.getItem('roxstar_laugh_enabled');
      if (saved !== null) return saved === 'true';
    } catch {}
    return true;
  });

  const roomRef = useRef<Room | null>(null);
  const analyserCleanupRef = useRef<(() => Promise<void>) | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const hasTriggeredVoiceCoinsRef = useRef(false);

  const isConnected = connectionState === ConnectionState.Connected;
  const isConnecting = connectionState === ConnectionState.Connecting;

  // Cleanup room and audio listeners
  const cleanup = useCallback(async () => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (analyserCleanupRef.current) {
      try {
        await analyserCleanupRef.current();
      } catch {}
      analyserCleanupRef.current = null;
    }
    if (roomRef.current) {
      // Detach any attached audio elements to prevent memory leaks and duplicate playback
      roomRef.current.remoteParticipants.forEach((p) => {
        p.audioTrackPublications.forEach((pub) => {
          pub.track?.detach();
        });
      });
      await roomRef.current.disconnect();
      roomRef.current = null;
    }
    setConnectionState(ConnectionState.Disconnected);
    setSimranState('idle');
    setAudioLevel(0);
    setIsSimranAway(false);
    setSimranAwayReason(null);
    setCoinsAwardedEvent(null);
    hasTriggeredVoiceCoinsRef.current = false;
    setNavigatedDuetRoom(null);
    setNavigatedSoloRecording(null);
  }, []);

  const connect = useCallback(
    async (userName: string, targetRoom?: string) => {
      setError(null);
      await cleanup();

      try {
        setConnectionState(ConnectionState.Connecting);
        const sess = await requestStsSession(userName, targetRoom);
        setSession(sess);

        const room = new Room({
          adaptiveStream: true,
          dynacast: true,
          audioCaptureDefaults: {
            autoGainControl: true,
            echoCancellation: true,
            noiseSuppression: true,
          },
        });
        roomRef.current = room;

        // Monitor connection state
        room.on(RoomEvent.ConnectionStateChanged, (state) => {
          setConnectionState(state);
          if (state === ConnectionState.Connected) {
            setSimranState('listening');
          }
        });

        // Handle Audio Tracks (Simran's speech)
        room.on(
          RoomEvent.TrackSubscribed,
          (track: RemoteTrack, _publication: RemoteTrackPublication, _participant: RemoteParticipant) => {
            if (track.kind === Track.Kind.Audio) {
              track.detach(); // Detach any existing audio elements to prevent duplicate/echo playback
              const el = track.attach();
              el.autoplay = true;

              try {
                // Use LiveKit's official createAudioAnalyser with cloneTrack=true so it NEVER interferes with the WebRTC playback stream
                const { calculateVolume, cleanup: analyserCleanup } = createAudioAnalyser(track as AudioTrack, {
                  cloneTrack: true,
                  fftSize: 64,
                  smoothingTimeConstant: 0.8,
                });
                analyserCleanupRef.current = analyserCleanup;

                let lastUpdate = 0;
                let prevLevel = 0;
                const updateMeter = (now: number) => {
                  const vol = calculateVolume();
                  // Throttle React state updates to at most once per 45ms (~22fps)
                  // and ignore insignificant jitter to prevent 120fps React render thrashing
                  if (now - lastUpdate > 45) {
                    lastUpdate = now;
                    if (Math.abs(vol - prevLevel) > 0.02 || (vol < 0.01 && prevLevel >= 0.01)) {
                      prevLevel = vol;
                      setAudioLevel(vol);
                    }
                  }
                  animFrameRef.current = requestAnimationFrame(updateMeter);
                };
                animFrameRef.current = requestAnimationFrame(updateMeter);
              } catch (e) {
                console.warn('AudioAnalyser setup failed:', e);
              }
            }
          },
        );

        room.on(RoomEvent.TrackUnsubscribed, (track: RemoteTrack) => {
          if (track.kind === Track.Kind.Audio) {
            track.detach();
            if (analyserCleanupRef.current) {
              void analyserCleanupRef.current().catch(() => {});
              analyserCleanupRef.current = null;
            }
          }
        });

        // Handle Real-Time Data (Telemetry, Transcripts, States)
        room.on(RoomEvent.DataReceived, (payload: Uint8Array) => {
          try {
            const text = new TextDecoder().decode(payload);
            const msg = JSON.parse(text);

            if (msg.type === 'roxstar.sts.telemetry') {
              setTelemetry((prev) => ({
                ...prev,
                ttfaMs: msg.ttfa_ms ?? prev.ttfaMs,
                tokensPerSec: msg.tokens_per_second ?? prev.tokensPerSec,
                durationS: msg.duration_s ?? prev.durationS,
                lastUpdated: Date.now(),
              }));
            } else if (msg.type === 'roxstar.sts.state') {
              if (msg.state === 'listening' || msg.state === 'thinking' || msg.state === 'speaking' || msg.state === 'idle') {
                setSimranState(msg.state);
              }
            } else if (msg.type === 'roxstar.bot_turned_off') {
              console.log('Bot turned off, onboarding complete:', msg.reason);
              setSimranState('idle');
              setIsSimranAway(true);
              if (msg.reason) {
                setSimranAwayReason(msg.reason);
              }
            } else if (msg.type === 'roxstar.tooltip') {
              setActiveTooltip({
                id: msg.id,
                title: msg.title || 'Tip',
                message: msg.message || '',
                target: msg.target,
              });
            } else if (msg.type === 'roxstar.user_state') {
              if (msg.profile) {
                setUserProfile(msg.profile);
              }
              if (Array.isArray(msg.discovered)) {
                setDiscoveredTopics(msg.discovered);
              }
            } else if (msg.type === 'roxstar.duet_navigation') {
              console.log('Duet navigation triggered by Simran:', msg.room_id);
              setNavigatedDuetRoom(msg.room_id || 'duet-active');
            } else if (msg.type === 'roxstar.solo_recording_navigation') {
              console.log('Solo recording navigation triggered by Simran:', msg.song_title);
              setNavigatedSoloRecording(msg.song_title || 'Tum Hi Ho');
            } else if (msg.type === 'roxstar.stage_transferred') {
              console.log('Stage transferred to user, Simran stepped away:', msg.reason);
              setIsSimranAway(true);
              setSimranAwayReason(msg.reason || 'Simran stepped aside so you can jam freely!');
            } else if (msg.type === 'roxstar.simran_rejoined' || msg.type === 'roxstar.saara_rejoined') {
              console.log('Simran rejoined the session');
              setIsSimranAway(false);
              setSimranAwayReason(null);
            } else if (msg.type === 'roxstar.coins_awarded') {
              const bal = Number(msg.balance ?? 50);
              const amt = Number(msg.amount ?? 50);
              console.log('Coins awarded:', amt, 'New balance:', bal);
              setCoinBalance(bal);
              setCoinsAwardedEvent({
                amount: amt,
                balance: bal,
                reason: msg.reason || 'Daily Login Bonus Claimed',
              });
            } else if (msg.type === 'roxstar.coin_balance') {
              if (typeof msg.balance === 'number') {
                setCoinBalance(msg.balance);
              }
            } else if (msg.type === 'roxstar.laugh_mode_updated') {
              if (typeof msg.enabled === 'boolean') {
                setLaughEnabled(msg.enabled);
              }
            } else if (msg.type === 'roxstar.sts.transcript') {
              const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
              const incomingText = String(msg.text || '').trim();
              if (!incomingText || incomingText === '---' || incomingText === '--' || incomingText === '-' || incomingText === '...') return;

              const isFinal = Boolean(msg.is_final ?? msg.isFinal ?? true);
              const speaker = (msg.speaker === 'Simran' || msg.speaker === 'Saraah') ? 'Simran' : 'You';

              // Dynamic StarMaker Coin Reward: Trigger celebratory coin popup when Simran talks about coins!
              if (speaker === 'Simran' && !hasTriggeredVoiceCoinsRef.current) {
                const lower = incomingText.toLowerCase();
                const mentionsCoins = ['coin', 'coins', 'सिक्के', 'कॉइन', 'कॉइन्स', 'daily login bonus', 'welcome coins'].some((kw) => lower.includes(kw));
                if (mentionsCoins) {
                  hasTriggeredVoiceCoinsRef.current = true;
                  const newBal = 50;
                  setCoinBalance((prev) => (prev > 0 ? prev : newBal));
                  setCoinsAwardedEvent({
                    amount: 50,
                    balance: newBal,
                    reason: 'Daily Login Bonus Claimed',
                  });
                }
              }

              setTranscripts((prev) => {
                const last = prev[prev.length - 1];
                // Suppress immediate consecutive duplicate turns from same speaker
                if (last && (last.speaker === speaker || (speaker === 'Simran' && (last.speaker === 'Simran' || last.speaker === 'Saraah'))) && last.text === incomingText) {
                  return prev;
                }
                // Only update the last message in-place if it is an ongoing non-final streaming turn from the same speaker
                if (last && last.speaker === msg.speaker && !last.isFinal) {
                  return [
                    ...prev.slice(0, -1),
                    { ...last, text: incomingText, isFinal },
                  ];
                }
                // Otherwise, append as a new turn in chat history
                return [
                  ...prev,
                  {
                    id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
                    speaker,
                    text: incomingText,
                    time: now,
                    isFinal,
                  },
                ];
              });
            }
          } catch (err) {
            console.warn('Failed to parse incoming room data:', err);
          }
        });

        // Connect to LiveKit Room
        await room.connect(sess.url, sess.token);

        // Publish local microphone with explicit echo cancellation and noise suppression
        await room.localParticipant.setMicrophoneEnabled(true, {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        });
        setIsMuted(false);

        // Add initial system greeting to transcript
        setTranscripts([
          {
            id: 'init',
            speaker: 'System',
            text: 'Connected with Simran. Say hello or share your favorite songs to begin!',
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            isFinal: true,
          },
        ]);
      } catch (err: unknown) {
        console.error('STS Room Connection failed:', err);
        const msg = err instanceof Error ? err.message : 'Failed to join STS room.';
        setError(msg);
        setConnectionState(ConnectionState.Disconnected);
      }
    },
    [cleanup],
  );

  const toggleMute = useCallback(async () => {
    if (!roomRef.current?.localParticipant) return;
    const nextState = !isMuted;
    await roomRef.current.localParticipant.setMicrophoneEnabled(!nextState);
    setIsMuted(nextState);
  }, [isMuted]);

  const sendTextTurn = useCallback(
    async (text: string) => {
      if (!roomRef.current?.localParticipant || !text.trim()) return;
      const payload = JSON.stringify({
        type: 'roxstar.chat',
        text: text.trim(),
        sender: 'User',
      });
      await roomRef.current.localParticipant.publishData(new TextEncoder().encode(payload), {
        reliable: true,
      });

      setTranscripts((prev) => [
        ...prev,
        {
          id: `${Date.now()}-${Math.random()}`,
          speaker: 'You',
          text: text.trim(),
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isFinal: true,
        },
      ]);
    },
    [],
  );

  const dismissTooltip = useCallback(() => {
    setActiveTooltip(null);
  }, []);

  const emitAppEvent = useCallback(
    async (action: string, data?: Record<string, any>) => {
      if (!roomRef.current?.localParticipant) return;
      const payload = JSON.stringify({
        type: 'roxstar.app_event',
        action,
        ...(data || {}),
      });
      await roomRef.current.localParticipant.publishData(new TextEncoder().encode(payload), {
        reliable: true,
      });
    },
    [],
  );

  const declineDuet = useCallback(async () => {
    if (!roomRef.current?.localParticipant) return;
    const payload = JSON.stringify({
      type: 'roxstar.duet_decline',
    });
    await roomRef.current.localParticipant.publishData(new TextEncoder().encode(payload), {
      reliable: true,
    });
  }, []);

  const clearDuetNavigation = useCallback(() => {
    setNavigatedDuetRoom(null);
  }, []);

  const clearSoloNavigation = useCallback(() => {
    setNavigatedSoloRecording(null);
  }, []);

  const dismissCoinsReward = useCallback(() => {
    setCoinsAwardedEvent(null);
  }, []);

  const triggerCoinsPopup = useCallback(
    (amount = 50, reason = 'Daily Login Bonus Claimed') => {
      setCoinBalance((prev) => (prev > 0 ? prev : amount));
      setCoinsAwardedEvent({
        amount,
        balance: Math.max(amount, coinBalance),
        reason,
      });
    },
    [coinBalance],
  );

  const rejoinSimran = useCallback(async () => {
    setIsSimranAway(false);
    setSimranAwayReason(null);
    await emitAppEvent('rejoin_simran');
  }, [emitAppEvent]);

  const rejoinSaara = rejoinSimran;

  const sendDuetGift = useCallback(
    async (gift: string, recipient: string) => {
      setCoinBalance((prev) => Math.max(0, prev - 5));
      await emitAppEvent('send_duet_gift', { gift, recipient });
    },
    [emitAppEvent],
  );

  const setLaughMode = useCallback(
    async (enabled: boolean) => {
      setLaughEnabled(enabled);
      try {
        localStorage.setItem('roxstar_laugh_enabled', String(enabled));
      } catch {}
      if (roomRef.current && roomRef.current.state === ConnectionState.Connected) {
        const payload = JSON.stringify({
          type: 'roxstar.set_laugh_mode',
          enabled,
          timestamp: Date.now(),
        });
        try {
          await roomRef.current.localParticipant.publishData(new TextEncoder().encode(payload), {
            reliable: true,
          });
          console.log('Sent roxstar.set_laugh_mode data packet:', enabled);
        } catch (err) {
          console.warn('Could not send set_laugh_mode packet:', err);
        }
      }
    },
    [],
  );

  useEffect(() => {
    return () => {
      void cleanup();
    };
  }, [cleanup]);

  return {
    session,
    isConnected,
    isConnecting,
    isMuted,
    simranState,
    saraahState: simranState,
    telemetry,
    transcripts,
    audioLevel,
    error,
    activeTooltip,
    dismissTooltip,
    userProfile,
    discoveredTopics,
    navigatedDuetRoom,
    clearDuetNavigation,
    navigatedSoloRecording,
    clearSoloNavigation,
    isSimranAway,
    isSaaraAway: isSimranAway,
    simranAwayReason,
    saaraAwayReason: simranAwayReason,
    coinBalance,
    coinsAwardedEvent,
    dismissCoinsReward,
    triggerCoinsPopup,
    rejoinSimran,
    rejoinSaara,
    sendDuetGift,
    laughEnabled,
    setLaughMode,
    connect,
    disconnect: cleanup,
    toggleMute,
    sendTextTurn,
    emitAppEvent,
    declineDuet,
  };
}
