/**
 * Saniyeyi MM:SS.s formatına çevirir.
 */
export function toTimeStr(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const sec = (seconds % 60).toFixed(1);
  return `${m}:${sec.padStart(4, '0')}`;
}
