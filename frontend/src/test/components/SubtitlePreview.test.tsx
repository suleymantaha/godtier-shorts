import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { SubtitlePreview } from '../../components/SubtitlePreview';

afterEach(() => {
  vi.useRealTimers();
});

describe('SubtitlePreview base rendering', () => {
  it('renders preview words with correct colors for HORMOZI', () => {
    render(<SubtitlePreview styleName="HORMOZI" disabled={false} />);

    const highlightWord = screen.getByText('Bu');
    expect(highlightWord).toBeInTheDocument();
    expect(highlightWord.style.color).toBe('rgb(255, 255, 0)');

    const primaryWord = screen.getByText('bir');
    expect(primaryWord.style.color).toBe('rgb(255, 255, 255)');
  });

  it('renders TIKTOK highlight as magenta', () => {
    render(<SubtitlePreview styleName="TIKTOK" disabled={false} />);

    const highlightWord = screen.getByText('Bu');
    expect(highlightWord.style.color).toBe('rgb(255, 0, 255)');
  });

  it('renders MRBEAST highlight as green', () => {
    render(<SubtitlePreview styleName="MRBEAST" disabled={false} />);

    const highlightWord = screen.getByText('Bu');
    expect(highlightWord.style.color).toBe('rgb(0, 255, 0)');
  });

  it('keeps the shell visible and shows a disabled overlay when subtitles are off', () => {
    render(<SubtitlePreview styleName="HORMOZI" disabled={true} />);

    expect(screen.getByTestId('subtitle-preview-disabled')).toBeInTheDocument();
    expect(screen.getByLabelText('subtitle-preview-stage')).toBeInTheDocument();
    expect(screen.queryByText('demo')).not.toBeInTheDocument();
  });

  it('renders inside a glass-card container', () => {
    const { container } = render(<SubtitlePreview styleName="MRBEAST" disabled={false} />);

    expect(container.querySelector('.glass-card')).toBeInTheDocument();
    expect(screen.getByLabelText('subtitle-preview-stage')).toBeInTheDocument();
  });

  it('uses backend-matched font family for Montserrat styles', () => {
    render(<SubtitlePreview styleName="HORMOZI" disabled={false} />);

    const word = screen.getByText('Bu');
    expect(word.style.fontFamily).toContain('Montserrat');
  });

  it('shows color swatches for primary and highlight', () => {
    render(<SubtitlePreview styleName="TIKTOK" disabled={false} />);

    expect(screen.getByText('primary')).toBeInTheDocument();
    expect(screen.getByText('highlight')).toBeInTheDocument();
  });

  it('hides highlight swatch when colors match', () => {
    render(<SubtitlePreview styleName="CORPORATE" disabled={false} />);

    expect(screen.getByText('primary')).toBeInTheDocument();
    expect(screen.queryByText('highlight')).not.toBeInTheDocument();
  });

  it('shows style label when not disabled', () => {
    render(<SubtitlePreview styleName="HIGHCARE" disabled={false} />);
    expect(screen.getByText('High Contrast')).toBeInTheDocument();
  });
});

