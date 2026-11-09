import React, { useState } from 'react';
import { useStsRoom } from './hooks/useStsRoom';
import { SaraahPresence } from './components/SaraahPresence';
import { TranscriptView } from './components/TranscriptView';
import { Controls } from './components/Controls';
import { TooltipOverlay } from './components/TooltipOverlay';
import { KaraokeStageBar } from './components/KaraokeStageBar';
import { DiscoveryProfileBadge } from './components/DiscoveryProfileBadge';
import { ArrowUpRight, Music2, Sparkles, Zap } from 'lucide-react';

export function App() {
  const [userName, setUserName] = useState('Rahul');
  const {
    session,
    isConnected,
    isConnecting,
    isMuted,
    saraahState,
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
    isSaaraAway,
    saaraAwayReason,
    coinBalance,
    coinsAwardedEvent,
    dismissCoinsReward,
    rejoinSaara,
    sendDuetGift,
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

  const ttfa = telemetry.ttfaMs ?? 385;

  return (
    <div className="room-shell">
      {/* Floating Contextual Tooltip */}
      <TooltipOverlay tooltip={activeTooltip} onDismiss={dismissTooltip} />

      {/* Refined Minimalist Top Header */}
      <header className="room-nav">
        <div className="room-nav__brand">
          <div className="brand-icon">
            <Music2 size={18} />
          </div>
          <span className="brand-wordmark">Roxstar</span>
          <span className="brand-divider">·</span>
          <span className="brand-companion">Saara</span>
          <span className="brand-role">Singing Buddy</span>
        </div>

        <div className="room-nav__meta">
          {/* Subtle Telemetry Pill */}
          <div
            className="telemetry-pill"
            title={`Direct Gemini 3.8 Live Speech-to-Speech (TTFA: ${ttfa}ms, Voice: Sulafat)`}
          >
            <Zap size={12} className="telemetry-pill__icon" />
            <span>{ttfa}ms</span>
            <span className="telemetry-pill__sub">S2S</span>
          </div>

          {/* Quiet Link to Dual-Bot Cascade UI */}
          <a
            href="http://127.0.0.1:5174"
            target="_blank"
            rel="noreferrer"
            className="nav-link-cascade"
            title="Switch to original Dual-Bot (Kabir & Saraah) Cascade UI"
          >
            <span>Dual-Bot (5174)</span>
            <ArrowUpRight size={13} />
          </a>
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

      {/* Main 2-Pane Clean Studio Layout */}
      <main className="room-main">
        {/* Left Pane: Stage */}
        <section className="stage-pane" aria-label="Audio Stage">
          <SaraahPresence
            state={saraahState}
            audioLevel={audioLevel}
            isConnected={isConnected}
            userName={userName}
            onUserNameChange={setUserName}
            isMuted={isMuted}
            isSaaraAway={isSaaraAway}
            saaraAwayReason={saaraAwayReason}
            onRejoinSaara={rejoinSaara}
          />

          {/* Karaoke Feature Controls */}
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
          />

          {/* Discovery Profile Badges */}
          <DiscoveryProfileBadge
            profile={userProfile}
            discoveredTopics={discoveredTopics}
          />

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
            saraahState={saraahState}
            onSendMessage={(text) => {
              void sendTextTurn(text);
            }}
            disabled={!isConnected}
          />
        </section>
      </main>
    </div>
  );
}
