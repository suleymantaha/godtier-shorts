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
});
