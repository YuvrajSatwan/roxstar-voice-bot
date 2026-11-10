import React, { useEffect, useRef, CSSProperties } from 'react';

const BARS = 5;

/** Simran's iconic silhouette and gain responsiveness from the main Roxstar design system. */
export const SIMRAN_SILHOUETTE = {
  rest: [0.3, 0.4, 0.24, 0.34, 0.2],
  gain: [0.7, 1.0, 0.6, 0.9, 0.5],
};

export const SARAAH_SILHOUETTE = SIMRAN_SILHOUETTE;

interface AiGlyphProps {
  state: 'idle' | 'listening' | 'thinking' | 'speaking';
  audioLevel?: number;
  size?: 'lg' | 'md' | 'sm' | 'xs';
}

export function AiGlyph({ state, audioLevel = 0, size = 'lg' }: AiGlyphProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const audioLevelRef = useRef(audioLevel);
  audioLevelRef.current = audioLevel;
  const { rest, gain } = SIMRAN_SILHOUETTE;
  const speaking = state === 'speaking';

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const bars = Array.from(el.querySelectorAll<HTMLElement>('.glyph__bar'));
    if (!speaking) {
      bars.forEach((bar) => bar.style.removeProperty('--live'));
      return;
    }

    let frame = 0;
    const smooth = rest.slice();
    const loop = (t: number) => {
      const level = Math.min(1, (audioLevelRef.current || 0) * 2.8);
      for (let i = 0; i < BARS; i++) {
        const sway = 0.78 + 0.22 * Math.sin(t / 170 + i * 1.7);
        const target = Math.min(1, rest[i] * 1.15 + level * gain[i] * sway);
        smooth[i] += (target - smooth[i]) * 0.28;
        bars[i].style.setProperty('--live', smooth[i].toFixed(3));
      }
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frame);
  }, [speaking, rest, gain]);

  return (
    <span ref={ref} className={`glyph glyph--${size}`} data-state={state} aria-hidden="true">
      <span className="glyph__ring" />
      <span className="glyph__bars">
        {rest.map((h, i) => (
          <span
            key={i}
            className="glyph__bar"
            style={{ '--rest': h, '--gain': gain[i], '--i': i } as CSSProperties}
          />
        ))}
      </span>
    </span>
  );
}