describe('SubtitlePreview layout and shell variants', () => {
  it('applies text-shadow for outline styles', () => {
    render(<SubtitlePreview styleName="HORMOZI" disabled={false} />);

    const word = screen.getByText('Bu');
    expect(word.style.textShadow).not.toBe('none');
    expect(word.style.textShadow).toContain('0');
  });

  it('can render a split-layout preview box', () => {
    render(<SubtitlePreview styleName="TIKTOK" disabled={false} layout="split" />);
    const stage = screen.getByLabelText('subtitle-preview-stage');
    expect(stage).toBeInTheDocument();
    expect(screen.getByText('Bu')).toBeInTheDocument();
  });

  it('renders split preview demo words across two lines when the planning helper breaks them', () => {
    render(<SubtitlePreview styleName="HORMOZI" disabled={false} layout="split" />);

    expect(screen.getByTestId('subtitle-preview-line-0')).toBeInTheDocument();
    expect(screen.getByTestId('subtitle-preview-line-1')).toBeInTheDocument();
  });

  it('moves preview subtitles upward when lower-third safe area is active', () => {
    render(<SubtitlePreview styleName="TIKTOK" disabled={false} safeAreaProfile="lower_third_safe" />);
    const stage = screen.getByLabelText('subtitle-preview-stage');
    const band = stage.querySelector('div[style*="bottom: 10.5%"]');
    expect(band).toBeInTheDocument();
  });

  it('uses a phone shell for short previews and a landscape shell otherwise', () => {
    const { rerender } = render(<SubtitlePreview styleName="TIKTOK" cutAsShort={true} disabled={false} />);
    expect(screen.getByLabelText('subtitle-preview-stage')).toHaveAttribute('data-shell-type', 'phone');

    rerender(<SubtitlePreview styleName="TIKTOK" cutAsShort={false} disabled={false} />);
    expect(screen.getByLabelText('subtitle-preview-stage')).toHaveAttribute('data-shell-type', 'landscape');
  });

  it('can render as a device-only preview without the glass card chrome', () => {
    const { container } = render(<SubtitlePreview styleName="TIKTOK" disabled={false} variant="device" showLegend={false} />);
    const stage = screen.getByLabelText('subtitle-preview-stage');

    expect(container.querySelector('.glass-card')).not.toBeInTheDocument();
    expect(stage).toHaveAttribute('data-shell-type', 'phone');
    expect(stage).toHaveAttribute('data-preview-size', 'default');
    expect(stage.className).toContain('h-[clamp(380px,46vw,500px)]');
    expect(screen.queryByText('primary')).not.toBeInTheDocument();
  });

  it('uses the compact device sizing for config preview layouts', () => {
    render(<SubtitlePreview styleName="TIKTOK" disabled={false} variant="device" size="compact" showLegend={false} />);
    const stage = screen.getByLabelText('subtitle-preview-stage');

    expect(stage).toHaveAttribute('data-preview-size', 'compact');
    expect(stage.className).toContain('h-[clamp(320px,34vw,420px)]');
    expect(stage.className).toContain('lg:h-full');
  });

  it('supports the tall device sizing for stacked config layouts', () => {
    render(<SubtitlePreview styleName="TIKTOK" disabled={false} variant="device" size="tall" showLegend={false} />);
    const stage = screen.getByLabelText('subtitle-preview-stage');

    expect(stage).toHaveAttribute('data-preview-size', 'tall');
    expect(stage.className).toContain('h-[clamp(360px,66vw,520px)]');
    expect(stage.className).toContain('lg:h-full');
    expect(screen.queryByText('primary')).not.toBeInTheDocument();
  });
});

describe('SubtitlePreview motion and band styling', () => {
  it('keeps the preview subtitle band content-sized inside the phone shell', () => {
    render(<SubtitlePreview styleName="TIKTOK" disabled={false} variant="device" size="tall" showLegend={false} />);

    const band = screen.getByTestId('subtitle-preview-band');
    expect(band).toHaveAttribute('data-preview-band-mode', 'plain');
    expect(band.className).toContain('w-full');
    expect(band.className).toContain('max-w-full');
    expect(band.className).not.toContain('rounded-[20px]');
  });

  it('keeps a light plate for preview styles that actually use a background', () => {
    render(<SubtitlePreview styleName="YOUTUBE_SHORT" disabled={false} variant="device" size="tall" showLegend={false} />);

    const band = screen.getByTestId('subtitle-preview-band');
    expect(band).toHaveAttribute('data-preview-band-mode', 'bold_plate');
    expect(screen.getByText('Bu').parentElement?.parentElement?.className).toContain('rounded-[15px]');
  });

  it('uses style-specific preview plates for podcast, glass, and terminal styles', () => {
    const { rerender } = render(
      <SubtitlePreview styleName="PODCAST" disabled={false} variant="device" size="tall" showLegend={false} />,
    );

    let band = screen.getByTestId('subtitle-preview-band');
    expect(band).toHaveAttribute('data-preview-band-mode', 'soft_plate');
    expect(screen.getByText('Bu').parentElement?.parentElement?.className).toContain('rounded-[16px]');

    rerender(<SubtitlePreview styleName="GLASS_MORPH" disabled={false} variant="device" size="tall" showLegend={false} />);
    band = screen.getByTestId('subtitle-preview-band');
    expect(band).toHaveAttribute('data-preview-band-mode', 'glass_plate');
    expect(screen.getByText('Bu').parentElement?.parentElement?.className).toContain('backdrop-blur-md');

    rerender(<SubtitlePreview styleName="HACKER_TERMINAL" disabled={false} variant="device" size="tall" showLegend={false} />);
    band = screen.getByTestId('subtitle-preview-band');
    expect(band).toHaveAttribute('data-preview-band-mode', 'terminal_plate');
    expect(screen.getByText('Bu').parentElement?.parentElement?.className).toContain('border-emerald-400/20');
  });
});

