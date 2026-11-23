import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Mic,
  MicOff,
  Music,
  Send,
  Eye,
  Star,
  Megaphone,
  Share2,
  Power,
  Hand,
  Menu,
  ChevronRight,
  Volume2,
} from 'lucide-react';
import { useStsRoom, type TranscriptItem } from '../hooks/useStsRoom';
import {
  announceReady,
  closeSimran,
  getAuthToken,
  getNativeName,
  getRoom,
  initBridge,
  onNativeMessage,
  waitForAuthToken,
} from '../bridge';
import './simran-webview.css';

const BACKGROUND_GRACE_MS = 30_000;
const HANDOFF_FALLBACK_MS = 20_000;
const END_GRACE_MS = 1_500;
// The app no longer puts the login token in the page URL; it sends it right after the page says "ready".
// Wait long enough for that hand-over on a slow phone. (No cost when a token is already there.)
const AUTH_WAIT_MS = 3000;

type Phase = 'waiting-auth' | 'ready' | 'connecting' | 'live' | 'problem';

interface Problem {
  reason: 'busy' | 'rate_limited' | 'unauthorized' | 'mic_denied' | 'session_expired' | 'error';
  title: string;
  message: string;
}

const PROBLEMS: Record<Problem['reason'], Omit<Problem, 'reason'>> = {
  busy: {
    title: 'Simran abhi busy hai',
    message: 'Bahut saare log party room mein hain. Thodi der baad dobara aana!',
  },
  rate_limited: {
    title: 'Thodi der baad milte hain',
    message: 'Aap kai baar join kar chuke ho. Thodi der rest leke phir aana!',
  },
  session_expired: {
    title: 'Session khatam ho gaya',
    message: 'Simran ke saath aapki baat ho chuki hai. Messages mein unse chat karte rahiye!',
  },
  unauthorized: {
    title: 'Login check nahi ho paya',
    message: 'App ko ek baar band karke dobara open karo.',
  },
  mic_denied: {
    title: 'Microphone permission chahiye',
    message: 'Simran ke saath gaane ke liye app settings mein mic allow karo.',
  },
  error: {
    title: 'Connection disconnect ho gaya',
    message: 'Live room connect nahi ho paya. Dobara try karo!',
  },
};

function classifyProblem(message: string): Problem['reason'] {
  const m = message.toLowerCase();
  if (m === 'busy') return 'busy';
  if (m === 'rate_limited') return 'rate_limited';
  if (m === 'unauthorized') return 'unauthorized';
  if (m === 'session_expired') return 'session_expired';
  if (/permission|denied|notallowed|not allowed|microphone/.test(m)) return 'mic_denied';
  return 'error';
}

/**
 * Exact vector representation of RoxStar's ic_sofa_icon.xml (33x33 viewport)
 */
