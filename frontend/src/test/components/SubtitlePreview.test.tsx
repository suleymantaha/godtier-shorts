import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { SubtitlePreview } from '../../components/SubtitlePreview';

describe('SubtitlePreview', () => {
  it('renders preview words with correct colors for HORMOZI', () => {
    render(<SubtitlePreview styleName="HORMOZI" disabled={false} />);

    const highlightWord = screen.getByText('ornek');
    expect(highlightWord).toBeInTheDocument();
    expect(highlightWord.style.color).toBe('rgb(255, 255, 0)');

    const primaryWord = screen.getByText('Bu');
    expect(primaryWord.style.color).toBe('rgb(255, 255, 255)');
  });

  it('renders TIKTOK highlight as magenta', () => {
    render(<SubtitlePreview styleName="TIKTOK" disabled={false} />);

    const highlightWord = screen.getByText('ornek');
    expect(highlightWord.style.color).toBe('rgb(255, 0, 255)');
  });

  it('renders MRBEAST highlight as green', () => {
    render(<SubtitlePreview styleName="MRBEAST" disabled={false} />);

    const highlightWord = screen.getByText('ornek');
    expect(highlightWord.style.color).toBe('rgb(0, 255, 0)');
  });

  it('shows disabled message when disabled is true', () => {
    render(<SubtitlePreview styleName="HORMOZI" disabled={true} />);

    expect(screen.getByText(/altyazi devre disi/i)).toBeInTheDocument();
    expect(screen.queryByText('ornek')).not.toBeInTheDocument();
  });

  it('renders inside a glass-card container', () => {
    const { container } = render(<SubtitlePreview styleName="MRBEAST" disabled={false} />);

    expect(container.querySelector('.glass-card')).toBeInTheDocument();
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
    expect(screen.getByText('Yuksek Kontrast')).toBeInTheDocument();
  });

  it('applies text-shadow for outline styles', () => {
    render(<SubtitlePreview styleName="HORMOZI" disabled={false} />);

    const word = screen.getByText('Bu');
    expect(word.style.textShadow).not.toBe('none');
    expect(word.style.textShadow).toContain('0');
  });
});
