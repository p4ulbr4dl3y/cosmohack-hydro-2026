import React from 'react';
import { STATUS_COLORS } from '../../lib/colors';

interface StatusBadgeProps {
  status: 'active' | 'baseline' | 'no_optical' | 'weak_signal';
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className = '' }) => {
  const cfg = STATUS_COLORS[status] || STATUS_COLORS.active;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold tracking-wide uppercase ${className}`}
      style={{
        backgroundColor: cfg.bg,
        color: cfg.text,
      }}
    >
      {cfg.label}
    </span>
  );
};
