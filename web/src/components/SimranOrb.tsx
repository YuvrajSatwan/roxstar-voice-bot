import React from 'react';
import { type SaraahState, type SimranState } from '../hooks/useStsRoom';
import { SpeakingOrb } from './SpeakingOrb';
import { Sparkles, Mic, Volume2, Cpu } from 'lucide-react';

export interface SimranOrbProps {
  state: SimranState | SaraahState;
  audioLevel: number;
  isConnected: boolean;
  caption?: string | null;
}

export const SimranOrb: React.FC<SimranOrbProps> = ({ state, audioLevel, isConnected, caption }) => {
  const currentState = isConnected ? state : 'idle';

  const stateDetails = {
    idle: {
      label: 'Disconnected',
      badgeClass: 'badge--idle',
      icon: <Cpu size={14} color="#7e7399" />,
    },
    listening: {
      label: 'Listening to your voice...',
      badgeClass: 'badge--listening',
      icon: <Mic size={14} color="#7c3aed" />,
    },
    thinking: {
      label: 'Gemini 3.8 Live Thinking...',
      badgeClass: 'badge--thinking',
      icon: <Sparkles size={14} color="#ff2e93" />,
    },
    speaking: {
      label: 'Simran Speaking (Sulafat)',
      badgeClass: 'badge--speaking',
      icon: <Volume2 size={14} color="#10b981" />,
    },
  }[currentState];

  return (
    <div className="saara-orb-container">
      {/* 12,000 Particle WebGL Speaking Orb */}
      <SpeakingOrb
        state={currentState}
        audioLevel={audioLevel}
        size="md"
        caption={currentState === 'speaking' ? caption : undefined}
      />

      {/* Persona Label & Realtime State Pill */}
      <div className="saara-info">
        <div className="saara-name-row">
          <h2 className="saara-name">Simran</h2>
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

export default SimranOrb;
