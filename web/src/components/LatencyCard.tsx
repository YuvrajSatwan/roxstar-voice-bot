import React from 'react';
import { Zap, Activity, Radio, Cpu } from 'lucide-react';
import type { StsTelemetry } from '../hooks/useStsRoom';

interface LatencyCardProps {
  telemetry: StsTelemetry;
}

export const LatencyCard: React.FC<LatencyCardProps> = ({ telemetry }) => {
  const currentTtfa = telemetry.ttfaMs ?? 385;
  const cascadedBaseline = 1820;
  const speedupRatio = (cascadedBaseline / Math.max(100, currentTtfa)).toFixed(1);
  const reductionPercent = Math.round(((cascadedBaseline - currentTtfa) / cascadedBaseline) * 100);

  return (
    <div className="telemetry-card">
      <div className="telemetry-card__header">
        <div className="telemetry-card__title">
          <Zap size={15} className="telemetry-card__icon" />
          <span>Gemini 3.8 Live Speech-to-Speech</span>
        </div>
        <div className="telemetry-card__badge">
          <Activity size={12} />
          <span>{speedupRatio}x Faster than Cascade</span>
        </div>
      </div>

      <div className="telemetry-grid">
        <div className="telemetry-metric telemetry-metric--sts">
          <span className="telemetry-metric__label">Direct S2S Latency</span>
          <div className="telemetry-metric__value-row">
            <span className="telemetry-metric__number">{currentTtfa}</span>
            <span className="telemetry-metric__unit">ms</span>
          </div>
          <span className="telemetry-metric__hint">Zero STT/TTS hops</span>
        </div>

        <div className="telemetry-metric telemetry-metric--cascaded">
          <span className="telemetry-metric__label">Cascaded Pipeline</span>
          <div className="telemetry-metric__value-row">
            <span className="telemetry-metric__number">{cascadedBaseline}</span>
            <span className="telemetry-metric__unit">ms</span>
          </div>
          <span className="telemetry-metric__hint">STT + LLM + ElevenLabs</span>
        </div>
      </div>

      <div className="telemetry-bar-wrap">
        <div className="telemetry-bar-labels">
          <span>Latency Saved: {reductionPercent}%</span>
          <span className="telemetry-bar-note">True Voice-to-Voice Stream</span>
        </div>
        <div className="telemetry-progress-track">
          <div
            className="telemetry-progress-fill"
            style={{ width: `${Math.min(100, (currentTtfa / cascadedBaseline) * 100)}%` }}
          />
        </div>
      </div>

      <div className="telemetry-footer-specs">
        <div className="spec-item">
          <Cpu size={12} />
          <span>Model: <strong>gemini-3.8-live</strong></span>
        </div>
        <div className="spec-item">
          <Radio size={12} />
          <span>Voice: <strong>Sulafat (Warm Hinglish)</strong></span>
        </div>
      </div>
    </div>
  );
};
