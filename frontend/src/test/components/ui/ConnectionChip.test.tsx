import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ConnectionChip } from '../../../components/ui/ConnectionChip';
import type { WsStatus } from '../../../types';

describe('ConnectionChip', () => {
  const cases: Array<{ status: WsStatus; expectedText: RegExp }> = [
    { status: 'connected',    expectedText: /online/i },
    { status: 'connecting',   expectedText: /connecting/i },
    { status: 'reconnecting', expectedText: /reconnecting/i },
    { status: 'disconnected', expectedText: /offline/i },
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
});
