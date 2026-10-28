import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AccountDeletionCard } from '../components/AccountDeletionCard';

const deleteMyDataMock = vi.fn();
const clearClientAccountStateMock = vi.fn();
const hardReloadPageMock = vi.fn();
const userDeleteMock = vi.fn();

vi.mock('@clerk/clerk-react', () => ({
  useUser: () => ({
    user: {
      delete: userDeleteMock,
    },
  }),
}));

vi.mock('../api/client', () => ({
  accountApi: {
    deleteMyData: (...args: unknown[]) => deleteMyDataMock(...args),
  },
}));

vi.mock('../auth/accountCleanup', () => ({
  clearClientAccountState: () => clearClientAccountStateMock(),
  hardReloadPage: () => hardReloadPageMock(),
}));

describe('AccountDeletionCard', () => {
  beforeEach(() => {
    deleteMyDataMock.mockReset();
    clearClientAccountStateMock.mockReset();
    hardReloadPageMock.mockReset();
    userDeleteMock.mockReset();
  });

  it('keeps deletion disabled until the typed confirmation matches DELETE', () => {
    render(<AccountDeletionCard />);

    const deleteButton = screen.getByRole('button', { name: /delete account/i });
    expect(deleteButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/delete account confirmation/i), {
      target: { value: 'DELETE' },
    });

    expect(deleteButton).toBeEnabled();
  });

  it('purges backend data first, then deletes the Clerk user, clears client state and reloads', async () => {
    deleteMyDataMock.mockResolvedValue({
      status: 'purged',
      summary: { deleted_projects: 1 },
    });
    userDeleteMock.mockResolvedValue(undefined);

    render(<AccountDeletionCard />);

    fireEvent.change(screen.getByLabelText(/delete account confirmation/i), {
      target: { value: 'DELETE' },
    });
    fireEvent.click(screen.getByRole('button', { name: /delete account/i }));

    await waitFor(() => {
      expect(deleteMyDataMock).toHaveBeenCalledWith('DELETE');
      expect(userDeleteMock).toHaveBeenCalledTimes(1);
      expect(clearClientAccountStateMock).toHaveBeenCalledTimes(1);
      expect(hardReloadPageMock).toHaveBeenCalledTimes(1);
    });
  });

  it('shows a user-facing warning when Clerk deletion fails after backend purge and still clears client state', async () => {
    deleteMyDataMock.mockResolvedValue({
      status: 'purged',
      summary: { deleted_projects: 1 },
    });
    userDeleteMock.mockRejectedValue(new Error('delete failed'));

    render(<AccountDeletionCard />);

    fireEvent.change(screen.getByLabelText(/delete account confirmation/i), {
      target: { value: 'DELETE' },
    });
    fireEvent.click(screen.getByRole('button', { name: /delete account/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'App data was deleted, but account deletion could not be completed.',
    );
    expect(clearClientAccountStateMock).toHaveBeenCalledTimes(1);
    expect(hardReloadPageMock).not.toHaveBeenCalled();
  });

  it.each([
    ['upload_url_expiry', 'Wait at least 120 seconds'],
    ['storage_finalization_unverified', 'Deletion is pending'],
    ['subscription_cancellation_required', 'Cancel your active subscription'],
    ['future_pending_reason', 'Deletion is pending'],
  ])('keeps the signed-in account available for retry when deletion is pending: %s', async (reason, guidance) => {
    deleteMyDataMock.mockResolvedValue({
      status: 'deletion_pending',
      summary: { status: 'deletion_pending', reason, deletion_fenced: true, retry_after_seconds: 120 },
    });
    render(<AccountDeletionCard />);
    fireEvent.change(screen.getByLabelText(/delete account confirmation/i), { target: { value: 'DELETE' } });
    fireEvent.click(screen.getByRole('button', { name: /delete account/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(guidance);
    expect(screen.getByRole('button', { name: /retry data deletion/i })).toBeEnabled();
    expect(userDeleteMock).not.toHaveBeenCalled();
    expect(clearClientAccountStateMock).not.toHaveBeenCalled();
    expect(hardReloadPageMock).not.toHaveBeenCalled();
  });

  it('retries pending deletion and deletes the Clerk account only after a purged response', async () => {
    deleteMyDataMock.mockResolvedValueOnce({
      status: 'deletion_pending',
      summary: { status: 'deletion_pending', reason: 'storage_not_empty', deletion_fenced: true },
    }).mockResolvedValueOnce({ status: 'purged', summary: { deleted_projects: 1 } });
    userDeleteMock.mockResolvedValue(undefined);
    render(<AccountDeletionCard />);
    fireEvent.change(screen.getByLabelText(/delete account confirmation/i), { target: { value: 'DELETE' } });
    fireEvent.click(screen.getByRole('button', { name: /delete account/i }));
    fireEvent.click(await screen.findByRole('button', { name: /retry data deletion/i }));

    await waitFor(() => expect(hardReloadPageMock).toHaveBeenCalledTimes(1));
    expect(deleteMyDataMock).toHaveBeenCalledTimes(2);
    expect(userDeleteMock).toHaveBeenCalledTimes(1);
  });

  it('shows a retry failure without deleting the Clerk account or clearing its session', async () => {
    deleteMyDataMock.mockResolvedValueOnce({
      status: 'deletion_pending',
      summary: { status: 'deletion_pending', reason: 'worker_stop_unverified', deletion_fenced: true },
    }).mockRejectedValueOnce(new Error('Session must be refreshed'));
    render(<AccountDeletionCard />);
    fireEvent.change(screen.getByLabelText(/delete account confirmation/i), { target: { value: 'DELETE' } });
    fireEvent.click(screen.getByRole('button', { name: /delete account/i }));
    fireEvent.click(await screen.findByRole('button', { name: /retry data deletion/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Session must be refreshed');
    expect(userDeleteMock).not.toHaveBeenCalled();
    expect(clearClientAccountStateMock).not.toHaveBeenCalled();
    expect(hardReloadPageMock).not.toHaveBeenCalled();
  });

  it('can resubmit deletion after a remount and cleared local storage', async () => {
    deleteMyDataMock.mockResolvedValue({
      status: 'deletion_pending',
      summary: { status: 'deletion_pending', reason: 'storage_finalization_unverified', deletion_fenced: true },
    });
    const firstMount = render(<AccountDeletionCard />);
    fireEvent.change(screen.getByLabelText(/delete account confirmation/i), { target: { value: 'DELETE' } });
    fireEvent.click(screen.getByRole('button', { name: /delete account/i }));
    await screen.findByRole('button', { name: /retry data deletion/i });
    firstMount.unmount();
    localStorage.clear();
    render(<AccountDeletionCard />);
    fireEvent.change(screen.getByLabelText(/delete account confirmation/i), { target: { value: 'DELETE' } });
    fireEvent.click(screen.getByRole('button', { name: /delete account/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Deletion is pending');
    expect(deleteMyDataMock).toHaveBeenCalledTimes(2);
    expect(userDeleteMock).not.toHaveBeenCalled();
    expect(clearClientAccountStateMock).not.toHaveBeenCalled();
    expect(hardReloadPageMock).not.toHaveBeenCalled();
  });
});
