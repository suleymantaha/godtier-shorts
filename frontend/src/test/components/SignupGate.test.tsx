import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

const verifySignup = vi.fn();

vi.mock('@clerk/clerk-react', () => ({
  SignIn: () => <div>SignIn</div>,
  SignUp: () => <div>SignUp</div>,
  UserButton: () => <div>UserButton</div>,
}));

vi.mock('../../api/turnstile', () => ({
  turnstileApi: { verifySignup: (...args: unknown[]) => verifySignup(...args) },
}));

vi.mock('../../components/security/TurnstileGate', () => ({
  TurnstileGate: ({ onToken }: { onToken: (token: string) => void }) => (
    <button type="button" onClick={() => onToken('signup-token')}>Verify signup</button>
  ),
}));

describe('signup Turnstile gate', () => {
  it('shows Clerk SignUp only after backend verification', async () => {
    window.history.replaceState({}, '', '/sign-up');
    verifySignup.mockResolvedValue({ verified: true });
    const { SignedOutScreen } = await import('../../app/sections');
    render(<SignedOutScreen />);

    expect(screen.queryByText('SignUp')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Verify signup' }));

    expect(await screen.findByText('SignUp')).toBeInTheDocument();
    expect(verifySignup).toHaveBeenCalledWith('signup-token');
  });
});
