import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { VideoControls } from '../../../components/ui/VideoControls';

describe('VideoControls', () => {
  it('is always visible (not hover-only)', () => {
    render(<VideoControls isPlaying={false} onTogglePlay={() => {}} />);
    const btn = screen.getByRole('button', { name: /play|oynat|duraklat|pause/i });
    expect(btn).toBeVisible();
  });

  it('shows play icon when paused', () => {
    render(<VideoControls isPlaying={false} onTogglePlay={() => {}} />);
    expect(screen.getByRole('button', { name: /play|oynat/i })).toBeInTheDocument();
  });

  it('shows pause icon when playing', () => {
    render(<VideoControls isPlaying={true} onTogglePlay={() => {}} />);
    expect(screen.getByRole('button', { name: /pause|duraklat/i })).toBeInTheDocument();
  });

  it('calls onTogglePlay on click', async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<VideoControls isPlaying={false} onTogglePlay={handler} />);
    await user.click(screen.getByRole('button', { name: /play|oynat/i }));
    expect(handler).toHaveBeenCalledOnce();
  });

  it('is keyboard accessible', async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<VideoControls isPlaying={false} onTogglePlay={handler} />);
    const btn = screen.getByRole('button', { name: /play|oynat/i });
    btn.focus();
    await user.keyboard('{Enter}');
    expect(handler).toHaveBeenCalledOnce();
  });
});
