import type { FC } from 'react';
import type { AppErrorCode } from '../../api/errors';
import type { WsStatus } from '../../types';
import { useTranslation } from 'react-i18next';

const STATUS_CONFIG: Record<WsStatus, { dot: string; label: string }> = {
  connected:    { dot: 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]', label: 'connectionChip.labels.online' },
  connecting:   { dot: 'bg-yellow-500 animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.4)]', label: 'connectionChip.labels.connecting' },
  reconnecting: { dot: 'bg-yellow-500 animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.4)]', label: 'connectionChip.labels.reconnecting' },
  disconnected: { dot: 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]', label: 'connectionChip.labels.backendOffline' },
};

interface ConnectionChipProps {
  backendAuthStatus?: 'fresh' | 'paused' | 'refreshing';
  canUseProtectedRequests?: boolean;
  isOnline?: boolean;
  pauseReason?: AppErrorCode | null;
  status: WsStatus;
}

function resolveStatusDisplay({
  backendAuthStatus = 'fresh',
  canUseProtectedRequests = false,
  isOnline = true,
  pauseReason = null,
  status,
}: ConnectionChipProps) {
  if (!isOnline) {
    return {
      dot: 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]',
      label: 'connectionChip.labels.networkOffline',
    };
  }

  if (backendAuthStatus === 'refreshing') {
    return {
      dot: 'bg-yellow-500 animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.4)]',
      label: 'connectionChip.labels.authRefreshing',
    };
  }

  if (backendAuthStatus === 'paused') {
    const label = pauseReason === 'token_expired'
      ? 'connectionChip.labels.authExpired'
      : canUseProtectedRequests
        ? 'connectionChip.labels.authFallback'
        : 'connectionChip.labels.authPaused';

    return {
      dot: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.6)]',
      label,
    };
  }

  return STATUS_CONFIG[status];
}

export const ConnectionChip: FC<ConnectionChipProps> = (props) => {
  const { t } = useTranslation();
  const { dot, label } = resolveStatusDisplay(props);
  const translatedLabel = t(label);

  return (
    <div
      className="flex items-center gap-2"
      role="status"
      aria-live="polite"
      aria-label={t('connectionChip.ariaLabel', { label: translatedLabel })}
    >
      <div className={`w-2 h-2 rounded-full ${dot}`} />
      <span className="text-[11px] font-mono">{translatedLabel}</span>
    </div>
  );
};