function SofaIcon({ className = '' }: { className?: string }): React.ReactElement {
  return (
    <svg
      viewBox="0 0 33 33"
      width="24"
      height="24"
      fill="none"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="sofaGrad" x1="16.5" y1="0" x2="16.5" y2="33" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#E6E6E6" />
          <stop offset="100%" stopColor="#999999" />
        </linearGradient>
      </defs>
      <path
        d="M24.063 20.25H8.938C7.904 20.25 7.063 21.091 7.063 22.125V24C7.063 25.034 7.904 25.875 8.938 25.875H24.063C25.096 25.875 25.938 25.034 25.938 24V22.125C25.938 21.091 25.096 20.25 24.063 20.25Z"
        fill="url(#sofaGrad)"
      />
      <path
        d="M0.5 16.162C0.5 16.386 0.523 16.612 0.566 16.831L1.827 23.132C2.144 24.721 3.551 25.875 5.172 25.875H5.709C5.386 25.321 5.188 24.686 5.188 24V22.125C5.188 20.382 6.387 18.927 8 18.508V16.162C8 14.281 6.469 12.75 4.588 12.75H3.912C2.031 12.75 0.5 14.281 0.5 16.162Z"
        fill="url(#sofaGrad)"
      />
      <path
        d="M29.088 12.75H28.412C26.531 12.75 25 14.281 25 16.162V18.508C26.613 18.927 27.813 20.382 27.813 22.125V24C27.813 24.686 27.614 25.321 27.291 25.875H27.828C29.449 25.875 30.856 24.721 31.173 23.132L32.434 16.831C32.477 16.612 32.5 16.386 32.5 16.162C32.5 14.281 30.969 12.75 29.088 12.75Z"
        fill="url(#sofaGrad)"
      />
      <path
        d="M6.125 28.688C6.125 29.206 6.544 29.625 7.063 29.625C7.581 29.625 8 29.206 8 28.688V27.75H6.125V28.688Z"
        fill="url(#sofaGrad)"
      />
      <path
        d="M25 28.688C25 29.206 25.419 29.625 25.938 29.625C26.456 29.625 26.875 29.206 26.875 28.688V27.75H25V28.688Z"
        fill="url(#sofaGrad)"
      />
      <path
        d="M4.25 10.875H4.588C7.503 10.875 9.875 13.247 9.875 16.162V18.375H23.125V16.162C23.125 13.247 25.497 10.875 28.412 10.875H28.75V8.063C28.75 5.478 26.647 3.375 24.063 3.375H8.938C6.353 3.375 4.25 5.478 4.25 8.063V10.875ZM20.313 7.125C20.83 7.125 21.25 7.545 21.25 8.063C21.25 8.58 20.83 9 20.313 9C19.795 9 19.375 8.58 19.375 8.063C19.375 7.545 19.795 7.125 20.313 7.125ZM20.313 12.75C20.83 12.75 21.25 13.17 21.25 13.688C21.25 14.205 20.83 14.625 20.313 14.625C19.795 14.625 19.375 14.205 19.375 13.688C19.375 13.17 19.795 12.75 20.313 12.75ZM12.688 7.125C13.205 7.125 13.625 7.545 13.625 8.063C13.625 8.58 13.205 9 12.688 9C12.17 9 11.75 8.58 11.75 8.063C11.75 7.545 12.17 7.125 12.688 7.125ZM12.688 12.75C13.205 12.75 13.625 13.17 13.625 13.688C13.625 14.205 13.205 14.625 12.688 14.625C12.17 14.625 11.75 14.205 11.75 13.688C11.75 13.17 12.17 12.75 12.688 12.75Z"
        fill="url(#sofaGrad)"
      />
    </svg>
  );
}

/**
 * Exact vector representation of RoxStar's ic_gift_room.xml
 */
