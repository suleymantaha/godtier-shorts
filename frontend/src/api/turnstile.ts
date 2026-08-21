import { API_BASE } from '../config';


export const turnstileApi = {
  async verifySignup(token: string): Promise<{ verified: boolean }> {
    const response = await fetch(`${API_BASE}/api/security/turnstile/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, action: 'signup' }),
    });
    if (!response.ok) {
      throw new Error('Security verification failed. Please try again.');
    }
    return response.json() as Promise<{ verified: boolean }>;
  },
};
