import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { VideoOverlay } from '../../components/VideoOverlay';

const baseProps = {
  currentTime: 1.5,
  transcript: [{
    text: 'Hello there',
    start: 1,
    end: 2,
    words: [
      { word: 'Hello', start: 1, end: 1.4 },
      { word: 'there', start: 1.4, end: 1.8 },
    ],
  }],
  style: 'TIKTOK' as const,
  centerX: 0.5,
  onCropChange: vi.fn(),
};

describe('VideoOverlay', () => {
  it('shows current subtitle text', () => {
    render(<VideoOverlay {...baseProps} />);
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('there')).toBeInTheDocument();
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

  it('uses split gutter safe area when layout is split', () => {
    render(<VideoOverlay {...baseProps} layout="split" />);
    const subtitle = screen.getByText('Hello').parentElement?.parentElement?.parentElement;
    expect(subtitle).toHaveStyle({ top: '45%' });
  });

  it('renders split subtitles as two lines when the chunk is too wide', () => {
    render(
      <VideoOverlay
        {...baseProps}
        layout="split"
        transcript={[{
          text: 'mekanlarımızda, makamlarımızda',
          start: 1,
          end: 3,
          words: [
            { word: 'mekanlarımızda,', start: 1, end: 1.9 },
            { word: 'makamlarımızda', start: 1.95, end: 2.9 },
          ],
        }]}
      />,
    );

    expect(screen.getByTestId('live-subtitle-line-0')).toBeInTheDocument();
    expect(screen.getByTestId('live-subtitle-line-1')).toBeInTheDocument();
  });

  it('uses lower-third safe area when requested', () => {
    render(<VideoOverlay {...baseProps} safeAreaProfile="lower_third_safe" />);
    const subtitle = screen.getByText('Hello').parentElement?.parentElement?.parentElement;
    expect(subtitle).toHaveStyle({ bottom: '22%' });
  });
});
