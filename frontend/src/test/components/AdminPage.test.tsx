import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const getOverview = vi.fn();
const adjustCredit = vi.fn();
const getEconomics = vi.fn();

vi.mock('../../api/admin', () => ({
  adminApi: {
    getOverview: (...args: unknown[]) => getOverview(...args),
    getEconomics: (...args: unknown[]) => getEconomics(...args),
    adjustCredit: (...args: unknown[]) => adjustCredit(...args),
    suspendUser: vi.fn(),
    syncSubscription: vi.fn(),
    retryJob: vi.fn(),
  },
}));

describe('AdminPage', () => {
  beforeEach(() => {
    getOverview.mockReset();
    adjustCredit.mockReset();
    getEconomics.mockReset();
    getOverview.mockResolvedValue({ users: 10, subscriptions: 4, jobs: 20, failed_jobs: 2, risk_events: 3 });
    adjustCredit.mockResolvedValue({ available_credits: 125 });
    getEconomics.mockResolvedValue({ total_jobs: 20, success_rate: 0.9, review_required_rate: 0.1, cost_per_source_hour_usd: '1.25', cost_per_short_usd: '0.22', average_queue_wait_seconds: 8, average_render_seconds: 45 });
  });

  it('shows operational totals and requires a reason for credit adjustments', async () => {
    const { AdminPage } = await import('../../pages/AdminPage');
    const user = userEvent.setup();
    render(<AdminPage />);

    expect(await screen.findByText('20')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Kullanıcı ID'), '00000000-0000-0000-0000-000000000010');
    await user.clear(screen.getByLabelText('Kredi miktarı'));
    await user.type(screen.getByLabelText('Kredi miktarı'), '25');
    await user.type(screen.getByLabelText('İşlem nedeni'), 'Confirmed customer correction');
    await user.click(screen.getByRole('button', { name: 'Krediyi düzelt' }));

    expect(adjustCredit).toHaveBeenCalledWith(
      '00000000-0000-0000-0000-000000000010',
      25,
      'Confirmed customer correction',
    );
    expect(await screen.findByText('Yeni kullanılabilir bakiye: 125')).toBeInTheDocument();
  });
});
