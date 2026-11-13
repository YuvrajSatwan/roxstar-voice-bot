import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Mic, MicOff, PhoneOff } from 'lucide-react';
import { useStsRoom } from '../hooks/useStsRoom';
import { SpeakingOrb } from '../components/SpeakingOrb';
import {
  announceReady,
  closeSimran,
  getNativeName,
  initBridge,
  onNativeMessage,
  waitForAuthToken,
} from '../bridge';
import './simran-webview.css';

/**
 * The page the RoxStar app opens inside a WebView ("Simran's Room").
 *
 * In simple words, the life of this page:
 *   1. Page loads        -> tells the app "I'm ready" and waits for the user's login token.
 *   2. User taps "Talk"  -> (a tap is needed so the phone allows sound and the microphone)
 *                           asks the server for a PRIVATE voice room and joins it. Simran says hello.
 *   3. They chat         -> Simran learns their taste and invites them to sing.
 *   4. Handoff           -> Simran says goodbye and powers off. THEN this page tells the app
 *                           "close me and open duet room X" (or the solo studio).
 *   5. Anything goes wrong (busy, no mic, no login...) -> a friendly message, then the page asks
 *                           the app to close and go back to the chat. The user is never left stuck.
 *
 * It looks like a RoxStar party room, but there is NO real party room behind it.
 * Every user gets their own private session, so nobody ever waits for Simran.
 */

/** How long the app may stay in the background before we hang up (Gemini + LiveKit minutes cost money). */
const BACKGROUND_GRACE_MS = 30_000;
/** If Simran's "I'm off the mic" signal never arrives after a handoff, close anyway after this long. */
const HANDOFF_FALLBACK_MS = 20_000;
/** After Simran powers off with no handoff, wait a moment so the user can hear her last words land. */
const END_GRACE_MS = 1_500;
/** How long to wait for the app to hand over the login token. */
const AUTH_WAIT_MS = 4_000;

type Phase = 'waiting-auth' | 'ready' | 'connecting' | 'live' | 'problem';

interface Problem {
  /** Sent to the app as `reason`. */
  reason: 'busy' | 'rate_limited' | 'unauthorized' | 'mic_denied' | 'error';
  title: string;
  message: string;
}

const PROBLEMS: Record<Problem['reason'], Omit<Problem, 'reason'>> = {
  busy: {
    title: 'Simran abhi thodi busy hai',
    message: 'Bahut saare log baat kar rahe hain. 2 minute baad dobara try karo!',
  },
  rate_limited: {
    title: 'Aaj ke liye bahut ho gaya',
    message: 'Aap kai baar try kar chuke ho. Thodi der baad phir milte hain!',
  },
  unauthorized: {
    title: 'Login check nahi ho paya',
    message: 'App ko ek baar band karke dobara kholo, phir try karo.',
  },
  mic_denied: {
    title: 'Mic ki permission chahiye',
    message: 'Simran se baat karne ke liye app settings mein microphone allow karo.',
  },
  error: {
    title: 'Kuch gadbad ho gayi',
    message: 'Connection nahi ho paya. Thodi der baad phir try karo.',
  },
};

/** Turn whatever went wrong into one of our friendly problems. */
function classifyProblem(message: string): Problem['reason'] {
  const m = message.toLowerCase();
  if (m === 'busy') return 'busy';
  if (m === 'rate_limited') return 'rate_limited';
  if (m === 'unauthorized') return 'unauthorized';
  if (/permission|denied|notallowed|not allowed|microphone/.test(m)) return 'mic_denied';
  return 'error';
}

