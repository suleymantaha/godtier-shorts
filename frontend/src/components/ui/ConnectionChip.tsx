import type { FC } from 'react';
import type { WsStatus } from '../../types';

const STATUS_CONFIG: Record<WsStatus, { dot: string; label: string }> = {
  connected:    { dot: 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]', label: 'NEURAL_BACKEND:ONLINE' },
  connecting:   { dot: 'bg-yellow-500 animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.4)]', label: 'CONNECTING...' },
  reconnecting: { dot: 'bg-yellow-500 animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.4)]', label: 'RECONNECTING...' },
  disconnected: { dot: 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]', label: 'BACKEND:OFFLINE' },
};

interface ConnectionChipProps {
  status: WsStatus;
}

export const ConnectionChip: FC<ConnectionChipProps> = ({ status }) => {
  const { dot, label } = STATUS_CONFIG[status];

  return (
    <div
      className="flex items-center gap-2"
      role="status"
      aria-live="polite"
      aria-label={`Backend durumu: ${label}`}
    >
      <div className={`w-2 h-2 rounded-full ${dot}`} />
      <span className="text-[11px] font-mono">{label}</span>
    </div>
  );
};
