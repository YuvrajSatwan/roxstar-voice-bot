import React, { useEffect } from 'react';
import { Sparkles, X } from 'lucide-react';
import type { TooltipData } from '../hooks/useStsRoom';

interface TooltipOverlayProps {
  tooltip: TooltipData | null;
  onDismiss: () => void;
}

export const TooltipOverlay: React.FC<TooltipOverlayProps> = ({ tooltip, onDismiss }) => {
  useEffect(() => {
    if (!tooltip) return;
    const timer = setTimeout(() => {
      onDismiss();
    }, 9000);
    return () => clearTimeout(timer);
  }, [tooltip, onDismiss]);

  if (!tooltip) return null;

  return (
    <div className="tooltip-toast-container" role="status" aria-live="polite">
      <div className="tooltip-toast">
        <div className="tooltip-toast__icon">
          <Sparkles size={18} />
        </div>
        <div className="tooltip-toast__content">
          <div className="tooltip-toast__title">{tooltip.title}</div>
          <div className="tooltip-toast__message">{tooltip.message}</div>
        </div>
        <button
          type="button"
          onClick={onDismiss}
          className="tooltip-toast__close"
          aria-label="Dismiss tip"
        >
          <X size={14} />
        </button>
      </div>
    </div>
  );
};

