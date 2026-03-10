import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { VideoOverlay } from '../../components/VideoOverlay';

const baseProps = {
  currentTime: 1.5,
  transcript: [{ text: 'Hello', start: 1, end: 2, words: [] }],
  style: 'TIKTOK' as const,
  centerX: 0.5,
  onCropChange: vi.fn(),
};

describe('VideoOverlay', () => {
  it('shows current subtitle text', () => {
    render(<VideoOverlay {...baseProps} />);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('renders crop hint always visible', () => {
    render(<VideoOverlay {...baseProps} />);
    expect(screen.getByText(/crop/i)).toBeVisible();
  });

  it('handles touch events for crop', () => {
    const onCropChange = vi.fn();
    const { container } = render(<VideoOverlay {...baseProps} onCropChange={onCropChange} />);
    const overlay = container.firstElementChild!;

    Object.defineProperty(overlay, 'getBoundingClientRect', {
      value: () => ({ left: 0, top: 0, width: 200, height: 100, right: 200, bottom: 100 }),
    });

    fireEvent.touchStart(overlay, {
      touches: [{ clientX: 100, clientY: 50 }],
    });
    expect(onCropChange).toHaveBeenCalled();
  });

  it('supports keyboard crop adjustment', async () => {
    const user = userEvent.setup();
    const onCropChange = vi.fn();
    render(<VideoOverlay {...baseProps} onCropChange={onCropChange} />);

    const cropControl = screen.getByRole('slider');
    cropControl.focus();
    await user.keyboard('{ArrowRight}');
    expect(onCropChange).toHaveBeenCalled();
  });
});
