import { beforeEach, describe, expect, it } from 'vitest';

import {
  DEFAULT_AUTO_DURATION_RANGE,
  buildStartJobPayload,
  clampClipCount,
  clampDurationSeconds,
  readInitialEngine,
  resolveDurationRange,
} from '../../components/jobForm/helpers';

describe('jobForm helpers', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('reads a valid stored engine preference', () => {
    window.localStorage.setItem('godtier-job-form-preferences', JSON.stringify({ engine: 'cloud' }));

    expect(readInitialEngine()).toBe('cloud');
  });

  it('falls back to cloud engine for invalid stored values', () => {
    window.localStorage.setItem('godtier-job-form-preferences', JSON.stringify({ engine: 'unsupported' }));

    expect(readInitialEngine()).toBe('cloud');
  });

  it('clamps clip count and durations into allowed bounds', () => {
    expect(clampClipCount(0)).toBe(1);
    expect(clampClipCount(22)).toBe(20);
    expect(clampDurationSeconds(20)).toBe(30);
    expect(clampDurationSeconds(450)).toBe(300);
  });

  it('uses default auto duration range when auto mode is enabled', () => {
    expect(resolveDurationRange(true, 45, 90)).toEqual(DEFAULT_AUTO_DURATION_RANGE);
  });

  it('builds payload with custom duration and clamped clip count', () => {
    expect(buildStartJobPayload({
      animationType: 'default',
      autoMode: false,
      durationMax: 95,
      durationMin: 45,
      engine: 'cloud',
      layout: 'auto',
      numClips: 99,
      resolution: '1080p',
      skipSubtitles: true,
      style: 'TIKTOK',
      url: 'https://youtube.com/watch?v=test123',
    })).toEqual(expect.objectContaining({
      ai_engine: 'cloud',
      animation_type: 'default',
      auto_mode: false,
      duration_max: 95,
      duration_min: 45,
      force_reanalyze: false,
      force_rerender: false,
      layout: 'auto',
      num_clips: 20,
      resolution: '1080p',
      skip_subtitles: true,
      style_name: 'TIKTOK',
      youtube_url: 'https://youtube.com/watch?v=test123',
    }));
  });
});
