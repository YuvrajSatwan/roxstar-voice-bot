import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  MessageSquare, 
  Mic, 
  MicOff,
  Music, 
  Coins, 
  User, 
  ArrowLeft, 
  CheckCircle2, 
  Clock, 
  Send, 
  PhoneCall, 
  ChevronRight, 
  Radio,
  Layers,
  Flame,
  Volume2,
  Gift,
  Share2,
  X
} from 'lucide-react';
import { SimranWebViewPage } from '../simran/SimranWebViewPage';
import { resetBridgeState } from '../bridge';
import './simulator.css';

type FlowStep = 'signup' | 'inbox' | 'chat_thread' | 'webview' | 'duet_room' | 'solo_studio';

export function RoxStarUserFlowSimulator(): React.ReactElement {
  const [step, setStep] = useState<FlowStep>('signup');
  const [userName, setUserName] = useState('Rahul');
  const [signupMethod, setSignupMethod] = useState<'google' | 'email' | 'guest'>('google');
  const [pipelineEvents, setPipelineEvents] = useState<Array<{ time: string; source: string; msg: string; color: string }>>([]);
  const [showNudgeModal, setShowNudgeModal] = useState(false);
  const [unreadCount, setUnreadCount] = useState(1);
  const [activeBottomTab, setActiveBottomTab] = useState<'party' | 'sing' | 'messages' | 'profile'>('messages');
  const [duetMicActive, setDuetMicActive] = useState(true);
  const [handoffTarget, setHandoffTarget] = useState<{ type: 'duet' | 'solo'; label: string }>({
    type: 'duet',
    label: 'Room #304 (Arijit Hits Jam)'
  });

  // Push an event to the simulated backend pipeline feed
  const addPipelineLog = (source: string, msg: string, color: string) => {
    const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    setPipelineEvents(prev => [...prev.slice(-5), { time, source, msg, color }]);
  };

  // Wire up the Native Bridge receiver so SimranWebViewPage messages are handled
  useEffect(() => {
    window.SimranBridge = {
      postMessage: (jsonStr: string) => {
        try {
          const msg = JSON.parse(jsonStr);
          if (msg.type === 'simran.close') {
            if (msg.destination === 'duet') {
              const target = `Room #${msg.room_id || '304'} (Arijit Hits Jam)`;
              setHandoffTarget({ type: 'duet', label: target });
              setStep('duet_room');
              addPipelineLog('Native Bridge', `Received simran.close(destination='duet', room_id=${msg.room_id || '304'}) -> Navigating to Live Duet Room!`, '#10b981');
            } else if (msg.destination === 'solo') {
              const target = msg.song_title || 'Kesariya';
              setHandoffTarget({ type: 'solo', label: target });
              setStep('solo_studio');
              addPipelineLog('Native Bridge', `Received simran.close(destination='solo', song_title="${target}") -> Navigating to Solo Studio!`, '#a855f7');
            } else {
              setStep('chat_thread');
              addPipelineLog('Native Bridge', `Received simran.close(destination='none', reason='${msg.reason || 'ended'}') -> Returning to Chat Thread`, '#94a3b8');
            }
          }
        } catch (err) {
          console.warn('[Simulator] Error parsing native bridge message:', err);
        }
      }
    };
  }, []);

  const handleSignup = (method: 'google' | 'email' | 'guest') => {
    setSignupMethod(method);
    const finalName = userName.trim() || 'Rahul';
    setUserName(finalName);

    // Injected into bridge for WebView
    window.__ROXSTAR_AUTH__ = {
      accessToken: 'simulated_roxstar_jwt_token',
      name: finalName
    };

    // Step 1: Rox-Auth enqueues
    addPipelineLog('Rox-Auth-K8s', `Signup (${method}) successful for "${finalName}" (ID: 49102)`, '#10b981');
    addPipelineLog('Redis', `LPUSH simran:onboarding:queue note enqueued (<1ms)`, '#3b82f6');

    setTimeout(() => {
      // Step 2: rox-chat consumer dequeues & seeds
      addPipelineLog('rox-chat consumer', `BRPOPLPUSH note claimed -> seedSimranWelcomeChat()`, '#a855f7');
      addPipelineLog('MySQL', `INSERT INTO chat & chat_message (msg_type='SIMRAN_INVITE')`, '#f59e0b');
      addPipelineLog('Redis', `ZADD simran:nudges:pending in 120s`, '#ec4899');
      
      setUnreadCount(1);
      setStep('inbox');
    }, 600);
  };

  const openSimranChat = () => {
    setUnreadCount(0);
    setStep('chat_thread');
    addPipelineLog('Client', `Opened chat with Simran (1-on-1 thread)`, '#06b6d4');
  };

  const launchSimranWebView = () => {
    resetBridgeState();
    setStep('webview');
    setShowNudgeModal(false);
    addPipelineLog('Mobile App', `WebView opened -> SimranWebViewPage mounted`, '#6366f1');
    addPipelineLog('token_server', `POST /token -> LiveKit room "sts-simran-49102" created`, '#10b981');
    addPipelineLog('LiveKit Cloud', `Worker sts-simran dispatched exclusively to user`, '#3b82f6');
  };

  const triggerNudgeSimulation = () => {
    setShowNudgeModal(true);
    addPipelineLog('rox-chat poller', `ZRANGEBYSCORE claimed -> atomic ZREM succeeded`, '#ec4899');
    addPipelineLog('Socket.IO', `Emitted "roxstar:nudge:simran_live" popup event to app`, '#a855f7');
  };

  return (
    <div className="sim-container">
      {/* Top Banner / Explainer */}
      <header className="sim-header">
        <div className="sim-header-brand">
          <div className="sim-badge-rox">ROXSTAR</div>
          <h1>New User Onboarding Journey Simulator</h1>
        </div>
        <p className="sim-header-desc">
          Experience the <strong>exact mobile application workflow</strong> as seen by a newly registered RoxStar user.
        </p>
        
        {/* Step Indicator Tabs */}
        <div className="sim-steps-bar">
          <button 
            type="button" 
            className={`sim-step-pill ${step === 'signup' ? 'active' : ''}`}
            onClick={() => setStep('signup')}
          >
            1. Registration
          </button>
          <button 
            type="button" 
            className={`sim-step-pill ${step === 'inbox' ? 'active' : ''}`}
            onClick={() => setStep('inbox')}
          >
            2. Chat Inbox {unreadCount > 0 && <span className="sim-pill-unread">1</span>}
          </button>
          <button 
            type="button" 
            className={`sim-step-pill ${step === 'chat_thread' ? 'active' : ''}`}
            onClick={() => setStep('chat_thread')}
          >
            3. Welcome Card
          </button>
          <button 
            type="button" 
            className={`sim-step-pill ${step === 'webview' ? 'active' : ''}`}
            onClick={launchSimranWebView}
          >
            4. Simran Voice Stage
          </button>
          <button 
            type="button" 
            className={`sim-step-pill ${step === 'duet_room' ? 'active' : ''}`}
            onClick={() => setStep('duet_room')}
          >
            5. Duet Stage (Handoff)
          </button>
          <button 
            type="button" 
            className={`sim-step-pill ${step === 'solo_studio' ? 'active' : ''}`}
            onClick={() => setStep('solo_studio')}
          >
            6. Solo Studio (Handoff)
          </button>
          
          <button 
            type="button" 
            className="sim-step-pill sim-nudge-btn"
            onClick={triggerNudgeSimulation}
            title="Simulate user not tapping card for 2 minutes"
          >
            <Clock size={14} /> Simulate 2-Min Fallback Nudge
          </button>
        </div>
      </header>

      {/* Main split: Phone Mockup on left, Real-time Pipeline on right */}
      <div className="sim-workspace">
        {/* Mobile Device Frame */}
        <div className="sim-device">
          <div className="sim-phone-shell">
            {/* Phone Top Notch & Status Bar */}
            <div className="sim-phone-header">
              <span className="sim-clock">9:41</span>
              <div className="sim-notch" />
              <div className="sim-status-icons">
                <span>5G</span>
                <span>100%</span>
              </div>
            </div>

            {/* SCREEN 1: REGISTRATION / SIGNUP */}
            {step === 'signup' && (
              <div className="sim-screen sim-signup-screen">
                <div className="sim-auth-hero">
                  <div className="sim-logo-ring">
                    <Music size={32} className="sim-icon-glow" />
                  </div>
                  <h2>Welcome to RoxStar</h2>
                  <p>Social Karaoke, Duets &amp; Live Singing</p>
                </div>

                <div className="sim-auth-form">
                  <label htmlFor="sim-input-name" className="sim-label">Enter your display name:</label>
                  <input 
                    id="sim-input-name"
                    type="text" 
                    className="sim-input" 
                    value={userName} 
                    onChange={e => setUserName(e.target.value)}
                    placeholder="e.g. Rahul, Pooja"
                  />

                  <div className="sim-signup-actions">
                    <button 
                      type="button" 
                      className="sim-btn sim-btn-google"
                      onClick={() => handleSignup('google')}
                    >
                      <Sparkles size={16} /> Continue with Google
                    </button>
                    <button 
                      type="button" 
                      className="sim-btn sim-btn-email"
                      onClick={() => handleSignup('email')}
                    >
                      Register with Email
                    </button>
                    <button 
                      type="button" 
                      className="sim-btn sim-btn-guest"
                      onClick={() => handleSignup('guest')}
                    >
                      Quick Guest Login
                    </button>
                  </div>
                </div>

                <div className="sim-auth-footer">
                  <p>By signing up, you agree to RoxStar Terms &amp; Music Community Guidelines.</p>
                </div>
              </div>
            )}

            {/* SCREEN 2: ROXSTAR CHAT INBOX */}
            {step === 'inbox' && (
              <div className="sim-screen sim-inbox-screen">
                <div className="sim-app-nav">
                  <h3>Messages</h3>
                  <div className="sim-nav-right">
                    <span className="sim-badge-online">Online</span>
                  </div>
                </div>

                <div className="sim-chat-tabs">
                  <span className="sim-tab active">Chats</span>
                  <span className="sim-tab">Groups</span>
                  <span className="sim-tab">Notifications</span>
                </div>

                <div className="sim-chat-list">
                  {/* Simran Welcome Chat Thread */}
                  <div className="sim-chat-item sim-chat-highlight" onClick={openSimranChat}>
                    <div className="sim-avatar-wrapper">
                      <div className="sim-avatar sim-avatar-simran">
                        <span>S</span>
                      </div>
                      <span className="sim-online-dot" />
                    </div>
                    <div className="sim-chat-meta">
                      <div className="sim-chat-title-row">
                        <span className="sim-sender-name">Simran <span className="sim-bot-pill">AI Host</span></span>
                        <span className="sim-chat-time">Just now</span>
                      </div>
                      <div className="sim-chat-snippet-row">
                        <p className="sim-chat-snippet">Hey! Main Simran 👋 Tap to talk to me in my room!</p>
                        {unreadCount > 0 && <span className="sim-unread-bubble">{unreadCount}</span>}
                      </div>
                    </div>
                  </div>

                  {/* Standard mock chats for realism */}
                  <div className="sim-chat-item">
                    <div className="sim-avatar">
                      <span>R</span>
                    </div>
                    <div className="sim-chat-meta">
                      <div className="sim-chat-title-row">
                        <span className="sim-sender-name">RoxStar Support</span>
                        <span className="sim-chat-time">10m ago</span>
                      </div>
                      <p className="sim-chat-snippet">Welcome to RoxStar community!</p>
                    </div>
                  </div>

                  <div className="sim-chat-item">
                    <div className="sim-avatar">
                      <span>B</span>
                    </div>
                    <div className="sim-chat-meta">
                      <div className="sim-chat-title-row">
                        <span className="sim-sender-name">Bollywood Duets Jam</span>
                        <span className="sim-chat-time">1h ago</span>
                      </div>
                      <p className="sim-chat-snippet">Aman started singing Kesariya...</p>
                    </div>
                  </div>
                </div>

                {/* Bottom App Navigation */}
                <div className="sim-bottom-bar">
                  <div className={`sim-bar-item ${activeBottomTab === 'party' ? 'active' : ''}`} onClick={() => setActiveBottomTab('party')}>
                    <Flame size={20} />
                    <span>Rooms</span>
                  </div>
                  <div className={`sim-bar-item ${activeBottomTab === 'sing' ? 'active' : ''}`} onClick={() => setActiveBottomTab('sing')}>
                    <Mic size={20} />
                    <span>Sing</span>
                  </div>
                  <div className={`sim-bar-item ${activeBottomTab === 'messages' ? 'active' : ''}`} onClick={() => setActiveBottomTab('messages')}>
                    <div className="sim-icon-with-badge">
                      <MessageSquare size={20} />
                      {unreadCount > 0 && <span className="sim-tiny-badge" />}
                    </div>
                    <span>Messages</span>
                  </div>
                  <div className={`sim-bar-item ${activeBottomTab === 'profile' ? 'active' : ''}`} onClick={() => setActiveBottomTab('profile')}>
                    <User size={20} />
                    <span>Profile</span>
                  </div>
                </div>
              </div>
            )}

            {/* SCREEN 3: 1-ON-1 CHAT THREAD WITH SIMRAN */}
            {step === 'chat_thread' && (
              <div className="sim-screen sim-thread-screen">
                <div className="sim-thread-header">
                  <button type="button" className="sim-back-btn" onClick={() => setStep('inbox')}>
                    <ArrowLeft size={20} />
                  </button>
                  <div className="sim-thread-title">
                    <h4>Simran</h4>
                    <span className="sim-subtext">Online • RoxStar AI Voice Sathi</span>
                  </div>
                </div>

                <div className="sim-message-history">
                  <div className="sim-timestamp-divider">Today</div>

                  {/* Incoming text message */}
                  <div className="sim-bubble sim-bubble-incoming">
                    <p>Hey {userName}! Main Simran 👋 Tap to talk to me in my room!</p>
                    <span className="sim-bubble-time">9:41 AM</span>
                  </div>

                  {/* THE WELCOME CARD (msg_type = 'SIMRAN_INVITE') */}
                  <div className="sim-welcome-card">
                    <div className="sim-card-banner">
                      <div className="sim-card-icon">
                        <Mic size={28} className="sim-mic-pulse" />
                      </div>
                      <div className="sim-card-banner-text">
                        <h5>Talk to Simran</h5>
                        <span>Live Voice Welcome Stage</span>
                      </div>
                    </div>
                    <div className="sim-card-body">
                      <p>Meet your AI companion, get your <strong>50 Welcome Coins</strong>, and pick your first live duet song!</p>
                      <button 
                        type="button" 
                        className="sim-card-cta"
                        onClick={launchSimranWebView}
                      >
                        <Radio size={16} /> Talk to Simran
                      </button>
                    </div>
                  </div>
                </div>

                {/* Simulated chat input */}
                <div className="sim-thread-input-bar">
                  <input type="text" placeholder="Type a message..." disabled className="sim-fake-input" />
                  <button type="button" className="sim-send-btn"><Send size={16} /></button>
                </div>
              </div>
            )}

            {/* SCREEN 4: SIMRAN WEBVIEW STAGE */}
            {step === 'webview' && (
              <div className="sim-screen sim-webview-screen">
                {/* Embed the actual production WebView page */}
                <SimranWebViewPage />
              </div>
            )}

            {/* SCREEN 5: DUET PARTY ROOM (POST-HANDOFF) */}
            {step === 'duet_room' && (
              <div className="sim-screen sim-duet-screen">
                <div className="sim-stage-header">
                  <div className="sim-stage-title-wrap">
                    <h4>{handoffTarget.label}</h4>
                    <span className="sim-stage-sub">14 Listeners • Genre: Bollywood</span>
                  </div>
                  <button 
                    type="button" 
                    className="sim-leave-btn"
                    onClick={() => setStep('inbox')}
                  >
                    Leave Stage
                  </button>
                </div>

                <div className="sim-duet-seats-grid">
                  {/* Host Seat */}
                  <div className="sim-duet-seat sim-seat-active">
                    <div className="sim-seat-avatar sim-seat-pulse">
                      <span>P</span>
                    </div>
                    <span className="sim-seat-name">Priya_Singer</span>
                    <span className="sim-seat-tag">🎤 Host (Singing)</span>
                  </div>

                  {/* User Seat (Seated by Simran handoff) */}
                  <div className="sim-duet-seat sim-seat-active">
                    <div className="sim-seat-avatar" style={{ background: 'linear-gradient(135deg, #10b981, #06b6d4)' }}>
                      <span>{userName[0] || 'U'}</span>
                    </div>
                    <span className="sim-seat-name">{userName} (You)</span>
                    <span className="sim-seat-tag">🎙️ On Mic • 50 🪙</span>
                  </div>

                  {/* Empty Seat 3 */}
                  <div className="sim-duet-seat sim-seat-empty">
                    <span>Seat 3</span>
                    <span style={{ fontSize: '0.68rem', marginTop: '0.2rem' }}>Open Seat</span>
                  </div>

                  {/* Empty Seat 4 */}
                  <div className="sim-duet-seat sim-seat-empty">
                    <span>Seat 4</span>
                    <span style={{ fontSize: '0.68rem', marginTop: '0.2rem' }}>Open Seat</span>
                  </div>
                </div>

                <div className="sim-duet-bar">
                  <button 
                    type="button" 
                    className={`sim-duet-action ${duetMicActive ? 'mic-active' : ''}`}
                    onClick={() => setDuetMicActive(!duetMicActive)}
                  >
                    {duetMicActive ? <Mic size={20} /> : <MicOff size={20} />}
                    <span>{duetMicActive ? 'Mic On' : 'Mic Off'}</span>
                  </button>
                  <button type="button" className="sim-duet-action">
                    <Gift size={20} />
                    <span>Send Gift</span>
                  </button>
                  <button type="button" className="sim-duet-action">
                    <MessageSquare size={20} />
                    <span>Room Chat</span>
                  </button>
                  <button type="button" className="sim-duet-action">
                    <Share2 size={20} />
                    <span>Share</span>
                  </button>
                </div>
              </div>
            )}

            {/* SCREEN 6: SOLO RECORDING STUDIO (POST-HANDOFF) */}
            {step === 'solo_studio' && (
              <div className="sim-screen sim-solo-screen">
                <div className="sim-stage-header">
                  <div className="sim-stage-title-wrap">
                    <h4>Solo Studio: {handoffTarget.label}</h4>
                    <span className="sim-stage-sub">Pitch Monitor &amp; Vocal Guide</span>
                  </div>
                  <button 
                    type="button" 
                    className="sim-leave-btn"
                    onClick={() => setStep('inbox')}
                  >
                    Finish
                  </button>
                </div>

                <div className="sim-solo-content">
                  <div className="sim-lyrics-box">
                    <p className="sim-lyrics-line">Tu ru ru ru ru...</p>
                    <p className="sim-lyrics-line sim-lyrics-highlight">Kesariya tera ishq hai piya...</p>
                    <p className="sim-lyrics-line">Rang jaaun jo main haath lagaun</p>
                    <p className="sim-lyrics-line">Din beete saare teri fikr mein</p>
                  </div>

                  <div className="sim-solo-controls">
                    <div className="sim-record-btn" onClick={() => setStep('inbox')}>
                      <Mic size={32} />
                    </div>
                    <span style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>Tap to Stop &amp; Save Track</span>
                  </div>
                </div>
              </div>
            )}

            {/* FALLBACK NUDGE POPUP OVERLAY */}
            {showNudgeModal && (
              <div className="sim-modal-overlay">
                <div className="sim-nudge-modal">
                  <div className="sim-nudge-icon-ring">
                    <Mic size={28} />
                  </div>
                  <h3>Simran is Live! 🎤</h3>
                  <p>
                    Simran is in her room and wants to welcome you. Hop in for music &amp; free coins!
                  </p>
                  <div className="sim-nudge-actions">
                    <button 
                      type="button" 
                      className="sim-nudge-confirm"
                      onClick={launchSimranWebView}
                    >
                      Talk to Simran
                    </button>
                    <button 
                      type="button" 
                      className="sim-nudge-cancel"
                      onClick={() => setShowNudgeModal(false)}
                    >
                      Maybe Later
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Real-time Architecture & Event Pipeline Inspector */}
        <aside className="sim-inspector">
          <div className="sim-inspector-header">
            <Layers size={18} />
            <h3>Under-the-Hood Microservice Pipeline</h3>
          </div>

          <div className="sim-event-list">
            {pipelineEvents.length === 0 ? (
              <p className="sim-empty-log">
                Click <strong>&quot;Continue with Google&quot;</strong> or enter a name on the phone to trigger the multi-repo integration pipeline.
              </p>
            ) : (
              pipelineEvents.map((evt, idx) => (
                <div key={idx} className="sim-event-row">
                  <div className="sim-event-top">
                    <span className="sim-event-time">{evt.time}</span>
                    <span className="sim-event-src" style={{ color: evt.color }}>{evt.source}</span>
                  </div>
                  <p className="sim-event-msg">{evt.msg}</p>
                </div>
              ))
            )}
          </div>

          <div className="sim-tech-specs">
            <h4>Live Production Architecture Contracts</h4>
            <ul>
              <li><strong>Auth Enqueue</strong>: <code>LPUSH simran:onboarding:queue</code> (&lt;1ms non-blocking)</li>
              <li><strong>Chat Seed</strong>: <code>INSERT INTO chat_message (msg_type=&apos;SIMRAN_INVITE&apos;)</code></li>
              <li><strong>Nudge Coordination</strong>: Atomic Redis ZSET <code>simran:nudges:pending</code> claim</li>
              <li><strong>Audio Model</strong>: Ephemeral LiveKit room <code>sts-simran-{'{user_id}'}</code> (Gemini 3.8 Live Speech-to-Speech)</li>
              <li><strong>Duet Discovery</strong>: Dynamic seats via <code>rox-partyroom/v1/internal/partyroom/active-duets</code></li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
