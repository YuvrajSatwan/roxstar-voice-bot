import React from 'react';

interface AudioVisualizerProps {
  level: number;
  isActive: boolean;
}

export const AudioVisualizer: React.FC<AudioVisualizerProps> = ({ level, isActive }) => {
  const barCount = 28;

  return (
    <div className="audio-visualizer-container">
      {Array.from({ length: barCount }).map((_, i) => {
        const centerOffset = Math.abs(i - barCount / 2) / (barCount / 2);
        const factor = Math.cos(centerOffset * (Math.PI / 2));
        const minHeight = 4;
        const dynamicHeight = isActive
          ? Math.max(minHeight, Math.min(36, minHeight + level * 70 * factor + (Math.sin(i * 1.5 + Date.now() / 200) * 3)))
          : minHeight;

        return (
          <div
            key={i}
            className="visualizer-bar"
            style={{
              height: `${dynamicHeight}px`,
              opacity: isActive ? 0.35 + (dynamicHeight / 36) * 0.65 : 0.2,
            }}
          />
        );
      })}
    </div>
  );
};