function GiftRoomIcon(): React.ReactElement {
  return (
    <svg viewBox="0 0 21 21" width="22" height="22" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M19.398 8.944L19.274 10.686L18.963 15.913C18.901 16.784 18.341 17.593 17.532 17.904C11.123 20.393 11.309 20.393 11.061 20.455C10.75 20.517 10.376 20.517 10.003 20.455C9.692 20.393 9.941 20.455 3.532 17.904C2.723 17.593 2.163 16.784 2.101 15.913L1.789 10.686L1.665 8.944L10.501 11.744L19.398 8.944Z"
        fill="#F45170"
      />
      <path
        d="M10.998 12.864V20.393C10.687 20.455 10.314 20.455 9.941 20.393V12.864C10.314 13.05 10.687 13.05 10.998 12.864Z"
        fill="#FA5F7F"
      />
      <path
        d="M1.603 8.944L1.727 10.686L10.003 14.233C10.314 14.357 10.687 14.357 11.061 14.233L19.336 10.686L19.461 8.944L10.501 11.744L1.603 8.944Z"
        fill="#CC104A"
      />
      <path
        d="M19.834 9.255L11.061 12.988C10.936 13.051 10.75 13.113 10.563 13.113C10.376 13.113 10.252 13.051 10.065 12.988L1.167 9.255C0.545 9.006 0.421 7.202 0.669 6.019C0.732 5.771 0.794 5.584 0.856 5.397C0.981 5.211 1.043 5.086 1.167 5.024H19.834C19.958 5.086 20.021 5.148 20.083 5.273C20.207 5.459 20.27 5.708 20.332 5.957C20.581 7.202 20.394 9.006 19.834 9.255Z"
        fill="#E93565"
      />
      <path
        d="M7.514 3.779C6.145 4.526 4.838 5.21 3.656 5.895C2.972 6.33 2.536 7.077 2.598 7.886L3.345 17.655C3.407 18.153 3.656 18.65 4.03 18.899C4.963 19.584 6.518 20.517 7.265 19.895L6.456 19.335L6.27 7.637L10.501 5.273V3.779H7.514Z"
        fill="#FFD475"
      />
      <path
        d="M13.487 3.779C14.856 4.464 16.163 5.21 17.345 5.895C18.029 6.33 18.465 7.077 18.403 7.886L17.656 17.655C17.594 18.153 17.345 18.65 16.972 18.899C16.038 19.584 14.483 20.517 13.736 19.895L14.545 19.335L14.732 7.637L10.5 5.273V3.779H13.487Z"
        fill="#FFD475"
      />
    </svg>
  );
}

