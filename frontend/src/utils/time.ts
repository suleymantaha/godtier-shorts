import { tSafe } from '../i18n';

/**
 * Saniyeyi MM:SS.s formatına çevirir.
 */
export function toTimeStr(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const sec = (seconds % 60).toFixed(1);
  return `${m}:${sec.padStart(4, '0')}`;
}

/**
 * Saniyeyi kısa etiket olarak verir: 12.3s
 */
export function toSecondsStr(seconds: number): string {
  return tSafe('common.time.secondsShort', {
    value: Math.max(0, seconds).toFixed(1),
  });
}

/**
 * Saniyeyi dakika etiketi olarak verir: 1.5 dk
 */
export function toMinutesStr(seconds: number): string {
  return tSafe('common.time.minutesShort', {
    value: (Math.max(0, seconds) / 60).toFixed(1),
  });
}
