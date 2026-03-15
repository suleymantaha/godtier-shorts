import { beforeEach, describe, expect, it, vi } from 'vitest';

function createToken(expSecondsFromNow: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + expSecondsFromNow }));

  return `${header}.${payload}.signature`;
}

function createJsonResponse(body: unknown, status = 200): Response {
  return {
    json: async () => body,
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as Response;
}

async function loadClientModule() {
  vi.resetModules();
  return import('../../api/client');
}

describe('api client auth flow', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    Object.defineProperty(window.navigator, 'onLine', {
      configurable: true,
      value: true,
    });
    delete (window as Window & { Clerk?: unknown }).Clerk;
  });

  it('builds request headers from the freshest token instead of the stale active token', async () => {
    const freshToken = createToken(300);
    const getToken = vi.fn().mockResolvedValue(freshToken);
    (window as Window & { Clerk?: unknown }).Clerk = {
      session: { getToken },
    };
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(createJsonResponse({ jobs: [] }));

    const client = await loadClientModule();

    await client.jobsApi.list();

    expect(getToken).toHaveBeenCalledTimes(1);
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/jobs',
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: `Bearer ${freshToken}`,
          'Content-Type': 'application/json',
        }),
      }),
    );
  });

  it('shares a single refresh promise across concurrent protected requests', async () => {
    let resolveToken: ((token: string) => void) | null = null;
    const tokenPromise = new Promise<string>((resolve) => {
      resolveToken = resolve;
    });
    const getToken = vi.fn().mockReturnValue(tokenPromise);
    (window as Window & { Clerk?: unknown }).Clerk = {
      session: { getToken },
    };
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(createJsonResponse({ jobs: [] }));

    const client = await loadClientModule();

    const pending = Promise.all([client.jobsApi.list(), client.jobsApi.list()]);
    await Promise.resolve();

    expect(getToken).toHaveBeenCalledTimes(1);
    expect(fetchSpy).not.toHaveBeenCalled();

    resolveToken?.(createToken(300));
    await pending;

    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it('retries a token_expired response once with a forced token refresh', async () => {
    const staleToken = createToken(300);
    const refreshedToken = createToken(600);
    const getToken = vi.fn()
      .mockResolvedValueOnce(staleToken)
      .mockResolvedValueOnce(refreshedToken);
    (window as Window & { Clerk?: unknown }).Clerk = {
      session: { getToken },
    };
    const fetchSpy = vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce(
        createJsonResponse({
          detail: { error: { code: 'token_expired', message: 'expired' } },
        }, 401),
      )
      .mockResolvedValueOnce(createJsonResponse({ jobs: [] }));

    const client = await loadClientModule();

    await expect(client.jobsApi.list()).resolves.toEqual({ jobs: [] });

    expect(getToken).toHaveBeenCalledTimes(2);
    expect(fetchSpy).toHaveBeenNthCalledWith(
      1,
      'http://localhost:8000/api/jobs',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${staleToken}` }),
      }),
    );
    expect(fetchSpy).toHaveBeenNthCalledWith(
      2,
      'http://localhost:8000/api/jobs',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: `Bearer ${refreshedToken}` }),
      }),
    );
  });

  it('fails after a forced refresh error without replaying the request twice', async () => {
    const staleToken = createToken(300);
    const getToken = vi.fn()
      .mockResolvedValueOnce(staleToken)
      .mockRejectedValueOnce(new Error('clerk down'));
    (window as Window & { Clerk?: unknown }).Clerk = {
      session: { getToken },
    };
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(
      createJsonResponse({
        detail: { error: { code: 'token_expired', message: 'expired' } },
      }, 401),
    );

    const client = await loadClientModule();

    await expect(client.jobsApi.list()).rejects.toMatchObject({
      code: 'auth_provider_unavailable',
    });

    expect(getToken).toHaveBeenCalledTimes(2);
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it('maps ownership-style 404 responses to a generic unavailable resource message', async () => {
    const token = createToken(300);
    const getToken = vi.fn().mockResolvedValue(token);
    (window as Window & { Clerk?: unknown }).Clerk = {
      session: { getToken },
    };
    vi.spyOn(global, 'fetch').mockResolvedValue(
      createJsonResponse({
        detail: { code: 'HTTP_404', message: 'HTTP error', details: 'Kaynak bulunamadı' },
      }, 404),
    );

    const client = await loadClientModule();

    await expect(client.jobsApi.list()).rejects.toMatchObject({
      code: 'unknown',
      message: 'Istenen kaynak su anda kullanilamiyor.',
      status: 404,
    });
  });

  it('sends the account deletion confirmation payload with DELETE', async () => {
    const token = createToken(300);
    const getToken = vi.fn().mockResolvedValue(token);
    (window as Window & { Clerk?: unknown }).Clerk = {
      session: { getToken },
    };
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue(
      createJsonResponse({
        status: 'purged',
        summary: {
          deleted_projects: 1,
          deleted_social_rows: 0,
          cancelled_jobs: 0,
          closed_websockets: 0,
          scrubbed_grants: 0,
        },
      }),
    );

    const client = await loadClientModule();

    await expect(client.accountApi.deleteMyData()).resolves.toMatchObject({ status: 'purged' });
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8000/api/account/me/data',
      expect.objectContaining({
        method: 'DELETE',
        body: JSON.stringify({ confirm: 'DELETE' }),
        headers: expect.objectContaining({
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        }),
      }),
    );
  });
});
