import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { BillingAccount } from '../../types/billing';

const getAccountMock = vi.fn();
const cancelMock = vi.fn();
const checkoutMock = vi.fn();
const changePlanMock = vi.fn();

vi.mock('../../api/billing', () => ({
  billingApi: {
    getAccount: (...args: unknown[]) => getAccountMock(...args),
    cancel: (...args: unknown[]) => cancelMock(...args),
    checkout: (...args: unknown[]) => checkoutMock(...args),
    changePlan: (...args: unknown[]) => changePlanMock(...args),
  },
}));

const account: BillingAccount = {
  subscription: {
    plan: {
      code: 'creator', name: 'Creator', monthly_price_minor: 9_900, currency: 'TRY',
      monthly_compute_credits: 1_000, max_source_minutes_per_job: 60,
      max_clips_per_job: 10, max_active_jobs: 2, retention_days: 30,
    },
    interval: 'monthly', status: 'past_due', entitlement_active: false,
    period_start: '2026-08-01T00:00:00Z', period_end: '2026-09-01T00:00:00Z',
    cancel_at_period_end: false, grace_until: null,
  },
  plans: [{
    code: 'creator', name: 'Creator', monthly_price_minor: 9_900, currency: 'TRY',
    monthly_compute_credits: 1_000, max_source_minutes_per_job: 60,
    max_clips_per_job: 10, max_active_jobs: 2, retention_days: 30,
  }, {
    code: 'pro', name: 'Pro', monthly_price_minor: 19_900, currency: 'TRY',
    monthly_compute_credits: 2_500, max_source_minutes_per_job: 120,
    max_clips_per_job: 20, max_active_jobs: 4, retention_days: 60,
  }],
  usage: {
    current_period_source_seconds: 7_200, source_seconds_per_job_limit: 3_600,
    compute_credits_used: 250, compute_credits_available: 750, compute_credits_reserved: 25,
  },
  payments: [{ id: 'pay-1', amount_minor: 9_900, currency: 'TRY', status: 'succeeded', created_at: '2026-08-05T10:00:00Z' }],
};

describe('BillingPage', () => {
  beforeEach(() => {
    getAccountMock.mockReset().mockResolvedValue(account);
    cancelMock.mockReset().mockResolvedValue({ status: 'cancelled' });
    checkoutMock.mockReset();
    changePlanMock.mockReset();
    window.history.replaceState({}, '', '/?tab=billing&success=true');
  });

  it('treats checkout return parameters only as a refresh signal', async () => {
    const { BillingPage } = await import('../../pages/BillingPage');
    render(<BillingPage />);

    expect((await screen.findAllByText('Ödeme gecikmiş')).length).toBeGreaterThan(0);
    expect(screen.queryByText('Ödeme başarılı')).not.toBeInTheDocument();
    expect(getAccountMock).toHaveBeenCalledTimes(1);
    expect(screen.getByText('750')).toBeInTheDocument();
    expect(screen.getAllByText('₺99,00').length).toBeGreaterThan(0);
  });

  it('cancels through the backend and reloads the authoritative account', async () => {
    const { BillingPage } = await import('../../pages/BillingPage');
    const user = userEvent.setup();
    render(<BillingPage />);

    await user.click(await screen.findByRole('button', { name: 'Aboneliği iptal et' }));

    await waitFor(() => expect(cancelMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(getAccountMock).toHaveBeenCalledTimes(2));
  });

  it('changes an active subscription through the backend provider flow', async () => {
    const { BillingPage } = await import('../../pages/BillingPage');
    const user = userEvent.setup();
    render(<BillingPage />);

    await user.click((await screen.findAllByRole('button', { name: /Bu plana geç/ }))[0]);

    await waitFor(() => expect(changePlanMock).toHaveBeenCalledWith('pro', 'monthly'));
    await waitFor(() => expect(getAccountMock).toHaveBeenCalledTimes(2));
  });
});
