import React, { useEffect, useState } from 'react';
import { useStsRoom } from './hooks/useStsRoom';
import { SimranPresence } from './components/SimranPresence';
import { TranscriptView } from './components/TranscriptView';
import { Controls } from './components/Controls';
import { TooltipOverlay } from './components/TooltipOverlay';
import { KaraokeStageBar } from './components/KaraokeStageBar';
import { DiscoveryProfileBadge } from './components/DiscoveryProfileBadge';
import { NaturalLaughDemo } from './components/NaturalLaughDemo';
import { Coins, MessageSquare, Mic, Music2, Smile, Sparkles, Zap } from 'lucide-react';

export function App() {
  const [userName, setUserName] = useState('Rahul');
  const [stageMode, setStageMode] = useState<'lounge' | 'duet' | 'solo'>('lounge');
  const [mobileTab, setMobileTab] = useState<'stage' | 'chat'>('stage');
  const [showLaughLab, setShowLaughLab] = useState(false);

  const {
    session,
    isConnected,
    isConnecting,
    isMuted,
    simranState,
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
    simranAwayReason,
    coinBalance,
    coinsAwardedEvent,
    dismissCoinsReward,
    triggerCoinsPopup,
    rejoinSimran,
    sendDuetGift,
    laughEnabled,
    setLaughMode,
    connect,
    disconnect,
    toggleMute,
    sendTextTurn,
    emitAppEvent,
    declineDuet,
  } = useStsRoom();

  const handleStart = () => {
    void connect(userName);
  };

  // Auto-switch mobile view to stage when entering Duet or Solo
  useEffect(() => {
    if (stageMode === 'duet' || stageMode === 'solo') {
      setMobileTab('stage');
    }
  }, [stageMode]);

  // Extract latest turn from Simran for VIP front-row stage cheer
  const latestSimranTurn = [...transcripts].reverse().find(
    (t) => t.speaker === 'Simran' || t.speaker === 'Saraah',
  );
  const latestSimranTranscript = latestSimranTurn?.text;

  const ttfa = telemetry.ttfaMs ?? 385;

  return (
    <div className={`room-shell ${stageMode !== 'lounge' ? 'room-shell--live-stage' : ''}`}>
      {/* Floating Contextual Tooltip */}
      <TooltipOverlay tooltip={activeTooltip} onDismiss={dismissTooltip} />

      {/* StarMaker Studio Top Header */}
      <header className="room-nav">
        <div className="room-nav__brand">
          <div className="brand-icon">
            <Music2 size={18} />
          </div>
          <span className="brand-wordmark">Roxstar</span>
          <span className="brand-divider">·</span>
          <span className="brand-companion">Simran</span>
          <span className="brand-role">Singing Buddy</span>
        </div>

        <div className="room-nav__meta">
          {/* StarMaker Clickable Coins Pill */}
          <button
            type="button"
            onClick={() => triggerCoinsPopup(50, 'Daily Free Welcome Bonus Claimed')}
            className="room-nav__coins-btn"
            title="Your StarMaker Coins Wallet - Tap to claim daily bonus"
          >
            <Coins size={14} className="coin-gold-icon" />
            <span>{coinBalance} Coins</span>
          </button>

          {/* Direct Speech-to-Speech Telemetry Pill */}
          <div
            className="telemetry-pill"
            title={`Direct Gemini 3.8 Live Speech-to-Speech (TTFA: ${ttfa}ms, Voice: Leda)`}
          >
            <Zap size={12} className="telemetry-pill__icon" />
            <span>{ttfa}ms</span>
            <span className="telemetry-pill__sub">S2S</span>
          </div>

          {/* Natural Laugh Lab & Demo Pill */}
          <button
            type="button"
            onClick={() => setShowLaughLab(true)}
            className={`room-nav__laugh-btn ${laughEnabled ? 'room-nav__laugh-btn--on' : 'room-nav__laugh-btn--off'}`}
            title="Open Simran Natural Laugh Lab: Listen to demo samples or turn laugh off"
          >
            <Smile size={13} className="laugh-pill__icon" />
            <span>Laugh {laughEnabled ? 'ON' : 'OFF'}</span>
          </button>
        </div>
      </header>

      {/* Alert Banner if Error */}
      {error && (
        <div className="room-error-alert" role="alert">
          <span>{error}</span>
          <button type="button" onClick={handleStart} className="alert-retry-btn">
            Retry
          </button>
        </div>
      )}

      {/* StarMaker Mobile Segmented Tabs Bar */}
      <div className="mobile-tab-bar" role="tablist" aria-label="Mobile View Switcher">
        <button
          type="button"
          role="tab"
          aria-selected={mobileTab === 'stage'}
          onClick={() => setMobileTab('stage')}
          className={`mobile-tab-btn ${mobileTab === 'stage' ? 'mobile-tab-btn--active' : ''}`}
        >
          <Music2 size={15} />
          <span>Stage Studio</span>
          {(stageMode === 'duet' || stageMode === 'solo') && (
            <span className="mobile-tab-live-dot" />
          )}
        </button>

        <button
          type="button"
          role="tab"
          aria-selected={mobileTab === 'chat'}
          onClick={() => setMobileTab('chat')}
          className={`mobile-tab-btn ${mobileTab === 'chat' ? 'mobile-tab-btn--active' : ''}`}
        >
          <MessageSquare size={15} />
          <span>Simran & Chat</span>
          {simranState === 'speaking' && (
            <span className="mobile-tab-speaking-pulse" title="Simran is speaking" />
          )}
        </button>
      </div>

      {/* Main Studio Layout: Responsive 2-Pane on Desktop, Tabbed on Mobile */}
      <main className={`room-main ${mobileTab === 'chat' ? 'room-main--show-chat' : 'room-main--show-stage'}`}>
        {/* Left Pane: Stage */}
        <section className="stage-pane" aria-label="Audio Stage">
          <div className="stage-content-scroll">
            {/* In Lounge Mode, show Simran's living presence */}
            {stageMode === 'lounge' && (
              <SimranPresence
                state={simranState}
                audioLevel={audioLevel}
                isConnected={isConnected}
                userName={userName}
                onUserNameChange={setUserName}
                isMuted={isMuted}
                isSimranAway={isSimranAway}
                simranAwayReason={simranAwayReason}
                onRejoinSimran={rejoinSimran}
                caption={latestSimranTranscript}
              />
            )}

            {/* StarMaker Karaoke Stage & Feature Controls */}
            <KaraokeStageBar
              isConnected={isConnected}
              navigatedDuetRoom={navigatedDuetRoom}
              onClearDuetNavigation={clearDuetNavigation}
              navigatedSoloRecording={navigatedSoloRecording}
              onClearSoloNavigation={clearSoloNavigation}
              onEmitAppEvent={emitAppEvent}
              onDeclineDuet={declineDuet}
              coinBalance={coinBalance}
              coinsAwardedEvent={coinsAwardedEvent}
              onDismissCoinsReward={dismissCoinsReward}
              onSendDuetGift={sendDuetGift}
              onStageModeChange={setStageMode}
              latestSimranTranscript={latestSimranTranscript}
              onTriggerCoinsPopup={triggerCoinsPopup}
            />

            {/* Discovery Profile Badges (in lounge mode) */}
            {stageMode === 'lounge' && (
              <DiscoveryProfileBadge
                profile={userProfile}
                discoveredTopics={discoveredTopics}
              />
            )}
          </div>

          {/* Always-accessible Mic & Call Controls (Docked permanently on-screen, no scrolling needed!) */}
          <Controls
            isConnected={isConnected}
            isConnecting={isConnecting}
            isMuted={isMuted}
            onToggleMute={toggleMute}
            onConnect={handleStart}
            onDisconnect={disconnect}
            audioLevel={audioLevel}
          />
        </section>

        {/* Right Pane: Conversation & Composer */}
        <section className="conversation-pane" aria-label="Conversation">
          <TranscriptView
            transcripts={transcripts}
            simranState={simranState}
            onSendMessage={(text) => {
              void sendTextTurn(text);
            }}
            disabled={!isConnected}
          />
        </section>
      </main>

      {/* Natural Laugh Lab & Demo Modal */}
      <NaturalLaughDemo
        isOpen={showLaughLab}
        onClose={() => setShowLaughLab(false)}
        laughEnabled={laughEnabled}
        onToggleLaugh={setLaughMode}
        isConnected={isConnected}
      />
    </div>
  );
}
