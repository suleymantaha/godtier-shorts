import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';

import {
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
  await user.click(screen.getByRole('button', { name: /proje seçin/i }));
  await user.click(screen.getByRole('option', { name: projectId }));
  await waitFor(() => expect(mockGetProjectTranscript).toHaveBeenCalledWith(projectId));
  return user;
}

describe('SubtitleEditor project mode', () => {
  beforeEach(() => {
    resetSubtitleEditorMocks();
  });

  it('loads, edits and saves a project transcript', async () => {
    await renderSubtitleEditor();
    const user = await selectProject('proj_1');

    const firstTextarea = await screen.findByDisplayValue('First line');
    await user.clear(firstTextarea);
    await user.type(firstTextarea, 'Updated first line');
    await user.click(screen.getByRole('button', { name: /^kaydet$/i }));

    await waitFor(() => {
      expect(mockSaveTranscript).toHaveBeenCalledWith([
        { ...subtitleTranscript[0], text: 'Updated first line' },
        subtitleTranscript[1],
      ], 'proj_1');
    });

    expect(await screen.findByText(/transcript kaydedildi/i)).toBeInTheDocument();
  });

  it('starts manual clip rendering from the selected project range', async () => {
    await renderSubtitleEditor();
    const user = await selectProject('proj_1');

    await user.click(screen.getByRole('button', { name: /aralığı klip olarak üret/i }));

    await waitFor(() => {
      expect(mockProcessManual).toHaveBeenCalledWith({
        end_time: 60,
        project_id: 'proj_1',
        start_time: 0,
        style_name: 'HORMOZI',
        transcript: subtitleTranscript,
      });
    });
    expect(storeMock.fetchJobs).toHaveBeenCalled();
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

    expect(await screen.findByText(/transkript hazirlaniyor/i)).toBeInTheDocument();
    expect(screen.getByText(/transkripsiyon başladı/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /transcripti yeniden cikar/i })).not.toBeInTheDocument();
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
    await user.click(screen.getByRole('button', { name: /transcripti yeniden cikar/i }));

    await waitFor(() => {
      expect(mockRecoverProjectTranscript).toHaveBeenCalledWith({ project_id: 'proj_1' });
    });
  });
});