export function SimranWebViewPage(): React.ReactElement {
  const [phase, setPhase] = useState<Phase>('waiting-auth');
  const [problem, setProblem] = useState<Problem | null>(null);

  const {
    isConnected,
    isMuted,
    simranState,
    audioLevel,
    error,
    transcripts,
    navigatedDuetRoom,
    navigatedSoloRecording,
    botTurnedOff,
    connect,
    disconnect,
    toggleMute,
  } = useStsRoom();

  // Latest values for timers that fire later (so they never read stale data).
  const handoffRef = useRef<{ duet: string | null; solo: string | null }>({ duet: null, solo: null });
  handoffRef.current = { duet: navigatedDuetRoom, solo: navigatedSoloRecording };

  const hangUp = useCallback(
    (message: Parameters<typeof closeSimran>[0]) => {
      void disconnect(); // always leave the voice room first
      closeSimran(message); // then ask the app to close this page (only the first call counts)
    },
    [disconnect],
  );

  // 1) On load: connect the bridge, tell the app we're ready, wait for the login token.
  useEffect(() => {
    initBridge();
    announceReady();
    let alive = true;
    void waitForAuthToken(AUTH_WAIT_MS).then((token) => {
      if (!alive) return;
      if (token || import.meta.env.DEV) {
        setPhase('ready');
      } else {
        setProblem({ reason: 'unauthorized', ...PROBLEMS.unauthorized });
        setPhase('problem');
      }
    });
    return () => {
      alive = false;
    };
  }, []);

  // 2) Track the voice connection: connecting -> live.
  useEffect(() => {
    if (isConnected && phase === 'connecting') setPhase('live');
  }, [isConnected, phase]);

  // 3) Something failed while connecting or during the chat -> friendly message.
  useEffect(() => {
    if (!error || phase === 'problem') return;
    const reason = classifyProblem(error);
    void disconnect();
    setProblem({ reason, ...PROBLEMS[reason] });
    setPhase('problem');
  }, [error, phase, disconnect]);

  // 4) Handoff: Simran sent the user to a duet room or the solo studio.
  //    Wait until she has finished speaking and powered off, so nothing is cut off mid-sentence.
  const handoffTarget = navigatedDuetRoom ? 'duet' : navigatedSoloRecording ? 'solo' : null;
  useEffect(() => {
    if (!handoffTarget) return;
    const close = () => {
      const h = handoffRef.current;
      if (h.duet) hangUp({ destination: 'duet', room_id: h.duet });
      else if (h.solo) hangUp({ destination: 'solo', song_title: h.solo });
    };
    if (botTurnedOff) {
      close();
      return;
    }
    const fallback = window.setTimeout(close, HANDOFF_FALLBACK_MS);
    return () => window.clearTimeout(fallback);
  }, [handoffTarget, botTurnedOff, hangUp]);

  // 5) Simran powered off WITHOUT a handoff (user declined twice, or the time limit was reached).
  useEffect(() => {
    if (!botTurnedOff || handoffTarget) return;
    const t = window.setTimeout(() => {
      if (!handoffRef.current.duet && !handoffRef.current.solo) hangUp({ destination: 'none', reason: 'ended' });
    }, END_GRACE_MS);
    return () => window.clearTimeout(t);
  }, [botTurnedOff, handoffTarget, hangUp]);

  // 6) App minimised or screen locked for too long -> hang up so we stop paying for an empty call.
  useEffect(() => {
    let timer: number | undefined;
    const away = () => {
      if (timer !== undefined) return;
      timer = window.setTimeout(() => hangUp({ destination: 'none', reason: 'timeout' }), BACKGROUND_GRACE_MS);
    };
    const back = () => {
      if (timer !== undefined) {
        window.clearTimeout(timer);
        timer = undefined;
      }
    };
    const onVisibility = () => (document.hidden ? away() : back());
    document.addEventListener('visibilitychange', onVisibility);
    const offNative = onNativeMessage((m) => {
      if (m.type === 'app.background') away();
      else if (m.type === 'app.foreground') back();
    });
    const onPageHide = () => void disconnect();
    window.addEventListener('pagehide', onPageHide);
    return () => {
      back();
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('pagehide', onPageHide);
      offNative();
    };
  }, [hangUp, disconnect]);

  const start = () => {
    setPhase('connecting');
    void connect(getNativeName() || 'Friend');
  };

  // The last thing Simran said, shown as a caption (helps in noisy places, and for accessibility).
  const caption = useMemo(() => {
    for (let i = transcripts.length - 1; i >= 0; i--) {
      if (transcripts[i].speaker === 'Simran') return transcripts[i].text;
    }
    return null;
  }, [transcripts]);

  const orbState = simranState === 'idle' && phase === 'live' ? 'listening' : simranState;

  return (
    <main className="sw-root">
      <header className="sw-top">
        <span className="sw-live-dot" aria-hidden="true" />
        <span className="sw-title">Simran&apos;s Room</span>
        <button
          type="button"
          className="sw-close"
          onClick={() => hangUp({ destination: 'none', reason: 'ended' })}
          aria-label="Close"
        >
          ✕
        </button>
      </header>

      <section className="sw-stage" aria-live="polite">
        {/* Host chair: Simran */}
        <div className="sw-seat sw-seat-host">
          <div className="sw-orb">
            <SpeakingOrb state={orbState} audioLevel={audioLevel} size="lg" />
          </div>
          <div className="sw-name">Simran</div>
          <div className="sw-role">Host</div>
        </div>

        {phase === 'live' && caption && <p className="sw-caption">{caption}</p>}

        {phase === 'waiting-auth' && <p className="sw-hint">Ek second…</p>}

        {phase === 'ready' && (
          <div className="sw-card">
            <h1>Simran se milo 👋</h1>
            <p>Bas baat karo. Wo aapko RoxStar dikhayegi aur sahi duet dhoondhne mein help karegi.</p>
            <button type="button" className="sw-primary" onClick={start}>
              <Mic size={18} aria-hidden="true" /> Talk to Simran
            </button>
            <p className="sw-fine">Microphone ki permission maangi jayegi.</p>
          </div>
        )}

        {phase === 'connecting' && <p className="sw-hint">Simran ko bula rahe hain…</p>}

        {phase === 'problem' && problem && (
          <div className="sw-card" role="alert">
            <h1>{problem.title}</h1>
            <p>{problem.message}</p>
            <button type="button" className="sw-primary" onClick={() => hangUp({ destination: 'none', reason: problem.reason })}>
              Theek hai
            </button>
          </div>
        )}
      </section>

      {phase === 'live' && (
        <footer className="sw-bottom">
          <button type="button" className="sw-round" onClick={() => void toggleMute()} aria-label={isMuted ? 'Unmute' : 'Mute'}>
            {isMuted ? <MicOff size={22} /> : <Mic size={22} />}
          </button>
          <button
            type="button"
            className="sw-round sw-end"
            onClick={() => hangUp({ destination: 'none', reason: 'ended' })}
            aria-label="End chat"
          >
            <PhoneOff size={22} />
          </button>
        </footer>
      )}
    </main>
  );
}
