export interface WatchConfig {
  binaryInterval: number;
  interval: number;
  usePolling: true;
}

function readBooleanEnv(value: string | undefined): boolean {
  if (!value) {
    return false;
  }

  const normalized = value.trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on';
}

function readPositiveNumberEnv(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export function resolveWatchConfig(env: NodeJS.ProcessEnv = process.env): WatchConfig | undefined {
  if (!readBooleanEnv(env.CHOKIDAR_USEPOLLING)) {
    return undefined;
  }

  const interval = readPositiveNumberEnv(env.CHOKIDAR_INTERVAL, 300);
  return {
    binaryInterval: Math.max(interval, 300),
    interval,
    usePolling: true,
  };
}
