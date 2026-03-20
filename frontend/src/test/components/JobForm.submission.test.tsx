import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { mockFetchJobs, mockRegisterQueuedJob, mockStart, renderJobForm } from './jobForm.test-helpers';

describe('JobForm submission flow', () => {
  it('shows error message on failed submit', async () => {
    const user = userEvent.setup();
    await renderJobForm();

    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /initialize sequence/i }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('disables style select and sends skip_subtitles when subtitles are skipped', async () => {
    mockStart.mockResolvedValueOnce({ status: 'queued', job_id: 'test' });
    const user = userEvent.setup();
    await renderJobForm();

    const toggle = screen.getByRole('switch', { name: /altyaz/i });
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByLabelText(/visual style/i)).toBeDisabled();

    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /initialize sequence/i }));

    expect(mockStart).toHaveBeenCalledWith(expect.objectContaining({ skip_subtitles: true }));
  });

  it('refreshes jobs and clears the url after successful submit', async () => {
    mockStart.mockResolvedValueOnce({ status: 'queued', job_id: 'test', message: 'queued now' });
    const user = userEvent.setup();
    await renderJobForm();

    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /initialize sequence/i }));

    await waitFor(() => expect(mockFetchJobs).toHaveBeenCalledTimes(1));
    expect(mockRegisterQueuedJob).toHaveBeenCalledWith({
      job_id: 'test',
      message: 'queued now',
      style: 'TIKTOK',
      url: 'https://youtube.com/watch?v=test123',
    });
    expect(screen.getByLabelText(/source feed url/i)).toHaveValue('');
  });

  it('submits custom manual durations when auto mode is disabled', async () => {
    mockStart.mockResolvedValueOnce({ status: 'queued', job_id: 'test' });
    const user = userEvent.setup();
    await renderJobForm();

    await user.click(screen.getByRole('switch', { name: /otomatik mod/i }));
    fireEvent.change(screen.getByLabelText(/min sure/i), { target: { value: '45' } });
    fireEvent.change(screen.getByLabelText(/max sure/i), { target: { value: '90' } });
    await user.type(screen.getByLabelText(/source feed url/i), 'https://youtube.com/watch?v=test123');
    await user.click(screen.getByRole('button', { name: /initialize sequence/i }));

    expect(mockStart).toHaveBeenCalledWith(expect.objectContaining({
      auto_mode: false,
      duration_min: 45,
      duration_max: 90,
    }));
  });
});
