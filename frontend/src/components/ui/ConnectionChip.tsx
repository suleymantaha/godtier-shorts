import type { FC } from 'react';
import type { AppErrorCode } from '../../api/errors';
import type { WsStatus } from '../../types';

const STATUS_CONFIG: Record<WsStatus, { dot: string; label: string }> = {
  connected:    { dot: 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]', label: 'NEURAL_BACKEND:ONLINE' },
  connecting:   { dot: 'bg-yellow-500 animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.4)]', label: 'CONNECTING...' },
  reconnecting: { dot: 'bg-yellow-500 animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.4)]', label: 'RECONNECTING...' },
  disconnected: { dot: 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]', label: 'BACKEND:OFFLINE' },
};

interface ConnectionChipProps {
  backendAuthStatus?: 'fresh' | 'paused' | 'refreshing';
  isOnline?: boolean;
  pauseReason?: AppErrorCode | null;
  status: WsStatus;
}

function resolveStatusDisplay({
  backendAuthStatus = 'fresh',
  isOnline = true,
  pauseReason = null,
  status,
}: ConnectionChipProps) {
  if (!isOnline) {
    return {
      dot: 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]',
      label: 'NETWORK:OFFLINE',
    };
  }

  if (backendAuthStatus === 'refreshing') {
    return {
      dot: 'bg-yellow-500 animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.4)]',
      label: 'AUTH:REFRESHING',
    };
  }

  if (backendAuthStatus === 'paused') {
    const label = pauseReason === 'token_expired'
      ? 'AUTH:EXPIRED'
      : 'AUTH:PAUSED';

    return {
      dot: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]',
      label,
    };
  }

  return STATUS_CONFIG[status];
}

export const ConnectionChip: FC<ConnectionChipProps> = (props) => {
  const { dot, label } = resolveStatusDisplay(props);

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