describe('SubtitlePreview motion animations', () => {
  it('applies motion-specific band animations so preview effects are distinguishable', () => {
    const { rerender } = render(
      <SubtitlePreview
        styleName="TIKTOK"
        animationType="slide_up"
        disabled={false}
        variant="device"
        size="tall"
        showLegend={false}
      />,
    );

    let band = screen.getByTestId('subtitle-preview-band');
    expect(band).toHaveAttribute('data-preview-motion', 'slide_up');
    expect(band.style.animation).toContain('preview-band-slide-up');

    rerender(
      <SubtitlePreview
        styleName="TIKTOK"
        animationType="shake"
        disabled={false}
        variant="device"
        size="tall"
        showLegend={false}
      />,
    );
    band = screen.getByTestId('subtitle-preview-band');
    expect(band).toHaveAttribute('data-preview-motion', 'shake');
    expect(band.style.animation).toContain('preview-band-shake');

    rerender(
      <SubtitlePreview
        styleName="TIKTOK"
        animationType="fade"
        disabled={false}
        variant="device"
        size="tall"
        showLegend={false}
      />,
    );
    band = screen.getByTestId('subtitle-preview-band');
    expect(band).toHaveAttribute('data-preview-motion', 'fade');
    expect(band.style.animation).toContain('preview-band-fade');
  });

  it('reveals words progressively for typewriter motion', () => {
    vi.useFakeTimers();
    render(
      <SubtitlePreview
        styleName="STORY_TELLER"
        animationType="typewriter"
        disabled={false}
        variant="device"
        size="tall"
        showLegend={false}
      />,
    );

    expect(screen.getByTestId('subtitle-preview-word-0').style.display).not.toBe('none');
    expect(screen.getByTestId('subtitle-preview-word-1').style.display).toBe('none');

    act(() => {
      vi.advanceTimersByTime(900);
    });

    expect(screen.getByTestId('subtitle-preview-word-1').style.display).not.toBe('none');
  });
});

describe('SubtitlePreview media and timer behavior', () => {
  it('renders a decorative media layer when videoSrc is provided', () => {
    render(<SubtitlePreview styleName="TIKTOK" disabled={false} videoSrc="blob:auto-cut" />);

    const media = screen.getByTestId('subtitle-preview-media');
    expect(media).toBeInTheDocument();
    expect(media).toHaveAttribute('src', 'blob:auto-cut');
  });

  it('advances the active word on a timer', () => {
    vi.useFakeTimers();
    render(<SubtitlePreview styleName="TIKTOK" disabled={false} />);

    expect(screen.getByTestId('subtitle-preview-word-0')).toHaveAttribute('data-active', 'true');
    act(() => {
      vi.advanceTimersByTime(750);
    });
    expect(screen.getByTestId('subtitle-preview-word-1')).toHaveAttribute('data-active', 'true');
  });
});
