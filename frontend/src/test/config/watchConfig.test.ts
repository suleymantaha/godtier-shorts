import { describe, expect, it } from 'vitest';

import { resolveWatchConfig } from '../../../build/watchConfig';

describe('resolveWatchConfig', () => {
  it('returns undefined when polling is disabled', () => {
    expect(resolveWatchConfig({} as NodeJS.ProcessEnv)).toBeUndefined();
    expect(resolveWatchConfig({ CHOKIDAR_USEPOLLING: '0' } as NodeJS.ProcessEnv)).toBeUndefined();
  });

  it('enables polling with sane defaults', () => {
    expect(resolveWatchConfig({ CHOKIDAR_USEPOLLING: '1' } as NodeJS.ProcessEnv)).toEqual({
      binaryInterval: 300,
      interval: 300,
      usePolling: true,
    });
  });

  it('respects the configured polling interval', () => {
    expect(resolveWatchConfig({
      CHOKIDAR_INTERVAL: '450',
      CHOKIDAR_USEPOLLING: 'true',
    } as NodeJS.ProcessEnv)).toEqual({
      binaryInterval: 450,
      interval: 450,
      usePolling: true,
    });
  });
});
