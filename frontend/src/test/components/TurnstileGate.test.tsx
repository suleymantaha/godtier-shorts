import { render, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { TurnstileGate } from '../../components/security/TurnstileGate';


describe('TurnstileGate', () => {
  it('emits a token and clears it when Cloudflare expires the challenge', async () => {
    const onToken = vi.fn();
    const remove = vi.fn();
    const renderWidget = vi.fn((_container, options) => {
      options.callback('browser-token');
      options['expired-callback']();
      return 'widget-1';
    });
    window.turnstile = { render: renderWidget, remove, reset: vi.fn() };

    const { unmount } = render(
      <TurnstileGate action="preview_analyze" onToken={onToken} siteKey="public-site-key" />,
    );

    await waitFor(() => expect(renderWidget).toHaveBeenCalled());
    expect(onToken).toHaveBeenNthCalledWith(1, 'browser-token');
    expect(onToken).toHaveBeenNthCalledWith(2, null);
    unmount();
    expect(remove).toHaveBeenCalledWith('widget-1');
  });
});
