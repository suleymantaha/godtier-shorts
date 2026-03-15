import type { FC } from 'react';

const TONE_CLASSNAMES = {
  danger: 'border-red-500/30 bg-red-500/10 text-red-100',
  info: 'border-sky-500/30 bg-sky-500/10 text-sky-100',
  warning: 'border-amber-500/30 bg-amber-500/10 text-amber-100',
} as const;

interface SystemStatusBannerProps {
  message: string;
  title: string;
  tone: keyof typeof TONE_CLASSNAMES;
}

export const SystemStatusBanner: FC<SystemStatusBannerProps> = ({
  message,
  title,
  tone,
}) => (
  <div
    role="status"
    aria-live="polite"
    className={`rounded-2xl border px-4 py-3 text-sm shadow-lg backdrop-blur ${TONE_CLASSNAMES[tone]}`}
  >
    <p className="text-[11px] font-mono uppercase tracking-[0.24em] opacity-80">{title}</p>
    <p className="mt-1 leading-6">{message}</p>
  </div>
);