export function SimranWebViewPage(): React.ReactElement {
  const [phase, setPhase] = useState<Phase>('waiting-auth');
  const [problem, setProblem] = useState<Problem | null>(null);
  const [inputText, setInputText] = useState('');
  const [showGiftToast, setShowGiftToast] = useState(false);
  const [viewersCount, setViewersCount] = useState(1);

  const commentsEndRef = useRef<HTMLDivElement | null>(null);

  const {
    isConnected,
    isConnecting,
    isMuted,
    simranState,
    audioLevel,
    error,
    transcripts,
    navigatedDuetRoom,
    navigatedDuetPostId,
    navigatedSoloRecording,
    botTurnedOff,
    connect,
    disconnect,
    toggleMute,
    sendTextTurn,
    coinsAwardedEvent,
    dismissCoinsReward,
  } = useStsRoom();

  const userName = useMemo(() => getNativeName() || 'Guest', []);

  // Track handoff targets
  const handoffRef = useRef<{ duet: string | null; duetPost: string | null; solo: string | null }>({
    duet: null,
    duetPost: null,
    solo: null,
  });
  handoffRef.current = { duet: navigatedDuetRoom, duetPost: navigatedDuetPostId, solo: navigatedSoloRecording };
  const hasConnectedRef = useRef(false);

  const hangUp = useCallback(
    (message: Parameters<typeof closeSimran>[0]) => {
      void disconnect();
      closeSimran(message);
    },
    [disconnect],
  );

  // 1) Bridge initialization & token handshake (ensuring exactly ONE connection per page lifecycle)
  useEffect(() => {
    initBridge();
    announceReady();
    if (hasConnectedRef.current) return;
    hasConnectedRef.current = true;

    let alive = true;
    const targetRoom = getRoom() || undefined;

    // Fast-path: Token already available synchronously via URL or injected globals
    const immediateToken = getAuthToken();
    if (immediateToken || import.meta.env.DEV) {
      setPhase('ready');
      void connect(getNativeName() || 'Guest', targetRoom);
      return () => {
        alive = false;
      };
    }

    // Fallback: Wait briefly for native bridge handshake
    void waitForAuthToken(AUTH_WAIT_MS).then((token) => {
      if (!alive) return;
      if (token || import.meta.env.DEV) {
        setPhase('ready');
        void connect(getNativeName() || 'Guest', targetRoom);
      } else {
        setProblem({ reason: 'unauthorized', ...PROBLEMS.unauthorized });
        setPhase('problem');
      }
    });
    return () => {
      alive = false;
    };
  }, [connect]);

  // 2) Live status tracking
  useEffect(() => {
    if (isConnected) setPhase('live');
    else if (isConnecting) setPhase('connecting');
  }, [isConnected, isConnecting]);

  // 3) Error classified cleanly without AI keywords
  useEffect(() => {
    if (!error || phase === 'problem') return;
    const reason = classifyProblem(error);
    void disconnect();
    setProblem({ reason, ...PROBLEMS[reason] });
    setPhase('problem');
  }, [error, phase, disconnect]);

  // 4) Handoff transition
  const handoffTarget = navigatedDuetRoom ? 'duet' : navigatedSoloRecording ? 'solo' : null;
  useEffect(() => {
    if (!handoffTarget) return;
    const close = () => {
      const h = handoffRef.current;
      if (h.duet && h.duetPost) hangUp({ destination: 'duet_post', post_id: h.duetPost });
      else if (h.duet) hangUp({ destination: 'duet', room_id: h.duet });
      else if (h.solo) hangUp({ destination: 'solo', song_title: h.solo });
    };
    if (botTurnedOff) {
      close();
      return;
    }
    const fallback = window.setTimeout(close, HANDOFF_FALLBACK_MS);
    return () => window.clearTimeout(fallback);
  }, [handoffTarget, botTurnedOff, hangUp]);

  // 5) Clean shutdown when session ends naturally
  useEffect(() => {
    if (!botTurnedOff || handoffTarget) return;
    const t = window.setTimeout(() => {
      if (!handoffRef.current.duet && !handoffRef.current.solo) {
        hangUp({ destination: 'none', reason: 'ended' });
      }
    }, END_GRACE_MS);
    return () => window.clearTimeout(t);
  }, [botTurnedOff, handoffTarget, hangUp]);

  // 6) App background grace timer
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

  // 7) Scroll live comments feed smoothly
  useEffect(() => {
    commentsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts]);

  // Organic slight drift for live room viewers
  useEffect(() => {
    const interval = setInterval(() => {
      setViewersCount((prev) => Math.max(1, Math.min(6, prev + (Math.random() > 0.6 ? 1 : -1))));
    }, 12000);
    return () => clearInterval(interval);
  }, []);

  const handleSendComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    void sendTextTurn(inputText.trim());
    setInputText('');
  };

  // The popup appears ONLY when Simran talks about the welcome coins (see useStsRoom). Claim closes it for good:
  // the hook shows it once per session, so it cannot come back.
  const handleClaimCoins = () => {
    dismissCoinsReward();
    setShowGiftToast(true);
    setTimeout(() => setShowGiftToast(false), 3500);
  };

  const handleSendGift = () => {
    setShowGiftToast(true);
    setTimeout(() => setShowGiftToast(false), 3500);
  };

  const isSimranSpeaking = simranState === 'speaking';
  const rippleScale = isSimranSpeaking ? 1 + Math.min(audioLevel * 0.8, 0.45) : 1;

  return (
    <div className="roxstar-room-container">
      {/* ── TOP ROOM HEADER (Exact RoxStar 1:1 Live Room Layout) ── */}
      <header className="roxstar-room-header">
        {/* Left: User Profile & ID */}
        <div className="header-left-col">
          <div className="header-user-pill">
            <div className="header-user-gem">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
                <path
                  d="M12 2L2 7L12 12L22 7L12 2Z"
                  fill="#00E5FF"
                  stroke="#38BDF8"
                  strokeWidth="1.5"
                />
                <path
                  d="M2 17L12 22L22 17M2 12L12 17L22 12"
                  stroke="#38BDF8"
                  strokeWidth="1.5"
                />
              </svg>
            </div>
            <div className="header-user-meta">
              <span className="header-username">Simran</span>
              <span className="header-userid">ID: 990835</span>
            </div>
          </div>

          {/* Sub-row under username: Music circle + Translucent Pink Star Pill */}
          <div className="header-badges-row">
            <button type="button" className="music-circle-btn" aria-label="Music">
              <Music size={13} className="music-note-icon" />
            </button>
            <div className="star-capsule-pill">
              <Star size={11} className="star-icon-gold" />
              <span className="star-count-num">0</span>
              <ChevronRight size={11} className="star-arrow-icon" />
            </div>
          </div>

          {/* Stacked Loot Chests on the left */}
          <div className="header-chests-col">
            <div className="chest-badge-pill">
              <img
                src="/treasure_box_close.webp"
                alt="Chest"
                className="chest-icon-img"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
              <span className="chest-num">0/5K</span>
            </div>
            <div className="chest-badge-pill">
              <img
                src="/tresure_loot_box.png"
                alt="Loot"
                className="chest-icon-img"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
              <span className="chest-num">0/180</span>
            </div>
          </div>
        </div>

        {/* Right: Viewers, Megaphone, Share, Leave + Today's Exp Bar */}
        <div className="header-right-col">
          <div className="header-actions-row">
            {/* Viewers Pill */}
            <div className="action-viewers-pill">
              <Eye size={13} className="eye-icon-white" />
              <span className="viewers-count-num">{viewersCount}</span>
            </div>

            {/* Megaphone Action */}
            <button type="button" className="action-circle-icon-btn" aria-label="Announcements">
              <Megaphone size={14} />
            </button>

            {/* Share Action */}
            <button type="button" className="action-circle-icon-btn" aria-label="Share">
              <Share2 size={14} />
            </button>

            {/* Power / Leave Room Button */}
            <button
              type="button"
              className="action-circle-icon-btn action-leave-btn"
              onClick={() => hangUp({ destination: 'none', reason: 'ended' })}
              aria-label="Exit Party Room"
            >
              <Power size={14} />
            </button>
          </div>

          {/* Today's Exp Progress Row */}
          <div className="todays-exp-container">
            <div className="exp-labels-row">
              <span className="exp-title">Today&apos;s Exp</span>
              <span className="exp-ratio">0/3000</span>
            </div>
            <div className="exp-track-line">
              <div className="exp-fill-bar" style={{ width: '12%' }} />
            </div>
          </div>
        </div>
      </header>

      {/* ── STAGE SEATS: 1 HOST (TOP CENTER) + 8 GUEST SEATS (2x4) ── */}
      <main className="roxstar-stage-container">
        {/* Host Seat (Centered directly inside the background radial rings) */}
        <div className="stage-host-seat-wrapper">
          <div className="host-seat-circle-container">
            {/* RoxStar DuetSpeakingIndicatorView — Animated concentric pulse */}
            <div
              className={`speaking-ripple-container ${isSimranSpeaking ? 'speaking-ripple-container--active' : ''}`}
              style={{ transform: `scale(${rippleScale})` }}
            >
              <div className="ripple-ring ring-1" />
              <div className="ripple-ring ring-2" />
              <div className="ripple-ring ring-3" />
            </div>

            {/* Host Circle */}
            <div className="host-avatar-circle">
              <img
                src="/simran_avatar.jpg"
                alt="Host"
                className="host-avatar-img"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
              <div className="host-fallback-initial">S</div>
            </div>

            {/* Mic indicator */}
            <div className="host-mic-badge">
              <Volume2 size={9} />
            </div>
          </div>
          <span className="seat-label-text host-label">Host</span>
        </div>

        {/* 8 Guest Seats Grid: Row 1 (No.1 - No.4) & Row 2 (No.5 - No.8) */}
        <div className="stage-guest-seats-grid">
          {/* ── ROW 1 ── */}
          <div className="guest-seats-row">
            {/* Seat No.1 (User is automatically seated here!) */}
            <div className="guest-seat-item">
              <div className="guest-seat-circle guest-seat-circle--user">
                <div className="user-seat-avatar">
                  <span>{userName.charAt(0).toUpperCase()}</span>
                </div>
                <div className={`user-seat-mic ${isMuted ? 'user-seat-mic--muted' : 'user-seat-mic--active'}`}>
                  {isMuted ? <MicOff size={9} /> : <Mic size={9} />}
                </div>
              </div>
              <span className="seat-label-text">No.1</span>
            </div>

            {/* Seat No.2 */}
            <div className="guest-seat-item">
              <div className="guest-seat-circle guest-seat-circle--empty">
                <SofaIcon />
              </div>
              <span className="seat-label-text">No.2</span>
            </div>

            {/* Seat No.3 */}
            <div className="guest-seat-item">
              <div className="guest-seat-circle guest-seat-circle--empty">
                <SofaIcon />
              </div>
              <span className="seat-label-text">No.3</span>
            </div>

            {/* Seat No.4 */}
            <div className="guest-seat-item">
              <div className="guest-seat-circle guest-seat-circle--empty">
                <SofaIcon />
              </div>
              <span className="seat-label-text">No.4</span>
            </div>
          </div>

          {/* ── ROW 2 ── */}
          <div className="guest-seats-row">
            {/* Seat No.5 */}
            <div className="guest-seat-item">
              <div className="guest-seat-circle guest-seat-circle--empty">
                <SofaIcon />
              </div>
              <span className="seat-label-text">No.5</span>
            </div>

            {/* Seat No.6 */}
            <div className="guest-seat-item">
              <div className="guest-seat-circle guest-seat-circle--empty">
                <SofaIcon />
              </div>
              <span className="seat-label-text">No.6</span>
            </div>

            {/* Seat No.7 */}
            <div className="guest-seat-item">
              <div className="guest-seat-circle guest-seat-circle--empty">
                <SofaIcon />
              </div>
              <span className="seat-label-text">No.7</span>
            </div>

            {/* Seat No.8 */}
            <div className="guest-seat-item">
              <div className="guest-seat-circle guest-seat-circle--empty">
                <SofaIcon />
              </div>
              <span className="seat-label-text">No.8</span>
            </div>
          </div>
        </div>
      </main>

      {/* ── LOWER-THIRD NOTICES & LIVE CONVERSATION STREAM ── */}
      <section className="roxstar-notices-feed">
        {/* Notice 1: Welcome to Simran */}
        <div className="notice-row">
          <div className="notice-pink-circle">
            <Megaphone size={14} className="megaphone-white" />
          </div>
          <div className="notice-bubble-pill">
            <span>🎙️ Welcome to the Simran! 🎉</span>
          </div>
        </div>

        {/* Notice 2: Seated automatically */}
        <div className="notice-row">
          <div className="notice-pink-circle">
            <Megaphone size={14} className="megaphone-white" />
          </div>
          <div className="notice-bubble-pill">
            <span>Seated automatically in this room</span>
          </div>
        </div>

        {/* Notice 3: Keep it fun & respectful */}
        <div className="notice-row">
          <div className="notice-pink-circle">
            <Megaphone size={14} className="megaphone-white" />
          </div>
          <div className="notice-bubble-pill">
            <span>🌟 Let&apos;s keep it fun, respectful, and unforgettable!</span>
          </div>
        </div>

        {/* Live Conversation Stream as Chat Messages */}
        {transcripts.map((item: TranscriptItem) => {
          const isSimran = item.speaker === 'Simran' || item.speaker === 'Saraah';
          if (item.speaker === 'System') return null;

          return (
            <div key={item.id} className="live-chat-bubble-row">
              <div className={`chat-bubble-content ${isSimran ? 'chat-bubble--simran' : 'chat-bubble--user'}`}>
                <span className="chat-speaker-name">{isSimran ? 'Simran' : userName}:</span>
                <span className="chat-speaker-text">{item.text}</span>
              </div>
            </div>
          );
        })}

        <div ref={commentsEndRef} />
      </section>

      {/* ── WELCOME COINS CLAIM POPUP (only when Simran mentions the coins) ── */}
      {coinsAwardedEvent && (
        <div className="coins-claim-overlay" role="dialog" aria-modal="true" aria-label="Claim welcome coins">
          <div className="coins-claim-card">
            <div className="coins-claim-amount">+{coinsAwardedEvent.amount}</div>
            <strong className="coins-claim-title">Welcome Coins</strong>
            <span className="coins-claim-sub">A little welcome gift from Simran</span>
            <button type="button" className="coins-claim-btn" onClick={handleClaimCoins}>
              Claim
            </button>
          </div>
        </div>
      )}

      {/* ── GIFT REWARD CELEBRATION TOAST ── */}
      {showGiftToast && (
        <div className="gift-celebration-toast">
          <GiftRoomIcon />
          <div className="gift-toast-text">
            <strong>Welcome Bonus!</strong>
            <span>50 welcome coins claimed.</span>
          </div>
        </div>
      )}

      {/* ── CONNECTING / PROBLEM OVERLAYS ── */}
      {phase === 'connecting' && (
        <div className="roxstar-connecting-banner">
          <div className="connecting-pulse" />
          <span>Joining Simran&apos;s Party Room…</span>
        </div>
      )}

      {phase === 'problem' && problem && (
        <div className="roxstar-modal-scrim">
          <div className="roxstar-modal-card">
            <h3>{problem.title}</h3>
            <p>{problem.message}</p>
            <button
              type="button"
              className="modal-action-btn"
              onClick={() => hangUp({ destination: 'none', reason: problem.reason })}
            >
              OK
            </button>
          </div>
        </div>
      )}

      {/* ── BOTTOM CONTROL BAR (Exact RoxStar 1:1 Actions) ── */}
      <footer className="roxstar-bottom-bar">
        {/* Full-width "Let's talk" Input Pill */}
        <form onSubmit={handleSendComment} className="bottom-pill-input-form">
          <input
            type="text"
            placeholder="Let's talk"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={!isConnected}
            className="bottom-pill-input"
          />
          {inputText.trim() && (
            <button type="submit" className="bottom-pill-send-btn" aria-label="Send">
              <Send size={14} />
            </button>
          )}
        </form>

        {/* 4 Circular Action Buttons: Hand, Send/Plane, Menu, Gift */}
        <div className="bottom-action-buttons-group">
          {/* Hand Raise Button */}
          <button
            type="button"
            className="bottom-round-btn"
            onClick={() => void sendTextTurn('Hey Simran! I want to sing a song!')}
            title="Raise Hand"
            aria-label="Raise Hand"
          >
            <Hand size={18} />
          </button>

          {/* Send / Airplane Button (Quick Voice / Mic Toggle) */}
          <button
            type="button"
            className={`bottom-round-btn ${isMuted ? 'bottom-round-btn--muted' : ''}`}
            onClick={() => void toggleMute()}
            title={isMuted ? 'Unmute Mic' : 'Mute Mic'}
            aria-label="Toggle Mic"
          >
            {isMuted ? <MicOff size={18} /> : <Send size={16} />}
          </button>

          {/* Menu Button */}
          <button
            type="button"
            className="bottom-round-btn"
            onClick={() => void sendTextTurn('What songs should we sing next?')}
            title="Room Options"
            aria-label="Room Menu"
          >
            <Menu size={18} />
          </button>

          {/* 3D Gift Box Button */}
          <button
            type="button"
            className="bottom-round-btn bottom-gift-btn"
            onClick={handleSendGift}
            title="Send Gift"
            aria-label="Send Gift"
          >
            <GiftRoomIcon />
          </button>
        </div>
      </footer>
    </div>
  );
}
