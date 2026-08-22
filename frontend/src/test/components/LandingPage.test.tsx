import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { LandingPage } from '../../pages/LandingPage';
import { PENDING_PREVIEW_URL_KEY } from '../../marketing/funnel';

describe('LandingPage', () => {
  beforeEach(() => sessionStorage.clear());
  it('captures the YouTube URL before signup and explains the three-step promise', async () => {
    const onStart = vi.fn();
    const user = userEvent.setup();
    render(<LandingPage onStart={onStart} />);

    await user.type(screen.getByLabelText(/youtube video url/i), 'https://youtu.be/abc123DEF45');
    await user.click(screen.getByRole('button', { name: /youtube linkini yapıştır/i }));

    expect(sessionStorage.getItem(PENDING_PREVIEW_URL_KEY)).toBe('https://youtu.be/abc123DEF45');
    expect(onStart).toHaveBeenCalledOnce();
    expect(screen.getAllByTestId('product-step')).toHaveLength(3);
    expect(screen.getByText('Creator')).toBeInTheDocument();
  });
});
