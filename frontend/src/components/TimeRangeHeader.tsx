import { Clock } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { toMinutesStr, toSecondsStr, toTimeStr } from '../utils/time';

interface TimeRangeHeaderProps {
  endTime: number;
  extraLabel?: string;
  startTime: number;
  title: string;
}

export function TimeRangeHeader({
  endTime,
  extraLabel,
  startTime,
  title,
}: TimeRangeHeaderProps) {
  const { t } = useTranslation();
  const selectedDuration = Math.max(0, endTime - startTime);

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs font-mono uppercase tracking-widest text-muted-foreground">
      <Clock className="w-3 h-3" />
      <span>{title}</span>
      <span className="ml-auto text-right text-primary font-semibold leading-relaxed">
        {toSecondsStr(startTime)} - {toSecondsStr(endTime)}
        <span className="text-muted-foreground ml-1">({toTimeStr(startTime)} - {toTimeStr(endTime)})</span>
        <span className="text-muted-foreground ml-1">[{t('timeRangeHeader.totalLabel', {
          minutes: toMinutesStr(selectedDuration),
          seconds: toSecondsStr(selectedDuration),
        })}]</span>
        {extraLabel ? <span className="text-muted-foreground ml-1">{extraLabel}</span> : null}
      </span>
    </div>
  );
}
