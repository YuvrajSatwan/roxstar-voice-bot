import React from 'react';
import { type SaraahState } from '../hooks/useStsRoom';
import { Sparkles, Mic, Volume2, Cpu } from 'lucide-react';

interface SaaraOrbProps {
  state: SaraahState;
  audioLevel: number;
  isConnected: boolean;
}

export const SaaraOrb: React.FC<SaaraOrbProps> = ({ state, audioLevel, isConnected }) => {
  const pulseScale = isConnected ? 1 + Math.min(audioLevel * 0.8, 0.45) : 1;
  const ringScale = isConnected ? 1 + Math.min(audioLevel * 1.5, 0.9) : 1;

  const stateDetails = {
    idle: {
      label: 'Disconnected',
      badgeClass: 'badge--idle',
      icon: <Cpu size={14} color="#a1a1aa" />,
      glowColor: 'rgba(113, 113, 122, 0.2)',
    },
    listening: {
      label: 'Listening to your voice...',
      badgeClass: 'badge--listening',
      icon: <Mic size={14} color="#c4b5fd" />,
      glowColor: 'rgba(168, 85, 247, 0.35)',
    },
    thinking: {
      label: 'Gemini 3.8 Live Thinking...',
      badgeClass: 'badge--thinking',
      icon: <Sparkles size={14} color="#f0abfc" />,
      glowColor: 'rgba(217, 70, 239, 0.5)',
    },
    speaking: {
      label: 'Saraah Speaking (Sulafat)',
      badgeClass: 'badge--speaking',
      icon: <Volume2 size={14} color="#6ee7b7" />,
      glowColor: 'rgba(192, 132, 252, 0.65)',
    },
  }[isConnected ? state : 'idle'];

  return (
    <div className="saara-orb-container">
      {/* Outer Radiating Sonic Wave Rings */}
      {isConnected && (
        <>
          <div
            className="orb-ring orb-ring--outer"
            style={{
              transform: `scale(${ringScale * 1.15})`,
              opacity: state === 'speaking' ? 0.6 + audioLevel * 0.4 : 0.2,
            }}
          />
          <div
            className="orb-ring orb-ring--inner"
            style={{
              transform: `scale(${ringScale})`,
              opacity: state === 'speaking' ? 0.8 + audioLevel * 0.2 : 0.3,
            }}
          />
        </>
      )}

      {/* Main Core Glowing Orb */}
      <div
        className={`saara-orb ${state === 'speaking' ? 'saara-orb--speaking' : ''} ${
          state === 'thinking' ? 'saara-orb--thinking' : ''
        }`}
        style={{
          transform: `scale(${pulseScale})`,
          boxShadow: `0 0 50px ${stateDetails.glowColor}, inset 0 0 30px rgba(255, 255, 255, 0.25)`,
        }}
      >
        <div className="saara-orb-glow" />
        <div className="saara-orb-center">
          <span className="saara-initial">S</span>
        </div>
      </div>

      {/* Persona Label & Realtime State Pill */}
      <div className="saara-info">
        <div className="saara-name-row">
          <h2 className="saara-name">Saraah</h2>
          <span className="saara-tag">AI Sathi</span>
        </div>

        <div className={`status-badge ${stateDetails.badgeClass}`}>
          {stateDetails.icon}
          <span>{stateDetails.label}</span>
        </div>
      </div>
    </div>
  );
};
