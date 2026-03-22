import '@testing-library/jest-dom/vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const authRuntimeState = {
  canUseProtectedRequests: true,
};

vi.mock('../../auth/runtime', () => ({
  useAuthRuntimeStore: Object.assign(
    (selector: (state: typeof authRuntimeState) => unknown) => selector(authRuntimeState),
    { getState: () => authRuntimeState },
  ),
}));

import {
  mockGetProjects,
  mockGetProjectTranscript,
  mockProcessManual,
  mockRecoverProjectTranscript,
  mockSaveTranscript,
  renderSubtitleEditor,
  resetSubtitleEditorMocks,
  storeMock,
  subtitleTranscript,
} from './subtitleEditor.test-helpers';

async function selectProject(projectId: string) {
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', { name: /select project/i }));
  await user.click(screen.getByRole('option', { name: projectId }));
  await waitFor(() => expect(mockGetProjectTranscript).toHaveBeenCalledWith(projectId));
  return user;
}

describe('SubtitleEditor project mode', () => {
  beforeEach(() => {
    authRuntimeState.canUseProtectedRequests = true;
    resetSubtitleEditorMocks();
  });

  it('loads, edits and saves a project transcript', async () => {
    await renderSubtitleEditor();
    const user = await selectProject('proj_1');

    const firstTextarea = await screen.findByDisplayValue('First line');
    await user.clear(firstTextarea);
    await user.type(firstTextarea, 'Updated first line');
    await user.click(screen.getByRole('button', { name: /^save$/i }));

    await waitFor(() => {
      expect(mockSaveTranscript).toHaveBeenCalledWith([
        {
          ...subtitleTranscript[0],
          text: 'Updated first line',
          words: [
            { word: 'Updated', start: 0, end: 4 / 3, score: 1 },
            { word: 'first', start: 4 / 3, end: 8 / 3, score: 1 },
            { word: 'line', start: 8 / 3, end: 4, score: 1 },
          ],
        },
        subtitleTranscript[1],
      ], 'proj_1');
    });

    expect(await screen.findByText(/transcript saved/i)).toBeInTheDocument();
    expect(screen.queryByTestId('render-quality-summary')).not.toBeInTheDocument();
  });

  it('starts manual clip rendering from the selected project range', async () => {
    await renderSubtitleEditor();
    const user = await selectProject('proj_1');

    await user.click(screen.getByRole('button', { name: /render range as clip/i }));

    await waitFor(() => {
      expect(mockProcessManual).toHaveBeenCalledWith({
        animation_type: 'default',
        end_time: 60,
        project_id: 'proj_1',
        start_time: 0,
        style_name: 'HORMOZI',
        transcript: subtitleTranscript,
      });
    });
    expect(storeMock.fetchJobs).toHaveBeenCalled();
  });

  it('seeks the preview video when the selected range changes', async () => {
    await renderSubtitleEditor();
    await selectProject('proj_1');

    const video = document.querySelector('video') as HTMLVideoElement | null;
    expect(video).not.toBeNull();
    expect(video?.currentTime ?? 0).toBe(0);

    const endInput = await screen.findByLabelText(/end/i);
    fireEvent.change(endInput, { target: { value: '30' } });

    expect(video?.currentTime).toBe(30);
  });

  it('keeps the selected range stable while the render job completes and transcript reloads', async () => {
    const view = await renderSubtitleEditor();
    const user = await selectProject('proj_1');
    const { SubtitleEditor } = await import('../../components/SubtitleEditor');

    const endInput = await screen.findByLabelText(/end/i) as HTMLInputElement;
    fireEvent.change(endInput, { target: { value: '30' } });
    expect(endInput.value).toBe('30');
    const transcriptCallCountBeforeCompletion = mockGetProjectTranscript.mock.calls.length;

    await user.click(screen.getByRole('button', { name: /render range as clip/i }));
    storeMock.jobs = [{
      created_at: 1,
      job_id: 'manual_1',
      last_message: 'Manuel render başladı...',
      progress: 66,
      project_id: 'proj_1',
      status: 'completed',
      style: 'HORMOZI',
      timeline: [
        {
          at: '2026-03-22T10:00:00.000Z',
          id: 'manual_1:queued',
          job_id: 'manual_1',
          message: 'Manuel render kuyruğa alındı...',
          progress: 0,
          source: 'api',
          status: 'queued',
        },
        {
          at: '2026-03-22T10:00:03.000Z',
          id: 'manual_1:done',
          job_id: 'manual_1',
          message: 'Manuel render tamamlandı.',
          progress: 100,
          source: 'worker',
          status: 'completed',
        },
      ],
      url: 'proj_1',
    }];

    view.rerender(<SubtitleEditor />);

    await waitFor(() => expect(mockGetProjectTranscript.mock.calls.length).toBeGreaterThan(transcriptCallCountBeforeCompletion));
    expect(screen.getByText(/clip rendered/i)).toBeInTheDocument();
    expect((screen.getByLabelText(/end/i) as HTMLInputElement).value).toBe('30');
    expect(screen.getByText(/editable range/i)).toBeInTheDocument();
  });

  it('sends edited transcript words when creating a clip from the selected range', async () => {
    mockGetProjectTranscript.mockResolvedValue({
      active_job_id: null,
      last_error: null,
      transcript: [
        {
          end: 4,
          start: 0,
          text: 'First line',
          words: [
            { word: 'First', start: 0, end: 1.5, score: 0.8 },
            { word: 'line', start: 1.5, end: 4, score: 0.9 },
          ],
        },
      ],
      transcript_status: 'ready',
    });

    await renderSubtitleEditor();
    const user = await selectProject('proj_1');
    const firstTextarea = await screen.findByDisplayValue('First line');
    await user.clear(firstTextarea);
    await user.type(firstTextarea, 'Fresh copy');
    await user.click(screen.getByRole('button', { name: /render range as clip/i }));

    await waitFor(() => {
      expect(mockProcessManual).toHaveBeenCalledWith({
        animation_type: 'default',
        end_time: 60,
        project_id: 'proj_1',
        start_time: 0,
        style_name: 'HORMOZI',
        transcript: [
          {
            end: 4,
            start: 0,
            text: 'Fresh copy',
            words: [
              { word: 'Fresh', start: 0, end: 2, score: 1 },
              { word: 'copy', start: 2, end: 4, score: 1 },
            ],
          },
        ],
      });
    });
  });

  it('shows a pending state while the project transcript is still processing', async () => {
    mockGetProjectTranscript.mockResolvedValue({
      active_job_id: 'upload_1',
      last_error: null,
      transcript: [],
      transcript_status: 'pending',
    });
    storeMock.jobs = [{
      created_at: 1,
      job_id: 'upload_1',
      last_message: 'Transkripsiyon başladı...',
      progress: 42,
      status: 'processing',
      style: 'UPLOAD',
      url: '',
    }];

    await renderSubtitleEditor();
    await selectProject('proj_1');

    expect(await screen.findByText(/transcript is preparing/i)).toBeInTheDocument();
    const statusCard = await screen.findByTestId('subtitle-processing-status');
    expect(within(statusCard).getAllByText(/transkripsiyon başladı/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /retry project transcript/i })).not.toBeInTheDocument();
  });

  it('offers one-click retry when the project transcript failed', async () => {
    mockGetProjectTranscript.mockResolvedValue({
      active_job_id: null,
      last_error: 'Transkripsiyon çöktü',
      transcript: [],
      transcript_status: 'failed',
    });

    await renderSubtitleEditor();
    const user = await selectProject('proj_1');

    expect(await screen.findByText(/transkripsiyon çöktü/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /retry project transcript/i }));

    await waitFor(() => {
      expect(mockRecoverProjectTranscript).toHaveBeenCalledWith({ project_id: 'proj_1' });
    });
  });

});

describe('SubtitleEditor project source states', () => {
  beforeEach(() => {
    authRuntimeState.canUseProtectedRequests = true;
    resetSubtitleEditorMocks();
  });

  it('shows an unknown-state error instead of a healthy empty state when project listing fails', async () => {
    mockGetProjects.mockResolvedValue({
      error: 'Projeler alinamadi',
      projects: [],
      status: 'unknown',
    });

    await renderSubtitleEditor();

    expect(await screen.findByText(/projeler alinamadi/i)).toBeInTheDocument();
    expect(screen.queryByText(/no projects yet/i)).not.toBeInTheDocument();
  });

  it('shows a degraded warning while keeping the last synced project list usable', async () => {
    mockGetProjects.mockResolvedValue({
      error: 'Sunucuya baglanirken hata olustu',
      projects: [{
        active_job_id: null,
        has_master: true,
        has_transcript: true,
        id: 'proj_cached',
        last_error: null,
        transcript_status: 'ready',
      }],
      status: 'degraded',
    });

    await renderSubtitleEditor();
    const user = userEvent.setup();

    expect(await screen.findByText(/showing the last synced project list/i)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /select project/i }));
    expect(screen.getByRole('option', { name: 'proj_cached' })).toBeInTheDocument();
  });
});
