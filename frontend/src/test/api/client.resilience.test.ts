import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AUTH_IDENTITY_STORAGE_KEY, syncIdentityBoundary } from '../../auth/isolation';

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

async function client() {
  vi.resetModules();
  const module = await import('../../api/client');
  module.setApiToken('test-token');
  return module;
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem(AUTH_IDENTITY_STORAGE_KEY, 'user-a');
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe('request replay safety', () => {
  it.each(['network', 'server', 'timeout'])('does not replay a POST after %s failure', async (failure) => {
    const api = await client();
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    if (failure === 'server') fetchMock.mockResolvedValue(response({}, 500));
    else fetchMock.mockRejectedValue(failure === 'timeout'
      ? new DOMException('aborted', 'AbortError') : new TypeError('connection lost'));

    await expect(api.apiFetch('/api/process-manual', { method: 'POST', body: '{}' })).rejects.toBeDefined();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('keeps transient retries for GET requests', async () => {
    const api = await client();
    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(response({}, 500)).mockResolvedValueOnce(response({ jobs: [] }));
    await expect(api.jobsApi.list()).resolves.toEqual({ jobs: [] });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe('project cache ownership', () => {
  it('never falls back to another account or legacy unscoped cache', async () => {
    const api = await client();
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({ projects: [{ id: 'private-a' }] }));
    await api.editorApi.getProjects();
    localStorage.setItem('gts:projects-cache:v1', JSON.stringify([{ id: 'legacy-a' }]));
    localStorage.setItem(AUTH_IDENTITY_STORAGE_KEY, 'user-b');
    fetchMock.mockResolvedValue(response({}, 404));
    expect((await api.editorApi.getProjects()).projects).toEqual([]);
  });

  it('discards an in-flight result after identity changes', async () => {
    const api = await client();
    let resolve!: (value: Response) => void;
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise((done) => { resolve = done; }));
    const pending = api.editorApi.getProjects();
    await vi.waitFor(() => expect(resolve).toBeDefined());
    localStorage.setItem(AUTH_IDENTITY_STORAGE_KEY, 'user-b');
    resolve(response({ projects: [{ id: 'private-a' }] }));
    expect((await pending).projects).toEqual([]);
    expect(localStorage.getItem('gts:projects-cache:v2:user-b')).toBeNull();
  });

  it('clears both scoped and legacy cache on account switch', () => {
    localStorage.setItem('gts:projects-cache:v1', '[]');
    localStorage.setItem('gts:projects-cache:v2:user-a', '[]');
    syncIdentityBoundary('user-b');
    expect(localStorage.getItem('gts:projects-cache:v1')).toBeNull();
    expect(localStorage.getItem('gts:projects-cache:v2:user-a')).toBeNull();
  });
});

describe('multipart timeout policy', () => {
  it('allows callers to cancel an upload without replaying it', async () => {
    const api = await client();
    const controller = new AbortController();
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('cancelled', 'AbortError')));
    }));
    const pending = api.clipsApi.upload(new File(['video'], 'video.mp4'), controller.signal);
    const rejected = expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    controller.abort();
    await rejected;
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('retains the deadline for ordinary JSON mutations', async () => {
    const api = await client();
    vi.useFakeTimers();
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
    }));
    const rejected = expect(api.apiFetch('/api/process-manual', { method: 'POST' }))
      .rejects.toMatchObject({ code: 'network_timeout' });
    await vi.advanceTimersByTimeAsync(16000);
    await rejected;
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each(['upload', 'manual'])('allows %s uploads beyond the regular request deadline', async (kind) => {
    const api = await client();
    vi.useFakeTimers();
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => new Promise((resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')));
      window.setTimeout(() => resolve(response({ status: 'queued', job_id: 'one' })), 32000);
    }));
    const file = new File(['video'], 'video.mp4');
    const pending = kind === 'upload' ? api.clipsApi.upload(file)
      : api.editorApi.manualCutUpload(file, { start_time: 0, end_time: 10 });
    const settled = pending.then((value) => ({ value }), (error: unknown) => ({ error }));
    await vi.advanceTimersByTimeAsync(33000);
    expect(await settled).toEqual({ value: { status: 'queued', job_id: 'one' } });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
