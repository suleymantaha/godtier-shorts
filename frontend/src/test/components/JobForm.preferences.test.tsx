import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { mockStart, renderJobForm } from './jobForm.test-helpers';

describe('JobForm preferences', () => {
  it('sends default num_clips and auto duration on submit', async () => {
    mockStart.mockResolvedValueOnce({ status: 'queued', job_id: 'test' });
    const user = userEvent.setup();
    await renderJobForm();

    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /initialize sequence/i }));

    expect(mockStart).toHaveBeenCalledWith(expect.objectContaining({
      youtube_url: 'https://youtube.com/watch?v=test123',
      num_clips: expect.any(Number),
      auto_mode: true,
      duration_min: 120,
      duration_max: 180,
    }));
  });

  it('persists and reuses AI core engine selection', async () => {
    mockStart.mockResolvedValueOnce({ status: 'queued', job_id: 'test' });
    window.localStorage.setItem('godtier-job-form-preferences', JSON.stringify({ engine: 'cloud' }));
    const user = userEvent.setup();
    await renderJobForm();

    expect(screen.getByLabelText(/ai core engine/i)).toHaveTextContent(/cloud/i);
    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /initialize sequence/i }));

    expect(mockStart).toHaveBeenCalledWith(expect.objectContaining({ ai_engine: 'cloud' }));
  });
});
