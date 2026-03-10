import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { IconButton } from '../../../components/ui/IconButton';

function PlusIcon() {
  return <svg data-testid="icon" />;
}

describe('IconButton', () => {
  it('renders as button with aria-label', () => {
    render(<IconButton label="Add item" icon={<PlusIcon />} onClick={() => {}} />);
    const btn = screen.getByRole('button', { name: 'Add item' });
    expect(btn).toBeInTheDocument();
  });

  it('renders as anchor when href is provided', () => {
    render(<IconButton label="Download" icon={<PlusIcon />} href="/file.mp4" />);
    const link = screen.getByRole('link', { name: 'Download' });
    expect(link).toHaveAttribute('href', '/file.mp4');
  });

  it('fires onClick', async () => {
    const user = userEvent.setup();
    const handler = vi.fn();
    render(<IconButton label="Click me" icon={<PlusIcon />} onClick={handler} />);
    await user.click(screen.getByRole('button', { name: 'Click me' }));
    expect(handler).toHaveBeenCalledOnce();
  });

  it('has minimum 40px touch target', () => {
    render(<IconButton label="Tap me" icon={<PlusIcon />} onClick={() => {}} />);
    const btn = screen.getByRole('button', { name: 'Tap me' });
    expect(btn.className).toContain('min-w-[40px]');
    expect(btn.className).toContain('min-h-[40px]');
  });
});
