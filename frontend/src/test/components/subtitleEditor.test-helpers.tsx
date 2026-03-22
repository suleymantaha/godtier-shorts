import { act, render } from '@testing-library/react';
import { vi } from 'vitest';

import { SUBTITLE_SESSION_STORAGE_KEY } from '../../app/helpers';
import type { Clip, Job, Segment } from '../../types';

export const storeMock = {
  fetchJobs: vi.fn(),
  jobs: [] as Job[],
};

export const mockGetProjects = vi.fn();
export const mockGetProjectTranscript = vi.fn();
export const mockSaveTranscript = vi.fn();
export const mockProcessManual = vi.fn();
export const mockRecoverProjectTranscript = vi.fn();
export const mockReburn = vi.fn();
export const mockRecoverClipTranscript = vi.fn();
export const mockListClips = vi.fn();
export const mockGetClipTranscript = vi.fn();
export const mockGetFreshToken = vi.fn();

vi.mock('../../store/useJobStore', () => ({
  useJobStore: () => storeMock,
}));

vi.mock('../../api/client', () => ({
  clipsApi: {
    getTranscript: (...args: unknown[]) => mockGetClipTranscript(...args),
    list: (...args: unknown[]) => mockListClips(...args),
  },
  getFreshToken: (...args: unknown[]) => mockGetFreshToken(...args),
  editorApi: {
    getProjects: (...args: unknown[]) => mockGetProjects(...args),
    getTranscript: (...args: unknown[]) => mockGetProjectTranscript(...args),
    processManual: (...args: unknown[]) => mockProcessManual(...args),
    recoverProjectTranscript: (...args: unknown[]) => mockRecoverProjectTranscript(...args),
    recoverClipTranscript: (...args: unknown[]) => mockRecoverClipTranscript(...args),
    reburn: (...args: unknown[]) => mockReburn(...args),
    saveTranscript: (...args: unknown[]) => mockSaveTranscript(...args),
  },
}));

export const subtitleProjects = [
  { active_job_id: null, has_master: true, has_transcript: true, id: 'proj_1', last_error: null, transcript_status: 'ready' },
  { active_job_id: 'upload_1', has_master: true, has_transcript: false, id: 'proj_hidden', last_error: null, transcript_status: 'pending' },
];

export const subtitleClip: Clip = {
  created_at: Date.now(),
  has_transcript: true,
  name: 'clip_1.mp4',
  project: 'proj_1',
  url: '/api/projects/proj_1/files/clip/clip_1.mp4',
};

export const subtitleTranscript: Segment[] = [
  { end: 4, start: 0, text: 'First line', words: [] },
  { end: 9, start: 5, text: 'Second line', words: [] },
];

export function resetSubtitleEditorMocks() {
  vi.clearAllMocks();
  window.localStorage.removeItem(SUBTITLE_SESSION_STORAGE_KEY);
  storeMock.jobs = [];
  storeMock.fetchJobs.mockResolvedValue(undefined);
  mockGetProjects.mockResolvedValue({ error: null, projects: subtitleProjects, status: 'good' });
  mockGetProjectTranscript.mockResolvedValue({
    active_job_id: null,
    last_error: null,
    transcript: subtitleTranscript,
    transcript_status: 'ready',
  });
  mockSaveTranscript.mockResolvedValue({ status: 'success' });
  mockProcessManual.mockResolvedValue({ job_id: 'manual_1', status: 'started' });
  mockRecoverProjectTranscript.mockResolvedValue({ job_id: 'projecttranscript_1', status: 'started' });
  mockRecoverClipTranscript.mockResolvedValue({ job_id: 'cliprecover_1', status: 'started' });
  mockReburn.mockResolvedValue({ job_id: 'reburn_1', status: 'started' });
  mockListClips.mockResolvedValue({ clips: [subtitleClip] });
  mockGetClipTranscript.mockResolvedValue({
    active_job_id: null,
    capabilities: {
      can_recover_from_project: true,
      can_transcribe_source: true,
      has_clip_metadata: true,
      has_clip_transcript: true,
      has_raw_backup: true,
      project_has_transcript: true,
      resolved_project_id: 'proj_1',
    },
    last_error: null,
    recommended_strategy: null,
    transcript: subtitleTranscript,
    transcript_status: 'ready',
  });
  mockGetFreshToken.mockResolvedValue('token-123');
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    blob: async () => new Blob(['video'], { type: 'video/mp4' }),
    ok: true,
    status: 200,
  } as Response));
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:subtitle-video');
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
}

export async function renderSubtitleEditor(props?: Record<string, unknown>) {
  const { SubtitleEditor } = await import('../../components/SubtitleEditor');
  let view: ReturnType<typeof render> | null = null;

  await act(async () => {
    view = render(<SubtitleEditor {...props} />);
  });

  return view!;
}
