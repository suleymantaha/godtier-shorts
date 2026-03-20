import { describe, expect, it } from 'vitest';

import {
  buildAutoCutUploadPayload,
  deriveAutoCutJobState,
  getMarkerAdditionResult,
  getRangeForLoadedMetadata,
} from '../../components/autoCutEditor/helpers';
import type { Job } from '../../types';

function buildJob(overrides: Partial<Job>): Job {
  return {
    created_at: Date.now(),
    job_id: 'job_1',
    last_message: 'processing',
    progress: 50,
    status: 'processing',
    style: 'TIKTOK',
    url: '/video',
    ...overrides,
  };
}

describe('autoCutEditor job helpers', () => {
  it('derives completed job state and fallback result url', () => {
    const state = deriveAutoCutJobState({
      currentJob: buildJob({
        clip_name: 'clip_1.mp4',
        project_id: 'proj_1',
        status: 'completed',
      }),
      currentJobId: 'job_1',
      currentJobMissing: false,
      isSubmitting: false,
      pendingOutputUrl: null,
      requestError: null,
    });

    expect(state.hasTerminalJob).toBe(true);
    expect(state.processing).toBe(false);
    expect(state.resultUrl).toBe('/api/projects/proj_1/shorts/clip_1.mp4');
  });

  it('prefers explicit request errors over job status details', () => {
    const state = deriveAutoCutJobState({
      currentJob: buildJob({
        error: 'worker failed',
        last_message: 'job failed',
        status: 'error',
      }),
      currentJobId: 'job_1',
      currentJobMissing: false,
      isSubmitting: false,
      pendingOutputUrl: null,
      requestError: 'Manual cut failed: 500',
    });

    expect(state.errorMessage).toBe('Manual cut failed: 500');
    expect(state.processing).toBe(false);
  });

  it('preserves the last known result url when a completed job disappears from sync', () => {
    const state = deriveAutoCutJobState({
      currentJob: null,
      currentJobId: 'job_1',
      currentJobMissing: true,
      isSubmitting: false,
      pendingOutputUrl: '/api/projects/proj_1/shorts/clip_1.mp4',
      requestError: null,
    });

    expect(state.hasTerminalJob).toBe(false);
    expect(state.processing).toBe(false);
    expect(state.resultUrl).toBe('/api/projects/proj_1/shorts/clip_1.mp4');
  });

});

describe('autoCutEditor payload helpers', () => {
  it('builds sorted cut points for manual markers', () => {
    const payload = buildAutoCutUploadPayload({
      animationType: 'default',
      cutAsShort: true,
      duration: 180,
      endTime: 42,
      layout: 'split',
      markers: [30, 12, 70],
      numClips: 3,
      skipSubtitles: false,
      startTime: 5,
      style: 'TIKTOK',
    });

    expect(payload.cut_points).toEqual([5, 12, 30, 42]);
    expect(payload.animation_type).toBe('default');
    expect(payload.layout).toBe('split');
    expect(payload.num_clips).toBe(3);
    expect(payload.start_time).toBe(5);
    expect(payload.end_time).toBe(42);
  });

  it('uses the full video for AI clip generation without manual markers', () => {
    const payload = buildAutoCutUploadPayload({
      animationType: 'default',
      cutAsShort: true,
      duration: 95,
      endTime: 35,
      layout: 'auto',
      markers: [],
      numClips: 4,
      skipSubtitles: false,
      startTime: 10,
      style: 'HORMOZI',
    });

    expect(payload.cut_points).toBeUndefined();
    expect(payload.animation_type).toBe('default');
    expect(payload.layout).toBe('auto');
    expect(payload.num_clips).toBe(4);
    expect(payload.start_time).toBe(0);
    expect(payload.end_time).toBe(95);
  });

});

describe('autoCutEditor marker helpers', () => {
  it('rejects markers outside the selected range', () => {
    const result = getMarkerAdditionResult({
      currentTime: 5,
      endTime: 20,
      markers: [8],
      startTime: 5,
    });

    expect(result.markers).toEqual([8]);
    expect(result.feedback).toMatch(/Once videoyu oynatip/i);
  });

  it('adds a new marker in sorted order when valid', () => {
    const result = getMarkerAdditionResult({
      currentTime: 14,
      endTime: 40,
      markers: [20, 8],
      startTime: 5,
    });

    expect(result.markers).toEqual([8, 14, 20]);
    expect(result.feedback).toBe('Kesim noktasi eklendi.');
  });

});

describe('autoCutEditor metadata helpers', () => {
  it('clamps the selected range to loaded metadata duration', () => {
    const range = getRangeForLoadedMetadata(24, 60, 90);

    expect(range.startTime).toBe(23.5);
    expect(range.endTime).toBe(24);
  });
});
