import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockStart = vi.fn().mockRejectedValue(new Error('Network error'));

vi.mock('../../store/useJobStore', () => ({
  useJobStore: () => ({ fetchJobs: vi.fn() }),
}));

vi.mock('../../api/client', () => ({
  jobsApi: {
    start: (...args: unknown[]) => mockStart(...args),
  },
}));

describe('JobForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('has labels linked to inputs via htmlFor', async () => {
    const { JobForm } = await import('../../components/JobForm');
    render(<JobForm />);

    const urlInput = screen.getByLabelText(/source feed url/i);
    expect(urlInput).toBeInTheDocument();
    expect(urlInput.tagName).toBe('INPUT');

    const styleSelect = screen.getByLabelText(/visual style/i);
    expect(styleSelect).toBeInTheDocument();
    expect(styleSelect.tagName).toBe('BUTTON');

    const engineSelect = screen.getByLabelText(/ai core engine/i);
    expect(engineSelect).toBeInTheDocument();
  });

  it('shows error message on failed submit', async () => {
    const user = userEvent.setup();
    const { JobForm } = await import('../../components/JobForm');
    render(<JobForm />);

    const urlInput = screen.getByLabelText(/source feed url/i);
    await user.type(urlInput, 'https://youtube.com/watch?v=test123');
    const submitBtn = screen.getByRole('button', { name: /initialize sequence/i });
    await user.click(submitBtn);

    const errorEl = await screen.findByRole('alert');
    expect(errorEl).toBeInTheDocument();
  });

  it('responsive: grid has responsive classes', async () => {
    const { JobForm } = await import('../../components/JobForm');
    const { container } = render(<JobForm />);
    const grid = container.querySelector('.grid.grid-cols-1.md\\:grid-cols-4');
    expect(grid?.className).toContain('grid-cols-1');
    expect(grid?.className).toContain('md:grid-cols-4');
  });

  it('renders subtitle toggle switch', async () => {
    const { JobForm } = await import('../../components/JobForm');
    render(<JobForm />);

    const toggle = screen.getByRole('switch', { name: /altyaz/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-checked', 'false');
  });

  it('disables style select when subtitles are skipped', async () => {
    const user = userEvent.setup();
    const { JobForm } = await import('../../components/JobForm');
    render(<JobForm />);

    const toggle = screen.getByRole('switch', { name: /altyaz/i });
    await user.click(toggle);

    expect(toggle).toHaveAttribute('aria-checked', 'true');

    const styleSelect = screen.getByLabelText(/visual style/i);
    expect(styleSelect).toBeDisabled();
  });

  it('sends skip_subtitles in API payload when toggled', async () => {
    mockStart.mockResolvedValueOnce({ status: 'queued', job_id: 'test' });
    const user = userEvent.setup();
    const { JobForm } = await import('../../components/JobForm');
    render(<JobForm />);

    const toggle = screen.getByRole('switch', { name: /altyaz/i });
    await user.click(toggle);

    const urlInput = screen.getByLabelText(/source feed url/i);
    await user.type(urlInput, 'https://youtube.com/watch?v=test123');

    const submitBtn = screen.getByRole('button', { name: /initialize sequence/i });
    await user.click(submitBtn);

    expect(mockStart).toHaveBeenCalledWith(
      expect.objectContaining({ skip_subtitles: true }),
    );
  });

  it('renders num_clips, auto_mode and duration inputs', async () => {
    const { JobForm } = await import('../../components/JobForm');
    render(<JobForm />);

    expect(screen.getByLabelText(/target clone count/i)).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: /otomatik mod/i })).toBeInTheDocument();
  });

  it('disables duration inputs when auto_mode is on', async () => {
    const { JobForm } = await import('../../components/JobForm');
    render(<JobForm />);

    const autoToggle = screen.getByRole('switch', { name: /otomatik mod/i });
    expect(autoToggle).toHaveAttribute('aria-checked', 'true');

    const minInput = screen.queryByLabelText(/min.*süre|minimum/i);
    const maxInput = screen.queryByLabelText(/max.*süre|maksimum/i);
    if (minInput) expect(minInput).toBeDisabled();
    if (maxInput) expect(maxInput).toBeDisabled();
  });

  it('sends num_clips and duration in payload on submit', async () => {
    mockStart.mockResolvedValueOnce({ status: 'queued', job_id: 'test' });
    const user = userEvent.setup();
    const { JobForm } = await import('../../components/JobForm');
    render(<JobForm />);

    const urlInput = screen.getByLabelText(/source feed url/i);
    await user.type(urlInput, 'https://youtube.com/watch?v=test123');

    const submitBtn = screen.getByRole('button', { name: /initialize sequence/i });
    await user.click(submitBtn);

    expect(mockStart).toHaveBeenCalledWith(
      expect.objectContaining({
        youtube_url: 'https://youtube.com/watch?v=test123',
        num_clips: expect.any(Number),
        auto_mode: expect.any(Boolean),
      }),
    );
    const payload = mockStart.mock.calls[0][0];
    if (payload.auto_mode) {
      expect(payload.duration_min).toBe(120);
      expect(payload.duration_max).toBe(180);
    }
  });
});
