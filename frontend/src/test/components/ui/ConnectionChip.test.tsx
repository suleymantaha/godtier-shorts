import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ConnectionChip } from '../../../components/ui/ConnectionChip';
import type { WsStatus } from '../../../types';

describe('ConnectionChip', () => {
  const cases: Array<{ status: WsStatus; expectedText: RegExp }> = [
    { status: 'connected',    expectedText: /online/i },
    { status: 'connecting',   expectedText: /connecting/i },
    { status: 'reconnecting', expectedText: /reconnecting/i },
    { status: 'disconnected', expectedText: /backend:offline/i },
  ];

  cases.forEach(({ status, expectedText }) => {
    it(`renders "${status}" state correctly`, () => {
      render(<ConnectionChip status={status} />);
      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByText(expectedText)).toBeInTheDocument();
    });
  });

  it('has aria-live for screen readers', () => {
    render(<ConnectionChip status="disconnected" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
  });

  it('shows auth paused instead of backend offline when websocket is intentionally stopped', () => {
    render(
      <ConnectionChip
        backendAuthStatus="paused"
        isOnline
        pauseReason="auth_provider_unavailable"
        status="disconnected"
      />,
    );

    expect(screen.getByText(/auth:paused/i)).toBeInTheDocument();
  });

  it('shows auth expired when the token refresh flow is paused by expiry', () => {
    render(
      <ConnectionChip
        backendAuthStatus="paused"
        isOnline
        pauseReason="token_expired"
        status="disconnected"
      />,
    );

    expect(screen.getByText(/auth:expired/i)).toBeInTheDocument();
  });

  it('shows network offline when the browser is offline', () => {
    render(
      <ConnectionChip
        backendAuthStatus="paused"
        isOnline={false}
        pauseReason="network_offline"
        status="disconnected"
      />,
    );

    expect(screen.getByText(/network:offline/i)).toBeInTheDocument();
  });
});
